#!/usr/bin/env python3
"""Native source-card input: measured state, pending/failure, AR/EN at 360px."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class WalletSettings(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PySide6"), "native PySide6 unavailable")
    def test_pointer_keyboard_pending_failure_and_partial_preference(self):
        for language in ("ar", "en"):
            with self.subTest(language=language), tempfile.TemporaryDirectory(prefix="moos-wallet-card-") as tmp:
                root=Path(tmp)
                for n in ("home", "run", "config", "cache", "data"): (root/n).mkdir(mode=0o700)
                env={k:v for k,v in os.environ.items() if k not in ("DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY")}
                env.update(HOME=str(root/"home"), XDG_RUNTIME_DIR=str(root/"run"), XDG_CONFIG_HOME=str(root/"config"), XDG_CACHE_HOME=str(root/"cache"), XDG_DATA_HOME=str(root/"data"), QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", LANG="ar_SA.UTF-8" if language=="ar" else "en_US.UTF-8", LANGUAGE=language)
                (root/"bus.conf").write_text(f'<busconfig><type>session</type><listen>unix:path={root}/run/bus</listen><auth>EXTERNAL</auth><policy context="default"><allow user="{os.getuid()}"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
                bus=subprocess.Popen(["dbus-daemon", "--config-file="+str(root/"bus.conf"), "--nofork", "--print-address=1"], env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                try:
                    env["DBUS_SESSION_BUS_ADDRESS"]=bus.stdout.readline().strip()
                    result=subprocess.run([sys.executable, str(Path(__file__).resolve()), "--case"], env=env, capture_output=True, text=True, timeout=25)
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertIn("MOOS_WALLET_CARD_PASS", result.stdout)
                finally: bus.terminate(); bus.wait(timeout=5); bus.stdout.close()


def native_case():
    from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QPoint, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView, QQuickItem
    from PySide6.QtTest import QTest
    class Backend(QObject):
        changed=Signal()
        jobFinished=Signal(str,int,str)
        def __init__(self):
            super().__init__(); self.value={"wallet":{"known":True,"available":True,"enabled":False,"active":False,"ready":False,"choice":"off"}}; self.calls=[]; self.reject=False
        @Property('QVariantMap', notify=changed)
        def status(self): return self.value
        @Property(bool, notify=changed)
        def statusValid(self): return True
        @Slot(str,str,result=QObject)
        def runFixed(self, verb, arg):
            self.calls.append((verb,arg)); return None if self.reject else self
        @Slot()
        def refresh(self): pass
        def complete(self,on,exit=0):
            if exit==0:
                self.value={"wallet":dict(self.value["wallet"],enabled=on,active=on,ready=on,choice="on" if on else "off")}; self.changed.emit()
            self.jobFinished.emit("wallet-on" if on else "wallet-off",exit,"")
    app=QGuiApplication([]); backend=Backend(); view=QQuickView()
    view.engine().addImportPath(str(ROOT/"system_files/usr/lib64/qt6/qml"))
    view.rootContext().setContextProperty("walletBackend",backend)
    path=Path(os.environ["XDG_CONFIG_HOME"])/"card.qml"
    common=(ROOT/"moos-settings-kcm/common").as_uri()
    path.write_text('import QtQuick\nimport QtQuick.Layouts\nimport '+repr(common)+' as Moos\nItem { width: 360; height: 320; ColumnLayout { anchors.fill: parent; anchors.margins: 12; Moos.MoosWalletCard { objectName: "card"; Layout.fillWidth: true; backend: walletBackend } Item { Layout.fillHeight: true } } }')
    view.setSource(QUrl.fromLocalFile(str(path))); assert view.status()==QQuickView.Ready, view.errors()
    view.show(); view.requestActivate(); QTest.qWait(150)
    card=view.rootObject().findChild(QQuickItem,"card")
    row=card.findChild(QQuickItem,"moosWalletSwitch")
    assert row and row.width()>=300 and row.height()>=44
    assert row.property("text")==("محفظة كلمات المرور" if os.environ["LANGUAGE"]=="ar" else "Password wallet")
    point=row.mapToScene(row.boundingRect().center()).toPoint()
    QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,point); QTest.qWait(20)
    assert backend.calls==[("wallet-on","")], backend.calls
    assert card.property("busy") and not row.property("on")
    QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,point)
    assert len(backend.calls)==1, "pending switch must not start duplicate work"
    backend.complete(True); QTest.qWait(20)
    assert row.property("on") and not card.property("busy")
    row.forceActiveFocus(); QTest.keyClick(view,Qt.Key_Space); QTest.qWait(20)
    assert backend.calls[-1]==("wallet-off","")
    backend.complete(False,69); QTest.qWait(20)
    assert row.property("on") and card.property("errorText") and not card.property("busy")
    backend.reject=True; QTest.keyClick(view,Qt.Key_Space); QTest.qWait(20)
    assert not card.property("busy") and card.property("errorText")
    backend.reject=False
    backend.value={"wallet":dict(backend.value["wallet"],known=False)}; backend.changed.emit(); QTest.qWait(20)
    assert not row.isEnabled()
    # A partial, readable KDE preference can still be explicitly turned off.
    assert card.request(False) is None
    assert backend.calls[-1]==("wallet-off","") and card.property("busy")
    backend.complete(False); QTest.qWait(20)
    view.close(); print("MOOS_WALLET_CARD_PASS "+os.environ["LANGUAGE"])

if __name__=="__main__":
    if sys.argv[1:]==["--case"]: native_case()
    else: unittest.main(verbosity=2)
