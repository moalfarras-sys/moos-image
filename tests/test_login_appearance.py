#!/usr/bin/env python3
"""Exercise the real greeter config component and KDE's initial-property contract.

The actual installed KCM journey is separate. This private native Qt fixture
guards value/default/input behavior without a system bus or authentication.
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
CONFIG = ROOT/'system_files/usr/share/plasma/wallpapers/org.moos.ui2.greeter/contents/ui/config.qml'
PROFILES = json.loads((ROOT/'artwork/moos-design/theme-profiles.json').read_text())['profiles']


def probe(broken):
    from PySide6.QtCore import QObject, QUrl, Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    app = QApplication([])
    engine = QQmlEngine()
    engine.setProperty('_kirigamiTheme', 'org.kde.desktop')
    shell = QQmlComponent(engine)
    shell.setData(b'''import QtQuick
import QtQuick.Controls
import org.kde.kirigami as Kirigami
ApplicationWindow { width: 640; height: 800; visible: true
    Kirigami.FormLayout { objectName: "parentForm"; visible: false }
}''', QUrl())
    win = shell.create()
    assert win, [e.toString() for e in shell.errors()]
    engine.rootContext().setContextProperty('parentLayout', win.findChild(QQuickItem, 'parentForm'))
    source = CONFIG.read_text()
    if broken:
        needle = 'onClicked: root.cfg_Image = root.imageForLook(root.desktopLook)'
        assert source.count(needle) == 1
        source = source.replace(needle, 'onClicked: {}', 1)
    component = QQmlComponent(engine)
    component.setData(source.encode(), QUrl.fromLocalFile(str(CONFIG)))
    # WallpaperConfig.qml supplies both cfg_Key and cfg_KeyDefault. Omitting
    # these properties painted a page while Qt reported failed assignments.
    root = component.createWithInitialProperties({'configDialog': None,
        'cfg_Image': '/usr/share/wallpapers/MoOSUI2Graphite/', 'cfg_ImageDefault': '',
        'cfg_AmbientMotion': True, 'cfg_AmbientMotionDefault': True})
    assert root, [e.toString() for e in component.errors()]
    root.setParentItem(win.contentItem()); root.setWidth(600)
    picker = root.findChild(QQuickItem, 'moosLoginLookPicker')
    desktop = root.findChild(QQuickItem, 'moosLoginUseDesktopLook')
    assert picker and desktop
    QTest.qWait(100)
    assert picker.property('count') == len(PROFILES) == 18
    # Opening a config page must not replace a package URI with its preview.
    assert root.property('cfg_Image') == '/usr/share/wallpapers/MoOSUI2Graphite/'
    for index, profile in enumerate(PROFILES):
        package = '/usr/share/wallpapers/'+profile['wallpaper']
        root.setProperty('cfg_Image', package); QTest.qWait(5)
        assert picker.property('currentIndex') == index, profile['id']
    custom = '/private/unknown-owner-image.png'
    root.setProperty('cfg_Image', custom); QTest.qWait(10)
    assert picker.property('currentIndex') == -1 and root.property('cfg_Image') == custom
    root.setProperty('cfg_Image', ''); QTest.qWait(10)
    assert picker.property('currentIndex') == 0 and root.property('cfg_Image') == ''
    # Real Qt keyboard activation of the existing button changes only the
    # pending setting, using globally installed assets even with source XDG.
    desktop.forceActiveFocus(Qt.TabFocusReason)
    QTest.qWait(20)
    assert desktop.hasActiveFocus(), 'desktop appearance button did not take keyboard focus'
    QTest.keyClick(win, Qt.Key_Space); QTest.qWait(20)
    expected = '/usr/share/wallpapers/MoOSUI2BloomLight/contents/images/1672x941.png'
    assert root.property('cfg_Image') == expected, 'desktop appearance action was inert'
    root.setProperty('cfg_Image', '/usr/share/wallpapers/MoOSUI2Graphite/')
    QTest.qWait(10)
    assert picker.property('currentIndex') == 0, 'KDE Defaults did not update the selector'
    win.close()
    print('MOOS_LOGIN_CONFIG_INPUT_PASS', flush=True)


class NativeLoginAppearance(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable on SDK-free worker')
    def test_value_defaults_keyboard_and_broken_action(self):
        with tempfile.TemporaryDirectory(prefix='moos-login-config-') as td:
            private = Path(td)
            for name in ('home', 'config', 'cache', 'data', 'runtime'):
                (private/name).mkdir(mode=0o700)
            (private/'config/kdeglobals').write_text('[KDE]\nLookAndFeelPackage=org.moos.ui2.bloom.light\nAnimationDurationFactor=0\n')
            env = dict(os.environ, HOME=str(private/'home'), XDG_CONFIG_HOME=str(private/'config'),
                XDG_CONFIG_DIRS=str(private/'config'), XDG_CACHE_HOME=str(private/'cache'),
                XDG_DATA_HOME=str(private/'data'), XDG_RUNTIME_DIR=str(private/'runtime'),
                XDG_DATA_DIRS=str(ROOT/'system_files/usr/share')+':/usr/share',
                QML_IMPORT_PATH=str(ROOT/'system_files/usr/lib64/qt6/qml'),
                DBUS_SESSION_BUS_ADDRESS='unix:path='+str(private/'absent-session'),
                DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(private/'absent-system'),
                QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
                QT_QPA_PLATFORMTHEME='kde', QT_QUICK_CONTROLS_STYLE='Basic',
                QML_DISABLE_DISK_CACHE='1', LANG='ar_SA.UTF-8')
            for broken in (False, True):
                p = subprocess.run([sys.executable, __file__, '--probe']+(['--broken'] if broken else []),
                    env=env, capture_output=True, text=True, timeout=25)
                log = p.stdout+p.stderr
                if broken:
                    self.assertNotEqual(p.returncode, 0)
                    self.assertIn('desktop appearance action was inert', log)
                    self.assertNotIn('MOOS_LOGIN_CONFIG_INPUT_PASS', log)
                else:
                    self.assertEqual(p.returncode, 0, log[-5000:])
                    self.assertIn('MOOS_LOGIN_CONFIG_INPUT_PASS', log)
                    self.assertNotIn('Cannot assign', log)


if __name__ == '__main__':
    if '--probe' in sys.argv:
        probe('--broken' in sys.argv)
    else:
        unittest.main()
