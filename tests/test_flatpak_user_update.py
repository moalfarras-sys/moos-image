#!/usr/bin/env python3
"""Regression proof for the unified Flatpak update implementation."""

from pathlib import Path
import os
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


def run_case(mode: str, scope: str = "--user") -> tuple[subprocess.CompletedProcess[str], list[str]]:
    with tempfile.TemporaryDirectory(prefix="moos-flatpak-update-") as tmp:
        tmp_path = Path(tmp)
        log = tmp_path / "calls"
        fake = tmp_path / "flatpak"
        fake.write_text(
            """#!/usr/bin/bash
set -u
printf '%s\\n' "$*" >>"$MOOS_TEST_LOG"
case " $* " in
  *" update --no-static-deltas "*)
    [ "$MOOS_TEST_MODE" != "fail-both" ]
    ;;
  *" update "*)
    [ "$MOOS_TEST_MODE" = "normal" ]
    ;;
  *) exit 0 ;;
esac
""",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        env = os.environ | {
            "MOOS_FLATPAK_BIN": str(fake),
            "MOOS_TEST_LOG": str(log),
            "MOOS_TEST_MODE": mode,
        }
        result = subprocess.run(
            [str(HELPER), scope], text=True, capture_output=True, env=env, check=False
        )
        return result, log.read_text(encoding="utf-8").splitlines()


normal, normal_calls = run_case("normal")
assert normal.returncode == 0, normal.stderr
assert sum(" update " in f" {call} " for call in normal_calls) == 1
assert not any("--no-static-deltas" in call for call in normal_calls)

recovered, recovered_calls = run_case("retry")
assert recovered.returncode == 0, recovered.stderr
assert any("--no-static-deltas" in call for call in recovered_calls)
assert "retrying from complete objects" in recovered.stderr
assert recovered_calls[-1] == "--user repair"

failed, failed_calls = run_case("fail-both")
assert failed.returncode != 0, "both failed update paths must remain visible to systemd"
assert any("--no-static-deltas" in call for call in failed_calls)
assert failed_calls[-1] != "--user repair", "repair must not conceal an update failure"

system, system_calls = run_case("retry", "--system")
assert system.returncode == 0, system.stderr
assert all(call.startswith("--system ") for call in system_calls)
assert system_calls[-1] == "--system repair"

invalid = subprocess.run([str(HELPER), "--all"], text=True, capture_output=True, check=False)
assert invalid.returncode == 2, "an unbounded Flatpak scope must be rejected"

print("Unified Flatpak update recovery gate passed")
