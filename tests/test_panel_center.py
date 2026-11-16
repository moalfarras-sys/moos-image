#!/usr/bin/env python3
"""Exercise the shipped native panel center and fixed-action transaction contract."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/'build_files/plasma_logout/control-center/qml'


def native():
    from PySide6.QtCore import QUrl,QObject,Qt,QPoint,QPointF,qInstallMessageHandler
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlEngine,QQmlComponent,QQmlExpression
    from PySide6.QtQuick import QQuickWindow
    from PySide6.QtTest import QTest
    import json
    warnings=[]
    qInstallMessageHandler(lambda t,c,m:warnings.append(m))
    app=QApplication([])
    from PySide6.QtGui import QPalette,QColor,QFontDatabase,QFont
    import configparser
    for filename in ('MeyarSans[wght].ttf','MeyarArabic[wght].ttf'):
        assert QFontDatabase.addApplicationFont(str(ROOT/'system_files/usr/share/fonts/meyar'/filename))>=0
    app.setFont(QFont('Meyar Sans'))
    ini=configparser.ConfigParser();scheme=os.environ.get('MOOS_CENTER_SCHEME') or ('MoOSUI2AuroraLight' if '--light' in sys.argv else 'MoOSUI2Aurora')
    ini.read(ROOT/('system_files/usr/share/color-schemes/'+scheme+'.colors'))
    palette=QPalette()
    for role,group,key in ((QPalette.Window,'Colors:Window','BackgroundNormal'),(QPalette.WindowText,'Colors:Window','ForegroundNormal'),(QPalette.Text,'Colors:View','ForegroundNormal'),(QPalette.ButtonText,'Colors:Button','ForegroundNormal'),(QPalette.Button,'Colors:Button','BackgroundNormal'),(QPalette.Base,'Colors:View','BackgroundNormal'),(QPalette.Highlight,'Colors:Selection','BackgroundNormal'),(QPalette.HighlightedText,'Colors:Selection','ForegroundNormal')):
        palette.setColor(role,QColor(*map(int,ini[group][key].split(','))))
    app.setPalette(palette)
    engine=QQmlEngine()
    if '--wrong-owner' not in sys.argv:engine.setProperty('_kirigamiTheme','KirigamiPlasmaStyle')
    engine.addImportPath(str(ROOT/'system_files/usr/lib64/qt6/qml'))
    components=[]
    def create(name):
        c=QQmlComponent(engine,QUrl.fromLocalFile(str(UI/name)))
        assert not c.isError(),[e.toString() for e in c.errors()]
        components.append(c)
        o=c.create();assert o is not None,[e.toString() for e in c.errors()]
        return o
    b=create('CenterBackend.qml');b.setProperty('testing',True)
    good={"volume":45,"brightness":50,"muted":False,"mic_muted":False,"wifi":True,"bluetooth":False,"dnd":False,"night_light":False,"power_profile":"balanced"}
    result=lambda d,code=0:{"exit code":code,"exit status":0,"stdout":json.dumps(d)}
    b.refresh();b.finish(b.property('statusCommand'),result(good))
    assert b.property('ready') and not b.property('busy')
    for field,value in [('volume',101),('brightness',4),('wifi','on; echo unsafe'),('power_profile','other'),('shell','id')]:
        assert b.commandFor(field,value)=="",(field,value)
    assert b.request('wifi',False)
    assert not b.request('muted',True),'pending controls must be inert'
    action=b.property('currentCommand');b.finish(action,result({},7))
    b.finish(b.property('statusCommand'),result(good))
    assert b.property('errorText') and b.property('state').toVariant()['wifi'] is True
    b.setProperty('errorText','')
    assert b.request('volume',60)
    b.finish(b.property('currentCommand'),result({}))
    b.finish(b.property('statusCommand'),result(good))
    assert b.property('errorText'),'exit0 without measured value must fail'
    b.setProperty('errorText','')
    assert b.request('volume',60);b.finish(b.property('currentCommand'),result({}))
    b.finish(b.property('statusCommand'),result({**good,'volume':60}))
    assert b.property('ready') and not b.property('errorText')
    b.refresh();b.finish(b.property('statusCommand'),result({**good,'wifi':'false'}))
    assert not b.property('ready') and b.property('errorText')
    b.refresh();b.finish(b.property('statusCommand'),result({**good,'wifi':None}))
    assert not b.request('wifi',True),'unknown hardware is not off'
    qml='''import QtQuick
import org.kde.kirigami as K
import "'''+UI.as_uri()+'''" as C
Item {
 width:780; height:700
 property QtObject nativeTheme: K.Theme
 property color nativeSurface: K.Theme.backgroundColor
 property color nativeSelection: K.Theme.highlightColor
 property color nativeText: K.Theme.textColor
 property QtObject host: QtObject { property bool expanded:true }
 property QtObject recorder: QtObject {
  property var state: ({volume:45,brightness:50,wifi:true,bluetooth:false,dnd:false,night_light:false,muted:false,mic_muted:false,power_profile:"balanced"})
  property bool ready:true
  property bool busy:false
  property string pendingField:""
  property string errorText:""
  property var calls:[]
  function request(field,value) { calls=calls.concat([{field:field,value:value}]); return true; }
  function report() {return JSON.stringify(calls);}
  function measured() {state={volume:62,brightness:74,wifi:true,bluetooth:false,dnd:false,night_light:false,muted:false,mic_muted:false,power_profile:"balanced"};}
  function refresh() {}
 }
 Component { id:calendar; Item {} }
 C.ControlCenterView {id:center;objectName:"view";anchors.fill:parent;opened:parent.host.expanded;onCloseRequested:parent.host.expanded=false;backendOverride:parent.recorder;reviewMode:true}
}'''
    c=QQmlComponent(engine);c.setData(qml.encode(),QUrl.fromLocalFile(str(ROOT/'tests/center-fixture.qml')))
    assert not c.isError(),[e.toString() for e in c.errors()]
    item=c.create();assert item is not None,[e.toString() for e in c.errors()]
    assert item.property('nativeTheme').metaObject().className()=='PlasmaTheme','native Plasma theme owner required'
    window=QQuickWindow();window.setColor(palette.color(QPalette.Window));item.setParentItem(window.contentItem());window.show()
    for attempt in range(100):
        if item.property('nativeSurface')==palette.color(QPalette.Window) and item.property('nativeSelection')==palette.color(QPalette.Highlight):break
        QTest.qWait(10)
    assert item.property('nativeSurface')==palette.color(QPalette.Window),('native selected-style surface differs from source',item.property('nativeSurface').name(),palette.color(QPalette.Window).name())
    assert item.property('nativeSelection')==palette.color(QPalette.Highlight),'native selected-style accent differs from source'
    def rgb(color):return (color.redF(),color.greenF(),color.blueF())
    def over(ink,base,alpha):return tuple(alpha*a+(1-alpha)*b for a,b in zip(ink,base))
    def lum(color):
        linear=lambda c:c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
        return sum(w*linear(c) for w,c in zip((.2126,.7152,.0722),color))
    foreground=rgb(item.property('nativeText'));surface=rgb(item.property('nativeSurface'));accent=rgb(item.property('nativeSelection'))
    for fill in (surface,over(accent,surface,.17),over(foreground,surface,.045)):
        ink=over(foreground,fill,.78)
        ratio=(max(lum(ink),lum(fill))+.05)/(min(lum(ink),lum(fill))+.05)
        assert ratio>=4.5,('native secondary ink contrast',scheme,ratio)
    view=item.findChild(QObject,'view');fake=item.property('recorder');slider=item.findChild(QObject,'centerSlider_volume')
    for width,height in ((780,650),(440,650),(420,650),(320,480),(280,480)):
        item.setWidth(width);item.setHeight(height);window.resize(width,height);QTest.qWait(80)
        assert len(json.loads(fake.report()))==0,'reading/rendering wrote back a device value'
        assert slider.height()>=44
        fake.measured();QTest.qWait(30)
        assert len(json.loads(fake.report()))==0,'snapshot update submitted a slider action'
        assert slider.property('value')==62,'measured readback did not reach the slider'
    item.setWidth(780);item.setHeight(650);window.resize(780,650);QTest.qWait(60)
    pos=slider.mapToScene(QPointF(slider.width()*.7,slider.height()/2))
    QTest.mousePress(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(pos.x()),round(pos.y())))
    assert len(json.loads(fake.report()))==0,'slider committed before release'
    QTest.mouseRelease(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(pos.x()),round(pos.y())));QTest.qWait(20)
    assert len(json.loads(fake.report()))==1,("pointer",pos.x(),pos.y(),slider.width(),slider.height(),slider.property("value"),fake.report())
    device=QTest.createTouchDevice()
    touchPoint=QPoint(round(pos.x()-40),round(pos.y()))
    QTest.touchEvent(window,device).press(0,touchPoint,window).commit();QTest.qWait(30)
    assert len(json.loads(fake.report()))==1,'touch slider committed before release'
    QTest.touchEvent(window,device).release(0,touchPoint,window).commit();QTest.qWait(40)
    assert len(json.loads(fake.report()))==2,'touch release did not submit the value'
    def visual(name,scope=view):
        import json
        expression=QQmlExpression(engine.rootContext(),scope, 'JSON.stringify((function find(items) { for (const child of items) { if(child.objectName === '+json.dumps(name)+') { const p=child.mapToItem(null,child.width/2,child.height/2); return {x:p.x,y:p.y,width:child.width,height:child.height}; } const nested=find(child.children || []);if(nested)return nested; } return null; })(children))')
        result=expression.evaluate()[0];assert not expression.hasError(),expression.error().toString()
        return json.loads(result)
    details=visual('centerTileDetails_'+('واي فاي' if '--rtl' in sys.argv else 'Wi-Fi'))
    assert details is not None and details['width']>=44 and details['height']>=44,details
    detailDestinations=[]
    view.nativeAppletRequested.connect(lambda route:detailDestinations.append(route))
    at=QPointF(details['x'],details['y'])
    before=len(json.loads(fake.report()))
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(at.x()),round(at.y())))
    assert detailDestinations==['org.kde.plasma.networkmanagement'],'network details did not reach its native owner'
    assert len(json.loads(fake.report()))==before,'opening details also toggled Wi-Fi'
    tabs=item.findChild(QObject,'centerTabs')
    at=tabs.mapToScene(QPointF(tabs.width()/2,tabs.height()/2));start=QPoint(round(at.x()),round(at.y()))
    direction=1 if '--rtl' in sys.argv else -1
    QTest.mousePress(window,Qt.LeftButton,Qt.NoModifier,start)
    for step in range(1,9):QTest.mouseMove(window,start+QPoint(step*12*direction,0),20)
    QTest.mouseRelease(window,Qt.LeftButton,Qt.NoModifier,start+QPoint(96*direction,0));QTest.qWait(40)
    assert view.property('page')==1,'notification navigation gesture failed'
    view.setProperty('page',0);QTest.qWait(40)
    if os.environ.get('MOOS_CENTER_CAPTURE_DIR'):
        capture=Path(os.environ['MOOS_CENTER_CAPTURE_DIR']);capture.mkdir(parents=True,exist_ok=True)
        item.setWidth(440);item.setHeight(700);window.resize(440,700);QTest.qWait(200)
        assert window.grabWindow().save(str(capture/(('ar-' if '--rtl' in sys.argv else 'en-')+scheme+'.png')))
        item.setWidth(780);item.setHeight(650);window.resize(780,650);QTest.qWait(80)
    tools=item.findChild(QObject,'centerTools')
    assert tools is not None and tools.height()>=44,'all tray items need an accessible destination'
    power=item.findChild(QObject,'centerPower')
    assert power is not None and power.height()>=44,'power profiles require a native destination'
    settings=item.findChild(QObject,'centerSettings')
    assert settings is not None and settings.height()>=44
    routes=[];destinations=[]
    view.routeRequested.connect(lambda route:routes.append(route))
    view.nativeAppletRequested.connect(lambda route:destinations.append(route))
    at=power.mapToScene(QPointF(power.width()/2,power.height()/2))
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(at.x()),round(at.y())))
    assert destinations==['org.kde.plasma.battery'],'power did not use its native owner'
    at=settings.mapToScene(QPointF(settings.width()/2,settings.height()/2))
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,QPoint(round(at.x()),round(at.y())))
    assert routes==['moos://settings/full'] and item.property('host').property('expanded') is False,'Settings destination stayed covered by center'
    item.property('host').setProperty('expanded',True);QTest.qWait(80)
    handle=item.findChild(QObject,'centerHandle')
    point=handle.mapToScene(QPointF(handle.width()/2,handle.height()/2))
    start=QPoint(round(point.x()),round(point.y()))
    QTest.mousePress(window,Qt.LeftButton,Qt.NoModifier,start)
    for step in range(1,9):QTest.mouseMove(window,start+QPoint(0,step*12),20)
    QTest.mouseRelease(window,Qt.LeftButton,Qt.NoModifier,start+QPoint(0,96));QTest.qWait(30)
    assert item.property('host').property('expanded') is False,'handle drag failed to close'
    item.property('host').setProperty('expanded',True);QTest.qWait(80)
    QTest.keyClick(window,Qt.Key_Escape);QTest.qWait(20)
    assert item.property('host').property('expanded') is False
    from PySide6.QtCore import QAbstractListModel,QModelIndex,Property,Slot
    class History(QAbstractListModel):
        def __init__(self):
            super().__init__();self.calls=[]
            self.row={"applicationName":"MoOS Test","applicationIconName":"dialog-information","summary":"تحديث — Update","body":"مراجعة خاصة · Private native notification","closable":True,"type":1,"percentage":0,"hasDefaultAction":False,"actionNames":["review"],"actionLabels":["مراجعة طويلة · Long notification action " * 16],"hasReplyAction":False,"resident":False,"jobState":0,"suspendable":False,"killable":False}
            self.roles={Qt.UserRole+i:k.encode() for i,k in enumerate(self.row)}
        def roleNames(self):return self.roles
        def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else 1
        def data(self,index,role):return self.row.get(self.roles.get(role,b'').decode()) if index.isValid() else None
        @Property(int,constant=True)
        def expiredNotificationsCount(self):return 0
        @Property(int,constant=True)
        def unreadNotificationsCount(self):return 1
        @Slot(QModelIndex,str,int)
        def invokeAction(self,index,name,behavior):self.calls.append((index.row(),name,behavior))
    history=History()
    nc=QQmlComponent(engine,QUrl.fromLocalFile(str(UI/'CenterNotifications.qml')))
    assert not nc.isError(),[e.toString() for e in nc.errors()]
    notices=nc.createWithInitialProperties({'appletInterface':item.property('host'),'modelOverride':history})
    assert notices is not None,[e.toString() for e in nc.errors()]
    nw=QQuickWindow();notices.setParentItem(nw.contentItem());notices.setWidth(360);notices.setHeight(520);nw.resize(360,520);nw.show();QTest.qWait(60)
    assert notices.property('presentedCount')==0,'closed center presented notification history'
    item.property('host').setProperty('expanded',True);QTest.qWait(120)
    assert notices.property('presentedCount')==1,'open center did not present notification history'
    from PySide6.QtQml import QQmlExpression
    expression=QQmlExpression(engine.rootContext(),notices,'''JSON.stringify((function find(items) {
        for (let i=0;i<items.length;i++) {
            let child=items[i];
            if (child.objectName==="centerNotificationAction_0_0") {
                let p=child.mapToItem(null,child.width/2,child.height/2);
                return {x:p.x,y:p.y,width:child.width,limit:child.parent.width};
            }
            let result=find(child.children || []);if(result)return result;
        }
        return null;
    })(children))''')
    result=expression.evaluate()[0]
    assert not expression.hasError(),expression.error().toString()
    point=json.loads(result);assert point is not None,('native action not created',warnings)
    assert 0<point['width']<=point['limit'] and point['width']<=336,'long action overflowed its native card'
    assert 0<=point['x']<=360 and 0<=point['y']<=520,point
    QTest.mouseClick(nw,Qt.LeftButton,Qt.NoModifier,QPoint(round(point['x']),round(point['y'])))
    assert len(history.calls)==1 and history.calls[0][0:2]==(0,'review'),history.calls
    bad=[m for m in warnings if any(t in m for t in ('ReferenceError','TypeError','Binding loop','Unable to assign','Cannot assign','not a type'))]
    assert not bad,bad
    print('PANEL_CENTER_NATIVE_PASS: executor negatives, measured readback,320/420/780px, slider release and Escape')


class PanelCenter(unittest.TestCase):
    def test_native_transaction_and_input(self):
        try:import PySide6
        except ImportError:self.skipTest('native Qt unavailable; installed-session qualification still required')
        with tempfile.TemporaryDirectory(prefix='moos-center-test-') as name:
            base=Path(name);env=dict(os.environ)
            for k in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
                d=base/k;d.mkdir(mode=0o700);env[k]=str(d)
            env.update(QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='kde',XDG_DATA_DIRS=str(ROOT/'system_files/usr/share')+':/usr/local/share:/usr/share',XDG_CONFIG_DIRS=str(base/'XDG_CONFIG_HOME'),QT_QUICK_BACKEND='software',QML_DISABLE_DISK_CACHE='1')
            for k in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS'):env.pop(k,None)
            config=base/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+name+'</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
            cases=[('MoOSUI2Aurora',False),('MoOSUI2AuroraLight',True)]
            if os.environ.get('MOOS_CENTER_ALL_THEMES')=='1':
                cases=[(p.stem, p.stem.endswith('Light') or p.stem in ('MoOSUI2Light','MoOSUI2Daylight')) for p in sorted((ROOT/'system_files/usr/share/color-schemes').glob('MoOS*.colors'))]
            for language in ('ar_SA.UTF-8','en_US.UTF-8'):
                for scheme,reduced in cases:
                    light=reduced
                    env['LANG']=language;env['LC_ALL']=language;env['MOOS_CENTER_SCHEME']=scheme
                    (base/'XDG_CONFIG_HOME/kdeglobals').write_text((ROOT/('system_files/usr/share/color-schemes/'+scheme+'.colors')).read_text()+'\n[KDE]\nAnimationDurationFactor='+('0' if reduced else '1')+'\n[Icons]\nTheme='+scheme+'\n')
                    style='MoOSUI2' if scheme=='MoOSUI2Dark' else 'MoOSUI2Light' if scheme=='MoOSUI2Light' else scheme
                    (base/'XDG_CONFIG_HOME/plasmarc').write_text('[Theme]\nname='+style+'\n')
                    command=['dbus-run-session','--config-file',str(config),'--',sys.executable,str(Path(__file__).resolve()),'--native']+(['--light'] if light else [])+(['--rtl'] if language.startswith('ar') else [])
                    if scheme=='MoOSUI2Aurora' and language.startswith('ar'):
                        wrong=subprocess.run(command+['--wrong-owner'],capture_output=True,text=True,env=env,timeout=40)
                        self.assertNotEqual(wrong.returncode,0,'application palette falsely qualified Plasma appearance')
                        self.assertIn('native Plasma theme owner required',wrong.stderr)
                    r=subprocess.run(command,capture_output=True,text=True,env=env,timeout=40)
                    self.assertEqual(r.returncode,0,str((language,scheme,reduced))+r.stdout+r.stderr)
                    self.assertIn('PANEL_CENTER_NATIVE_PASS',r.stdout)

if __name__=='__main__':
    if '--native' in sys.argv:native()
    else:unittest.main(verbosity=2)
