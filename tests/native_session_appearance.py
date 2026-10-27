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
import re
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
                QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='kde',QT_QUICK_BACKEND='software',QML_DISABLE_DISK_CACHE='1',QT_FORCE_STDERR_LOGGING='1')
            # Native startplasma-login sets the KDE platform theme. Do not force
            # a QML style: 6.7 and 6.8 have different real greeter engine owners.
            env.pop('QT_QUICK_CONTROLS_STYLE',None)
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
            # The ordinary lock/power account reads only its own public data,
            # applying native colours in its process without replacing the
            # owner's Plasma style or registering a login publisher.
            personal_style=config/'plasmarc'
            personal_style.write_bytes(service_files['plasmarc']);os.chown(personal_style,61000,61000)
            own_log=root/'own-session.log';own_stream=own_log.open('w');logs.append(own_stream)
            own_process=subprocess.Popen([binary,'--consumer',imports,'own'],env=owner_env,
                preexec_fn=as_uid(61000),stdout=own_stream,stderr=own_stream)
            children.append(own_process);own=(own_process,own_log)
            wait_marker('MOOS_NATIVE_APPEARANCE_PHASE1',[own])
            consumers.append(own)
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
            native_engines=[]
            for process,file in consumers:
                assert process.wait(timeout=8)==0,file.read_text(errors='replace')[-3000:]
                assert 'MOOS_NATIVE_APPEARANCE_INVALID_REFUSED' in file.read_text()
                match=re.search(r'^MOOS_NATIVE_GREETER_ENGINE plasma=(\d+\.\d+\.\d+) api=(\w+) theme=(\w*) owner=(\w+)$',file.read_text(),re.M)
                assert match,'native engine identity missing'
                version,api,theme,owner=match.groups()
                expected=('globalEngine','KirigamiPlasmaStyle','PlasmaTheme') if tuple(map(int,version.split('.'))) >= (6,8,0) else ('SharedQmlEngine','','PlasmaDesktopTheme')
                assert (api,theme,owner)==expected,'native engine/palette owner mismatch'
                native_engines.append(dict(plasmaVersion=version,api=api,theme=theme,owner=owner))
            assert native_engines[0]==native_engines[1],'native owners used different engine contracts'
            for name,body in service_files.items():
                assert (service_home/name).read_bytes()==body,'appearance changed persistent service settings'
            assert personal_style.read_bytes()==service_files['plasmarc'],'session colours replaced the selected desktop style'
            print('MOOS_NATIVE_OWN_SESSION_APPEARANCE_PASS',flush=True)
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
            # The existing shell observes actual image keys, not every widget
            # move. Exercise the real native reader, inode rearming and pulse.
            desktop=config/'plasma-org.kde.plasma.desktop-appletsrc'
            pulse=config/'moos-wallpaper-intent.conf'
            def desktop_bytes(image='/tmp/first.png',extra='1',plugin='org.moos.ui2.wallpaper'):
                return ('[Containments][7]\nplugin=org.kde.plasma.folder\nwallpaperplugin='+plugin+'\n'
                    '[Containments][7][Wallpaper]['+plugin+'][General]\nImage='+image+'\n'
                    '[Containments][7][Applets][55]\nlocation='+extra+'\n').encode()
            def replace_desktop(body):
                temporary=config/'.native-desktop-next';temporary.write_bytes(body)
                os.chown(temporary,61000,61000);os.replace(temporary,desktop)
            def start_observer(label):
                file=root/(label+'.log');stream=file.open('w');logs.append(stream)
                process=subprocess.Popen([binary,'--desktop-observer',imports],env=owner_env,
                    preexec_fn=as_uid(61000),stdout=stream,stderr=stream)
                children.append(process)
                return process,file
            def pulse_state():
                if not pulse.exists():return None
                stat=pulse.stat();return stat.st_ino,stat.st_mtime_ns,pulse.read_bytes()
            def wait_pulse(previous=None):
                deadline=time.monotonic()+2
                while time.monotonic()<deadline:
                    value=pulse_state()
                    if value and value!=previous:return value
                    time.sleep(.025)
                raise AssertionError('native image intent did not arrive')
            replace_desktop(desktop_bytes())
            observer=start_observer('desktop-observer')
            initial=wait_pulse()
            # Atomic applet-layout rewrites must not notify the service.
            replace_desktop(desktop_bytes(extra='2'));time.sleep(.35)
            assert pulse_state()==initial,'unrelated widget move emitted wallpaper intent'
            replace_desktop(desktop_bytes(image='file:///tmp/first.png',extra='3'));time.sleep(.35)
            assert pulse_state()==initial,'equivalent local URI emitted wallpaper intent'
            replace_desktop(desktop_bytes(image='/tmp/second.png'));second=wait_pulse(initial)
            replace_desktop(desktop_bytes(image='/tmp/third.png',plugin='org.kde.image'));third=wait_pulse(second)
            for index in range(8):replace_desktop(desktop_bytes(image='/tmp/third.png',plugin='org.kde.image',extra=str(index)))
            time.sleep(.35);assert pulse_state()==third,'layout burst emitted wallpaper intent'
            assert observer[0].wait(timeout=7)==0,observer[1].read_text(errors='replace')[-2000:]
            assert 'MOOS_NATIVE_DESKTOP_OBSERVER_READY' in observer[1].read_text()
            print('MOOS_NATIVE_FILTERED_WALLPAPER_INTENT_PASS',flush=True)
            unknown=b'owner file, preserve exactly\n';pulse.write_bytes(unknown)
            refused_observer=start_observer('desktop-unknown-destination')
            assert refused_observer[0].wait(timeout=7)==0
            assert pulse.read_bytes()==unknown,'unknown owner destination overwritten'
            assert 'MoOS wallpaper intent refused' in refused_observer[1].read_text()
            print('MOOS_NATIVE_UNKNOWN_WALLPAPER_DESTINATION_REFUSED',flush=True)
            valid=b'[Wallpaper]\nFingerprint='+b'0'*64+b'\n'
            for kind in ('symlink','hardlink'):
                assert pulse.read_bytes()==(unknown if kind=='symlink' else valid)
                pulse.unlink()
                target=home/('preserved-'+kind);target.write_bytes(valid);os.chown(target,61000,61000)
                if kind=='symlink':
                    pulse.symlink_to(target);os.lchown(pulse,61000,61000)
                else:os.link(target,pulse)
                linked=start_observer('desktop-'+kind+'-destination')
                assert linked[0].wait(timeout=7)==0
                assert pulse.read_bytes()==valid and target.read_bytes()==valid
                assert pulse.is_symlink() if kind=='symlink' else pulse.stat().st_nlink==2
                assert 'MoOS wallpaper intent refused' in linked[1].read_text()
            print('MOOS_NATIVE_LINKED_WALLPAPER_DESTINATIONS_REFUSED',flush=True)
            if os.environ.get('MOOS_APPEARANCE_PROOF'):
                receipt=Path(os.environ['MOOS_APPEARANCE_PROOF']);receipt.parent.mkdir(parents=True,exist_ok=True)
                module=Path(imports)/'org/moos/appearance/libmoosappearanceplugin.so'
                receipt.write_text(json.dumps(dict(schema=1,twoNativeOwners=True,nativePersistence=True,administratorImmutableRefused=True,
                    ownSessionAppearance=True,filteredWallpaperIntent=True,unknownIntentDestinationRefused=True,
                    linkedIntentDestinationsRefused=True,
                    nativeEngine=native_engines[0],
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
