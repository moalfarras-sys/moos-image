"""The shared tool registry: schema sanity, validation, verified statuses, no secrets; Mira's identity,
her rules for every capability, the tracked agent task and the THIS MACHINE block."""
import ast
import asyncio
import importlib.util
import json
import os
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import tools

HERE = Path(__file__).resolve().parent


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
        self.assertEqual(declared - names, set(tools.MOAI_SKIP) & declared,
                         'every Mo AI tool but the ones Mira answers herself is declared by name')
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
            self.assertEqual(set(data) - {'elapsed_ms', 'summary_en'}, {'name', 'status', 'summary', 'args_preview'})
            self.assertIsNone(re.search('[؀-ۿ]', data['summary_en']), data)   # the English window's row

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
        self.assertEqual(result['summary_en'], 'Sent to Echo: Echo volume 40%')
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

    async def test_the_english_window_reads_english_action_rows(self):
        import moai_tools
        events, ctx = collect()
        status = {'status': 'ok', 'output': json.dumps({'volume': 40})}
        with patch.object(moai_tools, 'execute', side_effect=[{'status': 'ok'}, status]):
            result = await tools.run_tool('set_volume', {'value': 40}, ctx)
        self.assertEqual(result['summary_en'], 'Computer volume · done and confirmed')
        self.assertEqual(result['summary'], moai_tools.title('set_volume', 'ar') + ' · تم وتأكدت')
        with patch.object(moai_tools, 'execute', return_value={'status': 'error', 'error': 'busy'}):
            result = await tools.run_tool('disk_status', {}, ctx)
        self.assertEqual(result['summary_en'], 'Disk space · not done (busy)')
        rows = [json.loads(text) for kind, text in events if kind == 'tool']
        self.assertEqual([r['summary_en'] for r in rows], ['Computer volume · done and confirmed', 'Disk space · not done (busy)'])
        # A tool that wrote no English line gets none: the window falls back to the Arabic one.
        with patch('weather_link.current', return_value={'city': 'Berlin', 'condition_ar': 'صافٍ', 'temperature_c': 20,
                                                          'source': 'Open-Meteo', 'status': 'ok'}):
            result = await tools.run_tool('current_weather', {'city': 'Berlin'}, ctx)
        self.assertNotIn('summary_en', result)
        self.assertNotIn('summary_en', json.loads(events[-1][1]))

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
        self.assertEqual(result['summary_en'], 'Confirmed: colour pink · light.a · on')
        with patch.object(home_link, 'control_all_lights', return_value={'status': 'partial', 'confirmed': 1,
                                                                         'total': 2, 'results': []}):
            result = await tools.run_tool('home_lights_all', {'action': 'turn_off'}, ctx)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('1', result['summary'])
        self.assertEqual(result['summary_en'], 'All lights off · 1 of 2 confirmed')
        for kind, text in events:
            self.assertIsNone(re.search('[؀-ۿ]', json.loads(text).get('summary_en', '')), text)

    async def test_agent_answer_is_not_claimed_as_executed(self):
        # The task API is down (an older Mo AI): the agent is asked the old way, and its words stay unverified.
        import moai_agent
        import moai_link
        events, ctx = collect()
        hooks = []
        ctx.on_long_task = lambda: hooks.append(1)
        with patch.object(moai_agent, 'post', return_value={'error': 'agent_unreachable'}), \
                patch.object(moai_link, 'ask', return_value='فتحت المشروع'):
            result = await tools.run_tool('moai_project_task', {'request': 'افحص مشروع MoOS'}, ctx)
        self.assertEqual(result['status'], 'pending')
        self.assertFalse(result['execution_verified'])
        self.assertEqual(result['task_api'], 'agent_unreachable')
        self.assertEqual(hooks, [1])

    async def test_current_time_local_and_zone(self):
        events, ctx = collect()
        result = await tools.run_tool('current_time', {}, ctx)
        self.assertEqual(result['status'], 'ok')
        self.assertIn(result['weekday_ar'], tools._WEEKDAYS_AR)
        self.assertRegex(result['spoken_ar'], r'^الساعة \d{1,2} ')
        self.assertRegex(result['spoken_en'], r'^\d{1,2}:\d\d (AM|PM)$')
        self.assertTrue(result['summary_en'].startswith(result['spoken_en'] + ' · '))
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

    async def test_research_answers_in_the_question_s_language(self):
        import research
        events, ctx = collect()
        fake = {'status': 'ok', 'answer': 'x', 'sources': [], 'summary': 'x'}
        with patch.object(research, 'research', return_value=fake) as call:
            await tools.run_tool('research', {'question': 'Who won the 2026 World Cup?', 'web': True}, ctx)
            await tools.run_tool('research', {'question': 'مين ربح كأس العالم 2026?'}, ctx)
        self.assertEqual([c.args[1] for c in call.call_args_list], ['en', 'ar'])

    def test_message_language(self):
        cases = {'كم الساعة؟': 'ar', 'What time is it?': 'en', 'Wie spät ist es?': 'en', 'Mach das Licht aus 🙂': 'en',
                 'ok ميرا': 'ar', '42': 'ar', '': 'ar'}
        for text, lang in cases.items():
            self.assertEqual(tools.message_lang(text), lang, text)
        self.assertEqual(tools.message_lang('42', 'en'), 'en')
        self.assertEqual(tools.message_lang('', 'xx'), 'ar')

    async def test_the_owner_s_own_language_wins_over_the_question_s_script(self):
        # The model often rewrites an Arabic question in English for the search.
        import research
        events, ctx = collect()
        ctx.lang = 'ar'
        with patch.object(research, 'research', return_value={'status': 'ok', 'summary': 'x'}) as call:
            await tools.run_tool('research', {'question': 'latest Plasma release'}, ctx)
        self.assertEqual(call.call_args.args[1], 'ar')

    def test_research_carries_the_identity_and_strips_kernel_tags(self):
        import types as pytypes
        import research
        seen = []

        class Models:
            def generate_content(self, model, contents, config):
                seen.append(config.system_instruction)
                return pytypes.SimpleNamespace(text='The kernel is 7.2.7-200.fc44.x86_64.', candidates=[])
        client = pytypes.SimpleNamespace(models=Models())
        with patch.object(research, '_client', return_value=(client, {})):
            arabic = research.research('ما نواة جهازي؟', 'ar', web=False)
            english = research.research('Which kernel does my computer run?', 'en', web=False)
        import moai_tools
        self.assertIn(moai_tools.IDENTITY[0], seen[0])
        self.assertIn(moai_tools.IDENTITY[1], seen[1])
        self.assertIn('never name another distribution as its system or base', seen[1])
        self.assertIn('Answer in the language of the question', seen[1])     # German stays German
        self.assertIn('أجب بلغة السؤال نفسها', seen[0])
        for result in (arabic, english):
            self.assertEqual(result['status'], 'ok')
            self.assertNotIn('fc44', result['answer'])
            self.assertIn('7.2.7-200', result['answer'])
        self.assertEqual((arabic['lang'], english['lang']), ('ar', 'en'))


# ─── identity ─────────────────────────────────────────────────────────
# Built from pieces so this file itself never carries the words it forbids.
# The same words build_files/verify_no_foreign_identity.py forbids (LAUNCHER_FOREIGN and its unit sweep).
FOREIGN = re.compile('fed' + 'ora' + '|' + 'kino' + 'ite' + '|' + 'silver' + 'blue' + '|' + 'red' + r'[\s_-]*' + 'hat' +
                     '|' + r'\b' + 'rh' + 'el' + r'\b' + '|' + 'فيد' + 'ورا' + '|' + '(?<![؀-ۿ])' + 'ريد' + r'\s*' + 'هات' + '(?![؀-ۿ])', re.I)
_CODE_TOKEN = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`|(//[^\n]*|/\*.*?\*/)', re.S)


_RE_CALLS = {'compile', 'sub', 'subn', 'search', 'match', 'fullmatch', 'findall', 'finditer', 'split'}


def _python_strings(source):
    """Every string constant of a Python module except docstrings and regular-expression patterns
    (a scrubber that finds the base's name is code, not text; comments are not tokens at all)."""
    tree = ast.parse(source)
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                skip.add(id(first.value))
        if isinstance(node, ast.Call) and node.args and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 're' and node.func.attr in _RE_CALLS:
            skip.update(id(part) for part in ast.walk(node.args[0]))
    return [(node.lineno, node.value) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip]


def _without_comments(source, kind):
    keep_lines = lambda text: '\n' * text.count('\n')    # line numbers stay those of the file
    if kind == 'html':
        source = re.sub(r'<!--.*?-->', lambda m: keep_lines(m.group(0)), source, flags=re.S)
    if kind == 'desktop':
        return '\n'.join(line for line in source.splitlines() if not line.lstrip().startswith('#'))
    # QML, JS, CSS and the script parts of HTML: drop // and /* */ comments, never the inside of a string.
    return _CODE_TOKEN.sub(lambda m: keep_lines(m.group(0)) if m.group(1) else m.group(0), source)


def foreign_names(files):
    """(file, line, text) for every user-visible string that names the base distribution."""
    hits = []
    for path in files:
        source = path.read_text(encoding='utf-8', errors='replace')
        if path.suffix == '.py':
            for line, text in _python_strings(source):
                if FOREIGN.search(text):
                    hits.append((path.name, line, text[:80]))
            continue
        kind = 'html' if path.suffix == '.html' else 'desktop' if path.suffix == '.in' else 'code'
        cleaned = _without_comments(source, kind)
        for number, line in enumerate(cleaned.splitlines(), 1):
            if FOREIGN.search(line):
                hits.append((path.name, number, line.strip()[:80]))
    return hits


def shipped_sources():
    """What reaches a screen or a speaker: Mira's Python (not tests or developer tools), her QML and
    scripts, the phone app and the launchers, and the Echo client's spoken words."""
    files = [p for p in HERE.glob('*.py') if not p.name.startswith('test_')]
    for folder in ('pages', 'companion', 'device'):
        files += sorted((HERE / folder).glob('*.py'))
    for pattern in ('qml/**/*.qml', 'qml/**/*.js', 'companion/static/**/*', 'desktop/*.in'):
        files += [p for p in sorted(HERE.glob(pattern)) if p.is_file() and p.suffix in
                  ('.qml', '.js', '.html', '.css', '.webmanifest', '.in')]
    return files


class IdentityTest(unittest.IsolatedAsyncioTestCase):
    def test_kernel_is_a_number_only(self):
        import moai_tools
        cases = {'7.2.7-200.fc44.x86_64': '7.2.7-200', '7.2.7-200': '7.2.7-200',
                 '5.14.0-362.8.1.el9_3.x86_64': '5.14.0-362.8.1', '6.9.0-1.fc41.aarch64': '6.9.0-1',
                 None: '', '': ''}
        for raw, clean in cases.items():
            self.assertEqual(moai_tools.clean_kernel(raw), clean, raw)
        self.assertEqual(moai_tools.scrub_identity('kernel-7.2.7-200.fc44.x86_64 ok'), 'kernel-7.2.7-200.x86_64 ok')
        self.assertEqual(moai_tools.scrub_identity('fcitx5 and .fc44 alone'), 'fcitx5 and .fc44 alone')

    def test_the_page_cleaner_drops_the_tag_with_its_arch_and_the_name(self):
        """moai_tools.clean_identity: the one cleaner for text a page shows the owner."""
        import moai_tools
        base = 'fed' + 'ora'
        cases = {
            'kernel 7.2.7-200.fc44.x86_64 up': 'kernel 7.2.7-200 up',
            'Kernel 7.2.7-200.el9_4.aarch64': 'Kernel 7.2.7-200',
            '6.11.4-301.fc44': '6.11.4-301',
            'kernel-core-7.2.7-200.fc44.x86_64.rpm': 'kernel-core-7.2.7-200.rpm',
            f'rpm-ostree: pipewire-1.4.9-1.fc44.x86_64 from {base}-updates': 'rpm-ostree: pipewire-1.4.9-1 from MoOS-updates',
            f'Staged 44.20260929.960 on {base}-44 .fc44 base': 'Staged 44.20260929.960 on MoOS-44  base',
            f'{base.title()} Linux 44': 'MoOS 44',
            'gcc (GCC) 16.1 (Red' + ' Hat 16.1-1)': 'gcc (GCC) 16.1 (MoOS 16.1-1)',
            'يعمل على فيد' + 'ورا': 'يعمل على MoOS',
            None: '',
            44: '44',
        }
        for raw, clean in cases.items():
            self.assertEqual(moai_tools.clean_identity(raw), clean, raw)
            self.assertIsNone(FOREIGN.search(moai_tools.clean_identity(raw)), raw)
        for kept in ('fcitx5', 'shelf', 'Federal', 'org.videolan.VLC', 'hundred hats', 'أريد هاتفاً جديداً',
                     'init.el', 'v1.2.fcm', 'MoOS 44.20260927.952'):
            self.assertEqual(moai_tools.clean_identity(kept), kept)
        # The page form goes further than the model form, which keeps a bare tag and the architecture.
        self.assertEqual(moai_tools.clean_identity('fcitx5 and .fc44 alone'), 'fcitx5 and  alone')
        self.assertEqual(moai_tools.clean_identity('kernel-7.2.7-200.fc44.x86_64 ok'), 'kernel-7.2.7-200 ok')

    def test_store_results_keep_third_party_names_exact(self):
        import moai_tools
        app = {'id': 'org.' + 'fed' + 'oraproject.MediaWriter', 'name': 'Fed' + 'ora Media Writer', 'summary': 's',
               'installed': False, 'verified': True, 'installs': 10, 'recommended': False,
               'icon': 'https://dl.flathub.org/media/org/x/icon.png', 'note': 'ملاحظة | a note', 'extra': 'dropped'}
        with patch.object(moai_tools, '_request', return_value=(200, {'results': [app], 'source': 'flathub'})):
            found = moai_tools.search_apps('writer')
        self.assertEqual(found['apps'], [{key: app[key] for key in app if key != 'extra'}],
                         'the Apps page gets the icon and the note, and the id and name stay exact')

    async def test_tool_output_reaches_the_model_without_the_base_tag(self):
        import moai_tools
        events, ctx = collect()
        with patch.object(moai_tools, 'execute', return_value={'status': 'ok',
                                                               'output': 'booted 44.20260927.952 · kernel 7.2.7-200.fc44.x86_64'}):
            result = await tools.run_tool('os_state', {}, ctx)
        self.assertEqual(result['status'], 'ok')
        self.assertNotIn('fc44', json.dumps(result))
        self.assertIn('7.2.7-200', result['output'])

    def test_the_base_name_is_scrubbed_in_every_form(self):
        import moai_tools
        base = 'Fed' + 'ora'
        cases = [f'{base} Linux 44 (Kino' + 'ite)', f'Red Hat, Inc.', 'RH' + 'EL 9', f'{base.lower()}project.org',
                 'Silver' + 'blue', f'flatpak remote {base.lower()}', 'يعمل على فيد' + 'ورا', 'مبني على ريد' + ' هات',
                 f'gcc 15.2.1 (Red Hat 15.2.1-1)', f'{base.upper()}_44']
        for text in cases:
            clean = moai_tools.scrub_identity(text)
            self.assertIsNone(FOREIGN.search(clean), (text, clean))
        self.assertEqual(moai_tools.scrub_identity(f'{base} Linux 44'), 'MoOS 44')
        # «أريد» (I want) and «هاتف» (phone) hold the same letters: only the name standing alone goes.
        for kept in ('أريد هاتفاً جديداً', 'قال أريد هات', 'اتصل ريد هاتفياً', 'hundred hats', 'fcitx5', 'shelf', 'Federal'):
            self.assertEqual(moai_tools.scrub_identity(kept), kept)
        nested = moai_tools.scrub_identity({'a': [f'{base} 44', 7, None], 'b': {'c': '7.2.7-200.fc44'}})
        self.assertEqual(nested, {'a': ['MoOS 44', 7, None], 'b': {'c': '7.2.7-200'}})

    async def test_a_journal_line_naming_the_base_reaches_the_model_as_moos(self):
        import moai_tools
        base = 'fed' + 'ora'
        line = (f'Sep 29 kernel: Linux version 7.2.7-200.fc44.x86_64 (mockbuild@build.{base}project.org) '
                f'(gcc (GCC) 15.2.1 (Red Hat 15.2.1-1)) · rpm-ostree: remote "{base}" · {base.title()} Linux 44 (Kino' + 'ite)')
        events, ctx = collect()
        for name in ('read_journal', 'unit_status', 'support_bundle', 'device_report', 'os_state'):
            with patch.object(moai_tools, 'execute', return_value={'status': 'error', 'output': line, 'error': line}):
                result = await tools.run_tool(name, {'name': 'x.service'} if name == 'unit_status' else {}, ctx)
            payload = json.dumps(result, ensure_ascii=False)
            self.assertIsNone(FOREIGN.search(payload), (name, payload))
            self.assertIn('7.2.7-200', result['output'])
        self.assertIsNone(FOREIGN.search(''.join(text for _, text in events)))

    def test_a_research_answer_naming_the_base_is_scrubbed_and_its_source_left_out(self):
        import types as pytypes
        import research
        base = 'Fed' + 'ora'
        chunks = [pytypes.SimpleNamespace(web=pytypes.SimpleNamespace(title=f'{base} Magazine', uri='https://x')),
                  pytypes.SimpleNamespace(web=pytypes.SimpleNamespace(title='kde.org', uri='https://kde.org'))]
        response = pytypes.SimpleNamespace(
            text=f'This computer runs {base} Linux with kernel 7.2.7-200.fc44; فيد' + 'ورا مذكورة هنا.',
            candidates=[pytypes.SimpleNamespace(grounding_metadata=pytypes.SimpleNamespace(grounding_chunks=chunks))])

        class Models:
            def generate_content(self, model, contents, config):
                return response
        with patch.object(research, '_client', return_value=(pytypes.SimpleNamespace(models=Models()), {})):
            result = research.research('What runs my computer?', 'en')
        self.assertEqual(result['status'], 'ok')
        self.assertIsNone(FOREIGN.search(json.dumps(result, ensure_ascii=False)), result)
        self.assertEqual(result['sources'], [{'title': 'kde.org'}])
        self.assertTrue(result['searched'])
        self.assertIn('7.2.7-200', result['answer'])
        self.assertTrue(result['summary_en'].startswith('Searched the web'))

    async def test_health_and_machine_facts_are_scrubbed(self):
        import moai_tools
        base = 'Fed' + 'ora'
        report = {**REPORT, 'findings': [{'severity': 'warning', 'title': f'منفذ | {base} remote is enabled'}]}
        plan = {**PLAN, 'driver_status': f'{base} nouveau driver', 'actions': [
            {'severity': 'warning', 'title': f'تعريف | Kino' + 'ite firmware', 'url': ''}]}
        scan = {**SCAN, 'device_plan': plan, 'cpu': f'{base} vCPU'}

        def request(path, body=None, timeout=30):
            if path == '/health':
                return 200, {'report': report}
            if path == '/scan':
                return 200, scan
            if path == '/diagnose':
                return 200, {'healthy': False, 'ok': 1, 'fail': 1, 'issues': [f'x | {base} repo file']}
            return 200, QUICK
        with patch.object(moai_tools, '_request', side_effect=request):
            report_out = moai_tools.health('en', deep=True)
            facts = moai_tools.machine_facts()
        for value in (report_out, facts):
            self.assertIsNone(FOREIGN.search(json.dumps(value, ensure_ascii=False)), value)

    def test_approved_job_output_is_scrubbed_but_a_read_stays_exact(self):
        import moai_tools
        base = 'fed' + 'ora'
        listing = json.dumps([{'id': f'org.{base}project.MediaWriter'}])
        with patch.object(moai_tools, '_request', return_value=(200, {'status': 'ok', 'output': listing})):
            self.assertEqual(moai_tools.execute('list_installed_apps', {})['output'], listing)   # an id the page removes by
            approved = moai_tools.execute('system_update', {}, confirmed=True)
        self.assertIsNone(FOREIGN.search(approved['output']))
        with patch.object(moai_tools, '_request', return_value=(200, {'status': 'ok', 'output': f'remote {base} 7.2.7-200.fc44'})):
            job = moai_tools.job('j1')
        self.assertEqual(job['output'], 'remote MoOS 7.2.7-200')

    def test_both_channels_carry_the_identity_rule(self):
        with patch('mira_memory.load', return_value={}), patch('mira_memory.profile_text', return_value=''):
            voice = tools.system_instruction('ar', channel='voice')
            text = tools.system_instruction('en', channel='text')
        for instruction in (voice, text):
            self.assertIn(tools.IDENTITY.strip(), instruction)
            self.assertIn('MoOS', instruction)
            self.assertIsNone(FOREIGN.search(instruction), 'the instruction never names the base itself')

    def test_no_user_visible_string_names_the_base_distribution(self):
        files = shipped_sources()
        self.assertGreater(len(files), 40, 'the sweep found too few files to mean anything')
        self.assertIn('tools.py', {p.name for p in files})
        self.assertTrue(any(p.suffix == '.qml' for p in files))
        self.assertEqual(foreign_names(files), [])

    def test_the_sweep_bites(self):
        word = 'Fed' + 'ora'
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'a.py').write_text(f'"""Built from {word}."""\n# {word} comment\nx = "running {word} 44"\n'
                                       f'import re\nNAME = re.compile(r"\\b{word}\\b")\n')
            (root / 'b.qml').write_text(f'// {word}\nText {{ text: "https://x.org/{word}" }} /* {word} */\n')
            (root / 'c.qml').write_text(f'Text {{ text: "https://moos.example/" }} // {word}\n')
            (root / 'd.html').write_text(f'<!-- {word}\n-->\n<p>{"Red" + " Hat"}</p>\n')
            (root / 'e.in').write_text(f'# {word}\nName=Mira\n')
            arabic = 'فيد' + 'ورا'
            (root / 'f.qml').write_text(f'// {arabic}\nText {{ text: "يعمل بنظام {arabic}" }}\nText {{ text: "أريد هاتفاً" }}\n')
            (root / 'g.py').write_text(f'x = "{"Kino" + "ite"} 44"\n')
            hits = foreign_names(sorted(root.iterdir()))
        self.assertEqual(sorted((name, line) for name, line, _ in hits),
                         [('a.py', 3), ('b.qml', 2), ('d.html', 3), ('f.qml', 2), ('g.py', 1)])


# ─── titles and consequences ──────────────────────────────────────────
def tree_schema_names():
    """The tools the MoOS tree next to Mira declares (it may be newer than the installed image)."""
    path = HERE.parent / 'system_files/usr/lib/moai/moai_tool_schemas.py'
    if not path.is_file():
        return set()
    spec = importlib.util.spec_from_file_location('tree_moai_tool_schemas', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {t['function']['name'] for t in module.ALL_TOOLS}


NEW_TOOLS = ('install_codex', 'install_claude_code', 'install_opencode', 'install_hermes', 'install_openclaw',
             'smart_setup', 'check_system_update', 'restart_computer', 'install_rpm', 'remote_control', 'fast_remote')


class TitlesTest(unittest.TestCase):
    def test_both_title_tables_cover_every_declared_tool(self):
        import moai_tools
        declared = moai_tools.names() | tree_schema_names()
        self.assertGreaterEqual(len(declared), 50)
        for name in sorted(declared | set(NEW_TOOLS)):
            self.assertIn(name, moai_tools.TITLES_AR, f'{name}: no Arabic title')
            self.assertIn(name, moai_tools.TITLES_EN, f'{name}: no English title')
            self.assertNotEqual(moai_tools.title(name, 'en'), name.replace('_', ' '))
        arabic = re.compile('[؀-ۿ]')
        for name, text in moai_tools.TITLES_EN.items():
            self.assertIsNone(arabic.search(text), name)
        for name, text in moai_tools.TITLES_AR.items():
            self.assertTrue(arabic.search(text) or text.startswith('Mo '), name)
        self.assertEqual(moai_tools.title('no_such_tool', 'en'), 'no such tool')

    def test_every_change_the_owner_approves_says_what_it_will_do(self):
        import moai_tools
        for name in sorted(moai_tools.names()):
            info = moai_tools.meta(name)
            if info['category'] in moai_tools.CONFIRM or info.get('confirm_values'):
                self.assertTrue(moai_tools.consequence(name, 'ar'), name)
                self.assertTrue(moai_tools.consequence(name, 'en'), name)
        self.assertEqual(moai_tools.consequence('get_system_status', 'en'), '')

    def test_consequence_prefers_the_schema_and_survives_its_absence(self):
        import moai_tools
        with patch.object(moai_tools, 'meta', return_value={'category': 'user_confirm', 'consequence_ar': ' يثبّت  شيئاً ',
                                                            'consequence_en': 'Installs a thing'}):
            self.assertEqual(moai_tools.consequence('install_app', 'ar'), 'يثبّت شيئاً')
            self.assertEqual(moai_tools.consequence('install_app', 'en'), 'Installs a thing')
        with patch.object(moai_tools, 'meta', return_value={'category': 'user_confirm'}):
            self.assertEqual(moai_tools.consequence('install_app', 'en'), moai_tools.CONSEQUENCES_EN['install_app'])
        with patch.object(moai_tools, 'meta', return_value=None):
            self.assertEqual(moai_tools.consequence('restart_computer', 'ar'), moai_tools.CONSEQUENCES_AR['restart_computer'])
            self.assertEqual(moai_tools.consequence('unknown_tool', 'ar'), '')

    def test_consequence_tables_speak_both_languages(self):
        import moai_tools
        self.assertEqual(set(moai_tools.CONSEQUENCES_AR), set(moai_tools.CONSEQUENCES_EN))

    def test_the_phone_agent_fallback_promises_no_administrator_step(self):
        """moai-do install-openclaw installs into ~/.local with no password (as the schema says)."""
        import moai_tools
        english, arabic = moai_tools.CONSEQUENCES_EN['install_openclaw'], moai_tools.CONSEQUENCES_AR['install_openclaw']
        self.assertNotIn('administrator', english)
        self.assertIn('no password', english)
        self.assertIn('cloud brain', english)
        self.assertNotIn('مسؤول', arabic)
        self.assertIn('بلا كلمة مرور', arabic)


class ConsequenceCardTest(unittest.IsolatedAsyncioTestCase):
    async def test_a_card_says_what_approval_will_do(self):
        import moai_tools
        events, ctx = collect()
        asked = []
        ctx.request_confirmation = lambda item: asked.append(item) or {'id': 'p9'}
        with patch.object(moai_tools, 'execute', return_value={'status': 'confirm', 'category': 'privileged_confirm'}):
            result = await tools.run_tool('system_update', {}, ctx)
        self.assertEqual(asked[0]['consequence_ar'], moai_tools.consequence('system_update', 'ar'))
        self.assertIn('restart', asked[0]['consequence_en'])
        self.assertEqual((result['status'], result['awaiting']), ('pending', 'owner_confirmation'))
        self.assertEqual(result['will_happen_en'], asked[0]['consequence_en'])
        self.assertIs(result['executed'], False)
        self.assertEqual(result['summary_en'], 'Waiting for your approval: ' + moai_tools.title('system_update', 'en'))
        self.assertIn(tools.places()['approve'], result['next'])
        self.assertIn(('tool', 'system_update'), [(k, json.loads(t)['name']) for k, t in events if k == 'tool'])
        self.assertEqual(json.loads(events[-1][1])['summary_en'], result['summary_en'])
        # A tool with nothing to say keeps the card as it was.
        asked.clear()
        with patch.object(moai_tools, 'execute', return_value={'status': 'confirm', 'category': 'user_confirm'}), \
                patch.object(moai_tools, 'consequence', return_value=''):
            result = await tools.run_tool('update_apps', {}, ctx)
        self.assertNotIn('consequence_ar', asked[0])
        self.assertNotIn('will_happen_ar', result)


# ─── rules for every capability ───────────────────────────────────────
NOT_TOOLS = {'owner_confirmation', 'will_happen_ar', 'will_happen_en', 'fix_tool'}


class CapabilityRulesTest(unittest.TestCase):
    def test_a_rule_joins_only_with_its_tools(self):
        text = tools.capability_rules({'install_codex', 'install_opencode', 'restart_computer', 'remote_control'})
        for name in ('install_codex', 'install_opencode', 'restart_computer', 'remote_control'):
            self.assertIn(name, text)
        for name in ('install_claude_code', 'install_rpm', 'check_system_update', 'smart_setup', 'fast_remote'):
            self.assertNotIn(name, text)
        here = tools.places()
        self.assertIn(here['agents_tab'], text)       # the owner opens a coding agent from the Workbench's tab
        self.assertIn(here['workbench'], text)
        self.assertEqual(tools.capability_rules(set()), tools.APP_DROP_RULE.format(**here))
        everything = tools.capability_rules(set(NEW_TOOLS))
        for name in NEW_TOOLS:
            self.assertIn(name, everything)

    def test_rules_never_teach_a_tool_the_registry_lacks(self):
        text = tools.IDENTITY + tools.rules() + tools.capability_rules()
        names = set(re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', text)) - NOT_TOOLS
        self.assertTrue(names)
        self.assertEqual(names - set(tools._BY_NAME), set())

    def test_rules_name_the_new_surfaces(self):
        text, here = tools.rules(), tools.places()
        for needle in ('moai_project_task', 'deep=true', 'fix_tool', 'suggestions', 'will_happen_ar', 'will_happen_en',
                       'أوامر حرة', here['system'], here['apps'], here['from_file'], here['workbench'], here['tasks_tab'],
                       here['approve'], here['agent_card'], here['agent_allow'], here['agent_deny']):
            self.assertIn(needle, text)
        self.assertNotIn('تشغيل موسيقى في المتصفح', text)


# «عربي» (English): how the rules name a place of Mira's window.
PLACE = re.compile(r'«([^«»]+)» \(([^()]+)\)')
STALE = ('منضدة العمل', 'صندوق ميرا', 'تثبيت ملف', 'inbox', 'Inbox')


def shown_labels():
    return {tuple(v) for v in tools.interface_words().values() if isinstance(v, (tuple, list)) and len(v) == 2}


class PlacesTest(unittest.TestCase):
    """Every page or button Mira names is one her window shows, under the words it shows."""

    def tearDown(self):
        tools._labels_cache.clear()

    def test_every_key_is_a_current_label_and_the_fallbacks_match_it(self):
        words = tools.interface_words()
        for key, default in tools.LABEL_DEFAULTS.items():
            self.assertIn(key, words, f'{key}: the window no longer has this label; rename it in tools.PLACE_KEYS')
            self.assertEqual(tuple(words[key]), default, f'{key} was renamed: update tools.LABEL_DEFAULTS')
        self.assertEqual(set(tools.PLACE_KEYS.values()), set(tools.LABEL_DEFAULTS))

    def test_every_place_in_the_rules_is_a_label_the_window_shows(self):
        shown = shown_labels()
        text = tools.rules() + tools.capability_rules(set(NEW_TOOLS) | set(tools._BY_NAME))
        named = PLACE.findall(text)
        self.assertGreaterEqual(len(named), 12, named)
        for pair in named:
            self.assertIn(pair, shown, f'«{pair[0]}» ({pair[1]}) is not a label of Mira\'s window')
        for stale in STALE:
            self.assertNotIn(stale, text)

    def test_a_renamed_label_renames_the_sentence(self):
        tools._labels_cache.clear()
        words = {**tools.interface_words(), 'nav_workbench': ('المختبر', 'Lab')}
        with patch.object(tools, 'interface_words', return_value=words):
            text = tools.rules() + tools.capability_rules()
        self.assertIn('«المختبر» (Lab)', text)
        self.assertNotIn(tools.LABEL_DEFAULTS['nav_workbench'][0], text)

    def test_without_the_interface_tables_the_defaults_answer(self):
        tools._labels_cache.clear()
        with patch.object(tools, 'interface_words', return_value={}):
            self.assertEqual(tools.labels(), tools.LABEL_DEFAULTS)
            self.assertIn('«', tools.rules())
        self.assertEqual(tools._labels_cache, {}, 'a fallback reading is never cached')


# ─── the Workbench: a tracked agent task ──────────────────────────────
TASK = '0f8fad5b-d9cb-469f-a165-70867728950e'
PROJECTS = [{'id': 'ea6e19fda493e98f82e2', 'name': 'MoOS', 'path': '/var/home/moos/moos-image'},
            {'id': 'a' * 20, 'name': 'Mira Echo', 'path': '/var/home/moos/echo'},
            {'id': 'b' * 20, 'name': 'Mira Phone', 'path': '/var/home/moos/phone'}]


def fake_agent(projects=PROJECTS, create=None, start=None):
    calls = []

    def get(path, **query):
        calls.append(('GET', path))
        return projects

    def post(path, body):
        calls.append(('POST', path, body))
        return {'/api/task/create': create, '/api/task/action': start}.get(path, {'error': 'unexpected'})
    return calls, get, post


class AgentTaskTest(unittest.IsolatedAsyncioTestCase):
    async def run_task(self, args, **agent):
        import moai_agent
        import moai_link
        calls, get, post = fake_agent(**agent)
        events, ctx = collect()
        with patch.object(moai_agent, 'get', side_effect=get), patch.object(moai_agent, 'post', side_effect=post), \
                patch.object(moai_link, 'ask', return_value='جواب') as ask:
            result = await tools.run_tool('moai_project_task', args, ctx)
        return result, calls, events, ask

    async def test_a_request_becomes_a_started_tracked_task(self):
        result, calls, events, ask = await self.run_task(
            {'request': 'افحص الاختبارات وأصلح الفاشل منها'},
            create={'ok': True, 'id': TASK, 'status': 'pending'},
            start={'ok': True, 'id': TASK, 'status': 'running', 'session_key': 'moai-task-' + TASK})
        ask.assert_not_called()
        self.assertEqual(calls, [('POST', '/api/task/create', {'title': 'افحص الاختبارات وأصلح الفاشل منها',
                                                              'description': 'افحص الاختبارات وأصلح الفاشل منها'}),
                                 ('POST', '/api/task/action', {'id': TASK, 'action': 'start'})])
        self.assertEqual(result['status'], 'pending', 'started is not done')
        self.assertEqual((result['task_id'], result['task_status']), (TASK, 'running'))
        self.assertIs(result['execution_verified'], False)
        words, shown = tools.labels(), shown_labels()
        self.assertIn('«' + words['nav_workbench'][0] + '»', result['summary'])
        self.assertIn('«' + words['agent_approval_title'][0] + '»', result['summary'])
        self.assertIn(words['nav_workbench'][1], result['summary_en'])
        self.assertIsNone(re.search('[؀-ۿ]', result['summary_en'].replace(result['task_title'], '')))
        named = PLACE.findall(result['next'])
        self.assertGreaterEqual(len(named), 5)
        self.assertTrue(all(pair in shown for pair in named), named)
        for stale in STALE:
            self.assertNotIn(stale, result['summary'] + result['summary_en'] + result['next'])
        self.assertIn(('workbench', json.dumps({'task': TASK, 'status': 'running'})), events)

    async def test_a_named_project_is_resolved_to_its_id(self):
        for named in ('moos', 'MoOS', 'moos-image', 'ea6e19fda493e98f82e2'):
            result, calls, events, ask = await self.run_task(
                {'request': 'راجع آخر التعديلات', 'project': named},
                create={'ok': True, 'id': TASK}, start={'ok': True, 'id': TASK, 'status': 'running'})
            self.assertEqual(calls[1][2]['project'], 'ea6e19fda493e98f82e2', named)
            self.assertEqual(result['project'], 'MoOS')
        result, calls, *_ = await self.run_task({'request': 'x', 'project': 'phone'},
                                                create={'ok': True, 'id': TASK}, start={'ok': True, 'id': TASK})
        self.assertEqual(calls[1][2]['project'], 'b' * 20)     # one unique partial name

    async def test_an_unknown_or_ambiguous_project_starts_nothing(self):
        result, calls, events, ask = await self.run_task({'request': 'x', 'project': 'Website'})
        self.assertEqual((result['status'], result['error']), ('error', 'unknown_project'))
        self.assertEqual(result['projects'], ['MoOS', 'Mira Echo', 'Mira Phone'])
        self.assertIn('«' + tools.labels()['nav_workbench'][0] + '»', result['summary'])
        self.assertIn('MoOS, Mira Echo, Mira Phone', result['summary_en'])
        self.assertEqual([c for c in calls if c[0] == 'POST'], [])
        ask.assert_not_called()
        result, calls, *_ = await self.run_task({'request': 'x', 'project': 'mira'})
        self.assertEqual((result['error'], result['projects']), ('ambiguous_project', ['Mira Echo', 'Mira Phone']))
        self.assertEqual([c for c in calls if c[0] == 'POST'], [])

    async def test_a_task_that_did_not_start_is_reported_as_such(self):
        result, calls, events, ask = await self.run_task({'request': 'x'}, create={'ok': True, 'id': TASK},
                                                         start={'error': 'OpenClaw is not installed'})
        self.assertEqual(result['status'], 'error')
        self.assertEqual((result['task_id'], result['task_status']), (TASK, 'pending'))
        self.assertIn('لم تبدأ', result['summary'])
        self.assertIn('OpenClaw is not installed', result['summary'])
        ask.assert_not_called()

    async def test_the_old_path_answers_when_the_task_api_cannot(self):
        for create in ({'error': 'agent_unreachable'}, {'ok': True, 'id': 'not-a-task-id'}, None):
            result, calls, events, ask = await self.run_task({'request': 'افحص المشروع'}, create=create)
            ask.assert_called_once_with('افحص المشروع')
            self.assertEqual(result['status'], 'pending')
            self.assertEqual(result['agent_response'], 'جواب')
            self.assertFalse(result['execution_verified'])
        result, calls, events, ask = await self.run_task({'request': 'x', 'project': 'MoOS'}, projects={'error': 'agent_unreachable'})
        ask.assert_called_once()
        self.assertEqual(result['task_api'], 'agent_unreachable')

    def test_task_titles_are_one_bounded_line(self):
        title = tools._task_title('سطر أول\nسطر\tثانٍ\x07 ' + 'كلمة ' * 60)
        self.assertNotIn('\n', title)
        self.assertNotIn('\x07', title)
        self.assertLessEqual(len(title), 120)
        self.assertTrue(title.endswith('…'))
        self.assertEqual(tools._task_title('  قصير  '), 'قصير')


# ─── health report: daily check, device plan, self-check ──────────────
REPORT = {'generated_at': '2026-09-29T18:42:55+00:00',
          'system': {'version': '44.20260927.952', 'signed': True, 'staged': '', 'rollback': True,
                     'kernel': '7.2.7-200.fc44.x86_64'},
          'updates': {'nightly_system_update': True, 'last_nightly_result': 'success', 'apps': []},
          'summary': {'status': 'attention', 'counts': {'important': 0, 'warning': 4, 'info': 1}, 'app_updates': 0,
                      'system_update_staged': False},
          'findings': [{'severity': 'warning', 'title': 'منفذ مفتوح | A port is open to the network'}],
          'resources': {'top_cpu': [{'name': 'kwin_wayland', 'cpu_percent': 21}]}}
PLAN = {'schema': 1, 'health': 'action-needed', 'gpu_vendor': 'nvidia',
        'gpu': '01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [GeForce RTX 2080 SUPER] [10de:1e81] (rev a1)',
        'driver': 'nouveau', 'driver_status': 'NVIDIA detected; optimized image required',
        'driver_status_ar': 'تم اكتشاف NVIDIA؛ يلزم الانتقال إلى صورة MoOS NVIDIA', 'nvidia_image': False,
        'memory_gib': 15.4, 'missing_recommended_apps': ['org.videolan.VLC', 'org.mozilla.firefox'],
        'actions': [{'id': 'nvidia-image', 'severity': 'important', 'title': 'تعريف NVIDIA الرسمي | NVIDIA driver',
                     'url': 'moos://do/install-nvidia'},
                    {'id': 'kvm', 'severity': 'info', 'title': 'تسريع محاكي أندرويد | Android emulator acceleration',
                     'url': ''}]}
SCAN = {'os': 'MoOS', 'version': '44.20260927.952', 'cpu': 'Intel(R) Core(TM) i5-14400F', 'cores': 16,
        'kernel': '7.2.7-200.fc44.x86_64', 'mem_gb': 15, 'disk': {'total_gb': 476, 'free_gb': 194},
        'gpu': 'nvidia (discrete)', 'arch': 'x86_64', 'remote': {'active': False}, 'agents': {'codex': False},
        'device_plan': PLAN, 'health': {'summary': REPORT['summary']}}
QUICK = {'online': True, 'remote': {'active': True, 'pipewire': True, 'portal': True},
         'agents': {'codex': True, 'claude': False, 'opencode': True, 'hermes': True}}


def fake_control(paths, diagnose=None, scan=SCAN, quick=QUICK):
    def request(path, body=None, timeout=30):
        paths.append(path)
        if path == '/health':
            return 200, {'report': REPORT, 'scanning': False}
        if path == '/scan':
            return (200, scan) if scan is not None else (0, {'error': 'moai_control_unreachable'})
        if path == '/quick':
            return (200, quick) if quick is not None else (0, {'error': 'moai_control_unreachable'})
        if path == '/diagnose':
            return 200, diagnose or {'healthy': False, 'ok': 40, 'fail': 1,
                                     'issues': ['خدمة متعطلة | a service failed on 7.2.7-200.fc44.x86_64']}
        return 404, {'error': 'not found'}
    return request


class HealthReportTest(unittest.IsolatedAsyncioTestCase):
    def test_health_carries_the_device_plan_and_a_clean_kernel(self):
        import moai_tools
        paths = []
        with patch.object(moai_tools, '_request', side_effect=fake_control(paths)):
            report = moai_tools.health('en')
        self.assertEqual(paths, ['/health', '/scan'])
        self.assertEqual(report['moos']['kernel'], '7.2.7-200')
        self.assertIsNone(report['updates']['last_nightly_run'], "systemd's 'success' alone is not a run")
        plan = report['device_plan']
        self.assertEqual(plan['health'], 'action-needed')
        self.assertEqual(plan['driver'], 'NVIDIA detected; optimized image required')
        self.assertEqual(plan['problems'], [{'severity': 'important', 'title': 'NVIDIA driver', 'fix_tool': 'install_nvidia'}])
        self.assertEqual(plan['suggestions'], [{'severity': 'info', 'title': 'Android emulator acceleration', 'fix_tool': ''}])
        self.assertEqual(plan['missing_recommended_apps'], ['org.videolan.VLC', 'org.mozilla.firefox'])
        self.assertNotIn('selfcheck', report)
        self.assertIn('مشكلات 1، اقتراحات 1', report['summary'])
        self.assertIn('1 problems, 1 suggestions', report['summary_en'])

    def test_the_nightly_result_carries_the_time_of_its_run(self):
        import moai_tools
        ran = {**REPORT, 'updates': {**REPORT['updates'], 'last_nightly_run': '2026-09-29T02:10:04+00:00'}}

        def request(path, body=None, timeout=30):
            return (200, {'report': ran}) if path == '/health' else fake_control([])(path, body, timeout)
        with patch.object(moai_tools, '_request', side_effect=request):
            report = moai_tools.health('en')
        self.assertEqual(report['updates']['last_nightly_result'], 'success')
        self.assertEqual(report['updates']['last_nightly_run'], '2026-09-29T02:10:04+00:00')
        described = next(d['description'] for d in tools.DECLARATIONS if d['name'] == 'health_report')
        self.assertIn('last_nightly_run', described, 'the model is told how to read it')

    def test_a_healthy_machine_with_tips_has_no_problems(self):
        import moai_tools
        tips = {**PLAN, 'health': 'ready', 'actions': [
            {'id': 'kvm', 'severity': 'info', 'title': 'x | KVM acceleration', 'url': ''},
            {'id': 'memory', 'severity': 'info', 'title': 'x | More memory', 'url': ''}]}
        with patch.object(moai_tools, '_request', side_effect=fake_control([], scan={**SCAN, 'device_plan': tips})):
            report = moai_tools.health('ar')
            facts = moai_tools.machine_facts()
        self.assertEqual(report['device_plan']['problems'], [])
        self.assertEqual(len(report['device_plan']['suggestions']), 2)
        self.assertIn('مشكلات 0', report['summary'])
        self.assertEqual((facts['plan_problems'], facts['plan_important'], facts['plan_suggestions']), (0, 0, 2))
        english = tools.format_machine(facts, 'en')
        self.assertIn('device plan: ready, 0 problems (0 important), 2 suggestions', english)

    def test_the_deep_chain_fits_its_executor_budget(self):
        import moai_tools
        chain = moai_tools.HEALTH_TIMEOUT_S + moai_tools.SCAN_TIMEOUT_S + moai_tools.DIAGNOSE_TIMEOUT_S
        self.assertLess(chain, tools._EXECUTORS['health_report'][1])
        seen = {}

        def request(path, body=None, timeout=30):
            seen[path] = timeout
            return fake_control([])(path, body, timeout)
        with patch.object(moai_tools, '_request', side_effect=request):
            moai_tools.health('ar', deep=True)
        self.assertEqual(seen, {'/health': moai_tools.HEALTH_TIMEOUT_S, '/scan': moai_tools.SCAN_TIMEOUT_S,
                                '/diagnose': moai_tools.DIAGNOSE_TIMEOUT_S})
        # A hung agent API (projects + create, 15 s each) still leaves the gateway fallback its 190 s.
        self.assertGreaterEqual(tools._EXECUTORS['moai_project_task'][1], 15 + 15 + 190)

    async def test_health_follows_the_owner_s_language_when_known(self):
        import moai_tools
        events, ctx = collect()
        with patch.object(moai_tools, 'health', return_value={'status': 'ok', 'summary': 'x'}) as call:
            await tools.run_tool('health_report', {}, ctx)
            ctx.lang = 'en'
            await tools.run_tool('health_report', {'deep': True}, ctx)
        self.assertEqual([c.args for c in call.call_args_list], [('ar', False), ('en', True)])

    async def test_deep_adds_the_self_check_only_when_asked(self):
        import moai_tools
        events, ctx = collect()
        paths = []
        with patch.object(moai_tools, '_request', side_effect=fake_control(paths)):
            quick = await tools.run_tool('health_report', {}, ctx)
            self.assertNotIn('/diagnose', paths)
            deep = await tools.run_tool('health_report', {'deep': True}, ctx)
        self.assertIn('/diagnose', paths)
        self.assertEqual(quick['status'], 'ok')
        check = deep['selfcheck']
        self.assertEqual((check['status'], check['healthy'], check['broken']), ('ok', False, 1))
        self.assertNotIn('fc44', json.dumps(deep, ensure_ascii=False))
        self.assertIn('أعطال', deep['summary'])

    def test_an_unreachable_plan_or_self_check_is_left_out_honestly(self):
        import moai_tools
        paths = []
        with patch.object(moai_tools, '_request', side_effect=fake_control(paths, scan=None,
                                                                            diagnose={'error': 'x'})):
            report = moai_tools.health('ar', deep=True)
        self.assertEqual(report['status'], 'ok')
        self.assertNotIn('device_plan', report)
        self.assertEqual(report['selfcheck']['status'], 'error')


# ─── THIS MACHINE ─────────────────────────────────────────────────────
FACTS = {'status': 'ok', 'version': '44.20260927.952', 'nvidia_edition': True, 'arch': 'x86_64',
         'kernel': '7.2.7-200', 'cpu': 'Intel Core i5-14400F', 'threads': 16, 'ram_gb': 15.4, 'disk_free_gb': 194,
         'disk_total_gb': 476, 'gpu': 'NVIDIA GeForce RTX 2080 SUPER', 'driver_status': 'NVIDIA proprietary driver active',
         'driver_status_ar': 'تعريف NVIDIA الرسمي يعمل', 'remote_running': True,
         'agents_installed': ['Codex', 'OpenCode', 'Hermes'], 'agents_missing': ['Claude Code'],
         'plan_health': 'ready', 'plan_pending': False, 'plan_problems': 0, 'plan_important': 0, 'plan_suggestions': 2,
         'missing_recommended_apps': 5, 'health_status': 'attention', 'health_findings': 4, 'update_staged': False}


class MachineFactsTest(unittest.TestCase):
    def test_facts_from_scan_and_quick(self):
        import moai_tools
        paths = []
        with patch.object(moai_tools, '_request', side_effect=fake_control(paths)):
            facts = moai_tools.machine_facts()
        self.assertEqual(paths, ['/scan', '/quick'])
        self.assertEqual(facts['status'], 'ok')
        self.assertEqual(facts['kernel'], '7.2.7-200')
        self.assertEqual(facts['cpu'], 'Intel Core i5-14400F')
        self.assertEqual(facts['gpu'], 'NVIDIA GeForce RTX 2080 SUPER')
        self.assertEqual((facts['ram_gb'], facts['disk_free_gb'], facts['threads']), (15.4, 194, 16))
        self.assertIs(facts['remote_running'], True, '/quick is fresher than /scan')
        self.assertEqual(facts['agents_installed'], ['Codex', 'OpenCode', 'Hermes'])
        self.assertEqual(facts['agents_missing'], ['Claude Code'])
        self.assertEqual((facts['plan_problems'], facts['plan_important'], facts['plan_suggestions'],
                          facts['missing_recommended_apps']), (1, 1, 1, 2))
        self.assertEqual((facts['health_status'], facts['health_findings']), ('attention', 4))
        self.assertIs(facts['nvidia_edition'], False)
        with patch.object(moai_tools, '_request', side_effect=fake_control([], quick=None)):
            self.assertIs(moai_tools.machine_facts()['remote_running'], False)    # /scan's reading then
        with patch.object(moai_tools, '_request', side_effect=fake_control([], scan=None)):
            self.assertEqual(moai_tools.machine_facts()['status'], 'error')

    def test_graphics_names(self):
        import moai_tools
        cases = {
            PLAN['gpu']: 'NVIDIA GeForce RTX 2080 SUPER',
            '03:00.0 VGA compatible controller [0300]: Advanced Micro Devices, Inc. [AMD/ATI] Navi 22 '
            '[Radeon RX 6700 XT] [1002:73df] (rev c1)': 'AMD Radeon RX 6700 XT',
            '00:02.0 VGA compatible controller [0300]: Intel Corporation Alder Lake-S GT1 [UHD Graphics 730] '
            '[8086:4692] (rev 0c)': 'Intel UHD Graphics 730',
            '': 'nvidia (discrete)'}
        for pci, name in cases.items():
            self.assertEqual(moai_tools._gpu_name(pci, 'nvidia (discrete)'), name)

    def test_block_in_both_languages(self):
        arabic = tools.format_machine(FACTS, 'ar', 125)
        english = tools.format_machine(FACTS, 'en', 0)
        self.assertTrue(arabic.startswith('هذا الجهاز (قراءة MoOS نفسها قبل 2 دقيقة'))
        for needle in ('MoOS 44.20260927.952 (نسخة NVIDIA)', 'النواة 7.2.7-200', 'NVIDIA GeForce RTX 2080 SUPER',
                       'تعريف NVIDIA الرسمي يعمل', 'Mo PC Remote يعمل', 'Codex، OpenCode، Hermes', 'Claude Code',
                       'خطة الجهاز: جاهز، مشكلات: 0 (مهمة: 0)، اقتراحات: 2', 'تطبيقات مقترحة ناقصة: 5', '4 ملاحظات'):
            self.assertIn(needle, arabic)
        for needle in ('THIS MACHINE', 'kernel 7.2.7-200', '(16 threads)', 'memory 15.4 GB', 'disk 194 GB free of 476',
                       'driver: NVIDIA proprietary driver active', 'Mo PC Remote running', 'not installed: Claude Code',
                       'device plan: ready, 0 problems (0 important), 2 suggestions, 5 recommended apps missing'):
            self.assertIn(needle, english)
        leaked = tools.format_machine({**FACTS, 'kernel': '7.2.7-200.fc44.x86_64'}, 'en')
        self.assertNotIn('fc44', leaked)
        self.assertIsNone(FOREIGN.search(arabic + english))
        sparse = tools.format_machine({'version': '44.1'}, 'en')
        self.assertIn('MoOS 44.1', sparse)
        self.assertNotIn('None', sparse)


BLOCK = 'هذا الجهاز (قراءة MoOS'   # the block's own head, not the rules' mention of it


class MachineContextTest(unittest.TestCase):
    def setUp(self):
        tools._reset_machine_cache()
        self.memory = [patch('mira_memory.load', return_value={}), patch('mira_memory.profile_text', return_value='')]
        for item in self.memory:
            item.start()

    def tearDown(self):
        for item in self.memory:
            item.stop()
        ready = tools._machine.get('ready')
        if ready is not None:
            ready.wait(3)
        tools._reset_machine_cache()

    def test_limits(self):
        self.assertLessEqual(tools.MACHINE_WAIT_S, 1.5)
        self.assertEqual(tools.MACHINE_TTL_S, 600)

    def test_off_in_tests_and_review_on_in_mira_s_own_process(self):
        import sys
        import types as pytypes
        env = {k: v for k, v in os.environ.items() if k not in ('MIRA_MACHINE_CONTEXT', 'MIRA_TEST_MODE')}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(tools.machine_context_enabled())     # this process is unittest
            with patch.dict(sys.modules, {'__main__': pytypes.SimpleNamespace(__file__='/usr/lib/mira/app/app.py')}):
                self.assertTrue(tools.machine_context_enabled())
                with patch.dict(os.environ, {'MIRA_TEST_MODE': '1'}):
                    self.assertFalse(tools.machine_context_enabled())
                with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '0'}):
                    self.assertFalse(tools.machine_context_enabled())
            with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}):
                self.assertTrue(tools.machine_context_enabled())
            with patch.object(tools.moai_tools, 'machine_facts') as fetch:
                text = tools.system_instruction('ar')
            fetch.assert_not_called()
            self.assertNotIn(BLOCK, text)

    def test_the_block_joins_the_instruction(self):
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), \
                patch.object(tools.moai_tools, 'machine_facts', return_value=FACTS) as fetch:
            text = tools.system_instruction('ar')
            again = tools.system_instruction('en', channel='text')
        self.assertIn(BLOCK, text)
        self.assertIn('NVIDIA GeForce RTX 2080 SUPER', text)
        self.assertIn('THIS MACHINE', again)
        self.assertEqual(fetch.call_count, 1, 'read at most every ten minutes')

    def test_building_an_instruction_never_waits_long(self):
        gate = threading.Event()

        def slow():
            gate.wait(5)
            return FACTS
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), patch.object(tools, 'MACHINE_WAIT_S', 0.2), \
                patch.object(tools.moai_tools, 'machine_facts', side_effect=slow) as fetch:
            started = time.monotonic()
            text = tools.system_instruction('ar')
            self.assertLess(time.monotonic() - started, 1.0)
            self.assertNotIn(BLOCK, text, 'no reading yet: the block is left out')
            gate.set()
            self.assertTrue(tools._machine['ready'].wait(3))
            self.assertIn(BLOCK, tools.system_instruction('ar'))
        self.assertEqual(fetch.call_count, 1)

    def test_stale_reading_is_used_while_it_refreshes(self):
        newer = {**FACTS, 'version': '44.20261001.1'}
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), \
                patch.object(tools.moai_tools, 'machine_facts', return_value=newer) as fetch:
            with tools._machine_lock:
                tools._machine.update(facts=FACTS, at=time.monotonic() - tools.MACHINE_TTL_S - 1)
            facts, age = tools.machine_facts(wait=0)
            self.assertEqual(facts['version'], FACTS['version'])
            self.assertGreater(age, tools.MACHINE_TTL_S)
            self.assertTrue(tools._machine['ready'].wait(3))
            facts, age = tools.machine_facts(wait=0)
        self.assertEqual(facts['version'], '44.20261001.1')
        self.assertEqual(fetch.call_count, 1)

    def test_priming_starts_a_reading_without_waiting(self):
        gate = threading.Event()
        with patch.object(tools.moai_tools, 'machine_facts', side_effect=lambda: gate.wait(5) and FACTS) as fetch:
            with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '0'}):
                self.assertFalse(tools.prime_machine_context())
            fetch.assert_not_called()
            with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}):
                started = time.monotonic()
                self.assertTrue(tools.prime_machine_context())
                self.assertLess(time.monotonic() - started, 0.5)
                gate.set()
                self.assertTrue(tools._machine['ready'].wait(3))
                self.assertIn(BLOCK, tools.system_instruction('ar'))
        self.assertEqual(fetch.call_count, 1)

    def test_a_retry_after_a_failed_first_reading_never_waits(self):
        gate = threading.Event()
        calls = []

        def fetch():
            calls.append(1)
            if len(calls) == 1:
                return {'status': 'error', 'error': 'x'}
            gate.wait(5)          # the second reading hangs (a cold /scan)
            return FACTS
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), \
                patch.object(tools.moai_tools, 'machine_facts', side_effect=fetch):
            self.assertEqual(tools.machine_facts(), (None, 0.0))
            self.assertTrue(tools._machine['ready'].wait(3))
            with tools._machine_lock:
                tools._machine['tried'] -= tools.MACHINE_RETRY_S + 1   # a minute later
            started = time.monotonic()
            self.assertEqual(tools.machine_facts(), (None, 0.0))
            self.assertLess(time.monotonic() - started, 0.1, 'a retry must not hold up a voice session')
            self.assertEqual(len(calls), 2, 'the retry did start in the background')
            gate.set()
            self.assertTrue(tools._machine['ready'].wait(3))
            self.assertEqual(tools.machine_facts()[0]['version'], FACTS['version'])

    def test_a_second_caller_waits_for_the_first_reading_in_flight(self):
        gate = threading.Event()

        def slow():
            gate.wait(0.3)
            return FACTS
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), \
                patch.object(tools.moai_tools, 'machine_facts', side_effect=slow):
            self.assertTrue(tools.prime_machine_context())      # Mira's start-up
            facts, _age = tools.machine_facts()                  # the first voice session, right after
        self.assertEqual(facts['version'], FACTS['version'])

    def test_unavailable_is_skipped_and_not_hammered(self):
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), \
                patch.object(tools.moai_tools, 'machine_facts', return_value={'status': 'error', 'error': 'x'}) as fetch:
            first = tools.system_instruction('ar')
            tools._machine['ready'].wait(3)
            second = tools.system_instruction('ar')
        self.assertNotIn(BLOCK, first + second)
        self.assertEqual(fetch.call_count, 1, 'a failed reading is retried after MACHINE_RETRY_S, not every turn')
        with patch.dict(os.environ, {'MIRA_MACHINE_CONTEXT': '1'}), \
                patch.object(tools.moai_tools, 'machine_facts', side_effect=OSError('down')):
            tools._reset_machine_cache()
            self.assertIn('ميرا', tools.system_instruction('ar'))


if __name__ == '__main__':
    unittest.main()
