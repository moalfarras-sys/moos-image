#!/usr/bin/env python3
"""Behavioural proof that GUI helpers reject stale Wayland session state."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/moos-wayland-display"
UNIT = (ROOT / "system_files/usr/lib/systemd/user/mo-remote-personal.service").read_text()
OPEN = (ROOT / "system_files/usr/bin/moai-open").read_text()
SHOT = (ROOT / "system_files/usr/bin/moai-screenshot").read_text()


def run(runtime: str, preferred: str = "") -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "XDG_RUNTIME_DIR": runtime, "WAYLAND_DISPLAY": preferred}
    return subprocess.run([str(HELPER)], env=env, text=True, capture_output=True, timeout=2)


with tempfile.TemporaryDirectory(prefix="moos-wayland-") as runtime:
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(os.path.join(runtime, "wayland-stale"))
    stale.close()

    older = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    older.bind(os.path.join(runtime, "wayland-older"))
    older.listen(2)
    newer = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    newer.bind(os.path.join(runtime, "wayland-newer"))
    newer.listen(2)
    os.utime(os.path.join(runtime, "wayland-older"), ns=(1, 1))
    os.utime(os.path.join(runtime, "wayland-newer"), ns=(2, 2))

    selected = run(runtime, "wayland-stale")
    assert selected.returncode == 0 and selected.stdout.strip() == "wayland-newer", selected
    preferred = run(runtime, "wayland-older")
    assert preferred.returncode == 0 and preferred.stdout.strip() == "wayland-older", preferred
    older.close()
    newer.close()

with tempfile.TemporaryDirectory(prefix="moos-wayland-empty-") as runtime:
    missing = run(runtime, "wayland-gone")
    assert missing.returncode != 0 and "no live Wayland compositor" in missing.stderr

for surface, source in (("Remote", UNIT), ("Mo AI open", OPEN), ("Mo AI screenshot", SHOT)):
    assert "/usr/libexec/moos-wayland-display" in source, f"{surface} bypasses the shared resolver"
    assert "WAYLAND_DISPLAY:-wayland-0" not in source, f"{surface} still guesses wayland-0"

print("OK: Remote and Mo AI select a connectable Wayland compositor, not a stale filename")
