#!/usr/bin/env python3
"""Native Qt input and text bounds for the Settings front door.

This complements the installed KCM journey; it is not physical-touch or whole
System Settings acceptance. No owner bus, input device or configuration is used.
"""
from pathlib import Path
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def native_driver():
    from PySide6.QtCore import QObject, QPoint, Qt, QUrl, SIGNAL, qInstallMessageHandler
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest

    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(str(ROOT / 'system_files/usr/lib64/qt6/qml'))
    component = QQmlComponent(engine)
    common = (ROOT / 'moos-settings-kcm/common').as_uri()
    component.setData(('''import QtQuick
import org.moos.ui as MoUI
import "''' + common + '''" as Settings
Item {
    LayoutMirroring.enabled: MoUI.Locale.rtl
    LayoutMirroring.childrenInherit: true
    implicitHeight: button.implicitHeight
    Settings.MoosDestinationTile {
        id: button
        objectName: "destination"
        anchors.fill: parent
        glyph: "system"
        text: MoUI.Locale.local("الشاشة والعرض", "Display & screens")
        description: MoUI.Locale.local("الدقة، التحجيم وترتيب الشاشات", "Resolution, scale and screen arrangement")
    }
}''').encode(), QUrl.fromLocalFile(__file__))
    assert not component.isError(), [e.toString() for e in component.errors()]
    root = component.create()
    assert root is not None, [e.toString() for e in component.errors()]
    tile = root.findChild(QObject, 'destination')
    window = QQuickWindow()
    root.setParentItem(window.contentItem())
    window.show()
    clicks = []
    QObject.connect(tile, SIGNAL('clicked()'), lambda: clicks.append(True))
    device = QTest.createTouchDevice()
    for width in (320, 480, 720):
        root.setWidth(width)
        root.setHeight(max(96, root.implicitHeight()))
        window.resize(width, round(root.height()))
        QTest.qWait(50)
        assert tile.width() >= 44 and tile.height() >= 44
        for child in tile.findChildren(QObject):
            if child.property('text') in (tile.property('text'), tile.property('description')):
                assert child.property('paintedWidth') <= child.property('width') + 1
        point = QPoint(width // 2, round(root.height() / 2))
        count = len(clicks)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        assert len(clicks) == count + 1, 'Pointer activation must happen once'
        tile.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Space)
        assert len(clicks) == count + 2, 'Keyboard activation must happen once'
        QTest.touchEvent(window, device).press(0, point, window).commit()
        QTest.touchEvent(window, device).release(0, point, window).commit()
        QTest.qWait(30)
        assert len(clicks) == count + 3, 'Touch activation must happen once'
        tile.setProperty('enabled', False)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
        QTest.keyClick(window, Qt.Key_Space)
        QTest.touchEvent(window, device).press(0, point, window).commit()
        QTest.touchEvent(window, device).release(0, point, window).commit()
        QTest.qWait(30)
        assert len(clicks) == count + 3, 'Unavailable destinations must stay inert'
        tile.setProperty('enabled', True)
    assert not any(any(t in m for t in ('ReferenceError', 'TypeError', 'Binding loop',
                                      'Unable to assign', 'Cannot assign')) for m in messages), messages
    window.close()
    print(json.dumps({'language': sys.argv[2], 'widths': 3, 'pointer': True,
                      'keyboard': True, 'qt_touch': True, 'disabled_refusal': True}))


class SettingsDestinationInput(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt/PySide6 unavailable')
    def test_native_pointer_keyboard_touch_and_text_bounds(self):
        for language in ('ar', 'en'):
            with self.subTest(language=language), tempfile.TemporaryDirectory(prefix='moos-settings-input-') as tmp:
                env = dict(PATH='/usr/bin:/bin', HOME=tmp, XDG_CONFIG_HOME=tmp+'/config',
                           XDG_DATA_HOME=tmp+'/data', XDG_CACHE_HOME=tmp+'/cache',
                           XDG_RUNTIME_DIR=tmp, DBUS_SESSION_BUS_ADDRESS='unix:path='+tmp+'/absent',
                           LANG='ar_SA.UTF-8' if language == 'ar' else 'en_US.UTF-8',
                           LANGUAGE=language, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                           QML_DISABLE_DISK_CACHE='1')
                result = subprocess.run([sys.executable, __file__, '--native-driver', language],
                                        env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout)['widths'], 3)


if __name__ == '__main__':
    if sys.argv[1:2] == ['--native-driver']:
        native_driver()
    else:
        unittest.main()
