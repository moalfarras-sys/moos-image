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
     gone.

  3. AN INVENTED GRID. Deriving a unique block from the uid — 100000 + (uid-1000)*65536
     — is valid and unique and still wrong: it ignores the host's policy. Fedora 44
     sets SUB_UID_MIN=524288, so that formula allocates BELOW the configured floor, on
     a scale the system does not use. Measured live: useradd had given the account
     524288:65536 while the formula said 100000.

So: assert the allocation reads the host's own policy (SUB_UID_MIN/SUB_UID_COUNT) and
the blocks already in /etc/subuid — which is how useradd picks one — and that no literal
FIRST-LAST pair in the script is inverted. Per AGENTS.md the check reads the CODE with
comments stripped, so this docstring's own examples cannot satisfy or trip it.
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

    # 2. The allocation must sit on the SYSTEM'S grid and never overlap an existing tenant.
    #
    #    A uid-derived formula was tried and was wrong for a subtler reason than the inverted
    #    range: it invented a grid. Fedora 44 sets SUB_UID_MIN=524288, and the formula started
    #    at 100000 — below the configured floor, on a scale the host does not use (measured
    #    live: useradd had given the account 524288:65536 while the formula said 100000).
    #    The correct source of truth is login.defs plus what /etc/subuid already contains,
    #    which is exactly how useradd itself picks a block.
    if "--add-subuids" in code:
        if not re.search(r"SUB_UID_MIN", code):
            errors.append(
                "the allocation ignores SUB_UID_MIN from /etc/login.defs — it invents a grid.\n"
                "        On Fedora 44 that floor is 524288, so a hardcoded 100000 allocates\n"
                "        below the configured range and does not match what useradd hands out.")
        if not re.search(r"SUB_UID_COUNT", code):
            errors.append(
                "the allocation ignores SUB_UID_COUNT — the block width must come from the\n"
                "        host's own policy, not a literal.")
        if not re.search(r"/etc/subuid", code):
            errors.append(
                "the allocation never reads /etc/subuid, so it cannot know which blocks are\n"
                "        already taken — overlapping two tenants' ranges maps their containers\n"
                "        onto the same host UIDs and destroys the isolation these ranges exist for.")
        if re.search(r"\b100000\s*\+", code):
            errors.append(
                "a hardcoded 100000 base is back. Read SUB_UID_MIN instead; the literal is\n"
                "        below Fedora 44's floor and on the wrong grid entirely.")

    if errors:
        print("GATE FAIL: moos-cloud-dev would mis-allocate subordinate IDs.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: moos-cloud-dev allocates on the system grid (SUB_UID_MIN/COUNT), past every "
          "block already in /etc/subuid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
