#!/usr/bin/env python3
"""Gate: Mo PC Remote must fall back off a dead H.264 encoder — and must RECOVER afterwards.

WHY THIS EXISTS

On a host where H.264 cannot start — the documented case is the local LLM growing into the
VRAM the NVENC session was holding — the portal helper blacklists the failing encoder and
carries on over JPEG, then retries once the blacklist entry expires (BLACKLIST_TTL_MS, 90 s)
and free_gpu_and_retry() has asked for the card back. Both halves matter: falling back keeps
the session alive, and expiring keeps a one-minute condition from costing the session an hour.

Four ways that has been broken, each pinned below:

  1. `_h264_blacklist.add(name)` — the blacklist was refactored from a set to a dict
     {factory_name: monotonic_ms}. `.add()` is a set method; on a dict it raises
     AttributeError, inside the GStreamer bus handler.

  2. Blacklisting `msg.src.get_name()` — that is the element INSTANCE name, always "enc"
     (the pipeline builds the encoder as name=enc). The blacklist is keyed by FACTORY name
     (nvh264enc/…), so the failing encoder was never sin-binned and the next rebuild
     re-selected it. The factory name is get_factory().get_name().

  3. Keying the blacklist by the factory OBJECT rather than its NAME. `_blacklisted(name)`
     looks the key up by string, so an object key never matches: the entry is written, the
     lookup always misses, and the encoder is re-selected exactly as if nothing was recorded.
     This is the near-miss a spelling-only check cannot tell from a fix.

  4. A PERMANENT `state["want"] = "jpeg"` latch. It looks like the fallback and is a
     regression: `want` returns to "h264" only when the AGENT sends a codec message, and the
     agent sends one only when ITS arbitration changes — so one failure pins the session to
     JPEG for its whole life, overriding the TTL and defeating free_gpu_and_retry(). The
     helper's own comment says it: "a permanent JPEG latch is far too expensive a way to find
     out." The blacklist is the fallback, and it expires; nothing else may latch.

  (A fifth, historical: `if not pick_h264():` — both returns are non-empty tuples, so it is
  always False. It is refused below so the always-False idiom cannot come back.)

Per the two existing portal gates, this reads the CODE with comments stripped, so the prose
above cannot satisfy it.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def strip_comments(src: str) -> str:
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )


def main() -> int:
    if not HELPER.is_file():
        print(f"GATE FAIL: {HELPER.relative_to(ROOT)} is missing.")
        return 1

    code = strip_comments(HELPER.read_text(encoding="utf-8"))
    errors: list[str] = []

    # 1. The set method on a dict.
    if re.search(r"_h264_blacklist\.add\(", code):
        errors.append("`_h264_blacklist.add(` is back — the blacklist is a dict; .add() raises "
                      "AttributeError inside the bus handler. Assign _h264_blacklist[<name>] = ts.")

    # 2/3. Every blacklist WRITE must be keyed by a factory NAME (a string), never by the element
    #      instance name and never by the factory object. _blacklisted() looks up by string, so an
    #      object key is written and never matched — a fix-shaped no-op.
    writes = re.findall(r"_h264_blacklist\[([^\]]+)\]\s*=", code)
    if not writes:
        errors.append("nothing writes to _h264_blacklist — a failing encoder is never sin-binned, "
                      "so the next rebuild re-selects it and pays the PREROLL timeout again.")
    for key in writes:
        key = key.strip()
        if "get_factory()" in key and "get_name()" not in key:
            errors.append(f"_h264_blacklist[{key}] keys the blacklist by the factory OBJECT. "
                          f"_blacklisted() looks keys up by string, so this entry can never match "
                          f"— write get_factory().get_name().")
        if re.fullmatch(r"(msg\.)?src\.get_name\(\)", key):
            errors.append(f"_h264_blacklist[{key}] keys the blacklist by the element INSTANCE name "
                          f"(always 'enc'), not the factory name — nothing is ever sin-binned.")

    # The mid-stream handler specifically must resolve the factory.
    block = re.search(r'state\["codec"\]\s*==\s*"h264".*?GLib\.idle_add\(rebuild\)', code, re.S)
    if not block:
        errors.append("could not locate the mid-stream H.264 failure handler.")
    elif "get_factory()" not in block.group(0):
        errors.append("the mid-stream H.264 failure handler does not read get_factory() — "
                      "blacklisting by msg.src.get_name() records 'enc' and sin-bins nothing.")

    # 4. No permanent JPEG latch anywhere in the failure paths.
    latch = re.findall(r'state\["want"\]\s*=\s*"jpeg"', code)
    if latch:
        errors.append(f"{len(latch)} permanent `state[\"want\"] = \"jpeg\"` latch(es) present. "
                      f"`want` only returns to h264 when the AGENT sends a codec message, so this "
                      f"pins the session to JPEG for its whole life, overriding BLACKLIST_TTL_MS "
                      f"and defeating free_gpu_and_retry(). The expiring blacklist is the fallback.")

    # 5. The always-False idiom must not return.
    if re.search(r"if\s+not\s+pick_h264\(\)\s*:", code):
        errors.append("`if not pick_h264():` is back — both returns are non-empty tuples, so it is "
                      "always False. Test `pick_h264()[0] is None` if emptiness is needed.")

    # The recovery half must still be wired: the TTL and the GPU reclaim.
    # Defined AND compared: a constant that exists but is never used against the recorded
    # timestamp is not an expiry, and _blacklisted() would then be a permanent sin bin.
    if not re.search(r"^BLACKLIST_TTL_MS\s*=", code, re.M):
        errors.append("BLACKLIST_TTL_MS is no longer defined — without an expiry a transient VRAM "
                      "shortage costs the session H.264 for ever.")
    if not re.search(r"def _blacklisted\([^)]*\):.*?BLACKLIST_TTL_MS", code, re.S):
        errors.append("_blacklisted() no longer compares against BLACKLIST_TTL_MS — the sin bin "
                      "never expires, so a one-minute condition costs the session an hour.")
    if "free_gpu_and_retry()" not in code:
        errors.append("free_gpu_and_retry() is no longer called — the commonest cause of a refused "
                      "hardware encoder here is the local brain holding the card.")

    if errors:
        print("GATE FAIL: the H.264 fallback/recovery path is broken.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: the encoder is blacklisted by factory NAME, the blacklist expires, "
          "free_gpu_and_retry is wired, and nothing pins the session to JPEG.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
