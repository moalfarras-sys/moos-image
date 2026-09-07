#!/usr/bin/env python3
"""Gate: no root-run unit may execute a program a normal user can rewrite.

WHY THIS EXISTS

Found on the live Oracle A1 on 2026-09-07, enabled and active:

    /etc/systemd/system/moos-post-reboot-check.service
        [Service]
        Type=oneshot
        ExecStart=/var/home/moos/.local/state/moos/post-reboot-check.sh

    $ ls -l /var/home/moos/.local/state/moos/post-reboot-check.sh
    -rwxr-xr-x. 1 moos moos 633 Aug 30 17:18

A SYSTEM unit -- so root, no User= -- executing a script owned by, and writable
by, the unprivileged desktop user. Anything running as `moos` could rewrite that
file and be root at the next boot. It was hand-placed on 2026-08-30 as a one-off
check for an Arabic-font fix in image 44.20260830.203, it referenced a repo path
that no longer exists, and it had been running at every boot for eight days.

Nobody put it there maliciously; that is the point. Temporary verification
scaffolding is exactly the thing that gets written under $HOME because that is
where the agent or the maintainer already had a shell, and exactly the thing
nobody remembers to remove. The privilege boundary it crosses is invisible until
someone looks.

WHAT THIS CHECKS

The SHIPPED image: every unit MoOS installs must run its programs from the image
(/usr, /etc, /opt), never from a home directory or another world/user-writable
path. This cannot catch what a person adds to a running machine afterwards --
`tests/post-update-check.sh` does that on the live system -- but it makes the
image itself provably clean, and it stops such a unit from ever being committed.

IF THIS GATE FAILS

Do not add an exception. Move the program into the image (system_files/usr/...)
where it is read-only at runtime, or give the unit `User=` so it does not run
with privilege it does not need.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM_UNIT_DIRS = [
    ROOT / "system_files/usr/lib/systemd/system",
    ROOT / "system_files/etc/systemd/system",
]

# Paths a non-root user can write to, or that are not part of the read-only
# image. A program started by a privileged unit must not live in any of them.
UNTRUSTED_PREFIXES = (
    "/home/", "/var/home/", "/root/", "/tmp/", "/var/tmp/",
    "/var/lib/private/", "/srv/", "/media/", "/mnt/",
)

EXEC_KEYS = ("ExecStart", "ExecStartPre", "ExecStartPost", "ExecStop",
             "ExecStopPost", "ExecReload", "ExecCondition")


def program_of(value: str) -> str:
    """The executable a systemd Exec= line runs, minus its prefix characters.

    systemd allows '-', '@', '+', '!' and '!!' before the path; they change
    failure handling and privilege, not which file is executed.
    """
    value = value.strip()
    while value[:1] in ("-", "@", "+", "!", ":"):
        value = value[1:]
    return value.split()[0] if value.split() else ""


def main() -> int:
    problems: list[str] = []
    checked = 0

    for base in SYSTEM_UNIT_DIRS:
        if not base.is_dir():
            continue
        for unit in sorted(base.rglob("*")):
            if not unit.is_file() or unit.suffix not in (
                    ".service", ".socket", ".mount", ".path", ".timer"):
                continue
            checked += 1
            text = unit.read_text(encoding="utf-8", errors="replace")

            # A unit with User= set to a non-root account is not a privilege
            # boundary crossing; the whole point of the finding is root.
            user = re.search(r"^\s*User\s*=\s*(\S+)", text, re.M)
            if user and user.group(1) not in ("root", "0"):
                continue

            for line in text.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                if key.strip() not in EXEC_KEYS:
                    continue
                program = program_of(value)
                if not program.startswith("/"):
                    continue
                if program.startswith(UNTRUSTED_PREFIXES):
                    problems.append(
                        f"{unit.relative_to(ROOT)}: {key.strip()} runs {program}\n"
                        f"      A root unit must not execute a program from a "
                        f"user-writable path.")

    if problems:
        print("PRIVILEGED-UNIT GATE FAIL: a root unit executes a user-writable program.\n")
        for problem in problems:
            print(f"  - {problem}")
        print("\n  Move the program into the image (system_files/usr/...), where it is")
        print("  read-only at runtime, or set User= so the unit drops the privilege.")
        return 1

    print(f"privileged-unit gate passed ({checked} system units; none executes "
          f"from a user-writable path)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
