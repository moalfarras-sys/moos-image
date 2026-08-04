#!/usr/bin/env python3
"""moos-auto-update — the nightly signed-image train for digest-pinned installs.

`moai-do update` deliberately stages an exact digest (the privilege boundary
escalates only an immutable object), which leaves the origin digest-pinned —
and uupd's `bootc upgrade` cannot advance a digest-pinned origin, so background
OS updates silently died on every machine that ever updated manually. The
nightly unit must therefore carry the SAME contract as the manual path:
official editions only, digest-shape validation, exact-digest rebase through
the signature-enforcing transport, and polite refusal to race another writer.

Everything runs against command doubles: nothing here reaches rpm-ostreed or a
registry; the captured rebase argv is the proof of the boundary.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moos-auto-update"
BUILD_SH = ROOT / "build_files/build.sh"
UNIT_DIR = ROOT / "system_files/usr/lib/systemd/system"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def run_with_doubles(
    *,
    booted_ref: str,
    registry_digest: str,
    transaction: str = "",
) -> tuple[subprocess.CompletedProcess, str]:
    """Run the script against doubles; return (result, captured rebase argv)."""
    with tempfile.TemporaryDirectory() as tmp:
        bindir = Path(tmp)
        log = bindir / "rebase.log"
        transaction_json = f'"{transaction}"' if transaction else "null"
        status = (
            f'{{"transaction":{transaction_json},"deployments":[{{"booted":true,'
            f'"container-image-reference":"{booted_ref}"}}]}}'
        )
        # One double answers `status --json` AND records any `rebase` argv —
        # the same binary carries both verbs in production.
        rpm_ostree = (
            "#!/bin/sh\n"
            'if [ "$1" = "status" ]; then\n'
            f"    printf '%s\\n' '{status}'\n"
            'elif [ "$1" = "rebase" ]; then\n'
            '    printf "%s\\n" "$@" > "$MOOS_TEST_REBASE_LOG"\n'
            "fi\n"
        )
        doubles = {
            "rpm-ostree": rpm_ostree,
            "skopeo": f"#!/bin/sh\nprintf '%s\\n' '{registry_digest}'\n",
        }
        for name, body in doubles.items():
            path = bindir / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        env["MOOS_TEST_REBASE_LOG"] = str(log)
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            env=env,
        )
        captured = log.read_text(encoding="utf-8") if log.exists() else ""
        return result, captured


NEW = "sha256:" + "d" * 64
OLD = "sha256:" + "b" * 64
PINNED_NVIDIA = f"ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@{OLD}"

# 1. The happy path: a digest-pinned NVIDIA install with a newer :latest must
#    rebase to the EXACT new digest through the signed transport — nothing else.
result, captured = run_with_doubles(booted_ref=PINNED_NVIDIA, registry_digest=NEW)
check(result.returncode == 0, f"happy-path run failed: {result.stderr}")
check(
    captured == (
        "rebase\n"
        f"ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia@{NEW}\n"
    ),
    f"the nightly train must rebase to the exact signed digest; got {captured!r}",
)

# 2. Already current: no rebase may run.
result, captured = run_with_doubles(booted_ref=PINNED_NVIDIA, registry_digest=OLD)
check(result.returncode == 0, "already-current run must exit 0")
check(captured == "", f"already-current run must not rebase; got {captured!r}")

# 3. Every official edition rides the train, and the same three-edition allowlist
#    is what `moai-do update` and the updater window enforce (the specific
#    editions are matched before the generic one in all three).
for edition in ("moos", "moos-cloud", "moos-nvidia"):
    ref = f"ostree-image-signed:docker://ghcr.io/moalfarras-sys/{edition}@{OLD}"
    result, captured = run_with_doubles(booted_ref=ref, registry_digest=NEW)
    check(result.returncode == 0, f"{edition}: run failed: {result.stderr}")
    check(
        f"/{edition}@{NEW}" in captured,
        f"{edition} must advance to the new digest; got {captured!r}",
    )

# 4. A foreign origin is not ours to rewrite.
result, captured = run_with_doubles(
    booted_ref=f"ostree-image-signed:docker://ghcr.io/somebody-else/os@{OLD}",
    registry_digest=NEW,
)
check(result.returncode == 0, "foreign origin must exit 0 (leave it alone)")
check(captured == "", f"foreign origin must never be rebased; got {captured!r}")

# 5. A garbage digest from the registry must be refused loudly.
result, captured = run_with_doubles(
    booted_ref=PINNED_NVIDIA, registry_digest="latest-and-greatest"
)
check(result.returncode != 0, "an invalid registry digest must fail the run")
check(captured == "", f"an invalid digest must never reach rebase; got {captured!r}")

# 6. A transaction in progress means another writer owns the sysroot: skip.
result, captured = run_with_doubles(
    booted_ref=PINNED_NVIDIA, registry_digest=NEW, transaction="upgrade"
)
check(result.returncode == 0, "busy rpm-ostree must be a clean skip")
check(captured == "", f"busy rpm-ostree must not be raced; got {captured!r}")

# 7. The train must actually be wired: units shipped, timer enabled by the
#    image build, and the timer must fire clear of uupd's own window.
service = (UNIT_DIR / "moos-auto-update.service").read_text(encoding="utf-8")
timer = (UNIT_DIR / "moos-auto-update.timer").read_text(encoding="utf-8")
check("ExecStart=/usr/libexec/moos-auto-update" in service,
      "the service must run the shipped script")
check("After=network-online.target uupd.service" in service,
      "the service must order after the network and uupd")
check("Persistent=true" in timer,
      "machines that were off at 04:30 must still get their update")
check("systemctl enable moos-auto-update.timer" in BUILD_SH.read_text(encoding="utf-8"),
      "build.sh must bake the timer symlink into every edition")
check(os.access(SCRIPT, os.X_OK), "the script must be executable")

# 8. The staged update has to be ANNOUNCED. The train finishes at 04:30 and the
#    new deployment then sits on the disk, complete, until someone happens to
#    reboot — Plasma's notifier and `bootc upgrade --check` both read the
#    digest-pinned booted origin and report "no changes", so neither says a word.
NOTIFIER = ROOT / "system_files/usr/libexec/moos-update-ready"
USER_UNITS = ROOT / "system_files/usr/lib/systemd/user"
build_sh = BUILD_SH.read_text(encoding="utf-8")
check(os.access(NOTIFIER, os.X_OK), "the notifier must be executable")
check("systemctl --global enable moos-update-ready.timer" in build_sh,
      "an announcement nobody enabled is not an announcement")
notify_timer = (USER_UNITS / "moos-update-ready.timer").read_text(encoding="utf-8")
check("OnStartupSec=5min" in notify_timer,
      "the message must land after the session settles, not into the login storm")
check("OnUnitActiveSec=6h" in notify_timer,
      "a session left running across 04:30 must still learn about its update")


def run_notifier(*, staged_version: str, already_told: str = "") -> tuple[str, str]:
    """Run the notifier against doubles; return (notify-send argv, state file)."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        bindir = home / "bin"
        bindir.mkdir()
        sent = home / "sent.log"
        state_dir = home / "state" / "moos"
        state_dir.mkdir(parents=True)
        if already_told:
            (state_dir / "update-ready").write_text(already_told, encoding="utf-8")
        staged = f'"staged": true, "version": "{staged_version}"' if staged_version \
            else '"staged": false, "version": "44.1"'
        (bindir / "rpm-ostree").write_text(
            "#!/bin/sh\n"
            f"""printf '%s\\n' '{{"deployments":[{{"booted":true,"staged":false,"version":"44.0"}},"""
            f"""{{{staged}}}]}}'\n""",
            encoding="utf-8",
        )
        (bindir / "notify-send").write_text(
            f'#!/bin/sh\nprintf "%s\\n" "$@" > "{sent}"\n', encoding="utf-8")
        for tool in ("rpm-ostree", "notify-send"):
            (bindir / tool).chmod(0o755)
        subprocess.run(
            [BASH, str(NOTIFIER)],
            env={
                "PATH": f"{bindir}:/usr/bin:/bin",
                "HOME": str(home),
                "XDG_STATE_HOME": str(home / "state"),
                "LANG": "en_US.UTF-8",
            },
            capture_output=True,
            text=True,
            check=False,
        )
        state_file = state_dir / "update-ready"
        return (
            sent.read_text(encoding="utf-8") if sent.exists() else "",
            state_file.read_text(encoding="utf-8").strip() if state_file.exists() else "",
        )


if Path("/ostree/deploy").is_dir():
    told, recorded = run_notifier(staged_version="44.20260804.9")
    check("44.20260804.9" in told, f"a staged update must be announced; got {told!r}")
    check(recorded == "44.20260804.9", "the announced version must be recorded")
    check("--action" not in told,
          "the notification must carry no restart button — a stray click must not "
          "be able to take down a session that was in the middle of something")

    # Told once, never again for the same version — and nothing at all when the
    # machine has no staged update.
    told, _ = run_notifier(staged_version="44.20260804.9", already_told="44.20260804.9")
    check(told == "", f"the same version must not be announced twice; got {told!r}")
    told, _ = run_notifier(staged_version="")
    check(told == "", f"a machine with nothing staged must say nothing; got {told!r}")
else:
    print("note: /ostree/deploy is absent here, so the notifier's own guard "
          "short-circuits; its wiring was still checked")

if errors:
    print("MoOS auto-update test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("OK: the nightly train stages exact signed digests for all three editions "
      "and refuses foreign origins, bad digests and busy sysroots")
