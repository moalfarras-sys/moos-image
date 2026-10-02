"""homehub against a fake Home Assistant: RFC 6455 framing, the auth and command protocol, the
registries merged into an inventory, capability bits, hiding rules and the registry writes.

Everything runs on 127.0.0.1 ephemeral ports with an invented token; no real Home Assistant is
touched unless MIRA_LIVE_HA=1, and then only to read."""
import base64
import hashlib
import http.server
import json
import os
import socket
import stat
import struct
import tempfile
import threading
import unittest
from pathlib import Path

import homehub
from homehub import (OP_BINARY, OP_CLOSE, OP_CONT, OP_PING, OP_PONG, OP_TEXT, HubError,
                     encode_frame, read_frame)

TOKEN = 'test-token-' + 'x' * 48            # invented; never a real one
GUID = b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def _reader(data: bytes):
    view = memoryview(data)
    pos = [0]

    def read(n):
        if pos[0] + n > len(view):
            raise EOFError
        out = bytes(view[pos[0]:pos[0] + n])
        pos[0] += n
        return out
    return read


# ── realistic shapes (from a Home Assistant 2026.9 install, names made generic) ──

HUE_LAMP = {'min_color_temp_kelvin': 2000, 'max_color_temp_kelvin': 6535,
            'effect_list': ['off', 'candle', 'fire', 'prism', 'sparkle', 'opal', 'glisten',
                            'underwater', 'cosmos', 'sunbeam', 'enchant', 'sunrise', 'sunset'],
            'supported_color_modes': ['color_temp', 'xy'], 'effect': 'off', 'color_mode': 'xy',
            'brightness': 128, 'color_temp_kelvin': None, 'hs_color': [193.8, 5.1],
            'rgb_color': [242, 252, 255], 'xy_color': [0.31, 0.3277], 'mode': 'normal',
            'dynamics': 'none', 'friendly_name': 'Desk', 'supported_features': 44}
TUYA_LIGHT = {'supported_color_modes': ['hs', 'white'], 'color_mode': None, 'brightness': None,
              'hs_color': None, 'rgb_color': None, 'xy_color': None,
              'friendly_name': 'Wall Light ', 'supported_features': 0}
HUE_GROUP = {'min_color_temp_kelvin': 2000, 'max_color_temp_kelvin': 6535,
             'supported_color_modes': ['color_temp', 'xy'], 'color_mode': 'xy', 'brightness': 255,
             'is_hue_group': True, 'hue_scenes': [], 'hue_type': 'room', 'lights': ['Desk', 'Shelf'],
             'entity_id': ['light.room_desk', 'light.room_shelf'], 'dynamics': False,
             'friendly_name': 'Room', 'supported_features': 40}
RING = {'effect_list': ['None', 'Pulse', 'Candle', 'Rainbow'], 'supported_color_modes': ['rgb'],
        'effect': None, 'color_mode': None, 'brightness': None, 'friendly_name': 'Mira ring LED ring',
        'supported_features': 44}
ANDROID_TV = {'volume_level': 0.35, 'is_volume_muted': False, 'app_id': 'com.tcl.tv',
              'app_name': 'com.tcl.tv', 'assumed_state': True, 'device_class': 'tv',
              'friendly_name': 'Living TV', 'supported_features': 153529}
CAST_TV = {'friendly_name': 'Living TV', 'supported_features': 152461}
SPEAKER = {'volume_level': 1.0, 'is_volume_muted': False, 'device_class': 'speaker',
           'friendly_name': 'Mira Speaker', 'supported_features': 1201677}
TV_REMOTE = {'activity_list': [], 'current_activity': 'com.tcl.tv', 'friendly_name': 'Living TV',
             'supported_features': 4}
PLUG = {'device_class': 'outlet', 'friendly_name': 'Plug Socket 1'}
POWER = {'state_class': 'measurement', 'unit_of_measurement': 'W', 'device_class': 'power',
         'friendly_name': 'Plug Power'}


def st(entity_id, state, attrs):
    return {'entity_id': entity_id, 'state': state, 'attributes': dict(attrs)}


def ent(entity_id, platform, device_id=None, **kw):
    entry = {'entity_id': entity_id, 'platform': platform, 'device_id': device_id, 'area_id': None,
             'name': None, 'original_name': None, 'has_entity_name': True, 'entity_category': None,
             'hidden_by': None, 'disabled_by': None, 'unique_id': 'u-' + entity_id}
    entry.update(kw)
    return entry


def dev(device_id, name, area_id=None, **kw):
    return {'id': device_id, 'name': name, 'name_by_user': None, 'area_id': area_id,
            'manufacturer': kw.pop('manufacturer', 'Maker'), 'model': kw.pop('model', 'Model'),
            'parent_device_id': None, **kw}


def home():
    """A small home shaped like the owner's: Hue, Tuya, an Android TV seen twice, the Echo."""
    states = [
        st('light.room_desk', 'on', HUE_LAMP),
        st('light.room_room', 'on', HUE_GROUP),
        st('light.wall_light', 'off', TUYA_LIGHT),
        st('light.mira_ring_led_ring', 'off', RING),
        st('light.mira_ring_led_ring_segment_1', 'off', RING),
        st('media_player.living_tv_2', 'on', ANDROID_TV),
        st('media_player.living_tv', 'off', CAST_TV),
        st('media_player.mira_speaker', 'idle', SPEAKER),
        st('remote.living_tv', 'on', TV_REMOTE),
        st('switch.plug_socket_1', 'unavailable', PLUG),
        st('sensor.plug_power', 'unavailable', POWER),
        st('select.plug_power_on_behavior', 'unavailable', {'options': ['on', 'off']}),
        st('sensor.hue_zigbee', 'connected', {'friendly_name': 'Zigbee connectivity'}),
        st('number.mira_volume', '50', {'friendly_name': 'Mira volume'}),
        st('switch.mira_mute', 'off', {'friendly_name': 'Mira mute'}),
        st('update.mira_firmware', 'on', {'friendly_name': 'Mira Firmware'}),
        st('sun.sun', 'below_horizon', {'friendly_name': 'Sun'}),
        st('sensor.sun_next_dawn', '2026-10-03T05:10:28+00:00', {'device_class': 'timestamp'}),
        st('sensor.backup_backup_manager_state', 'idle', {'device_class': 'enum'}),
        st('zone.home', '0', {'friendly_name': 'Home'}),
        st('person.owner', 'unknown', {'friendly_name': 'Owner'}),
        st('todo.shopping_list', '0', {}),
        st('tts.google_translate_en_com', 'unknown', {}),
        st('conversation.home_assistant', 'unknown', {}),
        st('event.backup_automatic_backup', 'unknown', {}),
        st('scene.room_relax', 'unknown', {'friendly_name': 'Room Relax'}),
    ]
    registry = {
        'areas': [{'area_id': 'living_room', 'name': 'البيت', 'aliases': ['salon']},
                  {'area_id': 'office', 'name': 'Office', 'aliases': []}],
        'devices': [
            dev('d_desk', 'Desk', 'office', manufacturer='Signify', model='Hue color lamp'),
            dev('d_room', 'Room', 'office', manufacturer='Signify', model='Room', entry_type='service'),
            dev('d_wall', 'Wall Light ', 'living_room', manufacturer='Tuya', model='Wall Light'),
            dev('d_tv_atv', 'Living TV', 'living_room', manufacturer='TCL', model='Smart TV Pro'),
            dev('d_tv_cast', 'Living TV', None, manufacturer='TCL', model='Smart TV Pro'),
            dev('d_echo', 'Mira', 'living_room', manufacturer='TECHO5', model='Echo Dot 2'),
            dev('d_ring', 'Mira ring', 'living_room', manufacturer='TECHO5', model='Echo Dot 2'),
            dev('d_plug', 'Plug', 'living_room', manufacturer='Tuya', model='Plug+'),
            dev('d_sun', 'Sun', None, entry_type='service'),
            dev('d_backup', 'Backup', None, entry_type='service'),
            dev('d_child', 'Desk socket', None, manufacturer=None, model=None, parent_device_id='d_plug'),
        ],
        'entities': [
            ent('light.room_desk', 'hue', 'd_desk'),
            ent('light.room_room', 'hue', 'd_room'),
            ent('light.wall_light', 'tuya', 'd_wall'),
            ent('light.mira_ring_led_ring', 'esphome', 'd_ring', original_name='LED ring'),
            ent('light.mira_ring_led_ring_segment_1', 'esphome', 'd_ring',
                original_name='LED ring segment 1', hidden_by='integration'),
            ent('media_player.living_tv_2', 'androidtv_remote', 'd_tv_atv'),
            ent('media_player.living_tv', 'cast', 'd_tv_cast'),
            ent('media_player.mira_speaker', 'esphome', 'd_echo', original_name='Speaker'),
            ent('remote.living_tv', 'androidtv_remote', 'd_tv_atv'),
            ent('switch.plug_socket_1', 'tuya', 'd_plug', original_name='Socket 1'),
            ent('sensor.plug_power', 'tuya', 'd_plug', original_name='Power'),
            ent('select.plug_power_on_behavior', 'tuya', 'd_plug', entity_category='config'),
            ent('sensor.hue_zigbee', 'hue', 'd_desk', entity_category='diagnostic'),
            ent('number.mira_volume', 'esphome', 'd_echo', original_name='Volume'),
            ent('switch.mira_mute', 'esphome', 'd_echo', original_name='Mute'),
            ent('update.mira_firmware', 'esphome', 'd_echo', entity_category='config'),
            ent('sensor.sun_next_dawn', 'sun', 'd_sun', entity_category='diagnostic'),
            ent('sensor.backup_backup_manager_state', 'backup', 'd_backup'),
            ent('event.backup_automatic_backup', 'backup', 'd_backup'),
            ent('scene.room_relax', 'hue', 'd_room', original_name='Relax'),
            ent('switch.desk_socket', 'tuya', 'd_child', disabled_by='user'),
        ],
        'extended': {'light.wall_light': {'aliases': [None, 'lamp on the wall']}},
    }
    return states, registry


# ── framing ──────────────────────────────────────────────────────────

class Framing(unittest.TestCase):
    def test_rfc_examples(self):
        # RFC 6455 §5.7: a single-frame unmasked and masked "Hello"
        self.assertEqual(encode_frame(OP_TEXT, b'Hello', masked=False), bytes.fromhex('810548656c6c6f'))
        masked = encode_frame(OP_TEXT, b'Hello', key=bytes.fromhex('37fa213d'))
        self.assertEqual(masked, bytes.fromhex('818537fa213d7f9f4d5158'))
        self.assertEqual(read_frame(_reader(masked), masked=True), (True, OP_TEXT, b'Hello'))
        # a fragmented unmasked text message, and an unmasked ping
        fragments = bytes.fromhex('010348656c') + bytes.fromhex('80026c6f')
        read = _reader(fragments)
        self.assertEqual(read_frame(read), (False, OP_TEXT, b'Hel'))
        self.assertEqual(read_frame(read), (True, OP_CONT, b'lo'))
        self.assertEqual(read_frame(_reader(bytes.fromhex('890548656c6c6f'))), (True, OP_PING, b'Hello'))

    def test_client_masks_every_frame_with_a_fresh_key(self):
        a, b = encode_frame(OP_TEXT, b'same'), encode_frame(OP_TEXT, b'same')
        self.assertTrue(a[1] & 0x80 and b[1] & 0x80)
        self.assertNotEqual(a[2:6], b'\0\0\0\0')
        self.assertEqual(read_frame(_reader(a), masked=True)[2], b'same')
        self.assertEqual(homehub.mask(b'\1\2\3\4', homehub.mask(b'\1\2\3\4', b'abcdefg')), b'abcdefg')
        self.assertEqual(homehub.mask(b'\1\2\3\4', b''), b'')

    def test_length_forms(self):
        for n, header_len, marker in ((125, 2, 125), (126, 4, 126), (65535, 4, 126), (65536, 10, 127),
                                      (200_000, 10, 127)):
            payload = os.urandom(n)
            frame = encode_frame(OP_BINARY, payload, masked=False)
            self.assertEqual(frame[1] & 0x7F, marker, n)
            self.assertEqual(len(frame), header_len + n)
            if marker == 126:
                self.assertEqual(struct.unpack('!H', frame[2:4])[0], n)
            if marker == 127:
                self.assertEqual(struct.unpack('!Q', frame[2:10])[0], n)
            self.assertEqual(read_frame(_reader(frame)), (True, OP_BINARY, payload))
            masked = encode_frame(OP_BINARY, payload)
            self.assertEqual(len(masked), header_len + 4 + n)
            self.assertEqual(read_frame(_reader(masked), masked=True)[2], payload)

    def test_protocol_violations(self):
        bad = {
            'masked from server': encode_frame(OP_TEXT, b'x'),
            'reserved bit': bytes([0x80 | 0x40 | OP_TEXT, 1]) + b'x',
            'long control': bytes([0x80 | OP_PING, 126]) + struct.pack('!H', 126) + b'x' * 126,
            'fragmented control': bytes([OP_PING, 1]) + b'x',
            'unknown opcode': bytes([0x80 | 0x3, 1]) + b'x',
            'unknown control': bytes([0x80 | 0xB, 0]),
            'high bit length': bytes([0x80 | OP_BINARY, 127]) + struct.pack('!Q', 1 << 63),
        }
        for name, frame in bad.items():
            with self.subTest(name), self.assertRaises(HubError) as cm:
                read_frame(_reader(frame))
            self.assertEqual(cm.exception.code, 'protocol')
        with self.assertRaises(HubError):           # a server must reject an unmasked client frame
            read_frame(_reader(encode_frame(OP_TEXT, b'x', masked=False)), masked=True)
        with self.assertRaises(HubError):
            read_frame(_reader(encode_frame(OP_BINARY, b'x' * 300, masked=False)), limit=200)


class _RawServer:
    """A TCP server that runs `script(conn, request_head)` once, for byte-level WebSocket tests."""

    def __init__(self, script):
        self.sock = socket.create_server(('127.0.0.1', 0))
        self.port = self.sock.getsockname()[1]
        self.script, self.error, self.received = script, None, []
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        conn, _ = self.sock.accept()
        with conn:
            conn.settimeout(5)
            head = b''
            while b'\r\n\r\n' not in head:
                head += conn.recv(4096)
            try:
                self.script(conn, head.decode('iso-8859-1'))
            except Exception as exc:    # surfaced by the test through .error
                self.error = exc

    @staticmethod
    def accept_header(head, *, wrong=False):
        key = next(line.split(':', 1)[1].strip() for line in head.split('\r\n')
                   if line.lower().startswith('sec-websocket-key:'))
        accept = base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode()
        return 'AAAA' + accept[4:] if wrong else accept

    def upgrade(self, head, wrong=False):
        return ('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                f'Sec-WebSocket-Accept: {self.accept_header(head, wrong=wrong)}\r\n\r\n').encode()

    def read_client(self, conn):
        buf = bytearray()

        def read(n):
            while len(buf) < n:
                chunk = conn.recv(65536)
                if not chunk:
                    raise EOFError
                buf.extend(chunk)
            out = bytes(buf[:n])
            del buf[:n]
            return out
        return read

    def close(self):
        self.thread.join(5)
        self.sock.close()


class Stream(unittest.TestCase):
    def test_handshake_frames_in_the_same_segment_fragments_and_ping(self):
        def script(conn, head):
            first = json.dumps({'type': 'auth_required', 'ha_version': '2026.9.4'}).encode()
            body = json.dumps({'big': 'y' * 70_000}).encode()
            # the upgrade, a whole message, then a fragmented one with a ping in the middle: one write
            conn.sendall(server.upgrade(head) + encode_frame(OP_TEXT, first, masked=False)
                         + encode_frame(OP_TEXT, body[:10], fin=False, masked=False)
                         + encode_frame(OP_PING, b'are you there', masked=False)
                         + encode_frame(OP_CONT, body[10:40_000], fin=False, masked=False)
                         + encode_frame(OP_CONT, body[40_000:], masked=False))
            read = server.read_client(conn)
            server.received.append(read_frame(read, masked=True))      # the pong
            server.received.append(read_frame(read, masked=True))      # the close
            conn.sendall(encode_frame(OP_CLOSE, struct.pack('!H', 1000), masked=False))
        server = _RawServer(script)
        ws = homehub.WebSocket(f'ws://127.0.0.1:{server.port}/api/websocket', 5)
        self.assertEqual(ws.recv_json()['ha_version'], '2026.9.4')
        self.assertEqual(len(ws.recv_json()['big']), 70_000)
        ws.close()
        server.close()
        self.assertIsNone(server.error)
        self.assertEqual(server.received[0], (True, OP_PONG, b'are you there'))
        self.assertEqual(server.received[1][1], OP_CLOSE)
        self.assertEqual(struct.unpack('!H', server.received[1][2])[0], 1000)

    def test_server_close_is_answered_and_reported(self):
        def script(conn, head):
            conn.sendall(server.upgrade(head) + encode_frame(OP_CLOSE, struct.pack('!H', 1008) + b'policy', masked=False))
            server.received.append(read_frame(server.read_client(conn), masked=True))
        server = _RawServer(script)
        ws = homehub.WebSocket(f'ws://127.0.0.1:{server.port}/api/websocket', 5)
        with self.assertRaises(HubError) as cm:
            ws.recv_message()
        self.assertIn('1008 policy', cm.exception.en)
        ws.close()
        server.close()
        self.assertEqual(server.received[0], (True, OP_CLOSE, struct.pack('!H', 1008)))

    def test_bad_accept_and_refused_upgrade(self):
        server = _RawServer(lambda conn, head: conn.sendall(server.upgrade(head, wrong=True)))
        with self.assertRaises(HubError) as cm:
            homehub.WebSocket(f'ws://127.0.0.1:{server.port}/api/websocket', 5)
        self.assertEqual(cm.exception.code, 'protocol')
        server.close()
        server = _RawServer(lambda conn, head: conn.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n'))
        with self.assertRaises(HubError):
            homehub.WebSocket(f'ws://127.0.0.1:{server.port}/api/websocket', 5)
        server.close()

    def test_unreachable(self):
        sock = socket.create_server(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        with self.assertRaises(HubError) as cm:
            homehub.WebSocket(f'ws://127.0.0.1:{port}/api/websocket', 2)
        self.assertEqual(cm.exception.code, 'unreachable')
        self.assertEqual(str(cm.exception), 'خادم البيت غير متاح')


# ── a fake Home Assistant: REST + WebSocket on one port ──────────────

class FakeHA:
    def __init__(self, states=None, registry=None, *, onboarding=None, fragment=0, noise=False,
                 flows=None):
        base_states, base_registry = home()
        self.states = states if states is not None else base_states
        self.reg = registry if registry is not None else base_registry
        self.onboarding, self.fragment, self.noise = onboarding, fragment, noise
        self.flows = flows or []
        self.commands, self.http_log, self.pongs, self.services = [], [], [], []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *args):
                pass

            def _json(self, status, body):
                raw = json.dumps(body).encode()
                fake.http_log.append((self.command, self.path, status))
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _authed(self):
                return self.headers.get('Authorization') == 'Bearer ' + TOKEN

            def do_GET(self):
                if self.path == '/api/websocket' and self.headers.get('Upgrade', '').lower() == 'websocket':
                    return fake.websocket(self)
                if self.path == '/manifest.json':
                    return self._json(200, {'name': 'Home Assistant', 'short_name': 'Home Assistant'})
                if self.path == '/api/onboarding':
                    return self._json(200, fake.onboarding) if fake.onboarding is not None else self._json(404, {})
                if not self._authed():
                    return self._json(401, {'message': '401: Unauthorized'})
                if self.path == '/api/states':
                    return self._json(200, fake.states)
                if self.path.startswith('/api/states/'):
                    entity_id = self.path.rsplit('/', 1)[1]
                    match = [s for s in fake.states if s['entity_id'] == entity_id]
                    return self._json(200, match[0]) if match else self._json(404, {'message': 'Entity not found.'})
                return self._json(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'null')
                if not self._authed():
                    return self._json(401, {'message': '401: Unauthorized'})
                if self.path.startswith('/api/services/'):
                    fake.services.append((self.path, body))
                    return self._json(200, [])
                return self._json(404, {})

        self.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    # the WebSocket side
    def websocket(self, handler):
        key = handler.headers['Sec-WebSocket-Key']
        handler.send_response(101, 'Switching Protocols')
        handler.send_header('Upgrade', 'websocket')
        handler.send_header('Connection', 'Upgrade')
        handler.send_header('Sec-WebSocket-Accept',
                            base64.b64encode(hashlib.sha1(key.encode() + GUID).digest()).decode())
        handler.end_headers()
        handler.close_connection = True
        out, read = handler.wfile, handler.rfile.read

        def send(obj):
            data = json.dumps(obj).encode()
            if self.fragment and len(data) > self.fragment:
                chunks = [data[i:i + self.fragment] for i in range(0, len(data), self.fragment)]
                for i, chunk in enumerate(chunks):
                    out.write(encode_frame(OP_TEXT if i == 0 else OP_CONT, chunk,
                                           fin=i == len(chunks) - 1, masked=False))
            else:
                out.write(encode_frame(OP_TEXT, data, masked=False))

        def receive():
            while True:
                _fin, op, payload = read_frame(read, masked=True)     # the client must mask
                if op == OP_PONG:
                    self.pongs.append(payload)
                    continue
                if op == OP_CLOSE:
                    out.write(encode_frame(OP_CLOSE, payload[:2], masked=False))
                    return None
                return json.loads(payload)

        send({'type': 'auth_required', 'ha_version': '2026.9.4'})
        auth = receive()
        if auth is None:
            return
        if auth.get('access_token') != TOKEN:
            send({'type': 'auth_invalid', 'message': 'Invalid access token or password'})
            return
        send({'type': 'auth_ok', 'ha_version': '2026.9.4'})
        while (msg := receive()) is not None:
            self.commands.append(msg)
            if self.noise:      # a ping and an unrelated message before the answer
                out.write(encode_frame(OP_PING, b'p%d' % msg['id'], masked=False))
                send({'id': msg['id'] + 1000, 'type': 'event', 'event': {}})
            try:
                send({'id': msg['id'], 'type': 'result', 'success': True, 'result': self.answer(msg)})
            except LookupError as exc:
                send({'id': msg['id'], 'type': 'result', 'success': False,
                      'error': {'code': 'not_found', 'message': str(exc)}})
            except ValueError as exc:
                send({'id': msg['id'], 'type': 'result', 'success': False,
                      'error': {'code': 'invalid_info', 'message': str(exc)}})

    def _entry(self, entity_id):
        for e in self.reg['entities']:
            if e['entity_id'] == entity_id:
                return e
        raise LookupError('Entity not found')

    def _extended(self, entity_id):
        e = self._entry(entity_id)
        return {**e, 'aliases': self.reg['extended'].get(entity_id, {}).get('aliases', [])}

    def answer(self, msg):
        kind = msg['type']
        if kind == 'config/area_registry/list':
            return self.reg['areas']
        if kind == 'config/device_registry/list':
            return self.reg['devices']
        if kind == 'config/entity_registry/list':
            return self.reg['entities']
        if kind == 'config/entity_registry/get':
            return self._extended(msg['entity_id'])
        if kind == 'config/entity_registry/get_entries':
            return {i: self._extended(i) for i in msg['entity_ids']}
        if kind == 'config/entity_registry/update':
            entry = self._entry(msg['entity_id'])
            for k in ('name', 'area_id'):
                if k in msg:
                    entry[k] = msg[k]
            if 'aliases' in msg:
                self.reg['extended'].setdefault(msg['entity_id'], {})['aliases'] = msg['aliases']
            return {'entity_entry': self._extended(msg['entity_id'])}
        if kind == 'config/area_registry/create':
            if any(a['name'].casefold() == msg['name'].casefold() for a in self.reg['areas']):
                raise ValueError(f"The name {msg['name']} is already in use")
            area = {'area_id': msg['name'].lower().replace(' ', '_'), 'name': msg['name'], 'aliases': []}
            self.reg['areas'].append(area)
            return area
        if kind == 'config/area_registry/delete':
            self.reg['areas'] = [a for a in self.reg['areas'] if a['area_id'] != msg['area_id']]
            return 'success'
        if kind == 'config/device_registry/update':
            device = next(d for d in self.reg['devices'] if d['id'] == msg['device_id'])
            device['name_by_user'] = msg.get('name_by_user')
            return device
        if kind == 'config_entries/flow/progress':
            return self.flows
        raise ValueError('Unknown command.')


class _WithFake(unittest.TestCase):
    fake_kwargs: dict = {}

    def setUp(self):
        self.fake = FakeHA(**self.fake_kwargs)
        self.hub = homehub.Hub(self.fake.url, TOKEN, timeout=5)

    def tearDown(self):
        self.fake.stop()


class Protocol(_WithFake):
    fake_kwargs = {'noise': True, 'fragment': 700}

    def test_one_session_ids_results_pings_and_fragments(self):
        areas, devices, missing_ok = self.hub.ws([{'type': 'config/area_registry/list'},
                                                  {'type': 'config/device_registry/list'},
                                                  {'type': 'config_entries/flow/progress'}])
        self.assertEqual([a['area_id'] for a in areas], ['living_room', 'office'])
        self.assertEqual(len(devices), len(self.fake.reg['devices']))
        self.assertEqual(missing_ok, [])
        self.assertEqual([c['id'] for c in self.fake.commands], [1, 2, 3])
        self.assertEqual(self.fake.pongs, [b'p1', b'p2', b'p3'])

    def test_refusal_carries_home_assistants_message(self):
        with self.assertRaises(HubError) as cm:
            self.hub.ws([{'type': 'config/entity_registry/get', 'entity_id': 'light.nothing'}])
        self.assertIn('Entity not found', str(cm.exception))
        self.assertTrue(str(cm.exception).startswith('رفض Home Assistant الطلب'))
        self.assertEqual(cm.exception.code, 'not_found')

    def test_large_registry_crosses_the_64k_frame_form(self):
        self.fake.fragment = 0
        self.fake.reg['entities'] += [ent(f'sensor.filler_{i}', 'demo', original_name='x' * 60) for i in range(600)]
        entities = self.hub.registry()['entities']
        self.assertGreater(len(json.dumps(entities)), 65535)
        self.assertEqual(len(entities), len(self.fake.reg['entities']))

    def test_auth_invalid(self):
        hub = homehub.Hub(self.fake.url, 'wrong-' + 'y' * 48, timeout=5)
        with self.assertRaises(HubError) as cm:
            hub.registry()
        self.assertEqual(cm.exception.code, 'auth')
        self.assertNotIn('y' * 48, str(cm.exception) + cm.exception.en)
        self.assertEqual(self.fake.commands, [])

    def test_token_never_shows(self):
        self.assertNotIn(TOKEN, repr(self.hub) + str(vars(self.hub).get('url')))
        with self.assertRaises(HubError) as cm:
            homehub.Hub('http://127.0.0.1:1', TOKEN, timeout=1).states()
        self.assertNotIn(TOKEN, str(cm.exception) + cm.exception.en)


class Rest(_WithFake):
    def test_states_state_call(self):
        self.assertEqual(len(self.hub.states()), len(self.fake.states))
        self.assertEqual(self.hub.state('light.room_desk')['state'], 'on')
        with self.assertRaises(HubError) as cm:
            self.hub.state('light.nothing')
        self.assertEqual((cm.exception.code, str(cm.exception)), ('not_found', 'الجهاز غير موجود في البيت'))
        self.assertEqual(self.hub.call('light', 'turn_on', {'entity_id': 'light.room_desk'}), [])
        self.assertEqual(self.fake.services, [('/api/services/light/turn_on', {'entity_id': 'light.room_desk'})])
        with self.assertRaises(HubError):
            self.hub.call('light', '../config', {})
        with self.assertRaises(HubError):
            self.hub.state('light.x/../../config')

    def test_rejected_token(self):
        with self.assertRaises(HubError) as cm:
            homehub.Hub(self.fake.url, 'bad-' + 'z' * 48, timeout=5).states()
        self.assertEqual(cm.exception.code, 'auth')


class Probe(_WithFake):
    def test_finished_install(self):
        self.assertEqual(homehub.probe(self.fake.url), {'reachable': True, 'version': '2026.9.4', 'needs_onboarding': False})
        self.assertFalse([entry for entry in self.fake.http_log if entry[2] == 401],
                         'a 401 is a failed login that Home Assistant shows the owner')
        self.assertFalse(any(path.rstrip('/') == '/api' for _m, path, _s in self.fake.http_log))

    def test_fresh_install_and_nothing_there(self):
        self.fake.onboarding = [{'step': 'user', 'done': True}, {'step': 'core_config', 'done': False}]
        self.assertTrue(homehub.probe(self.fake.url)['needs_onboarding'])
        sock = socket.create_server(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        self.assertEqual(homehub.probe(f'http://127.0.0.1:{port}', timeout=1),
                         {'reachable': False, 'version': None, 'needs_onboarding': False})
        self.assertFalse(homehub.probe('ftp://example')['reachable'])


# ── capabilities ─────────────────────────────────────────────────────

class Capabilities(unittest.TestCase):
    def test_hue_lamp(self):
        caps = homehub.capabilities('light.desk', 'on', HUE_LAMP, 'hue')
        self.assertTrue(caps['brightness'] and caps['color'] and caps['transition'] and caps['flash'])
        self.assertFalse(caps['white'])
        self.assertEqual(caps['temp'], {'min_kelvin': 2000, 'max_kelvin': 6535})
        self.assertEqual(caps['effects'][:3], ['candle', 'fire', 'prism'])
        self.assertNotIn('off', caps['effects'])
        self.assertEqual(caps['current'], {'on': True, 'brightness': 50, 'rgb': [242, 252, 255],
                                           'kelvin': None, 'effect': None, 'color_mode': 'xy'})

    def test_tuya_hs_white(self):
        caps = homehub.capabilities('light.wall', 'off', TUYA_LIGHT, 'tuya')
        self.assertTrue(caps['color'] and caps['brightness'] and caps['white'])
        self.assertIsNone(caps['temp'])
        self.assertEqual(caps['effects'], [])
        self.assertFalse(caps['transition'])
        self.assertEqual(caps['current']['brightness'], None)

    def test_onoff_and_brightness_only(self):
        self.assertFalse(homehub.capabilities('light.a', 'on', {'supported_color_modes': ['onoff']})['brightness'])
        caps = homehub.capabilities('light.a', 'on', {'supported_color_modes': ['brightness'], 'brightness': 255})
        self.assertTrue(caps['brightness'])
        self.assertFalse(caps['color'])
        self.assertEqual(caps['current']['brightness'], 100)

    def test_esphome_ring_effects_drop_none(self):
        self.assertEqual(homehub.capabilities('light.mira_ring_led_ring', 'off', RING)['effects'],
                         ['Pulse', 'Candle', 'Rainbow'])

    def test_android_tv_153529(self):
        caps = homehub.capabilities('media_player.tv', 'on', ANDROID_TV, 'androidtv_remote')
        for yes in ('turn_on', 'turn_off', 'volume_step', 'mute', 'play', 'pause', 'stop', 'next',
                    'previous', 'play_media', 'browse', 'power', 'volume'):
            self.assertTrue(caps[yes], yes)
        for no in ('volume_set', 'select_source', 'seek', 'announce'):
            self.assertFalse(caps[no], no)
        self.assertEqual(caps['current']['volume'], 35)
        self.assertFalse(caps['current']['muted'])

    def test_cast_152461(self):
        caps = homehub.capabilities('media_player.tv', 'off', CAST_TV, 'cast')
        for yes in ('turn_on', 'turn_off', 'volume_set', 'mute', 'play', 'pause', 'stop', 'play_media', 'browse'):
            self.assertTrue(caps[yes], yes)
        for no in ('volume_step', 'next', 'previous', 'select_source'):
            self.assertFalse(caps[no], no)

    def test_esphome_speaker_1201677(self):
        caps = homehub.capabilities('media_player.mira_speaker', 'idle', SPEAKER, 'esphome')
        for yes in ('volume_set', 'volume_step', 'mute', 'play', 'pause', 'stop', 'announce', 'play_media', 'browse'):
            self.assertTrue(caps[yes], yes)
        for no in ('turn_on', 'turn_off', 'power', 'next', 'previous'):
            self.assertFalse(caps[no], no)
        self.assertEqual(caps['current']['volume'], 100)

    def test_sources(self):
        attrs = {'supported_features': 2048 | 4, 'source_list': ['HDMI 1', 'HDMI 2'], 'source': 'HDMI 1'}
        caps = homehub.capabilities('media_player.avr', 'on', attrs)
        self.assertEqual((caps['sources'], caps['current']['source']), (['HDMI 1', 'HDMI 2'], 'HDMI 1'))
        self.assertEqual(homehub.capabilities('media_player.avr', 'on', {**attrs, 'supported_features': 4})['sources'], [])

    def test_remote(self):
        caps = homehub.capabilities('remote.tv', 'on', TV_REMOTE, 'androidtv_remote')
        self.assertTrue(caps['send_command'] and caps['activity'])
        self.assertFalse(caps['learn'])
        self.assertIn('DPAD_CENTER', caps['keys'])
        self.assertIn('VOLUME_UP', caps['keys'])
        self.assertEqual(caps['current']['activity'], 'com.tcl.tv')
        self.assertEqual(homehub.capabilities('remote.ir', 'on', {'supported_features': 3}, 'broadlink')['keys'], [])

    def test_fan_cover_climate_and_the_rest(self):
        fan = homehub.capabilities('fan.a', 'on', {'supported_features': 1 | 8 | 16 | 32, 'preset_modes': ['sleep']})
        self.assertTrue(fan['speed'] and fan['presets'] and fan['power'])
        self.assertFalse(fan['oscillate'] or fan['direction'])
        self.assertEqual(fan['preset_modes'], ['sleep'])
        cover = homehub.capabilities('cover.a', 'open', {'supported_features': 1 | 2 | 4 | 8, 'current_position': 40})
        self.assertTrue(cover['open'] and cover['close'] and cover['position'] and cover['stop'])
        self.assertFalse(cover['tilt'])
        self.assertEqual(cover['current']['position'], 40)
        climate = homehub.capabilities('climate.a', 'cool', {'supported_features': 1 | 8 | 128 | 256,
                                                              'hvac_modes': ['off', 'cool', 'heat'],
                                                              'fan_modes': ['low', 'high'], 'min_temp': 16, 'max_temp': 30})
        self.assertTrue(climate['target_temperature'] and climate['fan_modes'] and climate['power'])
        self.assertFalse(climate['target_range'] or climate['presets'])
        self.assertEqual(climate['fan_mode_list'], ['low', 'high'])
        self.assertEqual(homehub.capabilities('scene.a', 'unknown', {}), {'activate': True})
        self.assertEqual(homehub.capabilities('button.a', 'unknown', {}), {'press': True})
        self.assertTrue(homehub.capabilities('switch.a', 'on', PLUG)['current']['on'])
        sensor = homehub.capabilities('sensor.p', '12.5', POWER)
        self.assertEqual((sensor['read_only'], sensor['value'], sensor['unit'], sensor['device_class']),
                         (True, '12.5', 'W', 'power'))
        self.assertTrue(homehub.capabilities('lock.door', 'locked', {'supported_features': 1})['open'])


# ── the inventory ────────────────────────────────────────────────────

class Inventory(unittest.TestCase):
    def setUp(self):
        states, registry = home()
        self.records = {r['entity_id']: r for r in homehub.build_inventory(states, registry)}
        self.all = {r['entity_id']: r for r in homehub.build_inventory(states, registry, include_hidden=True)}

    def test_hiding_rules(self):
        self.assertEqual(sorted(self.records), sorted([
            'light.room_desk', 'light.room_room', 'light.wall_light', 'light.mira_ring_led_ring',
            'media_player.living_tv_2', 'media_player.living_tv', 'media_player.mira_speaker',
            'remote.living_tv', 'switch.plug_socket_1', 'sensor.plug_power', 'scene.room_relax']))
        reasons = {i: r['hidden_reason'] for i, r in self.all.items() if r['hidden']}
        self.assertEqual(reasons, {
            'light.mira_ring_led_ring_segment_1': 'hidden', 'select.plug_power_on_behavior': 'config',
            'sensor.hue_zigbee': 'diagnostic', 'number.mira_volume': 'echo', 'switch.mira_mute': 'echo',
            'update.mira_firmware': 'config', 'sun.sun': 'domain', 'sensor.sun_next_dawn': 'diagnostic',
            'sensor.backup_backup_manager_state': 'platform', 'zone.home': 'domain', 'person.owner': 'domain',
            'todo.shopping_list': 'domain', 'tts.google_translate_en_com': 'domain',
            'conversation.home_assistant': 'domain', 'event.backup_automatic_backup': 'domain',
            'switch.desk_socket': 'disabled'})
        self.assertFalse(any(r['hidden'] for r in self.records.values()))
        self.assertIsNone(self.all['switch.desk_socket']['state'])          # disabled: no state
        self.assertFalse(self.all['switch.desk_socket']['available'])

    def test_echo_without_a_registry_entry(self):
        self.assertEqual(homehub.hidden_reason('select.mira_wake_word', None), 'echo')
        self.assertIsNone(homehub.hidden_reason('media_player.mira_speaker', None))
        self.assertIsNone(homehub.hidden_reason('light.mira_ring_led_ring', None))
        self.assertIsNone(homehub.hidden_reason('switch.mira_lamp', {'platform': 'tuya'}))   # not the Echo

    def test_names_areas_devices(self):
        wall = self.records['light.wall_light']
        self.assertEqual((wall['name'], wall['default_name'], wall['renamed'], wall['registry_name']),
                         ('Wall Light', 'Wall Light', False, None))
        self.assertEqual((wall['area'], wall['area_id'], wall['entity_area_id']), ('البيت', 'living_room', None))
        self.assertEqual((wall['manufacturer'], wall['model'], wall['integration']), ('Tuya', 'Wall Light', 'tuya'))
        self.assertEqual(wall['aliases'], ['lamp on the wall'])                # the null placeholder dropped
        self.assertEqual(wall['unique_id'], 'u-light.wall_light')
        ring = self.records['light.mira_ring_led_ring']
        self.assertEqual(ring['name'], 'Mira ring LED ring')
        self.assertEqual(self.records['switch.plug_socket_1']['kind'], 'plug')
        self.assertFalse(self.records['switch.plug_socket_1']['available'])
        # a child device without an area follows its parent's
        self.assertEqual(self.all['switch.desk_socket']['area_id'], 'living_room')
        self.assertEqual(self.all['switch.desk_socket']['manufacturer'], 'Tuya')

    def test_renamed_entity(self):
        states, registry = home()
        entry = next(e for e in registry['entities'] if e['entity_id'] == 'light.wall_light')
        entry.update(name='Lumen', area_id='office')
        next(s for s in states if s['entity_id'] == 'light.wall_light')['attributes']['friendly_name'] = 'Lumen'
        wall = next(r for r in homehub.build_inventory(states, registry) if r['entity_id'] == 'light.wall_light')
        self.assertEqual((wall['name'], wall['default_name'], wall['renamed'], wall['registry_name']),
                         ('Lumen', 'Wall Light', True, 'Lumen'))
        self.assertEqual((wall['area'], wall['entity_area_id']), ('Office', 'office'))

    def test_groups_and_kinds(self):
        room = self.records['light.room_room']
        self.assertTrue(room['is_group'])
        self.assertEqual(room['members'], ['light.room_desk', 'light.room_shelf'])
        self.assertFalse(self.records['light.room_desk']['is_group'])
        kinds = {i: r['kind'] for i, r in self.records.items()}
        self.assertEqual(kinds['media_player.living_tv_2'], 'tv')
        self.assertEqual(kinds['media_player.living_tv'], 'tv')               # cast: no class, a TV's name
        self.assertEqual(kinds['media_player.mira_speaker'], 'speaker')
        self.assertEqual(kinds['remote.living_tv'], 'remote')
        self.assertEqual(kinds['sensor.plug_power'], 'sensor')
        self.assertEqual(kinds['scene.room_relax'], 'scene')
        self.assertEqual(homehub.kind_of('media_player.kitchen', {}, 'Kitchen speaker Nest Mini'), 'speaker')

    def test_summaries_name_the_right_things(self):
        for record in self.all.values():
            self.assertTrue(record['summary_ar'].strip() and record['summary_en'].strip(), record['entity_id'])
        desk = self.records['light.room_desk']
        for word in ('ضوء ملوّن', 'سطوع', 'حرارة بيضاء 2000–6535K', 'تأثيرات: شمعة، نار'):
            self.assertIn(word, desk['summary_ar'])
        for word in ('colour light', 'brightness', '2000–6535K', 'effects: candle, fire'):
            self.assertIn(word, desk['summary_en'])
        self.assertIn('مجموعة أضواء (2)', self.records['light.room_room']['summary_ar'])
        wall = self.records['light.wall_light']
        self.assertIn('أبيض صافٍ', wall['summary_ar'])
        self.assertNotIn('حرارة', wall['summary_ar'])
        tv = self.records['media_player.living_tv_2']
        self.assertIn('تلفزيون', tv['summary_ar'])
        self.assertIn('رفع الصوت وخفضه', tv['summary_ar'])                  # steps only, no level
        self.assertNotIn('مستوى الصوت', tv['summary_ar'])
        self.assertIn('next/previous', tv['summary_en'])
        speaker = self.records['media_player.mira_speaker']
        self.assertIn('مستوى الصوت', speaker['summary_ar'])
        self.assertNotIn('تشغيل وإطفاء', speaker['summary_ar'])
        self.assertIn('announcements', speaker['summary_en'])
        self.assertIn('مقبس ذكي', self.records['switch.plug_socket_1']['summary_ar'])
        self.assertIn('حسّاس استطاعة', self.records['sensor.plug_power']['summary_ar'])
        self.assertIn('(W)', self.records['sensor.plug_power']['summary_en'])
        self.assertIn('ريموت', self.records['remote.living_tv']['summary_ar'])
        self.assertIn('تفعيل', self.records['scene.room_relax']['summary_ar'])

    def test_order(self):
        order = [r['entity_id'] for r in homehub.build_inventory(*home())]
        self.assertLess(order.index('light.room_desk'), order.index('scene.room_relax'))
        self.assertEqual(order[-1], 'media_player.living_tv')                 # no area: last


# ── writes: the payloads Home Assistant receives ─────────────────────

class Writes(_WithFake):
    def updates(self):
        return [c for c in self.fake.commands if c['type'].endswith('/update') or c['type'].endswith('/create')]

    def test_rename_and_restore(self):
        out = self.hub.rename('light.wall_light', '  Lumen   test ')
        self.assertEqual(self.updates(), [{'type': 'config/entity_registry/update', 'entity_id': 'light.wall_light',
                                           'name': 'Lumen test', 'id': 1}])
        self.assertEqual((out['name'], out['registry_name']), ('Lumen test', 'Lumen test'))
        self.fake.commands.clear()
        out = self.hub.rename('light.wall_light', '')
        self.assertIsNone(self.updates()[0]['name'])
        self.assertEqual((out['name'], out['registry_name']), ('Wall Light', None))
        with self.assertRaises(HubError):
            self.hub.rename('light.wall_light', 'x' * 101)
        with self.assertRaises(HubError):
            self.hub.rename('not an id', 'x')

    def test_rename_device(self):
        out = self.hub.rename_device('d_wall', 'Salon wall')
        self.assertEqual(self.updates()[0], {'type': 'config/device_registry/update', 'device_id': 'd_wall',
                                             'name_by_user': 'Salon wall', 'id': 1})
        self.assertEqual((out['name'], out['default_name']), ('Salon wall', 'Wall Light'))
        self.assertIsNone(self.hub.rename_device('d_wall', None)['name_by_user'])

    def test_set_area_new_existing_and_clear(self):
        out = self.hub.set_area('light.wall_light', 'Lumen test area')
        self.assertEqual(self.updates(), [
            {'type': 'config/area_registry/create', 'name': 'Lumen test area', 'id': 2},
            {'type': 'config/entity_registry/update', 'entity_id': 'light.wall_light', 'area_id': 'lumen_test_area', 'id': 3}])
        self.assertEqual((out['area'], out['area_id'], out['created']['area_id']), ('Lumen test area', 'lumen_test_area', 'lumen_test_area'))
        self.fake.commands.clear()
        out = self.hub.set_area('light.wall_light', 'office')                 # an id
        self.assertEqual(self.updates()[-1]['area_id'], 'office')
        self.assertIsNone(out['created'])
        self.fake.commands.clear()
        self.hub.set_area('light.wall_light', 'OFFICE')                        # a name, any case
        self.hub.set_area('light.wall_light', 'Salon')                         # an area alias
        self.assertEqual([c['area_id'] for c in self.updates()], ['office', 'living_room'])
        self.fake.commands.clear()
        out = self.hub.set_area('light.wall_light', None)
        self.assertEqual(self.updates(), [{'type': 'config/entity_registry/update', 'entity_id': 'light.wall_light',
                                           'area_id': None, 'id': 1}])
        self.assertEqual((out['area_id'], out['area'], out['effective_area_id']), (None, 'البيت', 'living_room'))

    def test_areas_and_create(self):
        self.assertEqual([a['name'] for a in self.hub.areas()], ['البيت', 'Office'])
        self.assertEqual(self.hub.create_area(' Hall ')['name'], 'Hall')
        with self.assertRaises(HubError) as cm:
            self.hub.create_area('office')
        self.assertIn('already in use', str(cm.exception))
        with self.assertRaises(HubError):
            self.hub.create_area('  ')

    def test_aliases_keep_the_computed_name(self):
        self.assertEqual(self.hub.aliases('light.wall_light'), ['lamp on the wall'])
        self.assertEqual(self.hub.set_aliases('light.wall_light', ['ضو الحيط', ' ضو  الحيط ', 'wall', '']),
                         ['ضو الحيط', 'wall'])
        self.assertEqual(self.updates()[-1]['aliases'], [None, 'ضو الحيط', 'wall'])
        self.assertEqual(self.hub.set_aliases('light.room_desk', ['desk']), ['desk'])
        self.assertEqual(self.updates()[-1]['aliases'], ['desk'])

    def test_discovered(self):
        self.fake.flows = [
            {'flow_id': 'f1', 'handler': 'hue', 'step_id': 'link',
             'context': {'source': 'zeroconf', 'title_placeholders': {'name': 'Hue Bridge 2'}}},
            {'flow_id': 'f2', 'handler': 'cast', 'step_id': 'confirm', 'context': {'source': 'zeroconf'}}]
        self.assertEqual(self.hub.discovered(), [
            {'flow_id': 'f1', 'domain': 'hue', 'title': 'Hue Bridge 2', 'source': 'zeroconf', 'step_id': 'link'},
            {'flow_id': 'f2', 'domain': 'cast', 'title': 'cast', 'source': 'zeroconf', 'step_id': 'confirm'}])

    def test_inventory_through_the_wire(self):
        records = self.hub.inventory()
        self.assertEqual(len(records), 11)
        self.assertEqual(next(r for r in records if r['entity_id'] == 'light.wall_light')['aliases'], ['lamp on the wall'])
        types = [c['type'] for c in self.fake.commands]
        self.assertEqual(types, ['config/area_registry/list', 'config/device_registry/list',
                                 'config/entity_registry/list', 'config/entity_registry/get_entries'])


# ── the owner's link file ────────────────────────────────────────────

class Link(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / 'mo-dot' / 'home.json'

    def tearDown(self):
        self.dir.cleanup()

    def test_save_load_keep_the_other_key(self):
        self.assertIsNone(homehub.load(self.path))
        homehub.save(TOKEN, path=self.path)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        hub = homehub.load(self.path)
        self.assertEqual(hub.url, 'http://127.0.0.1:8123')
        homehub.save(None, 'https://ha.example:8443/', path=self.path)
        self.assertEqual(json.loads(self.path.read_text()), {'token': TOKEN, 'url': 'https://ha.example:8443'})
        homehub.save(TOKEN[::-1], path=self.path)
        self.assertEqual(json.loads(self.path.read_text())['url'], 'https://ha.example:8443')
        homehub.save(None, '', path=self.path)
        self.assertNotIn('url', json.loads(self.path.read_text()))
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(os.listdir(self.path.parent), ['home.json'])         # no temp file left

    def test_validation(self):
        for token in ('short', 'x' * 30 + ' ' + 'y' * 30, None, 'ü' * 50):
            with self.subTest(token=token), self.assertRaises(HubError):
                homehub.save(token, path=self.path)
        for url in ('ftp://h', 'http://', 'http://u:p@h', 'http://h/path', 'http://h?q=1', 'http://h:99999'):
            with self.subTest(url=url), self.assertRaises(HubError):
                homehub.save(TOKEN, url, path=self.path)
        self.assertFalse(self.path.exists())
        self.path.parent.mkdir(parents=True)
        self.path.write_text('{broken')
        self.assertIsNone(homehub.load(self.path))
        self.path.write_text(json.dumps({'url': 'http://h:1'}))
        self.assertIsNone(homehub.load(self.path))


# ── the real Home Assistant, read-only, only when asked ─────────────

@unittest.skipUnless(os.environ.get('MIRA_LIVE_HA') == '1', 'set MIRA_LIVE_HA=1 to read the real Home Assistant')
class Live(unittest.TestCase):
    def test_read_only(self):
        hub = homehub.load()
        self.assertIsNotNone(hub, 'Home Assistant is not linked')
        self.assertTrue(homehub.probe(hub.url)['reachable'])
        registry = hub.registry()
        self.assertTrue(registry['entities'] and registry['devices'])
        records = hub.inventory()
        self.assertTrue(records)
        for record in records:
            self.assertTrue(record['summary_ar'] and record['summary_en'], record['entity_id'])
            self.assertFalse(record['hidden'])
        self.assertIsInstance(hub.discovered(), list)


if __name__ == '__main__':
    unittest.main()
