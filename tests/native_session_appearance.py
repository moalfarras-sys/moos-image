#!/usr/bin/python3
"""Real AccountsService + two native Qt owners, on a private container bus.

This is a build/test fixture, not a daemon, live desktop or authentication test.
No host bus, mount, user data or listener is used. Empty startup is a failure.
"""
import json
import hashlib
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote


def main():
    assert Path('/run/.containerenv').exists() or Path('/.dockerenv').exists(), 'container fixture required'
    assert os.getuid()==0 and len(sys.argv)==3
    # A developer replay can carry exact source inputs beside the executable.
    # Canonical stages already COPY these into their actual /usr paths.
    overlay=Path('/review/rootfs/usr')
    if overlay.is_dir(): shutil.copytree(overlay,Path('/usr'),dirs_exist_ok=True,symlinks=True)
    binary,imports = sys.argv[1:]
    assert Path(binary).is_file() and Path(imports).is_dir()
    extension = Path('/usr/share/accountsservice/interfaces/org.moos.Accounts.Appearance.xml')
    assert extension.is_symlink() and os.readlink(extension)=='../../dbus-1/interfaces/org.moos.Accounts.Appearance.xml'
    from PIL import Image
    from gi.repository import Gio,GLib
    for uid in (61000,61001):
        try: pwd.getpwuid(uid)
        except KeyError: subprocess.run(['useradd','-M','-u',str(uid),'moosappearance'+str(uid)],check=True)
        else: raise AssertionError('fixture UID occupied')
    try: greeter = pwd.getpwnam('plasmalogin')
    except KeyError:
        subprocess.run(['useradd','-r','-M','plasmalogin'],check=True);greeter=pwd.getpwnam('plasmalogin')
    with tempfile.TemporaryDirectory(prefix='moos-native-appearance-') as td:
        root = Path(td);root.chmod(0o755)
        def as_uid(uid):
            def drop(): os.setgroups([]);os.setgid(uid);os.setuid(uid)
            return drop
        home = root/'owner';home.mkdir(mode=0o700);os.chown(home,61000,61000)
        config = home/'.config';config.mkdir();os.chown(config,61000,61000)
        service_home = root/'greeter';service_home.mkdir(mode=0o700);os.chown(service_home,greeter.pw_uid,greeter.pw_gid)
        bus_config=root/'bus.conf'
        bus_config.write_text('<busconfig><type>system</type><listen>unix:tmpdir=/tmp</listen><auth>EXTERNAL</auth><policy context="default"><allow user="*"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
        bus=subprocess.Popen(['dbus-daemon','--nofork','--config-file='+str(bus_config),'--print-address'],stdout=subprocess.PIPE,text=True)
        children=[bus];logs=[]
        try:
            address=bus.stdout.readline().strip();assert address.startswith('unix:')
            env=os.environ | dict(DBUS_SYSTEM_BUS_ADDRESS=address,DBUS_SESSION_BUS_ADDRESS=address,
                QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',QML_DISABLE_DISK_CACHE='1',QT_FORCE_STDERR_LOGGING='1')
            env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)
            os.environ['DBUS_SYSTEM_BUS_ADDRESS']=address
            log=(root/'accounts.log').open('w');logs.append(log)
            daemon=subprocess.Popen(['/usr/libexec/accounts-daemon','--debug'],env=env,stdout=log,stderr=log);children.append(daemon)
            connection=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
            for attempt in range(100):
                try:
                    path=connection.call_sync('org.freedesktop.Accounts','/org/freedesktop/Accounts','org.freedesktop.Accounts','FindUserById',GLib.Variant('(x)',(61000,)),None,Gio.DBusCallFlags.NONE,1000,None).unpack()[0];break
                except GLib.Error: time.sleep(.05)
            else: raise AssertionError('native AccountsService unavailable')
            def read(): return connection.call_sync('org.freedesktop.Accounts',path,'org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.moos.Accounts.Appearance','Appearance')),None,Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
            assert read()==''
            owner_env=env | dict(HOME=str(home),XDG_CONFIG_HOME=str(config),XDG_CONFIG_DIRS=str(config),XDG_STATE_HOME=str(home/'.state'))
            def publish(look,color,custom=False):
                image=home/"خلفية #1%?.png";Image.new('RGB',(96,60),color).save(image);os.chown(image,61000,61000)
                for filename,body in {
                    'kdeglobals':'[KDE]\nLookAndFeelPackage='+look+'\n'+('[Colors:Window]\nBackgroundNormal=25,58,46\n[Colors:Selection]\nBackgroundNormal=226,143,51\n' if custom else ''),
                    'moos-session-appearance.conf':'[Appearance]\nLook='+look+'\nWallpaperEncoded='+quote(str(image),safe='-._~')+'\n'
                }.items():
                    file=config/filename;file.write_text(body);os.chown(file,61000,61000)
                result=subprocess.run(['/usr/libexec/moos-session-appearance','publish'],env=owner_env,preexec_fn=as_uid(61000),capture_output=True,text=True,timeout=12)
                assert result.returncode==0 and 'MOOS_LOGIN_APPEARANCE_PUBLISHED' in result.stdout,(result.stdout,result.stderr)
                assert json.loads(read())['look']==look
                print(result.stdout.strip(),flush=True)
            publish('org.moos.ui2.bloom.light','#1583b1')
            service_env=env | dict(HOME=str(service_home),XDG_CONFIG_HOME=str(service_home),XDG_CONFIG_DIRS=str(service_home),XDG_CACHE_HOME=str(service_home/'cache'))
            # The real greeter already has a complete Plasma style. A fixture
            # with no style silently exercises its application-palette fallback.
            service_files={
                'plasmarc':b'[Theme]\nname=MoOSUI2BloomLight\n',
                'kdeglobals':b'[General]\nColorScheme=MoOSUI2BloomLight\n[Icons]\nTheme=MoOSUI2BloomLight\n',
            }
            for name,body in service_files.items():
                file=service_home/name;file.write_bytes(body);os.chown(file,greeter.pw_uid,greeter.pw_gid)
            assert Path('/usr/share/plasma/desktoptheme/MoOSUI2BloomLight/colors').is_file()
            consumers=[]
            def start(role,label=None):
                file=root/((label or role)+'.log');stream=file.open('w');logs.append(stream)
                process=subprocess.Popen([binary,'--consumer',imports,role],env=service_env,preexec_fn=as_uid(greeter.pw_uid),stdout=stream,stderr=stream)
                children.append(process);consumers.append((process,file));return process,file
            def wait_marker(marker,targets):
                deadline=time.monotonic()+10
                while time.monotonic()<deadline:
                    if all(marker in file.read_text(errors='replace') for _,file in targets):return
                    for process,file in targets:
                        assert process.poll() is None,(file.name,file.read_text(errors='replace')[-3000:])
                    time.sleep(.05)
                raise AssertionError([(file.name,file.read_text(errors='replace')[-2000:]) for _,file in targets])
            first=start('follow');wait_marker('MOOS_NATIVE_APPEARANCE_PHASE1',[first])
            # A separate wallpaper owner starts late: it must read the existing
            # native snapshot, then receive the next actual account invalidation.
            second=start('listen');wait_marker('MOOS_NATIVE_APPEARANCE_PHASE1',[second])
            publish('org.moos.ui2.aurora','#b16b15');wait_marker('MOOS_NATIVE_APPEARANCE_PHASE2',consumers)
            # Same native style, new personal colours: no stale style/config
            # cache may retain the preceding palette or image.
            publish('org.moos.ui2.aurora','#156b35',custom=True);wait_marker('MOOS_NATIVE_APPEARANCE_PHASE3',consumers)
            invalid='{"schema":1,"look":"org.moos.ui2.aurora","image":"file:///etc/passwd"}'
            setter="""from gi.repository import Gio,GLib
import sys
c=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
c.call_sync('org.freedesktop.Accounts',sys.argv[1],'org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',('org.moos.Accounts.Appearance','Appearance',GLib.Variant('s',sys.argv[2]))),None,Gio.DBusCallFlags.NONE,3000,None)
"""
            result=subprocess.run(['python3','-c',setter,path,invalid],env=owner_env,preexec_fn=as_uid(61000),capture_output=True,text=True,timeout=6)
            assert result.returncode==0,result.stderr
            for process,file in consumers:
                assert process.wait(timeout=8)==0,file.read_text(errors='replace')[-3000:]
                assert 'MOOS_NATIVE_APPEARANCE_INVALID_REFUSED' in file.read_text()
                assert 'native greeter engine=KirigamiPlasmaStyle' in file.read_text()
            for name,body in service_files.items():
                assert (service_home/name).read_bytes()==body,'appearance changed persistent service settings'
            print('MOOS_NATIVE_TWO_OWNER_APPEARANCE_PASS',flush=True)
            result=subprocess.run(['python3','-c',setter,path,'cross-user'],env=env,preexec_fn=as_uid(61001),capture_output=True,text=True,timeout=6)
            assert result.returncode!=0 and read()==invalid,'unavailable cross-user authority changed metadata'
            print('MOOS_NATIVE_OTHER_ACCOUNT_AUTHORITY_UNAVAILABLE_REFUSED',flush=True)
            daemon.terminate();daemon.wait(timeout=5)
            daemon=subprocess.Popen(['/usr/libexec/accounts-daemon','--debug'],env=env,stdout=log,stderr=log);children.append(daemon)
            for attempt in range(100):
                try:
                    if read()==invalid:break
                except GLib.Error: pass
                time.sleep(.05)
            else: raise AssertionError('native appearance did not persist')
            print('MOOS_NATIVE_APPEARANCE_RESTART_PERSISTENCE_PASS',flush=True)
            # A fixed administrator global style must remain authoritative even
            # when our normal mechanism uses an application-specific group.
            locked=b'[Theme]\nname[$i]=MoOSUI2BloomLight\n'
            (service_home/'plasmarc').write_bytes(locked)
            publish('org.moos.ui2.aurora','#b16b15')
            refused=start('follow','admin-refused')
            assert refused[0].wait(timeout=23)==1,'immutable administrator style was bypassed'
            refusal=refused[1].read_text(errors='replace')
            assert 'MoOS login appearance payload or palette refused' in refusal,refusal[-2500:]
            assert 'native appearance phase 0 timed out' in refusal,refusal[-2500:]
            assert (service_home/'plasmarc').read_bytes()==locked
            print('MOOS_NATIVE_APPEARANCE_ADMIN_IMMUTABLE_REFUSED',flush=True)
            if os.environ.get('MOOS_APPEARANCE_PROOF'):
                receipt=Path(os.environ['MOOS_APPEARANCE_PROOF']);receipt.parent.mkdir(parents=True,exist_ok=True)
                module=Path(imports)/'org/moos/appearance/libmoosappearanceplugin.so'
                receipt.write_text(json.dumps(dict(schema=1,twoNativeOwners=True,nativePersistence=True,administratorImmutableRefused=True,
                    accountsDaemonSHA256=hashlib.sha256(Path('/usr/libexec/accounts-daemon').read_bytes()).hexdigest(),
                    moduleSHA256=hashlib.sha256(module.read_bytes()).hexdigest(),
                    package=subprocess.run(['rpm','-q','accountsservice'],capture_output=True,text=True,check=True).stdout.strip()),indent=2)+'\n')
        finally:
            for process in reversed(children):
                if process.poll() is None: process.terminate()
                process.wait(timeout=5)
            for stream in logs:stream.close()
            if sys.exc_info()[0] is not None:
                for file in root.glob('*.log'):
                    print(file.name,file.read_text(errors='replace')[-2500:],file=sys.stderr)


if __name__=='__main__': main()
