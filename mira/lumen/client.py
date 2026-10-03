"""How Mira (and anything else in the session) asks Lumen for something.

`call('set', target='المكتب', color='بنفسجي')` → the engine's own result dict. When Lumen is not
running, `ensure()` starts the user service the image ships (mira-lumen.service); a source checkout
without that unit starts `python3 -m lumen serve` from the same tree, so a review build never
needs the image to light anything up.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

UNIT = 'mira-lumen.service'
APP_DIR = Path(__file__).resolve().parent.parent


def socket_path() -> Path:
    runtime = os.environ.get('XDG_RUNTIME_DIR') or '/run/user/%d' % os.getuid()
    return Path(runtime) / 'mira-lumen.sock'


class LumenError(RuntimeError):
    pass


def call(op: str, timeout: float = 15.0, **args) -> dict:
    request = dict(args, op=op)
    data = (json.dumps(request, ensure_ascii=False) + '\n').encode('utf-8')
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(socket_path()))
            sock.sendall(data)
            chunks = []
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if chunk.endswith(b'\n'):
                    break
    except (FileNotFoundError, ConnectionRefusedError):
        raise LumenError('lumen-not-running') from None
    except socket.timeout:
        raise LumenError('lumen-timeout') from None
    except OSError as exc:
        raise LumenError(str(exc)) from None
    try:
        return json.loads(b''.join(chunks))
    except ValueError:
        raise LumenError('lumen-bad-reply') from None


def available() -> bool:
    try:
        return call('ping', timeout=1.5).get('pong') is True
    except LumenError:
        return False


def available_soon(wait: float = 4.0) -> bool:
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if available():
            return True
        time.sleep(0.2)
    return False


def ensure(wait: float = 8.0) -> bool:
    """Lumen answering, starting it when needed. Never raises."""
    if available():
        return True
    if os.environ.get('MIRA_TEST_MODE') == '1':
        return False
    started = False
    # the unit starts at sign-in only for someone who has used Lumen (ConditionPathExists on this
    # file); asking for a light is using it
    try:
        from lumen.store import Store
        store = Store()
        if not store.path.exists():
            store.set('created', int(time.time()))
    except OSError:
        pass
    try:
        result = subprocess.run(['systemctl', '--user', 'start', UNIT], capture_output=True, timeout=10)
        started = result.returncode == 0 and available_soon()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if not started and os.environ.get('MIRA_LUMEN_SPAWN', '1') != '0':
        try:
            subprocess.Popen([sys.executable, '-s', '-m', 'lumen', 'serve'], cwd=str(APP_DIR),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            return False
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        if available():
            return True
        time.sleep(0.25)
    return False


def request(op: str, timeout: float = 15.0, **args) -> dict:
    """call() that starts Lumen first and turns every failure into a result dict."""
    if not ensure():
        return {'status': 'error', 'error': 'lumen-not-running'}
    try:
        return call(op, timeout=timeout, **args)
    except LumenError as exc:
        return {'status': 'error', 'error': str(exc)}
