"""A local wake must keep the same microphone for the following question."""
import asyncio
import collections
import struct
import unittest
from unittest.mock import patch

from live_voice import LiveVoice


class FakeApi:
    is_connected = False


class FakeReader:
    def __init__(self, frames):
        self.frames = iter(frames)

    async def readexactly(self, count):
        frame = next(self.frames)
        assert len(frame) == count
        return frame


class SlowReader:
    async def readexactly(self, count):
        raise asyncio.TimeoutError()


class FakeWriter:
    def close(self):
        pass

    async def wait_closed(self):
        pass


class LocalVoiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_echo_silence_cannot_end_a_pc_microphone_turn(self):
        voice = LiveVoice(FakeApi(), {}, lambda *_: None)
        turn = {'local_source': 'pc-mic', 'done': False,
                'queue': asyncio.Queue(128)}
        voice.turn = turn
        await voice.stop(False)
        self.assertFalse(turn['done'])
        self.assertTrue(turn['echo_stop_pending'])
        await voice.stop(False, local=True)
        self.assertTrue(turn['done'])

    async def test_echo_mic_is_ignored_during_pc_wake_turn(self):
        events = []
        voice = LiveVoice(FakeApi(), {}, lambda kind, value: events.append(kind))
        turn = {'local_source': 'pc-mic', 'done': False, 'tts': False,
                'input': 0, 'peak': 0, 'queue': asyncio.Queue(128),
                'echo_buffer': collections.deque(maxlen=50)}
        voice.turn = turn
        await voice.audio(struct.pack('<1600h', *([600] * 1600)), None)
        self.assertEqual(turn['input'], 0)
        self.assertTrue(turn['queue'].empty())
        self.assertEqual(len(turn['echo_buffer']), 1)

    async def test_pc_audio_reaches_gemini_queue_and_closes_on_silence(self):
        events = []
        voice = LiveVoice(FakeApi(), {}, lambda kind, value: events.append(kind))
        turn = {'local_source': 'pc-mic', 'done': False, 'tts': False,
                'input': 0, 'peak': 0, 'queue': asyncio.Queue(128),
                'echo_buffer': collections.deque(maxlen=50)}
        voice.turn = turn
        speech = struct.pack('<1600h', *([600] * 1600))
        silence = bytes(3200)
        fake = FakeReader([speech] * 3 + [silence] * 10)
        with patch('asyncio.open_unix_connection', return_value=(fake, FakeWriter())) as create:
            await voice.capture_local(turn, 'pc-mic')
        self.assertIn('mira-pcm.sock', create.call_args.args[0])
        self.assertTrue(turn['done'])
        self.assertEqual(turn['input'], 13 * 3200)
        self.assertEqual(turn['peak'], 600)
        queued = [turn['queue'].get_nowait() for _ in range(turn['queue'].qsize())]
        self.assertEqual(len(queued), 14)
        self.assertIsNone(queued[-1])
        self.assertNotEqual(queued[0], silence)
        self.assertIn('thinking', events)

    async def test_slow_pc_source_falls_back_to_buffered_echo_audio(self):
        events = []
        voice = LiveVoice(FakeApi(), {}, lambda kind, value: events.append((kind,value)))
        echo = struct.pack('<1600h', *([500] * 1600))
        turn = {'local_source': 'pc-mic', 'done': False, 'tts': False,
                'input': 0, 'peak': 0, 'queue': asyncio.Queue(128),
                'echo_buffer': collections.deque([echo], maxlen=50),
                'input_source': 'pc_pending', 'echo_stop_pending': True}
        voice.turn = turn
        with patch('asyncio.open_unix_connection', return_value=(SlowReader(), FakeWriter())):
            await voice.capture_local(turn, 'pc-mic')
        self.assertIsNone(turn['local_source'])
        self.assertEqual(turn['input_source'], 'echo_fallback')
        self.assertEqual(turn['input'], len(echo))
        self.assertTrue(turn['done'])
        self.assertTrue(any(kind == 'listening' and 'Echo' in value for kind,value in events))



# ─── Gemini Live session, resampler and Echo stream (all offline fakes) ──
import contextlib
import json
import math
from array import array
from types import SimpleNamespace

from google.genai import errors, types

import live_voice
import tools


def server_message(**content):
    return types.LiveServerMessage(server_content=types.LiveServerContent(**content))


def audio_message(pcm, rate=24000):
    return server_message(model_turn=types.Content(role='model', parts=[types.Part(
        inline_data=types.Blob(data=pcm, mime_type=f'audio/pcm;rate={rate}'))]))


def tone(freq, seconds, rate=24000, amp=8000):
    return array('h', [int(amp * math.sin(2 * math.pi * freq * i / rate))
                       for i in range(int(seconds * rate))]).tobytes()


class FakeServer:
    """Scripted Gemini Live: reacts to end-of-input and tool responses."""

    def __init__(self):
        self.connects = []
        self.sessions = []
        self.refuse_advanced = False
        self.fail = None
        self.on_end = self.answer
        self.handle = None

    def answer(self, session):
        if self.handle:
            session.push(types.LiveServerMessage(session_resumption_update=types.LiveServerSessionResumptionUpdate(
                new_handle=self.handle, resumable=True)))
        session.push(server_message(input_transcription=types.Transcription(text='كم ')))
        session.push(server_message(input_transcription=types.Transcription(text='الساعة؟')))
        session.push(server_message(output_transcription=types.Transcription(text='الساعة ')))
        session.push(audio_message(tone(440, 0.06)))
        session.push(server_message(output_transcription=types.Transcription(text='الثامنة.')))
        session.push(audio_message(tone(440, 0.04)))
        session.push(server_message(turn_complete=True))

    def on_tool_response(self, session, responses):
        session.push(audio_message(tone(440, 0.05)))
        session.push(server_message(output_transcription=types.Transcription(text='تم.')))
        session.push(server_message(turn_complete=True))


class FakeSession:
    def __init__(self, server):
        self.server = server
        self.queue = asyncio.Queue()
        self.sent = []
        self.closed = False

    def push(self, message):
        self.queue.put_nowait(message)

    async def send_client_content(self, turns=None, turn_complete=True):
        self.sent.append(('content', turns, turn_complete))
        if turn_complete and turns and isinstance(turns, dict):
            self.server.on_end(self)

    async def send_realtime_input(self, audio=None, audio_stream_end=None, text=None):
        if audio is not None:
            self.sent.append(('audio', len(audio.data)))
        if text is not None:
            self.sent.append(('text', text))
            self.server.on_end(self)
        if audio_stream_end:
            self.sent.append(('end',))
            self.server.on_end(self)

    async def send_tool_response(self, function_responses):
        self.sent.append(('tool_response', function_responses))
        self.server.on_tool_response(self, function_responses)

    async def receive(self):
        while True:
            message = await self.queue.get()
            if message is None:
                raise ConnectionError('closed by server')
            yield message
            if message.server_content and message.server_content.turn_complete:
                return


class FakeClient:
    def __init__(self, server):
        self.server = server

        @contextlib.asynccontextmanager
        async def connect(model, config):
            server.connects.append(config)
            if server.fail:
                raise server.fail
            if server.refuse_advanced and 'session_resumption' in config:
                raise errors.APIError(1007, {'error': {'code': 1007, 'message': 'invalid argument'}})
            session = FakeSession(server)
            server.sessions.append(session)
            try:
                yield session
            finally:
                session.closed = True

        async def aclose():
            pass
        self.aio = SimpleNamespace(live=SimpleNamespace(connect=connect), aclose=aclose)


class FakeEcho:
    is_connected = True

    def __init__(self):
        self.events = []
        self.audio = []

    def send_voice_assistant_event(self, kind, data):
        self.events.append(kind.name.replace('VOICE_ASSISTANT_', ''))

    def send_voice_assistant_audio(self, data):
        self.audio.append(bytes(data))


class LiveSessionTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = FakeServer()
        self.echo = FakeEcho()
        self.events = []
        self.voice = LiveVoice(self.echo, {}, lambda kind, text: self.events.append((kind, text)))
        self.voice._load_config = lambda: {'api_key': 'test-key-not-real', 'model': 'fake-live'}
        self.voice._make_client = lambda config: FakeClient(self.server)
        self.patches = [patch.object(tools, 'conversation_turns', return_value=[
                            {'role': 'user', 'parts': [{'text': 'مرحبا'}]}]),
                        patch.object(tools, 'system_instruction', return_value='test persona'),
                        patch.object(live_voice, 'NO_REPLY_S', 0.3)]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in self.patches:
            item.stop()
        self.voice._cancel_idle()
        if self.voice.link:
            await self.voice.link.close()

    async def turn(self, chunks=3):
        self.assertEqual(await self.voice.start('conversation', 0, None, None), 0)
        t = self.voice.turn
        for _ in range(chunks):
            await self.voice.audio(struct.pack('<512h', *([300] * 512)), None)
        await self.voice.stop(False)
        await asyncio.wait_for(t['task'], 5)
        return t, dict(self.voice.last_stats)

    def kinds(self):
        return [kind for kind, _ in self.events]

    async def test_follow_up_reuses_one_session(self):
        t, first = await self.turn()
        self.assertEqual(len(self.server.connects), 1)
        setup = self.server.connects[0]
        self.assertEqual(setup['session_resumption'], {})
        self.assertIn('sliding_window', setup['context_window_compression'])
        self.assertEqual(setup['history_config'], {'initial_history_in_client_content': True})
        self.assertEqual(setup['tools'][0]['function_declarations'][0]['behavior'], 'BLOCKING')
        session = self.server.sessions[0]
        self.assertEqual(session.sent[0][0], 'content')
        self.assertIs(session.sent[0][2], True, 'initial history ends with turn_complete')
        self.assertEqual((first['session'], first['outcome'], first['error']), ('fresh', 'replied', None))
        for key in ('connect_ms', 'first_audio_ms', 'turn_ms', 'first_audio_since_start_ms'):
            self.assertIsInstance(first[key], int, key)
        self.assertEqual(first['heard'], 'كم الساعة؟')
        self.assertEqual(first['reply'], 'الساعة الثامنة.')
        self.assertEqual(first['microphone_bytes'], 3 * 1024)
        self.assertEqual(first['microphone_peak'], 300)
        # Echo stream: 16 kHz S16LE (0.1 s of 24 kHz -> 3200 bytes), 512-byte blocks, one short tail.
        self.assertEqual(sum(map(len, self.echo.audio)), first['reply_bytes'])
        self.assertAlmostEqual(first['reply_bytes'], 3200, delta=4)
        self.assertTrue(all(len(b) == 512 for b in self.echo.audio[:-1]))
        self.assertTrue(all(len(b) % 2 == 0 for b in self.echo.audio))
        self.assertEqual(self.echo.events, ['RUN_START', 'STT_START', 'STT_END', 'TTS_START', 'TTS_STREAM_START',
                                            'TTS_START', 'TTS_STREAM_END', 'RUN_END'])
        for kind in ('activating', 'listening', 'partial_heard', 'partial_reply', 'speaking', 'ready', 'heard',
                     'reply', 'stats', 'session'):
            self.assertIn(kind, self.kinds())
        self.assertIn(('partial_heard', 'كم'), self.events)
        self.assertEqual(self.voice.turn, None)

        self.events.clear()
        t2, second = await self.turn()
        self.assertEqual(len(self.server.connects), 1, 'follow-up reuses the open session')
        self.assertEqual(second['session'], 'reused')
        self.assertEqual([s[0] for s in session.sent].count('content'), 1, 'history is sent once')
        self.assertLess(second['connect_ms'], first['connect_ms'] + 50)

    async def test_idle_session_closes_and_next_turn_starts_fresh(self):
        self.server.handle = 'handle-1'
        with patch.object(live_voice, 'IDLE_CLOSE_S', 0.05):
            await self.turn()
            await asyncio.sleep(0.2)
            self.assertIsNone(self.voice.link)
            self.assertTrue(self.server.sessions[0].closed)
            self.assertIn(('session', json.dumps({'state': 'closed', 'reason': 'idle'})), self.events)
            _, stats = await self.turn()
        self.assertEqual(len(self.server.connects), 2)
        self.assertEqual(stats['session'], 'fresh', 'an idle-closed conversation is not resumed')
        self.assertEqual(self.server.connects[1]['session_resumption'], {})

    async def test_cut_turn_is_resumed_with_its_handle(self):
        self.server.handle = 'handle-7'
        original = self.server.answer

        def half_answer(session):
            session.push(types.LiveServerMessage(session_resumption_update=types.LiveServerSessionResumptionUpdate(
                new_handle='handle-7', resumable=True)))
            session.push(audio_message(tone(440, 0.5)))   # no turn_complete: the owner aborts
        self.server.on_end = half_answer
        self.assertEqual(await self.voice.start('c', 0, None, None), 0)
        t = self.voice.turn
        await self.voice.stop(False)
        for _ in range(100):
            if t['tts']:
                break
            await asyncio.sleep(0.01)
        await self.voice.stop(True)
        await asyncio.wait_for(t['task'], 5)
        self.assertEqual(t['error'], 'cancelled')
        self.assertTrue(self.voice.link.dirty)
        self.assertIn('ERROR', self.echo.events)
        self.server.on_end = original
        _, stats = await self.turn()
        self.assertEqual(stats['session'], 'resumed')
        self.assertEqual(self.server.connects[1]['session_resumption'], {'handle': 'handle-7'})
        self.assertNotIn('history_config', self.server.connects[1])
        self.assertNotIn('content', [s[0] for s in self.server.sessions[1].sent], 'no history re-send on resume')

    async def test_dead_socket_is_replaced_not_waited_on(self):
        await self.turn()

        class DeadSocket:
            async def ping(self):
                raise ConnectionError('gone')
        self.voice.link.session._ws = DeadSocket()
        _, stats = await self.turn()
        self.assertEqual(len(self.server.connects), 2)
        self.assertEqual(stats['session'], 'fresh')

    async def test_setup_failure_sets_readiness_and_reports(self):
        def broken():
            raise FileNotFoundError('/home/x/.config/mo-dot/gemini.json')
        self.voice._load_config = broken
        started = asyncio.get_running_loop().time()
        self.assertIsNone(await self.voice.start('c', 0, None, None))
        self.assertLess(asyncio.get_running_loop().time() - started, 1.0)
        self.assertIn(('error', 'تعذّر الصوت: FileNotFoundError'), self.events)
        self.assertIsNone(self.voice.turn)
        self.assertNotIn('RUN_START', self.echo.events)

    async def test_connect_failure_ends_turn_with_class_name_only(self):
        self.server.fail = OSError('wss://generativelanguage.googleapis.com/ws?key=AIzaSECRET')
        t, stats = await self.turn()
        self.assertEqual(stats['error'], 'OSError')
        self.assertIn('ERROR', self.echo.events)
        self.assertNotIn('SECRET', json.dumps(self.events, ensure_ascii=False))

    async def test_refused_advanced_setup_falls_back_to_plain_once(self):
        self.server.refuse_advanced = True
        _, stats = await self.turn()
        self.assertEqual(stats['session_features'], 'plain')
        self.assertFalse(self.voice._advanced)
        plain = self.server.connects[-1]
        self.assertNotIn('session_resumption', plain)
        self.assertNotIn('behavior', plain['tools'][0]['function_declarations'][0])
        self.assertIs(self.server.sessions[0].sent[0][2], False, 'plain mode seeds history inline')
        self.voice.link.dirty = True
        await self.turn()
        self.assertNotIn('session_resumption', self.server.connects[-1], 'no repeated refused attempt')

    async def test_barge_in_drops_queued_reply(self):
        def interrupted_answer(session):
            session.push(audio_message(tone(440, 2.0)))
            session.push(server_message(interrupted=True))
            session.push(server_message(turn_complete=True))
            session.push(audio_message(tone(440, 0.05)))
            session.push(server_message(turn_complete=True))
        self.server.on_end = interrupted_answer
        _, stats = await self.turn()
        self.assertEqual(stats['interrupted'], 1)
        self.assertGreater(stats.get('interrupted_dropped_bytes', 0), 30000)
        self.assertLess(stats['reply_bytes'], 32000, 'the two queued seconds were not played')
        self.assertIn('interrupted', self.kinds())
        self.assertEqual(stats['outcome'], 'replied')

    async def test_tool_call_runs_through_registry(self):
        def tool_answer(session):
            session.push(types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[
                types.FunctionCall(id='t1', name='current_time', args={})])))
        self.server.on_end = tool_answer
        _, stats = await self.turn()
        responses = [s[1] for s in self.server.sessions[0].sent if s[0] == 'tool_response'][0]
        self.assertEqual((responses[0].id, responses[0].name), ('t1', 'current_time'))
        self.assertEqual(responses[0].response['status'], 'ok')
        self.assertEqual(stats['tools'], [{'name': 'current_time', 'status': 'ok'}])
        tool_events = [json.loads(text) for kind, text in self.events if kind == 'tool']
        self.assertEqual(tool_events[0]['name'], 'current_time')
        self.assertIn('executing', self.kinds())
        self.assertEqual(stats['outcome'], 'replied')

    async def test_slow_tool_does_not_count_as_a_silent_server(self):
        def tool_answer(session):
            session.push(types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[
                types.FunctionCall(id='t9', name='current_time', args={})])))
        self.server.on_end = tool_answer
        answer_tool = self.server.on_tool_response
        # A real server needs a moment after the tool result; answer after 0.1 s.
        self.server.on_tool_response = lambda session, responses: asyncio.get_running_loop().call_later(
            0.1, answer_tool, session, responses)
        real = tools.run_tool

        async def slow_tool(name, args, ctx):
            await asyncio.sleep(0.5)
            return await real(name, args, ctx)
        with patch.object(live_voice, 'STALL_S', 0.2), patch.object(tools, 'run_tool', slow_tool):
            _, stats = await self.turn()
        self.assertEqual((stats['outcome'], stats['error']), ('replied', None))

    async def test_a_tool_gets_the_language_that_was_heard(self):
        seen = []

        async def spy(name, args, ctx):
            seen.append(ctx.lang)
            return {'status': 'ok', 'summary': 'x', 'summary_en': 'x'}

        def speak(heard):
            def answer(session):
                session.push(server_message(input_transcription=types.Transcription(text=heard)))
                session.push(types.LiveServerMessage(tool_call=types.LiveServerToolCall(function_calls=[
                    types.FunctionCall(id='t1', name='research', args={'question': 'weather'})])))
            return answer
        with patch.object(tools, 'run_tool', side_effect=spy):
            for heard, window in (('what is the weather', 'ar'), ('كيف الطقس', 'en'), ('', 'en')):
                self.voice.lang = window
                self.server.on_end = speak(heard)
                await self.turn()
        self.assertEqual(seen, ['en', 'ar', 'en'])

    async def test_a_new_chat_starts_the_next_turn_fresh(self):
        self.server.handle = 'handle-1'
        await self.turn()
        first = self.voice.link
        self.assertIsNotNone(first)
        self.assertTrue(self.voice.history)
        self.voice.forget_context()            # on the voice loop: applied at once
        self.assertIsNone(self.voice.link)
        self.assertEqual(self.voice.history, [])
        self.assertTrue(first.dirty and first.idle_closed)
        self.assertIsNone(first.resume_handle)
        self.assertIn(('session', json.dumps({'state': 'closed', 'reason': 'new_chat'})), self.events)
        _, stats = await self.turn()
        self.assertEqual(len(self.server.connects), 2)
        self.assertEqual(stats['session'], 'fresh', 'a forgotten conversation is neither reused nor resumed')
        self.assertEqual(self.server.connects[1]['session_resumption'], {})
        self.assertEqual(self.server.sessions[1].sent[0][0], 'content', 'the new session is seeded with the open chat')
        await asyncio.sleep(0.05)
        self.assertTrue(self.server.sessions[0].closed)

    async def test_forget_context_from_the_qt_thread_is_scheduled_on_the_voice_loop(self):
        import threading
        await self.turn()
        link = self.voice.link
        worker = threading.Thread(target=self.voice.forget_context)
        worker.start()
        worker.join()
        self.assertIs(self.voice.link, link, 'nothing was changed from the other thread')
        for _ in range(20):
            if self.voice.link is None:
                break
            await asyncio.sleep(0.01)
        self.assertIsNone(self.voice.link)
        self.assertFalse(self.voice._forget_pending)
        _, stats = await self.turn()
        self.assertEqual(stats['session'], 'fresh')

    async def test_forget_before_the_loop_is_known_applies_at_the_next_turn(self):
        await self.turn()
        link = self.voice.link
        self.voice._loop = None                 # e.g. created off the loop and never started
        self.voice.forget_context()
        self.assertIs(self.voice.link, link)
        self.assertTrue(self.voice._forget_pending)
        _, stats = await self.turn()
        self.assertEqual(stats['session'], 'fresh')
        self.assertFalse(self.voice._forget_pending)
        self.assertTrue(link.dirty and link.idle_closed)

    async def test_a_turn_already_speaking_finishes_but_joins_no_new_chat(self):
        release = asyncio.Event()
        original = self.server.answer

        def slow_answer(session):
            async def later():
                await release.wait()
                original(session)
            asyncio.get_running_loop().create_task(later())
        self.server.on_end = slow_answer
        self.assertEqual(await self.voice.start('c', 0, None, None), 0)
        t = self.voice.turn
        await self.voice.audio(struct.pack('<512h', *([300] * 512)), None)
        await self.voice.stop(False)
        for _ in range(100):
            if t.get('link') is not None:
                break
            await asyncio.sleep(0.01)
        self.voice.forget_context()             # the owner opens a new chat mid-answer
        link = t['link']
        self.assertIs(self.voice.link, link, 'the answer in flight keeps its session')
        self.assertTrue(link.dirty and link.idle_closed)
        release.set()
        await asyncio.wait_for(t['task'], 5)
        self.assertEqual(t['reply'], 'الساعة الثامنة.')
        self.assertEqual(self.voice.history, [], 'the old conversation does not follow into the new chat')
        self.server.on_end = original
        _, stats = await self.turn()
        self.assertEqual(stats['session'], 'fresh')

    async def test_silence_ends_without_error_and_without_hanging(self):
        self.server.on_end = lambda session: None
        _, stats = await self.turn()
        self.assertEqual((stats['outcome'], stats['error']), ('no_reply', None))
        self.assertEqual(stats['notice'], 'لم أسمع سؤالاً واضحاً')
        self.assertEqual(self.echo.events[-1], 'RUN_END')
        self.assertNotIn('ERROR', self.echo.events)
        self.assertEqual(self.kinds().count('error'), 0)
        self.assertIn('ready', self.kinds())
        self.assertFalse(self.voice.link.dirty, 'nothing pending on the server: keep the session')

    async def test_heard_without_answer_ends_and_replaces_session(self):
        self.server.on_end = lambda session: session.push(
            server_message(input_transcription=types.Transcription(text='شغلي الضوء')))
        with patch.object(live_voice, 'REPLY_WAIT_S', 0.3):
            _, stats = await self.turn()
        self.assertEqual((stats['outcome'], stats['error']), ('no_reply', None))
        self.assertIn('لم يصل رد', stats['notice'])
        self.assertTrue(self.voice.link.dirty, 'a late answer must not leak into the next turn')

    async def test_session_with_vad_signals_ends_a_silent_follow_up_quickly(self):
        def vad_only(session):
            session.push(types.LiveServerMessage(voice_activity=types.VoiceActivity(voice_activity_type='ACTIVITY_END')))
        self.server.on_end = vad_only
        with patch.object(live_voice, 'NO_REPLY_S', 5.0), patch.object(live_voice, 'NO_SPEECH_S', 0.1):
            started = asyncio.get_running_loop().time()
            _, stats = await self.turn()
        self.assertLess(asyncio.get_running_loop().time() - started, 2.0)
        self.assertEqual(stats['outcome'], 'no_reply')

    async def deaf_second_turn(self, stop_early):
        """Turn 1 is normal and reports VAD; on the reused session turn 2 is ignored."""
        self.server.handle = 'handle-9'
        original = self.server.answer

        def with_vad(session):
            session.push(types.LiveServerMessage(voice_activity=types.VoiceActivity(voice_activity_type='ACTIVITY_START')))
            session.push(types.LiveServerMessage(voice_activity=types.VoiceActivity(voice_activity_type='ACTIVITY_END')))
            original(session)
        self.server.on_end = with_vad
        await self.turn()
        self.assertTrue(self.voice._vad_supported)
        deaf = self.server.sessions[0]
        self.server.on_end = lambda session: None if session is deaf else with_vad(session)
        loud = struct.pack('<512h', *([3000] * 512))
        self.assertEqual(await self.voice.start('c', 0, None, None), 0)
        t = self.voice.turn
        for _ in range(60):                     # 1.9 s of loud "speech"
            await self.voice.audio(loud, None)
        if not stop_early:
            await asyncio.sleep(0.05)
            await self.voice.stop(False)
        else:
            for _ in range(100):                # the open mic alone must trigger the switch
                if t.get('retried'):
                    break
                await asyncio.sleep(0.02)
            self.assertTrue(t.get('retried'), 'switched while the mic was still open')
            await self.voice.stop(False)
        await asyncio.wait_for(t['task'], 5)
        return dict(self.voice.last_stats)

    async def test_deaf_reused_session_is_replaced_and_audio_replayed(self):
        with patch.object(live_voice, 'NO_REPLY_S', 5.0), patch.object(live_voice, 'NO_SPEECH_S', 0.2), \
                patch.object(live_voice, 'DEAF_TICK_S', 0.05):
            stats = await self.deaf_second_turn(stop_early=False)
        self.assertEqual((stats['deaf_retry'], stats['session'], stats['outcome'], stats['error']),
                         ('reused', 'resumed', 'replied', None))
        self.assertEqual(self.server.connects[1]['session_resumption'], {'handle': 'handle-9'})
        replayed = sum(item[1] for item in self.server.sessions[1].sent if item[0] == 'audio')
        self.assertEqual(replayed, 60 * 1024, 'the whole turn was replayed to the new session')
        self.assertEqual(stats['heard'], 'كم الساعة؟')

    async def test_deaf_session_is_detected_while_the_mic_is_open(self):
        with patch.object(live_voice, 'DEAF_TICK_S', 0.05), patch.object(live_voice, 'DEAF_LOUD_S', 1.5):
            stats = await self.deaf_second_turn(stop_early=True)
        self.assertEqual((stats['deaf_retry'], stats['outcome']), ('reused', 'replied'))

    async def test_levels_follow_playback_at_about_15_per_second(self):
        def long_answer(session):
            session.push(audio_message(tone(440, 0.6)))
            session.push(server_message(turn_complete=True))
        self.server.on_end = long_answer
        await self.turn(chunks=0)
        levels = [float(text) for kind, text in self.events if kind == 'level']
        self.assertGreaterEqual(len(levels), 5)
        self.assertLessEqual(len(levels), int(0.6 / live_voice.LEVEL_INTERVAL_S) + 3)
        self.assertEqual(levels[-1], 0.0)
        self.assertGreater(max(levels), 0.3)


class WakeWordTest(unittest.IsolatedAsyncioTestCase):
    def api(self, active, available):
        calls = []
        words = [SimpleNamespace(id=w, wake_word=w.title()) for w in available]

        class Api:
            is_connected = True

            async def get_voice_assistant_configuration(self, timeout, offers=None):
                calls.append(('get', offers))
                return SimpleNamespace(active_wake_words=list(active), available_wake_words=words,
                                       max_active_wake_words=2)

            async def set_voice_assistant_configuration(self, ids):
                calls.append(('set', ids))
                active[:] = ids

            def subscribe_voice_assistant(self, **handlers):
                calls.append(('subscribe', sorted(handlers)))
                return lambda: None
        return Api(), calls

    async def test_active_wake_words_are_never_changed(self):
        api, calls = self.api(['alexa', 'mira_ar_experimental'], ['alexa', 'mira_ar_experimental', 'okay_nabu'])
        events = []
        voice = LiveVoice(api, {}, lambda k, v: events.append((k, v)))
        await voice.enable()
        self.assertNotIn('set', [c[0] for c in calls])
        self.assertTrue(all(c[1] is None for c in calls if c[0] == 'get'), 'no wake model offered')
        self.assertEqual(voice.wake_hint, 'Alexa / Mira_Ar_Experimental')
        self.assertEqual(events[-1][0], 'ready')

    async def test_empty_selection_restores_mira_only(self):
        # The owner wants Echo to wake for Mira only (2026-09-29): a repair never brings Alexa back.
        active = []
        api, calls = self.api(active, ['alexa', 'hey_mira', 'mira_ar_experimental'])
        await LiveVoice(api, {}, lambda *_: None).enable()
        self.assertIn(('set', ['mira_ar_experimental']), calls)
        self.assertFalse(any(c[0] == 'set' and 'alexa' in (c[1] or []) for c in calls))


class AudioPathTest(unittest.TestCase):
    def rms(self, data, skip=200):
        values = array('h')
        values.frombytes(data)
        values = values[skip:-skip]
        return math.sqrt(sum(v * v for v in values) / len(values))

    def check(self, use_numpy):
        for freq, low, high in ((1000, -0.5, 0.5), (10000, -200, -30)):
            source = tone(freq, 1.0, amp=10000)
            resampler = live_voice.Resampler(24000, 16000, use_numpy=use_numpy)
            out = b''.join(resampler.process(source[i:i + 4801]) for i in range(0, len(source), 4801))
            self.assertAlmostEqual(len(out) / len(source), 2 / 3, places=3)
            gain = 20 * math.log10(max(self.rms(out), 1e-9) / (10000 / math.sqrt(2)))
            self.assertTrue(low <= gain <= high, (use_numpy, freq, gain))

    def test_resampler_numpy(self):
        if live_voice.np is None:
            self.skipTest('numpy not installed')
        self.check(True)

    def test_resampler_pure_python(self):
        self.check(False)

    def test_chunking_is_seamless_and_paths_agree(self):
        source = tone(1234, 0.3)
        whole = live_voice.Resampler(use_numpy=False).process(source)
        for use_numpy in ((False, True) if live_voice.np is not None else (False,)):
            stream = live_voice.Resampler(use_numpy=use_numpy)
            chunked = b''.join(stream.process(source[i:i + 777]) for i in range(0, len(source), 777))
            self.assertEqual(whole, chunked, use_numpy)   # odd-byte chunks included
        self.assertEqual(live_voice.Resampler(16000, 16000).process(b'\x01\x02'), b'\x01\x02')
        self.assertEqual(live_voice._mime_rate('audio/pcm;rate=24000'), 24000)
        self.assertEqual(live_voice._mime_rate('audio/pcm'), 24000)

    def test_gain_is_vectorised_and_clipped(self):
        data = struct.pack('<5h', 100, -100, 9000, -9000, -32768)
        expected = struct.pack('<5h', 400, -400, 32767, -32768, -32768)
        self.assertEqual(live_voice.amplify(data, 4), expected)
        saved = live_voice.np
        try:
            live_voice.np = None
            self.assertEqual(live_voice.amplify(data, 4), expected)
            self.assertEqual(live_voice.pcm_peak(data), 32768)
        finally:
            live_voice.np = saved
        self.assertEqual(live_voice.pcm_peak(data), 32768)


if __name__ == '__main__':
    unittest.main()


class CaptureModeTest(unittest.TestCase):
    """Voice enrolment: an armed window is recorded locally and never reaches Gemini."""

    def test_armed_window_is_recorded_to_a_private_wav(self):
        import asyncio, os, stat, tempfile, wave, json as _json
        import live_voice

        class Entity:
            def __init__(self, key):
                self.key = key
                self.device_id = 0

        class Api:
            is_connected = True
            def __init__(self):
                self.switches, self.events = [], []
            def switch_command(self, key, state, device_id=0):
                self.switches.append(state)
            def send_voice_assistant_event(self, kind, data):
                self.events.append(kind)

        events = []
        api = Api()
        voice = live_voice.LiveVoice(api, {'microphone_end_of_speech': Entity(7)}, lambda k, t: events.append((k, t)))
        folder = tempfile.mkdtemp()
        target = os.path.join(folder, 'enrol', 'mira-1.wav')

        async def scenario():
            voice.arm_capture(target, max_s=2.0)
            self.assertEqual(api.switches, [False])       # the whole window is kept
            with unittest.mock.patch.object(live_voice.LiveVoice, '_acquire', side_effect=AssertionError('no Gemini')):
                self.assertEqual(await voice.start(), 0)
                chunk = (b'\x00\x10' * 1600)                # 0.1 s at 16 kHz
                for _ in range(25):                          # 2.5 s offered, 2.0 s kept
                    await voice.audio(chunk)
                await voice.stop(False)
        asyncio.run(scenario())
        with wave.open(target) as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (16000, 1, 2))
            self.assertEqual(w.getnframes(), 32000)
        self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o600)
        self.assertEqual(api.switches[-1], True)            # end-of-speech restored
        capture = [_json.loads(t) for k, t in events if k == 'capture'][0]
        self.assertEqual((capture['status'], capture['seconds']), ('ok', 2.0))
        self.assertIsNone(voice.turn)

    def test_stale_arming_does_not_capture_a_real_conversation(self):
        import live_voice
        voice = live_voice.LiveVoice(type('A', (), {'is_connected': False})(), {}, lambda *a: None)
        voice.arm_capture('/nonexistent/x.wav')
        voice.capture['armed_at'] -= live_voice.CAPTURE_ARM_S + 1
        spec, voice.capture = voice.capture, None
        import time
        self.assertGreater(time.monotonic() - spec['armed_at'], live_voice.CAPTURE_ARM_S)
