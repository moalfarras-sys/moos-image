#!/usr/bin/env python3
"""Gate: the frame rate a viewer asks for is the frame rate Mo PC Remote sends.

WHAT THIS PREVENTS, MEASURED ON A REAL MACHINE

The pipeline's rate limit was `videorate drop-only=true max-rate=N`. It reads as a limit and is
not one for a ScreenCast: that source is variable-rate (`framerate=0/1, max-framerate=60/1`), and
on such a stream the element passes every frame. On the Oracle A1, busy 1920x1080 screen, fps=30:
36.8 frames a second arrived and 35.6 were encoded. Asked for 15 it would have been the same 36.

Nothing could see it. The stream worked, the picture moved, and the number in the settings was
simply not the number on the wire — while two cores paid software H.264 for the difference and
every frame got fewer bits than the budget (bits-per-pixel x pixels x FPS) had promised it.

THE TWO WAYS TO GET THIS WRONG

  * not limiting — the defect above;
  * limiting by DROPPING the early frame. The frame that arrives early is the newest picture.
    Drop it and the last step of a scroll, or the pointer's final position, is missing until the
    one-second keepalive. So the pacer WAITS, downstream of the leaky queue that already discards
    the right frames.

FramePacer and pace_frame are lifted out of the helper and executed; importing the helper would
contact the desktop portal and need PyGObject.
"""

from __future__ import annotations

import ast
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"
SECOND = 1_000_000_000


def node(tree: ast.Module, kind, name: str):
    for item in tree.body:
        if isinstance(item, kind) and item.name == name:
            return item
    raise AssertionError(f"the helper has no {name}")


def run(node_, namespace: dict) -> None:
    module = ast.fix_missing_locations(ast.Module(body=[node_], type_ignores=[]))
    exec(compile(module, str(HELPER), "exec"), namespace)


def releases(pacer, arrivals: list[int], fps: int) -> tuple[list[int], list[int]]:
    """Feed arrivals through the pacer the way one streaming thread does: a frame cannot enter
    before the one ahead of it has left."""
    out, waits, free_at = [], [], 0
    for arrive in arrivals:
        enter = max(arrive, free_at)
        wait = pacer.wait_ns(enter, fps)
        free_at = enter + wait
        out.append(free_at)
        waits.append(wait)
    return out, waits


def source(rate: float, seconds: float, jitter: float = 0.0, seed: int = 7) -> list[int]:
    rng = random.Random(seed)
    step = SECOND / rate
    count = int(seconds * rate)
    times = [int(i * step + rng.uniform(-jitter, jitter) * step) for i in range(count)]
    return sorted(max(0, t) for t in times)


def main() -> int:
    if not HELPER.is_file():
        print(f"GATE FAIL: {HELPER.relative_to(ROOT)} is missing.")
        return 1
    text = HELPER.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(HELPER))
    errors: list[str] = []

    try:
        ns: dict[str, object] = {}
        run(node(tree, ast.ClassDef, "FramePacer"), ns)
        FramePacer = ns["FramePacer"]
    except Exception as e:                                    # noqa: BLE001
        print(f"GATE FAIL: FramePacer could not be executed: {type(e).__name__}: {e}")
        return 1

    # 1. Whatever the compositor delivers, releases are never closer than one interval — which
    #    is the whole statement "at most fps frames a second" — and no frame is lost on the way.
    for fps in (15, 30, 60):
        interval = SECOND // fps
        for rate, jitter in ((36.8, 0.0), (46.0, 0.3), (60.0, 0.1), (120.0, 0.4), (7.0, 0.5)):
            arrivals = source(rate, 6, jitter)
            out, waits = releases(FramePacer(), arrivals, fps)
            if len(out) != len(arrivals):
                errors.append(f"fps={fps}, source {rate}/s: {len(arrivals) - len(out)} frame(s) vanished")
            gaps = [b - a for a, b in zip(out, out[1:])]
            if gaps and min(gaps) < interval - 1:
                errors.append(f"fps={fps}, source {rate}/s: two frames left {min(gaps) / 1e6:.2f} ms "
                              f"apart; one interval is {interval / 1e6:.2f} ms")
            if any(w < 0 or w > interval for w in waits):
                errors.append(f"fps={fps}, source {rate}/s: a frame waited {max(waits) / 1e6:.1f} ms, "
                              "more than one interval")

    # 2. A quiet desktop pays nothing: a frame that arrives on time never waits.
    for fps in (15, 30, 60):
        interval = SECOND // fps
        sparse = [i * (interval + 1_000_000) for i in range(200)]       # a keystroke now and then
        _out, waits = releases(FramePacer(), sparse, fps)
        if any(waits):
            errors.append(f"fps={fps}: {sum(1 for w in waits if w)} on-time frame(s) were held back")

    # 3. A still screen leaves no debt and grants no credit: after a pause the first frame passes
    #    at once, and the burst behind it is paced like any other.
    pacer = FramePacer()
    burst = [5 * SECOND + i * 4_000_000 for i in range(60)]             # 250 frames/s after 5 s still
    out, waits = releases(pacer, [0] + burst, 30)
    if waits[1] != 0:
        errors.append("the first frame after a still screen was held back")
    gaps = [b - a for a, b in zip(out[1:], out[2:])]
    if min(gaps) < SECOND // 30 - 1:
        errors.append("a burst after a still screen was let through faster than fps")

    # 4. One slow setting cannot hang the streaming thread: teardown waits for that sleep.
    pacer = FramePacer()
    pacer.wait_ns(0, 1)
    held = pacer.wait_ns(1, 1)
    if not 0 < held <= FramePacer.MAX_WAIT_NS <= 250_000_000:
        errors.append(f"at fps=1 a frame would sleep {held / 1e6:.0f} ms on the streaming thread")

    # 5. The probe: it sleeps exactly the wait, reads the live fps, and NEVER drops.
    class FakeTime:
        def __init__(self): self.now, self.slept = 0, []
        def monotonic_ns(self): return self.now
        def sleep(self, seconds):
            self.slept.append(seconds)
            self.now += round(seconds * SECOND)     # the thread really is away that long

    class Gst:
        class PadProbeReturn: OK, DROP = "OK", "DROP"

    clock = FakeTime()
    state = {"fps": 30}
    probe_ns: dict[str, object] = {"time": clock, "Gst": Gst, "state": state,
                                   "frame_pacer": FramePacer()}
    try:
        run(node(tree, ast.FunctionDef, "pace_frame"), probe_ns)
        verdicts = []
        for at in (0, 10_000_000, 20_000_000):                         # three frames 10 ms apart
            clock.now = max(clock.now, at)          # a frame cannot enter while the thread sleeps
            verdicts.append(probe_ns["pace_frame"](None, None))
        if verdicts != ["OK", "OK", "OK"]:
            errors.append(f"the probe returned {verdicts}: an early frame must wait, never be "
                          "dropped — the dropped one is the newest picture")
        if len(clock.slept) != 2 or not all(0 < s <= 1 / 30 + 1e-6 for s in clock.slept):
            errors.append(f"the probe slept {clock.slept} for two early frames at fps=30")
        state["fps"] = 15
        clock.now, clock.slept[:] = 10 * SECOND, []
        probe_ns["pace_frame"](None, None)
        clock.now += 1_000_000
        probe_ns["pace_frame"](None, None)
        if not clock.slept or abs(clock.slept[-1] - (1 / 15 - 0.001)) > 0.002:
            errors.append(f"a change of fps is not followed by the next frame (slept {clock.slept})")
    except Exception as e:                                    # noqa: BLE001
        errors.append(f"pace_frame could not be executed: {type(e).__name__}: {e}")

    # 6. Wiring, read from the code with comments and docstrings removed.
    code = re.sub(r'"""[\s\S]*?"""', '""', text)
    code = "\n".join(re.sub(r"(?<!\S)#.*$", "", line) for line in code.splitlines())
    build = re.search(r"^def build\(w, h\):\n([\s\S]*?)(?=^def )", code, re.M)
    body = build.group(1) if build else ""
    if not re.search(r'rate\.get_static_pad\("sink"\)\.add_probe\(\s*Gst\.PadProbeType\.BUFFER,\s*pace_frame\)', body):
        errors.append("build() does not put pace_frame on the rate limiter's sink pad")
    if "frame_pacer.reset()" not in body:
        errors.append("build() does not reset the pacer: a new pipeline would inherit the old cadence")
    queue_at, rate_at = body.find("queue name=capq leaky=downstream"), body.find("name=rate")
    if not 0 <= queue_at < rate_at:
        errors.append("the pacer must sit DOWNSTREAM of the leaky queue: upstream of it the wait "
                      "would be on the compositor's thread, and nothing would discard stale frames")
    if "PadProbeReturn.DROP" in code:
        errors.append("something in the helper drops frames in a probe")

    if errors:
        print("GATE FAIL: Mo PC Remote's frame rate limit.")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("ok: Mo PC Remote sends at most the frame rate that was asked for, and loses no frame doing it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
