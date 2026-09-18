#!/usr/bin/env python3
"""Gate: station pointer review is closed-loop, or it is not evidence.

WHY

`scripts/station/pointer.py` exists because open-loop pointer input lied. The
station review of 2026-09-17 recorded four items (Hub controls, removing a
widget, App Drop, a dismissed authentication) as untested because
`ydotool mousemove --absolute` "landed the click elsewhere", and a measurement on
2026-09-18 found the cursor still in the corner after every absolute request —
so a script that clicks blind can report a pass for a click that never touched
the thing. The tool therefore asks KWin where the pointer IS, walks it there with
relative moves, and only then clicks.

This gate keeps that shape (no live session needed): the module must import, a
click must be preceded by a verified move, absolute positioning must stay out,
and the owner's clipboard — the channel the answer comes back on — must be put
back.
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/station/pointer.py"


class StationPointer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = TOOL.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def method(self, name: str) -> ast.FunctionDef:
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        self.fail(f"{name} is missing from {TOOL.name}")

    def test_it_is_executable_and_parses(self):
        self.assertTrue(TOOL.exists(), "the station's pointer tool must be in the repository")
        self.assertTrue(TOOL.stat().st_mode & 0o111, "it is run directly on the station")

    def test_the_compositor_is_the_witness_for_where_the_pointer_is(self):
        where = ast.unparse(self.method("where"))
        self.assertIn("workspace.cursorPos", self.source,
                      "KWin itself reports the position; nothing else is trusted")
        self.assertIn("org.kde.kwin.Scripting.loadScript", where)
        self.assertIn("MOOS-CURSOR", where)

    def test_a_move_is_verified_and_gives_up_instead_of_guessing(self):
        move = ast.unparse(self.method("move"))
        self.assertIn("self.where()", move, "measure after every nudge")
        self.assertIn("tolerance", move)
        self.assertIn("SystemExit", move,
                      "an unreachable target must fail loudly, never silently click")

    def test_absolute_positioning_is_not_used(self):
        # The docstring explains WHY absolute moves are wrong; read the calls themselves.
        commands = [[element.value for element in node.elts
                     if isinstance(element, ast.Constant) and isinstance(element.value, str)]
                    for node in ast.walk(self.tree) if isinstance(node, ast.List)]
        ydotool = [command for command in commands if command[:1] == ["ydotool"]]
        self.assertTrue(ydotool, "the tool drives ydotool")
        for command in ydotool:
            for forbidden in ("--absolute", "-a"):
                self.assertNotIn(forbidden, command,
                                 "absolute ydotool moves do not land on this screen")

    def test_the_owners_clipboard_is_put_back(self):
        restore = ast.unparse(self.method("restore"))
        self.assertIn("setClipboardContents", restore)
        self.assertIn("unloadScript", restore, "the probe script is removed from KWin too")
        main = ast.unparse(self.method("main"))
        self.assertIn("finally", main, "restore even when a step fails")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(StationPointer))
    raise SystemExit(0 if result.wasSuccessful() else 1)
