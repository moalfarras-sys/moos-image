#!/usr/bin/env python3
"""Behavioural/static safety gate for MoOS theme transitions."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"
SWITCH = ROOT / "system_files/usr/bin/moos-theme"
PATH_UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-theme-sync.path"
SERVICE_UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-theme-sync.service"


def function(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^{re.escape(name)}\(\) \{{.*?^\}}$", text)
    if not match:
        raise AssertionError(f"could not extract {name}()")
    return match.group(0)


class TestMoOSThemeSafety(unittest.TestCase):
    def test_completed_ui1_rollback_remains_in_ui1_during_self_heal(self) -> None:
        text = APPLY.read_text(encoding="utf-8")
        resolver = function(text, "target_lnf")
        harness = f"""
set -uo pipefail
DARK_LNF=org.moos.ui2
LIGHT_LNF=org.moos.ui2.light
UI1_DARK_LNF=org.moos.ui
UI1_LIGHT_LNF=org.moos.ui.light
marker=/definitely/not/present
current_lookandfeel() {{ printf '%s\\n' "$CURRENT"; }}
{resolver}
target_lnf "$1" "$2"
"""
        cases = {
            ("org.moos.ui", "false"): "org.moos.ui2",
            ("org.moos.ui.light", "false"): "org.moos.ui2.light",
            ("org.moos.ui", "true"): "org.moos.ui",
            ("org.moos.ui.light", "true"): "org.moos.ui.light",
            ("org.moos.ui2", "true"): "org.moos.ui2",
            ("org.moos.ui2.light", "true"): "org.moos.ui2.light",
            ("org.example.foreign", "true"): "org.moos.ui2",
        }
        for (current, completed), expected in cases.items():
            with self.subTest(current=current, completed=completed):
                result = subprocess.run(
                    ["bash", "-c", harness, "test", current, completed],
                    check=True,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(result.stdout.strip(), expected)

        self.assertIn("migration_completed=true", text)
        self.assertIn(
            'target_lnf "$(current_lookandfeel)" "$migration_completed"', text
        )
        for token in (
            '"$UI1_DARK_LNF")',
            '"$UI1_LIGHT_LNF")',
            "want_widget=org.moos.nova.deskclock",
            "other_widget=org.moos.ui2.dashboard",
            "d.addWidget(TARGET, 80, 70, TARGET_WIDTH, TARGET_HEIGHT)",
        ):
            self.assertIn(token, text)

    def test_automatic_switch_has_bounded_non_recursive_supplement_sync(self) -> None:
        switch = SWITCH.read_text(encoding="utf-8")
        path = PATH_UNIT.read_text(encoding="utf-8")
        service = SERVICE_UNIT.read_text(encoding="utf-8")
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

        self.assertIn("PathChanged=%h/.config/kdeglobals", path)
        self.assertIn("WantedBy=plasma-workspace.target", path)
        self.assertIn("PartOf=plasma-workspace.target", path)
        self.assertIn("ExecStart=/usr/bin/moos-theme sync-auto", service)
        self.assertIn("Restart=on-failure", service)
        self.assertIn("StartLimitIntervalSec=60s", service)
        self.assertIn("StartLimitBurst=5", service)
        self.assertIn("TimeoutStartSec=45s", service)
        self.assertIn("systemctl --global enable moos-theme-sync.path", build)
        self.assertIn("systemd-analyze verify", build)

        sync = function(switch, "sync_auto")
        supplements = function(switch, "apply_supplements")
        self.assertNotIn("plasma-apply-lookandfeel", sync)
        self.assertNotIn("kwriteconfig6 --file kdeglobals", sync)
        self.assertIn('apply_supplements false', sync)
        self.assertIn('AutomaticLookAndFeel', sync)
        self.assertIn('automatic_after', sync)
        self.assertIn('automatic_supplements_complete', sync)
        self.assertIn('[ -d "/usr/share/plasma/look-and-feel/$lnf" ]', sync)

        for token in (
            "plasma-apply-wallpaperimage",
            "DefaultProfile",
            "gtk-application-prefer-dark-theme",
            "org.gnome.desktop.interface color-scheme",
            "WallpaperPlugin",
        ):
            self.assertIn(token, supplements)
        self.assertNotIn("kdeglobals", supplements)

        auto_case = switch[switch.index("    auto)"):switch.index("    sync-auto)")]
        self.assertIn("systemctl --user start moos-theme-sync.path", auto_case)
        self.assertIn("sync_auto", auto_case)
        self.assertIn("moos-theme.lock", switch)
        self.assertIn("moos-theme.lock", APPLY.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
