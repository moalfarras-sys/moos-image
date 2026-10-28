#!/usr/bin/env python3
"""Personal KDE packages remain native; only bounded data reaches MoOS login."""
import base64
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
API = runpy.run_path(str(ROOT/'system_files/usr/libexec/moos-session-appearance'))
GLOBALS = API['payload'].__globals__
CATALOG = ROOT/'system_files/usr/share/moos/theme-profiles.tsv'


class NativePersonalAppearance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='moos-kde-library-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.share = self.home/'.local/share'
        self.config = self.home/'.config'
        self.config.mkdir()
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, XDG_DATA_HOME=str(self.share), XDG_DATA_DIRS=str(self.home/'system-data'),
                   XDG_CONFIG_DIRS=str(self.home/'system-config'), XDG_STATE_HOME=str(self.home/'state')).start()

    def package(self,name):
        p = self.share/'plasma/look-and-feel'/name
        (p/'contents').mkdir(parents=True)
        (p/'contents/defaults').write_text('[kdeglobals][KDE]\nwidgetStyle=Breeze\n')
        (p/'metadata.json').write_text(json.dumps({'KPlugin':{'Id':name,'Name':name}}))
        return p

    def test_exact_installed_identity_not_kpackage_fallback(self):
        self.package('مظهري المحفوظ')
        self.assertTrue(API['installed_look']('مظهري المحفوظ',self.home))
        # The native package CLI falls back to another theme with exit 0.
        # A successful CLI exit cannot admit a missing package here.
        for name in ('missing','../escape','a/b','a\\b','a\nLook=other','.', '..'):
            self.assertFalse(API['installed_look'](name,self.home),name)
        p = self.package('wrong-id')
        (p/'metadata.json').write_text('{"KPlugin":{"Id":"another"}}')
        self.assertFalse(API['installed_look']('wrong-id',self.home))

    def test_a_link_or_oversized_metadata_is_not_an_installed_theme(self):
        p = self.package('source')
        (p.parent/'alias').symlink_to(p)
        self.assertFalse(API['installed_look']('alias',self.home))
        with (p/'metadata.json').open('wb') as out: out.truncate(1048577)
        self.assertFalse(API['installed_look']('source',self.home))

    def test_native_components_need_installed_counterparts(self):
        row = next(line.split('\t') for line in CATALOG.read_text().splitlines() if line.startswith('org.moos.ui2\t'))
        self.package(row[0])
        values = {('kdeglobals','General','ColorScheme'):row[1], ('kdeglobals','Icons','Theme'):row[4],
                  ('plasmarc','Theme','name'):row[2], ('kcminputrc','Mouse','cursorTheme'):row[6],
                  ('kwinrc','org.kde.kdecoration2','theme'):'__aurorae__svg__'+row[7],
                  ('kdeglobals','General','font'):'Meyar Sans,10,-1,5,400,0,0,0,0,0',
                  ('kdeglobals','General','fixed'):'Meyar Mono,10,-1,5,400,0,0,0,0,0'}
        def read(args,**kwargs):
            key = tuple(args[args.index(flag)+1] for flag in ('--file','--group','--key'))
            return subprocess.CompletedProcess(args,0,values.get(key,'')+'\n','')
        patch.dict(GLOBALS, selected_look=lambda:row[0]).start()
        patch.object(GLOBALS['subprocess'],'run',side_effect=read).start()
        self.assertFalse(API['native_customized'](self.home,CATALOG))
        values[('kdeglobals','Icons','Theme')] = 'Personal Icons'
        self.assertFalse(API['native_customized'](self.home,CATALOG))
        icons = self.share/'icons/Personal Icons'; icons.mkdir(parents=True)
        (icons/'index.theme').write_text('[Icon Theme]\nName=Personal Icons\n')
        self.assertTrue(API['native_customized'](self.home,CATALOG))
        values[('kdeglobals','Icons','Theme')] = row[4]
        values[('kwinrc','org.kde.kdecoration2','theme')] = '__aurorae__svg__Personal Frame'
        self.assertFalse(API['native_customized'](self.home,CATALOG))
        frame = self.share/'aurorae/themes/Personal Frame';frame.mkdir(parents=True)
        (frame/'metadata.desktop').write_text('[Desktop Entry]\nName=Personal Frame\n')
        self.assertTrue(API['native_customized'](self.home,CATALOG))
        values[('kwinrc','org.kde.kdecoration2','theme')] = '__aurorae__svg__'+row[7]
        values[('kdeglobals','Icons','Theme')] = row[4]
        values[('kdeglobals','General','font')] = 'Meyar Sans,10,-1,5,650,1,0,0,0,0'
        self.assertTrue(API['native_customized'](self.home,CATALOG))
        values[('kdeglobals','General','font')] = 'Missing,999,-1'
        self.assertFalse(API['native_customized'](self.home,CATALOG))
        values[('kdeglobals','General','font')] = 'Meyar Sans,10,-1,5,400,0,0,0,0,0'
        self.package('Personal')
        with patch.dict(GLOBALS,selected_look=lambda:'Personal'):
            self.assertTrue(API['native_customized'](self.home,CATALOG))
            values[('kdeglobals','Icons','Theme')] = 'Missing Icons'
            self.assertFalse(API['native_customized'](self.home,CATALOG))
        values[('kdeglobals','KDE','DefaultDarkLookAndFeel')] = row[0]
        values[('kdeglobals','KDE','DefaultLightLookAndFeel')] = 'Personal'
        self.assertTrue(API['native_pair'](self.home))
        values[('kdeglobals','KDE','DefaultLightLookAndFeel')] = 'Missing'
        self.assertFalse(API['native_pair'](self.home))

    def test_standard_static_wallpaper_package_and_refusals(self):
        from PIL import Image
        package = self.share/'wallpapers/Personal'
        images = package/'contents/images'; images.mkdir(parents=True)
        Image.new('RGB',(640,360),'#268db6').save(images/'640x360.png')
        Image.new('RGB',(1280,720),'#268db6').save(images/'1280x720.png')
        (images/'main.qml').write_text('this is never evaluated')
        self.assertEqual(API['image_file'](package),images/'1280x720.png')
        self.assertEqual(API['image_file'](images/'640x360.png'),images/'640x360.png')
        dark = package/'contents/images_dark'; dark.mkdir()
        Image.new('RGB',(1280,720),'#182c43').save(dark/'1280x720.png')
        self.assertEqual(API['image_file'](package,True),dark/'1280x720.png')
        with self.assertRaises(ValueError): API['image_file'](self.share/'wallpapers/Missing')
        for entry in images.glob('*.png'): entry.unlink()
        (dark/'1280x720.png').unlink()
        with self.assertRaises(ValueError): API['image_file'](package)

    def test_external_theme_publishes_native_colors_without_external_code_or_paths(self):
        from PIL import Image
        name = 'مظهري المحفوظ'; self.package(name)
        image = self.home/'صورة.png'; Image.new('RGB',(160,90),'#8d4ac0').save(image)
        (self.config/'moos-session-appearance.conf').write_text(
            '[Appearance]\nLook='+name+'\nBaseLook=org.moos.ui2\nWallpaperEncoded='+quote(str(image),safe='-._~')+'\n')
        (self.config/'kdeglobals').write_text('[General]\nColorScheme=Personal Palette\n')
        schemes = self.share/'color-schemes'; schemes.mkdir(parents=True)
        (schemes/'Personal Palette.colors').write_text('[Colors:Window]\nBackgroundNormal=25,30,40\nForegroundNormal=240,245,250\n')
        patch.dict(GLOBALS, selected_look=lambda:name).start()
        result = json.loads(API['payload'](self.home,self.config,CATALOG))
        self.assertEqual(result['look'],'org.moos.ui2')
        self.assertEqual(result['colors']['Colors:Window']['BackgroundNormal'],'25,30,40')
        self.assertTrue(base64.b64decode(result['image']).startswith(b'\xff\xd8'))
        self.assertNotIn(str(self.home),json.dumps(result))
        self.assertNotIn(name,json.dumps(result))
        # A transition cannot publish a stale snapshot for another selected look.
        patch.dict(GLOBALS, selected_look=lambda:'new-look').start()
        with self.assertRaisesRegex(ValueError,'transition'): API['payload'](self.home,self.config,CATALOG)

    def test_transaction_receipt_round_trips_native_package_names_as_json(self):
        source=(ROOT/'system_files/usr/bin/moos-theme').read_text()
        start=source.index('write_theme_state() {')
        body=source[start:source.index('\n}\n',start)+3]
        name='مظهري "المحفوظ" $(literal)'
        script='theme_state_root() { printf "%s\\n" '+shlex.quote(str(self.home))+'; }\n'
        script+='capture_wallpaper_identity() { printf "custom\\t%%2Fimage.png\\n"; }\n'+body+'\nwrite_theme_state committed "$1" "$2"\n'
        env={k:v for k,v in os.environ.items() if k not in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS')}
        result=subprocess.run(['bash','-c',script,'receipt',name,name],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=json.loads((self.home/'theme-state.json').read_text())
        self.assertEqual((receipt['active'],receipt['previous']),(name,name))
        self.assertEqual(receipt['wallpaperEncoded'],'%2Fimage.png')

    def test_personal_diagnostics_refuse_a_missing_native_automatic_pair(self):
        helper=self.home/'pair-check'
        helper.write_text('#!/bin/sh\n[ "$1" = check-pair ] || exit 9\nexit "$MOOS_PAIR_RESULT"\n')
        helper.chmod(0o700)
        for name in ('system_files/usr/bin/moos-selfcheck','tests/post-update-check.sh'):
            source=(ROOT/name).read_text()
            marker='if [ "$native_personal" = 1 ]; then\n    /usr/libexec/moos-session-appearance check-pair'
            start=source.index(marker)
            block=source[start:source.index('\nfi\n',start)+4]
            block=block.replace('/usr/libexec/moos-session-appearance',shlex.quote(str(helper)))
            script='native_personal=1\nok() { echo accepted; }\nbad() { echo refused; }\n'+block
            for code,expected in (('0','accepted'),('1','refused')):
                env={k:v for k,v in os.environ.items() if k not in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS')}
                result=subprocess.run(['bash','-c',script],env=env|{'MOOS_PAIR_RESULT':code},capture_output=True,text=True)
                self.assertEqual(result.stdout.strip(),expected,(name,result.stderr))

    def test_native_component_choice_survives_automatic_mode_without_replacing_its_owner(self):
        source=(ROOT/'system_files/usr/bin/moos-theme').read_text()
        start=source.index('reconcile() {');body=source[start:source.index('\n}\n',start)+3]
        helper=self.home/'native-owner'
        helper.write_text('#!/bin/sh\ncase "$1" in\ncheck-native) exit "$MOOS_NATIVE_RESULT" ;;\nsync-native) echo native ;;\n*) exit 9 ;;\nesac\n')
        helper.chmod(0o700)
        body=body.replace('/usr/libexec/moos-session-appearance',shlex.quote(str(helper)))
        setup='current() { echo org.moos.ui2.bloom; }\nload_profile() { return 0; }\nkreadconfig6() { echo true; }\nsync_auto() { echo automatic; }\npublish_session_appearance() { echo published; }\n'
        env={k:v for k,v in os.environ.items() if k not in ('DISPLAY','WAYLAND_DISPLAY','DBUS_SESSION_BUS_ADDRESS')}
        for code,expected in (('0','native'),('1','automatic\npublished')):
            result=subprocess.run(['bash','-c',setup+body+'\nreconcile\n'],env=env|{'MOOS_NATIVE_RESULT':code},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),expected)
        # Restore the old ordering: automatic mode must again overwrite the
        # same admitted personal choice. This control guards the actual defect.
        automatic_start=body.index('    automatic=')
        automatic_end=body.index('\n    fi\n',automatic_start)+8
        automatic=body[automatic_start:automatic_end]
        old=body[:automatic_start]+body[automatic_end:]
        native_start=old.index('    if '+shlex.quote(str(helper))+' check-native',old.index('if ! load_profile'))
        old=old[:native_start]+automatic+'\n'+old[native_start:]
        result=subprocess.run(['bash','-c',setup+old+'\nreconcile\n'],env=env|{'MOOS_NATIVE_RESULT':'0'},capture_output=True,text=True)
        self.assertEqual(result.stdout.strip(),'automatic\npublished')


if __name__=='__main__': unittest.main()
