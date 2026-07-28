#!/usr/bin/env python3
"""Gate: the picture ceiling, and the compatibility rule that makes raising it safe.

WHY THE CEILING MOVED

1920 was never a hardware limit — it was a constant. On a 3840-wide desktop it threw away half the
linear detail before the encoder ever saw it, which is why no bitrate ever made the text crisp and
why "the picture is not sharp" could not be tuned away. Measured on an RTX 2080 SUPER with the
worst-case content there is (videotestsrc pattern=snow; real desktops compress far better):

    1920x1080@30   30.3 fps        2560x1440@30   30.3 fps
    1920x1080@60   60.3 fps        2560x1440@60   60.3 fps
    3840x2160@30   30.3 fps        3840x2160@60   31.9 fps   <- the encoder runs out here

So 2560 is where the hardware stops being the limit at a frame rate worth having.

THE RULE THAT MAKES IT SAFE, AND WHY IT IS EASY TO DELETE BY ACCIDENT

`scale` is a FRACTION of the target width. Raise the target and every fraction silently means
something new: a service-worker-cached PWA asking for its "High" (scale 1.0) would jump from 1920
to 2560 — 1.8x the pixels and the bandwidth — without any human choosing it, quite possibly on
cellular. This agent already has a "legacy cached controller" path, so that population is real.

The higher ceiling is therefore something a client OPTS INTO by naming pixels (`width`). A client
that only speaks fractions must keep LEGACY_MAX_WIDTH and get byte-for-byte what it got before.
Anyone tidying target_size() into "one ceiling, one formula" removes that protection, and nothing
visible breaks on the machine they are testing on — only on somebody else's cached phone.

The other half is the room: two viewers share one pipeline, so width has to be arbitrated like
scale and quality. A width of 0 means "no opinion", and letting a no-opinion vote win the minimum
would pin the whole room to the fraction path the moment one old client joined.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"
CAPTURE = ROOT / "moremote/agent-linux/ScreenCapture.cs"
SESSION = ROOT / "moremote/agent/Web/StreamSession.cs"
TYPES = ROOT / "moremote/controller/src/types.ts"


def strip_py_comments(src: str) -> str:
    src = re.sub(r'"""[\s\S]*?"""', '""', src)
    return "\n".join(re.sub(r"#.*$", "", ln) for ln in src.splitlines())


def main() -> int:
    for f in (HELPER, CAPTURE, SESSION, TYPES):
        if not f.is_file():
            print(f"GATE FAIL: {f.relative_to(ROOT)} is missing.")
            return 1

    helper = strip_py_comments(HELPER.read_text(encoding="utf-8"))
    capture = CAPTURE.read_text(encoding="utf-8")
    session = SESSION.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")
    errors: list[str] = []

    # --- 1. both ceilings exist, and the legacy one is the smaller ------------------------------
    m_new = re.search(r"^MAX_WIDTH\s*=\s*(\d+)", helper, re.M)
    m_old = re.search(r"^LEGACY_MAX_WIDTH\s*=\s*(\d+)", helper, re.M)
    if not m_new:
        errors.append("the helper has no MAX_WIDTH.")
    if not m_old:
        errors.append("the helper has no LEGACY_MAX_WIDTH, so a client that only sends `scale` is\n"
                      "        measured against the NEW ceiling — a cached PWA's 'High' silently becomes\n"
                      "        1.8x the pixels and the bandwidth it asked for, possibly on cellular.")
    if m_new and m_old and int(m_old.group(1)) > int(m_new.group(1)):
        errors.append(f"LEGACY_MAX_WIDTH ({m_old.group(1)}) is above MAX_WIDTH ({m_new.group(1)}) — the\n"
                      f"        compatibility path would be the GENEROUS one, which is backwards.")

    # --- 2. target_size must actually use both --------------------------------------------------
    ts = re.search(r"^def target_size\(\):\n([\s\S]*?)(?=^def )", helper, re.M)
    if not ts:
        errors.append("no target_size() in the helper.")
    else:
        body = ts.group(1)
        if "LEGACY_MAX_WIDTH" not in body:
            errors.append("target_size() never consults LEGACY_MAX_WIDTH, so the `scale` path is being\n"
                          "        measured against the raised ceiling. That changes what every fraction an\n"
                          "        already-cached client sends means, with nobody choosing it.")
        if not re.search(r"state\.get\(\"width\"\)|state\[.width.\]", body):
            errors.append("target_size() ignores the pixel width, so a preset cannot mean a resolution\n"
                          "        and the raised ceiling is unreachable.")

    # --- 3. the room must arbitrate width, and 0 must not win ------------------------------------
    if "_wantWidth" not in capture:
        errors.append("ScreenCapture does not arbitrate width across viewers. One pipeline serves the\n"
                      "        whole room, so an un-arbitrated width is two clients fighting over it.")
    elif not re.search(r"width\s*>\s*0\s*&&\s*width\s*<\s*w", capture):
        errors.append("the width arbitration counts 'no opinion' (0) as a vote. min() would then pin the\n"
                      "        room to 0 — the fraction path — the moment one older client joined, undoing\n"
                      "        the pixel request of every current client in the room.")

    # --- 4. fps ceiling ---------------------------------------------------------------------------
    if re.search(r"Math\.Clamp\(\s*_fps\s*,\s*1\s*,\s*30\s*\)", session) or \
       re.search(r'TryGetInt\(root, "fps", out var f\)\) \{ _fps = Math\.Clamp\(f, 1, 30\)', session):
        errors.append("the agent still clamps fps to 30. Measured on this hardware, 1920x1080@60 and\n"
                      "        2560x1440@60 both hold 60.3fps, and a still desktop costs nothing at either\n"
                      "        setting because capture is damage-driven.")

    # --- 5. the client's presets must be absolute, and auto must not climb into the top one -------
    if "scale:" in types and "QUALITY_PRESETS" in types and "width:" not in types:
        errors.append("the client presets are still fractions. The same preset then means a different\n"
                      "        resolution on every machine, and the client cannot discover which it got —\n"
                      "        `hello` reports the LOGICAL desktop size, not the source pixels.")
    if "AUTO_MAX_PRESET" not in types:
        errors.append("there is no cap on how far the automatic ladder may climb. Auto steps on RTT, and\n"
                      "        RTT is not bandwidth: a 20ms link with a 5 Mbit/s uplink would be promoted\n"
                      "        into the most expensive preset precisely because it looked healthy.")

    if errors:
        print("GATE FAIL: the resolution ceiling or its compatibility rule is wrong.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"OK: ceiling {m_new.group(1)} for clients that name pixels, {m_old.group(1)} for clients that "
          f"only send a fraction; width arbitrated across the room; fps to 60; presets absolute")
    return 0


if __name__ == "__main__":
    sys.exit(main())
