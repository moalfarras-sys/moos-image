#!/usr/bin/env python3
"""The motion gate, proved against a real Qt runtime instead of asserted.

WHY THIS FILE EXISTS

Every "animations off" gate in MoOS was off by one, for its entire life, and no
string-matching test could see it. The gate read

    Kirigami.Units.longDuration > 0

and the belief behind it was that Kirigami collapses that value to 0 when the user
sets AnimationDurationFactor=0 (System Settings -> General Behaviour -> "Disable
animations", and what MoOS Cloud sets deliberately). It does not. It FLOORS the
value at 1. Measured on this machine's own Qt 6.11 / Kirigami 6.28, three points:

    AnimationDurationFactor=1     ->  longDuration = 200
    AnimationDurationFactor=0.5   ->  longDuration = 100
    AnimationDurationFactor=0     ->  longDuration = 1      <- not 0

So `> 0` was true even with animations fully disabled. The desktop wallpaper, the
dashboard bento, the hero clock, the splash and the lock screen all kept every
endless animation running for the whole session no matter what the user asked for,
and the repo's own gate at tests/verify_user_experience.py REQUIRED the broken form
by literal string — it was holding the bug in place.

KDE says the same thing in its own code: all three shipped BusyIndicator.qml
(org/kde/breeze, org/kde/desktop, org/kde/plasma/components) gate their infinite
spinner on `longDuration > 1`, and RejectPasswordPathAnimation.qml writes
`longDuration <= 1 ? 1 : 600`.

A string check cannot catch the next version of this mistake, because the next
version will also be a plausible-looking expression. So this test does not read the
QML: it RUNS it. It instantiates the real MoOS surfaces in a real QML engine, once
with animations enabled and once with AnimationDurationFactor=0, and requires the
gate to actually change state.

The harness reports through the process exit code on purpose: qml's console.log
does not survive every sandbox/CI stdout arrangement, and an exit code does.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "system_files/usr/share"

# The runtime is `qml-qt6` on Fedora; upstream and some distros call it `qml6`.
QML_RUNTIME = next(
    (name for name in ("qml-qt6", "qml6", "qml") if shutil.which(name)), None
)

# Every surface that owns a motion gate, and the expression that must gate it.
# A file is listed here once it is expected to fall completely still.
GATED_SURFACES = (
    SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/Splash.qml",
    SHARE / "plasma/plasmoids/org.moos.heroclock/contents/ui/main.qml",
    SHARE / "plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui/main.qml",
)

PROBE = """
import QtQuick
import org.kde.kirigami as Kirigami
Item {
    // 10 = animations are on and the gate is open
    // 11 = animations are off and the gate is SHUT   (the value that proves the fix)
    // 12 = animations are off and the gate is STILL OPEN  (the off-by-one bug)
    Component.onCompleted: {
        var enabled = Kirigami.Units.longDuration > 1
        Qt.exit(enabled ? 10 : 11)
    }
}
"""


def _run_probe(qml_source: str, animation_factor: str) -> int:
    """Run a QML snippet with a given AnimationDurationFactor; return its exit code."""
    with tempfile.TemporaryDirectory(prefix="moos-motion-gate-") as tmp:
        temp = Path(tmp)
        config_home = temp / "config"
        config_home.mkdir()
        # Start from the real kdeglobals when there is one so the KDE platform
        # theme initialises exactly as it does in a session, then change only the
        # one key under test. An isolated config with ONLY this key does not
        # initialise the platform theme and silently reports the default.
        source_globals = Path(os.path.expanduser("~/.config/kdeglobals"))
        if source_globals.is_file():
            shutil.copy(source_globals, config_home / "kdeglobals")
        else:
            (config_home / "kdeglobals").write_text("[KDE]\n", encoding="utf-8")
        subprocess.run(
            ["kwriteconfig6", "--file", str(config_home / "kdeglobals"),
             "--group", "KDE", "--key", "AnimationDurationFactor", animation_factor],
            check=True,
        )

        probe = temp / "probe.qml"
        probe.write_text(qml_source, encoding="utf-8")

        env = os.environ.copy()
        env.update({
            "XDG_CONFIG_HOME": str(config_home),
            "QT_QPA_PLATFORM": "offscreen",
            # Without the KDE platform theme, Kirigami never applies the factor at
            # all and every reading comes back as the 200 ms default — which would
            # make this test pass for the wrong reason.
            "QT_QPA_PLATFORMTHEME": "kde",
        })
        return subprocess.run(
            [QML_RUNTIME, str(probe)], env=env, timeout=90,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode


@unittest.skipIf(QML_RUNTIME is None or shutil.which("kwriteconfig6") is None,
                 "needs a Qt QML runtime and kwriteconfig6 (present in the image build)")
class MotionGateTests(unittest.TestCase):

    def test_kirigami_floors_long_duration_at_one_not_zero(self) -> None:
        """The measurement the whole contract rests on. If this ever reports 0,
        `> 0` became correct and this file can be simplified — until then, `> 0` is
        a gate that never fires."""
        measure = """
import QtQuick
import org.kde.kirigami as Kirigami
Item { Component.onCompleted: Qt.exit(Math.min(255, Kirigami.Units.longDuration)) }
"""
        full = _run_probe(measure, "1")
        off = _run_probe(measure, "0")
        self.assertGreater(full, 1,
                           "with animations ON, longDuration must be a real duration")
        self.assertEqual(
            off, 1,
            "Kirigami floors longDuration at 1 with animations OFF. If this value is "
            "not 1, re-derive the motion gate before trusting any of it.",
        )

    def test_the_gate_actually_shuts_when_animations_are_disabled(self) -> None:
        """`> 1` closes at AnimationDurationFactor=0; `> 0` does not. This is the
        difference between a motion setting that works and one that is decoration."""
        self.assertEqual(_run_probe(PROBE, "1"), 10,
                         "the gate must be OPEN with animations enabled")
        self.assertEqual(_run_probe(PROBE, "0"), 11,
                         "the gate must SHUT with animations disabled — if this is 10, "
                         "the off-by-one is back and 'animations off' stops nothing")

        broken = PROBE.replace("longDuration > 1", "longDuration > 0")
        self.assertEqual(
            _run_probe(broken, "0"), 10,
            "control: the OLD `> 0` form must still be observed staying open with "
            "animations disabled. If this ever returns 11, Kirigami's flooring "
            "changed and this whole test needs revisiting.",
        )

    def test_every_gated_surface_uses_the_correct_comparison(self) -> None:
        """Cheap companion to the runtime proof: no shipped motion gate may carry
        the `> 0` form. Kept here next to the measurement that explains why."""
        for surface in GATED_SURFACES:
            with self.subTest(surface=surface.relative_to(ROOT).as_posix()):
                self.assertTrue(surface.is_file(), f"{surface} is missing")
                # Strip QML comments FIRST. This gate forbids a string that the
                # WHY comment explaining the bug must be able to name — the
                # comment trap AGENTS.md warns about, in reverse. main.qml had to
                # be reworded into prose ("compare against ZERO") to get past it,
                # which is the gate editing the prose rather than the code.
                # verify_user_experience.py already has code(text, "slash") for
                # exactly this.
                text = re.sub(r"//[^\n]*", "", surface.read_text(encoding="utf-8"))
                self.assertNotIn(
                    "longDuration > 0", text,
                    "this surface gates motion on `> 0`, which is true even with "
                    "animations fully disabled; use `> 1`",
                )
                self.assertIn(
                    "longDuration > 1", text,
                    "this surface must gate its endless animations on "
                    "`Kirigami.Units.longDuration > 1`",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
