#!/usr/bin/env python3
"""Regression contract for hardware-policy ownership and boot placement."""

from pathlib import Path
import re

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

print("hardware-adapt lifecycle/ownership gate passed")
