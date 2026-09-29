"""Mira's controller: state machine, routes and honest results, with stand-in backends only."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['MIRA_TEST_MODE'] = '1'
_config = tempfile.TemporaryDirectory(prefix='mira-controller-test-')
os.environ['XDG_CONFIG_HOME'] = _config.name

from PySide6.QtCore import QCoreApplication, QSettings  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import controller as ctl  # noqa: E402
from review_fakes import FakeBridge, FakeEntity  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
QSettings.setDefaultFormat(QSettings.IniFormat)
QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, _config.name)


def pump(predicate=lambda: False, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


class ControllerTest(unittest.TestCase):
    def setUp(self):
        QSettings('MoOS', 'Mira').clear()
        self.c = ctl.Controller(bridge_class=FakeBridge)
        self.toasts = []
        self.c.toast.connect(lambda kind, text: self.toasts.append((kind, text)))
        self.c.chat.clear()

    def voice(self, kind, text=''):
        self.c._on_voice(kind, text)

    # ── state machine ───────────────────────────────────────────────
    def test_voice_states_drive_one_phase(self):
        self.c.bridge.online = True
        self.c._on_echo_connected([FakeEntity(1, 'speaker')])
        self.assertEqual(self.c.phase, 'idle')
        for kind, phase in [('activating', 'thinking'), ('listening', 'listening'), ('thinking', 'thinking'),
                            ('executing', 'executing'), ('speaking', 'speaking'), ('ready', 'idle'), ('off', 'offline')]:
            self.voice(kind)
            self.assertEqual(self.c.phase, phase, kind)
        self.voice('ready')
        self.assertTrue(self.c.status)

    def test_error_is_shown_then_clears(self):
        self.voice('ready')
        with patch.object(ctl.time, 'monotonic', return_value=1000.0):
            self.voice('error', 'تعذّر الصوت: TimeoutError')
            self.assertEqual(self.c.phase, 'error')
        self.assertEqual(self.c.chat.rows()[-1]['role'], 'error')
        with patch.object(ctl.time, 'monotonic', return_value=1010.0):
            self.c._resolve_phase()
            self.assertEqual(self.c.phase, 'idle')

    def test_level_is_clamped_and_reset(self):
        self.voice('listening')
        self.voice('level', '1.7')
        self.assertEqual(self.c.level, 1.0)
        self.voice('level', 'nonsense')
        self.assertEqual(self.c.level, 1.0)
        self.voice('thinking')
        self.assertEqual(self.c.level, 0.0)

    def test_live_captions_follow_the_speaker(self):
        self.voice('listening')
        self.voice('partial_heard', 'ميرا شغلي')
        self.assertEqual((self.c.caption, self.c.captionRole), ('ميرا شغلي', 'user'))
        self.voice('partial_reply', 'حاضر')
        self.assertEqual(self.c.captionRole, 'mira')
        self.voice('heard', 'ميرا شغلي الضو')
        self.voice('reply', 'شغّلت ضو المكتب')
        roles = [r['role'] for r in self.c.chat.rows()]
        self.assertEqual(roles[-2:], ['user', 'mira'])
        self.assertEqual(self.c.mood, 'proud')

    def test_tool_card_reports_the_real_status(self):
        self.voice('tool', json.dumps({'name': 'home_control', 'status': 'pending', 'summary': 'أُرسل ولم يتأكد'}))
        row = self.c.chat.rows()[-1]
        self.assertEqual((row['role'], row['status']), ('action', 'pending'))
        self.voice('tool', 'not json')
        self.assertEqual(self.c.chat.rows()[-1]['text'], 'not json')

    # ── typed requests ──────────────────────────────────────────────
    def test_typed_request_uses_the_brain_and_returns_to_idle(self):
        calls = []

        class Brain:
            @staticmethod
            def run_in_thread(text, emit, lang='ar', city=None):
                calls.append((text, lang, city))
                emit('thinking', '')
                emit('tool', json.dumps({'name': 'current_weather', 'status': 'ok', 'summary': 'Berlin 14°'}))
                emit('reply', 'الجو في برلين ١٤ درجة')
        with patch.dict('sys.modules', {'brain': Brain}):
            self.c.send('كيف الطقس؟')
        self.assertTrue(pump(lambda: self.c.chat.rows() and self.c.chat.rows()[-1]['role'] == 'mira'))
        self.assertEqual(calls[0][0], 'كيف الطقس؟')
        self.assertEqual([r['role'] for r in self.c.chat.rows()], ['user', 'action', 'mira'])
        self.assertEqual(self.c.phase, 'idle')

    def test_typed_request_without_brain_uses_the_fixed_router(self):
        routed = {'kind': 'home', 'message': 'أطفأت كل الأضواء المتاحة (3/3)', 'result': {'status': 'ok'}}
        with patch.dict('sys.modules', {'brain': None}), patch('command_router.dispatch', return_value=routed):
            self.c.send('أطفئي كل الأضواء')
            self.assertTrue(pump(lambda: self.c.chat.count >= 2))
        self.assertEqual(self.c.chat.rows()[-1]['status'], 'ok')
        self.assertEqual(self.c.phase, 'idle')

    def test_empty_and_oversized_messages_are_refused(self):
        self.c.send('   ')
        self.assertEqual(self.c.chat.count, 0)
        self.c.send('x' * 6001)
        self.assertEqual(self.c.chat.count, 0)
        self.assertEqual(self.toasts[-1][0], 'error')

    # ── voice controls ──────────────────────────────────────────────
    def test_talk_routes_to_echo_or_explains_why_not(self):
        self.c.bridge.online = False
        self.c.talk()
        self.assertEqual(self.toasts[-1][0], 'error')
        self.c.bridge.online = True
        self.voice('ready')
        self.c.talk()
        self.assertIn(('wake', 'wake_assistant_1'), self.c.bridge.commands)
        self.assertEqual(self.c.phase, 'thinking')
        self.voice('listening')
        self.c.talk()  # a second press while active stops the turn
        self.assertIn(('cancel',), self.c.bridge.commands)

    def test_echo_readbacks_populate_device_settings(self):
        entities = [FakeEntity(1, 'speaker'), FakeEntity(2, 'wake_threshold_1'), FakeEntity(3, 'mic_mute'),
                    FakeEntity(4, 'setup_page')]
        self.c._on_echo_connected(entities)
        self.assertTrue(self.c.echo['online'] and self.c.echo['setup'] and self.c.echo['mute_available'])
        self.assertFalse(self.c.echo['pair'])

        class State:
            def __init__(self, key, **kw):
                self.key = key
                self.__dict__.update(kw)
        self.c._on_echo_state(State(1, volume=0.45))
        self.c._on_echo_state(State(2, state=0.7))
        self.c._on_echo_state(State(3, state=True))
        self.assertEqual((self.c.echo['speaker_volume'], self.c.echo['wake_threshold'], self.c.echo['muted']), (45, 70, True))
        self.c._on_echo_error('غير متصل')
        self.assertFalse(self.c.echo['online'])
        self.assertEqual(self.c.services['echo'], 'offline')

    # ── home ────────────────────────────────────────────────────────
    def test_devices_expose_only_supported_controls(self):
        from review_fakes import SAMPLE_DEVICES
        rows = {r['entity_id']: r for r in self.c._devices_from(SAMPLE_DEVICES)}
        tv = rows['media_player.smart_tv_pro_2']
        self.assertTrue(tv['on_capable'] and tv['off_capable'] and tv['play_capable'] and tv['pause_capable'])
        self.assertFalse(tv['volume_capable'])  # the TCL reports volume but not VOLUME_SET
        self.assertTrue(rows['light.buro']['color_capable'])
        self.assertFalse(rows['light.desk']['color_capable'])
        self.assertTrue(rows['light.desk']['dimmable'])
        self.assertFalse(rows['light.hall']['available'])
        order = list(rows)
        self.assertEqual(order[-1], 'light.hall')  # unavailable devices sink to the end

    def test_home_list_updates_summary(self):
        from review_fakes import SAMPLE_DEVICES
        self.c._on_work('home_list', SAMPLE_DEVICES)
        self.assertEqual(self.c.home['lights_available'], 3)
        self.assertEqual(self.c.home['lights_on'], 2)
        self.assertEqual(self.c.home['tv']['entity_id'], 'media_player.smart_tv_pro_2')
        self.assertEqual(self.c.services['home'], 'online')
        self.c._on_work('home_list', {'status': 'error', 'error': 'خادم البيت غير متاح'})
        self.assertEqual(self.c.services['home'], 'offline')

    def test_home_action_reports_readback_not_request(self):
        with patch.object(self.c, 'refreshHome'):
            self.c._on_work('home_action', {'status': 'pending', 'entity_id': 'light.buro', 'observed_state': 'off'})
            self.assertEqual(self.c.chat.rows()[-1]['status'], 'pending')
            self.c._on_work('home_all', {'status': 'partial', 'confirmed': 2, 'total': 3, 'results': []})
            self.assertIn('2/3', self.c.chat.rows()[-1]['text'])
            self.assertEqual(self.toasts[-1][0], 'pending')

    # ── computer ────────────────────────────────────────────────────
    def test_computer_readings_and_catalog(self):
        self.c._on_pc('get_system_status', {'status': 'ok', 'output': json.dumps({'volume': 41.6, 'brightness': 80, 'wifi': True})})
        self.assertEqual((self.c.pc['volume'], self.c.pc['brightness'], self.c.pc['wifi']), (42, 80, True))
        self.c._on_pc('list_installed_apps', {'status': 'ok', 'output': 'org.kde.dolphin\tDolphin\nbad line\ncom.google.Chrome\tGoogle Chrome'})
        self.assertEqual([a['id'] for a in self.c.pc['apps']], ['org.kde.dolphin', 'com.google.Chrome'])
        self.c._on_pc('set_volume', {'status': 'pending', 'error': 'unverified'})
        self.assertEqual(self.c.chat.rows()[-1]['status'], 'pending')

    def test_volume_change_is_verified_by_reading_back(self):
        responses = [{'status': 'ok'}, {'status': 'ok', 'output': json.dumps({'volume': 30})}]
        with patch('moai_link.execute', side_effect=lambda *a: responses.pop(0)):
            self.assertEqual(self.c._pc_call('set_volume', {'value': '30'})['status'], 'ok')
        responses = [{'status': 'ok'}, {'status': 'ok', 'output': json.dumps({'volume': 55})}]
        with patch('moai_link.execute', side_effect=lambda *a: responses.pop(0)):
            self.assertEqual(self.c._pc_call('set_volume', {'value': '30'})['status'], 'pending')

    def test_open_app_rejects_non_catalog_ids(self):
        with patch.object(self.c, 'runPc') as run:
            self.c.openApp('rm -rf /')
            self.c.openApp('org.kde.dolphin')
        run.assert_called_once_with('open_app', {'app_id': 'org.kde.dolphin'})

    # ── owner-approved system actions ───────────────────────────────
    def _park(self, name='install_app', args=None):
        card = self.c.request_confirmation({'kind': 'moai', 'name': name, 'args': args or {'app_id': 'org.videolan.VLC'},
                                            'detail': 'VLC'})
        pump(lambda: self.c.actions.find(card['id']) >= 0)
        return card

    def test_a_parked_change_runs_only_after_the_owner_approves(self):
        import moai_tools
        calls = []

        def execute(name, args, confirmed=False):
            calls.append((name, args, confirmed))
            return {'status': 'pending', 'job': 'j1'}
        with patch.object(moai_tools, 'execute', side_effect=execute), \
                patch.object(moai_tools, 'wait_job', return_value={'status': 'ok', 'output': 'installed VLC', 'exit_code': 0}):
            card = self._park()
            self.assertEqual(self.c.actions.get(0)['stage'], 'ask')
            self.assertEqual(calls, [], 'parking runs nothing')
            self.c.approveAction(card['id'])
            self.assertTrue(pump(lambda: self.c.actions.get(0).get('stage') == 'ok', 3))
        self.assertEqual(calls, [('install_app', {'app_id': 'org.videolan.VLC'}, True)])
        self.assertIn('installed VLC', self.c.actions.get(0)['output'])
        self.c.approveAction(card['id'])     # one approval never runs twice
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.c.actions.get(0)['stage'], 'ok', 'a finished card keeps its real result')

    def test_only_known_moai_tools_can_be_parked(self):
        self.assertIsNone(self.c.request_confirmation({'kind': 'moai', 'name': 'rm_rf', 'args': {}}))
        self.assertIsNone(self.c.request_confirmation({'kind': 'command', 'name': 'install_app', 'args': {}}))
        self.assertEqual(self.c.actions.count, 0)

    def test_typed_yes_approves_and_no_cancels_without_asking_the_brain(self):
        import moai_tools
        with patch.object(moai_tools, 'execute', return_value={'status': 'ok', 'output': ''}) as execute, \
                patch.object(self.c, '_run_brain') as brain:
            card = self._park()
            self.c.send('نعم')
            self.assertTrue(pump(lambda: execute.called, 2))
            execute.assert_called_once_with('install_app', {'app_id': 'org.videolan.VLC'}, confirmed=True)
            card = self._park('fix_audio', {})
            self.c.send('لا')
            self.assertEqual(self.c.actions.get(self.c.actions.find(card['id']))['stage'], 'cancelled')
            self.c.send('نعم الساعة كم؟')        # a question, not an answer
            brain.assert_called_once()
        self.assertEqual(execute.call_count, 1)

    def test_spoken_yes_counts_only_from_a_later_turn(self):
        import moai_tools
        with patch.object(moai_tools, 'execute', return_value={'status': 'ok', 'output': ''}) as execute:
            self.voice('listening')
            self._park()
            self.voice('heard', 'نعم')          # the same turn that asked: not an approval
            pump(timeout=0.2)
            execute.assert_not_called()
            time.sleep(0.01)
            self.voice('listening')              # the owner's next turn
            self.voice('heard', 'ايوه أكيد')
            self.assertTrue(pump(lambda: execute.called, 2))

    def test_a_card_nobody_answers_expires_and_runs_nothing(self):
        import moai_tools
        with patch.object(moai_tools, 'execute') as execute:
            card = self._park()
            row = self.c.actions.find(card['id'])
            self.c.actions.update_key(card['id'], expires=1)
            self.c.pending._items[card['id']]['expires'] = 0
            self.c._tick_actions()
            self.assertEqual(self.c.actions.get(row)['stage'], 'expired')
            self.c.approveAction(card['id'])
            execute.assert_not_called()

    def test_launcher_pages_and_questions(self):
        sheets, filled = [], []
        self.c.showSheet.connect(sheets.append)
        self.c.prefill.connect(filled.append)
        with patch.object(self.c, 'systemAction') as action, patch.object(self.c, '_run_brain') as brain:
            self.c.handle_instance_command(b'open:' + json.dumps({'panel': 'device'}).encode())
            self.c.handle_instance_command(b'open:' + json.dumps({'panel': 'chat', 'ask': 'حدّث النظام'}).encode())
            self.c.handle_instance_command(b'open:not json')
            pump(lambda: action.called, 1)
        self.assertEqual(sheets, ['system', '', ''])
        self.assertEqual(filled, ['حدّث النظام'])
        brain.assert_not_called()               # a moos:// link never sends for the owner
        action.assert_called_once_with('device_report')

    def test_store_actions_are_parked_not_run(self):
        import moai_tools
        with patch.object(moai_tools, 'execute') as execute:
            self.c.storeAction('install_app', 'org.videolan.VLC')
            self.c.storeAction('install_app', 'VLC; rm -rf ~')
            self.c.storeAction('reboot', 'org.videolan.VLC')
            pump(lambda: self.c.actions.count == 1, 1)
        self.assertEqual(self.c.actions.count, 1)
        execute.assert_not_called()

    def test_a_computer_without_an_echo_gets_typed_mira(self):
        import mira_bridge
        with patch.object(mira_bridge, 'paired', return_value=False):
            c = ctl.Controller(bridge_class=mira_bridge.Bridge)
            c.start()
            pump(lambda: c.services['echo'] == 'off', 1)
        self.assertEqual(c.services['echo'], 'off')
        self.assertFalse(c.echo['paired'])
        self.assertFalse(c.bridge.thread.is_alive(), 'no connection attempts without a paired Echo')
        self.assertNotEqual(c.phase, 'error')

    def test_without_an_echo_talk_uses_this_computer(self):
        import mira_bridge
        with patch.object(mira_bridge, 'paired', return_value=False):
            c = ctl.Controller(bridge_class=mira_bridge.Bridge)
            c.start()
            pump(lambda: c.services['echo'] == 'off', 1)
        sheets = []
        c.showSheet.connect(sheets.append)
        with patch.object(c, '_gemini_state', return_value='missing'):
            c.talk()
        self.assertEqual(sheets, ['settings'], 'no key: say where to add one')
        self.assertIsNone(c.desk)
        started = []
        with patch.object(c, '_gemini_state', return_value='set'), \
                patch('desk_voice.DeskVoice.talk', lambda self: started.append(self.lang)):
            c.talk()
        self.assertEqual(started, ['ar'])
        self.assertIn('ميكروفون', c.status)
        c.shutdown()

    def test_a_user_keeps_and_tests_his_own_gemini_key(self):
        import brain
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'mo-dot' / 'gemini.json'
            with patch.object(brain, 'GEMINI_CONFIG', path), \
                    patch.object(self.c, '_test_gemini', return_value={'status': 'ok'}):
                self.c.saveGeminiKey('not a key')
                self.assertFalse(path.exists())
                self.c.saveGeminiKey('A' * 39)
                self.assertEqual(oct(path.stat().st_mode & 0o777), '0o600')
                self.assertEqual(json.loads(path.read_text())['api_key'], 'A' * 39)
                self.assertTrue(pump(lambda: self.c.brainKey == 'ok', 2))

    # ── preferences ─────────────────────────────────────────────────
    def test_preferences_persist(self):
        self.c.setFace('holo')
        self.c.setLang('en')
        self.c.setMotion(False)
        self.c.setVoiceName('Kore')
        self.c.setVoiceName('Unknown')
        again = ctl.Controller(bridge_class=FakeBridge)
        self.assertEqual((again.faceStyle, again.lang, again.motion, again.voiceName), ('holo', 'en', False, 'Kore'))
        self.assertEqual(again.s['send'], 'Send')
        again.toggleFace()
        self.assertEqual(again.faceStyle, 'rose')

    def test_invalid_city_is_refused(self):
        self.c.saveCity('Berlin; rm -rf')
        self.assertEqual(self.toasts[-1][0], 'error')
        self.assertEqual(self.c.city, '')

    def test_text_attachment_limits(self):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
            f.write('hello')
        self.assertEqual(self.c.readTextFile(f.name), 'hello')
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
            f.write('x' * 13000)
        self.assertEqual(self.c.readTextFile(f.name), '')
        self.assertEqual(self.toasts[-1][0], 'error')

    def test_mood_reading(self):
        self.assertEqual(ctl.mood_for('عذراً، تعذّر التنفيذ'), 'sad')
        self.assertEqual(ctl.mood_for('شغّلت الضو'), 'proud')
        self.assertEqual(ctl.mood_for('أهلا محمد'), 'happy')
        self.assertEqual(ctl.mood_for('أي ضو تقصد؟'), 'curious')
        self.assertEqual(ctl.mood_for('anything', 'error'), 'sad')


if __name__ == '__main__':
    unittest.main()
