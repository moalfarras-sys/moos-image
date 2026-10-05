"""MoOS session input through KWin's EIS endpoint, independent of screen capture.

Only the authenticated agent's private stdin reaches this client. It has no listener,
no network credentials, and never asks the desktop portal for an input grant.
libei's public sender ABI: https://libinput.pages.freedesktop.org/libei/api/
"""
import ctypes as C
import os
import select
import threading
import time

POINTER, ABSOLUTE, KEYBOARD, SCROLL, BUTTON = 1, 2, 4, 16, 32


class EisInput:
    def __init__(self, bus, Gio, GLib):
        self.bus, self.Gio, self.GLib = bus, Gio, GLib
        self.lock = threading.RLock()
        self.devices = {}
        self.held = {}
        self.sequence = 0
        self.cookie = None
        self.ctx = None
        self.lib = C.CDLL("libei.so.1")
        signatures = {
            "ei_new_sender": (C.c_void_p, [C.c_void_p]),
            "ei_unref": (C.c_void_p, [C.c_void_p]),
            "ei_configure_name": (None, [C.c_void_p, C.c_char_p]),
            "ei_setup_backend_fd": (C.c_int, [C.c_void_p, C.c_int]),
            "ei_get_fd": (C.c_int, [C.c_void_p]),
            "ei_dispatch": (None, [C.c_void_p]),
            "ei_get_event": (C.c_void_p, [C.c_void_p]),
            "ei_event_get_type": (C.c_int, [C.c_void_p]),
            "ei_event_get_seat": (C.c_void_p, [C.c_void_p]),
            "ei_event_get_device": (C.c_void_p, [C.c_void_p]),
            "ei_event_unref": (C.c_void_p, [C.c_void_p]),
            "ei_device_ref": (C.c_void_p, [C.c_void_p]),
            "ei_device_unref": (C.c_void_p, [C.c_void_p]),
            "ei_device_has_capability": (C.c_bool, [C.c_void_p, C.c_int]),
            "ei_device_start_emulating": (None, [C.c_void_p, C.c_uint32]),
            "ei_device_stop_emulating": (None, [C.c_void_p]),
            "ei_device_frame": (None, [C.c_void_p, C.c_uint64]),
            "ei_device_get_region": (C.c_void_p, [C.c_void_p, C.c_size_t]),
            "ei_device_pointer_motion": (None, [C.c_void_p, C.c_double, C.c_double]),
            "ei_device_pointer_motion_absolute": (None, [C.c_void_p, C.c_double, C.c_double]),
            "ei_device_scroll_delta": (None, [C.c_void_p, C.c_double, C.c_double]),
            "ei_device_scroll_discrete": (None, [C.c_void_p, C.c_int32, C.c_int32]),
            "ei_device_button_button": (None, [C.c_void_p, C.c_uint32, C.c_bool]),
            "ei_device_keyboard_key": (None, [C.c_void_p, C.c_uint32, C.c_bool]),
        }
        for name in ("x", "y", "width", "height"):
            signatures["ei_region_get_" + name] = (C.c_uint32, [C.c_void_p])
        for name, (restype, argtypes) in signatures.items():
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = restype, argtypes
        self.lib.ei_seat_bind_capabilities.restype = None
        self.lib.ei_seat_bind_capabilities.argtypes = [C.c_void_p]
        try:
            reply, fds = bus.call_with_unix_fd_list_sync(
                "org.kde.KWin", "/org/kde/KWin/EIS/RemoteDesktop",
                "org.kde.KWin.EIS.RemoteDesktop", "connectToEIS",
                GLib.Variant("(i)", (3,)), GLib.VariantType.new("(hi)"),
                Gio.DBusCallFlags.NO_AUTO_START, 5000, None, None)
            fd_index, self.cookie = reply.unpack()
            fd = fds.get(fd_index)
            self.ctx = self.lib.ei_new_sender(None)
            if not self.ctx:
                os.close(fd)
                raise RuntimeError("libei could not create an input context")
            self.lib.ei_configure_name(self.ctx, b"Mo PC Remote")
            # libei takes ownership, including a failed initialization.
            if self.lib.ei_setup_backend_fd(self.ctx, fd) != 0:
                raise RuntimeError("libei refused KWin's input socket")
            self.fd = self.lib.ei_get_fd(self.ctx)
            end = time.monotonic() + 5
            while not self.ready and time.monotonic() < end:
                select.select([self.fd], [], [], .1)
                self.dispatch()
            if not self.ready:
                raise RuntimeError("KWin did not offer mouse and keyboard devices")
        except Exception:
            self.close()
            raise

    @property
    def ready(self):
        return all(self.device(cap, required=False) for cap in (POINTER, ABSOLUTE, KEYBOARD, BUTTON))

    def device(self, cap, required=True):
        for device, resumed in self.devices.items():
            if resumed and self.lib.ei_device_has_capability(device, cap):
                return device
        if required:
            raise RuntimeError("KWin input device temporarily unavailable")
        return None

    def dispatch(self):
        with self.lock:
            self.lib.ei_dispatch(self.ctx)
            while event := self.lib.ei_get_event(self.ctx):
                try:
                    kind = self.lib.ei_event_get_type(event)
                    device = self.lib.ei_event_get_device(event)
                    if kind == 2:
                        raise RuntimeError("KWin input connection closed")
                    if kind == 3:
                        seat = self.lib.ei_event_get_seat(event)
                        self.lib.ei_seat_bind_capabilities(seat, POINTER, ABSOLUTE,
                                                           KEYBOARD, SCROLL, BUTTON, C.c_void_p())
                    elif kind == 5:
                        self.devices[device] = False
                        self.lib.ei_device_ref(device)
                    elif kind == 8:
                        self.devices[device] = True
                        self.sequence = (self.sequence + 1) & 0xffffffff
                        self.lib.ei_device_start_emulating(device, self.sequence)
                    elif kind in (6, 7):
                        self.devices[device] = False
                        self.held = {k: d for k, d in self.held.items() if d != device}
                        if kind == 6:
                            self.devices.pop(device, None)
                            self.lib.ei_device_unref(device)
                finally:
                    self.lib.ei_event_unref(event)

    def frame(self, device):
        self.lib.ei_device_frame(device, time.monotonic_ns() // 1000)
        self.lib.ei_dispatch(self.ctx)

    def absolute(self, x, y):
        with self.lock:
            device = self.device(ABSOLUTE)
            # This single-output capture uses KWin's first input region. Bounds come from KWin,
            # never the encoded picture or a remembered 1920px reference.
            region = self.lib.ei_device_get_region(device, 0)
            if not region:
                raise RuntimeError("KWin has no input output")
            left = self.lib.ei_region_get_x(region)
            top = self.lib.ei_region_get_y(region)
            w = self.lib.ei_region_get_width(region)
            h = self.lib.ei_region_get_height(region)
            if not w or not h:
                raise RuntimeError("KWin input output has no extent")
            self.lib.ei_device_pointer_motion_absolute(
                device, left + min(1, max(0, x)) * (w - 1),
                top + min(1, max(0, y)) * (h - 1))
            self.frame(device)

    def send(self, method, args, keysym_code):
        with self.lock:
            if method == "NotifyPointerMotion":
                device = self.device(POINTER)
                self.lib.ei_device_pointer_motion(device, args[-2], args[-1])
            elif method in ("NotifyPointerButton", "NotifyKeyboardKeycode", "NotifyKeyboardKeysym"):
                keyboard = method != "NotifyPointerButton"
                code, down = args[-2], bool(args[-1])
                if method == "NotifyKeyboardKeysym":
                    code = keysym_code(code)
                key = (keyboard, code)
                device = self.held.get(key) if not down else None
                device = device or self.device(KEYBOARD if keyboard else BUTTON)
                fn = self.lib.ei_device_keyboard_key if keyboard else self.lib.ei_device_button_button
                fn(device, code, down)
                if down:
                    self.held[key] = device
                else:
                    self.held.pop(key, None)
            elif method == "NotifyPointerAxis":
                device = self.device(SCROLL)
                self.lib.ei_device_scroll_delta(device, args[-2], args[-1])
            elif method == "NotifyPointerAxisDiscrete":
                device = self.device(SCROLL)
                axis, steps = args[-2:]
                self.lib.ei_device_scroll_discrete(device, steps * 120 if axis == 1 else 0,
                                                  steps * 120 if axis == 0 else 0)
            else:
                raise RuntimeError("unsupported native input method: " + method)
            self.frame(device)

    def release_all(self):
        with self.lock:
            for (keyboard, code), device in list(self.held.items()):
                if self.devices.get(device):
                    fn = self.lib.ei_device_keyboard_key if keyboard else self.lib.ei_device_button_button
                    fn(device, code, False)
                    self.frame(device)
            self.held.clear()

    def close(self):
        with self.lock:
            if self.ctx:
                try:
                    self.release_all()
                finally:
                    for device in self.devices:
                        if self.devices[device]:
                            self.lib.ei_device_stop_emulating(device)
                        self.lib.ei_device_unref(device)
                    self.devices.clear()
                    self.lib.ei_unref(self.ctx)
                    self.ctx = None
            if self.cookie is not None:
                try:
                    self.bus.call_sync("org.kde.KWin", "/org/kde/KWin/EIS/RemoteDesktop",
                        "org.kde.KWin.EIS.RemoteDesktop", "disconnect",
                        self.GLib.Variant("(i)", (self.cookie,)), None,
                        self.Gio.DBusCallFlags.NO_AUTO_START, 1000, None)
                except Exception:
                    pass
                self.cookie = None
