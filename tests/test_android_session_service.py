#!/usr/bin/env python3
"""One on-demand Android lifetime, and no mutation before confirmed readiness."""
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader("android_session_store", str(ROOT / "system_files/usr/bin/moos-storectl"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
STORE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = STORE
LOADER.exec_module(STORE)
POLICY_LOADER = importlib.machinery.SourceFileLoader(
    "android_edition_policy", str(ROOT / "build_files/android_session_policy.py"))
POLICY_SPEC = importlib.util.spec_from_loader(POLICY_LOADER.name, POLICY_LOADER)
POLICY = importlib.util.module_from_spec(POLICY_SPEC)
POLICY_LOADER.exec_module(POLICY)


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
                               STORE.CommandResult(0, output="Session: RUNNING\n"),
                               STORE.CommandResult(0, output="packageName: org.example.App\n")])
        with mock.patch.object(STORE.time, "sleep"):
            ctl._ensure_android_session(mock.Mock())
        self.assertEqual(ctl.runner.capture.call_count, 4)
        ctl.runner.spawn.assert_called_once_with(
            ["/usr/bin/systemctl", "--user", "start", "moos-android-session.service"])
        ctl.runner.run_cancellable.assert_not_called()

    def test_no_running_response_never_claims_success(self):
        ctl = self.controller([STORE.CommandResult(0, output="Session: STOPPED\n"),
                               STORE.CommandResult(0, output="Session: RUNNING\nSession: STOPPED\n")])
        with mock.patch.object(STORE.time, "sleep"), \
                mock.patch.object(STORE.time, "monotonic", side_effect=[0, 1, 100]):
            with self.assertRaisesRegex(STORE.StoreError, "did not become ready") as refused:
                ctl._ensure_android_session(mock.Mock())
        self.assertEqual(refused.exception.message_key, "android_start_timeout")
        ctl.runner.run_cancellable.assert_not_called()

    def test_running_android_does_not_start_another_session(self):
        ctl = self.controller([STORE.CommandResult(0, output="Session: RUNNING\n"),
                               STORE.CommandResult(0, output="packageName: org.example.App\n")])
        ctl._ensure_android_session(mock.Mock())
        ctl.runner.spawn.assert_not_called()

    def test_file_installs_share_the_store_authority(self):
        text = (ROOT / "system_files/usr/bin/moos-run-foreign").read_text()
        body = text.split("apk_install() {", 1)[1].split("\ncase ", 1)[0]
        self.assertIn('/usr/bin/moos-storectl install-file "$apk"', body)
        self.assertNotIn("waydroid session start", body)
        setup = (ROOT / "system_files/usr/bin/moai-do").read_text()
        self.assertIn("systemctl --user start moos-android-session.service", setup)
        self.assertNotIn("waydroid session start", setup)


class EditionClosure(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="moos-android-edition-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.unit = self.root / POLICY.UNIT
        self.unit.parent.mkdir(parents=True)
        self.unit.write_bytes((ROOT / "system_files" / POLICY.UNIT).read_bytes())
        self.provider = self.root / POLICY.PROVIDER

    def add_provider(self):
        self.provider.parent.mkdir(parents=True, exist_ok=True)
        self.provider.write_text("#!/bin/sh\nexit 0\n")
        self.provider.chmod(0o755)

    def test_old_shared_overlay_is_rejected_on_both_unsupported_editions(self):
        for edition in ("moos-cloud", "moos-arm"):
            with self.subTest(edition=edition):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "build_files/android_session_policy.py"),
                     "verify", "--root", str(self.root), "--edition", edition],
                    capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("GATE FAIL: Android edition closure", result.stderr)

    def test_composition_retires_only_the_unsupported_unit(self):
        other = self.unit.with_name("moos-owner-fixture.service")
        other.write_text("retained\n")
        for edition in ("moos-cloud", "moos-arm"):
            self.unit.write_bytes((ROOT / "system_files" / POLICY.UNIT).read_bytes())
            POLICY.compose(self.root, edition)
            POLICY.verify(self.root, edition)
            self.assertFalse(self.unit.exists())
            self.assertEqual(other.read_text(), "retained\n")

    def test_both_desktop_editions_keep_the_direct_unit_unchanged(self):
        self.add_provider()
        before = self.unit.read_bytes()
        for edition in ("moos", "moos-nvidia"):
            POLICY.compose(self.root, edition)
            POLICY.verify(self.root, edition)
            self.assertEqual(before, self.unit.read_bytes())

    def test_missing_provider_still_refuses_a_desktop_image(self):
        for edition in ("moos", "moos-nvidia"):
            with self.subTest(edition=edition), self.assertRaises(ValueError):
                POLICY.compose(self.root, edition)
        self.assertTrue(self.unit.is_file())

    def test_nonexecutable_provider_is_not_a_runtime(self):
        self.add_provider()
        self.provider.chmod(0o644)
        with self.assertRaises(ValueError):
            POLICY.verify(self.root, "moos")

    def test_a_provider_must_not_silently_expand_an_unsupported_edition(self):
        self.add_provider()
        for edition in ("moos-cloud", "moos-arm"):
            with self.subTest(edition=edition), self.assertRaises(ValueError):
                POLICY.compose(self.root, edition)
        self.assertTrue(self.unit.is_file())
        self.assertTrue(self.provider.is_file())

    def test_a_supported_provider_without_its_unit_is_refused(self):
        self.add_provider()
        self.unit.unlink()
        with self.assertRaises(ValueError):
            POLICY.verify(self.root, "moos-nvidia")

    def test_the_finished_tree_gate_rejects_a_reintroduced_unsupported_unit(self):
        POLICY.compose(self.root, "moos-cloud")
        self.unit.write_bytes((ROOT / "system_files" / POLICY.UNIT).read_bytes())
        with self.assertRaises(ValueError):
            POLICY.verify(self.root, "moos-cloud")

    def test_dangling_and_supported_global_wants_are_both_refused(self):
        wants = self.root / "etc/systemd/user/graphical-session.target.wants"
        wants.mkdir(parents=True)
        (wants / self.unit.name).symlink_to("/usr/lib/systemd/user/" + self.unit.name)
        with self.assertRaises(ValueError):
            POLICY.verify(self.root, "moos-cloud")
        self.add_provider()
        with self.assertRaises(ValueError):
            POLICY.verify(self.root, "moos")

    def test_a_wrapper_cannot_hide_a_missing_direct_provider(self):
        self.add_provider()
        self.unit.write_text(self.unit.read_text().replace(
            "ExecStart=/usr/bin/waydroid session start", "ExecStart=/usr/bin/true"))
        with self.assertRaises(ValueError):
            POLICY.verify(self.root, "moos")

    def test_both_builds_compose_and_recheck_the_actual_final_tree(self):
        for name in ("build.sh", "build-arm.sh"):
            text = (ROOT / "build_files" / name).read_text()
            compose = 'python3 /ctx/android_session_policy.py compose --edition "$MOOS_EDITION"'
            verify = 'python3 /ctx/android_session_policy.py verify --edition "$MOOS_EDITION"'
            self.assertIn(compose, text)
            self.assertIn(verify, text)
            self.assertLess(text.index(compose), text.index(verify))
            self.assertGreater(text.index(verify), text.rindex("dnf5 clean all"))



if __name__ == "__main__":
    unittest.main(verbosity=2)
