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

  2. A FOREIGN GRID. Deriving a range from the account uid looked unique, but started
     at a hard-coded 100000 even when the host policy started at 524288. The allocator
     must follow login.defs and the high-water mark already present in each map.

So: execute the policy-aware allocator, prove ensure_subids actually calls it for both
maps, and reject inverted literal ranges. Per AGENTS.md the static checks read code
with comments stripped, so examples in this docstring cannot satisfy or trip them.
"""

from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile

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

    # 2. Exercise the allocator itself. The old static test blessed an unused correct helper while
    #    ensure_subids continued allocating from its own hard-coded grid.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        login_defs = root / "login.defs"
        allocated = root / "subuid"
        login_defs.write_text("SUB_UID_MIN 524288\nSUB_UID_COUNT 65536\n", encoding="utf-8")
        allocated.write_text("alice:524288:65536\nbob:720896:65536\n", encoding="utf-8")
        env = os.environ.copy()
        env.update({"MOOS_CLOUD_DEV_LIB_ONLY": "1", "MOOS_LOGIN_DEFS": str(login_defs)})
        probe = subprocess.run(
            ["bash", "-c", 'source "$1"; next_free_subid_block "$2"', "bash", str(SCRIPT), str(allocated)],
            text=True, capture_output=True, env=env, check=False,
        )
        if probe.returncode != 0:
            errors.append(f"the allocator cannot be executed: {probe.stderr.strip() or probe.stdout.strip()}")
        elif probe.stdout.strip() != "786432 65536":
            errors.append(
                "the allocator did not choose the first block after the highest existing range;\n"
                f"        expected `786432 65536`, got `{probe.stdout.strip()}`.")

    if not re.search(r'next_free_subid_block\s+"\$subuid_file"', code):
        errors.append("ensure_subids does not use the policy-aware allocator for /etc/subuid.")
    if not re.search(r'next_free_subid_block\s+"\$subgid_file"', code):
        errors.append("ensure_subids does not use the policy-aware allocator for /etc/subgid.")
    if re.search(r"100000\s*\+\s*\(uid", code):
        errors.append("the obsolete hard-coded 100000 uid grid is still active.")

    if errors:
        print("GATE FAIL: moos-cloud-dev would mis-allocate subordinate IDs.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: moos-cloud-dev allocates policy-aware, non-overlapping subuid/subgid ranges.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
