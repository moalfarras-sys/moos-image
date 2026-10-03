"""The Lumen and Home pages: what the engine and the hub read back is what the page shows, every
control reaches its backend with the owner's pick, and the real QML loads with live-shaped state.

No house, motherboard or Lumen service is touched: the Lumen client and the Home Assistant hub are
stand-ins, and the pages' worker threads run in-line.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
os.environ['MIRA_TEST_MODE'] = '1'
_config = tempfile.TemporaryDirectory(prefix='mira-lumen-page-test-')
os.environ.setdefault('XDG_CONFIG_HOME', _config.name)

from PySide6.QtCore import QObject, QUrl, Signal, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlComponent, QQmlEngine  # noqa: E402

import i18n  # noqa: E402
from pages import home, lumen  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
ROOT = Path(__file__).resolve().parent


class FakeHost(QObject):
    toast = Signal(str, str)
    showSheet = Signal(str)
    prefill = Signal(str)
    langChanged = Signal()

    def __init__(self, lang='ar'):
        super().__init__()
        self.lang = lang
        self.s = i18n.table(lang)
        self.sheets = []
        self.opened = []
        self.showSheet.connect(self.sheets.append)

    def openUrl(self, url):
        self.opened.append(url)


def inline(page):
    def run(tag, fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            result = {'status': 'error', 'error': str(exc)}
        page._deliver(tag, result)
    page.run = run
    return page


SNAPSHOT = {
    'status': 'ok',
    'lights': [
        {'id': 'ha:light.buro', 'ref': 'light.buro', 'name': 'Büro', 'room': 'Fernseher', 'source': 'home', 'kind': 'lamp',
         'online': True, 'group': False, 'members': [], 'integration': 'hue',
         'caps': {'color': True, 'temp': [2000, 6535], 'effects': ['candle', 'fire']},
         'state': {'on': True, 'brightness': 60, 'rgb': [157, 103, 255], 'kelvin': None, 'effect': None}},
        {'id': 'ha:light.sa9f', 'ref': 'light.sa9f', 'name': 'Sa9f', 'room': 'Fernseher', 'source': 'home', 'kind': 'lamp',
         'online': False, 'group': False, 'members': [], 'caps': {'color': True, 'effects': []},
         'state': {'on': None, 'brightness': None, 'rgb': None, 'kelvin': None, 'effect': None}},
        {'id': 'pc:D_LED1', 'ref': 'D_LED1', 'name': 'مراوح الواجهة', 'room': 'PC', 'source': 'pc', 'kind': 'pc',
         'online': True, 'group': False, 'members': [], 'detail': 'ARGB · D_LED1',
         'caps': {'color': True, 'effects': ['breathe'], 'leds': 32},
         'state': {'on': True, 'brightness': 100, 'rgb': None, 'kelvin': 2700, 'effect': None}},
    ],
    'rooms': [{'name': 'Fernseher', 'lights': ['ha:light.buro', 'ha:light.sa9f'], 'on': 1, 'online': 1},
              {'name': 'PC', 'lights': ['pc:D_LED1'], 'on': 1, 'online': 1}],
    'groups': [{'id': 'ha:light.room', 'name': 'Fernseher', 'kind': 'home', 'lights': ['ha:light.buro', 'ha:light.sa9f']}],
    'scenes': [{'id': 'aurora', 'name': 'شفق', 'mood': 'x', 'palette': ['#00F5A0', '#00D9F5'], 'living': True}],
    'scene': None, 'counts': {'lights': 3, 'online': 2, 'on': 2, 'pc': 1},
    'home': {'linked': True}, 'pc': {'present': True, 'maker': 'Gigabyte RGB Fusion 2', 'product': 'IT5701', 'firmware': '3'},
    'hue': {'paired': False, 'streaming': False}, 'sync': {'running': False, 'mode': 'video'},
}


class FakeClient:
    def __init__(self):
        self.calls = []
        self.sync = {'running': False, 'mode': 'video'}

    def request(self, op, timeout=15, **args):
        self.calls.append((op, args))
        if op == 'snapshot':
            return dict(SNAPSHOT, sync=dict(self.sync))
        if op == 'sync_start':
            self.sync = {'running': True, 'state': 'asking', 'mode': args.get('mode'), 'lights': ['pc:D_LED1']}
            return {'status': 'ok', 'sync': dict(self.sync)}
        return {'status': 'partial', 'confirmed': 1, 'total': 2}


class LumenPageState(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        self.client = FakeClient()
        patcher = mock.patch('pages.lumen._client', return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.page = inline(lumen.LumenPage(self.host))

    def test_snapshot_becomes_painted_lights(self):
        self.page.refresh()
        st = self.page.state
        self.assertTrue(st['ready'])
        lights = self.page.lights
        buro = next(l for l in lights if l['id'] == 'ha:light.buro')
        self.assertTrue(buro['on'])
        self.assertEqual(buro['level'], 60)
        self.assertEqual(buro['hex'][0], '#')
        self.assertEqual([e['name'] for e in buro['effect_names']], ['شمعة', 'نار'])
        offline = next(l for l in lights if l['id'] == 'ha:light.sa9f')
        self.assertFalse(offline['on'], 'an unreachable lamp is never painted lit')
        fan = next(l for l in lights if l['id'] == 'pc:D_LED1')
        self.assertNotEqual(fan['hex'], '#5A6282', 'a white temperature is painted as its colour')

    def test_an_unchanged_poll_rebuilds_nothing(self):
        self.page.refresh()
        seen = []
        for name in ('lightsChanged', 'roomsChanged', 'scenesChanged', 'syncChanged', 'changed'):
            getattr(self.page, name).connect(lambda n=name: seen.append(n))
        self.page.refresh()
        self.assertEqual(seen, [], 'the same snapshot again must not rebuild a single delegate')
        SNAPSHOT['lights'][0]['state']['brightness'] = 61
        try:
            self.page.refresh()
        finally:
            SNAPSHOT['lights'][0]['state']['brightness'] = 60
        self.assertEqual(seen, ['lightsChanged'])

    def test_every_control_carries_the_pick(self):
        pick = ['ha:light.buro']
        self.page.setColor(pick, '#FF0000')
        self.page.setWhite(pick, 2700)
        self.page.setBrightness([], 40)
        self.page.setEffect(pick, 'candle')
        self.page.applyScene('aurora', pick)
        self.page.setPower(pick, False)
        ops = [(op, args) for op, args in self.client.calls if op != 'snapshot']
        self.assertEqual(ops[0], ('set', {'target': pick, 'color': '#FF0000'}))
        self.assertEqual(ops[1], ('set', {'target': pick, 'kelvin': 2700}))
        self.assertEqual(ops[2], ('set', {'target': 'all', 'brightness': 40}), 'nothing picked = every light')
        self.assertEqual(ops[3], ('set', {'target': pick, 'effect': 'candle'}))
        self.assertEqual(ops[4], ('scene', {'name': 'aurora', 'target': pick}))
        self.assertEqual(ops[5], ('set', {'target': pick, 'on': False}))
        self.assertEqual(self.page.state['note']['status'], 'pending')
        self.assertIn('1/2', self.page.state['note']['text'])

    def test_choose_screen_asks_the_engine_for_a_fresh_portal_pick(self):
        pick = ['pc:D_LED1']
        self.page.chooseScreen('video', pick)
        self.assertIn(('sync_start', {'mode': 'video', 'target': pick, 'select_screen': True}),
                      self.client.calls)

    def test_sync_start_shows_the_approval_state(self):
        self.page.startSync('game', [])
        self.assertEqual(self.client.calls[0], ('sync_start', {'mode': 'game', 'target': 'all'}))
        self.assertTrue(self.page.sync['running'])
        self.assertEqual(self.page.sync['state'], 'asking')
        self.assertTrue(self.page._sync_timer.isActive(), 'a running sync is polled for its preview')
        self.page.hidden()
        self.assertFalse(self.page._sync_timer.isActive())

    def test_the_engine_down_is_said(self):
        self.client.request = lambda op, **a: {'status': 'error', 'error': 'lumen-not-running'}
        self.page.refresh()
        self.assertEqual(self.page.state['error'], 'lumen-not-running')


class FakeHub:
    def __init__(self):
        self.url = 'http://127.0.0.1:8123'
        self.calls = []
        self.records = [
            {'entity_id': 'light.buro', 'domain': 'light', 'name': 'Büro', 'default_name': 'Büro', 'renamed': False,
             'area': 'Fernseher', 'aliases': ['المكتب'], 'state': 'on', 'available': True, 'is_group': False,
             'members': [], 'kind': 'light', 'caps': {'power': True, 'current': {'brightness': 60}},
             'summary_ar': 'ضوء ملوّن', 'summary_en': 'colour light', 'manufacturer': 'Signify Netherlands B.V.',
             'model': 'Hue color lamp'},
            {'entity_id': 'media_player.tv', 'domain': 'media_player', 'name': 'Smart TV Pro', 'area': None,
             'aliases': [], 'state': 'on', 'available': True, 'is_group': False, 'members': [], 'kind': 'tv',
             'caps': {'power': True, 'volume_step': True, 'current': {'volume': 35}},
             'summary_ar': 'تلفزيون', 'summary_en': 'TV', 'manufacturer': 'TCL', 'model': ''},
            {'entity_id': 'sensor.t', 'domain': 'sensor', 'name': 'Temp', 'area': 'Fernseher', 'aliases': [],
             'state': '21.5', 'available': True, 'is_group': False, 'members': [], 'kind': 'sensor',
             'caps': {'read_only': True, 'value': '21.5', 'unit': '°C'}, 'summary_ar': 'حسّاس', 'summary_en': 'sensor'},
        ]

    def inventory(self, include_hidden=False):
        return self.records

    def areas(self):
        return [{'area_id': 'fernseher', 'name': 'Fernseher'}]

    def discovered(self):
        return [{'domain': 'wled', 'title': 'WLED'}]

    def rename(self, entity_id, name):
        self.calls.append(('rename', entity_id, name))
        return {'entity_id': entity_id, 'name': name}

    def set_area(self, entity_id, area):
        self.calls.append(('area', entity_id, area))
        return {'area': area}

    def set_aliases(self, entity_id, names):
        self.calls.append(('aliases', entity_id, names))
        return names

    def call(self, domain, service, data):
        self.calls.append(('call', domain, service, data))
        return []

    def state(self, entity_id):
        return {'state': 'off'}


class HomePageState(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        self.hub = FakeHub()
        patcher = mock.patch('homehub.load', return_value=self.hub)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.page = inline(home.HomePage(self.host))

    def test_rooms_names_and_what_each_can_do(self):
        self.page.refresh()
        st = self.page.state
        self.assertTrue(st['linked'])
        rooms = self.page.rooms
        self.assertEqual([r['name'] for r in rooms], ['Fernseher', ''], 'devices without a room come last')
        buro = rooms[0]['devices'][0]
        self.assertEqual(buro['detail'], 'Philips Hue · Hue color lamp')
        self.assertEqual(buro['level'], 60)
        self.assertEqual(buro['aliases'], ['المكتب'])
        tv = rooms[1]['devices'][0]
        self.assertTrue(tv['volume_step'])
        sensor = rooms[0]['devices'][1]
        self.assertEqual((sensor['value'], sensor['unit']), ('21.5', '°C'))
        self.assertEqual(st['discovered'], [{'domain': 'wled', 'title': 'WLED'}])

    def test_rename_room_and_voice_names_go_to_home_assistant(self):
        self.page.rename('light.buro', 'المكتب الكبير')
        self.page.moveTo('light.buro', 'غرفة الشغل')
        self.page.setAliases('light.buro', 'المكتب، ضو الشغل')
        self.assertIn(('rename', 'light.buro', 'المكتب الكبير'), self.hub.calls)
        self.assertIn(('area', 'light.buro', 'غرفة الشغل'), self.hub.calls)
        self.assertIn(('aliases', 'light.buro', ['المكتب', 'ضو الشغل']), self.hub.calls)
        self.assertEqual(self.page.state['note']['status'], 'ok')

    def test_a_tv_volume_is_a_step_and_a_plug_is_read_back(self):
        self.page.press('media_player.tv', 'volume_up')
        self.assertIn(('call', 'media_player', 'volume_up', {'entity_id': 'media_player.tv'}), self.hub.calls)
        with mock.patch('pages.home.time.sleep'):
            self.page.setPower('switch.plug', True)
        self.assertEqual(self.page.state['note']['status'], 'pending', 'a plug that stays off is not "done"')

    def test_unlinked_offers_the_hub_and_its_first_run(self):
        import homehub
        import homesetup
        with mock.patch('homehub.load', return_value=None), \
                mock.patch.object(homehub, 'probe', return_value={'reachable': False}), \
                mock.patch.object(homesetup, 'status', return_value={'stage': 'none'}):
            self.page.refresh()
        self.assertEqual(self.page.state['hub']['stage'], 'none')
        with mock.patch.object(homesetup, 'install', return_value={'status': 'pending', 'written': True}) as install, \
                mock.patch('homehub.load', return_value=None), \
                mock.patch.object(homehub, 'probe', return_value={'reachable': False}), \
                mock.patch.object(homesetup, 'status', return_value={'stage': 'starting'}):
            self.page.setupHub()
        install.assert_called_once_with()
        self.assertEqual(self.page.state['hub']['stage'], 'starting')
        with mock.patch.object(homesetup, 'onboard', return_value={'status': 'ok'}) as onboard:
            self.page.onboard('Mohammed', 'mohammed', 'secret-pass-1')
        onboard.assert_called_once_with('Mohammed', 'mohammed', 'secret-pass-1')
        self.assertEqual(self.page.state['note']['status'], 'ok')

    def test_unlinked_offers_the_link(self):
        import homehub
        with mock.patch('homehub.load', return_value=None), \
                mock.patch.object(homehub, 'probe', return_value={'reachable': True, 'version': '2026.9'}):
            self.page.refresh()
        self.assertFalse(self.page.state['linked'])
        self.assertTrue(self.page.state['probe']['reachable'])


class RealQml(unittest.TestCase):
    """Both pages load with live-shaped state and print no QML fault."""

    def load(self, file, prop, page):
        messages = []
        previous = qInstallMessageHandler(lambda mode, ctx, msg: messages.append(msg))
        try:
            engine = QQmlEngine()
            engine.addImportPath(str(ROOT / 'qml'))

            class Mira(QObject):
                pass
            mira = FakeMira(page, prop)
            engine.rootContext().setContextProperty('mira', mira)
            comp = QQmlComponent(engine)
            comp.setData(f'import QtQuick\nimport Mira\nItem {{ width: 1100; height: 900\n {file} {{ anchors.fill: parent }} }}'.encode(),
                         QUrl.fromLocalFile(str(ROOT / 'qml' / 'probe.qml')))
            obj = comp.create()
            self.assertIsNotNone(obj, comp.errors())
            for _ in range(20):
                APP.processEvents()
            obj.deleteLater()
            APP.processEvents()
        finally:
            qInstallMessageHandler(previous)
        faults = [m for m in messages if 'qml' in m.lower() or 'TypeError' in m or 'ReferenceError' in m
                  or 'Unable to assign' in m]
        self.assertEqual(faults, [])

    def test_lumen_page_loads(self):
        client = FakeClient()
        with mock.patch('pages.lumen._client', return_value=client):
            page = inline(lumen.LumenPage(FakeHost()))
            page.refresh()
            self.load('LumenPage', 'lumenPage', page)

    def test_home_page_loads(self):
        with mock.patch('homehub.load', return_value=FakeHub()):
            page = inline(home.HomePage(FakeHost()))
            page.refresh()
            self.load('HomePage', 'homePage', page)


from PySide6.QtCore import Property  # noqa: E402


class FakeMira(QObject):
    langChanged = Signal()

    def __init__(self, page, prop):
        super().__init__()
        self._page = page
        self._prop = prop
        self._s = i18n.table('ar')

    s = Property('QVariantMap', lambda self: self._s, constant=True)
    lang = Property(str, lambda self: 'ar', constant=True)
    motion = Property(bool, lambda self: False, constant=True)
    lumenPage = Property(QObject, lambda self: self._page if self._prop == 'lumenPage' else None, constant=True)
    homePage = Property(QObject, lambda self: self._page if self._prop == 'homePage' else None, constant=True)


if __name__ == '__main__':
    unittest.main()
