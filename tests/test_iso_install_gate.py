#!/usr/bin/env python3
"""Static regression gate for the final-ISO installation proof."""

from pathlib import Path


root = Path(__file__).resolve().parents[1]
script_path = root / "tests/install_live_iso.sh"
workflow_path = root / ".github/workflows/build-iso.yml"
script = script_path.read_text(encoding="utf-8")
workflow = workflow_path.read_text(encoding="utf-8")

required_script = (
    'file=$iso,media=cdrom,format=raw,readonly=on',
    "systemctl stop NetworkManager.service",
    "source: local containers-storage (offline)",
    "install-source-digest",
    "/usr/bin/moos-install-to-disk",
    "start_qemu live-install install-2d",
    "start_qemu installed proof-virgl -boot order=c",
    "! grep -qw rd.live.image /proc/cmdline",
    "ostree-image-signed:docker://${expected}",
    'hmp(["sendkey shift"])',
    '"sendkey ret"',
    "pgrep -u \"$uid\" -x kwin_wayland",
    "pgrep -u \"$uid\" -x plasmashell",
    '("dolphin", "dolphin")',
    '("mo-ai", "moai")',
    '("mo-store", "moos-store")',
    '("updater", "moos-update")',
    '("recovery", "moos-rollback")',
    '("themes", "moos-theme-picker")',
    '("moplayer", "moplayer")',
    '("mo-pc-remote", "mo-pc-remote")',
    "opened-closed-reopened",
    "systemctl --user --failed --no-legend --plain",
    "moos-ci-runtime-proof",
    "ci-proof=ephemeral-ssh",
    '"BatchMode=yes"',
    '"IdentitiesOnly=yes"',
    "moosci@127.0.0.1",
    '"mode": "reboot"',
    '"mode": "powerdown"',
    "qemu-img check",
)
for needle in required_script:
    assert needle in script, f"ISO install proof lost required contract: {needle}"

proof_unit = (
    root / "system_files/usr/lib/systemd/system/moos-ci-runtime-proof.service"
).read_text(encoding="utf-8")
assert "ConditionPathExists=|/home/mo/.ssh/authorized_keys" in proof_unit
assert "ConditionPathExists=|/home/moosci/.ssh/authorized_keys" in proof_unit

# The installed QEMU command is deliberately constructed without the ISO. A
# future refactor must not make the second boot silently fall back to the LiveOS.
installed_start = script.index("start_qemu installed proof-virgl -boot order=c")
installed_python = script.index('python3 - "$qga" "$monitor"', installed_start)
assert "media=cdrom" not in script[installed_start:installed_python]

assert "tests/install_live_iso.sh \"$FINAL_ISO\"" in workflow
assert workflow.index("Boot and prove the exact final live ISO") < workflow.index(
    "Install the exact final ISO offline and boot the target disk"
)
assert "name: moos-iso-install-proof" in workflow
assert "timeout-minutes: 180" in workflow

print("ISO end-to-end install gate passed")
