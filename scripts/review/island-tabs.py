#!/usr/bin/env python3
"""Render and exercise the production Island tab strip on native Qt, in private state.

Run under dbus-run-session on a desktop development host with PySide6 and Plasma QML:
  dbus-run-session -- python3 scripts/review/island-tabs.py OUT_DIR
  ... --source /path/to/old/main.qml  # negative control
This is tab-component evidence, not a complete installed desktop review.
"""
import argparse
import configparser
import json
import os
from pathlib import Path
import tempfile
import sys
import subprocess
import signal

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--source", type=Path, default=ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui/main.qml")
parser.add_argument("--motion", choices=("normal", "reduced"), default="normal")
parser.add_argument("--private-bus", action="store_true", help=argparse.SUPPRESS)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
if not args.private_bus:
    # A fresh default session bus can still activate the host's portal/KDE
    # services. This component needs no services: use an empty activation set
    # and bound the whole child group, including synchronous Qt initialization.
    with tempfile.TemporaryDirectory(prefix="moos-island-bus-") as bus_dir:
        config = Path(bus_dir) / "bus.conf"
        config.write_text('''<busconfig><type>session</type>
<listen>unix:tmpdir=''' + bus_dir + '''</listen><auth>EXTERNAL</auth>
<policy context="default"><allow send_destination="*" eavesdrop="true"/><allow eavesdrop="true"/><allow own="*"/></policy>
</busconfig>''')
        command = ["dbus-run-session", "--config-file", str(config), "--", sys.executable,
                   str(Path(__file__).resolve()), str(args.output.resolve()),
                   "--source", str(args.source.resolve()), "--motion", args.motion, "--private-bus"]
        child = subprocess.Popen(command, start_new_session=True)
        try:
            result = child.wait(timeout=35)
        except subprocess.TimeoutExpired:
            print("Island review child exceeded its initialization deadline",file=sys.stderr)
            os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=3)
            result = 1
    raise SystemExit(result)
private = tempfile.TemporaryDirectory(prefix="moos-island-tabs-")
base = Path(private.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
    path = base / key
    path.mkdir(mode=0o700)
    os.environ[key] = str(path)
for key in ("DISPLAY", "WAYLAND_DISPLAY", "KDE_FULL_SESSION", "SESSION_MANAGER",
            "QML_IMPORT_PATH", "QML2_IMPORT_PATH", "QT_PLUGIN_PATH"):
    os.environ.pop(key, None)
# A private bus must be supplied by the caller; an owner's session is never accepted.
if os.environ.get("DBUS_SESSION_BUS_ADDRESS", "").startswith("unix:path=/run/user/"):
    raise SystemExit("Run under dbus-run-session; do not use the desktop bus")
os.environ.update(QT_QPA_PLATFORM="offscreen", QT_QPA_PLATFORMTHEME="", QT_QUICK_BACKEND="software", QML_DISABLE_DISK_CACHE="1",
                  XDG_DATA_DIRS=f"{ROOT}/system_files/usr/share:/usr/share",
                  XDG_CONFIG_DIRS=f"{ROOT}/system_files/etc/xdg:/etc/xdg")
(base / "XDG_CONFIG_HOME" / "kdeglobals").write_text(
    "[KDE]\nAnimationDurationFactor=" + ("0" if args.motion == "reduced" else "1") + "\n")
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QKeyEvent, QPalette
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

source = args.source.read_text()
start = source.index("        PC3.TabBar {", source.index("fullRepresentation:"))
end = source.index("\n        ColumnLayout {", start)
strip = source[start:end]
details = source[source.index("    property string detailContext:"):source.index("    function openDetails()")]
# Begin on a present domain as openDetails()/a pointer selection would. A raw
# default of "remote" with no Remote is not the opened-popup precondition; test
# missing/retired domains after the real controls have loaded instead.
details = details.replace('property string detailContext: "remote"',
                          'property string detailContext: "privacy"', 1)
print("Starting isolated Qt component review",flush=True)
app = QApplication([])
print("Qt application ready",flush=True)
engines = []
records = []
failed = []
domains = ("remote", "privacy", "store", "moai", "media")
detail_flags = ("showRemoteDetails", "showPrivacyDetails", "showStoreDetails", "showMoaiDetails", "showMediaDetails")

# Apply actual shipped light/dark ink and surfaces to this private application.
def palette(light):
    scheme = "MoOSUI2AuroraLight" if light else "MoOSUI2Aurora"
    ini = configparser.ConfigParser()
    ini.read(ROOT / f"system_files/usr/share/color-schemes/{scheme}.colors")
    pal = QPalette()
    for role, group, key in ((QPalette.Window, "Colors:Window", "BackgroundNormal"),
                             (QPalette.WindowText, "Colors:Window", "ForegroundNormal"),
                             (QPalette.Text, "Colors:View", "ForegroundNormal"),
                             (QPalette.ButtonText, "Colors:Button", "ForegroundNormal"),
                             (QPalette.Button, "Colors:Button", "BackgroundNormal"),
                             (QPalette.Base, "Colors:View", "BackgroundNormal")):
        pal.setColor(role, QColor(*map(int, ini[group][key].split(","))))
    app.setPalette(pal)
    return pal.color(QPalette.Window).name()

cases = [(rtl, all_domains, light) for rtl in (True, False) for all_domains in (False, True) for light in (False, True)]

def run_case(index):
    if index == len(cases):
        (args.output / "measurements.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"samples":len(records), "failures":failed}, ensure_ascii=False))
        app.exit(bool(failed))
        return
    rtl, all_domains, light = cases[index]
    app.setLayoutDirection(Qt.RightToLeft if rtl else Qt.LeftToRight)
    bg = palette(light)
    qml = '''import QtQuick
import QtQuick.Window
import org.kde.plasma.components as PC3
Window {
 id:root; width:420; height:150; visible:false; color:"%s"
 property bool active:true
 property bool rtl:%s; property bool remotePresent:%s; property bool privacyPresent:true
 property bool storeJobPresent:%s; property bool moaiJobPresent:%s; property bool mediaPresent:true
 property string privacyIcon:"view-private"; property string storeJobIcon:"package"; property string moaiJobIcon:"moos-mira"; property string playerIcon:"media-playback-start"
 property QtObject design:QtObject { property int space4:16 }
 function local(ar,en) {return rtl?ar:en}
''' % (bg, str(rtl).lower(), str(all_domains).lower(), str(all_domains).lower(), str(all_domains).lower()) + details + strip + "\n}"
    engine = QQmlApplicationEngine()
    print(f"Loading Island sample {index}",flush=True)
    engine.loadData(qml.encode(), QUrl.fromLocalFile(str(base / f"tabs-{index}.qml")))
    engines.append(engine)
    if not engine.rootObjects():
        failed.append(f"case {index}: QML did not load")
        QTimer.singleShot(0, lambda:run_case(index+1))
        return
    window = engine.rootObjects()[0]
    print(f"Island sample {index} loaded",flush=True)
    window.show()
    def capture():
        tabs = []
        bars = []
        def walk(item):
            if isinstance(item, QQuickItem):
                kind = item.metaObject().className()
                if kind.startswith("TabBar"):
                    bars.append(item)
                if kind.startswith("TabButton"):
                    tabs.append(item)
                for child in item.childItems():
                    walk(child)
        walk(window.contentItem())
        data = {"rtl":rtl, "all_domains":all_domains, "light":light,
                "motion":args.motion, "device_pixel_ratio":window.devicePixelRatio(),
                "bar_height":bars[0].height(),
                "tabs":[{"text":t.property("text"), "width":t.width(), "height":t.height(), "visible":t.isVisible()} for t in tabs]}
        records.append(data)
        if len(tabs) != 5 or len(bars) != 1:
            failed.append(f"case {index}: missing production tab controls")
            app.exit(1)
            return
        if bars[0].height() > 52:
            failed.append(f"case {index}: strip expanded to {bars[0].height()}")
        for tab in tabs:
            if not tab.isVisible() and tab.width() > 0:
                failed.append(f"case {index}: hidden tab reserves width")
            if tab.isVisible():
                labels = [c for c in tab.childItems() if c.property("text")]
                if labels and labels[0].property("lineCount") != 1:
                    failed.append(f"case {index}: label wraps")
        # Exercise a real pointer on the component. Both active tabs fit in the two-domain case.
        if not all_domains and bars[0].height() <= 52:
            media = tabs[4]
            pos = media.mapToItem(window.contentItem(), media.width()/2, media.height()/2)
            QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(pos.x()), round(pos.y())))
            if window.property("detailContext") != "media":
                failed.append(f"case {index}: media tab click did not switch domain")
        # Deliver real Qt keys to every visible production control. JavaScript
        # routing alone cannot see the native TabBar's hidden-child navigation.
        visible = [i for i,t in enumerate(tabs) if t.isVisible()]
        data["keyboard"] = []
        for initial in visible:
            for key_name,key,delta in (("left",Qt.Key_Left,1 if rtl else -1),
                                       ("right",Qt.Key_Right,-1 if rtl else 1)):
                window.setProperty("detailContext",domains[initial])
                tabs[initial].forceActiveFocus(Qt.TabFocusReason)
                QTest.qWait(20)
                QTest.keyClick(window,key)
                QTest.qWait(30)
                expected = visible[(visible.index(initial)+delta) % len(visible)]
                focused = [i for i,t in enumerate(tabs) if t.hasActiveFocus()]
                shown = [i for i,flag in enumerate(detail_flags) if window.property(flag)]
                selected = bars[0].property("currentIndex")
                data["keyboard"].append({"from":initial,"key":key_name,
                                         "focus":focused,"selected":selected,"shown":shown})
                if focused != [expected] or selected != expected or shown != [expected]:
                    failed.append(f"case {index}: {key_name} from {initial} lost visible focus/domain")
            for key_name,key in (("space",Qt.Key_Space),("return",Qt.Key_Return),("enter",Qt.Key_Enter)):
                window.setProperty("detailContext",domains[visible[(visible.index(initial)+1)%len(visible)]])
                tabs[initial].forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(window,key)
                QTest.qWait(30)
                if bars[0].property("currentIndex") != initial or not window.property(detail_flags[initial]):
                    failed.append(f"case {index}: {key_name} did not activate {initial}")
            for key_name,key in (("return",Qt.Key_Return),("enter",Qt.Key_Enter)):
                other = visible[(visible.index(initial)+1)%len(visible)]
                window.setProperty("detailContext",domains[other])
                tabs[initial].forceActiveFocus(Qt.TabFocusReason)
                QCoreApplication.sendEvent(window,QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier,"",True,1))
                QTest.qWait(20)
                if bars[0].property("currentIndex") != other:
                    failed.append(f"case {index}: held {key_name} repeated tab activation")
            for key_name,key in (("tab",Qt.Key_Tab),("backtab",Qt.Key_Backtab)):
                tabs[initial].forceActiveFocus(Qt.TabFocusReason)
                QTest.keyClick(window,key)
                QTest.qWait(20)
                focused = [i for i,t in enumerate(tabs) if t.hasActiveFocus()]
                if len(focused) != 1 or focused[0] not in visible:
                    failed.append(f"case {index}: {key_name} focused a hidden/missing tab")
        window.setProperty("detailContext","privacy")
        tabs[1].forceActiveFocus(Qt.TabFocusReason)
        QTest.qWait(500)
        name = f"{'ar' if rtl else 'en'}-{'five' if all_domains else 'two'}-{'light' if light else 'dark'}.png"
        window.grabWindow().save(str(args.output / name))
        # A completed context can disappear while two other domains remain.
        if all_domains:
            window.setProperty("detailContext","store")
            window.setProperty("storeJobPresent",False)
            QTest.qWait(20)
            shown = [i for i,flag in enumerate(detail_flags) if window.property(flag)]
            data["retired_context"] = {"selected":bars[0].property("currentIndex"),"shown":shown}
            if len(shown) != 1 or shown[0] not in (0,1,3,4):
                failed.append(f"case {index}: finished Store left a blank context")
        for field in ("remotePresent","privacyPresent","storeJobPresent","moaiJobPresent","mediaPresent"):
            window.setProperty(field,False)
        QTest.qWait(20)
        if bars[0].property("currentIndex") != -1:
            failed.append(f"case {index}: empty strip selected an absent context")
        window.hide()
        QTimer.singleShot(0, lambda:run_case(index+1))
    QTimer.singleShot(250, capture)

QTimer.singleShot(0, lambda:run_case(0))
# The command's timeout also bounds a synchronous QML load; this timer bounds
# an event-loop stall and records it rather than leaving a review process live.
def deadline():
    print("Island review exceeded its 30-second deadline",file=sys.stderr)
    app.exit(1)
QTimer.singleShot(30000, deadline)
raise SystemExit(app.exec())
