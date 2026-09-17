#!/usr/bin/env python3
"""Gate: a shipped KConfig key must live in a group, and the system defaults must agree with the
default Global Theme.

WHY THIS EXISTS

On 2026-08-28 (a6527c83) a paragraph was added above two group headers and the `#` ran one line
too far:

    /etc/xdg/kdeglobals        #[Icons]          /etc/xdg/plasmarc        #[Theme]
                               Theme=MoOSUI2                              name=MoOSUI2Aurora

KConfig does not warn about either. In kdeglobals the key fell into the still-open [General]
group, which nothing reads for an icon theme; in plasmarc it preceded every group, so the file
configured nothing at all. The system-wide default icon theme and Plasma Style silently became
Plasma's own for three weeks.

Nothing noticed, because applying a Global Theme copies [Icons] and [Theme] into the USER's
config and that outranks /etc/xdg. The sessions that still read the system default are exactly
the ones nobody photographs: a second account, the first frames of a first login, an application
started as another user. Every gate that mentions these files matched a substring
(`"Theme=MoOSUI2" in text`), and a commented-out header leaves every substring in place.

This gate parses the files the way KConfig does.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XDG = ROOT / "system_files/etc/xdg"
LNF = ROOT / "system_files/usr/share/plasma/look-and-feel"

GROUP = re.compile(r"^\[.+\]$")
COMMENTED_GROUP = re.compile(r"^#\s*\[[A-Za-z][^\]]*\]$")
KEY = re.compile(r"^[A-Za-z][^=\[\]#]*(\[[^\]]*\])*\s*=")


def kconfig_files() -> list[Path]:
    """Every shipped file with KConfig/ini group syntax that a desktop component reads."""
    files = [p for p in XDG.rglob("*") if p.is_file()]
    files += [p for p in LNF.glob("*/contents/defaults")]
    files += list((ROOT / "system_files/usr/share").glob("plasma/shells/*/contents/defaults"))
    files += list((ROOT / "system_files/usr/share/moos").glob("*.conf"))
    return sorted(set(files))


def parse(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    groups: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    group: str | None = None
    previous = ""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return groups, problems
    if not any(GROUP.match(l.strip()) or COMMENTED_GROUP.match(l.strip()) for l in lines):
        return groups, problems          # not a grouped file (mimeapps-style lists have groups too)
    rel = path.relative_to(ROOT).as_posix()
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if GROUP.match(line):
            group = line
            groups.setdefault(group, {})
        elif KEY.match(line):
            key, _, value = line.partition("=")
            if group is None:
                problems.append(f"{rel}:{number}: `{line}` comes before any group header, so it "
                                "belongs to no group and configures nothing")
            elif COMMENTED_GROUP.match(previous):
                problems.append(f"{rel}:{number}: `{line}` follows the commented-out header "
                                f"`{previous}` and therefore lands in {group}, which is not where "
                                "its reader looks")
            if group is not None:
                groups[group][key.strip()] = value.strip()
        if line:
            previous = line
    return groups, problems


def main() -> int:
    errors: list[str] = []
    parsed: dict[str, dict[str, dict[str, str]]] = {}
    files = kconfig_files()
    for path in files:
        groups, problems = parse(path)
        parsed[path.relative_to(ROOT).as_posix()] = groups
        errors += problems

    kdeglobals = parsed.get("system_files/etc/xdg/kdeglobals", {})
    plasmarc = parsed.get("system_files/etc/xdg/plasmarc", {})
    lnf_name = kdeglobals.get("[KDE]", {}).get("LookAndFeelPackage", "")
    defaults = parsed.get(f"system_files/usr/share/plasma/look-and-feel/{lnf_name}/contents/defaults")
    if not lnf_name or defaults is None:
        errors.append(f"/etc/xdg/kdeglobals names LookAndFeelPackage={lnf_name!r}, which is not a "
                      "shipped look-and-feel package with a contents/defaults file")
    else:
        # The system default and the default Global Theme are two routes to one desktop. When they
        # disagree, which one the user sees depends on whether a theme was ever applied for them.
        pairs = (
            ("icon theme", kdeglobals.get("[Icons]", {}).get("Theme"),
             defaults.get("[kdeglobals][Icons]", {}).get("Theme")),
            ("colour scheme", kdeglobals.get("[General]", {}).get("ColorScheme"),
             defaults.get("[kdeglobals][General]", {}).get("ColorScheme")),
            ("Plasma Style", plasmarc.get("[Theme]", {}).get("name"),
             defaults.get("[plasmarc][Theme]", {}).get("name")),
        )
        for label, system_value, theme_value in pairs:
            if not system_value:
                errors.append(f"/etc/xdg sets no default {label}: a session that never had a "
                              "Global Theme applied draws Plasma's own")
            elif system_value != theme_value:
                errors.append(f"default {label} disagrees: /etc/xdg says {system_value!r}, the "
                              f"default Global Theme {lnf_name} says {theme_value!r}")
    if "Theme" in kdeglobals.get("[General]", {}):
        errors.append("/etc/xdg/kdeglobals has `Theme=` inside [General] — that is the icon theme "
                      "key stranded by a missing [Icons] header")

    if errors:
        print("GATE FAIL: tests/test_kconfig_group_headers.py")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"KConfig group gate passed ({len(files)} shipped config files: every key is inside a "
          f"group, and /etc/xdg agrees with the default Global Theme {lnf_name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
