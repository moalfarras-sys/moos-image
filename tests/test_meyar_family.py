#!/usr/bin/env python3
"""Delivery controls for the actual five-font MoOS overlay."""
import hashlib
import importlib.util
import importlib.machinery
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import subprocess
import os
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / 'system_files/usr/share/fonts/meyar'
spec = importlib.util.spec_from_file_location('verify_meyar', ROOT / 'build_files/verify_meyar.py')
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)


def rehash(directory, name):
    manifest = json.loads((directory / 'manifest.json').read_text())
    path = directory / name
    manifest['files'][name] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (directory / 'manifest.json').write_text(json.dumps(manifest))


class MeyarDelivery(unittest.TestCase):
    @unittest.skipUnless(shutil.which('fc-match'), 'native Fontconfig unavailable')
    def test_generic_defaults_survive_vendor_expansion_without_replacing_named_fonts(self):
        from native_meyar_fontconfig import configure
        with tempfile.TemporaryDirectory(prefix='meyar-generic-') as tmp:
            for fixed in (False, True):
                private = Path(tmp) / ('fixed' if fixed else 'old')
                private.mkdir()
                env = dict(os.environ, HOME=str(private), XDG_CONFIG_HOME=str(private),
                           XDG_DATA_HOME=str(private), XDG_CACHE_HOME=str(private),
                           LANG='C.UTF-8', LC_ALL='C.UTF-8')
                configure(env, private, defaults=fixed)
                for request, family in [('sans-serif','Meyar Sans' if fixed else 'Meyar Arabic'),
                                        ('monospace','Meyar Mono' if fixed else 'Meyar Mono Arabic'),
                                        ('Meyar Arabic,sans-serif','Meyar Arabic'),
                                        ('Meyar Mono Arabic,monospace','Meyar Mono Arabic')]:
                    result = subprocess.check_output(['fc-match','-f','%{family}',request],env=env,text=True)
                    if not fixed and request in ('sans-serif','monospace'):
                        self.assertNotEqual(result, 'Meyar Sans' if request == 'sans-serif' else 'Meyar Mono')
                    else:
                        self.assertEqual(result,family,(fixed,request))
                for family in ('Meyar Sans', 'Meyar Mono', 'Meyar Arabic', 'Meyar Mono Arabic'):
                    path = subprocess.check_output(['fc-match','-f','%{file}',family],env=env,text=True)
                    self.assertEqual(Path(path).parent, FONTS)

    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt unavailable')
    def test_native_fixed_font_chooser_and_old_dual_classification(self):
        from native_meyar_fontconfig import configure
        for old in (False, True):
            with self.subTest(old=old), tempfile.TemporaryDirectory(prefix='meyar-qt-fixed-') as tmp:
                private=Path(tmp); env=dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=tmp,
                    XDG_DATA_HOME=tmp, XDG_CACHE_HOME=tmp, XDG_RUNTIME_DIR=tmp,
                    QT_QPA_PLATFORM='offscreen', DBUS_SESSION_BUS_ADDRESS='unix:path='+tmp+'/absent')
                configure(env,private)
                if old:
                    original=ROOT/'system_files/etc/fonts/conf.d/61-moos-brand.conf'
                    tree=ET.parse(original); matches=tree.getroot().findall('match')
                    self.assertEqual(len(matches),2)
                    for match in matches: tree.getroot().remove(match)
                    policy=private/'old-policy.conf';tree.write(policy,encoding='unicode')
                    config=Path(env['FONTCONFIG_FILE'])
                    config.write_text(config.read_text().replace(str(original),str(policy)))
                script='''from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont,QFontInfo,QFontDatabase
import json
a=QApplication([])
print(json.dumps({x:[QFontInfo(QFont(x)).family(),QFontInfo(QFont(x)).fixedPitch(),QFontDatabase.isFixedPitch(x)]
for x in ['Meyar Mono','Meyar Mono Arabic']}))'''
                result=subprocess.run([os.sys.executable,'-c',script],env=env,capture_output=True,text=True,timeout=15)
                self.assertEqual(result.returncode,0,result.stderr)
                values=json.loads(result.stdout)
                for family,row in values.items():self.assertEqual(row,[family,not old,not old])

    @unittest.skipUnless(shutil.which('kwriteconfig6') and shutil.which('kreadconfig6'), 'native KConfig tools unavailable')
    def test_native_migration_preserves_personal_family_sizes_and_recovery(self):
        import os
        loader = importlib.machinery.SourceFileLoader('meyar_migrate', str(ROOT / 'system_files/usr/bin/moos-fonts-migrate'))
        migration = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader)); loader.exec_module(migration)
        with tempfile.TemporaryDirectory(prefix='meyar-native-kconfig-') as tmp:
            base = Path(tmp); config = base / 'config'; state = base / 'state'; config.mkdir()
            font = 'IBM Plex Sans,12,-1,5,600,0,0,0,0,0,0,0,0,0,0,1,,0,0'
            personal = 'Personal Choice,14,-1,5,400,0,0,0,0,0,0,0,0,0,0,1'
            before = '[General]\nfont=' + font + '\nmenuFont=' + personal + '\n'
            (config / 'kdeglobals').write_text(before)
            env = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_STATE_HOME=str(state),
                       XDG_CONFIG_DIRS=str(ROOT / 'system_files/etc/xdg'))
            env.pop('DBUS_SESSION_BUS_ADDRESS', None)
            with patch.dict(os.environ, env, clear=True): migration.main(FONTS)
            after = (config / 'kdeglobals').read_text()
            self.assertIn(font.replace('IBM Plex Sans', 'Meyar Sans'), after)
            self.assertIn(personal, after)
            recoveries = list((state / 'moos/font-recovery').glob('meyar-*/kdeglobals'))
            self.assertEqual(len(recoveries), 1); self.assertEqual(recoveries[0].read_text(), before)
            with patch.dict(os.environ, env, clear=True): migration.main(FONTS)
            self.assertEqual(len(list((state / 'moos/font-recovery').glob('meyar-*'))), 1)

    def test_actual_overlay(self):
        result = gate.verify(FONTS)
        self.assertTrue(result['pass'])
        self.assertEqual(len(result['families']), 5)

    def test_unknown_or_changed_bytes_refused(self):
        with tempfile.TemporaryDirectory(prefix='meyar-negative-') as tmp:
            dst = Path(tmp) / 'fonts'; shutil.copytree(FONTS, dst)
            (dst / 'unknown.ttf').write_bytes(b'unreviewed')
            with self.assertRaisesRegex(ValueError, 'contents'): gate.verify(dst)
            (dst / 'unknown.ttf').unlink()
            path = dst / 'MeyarSans[wght].ttf'; path.write_bytes(path.read_bytes() + b'x')
            with self.assertRaisesRegex(ValueError, 'byte mismatch'): gate.verify(dst)

    def test_ipa_digraph_wrong_cell_refused_even_with_updated_manifest(self):
        with tempfile.TemporaryDirectory(prefix='meyar-cell-negative-') as tmp:
            dst = Path(tmp) / 'fonts'; shutil.copytree(FONTS, dst)
            name = 'MeyarMono[wght].ttf'; path = dst / name; font = gate.Sfnt(path)
            gid = font.cmap()[0x2a5]  # ʥ is one native Unicode cell.
            data = bytearray(path.read_bytes()); hmtx = None
            for i in range(struct.unpack_from('>H', data, 4)[0]):
                tag, _, start, _ = struct.unpack_from('>4sIII', data, 12 + i * 16)
                if tag == b'hmtx': hmtx = start
            self.assertIsNotNone(hmtx)
            struct.pack_into('>H', data, hmtx + min(gid, font.number('hhea', 34) - 1) * 4, 1400)
            path.write_bytes(data); rehash(dst, name)
            with self.assertRaisesRegex(ValueError, 'terminal cell mismatch'): gate.verify(dst)

    def test_family_named_fallbacks_and_legacy_aliases(self):
        tree = ET.parse(ROOT / 'system_files/etc/fonts/conf.d/61-moos-brand.conf').getroot()
        aliases = {a.findtext('family'): a for a in tree.findall('alias')}
        for primary, fallback in [('Meyar Sans', 'Meyar Arabic'), ('Meyar Mono', 'Meyar Mono Arabic'),
                                  ('JetBrains Mono', 'Kawkab Mono'), ('IBM Plex Sans', 'IBM Plex Sans Arabic')]:
            alias = aliases[primary]
            self.assertEqual(alias.get('binding'), 'weak')
            self.assertIn(fallback, [x.text for x in alias.findall('accept/family')])

    def test_four_editions_share_overlay_and_fail_closed_gate(self):
        for file in ['Containerfile', 'Containerfile.arm', 'Containerfile.cloud']:
            if not (ROOT / file).exists(): continue
            self.assertIn('system_files/', (ROOT / file).read_text())
        build = (ROOT / 'build_files/build.sh').read_text()
        self.assertIn('python3 /ctx/verify_meyar.py /usr/share/fonts/meyar', build)
        self.assertIn("fc-match -s 'Meyar Mono:lang=ar'", build)
        self.assertIn("fc-match -s 'JetBrains Mono:lang=ar'", build)
        self.assertIn('tests/test_meyar_family.py', (ROOT / 'Justfile').read_text())


if __name__ == '__main__': unittest.main(verbosity=2)
