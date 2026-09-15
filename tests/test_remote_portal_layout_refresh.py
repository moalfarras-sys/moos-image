#!/usr/bin/env python3
"""Exercise real portal layout selection with a compositor whose keymap changes."""
import ast
from pathlib import Path
import types
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "moremote/agent-linux/mo-remote-portal.py"

class LayoutRefreshTests(unittest.TestCase):
    def setUp(self):
        self.codes = ["de", "us", "ara"]
        self.current = 1
        self.failed = False
        self.sent = []
        state = dict(codes=["de", "ara"], current=1, home=0, ara=1, us=None,
                     warned=set(), typed=False, toggle=True)
        def call(method, **kwargs):
            if self.failed:
                raise Error("unavailable")
            value = self.codes if method == "getLayoutsList" else self.current
            if method == "getLayoutsList":
                value = [(c, c, c) for c in value]
            return types.SimpleNamespace(unpack=lambda: (value,))
        class Error(Exception):
            message = "unavailable"
        self.ns = dict(layout_state=state, _layout_call=call,
            GLib=types.SimpleNamespace(GError=Error), emit=lambda **kw: None,
            _group_toggle_available=lambda: True, time=types.SimpleNamespace(sleep=lambda _: None),
            MAX_TOGGLE_ATTEMPTS=8, TOGGLE_CONFIRM_TRIES=12, TOGGLE_CONFIRM_POLL_MS=5,
            ALT_CODE=56, SHIFT_CODE=42, session="session", empty={},
            build_keymaps=self.compile, keymap_composition=lambda groups: [])
        self.compiled = []
        names = {"load_layouts", "_group_index", "_read_layout", "_toggle_events", "select_group"}
        tree = ast.parse(SOURCE.read_text())
        module = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
        exec(compile(module, str(SOURCE), "exec"), self.ns)
    def compile(self, codes):
        self.compiled.append(list(codes))
        return None
    def send(self, method, signature, args):
        self.sent.append(args)
        if args[-2:] == (56, 0):
            self.current = (self.current + 1) % len(self.codes)
    def test_inserted_us_does_not_receive_arabic_positions(self):
        self.assertTrue(self.ns["select_group"]("ara", self.send))
        self.assertEqual(self.current, 2)
        self.assertTrue(self.sent)
    def test_external_switch_invalidates_cached_fast_path(self):
        self.ns["layout_state"].update(codes=self.codes[:], current=2, ara=2)
        self.current = 0
        self.assertTrue(self.ns["select_group"]("ara", self.send))
        self.assertEqual(self.current, 2)
    def test_home_language_survives_reordering(self):
        self.ns["layout_state"]["home"] = 1
        self.assertTrue(self.ns["load_layouts"]())
        self.assertEqual(self.ns["layout_state"]["home"], 2)
    def test_unavailable_compositor_drops_run(self):
        self.failed = True
        self.assertFalse(self.ns["select_group"]("ara", self.send))
        self.assertFalse(self.sent)
    def test_planned_group_index_is_honoured_while_it_still_names_that_layout(self):
        self.codes = ["ara", "de", "ara"]
        self.assertTrue(self.ns["select_group"]("ara", self.send, 2))
        self.assertEqual(self.current, 2)
    def test_stale_planned_group_index_is_resolved_by_name(self):
        self.assertTrue(self.ns["select_group"]("ara", self.send, 0))
        self.assertEqual(self.current, 2, "index 0 is `de` now; the run must still reach Arabic")
    def test_keymap_is_recompiled_when_the_layout_list_changes_not_per_batch(self):
        self.assertTrue(self.ns["select_group"]("ara", self.send))
        self.assertTrue(self.ns["select_group"]("de", self.send))
        self.assertEqual(self.compiled, [["de", "us", "ara"]])
        self.assertTrue(self.ns["load_layouts"](refresh_keymaps=True))
        self.assertEqual(len(self.compiled), 2)
    def test_removed_arabic_drops_run(self):
        self.codes = ["de", "us"]
        self.assertFalse(self.ns["select_group"]("ara", self.send))
        self.assertFalse(self.sent)

if __name__ == "__main__":
    unittest.main()
