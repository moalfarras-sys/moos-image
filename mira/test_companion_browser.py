"""Optional Chromium journey over the real private Companion HTTP/SSE owner.

Run with an existing Playwright installation on NODE_PATH and optionally
MIRA_BROWSER_EXECUTABLE. This does not install a browser or use a live account.
No physical phone or phone microphone acceptance follows from browser emulation.
"""
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import threading
import time
import unittest

from test_companion import FakeController, Harness, dispose, pump


class CompanionBrowserTest(unittest.TestCase):
    def test_mobile_audio_route_scope_and_reconnect(self):
        if not shutil.which('node'):
            self.skipTest('optional browser qualification needs an existing Node/Playwright')
        available = subprocess.run(['node', '-e', 'require.resolve("playwright")'],
                                   capture_output=True, timeout=5)
        if available.returncode:
            self.skipTest('optional browser qualification needs Playwright on NODE_PATH')
        controller = FakeController()
        controller._echo['online'] = False
        harness = Harness(controller=controller, posts_per_minute=1000).ready()
        self.addCleanup(dispose, controller)
        self.addCleanup(harness.close)
        process = subprocess.Popen(['node', str(Path(__file__).with_name('companion_browser_test.cjs'))],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        def stop():
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        self.addCleanup(stop)
        process.stdin.write(json.dumps({'origin': harness.origin, 'cookie': harness.store.session_cookie()}) + '\n')
        process.stdin.flush()
        output = queue.Queue()
        def reader():
            for line in process.stdout:
                output.put(line.rstrip())
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        steps = []
        passed = False
        end = time.monotonic() + 45
        while time.monotonic() < end and process.poll() is None:
            pump(timeout=.02)
            try:
                line = output.get_nowait()
            except queue.Empty:
                continue
            if line.startswith('STEP '):
                step = line[5:]
                steps.append(step)
                if step == 'active':
                    self.assertTrue(pump(lambda: any(call[0] == ('talk',) for call in controller.calls)))
                    controller.set_phase('listening')
                elif step == 'busy':
                    self.assertTrue(pump(lambda: any(call[0] == ('stop',) for call in controller.calls)))
                    controller._phase, controller._busy = 'idle', True
                    controller.phaseChanged.emit()
                    controller.busyChanged.emit()
                elif step == 'setup':
                    controller._busy, controller._brain_key = False, 'missing'
                    controller.busyChanged.emit()
                    controller.settingsChanged.emit()
                elif step == 'echo':
                    controller._brain_key, controller._echo['online'] = 'set', True
                    controller.settingsChanged.emit()
                    controller.echoChanged.emit()
                elif step == 'retry':
                    controller._brain_key = 'failed'
                    controller.settingsChanged.emit()
                elif step == 'disconnect':
                    harness.server.close_streams('private-review-reconnect')
                elif step == 'english':
                    controller._lang, controller._echo['online'] = 'en', False
                    controller.langChanged.emit()
                    controller.echoChanged.emit()
                else:
                    self.fail('Unknown private browser step')
                process.stdin.write(json.dumps({'ack': step}) + '\n')
                process.stdin.flush()
            elif line.startswith('MIRA_COMPANION_BROWSER_PASS'):
                passed = True
        self.assertIsNotNone(process.poll(), 'private browser journey timed out')
        thread.join(timeout=1)
        while not output.empty():
            passed = passed or output.get_nowait().startswith('MIRA_COMPANION_BROWSER_PASS')
        self.assertEqual(process.returncode, 0, process.stderr.read())
        self.assertTrue(passed, 'browser did not execute its completed journey marker')
        self.assertEqual(steps, ['active', 'busy', 'setup', 'retry', 'echo', 'disconnect', 'english'])


if __name__ == '__main__':
    unittest.main()
