#!/usr/bin/env python3
"""Drive an X display through XTest: the review image has no xdotool.

    xinput.py move 400 300 move 410 310 sleep 1 focus type secret key Return

Commands run in order against $DISPLAY:
    scale S      multiply every later move by S (QT_SCALE_FACTOR: logical -> device)
    move X Y     pointer to absolute pixels
    click        left button press and release
    key NAME     tap one keysym (Return, Escape, Tab, a, ...)
    type TEXT    tap each character of an ASCII string
    focus        give X input focus to the topmost mapped top-level window
                 (there is no window manager under Xvfb, so nothing else will)
    sleep S      wait S seconds
"""
import ctypes
import sys
import time

x11 = ctypes.CDLL("libX11.so.6")
xtst = ctypes.CDLL("libXtst.so.6")

x11.XOpenDisplay.restype = ctypes.c_void_p
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XStringToKeysym.restype = ctypes.c_ulong
x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
x11.XKeysymToKeycode.restype = ctypes.c_ubyte
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
x11.XQueryTree.argtypes = [
    ctypes.c_void_p, ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
    ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)), ctypes.POINTER(ctypes.c_uint),
]
x11.XFree.argtypes = [ctypes.c_void_p]
xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]


class XWindowAttributes(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("width", ctypes.c_int), ("height", ctypes.c_int),
        ("border_width", ctypes.c_int), ("depth", ctypes.c_int),
        ("visual", ctypes.c_void_p), ("root", ctypes.c_ulong),
        ("c_class", ctypes.c_int), ("bit_gravity", ctypes.c_int),
        ("win_gravity", ctypes.c_int), ("backing_store", ctypes.c_int),
        ("backing_planes", ctypes.c_ulong), ("backing_pixel", ctypes.c_ulong),
        ("save_under", ctypes.c_int), ("colormap", ctypes.c_ulong),
        ("map_installed", ctypes.c_int), ("map_state", ctypes.c_int),
        ("all_event_masks", ctypes.c_long), ("your_event_mask", ctypes.c_long),
        ("do_not_propagate_mask", ctypes.c_long), ("override_redirect", ctypes.c_int),
        ("screen", ctypes.c_void_p),
    ]


x11.XGetWindowAttributes.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(XWindowAttributes)]

IS_VIEWABLE = 2
REVERT_TO_POINTER_ROOT = 1
SHIFTED = {
    "!": "exclam", "@": "at", "#": "numbersign", "$": "dollar", "%": "percent",
    "_": "underscore", "+": "plus", "?": "question", ":": "colon",
}
PLAIN = {" ": "space", "-": "minus", ".": "period", ",": "comma", "/": "slash", "=": "equal"}


def main(argv: list[str]) -> int:
    display = x11.XOpenDisplay(None)
    if not display:
        print("xinput: cannot open $DISPLAY", file=sys.stderr)
        return 1
    root = x11.XDefaultRootWindow(display)

    def tap(keysym_name: str, shift: bool = False) -> None:
        keysym = x11.XStringToKeysym(keysym_name.encode())
        keycode = x11.XKeysymToKeycode(display, keysym)
        if not keycode:
            raise SystemExit(f"xinput: no keycode for {keysym_name!r}")
        shift_code = x11.XKeysymToKeycode(display, x11.XStringToKeysym(b"Shift_L"))
        if shift:
            xtst.XTestFakeKeyEvent(display, shift_code, 1, 0)
        xtst.XTestFakeKeyEvent(display, keycode, 1, 0)
        xtst.XTestFakeKeyEvent(display, keycode, 0, 0)
        if shift:
            xtst.XTestFakeKeyEvent(display, shift_code, 0, 0)
        x11.XSync(display, 0)
        time.sleep(0.03)

    def focus_topmost() -> None:
        root_ret, parent_ret = ctypes.c_ulong(), ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)()
        count = ctypes.c_uint()
        x11.XQueryTree(display, root, ctypes.byref(root_ret), ctypes.byref(parent_ret),
                       ctypes.byref(children), ctypes.byref(count))
        target = 0
        best = 0
        for index in range(count.value):
            attrs = XWindowAttributes()
            if not x11.XGetWindowAttributes(display, children[index], ctypes.byref(attrs)):
                continue
            area = attrs.width * attrs.height
            # The largest viewable top-level is the surface under review; tooltips
            # and helper windows are smaller. Later siblings win ties (stacked above).
            if attrs.map_state == IS_VIEWABLE and area >= best and area > 64:
                best = area
                target = children[index]
        if children:
            x11.XFree(children)
        if target:
            x11.XSetInputFocus(display, target, REVERT_TO_POINTER_ROOT, 0)
            x11.XSync(display, 0)

    args = list(argv)
    factor = 1.0
    while args:
        command = args.pop(0)
        if command == "scale":
            factor = float(args.pop(0))
        elif command == "move":
            x = int(float(args.pop(0)) * factor)
            y = int(float(args.pop(0)) * factor)
            xtst.XTestFakeMotionEvent(display, -1, x, y, 0)
            x11.XSync(display, 0)
            time.sleep(0.05)
        elif command == "click":
            xtst.XTestFakeButtonEvent(display, 1, 1, 0)
            xtst.XTestFakeButtonEvent(display, 1, 0, 0)
            x11.XSync(display, 0)
        elif command == "key":
            tap(args.pop(0))
        elif command == "type":
            for char in args.pop(0):
                if char in SHIFTED:
                    tap(SHIFTED[char], shift=True)
                elif char in PLAIN:
                    tap(PLAIN[char])
                elif char.isupper():
                    tap(char.lower(), shift=True)
                else:
                    tap(char)
        elif command == "focus":
            focus_topmost()
        elif command == "sleep":
            time.sleep(float(args.pop(0)))
        else:
            raise SystemExit(f"xinput: unknown command {command!r}")
    x11.XFlush(display)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
