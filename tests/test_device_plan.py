#!/usr/bin/env python3
"""Black-box hardware-plan tests with deterministic fake host commands."""
from pathlib import Path
import json
import os
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "system_files/usr/bin/moos-device-plan"


def executable(path, body):
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    executable(bindir / "lspci", """cat <<'EOF'
01:00.0 VGA compatible controller [0300]: NVIDIA Corporation TU104 [10de:1e81]
\tKernel driver in use: nouveau
04:00.0 Ethernet controller [0200]: Realtek [10ec:8125]
\tKernel driver in use: r8169
EOF
""")
    executable(bindir / "flatpak", "exit 1\n")
    executable(bindir / "bootc", "printf '%s\\n' '{\"status\":\"ok\"}'\n")
    executable(bindir / "mokutil", "echo 'SecureBoot enabled'\n")
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:/usr/bin:/bin"
    data = json.loads(subprocess.check_output([str(PLAN)], text=True, env=env))
    assert data["gpu_vendor"] == "nvidia"
    assert data["driver"] == "nouveau", data["driver"]
    assert data["health"] == "action-needed"
    assert data["actions"][0]["url"] == "moos://do/install-nvidia"
    assert "r8169" not in data["driver"]

print("MoOS device-plan test passed")
