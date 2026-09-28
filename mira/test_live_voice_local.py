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


if __name__ == '__main__':
    unittest.main()
