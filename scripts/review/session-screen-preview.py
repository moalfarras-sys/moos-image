#!/usr/bin/env python3
"""Preview MoOS's REAL session components with every session action, on a private KWin.

    python3 scripts/review/session-screen-preview.py OUT.png [--look org.moos.ui2.bloom]
        [--lang ar|en] [--logical 1766x1104] [--scale 1.45] [--typed] [--refused]

The real greeters only offer Sleep/Restart/Shut Down when a system power
backend answers, which a private review cannot provide. This loads the
installed breeze components module with this tree's MoOS files over it (the
6.8 seam for SessionManagementScreen), MoOS's org.moos.ui, and composes them
the way plasma-login's Main/Login do: the session clock above, the island with
one account and the password row, and four MoOS ActionButtons in the dock, over
the selected look's wallpaper blurred and dimmed like the greeter's fader. It
runs as a Wayland client of a private `kwin_wayland --virtual` on the GPU and is
captured with ScreenShot2. Design evidence only: not the compiled greeter.
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
MODULE = Path("/usr/lib64/qt6/qml/org/kde/breeze/components")
SEAM = ROOT / "build_files/plasma-seams/6.8/usr/lib64/qt6/qml/org/kde/breeze/components/SessionManagementScreen.qml"
LOOKS = {
    "org.moos.ui2.bloom": ("MoOSUI2Bloom", "MoOSUI2Bloom", "MoOSUI2Bloom/contents/images_dark/1672x941.png"),
    "org.moos.ui2.bloom.light": ("MoOSUI2BloomLight", "MoOSUI2BloomLight",
                                 "MoOSUI2BloomLight/contents/images/1672x941.png"),
    "org.moos.ui2": ("MoOSUI2Dark", "MoOSUI2", "MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"),
    "org.moos.ui2.light": ("MoOSUI2Light", "MoOSUI2Light", "MoOSUI2Tide/contents/images/3840x2160.jpg"),
    "org.moos.ui2.aurora": ("MoOSUI2Aurora", "MoOSUI2Aurora", "MoOSUI2Aurora/contents/images_dark/3840x2160.jpg"),
    "org.moos.ui2.midnight.light": ("MoOSUI2Daylight", "MoOSUI2Daylight",
                                    "MoOSUI2Daylight/contents/images/3840x2160.jpg"),
    "org.moos.ui2.gaming": ("MoOSUI2Arena", "MoOSUI2Arena", "MoOSUI2Arena/contents/images_dark/3840x2160.jpg"),
}
SCENE = r'''
import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.plasma.extras as PlasmaExtras
import org.kde.breeze.components as Breeze
QQC2.ApplicationWindow {
    id: window
    visible: true
    visibility: QQC2.ApplicationWindow.FullScreen
    title: "MoOS session preview"
    color: "black"
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
    Kirigami.Theme.inherit: false
    LayoutMirroring.enabled: Qt.locale().textDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true
    Image {
        id: scene
        anchors.fill: parent
        source: "file://@WALLPAPER@"
        fillMode: Image.PreserveAspectCrop
        visible: false
    }
    MultiEffect {
        anchors.fill: parent
        source: scene
        blurEnabled: true
        blurMax: 64
        blur: 1.0
        brightness: @DIM@
        saturation: 0.25
    }
    Item {
        id: loginScreenRoot
        anchors.fill: parent
        property bool uiVisible: true
        Breeze.Clock {
            anchors.horizontalCenter: parent.horizontalCenter
            y: (login.userList.y + stack.y) / 2 - height / 2
        }
        Item {
            id: stack
            anchors.left: parent.left
            anchors.right: parent.right
            height: parent.height + Kirigami.Units.gridUnit * 3
            Breeze.SessionManagementScreen {
                id: login
                anchors.fill: parent
                userListModel: ListModel { ListElement { name: "moos"; realName: "MoOS"; icon: ""; needsPassword: true } }
                userListCurrentIndex: 0
                notificationMessage: "@NOTICE@"
                RowLayout {
                    Layout.fillWidth: true
                    PlasmaExtras.PasswordField {
                        id: password
                        Layout.fillWidth: true
                        placeholderText: "@PLACEHOLDER@"
                        text: "@TYPED@"
                        focus: true
                    }
                    QQC2.Button {
                        icon.name: Qt.locale().textDirection === Qt.RightToLeft ? "go-previous" : "go-next"
                        Accessible.name: "@PLACEHOLDER@"
                    }
                }
                actionItems: [
                    Breeze.ActionButton { icon.name: "system-suspend"; text: "@SLEEP@" },
                    Breeze.ActionButton { icon.name: "system-reboot"; text: "@RESTART@" },
                    Breeze.ActionButton { icon.name: "system-shutdown"; text: "@SHUTDOWN@" },
                    Breeze.ActionButton { icon.name: "system-user-prompt"; text: "@OTHER@" }
                ]
            }
        }
    }
    Component.onCompleted: password.forceActiveFocus()
}
'''
CLIENT = r'''
import sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
app = QGuiApplication(sys.argv)
engine = QQmlApplicationEngine()
engine.setProperty("_kirigamiTheme", "org.kde.desktop")
for path in sys.argv[2].split(":"):
    engine.addImportPath(path)
engine.load(QUrl.fromLocalFile(sys.argv[1]))
if not engine.rootObjects():
    print("MOOS_PREVIEW_FAILED", flush=True); sys.exit(2)
print("MOOS_PREVIEW_READY", flush=True)
sys.exit(app.exec())
'''


def no_core() -> None:
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--look", default="org.moos.ui2.bloom")
    ap.add_argument("--lang", default="ar")
    ap.add_argument("--logical", default="1766x1104")
    ap.add_argument("--scale", type=float, default=1.45)
    ap.add_argument("--typed", action="store_true")
    ap.add_argument("--refused", action="store_true")
    args = ap.parse_args()
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    lw, lh = (int(v) for v in args.logical.split("x"))
    scheme, icons, wallpaper = LOOKS[args.look]
    light = "Light" in scheme or "Daylight" in scheme
    arabic = args.lang == "ar"
    words = ({"SLEEP": "علّق", "RESTART": "أعد التّشغيل", "SHUTDOWN": "أطفئ", "OTHER": "مستخدم أخر…",
              "PLACEHOLDER": "كلمة السّر", "NOTICE": "فشل الولوج" if args.refused else ""}
             if arabic else
             {"SLEEP": "Sleep", "RESTART": "Restart", "SHUTDOWN": "Shut Down", "OTHER": "Other…",
              "PLACEHOLDER": "Password", "NOTICE": "Login Failed" if args.refused else ""})
    words["TYPED"] = "secret" if args.typed else ""
    words["DIM"] = "-0.18" if not light else "-0.08"
    words["WALLPAPER"] = str(ROOT / "system_files/usr/share/wallpapers" / wallpaper)
    base = Path(tempfile.mkdtemp(prefix="moos-session-preview."))
    run = base / "run"
    for d in ("home", "config", "cache", "data", "xdg", "run", "imports"):
        (base / d).mkdir(mode=0o700)
    module = base / "imports/org/kde/breeze/components"
    shutil.copytree(MODULE, module)
    for path in (ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components").iterdir():
        if path.suffix in (".qml", ".js"):
            shutil.copy2(path, module / path.name)
    shutil.copy2(SEAM, module / "SessionManagementScreen.qml")
    (module / "qmldir").write_text("\n".join(l for l in (module / "qmldir").read_text().splitlines()
                                             if not l.startswith("prefer ")) + "\n")
    scene = SCENE
    for key, value in words.items():
        scene = scene.replace(f"@{key}@", value)
    (base / "scene.qml").write_text(scene, encoding="utf-8")
    (base / "client.py").write_text(CLIENT, encoding="utf-8")
    cfg = base / "config"
    colors = Path(f"/usr/share/color-schemes/{scheme}.colors")
    if not colors.is_file():
        colors = ROOT / f"system_files/usr/share/color-schemes/{scheme}.colors"
    (cfg / "kdeglobals").write_text(colors.read_text(encoding="utf-8")
        + f"\n[General]\nColorScheme={scheme}\nfont=Meyar Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n"
          f"[KDE]\nLookAndFeelPackage={args.look}\n[Icons]\nTheme={icons}\n", encoding="utf-8")
    (cfg / "plasmarc").write_text(f"[Theme]\nname={scheme}\n", encoding="utf-8")
    pw, ph = round(lw * args.scale), round(lh * args.scale)
    (cfg / "kwinoutputconfig.json").write_text(json.dumps([
        {"name": "outputs", "data": [{"connectorName": "Virtual-0", "scale": args.scale,
                                      "mode": {"basic": {"width": pw, "height": ph, "refreshRate": 60000},
                                               "flags": 1}, "transform": "Normal", "overscan": 0,
                                      "rgbRange": "Automatic", "vrrPolicy": "Never"}]},
        {"name": "setups", "data": [{"lidClosed": False, "outputs": [
            {"enabled": True, "outputIndex": 0, "position": {"x": 0, "y": 0}, "priority": 1,
             "replicationSource": ""}]}]}]), encoding="utf-8")
    bus_conf = base / "bus.conf"
    bus_conf.write_text('<busconfig><type>session</type><listen>unix:path=' + str(run / "bus") +
                        '</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
                        '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
    lang = "ar_SA.UTF-8" if arabic else "en_US.UTF-8"
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("WAYLAND", "DBUS", "XDG_", "QT_", "QML", "KDE", "DISPLAY", "XAUTHORITY",
                                "LANG", "LC_"))}
    env.update(HOME=str(base / "home"), XDG_RUNTIME_DIR=str(run), XDG_CONFIG_HOME=str(cfg),
               XDG_CACHE_HOME=str(base / "cache"), XDG_DATA_HOME=str(base / "data"),
               XDG_CONFIG_DIRS=str(base / "xdg") + ":/etc/xdg",
               XDG_DATA_DIRS=str(ROOT / "system_files/usr/share") + ":/usr/share",
               DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(run / "bus"),
               DBUS_SYSTEM_BUS_ADDRESS="unix:path=" + str(base / "absent"),
               KWIN_WAYLAND_NO_PERMISSION_CHECKS="1", LANG=lang, LC_ALL=lang,
               LANGUAGE="ar" if arabic else "en", QML_DISABLE_DISK_CACHE="1")
    procs = []
    result = {"look": args.look, "lang": args.lang, "logical": [lw, lh], "scale": args.scale}
    sock = "wayland-session-preview"
    try:
        procs.append(subprocess.Popen(["dbus-daemon", "--nofork", "--config-file=" + str(bus_conf)], env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(50):
            if (run / "bus").is_socket():
                break
            time.sleep(0.1)
        procs.append(subprocess.Popen(["kwin_wayland", "--virtual", "--width", str(lw), "--height", str(lh),
                                       "--scale", str(args.scale), "--socket", sock, "--no-lockscreen",
                                       "--no-global-shortcuts", "--no-kactivities"], env=env,
                                      stdout=(base / "kwin.log").open("w"), stderr=subprocess.STDOUT,
                                      preexec_fn=no_core))
        for _ in range(100):
            if (run / sock).is_socket():
                break
            time.sleep(0.1)
        time.sleep(0.6)
        cenv = dict(env, WAYLAND_DISPLAY=sock, QT_QPA_PLATFORM="wayland", QT_QPA_PLATFORMTHEME="kde",
                    QT_QUICK_CONTROLS_STYLE="org.kde.desktop")
        imports = f"{base / 'imports'}:{ROOT / 'system_files/usr/lib64/qt6/qml'}"
        client = subprocess.Popen([sys.executable, "-s", "-B", str(base / "client.py"), str(base / "scene.qml"),
                                   imports], env=cenv, stdout=(base / "client.log").open("w"),
                                  stderr=subprocess.STDOUT, preexec_fn=no_core)
        procs.append(client)
        for _ in range(100):
            text = (base / "client.log").read_text(errors="replace")
            if "MOOS_PREVIEW_READY" in text or "MOOS_PREVIEW_FAILED" in text or client.poll() is not None:
                break
            time.sleep(0.1)
        time.sleep(2.2)
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
        QImage(bytes(data), w, h, stride, QImage.Format(fmt)).copy().save(str(out))
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
        log = (base / "client.log").read_text(errors="replace") if (base / "client.log").exists() else ""
        out.with_suffix(".log").write_text(log)
        shutil.rmtree(base, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("result") == "CAPTURED" else 1


if __name__ == "__main__":
    sys.exit(main())
