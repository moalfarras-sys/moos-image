#!/usr/bin/env python3
"""Gate: Mo AI's chat texture never leaves stray logos on a machine without a GPU.

WHY THIS EXISTS

Mo AI's backdrop is a line-art tile recoloured by MultiEffect, with the Mo AI mark woven in as
plain icons. /usr/bin/moai selects Qt Quick's software scene graph on every machine without a real
GPU (the ARM A1, the cloud edition, any VM), and the software scene graph runs no shader: the
MultiEffect layer drew nothing, the line art vanished, and the marks stayed as stray logos on an
empty surface, one cutting across the hero ring. Seen on the A1 on 2026-09-24, with the same source
rendered through llvmpipe GL beside it for the intended look.

Now the layer is enabled only where a shader runs; without one the tile keeps its own white strokes
on a dark scheme, and on a light scheme the texture and its marks are left out together. The
runtime half loads the real window offscreen under the software scene graph and reads the result.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOAI = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
HARNESS = ROOT / "tests/qml/moai-doodle-review.qml"
SHELL = shutil.which("moos-qml-shell")
RUNTIME = shutil.which("qml-qt6") or shutil.which("qml6") or shutil.which("qml")


def component(text: str) -> str:
    start = text.index("component ChatDoodle: Item {")
    end = text.index("\n    }\n", start)
    return text[start:end]


class TheSourceGatesTheShader(unittest.TestCase):
    def setUp(self):
        self.doodle = component(MOAI.read_text(encoding="utf-8"))

    def test_the_layer_runs_only_where_a_shader_can(self):
        self.assertIn("readonly property bool recolourable: GraphicsInfo.api !== GraphicsInfo.Software",
                      self.doodle)
        self.assertIn("layer.enabled: doodleRoot.recolourable", self.doodle)
        self.assertNotRegex(self.doodle, r"layer\.enabled:\s*true",
                            "an unconditional MultiEffect layer draws nothing on the software scene graph")

    def test_marks_never_outlive_their_texture(self):
        self.assertIn("readonly property bool drawsTexture: recolourable || root.isDark", self.doodle)
        self.assertIn("visible: drawsTexture", self.doodle)
        # The marks are children of the same item, so hiding the texture hides them too.
        self.assertIn('source: "moos-moai"', self.doodle)


@unittest.skipUnless(SHELL or RUNTIME, "no QML runtime on this machine")
class TheRealWindowOnTheSoftwareSceneGraph(unittest.TestCase):
    def state(self, scheme: str) -> dict:
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            (work / "run").mkdir(mode=0o700)
            config = work / "config"
            config.mkdir()
            colours = ROOT / f"system_files/usr/share/color-schemes/{scheme}.colors"
            (config / "kdeglobals").write_text(
                colours.read_text(encoding="utf-8") + f"\n[General]\nColorScheme={scheme}\n",
                encoding="utf-8")
            env = {
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": str(work), "XDG_CONFIG_HOME": str(config),
                "XDG_CACHE_HOME": str(work / "cache"), "XDG_RUNTIME_DIR": str(work / "run"),
                "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
                # The KDE platform theme is what makes Kirigami read the scheme above.
                "QT_QPA_PLATFORMTHEME": "kde", "QT_QUICK_CONTROLS_STYLE": "org.kde.desktop",
                "QML_IMPORT_PATH": str(ROOT / "system_files/usr/lib64/qt6/qml"),
                "QML_DISABLE_DISK_CACHE": "1", "QT_FORCE_STDERR_LOGGING": "1",
                # No live desktop, no session bus: a gate never reaches the owner's session.
                "DBUS_SESSION_BUS_ADDRESS": f"unix:path={work}/run/no-bus",
            }
            if SHELL:
                argv = [SHELL, "--app-id", "org.moos.moai.doodlegate", "--qml", str(HARNESS), "--"]
            else:
                argv = [RUNTIME, str(HARNESS), "--"]
            argv += ["--gateway-port", "65001", "--control-port", "65002", "--agent-port", "65003",
                     "--software-render"]
            done = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=120)
        line = next((l for l in (done.stderr + done.stdout).splitlines() if "DOODLE-STATE " in l), "")
        self.assertTrue(line, f"the window reported nothing (rc={done.returncode}):\n{done.stderr[-1500:]}")
        return json.loads(line.split("DOODLE-STATE ", 1)[1])

    def test_the_texture_is_drawn_raw_on_dark_and_left_out_on_light(self):
        seen = set()
        for scheme in ("MoOSUI2Nova", "MoOSUI2NovaLight"):
            state = self.state(scheme)
            seen.add(state["isDark"])
            self.assertTrue(state["doodles"], "no chat texture was found by name")
            for doodle in state["doodles"]:
                self.assertEqual(doodle["api"], state["software"], "the harness did not run on software")
                self.assertFalse(doodle["recolourable"])
                self.assertFalse(doodle["layer"], "a MultiEffect layer on the software scene graph draws nothing")
                self.assertEqual(doodle["drawsTexture"], state["isDark"],
                                 f"{scheme}: raw white strokes read only on a dark scheme; on a light "
                                 "one the texture and its marks must go together")
        if len(seen) != 2:
            self.skipTest("this machine's Qt did not apply both schemes, so one branch is unmeasured")


if __name__ == "__main__":
    unittest.main(verbosity=2)
