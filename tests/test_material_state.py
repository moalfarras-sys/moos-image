#!/usr/bin/env python3
"""Executable material protocol and event-policy regression tests; no desktop bus."""
import importlib.machinery
import importlib.util
from pathlib import Path
import os
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "system_files/usr/libexec/moos-material-state"
loader = importlib.machinery.SourceFileLoader("material_state", str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class MaterialStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.publisher = module.Publisher(self.temp.name)
        self.jobs = {}
        self.serial = 0
        self.answer = True
        self.probes = 0
        def probe():
            self.probes += 1
            if isinstance(self.answer, Exception):
                raise self.answer
            return self.answer
        def schedule(delay, callback):
            self.serial += 1
            self.jobs[self.serial] = (delay, callback)
            return self.serial
        self.state = module.State(self.publisher, probe, schedule, lambda key: self.jobs.pop(key))
        self.addCleanup(self.state.close)

    def names(self):
        return {p.name for p in self.publisher.directory.iterdir()}

    def tick(self):
        key = min(self.jobs)
        return self.jobs.pop(key)[1]()

    def test_startup_is_private_and_off(self):
        self.assertEqual(self.names(), {"blur-off"})
        self.assertEqual(self.publisher.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(self.probes, 0)

    def test_event_debounce_and_one_finite_retry(self):
        for _ in range(20):
            self.state.changed()
        self.assertEqual(len(self.jobs), 1)
        self.assertFalse(self.tick())
        self.assertEqual(self.names(), {"blur-on"})
        self.assertEqual(len(self.jobs), 1)
        self.assertFalse(self.tick())
        self.assertEqual(self.probes, 2)
        self.assertFalse(self.jobs, "no recurring poll may remain")

    def test_event_immediately_invalidates_previous_on(self):
        self.publisher.publish(True)
        self.state.changed()
        self.assertEqual(self.names(), {"blur-off"})

    def test_failure_unknown_and_false_are_off(self):
        for answer in (False, None, "true", 1, RuntimeError("bus lost")):
            self.answer = answer
            self.state.refresh(False)
            self.assertEqual(self.names(), {"blur-off"})

    def test_reload_race_second_probe_corrects_result(self):
        self.state.changed()
        self.tick()
        self.answer = False
        self.tick()
        self.assertEqual(self.names(), {"blur-off"})

    def test_close_removes_markers_and_cancels_events(self):
        self.state.changed()
        self.state.close()
        self.assertEqual(self.names(), set())
        self.assertFalse(self.jobs)
        self.state.changed()
        self.state.refresh()
        self.assertEqual(self.names(), set())

    def test_symlink_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as runtime:
            (Path(runtime) / "moos-material").symlink_to(self.publisher.directory)
            with self.assertRaises(RuntimeError):
                module.Publisher(runtime)

    def test_symlink_marker_is_not_followed(self):
        target = Path(self.temp.name) / "private"
        target.write_text("untouched")
        (self.publisher.directory / "blur-on").symlink_to(target)
        with self.assertRaises(OSError):
            self.publisher.publish(True)
        self.assertEqual(target.read_text(), "untouched")


if __name__ == "__main__":
    unittest.main()
