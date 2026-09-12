#!/usr/bin/env python3
"""Gate: one scroll convention on the wire — positive dy scrolls the remote DOWN.

WHY THIS EXISTS

Mo PC Remote has one controller and two agents. They disagreed about which way is down, and
because nothing compared them, the disagreement was "fixed" in the shared middle and the repair
inverted the mouse on MoOS itself.

  * `moremote/agent-linux/InputInjector.cs` — MoOS's own agent — declares "positive = right /
    down" and means it: the portal path hands `dy * PixelsPerNotch` to NotifyPointerAxis, which
    is positive-down like wl_pointer, libinput and a browser WheelEvent, and the uinput fallback
    negates because evdev REL_WHEEL is positive-UP.

  * `moremote/agent/Core/InputInjector.cs` — the Windows agent — used to declare "up = positive"
    and pass the value straight to MOUSEEVENTF_WHEEL, which counts forward/away from the user.

So the same packet scrolled opposite ways on the two platforms. The controller was then made to
send `conn.scroll(dx, -dy)` from its real-mouse path, which lined Windows up and left every MoOS
browser session scrolling backwards — for a whole release, with a green source gate in
`moremote/controller/tests/coordinates.test.ts` asserting the inversion.

The invariant is not "which platform is right". It is that a platform difference must be absorbed
AT THE PLATFORM BOUNDARY, so the wire has exactly one meaning for both agents and both input
paths (a phone swipe and a real wheel). This gate reads all three files and refuses a build in
which any of them drifts back.

The runtime half is `moremote/controller/tests/browser-input.test.mjs`, which reads the sign that
actually leaves the production bundle for a wheel turn and for a finger swipe and requires them to
agree. Prose cannot satisfy either: both strip comments first.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "moremote/controller/src/ui/RemoteScreen.tsx"
LINUX_AGENT = ROOT / "moremote/agent-linux/InputInjector.cs"
WINDOWS_AGENT = ROOT / "moremote/agent/Core/InputInjector.cs"
PORTAL = ROOT / "moremote/agent-linux/mo-remote-portal.py"


def strip_c_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("//")
    )


def strip_hash_comments(src: str) -> str:
    return "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )


def main() -> int:
    errors: list[str] = []
    for path in (CONTROLLER, LINUX_AGENT, WINDOWS_AGENT, PORTAL):
        if not path.is_file():
            print(f"GATE FAIL: {path.relative_to(ROOT)} is missing.")
            return 1

    controller = strip_c_comments(CONTROLLER.read_text(encoding="utf-8"))
    linux = strip_c_comments(LINUX_AGENT.read_text(encoding="utf-8"))
    windows = strip_c_comments(WINDOWS_AGENT.read_text(encoding="utf-8"))
    portal = strip_hash_comments(PORTAL.read_text(encoding="utf-8"))

    # 1. The controller's real-mouse path must pass the browser's own sign through untouched.
    #    desktop.ts deliberately performs no inversion of its own, so this callback is the only
    #    place a second one could hide.
    if re.search(r"scroll:\s*\(dx,\s*dy\)\s*=>\s*conn\.scroll\(dx,\s*-\s*dy\)", controller):
        errors.append(
            "RemoteScreen.tsx inverts the real-mouse wheel again (`conn.scroll(dx, -dy)`). "
            "WheelEvent.deltaY is already positive-down, which is the wire's convention; "
            "a platform that disagrees negates in ITS OWN injector."
        )
    if not re.search(r"scroll:\s*\(dx,\s*dy\)\s*=>\s*conn\.scroll\(dx,\s*dy\)", controller):
        errors.append(
            "RemoteScreen.tsx no longer forwards the real-mouse wheel unchanged; the desktop "
            "scroll callback must be `conn.scroll(dx, dy)`."
        )

    # 2. The touch path keeps its own, user-visible natural-scroll setting. It is a preference,
    #    not a platform difference, and repairing the mouse must never fold the two together.
    if not re.search(r"naturalScrollRef\.current\s*\?\s*-1\s*:\s*1", controller):
        errors.append(
            "the touch scroll path lost its independent natural-scroll direction; a finger has "
            "no inherent direction and the setting is the user's."
        )

    # 3. MoOS's agent: the portal axis carries the wire's sign unchanged, and only the uinput
    #    fallback — the boundary that genuinely differs — negates.
    if not re.search(r'type\s*=\s*"axis",\s*dx\s*=\s*x\s*\*\s*PixelsPerNotch,\s*dy\s*=\s*y\s*\*\s*PixelsPerNotch',
                     linux):
        errors.append(
            "agent-linux/InputInjector.cs no longer sends the portal axis as `dy * PixelsPerNotch`. "
            "NotifyPointerAxis is positive-down; anything else re-introduces the platform split."
        )
    if not re.search(r"Math\.Round\(\s*-\s*y\s*\)", linux):
        errors.append(
            "agent-linux/InputInjector.cs no longer negates for the uinput fallback. "
            "evdev REL_WHEEL is positive-UP, so that path — and only that path — must invert."
        )

    # 4. The portal helper must pass the axis straight to NotifyPointerAxis with no sign of its own.
    axis = re.search(r'elif\s+t\s*==\s*"axis":\s*\n\s*(.+)', portal)
    if not axis:
        errors.append("mo-remote-portal.py no longer handles the `axis` message.")
    elif "-" in axis.group(1).split("NotifyPointerAxis", 1)[-1]:
        errors.append(
            "mo-remote-portal.py negates the axis on its way to NotifyPointerAxis. The helper is "
            "a transport; the sign is settled by the injector above it."
        )

    # 5. The Windows agent absorbs Win32's opposite convention at its own boundary.
    if not re.search(r"_scrollRemY\s*\+=\s*-\s*dy\s*\*\s*WHEEL_DELTA", windows):
        errors.append(
            "agent/Core/InputInjector.cs no longer negates for MOUSEEVENTF_WHEEL. Win32 counts a "
            "wheel forward (away from the user) as positive, the wire counts down as positive, and "
            "that difference belongs here rather than in the shared controller."
        )
    if re.search(r"<param name=\"dy\">[^<]*up\s*=\s*positive", windows):
        errors.append(
            "agent/Core/InputInjector.cs still documents `dy` as up-positive. The wire is "
            "down-positive; the Win32 convention is an implementation detail of this file."
        )

    if errors:
        print("GATE FAIL: the wire's scroll direction has split again.")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("PASS: one scroll convention (positive dy = down) across controller, portal and both agents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
