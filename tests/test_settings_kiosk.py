#!/usr/bin/env python3
"""Gate: the x86 System Settings pages MoOS hides stay hidden, and ARM keeps its remote desktop.

WHY THIS EXISTS
build.sh appends a KIOSK group to /etc/xdg/kdeglobals — `[KDE Control Module Restrictions]` —
which System Settings, its KRunner runner and kcmshell6 obey. Two pages are hidden on the x86
editions: kcm_fcitx5 (its input-method engine is removed) and kcm_krdpserver, KRDP's Remote
Desktop page, which stood beside MoOS's own Mo PC Remote page and opens RDP to the whole
network (the server moos-remote-guard switches off as foreign sharing). On moos-arm KRDP IS
MoOS's remote desktop, and build-arm.sh never runs build.sh.

Until now nothing in the repository ran that block: only the image build did. This test runs
the block itself (the append and its embedded gate) against a scratch kdeglobals, proves its
gate refuses a file that lacks a restriction, holds the image gate's list to the same pages,
and — where the host has the modules — measures that the group really hides the page.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build_files/build.sh"
BUILD_ARM = ROOT / "build_files/build-arm.sh"
IMAGE_GATE = ROOT / "build_files/verify_image_experience.py"
HIDDEN = ("kcm_fcitx5", "kcm_krdpserver")


def kiosk_block() -> str:
    text = BUILD.read_text(encoding="utf-8")
    start = text.index("# --- System Settings offers no page for the input-method engine")
    end = text.index("MOOSKIOSKGATE\n", text.index("<<'MOOSKIOSKGATE'", start)) + len("MOOSKIOSKGATE\n")
    return text[start:end]


def restricted(path: Path) -> dict[str, str]:
    group, found = None, {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            group = line
        elif group == "[KDE Control Module Restrictions]" and "=" in line:
            key, value = line.split("=", 1)
            found[key.strip()] = value.strip()
    return found


class TheKioskBlockRuns(unittest.TestCase):
    def run_block(self, kdeglobals: Path) -> subprocess.CompletedProcess:
        block = kiosk_block().replace("/etc/xdg/kdeglobals", str(kdeglobals))
        self.assertNotIn("/etc/xdg/kdeglobals", block)
        return subprocess.run(["bash", "-euo", "pipefail", "-c", block], capture_output=True,
                              text=True, timeout=60)

    def test_it_hides_both_pages_and_its_gate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            kdeglobals = Path(tmp) / "kdeglobals"
            kdeglobals.write_text("[General]\nColorScheme=MoOSUI2Dark\n", encoding="utf-8")
            done = self.run_block(kdeglobals)
            self.assertEqual(done.returncode, 0, done.stderr)
            found = restricted(kdeglobals)
            for kcm in HIDDEN:
                self.assertEqual(found.get(kcm), "false", kcm)
            self.assertIn("ColorScheme=MoOSUI2Dark", kdeglobals.read_text(encoding="utf-8"))
            # Idempotent: a second run appends nothing.
            before = kdeglobals.read_text(encoding="utf-8")
            self.assertEqual(self.run_block(kdeglobals).returncode, 0)
            self.assertEqual(kdeglobals.read_text(encoding="utf-8"), before)

    def test_its_gate_refuses_a_file_that_lacks_the_remote_desktop_restriction(self):
        """A group that already exists is not appended to: the gate must catch the gap."""
        with tempfile.TemporaryDirectory() as tmp:
            kdeglobals = Path(tmp) / "kdeglobals"
            kdeglobals.write_text("[KDE Control Module Restrictions]\nkcm_fcitx5=false\n",
                                  encoding="utf-8")
            done = self.run_block(kdeglobals)
            self.assertNotEqual(done.returncode, 0, "the build went on with KRDP's page visible")
            self.assertIn("kcm_krdpserver", done.stdout + done.stderr)


class EveryEditionIsHeldToIt(unittest.TestCase):
    def test_the_image_gate_checks_the_same_pages(self):
        code = IMAGE_GATE.read_text(encoding="utf-8")
        loop = re.search(r"for _kcm in \(([^)]*)\):\n    if list\(Path\(\"/usr\"\)\.glob\(", code)
        self.assertIsNotNone(loop, "the image gate's KIOSK check changed shape")
        self.assertEqual(set(re.findall(r'"(kcm_[a-z0-9_]+)"', loop.group(1))), set(HIDDEN))

    def test_arm_keeps_krdp(self):
        arm = BUILD_ARM.read_text(encoding="utf-8")
        self.assertNotIn("kcm_krdpserver=false", arm,
                         "on moos-arm KRDP is MoOS's own remote desktop; its page must stay")
        self.assertIn("krdp", arm, "the ARM image no longer installs KRDP — revisit this test")


class TheGroupReallyHidesThePage(unittest.TestCase):
    """Measured with the host's own modules, offscreen, with a private config and no bus."""

    def test_kcmshell_refuses_the_hidden_page_and_opens_the_others(self):
        plugins = Path("/usr/lib64/qt6/plugins/plasma/kcms/systemsettings")
        if shutil.which("kcmshell6") is None or not (plugins / "kcm_krdpserver.so").is_file() \
                or not (plugins / "kcm_mouse.so").is_file():
            self.skipTest("this machine has no kcmshell6 or no KRDP/mouse module to measure")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xdg = root / "xdg"
            xdg.mkdir()
            (root / "run").mkdir(mode=0o700)
            kdeglobals = xdg / "kdeglobals"
            kdeglobals.write_text("", encoding="utf-8")
            self.assertEqual(TheKioskBlockRuns.run_block(self, kdeglobals).returncode, 0)
            env = {"PATH": "/usr/bin:/bin", "HOME": str(root), "LANG": "C.UTF-8",
                   "XDG_RUNTIME_DIR": str(root / "run"), "XDG_CONFIG_DIRS": str(xdg),
                   "XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data"),
                   "XDG_CACHE_HOME": str(root / "cache"), "QT_QPA_PLATFORM": "offscreen",
                   "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root}/no-bus"}

            def smoke(kcm: str) -> int:
                return subprocess.run(["kcmshell6", "--smoke-test", kcm], env=env,
                                      capture_output=True, timeout=60).returncode

            self.assertNotEqual(smoke("kcm_krdpserver"), 0, "KRDP's page still opens")
            self.assertEqual(smoke("kcm_mouse"), 0, "the group hid a page it does not name")
            if (Path("/usr/lib64/qt6/plugins/plasma/kcms/systemsettings_qwidgets")
                    / "kcm_kwinscreenedges.so").is_file():
                self.assertEqual(smoke("kcm_kwinscreenedges"), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
