#!/usr/bin/env python3
"""Exercise the installer's bounded ESP unmount retry without touching disks."""

from pathlib import Path
import re
import subprocess


root = Path(__file__).resolve().parents[1]
installer = (root / "system_files/usr/bin/moos-install-to-disk").read_text(encoding="utf-8")
match = re.search(
    r"^unmount_installer_mount\(\) \{\n.*?^\}\n",
    installer,
    re.MULTILINE | re.DOTALL,
)
assert match, "installer lost unmount_installer_mount"
function = match.group(0)


def run_case(failures_before_success: int) -> tuple[int, int, str]:
    script = (
        "set -uo pipefail\n"
        "LOG=/dev/stderr\n"
        "attempts=0\n"
        f"failures={failures_before_success}\n"
        "mountpoint() { return 0; }\n"
        "sleep() { :; }\n"
        "findmnt() { echo diagnostic-findmnt; }\n"
        "fuser() { echo diagnostic-fuser; }\n"
        "umount() { attempts=$((attempts + 1)); [ \"$attempts\" -gt \"$failures\" ]; }\n"
        + function
        + "set +e\n"
        + "unmount_installer_mount /run/moos-esp 'bootloader: target ESP'\n"
        + "rc=$?\n"
        + "printf '__RESULT__%s:%s\\n' \"$rc\" \"$attempts\"\n"
    )
    result = subprocess.run(
        ["bash"], input=script.encode(), capture_output=True, check=False
    )
    stdout = result.stdout.decode(errors="replace")
    stderr = result.stderr.decode(errors="replace")
    marker = re.search(r"__RESULT__(\d+):(\d+)", stdout)
    assert marker, stdout + stderr
    return int(marker.group(1)), int(marker.group(2)), stderr


recovered, attempts, recovered_log = run_case(2)
assert recovered == 0, recovered_log
assert attempts == 3
assert "unmounted after attempt 3" in recovered_log

failed, attempts, failed_log = run_case(40)
assert failed != 0
assert attempts == 40
assert "mount remained busy after 40 attempts" in failed_log
assert "diagnostic-findmnt" in failed_log and "diagnostic-fuser" in failed_log

print("OK: installer retries transient ESP EBUSY and fails with diagnostics when persistent")
