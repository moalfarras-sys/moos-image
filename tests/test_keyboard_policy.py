#!/usr/bin/env python3
"""The on-screen keyboard stays away while a physical keyboard is connected.

Owner steering 2026-11-24: "when a keyboard is connected I don't want it to appear".
Measured on V3 1187 the same day: KWin ran with VirtualKeyboardMode 2 (any input) and
tabletMode true from the cover switch while a Compx 2.4G USB keyboard was in use, so the
panel appeared on every focused field; the cover switch cannot see a USB keyboard.

Pure checks: device classification from a private sysfs (USB/Bluetooth external, i8042
internal, uinput/unknown virtual), the decision table and the owner's opt-out.
Native journey: the real moos-keyboard-policy against a fake KWin on a PRIVATE bus (its
org.kde.kwin.VirtualKeyboard, InputDeviceManager and TabletModeManager with their real
property and signal names): a USB keyboard hides the panel, removing it restores the
replaced mode, the internal keyboard counts only outside tablet mode, ydotoold never
counts, a Never the person chose is never undone, and the opt-out restores what the
policy changed. A mutant that also counts virtual devices must fail. Nothing here
reaches the owner's KWin, bus or config.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/libexec/moos-keyboard-policy"
UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-keyboard-policy.service"
loader = importlib.machinery.SourceFileLoader("moos_keyboard_policy", str(SCRIPT))
spec = importlib.util.spec_from_loader("moos_keyboard_policy", loader)
P = importlib.util.module_from_spec(spec)
loader.exec_module(P)


def fake_sysfs(root: Path, devices: dict[str, tuple[int, bool]]) -> Path:
    """class/input/<event>/device -> a device dir with id/bustype; virtual ones under devices/virtual."""
    for name, (bus, virtual) in devices.items():
        target = root / ("devices/virtual/input" if virtual else "devices/pci0000:00/usb1/1-1") / name
        (target / "id").mkdir(parents=True)
        (target / "id/bustype").write_text(f"{bus:04x}\n")
        link = root / "class/input" / name
        link.mkdir(parents=True)
        os.symlink(target, link / "device")
    return root


class Classification(unittest.TestCase):
    def test_bus_and_path_decide_the_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_sysfs(Path(tmp), {"event8": (0x03, False), "event9": (0x05, False),
                                          "event2": (0x11, False), "event22": (0x06, True),
                                          "event30": (0x03, True)})
            self.assertEqual(P.classify("event8", root), "external")
            self.assertEqual(P.classify("event9", root), "external")
            self.assertEqual(P.classify("event2", root), "internal")
            self.assertEqual(P.classify("event22", root), "virtual")
            self.assertEqual(P.classify("event30", root), "virtual", "a uinput USB look-alike is virtual")
            self.assertEqual(P.classify("event99", root), "virtual", "unknown provenance never hides the keyboard")

    def test_which_keyboards_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fake_sysfs(Path(tmp), {"event8": (0x03, False), "event2": (0x11, False),
                                          "event22": (0x06, True), "event7": (0x18, False)})
            usb = {"sysName": "event8", "alphaNumericKeyboard": True, "enabled": True}
            at = {"sysName": "event2", "alphaNumericKeyboard": True, "enabled": True}
            ydotool = {"sysName": "event22", "alphaNumericKeyboard": True, "enabled": True}
            touchpad = {"sysName": "event7", "alphaNumericKeyboard": False, "enabled": True}
            self.assertTrue(P.physical_keyboard([usb], tablet_mode=True, root=root))
            self.assertFalse(P.physical_keyboard([at], tablet_mode=True, root=root))
            self.assertTrue(P.physical_keyboard([at], tablet_mode=False, root=root))
            self.assertFalse(P.physical_keyboard([ydotool, touchpad], tablet_mode=False, root=root))
            self.assertFalse(P.physical_keyboard([dict(usb, enabled=False)], tablet_mode=True, root=root))


class Decision(unittest.TestCase):
    def test_table(self):
        self.assertEqual(P.decide(1, True, {}), (0, {"managed": True, "restore": 1}))
        self.assertEqual(P.decide(2, True, {}), (0, {"managed": True, "restore": 2}))
        self.assertEqual(P.decide(0, True, {}), (None, {}), "a person's own Never is left alone")
        self.assertEqual(P.decide(0, False, {"managed": True, "restore": 2}), (2, {"managed": False}))
        self.assertEqual(P.decide(0, False, {"managed": True, "restore": 7}), (1, {"managed": False}))
        self.assertEqual(P.decide(0, False, {}), (None, {}), "a Never the policy did not set stays")
        self.assertEqual(P.decide(1, False, {"managed": True, "restore": 1}), (None, {"managed": False}),
                         "the person changed the mode meanwhile: theirs wins")

    def test_owner_opt_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)
            self.assertTrue(P.enabled_by_owner(config))
            (config / "moos-keyboardrc").write_text("[Policy]\nHideWithPhysicalKeyboard=false\n")
            self.assertFalse(P.enabled_by_owner(config))

    def test_the_unit_is_a_graphical_user_service_outside_the_greeter(self):
        unit = UNIT.read_text()
        for needle in ("ConditionUser=!@system", "ExecStart=/usr/libexec/moos-keyboard-policy",
                       "WantedBy=graphical-session.target", "PartOf=graphical-session.target"):
            self.assertIn(needle, unit)
        for path in ("build_files/build.sh", "build_files/build-arm.sh"):
            self.assertIn("moos-keyboard-policy.service", (ROOT / path).read_text())
        self.assertTrue(os.access(SCRIPT, os.X_OK))


FAKE_KWIN = r'''
import sys
import warnings
warnings.simplefilter("ignore", DeprecationWarning)
from gi.repository import Gio, GLib
XML = """<node>
<interface name="org.kde.kwin.VirtualKeyboard"><property name="mode" type="i" access="readwrite"/></interface>
<interface name="org.kde.KWin.InputDeviceManager"><property name="devicesSysNames" type="as" access="read"/>
 <signal name="deviceAdded"><arg type="s"/></signal><signal name="deviceRemoved"><arg type="s"/></signal></interface>
<interface name="org.kde.KWin.InputDevice"><property name="sysName" type="s" access="read"/>
 <property name="alphaNumericKeyboard" type="b" access="read"/><property name="enabled" type="b" access="read"/></interface>
<interface name="org.kde.KWin.TabletModeManager"><property name="tabletMode" type="b" access="read"/>
 <signal name="tabletModeChanged"><arg type="b"/></signal></interface>
<interface name="org.moos.Test"><method name="Add"><arg type="s" direction="in"/><arg type="b" direction="in"/></method>
 <method name="Remove"><arg type="s" direction="in"/></method><method name="Tablet"><arg type="b" direction="in"/></method>
 <method name="SetMode"><arg type="i" direction="in"/></method><method name="Mode"><arg type="i" direction="out"/></method></interface>
</node>"""
node = Gio.DBusNodeInfo.new_for_xml(XML)
iface = {i.name: i for i in node.interfaces}
state = {"mode": int(sys.argv[1]), "tablet": sys.argv[2] == "1", "devices": {}}
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
registrations = {}

def get_property(conn, sender, path, interface, name):
    if interface == "org.kde.kwin.VirtualKeyboard": return GLib.Variant("i", state["mode"])
    if interface == "org.kde.KWin.InputDeviceManager": return GLib.Variant("as", list(state["devices"]))
    if interface == "org.kde.KWin.TabletModeManager": return GLib.Variant("b", state["tablet"])
    sys_name = path.rsplit("/", 1)[1]
    alnum = state["devices"][sys_name]
    return {"sysName": GLib.Variant("s", sys_name), "alphaNumericKeyboard": GLib.Variant("b", alnum),
            "enabled": GLib.Variant("b", True)}[name]

def set_property(conn, sender, path, interface, name, value):
    state["mode"] = value.unpack()
    print("MODE", state["mode"], flush=True)
    return True

def register(path, name):
    registrations[path] = bus.register_object(path, iface[name], method_call, get_property, set_property)

def method_call(conn, sender, path, interface, method, params, invocation):
    args = params.unpack()
    if method == "Add":
        state["devices"][args[0]] = args[1]
        register(f"/org/kde/KWin/InputDevice/{args[0]}", "org.kde.KWin.InputDevice")
        bus.emit_signal(None, "/org/kde/KWin/InputDevice", "org.kde.KWin.InputDeviceManager", "deviceAdded",
                        GLib.Variant("(s)", (args[0],)))
    elif method == "Remove":
        state["devices"].pop(args[0], None)
        bus.unregister_object(registrations.pop(f"/org/kde/KWin/InputDevice/{args[0]}"))
        bus.emit_signal(None, "/org/kde/KWin/InputDevice", "org.kde.KWin.InputDeviceManager", "deviceRemoved",
                        GLib.Variant("(s)", (args[0],)))
    elif method == "Tablet":
        state["tablet"] = args[0]
        bus.emit_signal(None, "/org/kde/KWin", "org.kde.KWin.TabletModeManager", "tabletModeChanged",
                        GLib.Variant("(b)", (args[0],)))
    elif method == "SetMode":
        state["mode"] = args[0]
    elif method == "Mode":
        invocation.return_value(GLib.Variant("(i)", (state["mode"],))); return
    invocation.return_value(None)

register("/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard")
register("/org/kde/KWin/InputDevice", "org.kde.KWin.InputDeviceManager")
register("/org/kde/KWin", "org.kde.KWin.TabletModeManager")
register("/test", "org.moos.Test")
Gio.bus_own_name_on_connection(bus, "org.kde.KWin", Gio.BusNameOwnerFlags.NONE, None, None)
print("FAKE_KWIN_READY", flush=True)
GLib.MainLoop().run()
'''


def native_available() -> str | None:
    if not shutil.which("dbus-daemon"):
        return "dbus-daemon is not installed"
    if importlib.util.find_spec("gi") is None:
        return "PyGObject is not installed"
    return None


class NativeJourney(unittest.TestCase):
    def setUp(self):
        reason = native_available()
        if reason:
            if os.environ.get("MOOS_REQUIRE_NATIVE_KEYBOARD_POLICY") == "1":
                self.fail(f"native keyboard-policy journey required but {reason}")
            self.skipTest(reason)
        self.tmp = Path(tempfile.mkdtemp(prefix="moos-kbpolicy-"))
        self.processes = []
        for name in ("home", "config", "state", "run"):
            (self.tmp / name).mkdir(mode=0o700)
        self.sysfs = fake_sysfs(self.tmp / "sys", {"event8": (0x03, False), "event2": (0x11, False),
                                                   "event22": (0x06, True)})
        conf = self.tmp / "bus.conf"
        conf.write_text(f'<busconfig><type>session</type><listen>unix:path={self.tmp}/run/bus</listen>'
                        '<auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
                        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        self.env = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG")}
        self.env.update(HOME=str(self.tmp / "home"), XDG_CONFIG_HOME=str(self.tmp / "config"),
                        XDG_STATE_HOME=str(self.tmp / "state"), XDG_RUNTIME_DIR=str(self.tmp / "run"),
                        DBUS_SESSION_BUS_ADDRESS=f"unix:path={self.tmp}/run/bus",
                        DBUS_SYSTEM_BUS_ADDRESS=f"unix:path={self.tmp}/no-system-bus",
                        MOOS_KEYBOARD_POLICY_SYSFS=str(self.sysfs))
        self.start(["dbus-daemon", "--nofork", f"--config-file={conf}"])
        for _ in range(50):
            if (self.tmp / "run/bus").is_socket():
                break
            time.sleep(0.1)

    def tearDown(self):
        for process in reversed(self.processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self, argv, **kwargs):
        process = subprocess.Popen(argv, env=self.env, stdin=subprocess.DEVNULL, text=True, **kwargs)
        self.processes.append(process)
        return process

    def fake(self, mode=1, tablet=True):
        (self.tmp / "fake.py").write_text(FAKE_KWIN)
        process = self.start([sys.executable, "-s", "-B", str(self.tmp / "fake.py"), str(mode), "1" if tablet else "0"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        seen = []
        for line in process.stdout:
            seen.append(line)
            if "FAKE_KWIN_READY" in line:
                return
        self.fail("fake KWin did not start: " + "".join(seen))

    def call(self, method, *args):
        signature = {"Add": "sb", "Remove": "s", "Tablet": "b", "SetMode": "i", "Mode": ""}[method]
        argv = ["gdbus", "call", "--session", "--dest", "org.kde.KWin", "--object-path", "/test",
                "--method", f"org.moos.Test.{method}", *[("true" if a else "false") if isinstance(a, bool) else str(a) for a in args]]
        out = subprocess.run(argv, env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def mode(self) -> int:
        return int(self.call("Mode").strip().strip("(),"))

    def wait_mode(self, expected, timeout=6.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.mode() == expected:
                return
            time.sleep(0.1)
        self.fail(f"mode stayed {self.mode()}, expected {expected}")

    def policy(self, script=SCRIPT):
        return self.start([sys.executable, "-s", "-B", str(script)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_a_connected_keyboard_hides_the_panel_and_its_removal_restores_it(self):
        if not shutil.which("gdbus"):
            self.skipTest("gdbus is not installed")
        self.fake(mode=2, tablet=True)
        self.call("Add", "event22", True)       # ydotoold: virtual, never counts
        self.policy()
        time.sleep(1.0)
        self.assertEqual(self.mode(), 2, "a virtual keyboard must not hide the panel")
        self.call("Add", "event8", True)        # the Compx USB receiver
        self.wait_mode(0)
        def presence():
            return subprocess.check_output([
                "gdbus", "call", "--session", "--dest", "org.moos.KeyboardPolicy", "--object-path", "/KeyboardPolicy",
                "--method", "org.freedesktop.DBus.Properties.Get", "org.moos.KeyboardPolicy", "PhysicalKeyboard"
            ], env=self.env, text=True).strip()
        self.assertEqual(presence(), "(<true>,)")
        state = json.loads((self.tmp / "state/moos/keyboard-policy.json").read_text())
        self.assertEqual(state, {"managed": True, "restore": 2})
        self.call("Remove", "event8")
        self.wait_mode(2)
        self.assertEqual(presence(), "(<false>,)")
        # The internal keyboard counts only with the cover on (tablet mode off).
        self.call("Add", "event2", True)
        time.sleep(1.0)
        self.assertEqual(self.mode(), 2, "the internal keyboard in tablet mode does not count")
        self.call("Tablet", False)
        self.wait_mode(0)
        self.call("Tablet", True)
        self.wait_mode(2)

    def test_a_never_the_person_chose_is_kept_and_the_opt_out_restores(self):
        if not shutil.which("gdbus"):
            self.skipTest("gdbus is not installed")
        self.fake(mode=0, tablet=True)          # the person chose Never in System Settings
        self.policy()
        self.call("Add", "event8", True)
        self.call("Remove", "event8")
        time.sleep(1.2)
        self.assertEqual(self.mode(), 0, "a Never the policy did not set is never undone")
        self.call("SetMode", 1)
        self.call("Add", "event8", True)
        self.wait_mode(0)
        (self.tmp / "config/moos-keyboardrc").write_text("[Policy]\nHideWithPhysicalKeyboard=false\n")
        self.call("Tablet", True)               # any event re-reads the opt-out
        self.wait_mode(1)

    def test_a_policy_that_counts_virtual_devices_is_refused(self):
        if not shutil.which("gdbus"):
            self.skipTest("gdbus is not installed")
        mutant = self.tmp / "mutant"
        text = SCRIPT.read_text()
        old = 'if kind == "external" or (kind == "internal" and not tablet_mode):'
        self.assertEqual(text.count(old), 1)
        mutant.write_text(text.replace(old, 'if kind in ("external", "virtual") or (kind == "internal" and not tablet_mode):'))
        self.fake(mode=1, tablet=True)
        self.call("Add", "event22", True)
        self.policy(mutant)
        time.sleep(1.2)
        self.assertEqual(self.mode(), 0, "control: the mutant hides the panel for ydotoold")


if __name__ == "__main__":
    unittest.main(verbosity=2)
