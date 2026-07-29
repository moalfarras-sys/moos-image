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
import re
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

    # Every OTHER account must get three valid, non-base, distinct ports.
    #
    # EXHAUSTIVE, NOT SAMPLED. The first version of this gate checked uid 1001, 1009,
    # 1010, 1100 and 5000 — and every one of them passed while the generator produced
    # port 67980 (an impossible port) for uid 1399, because none of those samples landed
    # near the top of the fold. Sampling is what let that through, so replicate the
    # generator's arithmetic in Python and prove EVERY uid in the plausible range, then
    # cross-check a spread of them against the real script.
    def expected_offset(uid: int) -> int:
        offset = (uid - 1000) * 100
        return offset if offset <= 900 else 10000 + ((uid - 1000) % 147) * 100

    # A LISTENING port must also stay out of the kernel's ephemeral range, or the bind
    # races the kernel's own outgoing connections and fails intermittently with
    # EADDRINUSE. Read the running kernel's range where there is one; fall back to the
    # standard default so a container build host still enforces the rule.
    ephemeral_lo, ephemeral_hi = 32768, 60999
    try:
        lo, hi = Path("/proc/sys/net/ipv4/ip_local_port_range").read_text().split()
        ephemeral_lo, ephemeral_hi = int(lo), int(hi)
    except (OSError, ValueError):
        pass

    for uid in range(1001, 6001):          # every account a real machine could have
        offset = expected_offset(uid)
        for name, base in BASE.items():
            value = base + offset
            if not (1024 < value < 65536):
                errors.append(f"uid {uid} would get {name}={value}, outside the usable port range "
                              f"(1024-65535) — that account's Mo AI could not bind at all")
                break
            if value == BASE[name]:
                errors.append(f"uid {uid} resolves {name}={value}, uid 1000's base port — fail-OPEN")
                break
            if ephemeral_lo <= value <= ephemeral_hi:
                errors.append(f"uid {uid} would listen on {name}={value}, inside the kernel's "
                              f"ephemeral range ({ephemeral_lo}-{ephemeral_hi}) — the bind races the "
                              f"kernel's own outgoing connections and fails intermittently with "
                              f"EADDRINUSE. Listening ports must stay below {ephemeral_lo}.")
                break
        else:
            continue
        break                              # one arithmetic failure is enough; report and stop

    # Now confirm the real script agrees with that arithmetic at a spread of uids,
    # including both ends of the fold (1399 is the one the first version got wrong).
    for uid in (1001, 1009, 1010, 1100, 1146, 1147, 1148, 1399, 2000, 5000):
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
            if value != BASE[name] + expected_offset(uid):
                errors.append(f"uid {uid} {name}={value} does not match the documented formula "
                              f"(expected {BASE[name] + expected_offset(uid)})")
        if len(set(ports.values())) != 3:
            errors.append(f"uid {uid} ports collide with each other: {ports}")

    # A system/dynamic user (uid < 1000) has no Mo AI session — emit nothing.
    if run_generator(999):
        errors.append("uid 999 (system user) must emit no Mo AI ports")

    # Giving each account its own port is worthless if something else writes the BASE port
    # into a config. moai-do's OpenCode provider hardcoded "http://127.0.0.1:8080/v1",
    # which pointed the SECOND tenant's coding agent at the FIRST tenant's gateway — the
    # one process holding the cloud API key, i.e. exactly the leak this generator prevents.
    # Anything that writes a gateway URL must read the injected port.
    for rel in ("system_files/usr/bin/moai-do",
                "system_files/usr/bin/moai",
                "system_files/usr/libexec/moai-openclaw-bootstrap"):
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        code = "\n".join(line for line in text.splitlines()
                         if not line.lstrip().startswith("#"))
        for hit in re.finditer(r"127\.0\.0\.1:(\d{4,5})", code):
            port = int(hit.group(1))
            if port in BASE.values():
                line_no = code[:hit.start()].count("\n") + 1
                errors.append(
                    f"{rel} (code line ~{line_no}) hardcodes 127.0.0.1:{port}, a BASE Mo AI port. "
                    f"On a machine with more than one account that address belongs to uid 1000, so "
                    f"this sends another tenant's traffic to uid 1000's service. Use the injected "
                    f"MOAI_*_PORT (e.g. ${{MOAI_GATEWAY_PORT:-8080}}).")

    if errors:
        print("GATE FAIL: 60-moai-ports does not fail closed.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: uid 1000 keeps the base ports; every other account gets unique non-base ports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
