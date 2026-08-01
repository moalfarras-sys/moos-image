#!/usr/bin/env python3
"""Keep a per-user MoOS Cloud remote from controlling the shared host."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
linux = (ROOT / "moremote/agent-linux/PowerActions.cs").read_text(encoding="utf-8")
api = (ROOT / "moremote/agent/Web/WebApi.cs").read_text(encoding="utf-8")
ui = (ROOT / "moremote/controller/src/ui/RemoteScreen.tsx").read_text(encoding="utf-8")

checks = {
    "the image does not bake an authoritative edition marker":
        'printf \'%s\\n\' "${MOOS_EDITION}" > /usr/lib/moos/edition' in build,
    "the Linux agent does not deny host power on moos-cloud":
        '!= "moos-cloud"' in linux and "HostPowerAllowed" in linux,
    "the API does not enforce the edition policy before execution":
        "PowerActions.CanRun(action)" in api and 'error = "unavailable_on_edition"' in api,
    "the status response does not advertise the power capability":
        "hostPowerAllowed = PowerActions.HostPowerAllowed" in api,
    "the phone still renders shared-host power buttons in Cloud":
        ui.count("hostPowerAllowed && <button") == 3,
}
failed = [message for message, passed in checks.items() if not passed]
if failed:
    raise SystemExit("remote power policy gate failed:\n- " + "\n- ".join(failed))
print("remote power policy gate passed")
