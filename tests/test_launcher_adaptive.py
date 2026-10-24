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

    def test_selfcheck_and_postboot_keep_one_responsive_predicate(self):
        bodies = []
        for name in ("system_files/usr/bin/moos-selfcheck", "tests/post-update-check.sh"):
            body = (ROOT / name).read_text().split("launcher_runtime_state() {", 1)[1]
            body = body.split("launcher_field()", 1)[0]
            function = re.search(r"            function popupFitsScreen\(.*?^            \}", body,
                                 re.S | re.M).group(0)
            bodies.append(function)
            self.assertIn("screenGeometry(ps[i].screen)", body)
            self.assertIn("panelBrands == 1 && panelLegacy == 0 && panelSized == 1", body)
        self.assertEqual(*bodies)
        self.assertIn("Math.min(600,", bodies[0])
        self.assertIn("Math.min(540,", bodies[0])
        # All palettes share the native frame geometry used by the predicate.
        import xml.etree.ElementTree as ET
        themes = list((ROOT / "system_files/usr/share/plasma/desktoptheme").glob("*/dialogs/background.svg"))
        self.assertEqual(len(themes), 18)
        for theme in themes:
            elements = {e.get("id"): e for e in ET.parse(theme).getroot().iter() if e.get("id")}
            for edge in ("left", "right", "top", "bottom"):
                dimension = "width" if edge in ("left", "right") else "height"
                self.assertEqual(float(elements["hint-" + edge + "-margin"].get(dimension)), 12)

    @unittest.skipUnless(shutil.which("node"), "health boundary evaluation needs Node")
    def test_live_size_hints_and_corrupt_geometry(self):
        source = (ROOT / "system_files/usr/bin/moos-selfcheck").read_text()
        function = re.search(r"            function popupFitsScreen\(.*?^            \}", source,
                             re.S | re.M).group(0)
        cases = [(318,576,360,640,70,True), (546,576,600,960,70,True),
                 (792,476,960,540,70,True), (792,576,1536,864,70,True),
                 (600,540,1536,864,70,True), (599,540,1536,864,70,False),
                 (600,539,1536,864,70,False), (100,100,360,640,70,False),
                 (0,576,360,640,70,False), (792,0,1536,864,70,False),
                 (792,576,0,864,70,False), (792,576,1536,0,70,False),
                 (792,576,1536,864,-1,False), (792,576,360,640,640,False)]
        program = function + "\nconst cases=" + json.dumps(cases) + ";\n"
        program += "process.stdout.write(JSON.stringify(cases.map(c=>popupFitsScreen(c[0],c[1],{width:c[2],height:c[3]},c[4]))));"
        result = subprocess.run([shutil.which("node"), "-e", program],
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), [c[-1] for c in cases])
        invalid = function + "\nconst g={width:1536,height:864};"
        invalid += "process.stdout.write(JSON.stringify([popupFitsScreen(NaN,576,g,70),popupFitsScreen(792,Infinity,g,70),popupFitsScreen(792,576,{width:Infinity,height:864},70),popupFitsScreen(792,576,g,Infinity),popupFitsScreen(792,576,null,70)]));"
        result = subprocess.run([shutil.which("node"), "-e", invalid],
                                capture_output=True, text=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), [False] * 5)

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
            command = [shutil.which("python3"), str(ROOT / "tests/launcher_adaptive_native.py"), "--native-popup"]
            fixed = subprocess.run(command + ["--output", str(output / "fixed")],
                                   capture_output=True, text=True, timeout=180)
            self.assertEqual(fixed.returncode, 0, fixed.stdout[-2500:] + fixed.stderr[-5000:])
            record = json.loads((output / "fixed/receipt.json").read_text())
            self.assertEqual(len(record["cases"]), 4)
            self.assertEqual([c["old_fixed_size_health_accepts"] for c in record["cases"]],
                             [False, False, False, True])
            self.assertTrue(record["owner_portal_unchanged"] and record["source_unchanged"])
            self.assertTrue(all(c['input']['categoryBrowsing'] for c in record['cases']))
            category = subprocess.run(command + ["--output", str(output / "category"), "--broken-category"],
                                      capture_output=True, text=True, timeout=60)
            self.assertNotEqual(category.returncode, 0, "decorative categories must refuse")
            log = (output / "category/360x640-ar-launcher.log").read_text()
            self.assertIn("MOOS_ADAPTIVE_ASSERT pointer selects native category", log)
            self.assertIn("MOOS_ADAPTIVE_INPUT_FAIL", log)
            self.assertNotIn("MOOS_ADAPTIVE_INPUT_PASS", log)
            if shutil.which("node"):
                function = re.search(r"            function popupFitsScreen\(.*?^            \}",
                    (ROOT / "system_files/usr/bin/moos-selfcheck").read_text(), re.S | re.M).group(0)
                samples = [[c["saved_popup"]["width"], c["saved_popup"]["height"],
                            c["output_width"], c["output_height"]] for c in record["cases"]]
                program = function + "\nconst cases=" + json.dumps(samples) + ";\n"
                program += "process.stdout.write(JSON.stringify(cases.map(c=>popupFitsScreen(c[0],c[1],{width:c[2],height:c[3]},0))));"
                health = subprocess.run([shutil.which("node"), "-e", program],
                    capture_output=True, text=True, timeout=10, check=True)
                self.assertEqual(json.loads(health.stdout), [True] * 4)
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
