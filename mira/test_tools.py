"""The shared tool registry: schema sanity, validation, verified statuses, no secrets."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools


def collect():
    events = []
    return events, tools.ToolContext(emit=lambda kind, text: events.append((kind, text)))


class RegistryTest(unittest.TestCase):
    def test_declarations_are_valid_genai_schemas(self):
        from google.genai import types
        names = [item['name'] for item in tools.DECLARATIONS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(tools._EXECUTORS))
        for item in tools.DECLARATIONS:
            types.FunctionDeclaration(**item)  # pydantic validation, as the SDK does
            params = item.get('parameters')
            if params is None:
                continue
            self.assertEqual(params['type'], 'OBJECT')
            self.assertTrue(params['properties'], item['name'] + ': empty OBJECT is refused by generate_content')
            for key in params.get('required', []):
                self.assertIn(key, params['properties'])
            for spec in params['properties'].values():
                self.assertIn(spec['type'], ('STRING', 'NUMBER', 'BOOLEAN', 'INTEGER'))
                if 'enum' in spec:
                    self.assertTrue(all(isinstance(v, str) for v in spec['enum']))
        types.Tool(function_declarations=tools.DECLARATIONS)
        live = tools.live_declarations()
        self.assertTrue(all(item['behavior'] == 'BLOCKING' for item in live))
        self.assertTrue(all('behavior' not in item for item in tools.DECLARATIONS), 'behavior is Live-only')

    def test_every_moai_tool_is_mira_s_and_there_is_no_free_shell(self):
        import moai_tools
        names = {item['name'] for item in tools.DECLARATIONS}
        declared = moai_tools.names()
        self.assertGreaterEqual(len(declared), 50, 'the MoOS schema module was not found')
        self.assertEqual(declared - names, set(tools.MOAI_SKIP), 'every Mo AI tool but open_app is declared by name')
        for name in ('install_app', 'system_update', 'fix_audio', 'set_volume', 'read_journal', 'device_report'):
            self.assertIn(name, names)
        self.assertNotIn('moai_control', names)
        text = json.dumps(tools.DECLARATIONS).lower()
        for forbidden in ('"shell"', '"run_command"', '"bash"', '"exec"', '"terminal"'):
            self.assertNotIn(forbidden, text)
        self.assertIn('current_time', names)
        self.assertIn('find_app', names)


class ValidationTest(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_missing_wrong_type_and_enum(self):
        events, ctx = collect()
        cases = [('rm_everything', {}, 'unsupported'),
                 ('home_control', {'action': 'turn_on'}, 'error'),           # entity_id missing
                 ('home_control', {'entity_id': 'light.x', 'action': 'explode'}, 'error'),
                 ('home_control', {'entity_id': 'light.x', 'action': 'brightness', 'value': 'high'}, 'error'),
                 ('current_weather', {'city': ['Berlin']}, 'error')]
        for name, args, status in cases:
            result = await tools.run_tool(name, args, ctx)
            self.assertEqual(result['status'], status, (name, args, result))
            self.assertTrue(result['summary'])
        self.assertEqual(len(events), len(cases), 'exactly one tool event per call')
        for kind, payload in events:
            self.assertEqual(kind, 'tool')
            data = json.loads(payload)
            self.assertEqual(set(data) - {'elapsed_ms'}, {'name', 'status', 'summary', 'args_preview'})

    async def test_allowlist_blocks_other_tools(self):
        events, ctx = collect()
        ctx.allowed_tools = frozenset({'current_time'})
        with patch('home_link.control') as control:
            result = await tools.run_tool('home_control', {'entity_id': 'light.a', 'action': 'turn_on'}, ctx)
        control.assert_not_called()
        self.assertEqual(result['status'], 'unsupported')
        self.assertEqual((await tools.run_tool('current_time', {}, ctx))['status'], 'ok')

    async def test_exception_text_with_url_is_reduced_to_class_name(self):
        events, ctx = collect()
        leak = OSError('wss://example.invalid/ws?key=AIzaSECRET')
        with patch('weather_link.current', side_effect=leak):
            result = await tools.run_tool('current_weather', {'city': 'Berlin'}, ctx)
        self.assertEqual(result['status'], 'error')
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertNotIn('SECRET', ''.join(text for _, text in events))
        with patch('weather_link.current', side_effect=RuntimeError('see https://x/?key=AIzaSECRET')):
            result = await tools.run_tool('current_weather', {'city': 'Berlin'}, ctx)
        self.assertNotIn('SECRET', json.dumps(result))

    def test_args_preview_redacts_and_truncates(self):
        text = tools.args_preview({'api_key': 'AIzaSECRET', 'fact': 'x' * 300, 'value': 40})
        self.assertNotIn('AIzaSECRET', text)
        self.assertIn('api_key=***', text)
        self.assertLessEqual(len(text), 140)


class VerifiedStatusTest(unittest.IsolatedAsyncioTestCase):
    async def test_device_control_is_pending_never_ok(self):
        events, ctx = collect()
        self.assertEqual((await tools.run_tool('device_control', {'action': 'light_on'}, ctx))['status'], 'unsupported')
        sent = []
        ctx.device_control = lambda args: sent.append(args) or {'ok': True, 'sent_to_device': True}
        result = await tools.run_tool('device_control', {'action': 'set_volume', 'value': 40}, ctx)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(sent, [{'action': 'set_volume', 'value': 40}])
        result = await tools.run_tool('device_control', {'action': 'set_volume', 'value': 140}, ctx)
        self.assertEqual(result['status'], 'error')

        async def async_device(args):
            return {'ok': True, 'sent_to_device': True}
        ctx.device_control = async_device
        self.assertEqual((await tools.run_tool('device_control', {'action': 'stop_music'}, ctx))['status'], 'pending')

    async def test_moai_tools_keep_validation_and_read_back(self):
        import moai_tools
        events, ctx = collect()
        with patch.object(moai_tools, 'execute') as execute:
            result = await tools.run_tool('install_app', {}, ctx)
            self.assertEqual(result['status'], 'error')      # app_id required
            result = await tools.run_tool('set_mute', {'value': 'loud'}, ctx)
            self.assertEqual(result['status'], 'error')      # outside the enum
            execute.assert_not_called()
        status = {'status': 'ok', 'output': json.dumps({'volume': 30})}
        with patch.object(moai_tools, 'execute', side_effect=[{'status': 'ok'}, status]) as execute:
            result = await tools.run_tool('set_volume', {'value': '40'}, ctx)
        self.assertEqual(result['status'], 'pending', 'readback 30 != requested 40')
        execute.assert_any_call('set_volume', {'value': '40'})
        status = {'status': 'ok', 'output': json.dumps({'volume': 40})}
        with patch.object(moai_tools, 'execute', side_effect=[{'status': 'ok'}, status]):
            result = await tools.run_tool('set_volume', {'value': 40.0}, ctx)
        self.assertEqual(result['status'], 'ok')
        with patch.object(moai_tools, 'execute', return_value={'status': 'ok', 'output': '{}'}) as execute:
            await tools.run_tool('show_windows', {'view': 'overview'}, ctx)
            await tools.run_tool('read_journal', {'unit': 'pipewire.service', 'user': 'true', 'lines': 30.0}, ctx)
        execute.assert_any_call('show_windows', {'view': 'overview'})
        execute.assert_any_call('read_journal', {'unit': 'pipewire.service', 'user': True, 'lines': 30})

    async def test_a_system_change_waits_for_the_owner(self):
        import moai_tools
        events, ctx = collect()
        confirm = {'status': 'confirm', 'category': 'user_confirm', 'summary': 'x'}
        with patch.object(moai_tools, 'execute', return_value=confirm) as execute:
            result = await tools.run_tool('install_app', {'app_id': 'org.videolan.VLC'}, ctx)
        execute.assert_called_once_with('install_app', {'app_id': 'org.videolan.VLC'})
        self.assertEqual(result['status'], 'unsupported', 'no owner surface: nothing may run')
        asked = []
        ctx.request_confirmation = lambda item: asked.append(item) or {'id': 'p1'}
        with patch.object(moai_tools, 'execute', return_value=confirm):
            result = await tools.run_tool('install_app', {'app_id': 'org.videolan.VLC'}, ctx)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['awaiting'], 'owner_confirmation')
        self.assertIs(result['executed'], False)
        self.assertEqual(asked[0]['name'], 'install_app')
        self.assertEqual(asked[0]['args'], {'app_id': 'org.videolan.VLC'})
        self.assertEqual(asked[0]['kind'], 'moai')

    async def test_moai_executor_never_receives_a_confirmation(self):
        import moai_tools
        events, ctx = collect()
        ctx.request_confirmation = lambda item: {'id': 'p1'}
        with patch.object(moai_tools, '_request', return_value=(403, {'error': 'confirmation_required',
                                                                      'category': 'privileged_confirm'})) as request:
            result = await tools.run_tool('system_update', {}, ctx)
            await tools.run_tool('get_system_status', {}, ctx)
        for call in request.call_args_list:
            path, body = call.args[0], call.args[1]
            self.assertEqual(path, '/tool/execute')
            self.assertIs(body['confirmed'], False)
        self.assertEqual(result['status'], 'pending')

    async def test_find_app_returns_real_ids(self):
        import moai_tools
        events, ctx = collect()
        body = {'results': [{'id': 'org.videolan.VLC', 'name': 'VLC', 'summary': 'player', 'installed': False,
                             'icon': 'https://x', 'verified': False}], 'source': 'flathub'}
        with patch.object(moai_tools, '_request', return_value=(200, body)) as request:
            result = await tools.run_tool('find_app', {'query': 'vlc player'}, ctx)
        self.assertEqual(request.call_args.args[0], '/search?q=vlc%20player')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['apps'][0]['id'], 'org.videolan.VLC')
        self.assertNotIn('icon', result['apps'][0])

    async def test_closing_a_window_waits_for_the_owner(self):
        import desktop_tools
        events, ctx = collect()
        asked = []
        ctx.request_confirmation = lambda item: asked.append(item) or {'id': 'p2'}
        with patch.object(desktop_tools, 'close_window') as close, \
                patch.object(desktop_tools, 'focus_window', return_value={'status': 'ok', 'summary': 'x'}) as focus:
            result = await tools.run_tool('windows', {'action': 'close', 'query': 'Konsole'}, ctx)
            await tools.run_tool('windows', {'action': 'focus', 'query': 'Konsole'}, ctx)
        close.assert_not_called()
        focus.assert_called_once_with('Konsole')
        self.assertEqual(result['awaiting'], 'owner_confirmation')
        self.assertEqual(asked[0], {'kind': 'desktop', 'name': 'close_window', 'args': {'query': 'Konsole'},
                                    'title_ar': 'إغلاق نافذة', 'title_en': 'Close a window', 'detail': 'Konsole'})

    async def test_reminders_and_routines_use_private_files(self):
        import reminders
        import routines
        events, ctx = collect()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(reminders, 'DEFAULT_PATH', Path(folder) / 'rem.json'), \
                patch.object(routines, 'DEFAULT_PATH', Path(folder) / 'rou.json'):
            result = await tools.run_tool('reminder', {'action': 'timer', 'minutes': 10, 'label': 'الفرن'}, ctx)
            self.assertEqual(result['status'], 'ok', result)
            self.assertIn('spoken', result)
            self.assertEqual(oct((Path(folder) / 'rem.json').stat().st_mode & 0o777), '0o600')
            listed = await tools.run_tool('reminder', {'action': 'list'}, ctx)
            self.assertEqual(len(listed['items']), 1)
            self.assertIn(('reminders', ''), events)
            bad = await tools.run_tool('reminder', {'action': 'add', 'text': 'x'}, ctx)
            self.assertEqual(bad['status'], 'error')         # no time given
            saved = await tools.run_tool('routine', {'action': 'save', 'name': 'ليلة',
                                                     'steps_json': json.dumps([{'tool': 'current_time', 'args': {}}])}, ctx)
            self.assertEqual(saved['status'], 'ok', saved)
            refused = await tools.run_tool('routine', {'action': 'save', 'name': 'x',
                                                       'steps_json': json.dumps([{'tool': 'routine', 'args': {}}])}, ctx)
            self.assertEqual(refused['status'], 'error')
            ran = await tools.run_tool('routine', {'action': 'run', 'name': 'ليلة'}, ctx)
            self.assertEqual(ran['status'], 'ok', ran)
            self.assertEqual([e for e in events if e[0] == 'tool' and '"current_time"' in e[1]].__len__(), 1)
            missing = await tools.run_tool('routine', {'action': 'run', 'name': 'غير موجود'}, ctx)
            self.assertEqual(missing['status'], 'error')

    async def test_home_statuses_follow_readback(self):
        import home_link
        events, ctx = collect()
        with patch.object(home_link, 'control', return_value={'status': 'pending', 'entity_id': 'light.a',
                                                              'observed_state': 'off', 'verified': False}) as control:
            result = await tools.run_tool('home_control', {'entity_id': 'light.a', 'action': 'turn_on'}, ctx)
        control.assert_called_once_with('light.a', 'turn_on')
        self.assertEqual(result['status'], 'pending')
        with patch.object(home_link, 'control', return_value={'status': 'ok', 'entity_id': 'light.a',
                                                              'observed_state': 'on', 'verified': True}) as control:
            result = await tools.run_tool('home_control', {'entity_id': 'light.a', 'action': 'color',
                                                           'color': 'pink', 'ignored': 1}, ctx)
        control.assert_called_once_with('light.a', 'color', color='pink')
        self.assertEqual(result['status'], 'ok')
        with patch.object(home_link, 'control_all_lights', return_value={'status': 'partial', 'confirmed': 1,
                                                                         'total': 2, 'results': []}):
            result = await tools.run_tool('home_lights_all', {'action': 'turn_off'}, ctx)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('1', result['summary'])

    async def test_agent_answer_is_not_claimed_as_executed(self):
        import moai_link
        events, ctx = collect()
        hooks = []
        ctx.on_long_task = lambda: hooks.append(1)
        with patch.object(moai_link, 'ask', return_value='فتحت المشروع'):
            result = await tools.run_tool('moai_project_task', {'request': 'افحص مشروع MoOS'}, ctx)
        self.assertEqual(result['status'], 'pending')
        self.assertFalse(result['execution_verified'])
        self.assertEqual(hooks, [1])

    async def test_current_time_local_and_zone(self):
        events, ctx = collect()
        result = await tools.run_tool('current_time', {}, ctx)
        self.assertEqual(result['status'], 'ok')
        self.assertIn(result['weekday_ar'], tools._WEEKDAYS_AR)
        self.assertRegex(result['spoken_ar'], r'^الساعة \d{1,2} ')
        self.assertRegex(result['spoken_en'], r'^\d{1,2}:\d\d (AM|PM)$')
        self.assertNotIn('iso', result)   # a bare 24-hour stamp is what the voice model misread
        tokyo = await tools.run_tool('current_time', {'timezone': 'Asia/Tokyo'}, ctx)
        self.assertEqual(tokyo['timezone'], 'Asia/Tokyo')
        bad = await tools.run_tool('current_time', {'timezone': '../../etc/passwd'}, ctx)
        self.assertEqual(bad['status'], 'error')

    async def test_memory_tools_write_private_files(self):
        with tempfile.TemporaryDirectory() as temp:
            old = os.environ.get('XDG_CONFIG_HOME')
            os.environ['XDG_CONFIG_HOME'] = temp
            import importlib
            import mira_memory
            importlib.reload(mira_memory)
            try:
                events, ctx = collect()
                result = await tools.run_tool('remember_owner_fact', {'fact': 'اسمي محمد'}, ctx)
                self.assertEqual(result['status'], 'ok')
                self.assertIn('اسمي محمد', mira_memory.profile_text())
                result = await tools.run_tool('remember_color', {'color': 'pink'}, ctx)
                self.assertEqual(result['status'], 'ok')
                self.assertEqual(mira_memory.load()['favorite_color'], 'pink')
            finally:
                if old is None:
                    os.environ.pop('XDG_CONFIG_HOME', None)
                else:
                    os.environ['XDG_CONFIG_HOME'] = old
                importlib.reload(mira_memory)


class PersonaTest(unittest.TestCase):
    def test_instruction_carries_persona_rules_time_city_and_memory(self):
        with patch('mira_memory.load', return_value={'favorite_color': 'pink', 'aliases': {'بيرو': 'light.b'}}), \
                patch('mira_memory.profile_text', return_value='أعمل على MoOS'):
            text = tools.system_instruction('ar', 'Berlin')
            english = tools.system_instruction('en', None, channel='text')
        self.assertIn('ميرا', text)
        self.assertIn('status=ok', text)
        self.assertIn('Berlin', text)
        self.assertIn('أعمل على MoOS', text)
        self.assertIn('light.b', text)
        self.assertIn('current_time', text)
        self.assertIn('تدرّبين', text)          # never claims self-training
        self.assertIn('أوامر حرة', text)        # no free command tool
        self.assertIn('install_app', text)
        self.assertIn('owner_confirmation', text)
        self.assertIn('English', english)
        self.assertIn('فاسأليه عنها', english)   # no city: ask for it

    def test_instruction_survives_broken_memory(self):
        with patch('mira_memory.load', side_effect=ValueError('corrupt')):
            self.assertIn('ميرا', tools.system_instruction())

    def test_conversation_turns_alternate_and_drop_repeated_question(self):
        rows = [{'role': 'mira', 'text': 'مرحبا'}, {'role': 'user', 'text': 'كم الساعة؟'},
                {'role': 'mira', 'text': 'الثامنة'}, {'role': 'user', 'text': 'شكرا'},
                {'role': 'user', 'text': 'ما الطقس؟'}]
        with patch('mira_memory.recent_messages', return_value=rows):
            turns = tools.conversation_turns(12, drop_trailing_user='ما الطقس؟')
        self.assertEqual([t['role'] for t in turns], ['user', 'model', 'user'])
        self.assertEqual(turns[-1]['parts'][0]['text'], 'شكرا')


if __name__ == '__main__':
    unittest.main()


class ResearchToolTest(unittest.IsolatedAsyncioTestCase):
    async def test_research_is_declared_and_reports_sources(self):
        import research
        self.assertIn('research', {d['name'] for d in tools.DECLARATIONS})
        fake = {'status': 'ok', 'answer': 'Plasma 6.7', 'sources': [{'title': 'kde.org'}], 'model': 'm',
                'searched': True, 'summary': 'بحثت في الإنترنت · kde.org'}
        events, ctx = collect()
        with patch.object(research, 'research', return_value=fake) as call:
            result = await tools.run_tool('research', {'question': 'آخر إصدار Plasma؟'}, ctx)
        call.assert_called_once_with('آخر إصدار Plasma؟', 'ar', True)
        self.assertEqual((result['status'], result['sources'][0]['title']), ('ok', 'kde.org'))

    def test_research_without_config_fails_honestly(self):
        import research
        with patch.object(research, 'GEMINI_CONFIG', research.Path('/nonexistent/gemini.json')):
            result = research.research('سؤال')
        self.assertEqual(result['status'], 'error')
        self.assertEqual(research.research('   ')['error'], 'empty_question')
