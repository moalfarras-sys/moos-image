#!/usr/bin/env python3
"""Native Qt session view, exact profile canvas and original power owners."""
from pathlib import Path
import importlib.util
import configparser
import json
import os
import subprocess
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'system_files/usr/lib64/qt6/qml'
PROFILES = json.loads((ROOT/'artwork/moos-design/theme-profiles.json').read_text())['profiles']


def check_glyph(button):
    from PySide6.QtQuick import QQuickItem
    glyph=button.findChild(QQuickItem,'moosSessionActionGlyph')
    assert glyph and glyph.isVisible(), 'missing shared session glyph'
    fill=glyph.findChild(QQuickItem,'moosSessionActionGlyphFill')
    icon=glyph.findChild(QQuickItem,'moosSessionActionGlyphInk')
    assert fill and icon
    resolved = str(icon.property('source'))
    assert resolved.startswith('moos-') and icon.property('valid'), ('session symbol did not resolve from MoOS', resolved)
    def luminance(color):
        values=[color.redF(),color.greenF(),color.blueF()]
        values=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in values]
        return sum(a*b for a,b in zip(values,(0.2126,0.7152,0.0722)))
    background=fill.property('color');ink=icon.property('color')
    a,b=sorted((luminance(background),luminance(ink)))
    contrast=(b+0.05)/(a+0.05)
    if contrast < 4.5:
        print('MOOS_SESSION_GLYPH_CONTRAST_MISMATCH',flush=True)
        raise AssertionError(('session glyph ink/fill',background.name(),ink.name(),contrast))
    assert background==glyph.property('accentColor') and ink==glyph.property('inkColor')
    assert glyph.opacity()==1
    return dict(accent=background.name(),ink=ink.name(),contrast=contrast,source=resolved)


def probe():
    from PySide6.QtCore import QUrl, Qt, QPoint, QPointF, QEvent, QCoreApplication
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlEngine, QQmlComponent, QQmlPropertyMap, QQmlExpression
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    app = QApplication([])
    engine = QQmlEngine()
    engine.setProperty('_kirigamiTheme', 'org.kde.desktop')
    types = QQmlPropertyMap()
    for name, value in dict(ShutdownTypeDefault=-1, ShutdownTypeNone=0, ShutdownTypeReboot=1,
                            ShutdownTypeHalt=2, ShutdownTypeLogout=3).items(): types.insert(name, value)
    methods = QQmlPropertyMap()
    for name in ('StandbyState', 'SuspendState', 'HibernateState'):
        methods.insert(name, name != 'HibernateState' or os.environ.get('PROBE_FIVE_ACTIONS') != '1')
    updates = os.environ.get('PROBE_FIVE_ACTIONS') != '1'
    ctx = engine.rootContext()
    for key, value in dict(ShutdownType=types, spdMethods=methods, sdtype=-1, maysd=True,
                           canLogout=True, softwareUpdatePending=updates, rebootToFirmwareSetup=True,
                           rebootToBootLoaderMenu=False, rebootToBootLoaderEntry='').items():
        ctx.setContextProperty(key, value)
    ctx.setContextProperty('proofWallpaperPackage',os.environ['PROBE_IMAGE'].split('/contents/')[0])
    qml = '''import QtQuick
import QtQuick.Window
import org.moos.ui as MoUI
Window {
    id: window; width: %s; height: %s; visible: true
    property string nativeMappedWallpaper: MoUI.WallpaperSources.imageForPackage("/usr/share/wallpapers/" + proofWallpaperPackage)
    property int fired: 0
    property string action: ""
    property int stopped: 0
    Item {
        id: host; anchors.fill: parent
        property real remainingTime: 19
        property bool countingDown: false
        function record(name) { window.action=name; window.fired++ }
        function logoutRequested() { record("logout") }
        function haltRequested() { record("halt") }
        function haltUpdateRequested() { record("halt-update") }
        function rebootRequested() { record("reboot") }
        function rebootUpdateRequested() { record("reboot-update") }
        function cancelRequested() { record("cancel") }
        function lockScreenRequested() { record("lock") }
        function cancelSoftwareUpdateRequested() { record("cancel-update") }
        function suspendRequested(method) { record("sleep-"+method) }
        function rebootRequested2(option) { record("boot-"+option) }
        MoUI.SessionPower {
            sessionHost: host
            cancelCountdown: () => window.stopped++
        }
    }
}''' % (os.environ['PROBE_WIDTH'], os.environ['PROBE_HEIGHT'])
    # Parse and instantiate explicitly. QQmlApplicationEngine.loadData hangs
    # on the native PySide6 stack while QQmlComponent loads this component;
    # retain that harness refusal and probe the real C++ greeter separately.
    component = QQmlComponent(engine)
    component.setData(qml.encode(), QUrl('file:///session-proof.qml'))
    window = component.create()
    assert window, [error.toString() for error in component.errors()]
    assert QTest.qWaitForWindowExposed(window, 3000)
    QTest.qWait(900)
    view = window.findChild(QQuickItem, 'moosSessionPower')
    assert view
    if view.property('activeLook') != os.environ['PROBE_LOOK']:
        print('MOOS_SESSION_LOOK_MISMATCH',flush=True)
        raise AssertionError(('wrong look', view.property('activeLook')))
    assert os.environ['PROBE_IMAGE'] in view.property('sceneWallpaper').toString()
    assert window.property('nativeMappedWallpaper').endswith(os.environ['PROBE_IMAGE'])
    image = view.findChild(QQuickItem, 'moosSessionWallpaper')
    # Keep the enum inside Qt: PySide has no converter for QQuickImageBase's
    # private Status enum. A real QML expression evaluates the same native item.
    assert image
    ready = QQmlExpression(QQmlEngine.contextForObject(image), image, 'status === Image.Ready')
    assert ready.evaluate()[0] is True, ('wallpaper not rendered',view.property('sceneWallpaper'),ready.error().toString())
    assert view.property('motionEnabled') == (os.environ['PROBE_MOTION']=='1')
    def descendants(item):
        for child in item.childItems():
            yield child
            yield from descendants(child)
    buttons = [x for x in descendants(view) if x.metaObject().indexOfProperty('revealOrder') >= 0 and x.isVisible()]
    assert len(buttons) == (6 if os.environ.get('PROBE_FIVE_ACTIONS') == '1' else 9), ('missing capability/update actions', len(buttons))
    geometry = []
    card = view.findChild(QQuickItem, 'moosSessionCard')
    assert card
    surface=card.property('surfaceColor')
    if surface.name()!=os.environ['PROBE_WINDOW_BG'] or card.property('fillOpacity')<0.9:
        print('MOOS_SESSION_POWER_MATERIAL_MISMATCH',flush=True)
        raise AssertionError(('working sheet does not match selected Window material',surface.name()))
    def over(ink,bg):
        alpha=ink.alphaF()
        return tuple(a*alpha+b*(1-alpha) for a,b in zip(
            (ink.redF(),ink.greenF(),ink.blueF()),bg))
    def luminance(rgb):
        return sum(a*b for a,b in zip((v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb),(.2126,.7152,.0722)))
    for button in buttons:
        rect = button.mapRectToItem(view, button.boundingRect())
        assert rect.left() >= 0 and rect.right() <= view.width(), ('horizontal overflow', button.property('text'), rect)
        assert rect.top() >= 0 and rect.bottom() <= view.height(), ('vertical overflow', button.property('text'), rect)
        assert button.width() >= 44 and button.height() >= 44, ('input target', rect)
        inside=button.mapRectToItem(card,button.boundingRect())
        assert inside.left()>=0 and inside.right()<=card.width() and inside.top()>=0 and inside.bottom()<=card.height(), ('control outside card',inside)
        caption=button.findChild(QQuickItem,'moosPowerActionCaption');assert caption
        assert caption.property('paintedHeight') <= caption.height()+1, ('caption ink outside line box',button.property('text'))
        assert not caption.property('truncated'), ('truncated power action',button.property('text'))
        face=button.findChild(QQuickItem,'moosPowerActionSurface');assert face
        # Bound the remaining sheet transparency with both extreme backdrops,
        # including the actual interactive fill and the caption's own alpha.
        for extreme in ((0,0,0),(1,1,1)):
            plate=over(card.property('color'),extreme)
            background=over(face.property('color'),plate)
            foreground=over(caption.property('color'),background)
            low,high=sorted((luminance(background),luminance(foreground)))
            assert (high+.05)/(low+.05)>=4.5, ('composed caption contrast',button.property('text'),(high+.05)/(low+.05))
        if button.property('revealOrder') != 8: check_glyph(button)
        geometry.append(dict(text=button.property('text'), x=rect.x(), y=rect.y(), width=rect.width(), height=rect.height()))
    if os.environ.get('PROBE_FIVE_ACTIONS') == '1':
        actions = [g for b, g in zip(buttons, geometry) if b.property('revealOrder') != 8]
        if len(actions) != 5 or len({round(g['y'], 1) for g in actions}) != 1:
            print('MOOS_SESSION_POWER_LAYOUT_MISMATCH', flush=True)
            raise AssertionError('the ordinary five actions do not share one desktop row')
    # Actual callbacks from the production controls: a sensitive first click
    # only arms, the second reaches the existing native root's signal.
    button = next(x for x in buttons if x.property('revealOrder') == 2)
    point = button.mapToScene(QPointF(button.width()/2, button.height()/2))
    at = QPoint(round(point.x()), round(point.y()))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, at)
    assert window.property('fired') == 0 and button.property('armed') is True
    hint=view.findChild(QQuickItem,'moosSessionConfirmationHint');assert hint
    assert hint.property('paintedHeight') <= hint.height()+1, 'confirmation ink clipped'
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, at)
    if window.property('fired') != 1 or window.property('action') != ('reboot-update' if updates else 'reboot'):
        print('MOOS_SESSION_POWER_DESTINATION_MISMATCH',flush=True)
        raise AssertionError('The shared view changed the native destination')
    assert window.property('stopped') >= 2
    # Navigation cancels the native countdown, and holding Enter cannot turn
    # the first confirmation into a power action.
    button.forceActiveFocus();before=window.property('stopped')
    QTest.keyClick(window,Qt.Key_Left)
    assert window.property('stopped') > before
    button.forceActiveFocus();fired=window.property('fired')
    QTest.keyClick(window,Qt.Key_Return);QTest.qWait(140)
    assert window.property('fired')==fired and button.property('armed') is True
    QCoreApplication.sendEvent(window,QKeyEvent(QEvent.KeyPress,Qt.Key_Return,Qt.NoModifier,'',True,3))
    QTest.qWait(140)
    assert window.property('fired')==fired,'held Enter bypassed confirmation'
    cancel = next(x for x in buttons if x.property('revealOrder') == 8)
    cancel.forceActiveFocus(); QTest.keyClick(window, Qt.Key_Space)
    assert window.property('action') == 'cancel'
    if os.environ.get('MOOS_SESSION_CAPTURE'):
        assert window.grabWindow().save(os.environ['MOOS_SESSION_CAPTURE'])
    print('MOOS_SESSION_CONTINUITY_PROOF ' + json.dumps(dict(buttons=geometry, look=view.property('activeLook'), wallpaper=view.property('sceneWallpaper').toString(), motion=view.property('motionEnabled'))))


def native_button_probe():
    from PySide6.QtCore import QUrl, Qt, QPoint, QPointF
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlEngine,QQmlComponent
    from PySide6.QtQuick import QQuickItem
    from PySide6.QtTest import QTest
    app=QApplication([]);engine=QQmlEngine();engine.setProperty('_kirigamiTheme','org.kde.desktop')
    labels={'ar':('تبديل المستخدم','إيقاف التشغيل'),'en':('Switch user','Shut down'),
            'de':('Benutzer wechseln','Herunterfahren')}[os.environ['PROBE_LANGUAGE']]
    url=(ROOT/'system_files/usr/lib64/qt6/qml/org/kde/breeze/components').as_uri()
    qml='''import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "%s" as NativeSession
Window {
    id: window; width: 640; height: 480; visible: true
    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
    property int activated: 0
    Row {
        anchors.centerIn: parent; spacing: 24
        NativeSession.ActionButton {
            objectName: "nativeSessionNormal"; text: %s
            icon.name: "system-switch-user"; onClicked: window.activated++
        }
        NativeSession.ActionButton {
            objectName: "nativeSessionDestructive"; text: %s
            icon.name: "system-shutdown"; onClicked: window.activated++
        }
    }
}''' % (url,json.dumps(labels[0],ensure_ascii=False),json.dumps(labels[1],ensure_ascii=False))
    component=QQmlComponent(engine);component.setData(qml.encode(),QUrl('file:///native-session-buttons.qml'))
    window=component.create();assert window,[e.toString() for e in component.errors()]
    assert QTest.qWaitForWindowExposed(window,3000);QTest.qWait(350)
    proof=[]
    for name in ('nativeSessionNormal','nativeSessionDestructive'):
        button=window.findChild(QQuickItem,name);assert button and button.isVisible()
        assert button.width()>=44 and button.height()>=44
        rect=button.mapRectToScene(button.boundingRect())
        assert rect.left()>=0 and rect.right()<=window.width() and rect.top()>=0 and rect.bottom()<=window.height()
        caption=button.findChild(QQuickItem,'moosSessionActionCaption');assert caption
        assert not caption.property('truncated') and caption.property('paintedHeight')<=caption.height()+1
        proof.append(check_glyph(button))
        point=button.mapToScene(QPointF(button.width()/2,button.height()/2))
        before=window.property('activated');QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(point.x()),round(point.y())))
        assert window.property('activated')==before+1
        button.forceActiveFocus();QTest.keyClick(window,Qt.Key_Return)
        assert window.property('activated')==before+2
    print('MOOS_NATIVE_SESSION_BUTTON_PROOF '+json.dumps(proof))


class SessionContinuity(unittest.TestCase):
    def test_generated_source_matches_the_one_visual_engine(self):
        p = subprocess.run([sys.executable, str(ROOT/'artwork/generate_moos_session.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout+p.stderr)

    def case(self, width=1536, height=864, language='ar', look='org.moos.ui2.bloom.light', motion=0, broken=None, native_button=False, five_actions=False):
        with tempfile.TemporaryDirectory(prefix='moos-session-') as td:
            home=Path(td)
            env={k:v for k,v in os.environ.items() if k in ('PATH','PYTHONPATH')}
            for name in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
                d=home/name;d.mkdir(mode=0o700);env[name]=str(d)
            env.update(XDG_CONFIG_DIRS=env['XDG_CONFIG_HOME'], XDG_DATA_DIRS=str(ROOT/'system_files/usr/share')+':/usr/share',
                QML_IMPORT_PATH=str(UI), QML_DISABLE_DISK_CACHE='1', QT_QPA_PLATFORM='offscreen',
                QT_QUICK_BACKEND='software', QT_QPA_PLATFORMTHEME='kde',
                DBUS_SESSION_BUS_ADDRESS='unix:path='+td+'/absent',
                DBUS_SYSTEM_BUS_ADDRESS='unix:path='+td+'/absent-system',
                LANG={'ar':'ar_SA.UTF-8','en':'en_US.UTF-8','de':'de_DE.UTF-8'}[language], LANGUAGE=language,
                PROBE_WIDTH=str(width),PROBE_HEIGHT=str(height),PROBE_LOOK=look,PROBE_MOTION=str(motion),PROBE_LANGUAGE=language)
            config=Path(env['XDG_CONFIG_HOME'])
            profile=next(p for p in PROFILES if p['id']==look)
            colors=ROOT/'system_files/usr/share/color-schemes'/(profile['scheme']+'.colors')
            palette=configparser.ConfigParser();palette.read(colors)
            env['PROBE_WINDOW_BG']='#'+''.join(f'{int(v):02x}' for v in palette['Colors:Window']['BackgroundNormal'].split(','))
            expected=profile['wallpaper']+'/contents/'+profile['wallpaperBranch']+'/'
            expected+='1672x941.png' if profile['family']=='bloom' else '3840x2160.jpg'
            env['PROBE_IMAGE']=expected
            if five_actions: env['PROBE_FIVE_ACTIONS']='1'
            (config/'kdeglobals').write_text(colors.read_text()+'\n[KDE]\nAnimationDurationFactor='+str(motion)+'\nLookAndFeelPackage='+look+'\n[Icons]\nTheme='+profile['icons']+'\n')
            (config/'plasmarc').write_text('[Theme]\nname='+profile['style']+'\n')
            before=(config/'kdeglobals').read_bytes()
            if broken:
                copied=home/'qml/org/moos/ui';shutil.copytree(UI/'org/moos/ui',copied)
                env['QML_IMPORT_PATH']=str(home/'qml')
                target=copied/('SessionAppearance.qml' if broken=='look' else 'SessionActionGlyph.qml' if broken=='glyph-ink' else 'SessionPower.qml')
                old,new=('color: glyph.inkColor','color: glyph.accentColor') if broken=='glyph-ink' else ('location: path','fileName: path') if broken=='look' else (
                    'onRebootUpdateRequested: root.sessionHost.rebootUpdateRequested()',
                    'onRebootUpdateRequested: root.sessionHost.haltUpdateRequested()')
                if broken == 'layout':
                    old, new = ('actionCount <= 5 ? actionCount', 'actionCount <= 4 ? actionCount')
                if broken == 'material':
                    old, new = ('Kirigami.Theme.colorSet: Kirigami.Theme.Window', 'Kirigami.Theme.colorSet: Kirigami.Theme.Complementary')
                body=target.read_text();self.assertEqual(body.count(old),1);target.write_text(body.replace(old,new))
            p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--native-button' if native_button else '--probe'],env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual((config/'kdeglobals').read_bytes(),before)
            if broken:
                self.assertNotEqual(p.returncode,0)
                self.assertIn('MOOS_SESSION_GLYPH_CONTRAST_MISMATCH' if broken=='glyph-ink' else 'MOOS_SESSION_LOOK_MISMATCH' if broken=='look' else 'MOOS_SESSION_POWER_LAYOUT_MISMATCH' if broken=='layout' else 'MOOS_SESSION_POWER_MATERIAL_MISMATCH' if broken=='material' else 'MOOS_SESSION_POWER_DESTINATION_MISMATCH',p.stdout)
            else:
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertIn('MOOS_NATIVE_SESSION_BUTTON_PROOF' if native_button else 'MOOS_SESSION_CONTINUITY_PROOF',p.stdout)
                self.assertNotRegex(p.stderr.lower(), r'referenceerror|typeerror|unable to assign|cannot assign|binding loop|is not a type|failed to load|setting initial properties failed')

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_native_actions_and_responsive_frame(self):
        for width, height in ((1536,864), (640,480), (800,1280)):
            for language in ('ar','en'):
                with self.subTest(size=(width,height),language=language):self.case(width,height,language)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_ordinary_desktop_row_and_old_two_row_negative(self):
        for language in ('ar', 'en'):
            self.case(language=language, five_actions=True)
        self.case(five_actions=True, broken='layout')

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_light_working_sheet_refuses_old_complementary_material(self):
        self.case(five_actions=True,broken='material')

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_every_theme_uses_its_actual_rendered_wallpaper_and_native_actions(self):
        for i,profile in enumerate(PROFILES):
            with self.subTest(look=profile['id']):
                self.case(language=('ar','en','de')[i%3],look=profile['id'],motion=i%2)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_wrong_look_and_wrong_native_destination_are_completed_negatives(self):
        self.case(broken='look')
        self.case(broken='destination')
        self.case(broken='glyph-ink')

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_actual_login_lock_action_controls_use_the_same_profile_ink_and_native_input(self):
        for i,profile in enumerate(PROFILES):
            with self.subTest(look=profile['id']):
                self.case(language=('ar','en','de')[i%3],look=profile['id'],native_button=True)
        self.case(broken='glyph-ink',native_button=True)

    def test_both_image_builders_execute_native_power_after_installing_seams(self):
        for script in ('build.sh','build-arm.sh'):
            body=(ROOT/'build_files'/script).read_text()
            self.assertEqual(body.count('python3 /ctx/verify_session_power.py'),1)
            self.assertGreater(body.index('python3 /ctx/verify_session_power.py'),body.index('python3 /ctx/plasma_seams.py build'))


if __name__=='__main__':
    if '--probe' in sys.argv: probe()
    elif '--native-button' in sys.argv: native_button_probe()
    else: unittest.main()
