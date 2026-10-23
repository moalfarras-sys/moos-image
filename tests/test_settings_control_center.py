#!/usr/bin/env python3
"""Native audio input, busy/refusal handling and narrow device text.

The real QML uses a recording backend here, never the owner's audio or bus.
Compiled action validation and physical Settings interaction are separate proofs.
"""
from pathlib import Path
import configparser
import importlib.util
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def native_driver():
    from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest

    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QApplication([])
    engine = QQmlEngine()
    engine.addImportPath(str(ROOT / 'system_files/usr/lib64/qt6/qml'))
    common_path = ROOT / 'moos-settings-kcm/common'
    broken_copy = None
    if '--broken-failure' in sys.argv:
        broken_copy = tempfile.TemporaryDirectory(prefix='moos-broken-audio-')
        common_path = Path(broken_copy.name) / 'common'
        shutil.copytree(ROOT / 'moos-settings-kcm/common', common_path)
        target = common_path / 'MoosAudioCard.qml'
        source = target.read_text()
        old = 'card.errorText = exitCode === 0 ? ""'
        assert source.count(old) == 1
        target.write_text(source.replace(old, 'card.errorText = true ? ""'))
    common = common_path.as_uri()
    component = QQmlComponent(engine)
    component.setData(('''import QtQuick
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI
import "''' + common + '''" as Settings
Item {
    readonly property color reviewBackground: Kirigami.Theme.backgroundColor
    readonly property int reviewDuration: Kirigami.Units.longDuration
    LayoutMirroring.enabled: MoUI.Locale.rtl
    LayoutMirroring.childrenInherit: true
    property QtObject recorder: QtObject {
        objectName: "backend"
        property var status: ({audio: {available: true, volume: 45, muted: false}, destinations: {audio: true}})
        property bool statusValid: true
        property bool accept: true
        property var calls: []
        property int refreshed: 0
        property var routes: []
        property QtObject task: QtObject {}
        signal jobFinished(string id, int exitCode, string output)
        function runFixed(id, argument) {
            calls = calls.concat([{id: id, argument: argument}]); return accept ? task : null;
        }
        function refresh() { refreshed += 1; }
        function openRoute(route) { routes = routes.concat([route]); return false; }
        function complete(code) { jobFinished(calls[calls.length-1].id, code, ""); }
        function measured(value, muted) { status = {audio: {available: true, volume: value, muted: muted}, destinations: {audio: true}}; }
        function destination(available) { status = {audio: status.audio, destinations: {audio: available}}; }
        function routeCount() { return routes.length; }
        function report() { return JSON.stringify(calls); }
    }
    Settings.MoosAudioCard {
        id: audio
        objectName: "audioCard"
        width: parent.width
        backend: recorder
    }
    Settings.MoosDeviceTile {
        objectName: "deviceTile"
        y: audio.height + 12
        width: parent.width
        text: MoUI.Locale.local("الشبكة", "Network")
        stateText: MoUI.Locale.local("يلزم تسجيل الدخول", "Sign-in required")
        detail: "A long network name : تجربة الشبكة الطويلة مع نص قابل للالتفاف"
        glyph: "wifi"
        compact: width < 400
    }
}''').encode(), QUrl.fromLocalFile(__file__))
    assert not component.isError(), [e.toString() for e in component.errors()]
    root = component.create()
    assert root is not None, [e.toString() for e in component.errors()]
    window = QQuickWindow()
    root.setParentItem(window.contentItem())
    window.show()
    backend = root.findChild(QObject, 'backend')
    card = root.findChild(QObject, 'audioCard')
    mute = root.findChild(QObject, 'moosAudioMute')
    slider = root.findChild(QObject, 'moosAudioVolume')
    label = root.findChild(QObject, 'moosAudioMeasuredState')
    devices = root.findChild(QObject, 'moosAudioSettings')
    device = QTest.createTouchDevice()

    def calls():
        return json.loads(backend.report())

    def point(item, fraction=.5):
        p = item.mapToScene(QPointF(item.width()*fraction, item.height()/2))
        return QPoint(round(p.x()), round(p.y()))

    for width in (320, 480, 960):
        root.setWidth(width)
        root.setHeight(500)
        window.resize(width, 500)
        QTest.qWait(40)
        assert slider.height() >= 44 and mute.width() >= 44 and mute.height() >= 44
        for item in root.findChildren(QObject):
            if item.property('paintedWidth') is not None:
                assert item.property('paintedWidth') <= item.property('width') + 1, item.property('text')
        count = len(calls())
        before = label.property('text')
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point(mute))
        assert len(calls()) == count + 1 and calls()[-1]['id'] == 'audio-mute'
        assert card.property('busy') and label.property('text') == before
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point(mute))
        assert len(calls()) == count + 1, 'A pending action must not launch twice'
        backend.complete(1)
        QTest.qWait(20)
        assert not card.property('busy') and card.property('errorText'), 'Failed mutation must show an error'
        assert label.property('text') == before, 'Failure must not invent a new measured state'

        slider.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Left if sys.argv[2] == 'ar' else Qt.Key_Right)
        assert calls()[-1] == {'id': 'audio-volume', 'argument': '46'}, (calls(), slider.property('value'), slider.property('activeFocus'), slider.property('enabled'))
        backend.measured(46, False)
        backend.complete(0)
        assert not card.property('errorText')
        backend.measured(45, True)
        QTest.touchEvent(window, device).press(0, point(mute), window).commit()
        QTest.touchEvent(window, device).release(0, point(mute), window).commit()
        QTest.qWait(20)
        assert calls()[-1]['id'] == 'audio-unmute'
        backend.measured(45, False)
        backend.complete(0)
        QTest.qWait(20)

        count = len(calls())
        QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, point(slider, .4))
        QTest.mouseMove(window, point(slider, .6))
        assert len(calls()) == count, 'Dragging must not start intermediate mutations'
        QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, point(slider, .6))
        QTest.qWait(20)
        assert len(calls()) == count + 1 and calls()[-1]['id'] == 'audio-volume'
        assert 0 <= int(calls()[-1]['argument']) <= 100
        backend.measured(int(calls()[-1]['argument']), False)
        backend.complete(0)
        QTest.qWait(20)

        backend.setProperty('accept', False)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point(mute))
        assert not card.property('busy') and card.property('errorText'), 'Executor refusal must remain visible'
        backend.setProperty('accept', True)
        backend.setProperty('statusValid', False)
        count = len(calls())
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point(mute))
        slider.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Home)
        assert len(calls()) == count, 'Unknown audio state must be inert'
        backend.setProperty('statusValid', True)
        backend.measured(45, False)
        QTest.qWait(20)
        count = backend.routeCount()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point(devices))
        assert backend.routeCount() == count + 1 and card.property('errorText')
        backend.destination(False)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point(devices))
        assert backend.routeCount() == count + 1, 'An absent device page must be inert'
        backend.destination(True)

    assert not any(any(t in m for t in ('ReferenceError', 'TypeError', 'Binding loop',
                                      'Unable to assign', 'Cannot assign')) for m in messages), messages
    background = root.property('reviewBackground')
    light = os.environ.get('MOOS_CONTROL_LIGHT') == '1'
    reduced = os.environ.get('MOOS_CONTROL_REDUCED') == '1'
    assert (background.lightnessF() > .5) == light, background.name()
    assert (root.property('reviewDuration') > 1) != reduced, root.property('reviewDuration')
    window.close()
    print(json.dumps({'background': background.name(), 'reduced': reduced, 'language': sys.argv[2], 'widths': 3, 'pointer': True,
                      'keyboard': True, 'qt_touch': True, 'busy_refusal': True,
                      'failed_action': True, 'executor_refusal': True, 'unknown_refusal': True}))


class ControlCenterInput(unittest.TestCase):
    def test_secondary_ink_against_the_composed_card_in_every_scheme(self):
        checks = runpy.run_path(str(ROOT / 'tests/test_secondary_text_contrast.py'))
        tile = ROOT / 'moos-settings-kcm/common/MoosDeviceTile.qml'
        fill = re.search(r'fillOpacity:\s*([0-9.]+)\s*\n', tile.read_text())
        self.assertIsNotNone(fill, 'The composed background needs a determinate opacity')
        alphas = checks['token_alphas']([tile], 'secondaryInk')
        self.assertEqual(len(alphas), 1)
        alpha = alphas[0][0]
        self.assertIsNotNone(alpha)

        def ratios(opacity):
            result = []
            for path in checks['SCHEMES'].glob('*.colors'):
                scheme = configparser.ConfigParser()
                scheme.read(path)
                for group in ('Colors:View', 'Colors:Window'):
                    background = tuple(map(int, scheme[group]['BackgroundNormal'].split(',')))
                    ink = tuple(map(int, scheme[group]['ForegroundNormal'].split(',')))
                    composed = checks['over'](ink, background, opacity)
                    ratio = checks['contrast'](checks['over'](ink, composed, alpha), composed)
                    result.append((ratio, path.stem, group))
            return result

        current = ratios(float(fill.group(1)))
        self.assertGreaterEqual(min(current)[0], checks['AA'], min(current))
        # Restore the measured old active fill under the same secondary ink.
        old_active = ratios(.09)
        self.assertLess(min(old_active)[0], checks['AA'], 'The old active card must fail the same contrast calculation')

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt/PySide6 unavailable')
    def test_native_input_and_truthful_failure_states(self):
        for language in ('ar', 'en'):
            for light in (False, True):
                for reduced in (False, True):
                    with self.subTest(language=language, light=light, reduced=reduced), \
                            tempfile.TemporaryDirectory(prefix='moos-control-input-') as tmp:
                        config = Path(tmp) / 'config'
                        config.mkdir()
                        theme = 'org.moos.ui2.light' if light else 'org.moos.ui2'
                        defaults = ROOT / 'system_files/usr/share/plasma/look-and-feel' / theme / 'contents/defaults'
                        matched = configparser.ConfigParser(interpolation=None)
                        matched.optionxform = str
                        matched.read_string(defaults.read_text())
                        scheme = matched['kdeglobals][General']['ColorScheme']
                        icons = matched['kdeglobals][Icons']['Theme']
                        style = matched['plasmarc][Theme']['name']
                        colors = (ROOT / 'system_files/usr/share/color-schemes' / (scheme+'.colors')).read_text()
                        (config/'kdeglobals').write_text(colors+'\n[KDE]\nAnimationDurationFactor='
                            + ('0' if reduced else '1')+'\n[Icons]\nTheme='+icons+'\n')
                        (config/'plasmarc').write_text('[Theme]\nname='+style+'\n')
                        env = dict(PATH='/usr/bin:/bin', HOME=tmp, XDG_CONFIG_HOME=str(config),
                                   XDG_CONFIG_DIRS=str(config), XDG_CURRENT_DESKTOP='KDE',
                                   XDG_DATA_HOME=tmp+'/data', XDG_CACHE_HOME=tmp+'/cache',
                                   XDG_RUNTIME_DIR=tmp, DBUS_SESSION_BUS_ADDRESS='unix:path='+tmp+'/absent',
                                   LANG='ar_SA.UTF-8' if language == 'ar' else 'en_US.UTF-8',
                                   LANGUAGE=language, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                                   QT_QPA_PLATFORMTHEME='kde', QT_QUICK_CONTROLS_STYLE='org.kde.desktop',
                                   QT_QUICK_CONTROLS_KIRIGAMI_PLATFORM='org.kde.kirigami.desktop',
                                   MOOS_CONTROL_LIGHT='1' if light else '0',
                                   MOOS_CONTROL_REDUCED='1' if reduced else '0', QML_DISABLE_DISK_CACHE='1')
                        result = subprocess.run([sys.executable, __file__, '--native-driver', language],
                                                env=env, capture_output=True, text=True, timeout=20)
                        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                        self.assertEqual(json.loads(result.stdout)['widths'], 3)
                        print('MOOS_CONTROL_CASE '+result.stdout.strip())
                        if not light and not reduced:
                            broken = subprocess.run([sys.executable, __file__, '--native-driver', language, '--broken-failure'],
                                                    env=env, capture_output=True, text=True, timeout=20)
                            self.assertNotEqual(broken.returncode, 0, 'The broken failure readback must fail the same input proof')
                            self.assertIn('Failed mutation must show an error', broken.stderr)



if __name__ == '__main__':
    if sys.argv[1:2] == ['--native-driver']:
        native_driver()
    else:
        unittest.main()
