#!/usr/bin/python3
"""Compose and verify Android's on-demand unit on the finished edition tree."""
from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path

EDITIONS = {"moos": True, "moos-nvidia": True, "moos-cloud": False, "moos-arm": False}
UNIT = "usr/lib/systemd/user/moos-android-session.service"
PROVIDER = "usr/bin/waydroid"


def verify(root: Path, edition: str) -> None:
    supported = EDITIONS[edition]
    unit, provider = root / UNIT, root / PROVIDER
    for directory in ("etc/systemd/user", "usr/lib/systemd/user"):
        for kind in ("*.wants", "*.requires"):
            if any(p.name == Path(UNIT).name for target in (root / directory).glob(kind)
                   for p in target.iterdir()):
                raise ValueError("Android session must not be globally pulled into a target")
    if not supported:
        if unit.exists() or unit.is_symlink() or provider.exists() or provider.is_symlink():
            raise ValueError(f"{edition} must not ship the Android unit or provider")
        return
    if not unit.is_file() or unit.is_symlink() or not provider.is_file() or not os.access(provider, os.X_OK):
        raise ValueError(f"{edition} needs both the Android unit and executable provider")
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    config.read_string(unit.read_text())
    required = {
        "Unit": {"PartOf": "graphical-session.target", "After": "graphical-session.target",
                 "ConditionFileIsExecutable": "/usr/bin/waydroid", "ConditionEnvironment": "WAYLAND_DISPLAY"},
        "Service": {"Type": "exec", "ExecStart": "/usr/bin/waydroid session start",
                    "ExecStop": "/usr/bin/waydroid session stop", "TimeoutStopSec": "20", "Restart": "no"},
    }
    if config.has_section("Install") or any(
        config.get(section, key, fallback=None) != value
        for section, values in required.items() for key, value in values.items()
    ):
        raise ValueError("Android session must retain its direct, on-demand lifecycle contract")


def compose(root: Path, edition: str) -> None:
    if root.resolve() == Path("/") and (
        not Path("/run/.containerenv").exists() or Path("/run/ostree-booted").exists()
    ):
        raise ValueError("Android unit composition requires an unbooted image container")
    if not EDITIONS[edition]:
        provider = root / PROVIDER
        if provider.exists() or provider.is_symlink():
            raise ValueError(f"unexpected Android provider in {edition}; review edition policy")
        (root / UNIT).unlink(missing_ok=True)
    verify(root, edition)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("compose", "verify"))
    parser.add_argument("--root", type=Path, default=Path("/"))
    parser.add_argument("--edition", choices=EDITIONS, required=True)
    args = parser.parse_args()
    try:
        (compose if args.action == "compose" else verify)(args.root, args.edition)
    except (OSError, ValueError, configparser.Error) as error:
        parser.exit(1, f"GATE FAIL: Android edition closure: {error}\n")
    print(f"Android edition closure passed: {args.edition} ({args.action})")


if __name__ == "__main__":
    main()
