"""Mute/disconnect capture boundaries with private native process recorders."""
import ast
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'mira'))
from capture_policy import SourceState, SourceWatch, inspect_source

# Execute the actual dependency-free helper functions, without importing wake
# training libraries or opening any microphone. CI's Python is sufficient.
fixture = types.ModuleType('wake_policy_fixture')
fixture.__dict__.update({'os': os, 'Path': Path, 'queue': queue,
    'subprocess': subprocess, 'time': time, 'FRAME_BYTES': 3200,
    'WhisperModel': Mock(), 'diagnostic': Mock(), 'send_wake': Mock(),
    'transcribe_wake': Mock()})
sys.modules[fixture.__name__] = fixture
source = ROOT / 'mira/local_wake.py'
tree = ast.parse(source.read_text())
names = {'runtime_root', 'offer_speech', 'recognize_loop', '_capture_loop', 'LazyWhisperModel'}
selected = ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                           and n.name in names], type_ignores=[])
exec(compile(selected, str(source), 'exec'), fixture.__dict__)
for name in names:
    globals()[name] = getattr(fixture, name)


class MicrophonePolicyTest(unittest.TestCase):
    def probe(self, **changes):
        source = {'index': 57, 'name': 'selected-mic', 'mute': False,
                  'monitor_of_sink': 4294967295, 'ports': []}
        source.update(changes)
        result = SimpleNamespace(stdout=json.dumps([source]))
        with patch('capture_policy.subprocess.run', return_value=result) as run:
            state = inspect_source('selected-mic')
        self.assertEqual(run.call_args.args[0], ['pactl', '-f', 'json', 'list', 'sources'])
        return state

    def test_only_a_verified_unmuted_microphone_is_allowed(self):
        self.assertTrue(self.probe().allowed)
        for change, reason in (({'mute': True}, 'muted'), ({'mute': 'false'}, 'unknown'),
                               ({'index': True}, 'unknown'), ({'name': 'other'}, 'missing'),
                               ({'monitor_of_sink': 32}, 'monitor_refused'),
                               ({'active_port': 'jack', 'ports': [{'name': 'jack',
                                  'availability': 'not available'}]}, 'unavailable')):
            with self.subTest(change=change):
                state = self.probe(**change)
                self.assertFalse(state.allowed)
                self.assertEqual(state.reason, reason)

    def test_command_failure_or_ambiguous_data_never_opens_capture(self):
        for raw in ('not json', '{}', '[]', '[{"name":"selected-mic"},{"name":"selected-mic"}]'):
            with patch('capture_policy.subprocess.run', return_value=SimpleNamespace(stdout=raw)):
                self.assertFalse(inspect_source('selected-mic').allowed)
        for error in (OSError(), subprocess.TimeoutExpired('pactl', 3)):
            with patch('capture_policy.subprocess.run', side_effect=error):
                self.assertFalse(inspect_source('selected-mic').allowed)

    def test_default_alias_is_resolved_without_changing_it(self):
        responses = [SimpleNamespace(stdout='named\n'), SimpleNamespace(stdout=json.dumps([
            {'name': 'named', 'index': 9, 'mute': False, 'monitor_of_sink': 4294967295}]))]
        with patch('capture_policy.subprocess.run', side_effect=responses) as run:
            self.assertTrue(inspect_source('@DEFAULT_SOURCE@').allowed)
        self.assertEqual(run.call_args_list[0].args[0], ['pactl', 'get-default-source'])
        self.assertEqual(run.call_count, 2)

    def test_muted_source_does_not_even_spawn_a_recorder(self):
        watch = SourceWatch('selected-mic')
        watch._publish(SourceState('muted', 57))
        with patch('wake_policy_fixture.subprocess.Popen') as spawn:
            _capture_loop(SimpleNamespace(), [], None, None, watch)
        spawn.assert_not_called()

    def test_recording_lease_cannot_survive_a_brief_mute(self):
        watch = SourceWatch('selected-mic')
        watch._publish(SourceState('ready', 57))
        generation, _ = watch.snapshot()
        recorder = Mock()
        self.assertTrue(watch.attach_recorder(recorder, generation))
        watch._publish(SourceState('muted', 57))
        watch._publish(SourceState('ready', 57))
        self.assertFalse(watch.permits(generation))
        recorder.terminate.assert_called()
        late = Mock()
        self.assertFalse(watch.attach_recorder(late, generation))
        late.terminate.assert_called_once()

    def test_completed_recognition_cannot_wake_after_mute_and_unmute(self):
        watch = SourceWatch('selected-mic')
        watch._publish(SourceState('ready', 57))
        generation, _ = watch.snapshot()
        entered, finish, stop = threading.Event(), threading.Event(), threading.Event()
        pending = queue.Queue(maxsize=2)
        offer_speech(pending, b'fixture', generation)
        def decode(*_args):
            entered.set()
            self.assertTrue(finish.wait(2))
            return True
        with patch('wake_policy_fixture.transcribe_wake', side_effect=decode), \
             patch('wake_policy_fixture.send_wake') as wake, patch('wake_policy_fixture.diagnostic'):
            worker = threading.Thread(target=recognize_loop,
                args=(SimpleNamespace(uid=123), None, pending, stop, watch))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                watch._publish(SourceState('muted', 57))
                watch._publish(SourceState('ready', 57))
                finish.set()
                stop.set()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                wake.assert_not_called()
            finally:
                finish.set()
                stop.set()
                worker.join(2)

    def test_wake_model_is_lazy_and_reused(self):
        with patch('wake_policy_fixture.WhisperModel') as create:
            lazy = LazyWhisperModel('/fixture/model')
            create.assert_not_called()
            lazy.transcribe(b'one')
            lazy.transcribe(b'two')
            create.assert_called_once()
            self.assertEqual(create.return_value.transcribe.call_count, 2)

    def test_pcm_and_health_use_a_private_runtime_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {'XDG_RUNTIME_DIR': directory}):
                self.assertEqual(runtime_root(os.getuid()), root)
                root.chmod(0o755)
                with self.assertRaises(ValueError):
                    runtime_root(os.getuid())


class SubscriptionLifetimeTest(unittest.TestCase):
    """Real private child pipes and process teardown; no owner audio or bus."""
    def setUp(self):
        self.current = SourceState('muted', 57)
        self.probe = Mock(side_effect=lambda: self.current)
        self.children = []
        def subscribe():
            process = subprocess.Popen([sys.executable, '-u', '-c',
                'import sys\nfor line in sys.stdin:\n print(line.rstrip(), flush=True)'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            self.children.append(process)
            return process
        self.watch = SourceWatch('selected-mic', probe=self.probe, subscribe=subscribe)
        self.watch.start()
        self.wait(lambda: self.watch.snapshot()[1].reason == 'muted')

    def tearDown(self):
        self.watch.close()
        for process in self.children:
            process.stdin.close()
            self.assertIsNotNone(process.poll())

    def wait(self, condition):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(.01)
        self.fail('private event was not processed')

    def event(self, text):
        self.children[0].stdin.write(text + '\n')
        self.children[0].stdin.flush()

    def test_idle_and_unrelated_events_do_not_poll(self):
        for text in ("Event 'change' on sink #8", "Event 'new' on client #9",
                     "Event 'change' on source #58"):
            self.event(text)
        self.event("Event 'change' on source #57")
        self.wait(lambda: self.probe.call_count >= 2)
        self.assertEqual(self.probe.call_count, 2)

    def test_unmute_resumes_but_mute_stops_a_real_private_child(self):
        self.current = SourceState('ready', 57)
        self.event("Event 'change' on source #57")
        self.assertTrue(self.watch.wait_ready(2))
        generation, _ = self.watch.snapshot()
        recorder = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        try:
            self.assertTrue(self.watch.attach_recorder(recorder, generation))
            self.current = SourceState('muted', 57)
            self.event("Event 'change' on source #57")
            recorder.wait(timeout=3)
            self.assertFalse(self.watch.permits(generation))
        finally:
            if recorder.poll() is None:
                recorder.kill()
                recorder.wait()

    def test_lost_subscription_fails_closed_and_all_children_retire(self):
        self.current = SourceState('ready', 57)
        self.event("Event 'change' on source #57")
        self.assertTrue(self.watch.wait_ready(2))
        generation, _ = self.watch.snapshot()
        self.children[0].terminate()
        self.wait(lambda: not self.watch.permits(generation))
        self.assertFalse(self.watch.snapshot()[1].allowed)


if __name__ == '__main__':
    unittest.main()
