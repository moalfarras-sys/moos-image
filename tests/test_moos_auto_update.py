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

# 3. Every official edition rides the train — including moos-cloud, which the
#    interactive updater deliberately does not offer.
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

if errors:
    print("MoOS auto-update test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("OK: the nightly train stages exact signed digests for all three editions "
      "and refuses foreign origins, bad digests and busy sysroots")
