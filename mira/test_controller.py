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
    def test_mouth_packets_refresh_equal_levels_and_reject_nonfinite_values(self):
        self.voice('speaking')
        self.voice('mouth_level', '0.3')
        count = self.c.mouthPacket
        self.voice('mouth_level', '0.3')
        self.assertEqual(self.c.mouthPacket, count + 1)
        self.assertAlmostEqual(self.c.mouthLevel, 0.3)
        for value in ('nan', 'inf', 'invalid'):
            self.voice('mouth_level', value)
        self.assertEqual(self.c.mouthPacket, count + 1)
        self.voice('ready')
        self.assertEqual(self.c.mouthLevel, 0)
        self.voice('level', '0.4')
        self.assertAlmostEqual(self.c.mouthLevel, 0.22)

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

    def test_a_brain_card_says_what_the_yes_does(self):
        """The consequence tools.py passes reaches the card: a restart asked for in chat or by voice
        must warn about unsaved work, not show only its name. A page card keeps its own words."""
        import asyncio
        import moai_tools
        from tools import ToolContext, _moai_tool
        ctx = ToolContext(emit=lambda *_: None, request_confirmation=self.c.request_confirmation)
        will = {'category': 'user_confirm', 'consequence_ar': 'يضيع ما لم يُحفظ.',
                'consequence_en': 'Open apps close and unsaved work is lost.'}
        with patch.object(moai_tools, 'execute', return_value={'status': 'confirm', 'category': 'user_confirm'}), \
                patch.object(moai_tools, 'names', return_value={'restart_computer'}), \
                patch.object(moai_tools, 'meta', return_value=will):
            asked = asyncio.run(_moai_tool('restart_computer', {}, ctx))
            self.assertEqual(asked.get('awaiting'), 'owner_confirmation', asked)
            self.assertTrue(pump(lambda: self.c.actions.count > 0))
            self.assertIn('يضيع ما لم يُحفظ', self.c.actions.get(0)['detail'])
            # both languages travel with the card: the English window reads the English sentence
            self.c.setLang('en')
            asyncio.run(_moai_tool('restart_computer', {}, ctx))
            self.assertTrue(pump(lambda: self.c.actions.count > 1))
            self.assertIn('unsaved work is lost', self.c.actions.get(0)['detail'])
            self.assertNotIn('يضيع', self.c.actions.get(0)['detail'])
        # A page's own card writes its sentence into its detail: nothing is added, and never twice.
        card = self._park()
        self.assertEqual(self.c.actions.get(self.c.actions.find(card['id']))['detail'], 'VLC')
        card = self.c.request_confirmation({'kind': 'moai', 'name': 'fix_audio', 'args': {}, 'origin': 'system',
                                            'detail': 'The page says it', **will})
        self.assertTrue(pump(lambda: self.c.actions.find(card['id']) >= 0))
        self.assertEqual(self.c.actions.get(self.c.actions.find(card['id']))['detail'], 'The page says it')

    # ── what the pages hear about the cards they raised ─────────────
    def _pages_listening(self):
        heard = {'update': [], 'changed': [], 'finished': []}

        class Broken:                     # one page's bug must not keep the others from hearing
            def action_update(self, *args):
                raise RuntimeError('page bug')

        class UpdatePage:                 # the PC and System pages' hook
            def action_update(self, card_id, stage, summary, output):
                heard['update'].append((card_id, stage))

        class ChangedPage:                # the Apps and Connect pages' hook
            def action_changed(self, card_id, name, stage):
                heard['changed'].append((card_id, name, stage))
        self.c._pages = {'broken': Broken(), 'update': UpdatePage(), 'changed': ChangedPage()}
        self.c.actionFinished.connect(lambda name, outcome: heard['finished'].append((name, outcome)))
        return heard

    def test_every_page_hears_how_its_card_ran(self):
        import moai_tools
        heard = self._pages_listening()
        with patch.object(moai_tools, 'execute', return_value={'status': 'ok', 'output': 'done'}):
            card = self._park()
            self.assertTrue(self.c.card_waiting(card['id']))
            self.c.approveAction(card['id'])
            self.assertFalse(self.c.card_waiting(card['id']), 'approved: no longer in front of the owner')
            self.assertTrue(pump(lambda: len(heard['update']) == 2, 3))
        self.assertEqual(heard['update'], [(card['id'], 'running'), (card['id'], 'ok')])
        self.assertEqual(heard['changed'], [(card['id'], 'install_app', 'running'), (card['id'], 'install_app', 'ok')])
        self.assertEqual(heard['finished'], [('install_app', 'ok')])
        self.assertFalse(self.c.card_waiting(''))

    def test_cancelled_expired_and_still_running_reach_the_pages(self):
        heard = self._pages_listening()
        card = self._park()
        self.c.rejectAction(card['id'])                                   # his Cancel
        self.assertEqual(heard['update'][-1], (card['id'], 'cancelled'))
        self.assertEqual(heard['changed'][-1], (card['id'], 'install_app', 'cancelled'))
        card = self._park('fix_audio', {})                                # nobody answered in time
        self.c.actions.update_key(card['id'], expires=1)
        self.c.pending._items[card['id']]['expires'] = 0
        self.c._tick_actions()
        self.assertEqual(heard['update'][-1], (card['id'], 'expired'))
        card = self._park('fix_audio', {})                                # an approval that came too late
        self.c.pending._items[card['id']]['expires'] = 0
        self.c.approveAction(card['id'])
        self.assertEqual(heard['update'][-1], (card['id'], 'expired'))
        with patch.object(self.c, '_run_brain'):                          # his typed «لا»
            card = self._park('fix_audio', {})
            self.c.send('لا')
        self.assertEqual(heard['update'][-1], (card['id'], 'cancelled'))
        self.assertEqual(heard['finished'], [('install_app', 'cancelled'), ('fix_audio', 'expired'),
                                             ('fix_audio', 'expired'), ('fix_audio', 'cancelled')])
        # A job that outlived its wait: the pages that follow every stage hear it; the others and the
        # Workbench keep following on their own (nothing will report its end).
        card = self._park('fix_audio', {})
        with patch.object(self.c.worker, 'run'):
            self.c.approveAction(card['id'])
        changed, finished = len(heard['changed']), len(heard['finished'])
        self.c._on_action_done(card['id'], {'status': 'pending', 'name': 'fix_audio'})
        self.assertEqual(heard['update'][-1], (card['id'], 'still-running'))
        self.assertEqual((len(heard['changed']), len(heard['finished'])), (changed, finished))
        # A late Cancel (a notification button) never reports a running job as cancelled.
        self.c.rejectAction(card['id'])
        self.assertEqual(heard['update'][-1], (card['id'], 'still-running'))
        self.assertEqual(self.c.actions.get(self.c.actions.find(card['id']))['stage'], 'running')

    def test_a_job_that_failed_on_the_worker_is_still_named(self):
        heard = self._pages_listening()
        card = self._park('fix_audio', {})
        with patch.object(self.c.worker, 'run'):
            self.c.approveAction(card['id'])
        self.c._on_action_done(card['id'], {'status': 'error', 'error': 'TimeoutError'})
        self.assertEqual(heard['changed'][-1], (card['id'], 'fix_audio', 'error'))
        self.assertEqual(heard['finished'], [('fix_audio', 'error')])

    def test_a_typed_no_also_denies_the_agents_waiting_requests(self):
        self.c.actions.insert_first({'aid': 'agent-x', 'kind': 'agent', 'name': 'agent_run', 'title': 't', 'detail': '',
                                     'reason': '', 'stage': 'ask', 'category': 'agent_confirm', 'summary': '',
                                     'output': '', 'started': 0, 'expires': 0, 'origin': 'agent'})
        with patch.object(self.c, '_answer_agent') as answer, patch.object(self.c, '_run_brain') as brain:
            card = self._park()
            self.c.send('لا')
        answer.assert_called_once_with('agent-x', 'deny')
        brain.assert_not_called()
        self.assertEqual(self.c.actions.get(self.c.actions.find(card['id']))['stage'], 'cancelled')

    def test_a_close_card_acts_on_the_exact_window(self):
        import desktop_tools
        card = self.c.request_confirmation({'kind': 'desktop', 'name': 'close_window', 'origin': 'pc', 'detail': 'x',
                                            'args': {'query': '~ : bash — Konsole', 'id': '{b-2}'}})
        item = self.c.pending.get(card['id'])
        self.assertEqual(item['payload']['args'], {'query': '~ : bash — Konsole', 'id': '{b-2}'})
        bad = self.c.request_confirmation({'kind': 'desktop', 'name': 'close_window',
                                           'args': {'query': 'Konsole', 'id': '"); workspace.x(); ("'}})
        self.assertEqual(self.c.pending.get(bad['id'])['payload']['args'], {'query': 'Konsole'})
        with patch.object(desktop_tools, 'close_window_id', return_value={'status': 'ok', 'title': 't'}) as by_id, \
                patch.object(desktop_tools, 'close_window') as by_title:
            out = self.c._execute_action(item['payload'])
        by_id.assert_called_once_with('{b-2}', '~ : bash — Konsole')
        by_title.assert_not_called()
        self.assertEqual((out['status'], out['kind'], out['name']), ('ok', 'desktop', 'close_window'))
        # a card that names a window by id never falls back to a title another window may share
        with patch.object(desktop_tools, 'close_window_id', None), patch.object(desktop_tools, 'close_window') as by_title:
            out = self.c._execute_action(item['payload'])
        by_title.assert_not_called()
        self.assertEqual(out['status'], 'error')

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

    def test_the_key_test_asks_the_model_typed_chat_uses(self):
        with patch('brain.probe_gemini', return_value={'status': 'ok', 'model': 'm', 'elapsed_ms': 5}) as probe:
            self.assertEqual(self.c._test_gemini()['status'], 'ok')
        probe.assert_called_once_with()

    def test_a_failed_key_gives_the_page_its_reason_and_the_owner_words(self):
        import brain
        heard = []

        class BrainPage:
            def keyChecked(self, state, reason):
                heard.append((state, reason))
        self.c._pages['brain'] = BrainPage()
        self.c._on_work('brain_key', {'status': 'error', 'model': 'm', 'reason': 'auth',
                                      'error': 'API key not valid: AIzaSyEXAMPLE'})
        self.assertEqual(heard, [('failed', 'auth')], 'the page hears the reason before QML does')
        self.assertEqual(self.c.brainKey, 'failed')
        self.assertEqual(self.toasts[-1], ('error', self.c.s['brain_key_failed'] + ' · ' + brain.REASONS['auth'][0]))
        self.c._on_work('brain_key', {'status': 'error', 'error': 'ConnectionError: AIzaSyEXAMPLE'})
        self.assertEqual(heard[-1], ('failed', ''), 'no classified reason: the page runs its own test')
        self.assertEqual(self.toasts[-1], ('error', self.c.s['brain_key_failed']), "the provider's text never shows")
        self.c._on_work('brain_key', {'status': 'ok', 'model': 'm'})
        self.assertEqual(heard[-1], ('ok', ''))

    # ── what the conversation shows ─────────────────────────────────
    def test_the_english_window_shows_the_english_action_row(self):
        event = json.dumps({'name': 'set_volume', 'status': 'ok', 'summary': 'صوت الكمبيوتر · تم وتأكدت',
                            'summary_en': 'Computer volume · done and confirmed'}, ensure_ascii=False)
        self.voice('tool', event)
        self.assertEqual(self.c.chat.rows()[-1]['text'], 'صوت الكمبيوتر · تم وتأكدت')
        self.c.setLang('en')
        self.voice('tool', event)
        self.assertEqual(self.c.chat.rows()[-1]['text'], 'Computer volume · done and confirmed')
        self.voice('tool', json.dumps({'name': 'x', 'status': 'ok', 'summary': 'عربي فقط'}, ensure_ascii=False))
        self.assertEqual(self.c.chat.rows()[-1]['text'], 'عربي فقط', 'no English half: the one the tool wrote')
        self.voice('tool', '[1, 2]')                  # not an object: shown as its text, never a crash
        self.assertEqual(self.c.chat.rows()[-1]['text'], '[1, 2]')

    def test_opening_another_chat_asks_each_voice_to_forget_its_context(self):
        from types import SimpleNamespace
        import live_voice
        self.assertTrue(callable(getattr(live_voice.LiveVoice, 'forget_context', None)),
                        'the real voice must offer it, or opening a chat would silently keep the old context')
        forgot = []
        self.c.bridge.voice = SimpleNamespace(forget_context=lambda: forgot.append('echo'))
        self.c.desk = SimpleNamespace(voice=SimpleNamespace(forget_context=lambda: forgot.append('desk')))
        self.c.reload_chat()
        self.assertEqual(forgot, ['echo', 'desk'])
        # A voice without that method is left alone: its session's fields belong to the voice thread.
        link = SimpleNamespace(dirty=False, idle_closed=False)
        self.c.bridge.voice, self.c.desk = SimpleNamespace(link=link), None
        self.c.reload_chat()
        self.assertEqual((link.dirty, link.idle_closed), (False, False))

    def test_a_started_agent_task_refreshes_the_workbench_and_reads_approvals_fast(self):
        loads = []

        class Workbench:
            def loadTasks(self):
                loads.append('tasks')

            def refresh(self):
                loads.append('refresh')
        self.c._pages['workbench'] = Workbench()
        with patch.object(self.c.inbox, 'busy') as busy, patch.object(self.c.inbox, 'poll') as poll, \
                patch.object(ctl.QTimer, 'singleShot') as later:
            self.voice('workbench', json.dumps({'task': 'task-7f3a', 'status': 'running'}))
            self.voice('workbench', json.dumps({'task': '../x y', 'status': 'running'}))
            self.voice('workbench', 'not json')
            self.assertEqual(loads, ['tasks', 'tasks', 'tasks'])
            busy.assert_called_once_with(True, 'task:task-7f3a')
            poll.assert_called_once_with()
            wait, context, release = later.call_args[0]
            self.assertEqual(wait, ctl.Controller.AGENT_TASK_WATCH_MS, 'the fast reads are bounded')
            self.assertIs(context, self.c.inbox, 'the release dies with the inbox, never after it')
            release()
            busy.assert_called_with(False, 'task:task-7f3a')

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

    # ── how much she moves (visual_tier) ────────────────────────────
    def test_motion_follows_the_visual_policy_strongest_reason_first(self):
        import visual_tier as vt
        cases = [   # policy, stored switch, then motion, motionLocked, motionScale
            (vt.Policy('off', 'off', 'flagship'), True, False, True, 0.0),
            (vt.Policy('still', 'software-scene-graph', 'flagship', True, None, True), True, False, True, 1.0),
            (vt.Policy('still', 'tier', 'essential'), None, False, False, 0.4),
            (vt.Policy('still', 'tier', 'essential'), True, True, False, 0.4),
            (vt.Policy('still', 'software-renderer', 'flagship', software=True), None, False, False, 1.0),
            (vt.Policy('full', 'tier', 'flagship', factor=0.75), False, False, False, 0.75),
            (vt.Policy('full', 'default'), None, True, False, 1.0),
        ]
        for policy, stored, motion, locked, scale in cases:
            with self.subTest(reason=policy.reason, stored=stored):
                QSettings('MoOS', 'Mira').clear()
                if stored is not None:
                    QSettings('MoOS', 'Mira').setValue('visual_motion', stored)
                with patch.object(vt, 'policy', return_value=policy):
                    c = ctl.Controller(bridge_class=FakeBridge)
                self.assertEqual((c.motion, c.motionLocked, c.motionScale), (motion, locked, scale))

    def test_a_locked_motion_switch_is_not_stored_and_says_why(self):
        import visual_tier as vt
        with patch.object(vt, 'policy', return_value=vt.Policy('still', 'software-scene-graph', software=True)):
            c = ctl.Controller(bridge_class=FakeBridge)
        seen = []
        c.motionChanged.connect(lambda: seen.append(c.motion))
        c.setMotion(True)
        self.assertEqual(seen, [False], 'the switch is told to return to off')
        self.assertFalse(QSettings('MoOS', 'Mira').contains('visual_motion'))
        self.assertIn('ساكنة', c.motionPolicy)
        c.setLang('en')
        self.assertIn('still', c.motionPolicy)

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

    def test_paused_wake_health_never_claims_audio_is_being_received(self):
        for language, muted_label in (('ar', 'الميكروفون مكتوم'), ('en', 'Microphone muted')):
            self.c.setLang(language)
            for reason in ('muted', 'missing', 'unavailable', 'unknown', 'monitor_refused'):
                with self.subTest(language=language, reason=reason):
                    health = {'state': reason, 'frames_per_second': 99,
                              'last_match_at': time.time()}
                    with patch.object(Path, 'read_text', return_value=json.dumps(health)):
                        self.c._check_local_wake()
                    label = self.c.wake['state']
                    self.assertNotIn('99', label)
                    self.assertNotIn('Heard', label)
                    self.assertNotIn('التقط', label)
                    if reason == 'muted':
                        self.assertIn(muted_label, label)


if __name__ == '__main__':
    unittest.main()
