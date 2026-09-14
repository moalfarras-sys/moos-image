#!/usr/bin/env python3
"""Verify MoOS sounds against the KDE event definitions in a finished image.

This reads files only: it never contacts the session bus or plays audio. Check
the packages that own core desktop/power/accessibility events; application
packages outside this list may legitimately ship their own sound files.
"""

from __future__ import annotations

import argparse
import configparser
from pathlib import Path


COMPONENTS = (
    "plasma_workspace", "powerdevil", "devicenotifications", "kaccess",
    "konsole", "kwrited", "oom_notifier", "plasma_applet_timer",
    "polkit-kde-authentication-agent-1",
)
REQUIRED_COMPONENTS = {"plasma_workspace", "powerdevil"}


def read_config(path: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.optionxform = str
    with path.open(encoding="utf-8") as handle:
        config.read_file(handle)
    return config


def verify(image_root: Path, overlay_root: Path | None = None) -> list[str]:
    """Read installed KDE definitions; optionally use source MoOS overlay files."""
    overlay = overlay_root if overlay_root is not None else image_root
    events_dir = image_root / "usr/share/knotifications6"
    sound_dir = overlay / "usr/share/sounds/moos/stereo"
    errors = []
    for component in COMPONENTS:
        event_path = events_dir / f"{component}.notifyrc"
        if not event_path.is_file():
            if component in REQUIRED_COMPONENTS:
                errors.append(f"missing core KDE event definitions: {component}")
            continue
        upstream = read_config(event_path)
        override_path = overlay / "etc/xdg" / f"{component}.notifyrc"
        if override_path.exists():
            override = read_config(override_path)
            for section in override.sections():
                if section.startswith("Event/") and not upstream.has_section(section):
                    errors.append(f"unknown KDE event: {component}/{section}")
            upstream.read(override_path, encoding="utf-8")
        for section in upstream.sections():
            if not section.startswith("Event/"):
                continue
            event = upstream[section]
            sound_name = event.get("Sound", "")
            if "Sound" in event.get("Action", "").split("|") and not sound_name:
                errors.append(f"audible event has no Sound: {component}/{section}")
            # Disabled optional events still need an original sound if the user
            # enables them in KDE Settings. Do not fall through to another family.
            if not sound_name:
                continue
            if Path(sound_name).name != sound_name:
                errors.append(f"non-themable core sound: {component}/{section}/{sound_name}")
                continue
            target = sound_dir / f"{sound_name}.oga"
            if not target.is_file() or target.stat().st_size < 2_000:
                errors.append(f"missing MoOS sound: {component}/{section}/{sound_name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/"))
    parser.add_argument("--overlay-root", type=Path)
    args = parser.parse_args()
    try:
        errors = verify(args.root, args.overlay_root)
    except (OSError, configparser.Error) as error:
        errors = [str(error)]
    for error in errors:
        print(f"MoOS sound gate: {error}")
    if errors:
        return 1
    print("MoOS sound gate: core KDE events resolve to the original MoOS family")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
