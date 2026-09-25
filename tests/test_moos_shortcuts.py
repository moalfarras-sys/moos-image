#!/usr/bin/env python3
"""Gate: every MoOS global shortcut is real, reachable and free.

WHY THIS EXISTS

Fast Remote shipped `X-KDE-GlobalAccel=Meta+R` for months. kglobalaccel never reads that key
(measured 2026-09-24: 18 registered components on the station, no org_moos_fastremote_desktop),
and Meta+R is Spectacle's stock "record region" binding. So the shortcut the dock comment, the
remote launcher and Mo PC Remote all promised did nothing, and would have fought Spectacle if it
had ever registered. Nothing tested any shortcut.

KDE's own apps declare a launch shortcut as `X-KDE-Shortcuts=` in their .desktop entry and link
that entry into /usr/share/kglobalaccel (Konsole, Spectacle, Dolphin, System Settings on the
host). kglobalaccel registers it, and System Settings > Shortcuts lists it for the person to
rebind. MoOS does the same, and this gate holds three rules:

  1. a MoOS entry never uses the dead X-KDE-GlobalAccel key;
  2. every X-KDE-Shortcuts value (and every default a MoOS KWin script registers) avoids the
     stock Plasma/KWin/app defaults and every other MoOS shortcut;
  3. every entry that declares X-KDE-Shortcuts has its kglobalaccel link, relative, in the tree
     (`../applications/<id>`), and every link names such an entry.

STOCK is the measured default map: the default column of every stock component in the station's
~/.config/kglobalshortcutsrc (Plasma 6.7.5, read-only, 2026-09-24; plasmashell's activity
cycling Meta+A / Meta+Shift+A is bound at runtime with an empty default and counts as taken),
plus the X-KDE-Shortcuts of every stock /usr/share/kglobalaccel entry. When this runs on a
machine that HAS /usr/share/kglobalaccel (the station, the image), those live entries are read
too, so a new stock binding arriving with a Plasma update is caught without editing this file.
"""

from __future__ import annotations

import configparser
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS = ROOT / "system_files/usr/share/applications"
KGLOBALACCEL = ROOT / "system_files/usr/share/kglobalaccel"
KWIN_SCRIPTS = ROOT / "system_files/usr/share/kwin/scripts"
HOST_KGLOBALACCEL = Path("/usr/share/kglobalaccel")

STOCK = {
    # plasmashell
    "Meta", "Alt+F1", "Ctrl+F12", "Meta+1", "Meta+2", "Meta+3", "Meta+4", "Meta+5", "Meta+6",
    "Meta+7", "Meta+8", "Meta+9", "Meta+Alt+P", "Meta+Ctrl+X", "Meta+Q", "Meta+V", "Meta+A",
    "Meta+Shift+A",
    # kwin
    "Alt+F3", "Alt+F4", "Alt+Shift+Tab", "Alt+Tab", "Alt+`", "Alt+~", "Ctrl+F1", "Ctrl+F2",
    "Ctrl+F3", "Ctrl+F4", "Ctrl+F7", "Ctrl+F9", "Ctrl+F10", "Launch (C)", "Meta++", "Meta+-",
    "Meta+0", "Meta+=", "Meta+Alt+Down", "Meta+Alt+Left", "Meta+Alt+Right", "Meta+Alt+Up",
    "Meta+Backspace", "Meta+Ctrl+A", "Meta+Ctrl+Down", "Meta+Ctrl+Esc", "Meta+Ctrl+Left",
    "Meta+Ctrl+Right", "Meta+Ctrl+Up", "Meta+Ctrl+Shift+Down", "Meta+Ctrl+Shift+Left",
    "Meta+Ctrl+Shift+Right", "Meta+Ctrl+Shift+Up", "Meta+D", "Meta+Down", "Meta+F1", "Meta+F2",
    "Meta+F3", "Meta+F4", "Meta+F5", "Meta+F6", "Meta+F7", "Meta+F9", "Meta+F10", "Meta+G",
    "Meta+Left", "Meta+PgDown", "Meta+PgUp", "Meta+Right", "Meta+Shift+Esc", "Meta+Shift+Left",
    "Meta+Shift+Right", "Meta+Shift+Tab", "Meta+T", "Meta+Tab", "Meta+Up", "Meta+W", "Meta+`",
    "Meta+~",
    # ksmserver, kaccess, keyboard layouts, power, sound, media
    "Ctrl+Alt+Del", "Meta+L", "Screensaver", "Meta+Alt+S", "Meta+Alt+K", "Meta+Alt+L",
    "Meta+B", "Battery", "Hibernate", "Sleep", "Power Down", "Power Off",
    "Monitor Brightness Up", "Monitor Brightness Down", "Shift+Monitor Brightness Up",
    "Shift+Monitor Brightness Down", "Keyboard Brightness Up", "Keyboard Brightness Down",
    "Keyboard Light On/Off", "Volume Up", "Volume Down", "Volume Mute", "Shift+Volume Up",
    "Shift+Volume Down", "Microphone Mute", "Meta+Volume Mute", "Microphone Volume Up",
    "Microphone Volume Down", "Media Play", "Media Pause", "Media Stop", "Media Next",
    "Media Previous", "Media Rewind", "Media Fast Forward",
    # /usr/share/kglobalaccel entries (Dolphin, Konsole, KRunner, KScreen, System Monitor,
    # Emoji Selector, Spectacle, touchpad, System Settings)
    "Meta+E", "Ctrl+Alt+T", "Alt+Space", "Alt+F2", "Search", "Alt+Shift+F2", "Display",
    "Meta+P", "Meta+Esc", "Meta+.", "Meta+Ctrl+Alt+Shift+Space", "Print", "Meta+Shift+S",
    "Shift+Print", "Meta+Print", "Meta+Shift+Print", "Meta+Ctrl+Print", "Meta+Shift+R", "Meta+R",
    "Meta+Alt+R", "Meta+Ctrl+R", "Touchpad On", "Touchpad Off", "Touchpad Toggle",
    "Meta+Ctrl+Touchpad Toggle", "Meta+Ctrl+Zenkaku Hankaku", "Tools", "Meta+I",
}
# The table may never be trimmed below what the task and the owner named as taken.
MUST_BE_TAKEN = ("Meta+R", "Meta+E", "Meta+I", "Meta+W", "Meta+D", "Meta+Tab", "Meta+A",
                 "Meta+Shift+A")

MODIFIERS = ("Meta", "Ctrl", "Alt", "Shift")
ALIASES = {"win": "Meta", "super": "Meta", "control": "Ctrl", "ctl": "Ctrl"}


def normalize(sequence: str) -> str:
    """One canonical, case-insensitive spelling: modifiers in Meta/Ctrl/Alt/Shift order."""
    text = sequence.strip()
    if not text:
        return ""
    # A trailing "+" key ("Meta++") must survive the split.
    parts = text[:-2].split("+") + ["+"] if text.endswith("++") else text.split("+")
    mods, keys = set(), []
    for part in (p.strip() for p in parts):
        name = ALIASES.get(part.lower(), part)
        canon = next((m for m in MODIFIERS if m.lower() == name.lower()), None)
        if canon and len(parts) > 1:
            mods.add(canon)
        else:
            keys.append(name.lower())
    return "+".join([m for m in MODIFIERS if m in mods] + keys).lower()


def sequences(value: str) -> list[str]:
    """X-KDE-Shortcuts separates alternatives with ','; kglobalshortcutsrc with a tab."""
    out = []
    for raw in re.split(r",|\t|\\t", value):
        if raw.strip() and raw.strip().lower() != "none":
            out.append(raw.strip())
    return out


def desktop_keys(path: Path) -> list[tuple[str, str, str]]:
    """(group, key, value) for every X-KDE-Shortcuts / X-KDE-GlobalAccel line, any group."""
    found, group = [], ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            group = stripped[1:-1]
            continue
        match = re.match(r"^(X-KDE-Shortcuts|X-KDE-GlobalAccel)\s*=\s*(.*)$", stripped)
        if match:
            found.append((group, match.group(1), match.group(2)))
    return found


def moos_shortcuts(applications: Path, kwin_scripts: Path) -> list[tuple[str, str]]:
    """(owner, sequence) for everything MoOS registers with kglobalaccel."""
    out = []
    for entry in sorted(applications.glob("*.desktop")):
        for group, key, value in desktop_keys(entry):
            if key == "X-KDE-Shortcuts":
                out += [(f"{entry.name} [{group}]", seq) for seq in sequences(value)]
    for script in sorted(kwin_scripts.rglob("*.js")) if kwin_scripts.is_dir() else []:
        code = script.read_text(encoding="utf-8")
        if "registerShortcut(" not in code:
            continue
        # Defaults may be passed literally or through a table (moos-arrange's ACTIONS), so every
        # shortcut-shaped literal in a script that registers shortcuts is a default it claims.
        for match in re.finditer(r'"((?:Meta|Ctrl|Alt|Shift)\+[^"\n]+)"', code):
            out.append((str(script.relative_to(kwin_scripts.parent)), match.group(1)))
    return out


def stock_defaults() -> set[str]:
    taken = {normalize(s) for s in STOCK}
    if HOST_KGLOBALACCEL.is_dir():
        for entry in HOST_KGLOBALACCEL.glob("*.desktop"):
            if entry.name.startswith("org.moos.") or not entry.exists():
                continue
            for _group, key, value in desktop_keys(entry):
                if key == "X-KDE-Shortcuts":
                    taken |= {normalize(s) for s in sequences(value)}
    return taken


def problems(applications: Path, kglobalaccel: Path, kwin_scripts: Path) -> list[str]:
    found = []
    for entry in sorted(applications.glob("*.desktop")):
        for group, key, value in desktop_keys(entry):
            if key == "X-KDE-GlobalAccel":
                found.append(f"{entry.name} [{group}]: X-KDE-GlobalAccel={value} is a key "
                             "kglobalaccel never reads; declare X-KDE-Shortcuts and link the "
                             "entry into usr/share/kglobalaccel")
    taken = stock_defaults()
    seen: dict[str, str] = {}
    for owner, sequence in moos_shortcuts(applications, kwin_scripts):
        canon = normalize(sequence)
        if canon in taken:
            found.append(f"{owner}: {sequence} is already a stock Plasma/KWin/app shortcut")
        if canon in seen and seen[canon] != owner:
            found.append(f"{owner}: {sequence} is also claimed by {seen[canon]}")
        seen.setdefault(canon, owner)
    declaring = {entry.name for entry in applications.glob("*.desktop")
                 if any(key == "X-KDE-Shortcuts" for _g, key, _v in desktop_keys(entry))}
    for name in sorted(declaring):
        link = kglobalaccel / name
        if not link.is_symlink():
            found.append(f"{name} declares X-KDE-Shortcuts but usr/share/kglobalaccel/{name} "
                         "is not a link to it, so kglobalaccel never registers the shortcut")
        elif os.readlink(link) != f"../applications/{name}":
            found.append(f"usr/share/kglobalaccel/{name} -> {os.readlink(link)}; it must be the "
                         f"relative ../applications/{name} so it resolves inside any root")
        elif not link.resolve().is_file():
            found.append(f"usr/share/kglobalaccel/{name} dangles")
    if kglobalaccel.is_dir():
        for link in sorted(kglobalaccel.iterdir()):
            if link.name not in declaring:
                found.append(f"usr/share/kglobalaccel/{link.name} names no entry that declares "
                             "X-KDE-Shortcuts")
    return found


class MoOSShortcuts(unittest.TestCase):
    def test_the_stock_table_was_not_trimmed(self):
        for sequence in MUST_BE_TAKEN:
            self.assertIn(normalize(sequence), stock_defaults(), sequence)

    def test_every_moos_shortcut_is_real_free_and_linked(self):
        self.assertEqual(problems(APPLICATIONS, KGLOBALACCEL, KWIN_SCRIPTS), [])

    def test_mo_ai_is_summoned_with_meta_space(self):
        """Spec D6: Mo AI is part of the desktop, one chord away, rebindable in System Settings."""
        declared = [value for _g, key, value
                    in desktop_keys(APPLICATIONS / "org.moos.moai.desktop")
                    if key == "X-KDE-Shortcuts"]
        self.assertEqual([normalize(s) for v in declared for s in sequences(v)],
                         [normalize("Meta+Space")])
        self.assertTrue((KGLOBALACCEL / "org.moos.moai.desktop").is_symlink())
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read(KGLOBALACCEL / "org.moos.moai.desktop", encoding="utf-8")
        self.assertEqual(parser["Desktop Entry"]["Exec"], "moai",
                         "the link must reach the Mo AI entry itself")

    def test_fast_remote_no_longer_promises_meta_r(self):
        keys = desktop_keys(APPLICATIONS / "org.moos.fastremote.desktop")
        self.assertEqual(keys, [], "Fast Remote is a switch inside Mo PC Remote, not a shortcut")
        layout = (ROOT / "system_files/usr/share/plasma/layout-templates/"
                  "org.kde.plasma.desktop.defaultPanel/contents/layout.js").read_text("utf-8")
        self.assertNotIn("back the Meta+R global shortcut", layout)


class TheCheckerBites(unittest.TestCase):
    """The checker itself, on synthetic trees: each rule must fire on its own defect."""

    def tree(self, entries: dict[str, str], links: dict[str, str]) -> tuple[Path, Path, Path]:
        root = Path(self.tmp.name)
        apps, accel, scripts = root / "applications", root / "kglobalaccel", root / "scripts"
        for folder in (apps, accel, scripts):
            folder.mkdir(parents=True, exist_ok=True)
        for name, body in entries.items():
            (apps / name).write_text("[Desktop Entry]\nType=Application\nExec=x\n" + body,
                                     encoding="utf-8")
        for name, target in links.items():
            os.symlink(target, accel / name)
        return apps, accel, scripts

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_stock_chord_is_refused_in_any_spelling(self):
        for spelling in ("Meta+E", "meta+e", "Shift+Meta+A", "Super+R", "Alt+Ctrl+Del"):
            with self.subTest(spelling=spelling):
                apps, accel, scripts = self.tree(
                    {"org.moos.x.desktop": f"X-KDE-Shortcuts={spelling}\n"},
                    {"org.moos.x.desktop": "../applications/org.moos.x.desktop"})
                self.assertTrue(any("stock" in p for p in problems(apps, accel, scripts)))
                self.tmp.cleanup()
                self.tmp = tempfile.TemporaryDirectory()

    def test_the_dead_key_a_missing_link_and_a_collision_are_refused(self):
        apps, accel, scripts = self.tree(
            {"org.moos.a.desktop": "X-KDE-GlobalAccel=Meta+J\n",
             "org.moos.b.desktop": "X-KDE-Shortcuts=Meta+J\n",
             "org.moos.c.desktop": "X-KDE-Shortcuts=Meta+Shift+J\n",
             "org.moos.d.desktop": "X-KDE-Shortcuts=Meta+Shift+J\n"},
            {"org.moos.c.desktop": "/usr/share/applications/org.moos.c.desktop",
             "org.moos.d.desktop": "../applications/org.moos.d.desktop",
             "org.moos.e.desktop": "../applications/org.moos.e.desktop"})
        found = "\n".join(problems(apps, accel, scripts))
        self.assertIn("org.moos.a.desktop [Desktop Entry]: X-KDE-GlobalAccel", found)
        self.assertIn("org.moos.b.desktop declares X-KDE-Shortcuts but", found)
        self.assertIn("-> /usr/share/applications/org.moos.c.desktop", found)
        self.assertIn("is also claimed by", found)
        self.assertIn("org.moos.e.desktop names no entry", found)

    def test_a_kwin_script_default_is_checked_too(self):
        apps, accel, scripts = self.tree({}, {})
        code = scripts / "moos-x/contents/code"
        code.mkdir(parents=True)
        (code / "main.js").write_text(
            'registerShortcut("MoOS X", "MoOS X", "Meta+W", function() {});\n', encoding="utf-8")
        self.assertTrue(any("Meta+W is already a stock" in p for p in problems(apps, accel, scripts)))

    def test_normalize(self):
        self.assertEqual(normalize("Meta++"), "meta++")
        self.assertEqual(normalize("Shift+Meta+Tab"), normalize("Meta+Shift+Tab"))
        self.assertEqual(normalize("Meta"), "meta")
        self.assertNotEqual(normalize("Meta+Space"), normalize("Alt+Space"))


if __name__ == "__main__":
    result = unittest.main(exit=False, verbosity=1).result
    sys.exit(0 if result.wasSuccessful() else 1)
