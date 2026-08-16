#!/usr/bin/env python3
"""Gate: moai-wake must survive a blocked or v6-only Telegram address.

WHY THIS EXISTS

moai-wake is the ONLY thing that can wake openclaw-gateway once openclaw-idle
has put it to sleep. If it cannot reach Telegram, the phone agent is silently
dead: messages arrive at Telegram, nothing ever reads them, and every surface
still reports healthy — `systemctl is-active moai-wake` says active, the unit
never fails, and the gateway is "correctly" asleep.

That is not hypothetical. Measured on the maintainer's own network:

    getaddrinfo("api.telegram.org") -> 149.154.166.110 AND 2001:67c:4e8:f004::9
    host has NO IPv6 default route  -> urlopen tried v6 first and died instantly
                                       with [Errno 101] Network is unreachable
    curl -4 149.154.166.110         -> no answer, 8s timeout
    curl -4 149.154.167.220 / .99   -> HTTP 302 in ~0.10s

Both halves of the default resolution were unusable while Telegram itself was
reachable on other addresses in its own range. OpenClaw's client already
retries an alternative API IP and stayed up; moai-wake used a bare urlopen,
had no such path, and logged "Network is unreachable" forever. It was masked
for months because an enabled WhatsApp channel pins the gateway awake, so the
wake path was never exercised — disabling WhatsApp exposed it immediately.

This gate is OFFLINE by construction: CI has no Telegram credentials and must
not depend on reaching a third party. It drives the real functions with the
socket layer stubbed.
"""

import importlib.util
import socket
import ssl
import sys
import urllib.error
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moai-wake"


def load_module():
    loader = SourceFileLoader("_moai_wake_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing.")
        return 1

    module = load_module()
    errors: list[str] = []

    # 1. Resolution must be IPv4-only. A host with no v6 route must never be
    #    handed an AAAA record to fail on.
    try:
        families = {info[0] for info in socket.getaddrinfo("localhost", 80)}
        if families - {socket.AF_INET}:
            errors.append(
                "getaddrinfo still returns non-IPv4 families "
                f"({families}); [Errno 101] can recur on a v6-less host")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"IPv4-only getaddrinfo raised {type(exc).__name__}: {exc}")

    # 2. The fallback list must be real, and must not carry the address that
    #    resolves inside Telegram's range but does not serve TLS on 443.
    ips = getattr(module, "TELEGRAM_FALLBACK_IPS", ())
    if not ips:
        errors.append("TELEGRAM_FALLBACK_IPS is empty — a blocked default address is fatal again")
    if "149.154.175.50" in ips:
        errors.append(
            "149.154.175.50 is in the fallback list; it answers with "
            "SSL: WRONG_VERSION_NUMBER and only wastes a round")

    # 3. A connection-level failure must ADVANCE to the next candidate.
    #    Every address fails except the last one in the order.
    attempts: list[object] = []

    def only_last_works(token, method, data, timeout, ip):
        attempts.append(ip)
        if len(attempts) < 1 + len(ips):        # default DNS + all but final IP
            raise OSError("simulated connection failure")
        return {"ok": True, "result": {"username": "bot"}}

    module._pinned_ip = None
    module._tg_via_ip = only_last_works
    try:
        result = module.tg_call("tok", "getMe", timeout=1)
        if not result.get("ok"):
            errors.append("tg_call returned a non-ok payload after failover")
        if len(attempts) < 2:
            errors.append(
                f"tg_call stopped after {len(attempts)} attempt(s); a blocked "
                "default address must fall through to the alternatives")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"tg_call did not survive connection failures: {type(exc).__name__}: {exc}")

    # 4. An HTTP error means Telegram ANSWERED. It must propagate unchanged so
    #    the caller's 409 (second poller) and 401 (bad token) handling works —
    #    retrying other IPs on a 409 would hammer Telegram for no reason.
    def always_http_error(token, method, data, timeout, ip):
        attempts.append(ip)
        raise urllib.error.HTTPError("u", 409, "Conflict", None, None)

    attempts.clear()
    module._pinned_ip = None
    module._tg_via_ip = always_http_error
    try:
        module.tg_call("tok", "getMe", timeout=1)
        errors.append("a 409 was swallowed; it must reach the caller")
    except urllib.error.HTTPError:
        if len(attempts) != 1:
            errors.append(
                f"a 409 was retried across {len(attempts)} addresses; "
                "Telegram answered, so there is nothing to fail over to")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"a 409 surfaced as {type(exc).__name__}, not HTTPError")

    # 5. Total failure must raise, never return None — a silent None would make
    #    the poll loop treat "no connectivity" as "no messages".
    def never_works(token, method, data, timeout, ip):
        raise OSError("down")

    module._pinned_ip = None
    module._tg_via_ip = never_works
    try:
        got = module.tg_call("tok", "getMe", timeout=1)
        errors.append(f"tg_call returned {got!r} with every address down; it must raise")
    except (OSError, ssl.SSLError, urllib.error.URLError):
        pass
    except Exception as exc:  # noqa: BLE001
        errors.append(f"unexpected failure type when all addresses are down: {type(exc).__name__}")

    if errors:
        for err in errors:
            print(f"GATE FAIL: {err}")
        return 1
    print("OK: moai-wake resolves IPv4-only, fails over past a blocked address, "
          "and still surfaces HTTP errors to the caller.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
