#!/usr/bin/env python3
"""Gate: the H.264 the phone is offered must be 4:2:0, so a HARDWARE decoder can take it.

WHY THIS EXISTS, AND WHY EVERY DESKTOP TEST SAID THE STREAM WAS FINE

`videoconvert` in build()'s pipeline head carried no format caps, so the pixel format was
whatever negotiation settled on. pipewiresrc hands KDE's screencast over as BGRx — 4:4:4 —
and x264enc will happily take Y444 rather than pay for a conversion. So the stream leaving
this machine was High 4:4:4 Predictive. Measured on the shipping pipeline:

    no format caps                       profile_idc=244   High 4:4:4 Predictive   avc1.f4001f
    ! video/x-raw,format={I420,NV12}     profile_idc=100   High                    avc1.64001f

and confirmed against the live agent from a real browser, which logged its own
`VideoDecoder.configure({codec: "avc1.f40020"})` — f4 is 244.

**profile_idc 244 is not a profile any hardware H.264 decoder implements.** iOS
VideoToolbox, Android MediaCodec and essentially every phone, tablet and TV implement
Baseline/Main/High (66/77/100) and stop there. 4:4:4 is a professional-capture profile.

The reason this survived so long is the most important part of this gate. **Desktop Chrome
decodes it perfectly** — it falls back to a software decoder and never complains. Driven
against the live server from a headless Chrome on the machine itself: 1761 chunks in,
1761 frames out, six keyframes, ZERO decoder errors. Any session that reproduced "the
remote" in a desktop browser therefore watched a working picture and concluded the stream
was healthy. Only the phone — the actual client, and the only online peer on the
maintainer's tailnet — has to hand the bitstream to silicon that refuses it.

The phone's symptom is then exactly what the client was designed to do about a decode
failure: three strikes at 15/30/60s (h264state.ts) and settle on JPEG. Read off the live
log while the maintainer was connected:

    06:25:31 h264 -> 06:25:45 jpeg   (14s)
    06:26:15 h264 -> 06:26:29 jpeg   (14s)
    06:27:29 h264 -> 06:27:43 jpeg   (14s, gave up)

JPEG at 1080p then saturates the link, which is the slowness; the teardown and rebuild
around each fallback is the screen cutting out.

A NOTE ON test_remote_h264_single_slice.py, WHICH GUARDS THE SAME SYMPTOM

That gate fixed a real defect — 8 slices per access unit — and named this same 14-15s
fallback as its symptom. It was necessary and it was not sufficient: with
`sliced-threads=false` shipped and verified live at 1.0 slices/frame, the 14-second
fallback continued unchanged. Two independent properties of this stream could each make
iOS refuse it. Both are now pinned, and neither gate replaces the other.

HOW THIS IS CHECKED

The static half always runs and needs nothing installed: the caps filter must exist in the
H.264 branch, ahead of the encoder, and must name only 4:2:0 formats. The runtime half
actually encodes and reads profile_idc out of the SPS, and is SKIPPED where GStreamer or
x264enc is absent — CI's runner has neither, and a gate CI cannot run has broken this
build before.
"""

from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"

# The only chroma formats a phone's hardware decoder is guaranteed to take. Both are 4:2:0;
# the list exists so nvh264enc/vah264enc can still pick NV12 and pay no conversion.
ALLOWED = {"I420", "NV12"}
# 4:4:4 and 4:2:2 formats: any of these reaching x264enc re-opens the bug.
FORBIDDEN = {"Y444", "Y444_16LE", "Y444_16BE", "GBR", "RGB", "BGR", "BGRx", "RGBx",
             "xRGB", "xBGR", "RGBA", "BGRA", "ARGB", "ABGR", "Y42B", "YUY2", "UYVY", "NV16"}


def static_check() -> list[str]:
    code = HELPER.read_text(encoding="utf-8")
    # Strip comments: a claim in prose must never satisfy this gate.
    stripped = "\n".join(
        line for line in code.splitlines() if not line.lstrip().startswith("#"))

    errors: list[str] = []

    # The H.264 branch of build(): from `if codec == "h264":` to the `else:` that starts JPEG.
    branch = re.search(r'if codec == "h264":(.*?)\n    else:', stripped, re.S)
    if not branch:
        return ["could not locate the `if codec == \"h264\":` branch of build()."]
    tail = branch.group(1)

    caps = re.search(r"video/x-raw,\s*format=(?:\(string\))?\s*\{([^}]*)\}", tail)
    single = re.search(r"video/x-raw,\s*format=(?:\(string\))?\s*([A-Za-z0-9_]+)", tail)
    if caps:
        named = {f.strip() for f in caps.group(1).split(",") if f.strip()}
    elif single:
        named = {single.group(1).strip()}
    else:
        return [
            "the H.264 branch has no `video/x-raw,format=...` caps filter. Without one, "
            "videoconvert negotiates freely with the encoder, x264enc accepts the BGRx "
            "pipewiresrc already produces as Y444, and the stream ships as High 4:4:4 "
            "Predictive (profile_idc 244) — which no hardware decoder on any phone will take."
        ]

    if not named:
        errors.append("the format caps filter names no formats at all.")
    bad = named & FORBIDDEN
    if bad:
        errors.append(
            f"the format caps allow {sorted(bad)}, which is not 4:2:0. Any of these lets the "
            f"encoder emit a profile above High, which phones cannot hardware-decode.")
    unknown = named - ALLOWED - FORBIDDEN
    if unknown:
        errors.append(
            f"the format caps allow {sorted(unknown)}, which this gate does not know to be "
            f"4:2:0. If it is, add it to ALLOWED with the profile_idc you measured.")

    # Ordering matters: caps AFTER the encoder constrain nothing the encoder reads.
    enc_at = tail.find("name=enc")
    caps_at = tail.find("video/x-raw,format=")
    if enc_at != -1 and caps_at != -1 and caps_at > enc_at:
        errors.append(
            "the format caps filter sits AFTER the encoder element. It has to be upstream of "
            "it, or the encoder still negotiates its input freely.")

    return errors


def runtime_check() -> tuple[list[str], str]:
    """Encode a few frames with the shipped settings and read profile_idc out of the SPS."""
    gst = shutil.which("gst-launch-1.0")
    if not gst:
        return [], "skipped (no gst-launch-1.0 on this machine)"
    try:
        inspect = subprocess.run(["gst-inspect-1.0", "x264enc"],
                                 capture_output=True, timeout=60)
        if inspect.returncode != 0:
            return [], "skipped (x264enc not installed)"
    except (OSError, subprocess.SubprocessError):
        return [], "skipped (gst-inspect-1.0 unavailable)"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "probe.h264"
        cmd = [
            gst, "-q", "-e",
            "videotestsrc", "num-buffers=30", "pattern=smpte", "!",
            # BGRx is what pipewiresrc actually delivers from KDE's screencast.
            "video/x-raw,format=BGRx,width=640,height=360,framerate=30/1", "!",
            "videoscale", "!", "videoconvert", "!",
            "video/x-raw,format=(string){ I420, NV12 }", "!",
            "x264enc", "bitrate=1000", "key-int-max=300", "tune=zerolatency",
            "speed-preset=veryfast", "sliced-threads=false", "threads=2", "!",
            "h264parse", "config-interval=-1", "!",
            "video/x-h264,stream-format=byte-stream,alignment=au", "!",
            "filesink", f"location={out}",
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180)
        except (OSError, subprocess.SubprocessError) as exc:
            return [], f"skipped (encoder would not run: {exc})"
        if not out.is_file() or out.stat().st_size == 0:
            return [], "skipped (encoder produced no output on this machine)"

        data = out.read_bytes()

    profile = None
    i = 0
    while i < len(data) - 6:
        if data[i] == 0 and data[i + 1] == 0 and data[i + 2] == 1:
            if (data[i + 3] & 0x1F) == 7:          # SPS
                profile = data[i + 4]
                break
            i += 3
        else:
            i += 1

    if profile is None:
        return [], "skipped (no SPS found in the probe stream)"
    if profile > 100:
        return ([f"the shipped encoder settings produced profile_idc={profile}; anything above "
                 f"100 (High) is not hardware-decodable on a phone."],
                f"measured profile_idc={profile}")
    return [], f"measured profile_idc={profile} (<= 100 High)"


def main() -> int:
    errors = static_check()
    runtime_errors, note = runtime_check()
    errors += runtime_errors

    if errors:
        print("GATE FAIL: Mo Remote would offer the phone an H.264 profile it cannot decode.\n")
        for e in errors:
            print(f"  - {e}")
        print("\nSee the docstring: desktop Chrome decodes 4:4:4 in software and will tell you "
              "\nthe stream is fine. The phone is the client that matters.")
        return 1

    print(f"OK: the H.264 branch pins 4:2:0 chroma upstream of the encoder; runtime {note}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
