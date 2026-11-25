#!/usr/bin/env python3
"""Look at the REAL plasma-keyboard, styled from this tree, on a private KWin.

    python3 scripts/review/keyboard-native.py OUT_DIR [--look org.moos.ui2.bloom]
        [--locales ar_AR,de_DE] [--logical 1766x1104] [--scale 1.45] [--stock] [--gpu]

A private `kwin_wayland --virtual` runs plasma-keyboard as its input method
(inside bubblewrap, with this tree's keyboard style files bound over the
installed ones and their qmldir without `prefer`, exactly as the image build
installs them). A private Qt client focuses a text field, KWin's
org.kde.kwin.VirtualKeyboard.forceActivate shows the panel, and ScreenShot2
captures the output. Nothing reaches the owner's display, bus or keyboard
settings. Source-harness evidence: virtual output, no touch hardware.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QDBUS = "/usr/lib64/qt6/bin/qdbus"
LIB = Path("/usr/lib64/qt6/qml/org/kde/plasma/keyboard/lib")
STYLE = Path("/usr/lib64/qt6/qml/QtQuick/VirtualKeyboard/Styles/Breeze")
SEAMS = ROOT / "build_files/plasma-seams/6.8.3"
LOOKS = {
    "org.moos.ui2.bloom": ("MoOSUI2Bloom", "MoOSUI2Bloom"),
    "org.moos.ui2.bloom.light": ("MoOSUI2BloomLight", "MoOSUI2BloomLight"),
    "org.moos.ui2": ("MoOSUI2Dark", "MoOSUI2"),
    "org.moos.ui2.light": ("MoOSUI2Light", "MoOSUI2Light"),
    "org.moos.ui2.aurora": ("MoOSUI2Aurora", "MoOSUI2Aurora"),
    "org.moos.ui2.midnight.light": ("MoOSUI2Daylight", "MoOSUI2Daylight"),
}
CLIENT = r'''
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.loadData("""
import QtQuick
import QtQuick.Controls
ApplicationWindow {
    visible: true; visibility: Window.Maximized; title: "MoOS keyboard review"
    color: "#202024"
    Timer { interval: 700; running: true; onTriggered: {
        const pt = field.mapToGlobal(field.width / 2, field.height / 2)
        console.info("MOOS_FIELD_AT", pt.x, pt.y)
    } }
    TextField { id: field; anchors.horizontalCenter: parent.horizontalCenter; y: parent.height * 0.15; width: Math.min(parent.width - 32, 520); placeholderText: "اكتب هنا"
        onTextChanged: console.info("MOOS_REVIEW_INPUT", JSON.stringify(text)); focus: true; Component.onCompleted: forceActiveFocus() }
}
""".encode("utf-8"))
if not engine.rootObjects():
    sys.exit("Cannot create private text client")
print("MOOS_KEYBOARD_CLIENT_READY", flush=True)
sys.exit(app.exec())
'''


def no_core() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (1, 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--look", default="org.moos.ui2.bloom")
    ap.add_argument("--locales", default="ar_AR,de_DE")
    ap.add_argument("--logical", default="1766x1104")
    ap.add_argument("--scale", type=float, default=1.45)
    ap.add_argument("--stock", action="store_true")
    ap.add_argument("--launcher", help="start the keyboard with this desktop file's exact Exec line "
                    "(a live copy's launcher) instead of binding this tree's seams over /usr")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--exercise-posture", action="store_true", help="exercise the desktop bar, keys, and live tablet posture transitions")
    ap.add_argument("--initial-tablet", action="store_true", help="begin the posture journey with a detached cover")
    ap.add_argument("--pointer-mode", choices=("any", "touch", "never"), default="any",
                    help="KWin pointer-focus policy for the posture journey")
    ap.add_argument("--exercise-digits", action="store_true", help="type all ten digits into a strict ASCII-only field")
    ap.add_argument("--exercise-arabic", action="store_true", help="verify native Arabic input and long-press selection")
    ap.add_argument("--exercise-touchbar", action="store_true",
                    help="type, learn and complete an Arabic word, insert emoji and open the emoji sheet")
    args = ap.parse_args()
    if sum((args.exercise_posture, args.exercise_digits, args.exercise_touchbar, args.exercise_arabic)) > 1:
        ap.error("choose one native interaction per run")
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lw, lh = (int(v) for v in args.logical.split("x"))
    scheme, icons = LOOKS[args.look]
    base = Path(tempfile.mkdtemp(prefix="moos-keyboard-review."))
    run = base / "run"
    for d in ("home", "config", "cache", "data", "xdg", "run"):
        (base / d).mkdir(mode=0o700)
    cfg = base / "config"
    colors = Path(f"/usr/share/color-schemes/{scheme}.colors")
    (cfg / "kdeglobals").write_text(
        colors.read_text(encoding="utf-8")
        + f"\n[General]\nColorScheme={scheme}\nfont=Meyar Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n"
        f"[KDE]\nLookAndFeelPackage={args.look}\n[Icons]\nTheme={icons}\n", encoding="utf-8")
    # Exercise the same published KWin state as the detachable cover, inside
    # this private compositor only. Pointer focus can open the compact panel.
    posture = "off" if args.exercise_posture and not args.initial_tablet else "on"
    visibility_mode = {"never": 0, "touch": 1, "any": 2}[args.pointer_mode]
    (cfg / "kwinrc").write_text(f"[Input]\nTabletMode={posture}\n[Wayland]\nVirtualKeyboardMode={visibility_mode}\n")
    (cfg / "kxkbrc").write_text("[Layout]\nUse=true\nLayoutList=ara\nVariantList=\n")
    (cfg / "plasmakeyboardrc").write_text(f"[General]\nenabledLocales={args.locales}\n", encoding="utf-8")
    pw, ph = round(lw * args.scale), round(lh * args.scale)
    (cfg / "kwinoutputconfig.json").write_text(json.dumps([
        {"name": "outputs", "data": [{"connectorName": "Virtual-0", "scale": args.scale,
                                      "mode": {"basic": {"width": pw, "height": ph, "refreshRate": 60000}, "flags": 1},
                                      "transform": "Normal", "overscan": 0, "rgbRange": "Automatic",
                                      "vrrPolicy": "Never"}]},
        {"name": "setups", "data": [{"lidClosed": False, "outputs": [
            {"enabled": True, "outputIndex": 0, "position": {"x": 0, "y": 0}, "priority": 1,
             "replicationSource": ""}]}]}]), encoding="utf-8")
    bus_conf = base / "bus.conf"
    bus_conf.write_text('<busconfig><type>session</type><listen>unix:path=' + str(run / "bus") +
                        '</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
                        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("WAYLAND", "DBUS", "XDG_", "QT_", "QML", "KDE", "DISPLAY", "XAUTHORITY",
                                "LANG", "LC_"))}
    env.update(HOME=str(base / "home"), XDG_RUNTIME_DIR=str(run), XDG_CONFIG_HOME=str(cfg),
               XDG_CACHE_HOME=str(base / "cache"), XDG_DATA_HOME=str(base / "data"),
               XDG_CONFIG_DIRS=str(base / "xdg") + ":/etc/xdg", XDG_DATA_DIRS="/usr/share",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(run / "bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(base / "absent"),
               KWIN_WAYLAND_NO_PERMISSION_CHECKS="1", LANG="ar_SA.UTF-8", LC_ALL="ar_SA.UTF-8",
               LANGUAGE="ar", QML_DISABLE_DISK_CACHE="1", QT_QPA_PLATFORMTHEME="kde", QT_FORCE_STDERR_LOGGING="1")
    env["XDG_DATA_DIRS"] = str(ROOT / "system_files/usr/share") + ":/usr/share"
    if not args.gpu:
        env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe")
    # plasma-keyboard runs inside bubblewrap with the reviewed style bound in.
    binds = ["--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev", "--bind", str(base), str(base),
             "--tmpfs", "/run/user"]
    if not args.stock and not args.launcher:
        for directory in (LIB, STYLE):
            seam_dir = SEAMS / directory.relative_to("/")
            for path in sorted(seam_dir.iterdir()):
                binds += ["--ro-bind", str(path), str(directory / path.name)]
            # The image drops `prefer` from both modules so these files load.
            qmldir = base / f"qmldir-{directory.name}"
            qmldir.write_text("\n".join(l for l in (directory / "qmldir").read_text().splitlines()
                                         if not l.startswith("prefer ")) + "\n")
            binds += ["--ro-bind", str(qmldir), str(directory / "qmldir")]
        layouts = Path("/usr/share/plasma/keyboard/layouts")
        for path in sorted((SEAMS / layouts.relative_to("/")).glob("*/*.qml")):
            binds += ["--ro-bind", str(path), str(layouts / path.parent.name / path.name)]
    # The MoOS Touch Bar module comes from this tree; the image installs it at
    # /usr/lib64/qt6/qml/org/moos/keyboard.
    tree_env = "" if args.stock else f"QML_IMPORT_PATH='{ROOT}/system_files/usr/lib64/qt6/qml' "
    if args.exercise_posture:
        tree_env += "WAYLAND_DEBUG=client "
    command = "/usr/bin/plasma-keyboard"
    if args.launcher:
        import shlex
        exec_line = next(line[5:] for line in Path(args.launcher).read_text().splitlines()
                         if line.startswith("Exec="))
        tree_env, command = "", " ".join(shlex.quote(a) for a in shlex.split(exec_line))
    wrapper = base / "moos-keyboard-wrapper"
    if args.launcher:
        # The live launcher is a bwrap itself (a nested one cannot map its user inside the
        # review's read-only one). KWin's environment is already this review's private
        # bus, runtime and XDG directories.
        wrapper.write_text(f"#!/bin/sh\nexec {command} \"$@\" >>'{base}/keyboard.log' 2>&1\n", encoding="utf-8")
    else:
        wrapper.write_text("#!/bin/sh\nexec env " + tree_env + "bwrap --die-with-parent --unshare-net " +
                           " ".join(f"'{b}'" for b in binds) + f" {command} \"$@\" "
                           f">>'{base}/keyboard.log' 2>&1\n", encoding="utf-8")
    wrapper.chmod(0o755)
    procs = []
    result = {"look": args.look, "locales": args.locales, "stock": args.stock}
    sock = "wayland-keyboard-review"
    try:
        procs.append(subprocess.Popen(["dbus-daemon", "--nofork", "--config-file=" + str(bus_conf)], env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(50):
            if (run / "bus").is_socket():
                break
            time.sleep(0.1)
        kwin = subprocess.Popen(["kwin_wayland", "--virtual", "--width", str(lw), "--height", str(lh),
                                 "--scale", str(args.scale), "--socket", sock, "--no-lockscreen",
                                 "--no-global-shortcuts", "--no-kactivities", "--inputmethod", str(wrapper)],
                                env=env, stdout=(base / "kwin.log").open("w"), stderr=subprocess.STDOUT,
                                preexec_fn=no_core)
        procs.append(kwin)
        for _ in range(100):
            if (run / sock).is_socket():
                break
            time.sleep(0.1)
        time.sleep(1.5)
        client_source = CLIENT
        if args.exercise_digits:
            client_source = client_source.replace("id: field;", "id: field; inputMethodHints: Qt.ImhDigitsOnly; "
                "validator: RegularExpressionValidator { regularExpression: /[0-9]*/ }")
        if args.exercise_posture:
            client_source = client_source.replace("visible: true; visibility:", "flags: Qt.Window | Qt.FramelessWindowHint; visible: true; visibility:")
            client_source = client_source.replace("focus: true; Component.onCompleted: forceActiveFocus()", "focus: false")
        (base / "client.py").write_text(client_source, encoding="utf-8")
        cenv = dict(env, WAYLAND_DISPLAY=sock, QT_QPA_PLATFORM="wayland", QT_QPA_PLATFORMTHEME="", QT_IM_MODULE="wayland")
        client = subprocess.Popen([sys.executable, "-s", "-B", str(base / "client.py")], env=cenv,
                                  stdout=(base / "client.log").open("w"), stderr=subprocess.STDOUT,
                                  preexec_fn=no_core)
        procs.append(client)
        for _ in range(400):
            if "MOOS_KEYBOARD_CLIENT_READY" in (base / "client.log").read_text():
                break
            if client.poll() is not None:
                raise RuntimeError("private text client failed to start")
            time.sleep(0.1)
        else:
            raise RuntimeError("private text client readiness timed out")
        if args.exercise_posture:
            # A real click on this private editor opens the panel through the
            # client's text-input protocol, as it does on a physical desktop.
            from gi.repository import Gio, GLib
            sys.path.insert(0, str(ROOT / "moremote/agent-linux"))
            from mo_remote_eis import EisInput
            private = Gio.DBusConnection.new_for_address_sync(
                env["DBUS_SESSION_BUS_ADDRESS"],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
            eis = EisInput(private, Gio, GLib)
            def ready_input():
                # KWin can re-create EIS devices when its native settings
                # change. The live client dispatches those events continuously.
                for _ in range(50):
                    eis.dispatch()
                    if eis.ready:
                        return
                    time.sleep(0.04)
                raise RuntimeError("private input devices did not return after the posture change")
            def click(x, y):
                ready_input()
                eis.absolute(x, y)
                time.sleep(0.12)
                eis.send("NotifyPointerButton", (272, 1), None)
                time.sleep(0.1)
                eis.send("NotifyPointerButton", (272, 0), None)
                time.sleep(0.25)
            for _ in range(50):
                coords = re.search(r"MOOS_FIELD_AT ([.\d]+) ([.\d]+)", (base / "client.log").read_text())
                if coords:
                    break
                time.sleep(0.1)
            if not coords:
                raise RuntimeError("private editor did not report its placement")
            click(float(coords[1]) / lw, float(coords[2]) / lh)
        for _ in range(0 if args.exercise_posture else 3):
            subprocess.run([QDBUS, "org.kde.KWin", "/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard.forceActivate"],
                           env=env, capture_output=True, timeout=10)
            time.sleep(1.5)
        import dbus
        from PySide6.QtGui import QImage
        session = dbus.bus.BusConnection("unix:path=" + str(run / "bus"))
        vk = dbus.Interface(session.get_object("org.kde.KWin", "/VirtualKeyboard"),
                            "org.freedesktop.DBus.Properties")
        for _ in range(50):
            state = vk.GetAll("org.kde.kwin.VirtualKeyboard")
            if state.get("visible"):
                break
            time.sleep(0.1)
        result["mode"] = int(state["mode"])
        manager = session.get_object("org.kde.KWin", "/org/kde/KWin")
        result["tablet"] = bool(dbus.Interface(manager, "org.freedesktop.DBus.Properties").Get(
            "org.kde.KWin.TabletModeManager", "tabletMode"))
        result["keyboard"] = {str(k): bool(v) for k, v in state.items() if isinstance(v, dbus.Boolean)}
        shot = dbus.Interface(session.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2"),
                              "org.kde.KWin.ScreenShot2")
        def capture(name: str | None = None):
            rd, wr = os.pipe()
            try:
                meta = shot.CaptureActiveScreen({"native-resolution": True, "include-cursor": False},
                                                dbus.types.UnixFd(wr))
            finally:
                os.close(wr)
            data = bytearray()
            with os.fdopen(rd, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    data += chunk
            w, h, stride, fmt = (int(meta[k]) for k in ("width", "height", "stride", "format"))
            if len(data) != h * stride:
                raise RuntimeError("incomplete native screen capture")
            frame = QImage(bytes(data), w, h, stride, QImage.Format(fmt)).copy()
            if frame.isNull() or (name and not frame.save(str(out / name))):
                raise RuntimeError("could not read the private display")
            return frame
        capture("keyboard.png")
        expect_hidden = args.exercise_posture and visibility_mode != 2
        if not state.get("active") or bool(state.get("visible")) == expect_hidden or int(state["mode"]) != visibility_mode:
            raise RuntimeError(f"unexpected panel state for pointer mode {args.pointer_mode}: {result['keyboard']!r}")
        # The keyboard process (a descendant of this private KWin, never the owner's).
        def descendants(root_pid):
            children = {}
            for stat in Path("/proc").glob("[0-9]*/stat"):
                try:
                    fields = stat.read_text().rsplit(")", 1)[1].split()
                    children.setdefault(int(fields[1]), []).append(int(stat.parent.name))
                except (OSError, ValueError, IndexError):
                    continue
            found, pending = [], [root_pid]
            while pending:
                for child in children.get(pending.pop(), []):
                    found.append(child)
                    pending.append(child)
            return found
        def keyboard_rss(key):
            for pid in descendants(kwin.pid):
                try:
                    if Path(f"/proc/{pid}/comm").read_text().strip() == "plasma-keyboard":
                        status = Path(f"/proc/{pid}/status").read_text()
                        result[key] = int(re.search(r"VmRSS:\s+(\d+)", status).group(1))
                except OSError:
                    pass
        keyboard_rss("keyboard_rss_kib")
        if args.exercise_posture and not expect_hidden:
            keys = max(150, round(lh * 0.3))
            bar = max(44, round(keys * 0.15))
            band = bar + max(8, round(keys * 0.03))
            regions = []
            def wait_region(label, height):
                # The input panel sends KWin this exact mask, including the area
                # it reserves from the editor. A cropped screenshot cannot prove it.
                pattern = r"wl_region#\d+\.add\(0, (\d+), " + str(lw) + r", (\d+)\)"
                last = []
                for _ in range(60):
                    last = re.findall(pattern, (base / "keyboard.log").read_text(errors="replace"))
                    if last and tuple(map(int, last[-1])) == (lh - height, height):
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError(f"{label} expected a {height}-pixel input region, last {last[-3:]}")
                # KWin animates the actual panel after it receives its final
                # mask. Wait for the left glass control to paint and settle
                # before sending another click to that position.
                previous = None
                for _ in range(25):
                    frame = capture()
                    y = round((lh - height + band / 2) / lh * frame.height())
                    row = tuple(frame.pixelColor(round(frame.width() * fx), y).rgb()
                                for fx in (.006, .011, .019, .026, .032, .039, .045))
                    if len(set(row)) > 1 and row == previous:
                        regions.append((label, height))
                        return
                    previous = row
                    time.sleep(0.1)
                raise RuntimeError(f"{label} input mask arrived but its controls did not paint")
            def change_posture(value):
                subprocess.run(["kwriteconfig6", "--file", "kwinrc", "--group", "Input",
                                "--key", "TabletMode", "--notify", value], env=env, check=True, timeout=5)
                for _ in range(40):
                    observed = dbus.Interface(manager, "org.freedesktop.DBus.Properties").Get(
                        "org.kde.KWin.TabletModeManager", "tabletMode")
                    if bool(observed) == (value == "on"):
                        return
                    time.sleep(0.05)
                raise RuntimeError(f"KWin did not publish test posture {value!r}")
            def tool_x(button):
                # Arabic input places settings, then the desktop keys button, on the left.
                edge = 6 * keys / (800 if lw < 500 else 600 if lw < 1200 else 700)
                x = edge + (bar * 1.15 / 2 if button == "settings" else bar * 1.15 + round(bar * 0.1) + bar / 2)
                return x / lw
            def bar_y(height):
                return (lh - height + band / 2) / lh
            if args.initial_tablet:
                wait_region("initially detached", keys + band)
                change_posture("off")
            wait_region("attached", band)
            capture("attached.png")
            ready_input()
            for down in (1, 0):
                eis.send("NotifyKeyboardKeycode", (30, down), None)
            time.sleep(0.25)
            capture("after-hardware-key.png")
            if not vk.Get("org.kde.kwin.VirtualKeyboard", "visible"):
                raise RuntimeError("the physical keystroke hid the Touch Bar")
            click(tool_x("keys"), bar_y(band))
            capture("after-manual-keys.png")
            wait_region("keys opened by hand", keys + band)
            click(tool_x("keys"), bar_y(keys + band))
            wait_region("keys closed by hand", band)
            click(tool_x("settings"), bar_y(band))
            wait_region("settings from compact bar", keys + band)
            capture("desktop-settings.png")
            click(tool_x("settings"), bar_y(keys + band))
            wait_region("settings closed", band)
            change_posture("on")
            wait_region("detached", keys + band)
            capture("tablet-keys.png")
            change_posture("off")
            wait_region("reattached", band)
            capture("reattached.png")
            typed = [json.loads(line.partition("MOOS_REVIEW_INPUT ")[2])
                     for line in (base / "client.log").read_text().splitlines() if "MOOS_REVIEW_INPUT " in line]
            if typed != ["ش"]:
                raise RuntimeError(f"the physical key did not reach the editor exactly once: {typed!r}")
            result["regions"] = regions
            result["keycode30"] = typed[-1]
        if args.exercise_arabic:
            from gi.repository import Gio, GLib
            sys.path.insert(0, str(ROOT / "moremote/agent-linux"))
            from mo_remote_eis import EisInput
            private = Gio.DBusConnection.new_for_address_sync(
                env["DBUS_SESSION_BUS_ADDRESS"],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
            eis = EisInput(private, Gio, GLib)
            try:
                # The native Arabic layout has twelve columns and four rows.
                # The second row is offset by half a letter key.
                row_y = 1 - max(0.3, 150 / lh) * 2.5 / 4
                def button(down):
                    eis.send("NotifyPointerButton", (272, int(down)), None)
                eis.absolute(2/12, row_y)
                time.sleep(0.15)
                button(True)
                time.sleep(0.12)
                button(False)
                time.sleep(0.4)
                eis.absolute(6/12, row_y)
                time.sleep(0.15)
                button(True)
                time.sleep(1.2)
                capture("alternate.png")
                eis.absolute(6/12 + 0.035, row_y - 0.08)
                time.sleep(0.3)
                button(False)
                time.sleep(0.6)
                capture("typed.png")
            finally:
                eis.close()
                private.close_sync(None)
            lines = (base / "client.log").read_text().splitlines()
            typed = [json.loads(line.partition("MOOS_REVIEW_INPUT ")[2]) for line in lines
                     if "MOOS_REVIEW_INPUT " in line]
            result["typed"] = typed
            if not typed or typed[0] != "س" or typed[-1] not in ("سأ", "سإ", "سآ", "سٱ"):
                raise RuntimeError("Arabic key and held alternate did not reach the private editor")
        if args.exercise_touchbar or args.exercise_digits:
            from gi.repository import Gio, GLib
            sys.path.insert(0, str(ROOT / "moremote/agent-linux"))
            from mo_remote_eis import EisInput
            private = Gio.DBusConnection.new_for_address_sync(
                env["DBUS_SESSION_BUS_ADDRESS"],
                Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
                None, None)
            eis = EisInput(private, Gio, GLib)
            # Geometry from the style: keys keep upstream's max(30% height, 150); the Touch
            # Bar's band (bar max(44, 15% of the keys) + max(8, 3%)) sits above them.
            keys = max(0.3 * lh, 150)
            bar = max(44, round(keys * 0.15))
            band = bar + max(8, round(keys * 0.03))
            top = lh - keys - band
            band_h = round(6 * keys / 700) + band
            bar_y = (top + round((band_h - bar) / 2) + bar / 2) / lh
            row = lambda r: (lh - keys + keys * (r + 0.5) / 4) / lh
            inset = 6 / (lw / (keys + band) * 700 * (keys + band) / keys) * lw
            def tap(fx, fy, hold=0.12):
                eis.absolute(fx, fy)
                time.sleep(0.12)
                eis.send("NotifyPointerButton", (272, 1), None)
                time.sleep(hold)
                eis.send("NotifyPointerButton", (272, 0), None)
                time.sleep(0.35)
            letters = {"س": (2 / 12, 1), "ل": (5 / 12, 1), "ا": (6 / 12, 1), "م": (9 / 12, 1),
                       "ق": (3.5 / 12, 0), "ب": (4 / 12, 1)}
            def write(word):
                for ch in word:
                    fx, r = letters[ch]
                    tap(fx, row(r))
            space = (0.5, row(3))
            middle_start = (lw - inset - round(bar * 1.35) - round(bar * 0.1)) / lw
            first_chip = middle_start - max(round(bar * 1.8), 0) / 2 / lw
            first_emoji = middle_start - round(bar * 1.1) / 2 / lw
            switch = (lw - inset - round(bar * 1.35) / 2) / lw
            if args.exercise_digits:
                try:
                    area = keys - 12 * keys / (800 if lw < 500 else 600 if lw < 1200 else 700)
                    left = (lw - area) / 2
                    for column, digit_row in ((1, 3), (0, 2), (1, 2), (2, 2), (0, 1),
                                              (1, 1), (2, 1), (0, 0), (1, 0), (2, 0)):
                        tap((left + area * (column + 0.5) / 4) / lw, row(digit_row))
                    capture("digits.png")
                finally:
                    eis.close()
                    private.close_sync(None)
            else:
                try:
                    write("سلام")
                    tap(*space)
                    write("سل")
                    time.sleep(0.4)
                    capture("suggest.png")
                    tap(first_chip, bar_y)
                    write("قلب")
                    time.sleep(0.4)
                    capture("emoji-for-word.png")
                    tap(first_emoji, bar_y)
                    tap(switch, bar_y)
                    time.sleep(0.6)
                    capture("emoji-sheet.png")
                    sheet_top = (top + band_h) / lh
                    cell = (keys + band - band_h) * 0.8 / 4
                    tap((lw - inset - cell * 1.12 / 2) / lw, sheet_top + cell / 2 / lh)
                    tap(switch, bar_y)
                    time.sleep(0.6)
                    capture("after-sheet.png")
                    keyboard_rss("keyboard_rss_after_sheet_kib")
                    # ⚙ sits at the bar's far end: the left in Arabic, the right in German/English.
                    gear = round(bar * 1.15) / 2 + inset
                    tap((gear if args.locales.startswith("ar") else lw - gear) / lw, bar_y)
                    time.sleep(0.6)
                    capture("settings-sheet.png")
                    tap((gear if args.locales.startswith("ar") else lw - gear) / lw, bar_y)
                    # The system button is adjacent to Settings on this tablet layout.
                    # Inspect a central band away from the toggle's own pressed state.
                    tools_x = inset + round(bar * 1.15) + round(bar * 0.1) + bar / 2
                    tools_x = (tools_x if args.locales.startswith("ar") else lw - tools_x) / lw
                    tap(tools_x, bar_y)
                    time.sleep(0.4)
                    tools_frame = capture("system-tools.png")
                    tap(tools_x, bar_y)
                    time.sleep(0.4)
                    text_frame = capture("restored-text-tools.png")
                    band_rect = (int(pw * 0.32), int(ph * bar_y - bar * args.scale * 0.28),
                                 int(pw * 0.38), max(1, round(bar * args.scale * 0.56)))
                    if tools_frame.copy(*band_rect) == text_frame.copy(*band_rect):
                        raise RuntimeError("device tools did not replace the central input targets")
                finally:
                    eis.close()
                    private.close_sync(None)
            lines = (base / "client.log").read_text().splitlines()
            typed = [json.loads(line.partition("MOOS_REVIEW_INPUT ")[2]) for line in lines
                     if "MOOS_REVIEW_INPUT " in line]
            result["typed"] = typed
            final = typed[-1] if typed else ""
            result["final"] = final
            # One ❤️ from the bar, one from the sheet: each exactly once (a key event
            # carrying ❤️ was committed once per keysym, twice, by plasma-keyboard 6.8.3).
            expected = "0123456789" if args.exercise_digits else "سلام سلام قلب❤️❤️"
            if final != expected:
                raise RuntimeError(f"private editor received {final!r}; expected {expected!r}")
        owned_errors = [line.strip() for line in (base / "keyboard.log").read_text(errors="replace").splitlines()
                        if re.search(r"(?i)(/org/moos/keyboard/|/Styles/Breeze/|/plasma/keyboard/(?:lib|layouts)/)", line)
                        and re.search(r"Error:|binding loop|unable to assign|cannot assign|is not a type", line, re.I)]
        if owned_errors:
            raise RuntimeError(f"keyboard reported {owned_errors[:3]}")
        result["result"] = "CAPTURED"
    except Exception as exc:  # evidence, not a verdict
        result["result"] = "ERROR"
        result["error"] = repr(exc)
    finally:
        if args.exercise_posture and "eis" in locals():
            eis.close()
            private.close_sync(None)
        for p in reversed(procs):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
        for name in ("kwin.log", "keyboard.log", "client.log"):
            if (base / name).exists():
                (out / name).write_text((base / name).read_text(errors="replace"))
        shutil.rmtree(base, ignore_errors=True)
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("result") == "CAPTURED" else 1


if __name__ == "__main__":
    sys.exit(main())
