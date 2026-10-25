#!/usr/bin/env python3
"""Native lock/power must follow the desktop's exact local image, inertly."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/'system_files/usr/bin/moos-theme').read_text()
LOOK = 'org.moos.ui2.bloom.light'


def function(name):
    start = SOURCE.index(name+'() {')
    return SOURCE[start:SOURCE.index('\n}\n', start)+3]


def native_probe():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication, QColor
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    app = QGuiApplication([])
    engine = QQmlEngine()
    engine.addImportPath(str(ROOT/'system_files/usr/lib64/qt6/qml'))
    expression = ('MoUI.SessionAppearance.wallpaperForLook(MoUI.SessionAppearance.configuredLook())'
                  if os.environ.get('OLD_WALLPAPER') else 'MoUI.SessionAppearance.configuredWallpaper()')
    component = QQmlComponent(engine)
    component.setData(('''import QtQuick
import org.moos.ui as MoUI
Window { id: window; width: 320; height: 200; visible: true
 property url selectedImage: '''+expression+'''
 Image { anchors.fill: parent; source: window.selectedImage; objectName: "picture" }
}''').encode(), QUrl('file:///session-image-proof.qml'))
    window = component.create()
    assert window, [e.toString() for e in component.errors()]
    assert isinstance(window, QQuickWindow)
    QTest.qWait(250)
    expected = os.environ['EXPECTED_IMAGE']
    actual = window.property('selectedImage').toLocalFile()
    assert actual == expected, ('wrong exact wallpaper', actual, expected)
    if os.environ.get('EXPECT_CUSTOM'):
        pixel = window.grabWindow().pixelColor(160, 100)
        assert pixel == QColor('#1583b1'), ('custom image did not paint', pixel.name())
    print('MOOS_NATIVE_SESSION_WALLPAPER_PASS', flush=True)


class SessionWallpaper(unittest.TestCase):
    @unittest.skipUnless(shutil.which('kwriteconfig6') and shutil.which('kreadconfig6'), 'native KConfig tools unavailable')
    def test_exact_native_lock_and_power_choice_and_refusals(self):
        with tempfile.TemporaryDirectory(prefix='moos-session-image-') as td:
            root = Path(td)
            config = root/'config'; config.mkdir()
            env = os.environ | dict(HOME=td, XDG_CONFIG_HOME=str(config), XDG_CONFIG_DIRS=str(config),
                XDG_DATA_HOME=str(root/'data'), XDG_CACHE_HOME=str(root/'cache'),
                XDG_DATA_DIRS=str(ROOT/'system_files/usr/share')+':/usr/share',
                DBUS_SESSION_BUS_ADDRESS='unix:path='+td+'/absent',
                QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QML_DISABLE_DISK_CACHE='1')
            env.pop('WAYLAND_DISPLAY',None); env.pop('DISPLAY',None)
            (config/'kdeglobals').write_text('[KDE]\nLookAndFeelPackage='+LOOK+'\n')
            script = root/'apply'
            script.write_text('set -eu\ncurrent() { echo '+LOOK+'; }\n'+
                '\n'.join(function(n) for n in ('session_wallpaper_value','apply_session_wallpaper_token','session_wallpaper_complete'))+
                '\napply_session_wallpaper_token "$1"\nsession_wallpaper_complete "$1"\n')
            from PIL import Image
            custom = root/"صورة #1%? 'اختيار'.png"
            Image.new('RGB',(64,40),'#1583b1').save(custom)
            token = quote(str(custom),safe='-._~')
            for invalid in ('relative.png','%2Ftmp%2Fbad%00.png','%2Ftmp%2Fbad%0A.png','%ZZ','%FF'):
                before = {p.name:p.read_bytes() for p in config.iterdir()}
                result = subprocess.run(['bash',str(script),invalid],env=env,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,invalid)
                self.assertEqual(before,{p.name:p.read_bytes() for p in config.iterdir()})
            result = subprocess.run(['bash',str(script),token],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            lock = subprocess.run(['kreadconfig6','--file','kscreenlockerrc','--group','Greeter','--group','Wallpaper',
                '--group','org.kde.image','--group','General','--key','Image'],env=env,capture_output=True,text=True,check=True).stdout.rstrip('\n')
            self.assertEqual(lock,custom.as_uri())
            try:
                import PySide6  # native rendered readback below, absence is explicit
            except ImportError:
                self.skipTest('native KConfig passed; native Qt rendering unavailable')
            before = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in config.iterdir()}
            for old in (False,True):
                probe_env = env | dict(EXPECTED_IMAGE=str(custom),EXPECT_CUSTOM='1')
                if old: probe_env['OLD_WALLPAPER']='1'
                result = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--probe'],env=probe_env,capture_output=True,text=True,timeout=10)
                if old:
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn('wrong exact wallpaper',result.stdout+result.stderr)
                else:
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    self.assertIn('MOOS_NATIVE_SESSION_WALLPAPER_PASS',result.stdout)
            self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in config.iterdir()})
            # The chosen look changes before reconciliation: don't reuse the
            # previous profile's custom snapshot during that transition.
            (config/'moos-session-appearance.conf').write_text('[Appearance]\nLook=org.moos.ui2.aurora\nWallpaperEncoded='+token+'\n')
            result = subprocess.run([sys.executable,str(Path(__file__).resolve()),'--probe'],env=env | dict(
                EXPECTED_IMAGE=str(ROOT/'system_files/usr/share/wallpapers/MoOSUI2BloomLight/contents/images/1672x941.png')),
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__ == '__main__':
    if '--probe' in sys.argv: native_probe()
    else: unittest.main()
