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
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moai"))
sys.path.insert(0, str(ROOT / "tests"))

import journal_isolation  # noqa: E402

# `moai-do help` writes an audit line with `logger`: never into the owner's journal.
journal_isolation.install()
LOGGER_STUB = journal_isolation.stub_dir()

from moai_tool_schemas import (  # noqa: E402
    ALL_TOOLS, READ_ONLY_NAMES, CONFIRM_NAMES, TOOL_META, SETTINGS_PAGES,
    get_schemas_for_model, get_schemas_with_meta, build_command, needs_confirmation,
    consequence, READ_ONLY, CONTROL, USER_CONFIRM, PRIV_CONFIRM,
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
            # SPEC D4/W9.10: each read from moos-control's OWN table, not restated here.
            "window": tuple(control.WINDOW_VIEWS), "arrange": tuple(control.ARRANGEMENTS),
            "desktop": tuple(control.DESKTOP_STEPS), "dnd": ("on", "off"),
            "mic": ("mute", "unmute"), "motion": control.MOTION, "clarity": control.CLARITY,
            "power-profile": control.POWER_PROFILES,
            "window-do": control.WINDOW_ACTIONS, "media": tuple(control.MEDIA),
            "desktops": ("add", "remove"), "reminders": ("list", "cancel-all"),
            "open-folder": tuple(control.FOLDERS), "animations": tuple(control.ANIMATION_SPEEDS),
            "click": control.CLICK_MODES,
            "remote": control.REMOTE_VALUES, "fast-remote": control.FAST_REMOTE_VALUES,
        }
        # A valid stand-in for every other required argument, so an enum on one parameter of a
        # multi-argument tool can still be built. Integers use the declared minimum; a free
        # string is a plain word that passes _valid (no dash, in range).
        def sample(spec):
            if spec.get("enum"):
                return spec["enum"][0]
            if spec.get("type") == "integer":
                return spec.get("minimum", 1)
            return "code"

        advertised = {verb: set() for verb in accepted}
        for tool in ALL_TOOLS:
            meta = tool["_moos"]
            if meta["executor"] != "moos-control":
                continue
            properties = tool["function"]["parameters"]["properties"]
            for key, spec in properties.items():
                for value in spec.get("enum", []):
                    arguments = {other: sample(other_spec) for other, other_spec
                                 in properties.items() if other in meta["required"]}
                    arguments[key] = value
                    argv = build_command(tool["function"]["name"], arguments)
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
        # And the other direction for the enum verbs: every value moos-control accepts is
        # one the model can ask for, so no verb is reachable only by typing it.
        for verb in ("window", "arrange", "desktop", "dnd", "mic", "motion", "clarity",
                     "power-profile", "window-do", "media", "desktops", "reminders",
                     "open-folder", "animations", "click", "remote", "fast-remote"):
            self.assertEqual(advertised[verb], set(accepted[verb]),
                             f"the schema and moos-control disagree about {verb}")
        # The multi-argument and integer verbs W9.10 added carry their arguments in order.
        self.assertEqual(build_command("window_action", {"action": "close", "target": "firefox"}),
                         ["moos-control", "window-do", "close", "firefox"])
        self.assertEqual(build_command("move_window_to_desktop", {"desktop": 2, "target": "code"}),
                         ["moos-control", "window-move", "2", "code"])
        self.assertEqual(build_command("set_reminder", {"minutes": 10, "text": "tea"}),
                         ["moos-control", "remind", "10", "tea"])
        self.assertEqual(build_command("go_to_desktop", {"number": 3}),
                         ["moos-control", "go-desktop", "3"])
        self.assertEqual(build_command("set_screen_lock", {"after_minutes": 0}),
                         ["moos-control", "screen-lock", "0"])
        # A window target that is really an option must never reach argv as one.
        self.assertIsNone(build_command("window_action", {"action": "close", "target": "-rf"}))
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
            # W9.10: a window target or a reminder is free text, but never an option or control char.
            ("window_action", {"action": "close", "target": "--fullscreen"}),
            ("window_action", {"action": "explode", "target": "firefox"}),
            ("move_window_to_desktop", {"desktop": 99, "target": "code"}),
            ("go_to_desktop", {"number": 0}),
            ("set_reminder", {"minutes": 0, "text": "x"}),
            ("set_reminder", {"minutes": 5, "text": "line\nbreak"}),
            ("control_media", {"action": "rewind"}),
            ("open_folder", {"folder": "/etc"}),
            ("set_animation_speed", {"speed": "instant"}),
            ("set_screen_lock", {"after_minutes": 999}),
            ("set_click_mode", {"mode": "triple"}),
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

    def test_the_desktop_hands_are_control_and_bounded(self):
        """W9.10: the window/desktop/media/reminder verbs run on moos-control, unprivileged.

        Their free-text parameters (a window target, a reminder's words, a URL) carry a hard
        maxLength so a model cannot push an unbounded argument through, and the two that could
        surprise the owner — closing a window, disabling the automatic lock — are confirmed.
        """
        hands = ("list_windows", "window_action", "move_window_to_desktop", "go_to_desktop",
                 "add_or_remove_desktop", "control_media", "lock_screen", "set_reminder",
                 "manage_reminders", "open_web_page", "open_folder", "set_animation_speed",
                 "set_screen_lock", "set_click_mode")
        for name in hands:
            meta = TOOL_META[name]
            self.assertEqual(meta["executor"], "moos-control", name)
            self.assertIn(meta["category"], (READ_ONLY, CONTROL), name)
            properties = next(t for t in ALL_TOOLS
                              if t["function"]["name"] == name)["function"]["parameters"]
            for key, spec in properties["properties"].items():
                if spec.get("type") == "string" and not spec.get("enum"):
                    self.assertIn("maxLength", spec, f"{name}.{key} is unbounded free text")
                    self.assertLessEqual(spec["maxLength"], 2048, f"{name}.{key} is too long")
        self.assertTrue(needs_confirmation("window_action", {"action": "close", "target": "x"}))
        self.assertFalse(needs_confirmation("window_action", {"action": "focus", "target": "x"}))
        self.assertTrue(needs_confirmation("set_screen_lock", {"after_minutes": 0}))
        self.assertFalse(needs_confirmation("set_screen_lock", {"after_minutes": 10}))
        self.assertFalse(needs_confirmation("lock_screen", {}))

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

    # ── a card says what happens after the yes ──────────────────────────────────────────────
    def test_every_card_says_what_confirming_does_in_both_languages(self):
        """Every tool that can show a card carries the consequence Mira prints on it.

        A card that repeats only the action's name asks the owner to approve something he has
        not been told: that firmware cannot be undone, that an update waits for a restart and
        leaves his files alone, that the password will be asked.
        """
        arabic = re.compile(r"[؀-ۿ]")
        carded = [t for t in ALL_TOOLS
                  if t["_moos"]["category"] in (USER_CONFIRM, PRIV_CONFIRM)
                  or t["_moos"]["confirm_values"]]
        self.assertGreaterEqual(len(carded), 25, "the confirmed tools were not found")
        for tool in carded:
            name, meta = tool["function"]["name"], tool["_moos"]
            with self.subTest(tool=name):
                ar, en = meta.get("consequence_ar", ""), meta.get("consequence_en", "")
                self.assertGreaterEqual(len(ar), 20, f"{name} has no Arabic consequence")
                self.assertGreaterEqual(len(en), 20, f"{name} has no English consequence")
                self.assertRegex(ar, arabic, f"{name}'s Arabic consequence is not Arabic")
                self.assertNotRegex(en, arabic, f"{name}'s English consequence carries Arabic")
                self.assertEqual(consequence(name, "ar"), ar)
                self.assertEqual(consequence(name, "en"), en)
                for text in (ar, en):
                    self.assertNotRegex(text, r"(?i)fedora|red hat",
                                        "the identity contract covers card text too")
                if meta["category"] == PRIV_CONFIRM:
                    # Every privileged action asks for the password, and says so.
                    self.assertIn("password", en, f"{name} escalates and does not say so")
                    self.assertIn("كلمة المرور", ar, f"{name} escalates and does not say so")
        # The texts the plan names, word for word in substance.
        self.assertIn("cannot be undone", consequence("update_firmware", "en"))
        self.assertIn("لا يمكن التراجع", consequence("update_firmware", "ar"))
        for name in ("system_update", "system_rollback"):
            self.assertIn("next restart", consequence(name, "en"))
            self.assertIn("untouched", consequence(name, "en"))
            self.assertIn("لا تُمسّ", consequence(name, "ar"))
        self.assertIn("unsaved work is lost", consequence("restart_computer", "en"))
        # A read has no card, so it has no consequence to show.
        self.assertEqual(consequence("check_system_update", "en"), "")
        self.assertEqual(consequence("a tool that does not exist", "ar"), "")

    def test_a_card_promises_a_password_exactly_when_its_action_can_ask_for_one(self):
        """The card's password line is held to the code: a `run_priv` the action can reach.

        install_openclaw shipped PRIV_CONFIRM saying "may ask for your password once so it stays
        available after you log out" — copied from an echo line — after the cloud-only change
        had removed the only call that did (setup_brain_impl's enable-linger). Mo AI's card also
        printed "the system will ask for your administrator password first". So the claim and
        the category are derived from moai-do's own functions, through every helper they call.
        """
        bodies = {}
        for match in re.finditer(r"^([a-z_][a-z0-9_]*)\(\) \{\n(.*?)^\}", self.moai_do,
                                 re.S | re.M):
            bodies[match.group(1)] = "\n".join(
                line for line in match.group(2).splitlines() if not line.lstrip().startswith("#"))
        self.assertIn("run_priv", bodies, "moai-do's functions were not read")
        dispatch = re.search(r'case "\$cmd" in(.*?)\n    esac', self.moai_do, re.S)
        self.assertIsNotNone(dispatch)

        def escalates(start):
            seen, todo = set(), [start]
            while todo:
                name = todo.pop()
                if name in seen or name not in bodies:
                    continue
                seen.add(name)
                if re.search(r"\brun_priv\s", bodies[name]):
                    return True
                todo.extend(other for other in bodies if other != name and re.search(
                    rf"(?<![\w-]){re.escape(other)}(?![\w-])", bodies[name]))
            return False

        checked = 0
        for tool in ALL_TOOLS:
            name, meta = tool["function"]["name"], tool["_moos"]
            if meta["executor"] != "moai-do" or meta["category"] == READ_ONLY:
                continue
            arm = re.search(rf"^\s+{re.escape(meta['command'])}\)\s+(\w+)", dispatch.group(1),
                            re.M)
            with self.subTest(tool=name):
                self.assertIsNotNone(arm, f"moai-do does not dispatch {meta['command']}")
                can_ask = escalates(arm.group(1))
                says_en = bool(re.search(r"(?i)\bask(?:s)? for your password",
                                         meta["consequence_en"]))
                says_ar = "تُطلب كلمة المرور" in meta["consequence_ar"]
                self.assertEqual(says_en, can_ask,
                                 f"{name}: the card's password line disagrees with moai-do")
                self.assertEqual(says_ar, can_ask,
                                 f"{name}: the Arabic password line disagrees with moai-do")
                if meta["category"] == PRIV_CONFIRM:
                    self.assertTrue(can_ask, f"{name} is privileged but never escalates, so "
                                             "its card warns of a password nobody asks for")
                # …and the other way: an action that can reach a password prompt is privileged,
                # so every window draws its card as the password card (optimize_system shipped
                # user_confirm while trimming the journal through pkexec).
                self.assertEqual(meta["category"] == PRIV_CONFIRM, can_ask,
                                 f"{name}: its category disagrees with whether moai-do escalates")
                checked += 1
        self.assertGreaterEqual(checked, 20, "the confirmed moai-do tools were not found")
        # The gate bites: the text install_openclaw carried before is refused by the same rule.
        self.assertRegex("It may ask for your password once so it stays available after you "
                         "log out.", r"(?i)\bask(?:s)? for your password")
        self.assertFalse(escalates("do_install_openclaw"))

    # ── the Mira-era tools: each is one fixed argv of an existing executor ─────────────────
    def test_the_new_tools_build_exactly_their_executor_argv(self):
        home = str(Path.home())
        expected = {
            ("install_codex", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "install-codex"]),
            ("install_claude_code", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "install-claude"]),
            ("install_opencode", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "install-opencode"]),
            ("install_hermes", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "install-hermes"]),
            ("install_openclaw", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "install-openclaw"]),
            ("smart_setup", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "smart-setup"]),
            ("check_system_update", ()): (READ_ONLY, ["moai-do", "--confirmed", "check-update"]),
            ("restart_computer", ()): (USER_CONFIRM, ["moai-do", "--confirmed", "restart"]),
            ("install_rpm", (("path", "~/Downloads/app-1.0.x86_64.rpm"),)):
                (PRIV_CONFIRM, ["moai-do", "--confirmed", "install-rpm",
                                f"{home}/Downloads/app-1.0.x86_64.rpm"]),
            ("install_rpm", (("path", "/var/home/moos/Desktop/My App.rpm"),)):
                (PRIV_CONFIRM, ["moai-do", "--confirmed", "install-rpm",
                                "/var/home/moos/Desktop/My App.rpm"]),
            ("install_rpm", (("path", "/home/moos/Documents/tool.rpm"),)):
                (PRIV_CONFIRM, ["moai-do", "--confirmed", "install-rpm",
                                "/home/moos/Documents/tool.rpm"]),
            # The owner's own folder names: an Arabic session's desktop and documents.
            ("install_rpm", (("path", "~/سطح المكتب/app.rpm"),)):
                (PRIV_CONFIRM, ["moai-do", "--confirmed", "install-rpm",
                                f"{home}/سطح المكتب/app.rpm"]),
            ("install_rpm", (("path", "/var/home/moos/المستندات/tool.rpm"),)):
                (PRIV_CONFIRM, ["moai-do", "--confirmed", "install-rpm",
                                "/var/home/moos/المستندات/tool.rpm"]),
            ("remote_control", (("value", "on"),)): (CONTROL, ["moos-control", "remote", "on"]),
            ("remote_control", (("value", "off"),)): (CONTROL, ["moos-control", "remote", "off"]),
            ("remote_control", (("value", "restart"),)):
                (CONTROL, ["moos-control", "remote", "restart"]),
            ("fast_remote", (("value", "on"),)): (CONTROL, ["moos-control", "fast-remote", "on"]),
            ("fast_remote", (("value", "off"),)): (CONTROL, ["moos-control", "fast-remote", "off"]),
        }
        for (name, arguments), (category, argv) in expected.items():
            with self.subTest(tool=name, arguments=arguments):
                self.assertEqual(TOOL_META[name]["category"], category)
                self.assertEqual(build_command(name, dict(arguments)), argv)
        # The moai-do verbs the new tools name are the ones moai-do dispatches (checked for every
        # tool above); the two NEW verbs are documented in its help, too.
        help_text = subprocess.run(["bash", str(ROOT / "system_files/usr/bin/moai-do"), "help"],
                                   capture_output=True, text=True, timeout=30,
                                   env={**os.environ, "PATH": f"{LOGGER_STUB}:/usr/bin:/bin"}).stdout
        for verb in ("check-update", "restart"):
            self.assertIn(verb, help_text)

    def test_a_package_path_is_one_rpm_in_one_visible_folder_of_the_home(self):
        """The schema holds the SHAPE; which folders is moai-do's to decide.

        A list of English folder names here refused the owner's real desktop («سطح المكتب»)
        while the description promised Desktop. moai-do's valid_local_rpm (tests/test_moai_do.py)
        and the root helper resolve the XDG folders and refuse ~/Pictures and the rest."""
        for path in ("/etc/passwd.rpm", "/etc/x.rpm", "~/Downloads/../x.rpm",
                     "~/Downloads/sub/x.rpm", "~/Downloads/x.rpm.sh",
                     "~/Downloads/x.RPM", "Downloads/x.rpm", "-rf.rpm", "~/Downloads/x.rpm\n",
                     "/home/../Downloads/x.rpm", "/home/./Downloads/x.rpm",
                     "/root/Downloads/x.rpm", "~/Downloads/.rpm" + "a" * 300, "~/Downloads/",
                     "~/../x.rpm", "~/./x.rpm", "~/.ssh/x.rpm", "~/.config/x.rpm", "~/x.rpm",
                     "~//x.rpm", "~/" + "a" * 129 + "/x.rpm"):
            with self.subTest(path=path):
                self.assertIsNone(build_command("install_rpm", {"path": path}))
        for path in ("~/Downloads/x.rpm", "~/سطح المكتب/x.rpm", "~/Schreibtisch/x.rpm",
                     "/var/home/moos/المستندات/x.rpm"):
            with self.subTest(path=path):
                self.assertIsNotNone(build_command("install_rpm", {"path": path}))
        self.assertIsNone(build_command("install_rpm", {}), "the path is required")
        self.assertIsNone(build_command("install_rpm", {"path": "~/Downloads/a.rpm",
                                                        "app_id": "org.x.Y"}))

    def test_the_remote_switches_ask_first_and_reconnecting_does_not(self):
        # ON lets a paired phone drive this computer after every start; OFF cuts off whoever
        # is driving it now. Reconnecting only restarts a remote that is already on.
        self.assertTrue(needs_confirmation("remote_control", {"value": "on"}))
        self.assertTrue(needs_confirmation("remote_control", {"value": "off"}))
        self.assertFalse(needs_confirmation("remote_control", {"value": "restart"}))
        # Fast Remote ON rewrites blur, motion and the keyboard layout until it is turned off.
        self.assertTrue(needs_confirmation("fast_remote", {"value": "on"}))
        self.assertFalse(needs_confirmation("fast_remote", {"value": "off"}))
        self.assertTrue(needs_confirmation("restart_computer", {}))
        self.assertFalse(needs_confirmation("check_system_update", {}))
        for name, arguments in (("remote_control", {"value": "start"}),
                                ("remote_control", {"value": "on; reboot"}),
                                ("fast_remote", {"value": "toggle"}),
                                ("fast_remote", {"value": "status"})):
            with self.subTest(name=name, arguments=arguments):
                self.assertIsNone(build_command(name, arguments))

    def test_checking_for_an_update_can_change_nothing(self):
        body = re.search(r"^do_check_update\(\) \{(.*?)^\}", self.moai_do, re.S | re.M)
        self.assertIsNotNone(body, "moai-do must define do_check_update")
        code = "\n".join(line for line in body.group(1).splitlines()
                         if not line.lstrip().startswith("#"))
        for forbidden in ("run_priv", "pkexec", '"stage"', "--expected-digest", "confirm ||",
                          "rpm-ostree", "bootc"):
            self.assertNotIn(forbidden, code, f"check-update must stay read-only: {forbidden}")
        self.assertIn('"state", "--format", "json"', code,
                      "check-update must ask the one update authority for its state")
        restart = re.search(r"^do_restart\(\) \{(.*?)^\}", self.moai_do, re.S | re.M)
        self.assertIsNotNone(restart, "moai-do must define do_restart")
        self.assertNotIn("run_priv", restart.group(1), "a restart goes through logind, not pkexec")
        self.assertNotRegex(restart.group(1), r"--ignore-inhibitors|\s-i\b|--force",
                            "a restart must honour whatever is holding it off")


# ── moos-control's remote verbs, run against stubs ──────────────────────────────────────────
# Recording stubs only: the unit's state lives in a file under the stub root, so each test
# proves the READ-BACK as well as the call. Nothing here reaches a real systemd or desktop.
RECORDER = r'''#!/bin/sh
line="${0##*/}"
for arg in "$@"; do line="$line$(printf '\t%s' "$arg")"; done
printf '%s\n' "$line" >> "$STUB_LOG"
'''
REMOTE_STUBS = {
    "systemctl": '''state=inactive; read -r state < "$STUB_ROOT/remote" 2>/dev/null
case "$*" in
  *is-active*) echo "$state"; [ "$state" = active ] && exit 0; exit 3;;
  *"enable --now"*) echo "${STUB_REMOTE_STARTS_AS:-active}" > "$STUB_ROOT/remote";;
  *"disable --now"*) echo "${STUB_REMOTE_STOPS_AS:-inactive}" > "$STUB_ROOT/remote";;
  *try-restart*) [ -z "$STUB_RESTART_SLOW" ] || sleep "$STUB_RESTART_SLOW";;
esac
''',
    "moos-fast-remote": '''state=off; read -r state < "$STUB_ROOT/fast" 2>/dev/null
case "$1" in
  status) echo "$state";;
  on|off) [ -z "$STUB_FAST_SLOW" ] || sleep "$STUB_FAST_SLOW"
          [ -n "$STUB_FAST_STUCK" ] || echo "$1" > "$STUB_ROOT/fast"; echo "Fast Remote: $1";;
esac
''',
    "logger": "",
}


class TestRemoteVerbs(unittest.TestCase):
    """remote on|off|restart and fast-remote on|off: one fixed argv each, read back."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.log.touch()
        for name, body in REMOTE_STUBS.items():
            (self.bin / name).write_text(RECORDER + body, encoding="utf-8")
            (self.bin / name).chmod(0o755)
        # The one real program the stubs use: PATH is the stub folder alone, so nothing else
        # on this machine can be reached by a verb under test.
        (self.bin / "sleep").symlink_to(shutil.which("sleep"))

    def tearDown(self):
        self.dir.cleanup()

    def control(self, *args, **extra):
        env = {"PATH": str(self.bin), "HOME": str(self.root), "STUB_LOG": str(self.log),
               "STUB_ROOT": str(self.root), "LANG": "C.UTF-8", **extra}
        return subprocess.run([sys.executable, str(ROOT / "system_files/usr/bin/moos-control"),
                               *args], env=env, capture_output=True, text=True, timeout=60)

    def calls(self):
        return [line.split("\t") for line in self.log.read_text(encoding="utf-8").splitlines()]

    def acting(self):
        return [call for call in self.calls()
                if call[0] in ("systemctl", "moos-fast-remote") and "is-active" not in call
                and "status" not in call]

    def test_the_unit_is_mo_pc_remotes_own(self):
        control = load_script("system_files/usr/bin/moos-control", "moos_control_units")
        self.assertTrue((ROOT / "system_files/usr/lib/systemd/user" / control.REMOTE_UNIT).is_file())
        router = (ROOT / "system_files/usr/bin/moos-open").read_text(encoding="utf-8")
        self.assertIn(f'REMOTE_UNIT="{control.REMOTE_UNIT}"', router,
                      "moos-control and moos-open must switch the same Mo PC Remote unit")

    def test_remote_on_enables_for_every_boot_and_reads_it_back(self):
        done = self.control("remote", "on")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Mo PC Remote on", done.stdout)
        self.assertEqual(self.acting(), [["systemctl", "--user", "enable", "--now",
                                          "mo-remote-personal.service"]])
        self.assertIn(["logger", "-t", "moos-control", "remote on"], self.calls())

    def test_a_remote_that_does_not_come_up_is_not_on(self):
        done = self.control("remote", "on", STUB_REMOTE_STARTS_AS="failed")
        self.assertEqual(done.returncode, 69, done.stdout)
        self.assertIn("did not start", done.stderr)
        self.assertEqual(done.stdout, "", "a failure must not also claim success")

    def test_remote_off_disables_and_reads_it_back(self):
        (self.root / "remote").write_text("active\n", encoding="utf-8")
        done = self.control("remote", "off")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.acting(), [["systemctl", "--user", "disable", "--now",
                                          "mo-remote-personal.service"]])
        (self.root / "remote").write_text("active\n", encoding="utf-8")
        still = self.control("remote", "off", STUB_REMOTE_STOPS_AS="active")
        self.assertEqual(still.returncode, 69)
        self.assertIn("still running", still.stderr)

    def test_restart_reconnects_only_a_remote_that_is_on(self):
        done = self.control("remote", "restart")
        self.assertEqual(done.returncode, 69, done.stdout)
        self.assertIn("turn it on first", done.stderr)
        self.assertEqual(self.acting(), [], "restart must never turn an off remote on")
        (self.root / "remote").write_text("active\n", encoding="utf-8")
        done = self.control("remote", "restart")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.acting(), [["systemctl", "--user", "try-restart",
                                          "mo-remote-personal.service"]])

    def test_fast_remote_runs_its_own_tool_and_reads_it_back(self):
        done = self.control("fast-remote", "on")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Fast Remote on", done.stdout)
        self.assertIn(["moos-fast-remote", "on"], self.calls())
        self.assertIn(["moos-fast-remote", "status"], self.calls())
        done = self.control("fast-remote", "off")
        self.assertEqual(done.returncode, 0, done.stderr)
        stuck = self.control("fast-remote", "on", STUB_FAST_STUCK="1")
        self.assertEqual(stuck.returncode, 69)
        self.assertIn("still off", stuck.stderr)

    def test_anything_else_runs_nothing(self):
        for args in (("remote",), ("remote", "start"), ("remote", "on;reboot"),
                     ("remote", "on", "extra"), ("remote", "ON"), ("fast-remote", "toggle"),
                     ("fast-remote", "status"), ("fast-remote", "recover"), ("fast-remote",)):
            with self.subTest(args=args):
                done = self.control(*args)
                self.assertEqual(done.returncode, 2, (done.stdout, done.stderr))
        self.assertEqual(self.acting(), [], "an invalid request reached a real command")
        self.assertEqual([call for call in self.calls() if call[0] == "logger"], [])

    def test_every_unconfirmed_verb_answers_inside_moai_controls_request(self):
        """remote restart and fast-remote off need no card, so moai-control runs them inside the
        request and answers 504 at QUICK_TIMEOUT while the action goes on: Mira then shows a
        failure for something that may still finish. Their worst case stays well inside it."""
        control = load_script("system_files/usr/bin/moos-control", "moos_control_budgets")
        broker = (ROOT / "system_files/usr/bin/moai-control").read_text(encoding="utf-8")
        quick = int(re.search(r"^QUICK_TIMEOUT = (\d+)", broker, re.M).group(1))
        state = control.REMOTE_STATE_TIMEOUT
        restart = (state + control.REMOTE_RESTART_TIMEOUT
                   + control.REMOTE_START_BUDGET + state + control.REMOTE_SETTLE + state)
        fast_off = control.FAST_REMOTE_BUDGET["off"] + state
        for label, worst in (("remote restart", restart), ("fast-remote off", fast_off)):
            with self.subTest(verb=label):
                self.assertLessEqual(worst, quick - 10,
                                     f"{label} can outlast moai-control's {quick}s request")
        # …and these are exactly the values that run without a card.
        self.assertFalse(needs_confirmation("remote_control", {"value": "restart"}))
        self.assertFalse(needs_confirmation("fast_remote", {"value": "off"}))

    def in_process(self, name):
        """moos-control loaded as a module, its commands found in the stub folder."""
        from unittest import mock
        control = load_script("system_files/usr/bin/moos-control", name)
        self.enterContext(mock.patch.dict(os.environ, {
            "PATH": str(self.bin), "STUB_LOG": str(self.log), "STUB_ROOT": str(self.root)}))
        return control

    def test_a_fast_remote_switch_past_its_budget_is_left_to_finish(self):
        control = self.in_process("moos_control_fast_budget")
        control.FAST_REMOTE_BUDGET = {"on": 0.3, "off": 0.3}
        (self.root / "fast").write_text("on\n", encoding="utf-8")
        os.environ["STUB_FAST_SLOW"] = "1.5"
        with self.assertRaises(control.Unavailable) as said:
            control.fast_remote("off")
        self.assertIn("still switching off", str(said.exception))
        self.assertIn("finishes on its own", str(said.exception))
        # Not killed at the budget: the restore completes by itself a moment later.
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and \
                (self.root / "fast").read_text(encoding="utf-8").strip() != "off":
            time.sleep(0.1)
        self.assertEqual((self.root / "fast").read_text(encoding="utf-8").strip(), "off",
                         "Fast Remote's restore was cut off at the budget")

    def test_a_restart_that_outlasts_its_wait_is_still_restarting_not_failed(self):
        control = self.in_process("moos_control_restart_budget")
        control.REMOTE_RESTART_TIMEOUT = 0.3
        (self.root / "remote").write_text("active\n", encoding="utf-8")
        os.environ["STUB_RESTART_SLOW"] = "2"
        with self.assertRaises(control.Unavailable) as said:
            control.remote("restart")
        self.assertIn("still restarting", str(said.exception))

    def test_a_failing_fast_remote_says_its_own_reason(self):
        (self.bin / "moos-fast-remote").write_text(
            RECORDER + 'echo "Fast Remote: another appearance transaction is still running" >&2\n'
                       'exit 1\n', encoding="utf-8")
        done = self.control("fast-remote", "on")
        self.assertEqual(done.returncode, 69)
        self.assertIn("another appearance transaction is still running", done.stderr)
        self.assertEqual(done.stdout, "")

    def test_a_missing_fast_remote_tool_is_unavailable(self):
        (self.bin / "moos-fast-remote").unlink()
        done = self.control("fast-remote", "on")
        self.assertEqual(done.returncode, 69)
        self.assertIn("moos-fast-remote", done.stderr)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    for case in (TestToolSchemaIntegrity, TestRemoteVerbs):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
