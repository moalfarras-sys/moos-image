#!/usr/bin/env python3
"""Regression gates for the single signed MoOS image-update authority."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "system_files/usr/libexec/moos-image-update"
BUILD_SH = ROOT / "build_files/build.sh"
UNIT_DIR = ROOT / "system_files/usr/lib/systemd/system"
NOTIFIER = ROOT / "system_files/usr/libexec/moos-update-ready"
USER_UNITS = ROOT / "system_files/usr/lib/systemd/user"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"

loader = importlib.machinery.SourceFileLoader("moos_image_update", str(BACKEND))
spec = importlib.util.spec_from_loader(loader.name, loader)
assert spec is not None
UPDATE = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = UPDATE
loader.exec_module(UPDATE)

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


NEW = "sha256:" + "d" * 64
NEWEST = "sha256:" + "e" * 64
OLD = "sha256:" + "b" * 64


def signed(edition: str, digest: str, *, transport: str = "signed") -> str:
    return (
        f"ostree-image-{transport}:docker://ghcr.io/moalfarras-sys/"
        f"{edition}@{digest}"
    )


@contextmanager
def no_lock():
    yield


def run_automatic(
    *,
    booted_ref: str,
    registry: str | list[str] = NEW,
    transaction: str | list[str] | None = None,
    staged_ref: str = "",
    status_payload: str | None = None,
    status_failure: bool = False,
    registry_failure: bool = False,
    missing_tool: str = "",
) -> tuple[int, list[tuple[str, ...]], str, str]:
    deployments = []
    if staged_ref:
        deployments.append({
            "booted": False,
            "staged": True,
            "version": "44.staged",
            "container-image-reference": staged_ref,
        })
    deployments.append({
        "booted": True,
        "staged": False,
        "version": "44.booted",
        "container-image-reference": booted_ref,
    })
    status = status_payload if status_payload is not None else json.dumps({
        "transaction": transaction,
        "deployments": deployments,
    })
    digests = list(registry) if isinstance(registry, list) else [registry]
    rebases: list[tuple[str, ...]] = []

    def fake_run(*argv: str, timeout: int = 60) -> str:
        del timeout
        if argv[:3] == (UPDATE.RPM_OSTREE, "status", "--json"):
            if status_failure:
                raise UPDATE.UpdateError("rpm-ostree failed", code=3)
            return status
        if argv[:2] == (UPDATE.SKOPEO, "inspect"):
            if registry_failure:
                raise UPDATE.UpdateError("network unavailable", code=3)
            return (digests.pop(0) if len(digests) > 1 else digests[0]) + "\n"
        if argv[:2] == (UPDATE.RPM_OSTREE, "rebase"):
            rebases.append(tuple(argv))
            return ""
        raise AssertionError(f"unexpected subprocess argv: {argv!r}")

    old_run = UPDATE.run
    old_access = UPDATE.os.access
    old_geteuid = UPDATE.os.geteuid
    old_lock = UPDATE.deployment_lock
    old_deferral = UPDATE.auto_deferral_reason
    UPDATE.run = fake_run
    UPDATE.os.access = lambda path, _mode: str(path) != missing_tool
    UPDATE.os.geteuid = lambda: 0
    UPDATE.deployment_lock = no_lock
    UPDATE.auto_deferral_reason = lambda: ""
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = UPDATE.automatic()
    finally:
        UPDATE.run = old_run
        UPDATE.os.access = old_access
        UPDATE.os.geteuid = old_geteuid
        UPDATE.deployment_lock = old_lock
        UPDATE.auto_deferral_reason = old_deferral
    return rc, rebases, stdout.getvalue(), stderr.getvalue()


# Happy path: only an exact signed target derived by the authority reaches rebase.
rc, rebases, _out, err = run_automatic(booted_ref=signed("moos-nvidia", OLD))
check(rc == 0, f"happy-path auto update failed: {err}")
check(
    rebases == [(UPDATE.RPM_OSTREE, "rebase", signed("moos-nvidia", NEW))],
    f"the backend must construct one exact signed rebase; got {rebases!r}",
)

# All product editions share the same policy, without prefix confusion.
for edition in UPDATE.EDITIONS:
    rc, rebases, _out, err = run_automatic(booted_ref=signed(edition, OLD))
    check(rc == 0, f"{edition}: auto update failed: {err}")
    check(rebases == [(UPDATE.RPM_OSTREE, "rebase", signed(edition, NEW))],
          f"{edition}: wrong target {rebases!r}")

for edition in UPDATE.EDITIONS:
    check(UPDATE.official_edition(signed(edition, OLD)) == edition,
          f"the exact {edition} origin must be recognized")
for refused in (
    signed("moos", OLD, transport="unverified"),
    f"ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos.evil@{OLD}",
    f"ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia.evil@{OLD}",
    f"ostree-image-signed:docker://evil/moos@{OLD}",
    f"ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos@{OLD}suffix",
):
    check(UPDATE.official_edition(refused) is None,
          f"a foreign/lookalike/unverified origin must be refused: {refused}")
    rc, rebases, _out, _err = run_automatic(booted_ref=refused)
    check(rc == 0 and not rebases,
          f"automatic updates must leave an unmanaged origin untouched: {refused}")

# Current, busy, and already-staged are clean no-op states.
rc, rebases, out, _err = run_automatic(
    booted_ref=signed("moos", OLD), registry=OLD)
check(rc == 0 and not rebases and "already current" in out,
      "an already-current machine must be a clean no-op")
for transaction in ("rebase", ["rebase", "target"]):
    rc, rebases, _out, _err = run_automatic(
        booted_ref=signed("moos", OLD), transaction=transaction)
    check(rc == 0 and not rebases, "a busy sysroot must never be raced")
rc, rebases, out, _err = run_automatic(
    booted_ref=signed("moos-cloud", OLD),
    staged_ref=signed("moos-cloud", NEW),
)
check(rc == 0 and not rebases and "already staged" in out,
      "the latest already-staged image must not be rebased again")

# An older staged deployment does not hide a newer candidate.
rc, rebases, _out, err = run_automatic(
    booted_ref=signed("moos-cloud", OLD),
    staged_ref=signed("moos-cloud", NEW),
    registry=NEWEST,
)
check(rc == 0 and rebases == [
    (UPDATE.RPM_OSTREE, "rebase", signed("moos-cloud", NEWEST))
], f"the newer candidate must replace an older staged image: {err} {rebases!r}")

# TOCTOU regression: if :latest moves after confirmation, do not silently stage it.
rc, rebases, _out, err = run_automatic(
    booted_ref=signed("moos", OLD), registry=[NEW, NEWEST])
check(rc == 76 and not rebases and "changed after confirmation" in err,
      "a candidate change between resolve and stage must fail closed")

# Malformed/security state is red; ordinary registry unavailability is deferred.
for bad in ("latest", "sha256:" + "a" * 63, "sha256:" + "A" * 64, " " + NEW):
    rc, rebases, _out, _err = run_automatic(
        booted_ref=signed("moos", OLD), registry=bad)
    check(rc == 5 and not rebases, f"invalid registry digest must fail: {bad!r}")
rc, rebases, _out, _err = run_automatic(
    booted_ref=signed("moos", OLD), status_payload="{not-json")
check(rc == 3 and not rebases, "malformed rpm-ostree state must fail the unit")
rc, rebases, _out, _err = run_automatic(
    booted_ref=signed("moos", OLD), status_failure=True)
check(rc == 3 and not rebases, "a broken rpm-ostree status call must fail the unit")
rc, rebases, _out, _err = run_automatic(
    booted_ref=signed("moos", OLD), registry_failure=True)
check(rc == 0 and not rebases, "temporary registry/network failure must defer cleanly")
for missing in (UPDATE.RPM_OSTREE, UPDATE.SKOPEO):
    rc, rebases, _out, _err = run_automatic(
        booted_ref=signed("moos", OLD), missing_tool=missing)
    check(rc == 3 and not rebases, f"missing required tool must fail: {missing}")

# Root enforcement lives inside stage(), not only in argparse's front door.
old_geteuid = UPDATE.os.geteuid
UPDATE.os.geteuid = lambda: 1000
try:
    try:
        UPDATE.stage(NEW)
        check(False, "non-root stage unexpectedly succeeded")
    except UPDATE.UpdateError as error:
        check(error.code == 77, f"non-root stage must return 77, got {error.code}")
finally:
    UPDATE.os.geteuid = old_geteuid

# Automatic work preserves the hardware-pressure policy that used to live in
# uupd's system module; manual user-requested staging is not blocked by it.
old_deferral = UPDATE.auto_deferral_reason
old_resolve = UPDATE.resolve
try:
    for reason in ("battery-low:12%", "cpu-busy:88%", "memory-busy:94%",
                   "network-busy:900000B/s"):
        UPDATE.auto_deferral_reason = lambda _reason=reason: _reason
        UPDATE.resolve = lambda: (_ for _ in ()).throw(
            AssertionError("a deferred run must not contact the registry"))
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = UPDATE.automatic()
        check(rc == 0 and reason in stdout.getvalue(),
              f"automatic update must defer cleanly for {reason}")
finally:
    UPDATE.auto_deferral_reason = old_deferral
    UPDATE.resolve = old_resolve

# Wiring and ownership: one OS backend, application-only uupd, no rival timers.
service = (UNIT_DIR / "moos-auto-update.service").read_text(encoding="utf-8")
timer = (UNIT_DIR / "moos-auto-update.timer").read_text(encoding="utf-8")
build_sh = BUILD_SH.read_text(encoding="utf-8")
uupd = json.loads((ROOT / "system_files/etc/uupd/config.json").read_text(encoding="utf-8"))
check("ExecStart=/usr/libexec/moos-image-update auto" in service,
      "the compatibility service name must execute the one backend directly")
check("After=network-online.target\n" in service and "uupd.service" not in service,
      "the OS writer must not be ordered behind a rival application updater")
check("Persistent=true" in timer, "missed overnight checks must run later")
check("systemctl enable moos-auto-update.timer" in build_sh,
      "the image must enable its OS update schedule")
check(os.access(BACKEND, os.X_OK), "the update backend must be executable")
check(not (BACKEND.parent / "moos-auto-update").exists(),
      "the retired duplicate updater executable must not remain")
check(uupd["modules"]["system"]["disable"] is True,
      "uupd must not be a second OS-image writer")
hardware = uupd["checks"]["hardware"]
check(UPDATE.BATTERY_MIN_PERCENT == hardware["bat-min-percent"]
      and UPDATE.CPU_MAX_PERCENT == hardware["cpu-max-percent"]
      and UPDATE.MEMORY_MAX_PERCENT == hardware["mem-max-percent"]
      and UPDATE.NETWORK_MAX_BYTES_PER_SECOND == hardware["net-max-bytes"],
      "the one OS backend must preserve MoOS's measured background-pressure limits")
check('run(RPM_OSTREE, "rebase", target' in BACKEND.read_text(encoding="utf-8"),
      "the authority must own the exact rebase")
for client in (
    ROOT / "system_files/usr/bin/moai-do",
    ROOT / "system_files/usr/bin/moos-update",
):
    source = client.read_text(encoding="utf-8")
    check('"rpm-ostree", "rebase"' not in source and "run_priv rpm-ostree rebase" not in source,
          f"{client.name} must delegate instead of writing deployments")


def run_notifier(*, staged_version: str, already_told: str = "") -> tuple[str, str]:
    """Run the staged-update notifier against command doubles."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        bindir = home / "bin"
        bindir.mkdir()
        sent = home / "sent.log"
        state_dir = home / "state" / "moos"
        state_dir.mkdir(parents=True)
        if already_told:
            (state_dir / "update-ready").write_text(already_told, encoding="utf-8")
        staged = f'"staged":true,"version":"{staged_version}"' if staged_version \
            else '"staged":false,"version":"44.1"'
        (bindir / "rpm-ostree").write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' '{{\"deployments\":[{{\"booted\":true,\"staged\":false," \
            f"\"version\":\"44.0\"}},{{{staged}}}]}}'\n",
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


check(os.access(NOTIFIER, os.X_OK), "the staged-update notifier must be executable")
check("systemctl --global enable moos-update-ready.timer" in build_sh,
      "the staged update announcement must be enabled")
notify_timer = (USER_UNITS / "moos-update-ready.timer").read_text(encoding="utf-8")
check("OnStartupSec=5min" in notify_timer and "OnUnitActiveSec=6h" in notify_timer,
      "the notifier must run after login and again in long sessions")
if Path("/ostree/deploy").is_dir():
    told, recorded = run_notifier(staged_version="44.20260804.9")
    check("44.20260804.9" in told and recorded == "44.20260804.9",
          "a staged update must be announced and recorded")
    told, _ = run_notifier(
        staged_version="44.20260804.9", already_told="44.20260804.9")
    check(told == "", "the same staged version must not be announced twice")
    told, _ = run_notifier(staged_version="")
    check(told == "", "no staged deployment means no notification")

if errors:
    print("MoOS image-update test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print("OK: one update authority stages exact signed digests for all four editions, "
      "fails closed on malformed/security state, and defers only transient conditions")
