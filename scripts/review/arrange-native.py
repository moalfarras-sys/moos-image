#!/usr/bin/env python3
"""Prove Arrange anchor exclusion in a private native virtual KWin.

Requires native KWin, Qt D-Bus tools and PySide6. All writable state and sockets
stay under a unique /tmp directory, retained as evidence. No portal or owner
session bus is used; the private bus has no service activation directories.
This is software compositor evidence, not physical display qualification.
"""
import os,pathlib,tempfile,subprocess,time,json
r=pathlib.Path(tempfile.mkdtemp(prefix='moos-arrange-native-')); print(r,flush=True)
for d in ('home','runtime','config','cache','data'): (r/d).mkdir(mode=0o700)
(r/'bus.conf').write_text('<busconfig><type>session</type><listen>unix:path='+str(r/'bus')+'</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/><allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
e=os.environ.copy(); e.update(HOME=str(r/'home'),XDG_RUNTIME_DIR=str(r/'runtime'),XDG_CONFIG_HOME=str(r/'config'),XDG_CACHE_HOME=str(r/'cache'),XDG_DATA_HOME=str(r/'data'),XDG_CONFIG_DIRS=str(r/'config'),DBUS_SESSION_BUS_ADDRESS='unix:path='+str(r/'bus'),LIBGL_ALWAYS_SOFTWARE='1',KWIN_COMPOSE='Q',QT_QUICK_BACKEND='software',WAYLAND_DISPLAY='wayland-arrange-proof',QT_QPA_PLATFORM='wayland',LANG='C.UTF-8',QT_FORCE_STDERR_LOGGING='1',QT_LOGGING_TO_CONSOLE='1')
bus=subprocess.Popen(['dbus-daemon','--nofork','--config-file='+str(r/'bus.conf')],env=e,stdout=(r/'bus.log').open('w'),stderr=subprocess.STDOUT)
kwin=None;client=None
q='/usr/lib64/qt6/bin/qdbus'
def db(*args): return subprocess.run([q,*args],env=e,text=True,capture_output=True,timeout=5)
def script(name,source):
 p=r/(name+'.js');p.write_text(source)
 a=db('org.kde.KWin','/Scripting','org.kde.kwin.Scripting.loadScript',str(p),name)
 if a.returncode: raise RuntimeError(a.stderr)
 a=db('org.kde.KWin','/Scripting','org.kde.kwin.Scripting.start')
 if a.returncode: raise RuntimeError(a.stderr)
 time.sleep(.5)
try:
 time.sleep(.2)
 if bus.poll() is not None:raise RuntimeError('private bus failed: '+(r/'bus.log').read_text())
 kwin=subprocess.Popen(['kwin_wayland','--virtual','--width','1280','--height','720','--socket',e['WAYLAND_DISPLAY'],'--no-lockscreen','--no-global-shortcuts','--no-kactivities'],env=e,stdout=(r/'kwin.log').open('w'),stderr=subprocess.STDOUT)
 for _ in range(60):
  if (r/'runtime'/e['WAYLAND_DISPLAY']).is_socket():break
  if kwin.poll() is not None:raise RuntimeError('KWin exited '+str(kwin.returncode))
  time.sleep(.1)
 else:raise RuntimeError('no private Wayland socket')
 (r/'client.py').write_text('from PySide6.QtWidgets import QApplication,QWidget\nfrom PySide6.QtCore import QTimer\na=QApplication([])\nw=QWidget();w.setWindowTitle("MOOS_ARRANGE_LEADER");w.resize(480,320);w.show()\nv=QWidget();v.setWindowTitle("MOOS_ARRANGE_OTHER");v.resize(420,300);v.show()\nQTimer.singleShot(45000,a.quit)\na.exec()\n')
 client=subprocess.Popen(['python3',str(r/'client.py')],env=e,stdout=(r/'client.log').open('w'),stderr=subprocess.STDOUT)
 time.sleep(2)
 root=pathlib.Path(__file__).resolve().parents[2]
 base=(root/'system_files/usr/share/kwin/scripts/moos-arrange/contents/code/main.js').read_text().replace('registerShortcut(', 'recordShortcut(').replace('registerUserActionsMenu(', 'recordMenu(')
 if 'if (!isArrangeable(leader))' not in base:raise RuntimeError('cannot construct old guard negative')
 pre='function recordShortcut() {}\nfunction recordMenu() {}\n'
 find='const leader=workspace.windowList().find(w=>w.caption === "MOOS_ARRANGE_LEADER"); if(!leader) throw new Error("leader missing"); '
 script('setup',find+'leader.skipSwitcher=true;leader.frameGeometry={x:50,y:50,width:480,height:320}; console.info("NATIVE_SETUP "+JSON.stringify({geometry:leader.frameGeometry,skip:leader.skipSwitcher,activities:leader.activities,activity:workspace.currentActivity}));')
 for name,src in [('old',base.replace('if (!isArrangeable(leader))','if (!leader)')),('fixed',base)]:
  script('reset_'+name,find+'leader.frameGeometry={x:50,y:50,width:480,height:320};')
  script('run_'+name,pre+src+'\n'+find+'arrange("centre",leader);')
  script('read_'+name,find+'console.info("NATIVE_'+name.upper()+' "+JSON.stringify(leader.frameGeometry));')
 script('positive_setup',find+'leader.skipSwitcher=false;leader.frameGeometry={x:50,y:50,width:480,height:320};')
 script('positive',pre+base+'\n'+find+'arrange("centre",leader);')
 script('positive_read',find+'console.info("NATIVE_POSITIVE "+JSON.stringify(leader.frameGeometry));')
 if kwin.poll() is not None or client.poll() is not None:raise RuntimeError('native surface exited before final capture')
 log=(r/'kwin.log').read_text();found={}
 for line in log.splitlines():
  for name in ('OLD','FIXED','POSITIVE'):
   marker='NATIVE_'+name+' '
   if marker in line:found[name]=json.loads(line.split(marker,1)[1])
 assert set(found)=={'OLD','FIXED','POSITIVE'},found
 assert found['FIXED']==dict(x=50,y=50,width=480,height=320),found
 assert found['OLD']!=found['FIXED'] and found['POSITIVE']==found['OLD'],found
 receipt={'result':'PASS','native_geometry':found,'scope':'private virtual KWin QPainter, native Wayland clients; no physical display, portal or Activities acceptance'}
 (r/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt,indent=2),flush=True)
finally:
 for proc in (client,kwin,bus):
  if proc and proc.poll() is None:
   proc.terminate()
   try:proc.wait(timeout=5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 print('EVIDENCE '+str(r),flush=True)
