#!/usr/bin/env python3
"""Gate: moos-cloud-dev hands each developer a VALID, UNIQUE subuid/subgid range.

WHY THIS EXISTS

Rootless podman maps the container's UIDs into a subordinate range the host has
delegated to that user (/etc/subuid, /etc/subgid). moos-cloud-dev's whole reason to
exist is adding the second, third, tenth developer to one server, so this allocation
is a product surface: get it wrong and either provisioning aborts or two tenants share
host UIDs.

Two failures, both silent, both live in the tree before this landed:

  1. AN INVERTED RANGE. The code wrote `usermod --add-subuids 100000-65535` — start
     ABOVE end. usermod rejects it ("invalid subordinate uid range"), the `|| die`
     aborts `add` AFTER the account and its authorized_keys already exist, and the
     death message blames rootless podman instead of the malformed range. It hid
     because Fedora's useradd usually pre-allocates a valid range, so the `grep`
     guard skipped the broken line — until the account-update path, or a host with
     SUB_UID_COUNT unset, reached it.

  2. A SHARED RANGE. "Just make it 100000-165535" fixes the inversion and introduces
     a worse bug: every account gets the SAME block, so two developers' containers
     map onto the same host UIDs and the isolation the ranges exist to provide is
     gone. The range must be keyed off something unique per account (the uid).

So: assert the allocation is uid-derived (unique) and that no literal FIRST-LAST pair
in the script is inverted. Per AGENTS.md the check reads the CODE with comments
stripped, so this docstring's own `100000-65535` example cannot satisfy or trip it.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-cloud-dev"


def code_of(path: Path) -> str:
    """The script with #-comments and blank lines removed, so prose cannot pass a gate."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Drop trailing inline comments, but not a '#' inside a string. moos-cloud-dev
        # has none in the subuid lines, so a simple split is safe and honest here.
        out.append(line.split(" #", 1)[0])
    return "\n".join(out)


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing — the cloud multi-tenant "
              "provisioner has no source.")
        return 1

    code = code_of(SCRIPT)
    errors: list[str] = []

    # 1. No inverted literal range anywhere in the script: FIRST-LAST with FIRST > LAST.
    for m in re.finditer(r"--add-sub[ug]ids\s+(\d+)-(\d+)", code):
        first, last = int(m.group(1)), int(m.group(2))
        if first >= last:
            errors.append(
                f"`{m.group(0)}` is not an ascending range (start {first} >= end {last}).\n"
                f"        usermod rejects it, and the || die aborts `add` after the account\n"
                f"        already exists — a half-provisioned tenant with a misleading error.")

    # 2. The allocation must be uid-derived, or two tenants share a range and lose
    #    isolation. The honest signal is arithmetic on the account's uid.
    if "--add-subuids" in code:
        if not re.search(r"id -u\b", code):
            errors.append(
                "the subuid range is not derived from the account's uid (no `id -u`).\n"
                "        A fixed range hands every developer the same block, so their\n"
                "        containers map onto the same host UIDs and rootless isolation is lost.")
        if not re.search(r"\buid\b.*\*\s*65536|65536\s*\*.*\buid\b|\(uid\b", code):
            errors.append(
                "the subuid range does not scale by a per-uid stride (expected a 65536-wide\n"
                "        block keyed off the uid), so consecutive accounts may overlap.")

    if errors:
        print("GATE FAIL: moos-cloud-dev would mis-allocate subordinate IDs.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: moos-cloud-dev allocates a valid, uid-derived (unique) subuid/subgid range.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
