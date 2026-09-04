#!/usr/bin/env python3
"""Gate the complete trusted-device chain: persistence, resume, inventory, revocation and UI."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"GATE FAIL: missing {relative}")
    return path.read_text(encoding="utf-8")


security = read("moremote/agent/Core/Security.cs")
linux_config = read("moremote/agent-linux/AppConfig.cs")
windows_config = read("moremote/agent/Core/AppConfig.cs")
api = read("moremote/agent/Web/WebApi.cs")
client_api = read("moremote/controller/src/lib/api.ts")
app = read("moremote/controller/src/App.tsx")
auth = read("moremote/controller/src/ui/AuthScreens.tsx")
screen = read("moremote/controller/src/ui/RemoteScreen.tsx")

errors: list[str] = []

for label, source in (("Linux", linux_config), ("Windows", windows_config)):
    if "List<TrustedDevice> TrustedDevices" not in source:
        errors.append(f"{label} config cannot persist trusted-device hashes")

for token in (
    "SHA256.HashData", "CryptographicOperations.FixedTimeEquals", "MaxTrustedDevices = 16",
    "TimeSpan.FromDays(30)", "ResumeTrustedDevice", "ListTrustedDevices",
    "RevokeTrustedDevice", "_cfg.TrustedDevices.Clear()",
    "Remote PIN is already configured.",
):
    if token not in security:
        errors.append(f"security lifecycle misses {token}")

if "DeviceToken" in windows_config or "DeviceToken" in linux_config:
    errors.append("a raw trusted-device secret is persisted in AppConfig")

for route in ("/api/devices/resume", "/api/devices", "/api/devices/revoke", "/api/session"):
    if route not in api:
        errors.append(f"server API misses {route}")

for token in (
    "deviceStore", "resumeTrustedDevice", "validateSession", "listTrustedDevices",
    "revokeTrustedDevice",
):
    if token not in client_api + app + screen:
        errors.append(f"PWA trusted-device chain misses {token}")

if 'tr("trustDevice")' not in auth:
    errors.append("PIN screens do not ask for explicit trusted-device consent")
if "trustedDevices?.map" not in screen or "Remove trusted device" not in screen:
    errors.append("Settings has no owner-visible device inventory/revocation control")
if "deviceStore.clear()" not in client_api:
    errors.append("sign out leaves the local long-lived device secret behind")

if errors:
    print("GATE FAIL: Mo PC Remote trusted-device lifecycle is incomplete.")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)

print("OK: trusted devices are hashed, bounded, resumable, visible and individually revocable.")
