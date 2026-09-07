#!/usr/bin/env python3
"""KDE and GTK windows must put their buttons on the same side.

MEASURED ON THE LIVE SESSION (2026-09-06):

    kwinrc  org.kde.kdecoration2  ButtonsOnLeft = XIA, ButtonsOnRight = (empty)
    gsettings org.gnome.desktop.wm.preferences button-layout
                                              = 'appmenu:minimize,maximize,close'
    xdg Settings portal, same key             = 'appmenu:minimize,maximize,close'

So every server-side-decorated window (Dolphin, Konsole, the Mo apps) put
close/minimise/maximise on the LEFT, macOS-style, while every client-side-
decorated app — all GTK, and every Flatpak, which learns the layout from the
portal — kept GNOME's default and put them on the RIGHT. Half the desktop
disagreed with the other half, and nothing noticed because each half was
internally consistent.

`moos-theme` already owned BOTH sides: it writes kwinrc's ButtonsOnLeft and it
writes the org.gnome.desktop.interface GSettings keys. It simply never wrote
this one. That is the whole bug, and this gate is the thing that would have
caught it.

XIA is close, minimise, maximise. The GTK string puts left of the colon on the
left, so XIA's exact mirror is 'close,minimize,maximize:' with nothing after it.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
THEME = (REPO / "system_files/usr/bin/moos-theme").read_text(encoding="utf-8")
KWINRC = (REPO / "system_files/etc/xdg/kwinrc").read_text(encoding="utf-8")

# KDE single-letter button codes (kwin src/kcms/decoration/utils.cpp).
KDE_TO_GTK = {"X": "close", "I": "minimize", "A": "maximize"}


def code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


class ButtonsAgree(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.theme = code(THEME)
        cls.kwinrc = code(KWINRC)

    def kde_left(self) -> str:
        m = re.search(r"^ButtonsOnLeft=(\S*)$", self.kwinrc, re.M)
        self.assertIsNotNone(m, "the shipped kwinrc must declare ButtonsOnLeft")
        return m.group(1)

    def gtk_layout(self) -> str:
        m = re.search(
            r"gsettings set org\.gnome\.desktop\.wm\.preferences button-layout\s*\\?\s*\n?\s*'([^']*)'",
            self.theme)
        self.assertIsNotNone(
            m, "moos-theme must write org.gnome.desktop.wm.preferences "
               "button-layout; without it GTK and Flatpak apps keep GNOME's "
               "right-hand default while KDE windows use the left")
        return m.group(1)

    def test_the_two_layouts_are_the_same_arrangement(self) -> None:
        expected = ",".join(KDE_TO_GTK[c] for c in self.kde_left()) + ":"
        self.assertEqual(
            self.gtk_layout(), expected,
            "the GTK layout must mirror kwinrc's ButtonsOnLeft exactly")

    def test_nothing_is_left_on_the_right_in_either_system(self) -> None:
        """MoOS puts everything on the left; a stray right-hand button in one
        system only is precisely the split this gate exists to stop."""
        m = re.search(r"^ButtonsOnRight=(\S*)$", self.kwinrc, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "", "kwinrc must keep the right side empty")
        self.assertTrue(self.gtk_layout().endswith(":"),
                        "the GTK layout must end at the colon — nothing on the right")

    def test_the_kde_side_is_still_written_by_the_same_owner(self) -> None:
        """One writer for both halves, or they drift again."""
        self.assertIn("--key ButtonsOnLeft XIA", self.theme)
        self.assertIn("org.gnome.desktop.wm.preferences button-layout", self.theme)


if __name__ == "__main__":
    unittest.main(verbosity=2)
