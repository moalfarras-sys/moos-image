#!/usr/bin/env python3
"""Behavior gate: Mo AI must not confuse a rejected GUI launch with success."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moai-do"


def executable(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def run(run_status: int) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as raw:
        bindir = Path(raw)
        executable(bindir / "flatpak", f'''case "$1" in
  info) exit 0 ;;
  run) exit {run_status} ;;
esac
exit 2
''')
        executable(bindir / "logger", "exit 0\n")
        executable(bindir / "moos-gpu-headroom", "exit 0\n")
        env = os.environ.copy()
        env["PATH"] = f"{bindir}:/usr/bin:/bin"
        return subprocess.run(
            ["bash", str(SCRIPT), "setup-windows"], text=True,
            capture_output=True, env=env, timeout=15,
        )


accepted = run(0)
assert accepted.returncode == 0, accepted.stderr
assert "create an 'Application' bottle" in accepted.stdout

rejected = run(7)
assert rejected.returncode != 0, "a rejected Flatpak launch reported success"
assert "could not be opened" in rejected.stderr
assert "create an 'Application' bottle" not in rejected.stdout, \
    "setup instructions claimed a window existed after launch rejection"

print("PASS: Mo AI distinguishes accepted and rejected GUI launches")
