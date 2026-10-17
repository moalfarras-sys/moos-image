#!/usr/bin/env python3
"""Portal serials and node IDs have different GStreamer properties.

The old path=serial plus ordinary policy fallback produced real camera frames
on the physical login screen. Execute the selector without contacting a portal;
also inspect the AST-backed pipeline so a correct unused helper cannot pass.
Native isolated PipeWire evidence is a separate opt-in review artifact.
"""
import ast
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "moremote/agent-linux/mo-remote-portal.py"
TREE = ast.parse(SOURCE.read_text())
sys.path.insert(0, str(ROOT / "build_files"))
from remote_screen_target_contract import validate_screen_target
NS = {}
SELECTOR = next(node for node in TREE.body if isinstance(node, ast.FunctionDef)
                and node.name == "screen_target")
exec(compile(ast.Module(body=[SELECTOR], type_ignores=[]), str(SOURCE), "exec"), NS)


class ScreenTarget(unittest.TestCase):
    def test_actual_pipeline_contract(self):
        self.assertTrue(validate_screen_target(SOURCE.read_text()))

    def test_wrong_serial_property_is_refused(self):
        self.assertFalse(validate_screen_target(SOURCE.read_text().replace(
            'return "target-object", serial', 'return "path", serial')))

    def test_default_video_fallback_is_refused(self):
        self.assertFalse(validate_screen_target(SOURCE.read_text().replace(
            'node.dont-fallback=(boolean)true', 'node.dont-fallback=(boolean)false')))

    def test_unused_correct_selector_cannot_qualify_a_wrong_pipeline(self):
        self.assertFalse(validate_screen_target(SOURCE.read_text().replace(
            'screen_target(node_id, node_props)', '("path", node_id)')))

    def test_v6_serial_never_becomes_a_node_id(self):
        self.assertEqual(NS["screen_target"](78, {"pipewire-serial": 1466, "source_type": 1}),
                         ("target-object", 1466))

    def test_v5_node_stays_a_node_id(self):
        self.assertEqual(NS["screen_target"](78, {}), ("path", 78))

    def test_missing_or_bad_serial_never_falls_back_to_default_video(self):
        for serial in (None, "78", True, 0, -1, 2**64):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                NS["screen_target"](78, {"pipewire-serial": serial})
        for node, props in ((0, {}), (-1, {}), (True, {}), (2**32, {}),
                            (78, None), (78, {"source_type": 2}), (78, {"source_type": 4})):
            with self.subTest(node=node, props=props), self.assertRaises(ValueError):
                NS["screen_target"](node, props)

    def test_live_pipeline_uses_selector_and_forbids_camera_fallback(self):
        build = next(node for node in TREE.body if isinstance(node, ast.FunctionDef)
                     and node.name == "build")
        source = ast.unparse(build)
        self.assertIn("pipewire_target[0]", source)
        self.assertIn("pipewire_target[1]", source)
        self.assertIn("node.dont-fallback=(boolean)true", source)
        calls = [node for node in ast.walk(TREE) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "screen_target"]
        self.assertEqual(len(calls), 1, "the pipeline must consume the portal's actual reply")


if __name__ == "__main__":
    unittest.main()
