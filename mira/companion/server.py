"""Mira Companion's HTTP server: the phone's only door into Mira.

Standard library only (asyncio on one private thread), so the desktop app gains no dependency.

What this module enforces, and why:
- It binds only to this computer's Tailscale address (100.64.0.0/10), or to 127.0.0.1 for tests
  and review. Never to the LAN or a wildcard address, and it never touches the firewall
  (firewalld already puts `tailscale0` in the trusted zone; the LAN zone stays closed).
- Every route that reads Mira's state or asks her to act needs the pairing token: either the
  `mira_session` cookie that /pair sets (an HMAC of the token; HttpOnly, SameSite=Strict) or
  `Authorization: Bearer <token>`. Comparisons are constant-time. Rotating the token invalidates
  every session at once and closes every open event stream.
- A request whose Host is not this server's own address is refused (DNS rebinding); a POST from
  another origin is refused (CSRF); bodies are capped at 16 KB; POSTs are rate limited per client
  and repeated authentication failures lock that client out for a minute.
- The phone has no computer-control route. It can type to Mira (her own brain, as on the
  desktop), start or stop the Echo, and use the Home controls with the desktop's validation.
  Every action answers `202 accepted`: what actually happened is what Mira reports afterwards
  on the event stream (her verified action cards, Home Assistant's read-back).
- Nothing logged here contains a token, a cookie, a query string or a message.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import errno
import hashlib
import hmac
import ipaddress
import json
import math
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, NamedTuple, Optional
from urllib.parse import parse_qs

from home_link import COLORS as HOME_COLORS

STATIC_DIR = Path(__file__).resolve().parent / 'static'
DEFAULT_PORT = 18770              # next to Mira's Echo model server (18769)
TAILNET = ipaddress.ip_network('100.64.0.0/10')
TAILSCALE_INTERFACE = 'tailscale0'
LOOPBACK = '127.0.0.1'

MAX_BODY = 16 * 1024
MAX_HEADER = 16 * 1024
MAX_HEADERS = 64
MAX_TEXT = 2000                    # a typed message from the phone
POSTS_PER_MINUTE = 20
AUTH_FAILURES_PER_MINUTE = 20
HEARTBEAT_S = 15.0
RECHECK_S = 30.0                   # is the Tailscale address still ours?
FIRST_REQUEST_S = 10.0
KEEPALIVE_S = 30.0
BODY_S = 10.0
WRITE_S = 10.0
MAX_CONNECTIONS = 48
MAX_CONNECTIONS_PER_IP = 16
MAX_STREAMS = 12
MAX_STREAMS_PER_IP = 4
STREAM_QUEUE = 256
COOKIE = 'mira_session'
COOKIE_MAX_AGE = 400 * 24 * 3600   # the longest browsers keep a cookie
SESSION_CONTEXT = b'mira-companion-session-v1'

ENTITY_RE = re.compile(r'(light|switch|media_player)\.[a-z0-9_]+')   # home_link.control's own rule
HOME_ACTIONS = ('turn_on', 'turn_off', 'brightness', 'color', 'volume', 'media_play', 'media_pause')
VALUE_ACTIONS = ('brightness', 'volume')
LIGHT_ONLY = ('brightness', 'color')
MEDIA_ONLY = ('volume', 'media_play', 'media_pause')
CAPABILITY = {'turn_on': 'on_capable', 'turn_off': 'off_capable', 'brightness': 'dimmable',
              'color': 'color_capable', 'volume': 'volume_capable', 'media_play': 'play_capable',
              'media_pause': 'pause_capable'}
# The desktop's swatch order (HomeSheet.qml); the names and colours are home_link.COLORS.
PALETTE = tuple({'name': name, 'color': '#%02X%02X%02X' % HOME_COLORS[name]}
                for name in ('pink', 'purple', 'blue', 'green', 'yellow', 'orange', 'red') if name in HOME_COLORS)

TOKEN_RE = re.compile(r'[A-Za-z0-9_-]{43,128}')
NAME_RE = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,62})(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}))*')
FACE_RE = re.compile(r'/face/([a-z]{2,12})/([a-z_]{2,24})\.(png|webp)')
METHOD_RE = re.compile(r'[A-Z]{3,8}')
HEADER_NAME_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
SINGLE_HEADERS = ('host', 'content-length', 'content-type', 'authorization', 'cookie', 'origin',
                  'transfer-encoding')
FACE_SIZES = (256, 512)
FACE_TYPES = {'png': 'image/png', 'webp': 'image/webp'}

STATIC_TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                '.css': 'text/css; charset=utf-8', '.webmanifest': 'application/manifest+json; charset=utf-8',
                '.png': 'image/png', '.svg': 'image/svg+xml', '.json': 'application/json; charset=utf-8'}
ICON_ALIASES = {'/apple-touch-icon.png': '/static/icons/apple-touch-icon.png',
                '/apple-touch-icon-precomposed.png': '/static/icons/apple-touch-icon.png',
                '/favicon.ico': '/static/icons/icon-192.png'}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; "
       "manifest-src 'self'; font-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
BASE_HEADERS = (('X-Content-Type-Options', 'nosniff'), ('Referrer-Policy', 'no-referrer'),
                ('X-Frame-Options', 'DENY'), ('Cross-Origin-Opener-Policy', 'same-origin'),
                ('Cross-Origin-Resource-Policy', 'same-origin'),
                ('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()'))
REASONS = {200: 'OK', 202: 'Accepted', 204: 'No Content', 303: 'See Other', 304: 'Not Modified',
           400: 'Bad Request', 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found',
           405: 'Method Not Allowed', 408: 'Request Timeout', 409: 'Conflict', 411: 'Length Required',
           413: 'Content Too Large', 415: 'Unsupported Media Type', 429: 'Too Many Requests',
           431: 'Request Header Fields Too Large', 500: 'Internal Server Error', 503: 'Service Unavailable',
           505: 'HTTP Version Not Supported'}


def _default_log(message):
    print('Mira companion:', message, file=sys.stderr, flush=True)


def default_config_path():
    """`~/.config/mo-dot/companion.json` (following XDG_CONFIG_HOME, like Mira's memory files)."""
    base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(base) / 'mo-dot' / 'companion.json'


# ── pairing token ───────────────────────────────────────────────────────────────────────────────
class TokenStore:
    """companion.json (0600): whether the owner turned the phone interface on, its port, and the
    pairing token (32 random bytes, url-safe). The session cookie is an HMAC of the token, so a
    rotation invalidates every paired phone and no session list has to be kept."""

    def __init__(self, path=None):
        self.path = Path(path) if path else default_config_path()
        self._lock = threading.Lock()
        self._data = self._read()

    def _read(self):
        data = {}
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                data = raw
            if self.path.stat().st_mode & 0o077:
                os.chmod(self.path, 0o600)
        except (OSError, ValueError):
            pass
        token = data.get('token')
        port = data.get('port')
        return {
            'version': 1,
            'enabled': data.get('enabled') is True,
            'token': token if isinstance(token, str) and TOKEN_RE.fullmatch(token) else None,
            'port': port if isinstance(port, int) and not isinstance(port, bool) and 1024 <= port <= 65535
            else DEFAULT_PORT,
        }

    def _save(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temp = self.path.with_name(f'.{self.path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(self._data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
            os.chmod(self.path, 0o600)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(temp)
            raise

    @property
    def enabled(self):
        with self._lock:
            return self._data['enabled']

    @property
    def port(self):
        with self._lock:
            return self._data['port']

    @property
    def token(self):
        with self._lock:
            return self._data['token']

    def ensure_token(self):
        with self._lock:
            if not self._data['token']:
                self._data['token'] = secrets.token_urlsafe(32)
                self._save()
            return self._data['token']

    def set_enabled(self, enabled):
        with self._lock:
            self._data['enabled'] = bool(enabled)
            if self._data['enabled'] and not self._data['token']:
                self._data['token'] = secrets.token_urlsafe(32)
            self._save()

    def rotate(self):
        with self._lock:
            self._data['token'] = secrets.token_urlsafe(32)
            self._save()
            return self._data['token']

    @staticmethod
    def _session_for(token):
        digest = hmac.new(token.encode('ascii'), SESSION_CONTEXT, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')

    def session_cookie(self):
        token = self.token
        return self._session_for(token) if token else None

    def check_token(self, candidate):
        token = self.token
        if not token or not isinstance(candidate, str):
            return False
        return hmac.compare_digest(candidate.encode('utf-8', 'replace'), token.encode('ascii'))

    def check_session(self, candidate):
        expected = self.session_cookie()
        if not expected or not isinstance(candidate, str):
            return False
        return hmac.compare_digest(candidate.encode('utf-8', 'replace'), expected.encode('ascii'))


# ── Tailscale discovery ─────────────────────────────────────────────────────────────────────────
class Tailnet(NamedTuple):
    ip: Optional[str]
    names: tuple = ()
    reason: str = ''      # '' when found, else 'not_installed' or 'not_connected'


def is_tailnet_ipv4(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return address.version == 4 and address in TAILNET


def interface_ipv4(name=TAILSCALE_INTERFACE):
    """The IPv4 address of a network interface (Linux SIOCGIFADDR), or None."""
    try:
        import fcntl
    except ImportError:
        return None
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            packed = fcntl.ioctl(probe.fileno(), 0x8915, struct.pack('256s', name.encode()[:15]))
        except OSError:
            return None
    return socket.inet_ntoa(packed[20:24])


def _tailscale_cli():
    found = shutil.which('tailscale')
    if found:
        return found
    return next((p for p in ('/usr/bin/tailscale', '/usr/sbin/tailscale', '/usr/local/bin/tailscale')
                 if os.access(p, os.X_OK)), None)


def parse_status(data):
    """(ipv4, names) from `tailscale status --json`, or (None, ()) unless the node is running."""
    if not isinstance(data, dict) or data.get('BackendState') != 'Running':
        return None, ()
    me = data.get('Self') if isinstance(data.get('Self'), dict) else {}
    ip = next((a for a in (me.get('TailscaleIPs') or data.get('TailscaleIPs') or [])
               if isinstance(a, str) and is_tailnet_ipv4(a)), None)
    names = []
    dns = str(me.get('DNSName') or '').rstrip('.').lower()
    if dns and len(dns) <= 253 and NAME_RE.fullmatch(dns):
        names = [dns, dns.split('.', 1)[0]]
    return ip, tuple(dict.fromkeys(names))


def find_tailscale(run=subprocess.run, interface=TAILSCALE_INTERFACE):
    """This computer's Tailscale IPv4 and MagicDNS names, found at runtime.

    `tailscale status --json` is authoritative (it also knows the MagicDNS name); the
    `tailscale0` interface address is the fallback when the CLI cannot answer.
    """
    cli = _tailscale_cli()
    local = interface_ipv4(interface)
    local = local if local and is_tailnet_ipv4(local) else None
    if cli:
        try:
            result = run([cli, 'status', '--json', '--peers=false'], capture_output=True, text=True, timeout=4)
            data = json.loads(result.stdout) if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, ValueError):
            data = None
        if isinstance(data, dict):
            ip, names = parse_status(data)
            if ip:
                return Tailnet(ip, names, '')
            return Tailnet(None, (), 'not_connected')
        if local:
            return Tailnet(local, (), '')
        try:
            result = run([cli, 'ip', '-4'], capture_output=True, text=True, timeout=4)
            ip = next((line.strip() for line in result.stdout.splitlines() if is_tailnet_ipv4(line.strip())), None)
        except (OSError, subprocess.SubprocessError):
            ip = None
        return Tailnet(ip, (), '') if ip else Tailnet(None, (), 'not_connected')
    if local:
        return Tailnet(local, (), '')
    return Tailnet(None, (), 'not_installed')


def address_still_ours(host):
    return host == LOOPBACK or interface_ipv4() == host


def bindable(host):
    """Only the Tailscale address, or loopback for tests/review. Never the LAN, never 0.0.0.0."""
    if host == LOOPBACK or (isinstance(host, str) and is_tailnet_ipv4(host)):
        return host
    raise ValueError('refusing to bind outside the tailnet')


# ── validation shared with the desktop ──────────────────────────────────────────────────────────
class Invalid(Exception):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code = code
        self.status = status


def validate_text(text):
    if not isinstance(text, str):
        raise Invalid('text')
    text = text.strip()
    if not 1 <= len(text) <= MAX_TEXT or '\x00' in text:
        raise Invalid('text')
    return text


def validate_home_action(entity_id, action, value=None, color=None):
    """The desktop's rules (home_link.control): supported entity ids and actions only, value 0–100,
    a colour from the fixed palette. Returns the (value, color) the controller slot expects."""
    if not isinstance(entity_id, str) or len(entity_id) > 128 or not ENTITY_RE.fullmatch(entity_id):
        raise Invalid('entity')
    if action not in HOME_ACTIONS:
        raise Invalid('action')
    domain = entity_id.split('.', 1)[0]
    if (action in LIGHT_ONLY and domain != 'light') or (action in MEDIA_ONLY and domain != 'media_player'):
        raise Invalid('action')
    if action in VALUE_ACTIONS:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                or not 0 <= value <= 100:
            raise Invalid('value')
        return float(value), ''
    if action == 'color':
        if not isinstance(color, str) or color not in HOME_COLORS:
            raise Invalid('color')
        return -1.0, color
    return -1.0, ''


def check_device(device, action):
    """Only the controls a device's read-back row says it supports (as the desktop shows them)."""
    if device is None:
        raise Invalid('unknown_device', 404)
    if device.get('available') is False:
        raise Invalid('unavailable', 409)
    if device.get(CAPABILITY[action]) is False:
        raise Invalid('unsupported', 409)


# ── small HTTP pieces ───────────────────────────────────────────────────────────────────────────
class RateLimiter:
    """Sliding window per client address; used only on the server's loop thread."""

    def __init__(self, limit, window=60.0, clock=time.monotonic, max_keys=512):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.max_keys = max_keys
        self._hits = {}

    def _recent(self, key, now):
        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= self.max_keys:
                self.prune()
                if len(self._hits) >= self.max_keys:
                    self._hits.pop(next(iter(self._hits)))
            hits = self._hits[key] = deque()
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        return hits

    def allow(self, key):
        now = self.clock()
        hits = self._recent(key, now)
        if len(hits) >= self.limit:
            return False, max(1, math.ceil(self.window - (now - hits[0])))
        hits.append(now)
        return True, 0

    def hit(self, key):
        now = self.clock()
        self._recent(key, now).append(now)

    def blocked(self, key):
        if key not in self._hits:
            return False
        return len(self._recent(key, self.clock())) >= self.limit

    def prune(self):
        now = self.clock()
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self.window]:
            del self._hits[key]


class _HttpError(Exception):
    def __init__(self, status, code):
        super().__init__(code)
        self.status = status
        self.code = code


class Request:
    __slots__ = ('method', 'path', 'query', 'version', 'headers')

    def __init__(self, method, path, query, version, headers):
        self.method, self.path, self.query, self.version, self.headers = method, path, query, version, headers


class Response:
    __slots__ = ('status', 'headers', 'body')

    def __init__(self, status, headers=(), body=b''):
        self.status, self.headers, self.body = status, list(headers), body


def parse_head(head):
    lines = head.decode('latin-1').split('\r\n')
    parts = lines[0].split(' ')
    if len(parts) != 3:
        raise _HttpError(400, 'request_line')
    method, target, version = parts
    if version not in ('HTTP/1.1', 'HTTP/1.0'):
        raise _HttpError(505, 'version')
    if not METHOD_RE.fullmatch(method) or not target.startswith('/') or len(target) > 4096 \
            or any(ch in target for ch in '\t\r\n# \\') or any(ord(ch) < 0x21 or ord(ch) > 0x7e for ch in target):
        raise _HttpError(400, 'target')
    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        if line[0] in ' \t':
            raise _HttpError(400, 'folding')
        name, sep, value = line.partition(':')
        if not sep or not HEADER_NAME_RE.fullmatch(name):
            raise _HttpError(400, 'header')
        name = name.lower()
        value = value.strip(' \t')
        if name in headers:
            if name in SINGLE_HEADERS:
                raise _HttpError(400, 'duplicate_' + name)
            headers[name] += ', ' + value
        else:
            headers[name] = value
        if len(headers) > MAX_HEADERS:
            raise _HttpError(431, 'headers')
    path, _, query = target.partition('?')
    return Request(method, path, query, version, headers)


def read_cookie(header, name):
    for part in header.split(';'):
        key, sep, value = part.strip().partition('=')
        if sep and key == name:
            return value.strip().strip('"')
    return None


def sse(event, data):
    """One Server-Sent Event; `data` is JSON, which never contains a raw newline."""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f'event: {event}\ndata: {payload}\n\n'.encode('utf-8')


def load_static(root):
    """Every servable file under static/, read once. Requests are looked up in this table by exact
    path, so no request ever becomes a filesystem path (no traversal is even expressible)."""
    table = {}
    root = Path(root)
    if not root.is_dir():
        return table
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file() or any(part.startswith('.') for part in rel.split('/')):
            continue
        ctype = STATIC_TYPES.get(path.suffix.lower())
        if not ctype:
            continue
        data = path.read_bytes()
        etag = '"' + hashlib.sha256(data).hexdigest()[:20] + '"'
        table['/static/' + rel] = (data, ctype, etag)
    return table


class _Stream:
    __slots__ = ('peer', 'queue')

    def __init__(self, peer):
        self.peer = peer
        self.queue = asyncio.Queue(maxsize=STREAM_QUEUE)


# ── the server ──────────────────────────────────────────────────────────────────────────────────
class CompanionServer:
    """Serves the phone app and API on the Tailscale address from its own asyncio thread.

    `backend` is the thread-safe bridge to Mira (companion.adapter.ControllerAdapter):
    snapshot(), devices(), device(id), send(text), talk(), stop(), home_action(id, action, value,
    color), all_lights(on), refresh_home(), face_image(style, expression, size, fmt), housekeeping().
    Callbacks (`on_status`, `on_clients`, `on_paired`) run on the server thread; the adapter
    marshals them to Qt. `publish()` and `close_streams()` may be called from any thread.
    """

    def __init__(self, backend, store, *, port=DEFAULT_PORT, discover=None, probe=None,
                 static_dir=STATIC_DIR, heartbeat=HEARTBEAT_S, recheck=RECHECK_S,
                 posts_per_minute=POSTS_PER_MINUTE, auth_failures_per_minute=AUTH_FAILURES_PER_MINUTE,
                 on_status=None, on_clients=None, on_paired=None, log=None):
        self.backend = backend
        self.store = store
        self._port_wanted = int(port)
        self._discover = discover or find_tailscale
        self._probe = probe or address_still_ours
        self._static = load_static(static_dir)
        self._heartbeat = heartbeat
        self._recheck = recheck
        self._posts = RateLimiter(posts_per_minute)
        self._failures = RateLimiter(auth_failures_per_minute)
        self._on_status = on_status
        self._on_clients = on_clients
        self._on_paired = on_paired
        self._log = log or _default_log
        self._post_routes = {'/api/send': self._do_send, '/api/talk': self._do_talk, '/api/stop': self._do_stop,
                             '/api/home/action': self._do_home_action, '/api/lights': self._do_lights,
                             '/api/home/refresh': self._do_refresh}
        self._get_routes = ('/api/state', '/api/home', '/api/events')
        self._thread = None
        self._loop = None
        self._stopping = None
        self._ready = threading.Event()
        self._listener = None
        self._host = None
        self._port = None
        self._allowed_hosts = frozenset()
        self._allowed_origins = frozenset()
        self._streams = set()
        self._stream_hint = 0
        self._connections = set()
        self._per_ip = {}
        self._clients = 0
        self._render = None
        self._failures_in_a_row = 0

    # ── lifecycle (any thread) ──────────────────────────────────────
    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def running(self):
        return self._listener is not None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name='mira-companion', daemon=True)
        self._thread.start()
        self._ready.wait(2.0)

    def stop(self, timeout=3.0):
        loop, stopping, thread = self._loop, self._stopping, self._thread
        if loop is not None and stopping is not None:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(stopping.set)
        if thread is not None:
            thread.join(timeout)
        self._thread = None

    def wait_listening(self, timeout=5.0):
        """For tests and review: block until bound (True) or the timeout passes (False)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self._listener is not None:
                return True
            time.sleep(0.01)
        return False

    def publish(self, event, data):
        loop = self._loop
        if loop is None or not self._stream_hint:
            return
        try:
            chunk = sse(event, data)
        except (TypeError, ValueError):
            return
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(self._fanout, chunk)

    def close_streams(self, reason):
        loop = self._loop
        if loop is not None:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(self._close_streams_now, reason)

    # ── loop thread ─────────────────────────────────────────────────
    def _run(self):
        loop = asyncio.new_event_loop()
        self._loop = loop
        try:
            loop.run_until_complete(self._main())
        except Exception as exc:  # the thread must never die silently
            self._log('stopped after an error: ' + type(exc).__name__)
            self._status('error', 'failed')
        finally:
            with contextlib.suppress(Exception):
                loop.run_until_complete(loop.shutdown_default_executor())
            loop.close()
            self._loop = None
            self._ready.set()

    def _status(self, state, detail):
        if self._on_status:
            try:
                self._on_status(state, detail)
            except Exception as exc:
                self._log('status callback failed: ' + type(exc).__name__)

    async def _main(self):
        self._stopping = asyncio.Event()
        self._render = ThreadPoolExecutor(max_workers=1, thread_name_prefix='mira-companion-faces')
        self._ready.set()
        self._status('starting', None)
        keeper = asyncio.create_task(self._housekeeping())
        try:
            while not self._stopping.is_set():
                listening = await self._ensure_listening()
                if listening:
                    self._failures_in_a_row = 0
                    delay = self._recheck
                else:
                    self._failures_in_a_row += 1
                    delay = min(30.0, 5.0 * 2 ** min(self._failures_in_a_row - 1, 3))
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stopping.wait(), delay)
        finally:
            keeper.cancel()
            await self._close_listener()
            self._close_streams_now('shutdown')
            pending = [task for task in self._connections if not task.done()]
            if pending:
                await asyncio.wait(pending, timeout=1.0)
                for task in pending:
                    task.cancel()
            self._render.shutdown(wait=False, cancel_futures=True)
            self._status('stopped', None)

    async def _ensure_listening(self):
        if self._listener is not None and await asyncio.to_thread(self._probe, self._host):
            return True
        found = await asyncio.to_thread(self._discover)
        if self._listener is not None:
            if found.ip == self._host:     # the cheap probe could not tell; discovery confirms it
                return True
            self._log('the Tailscale address went away or changed')
            await self._close_listener()
        if not found.ip:
            self._status('waiting', found.reason or 'not_connected')
            return False
        try:
            host = bindable(found.ip)
        except ValueError:
            self._status('error', 'refused_address')
            return False
        try:
            listener = await asyncio.start_server(self._client, host=host, port=self._port_wanted,
                                                  limit=MAX_HEADER, backlog=32)
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                self._status('error', 'port_busy')
            elif exc.errno == errno.EADDRNOTAVAIL:
                self._status('waiting', 'not_connected')
            else:
                self._status('error', 'failed')
            return False
        self._listener = listener
        self._host = host
        self._port = listener.sockets[0].getsockname()[1]
        names = tuple(n.lower() for n in found.names if isinstance(n, str) and NAME_RE.fullmatch(n))
        hosts = {f'{host}:{self._port}'} | {f'{name}:{self._port}' for name in names}
        self._allowed_hosts = frozenset(hosts)
        self._allowed_origins = frozenset('http://' + h for h in hosts)
        self._log(f'listening on {host}:{self._port}')
        self._status('running', {'host': host, 'port': self._port, 'names': list(names)})
        return True

    async def _close_listener(self):
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(listener.wait_closed(), 1.0)

    async def _housekeeping(self):
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(30)
            self._posts.prune()
            self._failures.prune()
            housekeeping = getattr(self.backend, 'housekeeping', None)
            if housekeeping:
                with contextlib.suppress(Exception):
                    await loop.run_in_executor(self._render, housekeeping)

    # ── connections ─────────────────────────────────────────────────
    async def _client(self, reader, writer):
        peer = (writer.get_extra_info('peername') or ('?',))[0]
        if len(self._connections) >= MAX_CONNECTIONS or self._per_ip.get(peer, 0) >= MAX_CONNECTIONS_PER_IP:
            writer.close()
            return
        task = asyncio.current_task()
        self._connections.add(task)
        self._per_ip[peer] = self._per_ip.get(peer, 0) + 1
        try:
            first = True
            while not self._stopping.is_set():
                request = await self._read_request(reader, first)
                first = False
                if request is None:
                    break
                if not await self._handle(request, reader, writer, peer):
                    break
        except _HttpError as error:
            with contextlib.suppress(Exception):
                await self._send(writer, self._json(error.status, {'error': error.code}), keep=False)
        except (ConnectionError, TimeoutError, asyncio.IncompleteReadError, OSError):
            pass
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # a bug must not leak a traceback (or a request) to the phone
            self._log('request failed: ' + type(exc).__name__)
            with contextlib.suppress(Exception):
                await self._send(writer, self._json(500, {'error': 'internal'}), keep=False)
        finally:
            self._connections.discard(task)
            left = self._per_ip.get(peer, 1) - 1
            if left > 0:
                self._per_ip[peer] = left
            else:
                self._per_ip.pop(peer, None)
            writer.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(writer.wait_closed(), 1.0)

    async def _read_request(self, reader, first):
        try:
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), FIRST_REQUEST_S if first else KEEPALIVE_S)
        except asyncio.IncompleteReadError as exc:
            if exc.partial.strip():
                raise _HttpError(400, 'incomplete') from None
            return None
        except asyncio.LimitOverrunError:
            raise _HttpError(431, 'headers') from None
        except TimeoutError:
            return None
        return parse_head(head)

    async def _send(self, writer, response, keep=True, head_only=False):
        headers = [*BASE_HEADERS, *response.headers]
        if response.status not in (204, 304):   # a 304 has no content and must not claim a length
            headers.append(('Content-Length', str(len(response.body))))
        headers.append(('Connection', 'keep-alive' if keep else 'close'))
        lines = [f'HTTP/1.1 {response.status} {REASONS.get(response.status, "Status")}']
        lines.extend(f'{name}: {value}' for name, value in headers)
        writer.write(('\r\n'.join(lines) + '\r\n\r\n').encode('latin-1'))
        if response.body and not head_only:
            writer.write(response.body)
        await asyncio.wait_for(writer.drain(), WRITE_S)

    @staticmethod
    def _json(status, payload, extra=()):
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        return Response(status, [('Content-Type', 'application/json; charset=utf-8'),
                                 ('Cache-Control', 'no-store'), *extra], body)

    async def _handle(self, request, reader, writer, peer):
        keep = request.version == 'HTTP/1.1' and 'close' not in request.headers.get('connection', '').lower()
        if request.headers.get('host', '').lower() not in self._allowed_hosts:
            await self._send(writer, self._json(403, {'error': 'host'}), keep=False)
            return False
        if self._failures.blocked(peer):
            await self._send(writer, self._json(429, {'error': 'slow_down'}, [('Retry-After', '60')]), keep=False)
            return False
        if 'transfer-encoding' in request.headers:
            raise _HttpError(411, 'length_required')
        body = b''
        length = request.headers.get('content-length')
        if length is not None:
            if not length.isdigit() or len(length) > 9:
                raise _HttpError(400, 'length')
            size = int(length)
            if size > MAX_BODY:
                raise _HttpError(413, 'too_large')
            if size:
                if request.headers.get('expect', '').lower() == '100-continue':
                    writer.write(b'HTTP/1.1 100 Continue\r\n\r\n')
                body = await asyncio.wait_for(reader.readexactly(size), BODY_S)
        response = await self._route(request, body, peer, reader, writer)
        if response is None:   # an event stream owned the connection until it ended
            return False
        await self._send(writer, response, keep=keep, head_only=request.method == 'HEAD')
        return keep

    # ── routing ─────────────────────────────────────────────────────
    async def _route(self, request, body, peer, reader, writer):
        method, path = request.method, request.path
        if method not in ('GET', 'HEAD', 'POST'):
            return self._json(405, {'error': 'method'}, [('Allow', 'GET, HEAD, POST')])
        if path in ('/', '/index.html') or path.startswith('/static/') or path in ICON_ALIASES:
            if method == 'POST':
                return self._json(405, {'error': 'method'}, [('Allow', 'GET, HEAD')])
            return self._static_file(request)
        if path == '/manifest.webmanifest':
            if method == 'POST':
                return self._json(405, {'error': 'method'}, [('Allow', 'GET, HEAD')])
            return self._manifest(request)
        if path == '/pair':
            if method != 'GET':
                return self._json(405, {'error': 'method'}, [('Allow', 'GET')])
            return self._pair(request, peer)
        if not (path.startswith('/api/') or path.startswith('/face/')):
            return self._json(404, {'error': 'not_found'})
        kind = self._auth(request)
        if kind is None:
            self._failures.hit(peer)
            return self._json(401, {'error': 'unauthorized'}, [('WWW-Authenticate', 'Bearer realm="mira"')])
        if method == 'POST':
            return self._post(request, body, peer, kind)
        if method != 'GET':
            return self._json(405, {'error': 'method'}, [('Allow', 'GET, POST')])
        if path == '/api/state':
            return self._json(200, self._snapshot())
        if path == '/api/home':
            snapshot = self._snapshot()
            return self._json(200, {'home': snapshot.get('home', {}), 'devices': snapshot.get('devices', []),
                                    'palette': list(PALETTE)})
        if path == '/api/events':
            await self._events(reader, writer, peer)
            return None
        if path.startswith('/face/'):
            return await self._face(request)
        if path in self._post_routes:
            return self._json(405, {'error': 'method'}, [('Allow', 'POST')])
        return self._json(404, {'error': 'not_found'})

    def _auth(self, request):
        header = request.headers.get('authorization')
        if header is not None:
            scheme, _, credential = header.partition(' ')
            if scheme.lower() == 'bearer' and self.store.check_token(credential.strip()):
                return 'bearer'
            return None
        cookie = read_cookie(request.headers.get('cookie', ''), COOKIE)
        if cookie and self.store.check_session(cookie):
            return 'cookie'
        return None

    def _snapshot(self):
        snapshot = self.backend.snapshot()
        snapshot['palette'] = list(PALETTE)
        return snapshot

    def _static_file(self, request):
        key = '/static/index.html' if request.path in ('/', '/index.html') else ICON_ALIASES.get(request.path, request.path)
        entry = self._static.get(key)
        if entry is None:
            return self._json(404, {'error': 'not_found'})
        data, ctype, etag = entry
        headers = [('Content-Type', ctype), ('ETag', etag), ('Cache-Control', 'no-cache')]
        if ctype.startswith('text/html'):
            headers.append(('Content-Security-Policy', CSP))
        if request.headers.get('if-none-match') == etag:
            return Response(304, headers)
        return Response(200, headers, data)

    def _manifest(self, request):
        entry = self._static.get('/static/manifest.webmanifest')
        if entry is None:
            return self._json(404, {'error': 'not_found'})
        manifest = json.loads(entry[0])
        # A Home Screen web app on iOS has its own cookie jar, so the paired start URL carries the
        # pairing link. Only a paired browser gets it, and only for its manifest fetch (page
        # scripts send Sec-Fetch-Dest: empty and cannot read it).
        if self._auth(request) and request.headers.get('sec-fetch-dest', 'manifest') == 'manifest':
            manifest['start_url'] = '/pair?t=' + self.store.token
        body = json.dumps(manifest, ensure_ascii=False).encode('utf-8')
        return Response(200, [('Content-Type', 'application/manifest+json; charset=utf-8'),
                              ('Cache-Control', 'no-store')], body)

    def _pair(self, request, peer):
        try:
            params = parse_qs(request.query, max_num_fields=4)
        except ValueError:
            params = {}
        candidate = (params.get('t') or [''])[0]
        if not self.store.check_token(candidate):
            self._failures.hit(peer)
            return Response(303, [('Location', '/?pair=invalid'), ('Cache-Control', 'no-store')])
        cookie = self.store.session_cookie()
        if self._on_paired:
            with contextlib.suppress(Exception):
                self._on_paired(peer)
        self._log('a phone paired')
        return Response(303, [('Set-Cookie', f'{COOKIE}={cookie}; Path=/; Max-Age={COOKIE_MAX_AGE}; HttpOnly; SameSite=Strict'),
                              ('Location', '/'), ('Cache-Control', 'no-store')])

    async def _face(self, request):
        match = FACE_RE.fullmatch(request.path)
        if not match:
            return self._json(404, {'error': 'not_found'})
        size = 256
        if request.query:
            try:
                params = parse_qs(request.query, max_num_fields=2)
            except ValueError:
                return self._json(400, {'error': 'query'})
            wanted = (params.get('s') or ['256'])[0]
            if not wanted.isdigit() or int(wanted) not in FACE_SIZES:
                return self._json(400, {'error': 'size'})
            size = int(wanted)
        style, expression, fmt = match.groups()
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(self._render, self.backend.face_image, style, expression, size, fmt)
        except Exception as exc:
            self._log('face rendering failed: ' + type(exc).__name__)
            data = None
        if not data:
            return self._json(404, {'error': 'not_found'})
        etag = '"' + hashlib.sha256(data).hexdigest()[:20] + '"'
        headers = [('Content-Type', FACE_TYPES[fmt]), ('ETag', etag), ('Cache-Control', 'private, max-age=86400')]
        if request.headers.get('if-none-match') == etag:
            return Response(304, headers)
        return Response(200, headers, data)

    # ── actions ─────────────────────────────────────────────────────
    def _post(self, request, body, peer, kind):
        handler = self._post_routes.get(request.path)
        if handler is None:
            if request.path in self._get_routes:
                return self._json(405, {'error': 'method'}, [('Allow', 'GET')])
            return self._json(404, {'error': 'not_found'})
        origin = request.headers.get('origin')
        if origin is not None:
            if origin.lower() not in self._allowed_origins:
                return self._json(403, {'error': 'origin'})
        elif kind == 'cookie':   # a browser always sends Origin with a POST; its absence is suspicious
            return self._json(403, {'error': 'origin'})
        if request.headers.get('sec-fetch-site', 'same-origin') not in ('same-origin', 'none'):
            return self._json(403, {'error': 'origin'})
        allowed, retry = self._posts.allow(peer)
        if not allowed:
            return self._json(429, {'error': 'slow_down'}, [('Retry-After', str(retry))])
        data = {}
        if body:
            ctype = request.headers.get('content-type', '').split(';', 1)[0].strip().lower()
            if ctype != 'application/json':
                return self._json(415, {'error': 'content_type'})
            try:
                data = json.loads(body.decode('utf-8'))
            except (UnicodeDecodeError, ValueError):
                return self._json(400, {'error': 'json'})
            if not isinstance(data, dict):
                return self._json(400, {'error': 'json'})
        try:
            accepted = handler(data)
        except Invalid as bad:
            return self._json(bad.status, {'error': bad.code})
        if not accepted:
            return self._json(503, {'error': 'unavailable'})
        return self._json(202, {'status': 'accepted'})

    def _do_send(self, data):
        return self.backend.send(validate_text(data.get('text')))

    def _do_talk(self, data):
        return self.backend.talk()

    def _do_stop(self, data):
        return self.backend.stop()

    def _do_refresh(self, data):
        return self.backend.refresh_home()

    def _do_lights(self, data):
        on = data.get('on')
        if not isinstance(on, bool):
            raise Invalid('on')
        return self.backend.all_lights(on)

    def _do_home_action(self, data):
        entity_id, action = data.get('entity_id'), data.get('action')
        value, color = validate_home_action(entity_id, action, data.get('value'), data.get('color'))
        check_device(self.backend.device(entity_id), action)
        return self.backend.home_action(entity_id, action, value, color)

    # ── event stream ────────────────────────────────────────────────
    async def _events(self, reader, writer, peer):
        mine = sum(1 for stream in self._streams if stream.peer == peer)
        if mine >= MAX_STREAMS_PER_IP or len(self._streams) >= MAX_STREAMS:
            await self._send(writer, self._json(429, {'error': 'too_many_streams'}), keep=False)
            return
        stream = _Stream(peer)
        # Subscribe before reading the snapshot: an event raced in between is only a repeat
        # (the page de-duplicates chat rows by their sequence number), never a loss.
        self._streams.add(stream)
        self._stream_hint = len(self._streams)
        self._report_clients()
        closed = asyncio.ensure_future(reader.read(1))
        try:
            head = [f'HTTP/1.1 200 {REASONS[200]}', *(f'{k}: {v}' for k, v in BASE_HEADERS),
                    'Content-Type: text/event-stream; charset=utf-8', 'Cache-Control: no-store',
                    'X-Accel-Buffering: no', 'Connection: close']
            writer.write(('\r\n'.join(head) + '\r\n\r\n').encode('latin-1'))
            writer.write(b'retry: 3000\n\n' + sse('snapshot', self._snapshot()))
            await asyncio.wait_for(writer.drain(), WRITE_S)
            while True:
                getter = asyncio.ensure_future(stream.queue.get())
                done, _ = await asyncio.wait({getter, closed}, timeout=self._heartbeat,
                                             return_when=asyncio.FIRST_COMPLETED)
                if closed in done:
                    getter.cancel()
                    break
                if getter not in done:
                    getter.cancel()
                    writer.write(b': keep-alive\n\n')
                    await asyncio.wait_for(writer.drain(), WRITE_S)
                    continue
                chunks, ending = [], False
                item = getter.result()
                while True:
                    if item is None:
                        ending = True
                        break
                    chunks.append(item)
                    if stream.queue.empty():
                        break
                    item = stream.queue.get_nowait()
                if chunks:
                    writer.write(b''.join(chunks))
                    await asyncio.wait_for(writer.drain(), WRITE_S)
                if ending:
                    break
        except (ConnectionError, TimeoutError, OSError):
            pass
        finally:
            closed.cancel()
            self._streams.discard(stream)
            self._stream_hint = len(self._streams)
            self._report_clients()

    def _fanout(self, chunk):
        for stream in list(self._streams):
            try:
                stream.queue.put_nowait(chunk)
            except asyncio.QueueFull:   # a phone that stopped reading: end it; it reconnects fresh
                self._end_stream(stream, None)

    def _close_streams_now(self, reason):
        for stream in list(self._streams):
            self._end_stream(stream, sse('bye', {'reason': reason}))

    @staticmethod
    def _end_stream(stream, last):
        queue = stream.queue
        while not queue.empty():
            queue.get_nowait()
        if last is not None:
            queue.put_nowait(last)
        queue.put_nowait(None)

    def _report_clients(self):
        phones = len({stream.peer for stream in self._streams})
        if phones != self._clients:
            self._clients = phones
            if self._on_clients:
                with contextlib.suppress(Exception):
                    self._on_clients(phones)
