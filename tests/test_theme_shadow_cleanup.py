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
    caller = apply.split("\n# A moved KWin package", 1)[1][:700]
    assert "if ! quarantine_moos_data_shadows; then" in apply
    if "--expect-reply=no" not in caller or 'quarantined_kwin" = "1"' not in caller:
        raise SystemExit("a quarantined KWin package must make KWin re-read (no-reply call)")

# A publisher icon registered as moos-antigravity-ide vanished on the actual
# reboot. Prefix ownership must not erase app exports. Exercise the same native
# quarantine with exact image files, unrelated names and an outside symlink.
with tempfile.TemporaryDirectory(prefix="moos-hicolor-shadow-test-") as temporary:
    root = Path(temporary)
    user_share, system_share = root / "user-share", root / "system-share"
    known = "icons/hicolor/512x512/apps/moos-store.png"
    for base, body in ((user_share, "preview"), (system_share, "image")):
        icon = base / known
        icon.parent.mkdir(parents=True)
        icon.write_text(body)
    preserved = [
        "icons/hicolor/512x512/apps/moos-antigravity-ide.png",
        "icons/hicolor/512x512/apps/moos-vscode-native.png",
        "icons/hicolor/512x512/apps/org.moos.personal.png",
        "icons/hicolor/512x512/apps/third-party.png",
        # Another size has no image counterpart: preserve unknown state.
        "icons/hicolor/123x123/apps/moos-store.png",
    ]
    for relative in preserved:
        icon = user_share / relative
        icon.parent.mkdir(parents=True, exist_ok=True)
        icon.write_text("publisher")
    outside = root / "outside.png"
    outside.write_text("outside")
    linked = user_share / "icons/hicolor/512x512/apps/moos-welcome.png"
    linked.symlink_to(outside)
    (system_share / linked.relative_to(user_share)).write_text("image")
    script = (
        "set -euo pipefail\n"
        f"XDG_DATA_HOME='{user_share}'\nMOOS_SYSTEM_SHARE='{system_share}'\n"
        f"log='{root / 'apply.log'}'\n"
        "quarantined_kwin=0\n"
        + extract_function(APPLY.read_text(encoding="utf-8"), "quarantine_moos_data_shadows")
        + "\nquarantine_moos_data_shadows\nquarantine_moos_data_shadows\n"
    )
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root / "home"),
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root / 'no-bus'}"}
    result = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True)
    if result.returncode:
        raise SystemExit("hicolor quarantine: " + (result.stderr or result.stdout))
    assert not (user_share / known).exists(), "known icon still shadows the image"
    backups = list((user_share / "MoOS/theme-shadow-backups").glob(f"*/{known}"))
    assert len(backups) == 1 and backups[0].read_text() == "preview"
    assert (system_share / known).read_text() == "image"
    for relative in preserved:
        assert (user_share / relative).read_text() == "publisher", relative
    assert linked.is_symlink() and outside.read_text() == "outside"
    # Reinserting the old prefix deletion after quarantine must break the app
    # preservation assertion. This negative never touches a real user share.
    old_delete = 'find "$XDG_DATA_HOME/icons/hicolor" -type f -name "moos-*" -delete\n'
    result = subprocess.run([BASH, "-c", script + old_delete], env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not (user_share / preserved[0]).exists(), "old destructive control did not execute"
    assert linked.is_symlink() and outside.read_text() == "outside"

# The timestamp is a label, not an exclusive recovery destination. Two fast
# applies must retain BOTH versions of a file and a package. A private clock
# provider makes the same-second class deterministic without changing the host.
with tempfile.TemporaryDirectory(prefix="moos-shadow-collision-test-") as temporary:
    root = Path(temporary)
    binary = root / "bin"
    binary.mkdir()
    date = binary / "date"
    date.write_text("#!/bin/sh\nprintf '%s\\n' '20261024T010000Z'\n")
    date.chmod(0o700)
    function = extract_function(APPLY.read_text(), "quarantine_moos_data_shadows")
    for label, implementation in (
        ("fixed", function),
        ("old-collision", function.replace(
            'backup="$(mktemp -d "${backup_root}/${stamp}.XXXXXX")"',
            'backup="${backup_root}/${stamp}"')),
    ):
        private = root / label
        user_share, system_share = private / "user", private / "system"
        icon = "icons/hicolor/512x512/apps/moos-store.png"
        theme = "plasma/desktoptheme/MoOSUI2Arena/tasks.svg"
        for relative in (icon, theme):
            for base, body in ((user_share, "first"), (system_share, "image")):
                target = base / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)
        env = {"PATH": f"{binary}:/usr/bin:/bin", "HOME": str(private / "home"),
               "XDG_DATA_HOME": str(user_share), "MOOS_SYSTEM_SHARE": str(system_share),
               "DBUS_SESSION_BUS_ADDRESS": f"unix:path={private / 'no-bus'}"}
        script = (f"set -euo pipefail\nlog='{private / 'log'}'\nquarantined_kwin=0\n"
                  + implementation + "\nquarantine_moos_data_shadows\n"
                  + f"mkdir -p '{(user_share / theme).parent}'\n"
                  + f"printf second > '{user_share / icon}'\n"
                  + f"printf second > '{user_share / theme}'\n"
                  + "quarantine_moos_data_shadows\n")
        result = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        recovery = user_share / "MoOS/theme-shadow-backups"
        icon_copies = sorted(p.read_text() for p in recovery.glob(f"*/{icon}"))
        theme_copies = sorted(p.read_text() for p in recovery.glob(f"*/{theme}"))
        if label == "fixed":
            assert icon_copies == ["first", "second"], icon_copies
            assert theme_copies == ["first", "second"], theme_copies
            assert not (user_share / icon).exists() and not (user_share / theme).exists()
            assert all(p.stat().st_mode & 0o077 == 0 for p in recovery.iterdir())
        else:
            assert icon_copies == ["second"], "old overwrite control did not execute"

# Refused recovery storage must stop the actual caller before later migration
# cleanup. An unrelated regular file at the backup root is protected state.
with tempfile.TemporaryDirectory(prefix="moos-shadow-storage-refusal-") as temporary:
    root = Path(temporary)
    user_share, system_share = root / "user", root / "system"
    relative = "icons/hicolor/512x512/apps/moos-store.png"
    for base, body in ((user_share, "preview"), (system_share, "image")):
        target = base / relative
        target.parent.mkdir(parents=True)
        target.write_text(body)
    protected = user_share / "MoOS/theme-shadow-backups"
    protected.parent.mkdir()
    protected.write_text("unknown")
    source = APPLY.read_text()
    start = source.index("\nif ! quarantine_moos_data_shadows; then")
    end = source.index("\nfi\n", start) + len("\nfi\n")
    script = (f"set -euo pipefail\nlog='{root / 'log'}'\nquarantined_kwin=0\n"
              + extract_function(source, "quarantine_moos_data_shadows")
              + source[start:end] + f"\nprintf reached > '{root / 'later-cleanup'}'\n")
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root / "home"),
           "XDG_DATA_HOME": str(user_share), "MOOS_SYSTEM_SHARE": str(system_share),
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root / 'no-bus'}"}
    result = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True)
    assert result.returncode != 0, "storage refusal was swallowed"
    assert not (root / "later-cleanup").exists()
    assert (user_share / relative).read_text() == "preview"
    assert protected.read_text() == "unknown"

print("OK: exact shipped shadows retire recoverably; publisher icons, both "
      "same-second versions and refused unknown recovery storage are preserved")
