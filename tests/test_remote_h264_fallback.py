#!/usr/bin/env python3
"""Gate: Mo PC Remote's "give up on H.264 and settle on JPEG" latch must actually fire.

WHY THIS EXISTS

On a host where H.264 cannot start — the documented case is the local LLM growing into
the VRAM the NVENC session was holding — the portal helper is supposed to blacklist the
encoder, fall back to JPEG, and keep the session alive. Three defects made that fallback
a no-op, so instead of settling once the picture froze for a full ~4s PREROLL timeout on
EVERY rebuild (any quality/resolution/fps change, a second viewer, each NVENC error):

  1. `if not pick_h264():`  — pick_h264() returns (name, props) on success and
     (None, None) when nothing is left. BOTH are non-empty tuples, so `not <tuple>` is
     ALWAYS False; the `state["want"] = "jpeg"` latch could never run. The emptiness test
     is `pick_h264()[0] is None`.

  2. `_h264_blacklist.add(name)` — the blacklist was refactored from a set to a dict
     {factory: monotonic_ms}. `.add()` is a set method; on a dict it raises AttributeError.

  3. blacklisting by `msg.src.get_name()` — that is the element INSTANCE name, always
     "enc" (the pipeline builds the encoder as name=enc). The blacklist is keyed by
     FACTORY name (nvh264enc/…), so the failing encoder was never sin-binned and the next
     rebuild re-selected it. The factory name comes from get_factory().get_name().

Per the two existing portal gates, this reads the CODE with comments stripped, so the
prose above cannot satisfy it.
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

    # 1. The always-False latch must be gone, and the real emptiness test present at BOTH sites.
    if re.search(r"if\s+not\s+pick_h264\(\)\s*:", code):
        errors.append("`if not pick_h264():` is back — pick_h264() returns a 2-tuple that is always "
                      "truthy, so the JPEG fallback latch never fires. Test `pick_h264()[0] is None`.")
    empties = len(re.findall(r"pick_h264\(\)\[0\]\s+is\s+None", code))
    if empties < 2:
        errors.append(f"expected the emptiness test `pick_h264()[0] is None` at BOTH fallback sites "
                      f"(mid-stream and PREROLL), found {empties}.")

    # 2. The set method on a dict must be gone.
    if re.search(r"_h264_blacklist\.add\(", code):
        errors.append("`_h264_blacklist.add(` is back — the blacklist is a dict now; .add() raises "
                      "AttributeError. Assign `_h264_blacklist[factory] = ...`.")

    # 3. The mid-stream fallback must blacklist by FACTORY name (get_factory), not the instance name.
    #    Find the h264-failed-mid-stream block and check it reads the factory.
    block = re.search(r'state\["codec"\]\s*==\s*"h264".*?GLib\.idle_add\(rebuild\)', code, re.S)
    if not block:
        errors.append("could not locate the mid-stream H.264 failure handler to check its blacklist key.")
    else:
        body = block.group(0)
        if "get_factory()" not in body:
            errors.append("the mid-stream H.264 failure handler does not read get_factory() — "
                          "blacklisting by msg.src.get_name() records the instance name 'enc', so the "
                          "failing encoder is never sin-binned.")
        if re.search(r"_h264_blacklist\[[^\]]*factory[^\]]*\]\s*=", body) is None and \
           "_h264_blacklist[factory]" not in body:
            errors.append("the mid-stream handler does not write _h264_blacklist[factory] = <ts>.")

    if errors:
        print("GATE FAIL: the H.264 -> JPEG fallback would not work.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: the JPEG fallback latch fires (pick_h264()[0] is None) and the encoder is "
          "blacklisted by factory name.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
