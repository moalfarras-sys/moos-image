"""The Brain page: real service shapes mapped honestly, choices validated and kept, tests that never
send a key, the paid-model yes, the answer that just finished, and no machine access in review mode.

Every backend is a fake: no test reaches moai-control, the Mo AI agent, Google or the owner's
QSettings (each test gets its own INI file).
"""
import contextlib
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QCoreApplication, QObject, QSettings, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

import brain  # noqa: E402
import i18n  # noqa: E402
import moos_routes  # noqa: E402
import pages.brain as brain_page  # noqa: E402
from pages.brain import BrainPage, STRINGS  # noqa: E402

APP = QGuiApplication.instance() or QGuiApplication([])

# The shapes measured on the owner's station on 2026-09-29 (read-only GETs), trimmed.
CONFIG = {
    'brain': {'mode': 'cloud'},
    'cloud': {'provider': 'openrouter-free', 'base': 'https://openrouter.ai/api/v1', 'model': 'openrouter/free',
              'has_key': True},
    'permissions': {'tier': 'full', 'web': False, 'exec': True, 'workspace': 'rw', 'sandbox': 'off',
                    'host_control': True, 'elevated': 'full', 'approvals': False, 'project': ''},
    'providers': [
        {'id': 'openrouter-free', 'name': 'OpenRouter (مجاني فقط | free only)', 'base': 'https://openrouter.ai/api/v1',
         'model': 'openrouter/free', 'api': 'openai-completions', 'free': True},
        {'id': 'openrouter-paid', 'name': 'OpenRouter (مدفوع باختيارك | paid by choice)',
         'base': 'https://openrouter.ai/api/v1', 'model': 'openai/gpt-5.4-mini', 'api': 'openai-completions', 'free': False}],
    'tiers': ['read', 'project', 'system', 'full'],
}
MODELS = {
    'local': [], 'cloud_error': '', 'default': 'cloud:openrouter/free', 'mode': 'cloud',
    'cloud': [
        {'id': 'cloud:openrouter/free', 'label': 'Free cloud · سحابي مجاني', 'serving': True, 'input': ['text'],
         'group': 'auto', 'label_ar': 'تلقائي — أفضل نموذج مجاني متاح', 'label_en': 'Automatic — best free model available',
         'note_ar': 'الآن: Nemotron Super', 'note_en': 'Right now: Nemotron Super'},
        {'id': 'cloud:nvidia/nemotron-3-super-120b-a12b:free', 'label': 'nvidia/nemotron-3-super-120b-a12b:free',
         'serving': False, 'input': ['text'], 'group': 'measured', 'rank': 4, 'label_ar': 'Nemotron Super',
         'label_en': 'Nemotron Super', 'note_ar': '1.9 ث للردّ', 'note_en': '1.9s to answer'},
        {'id': 'cloud:cohere/north-mini-code:free', 'label': 'cohere/north-mini-code:free', 'serving': False,
         'input': ['text', 'image'], 'group': 'curated', 'label_ar': 'North Code', 'label_en': 'North Code',
         'note_ar': 'مخصص للبرمجة', 'note_en': 'Built for code'},
        {'id': 'cloud:google/gemma-4-31b-it:free', 'label': 'google/gemma-4-31b-it:free', 'serving': False,
         'input': ['text'], 'group': 'all'},
        {'id': 'cloud:thinkingmachines/inkling:free', 'label': 'thinkingmachines/inkling:free', 'serving': False,
         'input': ['text'], 'group': 'all', 'note_ar': 'المزوّد رفض الطلب — HTTP 403', 'note_en': 'The provider refused it — HTTP 403'},
    ]}
PAID_MODELS = {**MODELS, 'cloud': MODELS['cloud'] + [
    {'id': 'cloud:openai/gpt-5.4-mini', 'label': 'openai/gpt-5.4-mini', 'serving': False, 'input': ['text'], 'group': 'paid'}]}
MEASURE = {'measuring': False, 'done': 0, 'total': 0, 'now': '', 'error': '', 'measuredAt': 1789744784.8, 'ageDays': 11.2,
           'tools': ['nex-agi/nex-n2.5-pro:free', 'nvidia/nemotron-3-super-120b-a12b:free'],
           'best': 'nex-agi/nex-n2.5-pro:free', 'bestLabel': 'Nex Pro', 'results': []}
GEMINI = {'has_key': True, 'voice_model': 'gemini-3.1-flash-live-preview', 'text_model': ''}


class Host(QObject):
    toast = Signal(str, str)

    def __init__(self, lang='ar'):
        super().__init__()
        self.lang = lang
        self.s = i18n.table(lang)
        self.toasts = []
        self.toast.connect(lambda kind, text: self.toasts.append((kind, text)))
        self.confirmations = []

    def request_confirmation(self, item):   # the page must never need it: nothing here changes the system
        self.confirmations.append(item)


def settle(until, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QCoreApplication.processEvents()
        if until():
            return True
        time.sleep(0.01)
    return False


class PageTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        ini = os.path.join(self.dir.name, 'Mira.conf')
        patches = [
            patch.object(brain, '_qsettings', side_effect=lambda: QSettings(ini, QSettings.IniFormat)),
            # Any backend a test does not set is a failure, never a real request.
            patch('moai_tools.get', side_effect=AssertionError('moai-control reached')),
            patch('moai_tools.post', side_effect=AssertionError('moai-control reached')),
            patch('moai_agent.get', side_effect=AssertionError('agent reached')),
            patch.object(brain, 'gemini_settings', side_effect=AssertionError('gemini.json read')),
            patch.object(brain, 'probe_gemini', side_effect=AssertionError('Google reached')),
            patch.object(moos_routes, 'open_route', side_effect=AssertionError('moos-open reached')),
            patch.object(brain_page, 'TEST_MODE', False),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.host = Host()
        self.page = BrainPage(self.host)
        # A page left behind must not poll into, or hear answers meant for, the next test.
        self.addCleanup(self.page.pageHidden)
        self.addCleanup(brain.remove_answer_listener, self.page._answer_arrived)

    def sync(self, page=None):
        """Run the page's work at once on this thread (the threaded path has its own test)."""
        page = page or self.page
        page.run = lambda tag, fn, *args, **kwargs: page._deliver(tag, fn(*args, **kwargs))

    def backends(self, models=MODELS, measure=MEASURE, config=CONFIG, gemini=GEMINI):
        def tools_get(path, timeout=20):
            return {'/models': models, '/measure': measure}[path]
        return [patch('moai_tools.get', side_effect=tools_get),
                patch('moai_agent.get', side_effect=lambda path, **q: config),
                patch.object(brain, 'gemini_settings', return_value=gemini)]

    def loaded(self, **kwargs):
        self.sync()
        with contextlib.ExitStack() as stack:
            for item in self.backends(**kwargs):
                stack.enter_context(item)
            self.page.refresh()
        return self.page.state

    # ── state ───────────────────────────────────────────────────────
    def test_initial_state_reads_nothing_and_offers_the_three_models(self):
        state = self.page.state
        self.assertEqual([m['id'] for m in state['text_models']], list(brain.TEXT_MODEL_IDS))
        self.assertEqual(state['text_model'], brain.DEFAULT_TEXT_MODEL)
        self.assertEqual((state['cloud']['state'], state['permissions']['state']), ('loading', 'loading'))
        self.assertIsInstance(state['last'], dict)
        for model in state['text_models']:
            self.assertIn(model['name_key'], STRINGS)
            self.assertIn(model['note_key'], STRINGS)

    def test_review_mode_activation_reads_nothing(self):
        with patch('pages.base.TEST_MODE', True):
            self.page.activated()      # the patched backends would raise if anything were read
        self.page.review()
        state = self.page.state
        self.assertEqual(state['cloud']['state'], 'ok')
        self.assertTrue(state['groups'])
        self.assertIn('sample', state['cloud_test']['reply'].lower())
        self.assertEqual(self.host.confirmations, [])

    def test_refresh_maps_the_real_shapes(self):
        state = self.loaded()
        cloud = state['cloud']
        self.assertEqual((cloud['name_ar'], cloud['name_en']), ('OpenRouter (مجاني فقط)', 'OpenRouter (free only)'))
        self.assertEqual((cloud['host'], cloud['has_key'], cloud['free'], cloud['wire']), ('openrouter.ai', True, True, 'openai'))
        self.assertNotIn('api_key', str(state))
        self.assertEqual([g['key'] for g in state['groups']], ['auto', 'measured', 'curated', 'all'])
        rows = {row['id']: row for group in state['groups'] for row in group['rows']}
        self.assertTrue(rows['openrouter/free']['serving'])
        self.assertEqual(rows['google/gemma-4-31b-it:free']['label_en'], 'gemma-4-31b-it', 'a raw id reads as its short name')
        self.assertTrue(rows['cohere/north-mini-code:free']['vision'])
        self.assertEqual(rows['thinkingmachines/inkling:free']['note_en'], 'The provider refused it — HTTP 403')
        self.assertEqual((state['moai_default'], state['all_count']), ('openrouter/free', 2))
        measure = state['measure']
        self.assertEqual((measure['best'], measure['best_label'], measure['best_available']),
                         ('nex-agi/nex-n2.5-pro:free', 'Nex Pro', False), 'a measured best that left the catalogue is not offered')
        perms = state['permissions']
        self.assertEqual((perms['tier'], perms['web'], perms['exec'], perms['approvals']), ('full', False, True, False))
        self.assertEqual((state['has_key'], state['voice_model'], state['text_model_source']),
                         (True, 'gemini-3.1-flash-live-preview', 'default'))

    def test_unknown_tier_is_custom_and_a_config_model_is_named(self):
        config = {**CONFIG, 'permissions': {**CONFIG['permissions'], 'tier': 'root-everything'}}
        state = self.loaded(config=config, gemini={**GEMINI, 'text_model': 'gemini-2.5-flash'})
        self.assertEqual(state['permissions']['tier'], 'custom')
        self.assertEqual((state['text_model'], state['text_model_source']), ('gemini-2.5-flash', 'config'))

    def test_refresh_on_threads_lands_on_the_qt_thread(self):
        seen = []

        def tools_get(path, timeout=20):
            seen.append(threading.current_thread() is threading.main_thread())
            return {'/models': MODELS, '/measure': MEASURE}[path]
        with patch('moai_tools.get', side_effect=tools_get), patch('moai_agent.get', return_value=CONFIG), \
                patch.object(brain, 'gemini_settings', return_value=GEMINI):
            self.page.refresh()
            self.assertTrue(settle(lambda: self.page.state['models_state'] == 'ok'
                                   and self.page.state['cloud']['state'] == 'ok'
                                   and self.page.state['measure']['best'] != ''))
        self.assertEqual(seen, [False, False], 'reads run off the Qt thread')

    def test_services_down_are_said_not_hidden(self):
        self.sync()
        with patch('moai_tools.get', return_value={'error': 'moai_control_unreachable', 'detail': 'URLError'}), \
                patch('moai_agent.get', return_value={'error': 'agent_unreachable', 'detail': 'URLError'}), \
                patch.object(brain, 'gemini_settings', return_value={'has_key': False, 'voice_model': '', 'text_model': ''}):
            self.page.refresh()
        state = self.page.state
        self.assertEqual((state['cloud']['state'], state['permissions']['state'], state['models_state']), ('error', 'error', 'error'))
        self.assertEqual(state['models_error_ar'], STRINGS['br_unreachable'][0])
        self.assertEqual(state['measure']['state'], 'error')
        self.assertEqual(state['groups'], [])

    def test_a_provider_error_is_shown_in_both_languages(self):
        state = self.loaded(models={'local': [], 'cloud': [], 'cloud_error': 'تعذّر جلب قائمة النماذج | could not fetch the model list',
                                    'default': 'cloud:openrouter/free'})
        self.assertEqual(state['models_state'], 'error')
        self.assertEqual((state['models_error_ar'], state['models_error_en']),
                         ('تعذّر جلب قائمة النماذج', 'could not fetch the model list'))

    # ── choosing ────────────────────────────────────────────────────
    def test_typed_model_is_kept_and_only_offered_ones_are_accepted(self):
        self.page.setTextModel('gemini-2.5-flash')
        self.assertEqual(brain.preferences()['text_model'], 'gemini-2.5-flash')
        self.assertEqual((self.page.state['text_model'], self.page.state['text_model_source']), ('gemini-2.5-flash', 'mira'))
        self.assertEqual(self.host.toasts[-1][0], 'ok')
        self.page.setTextModel('gemini-ultra-paid')
        self.assertEqual(self.host.toasts[-1][0], 'error')
        self.assertEqual(brain.preferences()['text_model'], 'gemini-2.5-flash')

    def test_cloud_model_must_be_in_the_list(self):
        self.page.setCloudModel('nvidia/nemotron-3-super-120b-a12b:free')
        self.assertEqual(self.host.toasts[-1][0], 'error', 'nothing is saved before the list was read')
        self.assertEqual(brain.preferences()['cloud_model'], '')
        self.loaded()
        self.page.setCloudModel('nvidia/nemotron-3-super-120b-a12b:free')
        self.assertEqual(brain.preferences()['cloud_model'], 'nvidia/nemotron-3-super-120b-a12b:free')
        self.assertEqual(self.page.state['cloud_model'], 'nvidia/nemotron-3-super-120b-a12b:free')
        self.assertIn('Nemotron Super', self.host.toasts[-1][1])
        self.page.setCloudModel('evil/unlisted:free')
        self.assertEqual(brain.preferences()['cloud_model'], 'nvidia/nemotron-3-super-120b-a12b:free')
        self.page.setCloudModel('')
        self.assertEqual((brain.preferences()['cloud_model'], self.page.state['cloud_model']), ('', ''))
        self.assertEqual(self.host.confirmations, [], 'a model pick is a preference, not a system change')

    def test_a_paid_model_needs_an_explicit_yes(self):
        self.loaded(models=PAID_MODELS)
        self.assertEqual(self.page.state['groups'][-1]['key'], 'paid')
        self.page.setCloudModel('openai/gpt-5.4-mini')
        self.assertEqual(self.page.state['paid_pending'], 'openai/gpt-5.4-mini')
        self.assertEqual(brain.preferences()['cloud_model'], '', 'not saved on the first click')
        self.page.cancelPaidModel()
        self.assertEqual((self.page.state['paid_pending'], brain.preferences()['cloud_model']), ('', ''))
        self.page.setCloudModel('openai/gpt-5.4-mini')
        self.page.confirmPaidModel()
        self.assertEqual(brain.preferences()['cloud_model'], 'openai/gpt-5.4-mini')
        self.assertEqual(self.page.state['paid_pending'], '')

    def test_a_pick_that_left_the_catalogue_is_flagged(self):
        brain.set_cloud_model('vanished/model:free')
        state = self.loaded()
        self.assertTrue(state['pick_missing'])
        self.assertEqual(state['cloud_model'], 'vanished/model:free')

    def test_choices_that_cannot_be_kept_say_so_in_their_own_words(self):
        with patch.object(brain, '_qsettings', return_value=None):
            self.page.setTextModel('gemini-2.5-flash')
        self.assertEqual(self.host.toasts[-1], ('error', STRINGS['br_model_not_saved'][0]))
        self.loaded()
        with patch.object(brain, '_qsettings', return_value=None):
            self.page.setCloudModel('nvidia/nemotron-3-super-120b-a12b:free')
        self.assertEqual(self.host.toasts[-1], ('error', STRINGS['br_model_not_saved'][0]))

    # ── the key and the route: one truth, TextBrain's own rule ──────
    def route(self):
        state = self.page.state
        return state['route_now'], state['key_status'], state['gemini_warning']

    def test_route_follows_the_saved_key_not_a_stale_save_result(self):
        self.assertEqual(self.route(), ('', 'unknown', ''), 'nothing is claimed before anything was read')
        self.loaded()                                   # gemini.json holds a key
        self.assertEqual(self.route(), ('gemini', 'set', ''))
        self.loaded(gemini={**GEMINI, 'has_key': False})
        self.assertEqual(self.route(), ('moai-cloud', 'missing', ''))

    def test_a_quota_failure_at_save_keeps_gemini_first_with_a_warning(self):
        self.loaded()
        self.sync()
        with patch.object(brain, 'probe_gemini', return_value={'status': 'error', 'model': brain.DEFAULT_TEXT_MODEL,
                                                              'elapsed_ms': 30, 'reason': 'quota'}) as probe:
            self.page.keyChecked('testing', '')
            self.assertEqual(self.route()[:2], ('gemini', 'testing'))
            self.page.keyChecked('failed', '')      # the save's own test gives no reason…
        probe.assert_called_once_with(brain.DEFAULT_TEXT_MODEL)   # …so the page's classified test runs
        self.assertEqual(self.route(), ('gemini', 'failed', 'quota'),
                         'TextBrain still asks Gemini first: the hero must not claim Mo AI answers')
        with patch.object(brain, 'probe_gemini', return_value={'status': 'ok', 'model': brain.DEFAULT_TEXT_MODEL,
                                                              'elapsed_ms': 700}):
            self.page.testGemini()
        self.assertEqual(self.route(), ('gemini', 'ok', ''), "a passing test clears the save's failure")

    def test_a_rejected_key_sends_the_route_to_mo_ai(self):
        self.loaded()
        self.sync()
        with patch.object(brain, 'probe_gemini', return_value={'status': 'error', 'model': brain.DEFAULT_TEXT_MODEL,
                                                              'elapsed_ms': 30, 'reason': 'auth'}):
            self.page.testGemini()
        self.assertEqual(self.route(), ('moai-cloud', 'failed', ''))
        self.page.keyChecked('testing', '')             # a new key is being saved
        self.assertEqual(self.route()[:2], ('gemini', 'testing'))
        self.assertEqual(self.page.state['gemini_test']['state'], 'idle', "the old key's test result is cleared")
        self.page.keyChecked('ok', '')
        self.assertEqual(self.route(), ('gemini', 'ok', ''))

    def test_a_save_clears_the_previous_keys_test(self):
        self.loaded()
        self.sync()
        with patch.object(brain, 'probe_gemini', return_value={'status': 'ok', 'model': brain.DEFAULT_TEXT_MODEL,
                                                              'elapsed_ms': 700}):
            self.page.testGemini()
        self.assertEqual(self.page.state['gemini_test']['state'], 'ok')
        with patch.object(brain_page, 'TEST_MODE', True):
            self.page.keyChecked('failed', '')     # the page first hears of a save that already failed
        self.assertEqual(self.page.state['gemini_test']['state'], 'idle', 'no "Works" beside a failed key')
        self.assertEqual(self.route(), ('gemini', 'failed', 'save'))

    def test_key_state_is_handled_once_per_change(self):
        self.loaded()
        self.sync()
        with patch.object(brain, 'probe_gemini', return_value={'status': 'error', 'reason': 'quota', 'elapsed_ms': 1}) as probe:
            self.page.keyChecked('failed', '')
            self.page.keyChecked('failed', '')      # the page re-opened: the same state again
        self.assertEqual(probe.call_count, 1)
        with patch.object(brain, 'probe_gemini', side_effect=AssertionError('probed')):
            self.page.keyChecked('ok', '')
            self.page.keyChecked('failed', 'auth')  # a classified reason needs no second test
        self.assertEqual(self.route(), ('moai-cloud', 'failed', ''))

    def test_the_controllers_first_state_only_answers_until_the_page_has_read(self):
        self.page.keyChecked('set', '')
        self.assertEqual(self.route(), ('gemini', 'set', ''))
        page = BrainPage(self.host)
        self.addCleanup(page.pageHidden)
        self.sync(page)
        with contextlib.ExitStack() as stack:
            for item in self.backends(gemini={**GEMINI, 'has_key': False}):
                stack.enter_context(item)
            page.refresh()
        page.keyChecked('set', '')                      # older than the page's own read of gemini.json
        self.assertEqual((page.state['route_now'], page.state['key_status']), ('moai-cloud', 'missing'))

    def test_review_mode_never_probes_after_a_failed_save(self):
        self.loaded()
        with patch.object(brain_page, 'TEST_MODE', True):
            self.page.keyChecked('failed', '')      # probe_gemini would raise
        self.assertEqual(self.route(), ('gemini', 'failed', 'save'))

    def test_answers_update_the_route(self):
        self.loaded()
        publish = lambda **s: self.page.on_answer('answer', {'status': 'ok', 'elapsed_ms': 1, 'at': time.time(), **s})
        publish(route='moai-cloud', model='x', fallback_reason='quota')
        self.assertEqual(self.route(), ('gemini', 'failed', 'quota'))
        publish(route='gemini', model=brain.DEFAULT_TEXT_MODEL, fallback_reason=None)
        self.assertEqual(self.route(), ('gemini', 'ok', ''))
        publish(route='gemini', model=brain.DEFAULT_TEXT_MODEL, status='cancelled', fallback_reason=None)
        self.assertEqual(self.route(), ('gemini', 'ok', ''), 'a stop proves nothing')
        publish(route='moai-cloud', model='x', fallback_reason='auth')
        self.assertEqual(self.route(), ('moai-cloud', 'failed', ''))
        publish(route='moai-cloud', model='x', fallback_reason='config')
        self.assertEqual(self.route(), ('moai-cloud', 'missing', ''), 'the brain found no key')

    def test_the_qml_reads_the_derived_route_not_the_controllers_key(self):
        qml = (Path(__file__).resolve().parent / 'qml' / 'Mira' / 'BrainPage.qml').read_text()
        self.assertIn('st.route_now', qml)
        self.assertIn('st.key_status', qml)
        # brainKey only feeds the page (keyChecked) and the Save button; it never decides the route.
        uses = [line.strip() for line in qml.splitlines() if 'mira.brainKey' in line]
        self.assertEqual(len(uses), 2, uses)
        self.assertTrue(any('brainKeyNow' in line for line in uses))

    # ── tests and measuring ─────────────────────────────────────────
    def test_cloud_test_sends_base_model_and_wire_but_never_a_key(self):
        self.loaded()
        sent = []

        def post(path, body, timeout=30):
            sent.append((path, dict(body)))
            return {'ok': True, 'reply': 'OK', 'model': 'openrouter/free', 'usage': {'in': 9, 'out': 1}}
        with patch('moai_tools.post', side_effect=post):
            self.page.testCloud()
        path, body = sent[0]
        self.assertEqual(path, '/test')
        self.assertEqual(set(body), {'cloud_base', 'cloud_model', 'cloud_wire'})
        self.assertEqual(body, {'cloud_base': 'https://openrouter.ai/api/v1', 'cloud_model': 'openrouter/free', 'cloud_wire': 'openai'})
        test = self.page.state['cloud_test']
        self.assertEqual((test['state'], test['reply'], test['model']), ('ok', 'OK', 'openrouter/free'))

        self.page.setCloudModel('nvidia/nemotron-3-super-120b-a12b:free')
        with patch('moai_tools.post', side_effect=post):
            self.page.testCloud()
        self.assertEqual(sent[-1][1]['cloud_model'], 'nvidia/nemotron-3-super-120b-a12b:free', 'tests the model Mira uses')

    def test_without_a_pick_the_test_uses_what_the_gateway_uses(self):
        # The agent's config and moai-control's default can differ; the gateway (no model sent) uses
        # moai-control's, which /models reports as `default`.
        self.loaded(config={**CONFIG, 'cloud': {**CONFIG['cloud'], 'model': 'agent/other:free'}})
        sent = []
        with patch('moai_tools.post', side_effect=lambda path, body, timeout=30: sent.append(body) or {'ok': True}):
            self.page.testCloud()
        self.assertEqual(sent[-1]['cloud_model'], 'openrouter/free')
        brain.set_cloud_model('vanished/model:free')     # a pick that left the list is refused by the gateway
        self.loaded(config={**CONFIG, 'cloud': {**CONFIG['cloud'], 'model': 'agent/other:free'}})
        self.assertTrue(self.page.state['pick_missing'])
        with patch('moai_tools.post', side_effect=lambda path, body, timeout=30: sent.append(body) or {'ok': True}):
            self.page.testCloud()
        self.assertEqual(sent[-1]['cloud_model'], 'openrouter/free')

    def test_cloud_test_failures_keep_the_providers_words(self):
        self.loaded()
        with patch('moai_tools.post', return_value={'ok': False, 'error': 'المفتاح مرفوض | key rejected (401): no'}):
            self.page.testCloud()
        test = self.page.state['cloud_test']
        self.assertEqual((test['state'], test['error_ar'], test['error_en']), ('failed', 'المفتاح مرفوض', 'key rejected (401): no'))
        with patch('moai_tools.post', return_value={'error': 'moai_control_unreachable'}):
            self.page.testCloud()
        self.assertEqual(self.page.state['cloud_test']['error_en'], STRINGS['br_unreachable'][1])

    def test_cloud_test_waits_for_the_provider(self):
        self.page.testCloud()     # config not read yet: nothing is sent (post would raise)
        self.assertEqual(self.host.toasts[-1][0], 'error')

    def test_gemini_test_uses_the_chosen_model_and_names_the_reason(self):
        self.sync()
        self.page.setTextModel('gemini-2.5-flash')
        with patch.object(brain, 'probe_gemini', return_value={'status': 'ok', 'model': 'gemini-2.5-flash', 'elapsed_ms': 812}) as probe:
            self.page.testGemini()
        probe.assert_called_once_with('gemini-2.5-flash')
        self.assertEqual(self.page.state['gemini_test'], {'state': 'ok', 'model': 'gemini-2.5-flash', 'ms': 812, 'reason': ''})
        with patch.object(brain, 'probe_gemini', return_value={'status': 'error', 'model': 'gemini-2.5-flash', 'elapsed_ms': 40,
                                                              'reason': 'quota'}):
            self.page.testGemini()
        test = self.page.state['gemini_test']
        self.assertEqual((test['state'], test['reason']), ('failed', 'quota'))
        self.assertIn('br_reason_' + test['reason'], STRINGS)

    def test_measuring_polls_until_done_then_rereads_the_list(self):
        self.loaded()
        running = {**MEASURE, 'measuring': True, 'done': 2, 'total': 8, 'now': 'x'}
        with patch('moai_tools.post', return_value=running) as post:
            self.page.measureNow()
        post.assert_called_once_with('/measure', {}, 30)
        self.assertEqual((self.page.state['measure']['measuring'], self.page.state['measure']['done']), (True, 2))
        self.assertTrue(self.page._poll.isActive(), 'polls while measuring')
        self.assertEqual(self.page._poll.interval(), brain_page.MEASURE_POLL_MS)
        finished = {**MEASURE, 'best': 'nvidia/nemotron-3-super-120b-a12b:free', 'bestLabel': 'Nemotron Super', 'ageDays': 0}
        reads = []

        def tools_get(path, timeout=20):
            reads.append(path)
            return {'/models': MODELS, '/measure': finished}[path]
        self.page._poll.stop()
        with patch('moai_tools.get', side_effect=tools_get):
            self.page._poll_measure()          # what the timer runs
        self.assertEqual(reads, ['/measure', '/models'])
        measure = self.page.state['measure']
        self.assertEqual((measure['measuring'], measure['best_available']), (False, True))
        self.assertFalse(self.page._poll.isActive(), 'no poll once the run is over')

    def test_refreshes_during_a_run_keep_a_single_poll(self):
        self.loaded()
        running = {**MEASURE, 'measuring': True, 'done': 1, 'total': 8}
        reads = []

        def tools_get(path, timeout=20):
            reads.append(path)
            return {'/models': MODELS, '/measure': running}[path]
        with patch('moai_tools.get', side_effect=tools_get), patch('moai_agent.get', return_value=CONFIG), \
                patch.object(brain, 'gemini_settings', return_value=GEMINI), patch('moai_tools.post', return_value=running):
            self.page.measureNow()
            self.page.refresh()
            self.page.refresh()
            self.assertEqual(self.page.findChildren(brain_page.QTimer), [self.page._poll], 'one timer, never a chain per read')
            self.assertTrue(self.page._poll.isActive())
            reads.clear()
            self.page._poll.setInterval(20)
            self.assertTrue(settle(lambda: reads.count('/measure') >= 1, 2.0))
            # Every read that reports a run restarts the same timer: one poll per interval, however many
            # reads asked. After the first tick exactly one more is pending, never three.
            self.page._poll.stop()
            ticks = reads.count('/measure')
        self.assertEqual(ticks, 1)

    def test_leaving_the_page_stops_polling(self):
        self.loaded()
        running = {**MEASURE, 'measuring': True, 'done': 1, 'total': 8}
        with patch('moai_tools.post', return_value=running):
            self.page.measureNow()
        self.assertTrue(self.page._poll.isActive())
        self.page.pageHidden()
        self.assertFalse(self.page._poll.isActive())
        with patch('moai_tools.get', side_effect=lambda path, timeout=20: running):
            self.page._deliver('measure:poll', running)     # a read already on its way
        self.assertFalse(self.page._poll.isActive(), 'a late read does not start polling again')
        with patch('pages.base.TEST_MODE', False), patch('moai_tools.get', side_effect=lambda path, timeout=20:
                                                         {'/models': MODELS, '/measure': running}[path]), \
                patch('moai_agent.get', return_value=CONFIG), patch.object(brain, 'gemini_settings', return_value=GEMINI):
            self.page.activated()
        self.assertTrue(self.page._poll.isActive(), 'coming back resumes it')

    def test_a_failed_new_run_keeps_the_best_and_says_why(self):
        # moai-control keeps the previous best beside the last run's error.
        measure = {**MEASURE, 'error': 'تعذّر الوصول إلى قائمة النماذج المجانية | The free model catalogue could not be reached'}
        state = self.loaded(measure=measure)
        self.assertEqual((state['measure']['state'], state['measure']['best'], state['measure']['error_en']),
                         ('error', 'nex-agi/nex-n2.5-pro:free', 'The free model catalogue could not be reached'))
        qml = (Path(__file__).resolve().parent / 'qml' / 'Mira' / 'BrainPage.qml').read_text()
        # The best line never takes the error's colour, and the reason has its own line.
        self.assertNotIn('measure.state === "error" && !page.measure.measuring ? Theme.danger', qml)
        self.assertIn('page.pick(page.measure.error_ar, page.measure.error_en)', qml)

    def test_a_refused_measurement_says_why(self):
        self.loaded()
        with patch('moai_tools.post', return_value={'error': 'القياس يخصّ النماذج المجانية | Measuring is for free models'}):
            self.page.measureNow()
        measure = self.page.state['measure']
        self.assertEqual((measure['state'], measure['measuring'], measure['error_en']), ('error', False, 'Measuring is for free models'))

    # ── elsewhere ───────────────────────────────────────────────────
    def test_settings_open_through_the_allowed_route(self):
        self.assertTrue(moos_routes.allowed(brain_page.SETTINGS_ROUTE))
        with patch.object(moos_routes, 'open_route', return_value={'status': 'ok'}) as route:
            self.page.openProviderSettings()
            self.page.openPermissionSettings()
        self.assertEqual([c.args[0] for c in route.call_args_list], ['moos://settings/assistant'] * 2)
        with patch.object(moos_routes, 'open_route', return_value={'status': 'error', 'error': 'FileNotFoundError'}):
            self.page.openProviderSettings()
        self.assertEqual(self.host.toasts[-1], ('error', STRINGS['br_route_failed'][0]))

    def test_key_help_opens_the_fixed_page(self):
        with patch.object(brain_page.QDesktopServices, 'openUrl') as open_url:
            self.page.openKeyHelp()
        self.assertEqual(open_url.call_args.args[0].toString(), 'https://aistudio.google.com/apikey')

    def test_the_answer_that_just_finished_is_shown(self):
        summary = {'route': 'moai-cloud', 'model': 'nvidia/nemotron-3-super-120b-a12b:free', 'status': 'ok',
                   'elapsed_ms': 2140, 'fallback_reason': 'quota', 'rounds': 2, 'tools': 1, 'at': time.time(),
                   'model_refused': ''}
        worker = threading.Thread(target=brain._publish, args=(summary,))
        worker.start()
        worker.join()
        self.assertTrue(settle(lambda: self.page.state['last'].get('route') == 'moai-cloud'))
        last = self.page.state['last']
        self.assertEqual((last['model'], last['ms'], last['reason'], last['tools']),
                         ('nvidia/nemotron-3-super-120b-a12b:free', 2140, 'quota', 1))
        self.assertRegex(last['time'], r'^\d\d:\d\d$')

    # ── words ───────────────────────────────────────────────────────
    def test_the_privacy_line_says_what_every_prompt_carries(self):
        """br_priv_local must match tools.system_instruction / conversation_turns: memory and profile
        leave the computer with every question."""
        import tools
        with patch('mira_memory.load', return_value={'favorite_color': 'MARK-MEMORY'}), \
                patch('mira_memory.profile_text', return_value='MARK-PROFILE'), \
                patch.object(tools, 'machine_block', return_value=''):
            prompt = tools.system_instruction('en', None, channel='text')
        self.assertIn('MARK-MEMORY', prompt)
        self.assertIn('MARK-PROFILE', prompt)
        with patch('mira_memory.recent_messages', return_value=[{'role': 'user', 'text': 'MARK-HISTORY'}]):
            self.assertIn('MARK-HISTORY', json.dumps(tools.conversation_turns(12)))
        ar, en = STRINGS['br_priv_local']
        self.assertIn('with each question', en)
        self.assertIn('recent conversation', en)
        self.assertIn('يُرسلان مع كل سؤال', ar)
        for claim in ('stay on this computer', 'تبقى على هذا الكمبيوتر'):
            self.assertNotIn(claim, ar + en)

    def test_ages_and_failures_read_naturally(self):
        qml = (Path(__file__).resolve().parent / 'qml' / 'Mira' / 'BrainPage.qml').read_text()
        self.assertNotIn('br_best_age', qml)
        for key in ('br_age_today', 'br_age_yesterday', 'br_age_two', 'br_age_few', 'br_age_many'):
            self.assertIn(key, qml)
        self.assertNotIn('"Gemini: "', qml, 'a Latin-first line in Arabic reads backwards')
        self.assertNotIn('br_test_failed', qml, 'the pill already says Failed')
        self.assertEqual(STRINGS['br_age_many'][0], 'قبل {days} يوماً')

    def test_words_are_bilingual_and_carry_no_other_os_name(self):
        for key, pair in STRINGS.items():
            self.assertEqual(len(pair), 2, key)
            self.assertTrue(pair[0].strip() and pair[1].strip(), key)
            for word in ('Fedora', 'Red Hat', 'fedora'):
                self.assertNotIn(word, pair[0] + pair[1], key)
        self.assertEqual(set(i18n.table('en')) >= set(STRINGS), True)
        for reason in brain.REASONS:
            self.assertIn('br_reason_' + reason, STRINGS)

    def test_every_slot_qml_calls_exists(self):
        import re
        from pathlib import Path
        qml = (Path(__file__).resolve().parent / 'qml' / 'Mira' / 'BrainPage.qml').read_text()
        called = set(re.findall(r'\bmira\.brainPage\.(\w+)\s*\(', qml))
        meta = self.page.metaObject()
        slots = {bytes(meta.method(i).name().data()).decode() for i in range(meta.methodCount())}
        self.assertTrue(called)
        self.assertEqual(sorted(called - slots), [])
        used = set(re.findall(r'\bmira\.s\.(br_\w+)', qml))
        self.assertEqual(sorted(used - set(STRINGS)), [])


if __name__ == '__main__':
    unittest.main()
