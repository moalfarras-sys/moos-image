#!/usr/bin/env python3
"""Real Qt component/input controls; private offscreen state, never the live panel."""
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui/MediaControl.qml"


def probe():
    from PySide6.QtCore import QPoint, Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    app = QGuiApplication([])
    engine = QQmlApplicationEngine()
    engine.setProperty("_kirigamiTheme", "org.kde.desktop")
    qml = Path(sys.argv[2])
    engine.load(QUrl.fromLocalFile(str(qml)))
    assert engine.rootObjects(), "component did not load"
    win = engine.rootObjects()[0]
    button = win.findChild(QQuickItem, "button")
    assert button is not None
    assert QTest.qWaitForWindowExposed(win, 5000)
    win.grabWindow(); QTest.qWait(100)
    tablet = os.environ["KDE_KIRIGAMI_TABLET_MODE"] == "1"
    slot = int(os.environ["PROBE_SLOT"])
    expected = max(slot, 44) if tablet else slot
    assert win.property("tablet") == tablet, "real Kirigami tablet-mode environment was not selected"
    if os.environ.get("PROBE_OLD") == "1":
        # The former 34px control cannot receive input inside the required
        # 44px target's outer edge. This is a real dispatched touch, not math.
        edge = QPoint(20 + expected-1, 20 + expected//2)
        n = win.property("activations")
        touch = QTest.createTouchDevice()
        QTest.touchEvent(win,touch).press(0,edge,win).commit()
        QTest.touchEvent(win,touch).release(0,edge,win).commit()
        QTest.qWait(30)
        assert win.property("activations") == n, "old edge unexpectedly activated"
        print("OLD_EDGE_TOUCH_MISSED", flush=True)
    assert abs(button.width()-expected)<.1 and abs(button.height()-expected)<.1, f"target geometry {button.width()}x{button.height()}, expected {expected}"
    # Plate retains the desktop slot while only the actual button target grows.
    plate = button.property("background").childItems()[0]
    assert abs(plate.width()-slot)<.1 and abs(plate.height()-slot)<.1
    glyph=button.property("contentItem").childItems()[0]
    assert glyph.width()==(26 if slot==52 else 18), "glyph geometry changed"
    def count(): return win.property("activations")
    edge = QPoint(20 + expected-1, 20 + expected//2)
    n = count(); QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, edge); assert count()==n+1, "edge click missed"
    touch = QTest.createTouchDevice()
    n = count(); QTest.touchEvent(win,touch).press(0,edge,win).commit(); QTest.qWait(20)
    QTest.touchEvent(win,touch).release(0,edge,win).commit(); QTest.qWait(30)
    assert count()==n+1, "edge touch missed"
    button.forceActiveFocus()
    for key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
        n=count(); QTest.keyClick(win,key); assert count()==n+1, f"keyboard {key} missed"
    for prop in ("controlEnabled", "revealed"):
        button.setProperty(prop,False); QTest.qWait(30); n=count()
        QTest.mouseClick(win,Qt.LeftButton,Qt.NoModifier,edge)
        QTest.touchEvent(win,touch).press(0,edge,win).commit(); QTest.touchEvent(win,touch).release(0,edge,win).commit()
        QTest.keyClick(win,Qt.Key_Return); QTest.qWait(20)
        assert count()==n, f"{prop}=false still activated"
        button.setProperty(prop,True); QTest.qWait(250)
    assert win.property("motionDuration") == (1 if os.environ["PROBE_FACTOR"]=="0" else 200), "KDE motion policy not effective"
    if os.environ["PROBE_FACTOR"]=="0":
        assert not button.property("motionEnabled")
        QTest.mousePress(win,Qt.LeftButton,Qt.NoModifier,edge); QTest.qWait(20)
        assert not button.property("settling"), "reduced motion still animates"
        QTest.mouseRelease(win,Qt.LeftButton,Qt.NoModifier,edge)
    print("ISLAND_TOUCH_PROOF " + json.dumps(dict(tablet=tablet, slot=slot, target=expected, controls="edge mouse/touch; Return/Enter/Space; hidden/disabled; motion")),flush=True)


class NativeTouchTarget(unittest.TestCase):
    def run_case(self, tablet, slot, factor, old=False):
        with tempfile.TemporaryDirectory(prefix="moos-island-touch-") as tmp:
            work=Path(tmp)
            for name in ("home","config","cache","data","runtime"):
                (work/name).mkdir(mode=0o700)
            (work/"config/kdeglobals").write_text(f"[KDE]\nAnimationDurationFactor={factor}\n")
            source=COMPONENT.read_text()
            if old:
                source=source.replace("implicitWidth: targetSize * revealProgress", "implicitWidth: slotSize * revealProgress").replace("implicitHeight: targetSize", "implicitHeight: slotSize")
            (work/"MediaControl.qml").write_text(source)
            (work/"probe.qml").write_text('''import QtQuick
import org.kde.kirigami as Kirigami
Window {
 id: fixture
 width: 160; height: 120; visible: true
 property bool tablet: Kirigami.Settings.tabletMode
 property int motionDuration: Kirigami.Units.longDuration
 property int activations: 0
 MediaControl { objectName: "button"; x:20; y:20; slotSize: '''+str(slot)+'''; primary: '''+str(slot==52).lower()+'''; label: "تشغيل"; onActivated: fixture.activations++ }
}''')
            bus = work/"bus.conf"
            bus.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(work/'runtime')+'</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*" eavesdrop="true"/><allow eavesdrop="true"/><allow own="*"/></policy></busconfig>')
            env={"PATH":"/usr/bin:/usr/sbin", "LANG":"C.UTF-8", "HOME":str(work/"home"),
                 "XDG_CONFIG_HOME":str(work/"config"),"XDG_CONFIG_DIRS":str(work/"config"),
                 "XDG_CACHE_HOME":str(work/"cache"),"XDG_DATA_HOME":str(work/"data"),
                 "XDG_RUNTIME_DIR":str(work/"runtime"),"DBUS_SESSION_BUS_ADDRESS":"unix:path="+str(work/"runtime/absent-bus"),
                 "QT_QPA_PLATFORM":"offscreen","QT_QUICK_BACKEND":"software","QT_QPA_PLATFORMTHEME":"kde",
                 "QT_QUICK_CONTROLS_STYLE":"Basic","QML_DISABLE_DISK_CACHE":"1","QT_FORCE_STDERR_LOGGING":"1",
                 "QML_IMPORT_PATH":str(ROOT/"system_files/usr/lib64/qt6/qml"),
                 "KDE_KIRIGAMI_TABLET_MODE":str(int(tablet)),"PROBE_SLOT":str(slot),"PROBE_FACTOR":str(factor),"PROBE_OLD":str(int(old))}
            command=["dbus-run-session","--config-file",str(bus),"--",sys.executable,str(Path(__file__).resolve()),"--probe",str(work/"probe.qml")]
            child=subprocess.Popen(command,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            try:
                stdout,stderr=child.communicate(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try: child.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL);child.communicate(timeout=3)
                self.fail("private component fixture timed out")
            result=subprocess.CompletedProcess(command,child.returncode,stdout,stderr)
            if old:
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn("OLD_EDGE_TOUCH_MISSED",result.stdout)
                self.assertIn("target geometry 34.0x34.0, expected 44",result.stderr)
            else:
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn("ISLAND_TOUCH_PROOF ",result.stdout)
                self.assertNotRegex(result.stderr,r"(?i)(failed to load|referenceerror|typeerror|syntaxerror|cannot assign|binding loop|module .*not installed)")
            if os.environ.get("MOOS_TOUCH_PROOF_DIR"):
                proof=Path(os.environ["MOOS_TOUCH_PROOF_DIR"]);proof.mkdir(parents=True,exist_ok=True)
                (proof/f"tablet{int(tablet)}-slot{slot}-factor{factor}-old{int(old)}.json").write_text(json.dumps(dict(exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2)+"\n")
    def test_native_geometry_input_and_motion(self):
        for tablet in (False,True):
            for slot in (34,40,52):
                for factor in (0,1):
                    with self.subTest(tablet=tablet,slot=slot,factor=factor): self.run_case(tablet,slot,factor)
    def test_old_compact_geometry_rejects_tablet_contract(self):
        self.run_case(True,34,0,old=True)

if __name__ == "__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--probe": probe()
    else: unittest.main()
