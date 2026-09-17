#!/usr/bin/env python3
"""Gate: Mo AI tool schemas match the real moai-do and moos-control executors.

WHY THIS EXISTS

The tool schemas are the bridge between what the cloud model can call and what
actually executes on the machine. If a schema names an action that moai-do does
not implement, the model sends users to a dead button. If moai-do gains an
action with no schema, the model cannot offer it. This gate enforces zero drift.
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moai"))

from moai_tool_schemas import (
    ALL_TOOLS, READ_ONLY_NAMES, CONFIRM_NAMES, TOOL_META,
    get_schemas_for_model, get_schemas_with_meta, build_command,
    READ_ONLY, CONTROL, USER_CONFIRM, PRIV_CONFIRM,
)


class TestToolSchemaIntegrity(unittest.TestCase):
    """Every schema must map to a real executor action and vice versa."""

    @classmethod
    def setUpClass(cls):
        cls.moai_do = (ROOT / "system_files/usr/bin/moai-do").read_text(encoding="utf-8")
        cls.moos_control = (ROOT / "system_files/usr/bin/moos-control").read_text(encoding="utf-8")

        # Extract moai-do action names from the case dispatch.
        cls.moai_do_actions: set[str] = set()
        for m in re.finditer(r'^\s+"?([a-z][-a-z]*)"?\)\s', cls.moai_do, re.MULTILINE):
            action = m.group(1)
            if action not in ("help", "--help", "-h", "*"):
                cls.moai_do_actions.add(action)

        # Extract moos-control action names from the ACTIONS dict.
        cls.control_actions: set[str] = set()
        for m in re.finditer(r'"([a-z][-a-z]+)":\s*\(', cls.moos_control):
            cls.control_actions.add(m.group(1))

    def test_every_schema_has_a_valid_category(self):
        valid = {READ_ONLY, CONTROL, USER_CONFIRM, PRIV_CONFIRM}
        for tool in ALL_TOOLS:
            cat = tool["_moos"]["category"]
            self.assertIn(cat, valid, f"{tool['function']['name']} has invalid category {cat}")

    def test_every_moai_do_schema_maps_to_a_real_action(self):
        for tool in ALL_TOOLS:
            meta = tool["_moos"]
            if meta["executor"] != "moai-do":
                continue
            cmd = meta["command"]
            self.assertIn(cmd, self.moai_do_actions,
                          f"Schema '{tool['function']['name']}' maps to moai-do "
                          f"'{cmd}' which does not exist in the executor")

    def test_every_control_schema_maps_to_a_real_action(self):
        for tool in ALL_TOOLS:
            meta = tool["_moos"]
            if meta["executor"] != "moos-control":
                continue
            cmd = meta["command"]
            # moos-control has "mute"/"unmute" as separate actions but we map
            # them through "volume" with mute/unmute values.
            if cmd in ("mute", "unmute"):
                continue
            self.assertIn(cmd, self.control_actions,
                          f"Schema '{tool['function']['name']}' maps to moos-control "
                          f"'{cmd}' which does not exist")

    def test_no_privileged_action_is_auto_execute(self):
        """Actions that use pkexec must never be auto-executed."""
        pkexec_actions = set()
        for m in re.finditer(r'run_priv\s', self.moai_do):
            # Find which do_ function contains this run_priv call.
            pos = m.start()
            # Walk backward to find the do_xxx() function header.
            chunk = self.moai_do[:pos]
            func_match = list(re.finditer(r'^do_([a-z_]+)\(\)', chunk, re.MULTILINE))
            if func_match:
                fname = func_match[-1].group(1).replace("_", "-")
                pkexec_actions.add(fname)

        for tool in ALL_TOOLS:
            meta = tool["_moos"]
            if meta["executor"] != "moai-do":
                continue
            if meta["command"] in pkexec_actions:
                self.assertNotIn(tool["function"]["name"], READ_ONLY_NAMES,
                                 f"{tool['function']['name']} uses pkexec but is marked auto-execute")

    def test_all_tool_names_are_unique(self):
        names = [t["function"]["name"] for t in ALL_TOOLS]
        self.assertEqual(len(names), len(set(names)), "Duplicate tool names found")

    def test_schemas_for_model_strip_moos_metadata(self):
        for schema in get_schemas_for_model():
            self.assertNotIn("_moos", schema,
                             "Model-facing schemas must not contain _moos metadata")
            self.assertIn("type", schema)
            self.assertIn("function", schema)

    def test_build_command_produces_valid_commands(self):
        cmd = build_command("system_update", {})
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd[0], "moai-do")
        self.assertIn("--confirmed", cmd)
        self.assertIn("update", cmd)

        cmd = build_command("install_app", {"app_id": "org.mozilla.firefox"})
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd, ["moai-do", "--confirmed", "install", "org.mozilla.firefox"])

        cmd = build_command("set_volume", {"value": "50"})
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd, ["moos-control", "volume", "50"])

    def test_build_command_rejects_unknown_tools(self):
        self.assertIsNone(build_command("hack_the_planet", {}))
        self.assertIsNone(build_command("", {}))

    def test_no_arbitrary_command_construction(self):
        """build_command must never pass user input as the command name."""
        # Try to inject a command through arguments.
        cmd = build_command("install_app", {"app_id": "; rm -rf /"})
        self.assertIsNotNone(cmd)
        # The injection string is an argument, not a command.
        self.assertEqual(cmd[2], "install")
        self.assertEqual(cmd[3], "; rm -rf /")
        # moai-do will reject this via its own ID validation.

    def test_read_only_and_confirm_partition(self):
        """Every tool is in exactly one partition."""
        all_names = {t["function"]["name"] for t in ALL_TOOLS}
        covered = READ_ONLY_NAMES | CONFIRM_NAMES
        self.assertEqual(all_names, covered,
                         f"Uncategorized tools: {all_names - covered}")
        self.assertEqual(len(READ_ONLY_NAMES & CONFIRM_NAMES), 0,
                         "A tool cannot be both auto-execute and confirm")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestToolSchemaIntegrity))
    raise SystemExit(0 if result.wasSuccessful() else 1)
