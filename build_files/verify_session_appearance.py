#!/usr/bin/env python3
"""Qualify the native appearance reader, its actual loader and tested daemon."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

MARKERS=('MOOS_NATIVE_TWO_OWNER_APPEARANCE_PASS','MOOS_NATIVE_APPEARANCE_RESTART_PERSISTENCE_PASS','MOOS_NATIVE_APPEARANCE_ADMIN_IMMUTABLE_REFUSED')


def fixture(script,binary,imports):
    result=subprocess.run([sys.executable,str(script),str(binary),str(imports)],capture_output=True,text=True,timeout=65)
    print(result.stdout,end='');print(result.stderr,end='',file=sys.stderr)
    assert result.returncode==0 and all(marker in result.stdout.splitlines() for marker in MARKERS),'native appearance fixture did not execute its proof'


def load_module(imports,ui_imports=None,logfile=None):
    module=Path(imports)/'org/moos/appearance/libmoosappearanceplugin.so'
    assert module.is_file(),'native appearance module missing'
    with tempfile.TemporaryDirectory(prefix='moos-native-appearance-load-') as td:
        root=Path(td)
        for name in ('home','config','cache','data','runtime'):(root/name).mkdir(mode=0o700)
        qml=root/'probe.qml'
        qml.write_text('''import QtQuick
import org.moos.appearance 1.0
import org.moos.ui as MoUI
QtObject {
 Component.onCompleted: {
  const profile = MoUI.SessionAppearance.nativeProfile();
  if (!profile || profile !== Appearance || profile.isGreeter || profile.ready) throw new Error("Unexpected native appearance bridge");
  console.warn("MOOS_RUNTIME_NATIVE_APPEARANCE_MODULE_READY");
  Qt.quit();
 }
}''')
        env=dict(PATH='/usr/bin:/usr/sbin',HOME=str(root/'home'),XDG_CONFIG_HOME=str(root/'config'),
            XDG_CONFIG_DIRS=str(root/'config'),XDG_DATA_HOME=str(root/'data'),XDG_DATA_DIRS='/usr/share',
            XDG_CACHE_HOME=str(root/'cache'),XDG_RUNTIME_DIR=str(root/'runtime'),
            DBUS_SESSION_BUS_ADDRESS='unix:path='+str(root/'runtime/absent'),
            DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(root/'runtime/absent-system'),
            QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QML_DISABLE_DISK_CACHE='1',
            QT_FORCE_STDERR_LOGGING='1',QT_LOGGING_RULES='*.debug=false;qml.warning=true',
            QML_IMPORT_PATH=str(imports)+(os.pathsep+str(ui_imports) if ui_imports else ''),LD_DEBUG='libs',LANG='en_US.UTF-8')
        result=subprocess.run(['/usr/bin/moos-qml-shell','--app-id','org.moos.AppearanceProbe','--qml',str(qml)],
            env=env,capture_output=True,text=True,timeout=12)
        log=result.stdout+result.stderr
        if logfile:Path(logfile).write_text(log)
        loaded=any('calling init:' in line and str(module) in line for line in log.splitlines())
        diagnostics='\n'.join(line for line in log.splitlines() if any(word in line for word in ('qml:','Error','error','moosappearance','native appearance','Unexpected')))
        assert result.returncode==0 and loaded and 'MOOS_RUNTIME_NATIVE_APPEARANCE_MODULE_READY' in log, (
            'native appearance module failed actual isolated loading: '+diagnostics[-3500:])
        return dict(module=str(module),sha256=hashlib.sha256(module.read_bytes()).hexdigest(),actualLoader=True)


def runtime():
    assert pwd.getpwnam('plasmalogin').pw_uid != 0,'native greeter account unavailable'
    link=Path('/usr/share/accountsservice/interfaces/org.moos.Accounts.Appearance.xml')
    assert link.is_symlink() and str(link.readlink())=='../../dbus-1/interfaces/org.moos.Accounts.Appearance.xml'
    receipt=json.loads(Path('/usr/share/moos/appearance-native-proof.json').read_text())
    assert receipt['twoNativeOwners'] and receipt['nativePersistence'] and receipt['administratorImmutableRefused']
    daemon=Path('/usr/libexec/accounts-daemon')
    assert hashlib.sha256(daemon.read_bytes()).hexdigest()==receipt['accountsDaemonSHA256'],'tested AccountsService bytes differ in final image'
    loaded=load_module(Path('/usr/lib64/qt6/qml'))
    assert loaded['sha256']==receipt['moduleSHA256'],'tested native reader bytes differ in final image'
    print('MOOS_RUNTIME_NATIVE_APPEARANCE_PASS '+json.dumps(loaded))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fixture',nargs=3,type=Path)
    args=parser.parse_args()
    if args.fixture:fixture(*args.fixture)
    else:runtime()
