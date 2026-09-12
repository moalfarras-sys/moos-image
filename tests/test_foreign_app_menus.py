#!/usr/bin/env python3
"""Gate: Wine's internal tools stay out of MoOS menus.

The MoOS launcher's "All applications" showed ten Wine entries (Wine Boot, Wine
Configuration, Wine File, Wine Help, Wine OLE View, Wine Software Uninstaller,
Wine Wordpad, WineMine, …). A Windows program runs in MoOS by double-click through
moos-run-foreign and Bottles, so the image hides those entries and fails the build
if one is still visible. This also exercises the exact sed used, on real files.
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")


class WineMenuTests(unittest.TestCase):
    def block(self):
        match = re.search(r"    for _wine_entry in /usr/share/applications/wine-\*\.desktop; do\n(.*?)\n    done\n", BUILD, re.S)
        self.assertIsNotNone(match, "the Wine hide loop is missing from build.sh")
        return match.group(1)

    def test_build_hides_wine_tools_and_gates_it(self):
        self.block()
        self.assertIn("GATE FAIL: Wine tools are still visible in menus", BUILD)
        self.assertLess(BUILD.index('dnf5 -y install "${_core_power[@]}"'),
                        BUILD.index("for _wine_entry in /usr/share/applications/wine-*.desktop"))

    def test_the_same_commands_hide_real_desktop_files(self):
        body = self.block()
        with tempfile.TemporaryDirectory() as tmp:
            apps = Path(tmp)
            (apps / "wine-winecfg.desktop").write_text("[Desktop Entry]\nName=Wine Configuration\nExec=winecfg\n")
            (apps / "wine-notepad.desktop").write_text("[Desktop Entry]\nName=Wine Notepad\nNoDisplay=false\n[Desktop Action x]\nName=x\n")
            script = "for _wine_entry in " + str(apps) + "/wine-*.desktop; do\n" + body + "\ndone\n"
            subprocess.run(["bash", "-c", script], check=True)
            for entry in apps.glob("wine-*.desktop"):
                text = entry.read_text()
                self.assertEqual(text.count("NoDisplay=true"), 1, text)
                self.assertTrue(text.startswith("[Desktop Entry]\nNoDisplay=true") or "NoDisplay=true" in text)
            self.assertIn("[Desktop Action x]", (apps / "wine-notepad.desktop").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
