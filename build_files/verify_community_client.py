#!/usr/bin/env python3
"""Prove the installed native launcher, shipped runtime and real QML load.

A private HOME/runtime/bus, software Qt and no account/network startup isolate
this proof. A syntax/file gate alone cannot prove the app opens. Missing runtime,
operator/server leakage, a broken launcher or a broken QML must fail the image.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

RUNTIME={'__init__.py','client.py','transport.py','outbox.py','main.qml'}


def main():
    root=Path('/usr/lib/moos-community/community')
    if not root.is_dir() or {p.name for p in root.iterdir()} != RUNTIME:
        raise SystemExit('GATE FAIL: native participation runtime is incomplete or contains server/developer files')
    launcher=Path('/usr/bin/moos-community')
    if not os.access(launcher,os.X_OK):
        raise SystemExit('GATE FAIL: native participation launcher unavailable')
    config=json.loads(Path('/usr/share/moos/community-service.json').read_text())
    if (type(config.get('schema')) is not int or config['schema']!=1
            or config.get('service_url')!='https://moos-oracle.tailab78a5.ts.net:10000'):
        raise SystemExit('GATE FAIL: native participation has no reviewed TLS service')
    if not Path('/usr/share/applications/org.moos.community.desktop').is_file():
        raise SystemExit('GATE FAIL: native participation has no desktop identity')
    with tempfile.TemporaryDirectory(prefix='moos-community-proof-') as directory:
        home=Path(directory);runtime=home/'runtime';runtime.mkdir(mode=0o700)
        env={'PATH':'/usr/bin:/bin','HOME':str(home),'XDG_CONFIG_HOME':str(home/'.config'),
             'XDG_DATA_HOME':str(home/'.local/share'),'XDG_RUNTIME_DIR':str(runtime),
             'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software',
             'QT_QUICK_CONTROLS_STYLE':'Basic','QML_DISABLE_DISK_CACHE':'1',
             'QT_FORCE_STDERR_LOGGING':'1','PYTHONDONTWRITEBYTECODE':'1','LANG':'ar_SA.UTF-8'}
        run=subprocess.run(['dbus-run-session','--',str(launcher),'--language','ar',
                            '--capture',str(home/'native.png')],env=env,capture_output=True,text=True,timeout=15)
        output=run.stdout+run.stderr
        errors=('ReferenceError','TypeError','Unable to assign','Binding loop','binding loop','Traceback')
        if (run.returncode or not (home/'native.png').is_file()
                or 'MOOS_COMMUNITY_UI_READY' not in output or any(error in output for error in errors)):
            print(output)
            raise SystemExit('GATE FAIL: shipped native participation did not load cleanly')
    print('MoOS participation image gate: actual native launcher rendered Arabic; no server or private state ships')


if __name__=='__main__':main()
