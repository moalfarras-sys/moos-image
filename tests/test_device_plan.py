import pathlib
#!/usr/bin/env python3
"""Black-box hardware-plan tests with deterministic fake host commands."""
from pathlib import Path
import json
import importlib.machinery
import importlib.util
import os
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "system_files/usr/bin/moos-device-plan"


def executable(path: Path, shell_body: str, windows_body: str) -> None:
    if os.name == "nt":
        path = path.with_suffix(".cmd")
        path.write_text("@echo off\r\n" + windows_body, encoding="utf-8")
    else:
        path.write_text("#!/bin/sh\n" + shell_body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if os.name == "nt":
    # Windows cannot directly execute the extensionless Linux helper or the
    # extensionless fake commands used by the black-box branch below. Import
    # the same production file and replace only its host probes; CI/Linux still
    # exercises the real process boundary.
    loader = importlib.machinery.SourceFileLoader("moos_device_plan", str(PLAN))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)

    lspci = """01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
\tKernel driver in use: nouveau
04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
\tKernel driver in use: r8169"""

    def fake_run(*args, timeout=12):
        if args and args[0] == "lspci":
            return lspci
        if args and args[0] == "bootc":
            return '{"status":"ok"}'
        if args and args[0] == "mokutil":
            return "SecureBoot enabled"
        return ""

    module.run = fake_run
    module.flatpak_installed = lambda _app_id: False
    module.firmware_report = lambda: ([], [])
    data = module.detect()
else:
    with tempfile.TemporaryDirectory() as tmp:
        bindir = Path(tmp)
        executable(bindir / "lspci", """cat <<'EOF'
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
\tKernel driver in use: nouveau
04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
\tKernel driver in use: r8169
EOF
""", """echo 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
echo   Kernel driver in use: nouveau
echo 04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
echo   Kernel driver in use: r8169
""")
        executable(bindir / "flatpak", "exit 1\n", "exit /b 1\r\n")
        executable(
            bindir / "bootc",
            "printf '%s\\n' '{\"status\":\"ok\"}'\n",
            "echo {\"status\":\"ok\"}\r\n",
        )
        executable(
            bindir / "mokutil",
            "echo 'SecureBoot enabled'\n",
            "echo SecureBoot enabled\r\n",
        )
        env = dict(os.environ)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        data = json.loads(subprocess.check_output([str(PLAN)], text=True, env=env))

assert data["gpu_vendor"] == "nvidia"
assert data["driver"] == "nouveau", data["driver"]
assert data["health"] == "action-needed"
assert data["actions"][0]["url"] == "moos://do/install-nvidia"
assert "r8169" not in data["driver"]
assert data["driver_status"] == "NVIDIA detected; optimized image required", data["driver_status"]
# Mo AI renders the status line verbatim; an Arabic session must get Arabic.
assert any("\u0600" <= ch <= "\u06ff" for ch in data["driver_status_ar"]), data["driver_status_ar"]

# The NVIDIA image is published only for x86_64. Some ARM boards expose an
# NVIDIA PCI display device too; the hardware card must never offer an x86 image
# switch there even when the driver is absent.
loader = importlib.machinery.SourceFileLoader("moos_device_plan_arm", str(PLAN))
spec = importlib.util.spec_from_loader(loader.name, loader)
arm_module = importlib.util.module_from_spec(spec)
loader.exec_module(arm_module)
arm_module.run = lambda *args, **kwargs: (
    "01:00.0 VGA compatible controller: NVIDIA Corporation Device" if args[0] == "lspci"
    else '{"status":"ok"}' if args[0] in ("bootc", "rpm-ostree")
    else ""
)
arm_module.flatpak_installed = lambda _app_id: False
arm_module.firmware_report = lambda: ([], [])
arm = arm_module.detect(machine="aarch64")
assert arm["architecture"] == "aarch64"
assert all(action.get("url") != "moos://do/install-nvidia" for action in arm["actions"])
assert "ARM" in arm["driver_status"], arm["driver_status"]

print("MoOS device-plan test passed")


# Every device-plan title reaches the owner's screen through Mo AI's diagnostic
# card. Four of the six carried "عربي | English"; two shipped English-only and
# showed up untranslated inside an otherwise fully Arabic Mo AI on the live
# session. The convention is only a convention if something enforces it.
import re as _re
_plan = (pathlib.Path(__file__).resolve().parent.parent
         / "system_files/usr/bin/moos-device-plan").read_text(encoding="utf-8")
_titles = _re.findall(r'"title":\s*"([^"]+)"', _plan)
assert _titles, "no device-plan titles found"
_english_only = [t for t in _titles if not _re.search(r"[؀-ۿ]", t)]
assert not _english_only, (
    "these titles reach an Arabic screen untranslated; follow the "
    f"\"عربي | English\" convention the others use: {_english_only}")
print(f"device-plan bilingual title gate passed ({len(_titles)} titles)")
