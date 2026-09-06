#!/usr/bin/env python3
"""Reject the live ARM regression: a timer without its refresh service."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("arm_gate", REPO / "build_files/verify_arm_image.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class AppStreamImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        old_root = gate.ROOT
        self.addCleanup(setattr, gate, "ROOT", old_root)
        gate.ROOT = self.root
        units = self.root / "usr/lib/systemd/system"
        units.mkdir(parents=True)
        self.service = units / "moos-appstream-refresh.service"
        shutil.copyfile(REPO / "build_files/moos-appstream-refresh.service", self.service)
        timer = units / "moos-appstream-refresh.timer"
        shutil.copyfile(REPO / "system_files/usr/lib/systemd/system" / timer.name, timer)
        self.link = self.root / "etc/systemd/system/timers.target.wants" / timer.name
        self.link.parent.mkdir(parents=True)
        self.link.symlink_to(os.path.relpath(timer, self.link.parent))
        self.executable = self.root / "usr/bin/appstreamcli"
        self.executable.parent.mkdir(parents=True)
        self.executable.write_text("#!/bin/sh\nexit 0\n")
        self.executable.chmod(0o755)

    def test_shipped_units_and_resolved_enable_link_pass(self):
        gate.verify_appstream_refresh()

    def test_missing_service_fails_even_when_timer_is_enabled(self):
        self.service.unlink()
        with self.assertRaisesRegex(SystemExit, "missing required file"):
            gate.verify_appstream_refresh()

    def test_dangling_enable_link_fails(self):
        self.link.unlink()
        self.link.symlink_to("missing.timer")
        with self.assertRaisesRegex(SystemExit, "dangling"):
            gate.verify_appstream_refresh()

    def test_missing_command_fails(self):
        self.executable.unlink()
        with self.assertRaisesRegex(SystemExit, "executable is missing"):
            gate.verify_appstream_refresh()

    def test_disabled_timer_fails(self):
        self.link.unlink()
        with self.assertRaisesRegex(SystemExit, "disabled"):
            gate.verify_appstream_refresh()


if __name__ == "__main__":
    unittest.main()
