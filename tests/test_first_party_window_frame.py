#!/usr/bin/env python3
"""Every first-party MoOS window uses the system frame, never its own.

THE BUG THIS PREVENTS, observed on the live session 2026-09-06: VS Code draws
its own title bar and placed its own close/restore/minimise controls at the LEFT,
on top of its own menu bar. Measured from a 4x crop of the title strip, "File"
was entirely hidden and "Ed" of "Edit" was covered, leaving the menu reading
"it  Selection  View  Go  Run  Terminal  Help". The top-right corner held only
VS Code's editor-layout toggles, confirming the controls were on the left.

MoOS puts window buttons on the left by design (kwinrc ButtonsOnLeft=XIA,
ButtonsOnRight empty — the macOS arrangement). That is only safe as long as the
compositor owns the title bar: KWin reserves the strip, so nothing in the client
area can be underneath it. An application that draws its OWN title bar has to
reserve that space itself, and an app written for right-hand buttons does not.

So the contract is not "buttons on the left is fine". It is: MoOS's own windows
must never take the title bar away from KWin. A first-party app that went
frameless would reintroduce exactly the collision the owner reported, on a
surface MoOS controls completely and has no excuse for.

Third-party apps are handled per app — VS Code by setting
`window.titleBarStyle: native` so it hands the title bar back.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APPS = REPO / "system_files/usr/share/moos/apps"

# Qt window flags that take the title bar away from the compositor.
FORBIDDEN_FLAGS = (
    "FramelessWindowHint",
    "Qt.CustomizeWindowHint",
    "Qt.NoTitleBarBackgroundHint",
)


def qml_code(text: str) -> str:
    """Strip comments so the prose above cannot satisfy or trip a check."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(l for l in without_blocks.splitlines()
                     if not l.lstrip().startswith("//"))


def windows():
    for main in sorted(APPS.glob("*/main.qml")):
        yield main.parent.name, qml_code(main.read_text(encoding="utf-8"))


class FirstPartyWindowsKeepTheSystemFrame(unittest.TestCase):
    def test_there_are_windows_to_check(self) -> None:
        found = [name for name, _ in windows()]
        self.assertTrue(found, "no first-party app QML was found to check")
        # If an app is added, it is covered automatically; this only guards
        # against the glob silently matching nothing after a directory move.
        self.assertGreaterEqual(len(found), 5, f"only found {found}")

    def test_no_first_party_window_goes_frameless(self) -> None:
        for name, src in windows():
            with self.subTest(app=name):
                for flag in FORBIDDEN_FLAGS:
                    self.assertNotIn(
                        flag, src,
                        f"{name} takes the title bar from KWin. MoOS puts the "
                        f"window buttons on the LEFT, and an app that draws its "
                        f"own title bar must reserve that strip itself — which "
                        f"is exactly how VS Code ended up covering its own File "
                        f"and Edit menus.")

    def test_every_window_is_a_real_ApplicationWindow(self) -> None:
        """A plain Window/Item root would also lose the decoration."""
        for name, src in windows():
            with self.subTest(app=name):
                self.assertRegex(
                    src, r"\b(?:Kirigami\.|QQC2\.)?ApplicationWindow\s*\{",
                    f"{name} must root in ApplicationWindow so the compositor "
                    f"owns its frame")


if __name__ == "__main__":
    unittest.main(verbosity=2)
