#!/usr/bin/env python3
"""Gate: opening the remote must not make the picture flash three times.

WHAT THIS PREVENTS, MEASURED ON A REAL CONNECT

Every setting that changes the encode pipeline rebuilds it, and a client that has just connected
changes three of them in a row — because it cannot say them all at once. From the maintainer's
machine, one phone opening the remote:

    11:19:16  Video stream: 1920x1080     <- built as JPEG, before the phone had said anything
    11:19:16  Video codec: h264           <- rebuild: the phone declared WebCodecs H.264
    11:19:16  Video stream: 1920x1080
    11:19:18  Video stream: 960x540       <- rebuild: its quality preset finally arrived

Four builds in two seconds, for one viewer. Each costs ~200ms with no picture and a fresh IDR
after it, so opening the remote meant watching the screen appear, blank, appear, blank, appear.
That reads as a bad connection and is not one — the machine is doing it to itself.

It cannot be fixed by reordering the client. The codec declaration rides along with the auth
message, but the quality preset can only be sent after `hello` comes back, which is a round trip
later — 2ms on a LAN, ~400ms over a relayed cellular link. There is no fixed moment at which the
client has finished talking, which is the shape debouncing exists for.

TWO HALVES, AND THE SECOND ONE IS EASY TO LOSE

  1. rebuild() must coalesce. A burst becomes one build.
  2. the teardown path must NOT. `streaming` going false has to drop the pipeline synchronously:
     its entire purpose is to stop the compositor copying frames the instant the last viewer
     leaves, and 220ms of extra load on an idle machine is 220ms nobody asked for. A future edit
     that "simplifies" rebuild() by routing every path through the timer would silently undo the
     idle-cost work this file's neighbours exist to protect, and nothing would look broken.

Per AGENTS.md the assertions read the CODE with comments stripped.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def strip_comments(src: str) -> str:
    """Comments and docstrings describe intent; a gate must read what the code DOES."""
    src = re.sub(r'"""[\s\S]*?"""', '""', src)
    return "\n".join(re.sub(r"#.*$", "", line) for line in src.splitlines())


def main() -> int:
    if not HELPER.is_file():
        print(f"GATE FAIL: {HELPER.relative_to(ROOT)} is missing.")
        return 1

    code = strip_comments(HELPER.read_text(encoding="utf-8"))
    errors: list[str] = []

    # --- the body of rebuild(), which is where both halves live ---------------------------------
    m = re.search(r"^def rebuild\(\):\n([\s\S]*?)(?=^def )", code, re.M)
    if not m:
        print("GATE FAIL: no rebuild() in the helper — the gate cannot check what it cannot find.")
        return 1
    body = m.group(1)

    # 1. it must schedule rather than build.
    if "timeout_add" not in body:
        errors.append("rebuild() does not schedule a debounced build (no GLib.timeout_add).\n"
                      "        Every settings change would rebuild the pipeline immediately, so one\n"
                      "        connecting client makes the picture appear, blank and reappear 3-4 times.")
    # and it must cancel the pending one, or a burst becomes a BUILD PER MESSAGE, delayed.
    if "source_remove" not in body:
        errors.append("rebuild() never cancels a pending timer, so a burst of settings schedules a\n"
                      "        build per message instead of coalescing into one — the same number of\n"
                      "        rebuilds as before, just later.")

    # 2. the idle path must stay synchronous.
    if not re.search(r"if not state\[.streaming.\][\s\S]{0,200}?teardown\(\)", body):
        errors.append("rebuild() no longer tears the pipeline down synchronously when streaming goes\n"
                      "        false. Idle must cost nothing the moment the last viewer leaves —\n"
                      "        pipewiresrc keeps the ScreenCast stream active, so the COMPOSITOR pays\n"
                      "        for every frame until the pipeline is actually dropped.")
    # The teardown branch has to come BEFORE the timer, or it is dead code behind a debounce.
    if "timeout_add" in body and "teardown()" in body:
        if body.index("teardown()") > body.index("timeout_add"):
            errors.append("the teardown branch sits AFTER the debounce timer in rebuild(), so the idle\n"
                          "        path is reached only through the delay it is supposed to bypass.")

    # 3. the deferred build has to actually exist and be a one-shot.
    if "_rebuild_now" not in code:
        errors.append("no _rebuild_now(): rebuild() schedules something that is not defined.")
    else:
        nb = re.search(r"^def _rebuild_now\(\):\n([\s\S]*?)(?=^def )", code, re.M)
        if nb and "return True" in nb.group(1):
            errors.append("_rebuild_now() can return True, which makes the GLib timeout REPEAT — the\n"
                          "        pipeline would be rebuilt every debounce interval, for ever.")

    if errors:
        print("GATE FAIL: connecting to the remote would flash the picture, or idle would cost CPU.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: rebuild() coalesces a settings burst into one build; the idle teardown stays immediate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
