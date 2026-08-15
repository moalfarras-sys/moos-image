#!/usr/bin/env python3
"""Gate: a computer with a touchscreen must get the real mouse and keyboard.

WHY THIS EXISTS

`DesktopInput` is the REAL mouse and keyboard path — physical key codes, mouse buttons, the wheel,
pointer lock, keyboard lock. RemoteScreen constructs it always but ATTACHES it only in "desktop"
mode, because its window-level keydown listener would otherwise steal every keystroke from the
phone's hidden-textarea path. So the gesture mode is not a cosmetic preference: in "touch" mode a
real keyboard and a real mouse are simply not connected to anything.

`defaultMode()` decided that on evidence of a touchscreen ALONE:

    const touch = maxTouchPoints > 0 || "ontouchstart" in window || (any-pointer: coarse)
    return touch ? "touch" : "desktop"

A Windows laptop with a touchscreen satisfies that while also having a mouse and a trackpad, so an
ordinary computer came up with no real mouse buttons, no wheel, no key codes, and click-and-drag
scrolling instead of selecting — which reads as the REMOTE being broken. The file's own note
predicted it ("A touchscreen laptop therefore starts in touch mode... the safer way to be wrong")
and it is not the safer way to be wrong; the owner reported exactly this from a computer browser.

This is the same misdiagnosis as the toolbar edge (see test_remote_toolbar_edge.py): asking about
the PRIMARY pointer instead of what is AVAILABLE.

AND THE HOLE THAT MUST STAY CLOSED

An earlier attempt — `(pointer: fine) && !(any-pointer: coarse)` — REQUIRED positive evidence of a
mouse, and a headless Firefox answers false to every pointer query, so a 1280x860 desktop window
silently came up in touch mode. The fix therefore has to use the mouse test only to RESCUE a device
that already looked like touch, never as a precondition for desktop. `touch && !mouse` does that;
`mouse ? "desktop" : "touch"` would reopen the hole, so the shape is asserted, not just the string.
"""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "moremote/controller/src/ui/RemoteScreen.tsx"


def main() -> int:
    src = SCREEN.read_text(encoding="utf-8")
    # Comments must never satisfy this gate.
    code = "\n".join(
        l for l in src.splitlines()
        if not l.lstrip().startswith(("//", "*", "/*")))

    errors: list[str] = []

    body = re.search(r"function defaultMode\(\): GestureMode \{(.*?)\n\}", code, re.S)
    if not body:
        print("GATE FAIL:\n  - could not locate defaultMode() in RemoteScreen.tsx.")
        return 1
    b = body.group(1)

    if "any-pointer: fine" not in b:
        errors.append(
            "defaultMode() never asks whether a fine pointer is AVAILABLE, so a Windows laptop "
            "with a touchscreen starts in touch mode and DesktopInput — the real mouse and "
            "keyboard — is never attached.")

    if not re.search(r"return\s+touch\s*&&\s*!\s*\w+\s*\?\s*[\"']touch[\"']\s*:\s*[\"']desktop[\"']", b):
        errors.append(
            "defaultMode() does not return `touch && !mouse ? \"touch\" : \"desktop\"`. The mouse "
            "test must only RESCUE a device that already looked like touch — making it a "
            "precondition for desktop reopens the headless-browser hole, where a browser that "
            "answers false to every pointer query got a phone layout in a 1280x860 window.")

    # Keyboard Lock must be requested BEFORE the fullscreen transition — Chrome 131 permission-gates
    # both locks, so asking afterwards prompts the user a second time on a screen that just resized.
    fs = re.search(r"if \(el\.requestFullscreen\) \{(.*?)\.catch", code, re.S)
    if not fs:
        errors.append("could not locate the requestFullscreen block to check lock ordering.")
    else:
        block = fs.group(1)
        lock_at = block.find("requestKeyboardLock")
        full_at = block.find("el.requestFullscreen()")
        if lock_at < 0:
            errors.append("the fullscreen path no longer requests Keyboard Lock, so Esc, Tab, "
                          "Ctrl+W and F11 stay the browser's and never reach the remote desktop.")
        elif full_at >= 0 and lock_at > full_at:
            errors.append(
                "Keyboard Lock is requested AFTER el.requestFullscreen(). Chrome's guidance is to "
                "lock first, or the user is prompted twice — the second time on a screen that has "
                "just changed size under them.")

    if errors:
        print("GATE FAIL: a computer browser would not get a real mouse and keyboard.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: a touchscreen machine with a mouse gets desktop mode, the headless-browser hole "
          "stays closed, and Keyboard Lock is requested before fullscreen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
