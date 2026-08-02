#!/usr/bin/env python3
"""Gate: the Mo AI per-user port generator must FAIL CLOSED — no account other than
uid 1000 may ever resolve to the base ports 8080/8079/8077.

WHY THIS EXISTS

Mo AI's three services (gateway/control/agent-api) read their loopback port from the
environment; 60-moai-ports injects a per-user port so that on MoOS Cloud two developers
on one machine do not share a front door. The gateway is the one process that holds the
cloud API key, so a second account reaching uid 1000's gateway is a key-spending,
config-rewriting cross-tenant takeover — the exact thing the generator exists to stop.

The bug this guards: the generator computed offset=(uid-1000)*100 and, for uid>=1010
(offset>900), ran `exit 0` printing NOTHING. With no MOAI_*_PORT injected, the services
fall back to their built-in defaults — 8080/8079/8077, uid 1000's ports. So the 11th
account silently re-created the collision. Exiting-without-printing is fail-OPEN.

This runs the REAL generator with a faked uid (a stub `id` on PATH) and asserts every
non-1000 account gets three valid, non-base ports.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "system_files/usr/lib/systemd/user-environment-generators/60-moai-ports"
BASE = {"MOAI_GATEWAY_PORT": 8080, "MOAI_CONTROL_PORT": 8079, "MOAI_AGENT_PORT": 8077}


def run_generator(uid: int) -> dict[str, int]:
    """Run the generator as if invoked by uid's user manager."""
    with tempfile.TemporaryDirectory() as tmp:
        stub = Path(tmp) / "id"
        # The generator calls `id -u`; everything else falls through to the real id.
        stub.write_text(f'#!/bin/sh\nif [ "$1" = "-u" ]; then echo {uid}; else exec /usr/bin/id "$@"; fi\n')
        stub.chmod(0o755)
        env = dict(os.environ, PATH=f"{tmp}:{os.environ.get('PATH', '')}")
        result = subprocess.run(["bash", str(GEN)], capture_output=True, text=True, env=env, timeout=15)
    ports: dict[str, int] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            if value.strip().isdigit():
                ports[key.strip()] = int(value.strip())
    return ports


def main() -> int:
    if not GEN.is_file():
        print(f"GATE FAIL: {GEN.relative_to(ROOT)} is missing.")
        return 1

    errors: list[str] = []

    # uid 1000 keeps the base ports exactly — the daily-driver invariant.
    p1000 = run_generator(1000)
    if p1000 != BASE:
        errors.append(f"uid 1000 must keep the base ports {BASE}, got {p1000}")

    # Every OTHER account must get three valid, non-base, distinct ports. Include uids
    # in the linear band (1001, 1009) and — the regression — the high band that used to
    # fail open (1010, 1100, 5000).
    for uid in (1001, 1009, 1010, 1100, 5000):
        ports = run_generator(uid)
        if set(ports) != set(BASE):
            errors.append(f"uid {uid} did not emit all three MOAI_*_PORT vars (got {ports}) — "
                          f"a missing var makes the service fall back to the base port")
            continue
        for name, value in ports.items():
            if value == BASE[name]:
                errors.append(f"uid {uid} resolves {name}={value}, which is uid 1000's base port — "
                              f"fail-OPEN: this account would reach uid 1000's service")
            if not (1024 < value < 65536):
                errors.append(f"uid {uid} {name}={value} is outside the usable port range")
        if len(set(ports.values())) != 3:
            errors.append(f"uid {uid} ports collide with each other: {ports}")

    # A system account (uid < 1000) has no Mo AI session — but "emit nothing" was the
    # SAME fail-open shape as the old uid>=1010 arm: with no override the services fall
    # back to their built-in 8080/8079/8077, which ARE uid 1000's ports. Measured on the
    # Cloud host, root has a real login session and its user manager started
    # moai-agent-api, which sat in a restart loop on "[Errno 98] Address already in use"
    # against uid 1000's port. The benign outcome. The other one is root WINNING the
    # race and owning the desktop user's front door as root.
    for uid in (0, 999):
        ports = run_generator(uid)
        if set(ports) != set(BASE):
            errors.append(f"uid {uid} (system) did not emit all three MOAI_*_PORT vars "
                          f"(got {ports}) — with no override it falls back to uid 1000's "
                          f"base ports, which is exactly the collision this file prevents")
            continue
        for name, value in ports.items():
            if value == BASE[name]:
                errors.append(f"uid {uid} (system) resolves {name}={value} — uid 1000's port")
            if not (1024 < value < 65536):
                errors.append(f"uid {uid} {name}={value} is outside the usable port range")

    # Ports are the second line. The first is that these units must not start for a
    # system user at all — a root-owned loopback API that shells out to `openclaw` and
    # `systemctl --user` is reachable by every local account, and X-Moai-* headers are
    # guards against web pages, not against another user on the same machine.
    user_units = ROOT / "system_files/usr/lib/systemd/user"
    for unit in ("moai-agent-api", "moai-control", "moai-gateway", "moai",
                 "moai-wake", "openclaw-gateway"):
        path = user_units / f"{unit}.service"
        if not path.is_file():
            errors.append(f"{unit}.service is missing")
            continue
        if "ConditionUser=!@system" not in path.read_text(encoding="utf-8"):
            errors.append(f"{unit}.service must carry ConditionUser=!@system — root has a "
                          f"login session on MoOS Cloud and its user manager will start "
                          f"this otherwise")

    if errors:
        print("GATE FAIL: 60-moai-ports does not fail closed.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: uid 1000 keeps the base ports; every other account gets unique non-base ports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
