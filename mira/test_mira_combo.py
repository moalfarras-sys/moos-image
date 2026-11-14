"""Private native Qt input and palette controls for Mira's shared ComboBox.

The child owns its HOME/XDG/bus and offscreen window. No Mira controller,
microphone, credentials, live desktop input or personal preference is used.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class MiraComboTest(unittest.TestCase):
    def test_native_selection_cancellation_bounds_rtl_and_palette(self):
        with tempfile.TemporaryDirectory(prefix='mira-combo-') as folder:
            base = Path(folder)
            for name in ('home', 'config', 'cache', 'data', 'state', 'run'):
                (base/name).mkdir(mode=0o700)
            env = os.environ.copy()
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'SESSION_MANAGER', 'QT_PLUGIN_PATH', 'QT_STYLE_OVERRIDE'):
                env.pop(key, None)
            env.update(HOME=str(base/'home'), XDG_CONFIG_HOME=str(base/'config'),
                       XDG_CONFIG_DIRS=str(base/'config'), XDG_CACHE_HOME=str(base/'cache'),
                       XDG_DATA_HOME=str(base/'data'), XDG_STATE_HOME=str(base/'state'),
                       XDG_RUNTIME_DIR=str(base/'run'), QT_QPA_PLATFORM='offscreen',
                       QT_QPA_PLATFORMTHEME='generic', QT_QUICK_BACKEND='software',
                       QT_QUICK_CONTROLS_STYLE='Basic', QML_DISABLE_DISK_CACHE='1',
                       QML_IMPORT_PATH=str(ROOT.parent/'system_files/usr/lib64/qt6/qml'),
                       DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'run/absent'))
            result = subprocess.run(['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                                     '--probe'], env=env, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('MIRA_COMBO_NATIVE_INPUT_PASS', result.stdout)


def probe():
    import time
    from PySide6.QtCore import QPoint, QPointF, Qt, QUrl, qInstallMessageHandler
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest

    app = QApplication([])
    app.setApplicationName('MiraComboPrivateProof')
    app.setOrganizationName('MoOSPrivateReview')
    messages = []
    old_handler = qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(ROOT/'qml'))
    engine.loadData(b'''import QtQuick
import QtQuick.Controls.Basic
import Mira
ApplicationWindow {
    id: win
    width: 360; height: 300; visible: true
    property int activations: 0
    property string selected: ""
    property bool rtl: false
    readonly property bool popupVisible: picker.popup.visible
    readonly property real popupWidth: picker.popup.width
    readonly property real popupHeight: picker.popup.height
    readonly property Item popupList: picker.popup.contentItem
    readonly property Item popupFloor: picker.popup.background
    readonly property bool textRightAligned: picker.contentItem.horizontalAlignment === Text.AlignRight
    MiraComboBox {
        id: picker
        objectName: "testCombo"; x: 32; y: 24; width: 220
        LayoutMirroring.enabled: win.rtl
        LayoutMirroring.childrenInherit: true
        model: [
            {label: "Internal microphone with an intentionally very long device name", source: "internal"},
            {label: "USB microphone", source: "usb"},
            {label: "\\u0645\\u064a\\u0643\\u0631\\u0648\\u0641\\u0648\\u0646 \\u0627\\u0644\\u062c\\u0647\\u0627\\u0632 \\u0627\\u0644\\u062f\\u0627\\u062e\\u0644\\u064a", source: "arabic"}
        ]
        textRole: "label"; valueRole: "source"
        onActivated: { win.activations += 1; win.selected = currentValue }
    }
}''', QUrl.fromLocalFile(str(ROOT/'qml/combo-private.qml')))
    assert engine.rootObjects(), str(messages)
    win = engine.rootObjects()[0]
    combo = win.findChild(QQuickItem, 'testCombo')
    current = combo.findChild(QQuickItem, 'comboCurrentText')

    def settle(duration=.12):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.003)

    def center(item):
        point = item.mapToScene(QPointF(item.width()/2, item.height()/2))
        return QPoint(round(point.x()), round(point.y()))

    def click_combo():
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, center(combo))
        settle()

    def visual_children(item):
        for child in item.childItems():
            yield child
            yield from visual_children(child)

    try:
        settle()
        assert combo and current, 'source ComboBox did not load'
        assert current.property('truncated'), 'long selected text did not elide'
        assert current.width() <= combo.width() - 32, 'text overlaps indicator'
        assert combo.height() >= 44, 'input target too short'

        # Native keyboard selection emits activated once; assignment never does.
        combo.forceActiveFocus()
        QTest.keyClick(win, Qt.Key_Space)
        settle()
        assert win.property('popupVisible'), 'Space did not open native popup'
        QTest.keyClick(win, Qt.Key_Down)
        QTest.keyClick(win, Qt.Key_Return)
        settle()
        assert combo.property('currentValue') == 'usb', 'keyboard did not select next row'
        assert win.property('activations') == 1 and win.property('selected') == 'usb'
        assert not win.property('popupVisible')

        click_combo()
        assert win.property('popupVisible'), 'pointer did not open popup'
        listing = win.property('popupList')
        entries = visual_children(listing)
        entry = next((item for item in entries if item.objectName() == 'comboEntry2'), None)
        assert entry, 'native delegate model did not create the Arabic row'
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, center(entry))
        settle()
        assert combo.property('currentValue') == 'arabic', 'pointer delegate did not activate'
        assert win.property('activations') == 2

        click_combo()
        QTest.keyClick(win, Qt.Key_Up)
        QTest.keyClick(win, Qt.Key_Escape)
        settle()
        assert not win.property('popupVisible') and combo.property('currentValue') == 'arabic'
        assert win.property('activations') == 2, 'Escape committed a pending row'
        combo.setProperty('currentIndex', 0)
        settle()
        assert win.property('activations') == 2, 'reading/model assignment activated a row'

        win.setProperty('rtl', True)
        combo.setWidth(170)
        settle()
        indicator = combo.findChild(QQuickItem, 'comboIndicator')
        assert combo.property('mirrored') and indicator.x() < current.x(), 'RTL indicator did not mirror'
        assert win.property('textRightAligned')
        assert current.property('truncated') and current.width() <= combo.width() - 32
        click_combo()
        assert win.property('popupWidth') <= combo.width(), 'popup exceeds the control width'
        assert win.property('popupHeight') <= win.height() - 24, 'popup exceeds window bounds'
        listing = win.property('popupList')
        assert listing.property('clip'), 'long delegates can paint outside popup'
        for item in visual_children(listing):
            if item.objectName().startswith('comboEntry'):
                assert item.width() <= listing.width(), 'delegate exceeds clipped list'
        QTest.keyClick(win, Qt.Key_Escape)
        settle()
        combo.setProperty('enabled', False)
        click_combo()
        assert not win.property('popupVisible') and win.property('activations') == 2
        combo.setProperty('enabled', True)

        # Runtime native application palette changes reach selected and popup ink.
        for base, ink in (('#f4f7fb', '#172536'), ('#182333', '#edf2fa')):
            palette = QPalette(app.palette())
            palette.setColor(QPalette.Window, QColor(base))
            palette.setColor(QPalette.Base, QColor(base))
            palette.setColor(QPalette.WindowText, QColor(ink))
            app.setPalette(palette)
            settle()
            background = win.property('popupFloor')
            assert background.property('color') == QColor(base), 'popup ignores native base'
            assert background.property('color').alpha() == 255, 'popup reading floor is translucent'
            assert current.property('color') == QColor(ink), 'selected text ignores native ink'
        bad = [line for line in messages if any(word in line for word in
               ('ReferenceError', 'TypeError', 'Cannot assign', 'Unable to assign', 'failed to load', 'is not defined'))]
        assert not bad, str(bad)
        print('MIRA_COMBO_NATIVE_INPUT_PASS: keyboard pointer Escape disabled RTL narrow palette')
    finally:
        win.close()
        engine.deleteLater()
        settle(.05)
        qInstallMessageHandler(old_handler)


if __name__ == '__main__':
    if '--probe' in sys.argv:
        probe()
    else:
        unittest.main()
