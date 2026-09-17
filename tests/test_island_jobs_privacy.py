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
