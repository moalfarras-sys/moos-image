#!/usr/bin/env python3
"""Real native KWin/Plasma/Qt input proof, isolated before bus creation.

The optional broken-backtab copy changes only the temporary applet, proving
that the input assertion fails for the previously observed focus defect.
This does not test physical touch, GPU performance or the installed session.
"""
from pathlib import Path
import argparse,configparser,datetime,hashlib,re,json,os,shutil,signal,subprocess,tempfile,time,uuid
from gi.repository import Gio,GLib

parser=argparse.ArgumentParser(description="Private native Plasma launcher viewport/input matrix")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--family", choices=("graphite", "aurora", "nova", "amethyst", "bloom", "dev", "gaming", "midnight", "study"), default="graphite")
parser.add_argument("--broken-backtab", action="store_true")
parser.add_argument("--broken-alignment", action="store_true")
parser.add_argument("--broken-category", action="store_true")
parser.add_argument("--broken-style", action="store_true")
parser.add_argument("--native-popup", action="store_true")
parser.add_argument("--trace-drag", action="store_true")
parser.add_argument("--short-only", action="store_true")
parser.add_argument("--broken-order-snapshot", action="store_true")
parser.add_argument("--broken-drop-cancel", action="store_true")
parser.add_argument("--broken-folders", action="store_true")
parser.add_argument("--broken-home-focus", action="store_true")
parser.add_argument("--broken-runner-preferences", action="store_true")
parser.add_argument("--broken-popup-reopen", action="store_true")
args=parser.parse_args()
if args.broken_popup_reopen and not args.native_popup:
    parser.error("--broken-popup-reopen requires --native-popup")
S=Path(__file__).resolve().parents[1]
O=args.output
O.mkdir(mode=0o700,parents=True,exist_ok=False)
owner_portal=Path('/run/user')/str(os.getuid())/'doc'
def portal():
    if not owner_portal.exists(): return {'exists':False}
    st=owner_portal.stat()
    return {'mounted':os.path.ismount(owner_portal),'device':st.st_dev,'inode':st.st_ino}
def source_state():
    paths=list((S/'system_files/usr/share/plasma/plasmoids/org.moos.brand').rglob('*'))
    paths+=list((S/'system_files/usr/lib64/qt6/qml/org/moos/ui').glob('*.qml'))
    paths+=[Path(__file__),S/'tests/qml/LauncherAdaptiveDriver.qml',S/'system_files/usr/bin/moos-selfcheck',S/'tests/post-update-check.sh']
    paths+=list((S/'system_files/usr/share/plasma/look-and-feel').glob('org.moos.ui2*/contents/defaults'))
    return {str(p.relative_to(S)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}
report={'scope':'adaptive source launcher development probe; native private KWin/OpenGL virtual outputs; Qt Quick software content, not physical touch or owner-session acceptance','portal_before':portal(),'source_before':source_state(),'cases':[],'started_utc':datetime.datetime.now(datetime.UTC).isoformat()}


def one(width,height,language,light,reduced):
    case={'output_width':width,'output_height':height,'language':language,'light':light,'reduced':reduced,'service_activation_directories':False}
    # Exercise both Milou's own defaults and a personal native ordering. The
    # private shell-first choice must survive app pin changes, even though the
    # native default puts applications before command execution.
    custom_runners = language == 'ar'
    runner_favorites = (['krunner_shell', 'krunner_services'] if custom_runners else
        ['krunner_sessions', 'krunner_powerdevil', 'krunner_services', 'krunner_systemsettings'])
    case['runner_favorites'] = runner_favorites
    case['runner_preference_source'] = 'private-personal' if custom_runners else 'native-default'
    prefix=f'{width}x{height}-{language}'
    with tempfile.TemporaryDirectory(prefix='moos-launcher-viewport-') as tmp:
        root=Path(tmp)
        for name in ('home','runtime','config','cache','data'):(root/name).mkdir(mode=0o700)
        package=root/'data/plasma/plasmoids/org.moos.brand'
        shutil.copytree(S/'system_files/usr/share/plasma/plasmoids/org.moos.brand',package)
        view=package/'contents/ui/LauncherView.qml'
        body=view.read_text().replace('import QtQuick\n','import QtQuick\nimport '+json.dumps((S/'tests/qml').as_uri())+' as Gate\n',1)
        driver='''
    property QtObject nativeThemeProbe: Kirigami.Theme
    Gate.LauncherAdaptiveDriver {
        surface: view; field: searchInput; appGrid: applicationsGrid
        homeGrid: favoritesGrid; homeScroll: homeScroll; canvas: commandCanvas
        pages: pages; navigation: navigation; categories: categoryStrip
        placesList: placesList
        powerButton: sessionMenuButton; powerMenu: sessionMenu; actionMenu: appActions
    }
'''
        driver=driver.replace('actionMenu: appActions','actionMenu: appActions; reviewDirectory: '+json.dumps(str(O.resolve()/prefix)))
        driver=driver.replace('surface: view;', 'runnerFavorites: '+json.dumps(runner_favorites)
            +'; firstSearchRunner: '+json.dumps('krunner_shell' if custom_runners else 'krunner_services')+'; surface: view;', 1)
        if args.trace_drag:
            body=body.replace('onActiveChanged: {\n                if (active)', 'onActiveChanged: {\n                console.info("MOVA_NATIVE_DRAG active", active, tile.favoriteSurface, tile.visible);\n                if (active)',1)
            body=body.replace('onActiveTranslationChanged: if (active && tile.favoriteSurface) {','onActiveTranslationChanged: if (active && tile.favoriteSurface) { console.info("MOVA_NATIVE_DRAG delta",activeTranslation);',1)
            body=body.replace('onEntered: event => {\n                event.accepted', 'onEntered: event => {\n                console.info("MOVA_NATIVE_DRAG entered", event.source, tile.index);\n                event.accepted',1)
            body=body.replace('onDropped: event => {\n                const source', 'onDropped: event => {\n                console.info("MOVA_NATIVE_DRAG dropped",event.source,tile.index);\n                const source',1)
        if args.broken_backtab:
            body=body.replace('KeyNavigation.priority: KeyNavigation.BeforeItem',
                              'KeyNavigation.priority: KeyNavigation.AfterItem')
        if args.broken_alignment:
            body=body.replace('horizontalAlignment: Text.AlignLeft',
                              'horizontalAlignment: view.rtl ? Text.AlignRight : Text.AlignLeft')
        if args.broken_category:
            body=body.replace('view.launcher.appsModelRow = row;',
                              'view.launcher.appsModelRow = 1;',1)
        if args.broken_home_focus:
            seam='onActiveFocusChanged: if (activeFocus) homeScroll.reveal(command)'
            assert body.count(seam)==1
            body=body.replace(seam,'',1)
        if args.broken_drop_cancel:
            seam='&& tile.visible && view.visible && view.launcher.expanded'
            assert body.count(seam)==1
            body=body.replace(seam,'&& tile.visible && view.visible',1)
        main=package/'contents/ui/main.qml'
        main_body=main.read_text()
        if args.broken_order_snapshot:
            seam='function onRowsMoved() { Qt.callLater(root.syncFavoriteSearchIds); }'
            assert main_body.count(seam)==1
            main_body=main_body.replace(seam,'function onRowsMoved() {}',1)
        if args.broken_folders:
            assert main_body.count('flat: false')==1
            main_body=main_body.replace('flat: false','flat: true',1)
        if args.broken_runner_preferences:
            seam='        queryString: root.searchQuery'
            assert main_body.count(seam)==1 and 'favoriteIds: root.favoriteSearchIds' not in main_body
            main_body=main_body.replace(seam,seam+'\n        favoriteIds: root.favoriteSearchIds',1)
        main.write_text(main_body)
        view.write_text(body[:body.rfind('}')]+driver+body[body.rfind('}'):])
        if args.native_popup:
            main=package/'contents/ui/main.qml'
            main_body=main.read_text()
            opening='\n    PlasmaCore.AppletPopup {\n        id: nativePopupProof\n        appletInterface: root\n        visualParent: root\n        popupDirection: Qt.TopEdge\n        mainItem: Item {\n            id: nativePopupProxy\n            implicitWidth: root.fullRepresentationItem ? root.fullRepresentationItem.implicitWidth : 0\n            implicitHeight: root.fullRepresentationItem ? root.fullRepresentationItem.implicitHeight : 0\n            Layout.minimumWidth: implicitWidth\n            Layout.minimumHeight: implicitHeight\n            Layout.maximumWidth: implicitWidth\n            Layout.maximumHeight: implicitHeight\n        }\n    }\n    Timer {\n        interval: 500\n        running: true\n        onTriggered: {\n            const surface = root.fullRepresentationItem;\n            if (!surface) throw Error("native popup has no full representation");\n            surface.parent = nativePopupProxy;\n            surface.anchors.fill = nativePopupProxy;\n            nativePopupProof.visible = true;\n        }\n    }\n'
            if not args.broken_popup_reopen:
                opening += """
    function reopenNativePopupProof() {
        if (!root.expanded) return;
        const surface = root.fullRepresentationItem;
        if (!surface) throw Error("reopened native popup has no full representation");
        surface.parent = nativePopupProxy;
        surface.anchors.fill = nativePopupProxy;
        nativePopupProof.visible = true;
    }
    Connections {
        target: root
        function onExpandedChanged() {
            if (root.expanded) Qt.callLater(root.reopenNativePopupProof);
            else nativePopupProof.visible = false;
        }
    }
"""
            main.write_text(main_body[:main_body.rfind('}')]+opening+main_body[main_body.rfind('}'):])

        merged=root/'config/menus/applications-merged'
        merged.mkdir(parents=True)
        (merged/'mova-fixture.menu').write_text('<!DOCTYPE Menu PUBLIC "-//freedesktop//DTD Menu 1.0//EN" "http://www.freedesktop.org/standards/menu-spec/1.0/menu.dtd"><Menu><Name>Applications</Name><Menu><Name>Mova Fixture</Name><Directory>mova-fixture.directory</Directory><Menu><Name>Nested</Name><Directory>mova-nested.directory</Directory><Include><Filename>mova-folder-fixture.desktop</Filename></Include></Menu></Menu></Menu>')
        (root/'data/desktop-directories').mkdir(parents=True)
        for filename,label in [('mova-fixture','Mova Fixture'),('mova-nested','Nested')]:
            (root/'data/desktop-directories'/(filename+'.directory')).write_text('[Desktop Entry]\nType=Directory\nName='+label+'\nIcon=folder\n')
        (root/'data/applications').mkdir(parents=True)
        (root/'data/applications/mova-folder-fixture.desktop').write_text('[Desktop Entry]\nType=Application\nName=Mova Native Folder Fixture\nExec=/usr/bin/false\nIcon=folder\n')
        # A real native services result competing with the native shell's
        # executable "true" result. Neither result is ever activated.
        (root/'data/applications/mova-provider-fixture.desktop').write_text('[Desktop Entry]\nType=Application\nName=true\nExec=/usr/bin/false mova-provider-fixture\nIcon=application-x-executable\nCategories=Utility;\n')
        if custom_runners:
            (root/'config/krunnerrc').write_text('[Plugins][Favorites]\nplugins='+','.join(runner_favorites)+'\n')
        theme=('org.moos.ui2' if args.family == 'graphite' else 'org.moos.ui2.'+args.family) + ('.light' if light else '')
        defaults=S/'system_files/usr/share/plasma/look-and-feel'/theme/'contents/defaults'
        matched=configparser.ConfigParser(interpolation=None)
        matched.optionxform=str
        matched.read_string(defaults.read_text())
        scheme=matched['kdeglobals][General']['ColorScheme']
        plasma_style=matched['plasmarc][Theme']['name']
        icons=matched['kdeglobals][Icons']['Theme']
        case['theme']={'global_theme':theme,'color_scheme':scheme,
                       'plasma_style':plasma_style,'icons':icons,
                       'defaults_sha256':hashlib.sha256(defaults.read_bytes()).hexdigest()}
        colors=(S/'system_files/usr/share/color-schemes'/(scheme+'.colors')).read_text()
        (root/'config/kdeglobals').write_text(colors+'\n[KDE]\nAnimationDurationFactor='+('0' if reduced else '1')+'\n[Icons]\nTheme='+icons+'\n')
        (root/'config/plasmarc').write_text('[Theme]\nname='+('MoOSUI2' if args.broken_style else plasma_style)+'\n')
        config=root/'bus.conf'
        config.write_text(f'<busconfig><type>session</type><listen>unix:path={root}/runtime/bus</listen><auth>EXTERNAL</auth><policy context="default"><allow user="{os.getuid()}"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
        env={'PATH':'/usr/bin:/usr/sbin:/bin','HOME':str(root/'home'),'XDG_RUNTIME_DIR':str(root/'runtime'),'XDG_CONFIG_HOME':str(root/'config'),'XDG_CACHE_HOME':str(root/'cache'),'XDG_DATA_HOME':str(root/'data'),'XDG_CONFIG_DIRS':str(S/'system_files/etc/xdg')+':/etc/xdg','XDG_DATA_DIRS':str(S/'system_files/usr/share')+':/usr/share','QML_IMPORT_PATH':str(S/'system_files/usr/lib64/qt6/qml'),'LANG':'ar_SA.UTF-8' if language=='ar' else 'en_US.UTF-8','LC_ALL':'ar_SA.UTF-8' if language=='ar' else 'en_US.UTF-8','LANGUAGE':language,'QT_QUICK_CONTROLS_STYLE':'org.kde.desktop','QT_QPA_PLATFORMTHEME':'kde','QT_QPA_PLATFORM':'wayland','WAYLAND_DISPLAY':'wayland-moos-viewport','KWIN_COMPOSE':'O2ES','QT_QUICK_BACKEND':'software','LP_NUM_THREADS':'2','QT_FORCE_STDERR_LOGGING':'1','QML_DISABLE_DISK_CACHE':'1'}
        children=[];streams=[]
        def start(args,name):
            stream=(O/f'{prefix}-{name}.log').open('wb');streams.append(stream)
            p=subprocess.Popen(args,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);children.append(p);return p
        bus=None
        try:
            stream=(O/f'{prefix}-bus.log').open('wb');streams.append(stream)
            daemon=subprocess.Popen(['dbus-daemon','--config-file='+str(config),'--nofork','--print-address=1'],env=env,stdout=subprocess.PIPE,stderr=stream,text=True,start_new_session=True);children.append(daemon)
            address=daemon.stdout.readline().strip();assert address.startswith('unix:path='+str(root/'runtime/bus'))
            env['DBUS_SESSION_BUS_ADDRESS']=address
            actual=dict(v.split(b'=',1) for v in Path('/proc',str(daemon.pid),'environ').read_bytes().split(b'\0') if b'=' in v)
            assert actual[b'HOME']==env['HOME'].encode() and actual[b'XDG_RUNTIME_DIR']==env['XDG_RUNTIME_DIR'].encode()
            kwin=start(['kwin_wayland','--virtual','--width',str(width),'--height',str(height),'--socket',env['WAYLAND_DISPLAY'],'--no-lockscreen','--no-global-shortcuts','--no-kactivities'],'kwin')
            for _ in range(120):
                if (root/'runtime'/env['WAYLAND_DISPLAY']).is_socket():break
                assert kwin.poll() is None,'private compositor exited'
                time.sleep(.05)
            else:raise RuntimeError('private compositor socket absent')
            bus=Gio.DBusConnection.new_for_address_sync(address,Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT|Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,None,None)
            def call(dest,path,interface,method,args=None):
                return bus.call_sync(dest,path,interface,method,args,None,Gio.DBusCallFlags.NONE,5000,None)
            for _ in range(100):
                if call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','NameHasOwner',GLib.Variant('(s)',('org.kde.KWin',))).unpack()[0]:break
                assert kwin.poll() is None,'private compositor exited before bus readiness'
                time.sleep(.05)
            else:raise RuntimeError('private compositor did not own its bus name')
            pid=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID',GLib.Variant('(s)',('org.kde.KWin',))).unpack()[0]
            assert pid==kwin.pid,'not the owned compositor'
            kamd=start(['/usr/libexec/kactivitymanagerd'],'activities')
            app=start(['plasmawindowed','org.moos.brand','moos-ci-full-representation'],'launcher')
            # The real Qt input journey contains bounded focus waits. An ARM
            # station under build load can finish after six seconds; wait for
            # its executed result, never infer completion from a sleep.
            started = time.monotonic()
            while time.monotonic() - started < 25:
                assert app.poll() is None,'launcher exited'
                log=(O/f'{prefix}-launcher.log').read_text(errors='replace')
                if 'MOOS_ADAPTIVE_INPUT_PASS ' in log or 'MOOS_ADAPTIVE_INPUT_FAIL' in log:
                    break
                time.sleep(.1)
            case['input_wait_seconds']=round(time.monotonic()-started,3)
            case['launcher_pid']=app.pid
            log=(O/f'{prefix}-launcher.log').read_text(errors='replace')
            case['ready_marker']=bool(re.search(r'MOOS_LAUNCHER_FULL_READY size=[0-9]+x[0-9]+',log)) or (args.native_popup and 'MOOS_ADAPTIVE_INPUT_PASS ' in log)
            assert case['ready_marker'], log[-4500:]
            assert 'MOOS_ADAPTIVE_INPUT_PASS ' in log and 'MOOS_ADAPTIVE_INPUT_FAIL' not in log,log[-6500:]
            case['input']=json.loads(re.search(r'MOOS_ADAPTIVE_INPUT_PASS (.+)',log)[1])
            # A matching application palette can hide a different native SVG
            # style. Read the actual KConfig cascade, not the requested input.
            style=subprocess.run(['kreadconfig6','--file','plasmarc','--group','Theme','--key','name'],
                env=env,capture_output=True,text=True,timeout=5,check=True).stdout.strip()
            case['native_style_readback']=style
            case['private_style_input']=(root/'config/plasmarc').read_text()
            assert style==plasma_style,('actual native Plasma style mismatch',style,plasma_style,case['input']['initialPalette'])

            expected=configparser.ConfigParser(interpolation=None)
            expected.read_string(colors)
            def hex_rgb(value):
                return '#' + ''.join(f'{int(channel):02x}' for channel in value.split(',')[:3])
            for role,key in (('background','BackgroundNormal'),('text','ForegroundNormal')):
                want=hex_rgb(expected['Colors:Window'][key])
                assert case['input']['palette'][role].lower()==want, ('actual Kirigami palette mismatch',role,case['input']['palette'],want)
            assert case['input']['palette']['accent'].lower()==hex_rgb(expected['Colors:Selection']['BackgroundNormal']), 'actual native accent mismatch'

            assert case['input']['rtl']==(language=='ar')
            assert case['input']['motion']==(0 if reduced else 220),case['input']
            assert not re.search(r'TypeError|ReferenceError|Cannot assign|Unable to assign|Binding loop|error when loading applet|non-existent',log,re.I),log[-4500:]
            owner=call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',GLib.Variant('(s)',('org.kde.KWin',))).unpack()[0]
            result=[];loop=GLib.MainLoop()
            info=Gio.DBusNodeInfo.new_for_xml('<node><interface name="org.moos.ViewportProbe"><method name="Record"><arg type="s" direction="in"/></method></interface></node>')
            def receive(connection,sender,path,interface,method,params,invocation):
                assert sender==owner;result.append(json.loads(params.unpack()[0]));invocation.return_value(GLib.Variant('()',()));loop.quit()
            reg=bus.register_object('/org/moos/ViewportProbe',info.interfaces[0],receive,None,None)
            name='moos-viewport-'+uuid.uuid4().hex;script=root/'window.js'
            expression='workspace.windowList().map(w=>({pid:w.pid,resourceClass:String(w.resourceClass),caption:String(w.caption),x:w.frameGeometry.x,y:w.frameGeometry.y,width:w.frameGeometry.width,height:w.frameGeometry.height,clientWidth:w.clientGeometry.width,clientHeight:w.clientGeometry.height}))'
            script.write_text('callDBus('+json.dumps(bus.get_unique_name())+',"/org/moos/ViewportProbe","org.moos.ViewportProbe","Record",JSON.stringify('+expression+'));')
            index=call('org.kde.KWin','/Scripting','org.kde.kwin.Scripting','loadScript',GLib.Variant('(ss)',(str(script),name))).unpack()[0];assert index>=0
            try:
                call('org.kde.KWin','/Scripting/Script'+str(index),'org.kde.kwin.Script','run')
                timer=GLib.timeout_add(5000,lambda:(loop.quit(),False)[1]);loop.run()
                if result: GLib.source_remove(timer)
                assert result,'owned private KWin did not reply'
                case['windows']=[w for w in result[0] if w['pid']==app.pid and w['caption']=='MoOS Adaptive Input Gate']
                case['all_owned_windows']=[w for w in result[0] if w['pid']==app.pid]
                if args.native_popup: assert len(case['all_owned_windows'])>=2,case
                assert len(case['windows'])==1
            finally:
                call('org.kde.KWin','/Scripting','org.kde.kwin.Scripting','unloadScript',GLib.Variant('(s)',(name,)))
                bus.unregister_object(reg)
            w=case['windows'][0]
            case['window_fits_output']=w['x']>=0 and w['y']>=0 and w['x']+w['width']<=width and w['y']+w['height']<=height
            capture=O/f'{prefix}.png'
            p=subprocess.run(['spectacle','--background','--nonotify','--fullscreen','--output',str(capture)],env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=15)
            case['capture_exit']=p.returncode;case['capture_exists']=capture.is_file()
            (O/f'{prefix}-capture.log').write_bytes(p.stdout+p.stderr)
            if args.native_popup:
                closing='moos-popup-close-'+uuid.uuid4().hex
                script.write_text('const windows=workspace.windowList().filter(w=>w.pid==='
                    +str(app.pid)+' && String(w.caption)==="MoOS Adaptive Input Gate");'
                    +'if(windows.length!==1)throw Error("owned popup not unique");windows[0].closeWindow();')
                index=call('org.kde.KWin','/Scripting','org.kde.kwin.Scripting','loadScript',
                    GLib.Variant('(ss)',(str(script),closing))).unpack()[0]
                assert index>=0
                try:
                    call('org.kde.KWin','/Scripting/Script'+str(index),'org.kde.kwin.Script','run')
                    saved=root/'config/plasmawindowedrc'
                    for _ in range(40):
                        text=saved.read_text() if saved.exists() else ''
                        pw=re.findall(r'^popupWidth=(\d+)$',text,re.M)
                        ph=re.findall(r'^popupHeight=(\d+)$',text,re.M)
                        if len(pw)==1 and len(ph)==1:break
                        time.sleep(.05)
                    assert len(pw)==len(ph)==1,'native popup did not persist unique dimensions'
                    case['saved_popup']={'width':int(pw[0]),'height':int(ph[0])}
                    case['old_fixed_size_health_accepts']=int(pw[0])>=600 and int(ph[0])>=540
                    assert int(pw[0])==round(case['input']['width'])
                    assert int(ph[0])==round(case['input']['height'])
                finally:
                    call('org.kde.KWin','/Scripting','org.kde.kwin.Scripting','unloadScript',
                        GLib.Variant('(s)',(closing,)))

        finally:
            if bus:bus.close_sync(None)
            for p in reversed(children):
                if p.poll() is None:
                    assert os.getpgid(p.pid)==p.pid
                    os.killpg(p.pid,signal.SIGTERM)
                    try:p.wait(timeout=4)
                    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
            for stream in streams:stream.close()
    return case

try:
    matrix=[(360,640,'ar',False,True),(600,960,'en',True,False),
            (960,540,'ar',True,True),(1536,864,'en',False,False)]
    if args.short_only: matrix=matrix[2:3]
    if args.broken_backtab or args.broken_alignment or args.broken_style or args.broken_order_snapshot or args.broken_drop_cancel or args.broken_folders or args.broken_home_focus or args.broken_runner_preferences or args.broken_popup_reopen: matrix=matrix[:1]
    for size in matrix:
        case=one(*size);report['cases'].append(case)
        (O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
finally:
    report['portal_after']=portal();report['source_after']=source_state()
    report['owner_portal_unchanged']=report['portal_before']==report['portal_after']
    report['source_unchanged']=report['source_before']==report['source_after']
    (O/'receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({"cases":report["cases"],"source_unchanged":report["source_unchanged"],"owner_portal_unchanged":report["owner_portal_unchanged"]},indent=2))
assert report['owner_portal_unchanged'] and report['source_unchanged']
assert all(c['ready_marker'] and c['window_fits_output'] and c['capture_exit']==0 for c in report['cases'])
