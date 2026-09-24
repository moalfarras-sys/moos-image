#!/usr/bin/env python3
"""Regression proof for the unified Flatpak update implementation.

Every case runs the real helper against a recording fake `flatpak` in a private HOME,
cache and state directory: the user scope takes Mo Store's lock and writes a record in
those directories, and a test must never do either in the owner's own home.
"""

from pathlib import Path
import fcntl
import json
import os
import stat
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/moos-flatpak-update"
USER_DROPIN = ROOT / (
    "system_files/usr/lib/systemd/user/flatpak-user-update.service.d/"
    "20-moos-resilient.conf"
)
SYSTEM_DROPIN = ROOT / (
    "system_files/usr/lib/systemd/system/flatpak-system-update.service.d/"
    "20-moos-resilient.conf"
)

assert HELPER.is_file() and os.access(HELPER, os.X_OK), "Flatpak update helper is not executable"
user_dropin = USER_DROPIN.read_text(encoding="utf-8")
system_dropin = SYSTEM_DROPIN.read_text(encoding="utf-8")
assert "ExecStart=/usr/libexec/moos-flatpak-update --user" in user_dropin
assert "ExecStart=/usr/libexec/moos-flatpak-update --system" in system_dropin


def run_case(mode: str, scope: str = "--user", hold_store_lock: bool = False):
    """Returns (result, calls, record or None, lock file mode or None)."""
    with tempfile.TemporaryDirectory(prefix="moos-flatpak-update-") as tmp:
        tmp_path = Path(tmp)
        log = tmp_path / "calls"
        fake = tmp_path / "flatpak"
        home = tmp_path / "home"
        home.mkdir()
        fake.write_text(
            """#!/usr/bin/bash
set -u
printf '%s\\n' "$*" >>"$MOOS_TEST_LOG"
case " $* " in
  *" update --no-static-deltas "*)
    if [ "$MOOS_TEST_MODE" = "fail-both" ]; then
      echo "Error: Failed to update app/org.example.Broken/x86_64/stable: Server returned status 404" >&2
      exit 1
    fi
    ;;
  *" update "*)
    if [ "$MOOS_TEST_MODE" != "normal" ]; then
      echo "Warning: Failed to update org.example.Broken: delta is corrupt" >&2
      echo "Warning: Failed to update org.example.Healed: delta is corrupt" >&2
      exit 1
    fi
    ;;
  *) exit 0 ;;
esac
""",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        env = {
            key: value for key, value in os.environ.items()
            if key not in {"DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY"}
        } | {
            "HOME": str(home),
            "XDG_CACHE_HOME": str(tmp_path / "cache"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_RUNTIME_DIR": str(tmp_path),
            "MOOS_FLATPAK_BIN": str(fake),
            "MOOS_TEST_LOG": str(log),
            "MOOS_TEST_MODE": mode,
        }
        lock_path = tmp_path / "cache/moos-store/job.lock"
        holder = None
        if hold_store_lock:
            lock_path.parent.mkdir(parents=True)
            holder = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            result = subprocess.run(
                [str(HELPER), scope], text=True, capture_output=True, env=env, check=False,
                timeout=60,
            )
        finally:
            if holder is not None:
                os.close(holder)
        record_path = tmp_path / "state/moos/app-updates.json"
        record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else None
        if record is not None:
            assert stat.S_IMODE(record_path.stat().st_mode) == 0o600, "the record is private"
        mode_bits = stat.S_IMODE(lock_path.stat().st_mode) if lock_path.exists() else None
        assert not (home / ".cache").exists() and not (home / ".local").exists(), \
            "the helper ignored XDG_CACHE_HOME/XDG_STATE_HOME and wrote into HOME"
        calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return result, calls, record, mode_bits


normal, normal_calls, normal_record, lock_mode = run_case("normal")
assert normal.returncode == 0, normal.stderr
assert sum(" update " in f" {call} " for call in normal_calls) == 1
assert not any("--no-static-deltas" in call for call in normal_calls)
assert normal_record is not None and normal_record["schema"] == 1
assert (normal_record["state"], normal_record["failures"]) == ("ok", []), normal_record
assert isinstance(normal_record["updated"], int) and normal_record["updated"] > 0
assert lock_mode == 0o600, f"Mo Store's lock must stay private, found {lock_mode:o}"

recovered, recovered_calls, recovered_record, _ = run_case("retry")
assert recovered.returncode == 0, recovered.stderr
assert any("--no-static-deltas" in call for call in recovered_calls)
assert "retrying from complete objects" in recovered.stderr
assert recovered_calls[-1] == "--user repair"
assert recovered_record["state"] == "ok", "a recovered update is a successful one"

failed, failed_calls, failed_record, _ = run_case("fail-both")
assert failed.returncode != 0, "both failed update paths must remain visible to systemd"
assert any("--no-static-deltas" in call for call in failed_calls)
assert failed_calls[-1] != "--user repair", "repair must not conceal an update failure"
assert failed_record["state"] == "failed", "a failed run must not stay 'running' or read 'ok'"
# The record says what the FINAL attempt says: the retry's reason for the app that failed
# again, and nothing for the one the retry updated (the delta error stays in the journal).
assert failed_record["failures"] == [
    {"app": "org.example.Broken", "reason": "Server returned status 404"},
], failed_record["failures"]
assert "delta is corrupt" in failed.stdout + failed.stderr, "the first attempt's words reach the journal"

system, system_calls, system_record, system_lock = run_case("retry", "--system")
assert system.returncode == 0, system.stderr
assert all(call.startswith("--system ") for call in system_calls)
assert system_calls[-1] == "--system repair"
assert system_record is None and system_lock is None, \
    "the system scope is not the owner's applications: no per-user lock or record"

# Mo Store is mid-transaction: the scheduled run steps aside without touching anything.
busy, busy_calls, busy_record, _ = run_case("normal", hold_store_lock=True)
assert busy.returncode == 0, busy.stderr
assert busy_calls == [], f"the updater raced a Mo Store job: {busy_calls}"
assert busy_record is None, "a skipped run must not claim a result"
assert "Mo Store is running a job" in busy.stderr

invalid = subprocess.run([str(HELPER), "--all"], text=True, capture_output=True, check=False)
assert invalid.returncode == 2, "an unbounded Flatpak scope must be rejected"

print("Unified Flatpak update recovery gate passed")
