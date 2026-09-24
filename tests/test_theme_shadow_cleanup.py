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

# THEME_REV 86: KWin's MoOS packages are quarantined the same way (the station ran a stale
# review copy of the task switcher for a week). A user's own KWin script and a MoOS-looking id
# the image does not ship are never touched; the caller learns that KWin must re-read.
with tempfile.TemporaryDirectory(prefix="moos-kwin-shadow-test-") as temporary:
    root = Path(temporary)
    user_share = root / "user-share"
    system_share = root / "system-share"
    for rel in ("kwin/tabbox/org.moos.ui2.switcher/contents/ui/main.qml",
                "kwin/scripts/moos-arrange/contents/code/main.js"):
        for base, body in ((user_share, "review"), (system_share, "image")):
            target = base / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
    own = user_share / "kwin/scripts/krohnkite/metadata.json"
    own.parent.mkdir(parents=True)
    own.write_text("{}", encoding="utf-8")
    unshipped = user_share / "kwin/effects/org.moos.experiment/metadata.json"
    unshipped.parent.mkdir(parents=True)
    unshipped.write_text("{}", encoding="utf-8")

    script = root / "probe.sh"
    script.write_text(
        "set -euo pipefail\n"
        f"HOME={root / 'home'}\n"
        f"XDG_DATA_HOME={user_share}\n"
        f"MOOS_SYSTEM_SHARE={system_share}\n"
        f"log={root / 'apply.log'}\n"
        "quarantined_kwin=0\n"
        f"{extract_function(APPLY.read_text(encoding='utf-8'), 'quarantine_moos_data_shadows')}\n"
        "quarantine_moos_data_shadows\n"
        "test \"$quarantined_kwin\" = 1\n"
        "test ! -e \"$XDG_DATA_HOME/kwin/tabbox/org.moos.ui2.switcher\"\n"
        "test ! -e \"$XDG_DATA_HOME/kwin/scripts/moos-arrange\"\n"
        "test -e \"$XDG_DATA_HOME/kwin/scripts/krohnkite/metadata.json\"\n"
        "test -e \"$XDG_DATA_HOME/kwin/effects/org.moos.experiment/metadata.json\"\n"
        "test \"$(cat \"$(find \"$XDG_DATA_HOME/MoOS/theme-shadow-backups\" "
        "-path '*/kwin/tabbox/org.moos.ui2.switcher/contents/ui/main.qml' -print -quit)\")\" = review\n"
        "test -n \"$(find \"$XDG_DATA_HOME/MoOS/theme-shadow-backups\" "
        "-path '*/kwin/scripts/moos-arrange/contents/code/main.js' -print -quit)\"\n"
        # Idempotent, and a second pass with nothing to move asks nothing of KWin.
        "quarantined_kwin=0\n"
        "quarantine_moos_data_shadows\n"
        "test \"$quarantined_kwin\" = 0\n",
        encoding="utf-8",
    )
    # The function makes no D-Bus call; isolate the bus anyway, as every test that runs MoOS
    # desktop code must.
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root / "home"),
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root / 'no-bus'}"}
    result = subprocess.run([BASH, str(script)], capture_output=True, text=True, env=env)
    if result.returncode:
        raise SystemExit("KWin shadow quarantine: " + (result.stderr or result.stdout))
    apply = APPLY.read_text(encoding="utf-8")
    caller = apply.split("\nquarantine_moos_data_shadows\n", 1)[1][:700]
    if "--expect-reply=no" not in caller or 'quarantined_kwin" = "1"' not in caller:
        raise SystemExit("a quarantined KWin package must make KWin re-read (no-reply call)")

print("OK: a post-marker MoOS shadow is quarantined and cleanup is idempotent "
      "(Plasma data and KWin packages)")
