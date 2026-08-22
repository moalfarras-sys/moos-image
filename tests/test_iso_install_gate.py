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
    "/usr/bin/moos-install-to-disk",
    "start_qemu installed -boot order=c",
    "! grep -qw rd.live.image /proc/cmdline",
    "ostree-image-signed:docker://${expected}",
    'hmp(["sendkey shift"])',
    '"sendkey ret"',
    "pgrep -u \"$uid\" -x kwin_wayland",
    "pgrep -u \"$uid\" -x plasmashell",
    "as_user moai-open dolphin",
    "as_user moai-open moos-settings",
    '"mode": "reboot"',
    '"mode": "powerdown"',
    "qemu-img check",
)
for needle in required_script:
    assert needle in script, f"ISO install proof lost required contract: {needle}"

# The installed QEMU command is deliberately constructed without the ISO. A
# future refactor must not make the second boot silently fall back to the LiveOS.
installed_start = script.index("start_qemu installed -boot order=c")
installed_python = script.index('python3 - "$qga" "$monitor"', installed_start)
assert "media=cdrom" not in script[installed_start:installed_python]

assert "tests/install_live_iso.sh \"$FINAL_ISO\"" in workflow
assert workflow.index("Boot and prove the exact final live ISO") < workflow.index(
    "Install the exact final ISO offline and boot the target disk"
)
assert "name: moos-iso-install-proof" in workflow
assert "timeout-minutes: 180" in workflow

print("ISO end-to-end install gate passed")
