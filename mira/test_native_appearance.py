"""Mira reads the native application palette and shared live MoOS appearance.

The child owns its HOME, config, runtime and D-Bus. It uses QApplication, as the
canonical app does. The default gate drives native Qt palette/font events;
MIRA_NATIVE_KDE_PROOF=1 additionally requires actual KDE palette/font/config
publication and rejects the generic-style control. No owner preference, device, model or credential is read or changed.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
OVERLAY = ROOT.parent / 'system_files'


class NativeAppearance(unittest.TestCase):
    def run_case(self, family, *, wrong_style=False):
        colors = OVERLAY / 'usr/share/color-schemes' / (family + '.colors')
        if not colors.exists():
            colors = Path('/usr/share/color-schemes') / (family + '.colors')
        native = os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1'
        if native:
            self.assertTrue(colors.exists() and shutil.which('kwriteconfig6'), 'native KDE proof unavailable')
        with tempfile.TemporaryDirectory(prefix='mira-native-appearance-') as temp:
            base = Path(temp)
            for name in ('home', 'config', 'cache', 'data', 'state', 'run'):
                (base / name).mkdir(mode=0o700)
            (base/'config/kdeglobals').write_text((colors.read_text() if colors.exists() else '') +
                '\n[KDE]\nAnimationDurationFactor=1\n[General]\nfont=Meyar Sans,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,0\n')
            (base/'run/moos-material').mkdir()
            (base/'run/moos-material/state-1-on-clear').touch()
            env = os.environ.copy()
            for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'SESSION_MANAGER', 'QT_PLUGIN_PATH', 'QT_STYLE_OVERRIDE'):
                env.pop(key, None)
            env.update(HOME=str(base/'home'), XDG_CONFIG_HOME=str(base/'config'),
                       XDG_CONFIG_DIRS=str(base/'config'), XDG_DATA_DIRS='/usr/share', XDG_DATA_HOME=str(base/'data'),
                       XDG_CACHE_HOME=str(base/'cache'), XDG_STATE_HOME=str(base/'state'),
                       XDG_RUNTIME_DIR=str(base/'run'), QT_QPA_PLATFORM='offscreen',
                       QT_QPA_PLATFORMTHEME='generic' if wrong_style or not native else 'kde',
                       QT_QUICK_BACKEND='software', QT_QUICK_CONTROLS_STYLE='Basic',
                       QML_DISABLE_DISK_CACHE='1', MIRA_TEST_MODE='1',
                       QML_IMPORT_PATH=str(OVERLAY/'usr/lib64/qt6/qml'),
                       DBUS_SESSION_BUS_ADDRESS='unix:path='+str(base/'run/absent'))
            result = subprocess.run(['dbus-run-session', '--', sys.executable, str(Path(__file__).resolve()),
                                     '--probe', str(ROOT), family], env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=35)
            if wrong_style and native:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('native palette owner mismatch', result.stderr)
            else:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('MIRA_NATIVE_APPEARANCE_PASS', result.stdout)

    def test_light_live_palette_font_material_motion_and_pages(self):
        self.run_case('MoOSUI2AuroraLight')

    def test_dark_live_palette_font_material_motion_and_pages(self):
        self.run_case('MoOSUI2Aurora')

    if os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1':
        def test_generic_qt_palette_is_not_native_kde_acceptance(self):
            self.run_case('MoOSUI2AuroraLight', wrong_style=True)


def probe(root, family):
    import configparser
    import time
    from unittest.mock import patch
    from PySide6.QtCore import QCoreApplication, QUrl, QPointF, qInstallMessageHandler
    from PySide6.QtGui import QColor, QFont, QFontInfo, QFontDatabase, QPalette, QGuiApplication
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
    from PySide6.QtQuick import QQuickItem
    sys.path.insert(0, str(root))
    from controller import Controller
    from faces import FaceProvider
    from review_fakes import FakeBridge
    import moai_tools
    app = QApplication([])
    source_fonts = OVERLAY / 'usr/share/fonts/meyar'
    for name in ('MeyarSans[wght].ttf', 'MeyarArabic[wght].ttf'):
        font_id=QFontDatabase.addApplicationFont(str(source_fonts/name))
        assert font_id>=0, 'source font unavailable: '+name
    assert QFontInfo(QFont('Meyar Sans',10)).family()=='Meyar Sans', 'source Meyar family unavailable' 
    app.setApplicationName('MiraAppearanceProof')
    app.setOrganizationName('MoOSPrivateReview')
    native = os.environ.get('MIRA_NATIVE_KDE_PROOF') == '1'
    colors = configparser.ConfigParser(interpolation=None, strict=False)
    colors.read(Path(os.environ['XDG_CONFIG_HOME'])/'kdeglobals')
    if native:
        rgb = [int(v) for v in colors['Colors:Window']['BackgroundNormal'].split(',')]
        assert app.palette().window().color() == QColor(*rgb), 'native palette owner mismatch'
        assert QFontInfo(app.font()).family()=='Meyar Sans', 'native default is not Meyar'
    else:
        palette=QPalette(app.palette())
        light=family.endswith('Light')
        palette.setColor(QPalette.Window,QColor('#c3d5e5' if light else '#151b28'))
        palette.setColor(QPalette.WindowText,QColor('#14283f' if light else '#e8eff8'))
        app.setPalette(palette)
    messages=[]
    previous=qInstallMessageHandler(lambda kind, ctx, text: messages.append(text))
    with patch.object(moai_tools, '_request', return_value=(0, {'error':'private-review'})):
        controller=Controller(bridge_class=FakeBridge)
        # Enable the upstream ambient opt-in in this private software fixture so
        # the native global-off control must actually stop a moving Main clock.
        controller._motion=True
        engine=QQmlApplicationEngine()
        engine.setProperty("_kirigamiTheme", "org.kde.desktop")
        engine.addImageProvider('mira', FaceProvider())
        engine.addImportPath(str(root/'qml'))
        engine.rootContext().setContextProperty('mira',controller)
        engine.rootContext().setContextProperty('miraApplication',app)
        engine.load(QUrl.fromLocalFile(str(root/'qml/Main.qml')))
        assert engine.rootObjects(), 'actual Main did not load: '+str(messages)
        win=engine.rootObjects()[0]
        c=QQmlComponent(engine)
        c.setData(b'''import QtQuick; import Mira; import org.moos.ui as MoUI; import org.kde.kirigami as Kirigami
QtObject {
 readonly property color bg: Theme.bg0
 readonly property color ink: Theme.ink
 readonly property color ink2: Theme.ink2
 readonly property color ink3: Theme.ink3
 readonly property color glass: Theme.glass
 readonly property string family: Theme.font
 readonly property int duration: MoUI.Tokens.liveLongDuration
 readonly property real motion: Theme.motionScale
 readonly property color face: Theme.phaseColor("speaking", "rose")
 property QtObject testMotion: QtObject { property int longDuration: 200 }
 function useTestMotion() { MoUI.Tokens.motionProbe = testMotion }
 function stopTestMotion() { testMotion.longDuration = 1 }
}''',QUrl())
        obj=c.create();assert obj, str([e.toString() for e in c.errors()])
        def settle(seconds=.25):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                QCoreApplication.processEvents();time.sleep(.005)
        def wait_for(predicate, label):
            end=time.monotonic()+4
            while not predicate() and time.monotonic()<end:settle(.03)
            assert predicate(), label
        if not native: obj.useTestMotion()
        settle()
        assert obj.property('bg') == app.palette().window().color(), 'Mira ignores the native palette'
        assert obj.property('ink') == app.palette().windowText().color()
        assert obj.property('face').name() == '#ff6fb5', 'Mira expression changed'
        assert abs(obj.property('glass').alphaF()-.82)<.002
        marker=Path(os.environ['XDG_RUNTIME_DIR'])/'moos-material/state-1-on-clear'
        marker.rename(marker.with_name('state-2-on-solid'))
        wait_for(lambda:abs(obj.property('glass').alphaF()-.97)<.002,'Solid did not reach Mira')
        marker=marker.with_name('state-2-on-solid')
        marker.rename(marker.with_name('state-3-off-clear'))
        wait_for(lambda:abs(obj.property('glass').alphaF()-.97)<.002,'no-blur not dense')
        marker=marker.with_name('state-3-off-clear')
        marker.rename(marker.with_name('state-4-on-clear'))
        wait_for(lambda:abs(obj.property('glass').alphaF()-.82)<.002,'Clear did not return')
        # Same QApplication owner emits palette/font changes; no config mirror.
        original=QPalette(app.palette())
        changed=QPalette(original);changed.setColor(QPalette.Window,QColor('#d6e8d5'))
        changed.setColor(QPalette.WindowText,QColor('#1c3020'))
        app.setPalette(changed);settle()
        assert obj.property('bg').name()=='#d6e8d5', 'live application palette ignored'
        available=QFontDatabase.families()
        personal='DejaVu Sans' if 'DejaVu Sans' in available else next(f for f in available if f!=app.font().family())
        font=QFont(personal,14)
        if native:
            subprocess.run(['kwriteconfig6','--file','kdeglobals','--group','General','--key','font','--notify',font.toString()],check=True)
            from PySide6.QtDBus import QDBusConnection,QDBusMessage
            signal=QDBusMessage.createSignal('/KDEPlatformTheme','org.kde.KDEPlatformTheme','refreshFonts')
            QDBusConnection.sessionBus().send(signal)
            settle(.3)
        else: QGuiApplication.setFont(font);settle()
        assert QFontInfo(app.font()).family()==personal, 'personal font control unavailable'
        assert obj.property('family')==personal, 'personal font ignored: '+str((obj.property('family'),personal,app.font().family(),win.property('font').family()))
        app.setPalette(original);settle()
        initial=win.property('clock');settle(.15)
        assert win.property('clock')>initial, 'ambient control was never running'
        if native:
            subprocess.run(['kwriteconfig6','--file','kdeglobals','--group','KDE','--key',
                            'AnimationDurationFactor','--notify','0'],check=True)
        else: obj.stopTestMotion()
        wait_for(lambda:obj.property('duration')==1,'native global-off did not publish')
        assert obj.property('motion')==0, 'global-off not reflected in Theme'
        assert not win.property('ambientMotion'), 'ambient loop ignores reduced motion'
        stopped=win.property('clock');settle(.2)
        assert win.property('clock')==stopped, 'clock kept running with global-off'
        if native:
            subprocess.run(['kwriteconfig6','--file','kdeglobals','--group','KDE','--key',
                            'AnimationDurationFactor','--notify','1'],check=True)
            wait_for(lambda:obj.property('duration')==200,'native global-on did not publish')
            settle(.15);assert win.property('clock')>stopped, 'clock did not resume'
            subprocess.run(['kwriteconfig6','--file','kdeglobals','--group','KDE','--key',
                            'AnimationDurationFactor','--notify','0'],check=True)
            wait_for(lambda:obj.property('duration')==1,'native global-off did not return')
        # Exercise every changed page at the physical constrained window and
        # narrow tablet size; pages own their scrolling, while composer stays visible.
        for width,height in ((1480,764),(640,800)):
            win.setWidth(width);win.setHeight(height)
            for page in ('','brain','system','home','pc','workbench','lumen','settings'):
                win.setProperty('sheet',page);settle(.12)
                composer=next(i for i in win.findChildren(QQuickItem,'composer') if i.isVisible())
                pos=composer.mapToScene(QPointF(0,0))
                assert composer.width()>0 and composer.height()>0
                assert pos.x()>=0 and pos.y()>=0 and pos.x()+composer.width()<=win.width() and pos.y()+composer.height()<=win.height(), 'composer outside window'
                loaders=[i for i in win.findChildren(QQuickItem) if i.metaObject().className().startswith('QQuickLoader') and i.property('active')]
                if page:
                    assert len(loaders)==1, 'page loader unavailable'
                    loaded=loaders[0].property('item')
                    assert loaded and loaded.isVisible() and loaded.width()>0 and loaded.height()>0, 'page root unavailable'
                    expected={'brain':'BrainPage','system':'SystemPage','home':'HomePage','pc':'PcPage','workbench':'WorkbenchPage','lumen':'LumenPage','settings':'SheetFrame'}[page]
                    assert loaded.metaObject().className().startswith(expected), (page,loaded.metaObject().className())
                    heading=loaded.findChild(QQuickItem,'pageHeaderText')
                    body=loaded.findChild(QQuickItem,'pageBody')
                    if heading and body:
                        end=heading.mapToScene(QPointF(0,heading.height())).y()
                        assert body.mapToScene(QPointF(0,0)).y()>=end+10, 'page heading overlaps reading body'
                capture=win.grabWindow()
                assert capture.width()>0, 'page has no rendered pixels'
                output=os.environ.get('MIRA_APPEARANCE_CAPTURE_DIR')
                if output and width==1480:
                    capture.save(str(Path(output)/(family+'-'+(page or 'chat')+'.png')))
        fatal=[m for m in messages if any(s in m for s in ('ReferenceError','TypeError','Cannot assign','Unable to assign','is not a type'))]
        assert not fatal, str(fatal)
        controller.shutdown();win.close();settle(.05)
    qInstallMessageHandler(previous)
    print('MIRA_NATIVE_APPEARANCE_PASS',json.dumps({'family':family,'native_window':original.window().color().name(),
          'personal_font':personal,'solid':.97,'native_off_duration':obj.property('duration'),
          'viewports':[[1480,764],[640,800]]}))


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--probe':
        probe(Path(sys.argv[2]),sys.argv[3])
    else:
        unittest.main(verbosity=2)
