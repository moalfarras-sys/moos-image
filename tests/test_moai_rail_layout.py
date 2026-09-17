#!/usr/bin/env python3
"""Gate: Mo AI's navigation rail is laid out correctly at the size the window actually opens at.

WHY THIS EXISTS

Mo AI opens 940 px wide. Under 1120 px its rail is COMPACT: a 76 px strip of icons with a small
label under each. The rail's entries were a RowLayout in both modes, and a row cannot stack: in
the compact rail the icon sat in one corner of the highlight pill and the label in the opposite
one, and the longest label ran out of the pill altogether. Every review of the window had been
rendered at 1400 px, where the rail is expanded and correct — so the first thing a person saw on
every launch was the one layout nobody had looked at.

Found by rendering the app at its DEFAULT size (scripts/review/render-app.sh moai … --w=940).
This gate measures the real window, in both modes and both directions:

  compact   the label is BELOW the icon, centred on it, inside its pill and not elided
  expanded  the label is BESIDE the icon on the same line, after it in reading direction

It needs a Qt QML runtime and Xvfb; without them it skips (the repo-gates runner has neither), so
run it on a development machine — `scripts/review/mirror-gates.sh` does.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/qml/moai-rail-review.qml"
MOAI = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
QML_RUNTIME = shutil.which("qml-qt6") or shutil.which("qml6") or shutil.which("qml")


def centre(box: dict, axis: str) -> float:
    return box[axis] + box["w" if axis == "x" else "h"] / 2


class DefaultSize(unittest.TestCase):
    def test_the_window_really_opens_compact(self) -> None:
        """If the default width or the breakpoint moves, the mode this gate guards moves with it."""
        qml = MOAI.read_text(encoding="utf-8")
        self.assertIn("width: root.argWindowDimension(0, 940)", qml)
        self.assertIn("readonly property bool workspaceSidebarExpanded: width >= 1120", qml)


@unittest.skipUnless(QML_RUNTIME and shutil.which("xvfb-run") and sys.platform.startswith("linux"),
                     "needs a Qt QML runtime and Xvfb (absent on the repo-gates runner)")
class TheRealRail(unittest.TestCase):
    def measure(self, width: int, height: int, arabic: bool) -> dict:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)
        (work / "run").mkdir(mode=0o700)
        env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(work / "config"),
                   XDG_CACHE_HOME=str(work / "cache"), XDG_RUNTIME_DIR=str(work / "run"),
                   QML_IMPORT_PATH=str(ROOT / "system_files/usr/lib64/qt6/qml"),
                   QML_DISABLE_DISK_CACHE="1", QT_QUICK_CONTROLS_STYLE="Basic", LIBGL_ALWAYS_SOFTWARE="1")
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
            env.pop(name, None)                        # a gate must never reach a live desktop
        argv = ["xvfb-run", "-a", "-s", "-screen 0 1600x1000x24", QML_RUNTIME, str(HARNESS), "--",
                # Ports nobody listens on: the rail does not depend on any backend.
                "--gateway-port", "65001", "--control-port", "65002", "--agent-port", "65003",
                f"--w={width}", f"--h={height}"] + (["--arabic"] if arabic else [])
        done = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
        line = next((l for l in (done.stderr + done.stdout).splitlines() if "RAIL-GEOMETRY " in l), "")
        self.assertTrue(line, f"the window reported nothing (rc={done.returncode}):\n{done.stderr[-1200:]}")
        report = json.loads(line.split("RAIL-GEOMETRY ", 1)[1])
        self.assertGreaterEqual(len(report["entries"]), 5, "the rail's entries were not found by name")
        return report

    def test_compact_stacks_the_label_under_its_icon(self) -> None:
        for arabic in (False, True):
            report = self.measure(940, 700, arabic)
            self.assertFalse(report["expanded"])
            self.assertEqual(report["rtl"], arabic)
            for entry in report["entries"]:
                with self.subTest(arabic=arabic, entry=entry["id"], text=entry["text"]):
                    icon, label, pill = entry["icon"], entry["label"], entry["pill"]
                    self.assertAlmostEqual(centre(icon, "x"), centre(pill, "x"), delta=1.5,
                                           msg="the icon is not centred in its pill")
                    self.assertAlmostEqual(centre(label, "x"), centre(icon, "x"), delta=1.5,
                                           msg="the label is not centred under its icon")
                    self.assertGreaterEqual(label["y"], icon["y"] + icon["h"] - 1,
                                            "the label is beside the icon, not under it")
                    self.assertGreaterEqual(label["x"], pill["x"] - 0.5)
                    self.assertLessEqual(label["x"] + label["w"], pill["x"] + pill["w"] + 0.5,
                                         "the label runs out of its pill")
                    self.assertLessEqual(label["y"] + label["h"], pill["y"] + pill["h"] + 0.5)
                    self.assertFalse(entry["truncated"], f"“{entry['text']}” is cut off in the compact rail")

    def test_expanded_puts_the_label_beside_its_icon(self) -> None:
        for arabic in (False, True):
            report = self.measure(1400, 900, arabic)
            self.assertTrue(report["expanded"])
            for entry in report["entries"]:
                with self.subTest(arabic=arabic, entry=entry["id"]):
                    icon, label = entry["icon"], entry["label"]
                    self.assertAlmostEqual(centre(icon, "y"), centre(label, "y"), delta=2.0)
                    if arabic:
                        self.assertLessEqual(label["x"] + label["w"], icon["x"] + 0.5,
                                             "in Arabic the label reads to the LEFT of its icon")
                    else:
                        self.assertGreaterEqual(label["x"], icon["x"] + icon["w"] - 0.5)
                    self.assertFalse(entry["truncated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
