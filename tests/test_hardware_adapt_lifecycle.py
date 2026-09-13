#!/usr/bin/env python3
"""Regression contract for hardware-policy ownership and boot placement."""

from pathlib import Path
import re
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
script = (ROOT / "system_files/usr/libexec/moos-hardware-adapt").read_text()
service = (ROOT / "system_files/usr/lib/systemd/system/moos-hardware-adapt.service").read_text()
timer = (ROOT / "system_files/usr/lib/systemd/system/moos-hardware-adapt.timer").read_text()
build = (ROOT / "build_files/build.sh").read_text()
image_gate = (ROOT / "build_files/verify_image_experience.py").read_text()

assert "tuned-adm profile" not in script, (
    "the recurring root adapter must not overwrite the user's power-profile choice"
)
stamp = re.search(r'^want_stamp="([^"]+)"', script, re.MULTILINE)
assert stamp, "hardware adapter lost its explicit idempotency stamp"
assert "image=" not in stamp.group(1) and "booted_img" not in stamp.group(1), (
    "an image digest must not retrigger live hardware mutation after every OS update"
)
for field in ("cpu=", "ram=", "chassis=", "battery=", "gpu=", "display="):
    assert field in stamp.group(1), f"hardware stamp does not track {field[:-1]} changes"

assert "After=graphical.target" in service, (
    "hardware adaptation must be ordered after graphical.target"
)
assert "WantedBy=multi-user.target" not in service, (
    "hardware adaptation must not be pulled into the login critical path"
)
assert "OnActiveSec=45s" in timer and "OnUnitActiveSec=1d" in timer, (
    "hardware adaptation needs a bounded post-boot and periodic timer"
)
assert "WantedBy=graphical.target" in timer
assert "systemctl enable moos-hardware-adapt.timer" in build
assert "systemctl disable moos-hardware-adapt.service" in build
assert "graphical.target.wants/moos-hardware-adapt.timer" in image_gate
assert "multi-user.target.wants/moos-hardware-adapt.service" in image_gate
assert "zram_size_matches_tier" in script, (
    "hardware adaptation must skip live zram restart when swap already matches the RAM tier"
)
assert "persisted config without live restart" in script

print("hardware-adapt lifecycle/ownership gate passed")

# The service's deadline is finite and outside the login path. The acceptance
# gate must wait for the timer/oneshot to finish, not sample --failed too early.
timeout = re.search(r'^TimeoutStartSec=(\d+)(s|min)$', service, re.M)
assert timeout and 300 <= int(timeout[1]) * (60 if timeout[2] == "min" else 1) <= 600
assert "systemctl enable --no-reload fwupd-refresh.timer" in script
runtime = (ROOT / 'tests/verify_arm_runtime.sh').read_text()
block = re.search(r'# BEGIN HARDWARE ADAPT ACCEPTANCE\n(.*?)# END HARDWARE ADAPT ACCEPTANCE', runtime, re.S)
assert block, 'ARM proof must await hardware adaptation'
for outcome, expected in [('success', 0), ('failed', 1), ('bad-status', 1), ('never-started', 1)]:
    with tempfile.TemporaryDirectory() as directory:
        counter = Path(directory) / 'polls'
        counter.write_text('0')
        stubs = r'''
set -euo pipefail
systemctl() {
    local n="$(cat "$TEST_POLLS")"
    case "$*" in
        'is-active moos-hardware-adapt.service')
            n=$((n+1)); printf '%s' "$n" > "$TEST_POLLS"
            if [ "$TEST_OUTCOME" = never-started ]; then echo inactive
            elif [ "$n" -lt 3 ]; then echo activating
            elif [ "$TEST_OUTCOME" = failed ]; then echo failed
            else echo active; fi ;;
        'show -p Result --value moos-hardware-adapt.service')
            if [ "$TEST_OUTCOME" = failed ] && [ "$n" -ge 3 ]; then echo timeout; else echo success; fi ;;
        'show -p ExecMainStatus --value moos-hardware-adapt.service')
            if [ "$TEST_OUTCOME" = bad-status ]; then echo 1; else echo 0; fi ;;
    esac
}
journalctl() { :; }
sleep() { SECONDS=$((SECONDS+100)); }
'''
        result = subprocess.run(['bash', '-c', stubs + block[1]], text=True,
            capture_output=True, timeout=5,
            env=os.environ | {'TEST_POLLS': str(counter), 'TEST_OUTCOME': outcome})
        assert result.returncode == expected, (outcome, result.stdout, result.stderr)
        assert int(counter.read_text()) >= 3, 'gate accepted an unfinished oneshot'
        assert ('hardware_adapt=active' in result.stdout) == (expected == 0)
print('hardware-adapt completed/failed/delayed first-boot acceptance passed')
