"""Typed brain: manual function-calling loop, honest fallbacks, Qt-safe runner."""
import asyncio
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import errors, types

import brain


def call_response(name, args=None, call_id='c1'):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role='model', parts=[types.Part(function_call=types.FunctionCall(name=name, args=args or {}, id=call_id))]))])


def text_response(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(
        role='model', parts=[types.Part(text=text)]))])


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({'model': model, 'contents': list(contents), 'config': config})
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)
        self.aio = SimpleNamespace(models=self.models)


HISTORY = [{'role': 'user', 'text': 'مرحبا'}, {'role': 'mira', 'text': 'أهلاً'},
           {'role': 'user', 'text': 'كم الساعة؟'}]


class BrainTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # The free cloud brain is unreachable unless a test gives it answers: no test may reach
        # the real moai-gateway on this computer.
        self.patches = [patch('mira_memory.recent_messages', return_value=HISTORY),
                        patch('mira_memory.load', return_value={'favorite_color': None, 'aliases': {}}),
                        patch('mira_memory.profile_text', return_value=''),
                        patch.object(brain, '_post_gateway', side_effect=brain.GatewayUnavailable('test')),
                        # The owner's real choices (QSettings) never steer a test.
                        patch.object(brain, 'preferences', return_value={'text_model': '', 'cloud_model': ''})]
        for item in self.patches:
            item.start()
        self.events = []

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def emit(self, kind, text):
        self.events.append((kind, text))

    async def test_tool_call_then_final_text(self):
        client = FakeClient([call_response('current_time'), text_response('الساعة الآن الثامنة.')])
        result = await brain.TextBrain(client=client).ask('كم الساعة؟', self.emit, city='Berlin')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['route'], 'gemini')
        self.assertEqual(result['reply'], 'الساعة الآن الثامنة.')
        self.assertEqual([t['name'] for t in result['tools']], ['current_time'])
        self.assertEqual(result['tools'][0]['status'], 'ok')
        kinds = [kind for kind, _ in self.events]
        self.assertEqual(kinds, ['thinking', 'executing', 'tool', 'thinking', 'reply'])
        final = json.loads(self.events[-1][1])
        self.assertEqual((final['status'], final['route']), ('ok', 'gemini'))
        first, second = client.models.calls
        self.assertEqual(first['model'], brain.DEFAULT_TEXT_MODEL)
        # History arrives as prior turns; the repeated current question is not duplicated.
        roles = [c.role for c in first['contents']]
        self.assertEqual(roles, ['user', 'model', 'user'])
        self.assertEqual(first['contents'][-1].parts[0].text, 'كم الساعة؟')
        self.assertTrue(first['config'].automatic_function_calling.disable)
        self.assertIn('Berlin', first['config'].system_instruction)
        self.assertFalse(any('behavior' in d for d in first['config'].tools[0].model_dump(exclude_none=True)['function_declarations']))
        response_part = second['contents'][-1].parts[0].function_response
        self.assertEqual((response_part.name, response_part.id), ('current_time', 'c1'))
        self.assertEqual(response_part.response['status'], 'ok')
        self.assertEqual(second['contents'][-2].parts[0].function_call.name, 'current_time')

    async def test_low_thinking_with_fallbacks_for_refusal_and_transient_5xx(self):
        refused = errors.ClientError(400, {'error': {'code': 400, 'status': 'INVALID_ARGUMENT',
                                                     'message': 'thinking_level is not supported by this model.'}})
        busy = errors.ServerError(503, {'error': {'code': 503, 'status': 'UNAVAILABLE', 'message': 'overloaded'}})
        client = FakeClient([refused, busy, text_response('أهلاً')])
        text_brain = brain.TextBrain(client=client)
        with patch.object(brain.asyncio, 'sleep', return_value=None):
            result = await text_brain.ask('مرحبا', self.emit)
        self.assertEqual((result['status'], result['route'], result['reply']), ('ok', 'gemini', 'أهلاً'))
        configs = [call['config'] for call in client.models.calls]
        self.assertEqual(str(configs[0].thinking_config.thinking_level.value), 'LOW')
        self.assertIsNone(configs[1].thinking_config, 'retried without thinking_level')
        self.assertIsNone(configs[2].thinking_config)
        self.assertIsNone(text_brain._thinking, 'remembered for the next question')

    async def test_rounds_are_bounded_and_last_round_forces_text(self):
        responses = [call_response('current_time', call_id=f'c{i}') for i in range(brain.MAX_ROUNDS - 1)]
        responses.append(text_response('انتهيت.'))
        client = FakeClient(responses)
        result = await brain.TextBrain(client=client).ask('اختبار', self.emit)
        self.assertEqual(len(client.models.calls), brain.MAX_ROUNDS)
        self.assertEqual(result['rounds'], brain.MAX_ROUNDS)
        last = client.models.calls[-1]['config']
        self.assertEqual(str(last.tool_config.function_calling_config.mode.value), 'NONE')
        self.assertIsNone(client.models.calls[0]['config'].tool_config)

    async def test_quota_falls_back_to_router_then_agent(self):
        quota = errors.ClientError(429, {'error': {'code': 429, 'message': 'quota', 'status': 'RESOURCE_EXHAUSTED'}})
        routed = {'kind': 'home', 'result': {'status': 'ok'}, 'message': 'تأكدت من التنفيذ · مصباح'}
        with patch('command_router.dispatch', return_value=routed) as dispatch, patch('moai_link.ask') as ask:
            result = await brain.TextBrain(client=FakeClient([quota])).ask('شغلي مصباح المكتب', self.emit)
        dispatch.assert_called_once_with('شغلي مصباح المكتب', None)
        ask.assert_not_called()
        self.assertEqual((result['route'], result['status'], result['fallback_reason']), ('router', 'ok', 'quota'))
        self.assertIn('حصة', result['reply'])
        self.assertIn('الأوامر المحلية', result['reply'])
        self.assertIn(('tool', 'command_router'), [(k, json.loads(v)['name']) for k, v in self.events if k == 'tool'])

        self.events.clear()
        network = OSError('unreachable')
        with patch('command_router.dispatch', return_value=None), patch('moai_link.ask', return_value='MoOS') as ask:
            result = await brain.TextBrain(client=FakeClient([network])).ask('ما مشروعي؟', self.emit)
        ask.assert_called_once_with('ما مشروعي؟')
        self.assertEqual((result['route'], result['status'], result['fallback_reason']), ('moai', 'ok', 'network'))
        self.assertIn('وكيل Mo AI', result['reply'])

        self.events.clear()
        with patch('command_router.dispatch', return_value=None), \
                patch('moai_link.ask', side_effect=RuntimeError('وكيل Mo AI غير متاح الآن')):
            result = await brain.TextBrain(client=FakeClient([asyncio.TimeoutError()])).ask('سؤال', self.emit)
        self.assertEqual((result['route'], result['status']), ('none', 'error'))
        self.assertEqual(self.events[-1][0], 'reply')

    async def test_without_a_key_the_free_cloud_brain_runs_the_same_tools(self):
        replies = [
            {'model': 'free/x', 'choices': [{'message': {'content': None, 'tool_calls': [
                {'id': 't1', 'type': 'function', 'function': {'name': 'current_time', 'arguments': '{}'}}]}}]},
            {'model': 'free/x', 'choices': [{'message': {'content': 'الساعة 3 و30 دقيقة.'}}]}]
        sent = []

        def gateway(body):
            sent.append(body)
            return replies.pop(0)
        with patch.object(brain, '_post_gateway', side_effect=gateway), patch('moai_link.ask') as ask:
            result = await brain.TextBrain(config_path='/nonexistent/gemini.json').ask('كم الساعة؟', self.emit)
        ask.assert_not_called()
        self.assertEqual((result['route'], result['status'], result['model']), ('moai-cloud', 'ok', 'free/x'))
        self.assertEqual(result['reply'], 'الساعة 3 و30 دقيقة.', 'no fallback note when there is simply no key')
        self.assertEqual([t['name'] for t in result['tools']], ['current_time'])
        names = {tool['function']['name'] for tool in sent[0]['tools']}
        self.assertIn('install_app', names)
        self.assertEqual(sent[0]['tools'][0]['function']['parameters']['type'], 'object')
        self.assertEqual(sent[1]['messages'][-1]['role'], 'tool')
        self.assertNotIn('moai', sent[0], 'the direct free route, not the Hermes agent')

    async def test_auth_and_missing_config_are_classified(self):
        auth = errors.ClientError(400, {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.',
                                                  'status': 'INVALID_ARGUMENT'}})
        self.assertEqual(brain.classify_failure(auth), 'auth')
        self.assertEqual(brain.classify_failure(errors.ServerError(503, {'error': {'code': 503}})), 'server')
        with patch('command_router.dispatch', return_value=None), patch('moai_link.ask', return_value='جواب'):
            result = await brain.TextBrain(config_path='/nonexistent/gemini.json').ask('مرحبا', self.emit)
        self.assertEqual((result['route'], result['fallback_reason']), ('moai', 'config'))

    async def test_router_error_message_is_reported_not_retried(self):
        with patch('command_router.dispatch', side_effect=ValueError('اذكر المدينة بعد «في» لمعرفة طقسها')), \
                patch('moai_link.ask') as ask:
            result = await brain.TextBrain(client=FakeClient([OSError()])).ask('ما الطقس؟', self.emit)
        ask.assert_not_called()
        self.assertEqual((result['route'], result['status']), ('router', 'error'))
        self.assertIn('اذكر المدينة', result['reply'])

    async def test_failure_after_a_tool_never_repeats_the_action(self):
        import home_link
        observed = {'status': 'ok', 'entity_id': 'light.a', 'observed_state': 'on', 'verified': True}
        client = FakeClient([call_response('home_control', {'entity_id': 'light.a', 'action': 'turn_on'}),
                             errors.ServerError(503, {'error': {'code': 503}}),
                             errors.ServerError(503, {'error': {'code': 503}})])
        with patch.object(home_link, 'control', return_value=observed) as control, \
                patch('command_router.dispatch') as dispatch, patch('moai_link.ask') as ask, \
                patch.object(brain.asyncio, 'sleep', return_value=None):
            result = await brain.TextBrain(client=client).ask('شغلي الضوء', self.emit)
        self.assertEqual(len(client.models.calls), 3, 'one retry of the 5xx, then stop')
        control.assert_called_once()
        dispatch.assert_not_called()
        ask.assert_not_called()
        self.assertEqual((result['status'], result['fallback_reason']), ('ok', 'server'))
        self.assertIn('تأكدت', result['reply'])

    async def test_invalid_text(self):
        result = await brain.TextBrain(client=FakeClient([])).ask('   ', self.emit)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(self.events[-1][0], 'reply')

    async def test_tools_get_the_language_the_owner_wrote_in(self):
        """research and health_report answer in the owner's language, even in the other window language."""
        import tools
        seen = []
        real = tools.run_tool

        async def spy(name, args, ctx):
            seen.append(ctx.lang)
            return await real(name, args, ctx)
        cases = [('What time is it?', 'ar', 'en'), ('كم الساعة؟', 'en', 'ar'), ('Wie spät ist es?', 'ar', 'en'),
                 ('42', 'en', 'en'), ('42', 'ar', 'ar')]
        with patch.object(tools, 'run_tool', side_effect=spy):
            for text, window, _ in cases:
                client = FakeClient([call_response('current_time'), text_response('8')])
                result = await brain.TextBrain(client=client).ask(text, self.emit, lang=window)
                self.assertEqual(result['status'], 'ok', text)
        self.assertEqual(seen, [want for _, _, want in cases])


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.prefs = patch.object(brain, 'preferences', return_value={'text_model': '', 'cloud_model': ''})
        self.prefs.start()
        self.addCleanup(self.prefs.stop)

    def test_run_in_thread_reports_on_its_own_loop(self):
        client = FakeClient([text_response('أهلاً!')])
        done = threading.Event()
        box = {}
        events = []
        with patch('mira_memory.recent_messages', return_value=[]):
            future = brain.run_in_thread('مرحبا', lambda k, v: events.append((k, threading.current_thread().name)),
                                         on_done=lambda result: (box.update(result), done.set()),
                                         brain=brain.TextBrain(client=client))
            result = future.result(10)
            self.assertTrue(done.wait(5))
        self.assertEqual(result['reply'], 'أهلاً!')
        self.assertEqual(box['status'], 'ok')
        self.assertTrue(all(name == 'mira-brain' for _, name in events))

    def test_echo_device_control_marshals_to_the_bridge_loop(self):
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        calls = []

        class Voice:
            def device_command(self, args):
                calls.append((args, threading.current_thread() is thread))
                return {'ok': True, 'sent_to_device': True}
        bridge = SimpleNamespace(loop=loop, online=True, voice=Voice())
        try:
            control = brain.echo_device_control(bridge)
            self.assertEqual(asyncio.run(control({'action': 'light_on'}))['sent_to_device'], True)
            self.assertEqual(calls, [({'action': 'light_on'}, True)])
            bridge.online = False
            with self.assertRaises(RuntimeError):
                asyncio.run(control({'action': 'light_on'}))
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(2)
            loop.close()



class ModelChainTest(unittest.TestCase):
    def setUp(self):
        self.prefs = patch.object(brain, 'preferences', return_value={'text_model': '', 'cloud_model': ''})
        self.prefs.start()
        self.addCleanup(self.prefs.stop)

    def test_quota_switches_to_next_model_before_any_tool(self):
        import brain as b
        calls = []
        class Models:
            async def generate_content(self, model, contents, config):
                calls.append(model)
                if model == 'first':
                    raise errors.ClientError(429, {'error': {'code': 429, 'message': 'quota', 'status': 'RESOURCE_EXHAUSTED'}})
                return text_response('تمام')
        class Aio:
            models = Models()
        class Client:
            aio = Aio()
        brain = b.TextBrain(client=Client(), model='first')
        brain._models = lambda: ['first', 'second']
        with patch.object(b.tools, 'conversation_turns', return_value=[]):
            result = asyncio.run(brain.ask('مرحبا', lambda *a: None))
        self.assertEqual(calls, ['first', 'second'])
        self.assertEqual((result['route'], result['model']), ('gemini', 'second'))

    def test_router_uses_saved_city(self):
        import command_router
        with patch.object(command_router, 'current_weather', return_value={
                'city': 'Berlin', 'condition_ar': 'غائم', 'temperature_c': 14, 'source': 'Open-Meteo'}) as weather:
            out = command_router.dispatch('كيف الطقس؟', 'Berlin')
        weather.assert_called_once_with('Berlin')
        self.assertEqual(out['kind'], 'weather')
        with self.assertRaises(ValueError):
            command_router.dispatch('كيف الطقس؟')


class HangingModels:
    """A model call that never answers until cancelled; `started` is set when a call is waiting."""

    def __init__(self, before=()):
        self.before = list(before)
        self.started = threading.Event()
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        if self.before:
            return self.before.pop(0)
        self.started.set()
        await asyncio.Event().wait()      # only a cancellation ends this


def hanging_client(before=()):
    models = HangingModels(before)
    return SimpleNamespace(aio=SimpleNamespace(models=models)), models


NO_PREFS = {'text_model': '', 'cloud_model': ''}


class ModelChoiceTest(unittest.TestCase):
    """The owner's picks in QSettings steer which model answers, and nothing else can."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.config = Path(self.dir.name) / 'gemini.json'

    def write_config(self, **fields):
        self.config.write_text(json.dumps({'api_key': 'k' * 30, 'model': 'gemini-live-x', **fields}))

    def test_owner_pick_wins_over_gemini_json_and_keeps_fallbacks(self):
        self.write_config(text_model='gemini-2.5-flash')
        chosen = brain.TextBrain(config_path=self.config,
                                 prefs=lambda: {'text_model': 'gemini-flash-latest', 'cloud_model': ''})
        self.assertEqual(chosen._models(), ['gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest'])
        from_config = brain.TextBrain(config_path=self.config, prefs=lambda: NO_PREFS)
        self.assertEqual(from_config._models(), ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-flash-lite-latest'])

    def test_unknown_pick_is_ignored_and_default_leads(self):
        self.write_config()
        text_brain = brain.TextBrain(config_path=self.config, prefs=lambda: {'text_model': 'gpt-evil', 'cloud_model': ''})
        self.assertEqual(text_brain._models()[0], brain.DEFAULT_TEXT_MODEL)
        broken = brain.TextBrain(config_path=self.config, prefs=lambda: (_ for _ in ()).throw(OSError()))
        self.assertEqual(broken._models()[0], brain.DEFAULT_TEXT_MODEL, 'unreadable settings never stop a question')

    def test_pick_reaches_the_model_call(self):
        client = FakeClient([text_response('أهلاً')])
        with patch('mira_memory.recent_messages', return_value=[]):
            result = asyncio.run(brain.TextBrain(client=client, prefs=lambda: {'text_model': 'gemini-2.5-flash'})
                                 .ask('مرحبا', None))
        self.assertEqual(client.models.calls[0]['model'], 'gemini-2.5-flash')
        self.assertEqual((result['route'], result['model']), ('gemini', 'gemini-2.5-flash'))

    def test_settings_round_trip_and_validation(self):
        from PySide6.QtCore import QSettings
        ini = str(Path(self.dir.name) / 'Mira.conf')
        with patch.object(brain, '_qsettings', side_effect=lambda: QSettings(ini, QSettings.IniFormat)):
            self.assertEqual(brain.preferences(), NO_PREFS)
            self.assertEqual(brain.set_text_model('gemini-2.5-flash'), 'gemini-2.5-flash')
            with self.assertRaises(ValueError):
                brain.set_text_model('gemini-ultra-paid')
            self.assertEqual(brain.set_cloud_model('cloud:nvidia/nemotron-3-super-120b-a12b:free'),
                             'nvidia/nemotron-3-super-120b-a12b:free')
            with self.assertRaises(ValueError):
                brain.set_cloud_model('https://evil.example/v1')
            with self.assertRaises(ValueError):
                brain.set_cloud_model('../../etc/passwd')
            self.assertEqual(brain.preferences(), {'text_model': 'gemini-2.5-flash',
                                                   'cloud_model': 'nvidia/nemotron-3-super-120b-a12b:free'})
            QSettings(ini, QSettings.IniFormat).setValue('text_model', 'made-up')
            self.assertEqual(brain.preferences()['text_model'], '', 'a hand-edited value is not trusted')
            self.assertEqual(brain.set_cloud_model(''), '')
            self.assertEqual(brain.preferences()['cloud_model'], '', 'empty follows Mo AI again')

    def test_gemini_settings_never_carry_the_key(self):
        self.write_config(text_model='gemini-2.5-flash')
        found = brain.gemini_settings(self.config)
        self.assertEqual(found, {'has_key': True, 'voice_model': 'gemini-live-x', 'text_model': 'gemini-2.5-flash'})
        self.assertNotIn('k' * 30, json.dumps(found))
        self.assertEqual(brain.gemini_settings(Path(self.dir.name) / 'missing.json')['has_key'], False)
        with patch.object(brain, 'preferences', return_value=NO_PREFS):
            self.assertEqual(brain.chosen_text_model(self.config), ('gemini-2.5-flash', 'config'))
        with patch.object(brain, 'preferences', return_value={'text_model': 'gemini-flash-latest', 'cloud_model': ''}):
            self.assertEqual(brain.chosen_text_model(self.config), ('gemini-flash-latest', 'mira'))

    def test_probe_uses_the_chosen_model_and_classifies_failures(self):
        self.write_config()
        seen = {}

        class Models:
            def generate_content(self, model, contents):
                seen['model'] = model
                return SimpleNamespace(text='ready')

        def client(key, timeout_ms):
            seen['key_given'] = key == 'k' * 30
            return SimpleNamespace(models=Models())
        with patch.object(brain, '_sync_client', side_effect=client), \
                patch.object(brain, 'preferences', return_value={'text_model': 'gemini-2.5-flash', 'cloud_model': ''}):
            result = brain.probe_gemini(path=self.config)
        self.assertEqual((result['status'], result['model']), ('ok', 'gemini-2.5-flash'))
        self.assertTrue(seen['key_given'])
        self.assertIsInstance(result['elapsed_ms'], int)

        quota = errors.ClientError(429, {'error': {'code': 429, 'message': 'quota', 'status': 'RESOURCE_EXHAUSTED'}})
        with patch.object(brain, '_sync_client', side_effect=quota), patch.object(brain, 'preferences', return_value=NO_PREFS):
            failed = brain.probe_gemini('gemini-flash-latest', path=self.config)
        self.assertEqual((failed['status'], failed['reason'], failed['model']), ('error', 'quota', 'gemini-flash-latest'))
        self.assertNotIn('quota', json.dumps({k: v for k, v in failed.items() if k != 'reason'}))
        with patch.object(brain, 'preferences', return_value=NO_PREFS):
            missing = brain.probe_gemini(path=Path(self.dir.name) / 'missing.json')
        self.assertEqual((missing['status'], missing['reason']), ('error', 'config'))


class CloudModelTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.patches = [patch('mira_memory.recent_messages', return_value=[]),
                        patch('mira_memory.load', return_value={'favorite_color': None, 'aliases': {}}),
                        patch('mira_memory.profile_text', return_value='')]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    async def test_chosen_cloud_model_goes_to_the_gateway(self):
        sent = []

        def gateway(body):
            sent.append(dict(body))
            return {'model': 'nvidia/nemotron-3-super-120b-a12b:free', 'choices': [{'message': {'content': 'أهلاً'}}]}
        prefs = {'text_model': '', 'cloud_model': 'nvidia/nemotron-3-super-120b-a12b:free'}
        with patch.object(brain, '_post_gateway', side_effect=gateway):
            result = await brain.TextBrain(config_path='/nonexistent/gemini.json', prefs=lambda: prefs).ask('مرحبا', None)
        self.assertEqual(sent[0]['model'], 'cloud:nvidia/nemotron-3-super-120b-a12b:free')
        self.assertEqual((result['route'], result['model']), ('moai-cloud', 'nvidia/nemotron-3-super-120b-a12b:free'))

    async def test_without_a_pick_mo_ai_decides(self):
        sent = []

        def gateway(body):
            sent.append(dict(body))
            return {'choices': [{'message': {'content': 'أهلاً'}}]}
        with patch.object(brain, '_post_gateway', side_effect=gateway):
            result = await brain.TextBrain(config_path='/nonexistent/gemini.json', prefs=lambda: NO_PREFS).ask('مرحبا', None)
        self.assertNotIn('model', sent[0])
        self.assertEqual((result['route'], result['model']), ('moai-cloud', ''), 'model is always a string')

    async def test_a_refused_pick_falls_back_to_mo_ais_setting_and_says_so(self):
        sent = []
        replies = [brain.GatewayUnavailable('http_409'), {'model': 'openrouter/free', 'choices': [{'message': {'content': 'تمام'}}]}]

        def gateway(body):
            sent.append(dict(body))
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        prefs = {'text_model': '', 'cloud_model': 'openai/gpt-paid'}
        seen = []
        with patch.object(brain, '_post_gateway', side_effect=gateway):
            text_brain = brain.TextBrain(config_path='/nonexistent/gemini.json', prefs=lambda: prefs)
            brain.add_answer_listener(seen.append)          # a builtin is held strongly: remove it after
            self.addCleanup(brain.remove_answer_listener, seen.append)
            result = await text_brain.ask('مرحبا', None)
        self.assertEqual(sent[0]['model'], 'cloud:openai/gpt-paid')
        self.assertNotIn('model', sent[1])
        self.assertEqual((result['status'], result['model'], result['model_refused']), ('ok', 'openrouter/free', 'openai/gpt-paid'))
        self.assertEqual(text_brain.last['model_refused'], 'openai/gpt-paid')
        self.assertEqual(seen[-1]['model_refused'], 'openai/gpt-paid')

    async def test_a_refusal_after_a_tool_ran_is_not_a_model_switch(self):
        sent = []
        replies = [{'model': 'pick/x:free', 'choices': [{'message': {'content': None, 'tool_calls': [
                       {'id': 't1', 'type': 'function', 'function': {'name': 'current_time', 'arguments': '{}'}}]}}]},
                   brain.GatewayUnavailable('http_400'), {'choices': [{'message': {'content': 'switched'}}]}]

        def gateway(body):
            sent.append(dict(body))
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        prefs = {'text_model': '', 'cloud_model': 'pick/x:free'}
        with patch.object(brain, '_post_gateway', side_effect=gateway), patch('command_router.dispatch') as dispatch, \
                patch('moai_link.ask') as ask:
            result = await brain.TextBrain(config_path='/nonexistent/gemini.json', prefs=lambda: prefs).ask('كم الساعة', None)
        self.assertEqual(len(sent), 2, 'no silent second try on another model halfway through')
        self.assertEqual(sent[1]['model'], 'cloud:pick/x:free')
        self.assertNotIn('model_refused', result)
        self.assertEqual((result['route'], [t['name'] for t in result['tools']]), ('moai-cloud', ['current_time']))
        self.assertIn('ما حدث فعلاً', result['reply'])
        dispatch.assert_not_called()
        ask.assert_not_called()

    async def test_router_answer_still_names_route_and_model(self):
        with patch.object(brain, '_post_gateway', side_effect=brain.GatewayUnavailable('test')), \
                patch('command_router.dispatch', return_value={'kind': 'time', 'result': {'status': 'ok'}, 'message': '8:00'}):
            result = await brain.TextBrain(config_path='/nonexistent/gemini.json', prefs=lambda: NO_PREFS).ask('كم الساعة', None)
        self.assertEqual((result['route'], result['model']), ('router', ''))


class AnswerListenerTest(unittest.TestCase):
    def test_every_answer_is_published_and_pages_are_held_weakly(self):
        class Page:
            def __init__(self):
                self.seen = []

            def arrived(self, summary):
                self.seen.append(summary)
        page = Page()
        brain.add_answer_listener(page.arrived)
        client = FakeClient([text_response('أهلاً')])
        with patch('mira_memory.recent_messages', return_value=[]):
            result = asyncio.run(brain.TextBrain(client=client, prefs=lambda: NO_PREFS).ask('مرحبا', None))
        self.assertEqual(page.seen[-1]['route'], 'gemini')
        self.assertEqual(page.seen[-1]['model'], brain.DEFAULT_TEXT_MODEL)
        self.assertEqual(page.seen[-1]['elapsed_ms'], result['elapsed_ms'])
        self.assertEqual(brain.last_answer()['status'], 'ok')
        count = len(brain._listeners)
        del page
        import gc
        gc.collect()
        with patch('mira_memory.recent_messages', return_value=[]):
            asyncio.run(brain.TextBrain(client=FakeClient([text_response('ثانية')]), prefs=lambda: NO_PREFS).ask('مرحبا', None))
        self.assertLess(len(brain._listeners), count, 'a page that went away is dropped')

    def test_invalid_input_is_not_an_answer(self):
        before = brain.last_answer()
        asyncio.run(brain.TextBrain(client=FakeClient([]), prefs=lambda: NO_PREFS).ask('  ', None))
        self.assertEqual(brain.last_answer(), before)

    def test_a_listener_can_be_removed(self):
        seen = []
        brain.add_answer_listener(seen.append)
        brain.remove_answer_listener(seen.append)
        brain.remove_answer_listener(seen.append)        # twice is harmless
        with patch('mira_memory.recent_messages', return_value=[]):
            asyncio.run(brain.TextBrain(client=FakeClient([text_response('أهلاً')]), prefs=lambda: NO_PREFS).ask('مرحبا', None))
        self.assertEqual(seen, [])
        self.assertFalse(any(ref() == seen.append for ref in brain._listeners))


class StepTitleTest(unittest.TestCase):
    def test_every_tool_is_named_in_the_owners_words(self):
        import tools
        for item in tools.DECLARATIONS:
            for en in (False, True):
                title = brain.step_title(item['name'], en)
                self.assertNotEqual(title, item['name'])
                self.assertNotIn('_', title, item['name'])
        self.assertEqual(brain.step_title('no_such_tool', False), 'إحدى أدوات ميرا')
        for ar, en in brain.STEP_TITLES.values():
            for word in ('Fedora', 'Red Hat', 'fedora'):
                self.assertNotIn(word, ar + en)


class CancelTest(unittest.TestCase):
    def setUp(self):
        self.patches = [patch('mira_memory.recent_messages', return_value=[]),
                        patch('mira_memory.load', return_value={'favorite_color': None, 'aliases': {}}),
                        patch('mira_memory.profile_text', return_value=''),
                        patch.object(brain, '_post_gateway', side_effect=brain.GatewayUnavailable('test')),
                        patch.object(brain, 'preferences', return_value=NO_PREFS)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_cancel_stops_a_waiting_model_call_honestly(self):
        client, models = hanging_client()
        events, done = [], threading.Event()
        box = {}
        turn = brain.run_in_thread('سؤال طويل', lambda k, v: events.append((k, v)), lang='en',
                                   on_done=lambda result: (box.update(result), done.set()),
                                   brain=brain.TextBrain(client=client, prefs=lambda: NO_PREFS))
        self.assertTrue(models.started.wait(5))
        self.assertIs(brain.current_turn(), turn)
        self.assertTrue(turn.cancel())
        result = turn.result(5)
        self.assertTrue(done.wait(5))
        self.assertEqual((result['status'], result['route'], result['model']), ('cancelled', 'gemini', brain.DEFAULT_TEXT_MODEL))
        self.assertEqual(result['reply'], 'Stopped.')
        self.assertEqual(box['status'], 'cancelled')
        self.assertTrue(turn.cancelled_by_owner)
        final = json.loads(events[-1][1])
        self.assertEqual((events[-1][0], final['status']), ('reply', 'cancelled'))
        self.assertFalse(turn.cancel(), 'a finished turn cannot be stopped again')
        self.assertIsNone(brain.current_turn())
        self.assertFalse(brain.cancel_current())

    def test_cancel_after_a_tool_says_what_already_happened(self):
        client, models = hanging_client(before=[call_response('current_time')])
        turn = brain.run_in_thread('كم الساعة؟', None, brain=brain.TextBrain(client=client, prefs=lambda: NO_PREFS))
        self.assertTrue(models.started.wait(5))
        self.assertTrue(brain.cancel_current())
        result = turn.result(5)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual([t['name'] for t in result['tools']], ['current_time'])
        self.assertIn('ما حدث فعلاً قبل الإيقاف', result['reply'])
        self.assertIn(result['tools'][0]['summary'], result['reply'])

    def test_a_callers_own_event_stops_the_turn(self):
        client, models = hanging_client()
        stop = threading.Event()
        turn = brain.run_in_thread('سؤال', None, brain=brain.TextBrain(client=client, prefs=lambda: NO_PREFS),
                                   cancel_event=stop)
        self.assertTrue(models.started.wait(5))
        started = time.monotonic()
        stop.set()
        result = turn.result(5)
        self.assertEqual(result['status'], 'cancelled')
        self.assertLess(time.monotonic() - started, 2.0)

    def test_cancel_during_the_free_cloud_route(self):
        release = threading.Event()
        entered = threading.Event()

        def slow_gateway(body):
            entered.set()
            release.wait(5)
            return {'choices': [{'message': {'content': 'late'}}]}
        with patch.object(brain, '_post_gateway', side_effect=slow_gateway):
            turn = brain.run_in_thread('مرحبا', None, brain=brain.TextBrain(config_path='/nonexistent/gemini.json',
                                                                            prefs=lambda: NO_PREFS))
            self.assertTrue(entered.wait(5))
            turn.cancel()
            result = turn.result(5)
            release.set()
        self.assertEqual((result['status'], result['route']), ('cancelled', 'moai-cloud'))

    def no_key(self):
        return brain.TextBrain(config_path='/nonexistent/gemini.json', prefs=lambda: NO_PREFS)

    def test_a_stop_during_local_commands_says_they_may_still_finish(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()

        def slow_dispatch(text, city=None):
            entered.set()
            release.wait(5)
            finished.set()
            return {'kind': 'home', 'result': {'status': 'ok'}, 'message': 'Turned off all lights (3/3)'}
        with patch('command_router.dispatch', side_effect=slow_dispatch), patch('moai_link.ask') as ask:
            turn = brain.run_in_thread('turn off all lights', None, lang='en', brain=self.no_key())
            self.assertTrue(entered.wait(5))
            self.assertTrue(turn.cancel())
            result = turn.result(5)
            release.set()
            self.assertTrue(finished.wait(5), 'the command itself ran on: that is what the reply must admit')
        ask.assert_not_called()
        self.assertEqual((result['status'], result['route']), ('cancelled', 'router'))
        self.assertIn('may still finish: local commands carrying out your request', result['reply'])

    def test_a_stop_while_the_agent_works_says_it_may_still_finish(self):
        entered, release = threading.Event(), threading.Event()

        def slow_agent(text):
            entered.set()
            release.wait(5)
            return 'done'
        with patch('command_router.dispatch', return_value=None), patch('moai_link.ask', side_effect=slow_agent):
            turn = brain.run_in_thread('نظّم مشروعي', None, brain=self.no_key())
            self.assertTrue(entered.wait(5))
            turn.cancel()
            result = turn.result(5)
            release.set()
        self.assertEqual((result['status'], result['route']), ('cancelled', 'moai'))
        self.assertIn('قد تكتمل رغم الإيقاف: وكيل Mo AI الذي يعمل على طلبك', result['reply'])

    def test_a_stopped_tool_is_named_in_the_owners_words(self):
        entered = threading.Event()

        async def hanging_tool(name, args, ctx):
            entered.set()
            await asyncio.Event().wait()
        client = FakeClient([call_response('set_volume', {'value': '30'})])
        with patch.object(brain.tools, 'run_tool', new=hanging_tool):
            turn = brain.run_in_thread('خفّض الصوت', None, brain=brain.TextBrain(client=client, prefs=lambda: NO_PREFS))
            self.assertTrue(entered.wait(5))
            turn.cancel()
            result = turn.result(5)
        self.assertEqual(result['status'], 'cancelled')
        self.assertIn('«صوت الكمبيوتر»', result['reply'])
        self.assertNotIn('set_volume', result['reply'])

    def run_until(self, release):
        async def main():
            try:
                return await self.no_key().ask('turn off all lights', None, lang='en')
            finally:
                release.set()          # let the worker thread end before the loop closes
        return asyncio.run(main())

    def test_local_commands_that_time_out_are_never_handed_to_the_agent(self):
        release = threading.Event()
        with patch('command_router.dispatch', side_effect=lambda text, city=None: release.wait(5)), \
                patch('moai_link.ask') as ask, patch.object(brain, 'ROUTER_TIMEOUT_S', 0.2):
            result = self.run_until(release)
        ask.assert_not_called()
        self.assertEqual((result['status'], result['route']), ('pending', 'router'))
        self.assertIn('may still complete', result['reply'])

    def test_an_agent_that_times_out_may_still_be_working(self):
        release = threading.Event()
        with patch('command_router.dispatch', return_value=None), \
                patch('moai_link.ask', side_effect=lambda text: release.wait(5)), patch.object(brain, 'AGENT_TIMEOUT_S', 0.2):
            result = self.run_until(release)
        self.assertEqual((result['status'], result['route']), ('pending', 'moai'))
        self.assertIn('check before asking again', result['reply'])

        def agent_read_timed_out(text):     # moai_link wraps its own socket timeout
            try:
                raise TimeoutError('timed out')
            except TimeoutError as exc:
                raise RuntimeError('وكيل Mo AI غير متاح الآن') from exc
        with patch('command_router.dispatch', return_value=None), patch('moai_link.ask', side_effect=agent_read_timed_out):
            result = self.run_until(threading.Event())
        self.assertEqual(result['status'], 'pending')

    def test_a_turn_stopped_before_it_starts_asks_nobody(self):
        client = FakeClient([])
        stop = threading.Event()
        stop.set()
        result = asyncio.run(brain.TextBrain(client=client, prefs=lambda: NO_PREFS).ask('مرحبا', None, cancel=stop))
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(client.models.calls, [])

    def test_a_cancellation_nobody_asked_for_still_propagates(self):
        client, models = hanging_client()

        async def main():
            task = asyncio.ensure_future(brain.TextBrain(client=client, prefs=lambda: NO_PREFS).ask('مرحبا', None,
                                                                                                  cancel=threading.Event()))
            while not models.started.is_set():
                await asyncio.sleep(0.01)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        asyncio.run(main())


if __name__ == '__main__':
    unittest.main()
