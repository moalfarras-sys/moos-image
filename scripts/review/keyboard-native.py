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
engine.loadData(b"""
import QtQuick
import QtQuick.Controls
ApplicationWindow {
    visible: true; visibility: Window.Maximized; title: "MoOS keyboard review"
    color: "#202024"
    TextField { id: field; anchors.centerIn: parent; width: 520; placeholderText: "اكتب هنا"
        focus: true; Component.onCompleted: forceActiveFocus() }
}
""")
print("MOOS_KEYBOARD_CLIENT_READY", flush=True)
sys.exit(app.exec())
'''


def no_core() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--look", default="org.moos.ui2.bloom")
    ap.add_argument("--locales", default="ar_AR,de_DE")
    ap.add_argument("--logical", default="1766x1104")
    ap.add_argument("--scale", type=float, default=1.45)
    ap.add_argument("--stock", action="store_true")
    ap.add_argument("--gpu", action="store_true")
    args = ap.parse_args()
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
               LANGUAGE="ar", QML_DISABLE_DISK_CACHE="1", QT_QPA_PLATFORMTHEME="kde")
    env["XDG_DATA_DIRS"] = str(ROOT / "system_files/usr/share") + ":/usr/share"
    if not args.gpu:
        env.update(LIBGL_ALWAYS_SOFTWARE="1", GALLIUM_DRIVER="llvmpipe")
    # plasma-keyboard runs inside bubblewrap with the reviewed style bound in.
    binds = ["--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev", "--bind", str(base), str(base),
             "--tmpfs", "/run/user"]
    if not args.stock:
        for directory in (LIB, STYLE):
            seam_dir = SEAMS / directory.relative_to("/")
            for path in sorted(seam_dir.iterdir()):
                binds += ["--ro-bind", str(path), str(directory / path.name)]
            # The image drops `prefer` from both modules so these files load.
            qmldir = base / f"qmldir-{directory.name}"
            qmldir.write_text("\n".join(l for l in (directory / "qmldir").read_text().splitlines()
                                         if not l.startswith("prefer ")) + "\n")
            binds += ["--ro-bind", str(qmldir), str(directory / "qmldir")]
    wrapper = base / "moos-keyboard-wrapper"
    wrapper.write_text("#!/bin/sh\nexec bwrap --die-with-parent --unshare-net " +
                       " ".join(f"'{b}'" for b in binds) + " /usr/bin/plasma-keyboard \"$@\" "
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
        (base / "client.py").write_text(CLIENT, encoding="utf-8")
        cenv = dict(env, WAYLAND_DISPLAY=sock, QT_QPA_PLATFORM="wayland", QT_IM_MODULE="qtvirtualkeyboard"
                    if False else "wayland")
        client = subprocess.Popen([sys.executable, "-s", "-B", str(base / "client.py")], env=cenv,
                                  stdout=(base / "client.log").open("w"), stderr=subprocess.STDOUT,
                                  preexec_fn=no_core)
        procs.append(client)
        time.sleep(3.0)
        for _ in range(3):
            subprocess.run([QDBUS, "org.kde.KWin", "/VirtualKeyboard", "org.kde.kwin.VirtualKeyboard.forceActivate"],
                           env=env, capture_output=True, timeout=10)
            time.sleep(1.5)
        import dbus
        from PySide6.QtGui import QImage
        session = dbus.bus.BusConnection("unix:path=" + str(run / "bus"))
        shot = dbus.Interface(session.get_object("org.kde.KWin", "/org/kde/KWin/ScreenShot2"),
                              "org.kde.KWin.ScreenShot2")
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
        QImage(bytes(data), w, h, stride, QImage.Format(fmt)).copy().save(str(out / "keyboard.png"))
        result["result"] = "CAPTURED"
    except Exception as exc:  # evidence, not a verdict
        result["result"] = "ERROR"
        result["error"] = repr(exc)
    finally:
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
