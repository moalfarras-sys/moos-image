#!/usr/bin/env python3
"""Native notification presentation must preserve its original lifecycle."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
PAYLOAD=ROOT/'build_files/plasma_logout/control-center/notification-qml'
ORIGINAL={
 'main.qml':'e807742f5c936a997a52161474d4b9920cba91d9b31ebb2aedb7a32ae94dcb47',
 'global/Globals.qml':'a3a4d9c506a453eaf8d3ff0e88a72d0c22f0f8d8797c153e802273c8c8cb2931',
 'NotificationPopup.qml':'d15452c7b7dea9d80f197e4e01c42f37f8ba6c2d6a5035146ce7e5cfdb297b6c'}

def block(source,anchor):
 start=source.index(anchor);opening=source.index('{',start);depth=0
 for end in range(opening,len(source)):
  if source[end]=='{':depth+=1
  elif source[end]=='}':
   depth-=1
   if depth==0:return source[start:end+1],source[opening+1:end]
 raise AssertionError('unterminated production block')

def native():
 from PySide6.QtCore import QUrl
 from PySide6.QtGui import QGuiApplication
 from PySide6.QtQml import QQmlEngine,QQmlComponent,QQmlExpression
 from PySide6.QtTest import QTest
 app=QGuiApplication([]);app.setQuitOnLastWindowClosed(False);engine=QQmlEngine()
 popup=(PAYLOAD/'NotificationPopup.qml').read_text()
 _,running=block(popup,'                running: {')
 a=popup.index('readonly property bool moosPresentationSuppressed:')+len('readonly property bool moosPresentationSuppressed:')
 suppression=popup[a:popup.index('\n    visible:',a)].strip()
 cases=[('represented',{},1,False),('overflow',{'moosNativeVisible':False},0,False),('permanent',{'deadline':0},0,False),
        ('hover',{'hovered':True},0,False),('menu',{'menuOpen':True},0,True),('drag',{'dragging':True},0,True),
        ('drop',{'acceptableDrop':True},0,True),('reply',{'replying':True,'pendingReply':True},0,True),
        ('popup-only',{'moosCenterHistoryVisible':False},1,True)]
 components=[]
 for old in (True,False):
  for name,values,fired,visible in cases:
   if old and name!='represented':continue
   body=running.replace('!notificationPopup.visible && !notificationPopup.moosPresentationSuppressed','!notificationPopup.visible') if old else running
   qml='''import QtQuick
import QtQuick.Window
Window {
 id:notificationPopup
 width:120;height:120
 property bool moosNativeVisible:true
 property bool moosCenterHistoryVisible:true
 property bool hovered:false
 property bool dragging:false
 property bool menuOpen:false
 property bool acceptableDrop:false
 property bool replying:false
 property bool pendingReply:false
 property int deadline:40
 property int fired:0
 readonly property bool moosPresentationSuppressed: '''+suppression+'''
 visible:moosNativeVisible&&!moosPresentationSuppressed
 property QtObject listener:QtObject {id:focusListener;property bool containsMouse:notificationPopup.hovered}
 property QtObject content:QtObject {id:notificationItem;property bool dragging:notificationPopup.dragging;property bool menuOpen:notificationPopup.menuOpen;property QtObject modelInterface:QtObject {property bool replying:notificationPopup.replying;property bool hasPendingReply:notificationPopup.pendingReply}}
 property QtObject drop:QtObject {id:activateDefaultActionDropArea;property bool containsAcceptableDrag:notificationPopup.acceptableDrop}
 Timer {id:timer;interval:notificationPopup.deadline;running:{'''+body+'''} onTriggered:notificationPopup.fired++}
}'''
   c=QQmlComponent(engine);c.setData(qml.encode(),QUrl.fromLocalFile(str(ROOT/'tests/notification-timeout-fixture.qml')));components.append(c)
   assert not c.isError(),[e.toString() for e in c.errors()]
   item=c.createWithInitialProperties(values);assert item is not None,[e.toString() for e in c.errors()]
   QTest.qWait(110)
   assert item.property('fired')==(0 if old else fired),(old,name,item.property('fired'))
   assert item.isVisible()==visible,(old,name,item.isVisible())
   item.close();item.deleteLater();QTest.qWait(10)
 globals_source=(PAYLOAD/'global/Globals.qml').read_text();function,_=block(globals_source,'    function isRepresentedByCenter(')
 c=QQmlComponent(engine);c.setData(('import QtQml\nQtObject { property var plasmoidItems: []\n'+function+'\n}').encode(),QUrl());components.append(c);o=c.create();assert o is not None,[e.toString() for e in c.errors()]
 for rows,expected in [([],False),([{'moosCenterHistoryVisible':True,'moosCenterHistoryIds':['other']}],False),([{'moosCenterHistoryVisible':False,'moosCenterHistoryIds':['notice']}],False),([{'moosCenterHistoryVisible':True,'moosCenterHistoryIds':['notice']}],True),([{'moosCenterHistoryVisible':False,'moosCenterHistoryIds':['notice']},{'moosCenterHistoryVisible':True,'moosCenterHistoryIds':['notice']}],True)]:
  expression=QQmlExpression(engine.rootContext(),o,'plasmoidItems = '+json.dumps(rows)+'; isRepresentedByCenter("notice")');value=expression.evaluate()[0];assert not expression.hasError(),expression.error().toString();assert value==expected,(rows,value)
 print('NATIVE_NOTIFICATION_PRESENTATION_PASS: original hidden immortality refusal; native expiry, overflow, permanent, interaction, excluded ID and multiple owners')

class Presentation(unittest.TestCase):
 def test_original_lifecycle_and_sound_owners_unchanged(self):
  main=(PAYLOAD/'main.qml').read_text().replace('\n    // The native tray publishes only IDs presented by its open history view.\n    property bool moosCenterHistoryVisible: false\n    property var moosCenterHistoryIds: []\n','')
  globals_source=(PAYLOAD/'global/Globals.qml').read_text();function,_=block(globals_source,'    function isRepresentedByCenter(')
  original_globals=globals_source.replace('\n'+function+'\n','').replace('popup.moosNativeVisible = visible;','popup.visible = visible;').replace('object.moosNativeVisible = true;','object.visible = true;').replace('            moosCenterHistoryVisible: globals.isRepresentedByCenter(notificationId)\n','')
  popup=(PAYLOAD/'NotificationPopup.qml').read_text();start=popup.index('    // Keep delegates, sound');end=popup.index('\n',popup.index('    visible: moosNativeVisible && !moosPresentationSuppressed',start))
  original_popup=(popup[:start]+'    visible: false'+popup[end:]).replace('!notificationPopup.visible && !notificationPopup.moosPresentationSuppressed','!notificationPopup.visible')
  for name,data in [('main.qml',main),('global/Globals.qml',original_globals),('NotificationPopup.qml',original_popup)]:
   self.assertEqual(hashlib.sha256(data.encode()).hexdigest(),ORIGINAL[name],name+' changed beyond the reviewed presentation seam')
 def test_native_timeout_and_representation(self):
  try:import PySide6
  except ImportError:self.skipTest('native Qt unavailable; installed notification journey remains required')
  with tempfile.TemporaryDirectory(prefix='moos-notification-presentation-') as tmp:
   env=dict(os.environ)
   for key in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR'):
    p=Path(tmp)/key;p.mkdir(mode=0o700);env[key]=str(p)
   for key in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS'):env.pop(key,None)
   env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',DBUS_SYSTEM_BUS_ADDRESS='unix:path='+tmp+'/no-system',QML_DISABLE_DISK_CACHE='1')
   config=Path(tmp)/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+tmp+'</listen><auth>EXTERNAL</auth><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
   r=subprocess.run(['dbus-run-session','--config-file',str(config),'--',sys.executable,str(Path(__file__).resolve()),'--native'],env=env,capture_output=True,text=True,timeout=30)
   self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('NATIVE_NOTIFICATION_PRESENTATION_PASS',r.stdout)

if __name__=='__main__':
 if '--native' in sys.argv:native()
 else:unittest.main(verbosity=2)
