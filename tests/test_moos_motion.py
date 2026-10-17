#!/usr/bin/env python3
"""Keep motion bounded and make runtime proof mandatory in both image builds."""
import json
import importlib.util
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("motion_gate", ROOT / "build_files/verify_moos_motion.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class MotionContract(unittest.TestCase):
    def test_review_selects_full_speed_without_inheriting_desktop_or_cloud_defaults(self):
        def run(argv, **kwargs):
            env = kwargs["env"]
            config = Path(env["XDG_CONFIG_HOME"])
            self.assertEqual((config / "kdeglobals").read_text(), "[KDE]\nAnimationDurationFactor=1\n")
            self.assertEqual(env["XDG_CONFIG_DIRS"], str(config))
            self.assertEqual(env["QT_QPA_PLATFORMTHEME"], "kde")
            self.assertEqual(Path(env["XDG_RUNTIME_DIR"]).stat().st_mode & 0o777, 0o700)
            self.assertNotEqual(env["HOME"], os.path.expanduser("~"))
            self.assertEqual(env["QT_QPA_PLATFORM"], "offscreen")
            self.assertTrue(env["DBUS_SESSION_BUS_ADDRESS"].endswith("/absent-bus"))
            self.assertNotIn("QT_PLUGIN_PATH", env)
            return subprocess.CompletedProcess(argv, 0, "MOOS_MOTION_PASSED: actual interaction\n", "")

        with patch.object(gate.subprocess, "run", side_effect=run):
            self.assertEqual(gate.verify(ROOT / "tests/qml/motion-review.qml"), 0)

    def test_physics_is_bounded_and_shared(self):
        tokens = json.loads((ROOT / "artwork/moos-design/tokens.json").read_text())["material"]
        self.assertGreater(tokens["springStiffness"], 0)
        self.assertLessEqual(tokens["springStiffness"], 5)
        self.assertGreater(tokens["springDamping"], 0)
        self.assertLess(tokens["springDamping"], 1)
        self.assertGreaterEqual(tokens["springEpsilon"], 0.001)
        self.assertLessEqual(tokens["springEpsilon"], 0.005)
        module = ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui"
        self.assertIn("SpringFeedback 1.0 SpringFeedback.qml", (module / "qmldir").read_text())
        source = (module / "SpringFeedback.qml").read_text()
        self.assertNotIn("Animation.Infinite", source)
        self.assertNotIn("Timer {", source)

    def test_both_images_execute_the_real_fixture(self):
        for suffix in ("", ".arm"):
            self.assertIn("COPY tests/qml/motion-review.qml /motion-review.qml",
                          (ROOT / ("Containerfile" + suffix)).read_text())
        for name in ("build.sh", "build-arm.sh"):
            self.assertIn("python3 /ctx/verify_moos_motion.py --qml /ctx/motion-review.qml",
                          (ROOT / "build_files" / name).read_text())

    @unittest.skipUnless(Path("/usr/bin/moos-qml-shell").exists(),
                         "native MoOS Qt runtime required; mandatory in image gates")
    def test_native_runtime(self):
        result = subprocess.run([
            "python3", str(ROOT / "build_files/verify_moos_motion.py"),
            "--qml", str(ROOT / "tests/qml/motion-review.qml"),
            "--imports", str(ROOT / "system_files/usr/lib64/qt6/qml"),
        ], text=True, capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(Path("/usr/bin/moos-qml-shell").exists(), "native Qt runtime required")
    def test_shared_hub_reveal_can_be_interrupted_and_stopped(self):
        result = subprocess.run([
            "python3", str(ROOT / "build_files/verify_moos_motion.py"),
            "--qml", str(ROOT / "tests/qml/hub-motion-review.qml"),
            "--imports", str(ROOT / "system_files/usr/lib64/qt6/qml"),
        ], text=True, capture_output=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
