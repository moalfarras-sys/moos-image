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

# The live bootc CLI requires root. The desktop hardware plan must fall back to
# rpm-ostree's unprivileged status instead of telling an NVIDIA-image user that
# the optimized image is missing.
if os.name != "nt":
    with tempfile.TemporaryDirectory() as tmp:
        bindir = Path(tmp)
        executable(bindir / "lspci", """cat <<'EOF'
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
\tKernel driver in use: nvidia
EOF
""", "")
        executable(bindir / "flatpak", "exit 1\n", "")
        executable(bindir / "bootc", "exit 1\n", "")
        executable(
            bindir / "rpm-ostree",
            """printf '%s\n' '{"deployments":[{"booted":true,"container-image-reference":"ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@sha256:abc"}]}'\n""",
            "",
        )
        executable(bindir / "mokutil", "echo 'SecureBoot enabled'\n", "")
        env = dict(os.environ)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
        nvidia_data = json.loads(
            subprocess.check_output([str(PLAN)], text=True, env=env)
        )
    assert nvidia_data["nvidia_image"] is True
    assert nvidia_data["driver_status"] == "NVIDIA proprietary driver active"

print("MoOS device-plan test passed")
