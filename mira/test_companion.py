"""Mira Companion: the phone's door is locked, and every request reaches Mira the desktop way.

The server runs for real on 127.0.0.1 (never another address) against a stand-in controller and,
once, against the real `controller.Controller` in test mode. Nothing here reaches the Echo, Home
Assistant, Gemini or Mo AI.
"""
import gc
import http.client
import json
import os
import queue
import re
import socket
import stat
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ['MIRA_TEST_MODE'] = '1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
os.environ.pop('MIRA_COMPANION_HOST', None)
_config = tempfile.TemporaryDirectory(prefix='mira-companion-test-')
os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import (QCoreApplication, QEvent, QObject, Property, QSettings, QUrl, Signal, Slot,  # noqa: E402
                            qInstallMessageHandler)
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from companion import CompanionServer, CompanionService, ControllerAdapter, Tailnet, TokenStore  # noqa: E402
from companion import server as srv  # noqa: E402
from companion.adapter import PANEL_TEXT, qr_code, webp_supported  # noqa: E402
from models import DictListModel  # noqa: E402

ROOT = Path(__file__).resolve().parent
PANEL = ROOT / 'qml' / 'Mira' / 'CompanionPanel.qml'
APP = QGuiApplication.instance() or QGuiApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _config.name)

DEVICE_ROLES = ['entity_id', 'name', 'domain', 'state', 'available', 'is_on', 'brightness', 'color_capable',
                'dimmable', 'rgb', 'volume', 'volume_capable', 'play_capable', 'pause_capable', 'on_capable',
                'off_capable', 'group']


def device(entity_id, **fields):
    row = {'entity_id': entity_id, 'name': entity_id, 'domain': entity_id.split('.')[0], 'state': 'off',
           'available': True, 'is_on': False, 'brightness': -1, 'color_capable': False, 'dimmable': False, 'rgb': '',
           'volume': -1, 'volume_capable': False, 'play_capable': False, 'pause_capable': False, 'on_capable': True,
           'off_capable': True, 'group': False}
    row.update(fields)
    return row


DEVICES = [
    device('light.buro', name='Büro', state='on', is_on=True, brightness=70, color_capable=True, dimmable=True, rgb='#ff5aaf'),
    device('light.desk', name='Desk'),                                     # on/off only
    device('light.hall', name='Hall', state='unavailable', available=False),
    device('media_player.tv', name='TV', state='on', is_on=True, volume=20, volume_capable=True, play_capable=True,
           pause_capable=True),
    device('switch.plug', name='Plug'),
]


def setUpModule():
    # Python's cyclic GC runs on whichever thread happens to allocate. These tests run server and
    # reader threads, and QObjects from this and earlier suites (controllers, adapters owning QTimers)
    # sit in reference cycles; collected on one of those threads they would be destroyed off Qt's
    # thread and crash its timer dispatch later (measured: adapters finalized on `mira-companion`, then
    # SIGSEGV in QTimerInfoList::activateTimers). So garbage is collected only here and after each
    # test, on the Qt thread.
    gc.collect()
    gc.disable()


def tearDownModule():
    gc.collect()
    gc.enable()


def dispose(*objects):
    """Delete Qt object trees now, parents first, on the Qt thread. Left to Python's cyclic GC, a
    Python-owned parent and its children's wrappers are torn down in arbitrary order (measured: a
    SIGSEGV inside gc.collect with a FakeController → CompanionService → adapter → QTimer tree)."""
    for obj in objects:
        try:
            obj.deleteLater()
        except RuntimeError:      # already deleted
            pass
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


class QtCase(unittest.TestCase):
    def tearDown(self):
        gc.collect()


def pump(predicate=lambda: False, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def _prop(kind, attr, signal):
    return Property(kind, lambda self: getattr(self, attr), notify=signal)


class FakeController(QObject):
    """The controller's QML-facing surface, recording every slot call and the thread it ran on."""
    phaseChanged = Signal(); levelChanged = Signal(); statusChanged = Signal(); captionChanged = Signal()  # noqa: E702
    moodChanged = Signal(); faceChanged = Signal(); langChanged = Signal(); servicesChanged = Signal()  # noqa: E702
    weatherChanged = Signal(); homeChanged = Signal(); echoChanged = Signal(); busyChanged = Signal()  # noqa: E702
    toast = Signal(str, str)

    def __init__(self, lang='ar'):
        super().__init__()
        self._phase, self._level, self._status = 'idle', 0.0, 'جاهزة'
        self._caption, self._caption_role, self._mood, self._face, self._lang = '', '', 'neutral', 'rose', lang
        self._s = {'talk': 'تحدّث', 'stop': 'إيقاف', 'phase_idle': 'جاهزة', 'tray_quit': 'not for the phone'}
        self._services = {'echo': 'online', 'home': 'online', 'moai': 'online', 'brain': 'online'}
        self._weather = {'ok': True, 'city': 'Berlin', 'temp': 14, 'condition': 'غائم'}
        self._home = {'available': 4, 'total': 5, 'lights_on': 1, 'lights_available': 2, 'tv': None, 'message': '',
                      'busy': False, 'linked': True}
        self._echo = {'online': True, 'voice_enabled': True, 'setup_url': 'http://192.168.3.83:8181/setup',
                      'wake_hint': 'private', 'speaker_volume': 40}
        self._busy = False
        self.chat = DictListModel(['role', 'text', 'time', 'status', 'title', 'tool'])
        self.devices = DictListModel(DEVICE_ROLES, key='entity_id')
        self.devices.set_rows(DEVICES)
        self.calls = []

    phase = _prop(str, '_phase', phaseChanged)
    level = _prop(float, '_level', levelChanged)
    status = _prop(str, '_status', statusChanged)
    caption = _prop(str, '_caption', captionChanged)
    captionRole = _prop(str, '_caption_role', captionChanged)
    mood = _prop(str, '_mood', moodChanged)
    faceStyle = _prop(str, '_face', faceChanged)
    lang = _prop(str, '_lang', langChanged)
    s = _prop('QVariantMap', '_s', langChanged)
    services = _prop('QVariantMap', '_services', servicesChanged)
    weather = _prop('QVariantMap', '_weather', weatherChanged)
    home = _prop('QVariantMap', '_home', homeChanged)
    echo = _prop('QVariantMap', '_echo', echoChanged)
    busy = _prop(bool, '_busy', busyChanged)
    chatModel = Property(QObject, lambda self: self.chat, constant=True)
    deviceModel = Property(QObject, lambda self: self.devices, constant=True)

    def _record(self, *call):
        self.calls.append((call, threading.current_thread() is threading.main_thread()))

    @Slot(str)
    def send(self, text):
        self._record('send', text)

    @Slot()
    def talk(self):
        self._record('talk')

    @Slot()
    def stop(self):
        self._record('stop')

    @Slot(str, str, float, str)
    def homeAction(self, entity_id, action, value=-1.0, color=''):
        self._record('homeAction', entity_id, action, value, color)

    @Slot(bool)
    def allLights(self, on):
        self._record('allLights', on)

    @Slot()
    def refreshHome(self):
        self._record('refreshHome')

    def set_phase(self, phase):
        self._phase = phase
        self.phaseChanged.emit()


class Harness:
    """A real server on 127.0.0.1 (ephemeral port) over a ControllerAdapter."""

    def __init__(self, controller=None, **kwargs):
        self.owns_controller = controller is None
        self.controller = controller or FakeController()
        self.closed = False
        self.dir = tempfile.TemporaryDirectory(prefix='mira-companion-')
        self.store = TokenStore(Path(self.dir.name) / 'mo-dot' / 'companion.json')
        self.store.set_enabled(True)
        self.adapter = ControllerAdapter(self.controller)
        self.logs = []
        self.statuses = []
        self.clients = []
        self.paired = []
        kwargs.setdefault('discover', lambda: Tailnet('127.0.0.1', ('localhost',), ''))
        kwargs.setdefault('probe', lambda host: True)
        self.server = CompanionServer(self.adapter, self.store, port=0, log=self.logs.append,
                                      on_status=lambda s, d: self.statuses.append((s, d)),
                                      on_clients=self.clients.append, on_paired=self.paired.append, **kwargs)
        self.adapter.attach(self.server.publish)
        self.server.start()

    def ready(self):
        assert self.server.wait_listening(5), self.statuses
        self.port = self.server.port
        self.host = f'127.0.0.1:{self.port}'
        self.origin = 'http://' + self.host
        return self

    @property
    def token(self):
        return self.store.token

    def bearer(self):
        return {'Authorization': 'Bearer ' + self.token}

    def cookie(self):
        return {'Cookie': 'mira_session=' + self.store.session_cookie()}

    def request(self, method, path, body=None, headers=None, host=None, content_type='application/json'):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        if host is not False:
            conn.putheader('Host', host or self.host)
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            if content_type:
                conn.putheader('Content-Type', content_type)
            conn.putheader('Content-Length', str(len(data)))
        for key, value in (headers or {}).items():
            conn.putheader(key, value)
        conn.endheaders(data)
        response = conn.getresponse()
        payload = response.read()
        result = response.status, {k.lower(): v for k, v in response.getheaders()}, payload
        conn.close()
        return result

    def post(self, path, body=None, headers=None):
        merged = {'Origin': self.origin, **self.cookie(), **(headers or {})}
        return self.request('POST', path, body, merged)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.server.stop()
        self.adapter.close()
        dispose(self.adapter, *([self.controller] if self.owns_controller else []))
        self.dir.cleanup()


class Stream:
    """A raw Server-Sent Events reader on its own thread."""

    def __init__(self, harness, headers):
        self.sock = socket.create_connection(('127.0.0.1', harness.port), timeout=10)
        lines = ['GET /api/events HTTP/1.1', f'Host: {harness.host}', 'Accept: text/event-stream']
        lines += [f'{k}: {v}' for k, v in headers.items()]
        self.sock.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode())
        self.file = self.sock.makefile('rb')
        self.status = int(self.file.readline().split()[1])
        self.headers = {}
        while True:
            line = self.file.readline().decode('latin-1').strip()
            if not line:
                break
            key, _, value = line.partition(':')
            self.headers[key.lower()] = value.strip()
        self.events = queue.Queue()
        self.closed = threading.Event()
        if self.status == 200:
            threading.Thread(target=self._read, daemon=True).start()
        else:
            self.closed.set()

    def _read(self):
        event, data = 'message', []
        try:
            for raw in self.file:
                line = raw.decode('utf-8').rstrip('\r\n')
                if line == '':
                    if data:
                        self.events.put((event, json.loads('\n'.join(data))))
                    event, data = 'message', []
                elif line.startswith(':'):
                    self.events.put(('comment', line[1:].strip()))
                elif line.startswith('event:'):
                    event = line[6:].strip()
                elif line.startswith('data:'):
                    data.append(line[5:].strip())
        except (OSError, ValueError):
            pass
        finally:
            self.closed.set()

    def wait(self, name, predicate=lambda data: True, timeout=4.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            try:
                kind, data = self.events.get(timeout=0.01)
            except queue.Empty:
                continue
            if kind == name and predicate(data):
                return data
        raise AssertionError(f'no {name!r} event arrived')

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


API_ROUTES = [('GET', '/api/state'), ('GET', '/api/home'), ('GET', '/api/events'), ('GET', '/face/rose/neutral.png'),
              ('GET', '/face/holo/happy.webp'), ('POST', '/api/send'), ('POST', '/api/talk'), ('POST', '/api/stop'),
              ('POST', '/api/home/action'), ('POST', '/api/lights'), ('POST', '/api/home/refresh')]


class ServerTest(QtCase):
    def harness(self, **kwargs):
        kwargs.setdefault('posts_per_minute', 1000)
        kwargs.setdefault('auth_failures_per_minute', 1000)
        h = Harness(**kwargs).ready()
        self.addCleanup(h.close)
        return h

    # ── the lock ────────────────────────────────────────────────────
    def test_every_api_and_face_route_needs_the_token(self):
        h = self.harness()
        wrong = 'x' * 43
        for method, path in API_ROUTES:
            body = {} if method == 'POST' else None
            for headers in ({}, {'Authorization': 'Bearer ' + wrong}, {'Cookie': 'mira_session=' + wrong},
                            {'Authorization': 'Basic ' + h.token}, {'Cookie': 'session=' + h.store.session_cookie()}):
                status, _, _ = h.request(method, path, body, {'Origin': h.origin, **headers})
                self.assertEqual(status, 401, (method, path, headers))
        self.assertEqual(h.controller.calls, [])
        for path in ('/api/state', '/api/home', '/face/rose/neutral.png'):
            self.assertEqual(h.request('GET', path, headers=h.bearer())[0], 200, path)
            self.assertEqual(h.request('GET', path, headers=h.cookie())[0], 200, path)

    def test_pairing_sets_a_strict_http_only_cookie_and_redirects(self):
        h = self.harness()
        status, headers, _ = h.request('GET', '/pair?t=' + h.token)
        self.assertEqual(status, 303)
        self.assertEqual(headers['location'], '/')
        cookie = headers['set-cookie']
        self.assertTrue(cookie.startswith('mira_session='), cookie)
        for attribute in ('HttpOnly', 'SameSite=Strict', 'Path=/'):
            self.assertIn(attribute, cookie)
        value = cookie.split(';', 1)[0].split('=', 1)[1]
        self.assertNotIn(h.token, cookie, 'the cookie must not be the pairing token itself')
        self.assertEqual(h.request('GET', '/api/state', headers={'Cookie': 'mira_session=' + value})[0], 200)
        self.assertTrue(pump(lambda: h.paired == ['127.0.0.1']))
        status, headers, _ = h.request('GET', '/pair?t=' + 'A' * 43)
        self.assertEqual((status, headers['location']), (303, '/?pair=invalid'))
        self.assertNotIn('set-cookie', headers)
        self.assertEqual(h.request('GET', '/pair')[1].get('set-cookie'), None)

    def test_a_foreign_host_header_is_refused(self):
        h = self.harness()
        for host in ('evil.example', f'evil.example:{h.port}', f'127.0.0.1:{h.port + 1}', f'100.98.129.115:{h.port}',
                     f'127.0.0.1:{h.port}.evil.example'):
            for path in ('/', '/api/state', '/pair?t=' + h.token):
                status, headers, _ = h.request('GET', path, headers=h.bearer(), host=host)
                self.assertEqual(status, 403, (host, path))
                self.assertNotIn('set-cookie', headers)
        self.assertEqual(h.request('GET', '/api/state', headers=h.bearer(), host=False)[0], 403)
        self.assertEqual(h.request('GET', '/api/state', headers=h.bearer(), host=f'localhost:{h.port}')[0], 200)

    def test_a_cross_site_post_is_refused(self):
        h = self.harness()
        cookie = h.cookie()
        evil = {'Origin': 'http://evil.example'}
        self.assertEqual(h.request('POST', '/api/talk', {}, {**cookie, **evil})[0], 403)
        self.assertEqual(h.request('POST', '/api/talk', {}, cookie)[0], 403, 'a cookie POST without Origin')
        self.assertEqual(h.request('POST', '/api/talk', {}, {**cookie, 'Origin': 'null'})[0], 403)
        self.assertEqual(h.request('POST', '/api/talk', {}, {**cookie, 'Origin': h.origin,
                                                             'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(h.request('POST', '/api/talk', {}, {**h.bearer(), **evil})[0], 403)
        self.assertEqual(h.controller.calls, [])
        self.assertEqual(h.request('POST', '/api/talk', {}, {**cookie, 'Origin': h.origin})[0], 202)
        self.assertEqual(h.request('POST', '/api/talk', {}, h.bearer())[0], 202, 'a non-browser client with the token')

    def test_an_oversize_or_unframed_body_is_refused(self):
        h = self.harness()
        big = json.dumps({'text': 'x' * (16 * 1024)}).encode()
        self.assertGreater(len(big), srv.MAX_BODY)
        self.assertEqual(h.post('/api/send', big)[0], 413)
        status, _, _ = h.request('POST', '/api/send', None, {**h.cookie(), 'Origin': h.origin,
                                                              'Transfer-Encoding': 'chunked'})
        self.assertEqual(status, 411)
        self.assertEqual(h.controller.calls, [])

    def test_bad_home_and_chat_requests_are_refused(self):
        h = self.harness()
        cases = [
            ('/api/home/action', {'entity_id': 'lock.front_door', 'action': 'turn_on'}, 400, 'entity'),
            ('/api/home/action', {'entity_id': 'light.buro; rm -rf', 'action': 'turn_on'}, 400, 'entity'),
            ('/api/home/action', {'entity_id': 'LIGHT.BURO', 'action': 'turn_on'}, 400, 'entity'),
            ('/api/home/action', {'entity_id': ['light.buro'], 'action': 'turn_on'}, 400, 'entity'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'unlock'}, 400, 'action'),
            ('/api/home/action', {'entity_id': 'switch.plug', 'action': 'brightness', 'value': 10}, 400, 'action'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'volume', 'value': 10}, 400, 'action'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'brightness', 'value': 150}, 400, 'value'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'brightness', 'value': -1}, 400, 'value'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'brightness', 'value': True}, 400, 'value'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'brightness', 'value': '50'}, 400, 'value'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'brightness'}, 400, 'value'),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'color', 'color': 'chartreuse'}, 400, 'color'),
            ('/api/home/action', {'entity_id': 'light.garage', 'action': 'turn_on'}, 404, 'unknown_device'),
            ('/api/home/action', {'entity_id': 'light.desk', 'action': 'brightness', 'value': 40}, 409, 'unsupported'),
            ('/api/home/action', {'entity_id': 'light.desk', 'action': 'color', 'color': 'blue'}, 409, 'unsupported'),
            ('/api/home/action', {'entity_id': 'light.hall', 'action': 'turn_on'}, 409, 'unavailable'),
            ('/api/send', {'text': ''}, 400, 'text'),
            ('/api/send', {'text': '   '}, 400, 'text'),
            ('/api/send', {'text': 'x' * 2001}, 400, 'text'),
            ('/api/send', {'text': 42}, 400, 'text'),
            ('/api/send', {'text': 'a\x00b'}, 400, 'text'),
            ('/api/send', ['hello'], 400, 'json'),
            ('/api/send', b'{not json', 400, 'json'),
            ('/api/lights', {'on': 'yes'}, 400, 'on'),
            ('/api/lights', {}, 400, 'on'),
        ]
        for path, body, status, code in cases:
            got, _, payload = h.post(path, body)
            self.assertEqual((got, json.loads(payload).get('error')), (status, code), (path, body))
        got, _, payload = h.request('POST', '/api/send', b'text=hi', {**h.cookie(), 'Origin': h.origin},
                                    content_type='application/x-www-form-urlencoded')
        self.assertEqual((got, json.loads(payload)['error']), (415, 'content_type'))
        self.assertEqual(h.request('GET', '/api/send', headers=h.bearer())[0], 405)
        self.assertEqual(h.post('/api/state', {})[0], 405)
        self.assertEqual(h.request('DELETE', '/api/state', headers=h.bearer())[0], 405)
        self.assertTrue(pump(timeout=0.2) or True)
        self.assertEqual(h.controller.calls, [], 'nothing invalid may reach Mira')

    def test_rotating_the_token_signs_every_phone_out(self):
        h = self.harness()
        old_cookie, old_bearer = h.cookie(), h.bearer()
        stream = Stream(h, old_cookie)
        self.addCleanup(stream.close)
        self.assertEqual(stream.status, 200)
        stream.wait('snapshot')
        new = h.store.rotate()
        h.server.close_streams('rotated')
        self.assertEqual(stream.wait('bye'), {'reason': 'rotated'})
        self.assertTrue(stream.closed.wait(3), 'the stream must end after a rotation')
        self.assertEqual(h.request('GET', '/api/state', headers=old_cookie)[0], 401)
        self.assertEqual(h.request('GET', '/api/state', headers=old_bearer)[0], 401)
        self.assertEqual(h.request('GET', '/api/state', headers={'Authorization': 'Bearer ' + new})[0], 200)
        self.assertEqual(h.request('GET', '/pair?t=' + old_bearer['Authorization'][7:])[1]['location'], '/?pair=invalid')

    # ── the live stream ─────────────────────────────────────────────
    def test_events_deliver_phase_changes_new_chat_rows_and_heartbeats(self):
        h = self.harness(heartbeat=0.25)
        stream = Stream(h, h.bearer())
        self.addCleanup(stream.close)
        self.assertEqual(stream.status, 200)
        self.assertTrue(stream.headers['content-type'].startswith('text/event-stream'))
        snapshot = stream.wait('snapshot')
        self.assertEqual((snapshot['phase'], snapshot['lang'], snapshot['faceStyle']), ('idle', 'ar', 'rose'))
        self.assertTrue(pump(lambda: h.clients[-1:] == [1]))
        h.controller.set_phase('listening')
        self.assertEqual(stream.wait('state', lambda d: 'phase' in d)['phase'], 'listening')
        h.controller.chat.append({'role': 'mira', 'text': 'أهلاً، أنا هنا', 'time': '12:30', 'status': '', 'title': '',
                                  'tool': ''})
        row = stream.wait('chat')
        self.assertEqual((row['role'], row['text'], row['time']), ('mira', 'أهلاً، أنا هنا', '12:30'))
        self.assertGreater(row['seq'], 0)
        h.controller._level = 0.62
        h.controller.levelChanged.emit()
        self.assertAlmostEqual(stream.wait('level')['level'], 0.62, places=2)
        h.controller.toast.emit('pending', 'Echo is offline')
        self.assertEqual(stream.wait('toast'), {'kind': 'pending', 'text': 'Echo is offline'})
        stream.wait('comment', lambda text: text == 'keep-alive', timeout=2)
        stream.close()
        self.assertTrue(pump(lambda: h.clients[-1:] == [0], timeout=4), 'a closed phone must be cleaned up')

    def test_the_snapshot_is_bounded_and_private(self):
        h = self.harness()
        for i in range(40):
            h.controller.chat.append({'role': 'user', 'text': f'm{i}', 'time': '', 'status': '', 'title': '', 'tool': ''})
        pump(timeout=0.1)
        status, headers, payload = h.request('GET', '/api/state', headers=h.bearer())
        snapshot = json.loads(payload)
        self.assertEqual((status, headers['cache-control']), (200, 'no-store'))
        self.assertEqual(len(snapshot['chat']), 30)
        self.assertEqual([r['text'] for r in snapshot['chat']][-1], 'm39')
        self.assertEqual(snapshot['chat'][-1]['seq'] - snapshot['chat'][0]['seq'], 29)
        self.assertEqual(set(snapshot['echo']), {'online', 'voice_enabled'}, 'only what the phone needs of the Echo')
        self.assertNotIn('tray_quit', snapshot['s'])
        self.assertEqual({p['name'] for p in snapshot['palette']}, set(srv.HOME_COLORS))
        home = json.loads(h.request('GET', '/api/home', headers=h.bearer())[2])
        self.assertEqual([d['entity_id'] for d in home['devices']], [d['entity_id'] for d in DEVICES])
        self.assertEqual(home['home']['lights_available'], 2)

    # ── requests reach Mira's own slots, on her thread ──────────────
    def test_send_talk_and_home_actions_reach_the_controller_on_the_qt_thread(self):
        h = self.harness()
        requests = [
            ('/api/send', {'text': '  مرحبا ميرا  '}, ('send', 'مرحبا ميرا')),
            ('/api/talk', None, ('talk',)),
            ('/api/stop', {}, ('stop',)),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'brightness', 'value': 40},
             ('homeAction', 'light.buro', 'brightness', 40.0, '')),
            ('/api/home/action', {'entity_id': 'light.buro', 'action': 'color', 'color': 'purple', 'value': 99},
             ('homeAction', 'light.buro', 'color', -1.0, 'purple')),
            ('/api/home/action', {'entity_id': 'light.desk', 'action': 'turn_off'},
             ('homeAction', 'light.desk', 'turn_off', -1.0, '')),
            ('/api/home/action', {'entity_id': 'media_player.tv', 'action': 'volume', 'value': 25.5},
             ('homeAction', 'media_player.tv', 'volume', 25.5, '')),
            ('/api/home/action', {'entity_id': 'media_player.tv', 'action': 'media_pause'},
             ('homeAction', 'media_player.tv', 'media_pause', -1.0, '')),
            ('/api/lights', {'on': True}, ('allLights', True)),
            ('/api/home/refresh', None, ('refreshHome',)),
        ]
        for path, body, _ in requests:
            status, _, payload = h.post(path, body)
            self.assertEqual((status, json.loads(payload)), (202, {'status': 'accepted'}), path)
        self.assertTrue(pump(lambda: len(h.controller.calls) == len(requests)))
        self.assertEqual([call for call, _ in h.controller.calls], [want for _, _, want in requests])
        self.assertTrue(all(on_qt_thread for _, on_qt_thread in h.controller.calls), 'slots must run on the Qt thread')

    # ── files ───────────────────────────────────────────────────────
    def test_static_files_are_served_and_cannot_be_escaped(self):
        h = self.harness()
        status, headers, body = h.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn("default-src 'none'", headers['content-security-policy'])
        self.assertEqual(headers['x-content-type-options'], 'nosniff')
        self.assertIn(b'/static/app.js', body)
        status, headers, body = h.request('GET', '/static/app.js')
        self.assertEqual((status, headers['content-type']), (200, 'text/javascript; charset=utf-8'))
        self.assertEqual(h.request('GET', '/static/app.js', headers={'If-None-Match': headers['etag']})[0], 304)
        self.assertEqual(h.request('HEAD', '/')[2], b'')
        for path in ('/static/../server.py', '/static/%2e%2e/server.py', '/static/..%2fserver.py', '/static/..%5cserver.py',
                     '/static//etc/passwd', '/static/./app.js', '/static/icons/../app.js', '/static/app.js%00',
                     '/../companion/server.py', '/static/.hidden', '/static/APP.JS', '/static', '/static/',
                     '/companion.json', '/static/../../test_companion.py', '/face/rose/../../server.py'):
            status, _, body = h.request('GET', path, headers=h.bearer())
            self.assertIn(status, (400, 404), path)
            self.assertNotIn(b'import asyncio', body)
        self.assertEqual(h.request('GET', '/static/app.js', body=b'x')[0], 200, 'a body on a GET is read and ignored')
        self.assertEqual(h.request('GET', '/static/app.js', headers={'Content-Length': '1'}, body=b'x')[0], 400,
                         'two Content-Length headers are refused')

    def test_faces_are_images_from_the_face_library(self):
        h = self.harness()
        status, headers, png = h.request('GET', '/face/rose/neutral.png', headers=h.bearer())
        self.assertEqual((status, headers['content-type']), (200, 'image/png'))
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (256, 256))
        big = h.request('GET', '/face/holo/speaking_open.png?s=512', headers=h.bearer())[2]
        self.assertEqual(struct.unpack('>II', big[16:24]), (512, 512))
        if webp_supported():
            status, headers, webp = h.request('GET', '/face/rose/thinking.webp?s=512', headers=h.bearer())
            self.assertEqual((status, headers['content-type'], webp[:4], webp[8:12]), (200, 'image/webp', b'RIFF', b'WEBP'))
        for path in ('/face/rose/smirk.png', '/face/gold/neutral.png', '/face/rose/neutral.gif'):
            self.assertEqual(h.request('GET', path, headers=h.bearer())[0], 404, path)
        self.assertEqual(h.request('GET', '/face/rose/neutral.png?s=1024', headers=h.bearer())[0], 400)

    def test_the_manifest_gives_a_paired_phone_its_start_url_only(self):
        h = self.harness()
        public = json.loads(h.request('GET', '/manifest.webmanifest')[2])
        self.assertEqual((public['start_url'], public['id'], public['display']), ('/', '/', 'standalone'))
        paired = json.loads(h.request('GET', '/manifest.webmanifest', headers=h.cookie())[2])
        self.assertEqual(paired['start_url'], '/pair?t=' + h.token)
        self.assertEqual(paired['id'], '/')
        scripted = json.loads(h.request('GET', '/manifest.webmanifest', headers={**h.cookie(), 'Sec-Fetch-Dest': 'empty'})[2])
        self.assertEqual(scripted['start_url'], '/', 'a page script must not be able to read the pairing link')

    # ── limits ──────────────────────────────────────────────────────
    def test_posts_are_rate_limited_per_client(self):
        h = self.harness(posts_per_minute=20)
        for _ in range(20):
            self.assertEqual(h.post('/api/talk')[0], 202)
        status, headers, _ = h.post('/api/talk')
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(headers['retry-after']), 1)
        self.assertTrue(pump(lambda: len(h.controller.calls) == 20))

    def test_repeated_bad_tokens_lock_the_client_out(self):
        h = self.harness(auth_failures_per_minute=5)
        for _ in range(5):
            self.assertEqual(h.request('GET', '/api/state', headers={'Authorization': 'Bearer nope'})[0], 401)
        self.assertEqual(h.request('GET', '/api/state', headers=h.bearer())[0], 429, 'locked out for the minute')

    def test_the_token_file_is_private_and_logs_hold_no_secret(self):
        h = self.harness()
        mode = stat.S_IMODE(os.stat(h.store.path).st_mode)
        self.assertEqual(mode, 0o600)
        self.assertGreaterEqual(len(h.token), 43)
        self.assertEqual(json.loads(h.store.path.read_text())['token'], h.token)
        h.request('GET', '/pair?t=' + h.token)
        h.request('GET', '/pair?t=' + 'B' * 43)
        secret_message = 'my secret message 7f3a'
        h.post('/api/send', {'text': secret_message})
        h.request('GET', '/api/state', headers={'Authorization': 'Bearer wrong-token-value'})
        pump(lambda: h.controller.calls)
        logs = '\n'.join(h.logs)
        self.assertIn('a phone paired', logs)
        for secret in (h.token, h.store.session_cookie(), secret_message, 'B' * 43, 'wrong-token-value', '/pair?t='):
            self.assertNotIn(secret, logs)
        os.chmod(h.store.path, 0o644)
        TokenStore(h.store.path)
        self.assertEqual(stat.S_IMODE(os.stat(h.store.path).st_mode), 0o600, 'a loosened file is tightened again')

    # ── where it may listen ─────────────────────────────────────────
    def test_it_binds_only_to_the_tailnet_or_loopback(self):
        for address in ('0.0.0.0', '192.168.3.10', '10.0.0.5', '::', '100.128.0.1', '8.8.8.8', ''):
            with self.assertRaises(ValueError, msg=address):
                srv.bindable(address)
        self.assertEqual(srv.bindable('100.98.129.115'), '100.98.129.115')
        self.assertEqual(srv.bindable('127.0.0.1'), '127.0.0.1')
        h = Harness(discover=lambda: Tailnet('192.168.3.10', (), ''))
        self.addCleanup(h.close)
        self.assertTrue(pump(lambda: ('error', 'refused_address') in h.statuses))
        self.assertFalse(h.server.running)
        h2 = Harness(discover=lambda: Tailnet(None, (), 'not_installed'))
        self.addCleanup(h2.close)
        self.assertTrue(pump(lambda: ('waiting', 'not_installed') in h2.statuses))
        self.assertFalse(h2.server.running)

    def test_the_address_is_rechecked_without_dropping_phones(self):
        address = {'ip': '127.0.0.1'}

        def discover():
            return Tailnet(address['ip'], (), '') if address['ip'] else Tailnet(None, (), 'not_connected')
        h = self.harness(recheck=0.15, probe=lambda host: False, discover=discover)
        stream = Stream(h, h.bearer())
        self.addCleanup(stream.close)
        stream.wait('snapshot')
        pump(timeout=0.8)                      # several rechecks where the cheap probe cannot tell
        self.assertFalse(stream.closed.is_set(), 'a confirmed address keeps its phones')
        self.assertEqual(h.request('GET', '/api/state', headers=h.bearer())[0], 200)
        self.assertEqual([s for s, _ in h.statuses].count('running'), 1, 'no rebinding while the address holds')
        address['ip'] = None
        self.assertTrue(pump(lambda: ('waiting', 'not_connected') in h.statuses, timeout=3))
        self.assertFalse(h.server.running)

    def test_tailscale_is_found_at_runtime(self):
        status = {'BackendState': 'Running', 'Self': {'DNSName': 'moos.tailab78a5.ts.net.',
                                                      'TailscaleIPs': ['100.98.129.115', 'fd7a:115c:a1e0::572d:8174']}}
        self.assertEqual(srv.parse_status(status), ('100.98.129.115', ('moos.tailab78a5.ts.net', 'moos')))
        self.assertEqual(srv.parse_status({**status, 'BackendState': 'Stopped'}), (None, ()))
        self.assertEqual(srv.parse_status({'BackendState': 'Running', 'Self': {'TailscaleIPs': ['192.168.1.4']}}), (None, ()))

        class Result:
            def __init__(self, stdout, code=0):
                self.stdout, self.returncode = stdout, code
        with patch.object(srv, '_tailscale_cli', return_value='/usr/bin/tailscale'), \
                patch.object(srv, 'interface_ipv4', return_value=None):
            found = srv.find_tailscale(run=lambda *a, **k: Result(json.dumps(status)))
            self.assertEqual(found, Tailnet('100.98.129.115', ('moos.tailab78a5.ts.net', 'moos'), ''))
            stopped = srv.find_tailscale(run=lambda *a, **k: Result(json.dumps({'BackendState': 'NeedsLogin'})))
            self.assertEqual(stopped, Tailnet(None, (), 'not_connected'))

            def broken(*args, **kwargs):
                raise FileNotFoundError('tailscale')
            self.assertEqual(srv.find_tailscale(run=broken).reason, 'not_connected')
        with patch.object(srv, '_tailscale_cli', return_value=None), \
                patch.object(srv, 'interface_ipv4', return_value='100.98.129.115'):
            self.assertEqual(srv.find_tailscale().ip, '100.98.129.115')
        with patch.object(srv, '_tailscale_cli', return_value=None), patch.object(srv, 'interface_ipv4', return_value=None):
            self.assertEqual(srv.find_tailscale(), Tailnet(None, (), 'not_installed'))


class ServiceTest(QtCase):
    def service(self, controller=None, **kwargs):
        controller = controller or FakeController()
        folder = tempfile.TemporaryDirectory(prefix='mira-companion-svc-')
        self.addCleanup(folder.cleanup)
        svc = CompanionService(controller, config_path=Path(folder.name) / 'companion.json', host='127.0.0.1', port=0,
                               **kwargs)
        self.addCleanup(dispose, controller)
        self.addCleanup(svc.shutdown)
        return controller, svc

    def test_the_panel_state_follows_the_server(self):
        controller, svc = self.service()
        notices = []
        svc.notice.connect(lambda kind, text: notices.append((kind, text)))
        state = svc.state()
        self.assertEqual((state['enabled'], state['state'], state['url'], state['clients']), (False, 'off', '', 0))
        self.assertFalse(svc.store.path.exists(), 'no token is created until the owner turns the phone on')
        svc.set_enabled(True)
        self.assertTrue(pump(lambda: svc.state()['state'] == 'running'), svc.state())
        state = svc.state()
        token = svc.store.token
        port = svc.server.port
        self.assertEqual(state['address'], f'http://127.0.0.1:{port}')
        self.assertEqual(state['url'], f'http://127.0.0.1:{port}/pair?t={token}')
        if state['qrAvailable']:
            self.assertEqual(state['qr'], qr_code(state['url']))
            self.assertGreaterEqual(state['qr']['size'], 21)
        self.assertEqual(state['label'], PANEL_TEXT['state_running'][0])

        harness = type('H', (), {'port': port, 'host': f'127.0.0.1:{port}'})()
        stream = Stream(harness, {'Authorization': 'Bearer ' + token})
        self.addCleanup(stream.close)
        stream.wait('snapshot')
        self.assertTrue(pump(lambda: svc.state()['clients'] == 1))
        self.assertEqual(svc.state()['phones'], PANEL_TEXT['phones_one'][0])

        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        conn.request('GET', '/pair?t=' + token)
        conn.getresponse().read()
        conn.close()
        self.assertTrue(pump(lambda: notices), 'a pairing is announced on the desktop')
        self.assertIn('127.0.0.1', notices[0][1])
        self.assertTrue(svc.state()['lastPaired'])

        svc.rotate_token()
        self.assertEqual(stream.wait('bye'), {'reason': 'rotated'})
        self.assertNotEqual(svc.store.token, token)
        self.assertIn(svc.store.token, svc.state()['url'])

        controller._lang = 'en'
        controller.langChanged.emit()
        self.assertEqual(svc.state()['text']['title'], 'Mira on your phone')
        svc.set_enabled(False)
        state = svc.state()
        self.assertEqual((state['enabled'], state['state'], state['url'], state['address']), (False, 'off', '', ''))
        self.assertFalse(json.loads(svc.store.path.read_text())['enabled'])

    def test_it_stays_off_and_says_why_without_tailscale(self):
        folder = tempfile.TemporaryDirectory(prefix='mira-companion-svc-')
        self.addCleanup(folder.cleanup)

        def factory(*args, **kwargs):
            kwargs['discover'] = lambda: Tailnet(None, (), 'not_installed')
            return CompanionServer(*args, **kwargs)
        controller = FakeController()
        svc = CompanionService(controller, config_path=Path(folder.name) / 'companion.json', server_factory=factory)
        self.addCleanup(dispose, controller)
        self.addCleanup(svc.shutdown)
        svc.set_enabled(True)
        self.assertTrue(pump(lambda: svc.state()['state'] == 'waiting'))
        state = svc.state()
        self.assertEqual(state['reason'], PANEL_TEXT['reason_not_installed'][0])
        self.assertEqual((state['url'], state['address']), ('', ''))

    def test_only_loopback_may_override_the_address(self):
        folder = tempfile.TemporaryDirectory(prefix='mira-companion-svc-')
        self.addCleanup(folder.cleanup)
        for value, expected in (('0.0.0.0', None), ('192.168.3.10', None), ('100.98.129.115', None),
                                ('127.0.0.1', '127.0.0.1')):
            with patch.dict(os.environ, {'MIRA_COMPANION_HOST': value}):
                controller = FakeController()
                svc = CompanionService(controller, config_path=Path(folder.name) / 'c.json')
                self.assertEqual(svc._host, expected, value)
                svc.shutdown()
                dispose(controller)


class RealControllerTest(QtCase):
    """The adapter against Mira's actual controller (test mode, stand-in Echo and brain)."""

    def test_the_real_controller_speaks_through_the_adapter(self):
        from controller import Controller
        from review_fakes import FakeBridge
        QSettings('MoOS', 'Mira').clear()
        controller = Controller(bridge_class=FakeBridge)
        controller.chat.clear()
        h = Harness(controller=controller, posts_per_minute=1000).ready()
        self.addCleanup(h.close)
        stream = Stream(h, h.bearer())
        self.addCleanup(stream.close)
        snapshot = stream.wait('snapshot')
        self.assertEqual(snapshot['s']['talk'], 'تحدّث')
        self.assertEqual(set(snapshot['echo']), {'online', 'voice_enabled'})
        controller._on_voice('listening', '')
        self.assertEqual(stream.wait('state', lambda d: d.get('phase') == 'listening')['phase'], 'listening')
        controller._on_voice('partial_heard', 'ميرا شغلي')
        self.assertEqual(stream.wait('state', lambda d: 'caption' in d)['caption'], 'ميرا شغلي')
        controller._on_voice('ready', '')

        heard = []

        class Brain:
            @staticmethod
            def run_in_thread(text, emit, lang='ar', city=None, on_done=None):
                heard.append((text, threading.current_thread() is threading.main_thread()))
                emit('thinking', '')
                emit('tool', json.dumps({'name': 'home_status', 'status': 'ok', 'summary': 'أضواء البيت · المضاء 2'}))
                emit('reply', 'في ضوءان مضاءان الآن')
                if on_done:
                    on_done({'status': 'ok', 'reply': 'في ضوءان مضاءان الآن'})
        with patch.dict('sys.modules', {'brain': Brain}):
            self.assertEqual(h.post('/api/send', {'text': 'كم ضوء مضاء؟'})[0], 202)
            user = stream.wait('chat', lambda row: row['role'] == 'user')
            card = stream.wait('chat', lambda row: row['role'] == 'action')
            reply = stream.wait('chat', lambda row: row['role'] == 'mira')
        self.assertEqual(heard, [('كم ضوء مضاء؟', True)])
        self.assertEqual(user['text'], 'كم ضوء مضاء؟')
        self.assertEqual((card['status'], card['text']), ('ok', 'أضواء البيت · المضاء 2'))
        self.assertEqual(reply['text'], 'في ضوءان مضاءان الآن')
        self.assertLess(user['seq'], card['seq'])
        self.assertLess(card['seq'], reply['seq'])

        # Echo not connected yet: Mira's own answer reaches the phone, not a success.
        self.assertEqual(h.post('/api/talk')[0], 202)
        self.assertEqual(stream.wait('toast')['kind'], 'error')
        self.assertEqual(controller.bridge.commands, [])
        controller.start()
        self.assertTrue(pump(lambda: controller.echo.get('online') is True))
        stream.wait('state', lambda d: d.get('echo', {}).get('online') is True)
        self.assertEqual(h.post('/api/talk')[0], 202)
        self.assertTrue(pump(lambda: ('wake', 'wake_assistant_1') in controller.bridge.commands))
        controller.chat.clear()
        self.assertEqual(stream.wait('chat_reset'), {'rows': []})
        # Tear down on the Qt thread, in order: the phone, the server and adapter, then Mira.
        stream.close()
        h.close()
        controller._wake_seq += 1          # the controller's pending 18 s wake timeout becomes a no-op
        dispose(controller)


class PanelTest(QtCase):
    FATAL = ('ReferenceError', 'TypeError', 'is not a type', 'Cannot assign', 'Unable to assign',
             'failed to load', 'is not defined', 'Cannot override', 'Type ', 'unavailable', 'Non-existent')

    def test_the_panel_uses_only_known_words_and_routes(self):
        text = PANEL.read_text()
        words = set(re.findall(r'\bpanel\.tx\.(\w+)', text))
        self.assertTrue(words)
        self.assertEqual(sorted(words - set(PANEL_TEXT)), [], 'panel words missing from PANEL_TEXT')
        folder = tempfile.TemporaryDirectory(prefix='mira-companion-panel-')
        self.addCleanup(folder.cleanup)
        controller = FakeController()
        svc = CompanionService(controller, config_path=Path(folder.name) / 'c.json', host='127.0.0.1')
        self.addCleanup(dispose, controller)
        self.addCleanup(svc.shutdown)
        fields = set(re.findall(r'\bpanel\.c\.(\w+)', text))
        self.assertEqual(sorted(fields - set(svc.state())), [], 'panel reads fields the service does not provide')
        routes = set(re.findall(r'\bmira\.(\w+)', text))
        self.assertEqual(routes, {'companion', 'setCompanionEnabled', 'rotateCompanionCode'},
                         'the controller wrappers the integrator adds')

    def test_the_panel_loads_in_every_state_and_both_languages(self):
        class Stub(QObject):
            companionChanged = Signal()
            langChanged = Signal()

            def __init__(self):
                super().__init__()
                self._companion, self._lang, self.calls = {}, 'ar', []
            companion = Property('QVariantMap', lambda self: self._companion, notify=companionChanged)
            lang = Property(str, lambda self: self._lang, notify=langChanged)

            @Slot(bool)
            def setCompanionEnabled(self, on):
                self.calls.append(('enable', on))

            @Slot()
            def rotateCompanionCode(self):
                self.calls.append(('rotate',))

        lines = []
        previous = qInstallMessageHandler(lambda mode, context, message: lines.append(message))
        try:
            stub = Stub()
            engine = QQmlApplicationEngine()
            engine.addImportPath(str(ROOT / 'qml'))
            engine.rootContext().setContextProperty('mira', stub)
            probe = (b'import QtQuick\nimport QtQuick.Window\n'
                     b'Window { width: 640; height: 1100; visible: true; color: Theme.bg0\n'
                     b'  property bool reveal: false\n'
                     b'  property real panelHeight: panel.implicitHeight\n'
                     b'  onRevealChanged: panel.revealed = reveal\n'
                     b'  CompanionPanel { id: panel; x: 20; y: 20; width: 600 } }\n')
            engine.loadData(probe, QUrl.fromLocalFile(str(ROOT / 'qml' / 'Mira' / 'CompanionPanelProbe.qml')))
            self.assertTrue(engine.rootObjects(), lines)
            window = engine.rootObjects()[0]
            folder = tempfile.TemporaryDirectory(prefix='mira-companion-panel-')
            self.addCleanup(folder.cleanup)
            for lang in ('ar', 'en'):
                controller = FakeController(lang=lang)
                svc = CompanionService(controller, config_path=Path(folder.name) / f'{lang}.json', host='127.0.0.1', port=0)
                stub._lang = lang
                stub.langChanged.emit()
                for step in ('off', 'on', 'reveal', 'waiting'):
                    if step == 'on':
                        svc.set_enabled(True)
                        self.assertTrue(pump(lambda: svc.state()['state'] == 'running'))
                    if step == 'reveal':
                        window.setProperty('reveal', True)
                    if step == 'waiting':
                        svc._status = ('waiting', 'not_connected')
                        svc._rebuild()
                    stub._companion = svc.state()
                    stub.companionChanged.emit()
                    pump(timeout=0.1)
                    self.assertGreater(window.property('panelHeight'), 200, (lang, step))
                window.setProperty('reveal', False)
                svc.shutdown()
                dispose(controller)
            window.setProperty('visible', False)
            dispose(engine)
            dispose(stub)
            pump(timeout=0.05)
        finally:
            qInstallMessageHandler(previous)
        fatal = [line for line in lines if any(word in line for word in self.FATAL)]
        self.assertEqual(fatal, [])


if __name__ == '__main__':
    unittest.main()
