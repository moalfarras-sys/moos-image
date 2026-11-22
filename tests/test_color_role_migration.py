#!/usr/bin/env python3
"""Corrected colour roles reach existing desktops without touching personal ones.

KDE copies a scheme into kdeglobals and plasma-apply-colorscheme refuses to
re-apply the selected scheme, so a fixed .colors file alone changes nothing on
an existing desktop. /usr/libexec/moos-color-roles rewrites a key only while it
still holds the exact retired MoOS value. Executed against private
XDG_CONFIG_HOME trees with the native kwriteconfig6 and no session bus.
"""
import configparser
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/moos-color-roles"
TABLE = ROOT / "system_files/usr/share/moos/color-role-migrations.json"
SCHEMES = ROOT / "system_files/usr/share/color-schemes"


def read(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


class ColorRoleMigration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("kwriteconfig6"):
            raise unittest.SkipTest("native kwriteconfig6 unavailable on this runner")
        cls.table = json.loads(TABLE.read_text())

    def run_helper(self, home: Path, *extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DBUS", "XDG_", "WAYLAND", "DISPLAY"))}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                   MOOS_COLOR_ROLE_TABLE=str(TABLE))
        return subprocess.run(["python3", "-B", str(HELPER), "migrate", *extra], env=env,
                              capture_output=True, text=True, timeout=60)

    def old_desktop(self, home: Path, scheme: str, personal: dict | None = None) -> Path:
        roles = self.table["migrations"][0]["schemes"][scheme]
        current = read(SCHEMES / f"{scheme}.colors")
        lines = [f"[General]\nColorScheme={scheme}\n"]
        for section in current.sections():
            if not section.startswith("Colors:"):
                continue
            lines.append(f"\n[{section}]\n")
            for key, value in current[section].items():
                retired = roles.get(section, {}).get(key)
                value = retired[0] if retired else value
                if personal and (section, key) in personal:
                    value = personal[(section, key)]
                lines.append(f"{key}={value}\n")
        path = home / ".config/kdeglobals"
        path.parent.mkdir(parents=True)
        path.write_text("".join(lines))
        return path

    def test_retired_values_become_current_and_personal_ones_stay(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            personal = {("Colors:View", "ForegroundLink"): "1,2,3"}
            kdeglobals = self.old_desktop(home, "MoOSUI2Daylight", personal)
            result = self.run_helper(home)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            after = read(kdeglobals)
            shipped = read(SCHEMES / "MoOSUI2Daylight.colors")
            self.assertEqual(after["Colors:View"]["ForegroundVisited"],
                             shipped["Colors:View"]["ForegroundVisited"])
            self.assertEqual(after["Colors:Selection"]["BackgroundAlternate"],
                             shipped["Colors:Selection"]["BackgroundAlternate"])
            self.assertEqual(after["Colors:View"]["ForegroundLink"], "1,2,3", "a personal colour was rewritten")
            self.assertEqual(after["General"]["ColorScheme"], "MoOSUI2Daylight")
            again = self.run_helper(home)
            self.assertIn(" 0 role(s) updated", again.stdout)

    def test_another_scheme_and_a_foreign_scheme_are_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            kdeglobals = self.old_desktop(home, "MoOSUI2ArenaLight")
            text = kdeglobals.read_text().replace("ColorScheme=MoOSUI2ArenaLight", "ColorScheme=BreezeLight")
            kdeglobals.write_text(text)
            result = self.run_helper(home)
            self.assertEqual(result.returncode, 0)
            self.assertIn("not a MoOS scheme", result.stdout)
            self.assertEqual(kdeglobals.read_text(), text)

    def test_dry_run_reports_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            kdeglobals = self.old_desktop(home, "MoOSUI2ForgeLight")
            before = kdeglobals.read_text()
            result = self.run_helper(home, "--dry-run")
            self.assertEqual(result.returncode, 0)
            self.assertIn("would set kdeglobals", result.stdout)
            self.assertEqual(kdeglobals.read_text(), before)

    def test_the_table_records_only_real_changes_to_shipped_values(self):
        for scheme, sections in self.table["migrations"][0]["schemes"].items():
            shipped = read(SCHEMES / f"{scheme}.colors")
            for section, keys in sections.items():
                for key, (retired, current) in keys.items():
                    with self.subTest(scheme=scheme, role=f"{section}/{key}"):
                        self.assertNotEqual(retired, current)
                        self.assertEqual(shipped[section][key], current)


if __name__ == "__main__":
    unittest.main()
