#!/usr/bin/env python3
"""Gate the explicit ordering contract for a portal ``keysyms`` batch.

Most typing stays fire-and-forget so portal latency cannot block the input queue.  The Unicode paste
fallback is different: its synthetic sequence is one transaction and must not be overtaken by a
later event.  It marks that batch ``sync:true``; layout-changing batches remain synchronous too.
"""

import ast
import sys
import unittest
from types import SimpleNamespace
from pathlib import Path

from test_remote_portal_layout_refresh import LayoutRefreshTests


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


class SecureModifierTests(unittest.TestCase):
    """The greeter workaround must never slow ordinary keys or legacy input."""
    def test_only_sensitive_native_keyboard_edges_are_paced(self):
        sent, waits = [], []
        tree = ast.parse(HELPER.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "notify_secure")
        scope = {"notify_sync": lambda *args: sent.append(args), "eis": object(),
                 "time": SimpleNamespace(sleep=waits.append)}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(HELPER), "exec"), scope)
        for code in (42, 54, 100):
            for down in (1, 0):
                scope["notify_secure"]("NotifyKeyboardKeycode", "", (code, down))
        self.assertEqual(waits, [.04] * 6)
        scope["notify_secure"]("NotifyKeyboardKeycode", "", (30, 1))
        scope["notify_secure"]("NotifyPointerButton", "", (42, 1))
        scope["eis"] = None
        scope["notify_secure"]("NotifyKeyboardKeycode", "", (42, 1))
        self.assertEqual(len(waits), 7)
        self.assertEqual(len(sent), 9, "every press/release still reaches its original backend")

    def test_ordinary_ordered_text_keeps_its_existing_sender(self):
        tree = ast.parse(HELPER.read_text())
        handle = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "handle")
        calls = []
        scope = dict(eis=object(), session="session", empty={},
            notify=lambda *args: calls.append("async"), notify_sync=lambda *args: calls.append("ordered"),
            notify_secure=lambda *args: calls.append("secure"), caps_lock_state=lambda: False,
            select_group=lambda *args: True, prepare_secure_input=lambda send: calls.append("prepare"),
            layout_state={})
        exec(compile(ast.Module(body=[handle], type_ignores=[]), str(HELPER), "exec"), scope)
        batch = dict(type="keysyms", text=True, sync=True, events=[dict(code=42, down=True)])
        scope["handle"](batch)
        scope["handle"]({**batch, "secure": True})
        scope["eis"] = None
        scope["handle"]({**batch, "secure": True})
        self.assertEqual(calls, ["ordered", "secure", "ordered"])

    def test_prompt_preparation_always_releases_its_own_shift(self):
        tree = ast.parse(HELPER.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare_secure_input")
        waits, edges = [], []
        scope = dict(session="session", empty={}, time=SimpleNamespace(sleep=waits.append))
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(HELPER), "exec"), scope)
        def send(method, signature, args):
            edges.append(args[-1])
            if args[-1] == 1:
                raise RuntimeError("private recorder failure")
        with self.assertRaises(RuntimeError):
            scope["prepare_secure_input"](send)
        self.assertEqual(edges, [1, 0])
        self.assertEqual(waits, [], "a failed preparation cannot continue to password text")


def main() -> int:
    source = HELPER.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(HELPER))
    handle = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "handle"),
        None,
    )
    if handle is None:
        print("GATE FAIL: portal helper has no input handler.")
        return 1

    code = ast.unparse(handle)
    errors: list[str] = []
    if "bool(m.get('sync')) or any(('layout' in e for e in events))" not in code:
        errors.append("keysyms does not make sync:true OR a layout change select ordered delivery")
    if "send = notify_sync if ordered else notify" not in code:
        errors.append("the ordered decision does not select notify_sync")

    if errors:
        print("GATE FAIL: an explicitly synchronous keysyms batch can be overtaken.\n")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: keysyms sync:true and layout changes use ordered portal delivery.")
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls)
                               for cls in (LayoutRefreshTests, SecureModifierTests))
    result = unittest.TextTestRunner().run(suite)
    if not result.wasSuccessful():
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
