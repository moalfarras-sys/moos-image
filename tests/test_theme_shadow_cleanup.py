#!/usr/bin/env python3
"""Regression test for post-marker user-local MoOS theme shadows."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"


def extract_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n", start) + 3
    return source[start:end]


with tempfile.TemporaryDirectory(prefix="moos-shadow-test-") as temporary:
    root = Path(temporary)
    user_share = root / "user-share"
    system_share = root / "system-share"
    shadow = user_share / "plasma/desktoptheme/MoOSUI2Arena"
    official = system_share / "plasma/desktoptheme/MoOSUI2Arena"
    shadow.mkdir(parents=True)
    official.mkdir(parents=True)
    (shadow / "tasks.svg").write_text("preview", encoding="utf-8")
    (official / "tasks.svg").write_text("image", encoding="utf-8")
    unrelated = user_share / "plasma/desktoptheme/PersonalTheme"
    unrelated.mkdir(parents=True)

    script = root / "probe.sh"
    script.write_text(
        "set -euo pipefail\n"
        f"HOME={root / 'home'}\n"
        f"XDG_DATA_HOME={user_share}\n"
        f"MOOS_SYSTEM_SHARE={system_share}\n"
        f"log={root / 'apply.log'}\n"
        f"{extract_function(APPLY.read_text(encoding='utf-8'), 'quarantine_moos_data_shadows')}\n"
        "quarantine_moos_data_shadows\n"
        "test ! -e \"$XDG_DATA_HOME/plasma/desktoptheme/MoOSUI2Arena\"\n"
        "test -e \"$XDG_DATA_HOME/plasma/desktoptheme/PersonalTheme\"\n"
        "test -n \"$(find \"$XDG_DATA_HOME/MoOS/theme-shadow-backups\" -path '*/plasma/desktoptheme/MoOSUI2Arena/tasks.svg' -print -quit)\"\n"
        "quarantine_moos_data_shadows\n"
        "test -e \"$XDG_DATA_HOME/plasma/desktoptheme/PersonalTheme\"\n",
        encoding="utf-8",
    )
    result = subprocess.run([BASH, str(script)], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(result.stderr or result.stdout)

print("OK: a post-marker MoOS shadow is quarantined and cleanup is idempotent")
