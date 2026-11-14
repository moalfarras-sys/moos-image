"""Offline first-key and Live setup controls; never read an owner's saved key."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from google.genai import errors, types

import live_voice
from api_credentials import normalize_api_key


class ApiCredentialTest(unittest.TestCase):
    def test_opaque_aq_and_legacy_keys_keep_exact_punctuation(self):
        for key in ('AQ.FAKE_FOR_TESTS_ONLY$not-a-real-secret+/=:', 'AIza' + 'x' * 35,
                    ''.join(chr(point) for point in range(33, 127)), 'x', 'x' * 4096):
            with self.subTest(length=len(key)):
                self.assertEqual(normalize_api_key(key), key)
                self.assertEqual(normalize_api_key(' \t\r\n' + key + '\t\n '), key)

    def test_no_prefix_rule_accepts_internal_whitespace_or_control_bytes(self):
        for key in (None, True, 12, {}, [], b'not-a-string', '', ' \n\t', 'x' * 4097,
                    'AQ.fake key', 'AQ.fake\tkey', 'AQ.fake\nkey', 'AQ.fake\rkey',
                    'AQ.fake\x00key', 'AQ.fake\x1fkey', 'AQ.fake\x7fkey', 'AQ.fake\u00a0key',
                    'AQ.fake\u200bkey', 'AQ.fak\u00e9key'):
            with self.subTest(kind=type(key).__name__):
                with self.assertRaises(ValueError) as caught:
                    normalize_api_key(key)
                self.assertEqual(str(caught.exception), 'API key is missing or has an invalid format')


class ConfigFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'gemini.json'
        self.key = 'AQ.FAKE_FOR_TESTS_ONLY$not-a-real-secret+/=:'

    def save(self, config):
        self.path.write_text(json.dumps(config))


class LiveConfigTest(ConfigFixture):
    def test_actual_first_save_fails_old_owner_but_fixed_voice_loads(self):
        self.save({'api_key': self.key})  # saveGeminiKey's first-save document
        original = self.path.read_bytes()
        config = json.loads(original)
        # Original _load_config predicate, retained as the refusal control.
        with self.assertRaises(ValueError):
            if not isinstance(config, dict) or not config.get('api_key') or not config.get('model'):
                raise ValueError('gemini.json needs api_key and model')
        with patch.object(live_voice, 'GEMINI_CONFIG', self.path):
            config = live_voice.LiveVoice._load_config(None)
        self.assertEqual(config['model'], live_voice.DEFAULT_LIVE_MODEL)
        self.assertEqual(config['api_key'], self.key)
        self.assertEqual(self.path.read_bytes(), original)

    def test_explicit_model_and_typed_choice_are_preserved(self):
        config = {'api_key': self.key, 'model': 'models/personal-live-002',
                  'text_model': 'my-typed-model', 'personal': True}
        self.save(config)
        self.assertEqual(live_voice.read_live_config(self.path), config)

    def test_aq_key_save_round_trip_preserves_bytes_without_prefix_guessing(self):
        self.save({'api_key': self.key})
        original = self.path.read_bytes()
        # The old save/load regex rejects this valid opaque credential shape.
        self.assertIsNone(__import__('re').fullmatch(r'[A-Za-z0-9_-]{20,200}', self.key))
        self.assertEqual(live_voice.read_live_config(self.path)['api_key'], self.key)
        self.assertEqual(self.path.read_bytes(), original)
        for key in ('AIza' + 'x' * 35, 'x', 'x' * 4096, 'opaque"key\\with$punctuation+/=:'):
            with self.subTest(length=len(key)):
                self.save({'api_key': ' \n' + key + '\t '})
                self.assertEqual(live_voice.read_live_config(self.path)['api_key'], key)

    def test_reviewed_live_choices_do_not_change_default_or_explicit_choice(self):
        expected = (live_voice.DEFAULT_LIVE_MODEL, 'gemini-2.5-flash-native-audio-preview-12-2025')
        self.assertEqual(tuple(choice['id'] for choice in live_voice.LIVE_MODEL_CHOICES), expected)
        for choice in live_voice.LIVE_MODEL_CHOICES:
            self.assertTrue(choice['free_tier'])
            self.assertIsInstance(choice['label'], str)
            self.save({'api_key': self.key, 'model': choice['id']})
            self.assertEqual(live_voice.read_live_config(self.path)['model'], choice['id'])

    def test_malformed_types_and_explicit_invalid_model_are_refused(self):
        for config in ([], True, None, {}, {'api_key': True}, {'api_key': []},
                       {'api_key': ''}, {'api_key': 'x' * 4097}, {'api_key': 'AQ.fake key'},
                       {'api_key': self.key, 'model': None},
                       {'api_key': self.key, 'model': 12},
                       {'api_key': self.key, 'model': ''},
                       {'api_key': self.key, 'model': 'a' * 161},
                       {'api_key': self.key, 'model': '../secret'},
                       {'api_key': self.key, 'model': 'model?key=' + self.key}):
            with self.subTest(config=config):
                self.save(config)
                with self.assertRaises(ValueError) as caught:
                    live_voice.read_live_config(self.path)
                self.assertNotIn(self.key, str(caught.exception))
                with patch.object(live_voice.genai, 'Client') as client:
                    result = live_voice.probe_live_connection(path=self.path)
                client.assert_not_called()
                self.assertEqual(result['reason'], 'config')
                self.assertNotIn(self.key, json.dumps(result))

    def test_missing_malformed_and_oversized_files_are_refused(self):
        for raw in (None, b'{bad-json', b'\xff', b' ' * 16385, b'[' * 2000 + b']' * 2000):
            with self.subTest(raw_size=None if raw is None else len(raw)):
                if raw is not None:
                    self.path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    live_voice.read_live_config(self.path)


class FakeConnection:
    def __init__(self, failure=None, delay=0):
        self.failure = failure
        self.delay = delay
        self.opened = False
        self.exited = False
        self.cancelled = False
        self.session = SimpleNamespace(send_client_content=AsyncMock(),
                                       send_realtime_input=AsyncMock(),
                                       send_tool_response=AsyncMock(),
                                       receive=Mock(), setup_complete=types.LiveServerSetupComplete())

    async def __aenter__(self):
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.failure:
                raise self.failure
            self.opened = True
            return self.session
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def __aexit__(self, *_):
        self.exited = True


class LiveProbeTest(ConfigFixture):
    def run_probe(self, connection, timeout_s=1):
        self.save({'api_key': self.key})
        client = SimpleNamespace(aio=SimpleNamespace(
            live=SimpleNamespace(connect=Mock(return_value=connection)), aclose=AsyncMock()))
        with patch.object(live_voice.genai, 'Client', return_value=client) as factory, \
                patch('asyncio.create_subprocess_exec', side_effect=AssertionError('no recorder')):
            result = live_voice.probe_live_connection(timeout_s, self.path)
        factory.assert_called_once_with(api_key=self.key)
        client.aio.live.connect.assert_called_once_with(
            model=live_voice.DEFAULT_LIVE_MODEL, config={'response_modalities': ['AUDIO']})
        client.aio.aclose.assert_awaited_once()
        connection.session.send_client_content.assert_not_called()
        connection.session.send_realtime_input.assert_not_called()
        connection.session.send_tool_response.assert_not_called()
        connection.session.receive.assert_not_called()
        self.assertNotIn(self.key, json.dumps(result))
        self.assertIsInstance(result['elapsed_ms'], int)
        return result

    def test_opens_and_closes_minimal_setup_without_user_content(self):
        connection = FakeConnection()
        result = self.run_probe(connection)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(connection.opened)
        self.assertTrue(connection.exited)

    def test_timeout_cancels_setup_and_disposes_client(self):
        connection = FakeConnection(delay=10)
        result = self.run_probe(connection, timeout_s=.01)
        self.assertEqual(result['reason'], 'timeout')
        self.assertTrue(connection.cancelled)
        self.assertFalse(connection.opened)
        self.assertLess(result['elapsed_ms'], 1500)

    def test_a_context_without_native_setup_receipt_is_refused_and_closed(self):
        for receipt in (None, True, {}):
            with self.subTest(receipt=receipt):
                connection = FakeConnection()
                connection.session.setup_complete = receipt
                result = self.run_probe(connection)
                self.assertEqual(result['reason'], 'request')
                self.assertTrue(connection.exited)

    def test_auth_quota_server_and_request_refusals_never_echo_error(self):
        for code, reason in ((403, 'auth'), (401, 'auth'), (429, 'quota'),
                             (503, 'server'), (400, 'request')):
            with self.subTest(code=code):
                failure = errors.ClientError(code, {'error': {'message': self.key,
                                                               'status': 'REFUSED'}})
                result = self.run_probe(FakeConnection(failure=failure))
                self.assertEqual(result['reason'], reason)

    def test_native_sdk_websocket_policy_wrapping_is_classified(self):
        for text, reason in (('API key not valid. ' + self.key, 'auth'),
                             ('Quota exceeded. ' + self.key, 'quota'),
                             ('Model not supported. ' + self.key, 'request')):
            with self.subTest(reason=reason):
                result = self.run_probe(FakeConnection(failure=errors.APIError(1008, text)))
                self.assertEqual(result['reason'], reason)

    def test_transport_and_unknown_failures_are_not_false_success(self):
        for error, reason in ((OSError(self.key), 'network'),
                              (TimeoutError(self.key), 'timeout'),
                              (RuntimeError(self.key), 'unknown')):
            with self.subTest(reason=reason):
                result = self.run_probe(FakeConnection(failure=error))
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['reason'], reason)

    def test_client_constructor_failure_is_classified_without_echoing_key(self):
        self.save({'api_key': self.key})
        with patch.object(live_voice.genai, 'Client', side_effect=RuntimeError(self.key)):
            result = live_voice.probe_live_connection(path=self.path)
        self.assertEqual(result['reason'], 'unknown')
        self.assertNotIn(self.key, json.dumps(result))

    def test_sdk_disposal_failure_cannot_turn_refused_setup_into_success(self):
        self.save({'api_key': self.key})
        connection = FakeConnection(failure=errors.ClientError(403, {'message': self.key}))
        client = SimpleNamespace(aio=SimpleNamespace(
            live=SimpleNamespace(connect=Mock(return_value=connection)),
            aclose=AsyncMock(side_effect=OSError(self.key))))
        with patch.object(live_voice.genai, 'Client', return_value=client):
            result = live_voice.probe_live_connection(path=self.path)
        self.assertEqual(result['reason'], 'auth')
        self.assertNotIn(self.key, json.dumps(result))

    def test_called_on_async_loop_refuses_without_leaking_coroutines(self):
        self.save({'api_key': self.key})

        async def run():
            with patch.object(live_voice.genai, 'Client') as client:
                result = live_voice.probe_live_connection(path=self.path)
            client.assert_not_called()
            return result
        self.assertEqual(asyncio.run(run())['reason'], 'unknown')

    def test_invalid_timeouts_do_not_connect(self):
        self.save({'api_key': self.key})
        for timeout in (None, True, 0, -1, float('inf'), float('nan'), 61, '12'):
            with self.subTest(timeout=timeout), patch.object(live_voice.genai, 'Client') as client:
                result = live_voice.probe_live_connection(timeout, self.path)
                self.assertEqual(result['reason'], 'config')
                client.assert_not_called()


class LiveConfigSessionTest(unittest.IsolatedAsyncioTestCase):
    """Use the existing executed Live lifecycle fixture, not a predicate-only mock."""
    async def asyncSetUp(self):
        import test_live_voice_local as fixture
        self.fixture = fixture
        await fixture.LiveSessionTest.asyncSetUp(self)
        self.config = {'api_key': 'AQ.FAKE_FOR_TESTS_ONLY$original', 'model': 'fake-live'}
        self.voice._load_config = lambda: dict(self.config)
        self.created_configs = []

        def create(config):
            self.created_configs.append(dict(config))
            return fixture.FakeClient(self.server)
        self.voice._make_client = create

    async def asyncTearDown(self):
        await self.fixture.LiveSessionTest.asyncTearDown(self)
        if self.voice._closing:
            await asyncio.gather(*self.voice._closing, return_exceptions=True)

    async def turn(self):
        return await self.fixture.LiveSessionTest.turn(self)

    async def test_key_or_model_change_replaces_live_link_and_discards_old_resume_handle(self):
        for change in ({'model': 'review-new-model'}, {'api_key': 'AQ.FAKE_FOR_TESTS_ONLY$new-key'}):
            with self.subTest(field=next(iter(change))):
                self.server.handle = 'old-context-must-not-cross-configuration'
                await self.turn()
                previous = self.voice.link
                self.assertTrue(previous.resume_handle)
                previous_config = dict(self.config)
                self.config.update(change)
                _, stats = await self.turn()
                self.assertIsNot(self.voice.link, previous)
                self.assertEqual(stats['session'], 'fresh')
                self.assertIsNone(previous.resume_handle)
                self.assertTrue(previous.idle_closed)
                self.assertEqual(self.server.connects[-1]['session_resumption'], {})
                self.assertEqual(self.created_configs[-1], self.config)
                self.assertEqual(self.voice.link.model, self.config['model'])
                self.assertNotIn(previous_config['api_key'], repr(self.voice.link.config_identity))
                self.assertNotIn(self.config['api_key'], json.dumps(self.events))

    async def test_same_connection_config_keeps_live_reuse_even_when_typed_metadata_changes(self):
        await self.turn()
        previous = self.voice.link
        self.config.update(text_model='different-typed-choice', personal={'keep': True})
        _, stats = await self.turn()
        self.assertIs(self.voice.link, previous)
        self.assertEqual(stats['session'], 'reused')
        self.assertEqual(len(self.created_configs), 1)

    async def test_changed_config_retries_advanced_setup_without_prior_models_refusal(self):
        self.server.refuse_advanced = True
        await self.turn()
        self.assertFalse(self.voice._advanced)
        previous = self.voice.link
        self.server.refuse_advanced = False
        self.config['model'] = 'review-new-model'
        _, stats = await self.turn()
        self.assertIsNot(self.voice.link, previous)
        self.assertEqual(stats['session'], 'fresh')
        self.assertTrue(self.voice._advanced)
        self.assertIn('session_resumption', self.server.connects[-1])


if __name__ == '__main__':
    unittest.main()
