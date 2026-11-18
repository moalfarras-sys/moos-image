#!/usr/bin/env python3
"""Native event-driven KWin tablet state, isolated from the owner session.

The real single-key tuple refusal and missing-watcher negative are preserved.
A separate typed D-Bus peer emits KWin's custom notify, without PropertiesChanged.
"""
from pathlib import Path
import sys,os,time,subprocess,json,unittest,tempfile,importlib.util,shutil
if len(sys.argv)==1:
 class MovaTabletMode(unittest.TestCase):
  @unittest.skipUnless(importlib.util.find_spec("PySide6") and importlib.util.find_spec("gi") and shutil.which("dbus-run-session"),"Native Qt/DBus tools unavailable")
  def test_native_events_tuple_refusal_service_loss_and_malformed_state(self):
   with tempfile.TemporaryDirectory(prefix="moos-mova-tablet-") as temporary:
    env={**os.environ,"HOME":temporary,"XDG_CONFIG_HOME":temporary+"/config","XDG_DATA_HOME":temporary+"/data","XDG_CACHE_HOME":temporary+"/cache","XDG_RUNTIME_DIR":temporary,"QT_QPA_PLATFORM":"offscreen","QML_DISABLE_DISK_CACHE":"1"}
    result=subprocess.run(["dbus-run-session","--",sys.executable,__file__,"--native"],env=env,capture_output=True,text=True,timeout=25)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    self.assertIn("PASS external native bool",result.stdout)
 unittest.main()
 raise SystemExit
if sys.argv[1:] and sys.argv[1]=='owner':
 from gi.repository import Gio,GLib
 conn=Gio.bus_get_sync(Gio.BusType.SESSION,None);loop=GLib.MainLoop();state={'value':False}
 typ='s' if len(sys.argv)>2 else 'b'
 xml='<node><interface name="org.kde.KWin.TabletModeManager"><property name="tabletMode" type="'+typ+'" access="read"/><signal name="tabletModeChanged"><arg type="b"/></signal><method name="Change"><arg type="b" direction="in"/></method><method name="Quit"/></interface></node>'
 def method(c,s,p,i,m,args,inv):
  if m=='Change':state['value']=args.unpack()[0];c.emit_signal(None,p,i,'tabletModeChanged',GLib.Variant('(b)',(state['value'],)))
  inv.return_value(GLib.Variant('()',()))
  if m=='Quit':GLib.idle_add(lambda:(loop.quit(),False)[1])
 def prop(c,s,p,i,n):return GLib.Variant(typ,'true' if typ=='s' else state['value'])
 conn.register_object('/org/kde/KWin',Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],method,prop,None)
 Gio.bus_own_name_on_connection(conn,'org.kde.KWin',Gio.BusNameOwnerFlags.NONE,lambda *a:print('READY',flush=True),lambda *a:loop.quit())
 loop.run();sys.exit(0)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtDBus import QDBusConnection,QDBusMessage
source=(Path(__file__).resolve().parents[1]/'system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/main.qml').read_text()
body='    readonly property bool tabletMode:'+source.split('    readonly property bool tabletMode:',1)[1].split('    property string searchQuery:',1)[0]
watcher='    DBus.SignalWatcher {'+body.split('    DBus.SignalWatcher {',1)[1].split('\n    }',1)[0]+'\n    }'
app=QGuiApplication([])
def engine(b):
 e=QQmlApplicationEngine();e.loadData(('import QtQuick\nimport org.kde.plasma.workspace.dbus as DBus\nItem { id: root\n'+b+'\nproperty var rawMode: tabletProperties.properties.tabletMode\nproperty string rawType: typeof tabletProperties.properties.tabletMode\nproperty bool rawPresent: tabletProperties.properties.tabletMode !== undefined\n}').encode(),QUrl('file:///private-tablet.qml'));assert len(e.rootObjects())==1;return e,e.rootObjects()[0]
def wait(fn,why):
 end=time.monotonic()+4
 while time.monotonic()<end:
  app.processEvents();time.sleep(.01)
  if fn():return
 raise AssertionError(why)
e,obj=engine(body);old,oldobj=engine(body.replace(watcher,''));tupleEngine,tupleObj=engine(body.replace('tabletProperties.updateAll()', 'tabletProperties.update("tabletMode")'));assert obj.property('tabletMode') is False
conn=QDBusConnection.sessionBus()
def call(method,args=[]):
 m=QDBusMessage.createMethodCall('org.kde.KWin','/org/kde/KWin','org.kde.KWin.TabletModeManager',method);m.setArguments(args);r=conn.call(m);assert r.type()!=QDBusMessage.ErrorMessage,r.errorMessage()
def owner(*extra):
 p=subprocess.Popen([sys.executable,__file__,'owner',*extra],stdout=subprocess.PIPE,text=True);assert p.stdout.readline().strip()=='READY';return p
p=owner()
try:
 wait(lambda:obj.property('rawMode') is False and oldobj.property('rawMode') is False,'initial property')
 call('Change',[True]);wait(lambda:obj.property('tabletMode') is True,'custom true notify');assert oldobj.property('tabletMode') is False
 wait(lambda:isinstance(tupleObj.property('rawMode'),list),'single-key tuple source');assert tupleObj.property('tabletMode') is False
 call('Change',[False]);wait(lambda:obj.property('tabletMode') is False,'custom false notify')
 call('Change',[True]);wait(lambda:obj.property('tabletMode') is True,'second true notify')
 call('Quit');p.wait(timeout=3);wait(lambda:obj.property('tabletMode') is False,'owner loss')
finally:
 if p.poll() is None:p.terminate();p.wait()
p=owner('string')
try:
 wait(lambda:obj.property('rawPresent') and obj.property('rawType') != 'boolean','wrong type source');assert obj.property('tabletMode') is False
 call('Quit');p.wait(timeout=3)
finally:
 if p.poll() is None:p.terminate();p.wait()
print('PASS external native bool signal/read/loss/malformed and old missing-watch refusal')
