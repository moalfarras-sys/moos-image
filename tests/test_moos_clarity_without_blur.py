#!/usr/bin/env python3
"""P2.5, proved on a real Qt runtime: glass stays readable when there is no blur.

Every Aurora Glass density assumes a blur pass behind the surface. Without one, 0.22
alpha over a wallpaper is not frosted glass — it is a window, and the text sits on
whatever photograph is underneath. Measured on the Oracle A1 (llvmpipe, no blur) during
its live review: "without blur Liquid Glass is see-through", and the row stayed open.

MoOS already decides this. `moos-visual-tier` turns blur OFF on the essential tier and
writes `kwinrc/Plugins/blurEnabled`, so the surfaces read that same key — which also
honours an owner who turned blur off themselves. `Qt.labs.settings` reads it
synchronously at load through the XDG configuration layers. Unknown policy uses
the readable fallback; inspecting policy must never create a user override.

String-matching cannot check any of that: the question is what a real QML engine
computes for `fillOpacity` given a real config file. So this runs one.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "system_files/usr/lib64/qt6/qml"
RUNTIME = next((name for name in ("moos-qml-shell", "qml-qt6", "qml6", "qml")
                if shutil.which(name)), None)

PROBE = """
import QtQuick
import Qt.labs.settings
import org.moos.ui as MoUI
import "%(hub)s" as Hub

QtObject {
    property var card: Hub.GlassCard { motionEnabled: false; accentMotion: false }
    property color dark: "#0b0f14"
    property var sink: Settings {
        fileName: "%(out)s"
        category: "Probe"
        property bool ran: false
        property bool blurActive: false
        property real glassClarity: 0
        property real sceneFill: 0
        property real popoverFill: 0
        property real floatingFill: 0
        property real cardUpper: 0
        property real cardLower: 0
    }
    Component.onCompleted: {
        sink.blurActive = MoUI.Tokens.blurActive
        sink.glassClarity = MoUI.Tokens.glassClarity
        sink.sceneFill = MoUI.Tokens.glassFill(dark, MoUI.Tokens.glassLevelScene,
                                               MoUI.Tokens.glassRestingOpacity)
        sink.popoverFill = MoUI.Tokens.glassFill(dark, MoUI.Tokens.glassLevelPopover,
                                                 MoUI.Tokens.glassRestingOpacity)
        sink.floatingFill = MoUI.Tokens.glassFill(dark, MoUI.Tokens.glassLevelDialog,
                                                  MoUI.Tokens.floatingGlassOpacity)
        sink.cardUpper = card.upperSurface.a
        sink.cardLower = card.lowerSurface.a
        sink.ran = true
        Qt.callLater(function () { Qt.exit(0) })
    }
}
"""


def layer(value) -> str | None:
    """The literal kwinrc a layer holds, from what the test wants it to SAY.

    `None` means the layer has no file at all. A `bool` is the ordinary
    `blurEnabled=true|false`. A `str` is written verbatim as the key's value, so a
    case can state the spellings KConfig accepts (`no`, `off`, `Off`) and MoOS must
    therefore accept too. `""` is the case that has no bug name and caused the worst
    behaviour: the file EXISTS, and says nothing about blur.
    """
    if value is None:
        return None
    if value == "":
        return "[Plugins]\n# a real user kwinrc, holding other keys and no blur policy\nslideEnabled=true\n"
    if isinstance(value, bool):
        value = "true" if value else "false"
    return f"[Plugins]\nblurEnabled={value}\n"


def measure(blur, system_blur=None, clarity=None) -> dict:
    """Run the real engine against a config that says blur is on or off."""
    with tempfile.TemporaryDirectory() as raw:
        work = Path(raw)
        config = work / "config"
        config.mkdir()
        system_config = work / "system-config"
        system_config.mkdir()
        written = {}
        for directory, value in ((config, blur), (system_config, system_blur)):
            text = layer(value)
            if text is not None:
                (directory / "kwinrc").write_text(text, encoding="utf-8")
                written[directory / "kwinrc"] = text
        if clarity is not None:
            appearance = config / "moos-appearancerc"
            appearance.write_text(
                f"[Material]\nClarity={clarity}\n", encoding="utf-8")
            written[appearance] = appearance.read_text(encoding="utf-8")
        out = work / "probe.ini"
        probe = work / "probe.qml"
        probe.write_text(PROBE % {"out": out, "hub": (ROOT / "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui").as_uri()}, encoding="utf-8")
        environment = {
            "HOME": str(work), "XDG_CONFIG_HOME": str(config),
            "XDG_CONFIG_DIRS": str(system_config),
            "QT_QUICK_BACKEND": "software", "QT_QPA_PLATFORM": "offscreen",
            "QML_IMPORT_PATH": str(UI), "QML2_IMPORT_PATH": str(UI),
            "PATH": "/usr/bin:/bin",
        }
        command = ([RUNTIME, "--app-id", "org.moos.clarity.gate", "--qml", str(probe)]
                   if RUNTIME == "moos-qml-shell" else [RUNTIME, str(probe)])
        result = subprocess.run(command, env=environment, capture_output=True, timeout=120)
        if result.returncode != 0 or not out.exists():
            raise AssertionError(f"QML clarity probe failed: {result.stderr.decode(errors='replace')}")
        # The regression this guards is not "a file appeared" — it is QSettings
        # writing its defaults back into a file it was only asked to read. Both
        # halves have to be checked, because only one of them is reachable at a
        # time: a layer MoOS never opens cannot be rewritten, and a layer it DOES
        # open is the one at risk. So assert on the file that exists.
        if blur is None and (config / "kwinrc").exists():
            raise AssertionError("Reading clarity created a user kwinrc override")
        for path, before in written.items():
            if path.read_text(encoding="utf-8") != before:
                raise AssertionError(
                    f"Reading clarity rewrote {path.name}:\n"
                    f"--- before ---\n{before}--- after ---\n{path.read_text(encoding='utf-8')}")
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
                raise AssertionError(f"the QML probe did not run ({name})")

    def test_system_policy_is_used_without_a_user_override(self):
        self.assertEqual(measure(None, False)["blurActive"], "false")
        self.assertEqual(measure(None, True)["blurActive"], "true")

    def test_explicit_user_choice_precedes_system_policy(self):
        self.assertEqual(measure(True, False)["blurActive"], "true")
        self.assertEqual(measure(False, True)["blurActive"], "false")

    def test_unknown_policy_keeps_the_readable_fallback(self):
        self.assertEqual(measure(None)["blurActive"], "false")

    def test_a_user_file_with_no_blur_policy_defers_to_the_system(self):
        """The case the old reader got wrong in the direction nobody notices.

        A user `kwinrc` almost always exists — Plasma writes one the first time the
        owner changes anything — and almost never mentions blur. "The user has a
        file" is therefore not "the user has an opinion", and treating it as one
        hands the answer to a layer that never spoke.
        """
        self.assertEqual(measure("", True)["blurActive"], "true")
        self.assertEqual(measure("", False)["blurActive"], "false")

    def test_the_spellings_kconfig_accepts_are_the_spellings_moos_accepts(self):
        """KConfig is what KWin reads this key with, so it decides what the key means.

        It accepts false/0/no/off, ignoring case, and treats every other non-empty
        value as true. A reader that understands a narrower vocabulary does not fail
        loudly — it silently skips the layer that spoke and obeys one that did not.
        """
        for spelling in ("no", "No", "OFF", "off", "0", "FALSE"):
            self.assertEqual(measure(spelling, True)["blurActive"], "false",
                             f"a user kwinrc saying blurEnabled={spelling} means blur is OFF")
        for spelling in ("yes", "on", "1", "True", "TRUE"):
            self.assertEqual(measure(spelling, False)["blurActive"], "true",
                             f"a user kwinrc saying blurEnabled={spelling} means blur is ON")

    def test_the_surfaces_see_the_real_kwin_setting(self):
        self.assertEqual(self.with_blur["blurActive"], "true")
        self.assertEqual(self.without_blur["blurActive"], "false")

    def test_with_blur_nothing_changes(self):
        """The frosted values the palette asks for, exactly as before."""
        self.assertAlmostEqual(float(self.with_blur["sceneFill"]), 0.22, places=3)
        self.assertAlmostEqual(float(self.with_blur["popoverFill"]), 0.22, places=3)
        self.assertAlmostEqual(float(self.with_blur["floatingFill"]), 0.82, places=3)

    def test_real_card_paints_distinct_clarity_endpoints(self):
        values = [measure(True, clarity=name) for name in ("clear", "balanced", "solid")]
        for key in ("cardUpper", "cardLower"):
            alpha = [float(v[key]) for v in values]
            self.assertGreater(alpha[1] - alpha[0], 0.2)
            self.assertGreater(alpha[2] - alpha[1], 0.05)
            self.assertGreater(alpha[2], 0.95)

    def test_saved_clarity_has_three_measured_material_endpoints(self):
        clear = measure(True, clarity="clear")
        balanced = measure(True, clarity="balanced")
        solid = measure(True, clarity="solid")
        self.assertAlmostEqual(float(clear["glassClarity"]), 0.0, places=3)
        self.assertAlmostEqual(float(balanced["glassClarity"]), 0.5, places=3)
        self.assertAlmostEqual(float(solid["glassClarity"]), 1.0, places=3)
        for row in ("sceneFill", "popoverFill", "floatingFill"):
            self.assertLess(float(clear[row]), float(balanced[row]), row)
            self.assertLessEqual(float(balanced[row]), float(solid[row]), row)
            self.assertAlmostEqual(float(solid[row]), 0.97, places=3)

    def test_without_blur_a_surface_stops_being_a_window(self):
        """0.22 over a photograph is not glass; the text has to sit on something."""
        for row in ("sceneFill", "popoverFill", "floatingFill"):
            value = float(self.without_blur[row])
            self.assertGreaterEqual(value, 0.80,
                                    f"{row} is {value} without blur — still see-through")
            self.assertLessEqual(value, 1.0, f"{row} is {value}, above opaque")
        # Reduced transparency is a policy, not a weak approximation: every
        # surface reaches the same near-solid endpoint while its rim/specular
        # still carry depth.
        self.assertAlmostEqual(float(self.without_blur["sceneFill"]), 0.97, places=3)
        self.assertAlmostEqual(float(self.without_blur["popoverFill"]), 0.97, places=3)

    def test_a_floating_surface_is_never_made_thinner(self):
        """glassFill may only ever ADD body, never remove it."""
        for row in ("sceneFill", "popoverFill", "floatingFill"):
            self.assertGreaterEqual(float(self.without_blur[row]), float(self.with_blur[row]),
                                    f"{row} lost opacity when blur went away")


if __name__ == "__main__":
    unittest.main()
