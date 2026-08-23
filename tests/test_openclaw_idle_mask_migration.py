#!/usr/bin/env python3
"""Run the real UI migration against the historical OpenClaw service mask."""

from pathlib import Path
import os
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
MIGRATE = ROOT / "system_files/usr/bin/moos-ui-migrate"


def run_case(mode: str, unit_kind: str = "mask") -> tuple[int, Path, list[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="moos-openclaw-mask-")
    # Keep the directory alive for assertions after the subprocess returns.
    run_case.temporary.append(temporary)
    root = Path(temporary.name)
    config = root / "config"
    state = root / "state"
    data = root / "data"
    cache = root / "cache"
    user_units = config / "systemd/user"
    system_units = root / "usr/lib/systemd/user"
    user_units.mkdir(parents=True)
    system_units.mkdir(parents=True)
    (system_units / "openclaw-idle.service").write_text("[Service]\n", encoding="utf-8")
    unit = user_units / "openclaw-idle.service"
    if unit_kind == "mask":
        unit.symlink_to("/dev/null")
    elif unit_kind == "custom":
        unit.write_text("[Service]\nExecStart=/opt/custom-idle\n", encoding="utf-8")

    calls = root / "systemctl.calls"
    fake = root / "systemctl"
    fake.write_text(
        """#!/usr/bin/bash
printf '%s\\n' "$*" >>"$MOOS_TEST_CALLS"
case "$*" in
  "--user is-enabled --quiet openclaw-idle.timer")
    [ "$MOOS_TEST_MODE" != "disabled" ] ;;
  "--user is-active --quiet openclaw-idle.timer")
    [ "$MOOS_TEST_MODE" != "start-fails" ] ;;
  "--user start openclaw-idle.timer")
    [ "$MOOS_TEST_MODE" != "start-fails" ] ;;
  *) exit 0 ;;
esac
""",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = os.environ | {
        "HOME": str(root / "home"),
        "XDG_CONFIG_HOME": str(config),
        "XDG_STATE_HOME": str(state),
        "XDG_DATA_HOME": str(data),
        "XDG_CACHE_HOME": str(cache),
        "MOOS_SYSTEMD_USER_DIR": str(system_units),
        "MOOS_SYSTEMCTL_BIN": str(fake),
        "MOOS_TEST_CALLS": str(calls),
        "MOOS_TEST_MODE": mode,
    }
    result = subprocess.run(
        [str(MIGRATE), "--input-only"], env=env, text=True, capture_output=True
    )
    call_list = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
    return result.returncode, root, call_list


run_case.temporary = []

code, healed, calls = run_case("enabled")
assert code == 0
assert not (healed / "config/systemd/user/openclaw-idle.service").exists()
assert (healed / "state/moos/openclaw-idle-mask-v1.done").is_file()
assert "--user start openclaw-idle.timer" in calls
assert "--user is-active --quiet openclaw-idle.timer" in calls

code, disabled, _ = run_case("disabled")
assert code == 0
assert (disabled / "config/systemd/user/openclaw-idle.service").is_symlink()
assert (disabled / "state/moos/openclaw-idle-mask-v1.done").is_file()

code, custom, _ = run_case("enabled", "custom")
assert code == 0
assert (custom / "config/systemd/user/openclaw-idle.service").is_file()
assert "ExecStart=/opt/custom-idle" in (
    custom / "config/systemd/user/openclaw-idle.service"
).read_text(encoding="utf-8")

code, rolled_back, _ = run_case("start-fails")
assert code == 0
assert (rolled_back / "config/systemd/user/openclaw-idle.service").is_symlink()
assert not (rolled_back / "state/moos/openclaw-idle-mask-v1.done").exists()

print("OpenClaw idle-mask migration gate passed")
