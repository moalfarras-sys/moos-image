#!/usr/bin/env python3
"""Keep a per-user MoOS Cloud remote from controlling the shared host."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
linux = (ROOT / "moremote/agent-linux/PowerActions.cs").read_text(encoding="utf-8")
windows = (ROOT / "moremote/agent/Core/PowerActions.cs").read_text(encoding="utf-8")
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
    "the phone does not gate the complete session/power surface in Cloud":
        'hostPowerAllowed ? <div className="grid">' in ui
        # The Cloud-managed fallback copy is now i18n-resolved at runtime: assert the binding exists.
        and 'tr("powerCloudManagedBody")' in ui,
    "Windows reports power success before shutdown.exe accepts the command":
        "return Execute(ShutdownCommand" in windows
        and "process.WaitForExit(timeoutMs)" in windows
        and "process.ExitCode != 0" in windows
        and 'Path.Combine(Environment.SystemDirectory, "shutdown.exe")' in windows,
    "Windows power execution can invoke a shell or concatenate arguments":
        "UseShellExecute = false" in windows and "startInfo.ArgumentList.Add(argument)" in windows,
}
failed = [message for message, passed in checks.items() if not passed]
if failed:
    raise SystemExit("remote power policy gate failed:\n- " + "\n- ".join(failed))
print("remote power policy gate passed")
