#!/usr/bin/env python3
"""Gate: ONE list of settings pages, and the public router agrees with it both ways.

WHY THIS EXISTS
The token -> settings page table used to be written out seven times — moos-control, Mo AI's
tool schema, the status helper, the search runner, the router, Mo AI's grammar and its
prompt — and tests only compared some of them, after the fact. Fourteen routes existed that
Mo AI could not name, and none of the window-manager or appearance pages could be reached at
all. SPEC D3 makes system_files/usr/share/moos/settings-destinations.json the one list.

What this proves:
  * the registry is well-formed, its tokens are unique, every label is bilingual and names
    no other desktop or distribution, and (on a machine that has them) every module id it
    lists is really installed;
  * moos-open keeps exactly one LITERAL arm per token, running exactly the registry's
    command — in both directions, with no wildcard and no URL text in any arm (moos: is a
    public scheme, so the router stays a literal allowlist rather than reading the file);
  * moos-control, Mo AI's open_settings enum, moos-settings-status and the search runner all
    offer exactly what the registry says;
  * a missing or malformed registry offers NOTHING (fail safe): the settings verb is
    unavailable, open_settings is not offered, every other control verb still works.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "system_files/usr/share/moos/settings-destinations.json"
MODULE = ROOT / "system_files/usr/lib/moos/moos_settings_destinations.py"
ROUTER = ROOT / "system_files/usr/bin/moos-open"
CONTROL = ROOT / "system_files/usr/bin/moos-control"
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
RUNNER = ROOT / "system_files/usr/libexec/moai-krunner"
SCHEMAS = ROOT / "system_files/usr/lib/moai/moai_tool_schemas.py"
HOST_KCMS = Path("/usr/lib64/qt6/plugins/plasma/kcms")

sys.path.insert(0, str(ROOT / "tests"))
from test_user_visible_identity import hit as foreign_name  # noqa: E402

ARM = re.compile(r"(?m)^    settings/([a-z0-9-]+)\)\s+gui ([^;\n]+?)\s*;;\s*$")


def load_module(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


destinations = load_module(MODULE, "moos_settings_destinations_under_test")


def case_labels(router: str) -> list[str]:
    """Every case label of the dispatch (the default `*` arm excluded)."""
    labels: list[str] = []
    for match in re.finditer(r"^\s{4}([a-z0-9/*|.-]+)\)", router, re.MULTILINE):
        labels.extend(label for label in match.group(1).split("|") if label != "*")
    return labels


def router_code() -> str:
    return "\n".join(line for line in ROUTER.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))


class TheRegistry(unittest.TestCase):
    def test_it_loads_and_every_token_is_unique(self):
        pairs: list[tuple[str, object]] = []

        def collect(items):
            pairs.extend(items)
            return dict(items)

        json.loads(REGISTRY.read_text(encoding="utf-8"), object_pairs_hook=collect)
        tokens = [key for key, value in pairs if isinstance(value, dict) and "host" in value]
        self.assertEqual(len(tokens), len(set(tokens)), "a token is listed twice")
        registry = destinations.load(REGISTRY)
        self.assertEqual(list(registry), tokens)
        self.assertGreaterEqual(len(destinations.moai_tokens(registry)), 45)

    def test_labels_are_bilingual_and_name_no_other_system(self):
        for token, entry in destinations.load(REGISTRY).items():
            label = entry["label"]
            if token not in ("assistant", "remote"):      # product names read the same
                self.assertRegex(label["ar"], r"[؀-ۿ]", f"{token}: the Arabic label is not Arabic")
            self.assertNotRegex(label["en"], r"[؀-ۿ]", f"{token}: the English label is Arabic")
            for text in label.values():
                self.assertIsNone(foreign_name(text), f"{token}: {text!r} names another system")

    def test_the_mandated_pages_are_offered_to_mo_ai(self):
        """SPEC D3: every MoOS module and the native pages Mo AI must reach."""
        offered = set(destinations.moai_tokens(destinations.load(REGISTRY)))
        required = {
            "overview", "about", "update", "whats-new", "assistant", "remote", "recovery",
            "appearance", "themes", "wallpaper", "display", "night-light", "audio", "network",
            "bluetooth", "keyboard", "mouse", "touchpad", "printers", "fonts", "accessibility",
            "notifications", "energy", "time", "region", "users", "storage", "default-apps",
            "autostart", "lock", "permissions", "global-theme", "colors", "icons", "cursors",
            "shortcuts", "window-behavior", "window-rules", "effects", "desktops",
            "screen-edges", "task-switcher", "animations", "sounds", "search", "login-screen",
            "virtual-keyboard", "touchscreen", "tablet", "game-controller", "window-decoration",
        }
        self.assertEqual(required - offered, set())

    def test_moos_modules_are_moos_settings_sections(self):
        registry = destinations.load(REGISTRY)
        for token in ("overview", "about", "update", "whats-new", "assistant", "remote",
                      "recovery", "appearance", "themes", "wallpaper"):
            self.assertEqual(registry[token]["host"], "moos-settings", token)
        for token in ("appearance", "themes", "wallpaper"):
            self.assertEqual(registry[token]["target"], "appearance",
                             "every appearance token opens MoOS Themes (SPEC D1)")

    def test_every_listed_module_is_installed_on_this_machine(self):
        """Measured, not remembered: each module id must exist where Plasma loads it from."""
        if not HOST_KCMS.is_dir():
            self.skipTest("no settings modules on this machine (the image gate checks the image)")
        installed = {path.stem for path in HOST_KCMS.rglob("*.so")}
        for token, entry in destinations.load(REGISTRY).items():
            if entry["host"] in ("systemsettings", "kinfocenter"):
                self.assertIn(entry["target"], installed,
                              f"settings/{token} names {entry['target']}, which is not installed")


class TheRouterIsTheRegistrysLiteralTwin(unittest.TestCase):
    def test_arms_equal_the_registry_in_both_directions(self):
        code = router_code()
        arms = {token: tuple(command.split()) for token, command in ARM.findall(code)}
        wanted = {token: destinations.argv(entry)
                  for token, entry in destinations.load(REGISTRY).items()}
        self.assertEqual(sorted(set(wanted) - set(arms)), [],
                         "registry tokens with no moos-open arm (a Mo AI button to nowhere)")
        self.assertEqual(sorted(set(arms) - set(wanted)), [],
                         "moos-open arms the registry does not list (a second, unlisted table)")
        for token, argv in wanted.items():
            self.assertEqual(arms[token], argv, f"settings/{token} runs something else")

    def test_no_settings_label_escapes_the_literal_form(self):
        code = router_code()
        labels = [label for label in case_labels(code) if label.startswith("settings/")]
        literal = [token for token, _command in ARM.findall(code)]
        self.assertNotIn("settings/*", labels, "a wildcard would turn URL text into argv")
        self.assertTrue(all("*" not in label for label in labels), labels)
        self.assertEqual(sorted(labels), sorted(f"settings/{token}" for token in literal),
                         "every settings arm is one token, one line, one fixed command")
        self.assertEqual(len(labels), len(set(labels)), "a settings arm is declared twice")
        for token, command in ARM.findall(code):
            self.assertNotIn("$", command, f"settings/{token} passes shell text through")


class EveryReaderOffersTheRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = destinations.load(REGISTRY)
        self.moai = destinations.moai_tokens(self.registry)

    def test_moos_control_opens_exactly_the_mo_ai_pages(self):
        pages = runpy.run_path(str(CONTROL), run_name="moos_control_registry")["SETTINGS_PAGES"]
        self.assertEqual(tuple(pages), self.moai)

    def test_open_settings_offers_exactly_the_mo_ai_pages(self):
        schemas = load_module(SCHEMAS, "moai_tool_schemas_registry")
        tool = next(tool for tool in schemas.ALL_TOOLS if tool["function"]["name"] == "open_settings")
        self.assertEqual(tuple(tool["function"]["parameters"]["properties"]["page"]["enum"]),
                         self.moai)

    def test_status_destinations_are_the_registry(self):
        status = runpy.run_path(str(STATUS))["DESTINATIONS"]
        self.assertEqual(status, {token: destinations.argv(entry)
                                  for token, entry in self.registry.items()})

    def test_the_search_runner_offers_exactly_the_mo_ai_pages(self):
        runner = runpy.run_path(str(RUNNER), run_name="moai_krunner_registry")
        self.assertEqual(tuple(token for token, _label in runner["SETTINGS_PAGES"]), self.moai)
        for token in self.moai:
            self.assertTrue(runner["ALLOWED_ROUTE"].match(f"settings/{token}"), token)
        for token in set(self.registry) - set(self.moai):
            self.assertFalse(runner["ALLOWED_ROUTE"].match(f"settings/{token}"),
                             f"settings/{token} is not offered to Mo AI")


class ABrokenRegistryOffersNothing(unittest.TestCase):
    """A registry that cannot be trusted must make settings unavailable, never misdirected."""

    def tree(self, registry_text: str | None) -> Path:
        root = Path(self.tmp.name)
        for relative in ("usr/bin/moos-control", "usr/lib/moos/moos_settings_destinations.py",
                         "usr/lib/moai/moai_tool_schemas.py", "usr/libexec/moai-krunner"):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "system_files" / relative, target)
        if registry_text is not None:
            path = root / "usr/share/moos/settings-destinations.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(registry_text, encoding="utf-8")
        return root

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()
        # The copied tree's module must not stand in for the real one in later tests.
        sys.modules.pop("moos_settings_destinations", None)

    def check_fail_safe(self, root: Path):
        stubs = root / "stubs"
        stubs.mkdir()
        log = root / "calls.log"
        for name in ("moos-open", "wpctl", "logger"):
            stub = stubs / name
            stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n'
                            'case "$1" in get-volume) echo "Volume: 0.50";; esac\n')
            stub.chmod(0o755)
        env = {"PATH": str(stubs), "HOME": str(root), "LANG": "C.UTF-8"}
        control = root / "usr/bin/moos-control"
        refused = subprocess.run([sys.executable, str(control), "settings", "display"],
                                 env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(refused.returncode, 69, refused.stderr)
        self.assertIn("settings list cannot be read", refused.stderr)
        working = subprocess.run([sys.executable, str(control), "volume", "30"],
                                 env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(working.returncode, 0, working.stderr)
        calls = log.read_text() if log.exists() else ""
        self.assertNotIn("moos-open", calls, "a broken registry still opened a page")
        schemas = load_module(root / "usr/lib/moai/moai_tool_schemas.py",
                              f"moai_tool_schemas_broken_{id(root)}")
        names = {tool["function"]["name"] for tool in schemas.ALL_TOOLS}
        self.assertNotIn("open_settings", names, "an empty page list must not be offered")
        self.assertIn("set_volume", names)
        runner = runpy.run_path(str(root / "usr/libexec/moai-krunner"), run_name="broken_runner")
        self.assertEqual(runner["SETTINGS_PAGES"], ())
        self.assertFalse(runner["ALLOWED_ROUTE"].match("settings/display"))

    def test_a_missing_registry(self):
        self.check_fail_safe(self.tree(None))

    def test_a_malformed_entry_rejects_the_whole_file(self):
        document = json.loads(REGISTRY.read_text(encoding="utf-8"))
        document["destinations"]["display"]["host"] = "sh"
        self.check_fail_safe(self.tree(json.dumps(document)))

    def test_an_unparsable_file(self):
        self.check_fail_safe(self.tree("{not json"))

    def test_the_loader_refuses_shapes_a_public_router_must_never_see(self):
        base = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for mutate in (
            lambda d: d["destinations"].__setitem__("../x", d["destinations"]["display"]),
            lambda d: d["destinations"]["display"].__setitem__("target", "kcm_x; reboot"),
            lambda d: d["destinations"]["display"].__setitem__("extra", 1),
            lambda d: d["destinations"]["display"].__setitem__("moai", "yes"),
            lambda d: d["destinations"]["display"]["label"].__setitem__("en", ""),
            lambda d: d.__setitem__("schema", 2),
        ):
            document = json.loads(json.dumps(base))
            mutate(document)
            path = Path(self.tmp.name) / "registry.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(destinations.RegistryError):
                destinations.load(path)
            self.assertEqual(destinations.safe_load(path), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
