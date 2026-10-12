#!/usr/bin/python3
"""Read the effective Settings launcher; retire only reviewed legacy hiding bytes.

The image's desktop entry is weaker than XDG_DATA_HOME. Checking /usr alone
missed an ordinary account with no visible Settings entry. No service is started
and no launcher is executed here. Unknown owner overrides are reported, preserved.
"""
from __future__ import annotations

import configparser
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile

CANONICAL = "systemsettings.desktop"
ALIASES = ("org.moos.settings.desktop", "kdesystemsettings.desktop")
# Actual Oracle 2026-10-12 readback: the old vendor entry with NoDisplay=true.
# Do not expand this set without reviewing the full bytes and a native control.
LEGACY_HIDDEN = frozenset({"f964152228a7c889342c1bed7f9332f91332250805707fdf1ae1791bc197e8f8"})
MAX_ENTRY = 1024 * 1024


def read_entry(path: Path) -> tuple[bytes, dict[str, str]]:
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ENTRY:
            raise ValueError("Settings launcher is not a bounded regular file")
        data = stream.read(MAX_ENTRY + 1)
    if len(data) > MAX_ENTRY:
        raise ValueError("Settings launcher exceeds the read limit")
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(data.decode("utf-8"))
    return data, dict(parser["Desktop Entry"])


def data_roots() -> list[Path]:
    home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [home, *(Path(p) for p in system.split(":") if p and Path(p).is_absolute())]


def effective_entry(roots: list[Path], name: str) -> dict[str, str] | None:
    for root in roots:
        path = root / "applications" / name
        # A broken link still shadows the image; never silently skip it.
        if path.exists() or path.is_symlink():
            return read_entry(path)[1]
    return None


def hidden(entry: dict[str, str]) -> bool:
    if any(entry.get(k, "").lower() == "true" for k in ("Hidden", "NoDisplay")):
        return True
    desktops = set((os.environ.get("XDG_CURRENT_DESKTOP") or "KDE").split(":"))
    only = set(filter(None, entry.get("OnlyShowIn", "").split(";")))
    excluded = set(filter(None, entry.get("NotShowIn", "").split(";")))
    return bool((only and not desktops.intersection(only)) or desktops.intersection(excluded))


def check(roots: list[Path]) -> None:
    entry = effective_entry(roots, CANONICAL)
    if entry is None or hidden(entry):
        raise ValueError("the effective MoOS Settings launcher is missing or hidden")
    expected = {"Type": "Application", "Name": "MoOS Settings", "Name[ar]": "إعدادات MoOS",
                "Exec": "moos-settings", "Icon": "moos-control-center",
                "StartupWMClass": "systemsettings"}
    if any(entry.get(k) != v for k, v in expected.items()):
        raise ValueError("an effective Settings override bypasses the MoOS entry")
    for name in ALIASES:
        alias = effective_entry(roots, name)
        if alias is not None and not hidden(alias):
            raise ValueError("a second Settings launcher is visible")


def repair(roots: list[Path]) -> Path | None:
    # Require the image to supply a working canonical replacement first.
    check(roots[1:])
    source = roots[0] / "applications" / CANONICAL
    if not source.exists() and not source.is_symlink():
        return None
    data, entry = read_entry(source)
    if hashlib.sha256(data).hexdigest() not in LEGACY_HIDDEN:
        return None
    if entry.get("NoDisplay") != "true" or source.stat().st_uid != os.geteuid():
        raise ValueError("reviewed Settings shadow ownership or state changed")
    parent = roots[0] / "MoOS/launcher-shadow-backups"
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = Path(tempfile.mkdtemp(prefix="settings-", dir=parent)) / CANONICAL
    source.rename(backup)
    return backup


def main() -> int:
    if sys.argv[1:] not in (["check"], ["repair"]):
        print("Usage: moos_settings_launcher.py check|repair", file=sys.stderr)
        return 2
    try:
        roots = data_roots()
        if sys.argv[1] == "repair":
            backup = repair(roots)
            if backup:
                print("Restored the image's MoOS Settings launcher; legacy copy preserved.")
        else:
            check(roots)
    except (OSError, ValueError, KeyError, configparser.Error) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
