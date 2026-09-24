#!/usr/bin/env python3
"""Gate: Wave W5 — Living Island privacy indicators and Store background jobs.

Verifies:
  1. moos-privacy-monitor daemon parses PipeWire state and drops atomic tokens.
  2. moos-privacy-stop kills active streams safely.
  3. moos-open declares privacy/stop route.
  4. org.moos.island enforces strict priority: Remote > Privacy > Store Jobs > Media.
  5. Island multi-context tabs switch between active domains cleanly.
"""

from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ISLAND_QML = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui/main.qml"
PRIVACY_MONITOR = ROOT / "system_files/usr/libexec/moos-privacy-monitor"
PRIVACY_STOP = ROOT / "system_files/usr/bin/moos-privacy-stop"
PRIVACY_SERVICE = ROOT / "system_files/usr/lib/systemd/user/moos-privacy-monitor.service"
MOOS_OPEN = ROOT / "system_files/usr/bin/moos-open"


def code(path: Path) -> str:
    """QML without // comment lines."""
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("//"))


class PrivacyInfrastructureTests(unittest.TestCase):
    def test_scripts_exist_and_are_executable(self):
        self.assertTrue(PRIVACY_MONITOR.is_file(), "moos-privacy-monitor must exist")
        self.assertTrue(os.access(PRIVACY_MONITOR, os.X_OK), "moos-privacy-monitor must be executable")
        self.assertTrue(PRIVACY_STOP.is_file(), "moos-privacy-stop must exist")
        self.assertTrue(os.access(PRIVACY_STOP, os.X_OK), "moos-privacy-stop must be executable")
        self.assertTrue(PRIVACY_SERVICE.is_file(), "moos-privacy-monitor.service must exist")

    def test_privacy_monitor_supports_once_flag_and_token_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            res = subprocess.run(
                [str(PRIVACY_MONITOR), "--once", "--dir", tmpdir],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"privacy-monitor --once failed: {res.stderr}")
            # stdout must be valid json array
            data = json.loads(res.stdout)
            self.assertIsInstance(data, list)

    def test_privacy_stop_handles_actions(self):
        content = PRIVACY_STOP.read_text(encoding="utf-8")
        self.assertIn("pw-cli destroy", content)
        self.assertIn("wpctl set-mute", content)

    def test_moos_open_declares_privacy_stop_route(self):
        content = MOOS_OPEN.read_text(encoding="utf-8")
        self.assertRegex(content, r"(?m)^\s*privacy/stop/\*\)")
        self.assertIn("moos-privacy-stop", content)


class PrivacyStopIsNarrow(unittest.TestCase):
    """moos://privacy/stop/<type>/<node> is a PUBLIC URL: it may only stop a live stream.

    It used to hand the URL's last segment straight to `pw-cli destroy`, so any web page could
    destroy an arbitrary PipeWire object by number, and its Mo PC Remote branch called
    `moai-do remote-stop`, an action that never existed.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.runtime = self.root / "run"
        (self.runtime / "moos-privacy").mkdir(parents=True)
        for name in ("pw-cli", "wpctl", "systemctl", "moai-do", "kdialog"):
            stub = self.bin / name
            stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.log}"\n')
            stub.chmod(0o755)

    def tearDown(self):
        self.tmp.cleanup()

    def env(self):
        return {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.root),
                "XDG_RUNTIME_DIR": str(self.runtime), "LANG": "C.UTF-8"}

    def stop(self, *args):
        return subprocess.run(["bash", str(PRIVACY_STOP), *args], env=self.env(),
                              capture_output=True, text=True, timeout=30)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def live(self, token):
        (self.runtime / "moos-privacy" / token).write_text("{}")

    def test_only_a_live_stream_of_that_type_is_destroyed(self):
        self.live("active-camera-57-Firefox")
        self.assertEqual(self.stop("camera", "57").returncode, 0)
        self.assertEqual(self.calls(), ["pw-cli destroy 57"])
        # Not live, or live as another type: nothing is destroyed.
        for args in (("camera", "58"), ("screen", "57"), ("mic", "57")):
            with self.subTest(args=args):
                self.log.unlink(missing_ok=True)
                result = self.stop(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse([c for c in self.calls() if c.startswith("pw-cli")], args)

    def test_hostile_arguments_are_refused_before_anything_runs(self):
        self.live("active-camera-57-Firefox")
        for args in (("camera", "57;reboot"), ("camera", "-1"), ("camera", "../57"),
                     ("camera", "12345678901"), ("everything", "57"), ("", "57"), ()):
            with self.subTest(args=args):
                result = self.stop(*args)
                self.assertEqual(result.returncode, 2, (args, result.stderr))
        self.assertEqual(self.calls(), [])

    def test_a_mo_pc_remote_screen_stream_stops_the_remote_without_a_fake_action(self):
        self.live("active-screen-91-Mo%20PC%20Remote")
        self.assertEqual(self.stop("screen", "91").returncode, 0)
        self.assertIn("systemctl --user stop mo-remote-personal.service", self.calls())
        self.assertFalse([c for c in self.calls() if c.startswith("moai-do")],
                         "moai-do has no remote-stop action")
        code = "\n".join(line for line in PRIVACY_STOP.read_text().splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertNotIn("moai-do", code)
        self.assertNotIn("disable", code, "a stop is not a persistent off switch")

    def test_the_microphone_is_muted(self):
        self.assertEqual(self.stop("mic").returncode, 0)
        self.assertEqual(self.calls(), ["wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1"])

    def test_the_router_validates_before_calling_the_helper(self):
        for url in ("moos://privacy/stop/camera/57;reboot", "moos://privacy/stop/camera/abc",
                    "moos://privacy/stop/anything/57", "moos://privacy/stop/camera/-5"):
            with self.subTest(url=url):
                result = subprocess.run(["bash", str(MOOS_OPEN), url], env=self.env(),
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 2, url)
        self.assertFalse([c for c in self.calls() if not c.startswith("kdialog")])
        self.live("active-camera-57-Firefox")
        subprocess.run(["bash", str(MOOS_OPEN), "moos://privacy/stop/camera/57"], env=self.env(),
                       capture_output=True, text=True, timeout=30)
        self.assertIn("pw-cli destroy 57", self.calls())


class IslandLivingSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qml = code(ISLAND_QML)

    def test_priority_hierarchy_is_strictly_enforced(self):
        # Active condition orders: Remote > Privacy > Store > Media
        self.assertIn("readonly property bool active: root.remotePresent", self.qml)
        self.assertIn("|| root.privacyPresent", self.qml)
        self.assertIn("|| root.storeJobPresent", self.qml)
        self.assertIn("|| root.mediaPresent", self.qml)

        # Context title follows the same hierarchy
        self.assertIn("root.remotePresent", self.qml)
        self.assertIn("? root.remoteTitle", self.qml)
        self.assertIn("? root.privacyTitle", self.qml)
        self.assertIn("? root.storeJobTitle", self.qml)
        self.assertIn(": root.displayTrack", self.qml)

    def test_privacy_presence_is_observed_and_parsed(self):
        self.assertIn("FolderListModel", self.qml)
        self.assertIn("id: privacyPresence", self.qml)
        self.assertIn("moos-privacy", self.qml)
        self.assertIn("function syncPrivacyPresence()", self.qml)
        self.assertIn("property string privacyType:", self.qml)
        self.assertIn("property string privacyApp:", self.qml)
        self.assertIn("property string privacyNodeId:", self.qml)

    def test_store_jobs_tracked_via_cache_model(self):
        self.assertIn("id: storeJobPresence", self.qml)
        self.assertIn("moos-store", self.qml)
        self.assertIn("property string storeJobTitle:", self.qml)
        self.assertIn("property real storeJobProgress:", self.qml)
        self.assertIn("property string storeJobAction:", self.qml)

    def test_multi_context_details_expose_all_domains(self):
        self.assertIn("readonly property bool showRemoteDetails:", self.qml)
        self.assertIn("readonly property bool showPrivacyDetails:", self.qml)
        self.assertIn("readonly property bool showStoreDetails:", self.qml)
        self.assertIn("readonly property bool showMediaDetails:", self.qml)
        self.assertIn('root.detailContext = "privacy"', self.qml)
        self.assertIn('root.detailContext = "store"', self.qml)

    def test_motion_is_finite_and_gated(self):
        self.assertNotIn("Animation.Infinite", self.qml)


if __name__ == "__main__":
    unittest.main()
