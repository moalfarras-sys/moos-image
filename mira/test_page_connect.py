"""The Connect page: read-backs mapped honestly, every button reaches its executor or its fixed route,
every system change goes to the owner's card, and every note ages or yields to a newer read.
No real service, route, Echo or phone is touched: every backend is a stand-in, and the page's worker
threads are run in-line. The last class loads the real page in Main.qml (offscreen) and presses its
buttons, so a wrong wire (Stop calling Start, a fast toggle sending the wrong value) fails here.
"""
import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
os.environ['MIRA_TEST_MODE'] = '1'
_config = tempfile.TemporaryDirectory(prefix='mira-connect-test-')
os.environ.setdefault('XDG_CONFIG_HOME', _config.name)

from PySide6.QtCore import QCoreApplication, QMetaObject, QObject, Qt, QUrl, Signal, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import i18n  # noqa: E402
from pages import base  # noqa: E402
from pages import connect  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])
ROOT = Path(__file__).resolve().parent

# The schemas this branch ships decide which remote actions are cards (the executor's own rule).
_spec = importlib.util.spec_from_file_location('connect_test_schemas',
                                               ROOT.parent / 'system_files/usr/lib/moai/moai_tool_schemas.py')
SCHEMAS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SCHEMAS)
TOOLS = {'remote_control', 'fast_remote', 'install_openclaw', 'install_app', 'remote_anywhere', 'open_app'}


class FakeHost(QObject):
    toast = Signal(str, str)
    showSheet = Signal(str)
    prefill = Signal(str)

    def __init__(self, lang='ar', card=True):
        super().__init__()
        self.lang = lang
        self.s = i18n.table(lang)
        self.cards = []
        self.card = card
        self.toasts = []
        self.sheets = []
        self.toast.connect(lambda kind, text: self.toasts.append((kind, text)))
        self.showSheet.connect(self.sheets.append)

    def request_confirmation(self, item):
        self.cards.append(item)
        return {'id': f'card-{len(self.cards)}'} if self.card else None


def inline(page):
    """Run the page's threaded work in-line (with base.run's error shaping) so results land at once."""
    page.ran = []

    def run(tag, fn, *args, **kwargs):
        page.ran.append(tag)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            result = {'status': 'error',
                      'error': str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__}
        page._deliver(tag, result)
    page.run = run
    return page


def remote(**fields):
    result = {'status': 'ok', 'active': False, 'pipewire': True, 'portal': True, 'fast': False}
    result.update(fields)
    return result


class Clock:
    """time.monotonic for the page, moved by hand."""
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


QUICK = {'online': True, 'remote': {'active': True, 'pipewire': True, 'portal': False}, 'agents': {}}
CONFIG = {'telegram': {'enabled': True, 'has_token': True, 'policy': 'allowlist', 'allow': ['111', '222']},
          'cloud': {'has_key': True}}
SCAN = {'compatibility': {'kdeconnect': False, 'kvm': True}, 'remote': QUICK['remote']}


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {'XDG_STATE_HOME': self.state.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.state.cleanup)

    def test_remote_reads_quick_and_the_fast_journal(self):
        with mock.patch.object(connect.moai_tools, 'get', return_value=QUICK) as get:
            result = connect.read_remote()
        get.assert_called_once_with('/quick', timeout=8)
        self.assertEqual(result, {'status': 'ok', 'active': True, 'pipewire': True, 'portal': False, 'fast': False})
        journal = Path(self.state.name) / 'moos/fast-remote.on'
        journal.parent.mkdir()
        journal.write_text('on\n')
        with mock.patch.object(connect.moai_tools, 'get', return_value=QUICK):
            self.assertTrue(connect.read_remote()['fast'])

    def test_fast_mode_being_applied_is_not_on(self):
        journal = Path(self.state.name) / 'moos/fast-remote.on'
        journal.parent.mkdir()
        journal.write_text('applying\n')                 # moos-fast-remote deletes it if applying fails
        self.assertFalse(connect.fast_remote_on())
        journal.unlink()
        journal.mkdir()                                   # unreadable as text: not on
        self.assertFalse(connect.fast_remote_on())

    def test_remote_error_and_wrong_shape(self):
        with mock.patch.object(connect.moai_tools, 'get', return_value={'error': 'moai_control_unreachable'}):
            self.assertEqual(connect.read_remote()['error'], 'moai_control_unreachable')
        with mock.patch.object(connect.moai_tools, 'get', return_value={'online': True}):
            self.assertEqual(connect.read_remote(), {'status': 'error', 'error': 'shape', 'fast': False})

    def test_channels_come_from_the_configuration_only(self):
        with mock.patch.object(connect.moai_agent, 'get', return_value=CONFIG) as get, \
             mock.patch.object(connect, 'agent_installed', return_value=False):
            result = connect.read_channels()
        get.assert_called_once_with('/api/config')      # never /api/channels (it starts the gateway)
        self.assertEqual(result['telegram'], {'enabled': True, 'has_token': True, 'policy': 'allowlist', 'allowed': 2})
        self.assertFalse(result['engine'])
        self.assertNotIn('111', repr(result))             # the allow list's accounts are counted, never shown

    def test_channels_error_and_unknown_policy(self):
        with mock.patch.object(connect.moai_agent, 'get', return_value={'error': 'agent_unreachable'}), \
             mock.patch.object(connect, 'agent_installed', return_value=True):
            result = connect.read_channels()
        self.assertEqual((result['status'], result['error'], result['engine']), ('error', 'agent_unreachable', True))
        odd = {'telegram': {'enabled': False, 'has_token': False, 'policy': 'open'}}
        with mock.patch.object(connect.moai_agent, 'get', return_value=odd), \
             mock.patch.object(connect, 'agent_installed', return_value=False):
            self.assertEqual(connect.read_channels()['telegram']['policy'], 'pairing')

    def test_phone_list_is_parsed_in_the_c_locale(self):
        out = ('- iPhone von Mo: d65b0e3a_6f18 (paired and reachable)\n'
               '- Old tablet: abc_123 (paired)\n'
               '- Neighbour: zz_9 (reachable)\n'
               '- Odd: -x (paired)\n'
               '3 devices found\n')
        with mock.patch.object(connect.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=out, stderr='')) as run:
            devices, error = connect.list_phones()
        argv, kwargs = run.call_args[0][0], run.call_args[1]
        self.assertEqual(argv[1:], ['--list-devices'])
        self.assertEqual(kwargs['env']['LC_ALL'], 'C')
        self.assertEqual(error, '')
        self.assertEqual(devices, [
            {'id': 'd65b0e3a_6f18', 'name': 'iPhone von Mo', 'paired': True, 'reachable': True},
            {'id': 'abc_123', 'name': 'Old tablet', 'paired': True, 'reachable': False},
            {'id': 'zz_9', 'name': 'Neighbour', 'paired': False, 'reachable': True}])
        with mock.patch.object(connect.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='x')):
            self.assertEqual(connect.list_phones(), (None, 'exit_1'))
        with mock.patch.object(connect.subprocess, 'run', side_effect=OSError('gone')):
            self.assertEqual(connect.list_phones(), (None, 'OSError'))

    def test_phone_prefers_the_image_app_and_reads_devices_only_when_its_service_runs(self):
        entry = Path(self.state.name) / 'org.kde.kdeconnect.app.desktop'
        entry.write_text('[Desktop Entry]\n')
        cli = Path(self.state.name) / 'kdeconnect-cli'
        cli.write_text('')
        devices = [{'id': 'a_1', 'name': 'Phone', 'paired': True, 'reachable': True}]
        with mock.patch.object(connect, 'PHONE_ENTRY', entry), mock.patch.object(connect, 'PHONE_CLI', cli), \
             mock.patch.object(connect.moai_tools, 'get', return_value=SCAN), \
             mock.patch.object(connect, '_daemon_running', return_value=True), \
             mock.patch.object(connect, 'list_phones', return_value=(devices, '')):
            result = connect.read_phone()
        self.assertEqual((result['status'], result['system'], result['local'], result['running'], result['listed']),
                         ('ok', True, False, True, True))
        self.assertEqual(result['devices'], devices)
        with mock.patch.object(connect, 'PHONE_ENTRY', entry), mock.patch.object(connect, 'PHONE_CLI', cli), \
             mock.patch.object(connect.moai_tools, 'get', return_value=SCAN), \
             mock.patch.object(connect, '_daemon_running', return_value=False), \
             mock.patch.object(connect, 'list_phones') as listing:
            result = connect.read_phone()
        listing.assert_not_called()              # a stopped service is never woken to list phones
        self.assertEqual((result['running'], result['listed'], result['devices']), (False, False, []))

    def test_phone_found_outside_the_image_is_local_and_never_a_store_install(self):
        missing = Path(self.state.name) / 'none.desktop'
        with mock.patch.object(connect, 'PHONE_ENTRY', missing), \
             mock.patch.object(connect.moai_tools, 'get', return_value={'compatibility': {'kdeconnect': True}}):
            result = connect.read_phone()
        self.assertEqual((result['system'], result['local']), (False, True))
        self.assertNotIn('flatpak', result)
        with mock.patch.object(connect, 'PHONE_ENTRY', missing), \
             mock.patch.object(connect.moai_tools, 'get', return_value={'compatibility': {'kdeconnect': False}}):
            self.assertEqual((connect.read_phone()['system'], connect.read_phone()['local']), (False, False))
        with mock.patch.object(connect, 'PHONE_ENTRY', missing), \
             mock.patch.object(connect.moai_tools, 'get', return_value={'error': 'moai_control_unreachable'}):
            result = connect.read_phone()
        self.assertEqual((result['status'], result['error']), ('error', 'moai_control_unreachable'))

    def test_ring_runs_in_the_c_locale_and_reports_the_cli_result(self):
        with mock.patch.object(connect.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')) as run:
            self.assertEqual(connect.ring_phone('a_1'), {'status': 'ok'})
        self.assertEqual(run.call_args[0][0][1:], ['--device=a_1', '--ring'])
        self.assertEqual(run.call_args[1]['env']['LC_ALL'], 'C')
        with mock.patch.object(connect.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='no device')):
            self.assertEqual(connect.ring_phone('a_1'), {'status': 'error', 'error': 'no device'})

    def test_has_tool_is_false_when_the_schemas_cannot_answer(self):
        with mock.patch.object(connect.moai_tools, 'names', side_effect=RuntimeError('broken')):
            self.assertFalse(connect.has_tool('remote_control'))
        with mock.patch.object(connect.moai_tools, 'names', return_value={'remote_control'}):
            self.assertTrue(connect.has_tool('remote_control'))


class PageCase(unittest.TestCase):
    """A page on a stand-in host. `tools` is what the installed executor offers."""
    tools = set()
    lang = 'ar'

    def setUp(self):
        self.host = FakeHost(self.lang)
        self.page = inline(connect.ConnectPage(self.host))
        self.addCleanup(self.page._follow_timer.stop)
        self.addCleanup(self.page._disarm_timer.stop)
        self.open_route = self.patch(connect.moos_routes, 'open_route', return_value={'status': 'ok'})
        self.patch(connect.moai_tools, 'names', return_value=set(self.tools))
        self.patch(connect.moai_tools, 'needs_confirmation', side_effect=SCHEMAS.needs_confirmation)
        self.patch(connect.moai_tools, 'consequence', side_effect=SCHEMAS.consequence)
        self.execute = self.patch(connect.moai_tools, 'execute', return_value={'status': 'ok'})
        self.read_remote = self.patch(connect, 'read_remote', return_value=remote())
        self.clock = Clock()
        self.patch(connect.time, 'monotonic', side_effect=self.clock)

    def patch(self, target, name, **kwargs):
        patcher = mock.patch.object(target, name, **kwargs)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    @property
    def state(self):
        return self.page.state

    def set_remote(self, **fields):
        self.page.update(remote={'known': True, 'active': False, 'pipewire': True, 'portal': True, 'fast': False, **fields})

    def follow_reads(self, *reads):
        """Deliver read-backs the follow timer would ask for, 2 s apart."""
        for read in reads:
            self.clock.now += 2
            self.read_remote.return_value = read
            self.page._follow_tick()


class FallbackTest(PageCase):
    """An installed image whose executor lacks the remote tools (today's station): moos-open routes."""

    def test_initial_state_renders_as_reading(self):
        self.assertFalse(self.state['remote']['known'])
        self.assertFalse(self.state['channels']['known'])
        self.assertFalse(self.state['phone']['known'])
        self.assertEqual((self.state['remote_busy'], self.state['remote_phase']), ('', ''))

    def test_refresh_maps_every_read(self):
        phone = {'status': 'ok', 'error': '', 'system': True, 'local': False, 'running': True, 'listed': True,
                 'devices': [{'id': 'a_1', 'name': 'Phone', 'paired': True, 'reachable': True}]}
        self.read_remote.return_value = remote(active=True, portal=False)
        with mock.patch.object(connect, 'read_channels', return_value={'status': 'ok', 'engine': True,
                               'telegram': {'enabled': False, 'has_token': True, 'policy': 'pairing', 'allowed': 0}}), \
             mock.patch.object(connect, 'read_phone', return_value=phone):
            self.page.refresh()
        self.assertEqual(self.state['remote'], {'known': True, 'active': True, 'pipewire': True, 'portal': False, 'fast': False})
        self.assertTrue(self.state['channels']['known'])
        self.assertTrue(self.state['channels']['engine'])
        self.assertTrue(self.state['channels']['telegram']['has_token'])
        self.assertEqual(self.state['phone']['devices'][0]['name'], 'Phone')
        self.assertFalse(self.state['loading'])

    def test_errors_become_words_never_raw_codes(self):
        self.read_remote.return_value = {'status': 'error', 'error': 'moai_control_unreachable', 'fast': False}
        with mock.patch.object(connect, 'read_channels', return_value={'status': 'error', 'error': 'agent_unreachable', 'engine': False}), \
             mock.patch.object(connect, 'read_phone', return_value={'status': 'error', 'error': 'odd_code', 'system': False}):
            self.page.refresh()
        self.assertFalse(self.state['remote']['known'])
        self.assertEqual(self.state['remote_error'], 'cn_err_control')
        self.assertEqual(self.state['channels']['error'], 'cn_err_agent')
        self.assertFalse(self.state['phone']['known'])
        self.assertEqual(self.state['phone']['error'], 'cn_err_read')     # an unknown code is a general word
        self.assertFalse(self.state['loading'])

    def test_start_needs_two_running_reads_in_a_row(self):
        self.set_remote(active=False)
        self.page.startRemote()
        self.open_route.assert_called_once_with('moos://remote/start')
        self.assertEqual((self.state['remote_busy'], self.state['remote_phase'], self.state['remote_note']),
                         ('start', 'dialog', 'cn_wait_dialog'))
        self.assertTrue(self.page._follow_timer.isActive())
        self.follow_reads(remote(active=True), remote(active=False), remote(active=True))
        self.assertEqual(self.state['remote_busy'], 'start')              # a unit that fell over is not "on"
        self.follow_reads(remote(active=True))
        self.assertEqual((self.state['remote_busy'], self.state['remote_note'], self.state['remote_tone']),
                         ('', 'cn_done_running', 'ok'))
        self.assertFalse(self.page._follow_timer.isActive())

    def test_an_unchanged_state_is_reported_as_not_confirmed(self):
        self.set_remote(active=True)
        self.page.setFastRemote(True)
        self.open_route.assert_called_once_with('moos://remote/fast-on')
        self.clock.now += 100
        self.follow_reads(remote(active=True, fast=False))
        self.assertEqual((self.state['remote_note'], self.state['remote_tone'], self.state['remote_busy']),
                         ('cn_not_confirmed', 'error', ''))

    def test_restart_by_route_says_only_that_it_was_sent_and_runs(self):
        self.set_remote(active=True)
        self.page.restartRemote()
        self.open_route.assert_called_once_with('moos://remote/restart')
        self.follow_reads(remote(active=True))
        self.assertEqual(self.state['remote_busy'], 'restart')
        self.follow_reads(remote(active=True))
        self.assertEqual(self.state['remote_note'], 'cn_done_restarted')
        self.assertIn('Restart sent', i18n.table('en')['cn_done_restarted'])

    def test_fast_off_route(self):
        self.set_remote(active=True, fast=True)
        self.page.setFastRemote(False)
        self.open_route.assert_called_once_with('moos://remote/fast-off')
        self.assertEqual((self.state['remote_note'], self.state['remote_phase']), ('cn_wait_readback', 'readback'))

    def test_one_remote_action_at_a_time(self):
        self.page.startRemote()
        self.page.setFastRemote(True)
        self.page.restartRemote()
        self.assertEqual(self.open_route.call_count, 1)

    def test_a_route_that_fails_is_said_in_words(self):
        self.open_route.return_value = {'status': 'error', 'error': 'route_not_allowed'}
        self.page.startRemote()
        self.assertEqual((self.state['remote_note'], self.state['remote_tone'], self.state['remote_busy']),
                         ('cn_route_failed', 'error', ''))
        self.assertIsNone(self.page._follow)
        kind, text = self.host.toasts[-1]
        self.assertEqual(kind, 'error')
        self.assertNotIn('route_not_allowed', text)
        self.assertIn(self.host.s['cn_err_route'], text)
        self.open_route.return_value = {'status': 'error', 'error': 'SomethingOdd'}
        self.page.openRemoteApp()
        self.assertEqual(self.host.toasts[-1], ('error', self.host.s['cn_route_failed']))

    def test_stop_needs_a_second_click_within_five_seconds(self):
        self.set_remote(active=True)
        self.page.stopRemote()
        self.open_route.assert_not_called()
        self.assertTrue(self.state['stop_armed'])
        self.clock.now += 6                                  # too late: this click arms again
        self.page.stopRemote()
        self.open_route.assert_not_called()
        self.assertTrue(self.state['stop_armed'])
        self.clock.now += 2                                  # within the window: stop
        self.page.stopRemote()
        self.open_route.assert_called_once_with('moos://remote/stop')
        self.assertFalse(self.state['stop_armed'])
        self.assertEqual(self.state['remote_busy'], 'stop')
        self.assertEqual(self.host.cards, [])

    def test_the_armed_stop_disarms_by_itself(self):
        self.page.stopRemote()
        self.assertTrue(self.page._disarm_timer.isActive())
        self.page._disarm()
        self.assertFalse(self.state['stop_armed'])
        self.page.stopRemote()                              # a fresh first click, not a confirmation
        self.open_route.assert_not_called()

    def test_stop_waiting_gives_the_buttons_back_while_a_dialog_is_open(self):
        self.page.startRemote()
        self.page.stopWaiting()
        self.assertEqual((self.state['remote_busy'], self.state['remote_note'], self.state['remote_phase']), ('', '', ''))
        self.assertFalse(self.page._follow_timer.isActive())
        self.page.setFastRemote(False)                      # a read-back needs no owner: nothing to stop waiting for
        self.page.stopWaiting()
        self.assertEqual(self.state['remote_busy'], 'fast-off')

    def test_open_routes(self):
        self.page.openRemoteApp()
        self.page.openRemoteSettings()
        self.page.setupChannels()
        self.assertEqual([c[0][0] for c in self.open_route.call_args_list],
                         ['moos://app/remote', 'moos://settings/remote', 'moos://settings/assistant'])
        for call in self.open_route.call_args_list:     # every route the page opens is on moos_routes' list
            self.assertTrue(connect.moos_routes.allowed(call[0][0]), call)

    def test_whatsapp_without_the_agent_tool_opens_the_assistant_settings(self):
        self.page.update(channels={**self.state['channels'], 'known': True, 'engine': False})
        self.page.whatsappLogin()
        self.page.setupAgent()
        self.assertEqual([c[0][0] for c in self.open_route.call_args_list],
                         ['moos://settings/assistant', 'moos://settings/assistant'])
        self.assertEqual(self.host.cards, [])
        self.open_route.reset_mock()
        self.page.update(channels={**self.state['channels'], 'engine': True})
        self.page.whatsappLogin()
        self.open_route.assert_called_once_with('moos://agent/whatsapp-login')


class ExecutorTest(PageCase):
    """An image whose schemas declare remote_control, fast_remote and install_openclaw (this branch)."""
    tools = TOOLS

    def test_start_is_an_owner_card_and_the_read_back_confirms_it(self):
        self.set_remote(active=False)
        self.page.startRemote()
        self.open_route.assert_not_called()
        card = self.host.cards[-1]
        self.assertEqual((card['kind'], card['name'], card['args'], card['origin']),
                         ('moai', 'remote_control', {'value': 'on'}, 'connect'))
        self.assertEqual(card['detail'], self.host.s['cn_card_start'])
        self.assertEqual((self.state['remote_busy'], self.state['remote_phase'], self.state['remote_note']),
                         ('start', 'card', 'cn_card_waiting'))
        self.follow_reads(remote(active=True), remote(active=True))
        self.assertEqual((self.state['remote_busy'], self.state['remote_note']), ('', 'cn_done_running'))

    def test_stop_is_an_owner_card_without_the_double_click(self):
        self.set_remote(active=True)
        self.page.stopRemote()
        self.assertFalse(self.state['stop_armed'])
        card = self.host.cards[-1]
        self.assertEqual((card['name'], card['args']), ('remote_control', {'value': 'off'}))
        self.assertIn('next boot', i18n.table('en')['cn_card_stop'])
        self.assertEqual(self.state['remote_busy'], 'stop')
        self.open_route.assert_not_called()

    def test_fast_on_is_a_card_that_says_what_it_changes(self):
        self.set_remote(active=True)
        self.page.setFastRemote(True)
        card = self.host.cards[-1]
        self.assertEqual((card['name'], card['args']), ('fast_remote', {'value': 'on'}))
        self.assertEqual(card['detail'], SCHEMAS.consequence('fast_remote', 'ar'))
        self.assertIn('US', card['detail'])                 # the keyboard switch is said before the yes

    def test_restart_runs_at_once_and_the_executor_answers(self):
        self.set_remote(active=True)
        self.read_remote.return_value = remote(active=True)
        self.page.restartRemote()
        self.execute.assert_called_once_with('remote_control', {'value': 'restart'})
        self.assertEqual(self.host.cards, [])
        self.assertEqual((self.state['remote_note'], self.state['remote_tone']), ('cn_done_restarted_tool', 'ok'))
        self.assertIn('remote:now', self.page.ran)          # and the pill is read again

    def test_a_failed_direct_action_says_why_in_words(self):
        self.set_remote(active=True, fast=True)
        self.read_remote.return_value = remote(active=True, fast=True)      # the read after it agrees
        self.execute.return_value = {'status': 'error', 'error': 'busy', 'summary': 'عملية أخرى'}
        self.page.setFastRemote(False)
        self.execute.assert_called_once_with('fast_remote', {'value': 'off'})
        self.assertEqual((self.state['remote_note'], self.state['remote_reason'], self.state['remote_tone'], self.state['remote_busy']),
                         ('cn_not_done_direct', 'cn_err_busy', 'error', ''))
        self.execute.return_value = {'status': 'error', 'exit_code': 69, 'output': 'Fast Remote is still on'}
        self.page.setFastRemote(False)
        self.assertEqual((self.state['remote_note'], self.state['remote_reason']), ('cn_not_done_direct', ''))

    def test_an_executor_that_asks_turns_into_a_card(self):
        self.set_remote(active=True, fast=True)
        self.execute.return_value = {'status': 'confirm', 'category': 'control'}
        self.page.setFastRemote(False)
        self.assertEqual((self.host.cards[-1]['name'], self.host.cards[-1]['args']), ('fast_remote', {'value': 'off'}))
        self.assertEqual((self.state['remote_phase'], self.state['remote_note']), ('card', 'cn_card_waiting'))

    def test_an_executor_that_does_not_answer_in_time_is_read_back(self):
        self.set_remote(active=True, fast=True)
        self.execute.return_value = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.page.setFastRemote(False)
        self.assertEqual((self.state['remote_phase'], self.state['remote_note']), ('readback', 'cn_wait_readback'))
        self.follow_reads(remote(active=True, fast=False))
        self.assertEqual(self.state['remote_note'], 'cn_done_fast_off')

    def test_a_refused_card_is_said_and_frees_the_buttons(self):
        self.host.card = False
        self.page.startRemote()
        self.assertEqual((self.state['remote_note'], self.state['remote_tone'], self.state['remote_busy']),
                         ('cn_card_failed', 'error', ''))
        self.assertIsNone(self.page._follow)

    def test_the_card_end_is_followed_when_the_controller_reports_it(self):
        self.set_remote(active=False)
        self.page.startRemote()
        card_id = 'card-1'
        self.page.action_changed(card_id, 'remote_control', 'running')
        self.assertEqual((self.state['remote_phase'], self.state['remote_note']), ('run', 'cn_card_running'))
        self.read_remote.return_value = remote(active=True)
        self.page.action_changed(card_id, 'remote_control', 'ok')
        self.assertEqual((self.state['remote_busy'], self.state['remote_note'], self.state['remote_tone']),
                         ('', 'cn_done_running', 'ok'))
        self.assertTrue(self.state['remote']['active'])      # read again at once

    def test_a_cancelled_or_expired_card_frees_the_buttons_at_once(self):
        for stage, word in (('cancelled', 'cn_card_cancelled'), ('expired', 'cn_card_expired'), ('error', 'cn_not_done')):
            self.set_remote(active=False)
            self.page.startRemote()
            card_id = f'card-{len(self.host.cards)}'
            self.page.action_changed(card_id, 'remote_control', stage)
            self.assertEqual((self.state['remote_busy'], self.state['remote_note']), ('', word), stage)
            self.assertIsNone(self.page._follow)

    def test_another_pages_card_is_not_ours(self):
        self.page.startRemote()
        self.page.action_changed('someone-else', 'install_app', 'cancelled')
        self.assertEqual(self.state['remote_busy'], 'start')

    def test_a_card_nobody_answers_is_let_go_after_its_lifetime(self):
        self.set_remote(active=False)
        self.page.startRemote()
        self.clock.now += connect.CARD_WAIT + connect.REMOTE['start']['run'] + 1
        self.follow_reads(remote(active=False))
        self.assertEqual((self.state['remote_busy'], self.state['remote_note']), ('', 'cn_not_confirmed'))
        self.assertEqual(self.page._cards, {})

    def test_approved_after_he_stopped_waiting_is_still_said(self):
        self.set_remote(active=False)
        self.page.startRemote()
        self.page.stopWaiting()
        self.assertEqual(self.state['remote_busy'], '')
        self.read_remote.return_value = remote(active=True)
        self.page.action_changed('card-1', 'remote_control', 'ok')
        self.assertEqual(self.state['remote_note'], 'cn_done_running')

    def test_restart_card_is_never_proved_by_a_read(self):
        self.set_remote(active=True)
        self.execute.return_value = {'status': 'confirm'}
        self.page.restartRemote()
        self.follow_reads(remote(active=True), remote(active=True), remote(active=True))
        self.assertEqual(self.state['remote_busy'], 'restart')   # "running" is not "restarted"
        self.page.action_changed('card-1', 'remote_control', 'ok')
        self.assertEqual(self.state['remote_note'], 'cn_done_restarted_tool')

    def test_the_messaging_agent_is_an_owner_card(self):
        self.page.update(channels={**self.state['channels'], 'known': True, 'engine': False})
        self.page.whatsappLogin()
        card = self.host.cards[-1]
        self.assertEqual((card['name'], card['args'], card['origin']), ('install_openclaw', {}, 'connect'))
        self.assertIn(SCHEMAS.consequence('install_openclaw', 'ar'), card['detail'])
        self.assertEqual((self.state['agent_install'], self.state['channel_note']), ('asked', 'cn_card_waiting'))
        self.page.setupAgent()
        self.assertEqual(len(self.host.cards), 1)            # never a second card while one waits
        self.open_route.assert_not_called()                   # no terminal route for it any more
        with mock.patch.object(connect, 'read_channels', return_value={'status': 'ok', 'engine': True,
                               'telegram': {'enabled': False, 'has_token': False, 'policy': 'pairing', 'allowed': 0}}):
            self.page.action_changed('card-1', 'install_openclaw', 'ok')
        self.assertEqual((self.state['agent_install'], self.state['channel_note']), ('', 'cn_agent_done'))
        self.assertTrue(self.state['channels']['engine'])

    def test_a_messaging_agent_card_that_ends_otherwise(self):
        self.page.setupAgent()
        self.page.action_changed('card-1', 'install_openclaw', 'running')
        self.assertEqual((self.state['agent_install'], self.state['channel_note']), ('running', 'cn_agent_running'))
        self.page.action_changed('card-1', 'install_openclaw', 'error')
        self.assertEqual((self.state['agent_install'], self.state['channel_note'], self.state['channel_tone']),
                         ('', 'cn_not_done', 'error'))

    def test_reach_from_outside_home_is_an_owner_card(self):
        self.page.remoteAnywhere()
        card = self.host.cards[-1]
        self.assertEqual((card['kind'], card['name'], card['args'], card['origin']), ('moai', 'remote_anywhere', {}, 'connect'))
        self.assertIn('Tailscale', card['detail'])
        self.assertEqual((self.state['anywhere_note'], self.state['anywhere_tone']), ('cn_card_waiting', 'pending'))
        self.page.remoteAnywhere()
        self.assertEqual(len(self.host.cards), 1)
        self.page.action_changed('card-1', 'remote_anywhere', 'ok')
        self.assertEqual((self.state['anywhere_note'], self.state['anywhere_tone']), ('cn_anywhere_done', 'ok'))
        self.open_route.assert_not_called()

    def test_a_refused_reach_card_is_said(self):
        self.host.card = False
        self.page.remoteAnywhere()
        self.assertEqual((self.state['anywhere_note'], self.state['anywhere_tone']), ('cn_card_failed', 'error'))


class NoteTest(PageCase):
    """A note never outlives what it says, nor contradicts the pill beside it."""

    def confirm_running(self):
        self.set_remote(active=False)
        self.page.startRemote()
        self.follow_reads(remote(active=True), remote(active=True))
        self.assertEqual(self.state['remote_note'], 'cn_done_running')

    def test_a_later_read_that_disagrees_clears_a_confirmation(self):
        self.confirm_running()
        self.page.on_remote('remote:poll', remote(active=True))
        self.assertEqual(self.state['remote_note'], 'cn_done_running')     # still true: kept
        self.page.on_remote('remote:poll', remote(active=False))            # crashed a moment later
        self.assertEqual((self.state['remote_note'], self.state['remote_tone']), ('', ''))
        self.assertFalse(self.state['remote']['active'])

    def test_a_failure_note_goes_once_the_state_changes_under_it(self):
        self.set_remote(active=False)
        self.page.startRemote()
        self.clock.now += 100
        self.follow_reads(remote(active=False))
        self.assertEqual(self.state['remote_note'], 'cn_not_confirmed')
        self.page.on_remote('remote:poll', remote(active=False))
        self.assertEqual(self.state['remote_note'], 'cn_not_confirmed')
        self.page.on_remote('remote:poll', remote(active=True))            # he approved the dialog late
        self.assertEqual(self.state['remote_note'], '')

    def test_notes_age_away_on_the_page_timer(self):
        self.confirm_running()
        with mock.patch.object(base, 'TEST_MODE', True):
            self.clock.now += connect.NOTE_S - 1
            self.page.poll()
            self.assertEqual(self.state['remote_note'], 'cn_done_running')
            self.clock.now += 2
            self.page.poll()
        self.assertEqual(self.state['remote_note'], '')

    def test_failures_stay_longer_than_confirmations(self):
        self.page.update(phone={**self.state['phone'], 'devices': [{'id': 'p_1', 'name': 'iPhone', 'paired': True, 'reachable': True}]})
        with mock.patch.object(connect, 'ring_phone', return_value={'status': 'error', 'error': 'x'}), \
             mock.patch.object(base, 'TEST_MODE', True):
            self.page.ringPhone('p_1')
            self.clock.now += connect.NOTE_S + 1
            self.page.poll()
            self.assertEqual(self.state['phone_note'], 'cn_ring_failed')
            self.clock.now += connect.ERROR_NOTE_S
            self.page.poll()
        self.assertEqual((self.state['phone_note'], self.state['phone_about']), ('', ''))

    def test_a_waiting_card_note_goes_after_the_cards_lifetime(self):
        self.page.remoteAnywhere()
        with mock.patch.object(base, 'TEST_MODE', True):
            self.clock.now += connect.CARD_WAIT
            self.page.poll()
            self.assertEqual(self.state['anywhere_note'], 'cn_card_waiting')
            self.clock.now += connect.CARD_MARGIN + 1
            self.page.poll()
        self.assertEqual(self.state['anywhere_note'], '')
        self.assertEqual(self.page._cards, {})
        self.page.remoteAnywhere()                            # and a new card may be asked for
        self.assertEqual(len(self.host.cards), 2)

    def test_refresh_clears_finished_notes_but_not_waiting_ones(self):
        self.confirm_running()
        self.page.remoteAnywhere()
        with mock.patch.object(connect, 'read_channels', return_value={'status': 'error', 'error': 'x'}), \
             mock.patch.object(connect, 'read_phone', return_value={'status': 'error', 'error': 'x'}):
            self.read_remote.return_value = remote(active=True)
            self.page.refresh()
        self.assertEqual(self.state['remote_note'], '')
        self.assertEqual(self.state['anywhere_note'], 'cn_card_waiting')

    def test_a_followed_action_keeps_its_note(self):
        self.page.startRemote()
        with mock.patch.object(base, 'TEST_MODE', True):
            self.clock.now += 70
            self.page.poll()
        self.assertEqual(self.state['remote_note'], 'cn_wait_dialog')


class PhoneLinkTest(PageCase):
    """The phone link is the edition's own app: there is no store package of it, so the page never
    offers to install it and an edition without it says so."""

    def test_the_page_has_no_install_path(self):
        self.assertFalse(hasattr(self.page, 'installPhoneLink'))
        self.assertNotIn('install_app', (ROOT / 'pages' / 'connect.py').read_text())
        self.assertNotIn('org.kde.kdeconnect\'', (ROOT / 'pages' / 'connect.py').read_text())

    def test_a_missing_phone_link_raises_no_card_and_opens_nothing(self):
        self.page.update(phone={**self.state['phone'], 'known': True})
        self.page.openPhoneApp()
        self.execute.assert_not_called()
        self.assertEqual(self.host.cards, [])

    def test_the_words_for_a_missing_link_name_the_edition(self):
        for lang in ('ar', 'en'):
            words = i18n.table(lang)
            self.assertNotRegex(words['cn_phone_missing_note'], r'(?i)install|ثبّت')
        self.assertEqual(i18n.table('en')['cn_phone_missing_note'], 'This MoOS edition has no phone link.')


class PhoneEnglishTest(PageCase):
    lang = 'en'

    def test_open_phone_uses_the_executor_and_fails_in_the_owners_language(self):
        self.page.update(phone={**self.state['phone'], 'system': True})
        self.page.openPhoneApp()
        self.execute.assert_called_once_with('open_app', {'app_id': 'org.kde.kdeconnect.app'})
        self.assertEqual(self.host.toasts[-1][0], 'info')
        self.execute.return_value = {'status': 'confirm'}
        self.page.openPhoneApp()
        self.assertEqual(self.host.cards[-1]['name'], 'open_app')
        self.execute.return_value = {'status': 'error', 'error': 'http_500', 'summary': 'تعذّر: فتح تطبيق'}
        self.page.openPhoneApp()
        self.assertEqual(self.host.toasts[-1], ('error', 'Could not open the Phone app'))   # never the Arabic summary
        self.execute.return_value = {'status': 'error', 'error': 'moai_control_unreachable'}
        self.page.openPhoneApp()
        self.assertEqual(self.host.toasts[-1], ('error', "Could not open the Phone app · MoOS's tools service is not answering"))
        self.page.update(phone={**self.state['phone'], 'system': False, 'local': True})
        self.execute.reset_mock()
        self.execute.return_value = {'status': 'ok'}
        self.page.openPhoneApp()                       # found outside the image: the same app, the same entry
        self.execute.assert_called_once_with('open_app', {'app_id': 'org.kde.kdeconnect.app'})

    def test_ring_only_a_paired_phone_in_reach_and_never_show_the_cli_words(self):
        devices = [{'id': 'near_1', 'name': 'iPhone', 'paired': True, 'reachable': True},
                   {'id': 'far_2', 'name': 'Tablet', 'paired': True, 'reachable': False}]
        self.page.update(phone={**self.state['phone'], 'devices': devices})
        with mock.patch.object(connect, 'ring_phone', return_value={'status': 'ok'}) as ring:
            self.page.ringPhone('far_2')
            self.page.ringPhone('unknown_3')
            self.page.ringPhone('near_1; rm -rf ~')
            ring.assert_not_called()
            self.page.ringPhone('near_1')
        ring.assert_called_once_with('near_1')
        self.assertEqual((self.state['phone_note'], self.state['phone_about'], self.state['ringing']),
                         ('cn_ring_sent', 'iPhone', ''))
        with mock.patch.object(connect, 'ring_phone', return_value={'status': 'error', 'error': 'Gerät nicht erreichbar'}):
            self.page.ringPhone('near_1')
        self.assertEqual((self.state['phone_note'], self.state['phone_about'], self.state['phone_tone']),
                         ('cn_ring_failed', 'iPhone', 'error'))

    def test_echo_settings_opens_the_settings_destination(self):
        self.page.openSettings()
        self.assertEqual(self.host.sheets, ['settings'])


class PollTest(PageCase):
    def test_poll_touches_nothing_in_review_mode(self):
        with mock.patch.object(base, 'TEST_MODE', True):
            self.page.poll()
        self.read_remote.assert_not_called()

    def test_poll_reads_the_remote_and_never_the_phone(self):
        self.read_remote.return_value = remote(active=True)
        with mock.patch.object(base, 'TEST_MODE', False), \
             mock.patch.object(connect, 'read_phone', return_value={'status': 'ok', 'local': False}) as phone:
            self.page.poll()
            self.read_remote.assert_called_once()
            self.clock.now += connect.READ_EVERY + 1
            self.page.poll()
            phone.assert_not_called()                 # the phone link is read by a refresh, never followed
            self.page.startRemote()
            self.read_remote.reset_mock()
            self.page.poll()                          # the follow timer reads while an action is followed
            self.read_remote.assert_not_called()
        self.assertTrue(self.state['remote']['active'])

    def test_activation_in_review_mode_reads_nothing(self):
        with mock.patch.object(base, 'TEST_MODE', True), \
             mock.patch.object(connect.moai_tools, 'get', side_effect=AssertionError('touched the machine')):
            self.page.activated()
        self.read_remote.assert_not_called()

    def test_every_review_variant_is_sample_and_uses_known_fields_and_words(self):
        words = i18n.table('en')
        known = set(self.page.initial())
        for variant in ('sample', 'error', 'armed', 'card', 'fast', 'initial'):
            page = connect.ConnectPage(self.host)
            page.review(variant)
            state = page.state
            self.assertEqual(set(state) - known, set(), variant)
            for key in ('remote_note', 'remote_reason', 'remote_error', 'anywhere_note', 'channel_note', 'phone_note'):
                if state[key]:
                    self.assertIn(state[key], words, (variant, key))
            self.assertTrue(all('(sample)' in d['name'] for d in state['phone']['devices']), variant)
        self.assertEqual(connect.ConnectPage(self.host).state, self.page.initial())


class WordsTest(unittest.TestCase):
    def test_every_word_has_both_languages_and_no_foreign_identity(self):
        banned = ('fedora', 'red hat', 'flatpak', 'wayland', 'kwin', 'pipewire', 'portal', 'openclaw', 'systemd',
                  'org.kde')
        for key, pair in connect.STRINGS.items():
            self.assertTrue(key.startswith('cn_'), key)
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(pair[0].strip() and pair[1].strip(), key)
            self.assertFalse(any('؀' <= ch <= 'ۿ' for ch in pair[1]), key)    # English is English
            for word in pair:
                self.assertFalse(any(b in word.lower() for b in banned), (key, word))

    def test_note_keys_the_page_stores_are_words(self):
        words = i18n.table('en')
        for spec in connect.REMOTE.values():
            for field in ('done', 'done_tool', 'card'):
                if spec[field]:
                    self.assertIn(spec[field], words, field)
        for key in ('cn_wait_dialog', 'cn_wait_readback', 'cn_not_confirmed', 'cn_route_failed', 'cn_card_waiting',
                    'cn_card_failed', 'cn_card_running', 'cn_not_done', 'cn_not_done_direct',
                    'cn_ring_sent', 'cn_ring_failed', 'cn_agent_done',
                    'cn_agent_running', 'cn_anywhere_done', 'cn_err_read', 'cn_working',
                    *connect.ERRORS.values(), *(k for k, _ in connect.CARD_END.values())):
            self.assertIn(key, words)

    def test_the_fast_mode_words_say_what_it_changes(self):
        words = i18n.table('en')
        for key in ('cn_fast_hint', 'cn_fast_now'):
            self.assertIn('keyboard', words[key])
            self.assertIn('US', words[key])
        self.assertIn('keyboard', words['cn_done_fast_off'])

    def test_every_remote_route_is_allowed(self):
        for spec in connect.REMOTE.values():
            self.assertTrue(connect.moos_routes.allowed(spec['url']), spec['url'])

    def test_every_remote_tool_is_one_the_branch_schemas_declare(self):
        declared = {t['function']['name'] for t in SCHEMAS.ALL_TOOLS}
        for spec in connect.REMOTE.values():
            name, value = spec['tool']
            self.assertIn(name, declared)
            self.assertIn(value, SCHEMAS._properties(name)['value']['enum'])
        self.assertIn(connect.AGENT_TOOL, declared)
        # the executor, not the page, decides the cards: on/off and fast-on ask; restart and fast-off do not
        self.assertEqual([v for v, s in connect.REMOTE.items() if SCHEMAS.needs_confirmation(s['tool'][0], {'value': s['tool'][1]})],
                         ['start', 'stop', 'fast-on'])


class QmlWiringTest(unittest.TestCase):
    """The real ConnectPage.qml in Main.qml (offscreen): every review variant renders without a warning,
    and each button calls the slot it says."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtQml import QQmlApplicationEngine
        from controller import Controller
        from faces import FaceProvider
        import review_fakes
        cls.lines = []
        cls.previous = qInstallMessageHandler(lambda mode, context, message: cls.lines.append(message))
        cls.controller = Controller(bridge_class=review_fakes.FakeBridge)
        cls.engine = QQmlApplicationEngine()
        cls.engine.addImageProvider('mira', FaceProvider())
        cls.engine.addImportPath(str(ROOT / 'qml'))
        cls.engine.rootContext().setContextProperty('mira', cls.controller)
        cls.engine.load(QUrl.fromLocalFile(str(ROOT / 'qml' / 'Main.qml')))
        if not cls.engine.rootObjects():
            qInstallMessageHandler(cls.previous)
            raise AssertionError('Main.qml did not load: ' + ' | '.join(cls.lines[-8:]))
        cls.window = cls.engine.rootObjects()[0]
        cls.window.setWidth(1480)
        cls.window.setHeight(920)
        cls.window.setProperty('sheet', 'connect')
        cls.page = cls.controller._pages['connect']
        cls.settle()

    @classmethod
    def tearDownClass(cls):
        cls.page._follow_timer.stop()
        cls.page._disarm_timer.stop()
        cls.engine.deleteLater()
        cls.settle(0.05)
        qInstallMessageHandler(cls.previous)

    @staticmethod
    def settle(seconds=0.25):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            QCoreApplication.processEvents()
            time.sleep(0.01)

    def setUp(self):
        self.words = i18n.table(self.controller.lang)
        self.page._follow = None
        self.page._armed_at = 0.0
        self.page._cards = {}
        self.page.update(**self.page.initial())
        self.open_route = mock.patch.object(connect.moos_routes, 'open_route', return_value={'status': 'ok'}).start()
        mock.patch.object(connect.moai_tools, 'needs_confirmation', side_effect=SCHEMAS.needs_confirmation).start()
        mock.patch.object(connect.moai_tools, 'consequence', side_effect=SCHEMAS.consequence).start()
        self.addCleanup(mock.patch.stopall)
        self.settle(0.05)

    def item(self, name):
        found = self.window.findChild(QObject, name)
        self.assertIsNotNone(found, name)
        return found

    def press(self, name, signal='clicked'):
        self.assertTrue(QMetaObject.invokeMethod(self.item(name), signal, Qt.DirectConnection), name)
        self.settle(0.05)

    def page_warnings(self):
        return [line for line in self.lines if 'ConnectPage.qml' in line or 'CompanionPanel.qml' in line]

    def test_every_variant_renders_without_a_warning(self):
        for lang in ('ar', 'en'):
            self.controller.setLang(lang)
            for variant in ('initial', 'sample', 'error', 'armed', 'card', 'fast'):
                self.page.update(**self.page.initial())
                self.page.review(variant)
                for width in (1480, 900):
                    self.window.setWidth(width)
                    self.settle(0.08)
        self.window.setWidth(1480)
        self.controller.setLang('ar')
        self.settle(0.05)
        self.assertEqual(self.page_warnings(), [])

    def test_start_and_stop_reach_their_own_slots(self):
        with mock.patch.object(connect.moai_tools, 'names', return_value=set()):
            self.page.update(remote={'known': True, 'active': False, 'pipewire': True, 'portal': True, 'fast': False})
            self.settle(0.05)
            self.press('cnPrimary')
            self.open_route.assert_called_once_with('moos://remote/start')
            self.page._follow = None
            self.page.update(remote_busy='', remote_phase='',
                             remote={'known': True, 'active': True, 'pipewire': True, 'portal': True, 'fast': False})
            self.settle(0.05)
            self.open_route.reset_mock()
            self.press('cnPrimary')                        # Stop arms, it never starts
            self.open_route.assert_not_called()
            self.assertTrue(self.page.state['stop_armed'])
            self.page._disarm()

    def test_the_fast_button_sends_the_opposite_of_what_is_read(self):
        with mock.patch.object(connect.moai_tools, 'names', return_value=set()):
            self.page.update(remote={'known': True, 'active': True, 'pipewire': True, 'portal': True, 'fast': True})
            self.settle(0.05)
            self.assertEqual(self.item('cnFast').property('text'), self.words['cn_fast_off'])
            self.press('cnFast')
            self.open_route.assert_called_once_with('moos://remote/fast-off')
            self.page._finish_follow('', '')
            self.page.update(remote={'known': True, 'active': True, 'pipewire': True, 'portal': True, 'fast': False})
            self.settle(0.05)
            self.open_route.reset_mock()
            self.press('cnFast')
            self.open_route.assert_called_once_with('moos://remote/fast-on')
            self.page._finish_follow('', '')

    def test_fast_on_is_offered_only_for_a_running_remote(self):
        self.page.update(remote={'known': True, 'active': False, 'pipewire': True, 'portal': True, 'fast': False})
        self.settle(0.05)
        self.assertFalse(self.item('cnFast').property('visible'))
        self.page.update(remote={'known': False, 'active': False, 'pipewire': False, 'portal': False, 'fast': True})
        self.settle(0.05)
        fast = self.item('cnFast')
        self.assertTrue(fast.property('visible'))            # on is on, even while /quick is unknown
        self.assertEqual(fast.property('text'), self.words['cn_fast_off'])

    def test_whatsapp_row_follows_the_agent(self):
        row = self.item('cnWhatsappRow')
        self.assertEqual((row.property('action'), row.property('detail')), ('', ''))   # nothing claimed before a read
        with mock.patch.object(connect.moai_tools, 'names', return_value=set(TOOLS)), \
             mock.patch.object(self.controller, 'request_confirmation', return_value={'id': 'p1'}) as ask:
            self.page.update(channels={'known': True, 'engine': False, 'error': '', 'telegram': {}})
            self.settle(0.05)
            self.assertEqual(row.property('action'), self.words['cn_agent_setup'])
            self.press('cnWhatsappRow', 'act')
            self.assertEqual(ask.call_args[0][0]['name'], 'install_openclaw')
        self.page.update(agent_install='', channels={'known': True, 'engine': True, 'error': '', 'telegram': {}})
        self.settle(0.05)
        self.press('cnWhatsappRow', 'act')
        self.open_route.assert_called_once_with('moos://agent/whatsapp-login')

    def test_the_phone_pill_says_unknown_after_a_failed_read(self):
        self.page.update(phone={'known': False, 'system': False, 'local': False, 'running': False, 'devices': [],
                                'listed': False, 'error': 'cn_err_control'})
        self.settle(0.05)
        self.assertEqual(self.item('cnPhonePill').property('text'), self.words['cn_unknown'])

    def test_two_waiting_cards_read_as_two_different_things(self):
        self.page.review('card')
        self.settle(0.05)
        remote_note, anywhere_note = self.item('cnRemoteNote').property('text'), self.item('cnAnywhereNote').property('text')
        self.assertNotEqual(remote_note, anywhere_note)
        self.assertTrue(anywhere_note.startswith(self.words['cn_anywhere']))

    def test_stop_waiting_is_offered_while_a_card_waits(self):
        with mock.patch.object(connect.moai_tools, 'names', return_value=set(TOOLS)), \
             mock.patch.object(self.controller, 'request_confirmation', return_value={'id': 'p2'}):
            self.page.update(remote={'known': True, 'active': False, 'pipewire': True, 'portal': True, 'fast': False})
            self.page.startRemote()
            self.settle(0.05)
            note = self.item('cnRemoteNote')
            self.assertEqual(note.property('action'), self.words['cn_stop_waiting'])
            self.press('cnRemoteNote', 'act')
        self.assertEqual((self.page.state['remote_busy'], self.page.state['remote_note']), ('', ''))
        self.assertIsNone(self.page._follow)


if __name__ == '__main__':
    unittest.main()
