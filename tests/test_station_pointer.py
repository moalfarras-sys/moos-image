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
import traceback
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/station/pointer.py"
spec = importlib.util.spec_from_file_location("station_pointer", TOOL)
pointer_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pointer_tool)
ACTUAL_BRIDGE = pointer_tool.bridge_available


class ClipboardSafety(unittest.TestCase):
    def setUp(self):
        dependency = patch.object(pointer_tool.shutil, "which", return_value="/usr/bin/wl-copy")
        dependency.start(); self.addCleanup(dependency.stop)
        bridge = patch.object(pointer_tool,"bridge_available",return_value=True)
        bridge.start(); self.addCleanup(bridge.stop)

    def test_plain_text_is_read_without_trimming(self):
        text = "  MOOS-CURSOR 1,2\nالعربية\n\n"
        replies = [subprocess.CompletedProcess([], 0, "text/plain\n"),
                   subprocess.CompletedProcess([], 0, text.encode())]
        with patch.object(pointer_tool.subprocess, "run", side_effect=replies) as run:
            self.assertEqual(pointer_tool.save_clipboard(), text)
            self.assertIn("--no-newline", run.call_args.args[0])

    def test_nontext_and_richtext_abort_before_any_probe(self):
        for formats in ("image/png\n", "text/plain\ntext/uri-list\n",
                        "text/plain\ntext/html\n", ""):
            with self.subTest(formats=formats), patch.object(
                    pointer_tool.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], 0, formats)), patch.object(
                    pointer_tool, "qdbus") as bus, patch.object(
                    pointer_tool.tempfile, "mkdtemp") as temp:
                with self.assertRaises(SystemExit):
                    pointer_tool.Pointer()
                bus.assert_not_called()
                temp.assert_not_called()

    def test_unreadable_clipboard_aborts_before_probe(self):
        with patch.object(pointer_tool.subprocess, "run", side_effect=FileNotFoundError), \
                patch.object(pointer_tool, "qdbus") as bus:
            with self.assertRaises(SystemExit):
                pointer_tool.Pointer()
            bus.assert_not_called()

    def test_restore_preserves_probe_prefix_and_whitespace(self):
        for text in ("MOOS-CURSOR 1,2", "  original\n\n", ""):
            with self.subTest(text=text), patch.object(
                    pointer_tool, "save_clipboard", return_value=text), patch.object(
                    pointer_tool, "qdbus", return_value="true") as bus, patch.object(pointer_tool, "run") as command, patch.object(pointer_tool,"clipboard_text",return_value=text):
                pointer = pointer_tool.Pointer()
                directory = Path(pointer._workspace)
                pointer.restore()
                if text:
                    command.assert_called_once_with(["wl-copy", "--type", "text/plain;charset=utf-8"], input_text=text)
                else:
                    command.assert_called_once_with(["wl-copy", "--clear"])
                self.assertFalse(directory.exists())

    def test_action_failure_still_restores(self):
        with patch.object(pointer_tool, "save_clipboard", return_value="original"), \
                patch.object(pointer_tool, "qdbus", return_value="true") as bus, \
                patch.object(pointer_tool, "run") as command, \
                patch.object(pointer_tool,"clipboard_text",return_value="original"), \
                patch.object(pointer_tool.Pointer, "where", side_effect=RuntimeError("probe")), \
                patch.object(pointer_tool.sys, "argv", [str(TOOL), "where"]):
            with self.assertRaisesRegex(RuntimeError, "probe"):
                pointer_tool.main()
            command.assert_called_once_with(["wl-copy", "--type", "text/plain;charset=utf-8"], input_text="original")

    def test_failed_restore_reports_failure_and_removes_fixture(self):
        with patch.object(pointer_tool, "save_clipboard", return_value="original"), patch.object(pointer_tool, "qdbus", return_value="true"):
            pointer = pointer_tool.Pointer()
            directory = Path(pointer._workspace)
            with patch.object(pointer_tool, "run", side_effect=SystemExit("restore refused")):
                with self.assertRaisesRegex(SystemExit, "private recovery retained"):
                    pointer.restore()
            self.assertTrue(directory.exists())
            self.assertEqual(Path(pointer._backup).read_text(),"original")
            self.assertEqual(Path(pointer._backup).stat().st_mode & 0o777,0o600)
            pointer_tool.shutil.rmtree(directory)

    def test_missing_bridge_refuses_before_a_probe_or_input(self):
        with patch.object(pointer_tool,"save_clipboard",return_value="original"), patch.object(pointer_tool,"bridge_available",return_value=False), patch.object(pointer_tool.tempfile,"mkdtemp") as temp, patch.object(pointer_tool,"run") as command:
            with self.assertRaisesRegex(SystemExit,"bridge is unavailable"):pointer_tool.Pointer()
            temp.assert_not_called();command.assert_not_called()

    def test_owned_name_without_an_actual_bridge_is_not_accepted(self):
        with patch.object(pointer_tool,"run",side_effect=['{"type":"b","data":[true]}',SystemExit("missing object")]):
            self.assertFalse(ACTUAL_BRIDGE())
        with patch.object(pointer_tool,"run",return_value='{"type":"b","data":[1]}') as run:
            self.assertFalse(ACTUAL_BRIDGE())
            self.assertEqual(run.call_count,1)

    def test_typed_clipboard_response_preserves_all_whitespace(self):
        import json
        text="  original\n\n"
        with patch.object(pointer_tool,"run",return_value=json.dumps({"type":"s","data":[text]})):
            self.assertEqual(pointer_tool.clipboard_text(),text)

    def test_failed_commands_never_print_private_argv_or_stdin(self):
        sentinel="PRIVATE-CLIPBOARD-SENTINEL"
        for error in (subprocess.CalledProcessError(1,["qdbus",sentinel]),subprocess.TimeoutExpired(["qdbus",sentinel],5),OSError(sentinel)):
            with self.subTest(error=type(error).__name__), patch.object(pointer_tool.subprocess,"run",side_effect=error):
                try:pointer_tool.run(["wl-copy","--type","text/plain;charset=utf-8"],input_text=sentinel)
                except SystemExit:
                    self.assertNotIn(sentinel,traceback.format_exc())
                else:self.fail("failed native command was accepted")

    def test_stale_or_malformed_clipboard_reply_cannot_supply_coordinates(self):
        with tempfile.TemporaryDirectory(prefix="moos-pointer-reply-") as tmp:
            pointer=pointer_tool.Pointer.__new__(pointer_tool.Pointer)
            pointer._script=str(Path(tmp)/"probe.js")
            replies=iter(["MOOS-CURSOR 1,2","MOOS-CURSOR abcd malformed,private","MOOS-CURSOR abcd 4,5"])
            with patch.object(pointer_tool,"qdbus",return_value=""), patch.object(pointer_tool,"clipboard_text",side_effect=lambda:next(replies)), patch.object(pointer_tool.secrets,"token_hex",return_value="abcd"), patch.object(pointer_tool.time,"sleep"):
                self.assertEqual(pointer.where(),(4,5))
            self.assertIn("MOOS-CURSOR abcd",Path(pointer._script).read_text())


class StationPointer(unittest.TestCase):
    def test_button_commands_match_ydotool_down_up_and_click(self):
        pointer = pointer_tool.Pointer.__new__(pointer_tool.Pointer)
        for button, down, up, click in (("left", "0x40", "0x80", "0xc0"),
                                       ("right", "0x41", "0x81", "0xc1"),
                                       ("middle", "0x42", "0x82", "0xc2")):
            with self.subTest(button=button), patch.object(pointer_tool, "run") as run, \
                    patch.object(pointer_tool.time, "sleep"):
                pointer.press(button)
                pointer.release(button)
                pointer.click(button)
                self.assertEqual([call.args[0] for call in run.call_args_list],
                                 [["ydotool", "click", code] for code in (down, up, click)])

    def test_failed_drag_releases_button_before_restoring(self):
        for fail_at in ("press", "move", "where"):
            with self.subTest(fail_at=fail_at), patch.object(pointer_tool, "Pointer") as cls, \
                    patch.object(pointer_tool.sys, "argv", [str(TOOL), "drag", "1", "2", "3", "4"]):
                pointer = cls.return_value
                pointer.move.side_effect = [(1, 2), (3, 4)]
                if fail_at == "move":
                    pointer.move.side_effect = [(1, 2), RuntimeError("drag failed")]
                else:
                    getattr(pointer, fail_at).side_effect = RuntimeError("drag failed")
                with self.assertRaisesRegex(RuntimeError, "drag failed"):
                    pointer_tool.main()
                self.assertEqual([call[0] for call in pointer.mock_calls][-2:],
                                 ["release", "restore"])

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
        self.assertIn("wl-copy", restore)
        self.assertIn("input_text", restore)
        self.assertIn("unloadScript", restore, "the probe script is removed from KWin too")
        main = ast.unparse(self.method("main"))
        self.assertIn("finally", main, "restore even when a step fails")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
