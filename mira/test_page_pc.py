"""This PC page: read-backs, controls, owner approval and error paths — with stand-in backends only.

Nothing here reaches the machine: Mo AI's executor, /scan, KWin, MPRIS, Baloo and xdg-open are all
replaced, and a guard fails the test if the real executor transport is ever reached. The Mo AI
schemas are pinned to this tree's (system_files/usr/lib/moai), so which values need the owner's
approval never depends on the image installed on the machine that runs the tests.
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import call, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['MIRA_TEST_MODE'] = '1'
_config = tempfile.TemporaryDirectory(prefix='mira-pc-test-')
os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import QCoreApplication, QObject, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import desktop_tools  # noqa: E402
import i18n  # noqa: E402
import moai_tools  # noqa: E402
from pages import pc  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
REAL_LOOK = pc.read_look
TREE_SCHEMAS = Path(__file__).resolve().parent.parent / 'system_files/usr/lib/moai'
HOME = str(Path.home())

STATUS = {'volume': 42, 'muted': False, 'brightness': 70, 'night_light': False, 'wifi': True, 'bluetooth': None,
          'theme': 'aurora', 'dnd': False, 'mic_muted': False, 'power_profile': 'balanced'}
# What a journal, a service status or a MoOS log can carry from the base image.
LEAKY = ('Sep 29 kernel: Linux version 7.2.7-200.fc44.x86_64 (gcc (GCC) 16.1 (Red Hat 16.1-1)) #1 SMP\n'
         'Sep 29 systemd[1]: Detected system Fedora Linux 44 (Kinoite)\n'
         'Sep 29 rpm-ostree: pipewire-1.4.9-1.fc44.x86_64 from fedora-updates')
LEAKS = ('fedora', 'red hat', 'redhat', 'fc44', 'kinoite')

_saved = {}


def setUpModule():
    """Mo AI's schemas from this tree, whatever an earlier suite in this process loaded."""
    _saved.update(dirs=moai_tools.SCHEMA_DIRS, cache=dict(moai_tools._cache),
                  module=sys.modules.pop('moai_tool_schemas', None))
    moai_tools.SCHEMA_DIRS = [TREE_SCHEMAS]
    moai_tools._cache.clear()
    moai_tools._load()
    loaded = moai_tools._cache.get('module')
    assert loaded is not None and Path(loaded.__file__).resolve().parent == TREE_SCHEMAS.resolve(), loaded


def tearDownModule():
    moai_tools.SCHEMA_DIRS = _saved['dirs']
    moai_tools._cache.clear()
    moai_tools._cache.update(_saved['cache'])
    sys.modules.pop('moai_tool_schemas', None)
    if _saved['module'] is not None:
        sys.modules['moai_tool_schemas'] = _saved['module']


def pump(predicate=lambda: False, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class Host(QObject):
    """The few controller services a page may use."""
    toast = Signal(str, str)
    prefill = Signal(str)
    showSheet = Signal(str)
    langChanged = Signal()

    def __init__(self, lang='en', accept=True):
        super().__init__()
        self.lang = lang
        self.s = i18n.table(lang)
        self.cards = []
        self.accept = accept
        self.toasts = []
        self.toast.connect(lambda kind, text: self.toasts.append((kind, text)))

    def request_confirmation(self, item):
        self.cards.append(item)
        return {'id': f'card-{len(self.cards)}'} if self.accept else None

    def switch(self, lang):
        self.lang = lang
        self.s = i18n.table(lang)
        self.langChanged.emit()


class Executor:
    """Mo AI's executor, played: records every call and answers from a status it keeps."""

    def __init__(self, status=None):
        self.status = dict(STATUS if status is None else status)
        self.calls = []
        self.answers = {}       # tool -> result dict (overrides the default behaviour)
        self.apply = True       # a control changes the kept status

    def __call__(self, name, args, confirmed=False):
        self.calls.append((name, dict(args)))
        if name in self.answers:
            answer = self.answers[name]
            return answer(args) if callable(answer) else dict(answer)
        if name == 'get_system_status':
            return {'status': 'ok', 'output': json.dumps(self.status)}
        if self.apply:
            value = args.get('value')
            if name == 'set_volume':
                self.status['volume'] = int(value)
            elif name == 'set_brightness':
                self.status['brightness'] = int(value)
            elif name == 'set_mute':
                self.status['muted'] = value == 'mute'
            elif name == 'toggle_wifi':
                self.status['wifi'] = value == 'on'
            elif name == 'toggle_night_light':
                self.status['night_light'] = value != 'off'
            elif name == 'set_mic_mute':
                self.status['mic_muted'] = value == 'mute'
            elif name == 'set_do_not_disturb':
                self.status['dnd'] = value == 'on'
            elif name == 'set_power_profile':
                self.status['power_profile'] = args['profile']
        return {'status': 'ok', 'output': f'✓ تم | Done: {name}'}

    def names(self):
        return [name for name, _ in self.calls]


def windows_answer(*rows):
    return {'status': 'ok', 'count': len(rows), 'windows': [
        {'id': wid, 'title': title, 'app': app, 'active': False, 'minimized': False} for wid, title, app in rows]}


def title_only():
    """desktop_tools as an older Mira had it: a window is reached by its title alone (no KWin-id
    functions). This tree has focus_window_id/close_window_id; the title path is still the fallback."""
    return patch.multiple(desktop_tools, focus_window_id=None, close_window_id=None)


class PcPageTest(unittest.TestCase):
    def setUp(self):
        # The real transport must never be reached from these tests.
        guard = patch('moai_tools._request', side_effect=AssertionError('the real executor was reached'))
        guard.start()
        self.addCleanup(guard.stop)
        self.exe = Executor()
        runner = patch('moai_tools.execute', side_effect=self.exe)
        runner.start()
        self.addCleanup(runner.stop)
        look = patch('pages.pc.read_look', return_value={'motion': 'gentle', 'clarity': 'solid', 'night': 'off'})
        self.look = look.start()
        self.addCleanup(look.stop)
        self.host = Host('en')
        self.page = pc.PcPage(self.host)

    def settle(self, predicate):
        self.assertTrue(pump(predicate), 'the page never finished')

    def read_status(self, page=None):
        page = page or self.page
        page.refreshStatus()
        self.settle(lambda: not page._reading)
        self.assertEqual(page.state['statusState'], 'ok')

    def load_windows(self, answer, page=None):
        page = page or self.page
        with patch('desktop_tools.list_windows', return_value=answer):
            page.refreshWindows()
            self.settle(lambda: page.state['windowsState'] in ('ok', 'error') and not page.state['busy'])
            pump(timeout=0.05)

    # ── pure mapping ──────────────────────────────────────────────────
    def test_status_mapping_keeps_unknown_values_unknown(self):
        mapped = pc.parse_status({'status': 'ok', 'output': json.dumps(
            {'volume': 41.6, 'muted': False, 'brightness': None, 'wifi': True, 'bluetooth': None, 'theme': '',
             'dnd': True, 'mic_muted': 'yes', 'power_profile': 'performance', 'night_light': False})})
        self.assertEqual(mapped['volume'], 42)
        self.assertIsNone(mapped['brightness'])
        self.assertIsNone(mapped['bluetooth'])
        self.assertIsNone(mapped['theme'])
        self.assertIsNone(mapped['mic_muted'], 'a non-boolean is not a reading')
        self.assertTrue(mapped['dnd'])
        self.assertIsNone(pc.parse_status({'status': 'error', 'error': 'moai_control_unreachable'}))
        self.assertIsNone(pc.parse_status({'status': 'ok', 'output': 'not json'}))
        self.assertIsNone(pc.parse_status({'status': 'ok', 'output': '[1, 2]'}))

    def test_theme_family_and_toggle_readback(self):
        self.assertEqual(pc.theme_family('dark'), 'dark')
        self.assertEqual(pc.theme_family('aurora'), 'dark')
        self.assertEqual(pc.theme_family('aurora-light'), 'light')
        self.assertEqual(pc.theme_family('daylight'), 'light')
        self.assertEqual(pc.theme_family('auto'), 'auto')
        self.assertIsNone(pc.theme_family(None))
        self.assertTrue(pc.toggle_on({'mic_muted': False}, 'mic'))
        self.assertIsNone(pc.toggle_on({'mic_muted': None}, 'mic'))
        self.assertIsNone(pc.toggle_on({}, 'wifi'))
        self.assertFalse(pc.toggle_on({'wifi': False}, 'wifi'))

    def test_look_is_read_where_moos_theme_verifies_it(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(pc, 'SYSTEM_CONFIG', Path(folder) / 'no-system-defaults'):
            config = Path(folder)
            self.assertEqual(REAL_LOOK(config), {'motion': None, 'clarity': None, 'night': 'off'})
            (config / 'moos-appearancerc').write_text('[Material]\nClarity=solid\n')
            (config / 'plasma-org.kde.plasma.desktop-appletsrc').write_text(
                '[Containments][179]\nplugin=org.kde.plasma.folder\nwallpaperplugin=org.moos.ui2.wallpaper\n\n'
                '[Containments][179][Wallpaper][org.moos.ui2.wallpaper][General]\nMotionMode=0\n\n'
                '[Containments][180]\nplugin=org.kde.panel\nwallpaperplugin=org.kde.image\n\n'
                '[Containments][180][Wallpaper][org.moos.ui2.wallpaper][General]\nMotionMode=2\n')
            self.assertEqual(REAL_LOOK(config)['motion'], 'still')
            self.assertEqual(REAL_LOOK(config)['clarity'], 'solid')
            # a second MoOS desktop that disagrees: the motion cannot be told
            with open(config / 'plasma-org.kde.plasma.desktop-appletsrc', 'a') as stream:
                stream.write('\n[Containments][181]\nwallpaperplugin=org.moos.ui2.wallpaper\n')
            self.assertIsNone(REAL_LOOK(config)['motion'], 'mixed desktops (0 and the default 1)')
            (config / 'moos-appearancerc').write_text('[Material]\n')
            self.assertEqual(REAL_LOOK(config)['clarity'], 'clear', 'unset means clear, as moos-theme reads it')
            (config / 'moos-appearancerc').write_text('[Material]\nClarity=fancy\n')
            self.assertIsNone(REAL_LOOK(config)['clarity'])

    def test_night_light_mode_is_read_from_kwin_config(self):
        with tempfile.TemporaryDirectory() as user, tempfile.TemporaryDirectory() as system:
            self.assertEqual(pc.read_night(user, system), 'off', 'no config: KWin keeps it off')
            (Path(user) / 'kwinrc').write_text('[NightColor]\nActive=true\nMode=Constant\n')
            self.assertEqual(pc.read_night(user, system), 'on')
            (Path(user) / 'kwinrc').write_text('[Other]\nMode=Constant\n[NightColor]\nActive=true\nMode=DarkLight\n')
            self.assertEqual(pc.read_night(user, system), 'auto', "Plasma's schedule is not 'always on'")
            (Path(user) / 'kwinrc').write_text('[NightColor]\nActive=false\nMode=Constant\n')
            self.assertEqual(pc.read_night(user, system), 'off')
            (Path(system) / 'kwinrc').write_text('[NightColor]\nActive=true\n')
            (Path(user) / 'kwinrc').write_text('[Compositing]\nBackend=OpenGL\n')
            self.assertEqual(pc.read_night(user, system), 'auto', 'the system default applies when the user has none')

    def test_hardware_shows_only_what_scan_gives_without_foreign_names(self):
        scan = {'os': 'MoOS', 'version': '44.20260927.952', 'cpu': 'Intel(R) Core(TM) i5-14400F', 'cores': 16,
                'kernel': '7.2.7-200.fc44.x86_64', 'mem_gb': 15, 'disk': {'total_gb': 476, 'free_gb': 194},
                'gpu': 'nvidia (discrete)', 'arch': 'x86_64',
                'device_plan': {'gpu': '01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 '
                                       '[GeForce RTX 2080 SUPER] [10de:1e81] (rev a1)',
                                'driver_status': 'NVIDIA proprietary driver active',
                                'driver_status_ar': 'تعريف NVIDIA الرسمي يعمل', 'memory_gib': 15.4}}
        hw = pc.hardware_from_scan(scan)
        self.assertEqual(hw['cpu'], 'Intel Core i5-14400F', 'no (R)/(TM) marks')
        self.assertEqual(hw['gpu'], 'NVIDIA GeForce RTX 2080 SUPER')
        self.assertEqual(hw['kernel'], '7.2.7-200')
        self.assertEqual(hw['memory_gb'], 15.4)
        self.assertEqual((hw['disk_free_gb'], hw['disk_total_gb']), (194, 476))
        self.assertEqual(hw['driver_en'], 'NVIDIA proprietary driver active')
        self.assertEqual(hw['driver_ar'], 'تعريف NVIDIA الرسمي يعمل', 'both languages, so a switch never goes stale')
        text = json.dumps(hw).lower()
        for leak in LEAKS:
            self.assertNotIn(leak, text)
        amd = dict(scan, device_plan={'gpu': '03:00.0 VGA compatible controller [0300]: Advanced Micro Devices, '
                                             'Inc. [AMD/ATI] Navi 23 [Radeon RX 6600] [1002:73ff] (rev c1)'})
        self.assertEqual(pc.hardware_from_scan(amd)['gpu'], 'AMD Radeon RX 6600')
        intel = dict(scan, device_plan={'gpu': '00:02.0 VGA compatible controller [0300]: Intel Corporation '
                                               'AlderLake-S GT1 [8086:4680] (rev 0c)'})
        self.assertEqual(pc.hardware_from_scan(intel)['gpu'], 'Intel AlderLake-S GT1')
        self.assertEqual(pc.hardware_from_scan(dict(scan, device_plan={}))['gpu'], 'nvidia (discrete)')
        self.assertEqual(pc.hardware_from_scan(dict(scan, device_plan={'driver_status': 'ok'}))['driver_ar'], 'ok',
                         'an untranslated driver line still shows')
        self.assertIsNone(pc.hardware_from_scan({'error': 'moai_control_unreachable'}))
        self.assertIsNone(pc.hardware_from_scan(None))

    def test_the_identity_cleaner(self):
        cleaned = pc.clean(LEAKY)
        for leak in LEAKS:
            self.assertNotIn(leak, cleaned.lower())
        self.assertIn('7.2.7-200 ', cleaned)
        self.assertIn('pipewire-1.4.9-1 ', cleaned)
        self.assertEqual(pc.clean('Kernel 7.2.7-200.el9_4.aarch64'), 'Kernel 7.2.7-200')
        self.assertEqual(pc.clean(None), '')
        with patch('moai_tools.clean_identity', create=True, side_effect=lambda text: 'shared:' + text):
            self.assertEqual(pc.clean('x'), 'shared:x', "Mo AI's shared cleaner wins when it exists")
        # An older moai_tools without clean_identity: its scrub_identity still leaves nothing to read.
        with patch.object(moai_tools, 'clean_identity', None):
            cleaned = pc.clean(LEAKY)
            self.assertEqual(pc.clean('Kernel 7.2.7-200.el9_4.aarch64'), 'Kernel 7.2.7-200')
        for leak in LEAKS:
            self.assertNotIn(leak, cleaned.lower())

    # ── read-backs ────────────────────────────────────────────────────
    def test_status_read_fills_state_and_look(self):
        self.read_status()
        state = self.page.state
        self.assertEqual(state['status']['volume'], 42)
        self.assertIsNone(state['status']['bluetooth'])
        self.assertEqual(state['look'], {'motion': 'gentle', 'clarity': 'solid', 'night': 'off'})
        self.assertRegex(state['readAt'], r'^\d\d:\d\d:\d\d$')

    def test_an_unreachable_executor_is_said_plainly_in_both_languages(self):
        self.exe.answers['get_system_status'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.page.refreshStatus()
        self.settle(lambda: self.page.state['statusState'] == 'error')
        self.assertEqual(self.page.state['statusError'], "Mo AI's executor is not answering")
        self.assertEqual(self.page.state['statusCode'], 'unreachable')
        self.assertEqual(pc._why({'error': 'moai_control_unreachable'}, 'ar'), 'خدمة Mo AI التنفيذية لا تجيب')
        self.assertEqual(self.page.state['status'], {}, 'no invented reading')

    def test_the_offline_banner_names_the_reason_once(self):
        cases = [({'status': 'error', 'error': 'moai_control_unreachable'}, 'unreachable'),
                 ({'status': 'error', 'error': 'tool execution timed out (8s)'}, 'timeout'),
                 ({'status': 'error', 'error': 'unknown tool: get_system_status'}, 'missing'),
                 ({'status': 'error', 'error': 'http_500'}, 'other'),
                 ({'status': 'error', 'error': 'OSError'}, 'other')]
        titles = {'unreachable': 'pcp_offline', 'timeout': 'pcp_offline_slow', 'missing': 'pcp_offline_old',
                  'other': 'pcp_offline_other'}
        for answer, code in cases:
            for lang in ('en', 'ar'):
                with self.subTest(answer=answer, lang=lang):
                    page = pc.PcPage(Host(lang))
                    self.exe.answers['get_system_status'] = answer
                    page.refreshStatus()
                    self.settle(lambda: page.state['statusState'] == 'error')
                    self.assertEqual(page.state['statusCode'], code)
                    why = page.state['statusError']
                    hint = pc.STRINGS['pcp_offline_hint'][lang == 'en']
                    title = pc.STRINGS[titles[code]][lang == 'en']
                    self.assertTrue(why)
                    self.assertNotIn(why.rstrip('.'), hint, 'the banner says the reason once')
                    self.assertNotEqual(why.rstrip('.'), title.rstrip('.'))
                    self.assertNotRegex(why, r'http_|unknown tool|timed out|OSError', 'words, not codes')

    def test_a_crashing_worker_is_an_error_not_a_reading(self):
        self.exe.answers['get_system_status'] = lambda args: (_ for _ in ()).throw(RuntimeError('boom'))
        self.page.refreshStatus()
        self.settle(lambda: self.page.state['statusState'] == 'error')
        self.assertEqual(self.page.state['statusError'], "Couldn't do it")
        self.assertEqual(self.page.state['statusCode'], 'other')

    def test_reasons_are_words_never_codes_or_broken_backend_phrases(self):
        results = [{'status': 'partial', 'error': 'action_failed', 'summary': 'تعذّر فعّلت النافذة'},
                   {'status': 'error', 'error': 'OSError', 'summary': 'تعذّر إرسال أمر الوسائط'},
                   {'status': 'error', 'error': 'RuntimeError'},
                   {'status': 'error', 'error': 'http_502'},
                   {'status': 'unsupported', 'error': 'bad_action'},
                   {'status': 'error', 'error': 'bad_player'},
                   {'status': 'error', 'error': 'empty_path'},
                   {'status': 'error', 'exit_code': 3},
                   'not a dict']
        for result in results:
            for lang in ('en', 'ar'):
                text = pc._why(result, lang)
                self.assertTrue(text)
                self.assertNotRegex(text, r'Error\b|http_|\b[a-z]+_[a-z]+\b|فعّلت', (result, lang))
        self.assertEqual(pc._why({'error': 'action_failed'}, 'en'), 'The window manager refused')

    def test_hardware_refresh(self):
        with patch('moai_tools.get', return_value={'cpu': 'X', 'cores': 4, 'kernel': '7.1.0-100.fc44.x86_64'}) as get:
            self.page.refreshHardware()
            self.settle(lambda: self.page.state['hardwareState'] == 'ok')
        get.assert_called_once_with('/scan', 30)
        self.assertEqual(self.page.state['hardware']['kernel'], '7.1.0-100')
        with patch('moai_tools.get', return_value={'error': 'http_0'}):
            self.page.refreshHardware()
            self.settle(lambda: self.page.state['hardwareState'] == 'error')

    # ── levels ────────────────────────────────────────────────────────
    def test_volume_is_done_only_when_read_back(self):
        self.read_status()
        self.page.setVolume(140)
        self.assertTrue(self.page.state['busy'].get('volume'))
        self.assertEqual(self.page.state['wanted'], {'volume': 100}, 'the slider holds the value on its way')
        self.settle(lambda: not self.page.state['busy'].get('volume'))
        self.assertIn(('set_volume', {'value': '100'}), self.exe.calls, 'clamped to the executor range')
        self.assertEqual(self.page.state['status']['volume'], 100)
        self.assertEqual(self.page.state['wanted'], {}, 'the read-back takes over')
        self.assertEqual(self.page.state['notes']['levels']['status'], 'ok')
        self.assertIn('100%', self.page.state['notes']['levels']['text'])

    def test_a_level_sent_while_one_runs_is_sent_after_it_never_dropped(self):
        self.read_status()
        gate = threading.Event()

        def slow(args):
            gate.wait(2)
            self.exe.status['volume'] = int(args['value'])
            return {'status': 'ok', 'output': 'ok'}
        self.exe.answers['set_volume'] = slow
        self.page.setVolume(50)
        self.page.setVolume(70)
        self.page.setVolume(90)             # the owner's final value, while 50 is on its way
        self.assertEqual(self.page.state['wanted'], {'volume': 90})
        gate.set()
        self.settle(lambda: not self.page.state['busy'].get('volume') and not self.page.state['wanted'])
        sets = [c for c in self.exe.calls if c[0] == 'set_volume']
        self.assertEqual(sets, [('set_volume', {'value': '50'}), ('set_volume', {'value': '90'})],
                         'the newest value only, after the running one')
        self.assertEqual(self.page.state['status']['volume'], 90)
        self.assertIn('90%', self.page.state['notes']['levels']['text'])

    def test_a_queued_level_the_read_back_already_shows_is_not_sent_again(self):
        self.read_status()
        gate = threading.Event()

        def slow(args):
            gate.wait(2)
            self.exe.status['brightness'] = int(args['value'])
            return {'status': 'ok', 'output': 'ok'}
        self.exe.answers['set_brightness'] = slow
        self.page.setBrightness(30)
        self.page.setBrightness(30)
        gate.set()
        self.settle(lambda: not self.page.state['busy'].get('brightness') and not self.page.state['wanted'])
        self.assertEqual(self.exe.names().count('set_brightness'), 1)

    def test_a_failed_level_still_sends_the_owners_newest_value(self):
        self.read_status()
        gate = threading.Event()
        answers = iter([{'status': 'error', 'error': 'busy'}, None])

        def flaky(args):
            gate.wait(2)
            answer = next(answers)
            if answer:
                return answer
            self.exe.status['volume'] = int(args['value'])
            return {'status': 'ok', 'output': 'ok'}
        self.exe.answers['set_volume'] = flaky
        self.page.setVolume(20)
        self.page.setVolume(60)
        gate.set()
        self.settle(lambda: not self.page.state['busy'].get('volume') and not self.page.state['wanted'])
        self.assertEqual(self.page.state['status']['volume'], 60)

    def test_a_slow_poll_never_replaces_a_newer_read_back(self):
        self.read_status()
        gate = threading.Event()
        count = {'n': 0}

        def status(args):
            snapshot = json.dumps(self.exe.status)     # read BEFORE the change lands
            count['n'] += 1
            if count['n'] == 1:
                gate.wait(2)
            return {'status': 'ok', 'output': snapshot}
        self.exe.answers['get_system_status'] = status
        self.page.refreshStatus()                      # a 5 s poll starts, slowly
        self.assertTrue(pump(lambda: count['n'] == 1))
        self.page.setVolume(80)                        # the owner moves the slider meanwhile
        self.settle(lambda: not self.page.state['busy'].get('volume'))
        self.assertEqual(self.page.state['status']['volume'], 80)
        self.assertEqual(self.page.state['notes']['levels']['text'], 'Volume is now 80%')
        gate.set()                                     # the old poll lands now
        self.settle(lambda: not self.page._reading)
        pump(timeout=0.05)
        self.assertEqual(self.page.state['status']['volume'], 80, 'the stale snapshot is dropped')
        self.assertEqual(self.page.state['statusState'], 'ok')
        self.page.refreshStatus()                      # and the next poll is read normally
        self.settle(lambda: not self.page._reading)
        self.assertEqual(self.page.state['status']['volume'], 80)

    def test_a_level_the_read_back_does_not_show_is_pending_not_done(self):
        self.read_status()
        self.exe.apply = False
        self.page.setBrightness(1)
        self.settle(lambda: not self.page.state['busy'].get('brightness'))
        self.assertIn(('set_brightness', {'value': '5'}), self.exe.calls)
        self.assertEqual(self.page.state['notes']['levels']['status'], 'pending')
        self.assertEqual(self.page.state['awaiting'].get('brightness'), 'settle')
        # the next read that shows it clears the wait and says so
        self.exe.status['brightness'] = 5
        self.read_status()
        self.assertNotIn('brightness', self.page.state['awaiting'])
        self.assertEqual(self.page.state['notes']['levels']['status'], 'ok')

    def test_mute_follows_the_read_back(self):
        self.read_status()
        self.page.toggleMute()
        self.settle(lambda: not self.page.state['busy'].get('mute'))
        self.assertIn(('set_mute', {'value': 'mute'}), self.exe.calls)
        self.assertTrue(self.page.state['status']['muted'])
        self.page.toggleMute()
        self.settle(lambda: ('set_mute', {'value': 'unmute'}) in self.exe.calls and not self.page.state['busy'].get('mute'))

    def test_mute_does_nothing_when_the_machine_cannot_tell(self):
        self.page.toggleMute()                  # nothing read yet
        self.assertEqual(self.exe.calls, [])

    def test_night_light_modes_run_and_are_read_back(self):
        self.read_status()
        self.look.return_value = {'motion': 'gentle', 'clarity': 'solid', 'night': 'auto'}
        self.page.setNightLight('auto')
        self.settle(lambda: not self.page.state['busy'].get('night'))
        self.assertIn(('toggle_night_light', {'value': 'auto'}), self.exe.calls, "Plasma's schedule, kept")
        self.assertEqual(self.page.state['look']['night'], 'auto')
        self.assertEqual(self.page.state['notes']['levels'], {'status': 'ok', 'text': 'Night light: Automatic · confirmed'})
        count = len(self.exe.calls)
        self.page.setNightLight('bright')
        self.page.setToggle('night_light', True)       # the old on/off tile is gone: its mode is the choice
        pump(timeout=0.1)
        self.assertEqual(len(self.exe.calls), count)

    def test_a_failed_control_says_why(self):
        self.read_status()
        self.exe.answers['set_power_profile'] = {'status': 'error', 'exit_code': 69,
                                                 'output': 'moos-control: this computer has no performance profile\n'}
        self.page.setPowerProfile('performance')
        self.settle(lambda: not self.page.state['busy'].get('power'))
        self.assertEqual(self.page.state['notes']['controls'],
                         {'status': 'error', 'text': 'this computer has no performance profile'})
        self.assertEqual(self.host.toasts[-1][0], 'error')
        self.assertEqual(self.page.state['status']['power_profile'], 'balanced', 'the read-back is unchanged')

    # ── owner approval ────────────────────────────────────────────────
    def test_wifi_off_is_asked_never_run(self):
        self.read_status()
        self.page.setToggle('wifi', False)
        self.assertNotIn('toggle_wifi', self.exe.names(), 'a value that can cut the owner off must not run')
        card = self.host.cards[-1]
        self.assertEqual((card['kind'], card['name'], card['args'], card['origin']),
                         ('moai', 'toggle_wifi', {'value': 'off'}, 'pc'))
        self.assertTrue(card['detail'].startswith('Turn Wi-Fi off · '))
        self.assertIn(moai_tools.consequence('toggle_wifi', 'en'), card['detail'])
        self.assertEqual(self.page.state['awaiting'], {'wifi': 'approval'})
        self.assertEqual(self.page.state['notes']['controls']['status'], 'pending')
        # the owner approves on the card; the job turns Wi-Fi off; the next poll shows it and clears the wait
        self.exe.status['wifi'] = False
        self.read_status()
        self.assertEqual(self.page.state['awaiting'], {})
        self.assertEqual(self.page.state['notes']['controls']['status'], 'ok')

    def test_cards_say_what_happens_in_both_languages_never_raw_values(self):
        expected = {'en': ('Turn Wi-Fi off', 'Turn Bluetooth off', 'Turn on Do not disturb', 'Turn the microphone back on'),
                    'ar': ('إيقاف الواي فاي', 'إيقاف البلوتوث', 'تشغيل عدم الإزعاج', 'إعادة تشغيل الميكروفون')}
        tools = ('toggle_wifi', 'toggle_bluetooth', 'set_do_not_disturb', 'set_mic_mute')
        for lang in ('en', 'ar'):
            host = Host(lang)
            page = pc.PcPage(host)
            page._state['status'] = dict(STATUS, bluetooth=True)
            page._state['statusState'] = 'ok'
            page.setToggle('wifi', False)
            page.setToggle('bluetooth', False)
            page.setToggle('dnd', True)
            page.setToggle('mic', True)
            self.assertEqual([c['name'] for c in host.cards], list(tools))
            for tool, action, card in zip(tools, expected[lang], host.cards):
                said = moai_tools.consequence(tool, lang)
                self.assertTrue(said, f'the schema says what {tool} does')
                self.assertEqual(card['detail'], action + ' · ' + said)
                self.assertNotRegex(card['detail'], r':\s*(off|on|mute|unmute)\b', 'no raw enum value')
        # a value the executor asks about that its consequence does not describe gets no consequence
        page = pc.PcPage(Host('en'))
        self.assertEqual(page._detail('toggle_wifi', {'value': 'on'}), 'Turn Wi-Fi on')
        self.assertEqual(page._detail('set_power_profile', {'profile': 'power-saver'}), 'Power mode: Saver')
        self.assertEqual(page._detail('set_volume', {'value': '40'}), 'Computer volume: 40%')
        self.assertEqual(page._detail('unit_status', {'name': 'pipewire.service'}), 'Service status: pipewire.service')

    def test_a_second_click_while_the_card_waits_raises_no_second_card(self):
        self.read_status()
        self.page.setToggle('wifi', False)
        self.page.setToggle('wifi', False)
        self.assertEqual(len(self.host.cards), 1)
        self.assertEqual(self.page.state['notes']['controls'],
                         {'status': 'pending', 'text': pc.STRINGS['pcp_card_open'][1]}, 'the click is answered')
        self.page._expect['wifi']['since'] -= pc.CARD_TTL + 1     # the card's own lifetime is over
        self.page.setToggle('wifi', False)
        self.assertEqual(len(self.host.cards), 2)

    def test_the_controller_says_whether_the_card_still_waits(self):
        live = set()
        self.host.card_waiting = lambda card_id: card_id in live
        self.read_status()
        self.page.setToggle('wifi', False)
        live.add('card-1')
        self.page.setToggle('wifi', False)
        self.assertEqual(len(self.host.cards), 1)
        live.clear()                       # rejected or expired: a click asks again at once
        self.page.setToggle('wifi', False)
        self.assertEqual(len(self.host.cards), 2)
        # a card that closed without the change: watched a little, then said plainly
        live.clear()
        self.read_status()
        self.assertEqual(self.page.state['awaiting'], {'wifi': 'settle'})
        self.page._expect['wifi']['until'] = time.monotonic() - 1
        self.read_status()
        self.assertEqual(self.page.state['awaiting'], {})
        self.assertEqual(self.page.state['notes']['controls'], {'status': 'info', 'text': pc.STRINGS['pcp_card_closed'][1]})

    def test_a_rejected_card_is_said_and_can_be_asked_again(self):
        self.read_status()
        self.page.setToggle('wifi', False)
        self.page.action_update('card-1', 'cancelled', '', '')
        self.assertEqual(self.page.state['awaiting'], {})
        self.assertEqual(self.page.state['notes']['controls'], {'status': 'info', 'text': pc.STRINGS['pcp_card_rejected'][1]})
        self.page.setToggle('wifi', False)
        self.assertEqual(len(self.host.cards), 2)
        self.page.action_update('card-2', 'expired', '', '')
        self.assertEqual(self.page.state['notes']['controls']['text'], pc.STRINGS['pcp_card_expired'][1])
        self.page.action_update('card-9', 'ok', '', '')              # not this page's card: ignored
        self.page.setToggle('wifi', False)
        self.page.action_update('card-3', 'error', 'x', 'moos-control: rfkill is blocked by the firmware\n')
        self.assertEqual(self.page.state['notes']['controls'], {'status': 'error', 'text': 'rfkill is blocked by the firmware'})
        # a job that outlived the controller's wait goes on: said as still going, never as a failure
        self.page.setToggle('wifi', False)
        self.page.action_update('card-4', 'running', '', '')
        self.page.action_update('card-4', 'still-running', 'Still running; it will finish on its own', '')
        self.assertEqual(self.page.state['awaiting'], {})
        self.assertEqual(self.page.state['notes']['controls'],
                         {'status': 'pending', 'text': 'Still running; it will finish on its own'})

    def test_an_approved_card_is_done_when_the_read_back_shows_it(self):
        self.read_status()
        self.page.setToggle('wifi', False)
        self.page.action_update('card-1', 'running', '', '')
        self.assertEqual(self.page.state['awaiting'], {'wifi': 'settle'})
        self.exe.status['wifi'] = False
        self.page.action_update('card-1', 'ok', 'done', '')
        self.settle(lambda: not self.page._reading and not self.page.state['awaiting'])
        self.assertEqual(self.page.state['notes']['controls'], {'status': 'ok', 'text': 'Wi-Fi: Off · confirmed'})

    def test_wifi_on_runs_at_once(self):
        self.exe.status['wifi'] = False
        self.read_status()
        self.page.setToggle('wifi', True)
        self.settle(lambda: not self.page.state['busy'].get('wifi'))
        self.assertIn(('toggle_wifi', {'value': 'on'}), self.exe.calls)
        self.assertEqual(self.host.cards, [])
        self.assertEqual(self.page.state['notes']['controls']['status'], 'ok')

    def test_microphone_back_on_and_dnd_on_need_the_owner(self):
        self.read_status()
        self.page.setToggle('mic', False)          # muting is always safe
        self.settle(lambda: not self.page.state['busy'].get('mic'))
        self.assertIn(('set_mic_mute', {'value': 'mute'}), self.exe.calls)
        self.page.setToggle('mic', True)
        self.assertEqual(self.host.cards[-1]['args'], {'value': 'unmute'})
        self.page.setToggle('dnd', True)
        self.assertEqual((self.host.cards[-1]['name'], self.host.cards[-1]['args']), ('set_do_not_disturb', {'value': 'on'}))
        self.assertNotIn(('set_do_not_disturb', {'value': 'on'}), self.exe.calls)
        self.assertEqual(self.page.state['awaiting'], {'mic': 'approval', 'dnd': 'approval'})

    def test_when_the_executor_asks_for_approval_the_owner_is_asked(self):
        self.read_status()
        self.exe.answers['set_power_profile'] = {'status': 'confirm', 'category': 'user_confirm'}
        self.page.setPowerProfile('power-saver')
        self.settle(lambda: bool(self.host.cards))
        self.assertEqual((self.host.cards[-1]['name'], self.host.cards[-1]['args']),
                         ('set_power_profile', {'profile': 'power-saver'}))
        self.assertEqual(self.host.cards[-1]['detail'], 'Power mode: Saver')
        self.assertEqual(self.page.state['awaiting'], {'power': 'approval'})

    def test_a_card_that_could_not_be_raised_is_an_error(self):
        self.host.accept = False
        self.read_status()
        self.page.setToggle('bluetooth', False)
        self.assertEqual(self.page.state['notes']['controls']['status'], 'error')
        self.assertEqual(self.page.state['awaiting'], {})

    def test_an_approval_that_never_lands_ends_with_a_plain_word(self):
        self.read_status()
        self.page.setToggle('wifi', False)
        self.page._expect['wifi']['until'] = time.monotonic() - 1
        self.read_status()
        self.assertEqual(self.page.state['awaiting'], {})
        self.assertEqual(self.page.state['notes']['controls']['status'], 'info')

    def test_unknown_controls_and_values_are_refused(self):
        self.read_status()
        before = list(self.exe.calls)
        self.page.setToggle('airplane', True)
        self.page.setTheme('neon')
        self.page.setPowerProfile('turbo')
        self.page.setMotion('wild')
        self.page.setClarity('glass')
        self.page.setNightLight('disco')
        self.page.showWindows('everything')
        self.page.arrange('spiral')
        self.page.switchDesktop('up')
        self.page.media('eject')
        self.page.runCheck('rm')
        self.page.readLog('secrets')
        pump(timeout=0.2)
        self.assertEqual(self.exe.calls, before)
        self.assertEqual(self.host.cards, [])

    # ── quick controls without a status read-back ─────────────────────
    def test_theme_applies_after_answering_and_is_watched(self):
        self.read_status()
        self.page.setTheme('light')
        self.settle(lambda: not self.page.state['busy'].get('theme'))
        self.assertIn(('set_theme_mode', {'value': 'light'}), self.exe.calls)
        self.assertEqual(self.page.state['awaiting'], {'theme': 'settle'})
        self.exe.status['theme'] = 'aurora-light'
        self.read_status()
        self.assertEqual(self.page.state['awaiting'], {})
        self.assertIn('confirmed', self.page.state['notes']['controls']['text'])

    def test_motion_and_clarity_read_back_from_the_look(self):
        self.read_status()
        self.look.return_value = {'motion': 'alive', 'clarity': 'solid', 'night': 'off'}
        self.page.setMotion('alive')
        self.settle(lambda: not self.page.state['busy'].get('motion'))
        self.assertIn(('set_motion', {'level': 'alive'}), self.exe.calls)
        self.assertEqual(self.page.state['look']['motion'], 'alive')
        self.assertEqual(self.page.state['notes']['controls']['status'], 'ok')

    def test_keyboard_layout_reads_its_own_answer(self):
        self.exe.answers['switch_keyboard_layout'] = {'status': 'ok', 'output': '⌨ لوحة المفاتيح: العربية | Keyboard layout: ara\n'}
        self.page.nextKeyboardLayout()
        self.settle(lambda: not self.page.state['busy'].get('keyboard'))
        self.assertEqual(self.page.state['layout'], 'ara')
        self.assertEqual(self.page.state['notes']['controls'], {'status': 'ok', 'text': 'Keyboard layout: ara'})

    def test_screenshot_is_done_only_when_the_file_exists(self):
        with tempfile.NamedTemporaryFile(suffix='.png') as shot:
            self.exe.answers['take_screenshot'] = {'status': 'ok', 'output': f'📸 حُفظت اللقطة | Screenshot saved: {shot.name}\n'}
            self.page.screenshot()
            self.settle(lambda: not self.page.state['busy'].get('screenshot'))
            self.assertEqual(self.page.state['notes']['controls']['status'], 'ok')
            self.assertIn(Path(shot.name).name, self.page.state['notes']['controls']['text'])
        self.exe.answers['take_screenshot'] = {'status': 'ok', 'output': 'Screenshot saved: /nonexistent/x.png'}
        self.page.screenshot()
        self.settle(lambda: not self.page.state['busy'].get('screenshot'))
        self.assertEqual(self.page.state['notes']['controls']['status'], 'pending')

    def test_settings_pages_open_through_the_executor(self):
        self.exe.answers['open_settings'] = {'status': 'ok', 'output': '⚙ فتح الإعدادات: audio | Opening settings: audio\n'}
        self.page.openSettings('audio')
        self.settle(lambda: not self.page.state['busy'])
        self.assertEqual(self.exe.calls, [('open_settings', {'page': 'audio'})], 'nothing to read back for a page')
        self.assertEqual(self.page.state['notes']['levels'], {'status': 'ok', 'text': 'Opening settings: audio'})
        self.exe.answers['open_settings'] = {'status': 'error', 'error': 'invalid arguments for tool open_settings'}
        self.page.openSettings('about')
        self.settle(lambda: not self.page.state['busy'])
        self.assertEqual(self.page.state['notes']['hardware'], {'status': 'error', 'text': 'The tool refused this value'})
        self.exe.answers['open_settings'] = {'status': 'ok', 'output': 'Opening settings: network\n'}
        self.page.openSettings('network')
        self.settle(lambda: not self.page.state['busy'])
        self.assertEqual(self.page.state['notes']['controls']['text'], 'Opening settings: network')
        count = len(self.exe.calls)
        self.page.openSettings('../../etc')
        self.page.openSettings('')
        self.assertEqual(len(self.exe.calls), count)
        # every page this page opens is one the executor's registry offers
        pages = set(moai_tools._cache['module'].SETTINGS_PAGES)
        qml = (Path(__file__).resolve().parent / 'qml/Mira/PcPage.qml').read_text()
        opened = set(re.findall(r'openSettings\("([a-z-]+)"\)', qml))
        self.assertTrue(opened)
        self.assertEqual(sorted(opened - pages), [])

    # ── identity ──────────────────────────────────────────────────────
    def test_nothing_a_backend_says_shows_a_base_distribution(self):
        self.exe.answers.update({name: {'status': 'ok', 'output': LEAKY}
                                 for name in ('memory_status', 'read_journal', 'read_moos_log', 'unit_status')})
        self.page.runCheck('memory_status')
        self.page.readJournal('', 'err', 'boot', False)
        self.page.readLog('store')
        self.page.unitStatus('pipewire', False)
        self.settle(lambda: len(self.page.state['outputs']) == 4 and not self.page.state['running'])
        for slot, entry in self.page.state['outputs'].items():
            self.assertEqual(entry['status'], 'ok', slot)
            self.assertIn('7.2.7-200', entry['text'])
            for leak in LEAKS:
                self.assertNotIn(leak, entry['text'].lower(), slot)
        # a failure's own last line, a control's answer and the keyboard's layout are cleaned too
        self.exe.answers['read_journal'] = {'status': 'error', 'exit_code': 1, 'output': LEAKY}
        self.page.readJournal('', 'err', 'boot', False)
        self.settle(lambda: not self.page.state['running'])
        self.exe.answers['switch_keyboard_layout'] = {'status': 'ok', 'output': 'Keyboard layout: Fedora us (Red Hat)\n'}
        self.page.nextKeyboardLayout()
        self.settle(lambda: not self.page.state['busy'])
        self.exe.answers['arrange_windows'] = {'status': 'ok', 'output': 'Arranged 7.2.7-200.fc44 windows\n'}
        with patch('desktop_tools.list_windows', return_value={'status': 'ok', 'windows': []}):
            self.page.arrange('halves')
            self.settle(lambda: not self.page.state['busy'])
            pump(timeout=0.05)
        text = json.dumps([self.page.state['outputs'], self.page.state['notes'], self.page.state['layout']]).lower()
        for leak in LEAKS:
            self.assertNotIn(leak, text)

    # ── windows and desktops ──────────────────────────────────────────
    def test_windows_actions_run_through_the_executor(self):
        self.page.showWindows('overview')
        self.page.arrange('thirds')
        self.page.switchDesktop('previous')
        with patch('desktop_tools.list_windows', return_value={'status': 'ok', 'windows': []}):
            self.settle(lambda: not self.page.state['busy'])
            pump(timeout=0.1)
        self.assertIn(('show_windows', {'view': 'overview'}), self.exe.calls)
        self.assertIn(('arrange_windows', {'layout': 'thirds'}), self.exe.calls)
        self.assertIn(('switch_desktop', {'direction': 'previous'}), self.exe.calls)
        self.assertNotIn('get_system_status', self.exe.names(), 'nothing to read back for a view')
        self.assertEqual(self.page.state['notes']['windows']['status'], 'ok')

    def test_windows_list_focus_and_close(self):
        self.enterContext(title_only())
        self.load_windows(windows_answer(('{a}', 'Report — Writer', 'libreoffice-writer'),
                                         ('{b}', 'Konsole', 'org.kde.konsole')))
        rows = self.page.state['windows']
        self.assertEqual([w['title'] for w in rows], ['Report — Writer', 'Konsole'])
        self.assertTrue(all(w['unique'] and w['canFocus'] and w['canClose'] for w in rows))
        with patch('desktop_tools.focus_window', return_value={'status': 'ok', 'title': 'Konsole'}) as focus, \
                patch('desktop_tools.list_windows', return_value={'status': 'ok', 'windows': []}):
            self.page.focusWindow('{b}', 'Konsole')
            self.settle(lambda: not self.page.state['busy'])
        focus.assert_called_once_with('Konsole')
        self.assertEqual(self.page.state['notes']['windows'], {'status': 'ok', 'text': 'Focused «Konsole»'})
        self.load_windows(windows_answer(('{a}', 'Report — Writer', 'libreoffice-writer'),
                                         ('{b}', 'Konsole', 'org.kde.konsole')))
        with patch('desktop_tools.close_window') as close:
            self.page.closeWindow('{b}', 'Konsole')
            close.assert_not_called()
        card = self.host.cards[-1]
        self.assertEqual((card['kind'], card['name'], card['args'], card['origin']),
                         ('desktop', 'close_window', {'query': 'Konsole'}, 'pc'))
        self.assertIn('Konsole', card['detail'])
        self.page.closeWindow('{b}', 'Konsole')        # a second click while the card waits
        self.assertEqual(len(self.host.cards), 1)
        self.assertEqual(self.page.state['notes']['windows']['text'], pc.STRINGS['pcp_card_open'][1])
        self.page.closeWindow('{gone}', 'Gone')
        self.assertEqual(len(self.host.cards), 1)
        self.assertEqual(self.page.state['notes']['windows']['text'], 'That window is no longer open')
        # the owner approves; the controller says it ran: the list is read again
        with patch('desktop_tools.list_windows', return_value=windows_answer(('{a}', 'Report — Writer', 'x'))) as listed:
            self.page.action_update('card-1', 'ok', '', '')
            self.settle(lambda: listed.called and len(self.page.state['windows']) == 1)
        self.assertEqual(self.page.state['notes']['windows'], {'status': 'ok', 'text': 'Asked «Konsole» to close'})

    def test_windows_that_share_a_title_are_never_acted_on_by_title(self):
        answer = windows_answer(('{a}', '~ : bash — Konsole', 'org.kde.konsole'),
                                ('{b}', '~ : bash — Konsole', 'org.kde.konsole'),
                                ('{c}', 'Downloads — Dolphin', 'org.kde.dolphin'),
                                ('{d}', 'Downloads — Dolphin (2)', 'org.kde.dolphin'),
                                ('{e}', 'Report — Writer', 'libreoffice-writer'))
        with title_only():
            self.load_windows(answer)
            unique = {w['id']: w['unique'] for w in self.page.state['windows']}
            self.assertEqual(unique, {'{a}': False, '{b}': False, '{c}': False, '{d}': True, '{e}': True})
            self.assertFalse(any(w['canFocus'] or w['canClose'] for w in self.page.state['windows'] if not w['unique']))
            with patch('desktop_tools.focus_window') as focus, patch('desktop_tools.close_window') as close:
                self.page.focusWindow('{a}', '~ : bash — Konsole')
                self.page.closeWindow('{c}', 'Downloads — Dolphin')
                pump(timeout=0.1)
            focus.assert_not_called()
            close.assert_not_called()
            self.assertEqual(self.host.cards, [], 'no card that would close the wrong window, or none')
            self.assertEqual(self.page.state['notes']['windows']['text'], pc.WHY['same_title'][1])
        # once desktop_tools acts by KWin's own window id, every row can be reached, by that id
        with patch('desktop_tools.focus_window_id', create=True,
                   return_value={'status': 'ok', 'title': '~ : bash — Konsole'}) as by_id, \
                patch('desktop_tools.close_window_id', create=True):
            self.load_windows(answer)
            self.assertTrue(all(w['canFocus'] and w['canClose'] for w in self.page.state['windows']))
            with patch('desktop_tools.list_windows', return_value=answer):
                self.page.focusWindow('{b}', '~ : bash — Konsole')
                self.settle(lambda: not self.page.state['busy'])
            by_id.assert_called_once_with('{b}', '~ : bash — Konsole')
            self.page.closeWindow('{a}', '~ : bash — Konsole')
        self.assertEqual(self.host.cards[-1]['args'], {'query': '~ : bash — Konsole', 'id': '{a}'})

    def test_this_tree_acts_on_the_window_by_its_kwin_id(self):
        """desktop_tools here has focus_window_id/close_window_id: every row, even one whose title
        another window shares, is reached by its own id, and the close card carries that id."""
        self.assertTrue(callable(getattr(desktop_tools, 'focus_window_id', None)))
        self.assertTrue(callable(getattr(desktop_tools, 'close_window_id', None)))
        answer = windows_answer(('{a}', '~ : bash — Konsole', 'org.kde.konsole'),
                                ('{b}', '~ : bash — Konsole', 'org.kde.konsole'))
        self.load_windows(answer)
        self.assertTrue(all(w['canFocus'] and w['canClose'] for w in self.page.state['windows']))
        with patch('desktop_tools.focus_window_id', return_value={'status': 'ok', 'title': '~ : bash — Konsole'}) as by_id, \
                patch('desktop_tools.focus_window') as by_title, \
                patch('desktop_tools.list_windows', return_value=answer):
            self.page.focusWindow('{b}', '~ : bash — Konsole')
            self.settle(lambda: not self.page.state['busy'])
        by_id.assert_called_once_with('{b}', '~ : bash — Konsole')
        by_title.assert_not_called()
        self.page.closeWindow('{a}', '~ : bash — Konsole')
        self.assertEqual(self.host.cards[-1]['args'], {'query': '~ : bash — Konsole', 'id': '{a}'})

    def test_an_older_windows_list_never_replaces_a_newer_one(self):
        gate = threading.Event()
        answers = [windows_answer(('{old}', 'Closed long ago', 'x')), windows_answer(('{new}', 'Konsole', 'y'))]

        def listed():
            answer = answers.pop(0)
            if answer['windows'][0]['id'] == '{old}':
                gate.wait(2)
            return answer
        with patch('desktop_tools.list_windows', side_effect=listed):
            self.page.refreshWindows()
            self.assertTrue(pump(lambda: len(answers) == 1), 'the first read is on its way')
            self.page.refreshWindows()
            self.settle(lambda: self.page.state['windows'] and self.page.state['windows'][0]['id'] == '{new}')
            gate.set()
            pump(timeout=0.2)
        self.assertEqual([w['id'] for w in self.page.state['windows']], ['{new}'])

    def test_windows_are_read_again_on_the_slow_tick(self):
        with patch.object(pc.PcPage, 'refreshStatus') as status, patch.object(pc.PcPage, 'refreshWindows') as windows, \
                patch.object(pc.PcPage, 'refreshMedia') as media:
            for _ in range(6):
                self.page._poll()
        self.assertEqual((status.call_count, windows.call_count, media.call_count), (6, 2, 2))

    def test_arabic_results_are_arabic(self):
        self.enterContext(title_only())
        page = pc.PcPage(Host('ar'))
        self.load_windows(windows_answer(('{k}', 'Konsole', 'org.kde.konsole')), page)
        with patch('desktop_tools.focus_window', return_value={'status': 'ok', 'title': 'Konsole'}), \
                patch('desktop_tools.list_windows', return_value={'status': 'ok', 'windows': []}):
            page.focusWindow('{k}', 'Konsole')
            self.assertTrue(pump(lambda: not page.state['busy']))
        self.assertEqual(page.state['notes']['windows']['text'], 'انتقلت إلى «Konsole»')
        self.assertEqual(pc._half('🔊 الصوت 40% | Volume 40%', 'ar'), '🔊 الصوت 40%')

    def test_windows_errors_are_shown(self):
        with patch('desktop_tools.list_windows', return_value={'status': 'unsupported', 'error': 'no_kwin'}):
            self.page.refreshWindows()
            self.settle(lambda: self.page.state['windowsState'] == 'error')
        self.assertEqual(self.page.state['windowsError'], 'The window manager is not answering')
        self.enterContext(title_only())
        self.load_windows(windows_answer(('{a}', 'Konsole', 'org.kde.konsole')))
        with patch('desktop_tools.focus_window', return_value={'status': 'partial', 'error': 'action_failed',
                                                               'summary': 'تعذّر فعّلت النافذة'}), \
                patch('desktop_tools.list_windows', return_value={'status': 'ok', 'windows': []}):
            self.page.focusWindow('{a}', 'Konsole')
            self.settle(lambda: not self.page.state['busy'])
        self.assertEqual(self.page.state['notes']['windows'], {'status': 'error', 'text': 'The window manager refused'})

    # ── media ─────────────────────────────────────────────────────────
    def test_media_status_and_controls_follow_the_same_player(self):
        playing = {'status': 'ok', 'player': 'vlc', 'state': 'Playing', 'title': 'Song', 'artist': 'Band', 'players': ['vlc']}
        with patch('desktop_tools.media', return_value=playing) as media:
            self.page.refreshMedia()
            self.settle(lambda: self.page.state['mediaState'] == 'ok')
            self.assertEqual(self.page.state['media']['title'], 'Song')
            media.return_value = dict(playing, state='Paused', action='pause')
            self.page.media('pause')
            self.settle(lambda: not self.page.state['busy'].get('media'))
        self.assertIn(call('pause', 'vlc'), media.call_args_list)
        self.assertIn(call('status', 'vlc'), media.call_args_list)
        self.assertEqual(self.page.state['media']['state'], 'Paused')
        self.assertEqual(self.page.state['notes']['media'], {'status': 'ok', 'text': 'vlc · Paused'})

    def test_no_player_is_an_empty_state_not_an_error(self):
        with patch('desktop_tools.media', return_value={'status': 'unsupported', 'error': 'no_player', 'players': []}):
            self.page.refreshMedia()
            self.settle(lambda: self.page.state['mediaState'] == 'none')
        with patch('desktop_tools.media', return_value={'status': 'error', 'error': 'OSError'}):
            self.page.refreshMedia()
            self.settle(lambda: self.page.state['mediaState'] == 'error')
        self.assertEqual(self.page.state['media']['error'], "Couldn't do it")
        with patch('desktop_tools.media', return_value={'status': 'error', 'error': 'OSError', 'summary': 'x'}):
            self.page.media('next')
            self.settle(lambda: not self.page.state['busy'].get('media'))
        self.assertEqual(self.page.state['notes']['media']['status'], 'error')

    # ── diagnostics ───────────────────────────────────────────────────
    def test_checks_show_the_executor_output_under_their_control(self):
        self.exe.answers['top_processes'] = {'status': 'ok', 'output': '== top processes by memory ==\nPID ...\n'}
        self.page.runCheck('top_processes:memory')
        self.assertEqual(self.page.state['running'], {'checks': 'top_processes:memory'})
        self.page.runCheck('disk_status')          # one at a time per control group
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.exe.calls, [('top_processes', {'by': 'memory'})])
        self.assertEqual(self.page.state['outputs']['checks'],
                         {'tool': 'top_processes:memory', 'status': 'ok', 'text': '== top processes by memory ==\nPID ...'})
        self.exe.answers['list_failed_units'] = {'status': 'error', 'error': 'busy'}
        self.page.runCheck('list_failed_units')
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.page.state['outputs']['checks']['status'], 'error')
        self.assertEqual(self.page.state['outputs']['checks']['text'], 'Another action is still running; wait for it to end')

    def test_service_status_validates_the_name(self):
        self.page.unitStatus('pipewire', True)
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.exe.calls[-1], ('unit_status', {'name': 'pipewire.service', 'user': True}))
        self.page.unitStatus('NetworkManager.service', False)
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.exe.calls[-1], ('unit_status', {'name': 'NetworkManager.service'}))
        count = len(self.exe.calls)
        self.page.unitStatus('rm -rf /', False)
        self.page.unitStatus('', False)
        self.assertEqual(len(self.exe.calls), count)
        self.assertEqual(self.page.state['outputs']['unit']['status'], 'error')

    def test_journal_arguments_are_the_schema_enums(self):
        self.page.readJournal('', 'err', '24h', True)
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.exe.calls[-1], ('read_journal', {'lines': 80, 'priority': 'err', 'since': '24h'}))
        self.page.readJournal('pipewire', 'loud', 'forever', True)
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.exe.calls[-1], ('read_journal', {'lines': 80, 'unit': 'pipewire.service', 'user': True}))
        count = len(self.exe.calls)
        self.page.readJournal('bad name!', 'err', 'boot', False)
        self.assertEqual(len(self.exe.calls), count)
        self.assertEqual(self.page.state['outputs']['journal']['status'], 'error')
        schema = next(s for s in moai_tools._load() if s['function']['name'] == 'read_journal')
        props = schema['function']['parameters']['properties']
        self.assertEqual(set(pc.PRIORITIES) - set(props['priority']['enum']), set())
        self.assertEqual(set(pc.SINCE) - set(props['since']['enum']), set())

    def test_moos_logs(self):
        self.page.readLog('store')
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.exe.calls[-1], ('read_moos_log', {'name': 'store'}))
        self.assertEqual(self.page.state['outputs']['logs']['tool'], 'log:store')

    def test_a_read_the_executor_wants_approved_goes_to_the_owner(self):
        self.exe.answers['memory_status'] = {'status': 'confirm'}
        self.page.runCheck('memory_status')
        self.settle(lambda: not self.page.state['running'])
        self.assertEqual(self.host.cards[-1]['name'], 'memory_status')
        self.assertEqual(self.host.cards[-1]['detail'], 'Memory')
        self.assertEqual(self.page.state['outputs']['checks']['status'], 'pending')

    # ── files ─────────────────────────────────────────────────────────
    def test_files_search_and_open_only_what_was_found(self):
        found = {'status': 'ok', 'count': 1, 'source': 'baloo', 'files': [
            {'path': HOME + '/Documents/report.odt', 'name': 'report.odt', 'size': 49152,
             'modified': '2026-09-28 14:10', 'is_dir': False}]}
        with patch('desktop_tools.find_files', return_value=found) as find:
            self.page.findFiles('  report ')
            self.settle(lambda: self.page.state['filesState'] == 'ok')
        find.assert_called_once_with('report', 20)
        row = self.page.state['files'][0]
        self.assertEqual((row['name'], row['folder'], row['bytes']), ('report.odt', '~/Documents', 49152),
                         'the size stays a number: the page words it in the language on screen')
        with patch('desktop_tools.open_path', return_value={'status': 'ok', 'path': row['path']}) as open_path:
            self.page.openFile(row['path'], False)
            self.settle(lambda: not self.page.state['busy'])
            open_path.assert_called_once_with(row['path'])
            self.page.openFile(row['path'], True)
            self.settle(lambda: open_path.call_count == 2 and not self.page.state['busy'])
            self.assertEqual(open_path.call_args.args, (HOME + '/Documents',))
            self.page.openFile('/etc/shadow', False)
            self.assertEqual(open_path.call_count, 2, 'a path the search did not return is never opened')
        self.assertEqual(self.page.state['notes']['files']['status'], 'error')

    def test_an_older_slower_search_never_replaces_a_newer_one(self):
        gate = threading.Event()

        def find(query, limit):
            if query == 'old':
                gate.wait(2)
            return {'status': 'ok', 'files': [{'path': f'{HOME}/{query}.txt', 'name': f'{query}.txt', 'size': 1,
                                               'modified': '', 'is_dir': False}]}
        with patch('desktop_tools.find_files', side_effect=find):
            self.page.findFiles('old')
            self.page.findFiles('new')          # the owner typed again and pressed Enter
            self.settle(lambda: self.page.state['filesState'] == 'ok')
            gate.set()
            pump(timeout=0.2)
        self.assertEqual([f['name'] for f in self.page.state['files']], ['new.txt'])
        self.assertEqual(self.page.state['filesQuery'], 'new')
        self.assertEqual(self.page._files, {f'{HOME}/new.txt'}, 'Open acts only on what is shown')

    def test_files_errors(self):
        self.page.findFiles('   ')
        self.assertEqual(self.page.state['filesState'], 'error')
        self.assertEqual(self.page.state['filesError'], 'Type what to look for')
        with patch('desktop_tools.find_files', return_value={'status': 'ok', 'files': [], 'count': 0}):
            self.page.findFiles('nothing')
            self.settle(lambda: self.page.state['filesState'] == 'ok')
        self.assertEqual(self.page.state['files'], [])

    # ── language ──────────────────────────────────────────────────────
    def test_a_language_switch_says_everything_again(self):
        self.exe.answers['get_system_status'] = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.page.refreshStatus()
        self.settle(lambda: self.page.state['statusState'] == 'error')
        with patch('desktop_tools.list_windows', return_value={'status': 'unsupported', 'error': 'no_kwin'}):
            self.page.refreshWindows()
            self.settle(lambda: self.page.state['windowsState'] == 'error')
        self.exe.answers['switch_keyboard_layout'] = {'status': 'ok', 'output': 'لوحة المفاتيح: العربية | Keyboard layout: ara\n'}
        self.page.nextKeyboardLayout()
        self.settle(lambda: not self.page.state['busy'])
        self.exe.answers['disk_status'] = {'status': 'error', 'error': 'busy'}
        self.page.runCheck('disk_status')
        self.settle(lambda: not self.page.state['running'])
        self.page.findFiles(' ')
        self.assertTrue(self.page.state['notes'])
        self.host.switch('ar')
        state = self.page.state
        self.assertEqual(state['statusError'], 'خدمة Mo AI التنفيذية لا تجيب')
        self.assertEqual(state['windowsError'], 'مدير النوافذ لا يجيب')
        self.assertEqual(state['layout'], 'العربية')
        self.assertEqual(state['outputs']['checks']['text'], 'عملية أخرى ما زالت تعمل؛ انتظر انتهاءها')
        self.assertEqual(state['filesError'], 'اكتب ما تبحث عنه')
        self.assertEqual(state['notes'], {}, 'one-off notes of the other language are dropped')

    # ── lifecycle ─────────────────────────────────────────────────────
    def test_polling_runs_only_while_the_page_is_shown(self):
        self.page.activated()                    # review/test mode: nothing is read, nothing polls
        self.assertFalse(self.page._timer.isActive())
        self.assertEqual(self.exe.calls, [])
        with patch.object(pc, 'TEST_MODE', False), patch.object(pc.PcPage, 'refresh') as refresh:
            self.page.activated()
            refresh.assert_called_once()
            self.assertTrue(self.page._timer.isActive())
            self.assertEqual(self.page._timer.interval(), 5000)
            self.page.hidden()
            self.assertFalse(self.page._timer.isActive())
            with patch.object(pc.PcPage, '_poll') as poll:
                self.page.resume()
                poll.assert_called_once()
            self.assertTrue(self.page._timer.isActive())
            self.page.hidden()

    def test_a_poll_never_overlaps_a_read_in_flight(self):
        self.page.refreshStatus()
        self.page.refreshStatus()
        self.settle(lambda: self.page.state['statusState'] == 'ok')
        self.assertEqual(self.exe.names().count('get_system_status'), 1)

    def test_review_fills_visibly_sample_state(self):
        self.page.review()
        state = self.page.state
        self.assertTrue(state['sample'])
        self.assertEqual(state['statusState'], 'ok')
        self.assertTrue(state['windows'] and state['files'] and state['hardware'] and state['outputs'])
        self.assertIn('sample', json.dumps(state, ensure_ascii=False).lower())
        self.assertTrue(any(not w['canFocus'] for w in state['windows']), 'the shared-title row is shown too')
        self.assertEqual(self.exe.calls, [])

    def test_words_are_complete_and_speak_only_of_moos(self):
        for key, pair in pc.STRINGS.items():
            self.assertTrue(key.startswith('pcp_'), key)
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(all(isinstance(w, str) and w.strip() for w in pair), key)
            for word in pair:
                self.assertNotRegex(word.lower(), r'fedora|red hat|redhat', key)
        qml = (Path(__file__).resolve().parent / 'qml/Mira/PcPage.qml').read_text()
        used = set(re.findall(r'mira\.s\.(pcp_\w+)', qml))
        self.assertEqual(sorted(used - set(pc.STRINGS)), [])
        self.assertNotRegex(qml.lower(), r'fedora|red hat')


if __name__ == '__main__':
    unittest.main()
