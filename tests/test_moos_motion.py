#!/usr/bin/env python3
"""Keep motion bounded and make runtime proof mandatory in both image builds."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MotionContract(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
