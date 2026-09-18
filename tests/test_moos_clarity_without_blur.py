#!/usr/bin/env python3
"""P2.5, proved on a real Qt runtime: glass stays readable when there is no blur.

Every Aurora Glass density assumes a blur pass behind the surface. Without one, 0.22
alpha over a wallpaper is not frosted glass — it is a window, and the text sits on
whatever photograph is underneath. Measured on the Oracle A1 (llvmpipe, no blur) during
its live review: "without blur Liquid Glass is see-through", and the row stayed open.

MoOS already decides this. `moos-visual-tier` turns blur OFF on the essential tier and
writes `kwinrc/Plugins/blurEnabled`, so the surfaces read that same key — which also
honours an owner who turned blur off themselves. `Qt.labs.settings` reads it
synchronously at load, with the default `true` matching /etc/xdg/kwinrc, so a machine
with no override behaves exactly as it did before.

String-matching cannot check any of that: the question is what a real QML engine
computes for `fillOpacity` given a real config file. So this runs one.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "system_files/usr/lib64/qt6/qml"
RUNTIME = next((name for name in ("moos-qml-shell", "qml-qt6", "qml6", "qml")
                if shutil.which(name)), None)

PROBE = """
import QtQuick
import Qt.labs.settings
import org.moos.ui as MoUI

QtObject {
    property color dark: "#0b0f14"
    property var sink: Settings {
        fileName: "%(out)s"
        category: "Probe"
        property bool ran: false
        property bool blurActive: false
        property real sceneFill: 0
        property real popoverFill: 0
        property real floatingFill: 0
    }
    Component.onCompleted: {
        sink.blurActive = MoUI.Tokens.blurActive
        sink.sceneFill = MoUI.Tokens.glassFill(dark, MoUI.Tokens.glassLevelScene,
                                               MoUI.Tokens.glassRestingOpacity)
        sink.popoverFill = MoUI.Tokens.glassFill(dark, MoUI.Tokens.glassLevelPopover,
                                                 MoUI.Tokens.glassRestingOpacity)
        sink.floatingFill = MoUI.Tokens.glassFill(dark, MoUI.Tokens.glassLevelDialog,
                                                  MoUI.Tokens.floatingGlassOpacity)
        sink.ran = true
        Qt.callLater(function () { Qt.exit(0) })
    }
}
"""


def measure(blur: bool) -> dict:
    """Run the real engine against a config that says blur is on or off."""
    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        config = work / "config"
        config.mkdir()
        (config / "kwinrc").write_text(
            f"[Plugins]\nblurEnabled={'true' if blur else 'false'}\n", encoding="utf-8")
        out = work / "probe.ini"
        probe = work / "probe.qml"
        probe.write_text(PROBE % {"out": out}, encoding="utf-8")
        environment = {
            "HOME": str(work), "XDG_CONFIG_HOME": str(config),
            "QT_QUICK_BACKEND": "software", "QT_QPA_PLATFORM": "offscreen",
            "QML_IMPORT_PATH": str(UI), "QML2_IMPORT_PATH": str(UI),
            "PATH": "/usr/bin:/bin",
        }
        command = ([RUNTIME, "--app-id", "org.moos.clarity.gate", "--qml", str(probe)]
                   if RUNTIME == "moos-qml-shell" else [RUNTIME, str(probe)])
        subprocess.run(command, env=environment, capture_output=True, timeout=120)
        if not out.exists():
            return {}
        values = {}
        for line in out.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
        return values


@unittest.skipIf(RUNTIME is None, "no QML runtime on this machine (CI)")
class ClarityWithoutBlur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.with_blur = measure(True)
        cls.without_blur = measure(False)
        for name, result in (("with blur", cls.with_blur), ("without blur", cls.without_blur)):
            if result.get("ran") != "true":
                raise unittest.SkipTest(f"the QML probe did not run ({name})")

    def test_the_surfaces_see_the_real_kwin_setting(self):
        self.assertEqual(self.with_blur["blurActive"], "true")
        self.assertEqual(self.without_blur["blurActive"], "false")

    def test_with_blur_nothing_changes(self):
        """The frosted values the palette asks for, exactly as before."""
        self.assertAlmostEqual(float(self.with_blur["sceneFill"]), 0.22, places=3)
        self.assertAlmostEqual(float(self.with_blur["popoverFill"]), 0.22, places=3)
        self.assertAlmostEqual(float(self.with_blur["floatingFill"]), 0.82, places=3)

    def test_without_blur_a_surface_stops_being_a_window(self):
        """0.22 over a photograph is not glass; the text has to sit on something."""
        for row in ("sceneFill", "popoverFill", "floatingFill"):
            value = float(self.without_blur[row])
            self.assertGreaterEqual(value, 0.80,
                                    f"{row} is {value} without blur — still see-through")
            self.assertLessEqual(value, 1.0, f"{row} is {value}, above opaque")
        # And depth still reads: a popover is denser than a scene card.
        self.assertGreater(float(self.without_blur["popoverFill"]),
                           float(self.without_blur["sceneFill"]),
                           "without blur the four depths collapsed into one sheet")

    def test_a_floating_surface_is_never_made_thinner(self):
        """glassFill may only ever ADD body, never remove it."""
        for row in ("sceneFill", "popoverFill", "floatingFill"):
            self.assertGreaterEqual(float(self.without_blur[row]), float(self.with_blur[row]),
                                    f"{row} lost opacity when blur went away")


if __name__ == "__main__":
    unittest.main()
