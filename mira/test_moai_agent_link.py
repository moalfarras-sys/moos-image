"""Mira text requests use the existing Mo AI agent and report a direct fallback."""
import json
import unittest
from unittest.mock import patch

import moai_link


class Response:
    def __init__(self, route):
        self.headers = {'X-MoAI-Agent': route}
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, *_):
        return json.dumps({'choices': [{'message': {'content': 'MoOS'}}]}).encode()


class AgentLinkTest(unittest.TestCase):
    def test_browser_uses_real_catalog_and_executor(self):
        with patch('command_router._installed_app', return_value=('com.google.Chrome', 'Chrome')) as catalog, patch.object(moai_link, 'execute', return_value={'status': 'ok'}) as execute:
            result = moai_link.open_application('المتصفح')
        catalog.assert_called_once_with('chrome')
        execute.assert_called_once_with('open_app', {'app_id': 'com.google.Chrome'})
        self.assertEqual(result['status'], 'ok')

    def test_open_failure_is_preserved(self):
        with patch('command_router._installed_app', return_value=('com.google.Chrome', 'Chrome')), patch.object(moai_link, 'execute', return_value={'status': 'error'}):
            self.assertEqual(moai_link.open_application('browser')['status'], 'error')

    def test_invalid_app_name(self):
        for name in ('', None, 'x' * 121):
            with self.assertRaises(ValueError):
                moai_link.open_application(name)

    def test_uses_hermes_session_and_owner_profile(self):
        with patch('mira_memory.profile_text', return_value='أعمل على MoOS'), patch.object(
            moai_link.OPENER, 'open', return_value=Response('hermes')) as open_request:
            self.assertEqual(moai_link.ask('ما مشروعي؟'), 'MoOS')
        request = open_request.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body['moai'], {'agent': True, 'session': 'mira-desktop-owner'})
        self.assertIn('أعمل على MoOS', body['messages'][0]['content'])
        self.assertEqual(body['messages'][-1]['content'], 'ما مشروعي؟')

    def test_direct_fallback_is_not_called_agent_work(self):
        with patch('mira_memory.profile_text', return_value=''), patch.object(
            moai_link.OPENER, 'open', return_value=Response('direct-fallback')):
            self.assertIn('دون أدوات', moai_link.ask('مرحبا'))


if __name__ == '__main__':
    unittest.main()
