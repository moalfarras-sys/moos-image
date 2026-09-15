#!/usr/bin/env python3
"""Gate: Mo PC Remote types on the RUNNING keymap, compiled the way KWin compiles it.

WHY THIS EXISTS

On 2026-09-15 the owner reported that the Remote typed no English, and that German and
iPhone-language keyboards did not type either. The live station explained it: KWin reported
groups `ara,de` with Arabic active. The helper typed Latin text as keysyms on `home` — the group
active when it started, which MoOS's Arabic-first default had made Arabic — and a Latin keysym has
no key on the Arabic group. German had no position table and no `us` group remained, so umlauts,
€ and every symbol went through the clipboard. A desktop viewer's physical German keyboard typed
Arabic letters, because positions landed on the active Arabic group.

The helper now compiles the per-group keymap with libxkbcommon from the same kxkbrc names KWin uses
(Xkb::loadKeymapFromConfig), and the agent plans every run against it. This gate holds:

  * the compiler agrees with MEASURED facts: every Arabic key pressed on a live session with the
    ara group active (level one and two, read back from a real editor — the retired AraKeymap
    table) and the German positions the owner types on;
  * a kxkbrc that disagrees with the live layout list yields no keymap (exact paste), never
    positions for layouts the compositor is not using;
  * the committed C# fixture is a real compiler output, not an invented table;
  * the agent's source routes text, shortcuts and physical keys through the live keymap.

Regenerate the fixture consumed by moremote's C# tests (on a MoOS host):

    python3 tests/test_remote_live_keymap.py --write-fixture
"""

import ast
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
import unicodedata
import unittest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"
INJECTOR = ROOT / "moremote/agent-linux/InputInjector.cs"
BRIDGE = ROOT / "moremote/agent-linux/PortalBridge.cs"
AGENT_LINUX = ROOT / "moremote/agent-linux"
FIXTURE = ROOT / "moremote/tests/fixtures/keymap-ara-de.json"

# The MoOS default ring on the development station.
CONFIG = {"LayoutList": "ara,de", "VariantList": ",", "Options": "grp:alt_shift_toggle",
          "ResetOldOptions": "true"}
SHIFT, LEVEL3 = 1, 2

FUNCTIONS = {"_xkb_library", "_kxkbrc_layout_config", "_kconfig_bool", "build_keymaps",
             "_group_keymap", "keymap_composition"}
CONSTANTS = {"XKB_DEAD_MARKS", "XKB_KEY_SHIFT_L", "XKB_KEY_ISO_LEVEL3_SHIFT", "XKB_MOD_INVALID",
             "KEYMAP_TYPING_CODES", "KEYMAP_MOD_SHIFT", "KEYMAP_MOD_LEVEL3", "KEYMAP_SHIFT_CODE",
             "KEYMAP_LEVEL3_CODE", "_xkb"}

# Measured on the live session (formerly moremote/agent-linux/AraKeymap.cs): evdev code -> text.
ARA_LEVEL1 = [
    (2, "1"), (3, "2"), (4, "3"), (5, "4"), (6, "5"), (7, "6"), (8, "7"), (9, "8"),
    (10, "9"), (11, "0"), (12, "-"), (13, "="),
    (16, "ض"), (17, "ص"), (18, "ث"), (19, "ق"), (20, "ف"), (21, "غ"), (22, "ع"),
    (23, "ه"), (24, "خ"), (25, "ح"), (26, "ج"), (27, "د"),
    (30, "ش"), (31, "س"), (32, "ي"), (33, "ب"), (34, "ل"), (35, "ا"), (36, "ت"),
    (37, "ن"), (38, "م"), (39, "ك"), (40, "ط"), (41, "ذ"),
    (43, "\\"),
    (44, "ئ"), (45, "ء"), (46, "ؤ"), (47, "ر"), (49, "ى"), (50, "ة"), (51, "و"),
    (52, "ز"), (53, "ظ"),
    (86, "|"), (57, " "),
]
ARA_LEVEL2 = [
    (2, "!"), (3, "@"), (4, "#"), (5, "$"), (6, "%"), (7, "^"), (8, "&"), (9, "*"),
    (10, ")"), (11, "("), (12, "_"), (13, "+"),
    (16, "َ"), (17, "ً"), (18, "ُ"), (19, "ٌ"), (21, "إ"),
    (22, "`"), (23, "÷"), (24, "×"), (25, "؛"), (26, "<"), (27, ">"),
    (30, "ِ"), (31, "ٍ"), (32, "]"), (33, "["), (35, "أ"), (36, "ـ"),
    (37, "،"), (38, "/"), (39, ":"), (40, "\""), (41, "ّ"),
    (43, "|"),
    (44, "~"), (45, "ْ"), (46, "}"), (47, "{"), (49, "آ"), (50, "'"), (51, ","),
    (52, "."), (53, "؟"),
    (86, "…"),
]
# German (de) positions: character -> (evdev code, modifiers).
DE_EXPECTED = {
    "z": (21, 0), "y": (44, 0), "Z": (21, SHIFT), "ä": (40, 0), "ö": (39, 0), "ü": (26, 0),
    "Ä": (40, SHIFT), "ß": (12, 0), "?": (12, SHIFT), "\"": (3, SHIFT), "§": (4, SHIFT),
    "/": (8, SHIFT), "=": (11, SHIFT), "+": (27, 0), "*": (27, SHIFT), "#": (43, 0),
    "'": (43, SHIFT), "-": (53, 0), "_": (53, SHIFT), ";": (51, SHIFT), ":": (52, SHIFT),
    "<": (86, 0), ">": (86, SHIFT), "@": (16, LEVEL3), "€": (18, LEVEL3), "{": (8, LEVEL3),
    "[": (9, LEVEL3), "]": (10, LEVEL3), "}": (11, LEVEL3), "\\": (12, LEVEL3),
    "~": (27, LEVEL3), "|": (86, LEVEL3),
}
DE_DEAD = {0x0301: (13, 0), 0x0300: (13, SHIFT), 0x0302: (41, 0)}


def helper_namespace():
    tree = ast.parse(HELPER.read_text(encoding="utf-8"), filename=str(HELPER))
    body = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            body.append(node)
        elif isinstance(node, ast.Assign):
            names = set()
            for target in node.targets:
                elements = target.elts if isinstance(target, ast.Tuple) else [target]
                names |= {element.id for element in elements if isinstance(element, ast.Name)}
            if names & CONSTANTS:
                body.append(node)
    namespace = {"ctypes": ctypes, "os": os, "unicodedata": unicodedata}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(HELPER), "exec"), namespace)
    missing = (FUNCTIONS | CONSTANTS) - namespace.keys()
    if missing:
        raise AssertionError(f"the portal helper no longer defines {sorted(missing)}")
    return namespace


def compiled(namespace):
    """The ara,de keymap, or None when this machine has no libxkbcommon/xkeyboard-config."""
    return namespace["build_keymaps"](["ara", "de"], dict(CONFIG))


def moos_host():
    return Path("/usr/lib64/libxkbcommon.so.0").exists() and Path("/usr/share/X11/xkb/symbols/ara").exists()


def entries(group):
    return {(key, mods, char) for key, mods, char in group["levels"]}


class LiveKeymapCompiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = helper_namespace()
        cls.groups = compiled(cls.ns)
        if cls.groups is None and moos_host():
            raise AssertionError("libxkbcommon and the ara layout exist here, yet the helper "
                                 "compiled no keymap — Remote typing would fall back to paste")

    def require_keymap(self):
        if self.groups is None:
            self.skipTest("libxkbcommon/xkeyboard-config unavailable on this runner")

    def test_mismatched_or_empty_layout_list_is_refused(self):
        build = self.ns["build_keymaps"]
        self.assertIsNone(build(["ara", "de"], {"LayoutList": "de,ara"}),
                          "positions for a layout order KWin is not using would be wrong")
        self.assertIsNone(build([], dict(CONFIG)))

    def test_kxkbrc_cascade_lets_the_user_file_win(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "kdedefaults").mkdir()
            (Path(home) / "kdedefaults/kxkbrc").write_text("[Layout]\nLayoutList=de\nModel=pc105\n")
            (Path(home) / "kxkbrc").write_text("[Other]\nLayoutList=fr\n[Layout]\nLayoutList=ara,de\n")
            previous = os.environ.get("XDG_CONFIG_HOME")
            os.environ["XDG_CONFIG_HOME"] = home
            try:
                config = self.ns["_kxkbrc_layout_config"]()
            finally:
                if previous is None:
                    os.environ.pop("XDG_CONFIG_HOME")
                else:
                    os.environ["XDG_CONFIG_HOME"] = previous
        self.assertEqual(config.get("LayoutList"), "ara,de")
        self.assertEqual(config.get("Model"), "pc105")

    def test_arabic_group_matches_the_live_measurement(self):
        self.require_keymap()
        ara = self.groups[0]
        self.assertEqual((ara["code"], ara["group"], ara["shift"]), ("ara", 0, 42))
        have = entries(ara)
        for mods, table in ((0, ARA_LEVEL1), (SHIFT, ARA_LEVEL2)):
            for key, text in table:
                self.assertIn((key, mods, ord(text)), have,
                              f"ara evdev {key} mods {mods} must produce {text!r} (measured live)")

    def test_german_group_carries_umlauts_symbols_and_dead_accents(self):
        self.require_keymap()
        de = self.groups[1]
        self.assertEqual((de["code"], de["group"], de["shift"], de["level3"]), ("de", 1, 42, 100))
        have = entries(de)
        for text, (key, mods) in DE_EXPECTED.items():
            self.assertIn((key, mods, ord(text)), have, f"de must type {text!r} as evdev {key} mods {mods}")
        dead = {(key, mods, mark) for key, mods, mark in de["dead"]}
        for mark, (key, mods) in DE_DEAD.items():
            self.assertIn((key, mods, mark), dead, f"de dead accent U+{mark:04X} must be evdev {key}")
        self.assertNotIn(ord("^"), {char for _key, _mods, char in de["levels"]},
                         "a dead key must never be offered as a direct character")

    def test_composition_covers_phone_accents(self):
        self.require_keymap()
        table = {tuple(row) for row in self.ns["keymap_composition"](self.groups)}
        for composed, base, mark in (("é", "e", 0x0301), ("ä", "a", 0x0308), ("أ", "ا", 0x0654)):
            self.assertIn((ord(composed), ord(base), mark), table)

    def test_committed_fixture_is_compiler_output(self):
        self.require_keymap()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([g["code"] for g in fixture["keymaps"]], ["ara", "de"])
        for built, stored in zip(self.groups, fixture["keymaps"]):
            # Levels one and two are stable across xkeyboard-config releases; higher levels may grow.
            stable = {entry for entry in entries(stored) if entry[1] in (0, SHIFT)}
            self.assertLessEqual(stable, entries(built),
                                 f"fixture group {stored['code']} contains positions the compiler rejects")


class CapsLockDoesNotInvertTypedText(unittest.TestCase):
    """Measured live 2026-09-15 with Caps Lock on at the desk: "Hello World" arrived "hELLO wORLD",
    ß arrived ẞ and AltGr symbols landed a level up. With the lock released around the batch, all
    fourteen live cases (Latin, German, AltGr, dead keys, Arabic, physical keys) typed exactly."""

    def namespace(self, caps):
        tree = ast.parse(HELPER.read_text(encoding="utf-8"), filename=str(HELPER))
        wanted = {"handle", "caps_lock_on", "caps_lock_state", "_tap_keycode", "_set_caps_lock"}
        body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        body += [n for n in tree.body if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in ("CAPS_LOCK_CODE", "CAPS_RESTORE_TRUST_S") for t in n.targets)]
        self.sent = []
        record = lambda method, signature, args: self.sent.append((method, args[2], args[3]))
        ns = {"os": os, "time": __import__("time"), "notify": record, "notify_sync": record,
              "select_group": lambda name, send, group=None: True, "layout_state": {"typed": False},
              "emit": lambda **kw: None, "session": "session", "empty": {}}
        exec(compile(ast.Module(body=body, type_ignores=[]), str(HELPER), "exec"), ns)
        self.assertEqual((wanted | {"CAPS_LOCK_CODE", "CAPS_RESTORE_TRUST_S"}) - ns.keys(), set())
        ns["caps_lock_on"] = lambda: caps
        return ns

    def typed(self, ns, **extra):
        ns["handle"](dict(type="keysyms", events=[{"layout": "de", "group": 1},
                                                   {"code": 30, "down": True}, {"code": 30, "down": False}], **extra))
        return [(code, down) for _method, code, down in self.sent]

    def test_text_batch_releases_and_restores_a_desk_caps_lock(self):
        ns = self.namespace(caps=True)
        self.assertEqual(self.typed(ns, text=True), [(58, 1), (58, 0), (30, 1), (30, 0), (58, 1), (58, 0)])

    def test_restored_lock_is_trusted_before_the_led_catches_up(self):
        ns = self.namespace(caps=True)
        self.typed(ns, text=True)
        ns["caps_lock_on"] = lambda: False   # the LED has not yet seen our restoring tap
        self.sent.clear()
        self.assertEqual(self.typed(ns, text=True)[:2], [(58, 1), (58, 0)])

    def test_lock_off_unobservable_or_non_text_batches_are_untouched(self):
        self.assertEqual(self.typed(self.namespace(caps=False), text=True), [(30, 1), (30, 0)])
        self.assertEqual(self.typed(self.namespace(caps=None), text=True), [(30, 1), (30, 0)],
                         "without a Caps Lock LED the lock cannot be read back, so it is never toggled")
        self.assertEqual(self.typed(self.namespace(caps=True)), [(30, 1), (30, 0)],
                         "a physical key's group selection must keep keyboard semantics")

    def test_viewer_lock_is_synchronized_only_when_it_differs_and_is_observable(self):
        for desk, viewer, taps in ((True, False, 2), (False, True, 2), (True, True, 0), (None, False, 0)):
            ns = self.namespace(caps=desk)
            ns["handle"]({"type": "keysyms", "text": False, "capsLock": viewer, "events": []})
            self.assertEqual([code for _m, code, _d in self.sent].count(58), taps,
                             f"desk lock {desk}, viewer lock {viewer}")
        ns = self.namespace(caps=True)
        ns["handle"]({"type": "keysyms", "text": False, "capsLock": False, "events": []})
        ns["caps_lock_on"] = lambda: True     # LED lags our tap
        ns["handle"]({"type": "keysyms", "text": False, "capsLock": False, "events": []})
        self.assertEqual([code for _m, code, _d in self.sent].count(58), 2,
                         "a lagging LED must not undo the synchronization on the next letter")

    def test_led_reader(self):
        ns = self.namespace(caps=False)
        del ns["caps_lock_on"]
        exec(compile(ast.Module(body=[n for n in ast.parse(HELPER.read_text(encoding="utf-8")).body
                                      if isinstance(n, ast.FunctionDef) and n.name == "caps_lock_on"],
                                type_ignores=[]), str(HELPER), "exec"), ns)
        with tempfile.TemporaryDirectory() as leds:
            self.assertIsNone(ns["caps_lock_on"](leds), "no LED means the lock is unobservable")
            os.makedirs(os.path.join(leds, "input3::capslock"))
            Path(leds, "input3::capslock", "brightness").write_text("1\n")
            os.makedirs(os.path.join(leds, "input3::numlock"))
            Path(leds, "input3::numlock", "brightness").write_text("1\n")
            self.assertTrue(ns["caps_lock_on"](leds))
            Path(leds, "input3::capslock", "brightness").write_text("0\n")
            self.assertFalse(ns["caps_lock_on"](leds), "Num Lock must not be read as Caps Lock")
        self.assertIsNone(ns["caps_lock_on"]("/nonexistent/leds"))


class AgentUsesLiveKeymap(unittest.TestCase):
    def test_injector_and_bridge_route_through_the_live_keymap(self):
        injector = INJECTOR.read_text(encoding="utf-8")
        bridge = BRIDGE.read_text(encoding="utf-8")
        helper = HELPER.read_text(encoding="utf-8")
        self.assertIn("KeymapPlanner.TryPlan(run, keymap, out var plan)", injector)
        self.assertIn("new { layout = group.Code, group = group.Group }", injector)
        self.assertIn('new { type = "keysyms", text = true, events }', injector)
        self.assertIn('new { type = "keysyms", text = false, capsLock = viewerLock, events }', injector)
        self.assertIn("keymap?.ShortcutPosition(letter)", injector)
        self.assertIn("keymap.PlanPhysical(c, produced, out var group)", injector)
        self.assertIn("LiveKeymap.Parse(keymaps, compose, current)", bridge)
        self.assertIn('select_group(str(event["layout"]), send, event.get("group"))', helper)
        self.assertIn("event.update(keymaps=layout_state[\"keymaps\"], compose=layout_state[\"compose\"])", helper)
        self.assertIn("_keyboard_changed)", helper, "active-group changes must reach the agent")
        for retired in ("AraKeymap", "UsKeymap", "TextRunPlanner", "TryDirectStrokes"):
            for source in AGENT_LINUX.glob("*.cs"):
                self.assertNotIn(retired, source.read_text(encoding="utf-8"),
                                 f"{source.name} still uses the retired {retired} path")


def write_fixture():
    namespace = helper_namespace()
    groups = compiled(namespace)
    if groups is None:
        print("cannot write fixture: libxkbcommon/xkeyboard-config unavailable", file=sys.stderr)
        return 1
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"source": "tests/test_remote_live_keymap.py --write-fixture (ara,de; grp:alt_shift_toggle)",
               "keymaps": groups, "compose": namespace["keymap_composition"](groups)}
    FIXTURE.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {FIXTURE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        sys.exit(write_fixture())
    result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    sys.exit(0 if result.wasSuccessful() else 1)
