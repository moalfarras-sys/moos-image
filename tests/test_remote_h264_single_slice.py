#!/usr/bin/env python3
"""Gate: the software H.264 encoder must emit ONE slice per frame, with a latency budget.

WHY THIS EXISTS

`tune=zerolatency` turns on x264's SLICED THREADS, which splits every frame into one slice
per thread so a slice can leave the encoder before the frame is finished. On an 8-core box
that is 8 slices in every access unit. Parsed straight out of the shipping encoder's own
output at the live 1836x1032:

    sliced-threads=true   AUs=200  P-slices=1568  IDR-slices=32  -> 8.0 slices/frame
    sliced-threads=false  AUs=200  P-slices=196   IDR-slices=4   -> 1.0 slices/frame

Multi-slice H.264 is perfectly legal and Chrome decodes it happily. It is also the single
most common thing an iOS WebCodecs VideoDecoder refuses — and iOS is not a hypothetical
client for MoOS Cloud: the only online peer on the maintainer's tailnet is an iPhone.

The symptom matched exactly. The room held H.264 for 14-15 seconds and then fell to JPEG,
every single time, which is the periodic IDR interval at that desktop's real damage-driven
frame rate — and the IDR is precisely the access unit carrying 8 IDR slices. Everything
else was healthy: all SPS byte-identical (so no renegotiation), an IDR only 2.0x the size
of a P-frame (so no bandwidth spike), and zero backlog drops in the agent's log. Each
fallback costs a full GStreamer teardown and rebuild, which the person watching
experiences as the screen cutting out, every fifteen seconds, for as long as they watch.

CORRECTION, 2026-08-16: THIS WAS NECESSARY AND IT WAS NOT SUFFICIENT.

The paragraph above reads as a solved case, and the fix it describes is real and shipped —
verified live at 1.0 slices per frame. The 14-second fallback carried on unchanged anyway.
A second, independent property of the same stream could also make iOS refuse it: the
pipeline had no format caps, so the encoder took pipewiresrc's BGRx as 4:4:4 and shipped
High 4:4:4 Predictive, profile_idc 244, which no phone decodes in hardware. That is gated
separately in test_remote_h264_chroma.py.

Two lessons worth more than either fix. First, a symptom matching a cause is not proof it
is the only cause — this file's confidence was the reason nobody looked further for a day.
Second, everything in the paragraph above was measured in a DESKTOP browser, which decodes
both defects in software without complaint. Neither could be reproduced where it was being
tested.

AND WHY `threads` IS PINNED TOO

Without sliced threads x264 falls back to FRAME threading, which delays output by
(threads - 1) frames — the very latency `zerolatency` exists to avoid. So the thread count
stops being "as many as you have" and becomes a latency budget. Measured here, 1836x1032,
300 frames of desktop-like content:

    sliced-threads=true              8.15s  ->  36.8 fps   8 slices, 0 frames of delay
    sliced-threads=false threads=1  13.87s  ->  21.6 fps   1 slice,  0 frames  (too slow)
    sliced-threads=false threads=2   7.40s  ->  40.5 fps   1 slice,  1 frame   <- shipped

One slice per frame is 10% FASTER than what shipped and costs a single frame (~33ms at
30fps), against the ~200ms rebuild a codec fallback costs. Raising `threads` silently
spends the interactive latency this product is judged on, so it is gated rather than left
to whoever next tunes the encoder.

A NOTE ON HOW THIS IS CHECKED

A property x264enc does not have is not a warning in Gst.parse_launch — it is a PARSE
FAILURE, which build() reads as "this encoder will not start", blacklists, and falls all
the way down to JPEG. That trap has already cost this file hardware encoding twice. So
this gate asserts the property names as well as their values; if GStreamer ever renames
them, the gate fires here instead of silently costing every viewer 18x the bandwidth.
"""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def main() -> int:
    code = HELPER.read_text(encoding="utf-8")
    # Strip comments so a claim in prose can never satisfy this gate.
    stripped = "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith("#"))

    errors: list[str] = []

    block = re.search(r"H264_ENCODERS\s*=\s*\[(.*?)^\]", stripped, re.S | re.M)
    if not block:
        errors.append("could not locate the H264_ENCODERS table.")
        print("GATE FAIL:\n  - " + errors[0])
        return 1

    table = block.group(1)
    x264 = re.search(r'\("x264enc",\s*(.*?)\),\s*(?:#|\()', table + "(", re.S)
    if not x264:
        errors.append("could not locate the x264enc entry in H264_ENCODERS.")
    else:
        props = x264.group(1)
        if "sliced-threads=false" not in props.replace('"', "").replace("\n", " "):
            errors.append(
                "x264enc does not set sliced-threads=false. tune=zerolatency turns sliced "
                "threads ON, which emits one slice per thread (8 on this hardware) and is "
                "the most common reason an iOS WebCodecs decoder rejects the stream.")
        flat = props.replace('"', "").replace("\n", " ")
        m = re.search(r"threads=(\d+)", flat)
        if not m:
            errors.append(
                "x264enc does not pin `threads`. Without sliced threads, x264 uses frame "
                "threading and delays output by (threads - 1) frames, so an unpinned thread "
                "count silently spends interactive latency.")
        elif int(m.group(1)) > 2:
            errors.append(
                f"x264enc asks for threads={m.group(1)}. Every thread beyond the first is "
                f"another frame of latency the user feels on every mouse move; 2 measured "
                f"40.5 fps at 1836x1032, which is already faster than the 8-slice config.")
        # zerolatency must survive: it is what kills B-frames, and the client's decoder
        # assumes presentation order equals coding order.
        if "tune=zerolatency" not in flat:
            errors.append("x264enc lost tune=zerolatency; the client decodes assuming no B-frames.")

    if errors:
        print("GATE FAIL: the software H.264 encoder would emit a stream iOS may refuse.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: x264enc emits one slice per frame (sliced-threads=false) with threads pinned "
          "to a latency budget, and zerolatency is intact.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
