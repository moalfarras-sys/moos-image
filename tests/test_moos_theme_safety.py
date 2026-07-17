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
        """MoOS now ships a FAMILY of looks on one engine: the Graphite/Tidal base pair plus
        the org.moos.ui2.* members (Nova, Amethyst, Midnight, Aurora). A member the user picked
        is a durable choice and is PRESERVED. Everything that is NOT a current MoOS look — the
        DELETED old generations (org.moos.nova, org.moos.ui, which are a different, top-level
        namespace), Breeze, any foreign theme — must still resolve to the dark half, because
        Plasma does not error on a missing Global Theme, it silently serves Breeze.
        """
        text = APPLY.read_text(encoding="utf-8")
        resolver = function(text, "target_lnf")
        harness = f"""
set -uo pipefail
DARK_LNF=org.moos.ui2
LIGHT_LNF=org.moos.ui2.light
NOVA_LNF=org.moos.ui2.nova
AMETHYST_LNF=org.moos.ui2.amethyst
MIDNIGHT_LNF=org.moos.ui2.midnight
AURORA_LNF=org.moos.ui2.aurora
marker=/definitely/not/present
current_lookandfeel() {{ printf '%s\\n' "$CURRENT"; }}
{resolver}
target_lnf "$1" "$2"
"""
        cases = {
            # the two base halves stay where they are
            ("org.moos.ui2", "true"): "org.moos.ui2",
            ("org.moos.ui2.light", "true"): "org.moos.ui2.light",
            ("org.moos.ui2", "false"): "org.moos.ui2",
            ("org.moos.ui2.light", "false"): "org.moos.ui2.light",
            # a chosen family member is a durable choice — PRESERVED, not reset to dark
            ("org.moos.ui2.nova", "true"): "org.moos.ui2.nova",
            ("org.moos.ui2.amethyst", "false"): "org.moos.ui2.amethyst",
            ("org.moos.ui2.midnight", "true"): "org.moos.ui2.midnight",
            ("org.moos.ui2.aurora", "true"): "org.moos.ui2.aurora",
            # the DELETED old generations (top-level namespace), and anything else, land on the
            # dark half — NOT on a theme that is no longer installed
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
        # …but the widget-era dashboards must still be REMOVABLE, or a user who has
        # one keeps it forever, drawing on top of the icons, on a desktop whose bento
        # now lives inside the wallpaper scene.
        self.assertIn('"org.moos.nova.deskclock"', text)
        self.assertIn('"org.moos.ui2.dashboard"', text)
        self.assertIn('d.wallpaperPlugin = "org.moos.ui2.wallpaper"', text)
        # addWidget placement is FORBIDDEN: as a desktop applet the bento always drew
        # over the Folder View icons — every coordinate collides with some icon layout.
        self.assertNotIn("d.addWidget(", text)
        # The icons grow from the RIGHT, opposite the bento's top-left corner of the scene.
        self.assertIn('d.writeConfig("alignment", "1")', text)

    def test_automatic_switch_has_bounded_non_recursive_supplement_sync(self) -> None:
        switch = SWITCH.read_text(encoding="utf-8")
        path = PATH_UNIT.read_text(encoding="utf-8")
        service = SERVICE_UNIT.read_text(encoding="utf-8")
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

        self.assertIn("PathChanged=%h/.config/kdeglobals", path)
        self.assertIn("WantedBy=plasma-workspace.target", path)
        self.assertIn("PartOf=plasma-workspace.target", path)
        # `reconcile`, not the old `sync-auto`: kdeglobals changes on EVERY Global
        # Theme Apply, not only the sunrise/sunset switch. LookAndFeelManager carries
        # colours and decoration but never the MoOS wallpaper scene, Konsole, GTK or
        # the lock screen, so a GUI pick of e.g. "MoOS Nova" stranded Nova's colours on
        # the OLD wallpaper (measured live). `reconcile` delegates to sync_auto in
        # automatic mode and otherwise applies those missing supplements.
        self.assertIn("ExecStart=/usr/bin/moos-theme reconcile", service)
        self.assertIn("reconcile()", switch)
        # It must carry the MANUAL family, not only the two auto halves, or a GUI pick
        # of Nova/Amethyst/Midnight/Aurora still strands the wallpaper.
        reconcile_body = switch.split("reconcile() {", 1)[1].split("\n}\n", 1)[0]
        for fam in ("NOVA_LNF", "AMETHYST_LNF", "MIDNIGHT_LNF", "AURORA_LNF"):
            self.assertIn(fam, reconcile_body)
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
        self.assertIn('apply_supplements', sync)
        self.assertIn('AutomaticLookAndFeel', sync)
        self.assertIn('automatic_after', sync)
        self.assertIn('automatic_supplements_complete', sync)
        self.assertIn('[ -d "/usr/share/plasma/look-and-feel/$lnf" ]', sync)

        # reconcile is the path unit's entry point and fires on Plasma's burst of
        # kdeglobals writes at login. It MUST NOT write kdeglobals itself or it
        # would re-arm the very watch that triggered it — an unbounded loop. It is
        # loop-safe structurally: it only reads, delegates to sync_auto, and calls
        # apply_supplements (both already proven kdeglobals-clean above).
        recon = function(switch, "reconcile")
        self.assertNotIn("kwriteconfig6 --file kdeglobals", recon)
        self.assertIn("apply_supplements", recon)
        self.assertIn("automatic_supplements_complete", recon)
        self.assertIn("sync_auto", recon)
        self.assertIn('[ -d "/usr/share/plasma/look-and-feel/$lnf" ]', recon)

        for token in (
            # The desktop wallpaper is the MoOS scene plugin, applied per
            # containment; plasma-apply-wallpaperimage is FORBIDDEN because it
            # forces org.kde.image back and erases the dashboard bento.
            "apply_desktop_scene",
            "DefaultProfile",
            "gtk-application-prefer-dark-theme",
            "org.gnome.desktop.interface color-scheme",
            "WallpaperPlugin",
        ):
            self.assertIn(token, supplements)
        self.assertNotIn("plasma-apply-wallpaperimage", supplements)
        self.assertNotIn("kdeglobals", supplements)

        auto_case = switch[switch.index("    auto)"):switch.index("    sync-auto)")]
        self.assertIn("systemctl --user start moos-theme-sync.path", auto_case)
        self.assertIn("sync_auto", auto_case)
        self.assertIn("moos-theme.lock", switch)
        self.assertIn("moos-theme.lock", APPLY.read_text(encoding="utf-8"))

    def test_every_family_has_a_matched_light_and_dark_sibling(self) -> None:
        """The owner's rule: every theme is a light+dark pair. Assert each family
        ships BOTH complete look-and-feel package sets, that the light scheme is
        genuinely light and the dark scheme genuinely dark (a light theme whose
        window is dark is the "no light theme" bug), and that moos-theme can drive
        each light id and toggle any family by the ".light" suffix rule."""
        share = ROOT / "system_files/usr/share"
        switch = SWITCH.read_text(encoding="utf-8")

        def window_bg_sum(scheme_style: str) -> int:
            text = (share / "color-schemes" / f"{scheme_style}.colors").read_text(encoding="utf-8")
            m = re.search(r"\[Colors:Window\][^\[]*?BackgroundNormal=(\d+),(\d+),(\d+)", text, re.S)
            self.assertIsNotNone(m, f"{scheme_style}: no [Colors:Window] BackgroundNormal")
            return sum(int(g) for g in m.groups())

        # base pair + four accent families, each (dark_lnf, dark_style, light_lnf, light_style)
        families = {
            "base":     ("org.moos.ui2",          "MoOSUI2Dark",     "org.moos.ui2.light",          "MoOSUI2Light"),
            "nova":     ("org.moos.ui2.nova",      "MoOSUI2Nova",     "org.moos.ui2.nova.light",     "MoOSUI2NovaLight"),
            "amethyst": ("org.moos.ui2.amethyst",  "MoOSUI2Amethyst", "org.moos.ui2.amethyst.light", "MoOSUI2AmethystLight"),
            "aurora":   ("org.moos.ui2.aurora",    "MoOSUI2Aurora",   "org.moos.ui2.aurora.light",   "MoOSUI2AuroraLight"),
            "midnight": ("org.moos.ui2.midnight",  "MoOSUI2Midnight", "org.moos.ui2.midnight.light", "MoOSUI2Daylight"),
        }
        for fam, (dark_lnf, dark_style, light_lnf, light_style) in families.items():
            for lnf in (dark_lnf, light_lnf):
                self.assertTrue((share / "plasma/look-and-feel" / lnf / "contents/defaults").is_file(),
                                f"{fam}: missing look-and-feel package {lnf}")
            for style in (dark_style, light_style):
                self.assertTrue((share / "color-schemes" / f"{style}.colors").is_file(),
                                f"{fam}: missing color scheme {style}")
            # light must read light, dark must read dark — the actual parity property
            self.assertGreater(window_bg_sum(light_style), 540,
                               f"{light_style} is not a LIGHT scheme (window bg too dark)")
            self.assertLess(window_bg_sum(dark_style), 320,
                            f"{dark_style} is not a DARK scheme (window bg too light)")
            # the accent families also ship desktoptheme/aurorae/wallpaper for both halves
            if fam not in ("base",):
                for style in (dark_style, light_style):
                    self.assertTrue((share / "plasma/desktoptheme" / style).is_dir(),
                                    f"{fam}: missing desktoptheme {style}")
                    self.assertTrue((share / "aurorae/themes" / style).is_dir(),
                                    f"{fam}: missing aurorae {style}")
                    self.assertTrue((share / "wallpapers" / style / "contents/screenshot.png").is_file(),
                                    f"{fam}: missing wallpaper {style}")
            # moos-theme must be able to apply the light id (a load_profile arm)
            self.assertIn(light_lnf, switch, f"moos-theme cannot drive {light_lnf}")
        # toggle flips ANY family by the ".light" suffix rule, in both directions
        self.assertIn('target="${cur%.light}"', switch)
        self.assertIn('target="${cur}.light"', switch)


if __name__ == "__main__":
    unittest.main(verbosity=2)
