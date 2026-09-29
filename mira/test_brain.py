"""Typed brain: manual function-calling loop, honest fallbacks, Qt-safe runner."""
import asyncio
import json
import threading
import unittest
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
                        patch.object(brain, '_post_gateway', side_effect=brain.GatewayUnavailable('test'))]
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


class RunnerTest(unittest.TestCase):
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



class ModelChainTest(unittest.TestCase):
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

if __name__ == '__main__':
    unittest.main()
