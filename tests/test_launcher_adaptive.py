#!/usr/bin/env python3
"""Guard actual responsive launcher geometry and native focus delivery.

The old fixed canvas clips in portrait/short outputs; source focus wiring also
passed despite GridView consuming Backtab before KeyNavigation. The native
Plasma-host matrix exercises real Qt key, pointer and synthetic touch events,
then restores the previously broken priority in a private copy to prove refusal.
No owner output, desktop configuration or input is used by this test.
"""
from pathlib import Path
import importlib.util
import contextlib
import os
import json
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
MAIN = VIEW.with_name("main.qml")


def code(path):
    return "\n".join(line for line in path.read_text().splitlines()
                     if not line.lstrip().startswith("//"))


class AdaptiveLauncher(unittest.TestCase):
    def test_work_area_is_owned_by_plasma_and_falls_back_to_current_screen(self):
        main, view = code(MAIN), code(VIEW)
        self.assertIn("root.screen >= 0", main)
        for axis, dimension in (("Width", "width"), ("Height", "height")):
            self.assertIn(f"root.availableScreenRect.{dimension}", main)
            self.assertIn(f": Screen.{dimension}", main)
            self.assertIn(f"launcher.popupAvailable{axis}", view)
            self.assertIn(f"Layout.maximum{axis}: implicit{axis}", view)
        self.assertNotIn("smokeFullRepresentation ?", view)

    def test_browse_and_session_actions_have_one_native_owner(self):
        view = code(VIEW)
        self.assertEqual(view.count("id: navApps"), 1)
        self.assertIn("columns: view.compact ? 4 : 1", view)
        self.assertIn("readonly property int targetSize: design.targetControl", view)
        self.assertIn("model: view.sessionModel", view)
        self.assertIn("view.launcher.triggerEntry(view.sessionModel, index)", view)
        self.assertIn("KeyNavigation.priority: KeyNavigation.BeforeItem", view)
        self.assertIn("contentHeight: Math.max(height, homeColumn.implicitHeight)", view)

    @unittest.skipUnless(shutil.which("node"), "column boundary evaluation needs Node")
    def test_real_column_function_keeps_labels_readable_and_caps_density(self):
        function = re.search(r"    function appColumns\(availableWidth\) \{.*?\n    \}",
                             VIEW.read_text(), re.S).group(0)
        sizes = [1, 100, 224, 320, 448, 560, 1200]
        result = subprocess.run([shutil.which("node"), "-e", function
            + "\nprocess.stdout.write(JSON.stringify(" + json.dumps(sizes)
            + ".map(appColumns)));"], capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), [1, 1, 2, 2, 4, 4, 4])

    @unittest.skipUnless(
        all(shutil.which(tool) for tool in ("kwin_wayland", "plasmawindowed", "spectacle", "dbus-daemon"))
        and Path("/usr/lib64/qt6/qml/QtTest").is_dir()
        and importlib.util.find_spec("gi"), "native Plasma/QtTest tools unavailable")
    def test_native_viewports_input_motion_and_broken_priority_control(self):
        retained = os.environ.get("MOOS_LAUNCHER_PROOF_DIR")
        if retained:
            retained = Path(retained)
            retained.mkdir(mode=0o700, parents=True, exist_ok=False)
        context = (contextlib.nullcontext(str(retained)) if retained else
                   tempfile.TemporaryDirectory(prefix="moos-launcher-gate-"))
        with context as temporary:
            output = Path(temporary)
            command = [shutil.which("python3"), str(ROOT / "tests/launcher_adaptive_native.py")]
            fixed = subprocess.run(command + ["--output", str(output / "fixed")],
                                   capture_output=True, text=True, timeout=180)
            self.assertEqual(fixed.returncode, 0, fixed.stdout[-2500:] + fixed.stderr[-5000:])
            record = json.loads((output / "fixed/receipt.json").read_text())
            self.assertEqual(len(record["cases"]), 4)
            self.assertTrue(record["owner_portal_unchanged"] and record["source_unchanged"])
            broken = subprocess.run(command + ["--output", str(output / "broken"), "--broken-backtab"],
                                    capture_output=True, text=True, timeout=60)
            self.assertNotEqual(broken.returncode, 0, "broken native focus must refuse")
            log = (output / "broken/360x640-ar-launcher.log").read_text()
            self.assertIn("MOOS_ADAPTIVE_ASSERT Backtab returns to current navigation", log)
            self.assertIn("MOOS_ADAPTIVE_INPUT_FAIL", log)
            self.assertNotIn("MOOS_ADAPTIVE_INPUT_PASS", log)
            alignment = subprocess.run(command + ["--output", str(output / "alignment"), "--broken-alignment"],
                                       capture_output=True, text=True, timeout=60)
            self.assertNotEqual(alignment.returncode, 0, "double-mirrored text must refuse")
            log = (output / "alignment/360x640-ar-launcher.log").read_text()
            self.assertIn("MOOS_ADAPTIVE_ASSERT section text follows the logical leading edge once", log)
            self.assertIn("MOOS_ADAPTIVE_INPUT_FAIL", log)
            self.assertNotIn("MOOS_ADAPTIVE_INPUT_PASS", log)


if __name__ == "__main__":
    unittest.main()
