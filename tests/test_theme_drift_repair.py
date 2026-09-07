#!/usr/bin/env python3
"""A desktop that drifts from its own theme must repair itself.

Observed twice on the live Oracle machine, once across a reboot: every theme
surface read Arena -- LookAndFeelPackage, decoration, colour scheme, icons,
Plasma style -- while the desktop still showed the Graphite canvas, and
theme-state.json recorded Arena as committed. moos-selfcheck called it broken
and nothing repaired it.

moos-theme-sync.path watches ~/.config/kdeglobals, so it catches Global Theme
changes but never a wallpaper that drifts alone: that lives in the containment
config. The timer added here runs the same idempotent reconcile on a schedule.

Watching the containment file instead would be the obvious fix and the wrong
one -- plasmashell rewrites it on every applet move -- so this gate also refuses
that regression.
"""

import configparser
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-theme-drift.timer"
SERVICE = ROOT / "system_files/usr/lib/systemd/user/moos-theme-sync.service"

assert UNIT.is_file(), "the drift-repair timer is missing"

parser = configparser.ConfigParser(strict=False, allow_no_value=True)
parser.optionxform = str
parser.read(UNIT, encoding="utf-8")

# An enable with no [Install] prints a warning, returns 0, and creates NO wants
# symlink -- the unit stays static and never runs. That exact trap has shipped
# in this repo before.
assert parser.has_section("Install"), (
    "the timer has no [Install] section, so `systemctl --global enable` would "
    "return 0 and wire nothing")
assert parser["Install"].get("WantedBy") == "timers.target", \
    "the timer must be wanted by timers.target"

assert parser["Timer"].get("Unit") == "moos-theme-sync.service", (
    "the timer must drive the existing reconcile service rather than "
    "introducing a second repair path")
assert SERVICE.is_file(), "the service the timer drives does not exist"

# A repair that runs constantly is a different bug. Keep the period calm.
interval = parser["Timer"].get("OnUnitActiveSec", "")
assert interval.endswith("min") and int(interval[:-3]) >= 15, (
    f"reconcile period {interval!r} is too aggressive; it must stay calm "
    "because the point of the timer is to avoid a churny path watch")

# Both build paths must ship AND enable it.
for script, name in ((ROOT / "build_files/build.sh", "x86"),
                     (ROOT / "build_files/build-arm.sh", "ARM")):
    body = script.read_text(encoding="utf-8")
    code = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith("#"))
    assert "moos-theme-drift.timer" in code, \
        f"{name} build never enables the drift-repair timer"

# The rejected alternative must stay rejected.
for unit in ROOT.glob("system_files/usr/lib/systemd/user/*.path"):
    text = unit.read_text(encoding="utf-8")
    watched = [l for l in text.splitlines() if l.startswith("PathChanged=")]
    for line in watched:
        assert "plasma-org.kde.plasma.desktop-appletsrc" not in line, (
            f"{unit.name} watches the containment config; plasmashell rewrites "
            "it on every applet move, so this fires constantly")

print("theme drift repair gate passed")
