"""Private event/parser/process controls; never start the host's pactl."""
import os
import sys
import time
import unittest

from PySide6.QtCore import QCoreApplication, QProcess

from audio_devices import AudioDeviceObserver, EventLines, is_device_event

APP = QCoreApplication.instance() or QCoreApplication([])


def pump(predicate=lambda: False, seconds=1.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        APP.processEvents()
        if predicate():
            return True
        time.sleep(.005)
    return predicate()


class EventParserTest(unittest.TestCase):
    def test_only_bounded_device_events_are_accepted(self):
        for action in ('new', 'change', 'remove'):
            for facility in ('source', 'sink', 'card', 'server'):
                self.assertTrue(is_device_event(f"Event '{action}' on {facility} #4294967295\n".encode()))
        for line in (b"Event 'change' on source-output #3\n", b"Event 'new' on sink-input #8\n",
                     b"Event 'change' on client #8\n", b"Event 'new' on source #3",
                     b"Event 'change' on source #4294967296\n", b"Event 'change' on source #-1\n",
                     b"Event 'destroy' on source #3\n", b"Event 'change' on source #3\nextra",
                     b"Event 'change' on source #3\x00\n", b' ' * 129, 'not bytes'):
            with self.subTest(line=line):
                self.assertFalse(is_device_event(line))

    def test_partial_events_wait_for_newline_and_oversized_lines_rearm_safely(self):
        parser = EventLines()
        self.assertFalse(parser.feed(b"Event 'change' on sou"))
        self.assertFalse(parser.feed(b'rce #3'))
        self.assertTrue(parser.feed(b'\n'))
        self.assertFalse(parser.feed(b'x' * 100000))
        self.assertLessEqual(len(parser.pending), 128)
        self.assertFalse(parser.feed(b"Event 'new' on source #3\n"), 'suffix of a rejected line is not an event')
        self.assertTrue(parser.feed(b"Event 'new' on source #3\r\n"))


class NativeObserverTest(unittest.TestCase):
    def setUp(self):
        self.observer = AudioDeviceObserver()
        self.changed, self.failed, self.stopped = [], [], []
        self.observer.changed.connect(lambda: self.changed.append(True))
        self.observer.failed.connect(lambda: self.failed.append(True))
        self.observer.stopped.connect(lambda: self.stopped.append(True))
        self.addCleanup(self.observer.close)

    def start_private(self, *, stubborn=False, exit_code=None):
        process = QProcess(self.observer)
        process.setProgram(sys.executable)
        code = 'import os, signal, sys\n'
        if stubborn:
            code += 'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
        code += 'os.write(1, b"private-ready\\n")\n'
        if exit_code is None:
            code += 'while True:\n data = os.read(0, 4096)\n if not data: break\n os.write(1, data)\n'
        else:
            code += 'sys.exit(' + str(exit_code) + ')\n'
        process.setArguments(['-u', '-c', code])
        self.observer._make_process = lambda: process
        self.observer.start()
        if exit_code is None:
            ready = bytearray()
            feed = self.observer._lines.feed

            def startup(data):
                ready.extend(data)
                return feed(data)
            self.observer._lines.feed = startup
            self.assertTrue(pump(lambda: process.state() == QProcess.Running))
            # Acknowledge the Python handler is installed before testing SIGTERM.
            self.assertTrue(pump(lambda: b'private-ready\n' in ready))
            self.observer._lines.feed = feed
        return process

    def test_native_process_debounces_events_and_ignores_streams_partial_lines(self):
        process = self.start_private()
        process.write(b"Event 'new' on source-output #3\nEvent 'change' on sink-input #4\n")
        process.write(b"Event 'change' on source #3")
        pump(seconds=.25)
        self.assertEqual(self.changed, [])
        process.write(b"\nEvent 'new' on card #2\nEvent 'change' on server #0\n")
        self.assertTrue(pump(lambda: len(self.changed) == 1))
        pump(seconds=.25)
        self.assertEqual(len(self.changed), 1)
        self.assertEqual(self.failed, [])
        old = self.observer._process
        self.observer.start()
        self.assertIs(self.observer._process, old, 'start is idempotent')

    def test_async_stop_reaps_owned_process_and_cancels_pending_change(self):
        process = self.start_private()
        pid = process.processId()
        process.write(b"Event 'remove' on source #3\n")
        started = time.monotonic()
        self.observer.stop()
        self.assertLess(time.monotonic() - started, .1)
        self.assertTrue(pump(lambda: bool(self.stopped)))
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        pump(seconds=.25)
        self.assertEqual(self.changed, [])
        self.assertEqual(self.failed, [])

    def test_async_stop_kills_a_private_process_that_ignores_terminate(self):
        process = self.start_private(stubborn=True)
        pid = process.processId()
        self.observer._kill_timer.setInterval(40)
        self.observer.stop()
        self.assertTrue(pump(lambda: bool(self.stopped)))
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(self.failed, [])

    def test_final_close_reaps_stubborn_process_without_gui_event_pumping(self):
        process = self.start_private(stubborn=True)
        pid = process.processId()
        started = time.monotonic()
        self.assertTrue(self.observer.close())
        self.assertLess(time.monotonic() - started, 1.6)
        self.assertIsNone(self.observer._process)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_unexpected_successful_exit_is_failed_not_a_healthy_subscription(self):
        self.start_private(exit_code=0)
        self.assertTrue(pump(lambda: bool(self.stopped)))
        self.assertEqual(self.failed, [True])
        self.assertEqual(self.changed, [])
        pump(seconds=.25)
        self.assertIsNone(self.observer._process, 'no automatic restart/polling')

    def test_failed_start_stops_without_raw_error_or_periodic_retry(self):
        process = QProcess(self.observer)
        process.setProgram('/not/a/real/audio-observer-command')
        self.observer._make_process = lambda: process
        self.observer.start()
        self.assertTrue(pump(lambda: bool(self.stopped)))
        self.assertEqual(self.failed, [True])
        self.assertEqual(self.changed, [])
        self.assertIsNone(self.observer._process)

    def test_previous_process_receipts_cannot_retire_an_explicit_restart(self):
        previous = self.start_private()
        self.observer.stop()
        self.assertTrue(pump(lambda: bool(self.stopped)))
        current = self.start_private()
        self.observer._finished(previous, 1, QProcess.CrashExit)
        self.observer._error(previous, QProcess.Crashed)
        self.assertIs(self.observer._process, current)
        self.assertEqual(current.state(), QProcess.Running)
        self.assertEqual(self.failed, [])

    def test_production_command_is_read_only_native_subscribe_with_fixed_locale(self):
        process = self.observer._make_process()
        self.assertEqual(process.program(), '/usr/bin/pactl')
        self.assertEqual(process.arguments(), ['subscribe'])
        self.assertEqual(process.processEnvironment().value('LC_ALL'), 'C')
        self.assertEqual(process.state(), QProcess.NotRunning, 'inspection never starts native pactl')


if __name__ == '__main__':
    unittest.main()
