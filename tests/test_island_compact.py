#!/usr/bin/env python3
"""Production compact Island, real Qt text/layout/input; never the owner bus."""
from pathlib import Path
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui/main.qml'
UI=SOURCE.parent


def fixture(source, old=False, broken_route=False):
    body=source[source.index('    compactRepresentation: FocusScope {'):source.index('    fullRepresentation:')]
    body=body.replace('    compactRepresentation: FocusScope {','    FocusScope {',1)
    body=body.replace('id: compact','id: compact; objectName: "compact"',1)
    body=body.replace('id: compactAction','id: compactAction; objectName: "compactAction"',1)
    if broken_route:
        prefix, action=body.split('id: compactAction;',1)
        route='Qt.openUrlExternally("moos://app/remote")'
        assert action.count(route)==1, 'negative must mutate the exercised shared action'
        body=prefix+'id: compactAction;'+action.replace(route,
                          'Qt.openUrlExternally("moos://app/store")',1)
    # Record actual production routing without launching apps or stopping any
    # privacy source. The fixture never sends an action to the owner's bus.
    body=body.replace('Qt.openUrlExternally(', 'root.recordUrl(')
    if old:
        # The actual old defect: a17px claimed line for28px Arabic painting.
        body=body.replace('id: compactCaption','id: compactCaption',1)
        start=body.index('                    PC3.Label {')
        part=body[start:].replace('anchors.fill: parent','anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; height: 17',1)
        part=part.replace('fontSizeMode: Text.VerticalFit','fontSizeMode: Text.FixedSize',1)
        body=body[:start]+part
    props=dict(active=True,remotePresent=False,privacyPresent=False,storeJobPresent=False,moaiJobPresent=False,
        mediaPresent=True,playing=False,canControl=True,canPause=True,canPlay=True,compactFocused=False,
        compactHovered=False,contextIcon='moos-moplayer',compactTitle='',contextTitle='Full context',
        contextSource='Application and artist',artUrl='',artworkSource='',artworkBridgeFailed=False,expanded=False,
        hasTimeline=True,hasVolume=False,remoteMode='active',remoteSessions=2,privacyType='camera',privacyNodeId='0',
        progress=.4,storeJobProgress=35,moaiJobIcon='moos-moai',motionEnabled=False,motionFast=0,motionGeometry=0)
    text='''import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3
import org.moos.ui as MoUI
import "%s"
Window { id: root; width: 230; height:110; visible:true
 readonly property var design: MoUI.Tokens
 readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft
 property var player: null
 property int primaryCount: 0
 property int toggleCount: 0
 property int miraCount: 0
 property string lastRoute: ""
 function local(ar,en){return rtl?ar:en}
 function bounded(v,a,b){return Math.max(a,Math.min(b,v))}
 function decodePx(v){return v}
 function openPrimary(){primaryCount++}
 function openMoAI(){miraCount++;lastRoute="mira"}
 function recordUrl(url){lastRoute=url;return true}
 function togglePlaying(){toggleCount++}
'''%UI.as_uri()
    for name,value in props.items():
        kind='bool' if isinstance(value,bool) else 'real' if isinstance(value,(int,float)) else 'string'
        text+='property '+kind+' '+name+': '+json.dumps(value)+'\n'
    return text+body+'\n}'


def probe():
    from PySide6.QtCore import QObject,QPoint,QPointF,QUrl,Qt,QEvent,QCoreApplication,qInstallMessageHandler
    from PySide6.QtGui import QColor,QPalette,QKeyEvent
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQuick import QQuickItem,QQuickWindow
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    import configparser
    messages=[];qInstallMessageHandler(lambda k,c,m:messages.append(m))
    app=QApplication([])
    scheme='MoOSUI2BloomLight' if os.environ['PROBE_LIGHT']=='1' else 'MoOSUI2Bloom'
    colors=configparser.ConfigParser();colors.read(ROOT/'system_files/usr/share/color-schemes'/ (scheme+'.colors'))
    palette=QPalette()
    for role,key in ((QPalette.Window,'BackgroundNormal'),(QPalette.WindowText,'ForegroundNormal'),(QPalette.Text,'ForegroundNormal'),(QPalette.ButtonText,'ForegroundNormal')):
        palette.setColor(role,QColor(*map(int,colors['Colors:Window'][key].split(','))))
    app.setPalette(palette)
    engine=QQmlApplicationEngine();engine.setProperty('_kirigamiTheme','org.kde.desktop');engine.load(QUrl.fromLocalFile(sys.argv[2]))
    assert engine.rootObjects(),messages
    window=engine.rootObjects()[0];compact=window.findChild(QQuickItem,'compact');caption=window.findChild(QQuickItem,'islandCompactCaption')
    assert compact and caption
    assert QTest.qWaitForWindowExposed(window,3000)
    rows=[];is_old=os.environ.get('PROBE_OLD')=='1'
    for height in (34,40,54):
        compact.setWidth(compact.implicitWidth());compact.setHeight(height);compact.setX(12);compact.setY(20)
        stable=compact.width()
        for context in ('search','remote','privacy','store','moai','media'):
            for key in ('remotePresent','privacyPresent','storeJobPresent','moaiJobPresent','mediaPresent'):
                window.setProperty(key,key==dict(remote='remotePresent',privacy='privacyPresent',store='storeJobPresent',moai='moaiJobPresent',media='mediaPresent').get(context,''))
            window.setProperty('active',context!='search')
            window.setProperty('compactTitle','اختبار حدود النص العربية — عنوان طويل جداً في MoOS مع KDE' if window.property('rtl') else 'A long title with file names & <plain text> — MoOS KDE')
            window.setProperty('motionEnabled',os.environ['PROBE_FACTOR']=='1')
            QTest.qWait(20)
            rect=caption.mapRectToItem(compact,caption.boundingRect())
            painted=caption.property('paintedHeight')
            if is_old:
                assert painted>caption.height()+1,'old line did not reproduce'
                print('OLD_ISLAND_INK_OVERFLOW',flush=True)
                raise AssertionError('caption painting exceeds its line box')
            assert compact.width()==stable==171,('moving panel slot',compact.width())
            assert caption.property('maximumLineCount')==1
            assert painted<=caption.height()+.1,('caption ink',height,context,painted,caption.height())
            assert rect.left()>=8 and rect.right()<=stable-8,rect
            assert rect.top()>=2 and rect.bottom()<=height-2,(height,context,rect)
            assert caption.width()>=50,(height,context,caption.width())
            rows.append(dict(height=height,context=context,paintedHeight=painted,box=[rect.x(),rect.y(),rect.width(),rect.height()]))
        # The real production MediaControl receives pointer, keys and a Qt
        # touch event. Its callback is isolated, so no media or privacy action
        # reaches the desktop. This is not physical Wayland touch acceptance.
        controls=[item for item in compact.childItems()]
        def descendants(item):
            for child in item.childItems():
                yield child
                yield from descendants(child)
        button=next(x for x in descendants(compact) if x.property('label') in ('تشغيل','Play') and x.isVisible())
        at=button.mapToScene(QPointF(button.width()/2,button.height()/2));point=QPoint(round(at.x()),round(at.y()))
        n=window.property('toggleCount');QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,point);assert window.property('toggleCount')==n+1
        button.forceActiveFocus()
        for key in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space):
            n=window.property('toggleCount');QTest.keyClick(window,key);assert window.property('toggleCount')==n+1
        touch=QTest.createTouchDevice();n=window.property('toggleCount')
        QTest.touchEvent(window,touch).press(0,point,window).commit();QTest.touchEvent(window,touch).release(0,point,window).commit();QTest.qWait(10)
        assert window.property('toggleCount')==n+1
    # Every context retains its original executor and priority while sharing
    # one physical button. A planted wrong Remote destination must fail here.
    button=compact.findChild(QQuickItem,'compactAction');assert button
    for flag in ('remotePresent','privacyPresent','storeJobPresent','moaiJobPresent','mediaPresent'):
        window.setProperty(flag,True)
    for flag,expected in (('remotePresent','moos://app/remote'),
                          ('privacyPresent','moos://privacy/stop/camera/0'),
                          ('storeJobPresent','moos://app/store'),
                          ('moaiJobPresent','mira'),('mediaPresent','media')):
        QTest.qWait(10);window.setProperty('lastRoute','');n=window.property('toggleCount')
        at=button.mapToScene(QPointF(button.width()/2,button.height()/2))
        QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(at.x()),round(at.y())))
        got='media' if window.property('toggleCount')==n+1 else window.property('lastRoute')
        if got!=expected:
            print('ISLAND_ACTION_OWNER_MISMATCH',flag,expected,got,flush=True)
            raise AssertionError('shared action changed its executor or priority')
        window.setProperty(flag,False)
    # Parent popup keys also keep the one activation and held-key guard.
    window.setProperty('active',False);QTest.qWait(10);compact.forceActiveFocus()
    for key in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space):
        n=window.property('primaryCount');QTest.keyClick(window,key)
        assert window.property('primaryCount')==n+1,('popup key',key)
        repeat=QKeyEvent(QEvent.KeyPress,key,Qt.NoModifier,'',True,2)
        QCoreApplication.sendEvent(window,repeat)
        assert window.property('primaryCount')==n+1,('held popup key',key)
    errors=[m for m in messages if any(k in m.lower() for k in ('typeerror','referenceerror','unable to assign','cannot assign','binding loop','failed to load','is not a type'))]
    assert not errors,errors
    print('ISLAND_COMPACT_PROOF '+json.dumps(dict(samples=rows,tablet=os.environ['KDE_KIRIGAMI_TABLET_MODE'],scale=os.environ['QT_SCALE_FACTOR'],light=os.environ['PROBE_LIGHT'],locale=os.environ['LANG'],input='mouse/key/Qt-touch')),flush=True)


class CompactIsland(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec('PySide6') is None:self.skipTest('native Qt development runtime unavailable')

    def case(self, language, light, tablet, scale, factor, old=False, broken_route=False):
        with tempfile.TemporaryDirectory(prefix='moos-island-compact-') as tmp:
            p=Path(tmp);env={k:v for k,v in os.environ.items() if k in ('PATH','PYTHONPATH')}
            for name in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
                path=p/name;path.mkdir(mode=0o700);env[name]=str(path)
            env.update(DBUS_SESSION_BUS_ADDRESS='unix:path='+str(p/'no-bus'),XDG_CONFIG_DIRS=str(p/'XDG_CONFIG_HOME'),
                LANG='ar_SA.UTF-8' if language=='ar' else 'en_US.UTF-8',LANGUAGE=language,
                QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QT_QPA_PLATFORMTHEME='kde',QML_DISABLE_DISK_CACHE='1',
                QML_IMPORT_PATH=str(ROOT/'system_files/usr/lib64/qt6/qml'),KDE_KIRIGAMI_TABLET_MODE=str(int(tablet)),
                QT_SCALE_FACTOR=str(scale),PROBE_LIGHT=str(int(light)),PROBE_FACTOR=str(factor),PROBE_OLD=str(int(old)))
            (p/'XDG_CONFIG_HOME/kdeglobals').write_text('[KDE]\nAnimationDurationFactor='+str(factor)+'\n')
            qml=p/'probe.qml';qml.write_text(fixture(SOURCE.read_text(),old,broken_route))
            result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--probe',str(qml)],env=env,capture_output=True,text=True,timeout=15)
            if broken_route:
                self.assertNotEqual(result.returncode,0)
                self.assertIn('ISLAND_ACTION_OWNER_MISMATCH',result.stdout)
            elif old:
                self.assertNotEqual(result.returncode,0)
                self.assertIn('OLD_ISLAND_INK_OVERFLOW',result.stdout)
            else:
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('ISLAND_COMPACT_PROOF ',result.stdout)
            if os.environ.get('MOOS_COMPACT_PROOF_DIR'):
                out=Path(os.environ['MOOS_COMPACT_PROOF_DIR']);out.mkdir(parents=True,exist_ok=True)
                (out/f'{language}-light{int(light)}-tablet{int(tablet)}-scale{scale}-motion{factor}-old{int(old)}-badroute{int(broken_route)}.json').write_text(json.dumps(dict(exit=result.returncode,stdout=result.stdout,stderr=result.stderr),indent=2)+'\n')

    def test_actual_native_text_and_controls(self):
        for language in ('ar','en'):
            for light in (False,True):
                for tablet in (False,True):
                    for scale in (1,1.5,2.5):
                        for factor in (0,1):
                            with self.subTest(language=language,light=light,tablet=tablet,scale=scale,factor=factor):
                                self.case(language,light,tablet,scale,factor)

    def test_fixed_height_old_line_is_a_completed_functional_negative(self):
        self.case('ar',True,False,2.5,0,old=True)

    def test_wrong_shared_action_owner_is_a_completed_functional_negative(self):
        self.case('ar',True,False,2.5,0,broken_route=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--probe':probe()
    else:unittest.main()
