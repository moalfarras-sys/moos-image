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
import shutil


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


def run_case(mode: str, scope: str = "--user", hold_store_lock: bool = False,
             store_settings: str | None = None, helper_text: str | None = None,
             session_bus: str | None = None):
    """Returns (result, calls, record or None, lock file mode or None)."""
    with tempfile.TemporaryDirectory(prefix="moos-flatpak-update-") as tmp:
        tmp_path = Path(tmp)
        log = tmp_path / "calls"
        bus_log = tmp_path / "bus-addresses"
        fake = tmp_path / "flatpak"
        home = tmp_path / "home"
        home.mkdir()
        # A running Flatpak can still bind-mount a retired runtime. Full repair
        # removes that deployment; ordinary updates must leave it available.
        runtime_shell = tmp_path / "retired-sdk/usr/bin/sh"
        runtime_shell.parent.mkdir(parents=True)
        runtime_shell.write_text("running-runtime-sentinel\n", encoding="utf-8")
        fake.write_text(
            """#!/usr/bin/bash
set -u
printf '%s\\n' "$*" >>"$MOOS_TEST_LOG"
if [[ " $* " == *" update "* && "$MOOS_TEST_MODE" == bus-* ]]; then
  printf '%s\\n' "${DBUS_SESSION_BUS_ADDRESS:-}" >>"$MOOS_TEST_BUS_LOG"
  gdbus call --session --dest org.freedesktop.DBus \\
    --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.GetId || exit 1
  [ "$MOOS_TEST_MODE" != bus-fail ] || exit 42
  exit 0
fi
case " $* " in
  *" list "*)
    if [ "$MOOS_TEST_MODE" = "font-refusal" ]; then
      echo "unknown-owner-installation"
    fi
    ;;
  *" repair "*)
    rm -f -- "$MOOS_TEST_RUNTIME_SHELL"
    ;;
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
            "MOOS_TEST_BUS_LOG": str(bus_log),
            "MOOS_TEST_MODE": mode,
            "MOOS_TEST_RUNTIME_SHELL": str(runtime_shell),
        }
        if session_bus is not None:
            env["DBUS_SESSION_BUS_ADDRESS"] = session_bus
        if store_settings is not None:
            settings = tmp_path / "config/moos/store.json"
            settings.parent.mkdir(parents=True)
            settings.write_text(store_settings, encoding="utf-8")
        env["XDG_CONFIG_HOME"] = str(tmp_path / "config")
        lock_path = tmp_path / "cache/moos-store/job.lock"
        holder = None
        if hold_store_lock:
            lock_path.parent.mkdir(parents=True)
            holder = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            helper = HELPER
            if helper_text is not None:
                helper = tmp_path / "usr/libexec/update-control"
                helper.parent.mkdir(parents=True)
                helper.write_text(helper_text, encoding="utf-8")
                helper.chmod(0o755)
                library = tmp_path / 'usr/lib/moos'
                library.mkdir(parents=True)
                shutil.copyfile(ROOT / 'system_files/usr/lib/moos/moos_flatpak_fonts.py',
                                library / 'moos_flatpak_fonts.py')
            result = subprocess.run(
                [str(helper), scope], text=True, capture_output=True, env=env, check=False,
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
        result.runtime_preserved = runtime_shell.exists()
        result.bus_addresses = bus_log.read_text().splitlines() if bus_log.exists() else []
        return result, calls, record, mode_bits


normal, normal_calls, normal_record, lock_mode = run_case("normal")
assert normal.returncode == 0, normal.stderr
assert sum(" update " in f" {call} " for call in normal_calls) == 1
assert not any("--no-static-deltas" in call for call in normal_calls)
assert normal_record is not None and normal_record["schema"] == 1
assert (normal_record["state"], normal_record["failures"]) == ("ok", []), normal_record
assert isinstance(normal_record["updated"], int) and normal_record["updated"] > 0
assert lock_mode == 0o600, f"Mo Store's lock must stay private, found {lock_mode:o}"
assert normal.runtime_preserved, "a healthy timer update erased a running app's retired runtime"
assert not any(" repair" in call for call in normal_calls), normal_calls

recovered, recovered_calls, recovered_record, _ = run_case("retry")
assert recovered.returncode == 0, recovered.stderr
assert any("--no-static-deltas" in call for call in recovered_calls)
assert "retrying from complete objects" in recovered.stderr
assert [call for call in recovered_calls if not call.startswith('list ')][-1] == \
    "--user update --no-static-deltas -y --noninteractive"
assert recovered_calls[-2:] == ['list --columns=installation',
                              'list --app --columns=application,runtime,installation']
assert recovered.runtime_preserved, "delta recovery erased a running app's retired runtime"
assert recovered_record["state"] == "ok", "a recovered update is a successful one"

# Packages survive a font-policy refusal, and the existing updater must report
# that incomplete result instead of publishing a healthy font delivery.
font_refused, font_calls, font_record, _ = run_case('font-refusal')
assert font_refused.returncode != 0 and font_record['state'] == 'failed'
assert 'custom Flatpak installations' in font_refused.stderr
assert font_refused.runtime_preserved and not any(' repair' in call for call in font_calls)

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
assert system_calls[-1] == "--system update --no-static-deltas -y --noninteractive"
assert system.runtime_preserved
assert system_record is None and system_lock is None, \
    "the system scope is not the owner's applications: no per-user lock or record"

# Mo Store is mid-transaction: the scheduled run steps aside without touching anything.
busy, busy_calls, busy_record, _ = run_case("normal", hold_store_lock=True)
assert busy.returncode == 0, busy.stderr
assert busy_calls == [], f"the updater raced a Mo Store job: {busy_calls}"
assert busy_record is None, "a skipped run must not claim a result"
assert "Mo Store is running a job" in busy.stderr

# The person turned automatic updates off in Mo Store: the scheduled run does nothing at all.
off, off_calls, off_record, _ = run_case("normal", store_settings='{"auto_updates": false}')
assert off.returncode == 0, off.stderr
assert off_calls == [] and off_record is None, f"automatic updates ran while off: {off_calls}"
assert "automatic app updates are off" in off.stderr
# Anything but an explicit false keeps the default: on.
for text in ('{"auto_updates": true}', "{broken", '{"auto_updates": "no"}', "[]"):
    on, on_calls, on_record, _ = run_case("normal", store_settings=text)
    assert on.returncode == 0 and any(" update " in f" {call} " for call in on_calls), text
    assert on_record["state"] == "ok", text

invalid = subprocess.run([str(HELPER), "--all"], text=True, capture_output=True, check=False)
assert invalid.returncode == 2, "an unbounded Flatpak scope must be rejected"

# Reinsert the exact old unconditional maintenance operation. The controlled
# deployment is lost even though the old helper returns success and publishes ok.
# This is a behavioral refusal, not a string-only ban or a real user's runtime.
original = HELPER.read_text(encoding="utf-8")
assert original.count("\nfinished=1\n") == 1
broken = original.replace("\nfinished=1\n", '\n"$flatpak_bin" "$scope" repair\n\nfinished=1\n')
for scope in ("--user", "--system"):
    old, old_calls, _, _ = run_case("normal", scope, helper_text=broken)
    assert old.returncode == 0 and not old.runtime_preserved, old_calls

# Exercise real D-Bus, not just a nonempty environment variable. A system
# transaction that requests authentication must work with no display/session;
# the same request fails on the old source and when a supplied bus is invalid.
headless, calls, record, lock = run_case("bus-needed", "--system")
assert headless.returncode == 0, headless.stderr
assert len(headless.bus_addresses) == 1 and headless.bus_addresses[0].startswith("unix:"), calls
assert record is None and lock is None and headless.runtime_preserved
# The private bus must end with its updater; do not leave another idle daemon.
closed = subprocess.run(
    ["gdbus", "call", "--address", headless.bus_addresses[0], "--dest", "org.freedesktop.DBus",
     "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.GetId"],
    text=True, capture_output=True, timeout=5,
)
assert closed.returncode != 0, "the updater leaked its private session bus"

bus_block = original[original.index('if [ "$scope" = --system ] && [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then'):
                     original.index('\nflatpak_bin=')]
old, _, _, _ = run_case("bus-needed", "--system", helper_text=original.replace(bus_block, ""))
assert old.returncode != 0 and not any(old.bus_addresses), old.stderr

for scope in ("--user", "--system"):
    supplied = "unix:path=/moos-test/no-supplied-session-bus"
    refused, _, _, _ = run_case("bus-needed", scope, session_bus=supplied)
    assert refused.returncode != 0, "an explicitly broken bus was silently replaced"
    assert refused.bus_addresses == [supplied, supplied], refused.bus_addresses

user_headless, _, user_record, _ = run_case("bus-needed")
assert user_headless.returncode != 0 and user_record["state"] == "failed"
assert not any(user_headless.bus_addresses), "system isolation was applied to the user session"

failed_bus, failed_bus_calls, _, _ = run_case("bus-fail", "--system")
assert failed_bus.returncode == 42, (failed_bus.returncode, failed_bus.stderr)
assert any("--no-static-deltas" in call for call in failed_bus_calls), failed_bus_calls

not_started, not_started_calls, _, _ = run_case(
    "bus-needed", "--system",
    helper_text=original.replace("/usr/bin/dbus-run-session", "/usr/bin/false"),
)
assert not_started.returncode != 0 and not_started_calls == [], not_started.stderr

# A healthy caller-supplied session belongs to that caller and must survive
# both scopes. Use another private daemon, never the owner's desktop bus.
with tempfile.TemporaryDirectory(prefix="moos-flatpak-inherited-bus-") as tmp:
    private = Path(tmp)
    env = os.environ | {key: str(private / key) for key in
                        ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR")}
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
        Path(env[key]).mkdir(mode=0o700)
    daemon = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        address = daemon.stdout.readline().strip()
        assert address.startswith("unix:"), address
        for scope in ("--user", "--system"):
            inherited, _, _, _ = run_case("bus-needed", scope, session_bus=address)
            assert inherited.returncode == 0 and inherited.bus_addresses == [address], inherited.stderr
        assert daemon.poll() is None, "the updater stopped a caller-owned bus"
    finally:
        daemon.terminate()
        daemon.communicate(timeout=5)

print("Unified Flatpak update recovery gate passed")
