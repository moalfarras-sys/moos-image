#!/usr/bin/env python3
"""Regression contract for hardware-policy ownership and boot placement."""

from pathlib import Path
import re
import subprocess

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

# Execute the exact runtime acceptance predicate, not a second model of it.
runtime = (ROOT / "tests/verify_arm_runtime.sh").read_text()
function = re.search(r"^hwadapt_completed\(\) \{\n.*?^\}", runtime, re.MULTILINE | re.DOTALL)
assert function, "runtime hardware completion predicate is missing"
assert "RemainAfterExit=no" in service, "periodic adaptation must return to inactive"
for name, fields, expected in (
    ("not-run", ("inactive", "dead", "success", "0", "0", "yes"), False),
    ("skipped", ("inactive", "dead", "success", "0", "0", "no"), False),
    ("failed", ("failed", "failed", "exit-code", "1", "42", "yes"), False),
    ("running", ("activating", "start", "success", "0", "0", "yes"), False),
    ("old-active-latch", ("active", "exited", "success", "0", "42", "yes"), False),
    ("completed-zero", ("inactive", "dead", "success", "0", "42", "yes"), True),
    ("completed-nonzero", ("inactive", "dead", "success", "1", "42", "yes"), False),
    ("skipped-after-prior-exit", ("inactive", "dead", "success", "0", "42", "no"), False),
    ("invalid-numeric", ("inactive", "dead", "success", "0", "unknown", "yes"), False),
    ("negative-numeric", ("inactive", "dead", "success", "0", "-1", "yes"), False),
    ("unknown-state", ("unknown", "dead", "success", "0", "42", "yes"), False),
    ("missing-receipt", ("inactive", "dead", "success", "0", "", "yes"), False),
):
    snapshot = "\n".join(f"{key}={value}" for key, value in zip(
        ("ActiveState", "SubState", "Result", "ExecMainStatus", "ExecMainExitTimestampMonotonic", "ConditionResult"), fields))
    result = subprocess.run(["bash", "-c", function.group(0) + '\nhwadapt_completed "$1"',
                             "hardware-completion", snapshot], timeout=5, capture_output=True)
    assert (result.returncode == 0) is expected, (name, result.returncode, result.stderr)
# A missing property must not inherit a truthy default or accept an old receipt.
complete = {"ActiveState": "inactive", "SubState": "dead", "Result": "success",
            "ExecMainStatus": "0", "ExecMainExitTimestampMonotonic": "42", "ConditionResult": "yes"}
for absent in complete:
    snapshot = "\n".join(f"{key}={value}" for key, value in complete.items() if key != absent)
    result = subprocess.run(["bash", "-c", function.group(0) + '\nhwadapt_completed "$1"',
                             "hardware-completion", snapshot], timeout=5, capture_output=True)
    assert result.returncode != 0, absent
print("hardware runtime completion and skipped/invalid/missing-property controls passed")

# A stuck cleanup subprocess must not skip the remaining owned-unit attempts.
import importlib.util
import subprocess as _subprocess
_spec = importlib.util.spec_from_file_location("hardware_timer_probe", ROOT / "scripts/review/hardware-adapt-timer.py")
_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_probe)
_calls = []
def _cleanup_timeout(*argv, check=False):
    _calls.append(argv)
    if ("stop" in argv and "--no-block" not in argv) or "reset-failed" in argv:
        raise _subprocess.TimeoutExpired(argv, 2)
    if "is-active" in argv:
        return _subprocess.CompletedProcess(argv, 3, "inactive\ninactive\n")
    return _subprocess.CompletedProcess(argv, 0, "")
_cleanup_record = {}
assert _probe.cleanup_owned_units("moos-hw-private-" + "a" * 32, _cleanup_record, _cleanup_timeout) is False
assert any("--no-block" in call and "stop" in call for call in _calls), _calls
assert any("reset-failed" in call for call in _calls), _calls
assert any("is-active" in call for call in _calls), _calls
assert _cleanup_record["cleanup_verified"] is True, _cleanup_record
assert len(_cleanup_record["cleanup_errors"]) == 2, _cleanup_record
try:
    _probe.cleanup_owned_units("moos-hardware-adapt", {}, _cleanup_timeout)
except ValueError:
    pass
else:
    raise AssertionError("probe must never clean up an owner service")
print("hardware timer cleanup timeout/fallback/independent-readback negative passed")
