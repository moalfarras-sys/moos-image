#!/usr/bin/env python3
"""Linux Remote must expose one authenticated door through Tailscale Serve, not a raw port."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "moremote/agent-linux/Program.cs"
PANEL = ROOT / "system_files/usr/bin/mo-pc-remote"
CLOUD = ROOT / "system_files/usr/bin/moos-cloud-desktop"

errors: list[str] = []


def uncommented(path: Path, marker: str) -> str:
    if not path.is_file():
        errors.append(f"missing {path.relative_to(ROOT)}")
        return ""
    return "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith(marker)
    )


program = uncommented(PROGRAM, "//")
panel = uncommented(PANEL, "#")
cloud = uncommented(CLOUD, "#")

if "ListenLocalhost(config.Port" not in program:
    errors.append("Linux Kestrel is not bound to loopback")
if re.search(r"\bListenAnyIP\s*\(", program):
    errors.append("Linux Kestrel still carries a wildcard listener")
if "Linux server listening: {svc.AccessUrl}" in program:
    errors.append("Linux startup log advertises the retired raw tailnet URL")
if "Linux server listening on loopback" not in program:
    errors.append("Linux startup log does not name its real loopback-only boundary")
for name, source in (("desktop panel", panel), ("cloud manager", cloud)):
    invokes_serve = bool(re.search(r"\btailscale\s+serve\b", source)) or (
        '"tailscale"' in source and '"serve"' in source
    )
    if not invokes_serve or "127.0.0.1:" not in source:
        errors.append(f"{name} no longer proxies Tailscale Serve to the loopback agent")

if errors:
    print("GATE FAIL: Mo PC Remote Linux network boundary regressed.")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)

print("OK: Linux Remote listens only on loopback; desktop and Cloud publish it through Tailscale Serve.")
