#!/usr/bin/env python3
"""Gate: every edition ships what MoOS's own desktop depends on, whoever supplied it.

WHY THIS EXISTS

The x86 editions build FROM kinoite-main, which carries KDE's full desktop; the ARM edition starts
from bare fedora-bootc and gets only what build-arm.sh names. Anything x86 inherits for free has
to be asked for by name on ARM, and no gate asked. Read on the A1 (moos-arm 44.20260923.568) on
2026-09-24, against the published x86 base:

  * qt6-qttranslations was absent, so Qt never learned that Arabic is right-to-left. The MoOS Bar
    in the Arabic session read left-to-right (brand left, clock right), while the x86 station's
    bar is mirrored, as the design contract requires.
  * pw-dump was absent. moos-privacy-monitor was "active (running)" for the whole session and
    spawned a failing pw-dump every 1.5 s, so the Island's camera/microphone/screen chip could
    never name an app on ARM.
  * moos-theme writes gtk-theme-name=Breeze, and /usr/share/themes held only Default and Emacs;
    kde-gtk-config's gtkconfig module was absent too. Every GTK app fell back to Adwaita.
  * No Sonnet plugin existed, so no KDE text field could spell-check, although the Arabic and
    English Hunspell dictionaries were installed.
  * No ALSA configuration routed ALSA clients into PipeWire.
  * Neither kdialog nor zenity existed, and App Drop's consent question treats "no dialog tool"
    as No: `ask()` returned False on the live A1, so no AppImage or dropped file could ever
    install there, and moos-run-foreign could not prompt either.

This gate names CAPABILITIES, not packages, and checks the finished filesystem of either
architecture, so it does not care which base supplied them. Each check says what the owner loses.
It also reads the bar's own layout template, so an applet the MoOS Bar places, or a status item it
pins, can never be missing from the edition that draws it.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LAYOUT = "usr/share/plasma/layout-templates/org.kde.plasma.desktop.defaultPanel/contents/layout.js"
APPLET_DIRS = ("usr/share/plasma/plasmoids/{id}/metadata.json",
               "usr/lib64/qt6/plugins/plasma/applets/{id}.so",
               "usr/lib/qt6/plugins/plasma/applets/{id}.so")

# (what the owner loses, [alternatives — any one satisfies the check])
CAPABILITIES: list[tuple[str, list[str]]] = [
    ("Arabic right-to-left detection for every Qt and KDE surface, including the MoOS Bar's mirroring",
     ["usr/share/qt6/translations/qtbase_ar.qm"]),
    ("the Island's privacy chip: moos-privacy-monitor reads PipeWire through pw-dump",
     ["usr/bin/pw-dump"]),
    ("GTK 3 apps wearing the theme moos-theme selects (gtk-theme-name=Breeze)",
     ["usr/share/themes/Breeze/gtk-3.0/gtk.css"]),
    ("GTK 4 apps wearing the theme moos-theme selects (gtk-theme-name=Breeze)",
     ["usr/share/themes/Breeze/gtk-4.0/gtk.css"]),
    ("Plasma keeping GTK fonts, icons and cursor in step with the MoOS look",
     ["usr/lib64/qt6/plugins/kf6/kded/gtkconfig.so", "usr/lib/qt6/plugins/kf6/kded/gtkconfig.so"]),
    ("spell checking in KDE text fields",
     ["usr/lib64/qt6/plugins/kf6/sonnet/sonnet_hunspell.so",
      "usr/lib/qt6/plugins/kf6/sonnet/sonnet_hunspell.so"]),
    ("ALSA-only applications playing through PipeWire instead of seizing the sound card",
     ["usr/share/alsa/alsa.conf.d/99-pipewire-default.conf",
      "etc/alsa/conf.d/99-pipewire-default.conf"]),
    ("App Drop's default-No consent dialog: without it every dropped or double-clicked app is refused",
     ["usr/bin/kdialog"]),
]


def applet_exists(root: Path, plugin: str) -> bool:
    return any((root / pattern.format(id=plugin)).exists() for pattern in APPLET_DIRS)


def bar_applets(layout_js: str) -> tuple[list[str], list[str]]:
    """Plugins the MoOS Bar template places, and the status items it pins as always shown."""
    code = re.sub(r"/\*.*?\*/", "", layout_js, flags=re.S)
    code = "\n".join(line.split("//", 1)[0] for line in code.splitlines())
    placed = re.findall(r'panel\.addWidget\("([^"]+)"\)', code)
    shown = re.search(r'writeConfig\("shownItems",\s*"([^"]*)"\)', code)
    pinned = [item for item in (shown.group(1).split(",") if shown else []) if item]
    return placed, pinned


def problems(root: Path) -> list[str]:
    found = []
    for loss, alternatives in CAPABILITIES:
        if not any((root / path).exists() for path in alternatives):
            found.append(f"{loss} — none of: {', '.join('/' + p for p in alternatives)}")
    layout = root / LAYOUT
    if not layout.is_file():
        found.append(f"the MoOS Bar template is missing: /{LAYOUT}")
        return found
    placed, pinned = bar_applets(layout.read_text(encoding="utf-8"))
    if not placed:
        found.append("the MoOS Bar template places no applet: the parser no longer matches it")
    for plugin in placed:
        if not applet_exists(root, plugin):
            found.append(f"the MoOS Bar places {plugin}, which this edition does not ship")
    for plugin in pinned:
        if not applet_exists(root, plugin):
            found.append(f"the MoOS Bar pins status item {plugin}, which this edition does not ship")
    return found


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="/")
    args = ap.parse_args(argv)
    root = Path(args.root)
    found = problems(root)
    for item in found:
        print(f"GATE FAIL: {item}", file=sys.stderr)
    if found:
        print("           An edition that lacks these draws a MoOS that does less than the other "
              "one. Install the capability in that edition's build script.", file=sys.stderr)
        return 1
    placed, pinned = bar_applets((root / LAYOUT).read_text(encoding="utf-8"))
    print(f"MoOS desktop parity OK: {len(CAPABILITIES)} capabilities, "
          f"{len(placed)} bar applets, {len(pinned)} pinned status items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
