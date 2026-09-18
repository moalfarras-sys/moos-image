#!/usr/bin/env python3
"""Execute the free-only boundary, not merely catalogue labels."""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

# ── ISOLATE THE OWNER'S OWN SETTINGS BEFORE ANYTHING IS IMPORTED ─────────────────────────────
#
# `selected_provider()` reads $XDG_CONFIG_HOME/moai-agent/state.json — the LIVE choice the person
# using this machine made — and `selected_cost_policy()` turns that into free-or-paid, which is
# what decides whether a paid model is refused with 409 or admitted.
#
# So two of these tests asserted the free-only behaviour while reading whatever the owner had
# selected. On a CI runner there is no such file, they pass, and the gate looks green forever. On
# the maintainer's own Oracle A1, where Settings says `openrouter-paid`, they FAIL — and `just
# check` is exactly what AGENTS.md tells every contributor to run before pushing. A gate that only
# passes on a machine shaped like CI teaches people that a red gate means nothing, which is the
# one thing this repository cannot afford.
#
# Pointing HOME and XDG_CONFIG_HOME at an empty directory for the whole module fixes it for every
# test here, not just the two that happened to notice: none of them is about the host's config.
#
# XDG_STATE_HOME belongs in the same sentence: it is where `moai-measure-free` writes the order
# this machine measured, and the picker's order and notes are read from it. A maintainer who has
# measured their own free models would otherwise run these tests against their own numbers.
_ISOLATED = tempfile.TemporaryDirectory()
os.environ["XDG_CONFIG_HOME"] = str(Path(_ISOLATED.name) / "config")
os.environ["XDG_STATE_HOME"] = str(Path(_ISOLATED.name) / "state")
os.environ["HOME"] = _ISOLATED.name

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(ROOT/path))
    spec=importlib.util.spec_from_loader(name,loader)
    module=importlib.util.module_from_spec(spec);loader.exec_module(module)
    return module
policy=load('moai_cloud_policy','system_files/usr/lib/moai/moai_cloud_policy.py')
gateway=load('moai_free_gateway','system_files/usr/bin/moai-gateway')
migration=load('moai_cloud_migrate','system_files/usr/libexec/moai-cloud-migrate')

class FreePolicy(unittest.TestCase):
    def test_paid_local_untrusted_and_ambiguous_routes_rejected(self):
        for base,model in [('http://127.0.0.1:11434','qwen3'),
                           ('https://openrouter.ai.evil/api/v1','openrouter/free'),
                           (policy.BASE,'openai/gpt-oss-120b'),
                           (policy.BASE,'vendor/model:free:online'),
                           (policy.BASE+'?key=x','openrouter/free')]:
            with self.subTest(base=base,model=model), self.assertRaises(ValueError):
                policy.validate(base,model)
    def test_caller_cannot_enable_paid_plugins_or_fallbacks(self):
        result=policy.request_body({'messages':[], 'plugins':[{'id':'web'}],
            'models':['paid/model'],'provider':{'max_price':{'prompt':100}},
            'audio':{'voice':'paid'},'modalities':['audio']},'openrouter/free')
        self.assertEqual(set(result),{'messages','model','provider'})
        self.assertTrue(all(v==0 for v in result['provider']['max_price'].values()))
    def test_model_catalog_rejects_nonzero_missing_nan_and_paid(self):
        items=[{'id':'vendor/model:free','pricing':{'prompt':'0','completion':'0'}},
               {'id':'vendor/other:free','pricing':{'prompt':'NaN'}},
               {'id':'vendor/paid:free','pricing':{'request':'1'}},
               {'id':'vendor/no-price:free'}, {'id':'vendor/paid','pricing':{'prompt':'0'}}]
        self.assertEqual(policy.visible_models(items),items[:1])
    def test_paid_requires_explicit_selection_and_free_stays_zero(self):
        with self.assertRaises(ValueError):
            policy.request_body({'messages':[]},'openai/gpt-5.4-mini')
        paid=policy.request_body({'messages':[]},'openai/gpt-5.4-mini',allow_paid=True)
        self.assertEqual(paid['model'],'openai/gpt-5.4-mini')
        free=policy.request_body({'models':['paid/model']},policy.DEFAULT_MODEL,allow_paid=True)
        self.assertNotIn('models',free)
        self.assertEqual(free['provider']['max_price']['prompt'],0)

    def catalogue(self, *entries):
        return policy.visible_models([
            {'id': model_id, 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': params, 'context_length': 262144}
            for model_id, params in entries])

    def test_automatic_route_prefers_measured_speed_over_size(self):
        items = self.catalogue(('nvidia/nemotron-3-ultra-550b-a55b:free', ['tools', 'reasoning']),
                               ('nex-agi/nex-n2.5-mini:free', ['tools', 'reasoning']),
                               ('nex-agi/nex-n2.5-pro:free', ['tools', 'reasoning']))
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            # The 550B model is the largest and was 25 s per answer when measured; size loses.
            self.assertEqual(policy.automatic_model(require_tools=True), 'nex-agi/nex-n2.5-pro:free')
            self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')
            self.assertEqual(policy.automatic_candidates(limit=3)[-2:],
                             ['nvidia/nemotron-3-ultra-550b-a55b:free', policy.DEFAULT_MODEL])

    def test_the_ranking_this_machine_measured_outranks_the_shipped_order(self):
        """`moai-measure-free` writes what actually answered here; it wins for 30 days.

        The shipped preference is a snapshot of one machine on one day, and the free
        catalogue turns over every few weeks. A machine that measured its own order
        must use it — but only to ORDER models the zero-price check already admitted.
        """
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']),
                               ('vendor/measured-here:free', ['tools']))
        with tempfile.TemporaryDirectory() as home:
            ranking = Path(home) / 'moai/free-ranking.json'
            ranking.parent.mkdir(parents=True)
            ranking.write_text(json.dumps({
                'measuredAt': policy.time.time(),
                'chat': ['vendor/measured-here:free'],
                'tools': ['vendor/measured-here:free'],
            }))
            with patch.dict(os.environ, {'XDG_STATE_HOME': home}), \
                    patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                    patch.dict(policy._cooldown, {}, clear=True):
                self.assertEqual(policy.automatic_model(require_tools=True),
                                 'vendor/measured-here:free')
                self.assertEqual(policy.measured_ranking('tools'),
                                 ('vendor/measured-here:free',))

    def test_a_stale_corrupt_or_priced_ranking_is_ignored(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']),
                               ('vendor/measured-here:free', ['tools']))
        cases = {
            'stale': {'measuredAt': policy.time.time() - policy.RANKING_MAX_AGE - 60,
                      'tools': ['vendor/measured-here:free']},
            'undated': {'tools': ['vendor/measured-here:free']},
            'empty': {'measuredAt': policy.time.time(), 'tools': []},
            'priced': {'measuredAt': policy.time.time(), 'tools': ['openai/gpt-5']},
        }
        for name, document in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as home:
                ranking = Path(home) / 'moai/free-ranking.json'
                ranking.parent.mkdir(parents=True)
                ranking.write_text(json.dumps(document))
                with patch.dict(os.environ, {'XDG_STATE_HOME': home}), \
                        patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                        patch.dict(policy._cooldown, {}, clear=True):
                    self.assertEqual(policy.automatic_model(require_tools=True),
                                     'nex-agi/nex-n2.5-pro:free')
        with tempfile.TemporaryDirectory() as home:
            ranking = Path(home) / 'moai/free-ranking.json'
            ranking.parent.mkdir(parents=True)
            ranking.write_text('{not json')
            with patch.dict(os.environ, {'XDG_STATE_HOME': home}):
                self.assertEqual(policy.measured_ranking(), ())

    def test_the_picker_puts_what_this_machine_measured_above_what_shipped(self):
        """Seconds measured here outrank an adjective measured on another machine.

        The shipped `CURATED_FREE` order calls Nex Pro the one to pick. On the machine
        below, Nex Mini answered in 0.6 s and Pro took 2.7 s — and a picker that still
        listed Pro first would be recommending against its own measurement. The rows
        that were measured here therefore come first, carrying their own numbers; the
        rest of the curated list follows with the reason that shipped; and a model the
        run caught failing is neither hidden nor promoted — it drops to "all free
        models" saying which half it failed.
        """
        control = load('moai_control_measure', 'system_files/usr/bin/moai-control')
        document = {
            'measuredAt': policy.time.time(),
            'chat': ['nex-agi/nex-n2.5-mini:free', 'nex-agi/nex-n2.5-pro:free',
                     'vendor/talks-only:free'],
            # `vendor/talks-only:free` is here on purpose: ranking files written before
            # 2026-09-18 listed a model in `tools` when it had answered in Arabic and
            # never emitted a tool call, and those files stay readable for thirty days.
            # It must NOT reach the measured group.
            'tools': ['nex-agi/nex-n2.5-mini:free', 'nex-agi/nex-n2.5-pro:free',
                      'vendor/talks-only:free'],
            'results': [
                {'model': 'nex-agi/nex-n2.5-mini:free', 'chatSeconds': 0.6, 'toolSeconds': 0.87,
                 'answeredArabic': True, 'calledTool': True},
                {'model': 'nex-agi/nex-n2.5-pro:free', 'chatSeconds': 2.69, 'toolSeconds': 1.74,
                 'answeredArabic': True, 'calledTool': True},
                {'model': 'vendor/mumbled-english:free', 'chatSeconds': 0.1, 'toolSeconds': 0.1,
                 'answeredArabic': False, 'calledTool': True},
                {'model': 'vendor/talks-only:free', 'chatSeconds': 0.3, 'toolSeconds': 0.3,
                 'answeredArabic': True, 'calledTool': False},
                {'model': 'vendor/refused:free', 'chatSeconds': 0.08, 'toolSeconds': 0.08,
                 'answeredArabic': False, 'calledTool': False,
                 'chatError': 'HTTP 403', 'toolError': 'HTTP 403'},
                # A CURATED model the run caught failing keeps its name and loses the
                # shipped sentence about how good it is.
                {'model': 'cohere/north-mini-code:free', 'chatSeconds': 0.2, 'toolSeconds': 0.2,
                 'answeredArabic': False, 'calledTool': False},
            ],
        }
        rows = [{'id': 'cloud:' + model} for model in (
            policy.DEFAULT_MODEL, 'nex-agi/nex-n2.5-pro:free', 'nex-agi/nex-n2.5-mini:free',
            'cohere/north-mini-code:free', 'vendor/mumbled-english:free',
            'vendor/talks-only:free', 'vendor/refused:free')]
        with tempfile.TemporaryDirectory() as home:
            ranking = Path(home) / 'moai/free-ranking.json'
            ranking.parent.mkdir(parents=True)
            ranking.write_text(json.dumps(document))
            with patch.dict(os.environ, {'XDG_STATE_HOME': home}), \
                    patch.object(control.cloud_policy, 'automatic_model',
                                 return_value='nex-agi/nex-n2.5-mini:free'):
                picker = control.curated_cloud_models(rows)
        groups = {row['id']: row['group'] for row in picker}
        notes = {row['id']: row['note_en'] for row in picker}
        self.assertEqual([(row['id'], row['group']) for row in picker[:3]], [
            ('cloud:' + policy.DEFAULT_MODEL, 'auto'),
            ('cloud:nex-agi/nex-n2.5-mini:free', 'measured'),
            ('cloud:nex-agi/nex-n2.5-pro:free', 'measured'),
        ])
        # Only models that passed BOTH halves are in the measured group.
        self.assertEqual(sorted(row['id'] for row in picker if row['group'] == 'measured'),
                         ['cloud:nex-agi/nex-n2.5-mini:free', 'cloud:nex-agi/nex-n2.5-pro:free'])
        # The first row names what "automatic" resolves to right now, so it is a
        # promise the owner can check instead of one they have to trust.
        self.assertIn('Nex Mini', picker[0]['note_en'])
        self.assertEqual(notes['cloud:nex-agi/nex-n2.5-mini:free'],
                         '0.60s to answer · 0.87s to act — measured here')
        self.assertEqual(notes['cloud:nex-agi/nex-n2.5-pro:free'],
                         '2.7s to answer · 1.7s to act — measured here')
        self.assertEqual(picker[1]['label_en'], 'Nex Mini')
        # A model listed in an OLD ranking file for a half it failed is not promoted,
        # and the row says which half — the branch that used to be unreachable.
        self.assertEqual(groups['cloud:vendor/talks-only:free'], 'all')
        self.assertEqual(notes['cloud:vendor/talks-only:free'], "Didn't run the action")
        self.assertEqual(notes['cloud:vendor/mumbled-english:free'], "Didn't answer in Arabic")
        # The provider's own refusal is the provider's, not the model's.
        self.assertEqual(notes['cloud:vendor/refused:free'], 'The provider refused it — HTTP 403')
        self.assertIn('المزوّد رفض الطلب', dict(
            (row['id'], row['note_ar']) for row in picker)['cloud:vendor/refused:free'])
        # A curated model the run caught failing keeps its NAME and loses the pitch.
        self.assertEqual(groups['cloud:cohere/north-mini-code:free'], 'all')
        labels = {row['id']: row.get('label_en', '') for row in picker}
        self.assertEqual(labels['cloud:cohere/north-mini-code:free'], 'North Code')
        self.assertNotEqual(notes['cloud:cohere/north-mini-code:free'], 'Built for code')
        self.assertTrue(all(row['note_ar'] for row in picker))
        # With nothing measured here, the shipped order stands and nothing claims
        # a measurement: the curated group is exactly what it was before.
        with tempfile.TemporaryDirectory() as empty:
            with patch.dict(os.environ, {'XDG_STATE_HOME': empty}), \
                    patch.object(control.cloud_policy, 'automatic_model',
                                 return_value=policy.DEFAULT_MODEL):
                plain = control.curated_cloud_models(rows)
        self.assertEqual([row['group'] for row in plain][:4], ['auto', 'curated', 'curated', 'curated'])
        self.assertEqual({row['id']: row.get('note_en', '') for row in plain}
                         ['cloud:cohere/north-mini-code:free'], 'Built for code')
        self.assertNotIn('measured here', plain[1]['note_en'])
        self.assertNotIn('Right now', plain[0]['note_en'])

    def test_the_action_ranking_counts_the_answer_the_same_turn_gives(self):
        """Measured live on 2026-09-18, and the reason this score has two halves.

        The tool ranking decides which model drives the agent loop, and that loop does
        not only call tools — it also says what it did. Ranked on the tool prompt alone,
        the 550B Nemotron won this run: it called the tool in 1.44 s. It then took
        16.56 s to write one Arabic sentence, while Ling did both in 2.91 s together.
        Whoever is waiting is waiting for the whole turn.
        """
        measurer = load('moai_measure_free', 'system_files/usr/bin/moai-measure-free')
        # chat seconds, tool seconds, and what each turn came back with — the numbers
        # this station actually recorded on 2026-09-18.
        live = {
            'nvidia/nemotron-3-ultra-550b-a55b:free': (16.56, 1.44, 'خفضت الصوت.', True),
            'inclusionai/ling-3.0-flash-vl:free': (1.29, 1.62, 'خفضت الصوت.', True),
            'nex-agi/nex-n2.5-mini:free': (3.12, 1.23, 'خفضت الصوت.', False),
            'thinkingmachines/inkling:free': (0.07, 0.07, 'Lowered the volume.', False),
        }

        def ask(model, prompt, schema=None):
            chat_seconds, tool_seconds, answer, called = live[model]
            if schema is None:
                return chat_seconds, {'content': answer}, ''
            # The prompt says "mute it", and MoOS's own `set_volume` description says
            # "To silence use set_mute" — so only `set_mute` counts as having acted.
            self.assertEqual(sorted(s['function']['name'] for s in schema),
                             ['set_mute', 'set_volume'])
            calls = [{'function': {'name': measurer.TOOL_NAME}}] if called else []
            return tool_seconds, {'content': '', 'tool_calls': calls}, ''

        with patch.object(measurer, 'ask', ask):
            results = [measurer.measure(model) for model in live]
        ranked = [row['model'] for row in sorted(results, key=lambda row: row['toolScore'],
                                                 reverse=True)]
        self.assertEqual(ranked[0], 'inclusionai/ling-3.0-flash-vl:free')
        # A model that did not call the tool never outranks one that did, however fast —
        # and an English answer to an Arabic question is last whatever its seconds say.
        self.assertEqual(ranked[-2:], ['nex-agi/nex-n2.5-mini:free', 'thinkingmachines/inkling:free'])
        # The answer ranking is still about answering, so the 550B model stays below Ling.
        chat = [row['model'] for row in sorted(results, key=lambda row: row['chatScore'],
                                               reverse=True)]
        self.assertEqual(chat[0], 'inclusionai/ling-3.0-flash-vl:free')
        self.assertEqual(chat[-1], 'thinkingmachines/inkling:free')

    def test_a_second_measure_request_reports_instead_of_deadlocking_the_server(self):
        """Found live: the second click hung moai-control, and everything behind it.

        `start_measurement()` reported the already-running state by calling
        `measure_state()` from inside the lock it had just taken, and threading.Lock
        is not reentrant. The lock was then never released, so /measure, /models and
        /quick all hung for the rest of the session — from one extra click.
        """
        control = load('moai_control_measure_lock', 'system_files/usr/bin/moai-control')
        started = []

        class Process:
            stdout = iter(())
            def wait(self, timeout=None): started.append('waited'); return 0

        with patch.object(control.subprocess, 'Popen', lambda *a, **k: Process()), \
                patch.object(control.cloud_policy, 'automatic_candidates',
                             return_value=['nex-agi/nex-n2.5-mini:free']):
            # Hold the run open so the second request takes the "already running" path.
            with control._measure_lock:
                control._measure.update(running=True, done=2, total=8, now='x', error='')
            done = threading.Event()
            result = {}

            def second():
                result['state'] = control.start_measurement()
                done.set()

            threading.Thread(target=second, daemon=True).start()
            self.assertTrue(done.wait(5), 'start_measurement deadlocked on its own lock')
            self.assertEqual((result['state']['measuring'], result['state']['done']), (True, 2))
            # Nothing was launched a second time, and the lock is free afterwards.
            self.assertEqual(started, [])
            self.assertTrue(control._measure_lock.acquire(timeout=1))
            control._measure_lock.release()
            with control._measure_lock:
                control._measure.update(running=False)

    def test_each_ranking_list_holds_only_the_models_that_passed_that_half(self):
        """A model cannot be ranked for a half it failed — that is the file's whole claim.

        Both lists used to be written from `answeredArabic OR calledTool`, so a model
        that answered in Arabic and never emitted a tool call still appeared in `tools`.
        The picker then read it as "measured, and it acted in 0.3 s", and the automatic
        route preferred it for thirty days on the path that drives the agent loop.
        """
        measurer = load('moai_measure_writes', 'system_files/usr/bin/moai-measure-free')
        results = [
            {'model': 'a/both:free', 'chatSeconds': 1.0, 'toolSeconds': 1.0,
             'answeredArabic': True, 'calledTool': True, 'chatError': '', 'toolError': '',
             'chatScore': (True, -1.0), 'toolScore': (True, True, -2.0)},
            {'model': 'a/talks-only:free', 'chatSeconds': 0.3, 'toolSeconds': 0.3,
             'answeredArabic': True, 'calledTool': False, 'chatError': '', 'toolError': '',
             'chatScore': (True, -0.3), 'toolScore': (False, True, -0.6)},
            {'model': 'a/acts-only:free', 'chatSeconds': 0.4, 'toolSeconds': 0.4,
             'answeredArabic': False, 'calledTool': True, 'chatError': '', 'toolError': '',
             'chatScore': (False, -0.4), 'toolScore': (True, False, -0.8)},
            {'model': 'a/refused:free', 'chatSeconds': 0.08, 'toolSeconds': 0.08,
             'answeredArabic': False, 'calledTool': False,
             'chatError': 'HTTP 403', 'toolError': 'HTTP 403',
             'chatScore': (False, -0.08), 'toolScore': (False, False, -0.16)},
        ]
        with tempfile.TemporaryDirectory() as home:
            ranking = Path(home) / 'ranking.json'
            with patch.object(measurer, 'RANKING', ranking), \
                    patch.object(measurer.policy, 'automatic_candidates',
                                 return_value=[row['model'] for row in results]), \
                    patch.object(measurer, 'measure', lambda model: next(
                        row for row in results if row['model'] == model)):
                self.assertEqual(measurer.main(), 0)
            document = json.loads(ranking.read_text())
        # Each list holds only that half's passers. Within `tools`, a model that also
        # answered in Arabic outranks one that only acted — the loop does both.
        self.assertEqual(document['chat'], ['a/talks-only:free', 'a/both:free'])
        self.assertEqual(document['tools'], ['a/both:free', 'a/acts-only:free'])
        # Every model is still in `results`, with the reason it fell out.
        self.assertEqual(sorted(row['model'] for row in document['results']),
                         ['a/acts-only:free', 'a/both:free', 'a/refused:free', 'a/talks-only:free'])
        self.assertEqual(next(row for row in document['results']
                              if row['model'] == 'a/refused:free')['chatError'], 'HTTP 403')

    def test_measured_results_refuses_a_priced_or_unreadable_row(self):
        """A ranking file can order free models. It can never introduce one."""
        with tempfile.TemporaryDirectory() as home:
            ranking = Path(home) / 'moai/free-ranking.json'
            ranking.parent.mkdir(parents=True)
            ranking.write_text(json.dumps({'measuredAt': policy.time.time(), 'results': [
                {'model': 'openai/gpt-5', 'chatSeconds': 0.1, 'toolSeconds': 0.1},
                {'model': 'nex-agi/nex-n2.5-mini:free', 'chatSeconds': 'fast', 'toolSeconds': 1},
                {'model': 'nex-agi/nex-n2.5-pro:free', 'chatSeconds': 1.5, 'toolSeconds': 2.5,
                 'answeredArabic': True, 'calledTool': True},
                'not-a-row',
            ]}))
            with patch.dict(os.environ, {'XDG_STATE_HOME': home}):
                self.assertEqual(list(policy.measured_results()), ['nex-agi/nex-n2.5-pro:free'])
            ranking.write_text(json.dumps({'measuredAt': policy.time.time() - policy.RANKING_MAX_AGE - 60,
                                           'results': [{'model': 'nex-agi/nex-n2.5-pro:free'}]}))
            with patch.dict(os.environ, {'XDG_STATE_HOME': home}):
                self.assertEqual(policy.measured_results(), {})

    def test_an_unmeasured_model_is_ranked_by_the_window_it_can_hold(self):
        """A system agent carries a long transcript; context outranks parameter count."""
        items = policy.visible_models([
            {'id': 'vendor/small-window-120b:free', 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': ['tools'], 'context_length': 32768},
            {'id': 'vendor/long-window-flash:free', 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': ['tools'], 'context_length': 1048576}])
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_model(require_tools=True),
                             'vendor/long-window-flash:free')

    def test_measured_preference_never_admits_a_priced_model(self):
        items = policy.visible_models([
            {'id': 'nex-agi/nex-n2.5-pro:free', 'pricing': {'prompt': '0.1'},
             'supported_parameters': ['tools']},
            {'id': 'vendor/big-400b:free', 'pricing': {'prompt': '0', 'completion': '0'},
             'supported_parameters': ['tools']}])
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_candidates(require_tools=True, limit=5),
                             ['vendor/big-400b:free', policy.DEFAULT_MODEL])

    def test_catalogue_failure_uses_official_zero_price_router(self):
        with patch.object(policy, '_catalogue', (0, [])), \
                patch.object(policy.urllib.request, 'urlopen', side_effect=OSError('offline')):
            self.assertEqual(policy.automatic_candidates(require_tools=True),
                             [policy.DEFAULT_MODEL])
        body = policy.request_body({'messages': [], 'tools': [{'type': 'function'}]},
                                   policy.DEFAULT_MODEL)
        self.assertTrue(all(value == 0 for value in body['provider']['max_price'].values()))

    def test_catalogue_refresh_failure_keeps_last_verified_models(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']))
        with patch.object(policy, '_catalogue', (0, items)), \
                patch.object(policy.urllib.request, 'urlopen', side_effect=OSError('offline')), \
                patch.dict(policy._cooldown, {}, clear=True):
            self.assertEqual(policy.automatic_candidates(),
                             ['nex-agi/nex-n2.5-pro:free', policy.DEFAULT_MODEL])

    def test_refused_free_model_cools_down_then_returns(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']),
                               ('dots-studio/dots-3-note-preview:free', ['tools']))
        now = policy.time.monotonic()
        with patch.object(policy, '_catalogue', (now, items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            policy.note_upstream_failure('nex-agi/nex-n2.5-pro:free', 429)
            self.assertEqual(policy.automatic_model(), 'dots-studio/dots-3-note-preview:free')
            policy.note_upstream_failure('dots-studio/dots-3-note-preview:free', 401)
            self.assertEqual(policy.automatic_model(), 'dots-studio/dots-3-note-preview:free')
            with patch.object(policy, '_catalogue', (now + 601, items)), \
                    patch.object(policy.time, 'monotonic', return_value=now + 601):
                self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')

    def test_curated_models_are_free_measured_and_named_in_both_languages(self):
        ids = [entry[0] for entry in policy.CURATED_FREE]
        self.assertEqual(len(ids), len(set(ids)))
        for model_id, name, arabic, english in policy.CURATED_FREE:
            with self.subTest(model=model_id):
                self.assertTrue(model_id.endswith(':free'))
                self.assertTrue(policy.free_model(model_id))
                self.assertTrue(name and english)
                self.assertRegex(arabic, '[\u0600-\u06ff]')
        for route in policy.MEASURED_PREFERENCE.values():
            self.assertTrue(set(route) <= set(ids), route)
        self.assertNotIn('dots-studio/dots-3-note-preview:free', ids)

    def test_every_candidate_cooled_still_answers(self):
        items = self.catalogue(('nex-agi/nex-n2.5-pro:free', ['tools']))
        with patch.object(policy, '_catalogue', (policy.time.monotonic(), items)), \
                patch.dict(policy._cooldown, {}, clear=True):
            policy.note_upstream_failure('nex-agi/nex-n2.5-pro:free', 503)
            self.assertEqual(policy.automatic_model(), 'nex-agi/nex-n2.5-pro:free')

    def test_gateway_refuses_paid_before_network(self):
        handler=object.__new__(gateway.Handler)
        handler._cloud_cfg=lambda cfg:(policy.BASE,'fixture','openai')
        errors=[];calls=[]
        handler._err=lambda code,msg:errors.append(code)
        handler._proxy=lambda *args,**kwargs:calls.append((args,kwargs))
        handler._to_cloud({'messages':[]},b'{}','vendor/paid',{})
        self.assertEqual(errors,[409]);self.assertEqual(calls,[])
        opened=[]
        handler._open_upstream=lambda method,url,headers,body:(opened.append(json.loads(body)),'upstream')[1]
        with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=['vendor/model:free']):
            handler._to_cloud({'messages':[],'plugins':[{'id':'web'}]},b'{}',policy.DEFAULT_MODEL,{})
        self.assertEqual([kwargs.get('upstream') for _,kwargs in calls],['upstream'])
        self.assertNotIn('plugins',opened[0])
        self.assertTrue(all(v==0 for v in opened[0]['provider']['max_price'].values()))

    def gateway_handler(self):
        handler=object.__new__(gateway.Handler)
        handler._cloud_cfg=lambda cfg:(policy.BASE,'fixture','openai')
        handler.errors=[];handler.opened=[];handler.relayed=[]
        handler._err=lambda code,msg:handler.errors.append(code)
        real_proxy=gateway.Handler._proxy
        def proxy(method,url,headers,body,wire,streaming,upstream=None):
            if upstream is not None:
                handler.relayed.append(upstream); return None
            return real_proxy(handler,method,url,headers,body,wire,streaming)
        handler._proxy=proxy
        return handler

    def http_error(self,code):
        import io, urllib.error
        return urllib.error.HTTPError(policy.BASE,code,'upstream',{},io.BytesIO(b'{"error":"busy"}'))

    def test_automatic_route_skips_a_refused_free_model_before_answering(self):
        handler=self.gateway_handler()
        replies=iter([self.http_error(429),'second'])
        def open_upstream(method,url,headers,body):
            handler.opened.append(json.loads(body)['model'])
            reply=next(replies)
            if isinstance(reply,Exception): raise reply
            return reply
        handler._open_upstream=open_upstream
        with patch.object(gateway.cloud_policy,'automatic_candidates',
                          return_value=['a/one:free','b/two:free','c/three:free']), \
                patch.dict(gateway.cloud_policy._cooldown,{},clear=True):
            handler._to_cloud({'messages':[]},b'{}',policy.DEFAULT_MODEL,{})
            self.assertIn('a/one:free',gateway.cloud_policy._cooldown)
        self.assertEqual(handler.opened,['a/one:free','b/two:free'])
        self.assertEqual(handler.relayed,['second']);self.assertEqual(handler.errors,[])
        self.assertEqual(handler.moai_model,'b/two:free')

    def test_explicit_models_and_auth_errors_are_never_retried(self):
        for model,candidates,code in (('a/one:free',[],429),(policy.DEFAULT_MODEL,['a/one:free','b/two:free'],401)):
            with self.subTest(model=model,code=code):
                handler=self.gateway_handler()
                def open_upstream(method,url,headers,body,handler=handler,code=code):
                    handler.opened.append(json.loads(body)['model']); raise self.http_error(code)
                handler._open_upstream=open_upstream
                with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=candidates), \
                        patch.dict(gateway.cloud_policy._cooldown,{},clear=True):
                    handler._to_cloud({'messages':[]},b'{}',model,{})
                self.assertEqual(handler.opened,['a/one:free']);self.assertEqual(handler.errors,[code])

    def test_automatic_route_reports_the_last_refusal_when_every_free_model_fails(self):
        handler=self.gateway_handler()
        def open_upstream(method,url,headers,body):
            handler.opened.append(json.loads(body)['model']); raise self.http_error(429)
        handler._open_upstream=open_upstream
        with patch.object(gateway.cloud_policy,'automatic_candidates',return_value=['a/one:free','b/two:free']), \
                patch.dict(gateway.cloud_policy._cooldown,{},clear=True):
            handler._to_cloud({'messages':[]},b'{}',policy.DEFAULT_MODEL,{})
        self.assertEqual(handler.opened,['a/one:free','b/two:free']);self.assertEqual(handler.errors,[429])

    def test_absent_hermes_runtime_answers_directly_and_says_so(self):
        handler=object.__new__(gateway.Handler)
        errors=[]
        handler._err=lambda code,msg:errors.append(code)
        started=[]
        with patch.object(gateway,'hermes_runtime_installed',return_value=False), \
                patch.object(gateway.subprocess,'run',side_effect=lambda *a,**k:started.append(a)):
            self.assertIs(handler._to_hermes({'messages':[]}),False)
        self.assertEqual(handler.moai_agent,'direct-fallback')
        self.assertEqual(errors,[]);self.assertEqual(started,[])

    def test_installed_or_unknown_hermes_is_never_silently_substituted(self):
        for installed in (True,None):
            with self.subTest(installed=installed), tempfile.TemporaryDirectory() as runtime:
                handler=object.__new__(gateway.Handler)
                errors=[]
                handler._err=lambda code,msg,errors=errors:errors.append(code)
                with patch.object(gateway,'hermes_runtime_installed',return_value=installed), \
                        patch.object(gateway,'PORT',8095), \
                        patch.dict(gateway.os.environ,{'XDG_RUNTIME_DIR':runtime}):
                    self.assertIs(handler._to_hermes({'messages':[]}),True)
                self.assertEqual(errors,[503])

    def test_first_message_waits_for_the_adapter_it_just_started(self):
        # Measured 2026-09-12 after a reboot: the adapter reported ready 2 s after the first
        # message started it, and a single 1 s probe had already answered 503.
        class Healthy:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): return False
        for ready_on_probe,wait,expected in ((3,5.0,[]),(None,0.3,[503])):
            with self.subTest(ready_on_probe=ready_on_probe), tempfile.TemporaryDirectory() as runtime:
                (Path(runtime)/'moai-hermes').mkdir()
                (Path(runtime)/'moai-hermes/token').write_text('fixture-token')
                handler=object.__new__(gateway.Handler)
                errors=[];proxied=[];probes=[];started=[]
                handler._err=lambda code,msg,errors=errors:errors.append(code)
                handler._proxy=lambda *args,**kwargs:proxied.append(args[1])
                def urlopen(req,timeout=0,probes=probes,ready_on_probe=ready_on_probe):
                    probes.append(req.full_url)
                    if ready_on_probe is None or len(probes)<ready_on_probe:
                        raise gateway.urllib.error.URLError('adapter still starting')
                    return Healthy()
                with patch.object(gateway,'hermes_runtime_installed',return_value=True), \
                        patch.object(gateway,'PORT',8080), patch.object(gateway,'HERMES_START_WAIT',wait), \
                        patch.object(gateway.subprocess,'run',side_effect=lambda *a,**k:started.append(a[0])), \
                        patch.object(gateway.urllib.request,'urlopen',side_effect=urlopen), \
                        patch.object(gateway._hermes_time,'sleep',lambda seconds:None), \
                        patch.dict(gateway.os.environ,{'XDG_RUNTIME_DIR':runtime}):
                    self.assertIs(handler._to_hermes({'messages':[],'moai':{'session':'s'}}),True)
                self.assertEqual(errors,expected)
                self.assertEqual(started,[['systemctl','--user','start','moai-agent-api.service','moai-hermes.service']])
                if expected:
                    self.assertEqual(proxied,[])
                else:
                    self.assertEqual(len(probes),3)
                    self.assertEqual(proxied,['http://127.0.0.1:8090/v1/chat/completions'])

    def test_runtime_status_comes_from_the_adapter_and_is_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter=Path(directory)/'moai-hermes'
            adapter.write_text('#!/bin/sh\nprintf \'{"installed": false, "ready": false}\\n\'\n')
            adapter.chmod(0o755)
            with patch.object(gateway,'HERMES_ADAPTER',str(adapter)), \
                    patch.object(gateway,'_hermes_status',(0.0,None)):
                self.assertIs(gateway.hermes_runtime_installed(),False)
                adapter.write_text('#!/bin/sh\nprintf \'{"installed": true}\\n\'\n')
                self.assertIs(gateway.hermes_runtime_installed(),False)
                later=gateway._hermes_time.monotonic()+61
                with patch.object(gateway._hermes_time,'monotonic',return_value=later):
                    self.assertIs(gateway.hermes_runtime_installed(),True)
                adapter.write_text('#!/bin/sh\nprintf \'not json\'\n')
                with patch.object(gateway._hermes_time,'monotonic',return_value=later+61):
                    self.assertIsNone(gateway.hermes_runtime_installed())

    def test_migration_preserves_key_and_backup_disables_local_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'openclaw.json'
            original={'models':{'providers':{'cloud':{'apiKey':'private-fixture','baseUrl':policy.BASE,
                'models':[{'id':'vendor/paid'}]},'ollama':{}}},
                'agents':{'defaults':{'model':{'primary':'ollama/qwen','fallbacks':['cloud/paid']}}}}
            p.write_text(json.dumps(original));migration.migrate(p)
            changed=json.loads(p.read_text())
            self.assertEqual(changed['models']['providers']['cloud']['apiKey'],'private-fixture')
            self.assertEqual(set(changed['models']['providers']),{'cloud'})
            self.assertEqual(changed['agents']['defaults']['model'],{'primary':'cloud/openrouter/free','fallbacks':[]})
            self.assertEqual(json.loads(p.with_name(p.name+'.before-free-cloud').read_text()),original)
            first=p.read_bytes();migration.migrate(p);self.assertEqual(p.read_bytes(),first)
            self.assertEqual(p.stat().st_mode & 0o777,0o600)

    def test_reboot_migration_preserves_a_selected_zen_key(self):
        """The pre-Zen migration erased the provider and key at every login."""
        with tempfile.TemporaryDirectory() as td, \
                patch.object(migration.policy, 'selected_provider',
                             return_value='opencode-zen'):
            p=Path(td)/'openclaw.json'
            original={'models':{'providers':{'cloud':{
                'apiKey':'zen-private-fixture','baseUrl':policy.ZEN_BASE,
                'api':'openai-completions',
                'models':[{'id':'deepseek-v4-flash','name':'DeepSeek V4 Flash'}]}}},
                'agents':{'defaults':{'model':{'primary':'cloud/deepseek-v4-flash'}}}}
            p.write_text(json.dumps(original));migration.migrate(p)
            changed=json.loads(p.read_text())
            cloud=changed['models']['providers']['cloud']
            self.assertEqual(cloud['baseUrl'],policy.ZEN_BASE)
            self.assertEqual(cloud['apiKey'],'zen-private-fixture')
            self.assertEqual(changed['agents']['defaults']['model']['primary'],
                             'cloud/deepseek-v4-flash')
            first=p.read_bytes();migration.migrate(p);self.assertEqual(p.read_bytes(),first)

    def test_migration_repairs_the_exact_key_loss_shape_from_backup(self):
        """Machines hit by the old login migration can recover without retyping."""
        with tempfile.TemporaryDirectory() as td, \
                patch.object(migration.policy, 'selected_provider',
                             return_value='opencode-zen'):
            p=Path(td)/'openclaw.json'
            reset={'models':{'providers':{'cloud':{
                'baseUrl':policy.BASE,'api':'openai-completions',
                'models':[{'id':policy.DEFAULT_MODEL,'name':'Mo AI Free Cloud'}]}}}}
            backup={'models':{'providers':{'cloud':{
                'apiKey':'recovered-zen-fixture','baseUrl':policy.ZEN_BASE,
                'api':'openai-completions',
                'models':[{'id':'deepseek-v4-flash','name':'DeepSeek V4 Flash'}]}}}}
            p.write_text(json.dumps(reset))
            p.with_name(p.name+'.before-free-cloud').write_text(json.dumps(backup))
            migration.migrate(p)
            cloud=json.loads(p.read_text())['models']['providers']['cloud']
            self.assertEqual((cloud['baseUrl'],cloud['apiKey']),
                             (policy.ZEN_BASE,'recovered-zen-fixture'))

    # ── OpenCode Zen: billed by explicit choice, chat-completions models only ──
    def zen(self, module=None):
        return patch.object(module or policy,'selected_provider',return_value='opencode-zen')

    def test_zen_needs_explicit_selection_and_a_chat_completions_model(self):
        with self.assertRaises(ValueError):
            policy.validate(policy.ZEN_BASE,'deepseek-v4-flash',allow_paid=True)
        with self.zen():
            policy.validate(policy.ZEN_BASE,'deepseek-v4-flash',allow_paid=True)
            policy.validate(policy.ZEN_BASE+'/','big-pickle',allow_paid=True)
            for model in ('gpt-5.5','grok-4.6','claude-opus-5','qwen3.6-plus','gemini-3.5-flash',
                          'muse-spark-1.3-contributor-free','openrouter/free','kimi-k3/../x'):
                with self.subTest(model=model), self.assertRaises(ValueError):
                    policy.validate(policy.ZEN_BASE,model,allow_paid=True)
            for base,model,paid in (('https://opencode.ai.evil/zen/v1','deepseek-v4-flash',True),
                                    (policy.ZEN_BASE,'deepseek-v4-flash',False),
                                    (policy.BASE,'deepseek-v4-flash',True)):
                with self.subTest(base=base,paid=paid), self.assertRaises(ValueError):
                    policy.validate(base,model,allow_paid=paid)

    def test_settings_choice_is_checked_against_the_provider_being_selected(self):
        policy.validate_selection('openrouter-free',policy.DEFAULT_MODEL)
        policy.validate_selection('openrouter-paid','openai/gpt-5.4-mini')
        policy.validate_selection('opencode-zen','kimi-k3')
        for provider,model in (('openrouter-free','openai/gpt-5.4-mini'),('openrouter-free','kimi-k3'),
                               ('opencode-zen','gpt-5.5'),('opencode-zen',policy.DEFAULT_MODEL),
                               ('openrouter-paid','kimi-k3'),('someone-else','kimi-k3')):
            with self.subTest(provider=provider,model=model), self.assertRaises(ValueError):
                policy.validate_selection(provider,model)

    def test_zen_body_carries_no_openrouter_routing(self):
        with self.zen():
            body=policy.request_body({'messages':[],'provider':{'max_price':{'prompt':9}},'models':['x'],
                                      'reasoning':{'effort':'high'},'plugins':[{'id':'web'}]},
                                     'glm-5.3',allow_paid=True,base=policy.ZEN_BASE)
            self.assertEqual(set(body),{'messages','model'})
            with self.assertRaises(ValueError):
                policy.request_body({'messages':[]},'gpt-5.5',allow_paid=True,base=policy.ZEN_BASE)
        with self.assertRaises(ValueError):
            policy.request_body({'messages':[]},'glm-5.3',allow_paid=True,base=policy.ZEN_BASE)

    def test_selected_provider_reads_settings_and_only_billed_ones_are_paid(self):
        with tempfile.TemporaryDirectory() as home:
            state=Path(home)/'moai-agent/state.json'; state.parent.mkdir()
            with patch.dict(policy.os.environ,{'XDG_CONFIG_HOME':home}):
                for stored,provider,cost in ((None,'','free'),('[]','','free'),('{"provider":7}','','free'),
                                             ('{"provider":"openrouter-free"}','openrouter-free','free'),
                                             ('{"provider":"openrouter-paid"}','openrouter-paid','paid'),
                                             ('{"provider":"opencode-zen"}','opencode-zen','paid')):
                    with self.subTest(stored=stored):
                        if stored is None:
                            state.unlink(missing_ok=True)
                        else:
                            state.write_text(stored)
                        self.assertEqual(policy.selected_provider(),provider)
                        self.assertEqual(policy.selected_cost_policy(),cost)
        self.assertTrue(policy.paid_model('kimi-k3','opencode-zen'))
        self.assertFalse(policy.paid_model('openai/gpt-5.4-mini','opencode-zen'))
        self.assertTrue(policy.paid_model('openai/gpt-5.4-mini','openrouter-paid'))
        self.assertFalse(policy.paid_model('kimi-k3','openrouter-free'))

    def test_gateway_sends_zen_requests_to_zen_with_the_chosen_model(self):
        handler=self.gateway_handler()
        handler._cloud_cfg=lambda cfg:(policy.ZEN_BASE,'zen-fixture','openai')
        sent=[]
        handler._proxy=lambda method,url,headers,body,wire,streaming,upstream=None:sent.append((url,headers,json.loads(body)))
        with self.zen(gateway.cloud_policy):
            # "Automatic" on Zen is the model the owner chose for Zen, and a GPT id is refused.
            handler._to_cloud({'messages':[{'role':'user','content':'hi'}]},b'{}',policy.DEFAULT_MODEL,
                              {'cloud_model':'deepseek-v4-flash'})
            handler._to_cloud({'messages':[]},b'{}','gpt-5.5',{'cloud_model':'deepseek-v4-flash'})
        self.assertEqual(handler.errors,[409]);self.assertEqual(len(sent),1)
        url,headers,body=sent[0]
        self.assertEqual(url,policy.ZEN_BASE+'/chat/completions')
        self.assertEqual(headers.get('Authorization'),'Bearer zen-fixture')
        self.assertEqual(body['model'],'deepseek-v4-flash');self.assertNotIn('provider',body)
        self.assertEqual(handler.moai_model,'deepseek-v4-flash')
        # Without the owner's Zen selection the same configuration is refused before any request.
        handler.errors.clear();sent.clear()
        with patch.object(gateway.cloud_policy,'selected_provider',return_value='openrouter-free'):
            handler._to_cloud({'messages':[]},b'{}','deepseek-v4-flash',{})
        self.assertEqual((handler.errors,sent),([409],[]))

    def test_control_sends_the_key_only_to_routable_services_and_lists_only_zen_chat_models(self):
        control=load('moai_control_zen','system_files/usr/bin/moai-control')
        opened=[]
        catalogue={'data':[{'id':m} for m in ('deepseek-v4-flash','gpt-5.5','claude-opus-5','big-pickle',
                                               'muse-spark-1.3-contributor-free','kimi-k3')]}
        class Reply:
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self): return json.dumps(catalogue).encode()
        def urlopen(req,timeout=0):
            opened.append((req.full_url,req.get_header('Authorization')));return Reply()
        with patch.object(control.urllib.request,'urlopen',side_effect=urlopen):
            with self.zen(control.cloud_policy):
                models,error=control.cloud_models({'cloud_base':policy.ZEN_BASE,'cloud_key':'zen-fixture'})
                self.assertEqual(error,'')
                self.assertEqual([m['id'] for m in models],['cloud:deepseek-v4-flash','cloud:big-pickle','cloud:kimi-k3'])
                self.assertEqual(control.cloud_models({'cloud_base':'https://collector.example/v1','cloud_key':'zen-fixture'}),
                                 ([],policy.ERROR))
            with patch.object(control.cloud_policy,'selected_provider',return_value='openrouter-free'):
                self.assertEqual(control.cloud_models({'cloud_base':policy.ZEN_BASE,'cloud_key':'or-fixture'}),
                                 ([],policy.ERROR))
        self.assertEqual(opened,[(policy.ZEN_BASE+'/models','Bearer zen-fixture')])

if __name__=='__main__':unittest.main()
