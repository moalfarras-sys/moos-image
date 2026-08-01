#!/usr/bin/env python3
"""Gate heavy Mo AI services against infinite restart and shutdown stalls."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
unit = (ROOT / "system_files/usr/lib/systemd/user/openclaw-gateway.service").read_text(encoding="utf-8")

def section(name: str) -> str:
    marker = f"[{name}]"
    if marker not in unit:
        return ""
    body = unit.split(marker, 1)[1]
    return body.split("\n[", 1)[0]

unit_section = section("Unit")
service_section = section("Service")
checks = {
    "OpenClaw no longer restarts clean reloads": "Restart=always" in service_section,
    "heavy OpenClaw failures can restart forever":
        "StartLimitIntervalSec=300" in unit_section and "StartLimitBurst=8" in unit_section,
    "StartLimit directives are incorrectly placed in [Service]":
        "StartLimit" not in service_section,
    "a wedged sandbox can hold logout/reboot for the default 90 seconds":
        "TimeoutStopSec=30s" in service_section,
}
failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("Mo AI service lifecycle gate failed:\n- " + "\n- ".join(failed))
print("Mo AI service lifecycle gate passed")
