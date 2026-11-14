"""PC mic ownership and finite meter controls; no microphone, cloud or GUI capture."""
import asyncio
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

import desk_voice as desk
from capture_policy import SourceState


def pcm(value, count=1600):
    return struct.pack('<h', value) * count


class Watch:
    def __init__(self, source, reason='ready'):
        self.source, self.state = source, SourceState(reason, 7)
        self.generation, self.closed, self.recorder = 1, False, None

    def start(self):
        pass

    def wait_ready(self, _timeout):
        return self.state.allowed

    def snapshot(self):
        return self.generation, self.state

    def permits(self, generation):
        return not self.closed and self.state.allowed and generation == self.generation

    def attach_recorder(self, recorder, generation):
        if not self.permits(generation):
            recorder.terminate()
            return False
        self.recorder = recorder
        return True

    def detach_recorder(self, recorder):
        if self.recorder is recorder:
            self.recorder = None

    def revoke(self, reason='muted'):
        self.state, self.generation = SourceState(reason, 7), self.generation + 1
        if self.recorder:
            self.recorder.terminate()

    def close(self):
        self.closed = True


class Reader:
    def __init__(self, data, after_read=None, eof=True):
        self.stream = asyncio.StreamReader()
        self.stream.feed_data(data)
        if eof:
            self.stream.feed_eof()
        self.after_read = after_read

    async def readexactly(self, count):
        data = await self.stream.readexactly(count)
        if self.after_read:
            self.after_read()
        return data


class Process:
    def __init__(self, data=b'', code=0, after_read=None, hold=False):
        self.stdout = Reader(data, after_read, eof=not hold)
        self.returncode = None if hold else code
        self.terminated = self.killed = self.waited = 0
        self.finished = asyncio.Event()

    def terminate(self):
        self.terminated += 1
        self.returncode = -15
        if not self.stdout.stream.at_eof():
            self.stdout.stream.feed_eof()
        self.finished.set()

    def kill(self):
        self.killed += 1
        self.returncode = -9
        self.finished.set()

    async def wait(self):
        self.waited += 1
        if self.returncode is None:
            await self.finished.wait()
        return self.returncode


class Voice:
    def __init__(self, after_audio=None, emit=None):
        self.turn = {'done': False, 'tts': False}
        self.audio_chunks, self.stops = [], []
        self.after_audio, self.emit = after_audio, emit

    async def audio(self, data):
        self.audio_chunks.append(data)
        if self.after_audio:
            self.after_audio(self)

    async def stop(self, abort):
        self.stops.append(abort)
        self.turn['done'] = True
        if self.emit:
            self.emit('ready', 'cancelled by voice owner')

    async def start(self):
        if self.turn is None:
            self.turn = {'done': False, 'tts': False}
        return 0


class SourceSelection(unittest.TestCase):
    def test_default_is_resolved_once_without_writing_any_preference(self):
        with patch.object(desk.subprocess, 'run', return_value=SimpleNamespace(stdout='internal-mic\n')) as run:
            actual = desk.resolve_source(desk.DEFAULT_SOURCE)
        self.assertEqual(actual, 'internal-mic')
        self.assertEqual(run.call_args.args[0], ['pactl', 'get-default-source'])
        self.assertTrue(run.call_args.kwargs['check'])
        command = desk.record_command(actual, 3)
        self.assertIn('--device=internal-mic', command)
        self.assertIn('--raw', command)
        self.assertNotIn('--sample-count', command)
        self.assertIn('--property=node.dont-fallback=true', command)
        self.assertIn('--property=node.dont-reconnect=true', command)

    def test_named_microphone_never_falls_back_to_a_default_or_old_usb_name(self):
        with patch.object(desk.subprocess, 'run') as run:
            self.assertEqual(desk.resolve_source('internal-mic'), 'internal-mic')
        run.assert_not_called()
        for invalid in ('', 'two\nlines', 'name\x00suffix', [], 'x' * 513):
            with self.subTest(invalid=repr(invalid)), self.assertRaises(desk.CaptureError):
                desk.resolve_source(invalid)


class NativePlayback(unittest.TestCase):
    def test_headerless_pcm_uses_raw_and_a_failed_player_is_not_silently_restarted(self):
        self.assertIn('--raw', desk.PLAY)
        api = desk.DeskApi()
        player = Mock()
        player.poll.return_value = None
        player.wait.return_value = 1
        with patch.object(desk.subprocess, 'Popen', return_value=player) as spawn, \
             patch.object(desk.DeskApi, '_write', side_effect=BrokenPipeError('private diagnostic')):
            with self.assertRaisesRegex(RuntimeError, '^computer_playback_failed$'):
                api.send_voice_assistant_audio(pcm(300))
            with self.assertRaisesRegex(RuntimeError, '^computer_playback_failed$'):
                api.send_voice_assistant_audio(pcm(300))
        self.assertEqual(spawn.call_count, 1)
        self.assertEqual(api.bytes_written, 0)
        player.terminate.assert_called_once()
        player.wait.assert_called()

    def test_late_failure_after_all_pcm_writes_is_a_refused_finish(self):
        api = desk.DeskApi()
        player = Mock()
        player.poll.return_value = None
        player.wait.return_value = 7
        with patch.object(desk.subprocess, 'Popen', return_value=player), \
             patch.object(desk.DeskApi, '_write'):
            api.send_voice_assistant_audio(pcm(300))
            with self.assertRaisesRegex(RuntimeError, '^computer_playback_failed$'):
                api.finish()
        self.assertEqual(api.bytes_written, 3200)
        self.assertEqual(api.playback_error, 'computer_playback_failed')
        self.assertIsNone(api.player)
        player.stdin.close.assert_called_once()
        player.wait.assert_called_once_with(timeout=2)

    @unittest.skipUnless(os.name == 'posix', 'native private playback-pipe lifetime control')
    def test_a_stalled_private_player_times_out_and_is_reaped(self):
        command = [sys.executable, '-c', 'import time;time.sleep(30)']
        real_spawn = subprocess.Popen
        processes = []
        def spawn(*_args, **kwargs):
            process = real_spawn(command, **kwargs)
            processes.append(process)
            return process
        api = desk.DeskApi()
        with patch.object(desk.subprocess, 'Popen', side_effect=spawn), \
             patch.object(desk, 'WRITE_TIMEOUT_S', .1):
            with self.assertRaisesRegex(RuntimeError, '^computer_playback_failed$'):
                api.send_voice_assistant_audio(b'\0' * 65536)
        self.assertIsNotNone(processes[0].returncode)
        self.assertEqual(api.bytes_written, 0)
        self.assertEqual(api.playback_error, 'computer_playback_failed')

    @unittest.skipUnless(os.environ.get('MIRA_NATIVE_AUDIO_PROOF') == '1',
                         'opt-in native no-link PipeWire headerless PCM proof')
    def test_real_native_player_old_format_refusal_and_raw_no_link_control(self):
        # Explicit target0 never links to an output. These digital zeros cannot
        # play through an owner's speaker, and the process is always reaped.
        old = [arg for arg in desk.PLAY if arg != '--raw']
        old[1:1] = ['--target', '0']
        refused = subprocess.run(old, input=b'\0' * 3200, capture_output=True, timeout=3)
        self.assertEqual(refused.returncode, 1)
        self.assertIn(b'Format not recognised', refused.stderr)
        fixed = desk.PLAY[:1] + ['--target', '0'] + desk.PLAY[1:]
        process = subprocess.Popen(fixed, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                process.communicate(b'\0' * 3200, timeout=.4)
        finally:
            process.terminate()
            _out, error = process.communicate(timeout=2)
        self.assertNotIn(b'Format not recognised', error)
        self.assertIsNotNone(process.returncode)


class ProbeAndCapture(unittest.IsolatedAsyncioTestCase):
    async def test_meter_counts_only_bounded_pcm_and_distinguishes_silence(self):
        for value, expected in ((700, 'ok'), (0, 'silent')):
            with self.subTest(value=value):
                process = Process(pcm(value, 4800))
                watch = Watch('internal-mic')
                with patch.object(desk, 'SourceWatch', return_value=watch), \
                     patch.object(desk.asyncio, 'create_subprocess_exec', return_value=process) as create:
                    result = await desk._probe_microphone('internal-mic', .3)
                self.assertEqual(result['status'], expected, result)
                self.assertEqual(result['bytes'], 9600)
                self.assertEqual(result['peak'], value)
                self.assertEqual(result['rms'], float(value))
                self.assertEqual(result['source'], 'internal-mic')
                self.assertIn('--device=internal-mic', create.call_args.args)
                self.assertTrue(watch.closed)
                self.assertGreater(process.waited, 0)
                self.assertNotIn('audio', result)

    async def test_muted_missing_unknown_or_monitor_refusal_never_spawns_capture(self):
        for reason in ('muted', 'missing', 'unknown', 'unavailable', 'monitor_refused'):
            with self.subTest(reason=reason):
                watch = Watch('internal-mic', reason)
                with patch.object(desk, 'SourceWatch', return_value=watch), \
                     patch.object(desk.asyncio, 'create_subprocess_exec') as create:
                    result = await desk._probe_microphone('internal-mic', .1)
                self.assertEqual((result['status'], result['reason']), ('error', reason))
                self.assertEqual(result['bytes'], 0)
                self.assertTrue(watch.closed)
                create.assert_not_called()

    async def test_ordinary_failure_and_empty_success_are_both_refused(self):
        for code, reason in ((7, 'capture_failed'), (0, 'no_data')):
            with self.subTest(code=code):
                with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic')), \
                     patch.object(desk.asyncio, 'create_subprocess_exec', return_value=Process(code=code)):
                    result = await desk._probe_microphone('internal-mic', .1)
                self.assertEqual((result['status'], result['reason']), ('error', reason))
                self.assertEqual(result['bytes'], 0)

    async def test_failed_exit_after_all_expected_bytes_does_not_become_success(self):
        for code in (1, 7):
            with self.subTest(code=code):
                with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic')), \
                     patch.object(desk.asyncio, 'create_subprocess_exec', return_value=Process(pcm(300), code=code)):
                    result = await desk._probe_microphone('internal-mic', .1)
                self.assertEqual((result['status'], result['reason']), ('error', 'capture_failed'))
                self.assertEqual(result['bytes'], 3200)

    async def test_finite_meter_owns_its_stop_only_after_the_exact_byte_budget(self):
        class NativeStop(Process):
            def terminate(self):
                self.terminated += 1
                self.returncode = 0      # parec's reviewed SIGTERM handler
                self.finished.set()
        process = NativeStop(pcm(500, 5000), hold=True)
        with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic')), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=process):
            result = await desk._probe_microphone('internal-mic', .3)
        self.assertEqual((result['status'], result['bytes']), ('ok', 9600))
        self.assertEqual(process.terminated, 1)
        self.assertEqual(process.killed, 0)
        self.assertGreater(process.waited, 0)

    async def test_disconnect_before_handoff_discards_the_last_chunk(self):
        watch = Watch('internal-mic')
        process = Process(pcm(600), after_read=lambda: watch.revoke('missing'))
        with patch.object(desk, 'SourceWatch', return_value=watch), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=process):
            result = await desk._probe_microphone('internal-mic', .1)
        self.assertEqual((result['status'], result['reason']), ('error', 'missing'))
        self.assertEqual(result['bytes'], 0)
        self.assertTrue(watch.closed)

    async def test_capture_spawn_failure_or_timeout_remains_an_error(self):
        watch = Watch('internal-mic')
        with patch.object(desk, 'SourceWatch', return_value=watch), \
             patch.object(desk.asyncio, 'create_subprocess_exec', side_effect=OSError()):
            result = await desk._probe_microphone('internal-mic', .1)
        self.assertEqual((result['status'], result['reason']), ('error', 'capture_failed'))
        self.assertTrue(watch.closed)
        process = Process(hold=True)
        with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic')), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=process), \
             patch.object(desk, 'READ_TIMEOUT_S', .01):
            result = await desk._probe_microphone('internal-mic', .1)
        self.assertEqual((result['status'], result['reason']), ('error', 'timeout'))
        self.assertEqual(process.terminated, 1)
        self.assertGreater(process.waited, 0)

    async def test_an_odd_partial_pcm_sample_is_refused(self):
        with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic')), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=Process(b'x')):
            result = await desk._probe_microphone('internal-mic', .1)
        self.assertEqual((result['status'], result['reason']), ('error', 'invalid_audio'))
        self.assertEqual(result['bytes'], 0)

    async def test_generation_cannot_survive_mute_then_unmute(self):
        watch = Watch('internal-mic')
        def change():
            watch.revoke('muted')
            watch.revoke('ready')
        with patch.object(desk, 'SourceWatch', return_value=watch), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=Process(pcm(600), after_read=change)):
            result = await desk._probe_microphone('internal-mic', .1)
        self.assertEqual((result['status'], result['reason']), ('error', 'changed'))
        self.assertEqual(result['bytes'], 0)

    async def test_invalid_duration_never_creates_a_watcher_or_recorder(self):
        for seconds in (False, 0, -1, 6, float('nan'), float('inf'), 1e-10, '3'):
            with self.subTest(seconds=seconds):
                with patch.object(desk, 'SourceWatch') as watch, \
                     patch.object(desk.asyncio, 'create_subprocess_exec') as create:
                    result = await desk._probe_microphone('internal-mic', seconds)
                self.assertEqual(result['reason'], 'invalid_duration')
                watch.assert_not_called()
                create.assert_not_called()

    @unittest.skipUnless(os.name == 'posix', 'native POSIX process lifetime control')
    async def test_cancellation_reaps_a_real_private_stubborn_producer(self):
        # This process produces synthetic bytes, not audio. SIGTERM is ignored
        # to require the same finite kill-and-wait path used by real recorders.
        command = [sys.executable, '-c',
                   'import signal,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                   'sys.stdout.buffer.write(b"x"*3200);sys.stdout.buffer.flush();time.sleep(30)']
        real_create = asyncio.create_subprocess_exec
        created = []
        async def spawn(*_args, **kwargs):
            process = await real_create(*command, **kwargs)
            created.append(process)
            return process
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        watch = Watch('internal-mic')
        executed = asyncio.Event()
        async def run():
            async with desk.MicrophoneCapture('internal-mic') as capture:
                await capture.read()
                executed.set()
                await asyncio.Event().wait()
        try:
            with patch.object(desk, 'SourceWatch', return_value=watch), \
                 patch.object(desk.asyncio, 'create_subprocess_exec', side_effect=spawn), \
                 patch.object(desk, 'READ_TIMEOUT_S', .3):
                task = asyncio.create_task(run())
                await asyncio.wait_for(executed.wait(), 3)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            self.assertEqual(created[0].returncode, -signal.SIGKILL)
            with self.assertRaises(ProcessLookupError):
                os.kill(created[0].pid, 0)
            self.assertTrue(watch.closed)
            self.assertIsNone(unrelated.poll(), 'capture cleanup must not signal another owner')
        finally:
            for process in created:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
            unrelated.terminate()
            unrelated.wait(timeout=2)


class DeskTurn(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.controller = desk.DeskVoice(source='internal-mic')
        self.events = []
        self.controller.voice_state.connect(lambda kind, text: self.events.append((kind, text)))

    def tearDown(self):
        self.controller.shutdown()

    async def test_muted_turn_never_hands_audio_or_announces_ready(self):
        voice = Voice(emit=self.controller._voice_event)
        with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic', 'muted')), \
             patch.object(desk.asyncio, 'create_subprocess_exec') as create:
            await self.controller._listen(voice, voice.turn)
        create.assert_not_called()
        self.assertEqual(voice.audio_chunks, [])
        self.assertEqual(voice.stops, [True])
        self.assertTrue(any(kind == 'error' for kind, _ in self.events))
        self.assertFalse(any(kind == 'ready' for kind, _ in self.events))

    async def test_permission_is_rechecked_immediately_before_voice_audio(self):
        watch = Watch('internal-mic')
        voice = Voice()
        def revoke_after_level(_data):
            watch.revoke('muted')
            return 300
        with patch.object(desk, 'SourceWatch', return_value=watch), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=Process(pcm(300))), \
             patch.object(desk, '_rms', side_effect=revoke_after_level):
            await self.controller._listen(voice, voice.turn)
        self.assertEqual(voice.audio_chunks, [])
        self.assertEqual(voice.stops, [True])

    async def test_half_duplex_drops_input_if_output_started_during_a_read(self):
        voice = Voice()
        process = Process(pcm(300), after_read=lambda: voice.turn.update(tts=True))
        with patch.object(desk, 'SourceWatch', return_value=Watch('internal-mic')), \
             patch.object(desk.asyncio, 'create_subprocess_exec', return_value=process):
            await self.controller._listen(voice, voice.turn)
        self.assertEqual(voice.audio_chunks, [])
        self.assertEqual(voice.stops, [], 'beginning the answer must not cancel it')

    async def test_talk_marks_the_pc_owner_and_async_failure_is_visible(self):
        voice = Voice()
        voice.turn = None
        async def no_input(_voice, _turn, source):
            self.assertEqual(source, 'internal-mic')
        with patch.object(self.controller, '_ensure_voice', return_value=voice), \
             patch.object(self.controller, '_listen', side_effect=no_input):
            await self.controller._talk()
            await self.controller._mic
        self.assertEqual(voice.turn['input_source'], 'pc')
        with patch.object(self.controller, '_ensure_voice', side_effect=RuntimeError('private detail')):
            await self.controller._talk()
        self.assertTrue(any(kind == 'error' for kind, _ in self.events))
        self.assertFalse(any('private detail' in text for _, text in self.events))

    async def test_a_new_turn_waits_for_previous_capture_cleanup(self):
        voice = Voice()
        voice.turn = None
        entered, cleaned = asyncio.Event(), asyncio.Event()
        async def previous():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(.01)
                cleaned.set()
        self.controller._mic = asyncio.create_task(previous())
        await entered.wait()
        async def next_capture(_voice, _turn, source):
            self.assertTrue(cleaned.is_set())
        with patch.object(self.controller, '_ensure_voice', return_value=voice), \
             patch.object(self.controller, '_listen', side_effect=next_capture):
            await self.controller._talk()
            await self.controller._mic
        self.assertTrue(cleaned.is_set())

    async def test_terminal_voice_event_waits_for_capture_cleanup(self):
        entered, cleaning, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def capture():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await finish.wait()
        task = self.controller._mic = asyncio.create_task(capture())
        task.add_done_callback(self.controller._mic_finished)
        await entered.wait()
        self.controller._voice_event('error', 'connection failed')
        self.assertFalse(any(kind == 'error' for kind, _ in self.events))
        task.cancel()
        await cleaning.wait()
        self.assertFalse(any(kind == 'error' for kind, _ in self.events))
        finish.set()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0)
        self.assertEqual(self.events, [('error', 'connection failed')])

    async def test_stop_keeps_old_ready_parked_until_capture_is_reaped(self):
        entered, cleaning, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def capture():
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await finish.wait()
        task = self.controller._mic = asyncio.create_task(capture())
        task.add_done_callback(self.controller._mic_finished)
        self.controller.voice = Voice(emit=self.controller._voice_event)
        await entered.wait()
        with patch.object(desk.asyncio, 'run_coroutine_threadsafe',
                          side_effect=lambda coroutine, _loop: asyncio.create_task(coroutine)):
            stopped = self.controller.stop()
        await cleaning.wait()
        self.controller._voice_event('ready', 'old early ready')
        self.assertFalse(any(kind == 'ready' for kind, _ in self.events))
        finish.set()
        await stopped
        self.assertTrue(task.done())
        self.assertEqual([kind for kind, _ in self.events], ['ready'])
        self.assertNotEqual(self.events[0][1], 'old early ready')

    async def test_playback_failure_is_visible_and_never_counted_as_delivered_reply(self):
        self.controller.api.playback_error = 'computer_playback_failed'
        self.controller.api.bytes_written = 3200
        self.controller._voice_event('stats', json.dumps({'reply_bytes': 3200, 'outcome': 'replied'}))
        stats = json.loads(self.events[-1][1])
        self.assertEqual(stats['reply_bytes'], 0)
        self.assertEqual(stats['playback_bytes_written'], 3200)
        self.assertEqual(stats['outcome'], 'playback_failed')
        with patch.object(self.controller.api, 'finish', side_effect=RuntimeError('private diagnostic')):
            self.controller._voice_event('ready', 'reply complete')
        self.assertEqual(self.events[-1][0], 'error')
        self.assertFalse(any('private diagnostic' in text for _, text in self.events))


if __name__ == '__main__':
    unittest.main(verbosity=2)
