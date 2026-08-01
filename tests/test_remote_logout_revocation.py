#!/usr/bin/env python3
"""The phone's Sign out must revoke the server session, not only localStorage."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
app = (ROOT / "moremote/controller/src/App.tsx").read_text(encoding="utf-8")
api = (ROOT / "moremote/controller/src/lib/api.ts").read_text(encoding="utf-8")
server = (ROOT / "moremote/agent/Web/WebApi.cs").read_text(encoding="utf-8")

checks = {
    "App does not import the server logout operation":
        bool(re.search(r'import\s*\{[^}]*\blogout\b[^}]*\}\s*from\s*"\./lib/api"', app, re.S)),
    "exitToLogin still only clears localStorage":
        "if (token) await logout(token)" in app,
    "client logout does not call the revocation endpoint":
        'post("/api/logout"' in api,
    "server logout does not revoke the presented bearer":
        "svc.Sessions.Revoke(token)" in server,
    "server logout leaves a trusted-device credential usable":
        "DeviceIdFor(token)" in server and "RevokeTrustedDevice(token, deviceId)" in server,
}
failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote logout revocation gate failed:\n- " + "\n- ".join(failed))
print("remote logout revocation gate passed")
