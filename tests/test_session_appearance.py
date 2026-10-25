#!/usr/bin/env python3
"""Fast contracts around the native per-user appearance publisher and wiring."""
import base64
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'system_files/usr/libexec/moos-session-appearance'
api=runpy.run_path(str(HELPER))


class AppearancePublication(unittest.TestCase):
    def test_paths_are_inert_absolute_data(self):
        path="/tmp/صورة #1%? 'quote' $(literal).png"
        from urllib.parse import quote
        self.assertEqual(str(api['decode_path'](quote(path,safe='-._~'))),path)
        for value in ('file%3A%2F%2F%2Fetc%2Fpasswd','relative','%00','%2Ftmp%0Aname','%ZZ','%FF'):
            with self.subTest(value=value),self.assertRaises((ValueError,UnicodeError)):
                api['decode_path'](value)

    def test_raster_is_bounded_and_discards_metadata(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'chosen.png'
            Image.new('RGB',(2400,1200),'#1583b1').save(path)
            encoded=api['raster'](path)
            self.assertLessEqual(len(base64.b64decode(encoded)),786432)
            with Image.open(io.BytesIO(base64.b64decode(encoded))) as actual:
                self.assertEqual(actual.size,(1920,960))
                self.assertEqual(actual.mode,'RGB')
                self.assertFalse(actual.getexif())
            with path.open('wb') as output:output.truncate(67108865)
            with self.assertRaises(ValueError):api['raster'](path)

    def test_native_extension_uses_only_the_existing_own_data_boundary(self):
        path=ROOT/'system_files/usr/share/accountsservice/interfaces/org.moos.Accounts.Appearance.xml'
        self.assertTrue(path.is_symlink())
        self.assertEqual(str(path.readlink()),'../../dbus-1/interfaces/org.moos.Accounts.Appearance.xml')
        interface=ET.parse(path).getroot().find('interface')
        self.assertEqual(interface.get('name'),'org.moos.Accounts.Appearance')
        annotations={a.get('name'):a.get('value') for a in interface.findall('annotation')}
        self.assertEqual(annotations,{'org.freedesktop.Accounts.VendorExtension':'true','org.freedesktop.Accounts.Authentication.ChangeOwn':''})
        self.assertEqual([(p.get('name'),p.get('type'),p.get('access')) for p in interface.findall('property')],[('Appearance','s','readwrite')])
        self.assertFalse(interface.findall('method'))
        source=HELPER.read_text()
        self.assertIn("(os.getuid(),)",source)
        self.assertNotIn('auth_admin',source)
        self.assertNotIn('shell=True',source)

    def test_both_editions_execute_the_native_proof_before_copying_the_module(self):
        for name in ('Containerfile','Containerfile.arm'):
            source=(ROOT/name).read_text()
            self.assertIn('native_session_appearance.py',source)
            self.assertIn('moos-appearance-contract-check',source)
            self.assertIn('COPY --from=kcm-contract /out/kcm/usr/ /usr/',source)
        stage=(ROOT/'moos-settings-kcm/appearance/CMakeLists.txt').read_text()
        self.assertIn('org/moos/appearance',stage)
        self.assertIn('add_executable(moos-appearance-contract-check',stage)

    def test_reconciler_preserves_the_publication_failure_and_wallpaper_watch(self):
        source=(ROOT/'system_files/usr/bin/moos-theme').read_text()
        function=source.split('reconcile() {',1)[1].split('\n}\n',1)[0]
        self.assertEqual(function.count('publish_session_appearance'),3)
        self.assertNotIn('publish_session_appearance\n        return 0',function)
        self.assertIn('plasma-org.kde.plasma.desktop-appletsrc',(ROOT/'system_files/usr/lib/systemd/user/moos-theme-sync.path').read_text())

    def test_empty_success_cannot_publish_native_qualification(self):
        check=runpy.run_path(str(ROOT/'build_files/verify_session_appearance.py'))
        with tempfile.TemporaryDirectory() as td:
            producer=Path(td)/'empty.py';producer.write_text('pass\n')
            with self.assertRaisesRegex(AssertionError,'did not execute'):
                check['fixture'](producer,Path('/absent-binary'),Path('/absent-imports'))


if __name__=='__main__':unittest.main()
