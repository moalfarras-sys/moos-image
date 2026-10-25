#!/usr/bin/env python3
"""Load the real power greeter against native shell bytes, with no live buses.

The upstream C++ owner remains the executor. This probe only starts its windowed
view and terminates that owned process; it cannot request a session operation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

SHELL = Path('/usr/share/plasma/shells/org.kde.plasma.desktop')
GREETER = '/usr/libexec/ksmserver-logout-greeter'
BAD = re.compile(r'TypeError|ReferenceError|Unable to assign|Cannot assign|Binding loop|is not a type|'
                 r'Setting initial properties failed|Failed to load|Couldn.t find a theme', re.I)


def probe(shell=SHELL, imports=None, share=Path('/usr/share'), *, broken=False,
          look='org.moos.ui2.bloom.light', motion=0):
    adapter = shell/'contents/logout/LogoutControls.qml'
    if not adapter.is_file() or 'MoUI.SessionPower {' not in adapter.read_text():
        raise ValueError('The native shell has no MoOS power controls at its actual destination')
    with tempfile.TemporaryDirectory(prefix='moos-power-probe-') as td:
        root=Path(td)
        for name in ('home','config','data','cache','runtime'):(root/name).mkdir(mode=0o700)
        if broken or shell != SHELL:
            package=root/'data/plasma/shells/org.kde.plasma.desktop'
            shutil.copytree(shell,package,symlinks=False)
            if broken:
                target=package/'contents/logout/LogoutControls.qml'
                body=target.read_text();assert body.count('MoUI.SessionPower {')==1
                target.write_text(body.replace('MoUI.SessionPower {','MoUI.SessionPowerMissing {',1))
        style='MoOSUI2BloomLight' if look.endswith('.light') else 'MoOSUI2Bloom'
        colors=(share/'color-schemes'/(style+'.colors')).read_text()
        config=root/'config/kdeglobals'
        config.write_text(colors+'\n[KDE]\nLookAndFeelPackage='+look+'\nAnimationDurationFactor='+str(motion)+'\n[Icons]\nTheme='+style+'\n')
        (root/'config/plasmarc').write_text('[Theme]\nname='+style+'\n')
        before=config.read_bytes()
        env={'PATH':'/usr/bin:/usr/sbin','HOME':str(root/'home'),
             'XDG_CONFIG_HOME':str(root/'config'),'XDG_CONFIG_DIRS':str(root/'config'),
             'XDG_DATA_HOME':str(root/'data'),'XDG_DATA_DIRS':str(share)+':/usr/share',
             'XDG_CACHE_HOME':str(root/'cache'),'XDG_RUNTIME_DIR':str(root/'runtime'),
             'DBUS_SESSION_BUS_ADDRESS':'unix:path='+str(root/'runtime/absent-session'),
             'DBUS_SYSTEM_BUS_ADDRESS':'unix:path='+str(root/'runtime/absent-system'),
             'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software',
             'QT_QPA_PLATFORMTHEME':'kde','QT_FORCE_STDERR_LOGGING':'1',
             'QML_DISABLE_DISK_CACHE':'1','LANG':'en_US.UTF-8','LANGUAGE':'en',
             'QT_LOGGING_RULES':'*.debug=false;qml.info=true;qml.warning=true'}
        if imports:env['QML_IMPORT_PATH']=str(imports)
        process=subprocess.Popen([GREETER,'--windowed'],env=env,stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
        try:
            output,_=process.communicate(timeout=3)
            early=True
        except subprocess.TimeoutExpired:
            early=False
            assert os.getpgid(process.pid)==process.pid
            os.killpg(process.pid,signal.SIGTERM)
            try:output,_=process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);output,_=process.communicate(timeout=5)
        ready='MOOS_SESSION_POWER_READY' in output
        failures=[line for line in output.splitlines() if BAD.search(line)]
        if broken:
            assert not ready and any('SessionPowerMissing is not a type' in line for line in failures), output
        else:
            assert not early and ready and not failures, output
            assert look in output and style+'/contents/' in output, output
        assert config.read_bytes()==before,'A read-only appearance lookup rewrote kdeglobals'
        return {'look':look,'motion':motion,'broken':broken,'ready':ready,'early_exit':early,
                'expected_native_adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
                'settings_unchanged':True,'output':output}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shell-dir',type=Path,default=SHELL)
    parser.add_argument('--imports',type=Path)
    parser.add_argument('--share',type=Path,default=Path('/usr/share'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    proofs=[]
    for look in ('org.moos.ui2.bloom','org.moos.ui2.bloom.light'):
        for motion in (0,1):proofs.append(probe(args.shell_dir,args.imports,args.share,look=look,motion=motion))
    proofs.append(probe(args.shell_dir,args.imports,args.share,broken=True))
    if args.output:args.output.write_text(json.dumps(proofs,indent=2)+'\n')
    print('MOOS_NATIVE_POWER_PROOF '+json.dumps([{k:v for k,v in row.items() if k!='output'} for row in proofs]))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,AssertionError,subprocess.TimeoutExpired) as error:
        print('GATE FAIL: native MoOS power screen:',error)
        raise SystemExit(1)
