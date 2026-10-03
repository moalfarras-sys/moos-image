"""Lumen's Hue bridge and its DTLS transport.

Everything here runs against fakes or local servers, except two opt-in groups:

* `DtlsRoundTrip` starts a real DTLS 1.2 PSK server (`openssl s_server`) on 127.0.0.1 and
  streams to it through GnuTLS; it is skipped when the openssl command is missing.
* `LiveBridge` reads the owner's real Hue bridge, and only reads, with the application key Home
  Assistant already holds. It runs only with LUMEN_LIVE_HUE=1. No key is ever printed.
"""
import hashlib
import http.server
import json
import math
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from lumen import dtls, hue

CONFIG_ID = 'e9c6c044-cfd7-4a8d-a6ea-1714b6d8df70'
LIGHT_ID = '4c2b5f2e-c488-4dbc-b67d-f4a403e349ef'
APP_KEY = 'fake-app-key-not-a-secret-0123456789abcd'
CLIENT_KEY = '00112233445566778899aabbccddeeff'
GAMUT_C = {'red': {'x': 0.6915, 'y': 0.3083}, 'green': {'x': 0.17, 'y': 0.7},
           'blue': {'x': 0.1532, 'y': 0.0475}}


# ── fakes ─────────────────────────────────────────────────────────────

class FakeBridge:
    """Stands in for the bridge behind hue._Link: routes (method, path) → answers, logs requests."""

    def __init__(self, routes=None):
        self.routes = dict(routes or {})
        self.log = []                   # (method, path, body, headers)

    def link(self, host, timeout, cert_sha256=None, port=443):
        return _FakeLink(self, host, cert_sha256)

    def requests(self, method=None, path=None):
        return [r for r in self.log if (method is None or r[0] == method)
                and (path is None or r[1] == path)]


class _FakeLink:
    def __init__(self, bridge, host, pin):
        self.bridge, self.host, self.pin = bridge, host, pin
        self.seen = 'ab' * 32
        self.timeout = 6.0

    def exchange(self, method, path, body=None, headers=None, retry=True):
        self.bridge.log.append((method, path, body, dict(headers or {})))
        answer = self.bridge.routes.get((method, path))
        if callable(answer):
            answer = answer(body)
        if answer is None:
            return 404, json.dumps({'errors': [{'description': 'resource not found'}],
                                    'data': []}).encode()
        if isinstance(answer, BaseException):
            raise answer
        status, doc = answer
        return status, doc if isinstance(doc, bytes) else json.dumps(doc).encode()

    def close(self):
        pass


class FakeDtls:
    instances = []
    fail_with = None

    def __init__(self, host, port, identity, key, timeout=5.0):
        self.host, self.port, self.identity, self.key = host, port, identity, key
        self.sent, self.closed = [], 0
        FakeDtls.instances.append(self)

    def connect(self):
        if FakeDtls.fail_with:
            raise FakeDtls.fail_with
        return self

    def send(self, data):
        self.sent.append(bytes(data))
        return len(data)

    def close(self):
        self.closed += 1


def light_resource(**extra):
    light = {
        'id': LIGHT_ID, 'type': 'light',
        'owner': {'rid': 'dev-buero', 'rtype': 'device'},
        'metadata': {'name': 'Hue lampe', 'archetype': 'table_wash'},
        'on': {'on': False}, 'dimming': {'brightness': 100.0, 'min_dim_level': 0.2},
        'color_temperature': {'mirek': None, 'mirek_valid': False,
                              'mirek_schema': {'mirek_minimum': 153, 'mirek_maximum': 500}},
        'color': {'xy': {'x': 0.31, 'y': 0.3277}, 'gamut': GAMUT_C, 'gamut_type': 'C'},
        'effects': {'status': 'no_effect',
                    'effect_values': ['no_effect', 'candle', 'fire', 'prism']},
    }
    light.update(extra)
    return light


def snapshot():
    """A small home shaped like the owner's real bridge (names and ids invented)."""
    devices = [
        {'id': 'dev-bridge', 'type': 'device', 'metadata': {'name': 'Hue Bridge'},
         'services': [{'rid': 'ent-proxy', 'rtype': 'entertainment'}]},
        {'id': 'dev-buero', 'type': 'device', 'metadata': {'name': 'Büro'},
         'services': [{'rid': 'zb-buero', 'rtype': 'zigbee_connectivity'},
                      {'rid': LIGHT_ID, 'rtype': 'light'},
                      {'rid': 'ent-buero', 'rtype': 'entertainment'}]},
        {'id': 'dev-tv', 'type': 'device', 'metadata': {'name': 'Tv  Links '},
         'services': [{'rid': 'zb-tv', 'rtype': 'zigbee_connectivity'},
                      {'rid': 'light-tv', 'rtype': 'light'},
                      {'rid': 'ent-tv', 'rtype': 'entertainment'}]},
        {'id': 'dev-white', 'type': 'device', 'metadata': {'name': 'Flur'},
         'services': [{'rid': 'light-white', 'rtype': 'light'}]},
    ]
    lights = [
        light_resource(),
        light_resource(id='light-tv', owner={'rid': 'dev-tv', 'rtype': 'device'},
                       metadata={'name': 'R', 'archetype': 'table_shade'},
                       on={'on': True}, dimming={'brightness': 74.31},
                       color_temperature={'mirek': 250, 'mirek_valid': True,
                                          'mirek_schema': {'mirek_minimum': 153,
                                                           'mirek_maximum': 500}},
                       gradient={'points_capable': 5}),
        {'id': 'light-white', 'type': 'light', 'owner': {'rid': 'dev-white', 'rtype': 'device'},
         'metadata': {'name': 'Extended light', 'archetype': 'classic_bulb'},
         'on': {'on': True}},
    ]
    entertainment = [
        {'id': 'ent-proxy', 'type': 'entertainment', 'renderer': False, 'proxy': True,
         'owner': {'rid': 'dev-bridge', 'rtype': 'device'}},
        {'id': 'ent-buero', 'type': 'entertainment', 'renderer': True,
         'owner': {'rid': 'dev-buero', 'rtype': 'device'},
         'renderer_reference': {'rid': LIGHT_ID, 'rtype': 'light'}},
        {'id': 'ent-tv', 'type': 'entertainment', 'renderer': True,
         'owner': {'rid': 'dev-tv', 'rtype': 'device'}},
    ]
    zigbee = [
        {'id': 'zb-buero', 'type': 'zigbee_connectivity', 'status': 'connected',
         'owner': {'rid': 'dev-buero', 'rtype': 'device'}},
        {'id': 'zb-tv', 'type': 'zigbee_connectivity', 'status': 'connectivity_issue',
         'owner': {'rid': 'dev-tv', 'rtype': 'device'}},
    ]
    config = {
        'id': CONFIG_ID, 'type': 'entertainment_configuration', 'name': 'old name',
        'metadata': {'name': 'Entertainment area'}, 'status': 'inactive',
        'configuration_type': 'screen',
        'channels': [
            {'channel_id': 0, 'position': {'x': -0.5, 'y': 0.25, 'z': 0.0},
             'members': [{'service': {'rid': 'ent-tv', 'rtype': 'entertainment'}, 'index': 0}]},
            {'channel_id': 1, 'position': {'x': 0.75, 'y': -1.0, 'z': 0.5},
             'members': [{'service': {'rid': 'ent-buero', 'rtype': 'entertainment'}, 'index': 0},
                         {'service': {'rid': 'ent-tv', 'rtype': 'entertainment'}, 'index': 0}]},
            {'channel_id': 2, 'position': {'x': 1.0, 'y': 1.0, 'z': -1.0},
             'members': [{'service': {'rid': 'ent-gone', 'rtype': 'entertainment'}, 'index': 0}]},
        ],
    }
    return {'errors': [], 'data': devices + lights + entertainment + zigbee + [config]}


def inside_or_on(p, gamut, slack=1e-9):
    r, g, b = gamut['red'], gamut['green'], gamut['blue']
    d = [hue._cross(r, g, p), hue._cross(g, b, p), hue._cross(b, r, p)]
    return all(x >= -slack for x in d) or all(x <= slack for x in d)


def xy_gamut(gamut_doc):
    return {k: [v['x'], v['y']] for k, v in gamut_doc.items()}


# ── the stream packet ─────────────────────────────────────────────────

class PacketTest(unittest.TestCase):
    def test_exact_bytes(self):
        packet = hue.stream_packet(CONFIG_ID, 263, {1: (255, 0, 0), 0: (0, 51, 255),
                                                    2: (0.5, 100.2, 254.9)})
        expected = (b'HueStream' + bytes([2, 0, 7, 0, 0, 0, 0]) + CONFIG_ID.encode('ascii')
                    + bytes.fromhex('00' '0000' '3333' 'ffff')      # channel 0: 0, 51, 255
                    + bytes.fromhex('01' 'ffff' '0000' '0000')      # channel 1: 255, 0, 0
                    + bytes.fromhex('02' '0080' '6497' 'ffe5'))     # big-endian, rounded
        self.assertEqual(packet, expected)
        self.assertEqual(len(packet), 16 + 36 + 3 * 7)

    def test_values_are_clamped_and_channels_capped(self):
        packet = hue.stream_packet(CONFIG_ID, 0, {5: (-5, 300, math.nan)})
        self.assertEqual(packet[-7:], bytes.fromhex('05' '0000' 'ffff' '0000'))
        many = hue.stream_packet(CONFIG_ID, 0, {ch: (1, 2, 3) for ch in range(25)})
        self.assertEqual(len(many), 52 + 20 * 7)
        self.assertEqual([many[52 + 7 * i] for i in range(20)], list(range(20)))

    def test_bad_ids_are_refused(self):
        with self.assertRaises(hue.HueError):
            hue.stream_packet('short', 0, {0: (0, 0, 0)})
        with self.assertRaises(hue.HueError):
            hue.stream_packet(CONFIG_ID, 0, {300: (0, 0, 0)})


# ── colour ────────────────────────────────────────────────────────────

class ColourTest(unittest.TestCase):
    def test_primaries_are_the_srgb_primaries(self):
        for rgb, xy in (((255, 0, 0), (0.64, 0.33)), ((0, 255, 0), (0.30, 0.60)),
                        ((0, 0, 255), (0.15, 0.06)), ((255, 255, 255), (0.3127, 0.3290))):
            x, y = hue.rgb_to_xy(*rgb)
            self.assertAlmostEqual(x, xy[0], places=3, msg=rgb)
            self.assertAlmostEqual(y, xy[1], places=3, msg=rgb)

    def test_gamut_corners_stay_and_primaries_land_inside(self):
        for name, gamut in hue.GAMUTS.items():
            for corner in gamut.values():
                self.assertEqual(hue.clamp_to_gamut(*corner, gamut), tuple(corner), name)
            for rgb in ((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 180, 20)):
                self.assertTrue(inside_or_on(hue.rgb_to_xy(*rgb, gamut), gamut), (name, rgb))

    def test_outside_colour_moves_to_the_nearest_edge_point(self):
        gamut = hue.GAMUTS['B']
        green = hue.rgb_to_xy(0, 255, 0)                 # (0.30, 0.60): outside gamut B
        self.assertFalse(inside_or_on(green, gamut))
        x, y = hue.rgb_to_xy(0, 255, 0, gamut)
        # brute force: no point on the triangle's edges is nearer
        best = min((math.dist(green, (a[0] + t / 2000 * (b[0] - a[0]),
                                      a[1] + t / 2000 * (b[1] - a[1]))), t)
                   for a, b in ((gamut['red'], gamut['green']), (gamut['green'], gamut['blue']),
                                (gamut['blue'], gamut['red'])) for t in range(2001))
        self.assertAlmostEqual(math.dist(green, (x, y)), best[0], places=4)
        self.assertTrue(inside_or_on((x, y), gamut, slack=1e-9))

    def test_inside_stays_and_black_is_white_point(self):
        self.assertEqual(hue.clamp_to_gamut(0.4, 0.35, hue.GAMUTS['C']), (0.4, 0.35))
        self.assertEqual(hue.rgb_to_xy(0, 0, 0), hue.D65)
        self.assertEqual(hue.clamp_to_gamut(0.9, 0.9, None), (0.9, 0.9))

    def test_kelvin_to_mirek_clamps_to_the_lamp(self):
        self.assertEqual(hue.kelvin_to_mirek(2700, [153, 500]), 370)
        self.assertEqual(hue.kelvin_to_mirek(6500, [153, 500]), 154)
        self.assertEqual(hue.kelvin_to_mirek(10000, [153, 500]), 153)
        self.assertEqual(hue.kelvin_to_mirek(1000, [153, 500]), 500)
        self.assertEqual(hue.kelvin_to_mirek(7042, [142, 500]), 142)
        self.assertEqual(hue.kelvin_to_mirek(2000), 500)
        for bad in (0, -1, 'warm', math.inf):
            with self.assertRaises(hue.HueError):
                hue.kelvin_to_mirek(bad)


# ── the bridge over fakes ─────────────────────────────────────────────

class BridgeFakeTest(unittest.TestCase):
    def bridge(self, routes, **kw):
        fake = FakeBridge(routes)
        with patch.object(hue, '_Link', fake.link):
            return hue.HueBridge('192.0.2.10', APP_KEY, **kw), fake

    def test_lights_use_device_names_and_capabilities(self):
        bridge, fake = self.bridge({('GET', '/clip/v2/resource'): (200, snapshot())})
        lights = {l['id']: l for l in bridge.lights()}
        self.assertEqual(len(fake.log), 1)
        self.assertEqual(fake.log[0][3]['hue-application-key'], APP_KEY)
        buero = lights[LIGHT_ID]
        self.assertEqual(buero['name'], 'Büro')                # the device's name, not 'Hue lampe'
        self.assertEqual(buero['device_id'], 'dev-buero')
        self.assertEqual((buero['on'], buero['brightness'], buero['xy'], buero['mirek']),
                         (False, 100.0, [0.31, 0.3277], None))
        self.assertEqual(buero['gamut'], xy_gamut(GAMUT_C))
        self.assertEqual((buero['gamut_type'], buero['mirek_range']), ('C', [153, 500]))
        self.assertEqual(buero['effects'], ['candle', 'fire', 'prism'])
        self.assertTrue(buero['entertainment'] and buero['reachable'])
        tv = lights['light-tv']
        self.assertEqual(tv['name'], 'Tv Links')
        self.assertEqual((tv['mirek'], tv['gradient_points'], tv['reachable'], tv['entertainment']),
                         (250, 5, False, True))
        white = lights['light-white']
        self.assertEqual((white['xy'], white['gamut'], white['mirek_range'], white['effects']),
                         (None, None, None, []))
        self.assertEqual((white['brightness'], white['entertainment'], white['reachable']),
                         (100.0, False, True))
        self.assertEqual(list(lights), sorted(lights, key=lambda i: lights[i]['name'].casefold()))

    def test_entertainment_channels_map_to_light_ids_through_devices(self):
        bridge, _ = self.bridge({('GET', '/clip/v2/resource'): (200, snapshot())})
        (config,) = bridge.entertainment_configs()
        self.assertEqual((config['id'], config['name'], config['status'], config['type']),
                         (CONFIG_ID, 'Entertainment area', 'inactive', 'screen'))
        channels = {c['id']: c for c in config['channels']}
        self.assertEqual(channels[0]['lights'], ['light-tv'])
        self.assertEqual(channels[1]['lights'], [LIGHT_ID, 'light-tv'])
        self.assertEqual(channels[2]['lights'], [])           # a removed lamp maps to nothing
        self.assertEqual((channels[1]['x'], channels[1]['y'], channels[1]['z']), (0.75, -1.0, 0.5))

    def test_bridge_id_is_read_once_and_lowercased(self):
        bridge, fake = self.bridge({('GET', '/clip/v2/resource/bridge'):
                                    (200, {'errors': [], 'data': [{'bridge_id': 'ECB5FAFFFE00ABCD'}]})})
        self.assertEqual(bridge.bridge_id(), 'ecb5fafffe00abcd')
        self.assertEqual(bridge.bridge_id(), 'ecb5fafffe00abcd')
        self.assertEqual(len(fake.log), 1)
        known, fake2 = self.bridge({}, bridge_id='ECB5FAFFFE00ABCD')
        self.assertEqual(known.bridge_id(), 'ecb5fafffe00abcd')
        self.assertEqual(fake2.log, [])

    def put_body(self, fake):
        (put,) = fake.requests('PUT')
        self.assertEqual(put[1], f'/clip/v2/resource/light/{LIGHT_ID}')
        self.assertEqual(put[3]['hue-application-key'], APP_KEY)
        return put[2]

    def light_routes(self, light=None):
        ok = (200, {'errors': [], 'data': [{'rid': LIGHT_ID, 'rtype': 'light'}]})
        return {('GET', f'/clip/v2/resource/light/{LIGHT_ID}'):
                (200, {'errors': [], 'data': [light or light_resource()]}),
                ('PUT', f'/clip/v2/resource/light/{LIGHT_ID}'): ok}

    def test_set_light_json(self):
        cases = [
            (dict(on=True, rgb=(255, 0, 0), brightness=50, duration_ms=400),
             {'on': {'on': True}, 'color': {'xy': {'x': 0.6401, 'y': 0.33}},
              'dimming': {'brightness': 50.0}, 'dynamics': {'duration': 400}}),
            (dict(kelvin=2700), {'color_temperature': {'mirek': 370}}),
            (dict(kelvin=10000), {'color_temperature': {'mirek': 153}}),
            (dict(brightness=0), {'on': {'on': False}}),
            (dict(on=True, brightness=0), {'on': {'on': False}}),
            (dict(brightness=140.5), {'dimming': {'brightness': 100.0}}),
            (dict(rgb=(0, 0, 0)), {'on': {'on': False}}),
            (dict(effect='none'), {'effects': {'effect': 'no_effect'}}),
            (dict(effect='off'), {'effects': {'effect': 'no_effect'}}),
            (dict(effect='Candle'), {'effects': {'effect': 'candle'}}),
            (dict(on=False), {'on': {'on': False}}),
        ]
        for kwargs, expected in cases:
            with self.subTest(kwargs=kwargs):
                bridge, fake = self.bridge(self.light_routes())
                reply = bridge.set_light(LIGHT_ID, **kwargs)
                self.assertEqual(self.put_body(fake), expected)
                self.assertEqual(reply['data'][0]['rid'], LIGHT_ID)

    def test_colour_is_clamped_into_the_lamps_gamut(self):
        bridge, fake = self.bridge(self.light_routes())
        bridge.set_light(LIGHT_ID, rgb=(0, 0, 255))
        xy = self.put_body(fake)['color']['xy']
        self.assertTrue(inside_or_on((xy['x'], xy['y']), xy_gamut(GAMUT_C), slack=1e-4))
        self.assertNotEqual((xy['x'], xy['y']), (0.15, 0.06))

    def test_capabilities_are_fetched_once(self):
        bridge, fake = self.bridge(self.light_routes())
        bridge.set_light(LIGHT_ID, rgb=(10, 20, 30))
        bridge.set_light(LIGHT_ID, kelvin=3000)
        bridge.set_light(LIGHT_ID, effect='fire')
        self.assertEqual(len(fake.requests('GET')), 1)
        self.assertEqual(len(fake.requests('PUT')), 3)

    def test_refusals_send_nothing(self):
        white = light_resource(color={}, effects={})
        white.pop('color')
        cases = [
            ('not-a-uuid', dict(on=True), self.light_routes()),
            (LIGHT_ID, dict(rgb=(255, 0, 0), kelvin=3000), self.light_routes()),
            (LIGHT_ID, dict(effect='disco'), self.light_routes()),
            (LIGHT_ID, dict(rgb=(255, 0, 0)), self.light_routes(white)),
            (LIGHT_ID, dict(rgb='red'), self.light_routes()),
            (LIGHT_ID, dict(brightness=math.nan), self.light_routes()),
            (LIGHT_ID, dict(), self.light_routes()),
        ]
        for light_id, kwargs, routes in cases:
            with self.subTest(kwargs=kwargs):
                bridge, fake = self.bridge(routes)
                with self.assertRaises(hue.HueError):
                    bridge.set_light(light_id, **kwargs)
                self.assertEqual(fake.requests('PUT'), [])

    def test_bridge_errors_carry_the_bridges_words(self):
        routes = self.light_routes()
        routes[('PUT', f'/clip/v2/resource/light/{LIGHT_ID}')] = (
            400, {'errors': [{'description': 'invalid value 900 for brightness'}], 'data': []})
        bridge, _ = self.bridge(routes)
        with self.assertRaises(hue.HueError) as caught:
            bridge.set_light(LIGHT_ID, on=True)
        self.assertEqual(str(caught.exception), 'invalid value 900 for brightness')
        self.assertEqual(caught.exception.status, 400)

    def test_a_207_warning_is_returned_not_raised(self):
        routes = self.light_routes()
        warning = {'errors': [{'description': 'device (light) has communication issues, '
                                              'command (.on.on) may not have effect'}],
                   'data': [{'rid': LIGHT_ID, 'rtype': 'light'}]}
        routes[('PUT', f'/clip/v2/resource/light/{LIGHT_ID}')] = (207, warning)
        bridge, _ = self.bridge(routes)
        self.assertEqual(bridge.set_light(LIGHT_ID, on=True), warning)

    def test_unreachable_is_a_hue_error(self):
        bridge, _ = self.bridge({('GET', '/clip/v2/resource'):
                                 hue.BridgeUnreachable('the Hue bridge at 192.0.2.10 did not answer')})
        with self.assertRaises(hue.HueError):
            bridge.lights()

    def test_repr_never_shows_keys(self):
        bridge, _ = self.bridge({}, client_key=CLIENT_KEY)
        self.assertNotIn(APP_KEY, repr(bridge))
        self.assertNotIn(CLIENT_KEY, repr(bridge))
        client = dtls.DtlsPskClient('127.0.0.1', 2100, APP_KEY, bytes.fromhex(CLIENT_KEY))
        self.assertNotIn(APP_KEY, repr(client))
        self.assertNotIn(CLIENT_KEY, repr(client))


class DecodeTest(unittest.TestCase):
    def test_error_mapping(self):
        def err(status, payload):
            with self.assertRaises(hue.HueError) as caught:
                hue._decode(status, payload, '192.0.2.10')
            return caught.exception
        e = err(403, b'<!DOCTYPE HTML><html>hue personal wireless lighting</html>')
        self.assertEqual(e.status, 403)
        self.assertIn('pair again', str(e))
        e = err(302, b'')
        self.assertIn('redirect', str(e))
        e = err(200, b'not json')
        self.assertIn('JSON', str(e))
        e = err(200, json.dumps([{'error': {'type': 101, 'address': '',
                                            'description': 'link button not pressed'}}]).encode())
        self.assertEqual((str(e), e.error_type), ('link button not pressed', 101))
        e = err(503, b'busy')
        self.assertIn('busy', str(e))
        e = err(404, json.dumps({'errors': [{'description': 'resource not found'}],
                                 'data': []}).encode())
        self.assertEqual(str(e), 'resource not found')
        ok = hue._decode(200, b'{"errors": [], "data": [1]}', 'h')
        self.assertEqual(ok['data'], [1])


# ── the HTTPS link against a real local TLS server ────────────────────

class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'           # keep-alive, as the bridge does

    def log_message(self, *args):
        pass

    def _answer(self):
        self.server.hits.append((self.command, self.path, self.client_address[1]))
        if self.path == '/moved':
            self.send_response(302)
            self.send_header('Location', f'https://127.0.0.1:{self.server.other_port}/x')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        length = int(self.headers.get('Content-Length') or 0)
        body = json.loads(self.rfile.read(length)) if length else None
        data = json.dumps({'errors': [], 'data': [{'echo': body, 'path': self.path}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_PUT = do_POST = _answer


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass                    # a client hanging up on a kept-alive connection is not news


@unittest.skipUnless(shutil.which('openssl'), 'the openssl command makes the test certificate')
class LinkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cert, key = Path(cls.tmp.name, 'c.pem'), Path(cls.tmp.name, 'k.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'ec', '-pkeyopt',
                        'ec_paramgen_curve:prime256v1', '-nodes', '-keyout', str(key), '-out',
                        str(cert), '-days', '1', '-subj', '/O=Philips Hue/CN=ecb5fafffe00abcd'],
                       check=True, capture_output=True)
        der = ssl.PEM_cert_to_DER_cert(cert.read_text())
        cls.fingerprint = hashlib.sha256(der).hexdigest()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        cls.servers = []
        for _ in range(2):
            server = _QuietServer(('127.0.0.1', 0), _Handler)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            server.hits = []
            threading.Thread(target=server.serve_forever, daemon=True).start()
            cls.servers.append(server)
        cls.main, cls.other = cls.servers
        cls.main.other_port = cls.other.server_address[1]
        cls.port = cls.main.server_address[1]

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.shutdown()
            server.server_close()
        cls.tmp.cleanup()

    def setUp(self):
        for server in self.servers:
            server.hits.clear()

    def test_self_signed_bridge_is_accepted_and_fingerprinted(self):
        link = hue._Link('127.0.0.1', 3.0, port=self.port)
        status, payload = link.exchange('PUT', '/clip/v2/resource/light/x', {'on': {'on': True}},
                                        {'hue-application-key': APP_KEY})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(payload)['data'][0]['echo'], {'on': {'on': True}})
        self.assertEqual(link.seen, self.fingerprint)
        status, _ = link.exchange('GET', '/again')
        self.assertEqual(status, 200)
        link.close()
        self.assertEqual([h[:2] for h in self.main.hits],
                         [('PUT', '/clip/v2/resource/light/x'), ('GET', '/again')])
        self.assertEqual(self.main.hits[0][2], self.main.hits[1][2])   # one kept-alive connection

    def test_redirect_is_not_followed(self):
        link = hue._Link('127.0.0.1', 3.0, port=self.port)
        status, payload = link.exchange('GET', '/moved')
        with self.assertRaises(hue.HueError) as caught:
            hue._decode(status, payload, '127.0.0.1')
        self.assertIn('redirect', str(caught.exception))
        link.close()
        self.assertEqual(self.other.hits, [])

    def test_pinned_certificate_must_match(self):
        good = hue._Link('127.0.0.1', 3.0, cert_sha256=self.fingerprint.upper(), port=self.port)
        self.assertEqual(good.exchange('GET', '/ok')[0], 200)
        good.close()
        self.main.hits.clear()
        bad = hue._Link('127.0.0.1', 3.0, cert_sha256='00' * 32, port=self.port)
        with self.assertRaises(hue.HueError) as caught:
            bad.exchange('GET', '/secret', headers={'hue-application-key': APP_KEY})
        self.assertNotIsInstance(caught.exception, hue.BridgeUnreachable)
        self.assertIn('not the bridge', str(caught.exception))
        self.assertEqual(self.main.hits, [])                  # the key was never sent

    def test_nothing_listening_is_unreachable(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        link = hue._Link('127.0.0.1', 2.0, port=port)
        with self.assertRaises(hue.BridgeUnreachable) as caught:
            link.exchange('GET', '/')
        self.assertIn('connection refused', str(caught.exception))

    def test_a_silent_peer_times_out(self):
        with socket.socket() as silent:
            silent.bind(('127.0.0.1', 0))
            silent.listen()
            link = hue._Link('127.0.0.1', 0.5, port=silent.getsockname()[1])
            started = time.monotonic()
            with self.assertRaises(hue.BridgeUnreachable) as caught:
                link.exchange('GET', '/')
            self.assertLess(time.monotonic() - started, 3.0)
            self.assertIn('timed out', str(caught.exception))


# ── pairing ───────────────────────────────────────────────────────────

class PairTest(unittest.TestCase):
    WAIT = (200, [{'error': {'type': 101, 'address': '', 'description': 'link button not pressed'}}])
    DONE = (200, [{'success': {'username': APP_KEY, 'clientkey': CLIENT_KEY.upper()}}])
    BRIDGE = (200, {'errors': [], 'data': [{'bridge_id': 'ecb5fafffe00abcd'}]})

    def run_pair(self, answers, **kw):
        queue = list(answers)
        fake = FakeBridge({('POST', '/api'): lambda body: queue.pop(0) if len(queue) > 1 else queue[0],
                           ('GET', '/clip/v2/resource/bridge'): self.BRIDGE})
        with patch.object(hue, '_Link', fake.link):
            return hue.pair('192.0.2.10', **kw), fake

    def test_waits_for_the_button_then_returns_keys(self):
        creds, fake = self.run_pair([self.WAIT, self.WAIT, self.DONE], poll=0.01)
        self.assertEqual(creds, {'app_key': APP_KEY, 'client_key': CLIENT_KEY.upper(),
                                 'bridge_id': 'ecb5fafffe00abcd', 'host': '192.0.2.10',
                                 'cert_sha256': 'ab' * 32})
        posts = fake.requests('POST', '/api')
        self.assertEqual(len(posts), 3)
        self.assertEqual(posts[0][2], {'devicetype': 'moos#lumen', 'generateclientkey': True})
        self.assertNotIn('hue-application-key', posts[0][3])

    def test_timeout_raises_link_button_not_pressed(self):
        started = time.monotonic()
        with self.assertRaises(hue.LinkButtonNotPressed) as caught:
            self.run_pair([self.WAIT], timeout=0.2, poll=0.02)
        self.assertFalse(caught.exception.cancelled)
        self.assertEqual(caught.exception.error_type, 101)
        self.assertLess(time.monotonic() - started, 1.5)

    def test_cancel_stops_waiting(self):
        cancel = threading.Event()
        threading.Timer(0.1, cancel.set).start()
        started = time.monotonic()
        with self.assertRaises(hue.LinkButtonNotPressed) as caught:
            self.run_pair([self.WAIT], timeout=30, poll=0.5, cancel=cancel)
        self.assertTrue(caught.exception.cancelled)
        self.assertLess(time.monotonic() - started, 2.0)

    def test_a_bridge_that_never_answers_is_unreachable(self):
        with self.assertRaises(hue.BridgeUnreachable):
            self.run_pair([hue.BridgeUnreachable('the Hue bridge at 192.0.2.10 did not answer')],
                          timeout=0.1, poll=0.02)

    def test_other_refusals_and_old_firmware(self):
        refused = (200, [{'error': {'type': 7, 'address': '/devicetype',
                                    'description': 'invalid value, moos#lumen, for parameter, devicetype'}}])
        with self.assertRaises(hue.HueError) as caught:
            self.run_pair([refused], poll=0.01)
        self.assertNotIsInstance(caught.exception, hue.LinkButtonNotPressed)
        self.assertEqual(caught.exception.error_type, 7)
        with self.assertRaises(hue.HueError):
            self.run_pair([(200, [{'success': {'username': APP_KEY}}])], poll=0.01)
        with self.assertRaises(hue.HueError):
            self.run_pair([self.DONE], devicetype='no hash sign here')


# ── discovery ─────────────────────────────────────────────────────────

SSDP_HUE = (b'HTTP/1.1 200 OK\r\nHOST: 239.255.255.250:1900\r\nEXT:\r\nCACHE-CONTROL: max-age=100\r\n'
            b'LOCATION: http://192.168.9.99:80/description.xml\r\n'
            b'SERVER: Hue/1.0 UPnP/1.0 IpBridge/1.78.0\r\nhue-bridgeid: ECB5FAFFFE00ABCD\r\n'
            b'ST: upnp:rootdevice\r\nUSN: uuid:2f402f80-da50-11e1-9b23-ecb5fa00abcd::upnp:rootdevice\r\n\r\n')
SSDP_ROUTER = (b'HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\nLOCATION: http://192.168.1.1:5000/rootDesc.xml\r\n'
               b'SERVER: OpenWRT/OpenWrt UPnP/1.1 MiniUPnPd/2.3.3\r\nST: upnp:rootdevice\r\n\r\n')


class DiscoveryTest(unittest.TestCase):
    def test_ssdp_answers(self):
        self.assertEqual(hue._parse_ssdp(SSDP_HUE, '192.168.1.20'),
                         {'host': '192.168.1.20', 'bridge_id': 'ecb5fafffe00abcd', 'name': ''})
        self.assertIsNone(hue._parse_ssdp(SSDP_ROUTER, '192.168.1.1'))
        self.assertIsNone(hue._parse_ssdp(b'NOTIFY * HTTP/1.1\r\nhue-bridgeid: X\r\n\r\n', '1.2.3.4'))
        old = SSDP_HUE.replace(b'hue-bridgeid: ECB5FAFFFE00ABCD\r\n', b'')
        self.assertEqual(hue._parse_ssdp(old, '192.168.1.21')['bridge_id'], '')

    def test_mdns_record(self):
        item = hue._from_mdns('Hue Bridge - 00ABCD._hue._tcp.local.', ['fe80::1', '192.168.1.20'],
                              {b'bridgeid': b'ecb5fafffe00abcd', b'modelid': b'BSB002', b'x': None})
        self.assertEqual(item, {'host': '192.168.1.20', 'bridge_id': 'ecb5fafffe00abcd',
                                'name': 'Hue Bridge - 00ABCD'})
        self.assertIsNone(hue._from_mdns('x._hue._tcp.local.', [], {}))
        self.assertIsNone(hue._from_mdns('x._hue._tcp.local.', ['fe80::1'], {}))
        self.assertEqual(hue._from_mdns('y._hue._tcp.local.', ['10.0.0.5'], {b'bridgeid': b'junk'})
                         ['bridge_id'], '')

    def test_avahi_lines(self):
        output = ('+;wlp5s0;IPv4;Hue\\032Bridge\\032-\\03200ABCD;_hue._tcp;local\n'
                  '=;wlp5s0;IPv6;Hue\\032Bridge\\032-\\03200ABCD;_hue._tcp;local;ecb5fa00abcd.local;'
                  'fe80::1;443;"modelid=BSB002" "bridgeid=ecb5fafffe00abcd"\n'
                  '=;wlp5s0;IPv4;Hue\\032Bridge\\032-\\03200ABCD;_hue._tcp;local;ecb5fa00abcd.local;'
                  '192.168.1.20;443;"modelid=BSB002" "bridgeid=ecb5fafffe00abcd"\n'
                  '=;wlp5s0;IPv4;Wohnzimmer\\032\\195\\164;_hue._tcp;local;x.local;192.168.1.21;443;\n'
                  '=;wlp5s0;IPv4;Printer;_ipp._tcp;local;p.local;192.168.1.9;631;""\n')
        self.assertEqual(hue._parse_avahi(output), [
            {'host': '192.168.1.20', 'bridge_id': 'ecb5fafffe00abcd', 'name': 'Hue Bridge - 00ABCD'},
            {'host': '192.168.1.21', 'bridge_id': '', 'name': 'Wohnzimmer ä'}])
        with patch.object(hue.subprocess, 'run', side_effect=FileNotFoundError('avahi-browse')):
            self.assertEqual(hue._avahi(0.1), [])

    def test_merge_dedupe_and_cloud_only_on_request(self):
        mdns = [{'host': '192.168.1.20', 'bridge_id': 'ecb5fafffe00abcd', 'name': 'Hue Bridge - 00ABCD'}]
        ssdp = [{'host': '192.168.1.20', 'bridge_id': 'ecb5fafffe00abcd', 'name': ''},
                {'host': '192.168.1.30', 'bridge_id': '', 'name': ''}]
        about = {'name': 'Upstairs', 'bridgeid': 'ECB5FAFFFE00FFFF'}
        with patch.object(hue, '_avahi', return_value=[]), \
                patch.object(hue, '_mdns', return_value=mdns), \
                patch.object(hue, '_ssdp', return_value=ssdp), \
                patch.object(hue, '_config', return_value=about) as config, \
                patch.object(hue, '_cloud') as cloud:
            found = hue.discover(timeout=0.1)
        self.assertEqual(found, [mdns[0], {'host': '192.168.1.30', 'bridge_id': 'ecb5fafffe00ffff',
                                           'name': 'Upstairs'}])
        config.assert_called_once()
        cloud.assert_not_called()
        with patch.object(hue, '_avahi', return_value=[]), \
                patch.object(hue, '_mdns', return_value=[]), patch.object(hue, '_ssdp', return_value=[]), \
                patch.object(hue, '_cloud', return_value=[]) as cloud:
            self.assertEqual(hue.discover(timeout=0.1), [])
            cloud.assert_not_called()
            hue.discover(timeout=0.1, cloud=True)
            cloud.assert_called_once()


# ── the stream over fakes ─────────────────────────────────────────────

class StreamFakeTest(unittest.TestCase):
    def setUp(self):
        FakeDtls.instances, FakeDtls.fail_with = [], None
        config = snapshot()['data'][-1]
        self.fake = FakeBridge({
            ('GET', f'/clip/v2/resource/entertainment_configuration/{CONFIG_ID}'):
                (200, {'errors': [], 'data': [config]}),
            ('PUT', f'/clip/v2/resource/entertainment_configuration/{CONFIG_ID}'):
                (200, {'errors': [], 'data': [{'rid': CONFIG_ID}]}),
        })
        patches = [patch.object(hue, '_Link', self.fake.link),
                   patch.object(hue, 'DtlsPskClient', FakeDtls)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def actions(self):
        return [r[2]['action'] for r in self.fake.requests('PUT')]

    def test_needs_a_client_key(self):
        bridge = hue.HueBridge('192.0.2.10', APP_KEY)
        with self.assertRaises(hue.HueError):
            bridge.start_stream(CONFIG_ID)
        self.assertEqual(self.fake.log, [])

    def test_start_send_close(self):
        bridge = hue.HueBridge('192.0.2.10', APP_KEY, CLIENT_KEY)
        with bridge.start_stream(CONFIG_ID) as stream:
            self.assertEqual(stream.channels, [0, 1, 2])
            self.assertEqual(self.actions(), ['start'])
            (client,) = FakeDtls.instances
            self.assertEqual((client.host, client.port, client.identity, client.key),
                             ('192.0.2.10', 2100, APP_KEY, bytes.fromhex(CLIENT_KEY)))
            stream.send({1: (255, 0, 0), 9: (1, 2, 3)})
            stream.send({7: (1, 2, 3)})                     # nothing the area has: nothing sent
            stream.send({0: (0, 0, 255)})
            self.assertEqual(client.sent[0], hue.stream_packet(CONFIG_ID, 0, {1: (255, 0, 0)}))
            self.assertEqual(client.sent[1], hue.stream_packet(CONFIG_ID, 1, {0: (0, 0, 255)}))
            self.assertEqual(len(client.sent), 2)
        stream.close()
        self.assertEqual(client.closed, 1)
        self.assertEqual(self.actions(), ['start', 'stop'])
        with self.assertRaises(hue.HueError):
            stream.send({0: (1, 1, 1)})

    def test_keepalive_repeats_the_last_frame(self):
        bridge = hue.HueBridge('192.0.2.10', APP_KEY, CLIENT_KEY)
        with patch.object(hue.HueStream, 'KEEPALIVE', 0.1):
            stream = bridge.start_stream(CONFIG_ID)
            stream.send({2: (10, 20, 30)})
            time.sleep(0.45)
            stream.close()
        (client,) = FakeDtls.instances
        self.assertGreaterEqual(len(client.sent), 3)
        for seq, packet in enumerate(client.sent):
            self.assertEqual(packet, hue.stream_packet(CONFIG_ID, seq, {2: (10, 20, 30)}))

    def test_failed_handshake_frees_the_area(self):
        FakeDtls.fail_with = dtls.DtlsError('the DTLS handshake did not finish')
        bridge = hue.HueBridge('192.0.2.10', APP_KEY, CLIENT_KEY)
        with self.assertRaises(hue.HueError) as caught:
            bridge.start_stream(CONFIG_ID)
        self.assertIn('did not accept the light stream', str(caught.exception))
        self.assertEqual(self.actions(), ['start', 'stop'])


# ── DTLS for real, against openssl s_server ───────────────────────────

def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class DtlsServer:
    """openssl s_server in DTLS 1.2 PSK mode; it prints the application data it receives."""

    def __init__(self, identity: str, key: bytes):
        self.port = free_udp_port()
        self.proc = subprocess.Popen(
            ['openssl', 's_server', '-dtls1_2', '-nocert', '-psk', key.hex(), '-psk_identity',
             identity, '-cipher', 'PSK-AES128-GCM-SHA256', '-accept', f'127.0.0.1:{self.port}'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.output = bytearray()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.wait_for(b'ACCEPT', 5.0)

    def _read(self):
        for chunk in iter(lambda: self.proc.stdout.read1(4096), b''):
            self.output += chunk

    def wait_for(self, needle: bytes, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if needle in self.output:
                return True
            time.sleep(0.02)
        return needle in self.output

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc.stdin.close()
        self._reader.join(2)
        self.proc.stdout.close()


@unittest.skipUnless(shutil.which('openssl'), 'needs the openssl command for a DTLS server')
class DtlsRoundTrip(unittest.TestCase):
    KEY = bytes.fromhex('8c1e2bd94f7a6e30c5d2a1b3f40e9d77')
    IDENTITY = 'lumen-test-identity'

    def setUp(self):
        self.server = DtlsServer(self.IDENTITY, self.KEY)
        self.addCleanup(self.server.stop)

    def test_handshake_and_datagrams_reach_the_server(self):
        with dtls.DtlsPskClient('127.0.0.1', self.server.port, self.IDENTITY, self.KEY,
                                timeout=5) as client:
            self.assertEqual(client.cipher, 'DTLS1.2 PSK AES-128-GCM')
            for i in range(3):
                self.assertEqual(client.send(b'lumen-frame-%d\n' % i), 14)
            self.assertTrue(self.server.wait_for(b'lumen-frame-2', 3.0), bytes(self.server.output))
        self.assertIn(b'CIPHER is PSK-AES128-GCM-SHA256', self.server.output)
        for i in range(3):
            self.assertIn(b'lumen-frame-%d\n' % i, self.server.output)
        self.assertFalse(client.connected)
        client.close()                                       # idempotent

    def test_a_hue_stream_packet_arrives_intact(self):
        fake = FakeBridge({('PUT', f'/clip/v2/resource/entertainment_configuration/{CONFIG_ID}'):
                           (200, {'errors': [], 'data': []})})
        client = dtls.DtlsPskClient('127.0.0.1', self.server.port, self.IDENTITY, self.KEY).connect()
        with patch.object(hue, '_Link', fake.link):
            bridge = hue.HueBridge('127.0.0.1', self.IDENTITY, self.KEY.hex())
        stream = hue.HueStream(bridge, CONFIG_ID, [0, 1], client)
        stream.send({0: (255, 128, 0), 1: (0, 0, 255)})
        expected = hue.stream_packet(CONFIG_ID, 0, {0: (255, 128, 0), 1: (0, 0, 255)})
        self.assertTrue(self.server.wait_for(expected, 3.0))
        stream.close()
        self.assertEqual([r[2] for r in fake.requests('PUT')], [{'action': 'stop'}])

    def test_wrong_key_fails_cleanly(self):
        client = dtls.DtlsPskClient('127.0.0.1', self.server.port, self.IDENTITY, b'\x01' * 16,
                                    timeout=1.5)
        with self.assertRaises(dtls.DtlsError) as caught:
            client.connect()
        self.assertFalse(client.connected)
        self.assertNotIn('01' * 16, str(caught.exception))

    def test_nothing_listening(self):
        client = dtls.DtlsPskClient('127.0.0.1', free_udp_port(), self.IDENTITY, self.KEY,
                                    timeout=1.5)
        with self.assertRaises(dtls.DtlsError) as caught:
            client.connect()
        self.assertIn('127.0.0.1', str(caught.exception))
        with self.assertRaises(dtls.DtlsError):
            client.send(b'x')

    def test_arguments_are_checked(self):
        for identity, key in (('', self.KEY), ('é', self.KEY), ('id', b''), ('id', 'text')):
            with self.assertRaises(dtls.DtlsError):
                dtls.DtlsPskClient('127.0.0.1', 1, identity, key)


# ── the owner's bridge, read-only ─────────────────────────────────────

HA_ENTRIES = Path.home() / '.local/share/mira-homeassistant/config/.storage/core.config_entries'


def ha_hue_entry() -> dict:
    entries = json.loads(HA_ENTRIES.read_text(encoding='utf-8'))['data']['entries']
    return next(e['data'] for e in entries if e.get('domain') == 'hue')


@unittest.skipUnless(os.environ.get('LUMEN_LIVE_HUE') == '1',
                     "reads the owner's real Hue bridge; set LUMEN_LIVE_HUE=1 to run")
class LiveBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        entry = ha_hue_entry()
        cls.host = entry['host']
        cls.bridge = hue.HueBridge(entry['host'], entry['api_key'])

    @classmethod
    def tearDownClass(cls):
        cls.bridge.close()

    def test_reads(self):
        bridge_id = self.bridge.bridge_id()
        self.assertRegex(bridge_id, r'^[0-9a-f]{16}$')
        lights = self.bridge.lights()
        self.assertTrue(lights)
        ids = {l['id'] for l in lights}
        for light in lights:
            self.assertRegex(light['id'], hue.UUID.pattern)
            self.assertTrue(light['name'])
            self.assertTrue(0.0 <= light['brightness'] <= 100.0)
        configs = self.bridge.entertainment_configs()
        for config in configs:
            for channel in config['channels']:
                self.assertTrue(set(channel['lights']) <= ids, channel)
                for axis in 'xyz':
                    self.assertTrue(-1.0 <= channel[axis] <= 1.0)
        self.assertEqual(len(self.bridge.cert_sha256 or ''), 64)
        names = {l['id']: l['name'] for l in lights}
        print(f'\n  bridge {bridge_id} at {self.host}: {len(lights)} lights')
        for l in lights:
            print(f"    {l['name']:<10} on={l['on']!s:<5} bri={l['brightness']:<6} xy={l['xy']} "
                  f"mirek={l['mirek']} gamut={l['gamut_type']} ent={l['entertainment']} "
                  f"reachable={l['reachable']} effects={len(l['effects'])}")
        for c in configs:
            print(f"  area {c['name']!r} {c['type']} {c['status']}: " + ', '.join(
                f"ch{ch['id']}=" + '+'.join(names.get(i, i) for i in ch['lights'])
                for ch in c['channels']))

    def test_discovery_finds_it(self):
        found = hue.discover(timeout=3.0)
        print(f'\n  discovered: {found}')
        self.assertIn(self.host, [b['host'] for b in found])

    def test_pairing_without_the_button_waits_and_gives_up(self):
        started = time.monotonic()
        with self.assertRaises(hue.LinkButtonNotPressed) as caught:
            hue.pair(self.host, devicetype='moos#lumentest', timeout=2.5, poll=1.0)
        self.assertFalse(caught.exception.cancelled)
        print(f'\n  pair() without the button: {caught.exception} '
              f'({time.monotonic() - started:.1f} s)')


if __name__ == '__main__':
    unittest.main()
