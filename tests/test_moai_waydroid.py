#!/usr/bin/env python3
"""Behavior gate for Mo AI's confirmed, truth-reporting Waydroid setup action."""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moai-do"


def command(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    path.chmod(0o755)


def run(container_ok: bool, answer: str = "y\n") -> tuple[subprocess.CompletedProcess[str], str]:
    with tempfile.TemporaryDirectory() as raw:
        bindir = Path(raw)
        log = bindir / "calls.log"
        command(bindir / "waydroid", f'''printf 'waydroid %s\\n' "$*" >> "{log}"
case "$1 $2" in
  "status ") printf 'Session: RUNNING\\n' ;;
esac
exit 0
''')
        command(bindir / "systemctl", f'''printf 'systemctl %s\\n' "$*" >> "{log}"
case "$1 $2" in
  "is-active --quiet") {'exit 0' if container_ok else 'exit 1'} ;;
  "enable --now") {'exit 0' if container_ok else 'exit 1'} ;;
esac
exit 0
''')
        command(bindir / "pkexec", 'exec "$@"\n')
        command(bindir / "logger", "exit 0\n")
        command(bindir / "moos-gpu-headroom", "exit 0\n")
        command(bindir / "sleep", "exit 0\n")
        env = os.environ.copy()
        env["PATH"] = f"{bindir}:/usr/bin:/bin"
        result = subprocess.run(
            ["bash", str(SCRIPT), "setup-waydroid"], input=answer,
            text=True, capture_output=True, env=env, timeout=15,
        )
        return result, log.read_text(encoding="utf-8") if log.exists() else ""


declined, decline_log = run(container_ok=True, answer="n\n")
assert declined.returncode == 0
assert "systemctl enable --now" not in decline_log, "a declined public route changed state"

failed, failed_log = run(container_ok=False)
assert failed.returncode != 0, "a rejected container start reported success"
assert "Android جاهز" not in failed.stdout, "failure printed the ready banner"
assert "show-full-ui" not in failed_log, "the UI launched after container failure"

passed, passed_log = run(container_ok=True)
assert passed.returncode == 0, passed.stderr
assert "systemctl enable --now waydroid-container.service" in passed_log
assert "systemctl is-active --quiet waydroid-container.service" in passed_log
assert "waydroid session start" in passed_log
assert "waydroid show-full-ui" in passed_log
assert "Android جاهز" in passed.stdout

print("PASS: Waydroid always confirms and reports ready only after container/session proof")
