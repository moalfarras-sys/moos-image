#!/usr/bin/env python3
"""The rig's consumer: what Mo PC Remote's helper does with a ScreenCast node, minus the network.

The same chain to openh264, counting what the compositor DELIVERS and what reaches the encoder.
RIG_RATE=helper installs the repository helper's own FramePacer and pace_frame — lifted out of
moremote/agent-linux/mo-remote-portal.py, not copied — so the number printed is for what ships."""
import ast
import os
import sys
import time
from pathlib import Path

import gi
gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

HELPER = Path(__file__).resolve().parents[3] / "moremote/agent-linux/mo-remote-portal.py"
RATE = os.environ.get("RIG_RATE", "helper")
FPS = int(os.environ.get("RIG_FPS", "30"))
LIMITERS = {
    "maxrate": f"! videorate drop-only=true max-rate={FPS} name=rate ",
    "helper": f"! videorate drop-only=true max-rate={FPS} name=rate ",
    "caps": f"! videorate drop-only=true name=rate ! video/x-raw,framerate={FPS}/1 ",
    "none": "",
}

Gst.init(None)
node, seconds = sys.argv[1], float(sys.argv[2])
cap = os.environ.get("RIG_MAX_FRAMERATE", "")
asked = f"! video/x-raw,max-framerate={cap}/1 " if cap else ""
out_w, out_h = os.environ.get("RIG_OUT", "1920x1080").split("x")
pipeline = Gst.parse_launch(
    f"pipewiresrc path={node} do-timestamp=true keepalive-time=1000 name=src {asked}"
    "! queue name=capq leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0 "
    + LIMITERS[RATE] +
    f"! videoscale method=bilinear ! video/x-raw,width={out_w},height={out_h} ! videoconvert "
    "! video/x-raw,format=(string){ I420, NV12 } "
    "! openh264enc bitrate=4000000 max-bitrate=6000000 gop-size=300 complexity=low "
    "rate-control=bitrate usage-type=screen ! fakesink name=sink sync=false")

if RATE == "helper":
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    shipped = {"time": time, "Gst": Gst, "state": {"fps": FPS}}
    for name in ("FramePacer", "pace_frame"):
        item = next(n for n in tree.body if getattr(n, "name", None) == name)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[item], type_ignores=[])),
                     str(HELPER), "exec"), shipped)
    shipped["frame_pacer"] = shipped["FramePacer"]()
    pipeline.get_by_name("rate").get_static_pad("sink").add_probe(
        Gst.PadProbeType.BUFFER, shipped["pace_frame"])

counts = {"delivered": 0, "encoded": 0}


def counter(key):
    def probe(_pad, _info):
        counts[key] += 1
        return Gst.PadProbeReturn.OK
    return probe


pipeline.get_by_name("src").get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, counter("delivered"))
pipeline.get_by_name("sink").get_static_pad("sink").add_probe(Gst.PadProbeType.BUFFER, counter("encoded"))
pipeline.set_state(Gst.State.PLAYING)
ok, _state, _pending = pipeline.get_state(8 * Gst.SECOND)
caps = pipeline.get_by_name("src").get_static_pad("src").get_current_caps()
print("RIG consumer state", ok.value_nick, "| negotiated:", caps.to_string() if caps else None, flush=True)

loop = GLib.MainLoop()
start = {"t": 0.0, "d": 0, "e": 0}


def begin():
    start.update(t=time.monotonic(), d=counts["delivered"], e=counts["encoded"])
    print("RIG consumer measuring", flush=True)
    return False


def end():
    elapsed = time.monotonic() - start["t"]
    print(f"RIG frames delivered by the compositor: {(counts['delivered'] - start['d']) / elapsed:.1f}/s, "
          f"encoded: {(counts['encoded'] - start['e']) / elapsed:.1f}/s over {elapsed:.1f} s", flush=True)
    loop.quit()
    return False


GLib.timeout_add(2000, begin)                 # let the stream settle
GLib.timeout_add(int((2 + seconds) * 1000), end)
loop.run()
pipeline.set_state(Gst.State.NULL)
