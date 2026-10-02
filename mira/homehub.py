"""Mira's whole view of the owner's home, read from his own Home Assistant.

`home_link.py` reads /api/states and nothing else: a friendly name, a state and a few attributes.
That is enough to switch a lamp, not to know a home. The room a lamp stands in, the device it
belongs to, the name the owner gave it, the names he calls it by (voice aliases), whether he hid
it, and the integration behind it live in Home Assistant's three registries (areas, devices,
entities), and those are reachable only over the WebSocket API. The image carries no WebSocket
library (/usr/lib/mira/site has none, and one socket is not worth a dependency), so this module
speaks RFC 6455 itself: a client that masks every frame, reads all three length forms, joins
fragments, answers pings and closes cleanly. That is the subset Home Assistant uses.

What the owner sees is `Hub.inventory()`: one record per thing worth showing, merged from the
live states and the registries. Its capabilities come from the entity's colour modes and
supported_features bits, the same bits Home Assistant checks before it accepts a service call, so
a control the UI draws is a call Home Assistant will accept.

The token stays in ~/.config/mo-dot/home.json (0600). It is read here, sent only to the
configured Home Assistant, and never appears in a message, a repr or a log. `probe()` needs no
token and never touches an endpoint that answers 401: Home Assistant counts every 401 as a failed
login and shows the owner a "Login attempt failed" notification (components/http/ban.py).
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import re
import socket
import ssl
import struct
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path.home() / '.config/mo-dot/home.json'
DEFAULT_URL = 'http://127.0.0.1:8123'


class HubError(RuntimeError):
    """A failure the owner can read. str() is Arabic (the UI shows it); `.en` is the English line;
    `.code` is one of unreachable | auth | not_found | refused | protocol | invalid."""

    def __init__(self, ar: str, en: str | None = None, code: str = 'refused'):
        super().__init__(ar)
        self.en = en or ar
        self.code = code


_UNREACHABLE = 'خادم البيت غير متاح'
_REJECTED = 'رفض Home Assistant رمز الوصول؛ اربط البيت من جديد'
_BROKEN = 'انقطع الاتصال بخادم البيت'


# ── the owner's link (token + address) ───────────────────────────────

def _clean_token(token) -> str:
    token = token.strip() if isinstance(token, str) else ''
    if len(token) < 40 or not token.isascii() or any(c.isspace() for c in token):
        raise HubError('رمز الوصول غير صالح', 'invalid access token', 'invalid')
    return token


def _clean_url(url) -> str:
    """scheme://host[:port] of a Home Assistant; nothing else (no path, credentials or query)."""
    bad = HubError('عنوان Home Assistant غير صالح', 'invalid Home Assistant address', 'invalid')
    if not isinstance(url, str):
        raise bad
    parts = urllib.parse.urlsplit(url.strip())
    try:
        parts.port                                  # raises on a malformed port
    except ValueError:
        raise bad from None
    if (parts.scheme not in ('http', 'https') or not parts.hostname or parts.username is not None
            or parts.password is not None or parts.query or parts.fragment or parts.path not in ('', '/')):
        raise bad
    return f'{parts.scheme}://{parts.netloc}'


def load(path=CONFIG) -> 'Hub | None':
    """The linked Home Assistant, or None when the owner has not linked one."""
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None
    except ValueError:
        return None                                 # a broken file links nothing; save() rewrites it
    except OSError as exc:
        raise HubError('تعذّرت قراءة إعداد البيت', f'cannot read {path}: {exc.strerror}', 'invalid') from None
    if not isinstance(data, dict):
        return None
    try:
        token = _clean_token(data.get('token'))
    except HubError:
        return None
    return Hub(_clean_url(data.get('url') or DEFAULT_URL), token)


def save(token: str | None, url: str | None = None, path=CONFIG) -> None:
    """Write the link (0600, atomically). A None token or url keeps the one already saved;
    url '' returns to the default address. Other keys in the file are kept."""
    path = Path(path)
    try:
        current = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        current = {}
    data = dict(current) if isinstance(current, dict) else {}
    data['token'] = _clean_token(data.get('token') if token is None else token)
    if url == '':
        data.pop('url', None)
    elif url is not None:
        data['url'] = _clean_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.home-', suffix='.json', dir=path.parent)   # created 0600
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(data, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# ── HTTP (REST) ──────────────────────────────────────────────────────

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None                                 # the token never follows a redirect


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def _http(url: str, *, token: str | None = None, body=None, timeout: float) -> tuple[int, bytes]:
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        with exc:
            return exc.code, exc.read() or b''
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, 'reason', exc)
        raise HubError(_UNREACHABLE, f'Home Assistant is unreachable ({reason})', 'unreachable') from None


# ── WebSocket (RFC 6455, client side) ────────────────────────────────

_WS_GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'     # RFC 6455 §1.3
OP_CONT, OP_TEXT, OP_BINARY, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
MAX_MESSAGE = 32 << 20                                  # a large home's registry is ~2 MB


def _protocol(detail: str) -> HubError:
    return HubError(_BROKEN, 'WebSocket protocol error: ' + detail, 'protocol')


def mask(key: bytes, data: bytes) -> bytes:
    """XOR data with the 4-byte key repeated (RFC 6455 §5.3), as one big-integer operation."""
    n = len(data)
    if not n:
        return b''
    pad = (key * (n // 4 + 1))[:n]
    return (int.from_bytes(data, 'big') ^ int.from_bytes(pad, 'big')).to_bytes(n, 'big')


def encode_frame(opcode: int, payload: bytes = b'', *, fin: bool = True, masked: bool = True,
                 key: bytes | None = None) -> bytes:
    """One frame (§5.2). A client masks every frame; `masked=False` is a server's frame."""
    head = bytearray([(0x80 if fin else 0) | opcode])
    bit, n = (0x80 if masked else 0), len(payload)
    if n < 126:
        head.append(bit | n)
    elif n < 1 << 16:
        head.append(bit | 126)
        head += struct.pack('!H', n)
    else:
        head.append(bit | 127)
        head += struct.pack('!Q', n)
    if not masked:
        return bytes(head) + payload
    key = key or os.urandom(4)
    return bytes(head) + key + mask(key, payload)


def read_frame(read, *, masked: bool = False, limit: int = MAX_MESSAGE) -> tuple[bool, int, bytes]:
    """(fin, opcode, payload) of the next frame; `read(n)` returns exactly n bytes.
    A client expects unmasked frames (§5.1: it must fail on a masked one); a server, masked."""
    b0, b1 = read(2)
    if b0 & 0x70:
        raise _protocol('reserved bits set; no extension was negotiated')
    fin, opcode, n = bool(b0 & 0x80), b0 & 0x0F, b1 & 0x7F
    if bool(b1 & 0x80) != masked:
        raise _protocol('masked frame from the server' if not masked else 'unmasked frame from a client')
    if n == 126:
        (n,) = struct.unpack('!H', read(2))
    elif n == 127:
        (n,) = struct.unpack('!Q', read(8))
        if n >> 63:
            raise _protocol('64-bit length with the high bit set')
    if opcode >= 0x8:
        if opcode not in (OP_CLOSE, OP_PING, OP_PONG):
            raise _protocol(f'unknown control opcode {opcode:#x}')
        if not fin or n > 125:
            raise _protocol('fragmented or oversized control frame')
    elif opcode not in (OP_CONT, OP_TEXT, OP_BINARY):
        raise _protocol(f'unknown data opcode {opcode:#x}')
    if n > limit:
        raise _protocol(f'frame of {n} bytes exceeds the {limit}-byte limit')
    key = read(4) if masked else None
    payload = read(n) if n else b''
    return fin, opcode, (mask(key, payload) if key else payload)


def _ws_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(('wss' if parts.scheme == 'https' else 'ws', parts.netloc,
                                    '/api/websocket', '', ''))


class WebSocket:
    """One client connection: the opening handshake, masked frames out, whole messages in."""

    def __init__(self, url: str, timeout: float):
        parts = urllib.parse.urlsplit(url)
        secure = parts.scheme in ('wss', 'https')
        host, port = parts.hostname, parts.port or (443 if secure else 80)
        self.closed = False
        self._buf = bytearray()
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            if secure:
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        except OSError as exc:
            raise HubError(_UNREACHABLE, f'cannot connect to {host}:{port} ({exc})', 'unreachable') from None
        self.sock = sock
        try:
            self._handshake(parts.netloc, parts.path or '/')
        except BaseException:
            sock.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # the byte stream
    def _fill(self):
        try:
            chunk = self.sock.recv(1 << 16)
        except TimeoutError:
            raise HubError('خادم البيت لا يستجيب', 'Home Assistant did not answer in time', 'unreachable') from None
        except OSError as exc:
            raise HubError(_BROKEN, f'connection lost ({exc})', 'unreachable') from None
        if not chunk:
            raise HubError(_BROKEN, 'Home Assistant closed the connection', 'unreachable')
        self._buf += chunk

    def _read(self, n: int) -> bytes:
        while len(self._buf) < n:
            self._fill()
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    def _handshake(self, netloc: str, path: str):
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {path} HTTP/1.1\r\nHost: {netloc}\r\nUpgrade: websocket\r\n'
                           f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                           f'Sec-WebSocket-Version: 13\r\nUser-Agent: Mira\r\n\r\n').encode('ascii'))
        while b'\r\n\r\n' not in self._buf:
            if len(self._buf) > 16384:
                raise _protocol('oversized handshake response')
            self._fill()
        head, _, rest = bytes(self._buf).partition(b'\r\n\r\n')
        self._buf = bytearray(rest)                 # frames that arrived with the response
        lines = head.decode('iso-8859-1').split('\r\n')
        status = lines[0].split(' ', 2)
        if len(status) < 2 or status[1] != '101':
            raise HubError('رفض خادم البيت الاتصال', f'WebSocket upgrade refused: {lines[0]}', 'protocol')
        headers = {}
        for line in lines[1:]:
            name, _, value = line.partition(':')
            headers[name.strip().lower()] = value.strip()
        accept = base64.b64encode(hashlib.sha1(key.encode() + _WS_GUID).digest()).decode()
        if (headers.get('upgrade', '').lower() != 'websocket'
                or 'upgrade' not in headers.get('connection', '').lower()
                or headers.get('sec-websocket-accept') != accept):
            raise _protocol('handshake response does not accept this key')
        if headers.get('sec-websocket-extensions'):
            raise _protocol('the server enabled an extension that was not offered')

    # frames and messages
    def send(self, opcode: int, payload: bytes = b''):
        try:
            self.sock.sendall(encode_frame(opcode, payload))
        except OSError as exc:
            raise HubError(_BROKEN, f'cannot send ({exc})', 'unreachable') from None

    def send_json(self, obj):
        self.send(OP_TEXT, json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode())

    def recv_message(self) -> tuple[int, bytes]:
        """The next whole data message; pings are answered and pongs dropped on the way."""
        opcode, parts, size = None, [], 0
        while True:
            fin, op, payload = read_frame(self._read)
            if op == OP_PING:
                self.send(OP_PONG, payload)
                continue
            if op == OP_PONG:
                continue
            if op == OP_CLOSE:
                code = struct.unpack('!H', payload[:2])[0] if len(payload) >= 2 else 1005
                reason = payload[2:].decode('utf-8', 'replace')
                if not self.closed:
                    self.closed = True
                    with contextlib.suppress(HubError):
                        self.send(OP_CLOSE, payload[:2])
                raise HubError('أغلق خادم البيت الاتصال', f'Home Assistant closed the WebSocket ({code} {reason})'.strip(), 'unreachable')
            if op == OP_CONT:
                if opcode is None:
                    raise _protocol('continuation frame outside a message')
            elif opcode is not None:
                raise _protocol('a new message began inside a fragmented one')
            else:
                opcode = op
            size += len(payload)
            if size > MAX_MESSAGE:
                raise _protocol('message exceeds the size limit')
            parts.append(payload)
            if fin:
                return opcode, b''.join(parts)

    def recv_json(self):
        opcode, data = self.recv_message()
        if opcode != OP_TEXT:
            raise _protocol('binary message where JSON text was expected')
        try:
            return json.loads(data.decode('utf-8'))
        except ValueError:
            raise _protocol('message is not JSON') from None

    def close(self, code: int = 1000):
        """The closing handshake (§7): send Close, wait briefly for the server's, drop the socket."""
        try:
            if not self.closed:
                self.closed = True
                self.send(OP_CLOSE, struct.pack('!H', code))
                self.sock.settimeout(min(self.sock.gettimeout() or 2.0, 2.0))
                for _ in range(64):
                    _fin, op, _payload = read_frame(self._read)
                    if op == OP_CLOSE:
                        break
        except (HubError, OSError, ValueError):
            pass
        finally:
            with contextlib.suppress(OSError):
                self.sock.close()


class Session:
    """One authenticated Home Assistant WebSocket session: auth, then id-numbered commands."""

    def __init__(self, url: str, token: str, timeout: float):
        self.ws = WebSocket(_ws_url(url), timeout)
        self._pending: list = []
        self._next = 0
        try:
            hello = self._recv()
            if hello.get('type') != 'auth_required':
                raise _protocol('Home Assistant did not ask for authentication')
            self.version = hello.get('ha_version')
            self.ws.send_json({'type': 'auth', 'access_token': token})
            reply = self._recv()
            if reply.get('type') == 'auth_invalid':
                raise HubError(_REJECTED, 'Home Assistant rejected the token: ' + str(reply.get('message') or ''), 'auth')
            if reply.get('type') != 'auth_ok':
                raise _protocol('unexpected answer to auth: ' + str(reply.get('type')))
        except BaseException:
            self.ws.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.ws.close()

    def _recv(self) -> dict:
        while not self._pending:
            message = self.ws.recv_json()
            # with coalesce_messages a frame holds an array of messages; never requested, still read
            self._pending.extend(message if isinstance(message, list) else [message])
        message = self._pending.pop(0)
        return message if isinstance(message, dict) else {}

    def command(self, payload: dict):
        """Send one command and return its `result`; HubError carries Home Assistant's refusal."""
        if not isinstance(payload, dict) or not isinstance(payload.get('type'), str):
            raise HubError('أمر غير صالح', 'a command needs a type', 'invalid')
        self._next += 1
        ident = self._next
        self.ws.send_json({**payload, 'id': ident})
        while True:
            message = self._recv()
            if message.get('id') != ident or message.get('type') != 'result':
                continue                            # an event or a stray message; nothing is subscribed
            if message.get('success'):
                return message.get('result')
            error = message.get('error') or {}
            text = str(error.get('message') or error.get('code') or 'unknown error')
            code = {'not_found': 'not_found', 'unauthorized': 'auth'}.get(error.get('code'), 'refused')
            raise HubError('رفض Home Assistant الطلب: ' + text, f"Home Assistant refused {payload['type']}: {text}", code)


# ── probing, without a token ─────────────────────────────────────────

def probe(url: str = DEFAULT_URL, timeout: float = 2.0) -> dict:
    """Is a Home Assistant answering at `url`, which version, and does it still need its first-run
    setup? /manifest.json and /api/onboarding need no auth; the version is in the WebSocket's
    unauthenticated auth_required greeting. /api/ is not asked: its 401 would be logged as a failed
    login and shown to the owner."""
    out = {'reachable': False, 'version': None, 'needs_onboarding': False}
    try:
        base = _clean_url(url)
    except HubError:
        return out
    try:
        status, raw = _http(base + '/manifest.json', timeout=timeout)
        out['reachable'] = status == 200 and 'Home Assistant' in str(json.loads(raw).get('name', ''))
    except (HubError, ValueError, AttributeError):
        pass
    try:
        with WebSocket(_ws_url(base), timeout) as ws:
            hello = ws.recv_json()
        if isinstance(hello, dict) and hello.get('type') == 'auth_required':
            out['reachable'] = True
            out['version'] = hello.get('ha_version')
    except HubError:
        pass
    if out['reachable']:
        try:
            # registered only until onboarding is finished; a finished one answers 404
            status, raw = _http(base + '/api/onboarding', timeout=timeout)
            steps = json.loads(raw) if status == 200 else []
            out['needs_onboarding'] = any(isinstance(s, dict) and not s.get('done') for s in steps)
        except (HubError, ValueError, TypeError):
            pass
    return out


# ── what an entity can do ────────────────────────────────────────────
# Feature bits are Home Assistant 2026.9's <Domain>EntityFeature IntFlags, read from the running
# container's homeassistant/components/<domain>/const.py (remote, fan, lock: __init__.py).

LIGHT_EFFECT, LIGHT_FLASH, LIGHT_TRANSITION = 4, 8, 32           # light/const.py LightEntityFeature
# light/const.py ColorMode: COLOR_MODES_COLOR, and brightness = any valid mode except onoff
COLOR_MODES_COLOR = ('hs', 'xy', 'rgb', 'rgbw', 'rgbww')
COLOR_MODES_BRIGHTNESS = ('brightness', 'color_temp', 'white') + COLOR_MODES_COLOR

MEDIA_FEATURES = {                                                # media_player/const.py
    'pause': 1, 'seek': 2, 'volume_set': 4, 'mute': 8, 'previous': 16, 'next': 32,
    'turn_on': 128, 'turn_off': 256, 'play_media': 512, 'volume_step': 1024,
    'select_source': 2048, 'stop': 4096, 'play': 16384, 'shuffle': 32768,
    'sound_mode': 65536, 'browse': 131072, 'repeat': 262144, 'grouping': 524288,
    'announce': 1048576,
}
REMOTE_LEARN, REMOTE_DELETE, REMOTE_ACTIVITY = 1, 2, 4            # remote/__init__.py
FAN_FEATURES = {'speed': 1, 'oscillate': 2, 'direction': 4, 'presets': 8,
                'turn_off': 16, 'turn_on': 32}                    # fan/__init__.py
COVER_FEATURES = {'open': 1, 'close': 2, 'position': 4, 'stop': 8, 'open_tilt': 16,
                  'close_tilt': 32, 'stop_tilt': 64, 'tilt_position': 128}   # cover/const.py
CLIMATE_FEATURES = {'target_temperature': 1, 'target_range': 2, 'target_humidity': 4,
                    'fan_modes': 8, 'presets': 16, 'swing': 32, 'turn_off': 128,
                    'turn_on': 256, 'swing_horizontal': 512}      # climate/const.py
LOCK_OPEN = 1                                                     # lock/__init__.py
VACUUM_FEATURES = {'pause': 4, 'stop': 8, 'return_home': 16, 'fan_speed': 32,
                   'locate': 512, 'start': 8192}                  # vacuum/const.py

# Keys remote.send_command takes on an Android TV: androidtvremote2's RemoteKeyCode names without
# the KEYCODE_ prefix (each checked against the enum the running integration ships).
ANDROID_TV_KEYS = (
    'POWER', 'HOME', 'BACK', 'MENU', 'SETTINGS', 'SEARCH', 'ASSIST', 'INFO', 'GUIDE', 'CAPTIONS',
    'DPAD_UP', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_RIGHT', 'DPAD_CENTER', 'ENTER',
    'VOLUME_UP', 'VOLUME_DOWN', 'VOLUME_MUTE',
    'MEDIA_PLAY_PAUSE', 'MEDIA_PLAY', 'MEDIA_PAUSE', 'MEDIA_STOP', 'MEDIA_NEXT', 'MEDIA_PREVIOUS',
    'MEDIA_REWIND', 'MEDIA_FAST_FORWARD', 'CHANNEL_UP', 'CHANNEL_DOWN', 'TV', 'TV_INPUT',
    'TV_INPUT_HDMI_1', 'TV_INPUT_HDMI_2', 'TV_INPUT_HDMI_3', 'TV_INPUT_HDMI_4',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
)


def _bits(features: int, table: dict) -> dict:
    return {name: bool(features & bit) for name, bit in table.items()}


def _no_effect(name) -> bool:
    return str(name).strip().lower() in ('', 'none', 'off')


def _pct(value, scale: float):
    return round(value * 100 / scale) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _light_caps(state: str | None, a: dict, f: int) -> dict:
    modes = [m for m in a.get('supported_color_modes') or [] if isinstance(m, str)]
    temp = None
    if 'color_temp' in modes:
        temp = {'min_kelvin': a.get('min_color_temp_kelvin'), 'max_kelvin': a.get('max_color_temp_kelvin')}
    on = state == 'on'
    effect = a.get('effect')
    return {
        'power': True,
        'brightness': any(m in COLOR_MODES_BRIGHTNESS for m in modes),
        'color': any(m in COLOR_MODES_COLOR for m in modes),
        'white': 'white' in modes,
        'temp': temp,
        'effects': [e for e in a.get('effect_list') or [] if isinstance(e, str) and not _no_effect(e)],
        'transition': bool(f & LIGHT_TRANSITION),
        'flash': bool(f & LIGHT_FLASH),
        'color_modes': modes,
        'current': {
            'on': on,
            'brightness': _pct(a.get('brightness'), 255) if on else None,
            'rgb': list(a['rgb_color']) if on and isinstance(a.get('rgb_color'), (list, tuple)) else None,
            'kelvin': a.get('color_temp_kelvin') if on else None,
            'effect': effect if on and isinstance(effect, str) and not _no_effect(effect) else None,
            'color_mode': a.get('color_mode'),
        },
    }


def _media_caps(state: str | None, a: dict, f: int) -> dict:
    caps = _bits(f, MEDIA_FEATURES)
    caps['power'] = caps['turn_on'] or caps['turn_off']
    caps['volume'] = caps['volume_set'] or caps['volume_step']
    sources = a.get('source_list')
    caps['sources'] = list(sources) if caps['select_source'] and isinstance(sources, list) else []
    caps['current'] = {
        'state': state,
        'volume': _pct(a.get('volume_level'), 1),
        'muted': a.get('is_volume_muted'),
        'source': a.get('source'),
        'app': a.get('app_name'),
        'title': a.get('media_title'),
    }
    return caps


def _remote_caps(state: str | None, a: dict, f: int, integration: str | None) -> dict:
    activities = a.get('activity_list')
    return {
        'power': True,
        'send_command': True,               # remote.send_command needs no feature bit
        'keys': list(ANDROID_TV_KEYS) if integration == 'androidtv_remote' else [],
        'activity': bool(f & REMOTE_ACTIVITY),
        'activities': list(activities) if isinstance(activities, list) else [],
        'learn': bool(f & REMOTE_LEARN),
        'current': {'on': state == 'on', 'activity': a.get('current_activity')},
    }


def _fan_caps(state, a, f):
    caps = _bits(f, FAN_FEATURES)
    caps['power'] = caps['turn_on'] or caps['turn_off']
    caps['preset_modes'] = list(a.get('preset_modes') or []) if caps['presets'] else []
    caps['current'] = {'on': state == 'on', 'percentage': a.get('percentage'),
                       'preset': a.get('preset_mode'), 'oscillating': a.get('oscillating'),
                       'direction': a.get('direction')}
    return caps


def _cover_caps(state, a, f):
    caps = _bits(f, COVER_FEATURES)
    caps['tilt'] = caps['open_tilt'] or caps['close_tilt'] or caps['tilt_position']
    caps['current'] = {'state': state, 'position': a.get('current_position'),
                       'tilt': a.get('current_tilt_position')}
    return caps


def _climate_caps(state, a, f):
    caps = _bits(f, CLIMATE_FEATURES)
    caps['power'] = caps['turn_on'] or caps['turn_off']
    caps['hvac_modes'] = list(a.get('hvac_modes') or [])
    caps['fan_mode_list'] = list(a.get('fan_modes') or []) if caps['fan_modes'] else []
    caps['preset_modes'] = list(a.get('preset_modes') or []) if caps['presets'] else []
    caps['min_temp'], caps['max_temp'] = a.get('min_temp'), a.get('max_temp')
    caps['current'] = {'mode': state, 'temperature': a.get('current_temperature'),
                       'target': a.get('temperature'), 'humidity': a.get('current_humidity')}
    return caps


def capabilities(entity_id: str, state: str | None, attrs: dict, integration: str | None = None) -> dict:
    """What `entity_id` can do, read from its attributes and supported_features."""
    domain = entity_id.split('.', 1)[0]
    a = attrs or {}
    f = a.get('supported_features') or 0
    f = f if isinstance(f, int) else 0
    if domain == 'light':
        return _light_caps(state, a, f)
    if domain == 'media_player':
        return _media_caps(state, a, f)
    if domain == 'remote':
        return _remote_caps(state, a, f, integration)
    if domain in ('switch', 'input_boolean', 'siren', 'humidifier'):
        return {'power': True, 'current': {'on': state == 'on'}}
    if domain == 'fan':
        return _fan_caps(state, a, f)
    if domain == 'cover':
        return _cover_caps(state, a, f)
    if domain == 'climate':
        return _climate_caps(state, a, f)
    if domain == 'lock':
        return {'lock': True, 'unlock': True, 'open': bool(f & LOCK_OPEN), 'current': {'state': state}}
    if domain == 'vacuum':
        return {**_bits(f, VACUUM_FEATURES), 'current': {'state': state}}
    if domain == 'scene':
        return {'activate': True}
    if domain == 'script':
        return {'run': True, 'current': {'running': state == 'on'}}
    if domain in ('button', 'input_button'):
        return {'press': True}
    if domain in ('sensor', 'binary_sensor'):
        return {'read_only': True, 'value': state, 'unit': a.get('unit_of_measurement'),
                'device_class': a.get('device_class')}
    return {}


# ── what kind of thing it is, and whether the owner wants to see it ──

_TV_WORDS = re.compile(r'\btv\b|television|fernseher|chromecast|bravia|تلفزيون|تلفاز', re.I)
ECHO_PREFIX = 'mira_'           # the owner's Echo runs as "Mira": its settings are Mira's own
HIDDEN_DOMAINS = frozenset({
    'update', 'sun', 'zone', 'person', 'todo', 'tts', 'conversation', 'event', 'select', 'number',
    'stt', 'wake_word', 'assist_satellite', 'ai_task',       # the rest of Assist's plumbing
})
HIDDEN_PLATFORMS = frozenset({'sun', 'backup'})


def kind_of(entity_id: str, attrs: dict, words: str = '') -> str:
    domain = entity_id.split('.', 1)[0]
    device_class = (attrs or {}).get('device_class')
    if domain == 'switch':
        return 'plug' if device_class == 'outlet' else 'switch'
    if domain == 'input_boolean':
        return 'switch'
    if domain == 'media_player':
        if device_class == 'tv':
            return 'tv'
        if device_class in ('speaker', 'receiver'):
            return 'speaker'
        return 'tv' if _TV_WORDS.search(words or '') else 'speaker'
    if domain in ('sensor', 'binary_sensor'):
        return 'sensor'
    if domain == 'input_button':
        return 'button'
    return domain


def hidden_reason(entity_id: str, entry: dict | None, echo_devices=frozenset()) -> str | None:
    """Why the inventory leaves this entity out by default, or None."""
    domain, object_id = entity_id.split('.', 1)
    entry = entry or {}
    if entry.get('disabled_by'):
        return 'disabled'
    if entry.get('hidden_by'):
        return 'hidden'
    if entry.get('entity_category') in ('config', 'diagnostic'):
        return entry['entity_category']
    on_echo = (entry.get('device_id') in echo_devices if entry.get('device_id')
               else object_id.startswith(ECHO_PREFIX) and entry.get('platform') in (None, 'esphome'))
    if on_echo and domain not in ('light', 'media_player'):
        return 'echo'               # the ring light and the speaker are the owner's to use
    if domain in HIDDEN_DOMAINS:
        return 'domain'
    if entry.get('platform') in HIDDEN_PLATFORMS:
        return 'platform'
    return None


# ── words for the owner ──────────────────────────────────────────────

_EFFECT_AR = {
    'candle': 'شمعة', 'fire': 'نار', 'fireplace': 'موقد', 'prism': 'موشور', 'sparkle': 'بريق',
    'opal': 'أوبال', 'glisten': 'لمعان', 'underwater': 'تحت الماء', 'cosmos': 'فضاء',
    'sunbeam': 'شعاع شمس', 'enchant': 'سحر', 'sunrise': 'شروق', 'sunset': 'غروب',
    'pulse': 'نبض', 'heartbeat': 'نبضات قلب', 'ripple': 'تموّج', 'twinkle': 'وميض',
    'embers': 'جمر', 'aurora': 'شفق', 'rainbow': 'قوس قزح', 'comet': 'مذنّب', 'chase': 'مطاردة',
    'scanner': 'ماسح', 'spiral': 'دوّامة', 'wipe': 'مسح', 'bounce': 'ارتداد', 'alert': 'تنبيه',
    'beacon': 'منارة', 'colorloop': 'دورة ألوان', 'breathe': 'تنفّس', 'strobe': 'ومّاض',
}
_SENSOR_AR = {
    'temperature': 'حرارة', 'humidity': 'رطوبة', 'power': 'استطاعة', 'energy': 'طاقة',
    'voltage': 'جهد', 'current': 'تيار', 'battery': 'بطارية', 'illuminance': 'إضاءة',
    'motion': 'حركة', 'occupancy': 'إشغال', 'presence': 'وجود', 'door': 'باب', 'window': 'نافذة',
    'opening': 'فتح', 'plug': 'قابس', 'running': 'تشغيل', 'connectivity': 'اتصال',
    'problem': 'أعطال', 'smoke': 'دخان', 'moisture': 'تسرّب ماء', 'timestamp': 'وقت',
    'enum': 'حالة', 'pm25': 'غبار دقيق', 'co2': 'ثاني أكسيد الكربون', 'pressure': 'ضغط',
}
_HVAC_AR = {'off': 'إطفاء', 'heat': 'تدفئة', 'cool': 'تبريد', 'heat_cool': 'تدفئة وتبريد',
            'auto': 'تلقائي', 'dry': 'تجفيف', 'fan_only': 'مروحة فقط'}
_COVER_NOUN = {'garage': ('باب كراج', 'garage door'), 'door': ('باب', 'door'),
               'gate': ('بوابة', 'gate'), 'window': ('نافذة', 'window'),
               'awning': ('مظلّة', 'awning'), 'curtain': ('ستارة', 'curtain')}


def _few(items, n=4, ar=False, words=None):
    """The first n items and how many more; Arabic uses its comma and, when given, its words."""
    shown = [(words or {}).get(str(i).lower(), str(i)) if ar else str(i) for i in items[:n]]
    more = f' +{len(items) - n}' if len(items) > n else ''
    return ('، ' if ar else ', ').join(shown) + more


def summarize(kind: str, caps: dict, *, members: int = 0) -> tuple[str, str]:
    """One short line each, Arabic and English, of what the thing can do."""
    ar, en = [], []

    def add(a, e):
        ar.append(a)
        en.append(e)

    if kind == 'light':
        if members:
            add(f'مجموعة أضواء ({members})', f'group of {members} lights')
        if caps.get('color'):
            add('ضوء ملوّن', 'colour light')
        elif caps.get('temp'):
            add('ضوء أبيض متدرّج', 'tunable white light')
        elif caps.get('brightness'):
            add('ضوء قابل للتعتيم', 'dimmable light')
        else:
            add('ضوء تشغيل وإطفاء', 'on/off light')
        if caps.get('brightness') and (caps.get('color') or caps.get('temp')):
            add('سطوع', 'brightness')
        temp = caps.get('temp') or {}
        if temp.get('min_kelvin') and temp.get('max_kelvin'):
            add(f"حرارة بيضاء {temp['min_kelvin']}–{temp['max_kelvin']}K",
                f"white temperature {temp['min_kelvin']}–{temp['max_kelvin']}K")
        elif temp:
            add('حرارة بيضاء', 'white temperature')
        if caps.get('white'):
            add('أبيض صافٍ', 'pure white')
        if caps.get('effects'):
            add('تأثيرات: ' + _few(caps['effects'], ar=True, words=_EFFECT_AR), 'effects: ' + _few(caps['effects']))
    elif kind in ('tv', 'speaker'):
        add(*(('تلفزيون', 'TV') if kind == 'tv' else ('سمّاعة', 'speaker')))
        if caps.get('turn_on') and caps.get('turn_off'):
            add('تشغيل وإطفاء', 'on/off')
        elif caps.get('turn_on') or caps.get('turn_off'):
            add(*(('تشغيل', 'turn on') if caps.get('turn_on') else ('إطفاء', 'turn off')))
        if caps.get('volume_set'):
            add('مستوى الصوت', 'volume level')
        elif caps.get('volume_step'):
            add('رفع الصوت وخفضه', 'volume up/down')
        if caps.get('mute'):
            add('كتم', 'mute')
        if caps.get('play') and caps.get('pause'):
            add('إيقاف مؤقت واستئناف', 'play/pause')
        elif caps.get('pause') or caps.get('play'):
            add(*(('إيقاف مؤقت', 'pause') if caps.get('pause') else ('استئناف', 'play')))
        if caps.get('next') or caps.get('previous'):
            add('التالي والسابق', 'next/previous')
        if caps.get('sources'):
            add('المصادر: ' + _few(caps['sources'], 3, ar=True),
                'sources: ' + _few(caps['sources'], 3))
        if caps.get('announce'):
            add('إعلانات صوتية', 'announcements')
    elif kind == 'remote':
        add('ريموت', 'remote')
        if caps.get('keys'):
            add('أزرار التنقّل والصوت والقنوات', 'navigation, volume and channel keys')
        else:
            add('إرسال أوامر', 'send commands')
        if caps.get('activities'):
            add('تطبيقات: ' + _few(caps['activities'], 3, ar=True),
                'apps: ' + _few(caps['activities'], 3))
    elif kind in ('switch', 'plug'):
        add(*(('مقبس ذكي', 'smart plug') if kind == 'plug' else ('مفتاح', 'switch')))
        add('تشغيل وإطفاء', 'on/off')
    elif kind == 'fan':
        add('مروحة', 'fan')
        if caps.get('power'):
            add('تشغيل وإطفاء', 'on/off')
        if caps.get('speed'):
            add('سرعة', 'speed')
        if caps.get('oscillate'):
            add('تأرجح', 'oscillation')
        if caps.get('direction'):
            add('اتجاه الدوران', 'direction')
        if caps.get('preset_modes'):
            add('أنماط: ' + _few(caps['preset_modes'], 3, ar=True),
                'modes: ' + _few(caps['preset_modes'], 3))
    elif kind == 'cover':
        add(*_COVER_NOUN.get(caps.get('device_class'), ('ستارة', 'blind')))
        if caps.get('open') or caps.get('close'):
            add('فتح وإغلاق', 'open/close')
        if caps.get('position'):
            add('تحديد الموضع', 'position')
        if caps.get('stop'):
            add('إيقاف', 'stop')
        if caps.get('tilt'):
            add('إمالة', 'tilt')
    elif kind == 'climate':
        add('تكييف', 'climate')
        if caps.get('target_temperature'):
            low, high = caps.get('min_temp'), caps.get('max_temp')
            span = f' {low:g}–{high:g}°' if isinstance(low, (int, float)) and isinstance(high, (int, float)) else ''
            add('درجة الحرارة' + span, 'temperature' + span)
        modes = [m for m in caps.get('hvac_modes') or [] if m != 'off']
        if modes:
            add('أوضاع: ' + '، '.join(_HVAC_AR.get(m, m) for m in modes), 'modes: ' + ', '.join(modes))
        if caps.get('fan_mode_list'):
            add('سرعات المروحة', 'fan speeds')
        if caps.get('target_humidity'):
            add('رطوبة', 'humidity')
    elif kind == 'lock':
        add('قفل', 'lock')
        add('قفل وفتح', 'lock/unlock')
        if caps.get('open'):
            add('فتح الباب', 'open the door')
    elif kind == 'vacuum':
        add('مكنسة روبوت', 'robot vacuum')
        if caps.get('start'):
            add('بدء التنظيف', 'start')
        if caps.get('pause'):
            add('إيقاف مؤقت', 'pause')
        if caps.get('return_home'):
            add('العودة إلى القاعدة', 'return to dock')
    elif kind == 'scene':
        add('مشهد', 'scene')
        add('تفعيل', 'activate')
    elif kind == 'script':
        add('سكربت', 'script')
        add('تشغيل', 'run')
    elif kind == 'button':
        add('زر', 'button')
        add('ضغط', 'press')
    elif kind == 'sensor':
        dc = caps.get('device_class')
        add(f'حسّاس {_SENSOR_AR[dc]}' if dc in _SENSOR_AR else 'حسّاس', f'{dc} sensor' if dc else 'sensor')
        unit = caps.get('unit')
        add('قراءة فقط' + (f' ({unit})' if unit else ''), 'read-only' + (f' ({unit})' if unit else ''))
    else:
        add(kind, kind)
    return ' · '.join(ar), ' · '.join(en)


# ── the inventory: states + registries, one record per entity ────────

_KIND_ORDER = ('light', 'plug', 'switch', 'tv', 'speaker', 'remote', 'fan', 'climate', 'cover',
               'lock', 'vacuum', 'scene', 'script', 'button', 'sensor')


def _device_name(device: dict | None) -> str:
    return ((device or {}).get('name_by_user') or (device or {}).get('name') or '').strip()


def _names(entity_id: str, entry: dict | None, device: dict | None, attrs: dict) -> tuple[str, str]:
    """(effective name, default name), the way Home Assistant composes friendly_name
    (helpers/entity_registry.py _async_get_full_entity_name, legacy naming): a registry name
    replaces everything; otherwise the device's name joined with the entity's own part, which is
    empty for the device's main entity."""
    friendly = str(attrs.get('friendly_name') or '').strip()
    registry_name = ((entry or {}).get('name') or '').strip()
    fallback = entity_id.split('.', 1)[1].replace('_', ' ')
    if entry is None:
        return friendly or fallback, friendly or fallback
    own = (entry.get('original_name') or '').strip()
    if registry_name or not friendly:
        default = ' '.join(p for p in (_device_name(device), own) if p) or fallback
    else:
        default = friendly
    if registry_name:
        return registry_name, default
    if entry.get('has_entity_name') and not own and _device_name(device):
        return _device_name(device), default         # the device's main entity carries its name
    return friendly or default, default


def build_inventory(states: list, registry: dict, *, include_hidden: bool = False) -> list[dict]:
    """Merge live states with the registries. Pure: tests feed it recorded shapes."""
    areas = {a['area_id']: a for a in registry.get('areas') or [] if isinstance(a, dict)}
    devices = {d['id']: d for d in registry.get('devices') or [] if isinstance(d, dict)}
    entries = {e['entity_id']: e for e in registry.get('entities') or [] if isinstance(e, dict)}
    extended = registry.get('extended') or {}
    echo_devices = frozenset(
        e['device_id'] for e in entries.values()
        if e.get('platform') == 'esphome' and e.get('device_id')
        and e['entity_id'].split('.', 1)[1].startswith(ECHO_PREFIX))
    live = {s['entity_id']: s for s in states if isinstance(s, dict) and 'entity_id' in s}
    ids = list(live) + ([e for e in entries if e not in live] if include_hidden else [])

    records = []
    for entity_id in ids:
        entry = entries.get(entity_id)
        reason = hidden_reason(entity_id, entry, echo_devices)
        if reason and not include_hidden:
            continue
        state = live.get(entity_id) or {}
        attrs = state.get('attributes') or {}
        device = devices.get((entry or {}).get('device_id'))
        parent = devices.get((device or {}).get('parent_device_id'))
        area_id = ((entry or {}).get('area_id') or (device or {}).get('area_id')
                   or (parent or {}).get('area_id'))
        integration = (entry or {}).get('platform')
        name, default = _names(entity_id, entry, device, attrs)
        manufacturer = (device or {}).get('manufacturer') or (parent or {}).get('manufacturer')
        model = (device or {}).get('model') or (parent or {}).get('model')
        kind = kind_of(entity_id, attrs, ' '.join(str(x) for x in (name, default, model) if x))
        caps = capabilities(entity_id, state.get('state'), attrs, integration)
        if kind == 'cover':
            caps['device_class'] = attrs.get('device_class')
        members = attrs.get('entity_id')
        members = [m for m in members if isinstance(m, str)] if isinstance(members, list) else []
        is_group = bool(attrs.get('is_hue_group')) or bool(members)
        summary_ar, summary_en = summarize(kind, caps, members=len(members) if kind == 'light' else 0)
        aliases = (extended.get(entity_id) or {}).get('aliases') or []
        records.append({
            'entity_id': entity_id,
            'domain': entity_id.split('.', 1)[0],
            'name': name,
            'default_name': default,
            'renamed': bool(((entry or {}).get('name') or '').strip()),
            'registry_name': (entry or {}).get('name'),
            'area': (areas.get(area_id) or {}).get('name') if area_id else None,
            'area_id': area_id if area_id in areas else None,
            'entity_area_id': (entry or {}).get('area_id'),   # None: it follows its device's area
            'device_id': (entry or {}).get('device_id'),
            'device': _device_name(device) or None,
            'manufacturer': manufacturer,
            'model': model,
            'integration': integration,
            'aliases': [a for a in aliases if isinstance(a, str)],
            'state': state.get('state'),
            'available': state.get('state') not in (None, 'unavailable'),
            'is_group': is_group,
            'members': members,
            'kind': kind,
            'caps': caps,
            'summary_ar': summary_ar,
            'summary_en': summary_en,
            'unique_id': (entry or {}).get('unique_id'),
            'hidden': bool(reason),
            'hidden_reason': reason,
        })
    order = {k: i for i, k in enumerate(_KIND_ORDER)}
    records.sort(key=lambda r: (r['area'] is None, (r['area'] or '').casefold(),
                                order.get(r['kind'], len(order)), r['name'].casefold(), r['entity_id']))
    return records


# ── the hub ──────────────────────────────────────────────────────────

_ENTITY_ID = re.compile(r'[a-z0-9_]+\.[a-z0-9_]+')
_SLUG = re.compile(r'[a-z0-9_]+')


def _entity_id(entity_id) -> str:
    if not isinstance(entity_id, str) or not _ENTITY_ID.fullmatch(entity_id):
        raise HubError('معرّف الجهاز غير صالح', f'invalid entity id: {entity_id!r}', 'invalid')
    return entity_id


def _label(name, what='الاسم') -> str | None:
    """A name the owner typed: stripped, None when empty, bounded."""
    if name is None:
        return None
    if not isinstance(name, str):
        raise HubError(f'{what} غير صالح', 'a name must be text', 'invalid')
    name = ' '.join(name.split())
    if len(name) > 100:
        raise HubError(f'{what} طويل جداً', 'a name must be at most 100 characters', 'invalid')
    return name or None


class Hub:
    """The owner's Home Assistant. Each call opens its own connection; nothing is kept open."""

    def __init__(self, url: str, token: str, timeout: float = 8.0):
        self.url = _clean_url(url)
        self._token = _clean_token(token)
        self.timeout = timeout

    def __repr__(self):
        return f'Hub({self.url!r})'                    # never the token

    # REST
    def _rest(self, path: str, body=None):
        status, raw = _http(self.url + '/api/' + path, token=self._token, body=body, timeout=self.timeout)
        if status in (200, 201):
            try:
                return json.loads(raw) if raw else None
            except ValueError:
                raise HubError(_BROKEN, f'/api/{path} did not answer JSON', 'protocol') from None
        if status in (401, 403):
            raise HubError(_REJECTED, f'Home Assistant answered {status} for /api/{path}', 'auth')
        if status == 404:
            raise HubError('غير موجود في Home Assistant', f'/api/{path} not found', 'not_found')
        try:
            message = json.loads(raw).get('message')
        except (ValueError, AttributeError):
            message = None
        if message:
            raise HubError('رفض Home Assistant الطلب: ' + str(message), f'Home Assistant refused /api/{path}: {message}', 'refused')
        raise HubError(f'تعذّر ربط البيت: {status}', f'Home Assistant answered {status} for /api/{path}', 'refused')

    def states(self) -> list[dict]:
        return self._rest('states')

    def state(self, entity_id) -> dict:
        try:
            return self._rest('states/' + _entity_id(entity_id))
        except HubError as exc:
            if exc.code == 'not_found':
                raise HubError('الجهاز غير موجود في البيت', f'{entity_id} does not exist', 'not_found') from None
            raise

    def call(self, domain, service, data: dict) -> list:
        """POST /api/services/<domain>/<service>; the states it changed."""
        if not (isinstance(domain, str) and _SLUG.fullmatch(domain)
                and isinstance(service, str) and _SLUG.fullmatch(service)):
            raise HubError('أمر غير صالح', f'invalid service {domain}.{service}', 'invalid')
        return self._rest(f'services/{domain}/{service}', dict(data or {}))

    # WebSocket
    def session(self) -> Session:
        return Session(self.url, self._token, self.timeout)

    def ws(self, commands: list[dict]) -> list:
        """Run the commands in one authenticated session; the result of each, in order."""
        with self.session() as s:
            return [s.command(c) for c in commands]

    def registry(self) -> dict:
        areas, devices, entities = self.ws([{'type': 'config/area_registry/list'},
                                            {'type': 'config/device_registry/list'},
                                            {'type': 'config/entity_registry/list'}])
        return {'areas': areas, 'devices': devices, 'entities': entities}

    def _full_registry(self, entity_ids=None) -> dict:
        """The registries plus extended entries (the list omits aliases), in one session."""
        with self.session() as s:
            areas = s.command({'type': 'config/area_registry/list'})
            devices = s.command({'type': 'config/device_registry/list'})
            entities = s.command({'type': 'config/entity_registry/list'})
            wanted = [e['entity_id'] for e in entities if entity_ids is None or e['entity_id'] in entity_ids]
            extended = s.command({'type': 'config/entity_registry/get_entries', 'entity_ids': wanted}) if wanted else {}
        return {'areas': areas, 'devices': devices, 'entities': entities, 'extended': extended or {}}

    def inventory(self, *, include_hidden=False) -> list[dict]:
        return build_inventory(self.states(), self._full_registry(), include_hidden=include_hidden)

    def record(self, entity_id) -> dict:
        """One entity's inventory record, read fresh (hidden or not)."""
        entity_id = _entity_id(entity_id)
        registry = self._full_registry({entity_id})
        try:
            states = [self.state(entity_id)]
        except HubError as exc:
            if exc.code != 'not_found':
                raise
            states = []                                 # a disabled entity has no state
        for item in build_inventory(states, registry, include_hidden=True):
            if item['entity_id'] == entity_id:
                return item
        raise HubError('الجهاز غير موجود في البيت', f'{entity_id} does not exist', 'not_found')

    # names
    def rename(self, entity_id: str, name: str | None) -> dict:
        """Give an entity the owner's name; None or '' restores Home Assistant's own."""
        entity_id = _entity_id(entity_id)
        self.ws([{'type': 'config/entity_registry/update', 'entity_id': entity_id, 'name': _label(name)}])
        item = self.record(entity_id)
        return {'entity_id': entity_id, 'name': item['name'], 'registry_name': item['registry_name'],
                'default_name': item['default_name']}

    def rename_device(self, device_id: str, name: str | None) -> dict:
        if not isinstance(device_id, str) or not re.fullmatch(r'[0-9a-zA-Z_]+', device_id):
            raise HubError('معرّف الجهاز غير صالح', f'invalid device id: {device_id!r}', 'invalid')
        device = self.ws([{'type': 'config/device_registry/update', 'device_id': device_id,
                           'name_by_user': _label(name)}])[0]
        return {'device_id': device_id, 'name': _device_name(device) or None,
                'name_by_user': device.get('name_by_user'), 'default_name': (device.get('name') or '').strip() or None}

    # areas
    def areas(self) -> list[dict]:
        return [{'area_id': a.get('area_id'), 'name': a.get('name'), 'aliases': a.get('aliases') or [],
                 'floor_id': a.get('floor_id'), 'icon': a.get('icon')}
                for a in self.ws([{'type': 'config/area_registry/list'}])[0]]

    def create_area(self, name: str) -> dict:
        name = _label(name, 'اسم الغرفة')
        if not name:
            raise HubError('اكتب اسم الغرفة', 'an area needs a name', 'invalid')
        return self.ws([{'type': 'config/area_registry/create', 'name': name}])[0]

    def set_area(self, entity_id: str, area: str | None) -> dict:
        """Put an entity in an area, by id or name; a new name creates the area; None clears the
        entity's own area (it then follows its device's). Returns the read-back."""
        entity_id = _entity_id(entity_id)
        area = _label(area, 'اسم الغرفة')
        created = None
        with self.session() as s:
            area_id = None
            if area:
                known = s.command({'type': 'config/area_registry/list'})
                by_id = {a['area_id']: a for a in known}
                if area in by_id:
                    area_id = area
                else:
                    match = [a for a in known if a['name'].casefold() == area.casefold()
                             or area.casefold() in (x.casefold() for x in a.get('aliases') or [])]
                    if match:
                        area_id = match[0]['area_id']
                    else:
                        created = s.command({'type': 'config/area_registry/create', 'name': area})
                        area_id = created['area_id']
            s.command({'type': 'config/entity_registry/update', 'entity_id': entity_id, 'area_id': area_id})
        item = self.record(entity_id)
        return {'entity_id': entity_id, 'area_id': item['entity_area_id'], 'area': item['area'],
                'effective_area_id': item['area_id'], 'created': created}

    # discovery
    def discovered(self) -> list[dict]:
        """Config flows waiting for the owner (Home Assistant already leaves out his own wizards)."""
        flows = self.ws([{'type': 'config_entries/flow/progress'}])[0] or []
        out = []
        for flow in flows:
            context = flow.get('context') or {}
            placeholders = context.get('title_placeholders') or {}
            out.append({'flow_id': flow.get('flow_id'), 'domain': flow.get('handler'),
                        'title': placeholders.get('name') or flow.get('handler'),
                        'source': context.get('source'), 'step_id': flow.get('step_id')})
        return out

    # voice names
    def aliases(self, entity_id) -> list[str]:
        """The names the owner calls an entity by (Home Assistant's own computed name, stored as
        a null placeholder, is not one of them)."""
        entry = self.ws([{'type': 'config/entity_registry/get', 'entity_id': _entity_id(entity_id)}])[0]
        return [a for a in entry.get('aliases') or [] if isinstance(a, str)]

    def set_aliases(self, entity_id, names: list) -> list[str]:
        """Replace the owner's aliases. A computed-name placeholder already there is kept, first."""
        entity_id = _entity_id(entity_id)
        if not isinstance(names, (list, tuple)):
            raise HubError('الأسماء غير صالحة', 'aliases must be a list', 'invalid')
        clean = []
        for name in names:
            name = _label(name)
            if name and name.casefold() not in (c.casefold() for c in clean):
                clean.append(name)
        with self.session() as s:
            current = s.command({'type': 'config/entity_registry/get', 'entity_id': entity_id}).get('aliases') or []
            keep = [None] if None in current else []
            entry = s.command({'type': 'config/entity_registry/update', 'entity_id': entity_id,
                               'aliases': keep + clean})['entity_entry']
        return [a for a in entry.get('aliases') or [] if isinstance(a, str)]
