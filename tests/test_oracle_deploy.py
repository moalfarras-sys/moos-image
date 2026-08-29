#!/usr/bin/env python3
"""Offline gate for the Oracle ARM deployment helper.

The first helper shipped with three failures that all looked green from the
console: a valid config made ``require_oci`` return grep's no-match status under
``set -e``; it called a nonexistent ``resource-availability list`` command; and
the imported AArch64 disk defaulted to BIOS even though the release QCOW2 is
UEFI-only. Exercise those paths against a recording OCI stub so they cannot
return unnoticed.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts/oracle_deploy.sh"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="moos-oracle-gate-") as temporary:
        temp = Path(temporary)
        calls = temp / "calls"
        config = temp / "config"
        fake_oci = temp / "oci"
        config.write_text(
            "[DEFAULT]\n"
            "tenancy=ocid1.tenancy.test\n"
            "user=ocid1.user.test\n"
            "fingerprint=00:11\n"
            "key_file=/not/read/by/the/stub\n"
            "region=eu-test-1\n",
            encoding="utf-8",
        )
        fake_oci.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -eu
                printf '%s\\n' "$*" >> "$MOOS_OCI_CALLS"
                case "$*" in
                    *"iam availability-domain list"*)
                        echo '["AD-1", "AD-2", "AD-3"]'
                        ;;
                    *"limits resource-availability get"*)
                        echo 'available used'
                        ;;
                    *"compute instance list"*)
                        echo 'name shape state'
                        ;;
                    *"global-image-capability-schema list"*)
                        echo 'schema-version'
                        ;;
                    *"image-capability-schema list"*"data[0].id"*)
                        echo null
                        ;;
                    *"image-capability-schema create"*)
                        echo '{}'
                        ;;
                    *"image-capability-schema list"*"default-value"*)
                        echo UEFI_64
                        ;;
                    *)
                        echo "unexpected OCI call: $*" >&2
                        exit 90
                        ;;
                esac
                """
            ),
            encoding="utf-8",
        )
        fake_oci.chmod(0o755)
        env = {
            **os.environ,
            "OCI_CLI": str(fake_oci),
            "OCI_CONFIG": str(config),
            "MOOS_OCI_CALLS": str(calls),
        }

        verify = subprocess.run(
            ["bash", str(HELPER), "verify"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        if verify.returncode:
            print("GATE FAIL: valid Oracle config did not reach OCI verification")
            print(verify.stdout)
            print(verify.stderr)
            return 1

        recorded = calls.read_text(encoding="utf-8")
        if recorded.count("limits resource-availability get") != 3:
            print("GATE FAIL: verify did not query every availability domain with the real OCI command")
            return 1
        if "resource-availability list" in recorded:
            print("GATE FAIL: helper regressed to the nonexistent resource-availability list command")
            return 1
        if "ocid1.tenancy.test" not in recorded:
            print("GATE FAIL: the tenancy OCID was not used as the root compartment")
            return 1

        calls.write_text("", encoding="utf-8")
        uefi = subprocess.run(
            ["bash", str(HELPER), "image-uefi", "ocid1.image.test"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
        )
        if uefi.returncode:
            print("GATE FAIL: image-uefi did not produce and verify an active capability schema")
            print(uefi.stdout)
            print(uefi.stderr)
            return 1
        recorded = calls.read_text(encoding="utf-8")
        if "Compute.Firmware" not in recorded or "UEFI_64" not in recorded:
            print("GATE FAIL: Oracle custom image is not explicitly bound to UEFI_64")
            return 1

        helper = HELPER.read_text(encoding="utf-8")
        required_capacity_guards = (
            "running_instance_id",
            "--wait-for-state RUNNING",
            "--wait-for-state TERMINATED",
            "[ \"$firmware\" = UEFI_64 ]",
            "systemd-creds decrypt --name=moos-oracle-management-password",
            "--ssh-authorized-keys-file",
            "--user-data-file",
            "cleanup_instance_metadata",
            "--force",
        )
        missing = [guard for guard in required_capacity_guards if guard not in helper]
        if missing:
            print("GATE FAIL: capacity watcher lost safety guards: " + ", ".join(missing))
            return 1

    print("Oracle deploy gate OK: config, all-AD limits and UEFI_64 image capability are enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
