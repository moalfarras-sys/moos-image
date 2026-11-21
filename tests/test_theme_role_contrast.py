#!/usr/bin/env python3
"""Every MoOS look draws its text roles at a readable contrast.

Measured 2026-11-22: light families drew KDE links/visited/active text in
bright accent tones (Arena Light 2.38:1, Daylight visited 2.56:1, Forge Light
visited 2.25:1), Selection's alternate rows put selected ink at 3.0:1,
terminal ANSI colours fell to 2.4:1 and libadwaita's accent carried light ink
at 2.98:1 in Daylight. The generators now move a failing role in lightness
only (generate_moos_ui2.legible). This gate reads the SHIPPED files:

* KDE schemes: each text role (Normal, Inactive, Active, Link, Visited,
  Negative, Neutral, Positive) >= 4.5:1 on its group's Normal and Alternate
  background; DecorationFocus/Hover >= 3:1; selected ink >= 4.5:1 on both
  Selection backgrounds.
* Konsole: ANSI 1-6 normal and intense >= 4.5:1 on the terminal background.
* GTK/libadwaita: every fg/bg pair, accent ink on accent, accent-as-text on
  view and window >= 4.5:1.

Negative controls: the retired values fail the same predicate, and legible()
returns a passing role byte-identical.
"""
import configparser
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files/usr/share"
sys.path.insert(0, str(ROOT / "artwork"))
import generate_moos_ui2 as gen  # noqa: E402

TEXT = ("ForegroundNormal", "ForegroundInactive", "ForegroundActive", "ForegroundLink",
        "ForegroundVisited", "ForegroundNegative", "ForegroundNeutral", "ForegroundPositive")
MARKS = ("DecorationFocus", "DecorationHover")
GTK_PAIRS = (("window_fg_color", "window_bg_color"), ("view_fg_color", "view_bg_color"),
             ("card_fg_color", "card_bg_color"), ("popover_fg_color", "popover_bg_color"),
             ("headerbar_fg_color", "headerbar_bg_color"), ("dialog_fg_color", "dialog_bg_color"),
             ("sidebar_fg_color", "sidebar_bg_color"), ("accent_fg_color", "accent_bg_color"),
             ("accent_color", "view_bg_color"), ("accent_color", "window_bg_color"),
             ("success_color", "view_bg_color"), ("warning_color", "view_bg_color"),
             ("error_color", "view_bg_color"))


def hexed(value: str) -> str:
    parts = [int(p) for p in value.split(",")[:3]]
    return "#" + "".join(f"{p:02X}" for p in parts)


def ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def scheme_failures(parser: configparser.ConfigParser) -> list[str]:
    failures = []
    for section in parser.sections():
        if not section.startswith("Colors:") or section == "Colors:Selection":
            continue
        group = parser[section]
        grounds = [hexed(group[k]) for k in ("BackgroundNormal", "BackgroundAlternate") if k in group]
        for role, need in [(r, 4.5) for r in TEXT] + [(m, 3.0) for m in MARKS]:
            if role not in group:
                continue
            for ground in grounds:
                ratio = gen.contrast_ratio(hexed(group[role]), ground)
                if ratio < need:
                    failures.append(f"[{section}] {role} {ratio:.2f} < {need}")
    selection = parser["Colors:Selection"]
    ink = hexed(selection["ForegroundNormal"])
    for key in ("BackgroundNormal", "BackgroundAlternate"):
        ratio = gen.contrast_ratio(ink, hexed(selection[key]))
        if ratio < 4.5:
            failures.append(f"[Selection] ink on {key} {ratio:.2f}")
    return failures


class ThemeRoleContrast(unittest.TestCase):
    def test_every_kde_scheme_role_reads(self):
        schemes = sorted((SHARE / "color-schemes").glob("MoOSUI2*.colors"))
        self.assertGreaterEqual(len(schemes), 18)
        for path in schemes:
            with self.subTest(scheme=path.stem):
                self.assertEqual(scheme_failures(ini(path)), [])
        for style in sorted((SHARE / "plasma/desktoptheme").glob("MoOSUI2*/colors")):
            with self.subTest(style=style.parent.name):
                self.assertEqual(scheme_failures(ini(style)), [])

    def test_every_terminal_ansi_colour_reads(self):
        for path in sorted((SHARE / "konsole").glob("MoOSUI2*.colorscheme")):
            scheme = ini(path)
            ground = hexed(scheme["Background"]["Color"])
            for number in range(1, 7):
                for suffix in ("", "Intense"):
                    with self.subTest(scheme=path.stem, colour=f"{number}{suffix}"):
                        ink = hexed(scheme[f"Color{number}{suffix}"]["Color"])
                        self.assertGreaterEqual(gen.contrast_ratio(ink, ground), 4.5)

    def test_every_gtk_palette_pair_reads(self):
        sheets = sorted((SHARE / "moos/gtk").glob("moos-ui2-*.css"))
        self.assertGreaterEqual(len(sheets), 16)
        for path in sheets:
            colours = dict(re.findall(r"@define-color\s+(\w+)\s+(#[0-9A-Fa-f]{6})\s*;",
                                      path.read_text(encoding="utf-8")))
            for ink, ground in GTK_PAIRS:
                if ink in colours and ground in colours:
                    with self.subTest(sheet=path.name, pair=f"{ink}/{ground}"):
                        self.assertGreaterEqual(gen.contrast_ratio(colours[ink], colours[ground]), 4.5)

    def test_negative_control_the_retired_roles_fail_the_same_predicate(self):
        daylight = ini(SHARE / "color-schemes/MoOSUI2Daylight.colors")
        daylight["Colors:View"]["ForegroundVisited"] = "8,145,178"         # retired cyan
        daylight["Colors:Selection"]["BackgroundAlternate"] = "79,70,229"  # retired alternate
        failures = scheme_failures(daylight)
        self.assertTrue(any("ForegroundVisited" in f for f in failures), failures)
        self.assertTrue(any("BackgroundAlternate" in f for f in failures), failures)
        self.assertLess(gen.contrast_ratio("#CCDEF1", "#0284C7"), 4.5)   # retired GTK accent ink

    def test_legible_keeps_passing_roles_and_hue(self):
        self.assertEqual(gen.legible("#17302E", ("#CCDEF1",), 4.5), "#17302E")
        moved = gen.legible("#0891B2", ("#CCDEF1", "#D0E0F3"), 4.5)
        self.assertNotEqual(moved, "#0891B2")
        self.assertGreaterEqual(gen.contrast_ratio(moved, "#CCDEF1"), 4.5)
        import colorsys
        def hue(value):
            v = value.lstrip("#")
            return colorsys.rgb_to_hls(*(int(v[i:i + 2], 16) / 255 for i in (0, 2, 4)))[0]
        self.assertAlmostEqual(hue(moved), hue("#0891B2"), delta=0.02)


if __name__ == "__main__":
    unittest.main()
