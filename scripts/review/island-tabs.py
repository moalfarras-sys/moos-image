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

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--source", type=Path, default=ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui/main.qml")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
private = tempfile.TemporaryDirectory(prefix="moos-island-tabs-")
base = Path(private.name)
for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR"):
    path = base / key
    path.mkdir(mode=0o700)
    os.environ[key] = str(path)
for key in ("DISPLAY", "WAYLAND_DISPLAY", "KDE_FULL_SESSION", "SESSION_MANAGER"):
    os.environ.pop(key, None)
# A private bus must be supplied by the caller; an owner's session is never accepted.
if os.environ.get("DBUS_SESSION_BUS_ADDRESS", "").startswith("unix:path=/run/user/"):
    raise SystemExit("Run under dbus-run-session; do not use the desktop bus")
os.environ.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QML_DISABLE_DISK_CACHE="1",
                  XDG_DATA_DIRS=f"{ROOT}/system_files/usr/share:/usr/share",
                  XDG_CONFIG_DIRS=f"{ROOT}/system_files/etc/xdg:/etc/xdg")
from PySide6.QtCore import QPoint, QTimer, QUrl, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

source = args.source.read_text()
start = source.index("        PC3.TabBar {", source.index("fullRepresentation:"))
end = source.index("\n        ColumnLayout {", start)
strip = source[start:end]
app = QApplication([])
engines = []
records = []
failed = []

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
    bg = palette(light)
    qml = '''import QtQuick
import QtQuick.Window
import org.kde.plasma.components as PC3
Window {
 id:root; width:420; height:150; visible:true; color:"%s"
 property bool active:true; property bool multipleContexts:true
 property bool rtl:%s; property bool remotePresent:%s; property bool privacyPresent:true
 property bool storeJobPresent:%s; property bool moaiJobPresent:%s; property bool mediaPresent:true
 property string detailContext:"privacy"
 property bool showRemoteDetails:detailContext=="remote"; property bool showPrivacyDetails:detailContext=="privacy"
 property bool showStoreDetails:detailContext=="store"; property bool showMoaiDetails:detailContext=="moai"
 property string privacyIcon:"view-private"; property string storeJobIcon:"package"; property string moaiJobIcon:"moos-mira"; property string playerIcon:"media-playback-start"
 property QtObject design:QtObject { property int space4:16 }
 function local(ar,en) {return rtl?ar:en}
''' % (bg, str(rtl).lower(), str(all_domains).lower(), str(all_domains).lower(), str(all_domains).lower()) + strip + "\n}"
    engine = QQmlApplicationEngine()
    engine.loadData(qml.encode(), QUrl.fromLocalFile(str(base / f"tabs-{index}.qml")))
    engines.append(engine)
    if not engine.rootObjects():
        failed.append(f"case {index}: QML did not load")
        QTimer.singleShot(0, lambda:run_case(index+1))
        return
    window = engine.rootObjects()[0]
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
                "bar_height":bars[0].height(),
                "tabs":[{"text":t.property("text"), "width":t.width(), "height":t.height(), "visible":t.isVisible()} for t in tabs]}
        records.append(data)
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
        name = f"{'ar' if rtl else 'en'}-{'five' if all_domains else 'two'}-{'light' if light else 'dark'}.png"
        window.grabWindow().save(str(args.output / name))
        window.hide()
        QTimer.singleShot(0, lambda:run_case(index+1))
    QTimer.singleShot(250, capture)

QTimer.singleShot(0, lambda:run_case(0))
raise SystemExit(app.exec())
