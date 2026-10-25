#!/usr/bin/env python3
"""Whole native session template: material, password semantics and original input.

The private module retains the installed Breeze plugin/qmldir and explicitly
selects MoOS's reviewed6.8 variant. An import path alone doesn't do that.
"""
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = Path('/usr/lib64/qt6/qml/org/kde/breeze/components')
REVIEWED = ROOT/'build_files/plasma-seams/6.8/usr/lib64/qt6/qml/org/kde/breeze/components/SessionManagementScreen.qml'


def probe():
    from PySide6.QtCore import QUrl, Qt, QPoint, QEvent, QCoreApplication
    from PySide6.QtGui import QGuiApplication, QKeyEvent
    from PySide6.QtQuick import QQuickItem, QQuickWindow
    from PySide6.QtQml import QQmlEngine, QQmlComponent, QQmlExpression
    from PySide6.QtTest import QTest
    app = QGuiApplication([])
    engine = QQmlEngine(); engine.setProperty('_kirigamiTheme','org.kde.desktop')
    engine.addImportPath(str(ROOT/'system_files/usr/lib64/qt6/qml'))
    engine.addImportPath(os.environ['AUTH_IMPORTS'])
    c = QQmlComponent(engine)
    c.setData(('''import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.breeze.components as Native
Window { id: window; width: '''+os.environ['AUTH_WIDTH']+'''; height: 640; visible: true
 Kirigami.Theme.inherit: false
 Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
 property int submitted: 0
 Native.SessionManagementScreen { id: screen; objectName: "nativeScreen"; anchors.fill: parent
  userListModel: ListModel { ListElement { name: "fixture"; realName: "مستخدم MoOS"; icon: ""; needsPassword: true } }
  userListCurrentIndex: 0
  RowLayout {
   C.TextField { id: password; objectName: "nativePassword"; Layout.fillWidth: true; echoMode: TextInput.Password
    placeholderText: "كلمة المرور"; onAccepted: window.submitted++ }
   C.Button { objectName: "nativeSubmit"; text: "دخول"; onClicked: window.submitted++ }
  }
 }
}''').encode(),QUrl('file:///native-auth-proof.qml'))
    window = c.create()
    if os.environ.get('AUTH_BROKEN') == 'type':
        assert not window and any('MoOSBrokenAuthenticationType' in e.toString() for e in c.errors())
        print('MOOS_NATIVE_AUTH_BROKEN_TYPE_REFUSED',flush=True);return
    assert window,[e.toString() for e in c.errors()]
    assert isinstance(window,QQuickWindow)
    QTest.qWait(600)
    screen = window.findChild(QQuickItem,'nativeScreen')
    for _ in range(80):
        if screen.property('arrival') >= .999: break
        QTest.qWait(20)
    assert screen.property('arrival') >= .999,'native arrival did not settle'
    card = screen.findChild(QQuickItem,'moosAuthenticationCard')
    assert card and card.isVisible()
    base = QQmlEngine.contextForObject(card).baseUrl().toLocalFile()
    assert base == os.environ['AUTH_SOURCE'],('wrong loaded session module',base)
    assert card.property('surfaceColor').name() == os.environ['AUTH_BG'] and card.property('fillOpacity') >= .9, 'MOOS_AUTH_MATERIAL_MISMATCH'
    assert card.opacity() >= .99,'native authentication plate remained invisible'
    # Inspect actual painted ink under an interior gutter, not just fitting
    # outer bounds or a ready property. This fixture has a white window behind
    # the working sheet; native software fallback can be fully opaque.
    pixels=window.grabWindow();assert not pixels.isNull()
    point=card.mapToScene(__import__('PySide6.QtCore',fromlist=['QPointF']).QPointF(14,card.height()*.70))
    pixel=pixels.pixelColor(round(point.x()*window.devicePixelRatio()),round(point.y()*window.devicePixelRatio()))
    expected=card.property('surfaceColor')
    target=[round(channel*.94+255*.06) for channel in (expected.red(),expected.green(),expected.blue())]
    assert max(abs(a-b) for a,b in zip((pixel.red(),pixel.green(),pixel.blue()),target))<=25,('working sheet did not paint',pixel.name(),expected.name())
    field = window.findChild(QQuickItem,'nativePassword'); button = window.findChild(QQuickItem,'nativeSubmit')
    expression = QQmlExpression(QQmlEngine.contextForObject(field),field,'echoMode === TextInput.Password && text === ""')
    assert expression.evaluate()[0] is True,'password semantics changed on adoption'
    window.requestActivate(); field.forceActiveFocus(); QTest.qWait(50)
    assert field.hasActiveFocus(), 'native field cannot receive keyboard focus'
    for char in 'fixture-only':
        QCoreApplication.sendEvent(window,QKeyEvent(QEvent.KeyPress,0,Qt.NoModifier,char))
        QCoreApplication.sendEvent(window,QKeyEvent(QEvent.KeyRelease,0,Qt.NoModifier,char))
    assert field.property('text') == 'fixture-only',repr(field.property('text'))
    QTest.keyClick(window,Qt.Key_Return); assert window.property('submitted') == 1
    point = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
    assert window.property('submitted') == 2,'native submit handler was replaced'
    assert field.property('text') == 'fixture-only'
    for item in (field,button):
        position = item.mapToScene(item.boundingRect().topLeft())
        assert 0 <= position.x() and position.x()+item.width() <= window.width()+1
        assert card.y()-1 <= position.y() and position.y()+item.height() <= card.y()+card.height()+1
    print('MOOS_NATIVE_AUTH_MATERIAL_INPUT_PASS '+json.dumps(dict(source=base,bg=card.property('surfaceColor').name())),flush=True)


class NativeAuthenticationMaterial(unittest.TestCase):
    def test_selected_material_and_native_input_in_the_reviewed_module(self):
        if not (MODULE/'qmldir').exists(): self.skipTest('installed native Breeze module unavailable')
        try: import PySide6
        except ImportError: self.skipTest('native Qt runtime unavailable')
        profiles = json.loads((ROOT/'artwork/moos-design/theme-profiles.json').read_text())['profiles']
        with tempfile.TemporaryDirectory(prefix='moos-native-auth-') as td:
            base = Path(td); imports = base/'imports'; module = imports/'org/kde/breeze/components'
            shutil.copytree(MODULE,module)
            source = ROOT/'system_files/usr/lib64/qt6/qml/org/kde/breeze/components'
            for path in source.iterdir():
                if path.suffix in ('.qml','.js'): shutil.copy2(path,module/path.name)
            target = module/'SessionManagementScreen.qml'; shutil.copy2(REVIEWED,target)
            manifest = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in module.iterdir() if p.is_file()}
            self.assertEqual(manifest['SessionManagementScreen.qml'],hashlib.sha256(REVIEWED.read_bytes()).hexdigest())
            for i, profile in enumerate(profiles):
                config = base/'config';config.mkdir(exist_ok=True)
                colors = ROOT/'system_files/usr/share/color-schemes'/(profile['scheme']+'.colors')
                palette = configparser.ConfigParser(interpolation=None);palette.read(colors)
                (config/'kdeglobals').write_text('[General]\nColorScheme='+profile['scheme']+'\n[KDE]\nLookAndFeelPackage='+profile['id']+'\n[Icons]\nTheme='+profile['icons']+'\n')
                (config/'plasmarc').write_text('[Theme]\nname='+profile['style']+'\n')
                # Each subprocess starts from all matched native selectors.
                env = os.environ | dict(HOME=td,XDG_CONFIG_HOME=str(config),XDG_CONFIG_DIRS=str(config),
                    XDG_DATA_HOME=str(base/'data'),XDG_CACHE_HOME=str(base/'cache'),
                    XDG_DATA_DIRS=str(ROOT/'system_files/usr/share')+':/usr/share',
                    DBUS_SESSION_BUS_ADDRESS='unix:path='+td+'/absent',QT_QPA_PLATFORM='offscreen',
                    QT_QUICK_BACKEND='software',QML_DISABLE_DISK_CACHE='1',AUTH_IMPORTS=str(imports),
                    AUTH_SOURCE=str(target),AUTH_WIDTH='360' if i%2 else '1280',
                    AUTH_BG='#'+''.join(f'{int(v):02x}' for v in palette['Colors:Window']['BackgroundNormal'].split(',')))
                env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
                before = {p.name:p.read_bytes() for p in config.iterdir()}
                for broken in (None,'material','role','type') if i == 0 else (None,):
                    text = REVIEWED.read_text()
                    if broken == 'material': text=text.replace('fillOpacity: 0.94','fillOpacity: 0.58')
                    if broken == 'role': text=text.replace('Kirigami.Theme.colorSet: Kirigami.Theme.Window','Kirigami.Theme.colorSet: Kirigami.Theme.Complementary',1)
                    if broken == 'type': text=text.replace('FocusScope {','MoOSBrokenAuthenticationType {',1)
                    target.write_text(text)
                    case = env | ({'AUTH_BROKEN':broken} if broken else {})
                    result = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--probe'],env=case,capture_output=True,text=True,timeout=12)
                    log = result.stdout+result.stderr
                    if broken in ('material','role'):
                        self.assertNotEqual(result.returncode,0);self.assertIn('MOOS_AUTH_MATERIAL_MISMATCH',log)
                    else:
                        self.assertEqual(result.returncode,0,profile['id']+'\n'+log[-3500:])
                        self.assertIn('MOOS_NATIVE_AUTH_BROKEN_TYPE_REFUSED' if broken else 'MOOS_NATIVE_AUTH_MATERIAL_INPUT_PASS',log)
                    self.assertEqual(before,{p.name:p.read_bytes() for p in config.iterdir()})


if __name__ == '__main__':
    if '--probe' in sys.argv: probe()
    else: unittest.main()
