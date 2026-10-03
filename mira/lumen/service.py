"""Lumen's door: one JSON request per line on a private Unix socket.

Mira's window, her voice and text brains, System Settings and the `mira-lumen` command all reach the
one engine through `$XDG_RUNTIME_DIR/mira-lumen.sock`. The runtime directory is the user's own
(0700) and the socket is 0600, so nothing but the owner's session can turn his lights. There is
no network listener: a web page cannot reach it.

Every operation is a fixed name with typed arguments; nothing here runs a command.
"""
from __future__ import annotations

import json
import os
import signal
import socketserver
import sys
import threading
from pathlib import Path

from lumen.engine import Engine

MAX_REQUEST = 64 * 1024


def socket_path() -> Path:
    runtime = os.environ.get('XDG_RUNTIME_DIR') or '/run/user/%d' % os.getuid()
    return Path(runtime) / 'mira-lumen.sock'


def _num(value, lo=None, hi=None):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError('expected a number') from None
    if lo is not None and value < lo or hi is not None and value > hi:
        raise ValueError('number out of range')
    return value


def _rgb(value):
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('rgb is [r, g, b]')
    return [int(_num(c, 0, 255)) for c in value]


def dispatch(engine: Engine, request: dict) -> dict:
    op = request.get('op')
    a = request
    if op == 'ping':
        return {'status': 'ok', 'pong': True}
    if op == 'snapshot':
        if a.get('lang') in ('ar', 'en'):
            engine.lang = engine.pc.lang = a['lang']
        if a.get('force'):
            engine.refresh(force=True)
        return engine.snapshot()
    if op == 'set':
        on = a.get('on')
        if on is not None and not isinstance(on, bool):
            raise ValueError('on is true or false')
        return engine.set(a.get('target'), on=on, color=a.get('color') or None, rgb=_rgb(a.get('rgb')),
                          brightness=_num(a.get('brightness'), 0, 100), kelvin=_num(a.get('kelvin'), 1000, 10000),
                          effect=a.get('effect') or None, transition=_num(a.get('transition'), 0, 60))
    if op == 'scene':
        b = _num(a.get('brightness'), 1, 100)
        return engine.scene(str(a.get('name') or ''), a.get('target'), int(b) if b else None)
    if op == 'stop_living':
        return engine.stop_living(a.get('target'))
    if op == 'sync_start':
        mode = a.get('mode') or 'video'
        if mode not in ('video', 'game', 'ambient'):
            raise ValueError('mode is video, game or ambient')
        select_screen = a.get('select_screen', False)
        if not isinstance(select_screen, bool):
            raise ValueError('select_screen is true or false')
        return engine.sync_start(mode, a.get('target'), _num(a.get('brightness'), 0.1, 1.0),
                                 select_screen=select_screen)
    if op == 'sync_stop':
        return engine.sync_stop()
    if op == 'sync_status':
        return {'status': 'ok', 'sync': engine.sync_status()}
    if op == 'rename':
        return engine.rename(str(a.get('id') or ''), str(a.get('name') or ''))
    if op == 'set_room':
        return engine.set_room(str(a.get('id') or ''), a.get('room') or None)
    if op == 'save_group':
        ids = a.get('ids') or []
        if not isinstance(ids, list):
            raise ValueError('ids is a list')
        return engine.save_group(str(a.get('name') or ''), [str(i) for i in ids])
    if op == 'identify':
        return engine.identify(str(a.get('id') or ''))
    if op == 'pc_configure':
        leds = _num(a.get('leds'), 1, 1024)
        return engine.pc.configure(str(a.get('zone') or ''), name=a.get('name'),
                                   leds=int(leds) if leds else None, hidden=a.get('hidden'))
    if op == 'pc_restore':
        return {'status': 'ok', 'restored': engine.pc.restore()}
    if op == 'hue_discover':
        return engine.hue_discover()
    if op == 'hue_pair':
        return engine.hue_pair(a.get('host') or None)
    if op == 'hue_status':
        return {'status': 'ok', 'hue': engine.hue_status()}
    if op == 'hue_forget':
        return engine.hue_forget()
    raise ValueError('unknown operation')


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(MAX_REQUEST + 1)
        if not line:
            return
        try:
            if len(line) > MAX_REQUEST:
                raise ValueError('request too large')
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError('request is an object')
            reply = dispatch(self.server.engine, request)
        except (ValueError, KeyError, TypeError) as exc:
            reply = {'status': 'error', 'error': str(exc)}
        except Exception as exc:      # the engine's own failure, said plainly
            reply = {'status': 'error', 'error': '%s: %s' % (type(exc).__name__, exc)}
        self.wfile.write((json.dumps(reply, ensure_ascii=False, default=str) + '\n').encode('utf-8'))


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


def serve(engine: Engine | None = None, path: Path | None = None) -> int:
    path = path or socket_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    engine = engine or Engine()
    old = os.umask(0o177)
    try:
        server = Server(str(path), Handler)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
    server.engine = engine
    threading.Thread(target=engine.start, daemon=True, name='lumen-start').start()

    def stop(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    print('Lumen: listening on', path, flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        engine.close()
        server.server_close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(serve())
