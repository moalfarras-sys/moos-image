#!/usr/bin/env python3
"""Gate: Mo AI tool schemas match the real moai-do and moos-control executors.

WHY THIS EXISTS

The tool schemas are the bridge between what the cloud model can call and what
actually executes on the machine. If a schema names an action that moai-do does
not implement, the model sends users to a dead button. If moai-do gains an
action with no schema, the model cannot offer it. This gate enforces zero drift.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import itertools
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moai"))

from moai_tool_schemas import (
    ALL_TOOLS, READ_ONLY_NAMES, CONFIRM_NAMES, TOOL_META, SETTINGS_PAGES,
    get_schemas_for_model, get_schemas_with_meta, build_command, needs_confirmation,
    READ_ONLY, CONTROL, USER_CONFIRM, PRIV_CONFIRM,
)


def load_script(relative: str, name: str):
    """Import a shipped extensionless Python script as a module, without running its main()."""
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / relative))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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
            # This test used to SKIP mute/unmute with the note "we map them through volume with
            # mute/unmute values" — and moos-control's `volume` rejects both. The skip is what
            # let `set_volume` advertise two values that always failed.
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

    # ── a tool may advertise only what its executor accepts ─────────────────────────────────
    def test_every_advertised_control_value_is_accepted_by_moos_control(self):
        """Run each enum value through moos-control's OWN validator, not a copy of it."""
        control = load_script("system_files/usr/bin/moos-control", "moos_control_under_test")
        accepted = {
            "night-light": ("on", "off", "auto"), "wifi": ("on", "off"), "bluetooth": ("on", "off"),
            "theme": control.THEMES, "settings": control.SETTINGS_PAGES,
            # SPEC D4: each read from moos-control's OWN table, not restated here.
            "window": tuple(control.WINDOW_VIEWS), "arrange": tuple(control.ARRANGEMENTS),
            "desktop": tuple(control.DESKTOP_STEPS), "dnd": ("on", "off"),
            "mic": ("mute", "unmute"), "motion": control.MOTION, "clarity": control.CLARITY,
            "power-profile": control.POWER_PROFILES,
        }
        advertised = {verb: set() for verb in accepted}
        for tool in ALL_TOOLS:
            meta = tool["_moos"]
            if meta["executor"] != "moos-control":
                continue
            for key, spec in tool["function"]["parameters"]["properties"].items():
                for value in spec.get("enum", []):
                    argv = build_command(tool["function"]["name"], {key: value})
                    self.assertIsNotNone(argv, f"{tool['function']['name']}({key}={value!r}) "
                                               "is advertised but build_command refuses it")
                    verb = argv[1]
                    self.assertIn(verb, control.ACTIONS, f"moos-control has no verb {verb!r}")
                    arity = control.ACTIONS[verb][0]
                    self.assertEqual(arity, len(argv) - 2,
                                     f"moos-control {verb} takes {arity} argument(s); "
                                     f"the schema sends {argv[2:]}")
                    if verb in accepted:
                        self.assertIn(value, accepted[verb],
                                      f"{tool['function']['name']} advertises {value!r}, which "
                                      f"moos-control {verb} rejects")
                        advertised[verb].add(value)
        self.assertEqual(tuple(SETTINGS_PAGES), tuple(control.SETTINGS_PAGES),
                         "open_settings must offer exactly the pages moos-control opens")
        # And the other direction for the desktop verbs: every value moos-control accepts is
        # one the model can ask for, so no verb is reachable only by typing it.
        for verb in ("window", "arrange", "desktop", "dnd", "mic", "motion", "clarity",
                     "power-profile"):
            self.assertEqual(advertised[verb], set(accepted[verb]),
                             f"the schema and moos-control disagree about {verb}")
        # The one argument-less desktop tool is built to the one direction moos-control has.
        self.assertEqual(build_command("switch_keyboard_layout", {}),
                         ["moos-control", "keyboard-layout", "next"])
        self.assertIsNone(build_command("switch_keyboard_layout", {"value": "previous"}))
        # The volume validator itself: the two values W4 advertised must really be refused there.
        for value in ("mute", "unmute"):
            with self.assertRaises(control.Invalid):
                control.level(value, 0, 100, "volume")

    def test_every_inspect_tool_parses_in_the_real_inspector(self):
        """Every combination of advertised values must be argv the inspector's parser accepts."""
        inspector = load_script("system_files/usr/bin/moos-inspect", "moos_inspect_under_test")
        samples = {"string": "pipewire.service", "integer": 40, "boolean": True}
        seen = 0
        for tool in ALL_TOOLS:
            if tool["_moos"]["executor"] != "moos-inspect":
                continue
            name = tool["function"]["name"]
            properties = tool["function"]["parameters"]["properties"]
            choices = []
            for key, spec in properties.items():
                values = spec.get("enum") or [samples[spec["type"]]]
                if spec["type"] == "integer":
                    values = [spec["minimum"], spec["maximum"]]
                if key not in tool["_moos"]["required"]:
                    values = [None, *values]           # and the optional argument left out
                choices.append([(key, value) for value in values])
            for combination in itertools.product(*choices):
                arguments = {key: value for key, value in combination if value is not None}
                argv = build_command(name, arguments)
                self.assertIsNotNone(argv, f"{name}{arguments} is advertised but refused")
                self.assertEqual(argv[0], "moos-inspect")
                try:
                    inspector.parser().parse_args(argv[1:])
                except SystemExit:
                    self.fail(f"moos-inspect rejects what the schema builds for {name}: {argv}")
                seen += 1
        self.assertGreater(seen, 40, "the inspector tools were not exercised")

    def test_invented_arguments_never_reach_argv(self):
        for name, arguments in (
            ("unit_status", {"name": "x; rm -rf ~"}),
            ("unit_status", {"name": "../../etc/shadow"}),
            ("read_journal", {"unit": "--output=json"}),
            ("read_journal", {"lines": 5000}),
            ("read_journal", {"lines": True}),
            ("read_journal", {"since": "forever"}),
            ("top_processes", {"by": "everything"}),
            ("top_processes", {"by": "cpu", "shell": "bash"}),
            ("open_settings", {"page": "kcm_kscreen"}),
            ("open_settings", {"page": "usb"}),          # in the registry, not offered to Mo AI
            ("set_mute", {"value": "toggle"}),
            ("show_windows", {"view": "close"}),
            ("arrange_windows", {"layout": "halves", "view": "grid"}),
            ("set_power_profile", {"profile": "turbo"}),
            ("set_do_not_disturb", {"value": "on; rm -rf ~"}),
            ("read_moos_log", {"name": "../../.ssh/id_ed25519"}),
        ):
            self.assertIsNone(build_command(name, arguments),
                              f"{name}{arguments} must be refused before it becomes argv")

    def test_the_inspector_can_change_nothing(self):
        """moos-inspect is the executor that auto-runs for a cloud model: keep it read-only."""
        for tool in ALL_TOOLS:
            if tool["_moos"]["executor"] == "moos-inspect":
                self.assertEqual(tool["_moos"]["category"], READ_ONLY)
        source = (ROOT / "system_files/usr/bin/moos-inspect").read_text(encoding="utf-8")
        code = "\n".join(l for l in source.splitlines() if not l.lstrip().startswith("#"))
        body = code[code.index("def _redactor"):]
        for forbidden in ("shell=True", "os.system", "pkexec", "sudo", "run_priv", '"rm"', '"restart"',
                          '"start"', '"stop"', '"enable"', '"disable"', ".write_text(", "os.remove"):
            self.assertNotIn(forbidden, body, f"moos-inspect must stay read-only; found {forbidden}")
        self.assertIn("redact(", body, "everything the inspector prints must be redacted first")

    def test_the_desktop_tools_are_instant_control_on_moos_control(self):
        """SPEC D4: unprivileged, reversible, no card — and no way to run model text."""
        for name in ("show_windows", "arrange_windows", "switch_desktop", "set_do_not_disturb",
                     "set_mic_mute", "switch_keyboard_layout", "set_motion",
                     "set_glass_clarity", "set_power_profile"):
            meta = TOOL_META[name]
            self.assertEqual((meta["category"], meta["executor"]), (CONTROL, "moos-control"), name)
            properties = next(t for t in ALL_TOOLS
                              if t["function"]["name"] == name)["function"]["parameters"]
            for spec in properties["properties"].values():
                self.assertTrue(spec.get("enum"), f"{name} takes free text")

    def test_cutting_the_owner_off_is_confirmed_even_for_a_control_tool(self):
        self.assertTrue(needs_confirmation("toggle_wifi", {"value": "off"}))
        self.assertTrue(needs_confirmation("toggle_bluetooth", {"value": "off"}))
        self.assertFalse(needs_confirmation("toggle_wifi", {"value": "on"}))
        # Re-opening a microphone the owner muted is a privacy change: it asks. Muting does not.
        self.assertTrue(needs_confirmation("set_mic_mute", {"value": "unmute"}))
        self.assertFalse(needs_confirmation("set_mic_mute", {"value": "mute"}))
        self.assertFalse(needs_confirmation("set_volume", {"value": "30"}))
        self.assertTrue(needs_confirmation("system_update", {}))
        self.assertTrue(needs_confirmation("a tool that does not exist", {}))

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
