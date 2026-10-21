#!/usr/bin/env python3
"""Archive and replacement controls protect an existing owner's tool files."""
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('analysis_profile',ROOT/'scripts/setup-analysis-tools.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class ProfileFileControls(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)

    def zip(self,name,body=b'vendor payload',mode=0o100755):
        archive=self.root/'release.zip'
        with zipfile.ZipFile(archive,'w') as zipped:
            entry=zipfile.ZipInfo(name);entry.external_attr=mode<<16;zipped.writestr(entry,body)
        return archive,{'directory':'ghidra_reviewed','bytes':archive.stat().st_size,'sha256':M.digest(archive)}

    def test_verified_archive_installs_and_detects_drift_without_deleting_owner_files(self):
        archive,manifest=self.zip('ghidra_reviewed/support/launch.sh')
        target=self.root/'installed';target.mkdir()
        M.verify_ghidra(archive,target,manifest,extract=True)
        M.verify_ghidra(archive,target,manifest)
        user=target/'owner-project';user.write_text('keep')
        launch=target/'support/launch.sh';self.assertEqual(stat.S_IMODE(launch.stat().st_mode),0o755)
        launch.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'bytes drifted'):M.verify_ghidra(archive,target,manifest)
        self.assertEqual(user.read_text(),'keep');self.assertEqual(launch.read_bytes(),b'changed')

    def test_wrong_digest_archive_links_and_path_escape_never_touch_outside_data(self):
        keep=self.root/'keep';keep.write_bytes(b'owner data');target=self.root/'target';target.mkdir()
        archive,manifest=self.zip('ghidra_reviewed/support/launch.sh')
        manifest['sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'digest'):M.verify_ghidra(archive,target,manifest,extract=True)
        self.assertEqual(list(target.iterdir()),[])
        for name,mode in [('ghidra_reviewed/../keep',0o100644),('ghidra_reviewed/link',0o120777),('/ghidra_reviewed/keep',0o100644)]:
            with self.subTest(name=name):
                archive,manifest=self.zip(name,mode=mode)
                with self.assertRaisesRegex(RuntimeError,'unsafe|link|root'):M.verify_ghidra(archive,target,manifest,extract=True)
                self.assertEqual(keep.read_bytes(),b'owner data')

    def test_rea_integrity_and_payload_bytes_are_checked_without_running_package_code(self):
        archive=self.root/'rea.tgz';body=b'console.log("fixture")\n'
        with tarfile.open(archive,'w:gz') as tar:
            entry=tarfile.TarInfo('package/scripts/rea.mjs');entry.size=len(body);tar.addfile(entry,io.BytesIO(body))
        manifest={'integrity':'sha512-'+base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()}
        target=self.root/'installed';(target/'scripts').mkdir(parents=True);path=target/'scripts/rea.mjs';path.write_bytes(body)
        M.verify_rea_archive(archive,target,manifest)
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'bytes drifted'):M.verify_rea_archive(archive,target,manifest)
        manifest['integrity']='sha512-wrong'
        with self.assertRaisesRegex(RuntimeError,'integrity'):M.verify_rea_archive(archive,target,manifest)
        self.assertEqual(path.read_bytes(),b'changed')

    def test_launcher_collision_refuses_then_explicit_replace_keeps_exact_private_backup(self):
        path=self.root/'moos-rea';path.write_bytes(b'owner launcher')
        with self.assertRaisesRegex(RuntimeError,'existing launcher differs'):M.replace_file(path,b'new',0o755)
        self.assertEqual(path.read_bytes(),b'owner launcher')
        self.assertTrue(M.replace_file(path,b'new',0o755,replace=True))
        backups=list(self.root.glob('moos-rea.before-analysis-*'));self.assertEqual(len(backups),1)
        self.assertEqual(backups[0].read_bytes(),b'owner launcher');self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode),0o600)
        self.assertFalse(M.replace_file(path,b'new',0o755,replace=True));self.assertEqual(len(list(self.root.iterdir())),2)
        path.chmod(0o644);self.assertTrue(M.replace_file(path,b'new',0o755));self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o755)

    def test_links_and_preexisting_backup_collision_are_refused_without_overwriting_either_file(self):
        keep=self.root/'keep';keep.write_bytes(b'owner data');link=self.root/'launcher';link.symlink_to(keep)
        with self.assertRaisesRegex(RuntimeError,'link refused'):M.replace_file(link,b'new',0o755,True)
        self.assertEqual(keep.read_bytes(),b'owner data');link.unlink();link.write_bytes(b'old')
        backup=link.with_name(link.name+'.before-analysis-'+M.digest(link)[:16]);backup.write_bytes(b'other data')
        with self.assertRaisesRegex(RuntimeError,'backup collision'):M.replace_file(link,b'new',0o755,True)
        self.assertEqual(link.read_bytes(),b'old');self.assertEqual(backup.read_bytes(),b'other data')

    def test_legacy_local_tar_lock_keeps_all_reviewed_transitive_pins_and_refuses_extra_dependencies(self):
        lock=json.loads((M.INPUTS/'package-lock.json').read_text());old=json.loads(json.dumps(lock))
        old['packages']['']['dependencies']['rea-agents']='file:../downloads/rea-agents-6.7.0.tgz'
        old['packages']['node_modules/rea-agents']['resolved']='file:../downloads/rea-agents-6.7.0.tgz'
        self.assertEqual(M.normalized_lock(old),lock)
        old['packages']['']['dependencies']['other']='1'
        with self.assertRaisesRegex(RuntimeError,'root dependencies'):M.normalized_lock(old)
        old=json.loads(json.dumps(lock));old['packages']['node_modules/rea-agents']['resolved']='https://example.invalid/rea.tgz'
        with self.assertRaisesRegex(RuntimeError,'archive source'):M.normalized_lock(old)


if __name__=='__main__':unittest.main()
