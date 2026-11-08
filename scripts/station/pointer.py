#!/usr/bin/env python3
"""Drive the pointer on a live MoOS session, with the compositor as the witness.

WHY THIS EXISTS

Every pointer-driven item of the station review (Hub controls, removing a widget,
App Drop, a dismissed authentication) had been recorded as "untested" because
`ydotool mousemove --absolute` does not land where it is asked to on this screen:
the review of 2026-09-17 says two calibration attempts clicked somewhere else, and
a measurement on 2026-09-18 found the cursor still at the top-left corner after
every absolute request. Open-loop pointer input is therefore not usable evidence.

This tool closes the loop instead of calibrating it. KWin itself reports where the
pointer is (`workspace.cursorPos` in a KWin script), the answer comes back through
Klipper's D-Bus interface, and the pointer is walked to the target with relative
moves until the compositor agrees it is there. The gain of a relative move is
measured on the way, so the walk converges in two or three steps whatever pointer
acceleration the session applies.

Coordinates are LOGICAL pixels, the same ones KWin, Plasma and `kscreen-doctor`
use (this station: 1450x816 at 265% scale), not the 3840x2160 device pixels a
screenshot returns.

  scripts/station/pointer.py where
  scripts/station/pointer.py move 700 400
  scripts/station/pointer.py click 700 400 --button right
  scripts/station/pointer.py drag 700 400 900 500

The owner's plain-text clipboard is backed up privately and put back literally.
An unconfirmed restore retains that recovery file; command errors omit its text.
Non-text or unreadable clipboard content aborts BEFORE the probe: Klipper's
string interface cannot restore images, file lists or rich-text alternatives.
The probe leaves an entry in Klipper history; that history is never cleared.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

SOCKET = os.environ.get("YDOTOOL_SOCKET", "/run/user/1000/.ydotool_socket")
ENV = os.environ | {"YDOTOOL_SOCKET": SOCKET}
QDBUS = "qdbus-qt6"
KLIPPER = ("org.kde.klipper", "/klipper", "org.kde.klipper.klipper")
# ydotool button indices; OR 0x40 for down, 0x80 for up, 0xC0 for a full click.
BUTTONS = {"left": 0x00, "right": 0x01, "middle": 0x02}

PROBE = (
    'callDBus("org.kde.klipper", "/klipper", "org.kde.klipper.klipper",'
    ' "setClipboardContents", "MOOS-CURSOR @nonce@ " + workspace.cursorPos.x + ","'
    ' + workspace.cursorPos.y);\n'
)


def run(argv: list[str], timeout: int = 20, *, input_text: str | None = None) -> str:
    try:
        done = subprocess.run(argv, env=ENV, capture_output=True, text=True, timeout=timeout,
                              check=True, input=input_text)
    except (OSError, subprocess.SubprocessError):
        # CalledProcessError and TimeoutExpired include argv in their repr.
        # A clipboard restoration must never put the owner's text there.
        raise SystemExit("pointer: native control failed; command data withheld") from None
    return done.stdout.strip()


def qdbus(*args: str) -> str:
    return run([QDBUS, *args])


def bridge_available() -> bool:
    # Ask the bus itself without introspection or service activation.
    value = run(["busctl", "--user", "--timeout=3s", "--json=short", "call",
                 "org.freedesktop.DBus", "/org/freedesktop/DBus",
                 "org.freedesktop.DBus", "NameHasOwner", "s", "org.kde.klipper"], timeout=5)
    try:
        reply = json.loads(value)
        if (reply.get("type") != "b" or reply.get("data") != [True]
                or type(reply["data"][0]) is not bool):
            return False
        # Plasma may own the name while its clipboard object is not loaded.
        # An owned bus name alone is not an active clipboard bridge.
        value = run(["busctl", "--user", "--timeout=3s", "--json=short", "call",
                     KLIPPER[0], KLIPPER[1], "org.freedesktop.DBus.Introspectable", "Introspect"], timeout=5)
        xml = json.loads(value)["data"][0]
        if not isinstance(xml, str) or len(xml) > 256 * 1024:
            return False
        node = ET.fromstring(xml)
        methods = {m.get("name") for i in node.findall("interface") if i.get("name") == KLIPPER[2]
                   for m in i.findall("method")}
        return {"getClipboardContents", "setClipboardContents"} <= methods
    except (ValueError, AttributeError, KeyError, IndexError, TypeError, ET.ParseError, SystemExit):
        return False


def clipboard_text() -> str:
    # JSON preserves leading/trailing whitespace, unlike qdbus's CLI newline.
    try:
        value = run(["busctl", "--user", "--timeout=3s", "--json=short", "call",
                     *KLIPPER, "getClipboardContents"], timeout=5)
        reply = json.loads(value)
        if (reply.get("type") == "s" and isinstance(reply.get("data"), list)
                and len(reply["data"]) == 1 and isinstance(reply["data"][0], str)):
            return reply["data"][0]
    except (ValueError, AttributeError):
        pass
    raise SystemExit("pointer: clipboard response is unavailable")


def save_clipboard() -> str:
    """Accept only a clipboard we can restore losslessly through Klipper."""
    try:
        types = subprocess.run(["wl-paste", "--list-types"], env=ENV,
                               capture_output=True, text=True, check=True, timeout=5)
        formats = set(types.stdout.splitlines())
        plain = {"text/plain", "text/plain;charset=utf-8", "UTF8_STRING", "STRING", "TEXT"}
        metadata = {"TARGETS", "TIMESTAMP", "SAVE_TARGETS", "MULTIPLE"}
        if not formats or formats - plain - metadata or not formats & plain:
            raise ValueError("clipboard contains non-text formats")
        mime = next(item for item in ("text/plain;charset=utf-8", "text/plain",
                                     "UTF8_STRING", "STRING", "TEXT") if item in formats)
        result = subprocess.run(["wl-paste", "--no-newline", "--type", mime], env=ENV,
                                capture_output=True, check=True, timeout=5)
        return result.stdout.decode("utf-8")
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        raise SystemExit("pointer: clipboard cannot be preserved as plain text; "
                         "copy plain text before reviewing. Clipboard left untouched.") from error


class Pointer:
    """The live pointer, with KWin as the source of truth for where it is."""

    def __init__(self) -> None:
        if not shutil.which("wl-copy"):
            raise SystemExit("pointer: clipboard restoration is unavailable; no input performed")
        if not bridge_available():
            raise SystemExit("pointer: compositor clipboard bridge is unavailable; no input performed")
        self._saved = save_clipboard()
        self._workspace = tempfile.mkdtemp(prefix="moos-pointer-")
        self._backup = os.path.join(self._workspace, "clipboard.txt")
        fd = os.open(self._backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(self._saved.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        self._script = os.path.join(self._workspace, "probe.js")
        with open(self._script, "w", encoding="utf-8") as handle:
            handle.write(PROBE)
        self._loaded = False

    def restore(self) -> None:
        """Restore the saved text literally, even text resembling a probe reply."""
        restored = False
        try:
            if self._saved:
                run(["wl-copy", "--type", "text/plain;charset=utf-8"], input_text=self._saved)
            else:
                run(["wl-copy", "--clear"])
            # Confirm the native clipboard manager actually retained the text,
            # before its temporary Wayland supplier and backup can disappear.
            for _ in range(10):
                if clipboard_text() == self._saved:
                    restored = True
                    break
                time.sleep(.08)
            if not restored:
                raise SystemExit("pointer: clipboard restoration could not be confirmed")
        except BaseException:
            raise SystemExit("pointer: clipboard restoration failed; private recovery retained at "
                             + self._backup) from None
        finally:
            try:
                qdbus("org.kde.KWin", "/Scripting",
                      "org.kde.kwin.Scripting.unloadScript", "moospointer")
            except SystemExit:
                if restored:
                    raise
            finally:
                if restored:
                    shutil.rmtree(self._workspace, ignore_errors=True)

    def where(self) -> tuple[int, int]:
        """Ask KWin where the pointer is. Raises if the compositor does not answer."""
        for _ in range(3):
            prefix = "MOOS-CURSOR " + secrets.token_hex(8) + " "
            with open(self._script, "w", encoding="utf-8") as handle:
                handle.write(PROBE.replace("@nonce@", prefix.split()[1]))
            qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.unloadScript", "moospointer")
            qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.loadScript",
                  self._script, "moospointer")
            qdbus("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting.start")
            for _ in range(10):
                time.sleep(0.08)
                value = clipboard_text()
                if value.startswith(prefix):
                    x, _, y = value[len(prefix):].partition(",")
                    try:
                        return int(float(x)), int(float(y))
                    except (ValueError, OverflowError):
                        pass
        raise SystemExit("pointer: KWin did not report a cursor position")

    def nudge(self, dx: int, dy: int) -> None:
        run(["ydotool", "mousemove", "-x", str(dx), "-y", str(dy)])
        time.sleep(0.12)

    def move(self, x: int, y: int, tolerance: int = 2, steps: int = 12) -> tuple[int, int]:
        """Walk to (x, y) until KWin agrees, measuring the gain of each move."""
        here = self.where()
        gain = 1.0
        for _ in range(steps):
            dx, dy = x - here[0], y - here[1]
            if abs(dx) <= tolerance and abs(dy) <= tolerance:
                return here
            self.nudge(round(dx / gain), round(dy / gain))
            moved = self.where()
            travelled = max(abs(moved[0] - here[0]), abs(moved[1] - here[1]))
            asked = max(abs(round(dx / gain)), abs(round(dy / gain)))
            if asked >= 20 and travelled >= 5:
                # One measured gain, damped, so acceleration cannot make it oscillate.
                gain = max(0.3, min(3.0, (gain + travelled / asked) / 2))
            here = moved
        raise SystemExit(f"pointer: could not reach {x},{y}; stopped at {here[0]},{here[1]}")

    def click(self, button: str = "left", *, double: bool = False) -> None:
        code = BUTTONS[button]
        run(["ydotool", "click", f"0x{code | 0xC0:02x}"])
        if double:
            time.sleep(0.12)
            run(["ydotool", "click", f"0x{code | 0xC0:02x}"])
        time.sleep(0.25)

    def press(self, button: str = "left") -> None:
        run(["ydotool", "click", f"0x{BUTTONS[button] | 0x40:02x}"])
        time.sleep(0.12)

    def release(self, button: str = "left") -> None:
        run(["ydotool", "click", f"0x{BUTTONS[button] | 0x80:02x}"])
        time.sleep(0.12)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=("where", "move", "click", "drag"))
    parser.add_argument("coordinates", nargs="*", type=int)
    parser.add_argument("--button", default="left", choices=sorted(BUTTONS))
    parser.add_argument("--double", action="store_true")
    args = parser.parse_args()

    pointer = Pointer()
    try:
        if args.action == "where":
            print("%d,%d" % pointer.where())
            return 0
        if len(args.coordinates) < 2:
            parser.error(f"{args.action} needs x and y")
        x, y = args.coordinates[0], args.coordinates[1]
        landed = pointer.move(x, y)
        if args.action == "move":
            print("%d,%d" % landed)
            return 0
        if args.action == "click":
            pointer.click(args.button, double=args.double)
            print("clicked %s at %d,%d" % (args.button, *landed))
            return 0
        if len(args.coordinates) < 4:
            parser.error("drag needs x1 y1 x2 y2")
        try:
            pointer.press(args.button)
            pointer.move(args.coordinates[2], args.coordinates[3])
            end = pointer.where()
        finally:
            pointer.release(args.button)
        print("dragged %d,%d -> %d,%d" % (landed[0], landed[1], end[0], end[1]))
        return 0
    finally:
        pointer.restore()


if __name__ == "__main__":
    sys.exit(main())
