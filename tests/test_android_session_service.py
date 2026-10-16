#!/usr/bin/env python3
"""One on-demand Android lifetime, and no mutation before confirmed readiness."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("android_session_store", str(ROOT / "system_files/usr/bin/moos-storectl"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
STORE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = STORE
LOADER.exec_module(STORE)


class AndroidSession(unittest.TestCase):
    def controller(self, replies):
        controller = object.__new__(STORE.Controller)
        controller.runner = mock.Mock()
        controller.runner.capture.side_effect = replies
        controller._cancelled = lambda job: False
        return controller

    def test_unit_is_on_demand_and_stops_with_the_graphical_session(self):
        text = (ROOT / "system_files/usr/lib/systemd/user/moos-android-session.service").read_text()
        for line in ("Type=exec", "PartOf=graphical-session.target", "After=graphical-session.target",
                     "ConditionFileIsExecutable=/usr/bin/waydroid", "ConditionEnvironment=WAYLAND_DISPLAY",
                     "ExecStart=/usr/bin/waydroid session start", "ExecStop=/usr/bin/waydroid session stop",
                     "Restart=no", "TimeoutStopSec=20"):
            self.assertIn(line, text)
        self.assertNotIn("[Install]", text)
        self.assertNotIn("WantedBy=", text)
        for build in ("build.sh", "build-arm.sh"):
            self.assertNotRegex((ROOT / "build_files" / build).read_text(), r"enable[^\n]*moos-android-session")

    def test_startup_transient_is_bounded_but_never_treated_as_ready(self):
        ctl = self.controller([STORE.CommandResult(0, output="Session: STOPPED\n"),
                               STORE.CommandResult(1, reason="starting"),
                               STORE.CommandResult(0, output="Session: RUNNING\n")])
        with mock.patch.object(STORE.time, "sleep"):
            ctl._ensure_android_session(object())
        self.assertEqual(ctl.runner.capture.call_count, 3)
        ctl.runner.spawn.assert_called_once_with(
            ["/usr/bin/systemctl", "--user", "start", "moos-android-session.service"])
        ctl.runner.run_cancellable.assert_not_called()

    def test_no_running_response_never_claims_success(self):
        ctl = self.controller([STORE.CommandResult(0, output="Session: STOPPED\n"),
                               STORE.CommandResult(0, output="Session: RUNNING\nSession: STOPPED\n")])
        with mock.patch.object(STORE.time, "sleep"), \
                mock.patch.object(STORE.time, "monotonic", side_effect=[0, 1, 21]):
            with self.assertRaisesRegex(STORE.StoreError, "did not become ready"):
                ctl._ensure_android_session(object())
        ctl.runner.run_cancellable.assert_not_called()

    def test_running_android_does_not_start_another_session(self):
        ctl = self.controller([STORE.CommandResult(0, output="Session: RUNNING\n")])
        ctl._ensure_android_session(object())
        ctl.runner.spawn.assert_not_called()

    def test_file_installs_share_the_store_authority(self):
        text = (ROOT / "system_files/usr/bin/moos-run-foreign").read_text()
        body = text.split("apk_install() {", 1)[1].split("\ncase ", 1)[0]
        self.assertIn('/usr/bin/moos-storectl install-file "$apk"', body)
        self.assertNotIn("waydroid session start", body)
        setup = (ROOT / "system_files/usr/bin/moai-do").read_text()
        self.assertIn("systemctl --user start moos-android-session.service", setup)
        self.assertNotIn("waydroid session start", setup)



if __name__ == "__main__":
    unittest.main(verbosity=2)
