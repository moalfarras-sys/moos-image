"""Lumen's engine: words → lights, read-back honesty, scenes, the PC's controller bytes, the socket.

Nothing here reaches a real house or a real motherboard: Home Assistant is a fake hub with the
attribute shapes the owner's own bridge reported (Hue lamps in xy with effects, a Tuya hs+white
lamp, Hue room/zone groups, an unavailable lamp, the Echo's ring), and the lighting controller is
a fake file descriptor that records every HID feature report it is sent.
"""
import json
import os
import socket
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from lumen import colors, scenes
from lumen import fusion2
from lumen.engine import Engine, norm
from lumen.pc import PcLights
from lumen.store import Store


def hue_attrs(rgb=None, bri=None, effect='off', mode='xy'):
    attrs = {'supported_color_modes': ['color_temp', 'xy'], 'min_color_temp_kelvin': 2000,
             'max_color_temp_kelvin': 6535, 'supported_features': 44,
             'effect_list': ['off', 'candle', 'fire', 'prism'], 'friendly_name': 'x'}
    if rgb is not None:
        attrs.update(rgb_color=list(rgb), brightness=bri, color_mode=mode, effect=effect)
    return attrs


class FakeHub:
    """A Home Assistant that answers like the owner's, and applies light services to its state."""

    def __init__(self):
        self.calls = []
        self.lag = 0          # polls before a change shows (a slow bridge)
        self.ignore = set()   # lamps that accept a command and never change (a dead bulb)
        self.states_ = {
            'light.buro': {'state': 'off', 'attributes': hue_attrs()},
            'light.zauia': {'state': 'on', 'attributes': hue_attrs((242, 252, 255), 255)},
            'light.links': {'state': 'off', 'attributes': hue_attrs()},
            'light.sa9f': {'state': 'unavailable', 'attributes': hue_attrs()},
            'light.wall': {'state': 'off', 'attributes': {'supported_color_modes': ['hs', 'white'], 'friendly_name': 'Wall'}},
            'light.room': {'state': 'on', 'attributes': dict(hue_attrs((242, 252, 255), 255), is_hue_group=True,
                                                             entity_id=['light.buro', 'light.zauia', 'light.links', 'light.sa9f'])},
            'light.mira_ring_led_ring': {'state': 'off', 'attributes': {'supported_color_modes': ['rgb'], 'effect_list': ['None', 'Pulse']}},
        }
        self.records = [
            {'entity_id': 'light.buro', 'domain': 'light', 'name': 'Büro', 'area': 'Fernseher', 'aliases': ['المكتب'],
             'integration': 'hue', 'unique_id': 'uuid-buro'},
            {'entity_id': 'light.zauia', 'domain': 'light', 'name': 'Zauia', 'area': 'Fernseher', 'aliases': [],
             'integration': 'hue', 'unique_id': 'uuid-zauia'},
            {'entity_id': 'light.links', 'domain': 'light', 'name': 'Links', 'area': 'Fernseher', 'aliases': []},
            {'entity_id': 'light.sa9f', 'domain': 'light', 'name': 'Sa9f', 'area': 'Fernseher', 'aliases': []},
            {'entity_id': 'light.wall', 'domain': 'light', 'name': 'Fancy Wall Light', 'area': 'البيت', 'aliases': []},
            {'entity_id': 'light.room', 'domain': 'light', 'name': 'Fernseher', 'area': 'Fernseher', 'aliases': []},
            {'entity_id': 'light.mira_ring_led_ring', 'domain': 'light', 'name': 'Mira ring', 'area': 'البيت', 'aliases': []},
        ]
        self.renamed = {}
        self._pending = []

    def inventory(self, include_hidden=False):
        return [dict(r) for r in self.records]

    def states(self):
        if self._pending:
            self._pending = [(n - 1, fn) for n, fn in self._pending]
            for n, fn in [p for p in self._pending if p[0] <= 0]:
                fn()
            self._pending = [p for p in self._pending if p[0] > 0]
        return [dict(entity_id=k, **v) for k, v in self.states_.items()]

    def state(self, entity_id):
        return dict(entity_id=entity_id, **self.states_[entity_id])

    def call(self, domain, service, data):
        self.calls.append((domain, service, dict(data)))
        targets = [data['entity_id']]
        group = self.states_[data['entity_id']]['attributes'].get('entity_id')
        if group:
            targets = list(group)

        def apply():
            for eid in targets:
                if eid in self.ignore or self.states_[eid]['state'] == 'unavailable':
                    continue
                st = self.states_[eid]
                if service == 'turn_off':
                    st['state'] = 'off'
                    continue
                st['state'] = 'on'
                a = st['attributes']
                if 'brightness_pct' in data:
                    a['brightness'] = round(data['brightness_pct'] * 255 / 100)
                a.setdefault('brightness', 255)
                if 'rgb_color' in data:
                    a['rgb_color'], a['color_mode'] = list(data['rgb_color']), 'xy'
                if 'color_temp_kelvin' in data:
                    a['color_temp_kelvin'], a['color_mode'] = data['color_temp_kelvin'], 'color_temp'
                    a['rgb_color'] = list(colors.kelvin_to_rgb(data['color_temp_kelvin']))
                if 'effect' in data:
                    a['effect'] = data['effect']
        if self.lag:
            self._pending.append((self.lag, apply))
        else:
            apply()
        return []

    def rename(self, entity_id, name):
        for r in self.records:
            if r['entity_id'] == entity_id:
                r['name'] = name or r['entity_id']
        return {'entity_id': entity_id, 'name': name}

    def set_area(self, entity_id, area):
        for r in self.records:
            if r['entity_id'] == entity_id:
                r['area'] = area
        return {'entity_id': entity_id, 'area': area}


class FakeController:
    def __init__(self):
        self.zones = {z.key: fusion2.Zone(z.key, z.kind, z.index, z.leds) for z in fusion2.DEFAULT_LAYOUT}
        self.effects, self.frames, self.offs = [], [], []
        self._ready = True

    def describe(self):
        return {'path': '/dev/hidraw-fake', 'product': 'IT5701', 'firmware': '3.0.27.0', 'chip': '0x1', 'zones': []}

    def set_effect(self, keys, effect='static', rgb=(255, 255, 255), brightness=255, speed=4):
        self.effects.append((tuple(keys), effect, tuple(rgb), brightness))

    def off(self, keys):
        self.offs.append(tuple(keys))

    def stream(self, frame):
        self.frames.append(frame)


def engine_with(hub=None, controller=None):
    store = Store(Path(tempfile.mkdtemp()))
    hub = hub or FakeHub()
    pc = PcLights(store)
    pc.controller = controller if controller is not None else FakeController()
    engine = Engine(store, hub_loader=lambda: hub, pc=pc)
    engine._take_budget = lambda n=1: None      # no rate pacing inside a test
    return engine, hub, pc


class Colours(unittest.TestCase):
    def test_owner_words(self):
        self.assertEqual(colors.parse('بنفسجي'), {'rgb': colors.NAMED['violet']})
        self.assertEqual(colors.parse('الأحمر'), {'rgb': colors.NAMED['red']})
        self.assertEqual(colors.parse('زهري'), {'rgb': colors.NAMED['pink']})
        self.assertEqual(colors.parse('الأبيض الدافئ'), {'kelvin': 2700})
        self.assertEqual(colors.parse('لون أزرق'), {'rgb': colors.NAMED['blue']})
        self.assertEqual(colors.parse('#FF00aa'), {'rgb': (255, 0, 170)})
        self.assertEqual(colors.parse('2700K'), {'kelvin': 2700})
        self.assertIsNone(colors.parse('banana'))
        self.assertIsNone(colors.parse(''))

    def test_readback_tolerance_is_about_what_a_person_sees(self):
        # Hue reads violet back through its own gamut
        self.assertTrue(colors.close([157, 103, 255], colors.NAMED['violet']))
        self.assertFalse(colors.close([255, 30, 45], colors.NAMED['blue']))
        self.assertTrue(colors.close([242, 252, 255], [255, 255, 255]))

    def test_kelvin_and_palette(self):
        warm, cool = colors.kelvin_to_rgb(2200), colors.kelvin_to_rgb(6500)
        self.assertGreater(warm[0] - warm[2], 150)
        self.assertLess(abs(cool[0] - cool[2]), 20)
        pal = [(255, 0, 0), (0, 0, 255)]
        self.assertEqual(colors.palette_at(pal, 0.0), (255, 0, 0))
        self.assertEqual(colors.palette_at(pal, 0.5), (0, 0, 255))
        self.assertEqual(colors.name_of((140, 60, 255)), 'موف')


class Scenes(unittest.TestCase):
    def test_every_scene_is_complete(self):
        for scene in scenes.SCENES:
            self.assertTrue(scene.name_ar and scene.name_en and scene.mood_ar and scene.mood_en, scene.id)
            self.assertTrue(scene.palette or scene.kelvin, scene.id)
            for stop in scene.palette:
                self.assertIsNotNone(colors.from_hex(stop), (scene.id, stop))
            self.assertIn(scene.pc, ('palette', 'breathe', 'cycle', 'wave', 'off'))

    def test_owner_names(self):
        self.assertEqual(scenes.find('غروب').id, 'sunset')
        self.assertEqual(scenes.find('فيلم').id, 'cinema')
        self.assertEqual(scenes.find('Aurora').id, 'aurora')
        self.assertIsNone(scenes.find('nothing'))

    def test_the_tool_enum_is_the_library(self):
        import tools
        decl = next(d for d in tools.DECLARATIONS if d['name'] == 'light_scene')
        listed = set(decl['parameters']['properties']['scene']['enum']) - {'stop'}
        self.assertEqual(listed, {s.id for s in scenes.SCENES})


class Words(unittest.TestCase):
    def setUp(self):
        self.engine, self.hub, self.pc = engine_with()

    def names(self, target):
        return sorted(l['name'] for l in self.engine.resolve(target)[0])

    def test_all_means_every_lamp_but_the_assistants_ring(self):
        got = self.names('كل الأضواء')
        self.assertNotIn('Mira ring', got)
        self.assertIn('Büro', got)
        self.assertEqual(sum(n.startswith(('إضاءة الكيس', 'شريط')) for n in got), 4)
        self.assertNotIn('Fernseher', got, 'a group is expanded, never controlled twice')

    def test_room_group_alias_and_pc(self):
        self.assertEqual(self.names('Fernseher'), ['Büro', 'Links', 'Sa9f', 'Zauia'])
        self.assertEqual(self.names('المكتب'), ['Büro'])
        self.assertEqual(self.names('بيرو'), [], 'an unknown word picks nothing rather than guessing')
        self.assertEqual(len(self.names('الكيس')), 4)
        self.assertEqual(self.names('Büro و Zauia'), ['Büro', 'Zauia'])
        self.assertEqual(self.names(['ha:light.wall']), ['Fancy Wall Light'])

    def test_norm(self):
        self.assertEqual(norm('الإضاءة'), norm('اضاءه'))
        self.assertEqual(norm('  Büro '), 'büro')


class Control(unittest.TestCase):
    def setUp(self):
        self.engine, self.hub, self.pc = engine_with()

    def test_colour_is_ok_only_when_read_back(self):
        result = self.engine.set('Büro', color='بنفسجي', brightness=60)
        self.assertEqual(result['status'], 'ok')
        call = self.hub.calls[-1]
        self.assertEqual(call[:2], ('light', 'turn_on'))
        self.assertEqual(call[2]['rgb_color'], list(colors.NAMED['violet']))
        self.assertEqual(call[2]['brightness_pct'], 60)

    def test_a_lamp_that_never_changes_is_pending_not_ok(self):
        self.hub.ignore.add('light.buro')
        with mock.patch('lumen.engine.time.sleep'):
            result = self.engine.set('Büro', on=True)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['confirmed'], 0)

    def test_unavailable_lamps_are_named_and_never_counted(self):
        result = self.engine.set('Fernseher', on=True)
        rows = {r['name']: r['status'] for r in result['results']}
        self.assertEqual(rows['Sa9f'], 'unavailable')
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['confirmed'], 3)

    def test_a_whole_hue_room_is_one_call(self):
        self.hub.states_['light.sa9f']['state'] = 'off'      # every member online
        self.engine.refresh(force=True)
        self.hub.calls.clear()
        self.engine.set('Fernseher', on=False)
        self.assertEqual([c[2]['entity_id'] for c in self.hub.calls], ['light.room'])

    def test_white_is_a_temperature_where_the_lamp_has_one(self):
        self.engine.set('Büro', color='أبيض دافئ')
        self.assertEqual(self.hub.calls[-1][2]['color_temp_kelvin'], 2700)
        self.engine.set('Fancy Wall Light', kelvin=2700)
        self.assertIn('rgb_color', self.hub.calls[-1][2], 'an hs lamp gets the colour of the temperature')

    def test_effects_only_where_they_exist(self):
        self.engine.set('Büro', effect='candle')
        self.assertEqual(self.hub.calls[-1][2]['effect'], 'candle')
        self.engine.set('Büro', effect='none')
        self.assertEqual(self.hub.calls[-1][2]['effect'], 'off', "Hue's own word for no effect")
        self.engine.set('Fancy Wall Light', effect='candle', on=True)
        self.assertNotIn('effect', self.hub.calls[-1][2])

    def test_pc_lights_say_the_controller_accepted(self):
        result = self.engine.set('pc', color='#9B7BFF')
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(all(r['verified'] == 'controller' for r in result['results']))
        self.assertEqual(len(self.pc.controller.effects), 4)
        last = self.engine.store.get('pc')['last']
        self.assertEqual(last['D_LED1']['rgb'], [155, 123, 255])

    def test_unknown_words_and_colours_fail_plainly(self):
        self.assertEqual(self.engine.set('nowhere', on=True)['status'], 'error')
        self.assertEqual(self.engine.set('Büro', color='banana')['status'], 'error')


class LivingScenes(unittest.TestCase):
    def test_a_scene_spreads_its_palette_and_lives(self):
        engine, hub, pc = engine_with()
        result = engine.scene('aurora', 'Fernseher')
        self.assertIn(result['status'], ('ok', 'partial'))
        sent = [c[2].get('rgb_color') for c in hub.calls if c[1] == 'turn_on']
        self.assertGreaterEqual(len({tuple(x) for x in sent if x}), 2, 'each lamp its own colour')
        self.assertTrue(engine._living)
        self.assertEqual(engine.snapshot()['scene']['id'], 'aurora')
        engine.set('Büro', on=False)
        self.assertNotIn('ha:light.buro', engine._living, 'a hand on a lamp takes it out of the scene')

    def test_white_scene_and_pc_off(self):
        engine, hub, pc = engine_with()
        engine.scene('focus', 'all')
        temps = {c[2].get('color_temp_kelvin') for c in hub.calls if c[1] == 'turn_on'}
        self.assertIn(5000, temps)
        self.assertEqual(len(pc.controller.offs), 4, 'focus turns the case lights off')
        self.assertFalse(engine._living)

    def test_the_director_streams_the_pc_and_sleeps_when_idle(self):
        engine, hub, pc = engine_with()
        engine._director = threading.Thread(target=engine._direct, daemon=True)
        engine._director.start()
        engine.scene('neon', 'pc')
        time.sleep(0.4)
        self.assertGreater(len(pc.controller.frames), 3)
        engine.stop_living()
        time.sleep(0.15)
        before = len(pc.controller.frames)
        time.sleep(0.4)
        self.assertEqual(len(pc.controller.frames), before, 'nothing living: no frames')
        engine.close()


class FakeBridge:
    def __init__(self):
        self.puts = []
        self.lamps = {'1f0e6b9e-0000-4000-8000-000000000001': {
            'id': '1f0e6b9e-0000-4000-8000-000000000001', 'name': 'Büro', 'on': False, 'brightness': 100.0,
            'xy': [0.31, 0.3277], 'mirek': None, 'mirek_range': [153, 500], 'gamut': {'red': [0.69, 0.3]},
            'effects': ['candle'], 'entertainment': True, 'reachable': True}}

    def lights(self):
        return [dict(v) for v in self.lamps.values()]

    def set_light(self, light_id, **kw):
        self.puts.append((light_id, kw))
        lamp = self.lamps[light_id]
        if kw.get('on') is not None:
            lamp['on'] = kw['on']
        if kw.get('brightness') is not None:
            lamp['brightness'] = kw['brightness']
        if kw.get('rgb') is not None:
            from lumen.hue import rgb_to_xy
            lamp['xy'], lamp['mirek'] = list(rgb_to_xy(*kw['rgb'])), None
        if kw.get('kelvin') is not None:
            lamp['mirek'] = round(1_000_000 / kw['kelvin'])
        return {'data': []}


class DirectHue(unittest.TestCase):
    """A fresh MoOS with a paired Hue bridge and no Home Assistant: the lamps are Lumen's own."""

    def setUp(self):
        store = Store(Path(tempfile.mkdtemp()))
        store.save_hue({'host': '192.0.2.2', 'app_key': 'k' * 40, 'client_key': 'c' * 32})
        self.bridge = FakeBridge()
        pc = PcLights(store)
        pc.controller = None
        self.engine = Engine(store, hub_loader=lambda: None, pc=pc, hue_factory=lambda creds: self.bridge)
        self.engine._take_budget = lambda n=1: None

    def test_lamps_appear_and_answer_with_readback(self):
        lights = self.engine.refresh(force=True)
        self.assertIn('hue:1f0e6b9e-0000-4000-8000-000000000001', lights)
        result = self.engine.set('Büro', color='بنفسجي', brightness=40)
        self.assertEqual(result['status'], 'ok', result)
        lid, kw = self.bridge.puts[-1]
        self.assertEqual((kw['on'], kw['brightness']), (True, 40))
        result = self.engine.set('Büro', color='أبيض دافئ')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(self.bridge.puts[-1][1]['kelvin'], 2700)

    def test_home_assistant_owns_a_bridge_it_already_has(self):
        engine, hub, pc = engine_with()
        engine.store.save_hue({'host': '192.0.2.2', 'app_key': 'k' * 40})
        engine.hue.factory = lambda creds: self.bridge
        lights = engine.refresh(force=True)
        self.assertFalse(any(i.startswith('hue:') for i in lights), 'no lamp listed twice')


class Fusion2Bytes(unittest.TestCase):
    """The reports the motherboard controller receives, byte for byte."""

    def setUp(self):
        self.sent = []
        self.ctl = fusion2.Fusion2(-1, '/dev/hidraw-test')
        self.ctl._send = lambda payload: self.sent.append(bytes(payload))
        self.ctl.identity = fusion2.Identity('IT5701', '3.0.27.0', '0x1', 'IT5701-GIGABYTE',
                                             {'D_LED1': (1, 0, 2), 'D_LED2': (1, 0, 2)})

    def test_start_clears_registers_and_sets_counts(self):
        self.ctl.start()
        self.assertEqual(self.sent[0], bytes((0x20, 0, 0)))
        self.assertEqual(self.sent[8], bytes((0x28, 0xFF, 0x00)))
        self.assertIn(bytes((0x34, 0x00, 0, 0)), self.sent)

    def test_static_effect_packet(self):
        self.ctl._ready = True
        self.ctl.set_effect(['LED_C1'], 'static', (0x11, 0x22, 0x33), 200)
        packet = self.sent[0]
        self.assertEqual(packet[0], 0x21)
        self.assertEqual(struct.unpack_from('<I', packet, 1)[0], 1 << 1)
        self.assertEqual(packet[10], fusion2.STATIC)
        self.assertEqual(packet[11], 200)
        self.assertEqual(packet[13:17], bytes((0x33, 0x22, 0x11, 0)), 'colour is B, G, R, 0')
        self.assertEqual(self.sent[-1][:5], bytes((0x28, 0x02, 0, 0, 0)))

    def test_direct_strip_in_calibrated_order(self):
        self.ctl._ready = True
        self.ctl.zones['D_LED1'].leds = 21
        self.ctl.stream({'D_LED1': [(10, 20, 30)] * 21})
        self.assertEqual(self.sent[0], bytes((0x32, 0x01)), 'built-in effect off for D_LED1 first')
        first, second = self.sent[1], self.sent[2]
        self.assertEqual(first[0], 0x58)
        self.assertEqual(struct.unpack_from('<HB', first, 1), (0, 19 * 3))
        self.assertEqual(first[4:7], bytes((20, 10, 30)), 'GRB')
        self.assertEqual(struct.unpack_from('<HB', second, 1), (19 * 3, 2 * 3))

    def test_finds_only_its_own_usb_ids(self):
        root = Path(tempfile.mkdtemp())
        for name, hid in (('hidraw0', '0003:0000048D:00005702'), ('hidraw1', '0003:000025A7:0000FA67')):
            (root / name / 'device').mkdir(parents=True)
            (root / name / 'device' / 'uevent').write_text(f'HID_ID={hid}\nHID_NAME=x\n')
        self.assertEqual(fusion2.find_devices(str(root)), ['/dev/hidraw0'])


class ScreenOutputs(unittest.TestCase):
    def test_failed_portal_is_stopped_and_keeps_the_real_failure(self):
        from lumen.syncsession import SyncSession
        engine, hub, pc = engine_with()
        session = SyncSession(engine, [])
        session.capture = mock.Mock(state='error', error='screen choice timed out')
        session.capture.stats.return_value = {}
        session.stream = mock.Mock()
        stream = session.stream
        status = session.status()
        self.assertFalse(status['running'])
        self.assertEqual(status['state'], 'error')
        self.assertEqual(status['error'], 'screen choice timed out')
        stream.close.assert_called_once()
        self.assertEqual(session.status()['state'], 'error')
        engine.close()

    def test_choosing_screen_discards_only_the_saved_capture_grant(self):
        engine, hub, pc = engine_with()
        token = engine.store.dir / 'lumen-screencast.token'
        token.write_text('previous-screen')
        with mock.patch('lumen.syncsession.SyncSession') as session:
            session.return_value.status.return_value = {'state': 'asking'}
            engine.sync_start(target='pc')
            self.assertEqual(token.read_text(), 'previous-screen')
            engine.sync_start(target='pc', select_screen=True)
            self.assertFalse(token.exists())
        engine.close()

    def test_hue_channel_region_survives_layout_and_receives_frames(self):
        from lumen.syncsession import SyncSession
        engine, hub, pc = engine_with()
        lamp = engine.resolve('Büro')[0][0]
        session = SyncSession(engine, [lamp])
        session.stream_channels = {lamp['id']: 2}
        session.regions = {lamp['id']: (0, 0, 1, 1)}
        session.stream = mock.Mock()
        session._layout()
        session.analyzer = __import__('lumen.sync', fromlist=['Analyzer']).Analyzer()
        session._frame(bytes((255, 0, 0)) * (64 * 36), 64, 36)
        session.stream.send.assert_called_once_with({2: (255, 0, 0)})
        engine.close()

    def test_screen_colour_cancels_ring_effect_and_black_turns_it_off(self):
        from lumen.syncsession import SyncSession
        for colour in ((255, 0, 0), (0, 0, 0)):
            engine, hub, pc = engine_with()
            lamp = engine.resolve('ha:light.mira_ring_led_ring')[0][0]
            session = SyncSession(engine, [lamp])
            session.latest[lamp['id']] = colour
            received = []
            def receive(light, request, transition=None):
                received.append(request)
                session._stop.set()
            engine.home.call = receive
            session._ha_loop()
            self.assertEqual(len(received), 1)
            if max(colour):
                self.assertEqual(received[0]['effect'], 'none')
                self.assertEqual(received[0]['rgb'], list(colour))
            else:
                self.assertIs(received[0]['on'], False)
            engine.close()

    def test_pc_stream_is_current_but_does_not_replace_saved_choice(self):
        engine, hub, pc = engine_with()
        pc.apply('D_LED1', rgb=[0, 0, 255], brightness=55)
        pc.stream({'D_LED1': [(255, 0, 0)] * 32})
        state = next(l['state'] for l in pc.lights() if l['ref'] == 'D_LED1')
        self.assertEqual(state['rgb'], [255, 0, 0])
        self.assertIsNone(state['effect'])
        self.assertEqual(engine.store.get('pc')['last']['D_LED1']['rgb'], [0, 0, 255])
        self.assertEqual(pc.apply('D_LED1', effect='DNA')['status'], 'error')
        with mock.patch.object(pc.controller, 'stream', side_effect=OSError('USB lost')):
            self.assertFalse(pc.stream({'D_LED1': [(0, 255, 0)]}))
            self.assertEqual(pc.error, 'USB lost')
        engine.close()


class Socket(unittest.TestCase):
    def test_round_trip_and_refusals(self):
        from lumen import client, service
        engine, hub, pc = engine_with()
        runtime = Path(tempfile.mkdtemp())
        path = runtime / 'mira-lumen.sock'
        server = service.Server(str(path), service.Handler)
        server.engine = engine
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with mock.patch.dict(os.environ, {'XDG_RUNTIME_DIR': str(runtime)}):
                self.assertTrue(client.available())
                snap = client.call('snapshot')
                self.assertEqual(snap['status'], 'ok')
                self.assertEqual(snap['counts']['pc'], 4)
                ok = client.call('set', target='Büro', color='أخضر')
                self.assertEqual(ok['status'], 'ok')
                self.assertEqual(client.call('set', target='Büro', brightness=400)['status'], 'error')
                self.assertEqual(client.call('rm -rf')['status'], 'error')
                self.assertEqual(client.call('sync_start', mode='disco')['status'], 'error')
        finally:
            server.shutdown()
            server.server_close()


class Tools(unittest.TestCase):
    def test_lights_tool_reports_partial_honestly(self):
        import asyncio
        import tools
        reply = {'status': 'partial', 'confirmed': 3, 'total': 4,
                 'results': [{'name': 'Sa9f', 'status': 'unavailable'}] + [{'name': 'x', 'status': 'ok'}] * 3}
        ctx = tools.ToolContext(emit=lambda *a: None) if hasattr(tools, 'ToolContext') else None
        with mock.patch('tools._lumen', return_value=reply) as call:
            result = asyncio.run(tools.run_tool('lights', {'target': 'Fernseher', 'action': 'on'}, ctx))
        call.assert_called_once()
        self.assertEqual(result['status'], 'partial')
        self.assertIn('3 من 4', result['summary'])
        self.assertIn('Sa9f', result['summary'])

    def test_home_block_names_rooms_devices_and_pc(self):
        import tools
        records = [{'entity_id': 'light.buro', 'domain': 'light', 'name': 'Büro', 'aliases': ['المكتب'],
                    'area': 'Fernseher', 'available': True, 'state': 'on', 'kind': 'light',
                    'summary_ar': 'ضوء ملوّن · سطوع', 'summary_en': 'colour light'},
                   {'entity_id': 'media_player.tv', 'domain': 'media_player', 'name': 'TV', 'aliases': [],
                    'area': None, 'available': False, 'state': 'unavailable', 'kind': 'tv',
                    'summary_ar': 'تلفزيون', 'summary_en': 'TV'}]
        text = tools.format_home(records, [{'id': 'pc:D_LED1', 'name': 'مراوح الواجهة'}], 'ar')
        for word in ('غرفة «Fernseher»', '«Büro / المكتب»', 'light.buro', 'ضوء ملوّن', 'مضاء', 'غير متاح', 'pc:D_LED1'):
            self.assertIn(word, text)


if __name__ == '__main__':
    unittest.main()
