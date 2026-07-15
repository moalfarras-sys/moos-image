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
    def test_any_foreign_look_resolves_to_the_one_moos_look(self) -> None:
        """MoOS ships ONE look now, in a light half and a dark half.

        This test used to assert the opposite: that a user who had rolled back to the older MoOS
        UI generation was PRESERVED there. That behaviour was right while UI1 was installed, and it
        became a trap the moment it was not — Plasma does not error on a Global Theme that is
        missing from the disk, it silently serves Breeze. So the resolver must now pull every look
        that is not one of MoOS's two halves onto the dark half, which is what the image ships.
        """
        text = APPLY.read_text(encoding="utf-8")
        resolver = function(text, "target_lnf")
        harness = f"""
set -uo pipefail
DARK_LNF=org.moos.ui2
LIGHT_LNF=org.moos.ui2.light
marker=/definitely/not/present
current_lookandfeel() {{ printf '%s\\n' "$CURRENT"; }}
{resolver}
target_lnf "$1" "$2"
"""
        cases = {
            # the two halves stay where they are
            ("org.moos.ui2", "true"): "org.moos.ui2",
            ("org.moos.ui2.light", "true"): "org.moos.ui2.light",
            ("org.moos.ui2", "false"): "org.moos.ui2",
            ("org.moos.ui2.light", "false"): "org.moos.ui2.light",
            # the deleted generations, and anything else, land on the dark half — NOT on a theme
            # that is no longer installed
            ("org.moos.ui", "true"): "org.moos.ui2",
            ("org.moos.ui.light", "true"): "org.moos.ui2",
            ("org.moos.nova", "true"): "org.moos.ui2",
            ("org.kde.breezedark.desktop", "true"): "org.moos.ui2",
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
        # No generation but this one may be a TARGET…
        self.assertNotIn("UI1_DARK_LNF", text)
        self.assertNotIn("UI1_LIGHT_LNF", text)
        # …but the old desk clock must still be REMOVABLE, or a user who has one keeps it forever
        # on a desktop that also has the new dashboard.
        self.assertIn("other_widget=org.moos.nova.deskclock", text)
        self.assertIn("d.addWidget(TARGET, 360, 70, TARGET_WIDTH, TARGET_HEIGHT)", text)
        # The dashboard is top-left and the icons must grow from the RIGHT, or they land under it —
        # which on the ISO is the "Install MoOS" icon with its label swallowed by the clock.
        self.assertIn('d.writeConfig("alignment", "1")', text)

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
        # The bound that matters is on the RUN (TimeoutStartSec), never on the RATE.
        # A path-triggered unit must not be rate-limited: Plasma rewrites kdeglobals
        # several times in the first seconds of a session, so the old 5-per-60s limit
        # turned an ordinary login into failed(start-limit-hit) — and systemd fails the
        # .path unit along with it, so the watch was dead for the rest of the session
        # and the sunrise/sunset supplements stopped following the theme. Reproduced on
        # the maintainer's machine with eight touches of kdeglobals. Recursion is what
        # the limit was really guarding against, and that is guaranteed structurally
        # below — sync_auto never writes kdeglobals — not by counting starts.
        self.assertIn("StartLimitIntervalSec=0", service)
        self.assertNotIn("StartLimitBurst", service)
        self.assertIn("TimeoutStartSec=45s", service)
        self.assertIn("systemctl --global enable moos-theme-sync.path", build)
        self.assertIn("systemd-analyze verify", build)

        # `auto` must ARRIVE on UI2, not merely arm the switch. sync_auto refuses to touch a
        # look that is not already a UI2 half (by design — see below), so without a bootstrap
        # the command pins the targets, prints "auto", and leaves a UI1 desktop on UI1 until
        # the next sunrise: success reported for doing nothing. It did exactly that on the
        # maintainer's machine.
        # The branch ends at a ';;' on its own line at the case-arm indent; the ';;' inside
        # the bootstrap's own case statement are deeper and inline, so they do not match.
        auto_branch = switch.split("\n    auto)")[1].split("\n        ;;")[0]
        self.assertIn('apply "$DARK_LNF"', auto_branch)

        # …and it must arm the switch AFTER that bootstrap, never before. plasma-apply-
        # lookandfeel CLEARS AutomaticLookAndFeel — applying a Global Theme by hand is
        # Plasma's own signal that the user took manual control — so arming first arms
        # nothing: the bootstrap disarms it one line later and `auto` leaves the switch OFF
        # while printing success. Measured exactly that way on the maintainer's machine.
        # Ordering is invisible to a "does the file contain X" gate, so assert the order.
        self.assertLess(
            auto_branch.index('apply "$DARK_LNF"'),
            auto_branch.index("AutomaticLookAndFeel true"),
            "moos-theme auto arms the day/night switch before its bootstrap apply, "
            "which clears it — the switch ends up off",
        )

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
