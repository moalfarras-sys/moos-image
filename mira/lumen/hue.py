"""The Philips Hue bridge, spoken to directly: its CLIP v2 API and its Entertainment stream.

A Hue Bridge (v2, BSB002 and later) is the hub of a Zigbee network of lamps. Home Assistant
already drives it, one HTTPS command per change, and the bridge accepts only about ten such
commands a second: plenty for a scene, far too few for light that follows the screen. The bridge's
own answer is the Entertainment API: Lumen asks it over HTTPS to start an "entertainment area",
then sends up to 20 channel colours per UDP datagram, many times a second, inside DTLS
(`dtls.py`); the bridge forwards them to the lamps over Zigbee at its own pace. A stream needs a
key pair Home Assistant's key does not have (the PSK "clientkey"), which only link-button pairing
hands out, so Lumen pairs with the bridge itself.

What is deliberate:

* HTTPS without certificate validation, plus trust on first use. The bridge's certificate is
  issued for its bridge id (CN=ecb5fafffe…) by Signify's private "root-bridge" CA, never for a
  host name or an address, so neither the system's CA store nor a hostname check can accept it.
  Lumen records the certificate's SHA-256 when it pairs (`pair()` returns it as `cert_sha256`)
  and, when given that value later, refuses a bridge that presents another certificate.
* No proxy and no redirect: the bridge is on the LAN and never redirects. A request goes to the
  address given and nowhere else; a 3xx answer is an error, not a hop.
* Every request has a timeout. Every failure becomes a HueError in the bridge's own words (CLIP v2
  answers `{"errors": [{"description": …}], "data": […]}`); a bridge that cannot be reached is a
  BridgeUnreachable.
* Discovery stays on the LAN: the system's mDNS daemon (Avahi, which caches every record it has
  seen), Lumen's own mDNS query (zeroconf) and an SSDP search, side by side. Measured on the
  station's Wi-Fi, zeroconf alone missed the bridge in 2 of 8 three-second windows, and every
  find came after its second question (~1.2 s): the first asks for a unicast answer, which on
  the port 5353 it shares with Avahi is delivered to one socket only, and Wi-Fi drops multicast
  answers. Avahi answered from its cache in about a second each time. SSDP answers are unicast
  to a port the default MoOS firewall zone does not open, so on MoOS it rarely helps; it stays
  for systems without mDNS. The cloud endpoint tells Signify the home's public address, so it
  is asked only when the caller says so.
* A lamp's name is its DEVICE's name. The Hue app renames devices; light resources keep stale
  names ("Hue lampe" is the lamp the owner calls "Büro").
* Colour is Philips' published sRGB → XYZ → xy conversion, clamped into the lamp's own gamut
  triangle: a point outside it is rendered as whatever the firmware picks, not the nearest colour.
* The keys never appear in a repr, an error or a log line.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import re
import socket
import ssl
import struct
import subprocess
import threading
import time

from lumen.dtls import DtlsError, DtlsPskClient

HTTPS_PORT = 443
STREAM_PORT = 2100
MAX_CHANNELS = 20
MDNS_TYPE = '_hue._tcp.local.'
SSDP_ADDR = ('239.255.255.250', 1900)
CLOUD_DISCOVERY = 'discovery.meethue.com'
UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
BRIDGE_ID = re.compile(r'[0-9a-f]{16}')

# Philips' published gamuts, for a lamp that names its gamut type but does not list the corners.
GAMUTS = {
    'A': {'red': [0.704, 0.296], 'green': [0.2151, 0.7106], 'blue': [0.138, 0.08]},
    'B': {'red': [0.675, 0.322], 'green': [0.409, 0.518], 'blue': [0.167, 0.04]},
    'C': {'red': [0.6915, 0.3083], 'green': [0.17, 0.7], 'blue': [0.1532, 0.0475]},
}
D65 = (0.3127, 0.3290)
DEFAULT_MIREK = (153, 500)


class HueError(RuntimeError):
    """The bridge said no, in its own words (`status`: HTTP status; `error_type`: v1 error type)."""

    def __init__(self, message: str, *, status: int | None = None, error_type: int | None = None):
        super().__init__(message)
        self.status = status
        self.error_type = error_type


class BridgeUnreachable(HueError):
    """No answer at all: the bridge is off, elsewhere, or the network is down."""


class LinkButtonNotPressed(HueError):
    """Pairing ended before anyone pressed the bridge's round button (`cancelled`: by the caller)."""

    def __init__(self, message: str, *, cancelled: bool = False):
        super().__init__(message, error_type=101)
        self.cancelled = cancelled


# ── HTTPS ─────────────────────────────────────────────────────────────

def _tls_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False              # the certificate names a bridge id, not a host
    ctx.verify_mode = ssl.CERT_NONE         # issued by Signify's private CA; see the docstring
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def _why(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return 'timed out'
    if isinstance(exc, ConnectionRefusedError):
        return 'connection refused'
    if isinstance(exc, ssl.SSLError):
        return f'TLS: {exc.reason or exc}'
    if isinstance(exc, OSError) and exc.strerror:
        return exc.strerror
    return str(exc) or type(exc).__name__


class _Link:
    """One kept-alive HTTPS connection to one bridge; requests take turns."""

    def __init__(self, host: str, timeout: float, cert_sha256: str | None = None,
                 port: int = HTTPS_PORT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.pin = cert_sha256.lower() if cert_sha256 else None
        self.seen: str | None = None            # SHA-256 of the certificate last presented
        self._conn: http.client.HTTPSConnection | None = None
        self._lock = threading.Lock()

    def close(self) -> None:
        with self._lock:
            self._drop()

    def _drop(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def _connect(self) -> http.client.HTTPSConnection:
        conn = http.client.HTTPSConnection(self.host, self.port, timeout=self.timeout,
                                           context=_tls_context())
        conn.connect()
        der = conn.sock.getpeercert(binary_form=True) or b''
        digest = hashlib.sha256(der).hexdigest()
        if self.pin and digest != self.pin:
            conn.close()
            raise HueError(f'the device at {self.host} is not the bridge Lumen paired with (its '
                           'certificate changed); pair again if the bridge was replaced')
        self.seen = digest
        return conn

    def exchange(self, method: str, path: str, body=None, headers=None,
                 retry: bool = True) -> tuple[int, bytes]:
        data = None if body is None else json.dumps(body).encode('utf-8')
        sent = {'Accept': 'application/json'}
        if data is not None:
            sent['Content-Type'] = 'application/json'
        sent.update(headers or {})
        with self._lock:
            for attempt in (0, 1):
                fresh = self._conn is None
                try:
                    if self._conn is None:
                        self._conn = self._connect()
                    self._conn.request(method, path, body=data, headers=sent)
                    response = self._conn.getresponse()
                    payload = response.read()
                    if response.will_close:
                        self._drop()
                    return response.status, payload
                except HueError:
                    self._drop()
                    raise
                except (http.client.HTTPException, OSError) as exc:
                    self._drop()
                    # a kept-alive connection the bridge had already closed: once more, fresh
                    if attempt == 0 and retry and not fresh and not isinstance(exc, TimeoutError):
                        continue
                    raise BridgeUnreachable(f'the Hue bridge at {self.host} did not answer '
                                            f'({_why(exc)})') from None
        return 0, b''                           # not reached: the second attempt returns or raises


def _errors(doc) -> list[tuple[str, int | None]]:
    """(description, v1 type) for every error in a CLIP v2 or v1 answer."""
    found = []
    if isinstance(doc, dict):
        for err in doc.get('errors') or []:
            if isinstance(err, dict):
                found.append((str(err.get('description') or 'error'), None))
    elif isinstance(doc, list):
        for entry in doc:
            err = entry.get('error') if isinstance(entry, dict) else None
            if isinstance(err, dict):
                kind = err.get('type')
                found.append((str(err.get('description') or 'error'),
                              kind if isinstance(kind, int) else None))
    return found


def _decode(status: int, payload: bytes, host: str):
    try:
        doc = json.loads(payload) if payload else None
    except ValueError:
        doc = None
    if 300 <= status < 400:
        raise HueError(f'the device at {host} answered with a redirect (HTTP {status}); '
                       'Lumen does not follow it', status=status)
    errors = _errors(doc)
    data = doc.get('data') if isinstance(doc, dict) else None
    # 207: the bridge took the command and warns it may not reach a lamp; the caller sees 'errors'
    if errors and (status >= 400 or not data):
        raise HueError('; '.join(text for text, _ in errors), status=status,
                       error_type=errors[0][1])
    if status >= 400:
        # the bridge answers these with an HTML page, not with CLIP v2 errors
        meaning = {401: 'it does not know this application key; pair again',
                   403: 'it does not know this application key; pair again',
                   429: 'too many requests at once; slow down',
                   503: 'it is busy; try again in a moment'}.get(status, '')
        raise HueError(f'the Hue bridge answered HTTP {status}' + (f': {meaning}' if meaning else ''),
                       status=status)
    if doc is None:
        raise HueError(f'the device at {host} did not answer in JSON', status=status)
    return doc


# ── colour ────────────────────────────────────────────────────────────

def _cross(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _nearest_on_segment(p, a, b) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / span
    t = max(0.0, min(1.0, t))
    return a[0] + t * dx, a[1] + t * dy


def clamp_to_gamut(x: float, y: float, gamut: dict | None) -> tuple[float, float]:
    """(x, y) itself when the lamp can show it, else the nearest point on its gamut triangle."""
    if not gamut:
        return x, y
    r, g, b = gamut['red'], gamut['green'], gamut['blue']
    p = (x, y)
    d1, d2, d3 = _cross(r, g, p), _cross(g, b, p), _cross(b, r, p)
    if not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0)):
        return x, y
    candidates = [_nearest_on_segment(p, a, c) for a, c in ((r, g), (g, b), (b, r))]
    return min(candidates, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)


def rgb_to_xy(r: float, g: float, b: float, gamut: dict | None = None) -> tuple[float, float]:
    """sRGB (0–255) → CIE xy, as Philips publishes it: undo the sRGB gamma, the sRGB/D65 matrix
    to XYZ, normalise, then clamp into the lamp's gamut. Black has no colour: it maps to white."""
    def linear(v: float) -> float:
        v = max(0.0, min(255.0, float(v))) / 255.0
        return ((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92
    rl, gl, bl = linear(r), linear(g), linear(b)
    big_x = rl * 0.4124 + gl * 0.3576 + bl * 0.1805
    big_y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722
    big_z = rl * 0.0193 + gl * 0.1192 + bl * 0.9505
    total = big_x + big_y + big_z
    x, y = (big_x / total, big_y / total) if total > 0 else D65
    return clamp_to_gamut(x, y, gamut)


def kelvin_to_mirek(kelvin: float, mirek_range=None) -> int:
    """Colour temperature → mirek (10⁶ / K), clamped into the lamp's own white range."""
    try:
        kelvin = float(kelvin)
    except (TypeError, ValueError):
        kelvin = math.nan
    if not kelvin > 0 or math.isinf(kelvin):
        raise HueError('a colour temperature is a positive number of kelvin')
    low, high = mirek_range or DEFAULT_MIREK
    return int(max(low, min(high, round(1_000_000 / kelvin))))


# ── the Entertainment stream's packet ─────────────────────────────────

def _u16(value) -> int:
    v = float(value)
    v = 0.0 if math.isnan(v) else max(0.0, min(255.0, v))
    return int(round(v * 65535 / 255))


def stream_packet(config_id: str, seq: int, colors: dict) -> bytes:
    """HueStream v2.0: 'HueStream', version 2.0, sequence, 2 reserved, colour space 0 (RGB),
    1 reserved, the area's id as 36 ASCII bytes, then per channel: id, R, G, B (big-endian
    uint16). Colours arrive as 0–255 floats; at most 20 channels, lowest ids first."""
    ident = config_id.encode('ascii')
    if len(ident) != 36:
        raise HueError('an entertainment area id is a 36-character UUID')
    out = bytearray(b'HueStream')
    out += bytes((2, 0, seq & 0xFF, 0, 0, 0, 0))
    out += ident
    for channel in sorted(colors)[:MAX_CHANNELS]:
        if not 0 <= int(channel) <= 255:
            raise HueError(f'channel {channel} is not a Hue channel id')
        r, g, b = colors[channel]
        out.append(int(channel))
        out += struct.pack('>HHH', _u16(r), _u16(g), _u16(b))
    return bytes(out)


class HueStream:
    """An open Entertainment stream. `send()` many times a second; `close()` when done.

    The bridge ends a stream that has been silent for ten seconds, and screen capture sends
    nothing while the picture stands still, so the last frame is repeated once a second while
    the caller is quiet."""

    KEEPALIVE = 1.0

    def __init__(self, bridge: 'HueBridge', config_id: str, channels: list[int], client):
        self.config_id = config_id
        self.channels = list(channels)
        self.stop_error = ''                 # why the bridge was not told to stop, if it was not
        self._known = set(self.channels)
        self._bridge = bridge
        self._client = client
        self._seq = 0
        self._last: dict = {}
        self._last_at = time.monotonic()
        self._lock = threading.Lock()
        self._closed = threading.Event()
        self._keeper = threading.Thread(target=self._keepalive, daemon=True,
                                        name='lumen-hue-keepalive')
        self._keeper.start()

    def __repr__(self) -> str:
        return f'<HueStream {self.config_id} channels={self.channels}>'

    def __enter__(self) -> 'HueStream':
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def send(self, colors: dict) -> None:
        """{channel id: (r, g, b) 0–255}. Channels the area does not have are ignored."""
        frame = {int(ch): rgb for ch, rgb in colors.items() if int(ch) in self._known}
        if not frame:
            return
        with self._lock:
            if self._closed.is_set():
                raise HueError('the light stream is closed')
            self._last.update(frame)
            self._write(frame)

    def _write(self, frame: dict) -> None:
        packet = stream_packet(self.config_id, self._seq, frame)
        self._seq = (self._seq + 1) & 0xFF
        try:
            self._client.send(packet)
        except DtlsError as exc:
            raise HueError(f'the light stream to the bridge was lost: {exc}') from None
        self._last_at = time.monotonic()

    def _keepalive(self) -> None:
        while not self._closed.wait(self.KEEPALIVE / 2):
            with self._lock:
                if self._closed.is_set():
                    return
                if self._last and time.monotonic() - self._last_at >= self.KEEPALIVE:
                    try:
                        self._write(dict(self._last))
                    except HueError:
                        return              # the caller's next send() reports it

    def close(self) -> None:
        """Close the DTLS session, then tell the bridge the area is free. Idempotent."""
        with self._lock:
            if self._closed.is_set():
                return
            self._closed.set()
            self._client.close()
        try:
            self._bridge._call('PUT', f'/entertainment_configuration/{self.config_id}',
                               {'action': 'stop'})
        except HueError as exc:
            self.stop_error = str(exc)


# ── the bridge ────────────────────────────────────────────────────────

def _xy(value) -> list[float] | None:
    if isinstance(value, dict) and 'x' in value and 'y' in value:
        return [float(value['x']), float(value['y'])]
    return None


def _caps(light: dict) -> dict:
    color = light.get('color') or {}
    ct = light.get('color_temperature') or {}
    schema = ct.get('mirek_schema') or {}
    gamut_type = color.get('gamut_type') if color else None
    gamut = None
    if isinstance(color.get('gamut'), dict):
        corners = {k: _xy(color['gamut'].get(k)) for k in ('red', 'green', 'blue')}
        gamut = corners if all(corners.values()) else None
    if gamut is None and gamut_type in GAMUTS:
        gamut = {k: list(v) for k, v in GAMUTS[gamut_type].items()}
    effects = (light.get('effects') or {}).get('effect_values') or []
    return {
        'color': bool(color),
        'gamut': gamut,
        'gamut_type': gamut_type,
        'mirek_range': ([int(schema['mirek_minimum']), int(schema['mirek_maximum'])]
                        if 'mirek_minimum' in schema and 'mirek_maximum' in schema
                        else (list(DEFAULT_MIREK) if ct else None)),
        'effects': [e for e in effects if e != 'no_effect'],
    }


class HueBridge:
    """One bridge, reached with an application key (and a client key when it may stream)."""

    def __init__(self, host: str, app_key: str, client_key: str | None = None,
                 bridge_id: str | None = None, timeout: float = 6.0, *,
                 cert_sha256: str | None = None):
        if not host or not app_key:
            raise HueError('a Hue bridge needs an address and an application key')
        self.host = host
        self.timeout = float(timeout)
        self._app_key = app_key
        self._client_key = client_key or None
        self._bridge_id = bridge_id.lower() if bridge_id else None
        self._link = _Link(host, self.timeout, cert_sha256)
        self._caps: dict[str, dict] = {}

    def __repr__(self) -> str:
        return f'<HueBridge {self.host} {self._bridge_id or "?"}>'

    @property
    def cert_sha256(self) -> str | None:
        """The certificate fingerprint seen on the last connection (or the one pinned)."""
        return self._link.seen or self._link.pin

    @property
    def can_stream(self) -> bool:
        return bool(self._client_key)

    def close(self) -> None:
        self._link.close()

    def _call(self, method: str, resource: str, body=None) -> dict:
        status, payload = self._link.exchange(method, '/clip/v2/resource' + resource, body,
                                              {'hue-application-key': self._app_key},
                                              retry=method in ('GET', 'PUT'))
        doc = _decode(status, payload, self.host)
        if not isinstance(doc, dict):
            raise HueError('the bridge answered something that is not CLIP v2', status=status)
        return doc

    def _everything(self) -> dict[str, list[dict]]:
        """Every resource in one request: one consistent snapshot, one round trip."""
        by_type: dict[str, list[dict]] = {}
        for item in self._call('GET', '').get('data') or []:
            if isinstance(item, dict):
                by_type.setdefault(item.get('type', ''), []).append(item)
        return by_type

    def bridge_id(self) -> str:
        if not self._bridge_id:
            data = self._call('GET', '/bridge').get('data') or []
            found = str((data[0] if data else {}).get('bridge_id') or '').lower()
            if not BRIDGE_ID.fullmatch(found):
                raise HueError('the bridge did not say its id')
            self._bridge_id = found
        return self._bridge_id

    def lights(self) -> list[dict]:
        res = self._everything()
        devices = {d['id']: d for d in res.get('device', []) if 'id' in d}
        reachable = {}
        for z in res.get('zigbee_connectivity', []):
            owner = (z.get('owner') or {}).get('rid')
            if owner:
                reachable[owner] = z.get('status') == 'connected'
        renders = set()                     # light ids and device ids that take a stream
        for ent in res.get('entertainment', []):
            if ent.get('renderer'):
                renders.add((ent.get('owner') or {}).get('rid'))
                renders.add((ent.get('renderer_reference') or {}).get('rid'))
        out = []
        for light in res.get('light', []):
            lid = light.get('id')
            if not lid:
                continue
            device_id = (light.get('owner') or {}).get('rid', '')
            device = devices.get(device_id) or {}
            caps = _caps(light)
            self._caps[lid] = caps
            name = ((device.get('metadata') or {}).get('name')
                    or (light.get('metadata') or {}).get('name') or lid)
            on = bool((light.get('on') or {}).get('on'))
            dimming = light.get('dimming')
            ct = light.get('color_temperature') or {}
            out.append({
                'id': lid,
                'device_id': device_id,
                'name': ' '.join(str(name).split()),
                'archetype': (light.get('metadata') or {}).get('archetype', ''),
                'on': on,
                'brightness': (float(dimming.get('brightness', 0.0)) if isinstance(dimming, dict)
                               else (100.0 if on else 0.0)),
                'xy': _xy((light.get('color') or {}).get('xy')),
                'mirek': int(ct['mirek']) if ct.get('mirek_valid') and ct.get('mirek') else None,
                'mirek_range': caps['mirek_range'],
                'gamut': caps['gamut'],
                'gamut_type': caps['gamut_type'],
                'effects': caps['effects'],
                'gradient_points': int((light.get('gradient') or {}).get('points_capable') or 0),
                'entertainment': lid in renders or device_id in renders,
                'reachable': reachable.get(device_id, True),
            })
        out.sort(key=lambda item: item['name'].casefold())
        return out

    def entertainment_configs(self) -> list[dict]:
        res = self._everything()
        ents = {e['id']: e for e in res.get('entertainment', []) if 'id' in e}
        devices = {d['id']: d for d in res.get('device', []) if 'id' in d}

        def lights_of(service_id: str) -> list[str]:
            ent = ents.get(service_id) or {}
            device = devices.get((ent.get('owner') or {}).get('rid')) or {}
            found = [s['rid'] for s in device.get('services', []) if s.get('rtype') == 'light']
            ref = ent.get('renderer_reference') or {}
            if not found and ref.get('rtype') == 'light':
                found = [ref['rid']]
            return found

        configs = []
        for cfg in res.get('entertainment_configuration', []):
            channels = []
            for ch in cfg.get('channels', []):
                pos = ch.get('position') or {}
                lights: list[str] = []
                for member in ch.get('members', []):
                    for lid in lights_of((member.get('service') or {}).get('rid', '')):
                        if lid not in lights:
                            lights.append(lid)
                channels.append({'id': int(ch.get('channel_id', 0)),
                                 'x': float(pos.get('x', 0.0)), 'y': float(pos.get('y', 0.0)),
                                 'z': float(pos.get('z', 0.0)), 'lights': lights})
            configs.append({'id': cfg.get('id', ''),
                            'name': (cfg.get('metadata') or {}).get('name') or cfg.get('name', ''),
                            'status': cfg.get('status', 'inactive'),
                            'type': cfg.get('configuration_type', 'other'),
                            'channels': channels})
        return configs

    def _light_caps(self, light_id: str) -> dict:
        if light_id not in self._caps:
            data = self._call('GET', f'/light/{light_id}').get('data') or []
            if not data:
                raise HueError('the bridge has no such light')
            self._caps[light_id] = _caps(data[0])
        return self._caps[light_id]

    def set_light(self, light_id: str, *, on: bool | None = None, rgb=None,
                  brightness: float | None = None, kelvin: int | None = None,
                  effect: str | None = None, duration_ms: int | None = None) -> dict:
        """One PUT to the light. Colour and brightness do not switch a lamp on by themselves
        (pass on=True); black and brightness 0 switch it off. Returns the bridge's answer
        (a 207 answer carries the bridge's warnings in 'errors')."""
        if not isinstance(light_id, str) or not UUID.fullmatch(light_id):
            raise HueError('that is not a Hue light id')
        if rgb is not None and kelvin is not None:
            raise HueError('a colour or a white temperature, not both')
        body: dict = {}
        if on is not None:
            body['on'] = {'on': bool(on)}
        caps = self._light_caps(light_id) if (rgb is not None or kelvin is not None
                                              or effect not in (None, 'none', 'off')) else None
        if rgb is not None:
            try:
                r, g, b = (float(c) for c in rgb)
            except (TypeError, ValueError):
                raise HueError('a colour is three numbers 0–255') from None
            if max(r, g, b) <= 0:
                body['on'] = {'on': False}
            else:
                if not caps['color']:
                    raise HueError('this lamp has no colour, only white')
                x, y = rgb_to_xy(r, g, b, caps['gamut'])
                body['color'] = {'xy': {'x': round(x, 4), 'y': round(y, 4)}}
        if kelvin is not None:
            if not caps['mirek_range']:
                raise HueError('this lamp has no adjustable white')
            body['color_temperature'] = {'mirek': kelvin_to_mirek(kelvin, caps['mirek_range'])}
        if brightness is not None:
            level = float(brightness)
            if math.isnan(level):
                raise HueError('brightness is a number 0–100')
            if level <= 0:
                body['on'] = {'on': False}
            else:
                body['dimming'] = {'brightness': round(min(100.0, level), 2)}
        if effect is not None:
            name = str(effect).strip().lower()
            name = 'no_effect' if name in ('', 'none', 'off', 'no_effect') else name
            if name != 'no_effect' and name not in caps['effects']:
                raise HueError(f'this lamp has no effect called {effect!r}')
            body['effects'] = {'effect': name}
        if duration_ms is not None:
            body['dynamics'] = {'duration': max(0, int(duration_ms))}
        if not body:
            raise HueError('nothing to change')
        return self._call('PUT', f'/light/{light_id}', body)

    def start_stream(self, config_id: str) -> HueStream:
        if not self._client_key:
            raise HueError('streaming needs Lumen\'s own pairing with the bridge (press its button)')
        if not isinstance(config_id, str) or not UUID.fullmatch(config_id):
            raise HueError('that is not an entertainment area id')
        try:
            psk = bytes.fromhex(self._client_key)
        except ValueError:
            raise HueError('the stored client key is damaged; pair again') from None
        data = self._call('GET', f'/entertainment_configuration/{config_id}').get('data') or []
        if not data:
            raise HueError('the bridge has no such entertainment area')
        channels = sorted(int(ch.get('channel_id', 0)) for ch in data[0].get('channels', []))
        self._call('PUT', f'/entertainment_configuration/{config_id}', {'action': 'start'})
        client = DtlsPskClient(self.host, STREAM_PORT, self._app_key, psk, timeout=self.timeout)
        try:
            client.connect()
        except DtlsError as exc:
            try:
                self._call('PUT', f'/entertainment_configuration/{config_id}', {'action': 'stop'})
            except HueError:
                pass
            raise HueError(f'the bridge did not accept the light stream: {exc}') from None
        return HueStream(self, config_id, channels, client)


# ── pairing ───────────────────────────────────────────────────────────

def _config(host: str, timeout: float) -> dict:
    """The bridge's public description (/api/0/config needs no key): name, bridgeid, model."""
    link = _Link(host, timeout)
    try:
        status, payload = link.exchange('GET', '/api/0/config')
        doc = _decode(status, payload, host)
    finally:
        link.close()
    return doc if isinstance(doc, dict) else {}


def pair(host: str, devicetype: str = 'moos#lumen', timeout: float = 30.0, poll: float = 1.0,
         cancel: threading.Event | None = None) -> dict:
    """Ask the bridge for a new key pair until someone presses its link button.

    Returns {'app_key', 'client_key', 'bridge_id', 'host', 'cert_sha256'}. Raises
    LinkButtonNotPressed when `timeout` passes or `cancel` is set first, BridgeUnreachable when
    the bridge never answered, HueError when it refused for another reason."""
    if not re.fullmatch(r'[\w.-]{1,20}#[\w .-]{1,19}', devicetype):
        raise HueError('devicetype is "application#instance" (20 + 19 characters at most)')
    deadline = time.monotonic() + timeout
    link = _Link(host, 6.0)
    body = {'devicetype': devicetype, 'generateclientkey': True}
    unreachable: BridgeUnreachable | None = None
    answered = False
    try:
        while True:
            if cancel is not None and cancel.is_set():
                raise LinkButtonNotPressed('pairing was cancelled', cancelled=True)
            link.timeout = max(1.0, min(6.0, deadline - time.monotonic()))
            try:
                status, payload = link.exchange('POST', '/api', body, retry=False)
            except BridgeUnreachable as exc:
                unreachable = exc
            else:
                answered = True
                try:
                    doc = _decode(status, payload, host)
                except HueError as exc:
                    if exc.error_type != 101:
                        raise
                    doc = []
                success = next((e['success'] for e in doc if isinstance(e, dict)
                                and isinstance(e.get('success'), dict)), None) \
                    if isinstance(doc, list) else None
                if success:
                    break
            if time.monotonic() + poll > deadline:
                if not answered and unreachable is not None:
                    raise unreachable
                raise LinkButtonNotPressed(f'nobody pressed the link button on the bridge at '
                                           f'{host} within {timeout:g} s')
            if cancel is not None:
                cancel.wait(poll)
            else:
                time.sleep(poll)
    finally:
        link.close()
    app_key, client_key = success.get('username'), success.get('clientkey')
    if not app_key:
        raise HueError('the bridge accepted the pairing but sent no key')
    if not client_key:
        raise HueError('the bridge sent no client key: its firmware predates the Entertainment API')
    bridge = HueBridge(host, app_key, client_key, timeout=6.0, cert_sha256=link.seen)
    try:
        bridge_id = bridge.bridge_id()
    except HueError:
        try:
            bridge_id = str(_config(host, 6.0).get('bridgeid') or '').lower()
        except HueError:
            bridge_id = ''
    finally:
        bridge.close()
    return {'app_key': app_key, 'client_key': client_key, 'bridge_id': bridge_id, 'host': host,
            'cert_sha256': link.seen}


# ── discovery ─────────────────────────────────────────────────────────

def _from_mdns(name: str, addresses, properties) -> dict | None:
    """A `_hue._tcp` service record → {'host', 'bridge_id', 'name'}."""
    props = {(k.decode() if isinstance(k, bytes) else str(k)).lower():
             (v.decode('utf-8', 'replace') if isinstance(v, bytes) else (v or ''))
             for k, v in (properties or {}).items()}
    # IPv4 only: a bridge always has one, and a link-local IPv6 address needs a scope to be used
    v4 = [a for a in addresses or [] if re.fullmatch(r'\d{1,3}(\.\d{1,3}){3}', a)]
    if not v4:
        return None
    host = v4[0]
    instance = name[:-len(MDNS_TYPE)].rstrip('.') if name.endswith(MDNS_TYPE) else name
    bridge_id = props.get('bridgeid', '').lower()
    return {'host': host, 'bridge_id': bridge_id if BRIDGE_ID.fullmatch(bridge_id) else '',
            'name': instance or 'Hue Bridge'}


def _parse_ssdp(data: bytes, sender: str) -> dict | None:
    """An SSDP answer → {'host', 'bridge_id', 'name'} when it comes from a Hue bridge.

    The host is the address that answered, never the one written in LOCATION."""
    lines = data.decode('latin-1', 'replace').split('\r\n')
    if not lines or not lines[0].startswith('HTTP/1.1 200'):
        return None
    headers = {}
    for line in lines[1:]:
        key, sep, value = line.partition(':')
        if sep:
            headers[key.strip().lower()] = value.strip()
    bridge_id = headers.get('hue-bridgeid', '').lower()
    if not bridge_id and 'IpBridge' not in headers.get('server', ''):
        return None
    return {'host': sender, 'bridge_id': bridge_id if BRIDGE_ID.fullmatch(bridge_id) else '',
            'name': ''}


def _unescape_avahi(text: str) -> str:
    """avahi-browse escapes a name byte-wise: \\032 is a space, \\. a dot."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == '\\' and text[i + 1:i + 4].isdigit() and len(text[i + 1:i + 4]) == 3:
            out.append(int(text[i + 1:i + 4]) & 0xFF)
            i += 4
        elif text[i] == '\\' and i + 1 < len(text):
            out += text[i + 1].encode('utf-8')
            i += 2
        else:
            out += text[i].encode('utf-8')
            i += 1
    return out.decode('utf-8', 'replace')


def _parse_avahi(output: str) -> list[dict]:
    """`avahi-browse -rpt` lines ("=;iface;IPv4;name;type;domain;host;address;port;txt") → bridges."""
    found = []
    for line in output.splitlines():
        fields = line.split(';', 9)
        if len(fields) < 9 or fields[0] != '=' or fields[2] != 'IPv4' or fields[4] != '_hue._tcp':
            continue
        txt = {}
        for entry in re.findall(r'"((?:[^"\\]|\\.)*)"', fields[9] if len(fields) > 9 else ''):
            key, _, value = entry.partition('=')
            txt[key.encode()] = value.encode()
        item = _from_mdns(_unescape_avahi(fields[3]) + '.' + MDNS_TYPE, [fields[7]], txt)
        if item:
            found.append(item)
    return found


def _avahi(timeout: float) -> list[dict]:
    """Ask the system's mDNS daemon, which answers from its cache within about a second."""
    try:
        done = subprocess.run(['avahi-browse', '--resolve', '--parsable', '--terminate',
                               '--no-db-lookup', '_hue._tcp'], capture_output=True, text=True,
                              timeout=timeout, check=False)
        output = done.stdout
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout.decode('utf-8', 'replace') if isinstance(exc.stdout, bytes) \
            else (exc.stdout or '')
    except OSError:                         # no Avahi tools on this system
        return []
    return _parse_avahi(output)


def _mdns(timeout: float) -> list[dict]:
    try:
        from zeroconf import IPVersion, ServiceBrowser, Zeroconf
    except ImportError:
        return []
    names: set[str] = set()

    class Listener:
        def add_service(self, zc, kind, name):
            names.add(name)

        def update_service(self, zc, kind, name):
            names.add(name)

        def remove_service(self, zc, kind, name):
            pass

    try:
        zc = Zeroconf(ip_version=IPVersion.V4Only)
    except OSError:
        return []
    found = []
    try:
        browser = ServiceBrowser(zc, MDNS_TYPE, listener=Listener())
        time.sleep(timeout)
        browser.cancel()
        for name in sorted(names):
            info = zc.get_service_info(MDNS_TYPE, name, timeout=1500)
            if info is not None:
                item = _from_mdns(name, info.parsed_addresses(), info.properties)
                if item:
                    found.append(item)
    except OSError:
        pass
    finally:
        zc.close()
    return found


def _ssdp(timeout: float) -> list[dict]:
    query = ('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\n'
             'MX: 2\r\nST: ssdp:all\r\n\r\n').encode('ascii')
    found = []
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    except OSError:
        return []
    with sock:
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            for _ in range(2):              # UDP may drop one
                sock.sendto(query, SSDP_ADDR)
        except OSError:
            return []
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            sock.settimeout(left)
            try:
                data, (sender, _) = sock.recvfrom(4096)
            except OSError:
                break
            item = _parse_ssdp(data, sender)
            if item:
                found.append(item)
    return found


def _cloud(timeout: float) -> list[dict]:
    """Signify's discovery service: it sees the home's public address, so only on request."""
    conn = http.client.HTTPSConnection(CLOUD_DISCOVERY, timeout=timeout,
                                       context=ssl.create_default_context())
    try:
        conn.request('GET', '/')
        response = conn.getresponse()
        doc = json.loads(response.read()) if response.status == 200 else []
    except (OSError, http.client.HTTPException, ValueError):
        return []
    finally:
        conn.close()
    return [{'host': str(e.get('internalipaddress')), 'bridge_id': str(e.get('id', '')).lower(),
             'name': ''} for e in doc if isinstance(e, dict) and e.get('internalipaddress')]


def discover(timeout: float = 3.0, *, cloud: bool = False) -> list[dict]:
    """Bridges on the LAN: [{'host', 'bridge_id', 'name'}], one per bridge.

    Avahi, zeroconf and SSDP run side by side for `timeout` seconds (any of them may be missing
    or blocked); a bridge found without a name or id is asked for its public description."""
    results: dict[str, list[dict]] = {}

    def run(key, fn):
        try:
            results[key] = fn(timeout)
        except Exception:                   # discovery is best effort; one method may fail
            results[key] = []
    workers = [threading.Thread(target=run, args=(k, f), daemon=True)
               for k, f in (('avahi', _avahi), ('mdns', _mdns), ('ssdp', _ssdp))]
    for w in workers:
        w.start()
    for w in workers:
        w.join(timeout + 5)
    candidates = results.get('avahi', []) + results.get('mdns', []) + results.get('ssdp', [])
    if cloud and not candidates:
        candidates = _cloud(timeout)
    bridges: dict[str, dict] = {}
    for item in candidates:
        key = item['bridge_id'] or item['host']
        known = bridges.get(key) or next((b for b in bridges.values()
                                           if b['host'] == item['host']), None)
        if known is None:
            bridges[key] = dict(item)
        else:
            for field in ('bridge_id', 'name'):
                known[field] = known[field] or item[field]
    for bridge in bridges.values():
        if not bridge['name'] or not bridge['bridge_id']:
            try:
                about = _config(bridge['host'], min(3.0, timeout))
            except HueError:
                about = {}
            bridge['name'] = bridge['name'] or str(about.get('name') or 'Hue Bridge')
            bridge['bridge_id'] = bridge['bridge_id'] or str(about.get('bridgeid') or '').lower()
    return list(bridges.values())
