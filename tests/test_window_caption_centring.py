#!/usr/bin/env python3
"""Every MoOS window caption is centred on its window and survives a dialog.

MEASURED, 2026-11-18, on the owner's Oracle desktop (1280x720 at 75 %, Arabic,
Bloom Light) and then in a private native KWin with
scripts/review/window-frames-native.py:

  * every caption sat half a button group off the window centre: +-36.5 logical
    px with the sixteen MoOS UI2 frames, +-68 px with Bloom, mirrored for RTL;
  * Bloom's 140 px TitleBorderLeft/Right left a 388 px window with no caption
    and elided "Open File — Documents" to two letters.

Aurorae v2 (aurorae 6.8.3 v2/decoration.cpp, positionButtons/updateCaption)
places the left button group at TitleEdgeLeft, the right group flush against
TitleEdgeRight, and centres the caption between `left.right + TitleBorderLeft`
and `right.left - TitleBorderRight` — between the groups, not in the window.
KDecoration (6.8.3 src/decorationbuttongroup.cpp) swaps the two lists for an
RTL session. A group is the sum of its button widths plus ButtonSpacing between
them; a spacer `_` is ExplicitButtonSpacer wide and is created disabled, so it
never takes a press from the title bar.

This gate evaluates that exact arithmetic for every shipped theme with the
shipped kwinrc buttons, in both directions and restored/maximized, and proves
that the same predicate refuses the measured old geometry. It is the static
half; the native capture above is the rendered half and remains review
evidence, not physical-display or touch acceptance.
"""
from __future__ import annotations

import configparser
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
THEMES = REPO / "system_files/usr/share/aurorae/themes"
KWINRC = REPO / "system_files/etc/xdg/kwinrc"

# Logical widths: a compact message box, a file dialog, an editor, a maximized desk.
WIDTHS = (380, 480, 720, 1707)
# The shortest caption room any MoOS frame may leave in a 380 px window.
MIN_ROOM_AT_380 = 80
WIDTH_KEYS = {"X": "ButtonWidthClose", "I": "ButtonWidthMinimize", "A": "ButtonWidthMaximizeRestore",
              "S": "ButtonWidthAlldesktops", "F": "ButtonWidthKeepabove", "B": "ButtonWidthKeepbelow",
              "L": "ButtonWidthShade", "H": "ButtonWidthHelp", "M": "ButtonWidthMenu", "N": "ButtonWidthAppMenu"}


def layout(path: Path) -> dict[str, float]:
    cfg = configparser.ConfigParser(interpolation=None, strict=False)
    cfg.optionxform = str
    cfg.read(path, encoding="utf-8")
    return {k: float(v) for k, v in cfg["Layout"].items()}


def kwin_buttons() -> tuple[str, str]:
    text = "\n".join(l for l in KWINRC.read_text(encoding="utf-8").splitlines()
                     if not l.lstrip().startswith("#"))
    group = text.split("[org.kde.kdecoration2]", 1)[1]
    left = re.search(r"^ButtonsOnLeft=(\S*)$", group, re.M).group(1)
    right = re.search(r"^ButtonsOnRight=(\S*)$", group, re.M).group(1)
    return left, right


def group_width(codes: str, lay: dict[str, float]) -> float:
    if not codes:
        return 0.0
    base = lay.get("ButtonWidth", 20.0)
    widths = [lay.get("ExplicitButtonSpacer", 10.0) if c == "_" else lay.get(WIDTH_KEYS.get(c, ""), base)
              for c in codes]
    return sum(widths) + lay.get("ButtonSpacing", 5.0) * (len(widths) - 1)


def caption(width: float, lay: dict[str, float], left: str, right: str, rtl: bool, maximized: bool):
    """(centre offset from the window centre, caption room) as aurorae v2 lays it out."""
    if rtl:
        left, right = right, left
    suffix = "Maximized" if maximized else ""
    edge_l = lay.get("TitleEdgeLeft" + suffix, 0.0 if maximized else 5.0)
    edge_r = lay.get("TitleEdgeRight" + suffix, 0.0 if maximized else 5.0)
    lo = edge_l + group_width(left, lay) + lay.get("TitleBorderLeft", 5.0)
    hi = width - edge_r - group_width(right, lay) - lay.get("TitleBorderRight", 5.0)
    return (lo + hi) / 2 - width / 2, hi - lo


def themes() -> list[Path]:
    found = sorted(p for p in THEMES.iterdir() if (p / "decoration.svg").is_file())
    return found


def violations(lay: dict[str, float], left: str, right: str) -> list[str]:
    found = []
    for rtl in (False, True):
        for maximized in (False, True):
            for width in WIDTHS:
                offset, room = caption(width, lay, left, right, rtl, maximized)
                where = f"{'RTL' if rtl else 'LTR'} {'maximized' if maximized else 'restored'} {width}px"
                if abs(offset) > 1.0:
                    found.append(f"{where}: caption {offset:+.1f} px off the window centre")
                if width == 380 and room < MIN_ROOM_AT_380:
                    found.append(f"{where}: only {room:.0f} px of caption room")
    return found


class CaptionsAreCentredAndPresent(unittest.TestCase):
    def test_every_shipped_frame_with_the_shipped_buttons(self) -> None:
        left, right = kwin_buttons()
        found = themes()
        self.assertGreaterEqual(len(found), 18, "the MoOS Aurorae themes were not found")
        for theme in found:
            with self.subTest(frame=theme.name):
                self.assertEqual(violations(layout(theme / f"{theme.name}rc"), left, right), [])

    def test_the_spacer_is_not_a_button(self) -> None:
        _left, right = kwin_buttons()
        self.assertTrue(right and set(right) == {"_"}, "the balancing side may hold spacers only")

    def test_predicate_refuses_the_measured_old_geometry(self) -> None:
        """The old shipped values must fail this exact predicate, or it proves nothing."""
        bloom = layout(THEMES / "MoOSUI2BloomLight/MoOSUI2BloomLightrc")
        ui2 = layout(THEMES / "MoOSUI2/MoOSUI2rc")
        old_bloom = dict(bloom, TitleBorderLeft=140.0, TitleBorderRight=140.0, TitleEdgeLeft=16.0,
                         TitleEdgeRight=16.0, ExplicitButtonSpacer=0.0)
        old_ui2 = dict(ui2, ExplicitButtonSpacer=8.0)
        # Old buttons (nothing on the right) with each old frame, as measured.
        self.assertAlmostEqual(caption(1048, old_bloom, "XIA", "", True, False)[0], -68.0)
        self.assertAlmostEqual(caption(728, old_ui2, "XIA", "", False, False)[0], 36.0)
        self.assertLess(caption(388, old_bloom, "XIA", "", True, False)[1], 0)
        self.assertTrue(any("caption room" in v for v in violations(old_bloom, "XIA", "")))
        self.assertTrue(any("off the window centre" in v for v in violations(old_bloom, "XIA", "")))
        self.assertTrue(violations(old_ui2, "XIA", ""))
        # New frames with the old empty right side are still off centre, and an
        # old 8 px spacer slot with the new buttons does not balance either.
        self.assertTrue(violations(ui2, "XIA", ""))
        self.assertTrue(violations(old_ui2, "XIA", "_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
