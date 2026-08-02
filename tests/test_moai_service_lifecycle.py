#!/usr/bin/env python3
"""Gate heavy Mo AI services against infinite restart and shutdown stalls."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
unit = (ROOT / "system_files/usr/lib/systemd/user/openclaw-gateway.service").read_text(encoding="utf-8")
speech = (ROOT / "system_files/usr/share/moos/containers/speaches.container").read_text(encoding="utf-8")
brain = (ROOT / "system_files/usr/share/moos/containers/moai-brain.container").read_text(encoding="utf-8")
user_units = ROOT / "system_files/usr/lib/systemd/user"
control = (user_units / "moai-control.service").read_text(encoding="utf-8")
gateway = (user_units / "moai-gateway.service").read_text(encoding="utf-8")
wake = (user_units / "moai-wake.service").read_text(encoding="utf-8")
agent_api = (user_units / "moai-agent-api.service").read_text(encoding="utf-8")
remote = (user_units / "mo-remote-personal.service").read_text(encoding="utf-8")
cloud_audio = (user_units / "moos-cloud-audio.service").read_text(encoding="utf-8")
ramalama = (user_units / "moai.service").read_text(encoding="utf-8")

def section(name: str, source: str = unit) -> str:
    match = re.search(rf"(?m)^\[{re.escape(name)}\]\s*$", source)
    if not match:
        return ""
    body = source[match.end():]
    next_section = re.search(r"(?m)^\[[^]]+\]\s*$", body)
    return body[:next_section.start()] if next_section else body

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
    "a wedged OpenClaw preflight can pin the Telegram wake receiver":
        "TimeoutStartSec=100s" in service_section,
    "the speech container can restart its 1.5 GB stack forever":
        "StartLimitIntervalSec=300" in speech and "StartLimitBurst=5" in speech,
    "the local brain container can restart/pull forever":
        "StartLimitIntervalSec=300" in brain and "StartLimitBurst=5" in brain,
    "the RamaLama local brain can restart/reload its multi-gigabyte model forever":
        "StartLimitIntervalSec=300" in section("Unit", ramalama)
        and "StartLimitBurst=5" in section("Unit", ramalama),
    "RamaLama StartLimit directives are incorrectly placed in [Service]":
        "StartLimit" not in section("Service", ramalama),
    "the local brain can hold session shutdown for 90 seconds":
        "TimeoutStopSec=30" in brain,
    "the always-on control API can restart forever":
        "StartLimitIntervalSec=120" in section("Unit", control)
        and "StartLimitBurst=6" in section("Unit", control),
    "the gateway limiter sits on its restart-window boundary":
        "StartLimitIntervalSec=120" in section("Unit", gateway)
        and "StartLimitBurst=12" in section("Unit", gateway),
    "the Telegram wake receiver can crash-loop forever":
        "StartLimitIntervalSec=300" in section("Unit", wake)
        and "StartLimitBurst=5" in section("Unit", wake),
    "the Remote agent can restart forever at a three-second cadence":
        "StartLimitIntervalSec=300" in section("Unit", remote)
        and "StartLimitBurst=5" in section("Unit", remote),
    "small always-on services can hold logout for systemd's default 90 seconds":
        all("TimeoutStopSec=" in section("Service", candidate) for candidate in
            (control, gateway, wake, agent_api, remote, cloud_audio)),
}
failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("Mo AI service lifecycle gate failed:\n- " + "\n- ".join(failed))
print("Mo AI service lifecycle gate passed")
