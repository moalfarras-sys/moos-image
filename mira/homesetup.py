"""The home hub on this computer: Home Assistant set up from Mira, for a MoOS that has none.

A fresh MoOS has no Home Assistant, and without one Mira can reach only the lights Lumen finds by
itself (the PC's controller, a Hue bridge). This module gives the Home page one button that makes
the computer the home's hub, as the owner's own container — no root, no system change:

    1. write ~/.config/containers/systemd/mira-homeassistant.container (a Podman quadlet: the
       container becomes the user service mira-homeassistant.service, started at sign-in)
    2. start it (the first start downloads the pinned image, ~2.5 GB)
    3. wait until it answers on 127.0.0.1:8123
    4. finish Home Assistant's first-run setup with the owner's own name, user name and password
       (they go to Home Assistant only; Mira keeps none of them), then ask it for a long-lived
       token and save that the way a pasted token is saved (homehub.save, 0600)

Home Assistant then discovers the house by itself (zeroconf, SSDP, DHCP): Hue bridges, Chromecasts,
TVs, ESPHome devices … appear on the Home page as "found on your network", one button away.

A quadlet that is already there is never overwritten: a hub the owner set up himself stays his.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import homehub

UNIT = 'mira-homeassistant.service'
QUADLET = Path.home() / '.config' / 'containers' / 'systemd' / 'mira-homeassistant.container'
DATA = Path.home() / '.local' / 'share' / 'mira-homeassistant' / 'config'
URL = 'http://127.0.0.1:8123'
# The image the owner's station has run since 2026-09: pinned by digest, so a moved tag can never
# put different code on the owner's network.
IMAGE = ('ghcr.io/home-assistant/home-assistant:2026.9.4'
         '@sha256:e47c978e1b801466e7f62f612fd552bc3a228e077b31a3f1c22c05cf63d754da')
CLIENT_ID = URL + '/'                       # Home Assistant's own frontend client id
REDIRECT = URL + '/?auth_callback=1'

QUADLET_TEXT = """[Unit]
Description=Mira's home hub (Home Assistant)
Documentation=file:///usr/lib/mira/app/homesetup.py
After=network-online.target
Wants=network-online.target

[Container]
Image={image}
ContainerName=mira-homeassistant
# host network: discovery (mDNS, SSDP, DHCP) and the Hue/Cast/ESPHome devices need the LAN as-is
Network=host
Volume={data}:/config:Z
Environment=TZ={tz}

[Service]
Restart=on-failure
# the first start downloads the image
TimeoutStartSec=900
TimeoutStopSec=120

[Install]
WantedBy=default.target
"""


class SetupError(RuntimeError):
    pass


def _zone() -> str:
    try:
        target = os.path.realpath('/etc/localtime')
        if 'zoneinfo/' in target:
            return target.split('zoneinfo/', 1)[1]
    except OSError:
        pass
    return 'UTC'


def status(url: str = URL) -> dict:
    """Where the hub is: none | installed | starting | ready (needs first-run setup) | linked."""
    probe = homehub.probe(url, timeout=1.5)
    linked = homehub.load() is not None
    unit = _unit_state()
    if linked and probe.get('reachable'):
        stage = 'linked'
    elif probe.get('reachable'):
        stage = 'onboarding' if probe.get('needs_onboarding') else 'token'
    elif QUADLET.exists():
        stage = 'starting' if unit in ('activating', 'active') else 'installed'
    else:
        stage = 'none'
    return {'stage': stage, 'unit': unit, 'quadlet': QUADLET.exists(), 'version': probe.get('version'),
            'url': url}


def _systemctl(*args, timeout=30) -> subprocess.CompletedProcess:
    return subprocess.run(['systemctl', '--user', *args], capture_output=True, text=True, timeout=timeout)


def _unit_state() -> str:
    try:
        return _systemctl('is-active', UNIT, timeout=5).stdout.strip() or 'unknown'
    except (OSError, subprocess.TimeoutExpired):
        return 'unknown'


def install(*, image: str = IMAGE) -> dict:
    """Write the quadlet (never over another one) and start the hub. Returns at once while the
    image downloads; status() follows it."""
    text = QUADLET_TEXT.format(image=image, data=DATA, tz=_zone())
    if QUADLET.exists() and QUADLET.read_text(encoding='utf-8') != text:
        # the owner's own hub, or an older one of Mira's: start it, never rewrite it
        written = False
    else:
        QUADLET.parent.mkdir(parents=True, exist_ok=True)
        tmp = QUADLET.with_suffix('.tmp')
        tmp.write_text(text, encoding='utf-8')
        os.replace(tmp, QUADLET)
        written = True
    DATA.mkdir(parents=True, exist_ok=True)
    reload = _systemctl('daemon-reload')
    if reload.returncode != 0:
        raise SetupError('systemd: ' + (reload.stderr.strip() or 'daemon-reload failed'))
    # --no-block: the first start downloads ~2.5 GB; the page follows it through status()
    start = _systemctl('start', '--no-block', UNIT)
    if start.returncode != 0:
        raise SetupError('systemd: ' + (start.stderr.strip() or 'start failed'))
    return {'status': 'pending', 'written': written, 'unit': UNIT}


def wait_ready(url: str = URL, timeout: float = 900.0, poll: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = homehub.probe(url, timeout=1.5)
        if probe.get('reachable'):
            return probe
        time.sleep(poll)
    raise SetupError('Home Assistant did not answer in time')


# ── first-run setup ──────────────────────────────────────────────────
def _post(url: str, body, *, token: str | None = None, form: bool = False, timeout: float = 30.0):
    data = urllib.parse.urlencode(body).encode() if form else json.dumps(body).encode()
    headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode('utf-8', 'replace')
        raise SetupError(f'Home Assistant answered {exc.code}: {detail}') from None
    except urllib.error.URLError as exc:
        raise SetupError(f'Home Assistant is not reachable: {exc.reason}') from None
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        raise SetupError('Home Assistant answered something that is not JSON') from None


def onboard(name: str, username: str, password: str, *, language: str = 'ar', url: str = URL,
            config_path: Path | None = None) -> dict:
    """Create the owner's account in a Home Assistant that still needs its first-run setup, finish
    the setup, and link Mira with a long-lived token. Nothing of the password is kept."""
    name, username = ' '.join(str(name or '').split())[:60], str(username or '').strip().lower()[:40]
    if not name or not username or len(str(password or '')) < 8:
        raise SetupError('a name, a user name and a password of at least 8 characters')
    base = url.rstrip('/')
    created = _post(base + '/api/onboarding/users', {'client_id': CLIENT_ID, 'name': name, 'username': username,
                                                      'password': password, 'language': language})
    code = created.get('auth_code')
    if not code:
        raise SetupError('Home Assistant created no account (is it already set up?)')
    tokens = _post(base + '/auth/token', {'grant_type': 'authorization_code', 'code': code,
                                          'client_id': CLIENT_ID}, form=True)
    access = tokens.get('access_token')
    if not access:
        raise SetupError('Home Assistant gave no sign-in token')
    # the remaining first-run steps, with Home Assistant's own detected defaults
    for step, body in (('core_config', {}), ('analytics', {}),
                       ('integration', {'client_id': CLIENT_ID, 'redirect_uri': REDIRECT})):
        try:
            _post(base + '/api/onboarding/' + step, body, token=access)
        except SetupError as exc:
            if '403' not in str(exc):        # 403: that step is already done
                raise
    with homehub.Session(base, access, 15.0) as session:
        long_lived = session.command({'type': 'auth/long_lived_access_token', 'client_name': 'Mira',
                                      'lifespan': 3650})
    if not isinstance(long_lived, str) or len(long_lived) < 40:
        raise SetupError('Home Assistant gave no long-lived token')
    path = config_path or homehub.CONFIG
    homehub.save(long_lived, None if base == URL else base, path=path)
    hub = homehub.load(path)
    if hub is None:
        raise SetupError('the token was not saved')
    hub.states()                                # read back: the saved token really works
    return {'status': 'ok', 'url': base, 'user': username}
