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
    no other desktop or distribution;
  * the image gate (verify_image_experience.py) parses every module route of the registry,
    and — using that gate's own rule, read from its source — every module id resolves on a
    machine that has settings modules installed;
  * moos-open keeps exactly one LITERAL arm per token, running exactly the registry's
    command — in both directions, with no wildcard and no URL text in any arm (moos: is a
    public scheme, so the router stays a literal allowlist rather than reading the file);
  * moos-control, Mo AI's open_settings enum, moos-settings-status and the search runner all
    offer exactly what the registry says;
  * a missing or malformed registry offers NOTHING (fail safe): the settings verb is
    unavailable, open_settings is not offered, every other control verb still works.
"""
from __future__ import annotations

import ast
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
IMAGE_GATE = ROOT / "build_files/verify_image_experience.py"
MOOS_SETTINGS = ROOT / "system_files/usr/bin/moos-settings"
KCM_MODULES = ROOT / "moos-settings-kcm/modules"

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
            # screen-edges is listed (see test_screen_edges_is_a_native_page) but not yet
            # offered: Mo AI's control grammar must name it in the same change.
            "task-switcher", "animations", "sounds", "search", "login-screen",
            "virtual-keyboard", "touchscreen", "tablet", "game-controller", "window-decoration",
        }
        self.assertEqual(required - offered, set())

    def test_screen_edges_is_a_native_page(self):
        """SPEC D3's screen-edges page: kcm_kwinscreenedges, which ships no .desktop and whose
        plugin lives only in kcms/systemsettings_qwidgets/ — it needs the image gate to look in
        every module folder (TheImageGateSeesAndResolvesEveryModule holds that)."""
        entry = destinations.load(REGISTRY)["screen-edges"]
        self.assertEqual((entry["host"], entry["target"]), ("systemsettings", "kcm_kwinscreenedges"))

    def test_moos_modules_are_moos_settings_sections(self):
        registry = destinations.load(REGISTRY)
        for token in ("overview", "about", "update", "whats-new", "assistant", "remote",
                      "recovery", "appearance", "themes", "wallpaper"):
            self.assertEqual(registry[token]["host"], "moos-settings", token)
        for token in ("appearance", "themes", "wallpaper"):
            self.assertEqual(registry[token]["target"], "appearance",
                             "every appearance token opens MoOS Themes (SPEC D1)")


class TheImageGateSeesAndResolvesEveryModule(unittest.TestCase):
    """The image gate decides whether a settings route ships; this test uses ITS rule.

    The first version of this check asked `rglob('*.so')` under every module folder — wider
    than verify_image_experience.py, which accepts only a `<id>.desktop` or a plugin in
    `kcms/` or `kcms/kinfocenter/`. `screen-edges` (kcm_kwinscreenedges: no .desktop, plugin
    in `kcms/systemsettings_qwidgets/`) passed here and would have failed every x86 image
    build. So the rule is no longer re-typed: the route regex, the comment stripper, the
    .desktop template and the plugin globs are read out of the image gate's own source.
    When that gate changes its rule, this test follows it, and it cannot drift again.
    """

    @staticmethod
    def _template(node: ast.AST) -> str:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if not isinstance(node, ast.JoinedStr):
            raise AssertionError(f"unexpected image-gate path shape: {ast.dump(node)}")
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(value.value)
            elif (isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name)
                  and value.value.id == "_kcm"):
                parts.append("{kcm}")
            else:
                raise AssertionError(f"unexpected image-gate path part: {ast.dump(value)}")
        return "".join(parts)

    @classmethod
    def setUpClass(cls):
        tree = ast.parse(IMAGE_GATE.read_text(encoding="utf-8"))
        namespace: dict = {"re": re}
        found: dict[str, list] = {"source": [], "_kcm_routes": [], "_desktop": [], "_plugins": []}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "source":
                found["source"].append(node)
            elif (isinstance(node, ast.Assign) and len(node.targets) == 1
                  and isinstance(node.targets[0], ast.Name) and node.targets[0].id in found):
                found[node.targets[0].id].append(node.value)
        for name, nodes in found.items():
            if len(nodes) != 1:
                raise AssertionError(f"the image gate's settings-route rule changed shape: "
                                     f"{name} appears {len(nodes)} times — update this test")
        exec(compile(ast.Module(body=found["source"], type_ignores=[]), str(IMAGE_GATE), "exec"),
             namespace)
        cls.strip = staticmethod(namespace["source"])
        cls.route_regex = found["_kcm_routes"][0].args[0].value
        cls.desktop = cls._template(found["_desktop"][0].args[0])
        cls.plugins = []
        for call in ast.walk(found["_plugins"][0]):
            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "glob"):
                base = call.func.value.args[0].value           # Path("/usr")
                cls.plugins.append((base, cls._template(call.args[0])))
        if not cls.plugins:
            raise AssertionError("the image gate lists no plugin location — update this test")

    def test_the_image_gate_parses_every_module_route_of_the_registry(self):
        """A route the gate's regex cannot parse is a route the image never checks."""
        routes = re.findall(self.route_regex,
                            self.strip(ROUTER.read_text(encoding="utf-8"), "#"))
        wanted = sorted((token, entry["host"], entry["target"])
                        for token, entry in destinations.load(REGISTRY).items()
                        if entry["host"] in ("systemsettings", "kinfocenter"))
        self.assertGreaterEqual(len(wanted), 25)
        self.assertEqual(sorted(routes), wanted)

    def resolves(self, kcm: str) -> bool:
        desktop = Path(self.desktop.format(kcm=kcm)).is_file()
        return desktop or any(path.is_file() for base, pattern in self.plugins
                              for path in Path(base).glob(pattern.format(kcm=kcm)))

    def test_the_rule_looks_in_every_module_folder_and_still_refuses_an_unknown_id(self):
        """The widened rule must still bite: an id nobody installed resolves to nothing."""
        self.assertTrue(any("kcms/*/" in pattern for _base, pattern in self.plugins),
                        "the image gate does not look in every module folder")
        if not HOST_KCMS.is_dir():
            self.skipTest("no settings modules on this machine (the image gate checks the image)")
        self.assertTrue(self.resolves("kcm_kwinscreenedges"),
                        "kcm_kwinscreenedges (kcms/systemsettings_qwidgets/) is not resolved")
        self.assertTrue(self.resolves("kcm_usb"), "a kinfocenter module is not resolved")
        for unknown in ("kcm_moos_no_such_page", "kcm_kwinscreenedgesx", "kcm_"):
            self.assertFalse(self.resolves(unknown), f"{unknown} resolved to something")

    def test_every_listed_module_resolves_by_the_image_gates_rule(self):
        """Measured on this machine, with exactly the lookup the image build performs."""
        if not HOST_KCMS.is_dir():
            self.skipTest("no settings modules on this machine (the image gate checks the image)")
        missing = []
        for token, entry in destinations.load(REGISTRY).items():
            if entry["host"] not in ("systemsettings", "kinfocenter"):
                continue
            kcm = entry["target"]
            desktop = Path(self.desktop.format(kcm=kcm)).is_file()
            plugin = any(path.is_file() for base, pattern in self.plugins
                         for path in Path(base).glob(pattern.format(kcm=kcm)))
            if not (desktop or plugin):
                missing.append(f"settings/{token} -> {kcm}")
        self.assertEqual(missing, [], "the image gate would call these modules not installed; "
                         "the x86 image build would fail")


class TheImageGateResolvesEveryMoosSection(unittest.TestCase):
    """The image gate's `moos_section_problems`, run on this tree and on broken copies.

    Every `moos-settings --section=<s>` route must open a kcm_moos* module that the KCM
    stage built (settings-modules.list) and installed; no section has a stand-in. The
    function is read out of
    the image gate's source, so this proves the exact code the image build runs can fail.

    The built set is the one CMake builds — one module per moos-settings-kcm/modules/*/<id>.json
    — never the launcher's own `module=` lines: a test that took its "built" set from the
    launcher agreed with the launcher by construction, stayed green on a tree whose image gate
    was red (review of wave G), and so proved nothing about the real tree.
    """

    @classmethod
    def setUpClass(cls):
        tree = ast.parse(IMAGE_GATE.read_text(encoding="utf-8"))
        wanted = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name in ("source", "moos_section_problems")]
        if len(wanted) != 2:
            raise AssertionError("the image gate lost moos_section_problems — update this test")
        namespace: dict = {"re": re}
        exec(compile(ast.Module(body=wanted, type_ignores=[]), str(IMAGE_GATE), "exec"),
             namespace)
        cls.problems = staticmethod(namespace["moos_section_problems"])
        cls.router = namespace["source"](ROUTER.read_text(encoding="utf-8"), "#")
        cls.launcher = namespace["source"](MOOS_SETTINGS.read_text(encoding="utf-8"), "#")
        # Every kcm_moos* id the launcher can open: the tree once every slice has landed.
        cls.modules = set(re.findall(r"module=(kcm_moos(?:_[a-z]+)?)\b", cls.launcher))
        # What CMakeLists.txt's module glob builds, and so writes into settings-modules.list.
        cls.built = {path.stem for path in KCM_MODULES.glob("*/*.json")}

    @staticmethod
    def program_shipped(program: str) -> bool:
        return (ROOT / "system_files/usr/bin" / program).is_file()

    def installed_on_this_tree(self, module: str) -> bool:
        """A MoOS module is installed when CMake builds it. Whether a Plasma module is
        installed is the image's question: the image gate answers it from the real plugin
        folders, and the host half of this suite checks the ids resolve."""
        return module in self.built or not module.startswith("kcm_moos")

    def test_this_tree_resolves_with_the_modules_cmake_builds(self):
        self.assertTrue({"kcm_moos", "kcm_moos_update", "kcm_moos_whatsnew", "kcm_moos_remote",
                         "kcm_moos_recovery"} <= self.built,
                        f"the module scan went blind: {sorted(self.built)}")
        for module in self.built:
            self.assertRegex(module, r"^kcm_moos(_[a-z]+)?$", "CMake refuses any other id")
        self.assertEqual(self.problems(self.router, self.launcher, self.built,
                                       self.installed_on_this_tree, self.program_shipped), [],
                         "the x86 image build would fail verify_image_experience.py")

    def test_the_tree_resolves_once_every_module_is_built(self):
        self.assertGreaterEqual(len(self.modules), 7, self.modules)
        self.assertEqual(self.problems(self.router, self.launcher, self.modules,
                                       lambda _module: True, self.program_shipped), [])

    def test_a_module_the_build_did_not_list_fails(self):
        for listed in (self.built, self.modules):
            found = self.problems(self.router, self.launcher, listed - {"kcm_moos_update"},
                                  lambda _module: True, self.program_shipped)
            self.assertTrue(any("kcm_moos_update" in problem
                                and "settings-modules.list" in problem for problem in found),
                            found)

    def test_a_listed_module_that_is_not_installed_fails(self):
        found = self.problems(self.router, self.launcher, self.built,
                              lambda module: module != "kcm_moos_remote", self.program_shipped)
        self.assertTrue(any("kcm_moos_remote" in problem and "not installed" in problem
                            for problem in found), found)

    def test_an_unbuilt_module_fails_because_no_section_has_a_stand_in(self):
        """Mo AI and MoOS Themes used to fall back to their old windows; they are required now."""
        for lost in ("kcm_moos_ai", "kcm_moos_appearance"):
            found = self.problems(self.router, self.launcher, self.modules - {lost},
                                  lambda _m: True, self.program_shipped)
            self.assertTrue(any(lost in problem and "settings-modules.list" in problem
                                for problem in found), found)

    def test_a_listed_module_that_is_lost_fails_too(self):
        found = self.problems(self.router, self.launcher, self.modules,
                              lambda module: module != "kcm_moos_ai", self.program_shipped)
        self.assertTrue(any("kcm_moos_ai" in problem and "listed but not installed" in problem
                            for problem in found), found)

    def test_a_section_the_launcher_does_not_have_fails(self):
        launcher = self.launcher.replace("--section=update)", "--section=renamed)")
        found = self.problems(self.router, launcher, self.modules, lambda _module: True,
                              self.program_shipped)
        self.assertTrue(any("--section=update" in problem and "no such section" in problem
                            for problem in found), found)

    def test_a_section_that_opens_another_module_fails(self):
        launcher = self.launcher.replace("module=kcm_moos_recovery", "module=kcm_lookandfeel")
        found = self.problems(self.router, launcher, self.modules, lambda _module: True,
                              self.program_shipped)
        self.assertTrue(any("kcm_lookandfeel" in problem and "not a MoOS module" in problem
                            for problem in found), found)

    def test_a_blind_parser_fails(self):
        found = self.problems("", self.launcher, self.modules, lambda _module: True,
                              self.program_shipped)
        self.assertTrue(any("found almost nothing" in problem for problem in found), found)


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


def accepted_sections() -> set[str]:
    """The sections moos-settings really opens: its case labels, minus any arm that refuses.

    The `--section=*` default arm prints "unknown section" and exits 2. It is skipped by its
    refusal, not by its spelling, so a wildcard can never make every section look accepted.
    """
    code = "\n".join(line for line in MOOS_SETTINGS.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))
    accepted: set[str] = set()
    for labels, body in re.findall(r"(?ms)^\s*(--section=[^)\n]*)\)(.*?);;", code):
        if re.search(r"\bexit\s+[1-9]", body):
            continue
        for label in labels.split("|"):
            name = label.strip().removeprefix("--section=")
            if re.fullmatch(r"[a-z0-9-]+", name):
                accepted.add(name)
    return accepted


class EveryMoosSettingsSectionExists(unittest.TestCase):
    """A route to a section moos-settings refuses is a dead button with every gate green.

    settings/overview, settings/assistant, brain/start, do/setup-brain and moai-do setup-brain
    all open `moos-settings --section=<s>`. Nothing compared <s> with what moos-settings
    accepts, and a moos-settings without those sections exits 2 on each of them. This holds
    the registry and every caller in the overlay to moos-settings' own case labels.
    """
    CALL = re.compile(r"moos-settings(?:[\"',]|\s)+--section=([a-z0-9-]+)")

    def test_the_section_parser_reads_moos_settings(self):
        sections = accepted_sections()
        self.assertIn("update", sections, "the parser found nothing in moos-settings")
        self.assertTrue(all("*" not in name for name in sections))

    def test_every_moos_settings_destination_is_a_section_it_accepts(self):
        sections = accepted_sections()
        refused = sorted(f"settings/{token} -> --section={entry['target']}"
                         for token, entry in destinations.load(REGISTRY).items()
                         if entry["host"] == "moos-settings" and entry["target"] not in sections)
        self.assertEqual(refused, [], "moos-settings answers 'unknown section' to these")

    def test_every_caller_in_the_overlay_names_a_section_it_accepts(self):
        sections = accepted_sections()
        refused, callers = [], 0
        for root in (ROOT / "system_files", ROOT / "moos-settings-kcm"):
            for path in sorted(root.rglob("*")) if root.is_dir() else ():
                if not path.is_file() or path.is_symlink() or path == MOOS_SETTINGS:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                for section in self.CALL.findall(text):
                    callers += 1
                    if section not in sections:
                        refused.append(f"{path.relative_to(ROOT)}: --section={section}")
        self.assertGreaterEqual(callers, 10, "the caller scan found almost nothing")
        self.assertEqual(sorted(set(refused)), [], "moos-settings answers 'unknown section'")


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
