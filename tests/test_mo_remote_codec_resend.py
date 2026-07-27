#!/usr/bin/env python3
"""Gate the one thing that turns a fast screen into a slow one without saying so.

Mo PC Remote's capture helper is a separate process, and it is restarted whenever it
dies — a portal input injection hitting a dead D-Bus destination is enough. A FRESH
HELPER ALWAYS STARTS ON JPEG. So every piece of state the agent wants it to have must
be re-pushed to the new one, not merely "changed".

`streaming` already worked that way. The codec did not: ScreenCapture told the helper
only about a codec CHANGE, so after a restart the new helper sat on jpeg while the agent
still believed it had asked for h264, nothing had changed, nothing was re-sent, and the
viewer spent the rest of the session on whole-picture frames. Measured on the cloud
server: 346 KB frames and a round trip that went from 32 ms to 2.7 SECONDS, with no error
logged anywhere.

The failure is invisible by construction — the stream keeps working, it just gets ten
times more expensive — so it needs a gate rather than a reader's attention.

Per AGENTS.md the assertions read the CODE with comments stripped.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = "moremote/agent-linux/PortalBridge.cs"
CAPTURE = "moremote/agent-linux/ScreenCapture.cs"

errors: list[str] = []


def code_of(rel: str) -> str:
    path = ROOT / rel
    if not path.is_file():
        errors.append(f"{rel}: missing")
        return ""
    out, in_block = [], False
    for line in path.read_text().splitlines():
        s = line.strip()
        if in_block:
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*"):
            in_block = "*/" not in s
            continue
        if s.startswith("//") or s.startswith("///"):
            continue
        out.append(line)
    return "\n".join(out)


bridge = code_of(BRIDGE)
capture = code_of(CAPTURE)

if bridge:
    # The bridge owns the codec, the way it already owns `streaming`: remembered, and
    # pushed against the generation of the helper it was pushed to.
    if "SetCodec" not in bridge:
        errors.append(
            f"{BRIDGE}: no SetCodec — the codec must be owned here, where a helper "
            "restart can re-push it, not decided by the caller"
        )
    if "_codecGeneration" not in bridge:
        errors.append(
            f"{BRIDGE}: the codec is not tracked per helper generation, so a plain "
            "re-call is swallowed by the idempotence check (this is exactly how "
            "`streaming` was fixed)"
        )

    # The re-push must actually happen where a new helper announces itself.
    ready = re.search(r'case "ready":(.*?)break;', bridge, re.S)
    if not ready:
        errors.append(f"{BRIDGE}: no `ready` handler found")
    else:
        body = ready.group(1)
        if "codec" not in body:
            errors.append(
                f"{BRIDGE}: the `ready` handler re-pushes streaming but not the codec — "
                "a restarted helper stays on JPEG for the rest of the session"
            )

if capture:
    # Deciding "has it changed?" on this side is precisely what hid the restart.
    if "_wantCodec" in capture:
        errors.append(
            f"{CAPTURE}: still keeps its own last-sent codec. That check cannot see a "
            "helper restart, so it suppresses the one message that would fix it"
        )
    if "SetCodec" not in capture:
        errors.append(f"{CAPTURE}: must ask the bridge via SetCodec")


if errors:
    print("FAIL: Mo PC Remote codec re-send gate")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("OK: a restarted capture helper is told the codec again, so H.264 survives it")
