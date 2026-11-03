#!/usr/bin/env python3
"""Archive and replacement controls protect an existing owner's tool files."""
import base64
import hashlib
import importlib.util
import io
import json
import multiprocessing
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
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


class ProfileGenerations(unittest.TestCase):
    """Private package/launcher transaction with real files and process leases."""
    zip=ProfileFileControls.zip

    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.home=self.root/'owner';self.base=self.home/'.local/share/moos-dev-platform'
        self.base.mkdir(parents=True)
        self.inputs=self.root/'inputs';self.inputs.mkdir()
        for name in ('moos-rea','moos-ghidra'):
            (self.inputs/name).write_bytes((M.INPUTS/name).read_bytes())
        self.rea=self.root/'rea-agents-6.7.0.tgz'
        self.package={'name':'rea-agents','version':'6.7.0'}
        with tarfile.open(self.rea,'w:gz') as tar:
            for name,body in [('package.json',json.dumps(self.package).encode()),('scripts/rea.mjs',b'// verified REA fixture\n')]:
                entry=tarfile.TarInfo('package/'+name);entry.size=len(body);tar.addfile(entry,io.BytesIO(body))
        self.ghidra,ghidra=self.zip('ghidra_reviewed/Ghidra/application.properties',b'application.version=12.1.4\n')
        ghidra['version']='12.1.4'
        self.manifest={'rea':{'version':'6.7.0','integrity':'sha512-'+base64.b64encode(hashlib.sha512(self.rea.read_bytes()).digest()).decode()},
                       'ghidra':ghidra,'node':'26.12.0','sdk_container':'moos-dev','java_home':'/reviewed/java'}
        self.lock={'name':'moos-analysis-rea','version':'1.0.0','lockfileVersion':3,'packages':{
            '':{'name':'moos-analysis-rea','version':'1.0.0','dependencies':{'rea-agents':'6.7.0'}},
            'node_modules/rea-agents':{'version':'6.7.0','resolved':'https://registry.npmjs.org/rea-agents/-/rea-agents-6.7.0.tgz'},
            'node_modules/reviewed-dependency':{'version':'1.0.0'}}}
        self.select_lock('2.0.0')
        self.args=SimpleNamespace(install=True,replace_launchers=True,rea_tarball=self.rea,ghidra_archive=self.ghidra)
        self.npm_calls=0
        self.addCleanup(patch.stopall)
        patch.object(M,'INPUTS',self.inputs).start()
        patch.object(M.subprocess,'check_output',return_value='v26.12.0\n').start()
        patch.object(M.subprocess,'run',side_effect=self.command).start()

    def select_lock(self,version):
        self.lock['packages']['node_modules/reviewed-dependency']['version']=version
        (self.inputs/'package-lock.json').write_text(json.dumps(self.lock))
        (self.inputs/'package.json').write_text(json.dumps(self.lock['packages']['']))
        self.manifest['package_lock_sha256']=M.digest(self.inputs/'package-lock.json')
        (self.inputs/'manifest.json').write_text(json.dumps(self.manifest))

    def packages(self,target,lock):
        target.mkdir(parents=True,exist_ok=True)
        (target/'package-lock.json').write_text(json.dumps(lock))
        for name,record in lock['packages'].items():
            if name:
                path=target/name;path.mkdir(parents=True)
                (path/'package.json').write_text(json.dumps({'version':record['version']}))
        (target/'node_modules/rea-agents/package.json').write_text(json.dumps(self.package))
        scripts=target/'node_modules/rea-agents/scripts';scripts.mkdir()
        (scripts/'rea.mjs').write_bytes(b'// verified REA fixture\n')

    def command(self,argv,**kwargs):
        if argv[0].endswith('/npm'):
            self.assertIn('--ignore-scripts',argv)
            self.npm_calls+=1
            self.packages(Path(kwargs['cwd']),json.loads((self.inputs/'package-lock.json').read_text()))
        else:self.assertIn(argv[0],('/usr/bin/podman','/usr/bin/toolbox'))
        return subprocess.CompletedProcess(argv,0)

    def snapshot(self):
        return {str(p.relative_to(self.home)):(p.read_bytes(),p.stat().st_mtime_ns,p.stat().st_mode)
                for p in self.home.rglob('*') if p.is_file()}

    def test_old_prefix_refuses_new_lock_but_upgrade_keeps_running_reader_and_uses_new_generation(self):
        old=self.base/'rea-6.7.0';old_lock=json.loads(json.dumps(self.lock))
        old_lock['packages']['node_modules/reviewed-dependency']['version']='1.0.0'
        self.packages(old,old_lock)
        resource=old/'node_modules/reviewed-dependency/package.json'
        reader=subprocess.Popen([sys.executable,'-u','-c',
            'import pathlib,sys; p=pathlib.Path(sys.argv[1]); f=p.open(); print(f.read(),flush=True); '
            'sys.stdin.readline(); f.seek(0); print(f.read(),flush=True); print(p.read_text(),flush=True)',str(resource)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            before=reader.stdout.readline().strip()
            with self.assertRaisesRegex(RuntimeError,'transitive lock differs'):M.check_rea(old,self.manifest)
            launcher=self.home/'.local/bin/moos-rea';launcher.parent.mkdir(parents=True)
            launcher.write_bytes(b'legacy owner launcher\n')
            old_snapshot={str(p):p.read_bytes() for p in old.rglob('*') if p.is_file()}
            M.run_profile(self.home,self.manifest,self.args)
            output,_=reader.communicate('\n',timeout=3)
            self.assertEqual(output.splitlines(),[before,before]);self.assertEqual(reader.returncode,0)
            self.assertEqual(old_snapshot,{str(p):p.read_bytes() for p in old.rglob('*') if p.is_file()})
            generation=M.rea_generation(self.manifest)
            self.assertIn(generation.encode(),launcher.read_bytes());self.assertNotIn(b'@REA_GENERATION@',launcher.read_bytes())
            self.assertEqual(json.loads((self.base/'analysis-tools-profile.json').read_text())['rea_generation'],generation)
            self.assertEqual(next(launcher.parent.glob('moos-rea.before-analysis-*')).read_bytes(),b'legacy owner launcher\n')
            self.assertEqual(self.npm_calls,1)
            before=self.snapshot();M.run_profile(self.home,self.manifest,self.args)
            self.assertEqual(self.snapshot(),before);self.assertEqual(self.npm_calls,1)
            self.select_lock('3.0.0');self.assertNotEqual(M.rea_generation(self.manifest),generation)
            M.run_profile(self.home,self.manifest,self.args)
            self.assertTrue((self.base/generation).is_dir());self.assertEqual(self.npm_calls,2)
        finally:
            if reader.poll() is None:reader.kill();reader.wait()

    def test_unknown_generation_and_lock_drift_are_refused_without_replacement(self):
        target=self.base/M.rea_generation(self.manifest);target.mkdir();keep=target/'owner';keep.write_bytes(b'keep')
        with self.assertRaisesRegex(RuntimeError,'unknown REA generation'):M.run_profile(self.home,self.manifest,self.args)
        self.assertEqual(keep.read_bytes(),b'keep');self.assertEqual(self.npm_calls,0)
        self.assertFalse((self.home/'.local/bin/moos-rea').exists())
        (target/'.moos-rea-generation.json').write_bytes(M.generation_record(self.manifest))
        self.packages(target,self.lock)
        installed=json.loads((target/'package-lock.json').read_text())
        installed['packages']['node_modules/reviewed-dependency']['version']='0.0.0'
        (target/'package-lock.json').write_text(json.dumps(installed))
        with self.assertRaisesRegex(RuntimeError,'transitive lock differs'):M.run_profile(self.home,self.manifest,self.args)
        self.assertEqual(keep.read_bytes(),b'keep');self.assertEqual(self.npm_calls,0)

    def test_check_is_read_only_including_absent_lease_and_detects_receipt_mismatch(self):
        check=SimpleNamespace(install=False)
        before=self.snapshot()
        with self.assertRaises(FileNotFoundError):M.run_profile(self.home,self.manifest,check)
        self.assertEqual(self.snapshot(),before);self.assertFalse((self.base/M.LEASE).exists())
        M.run_profile(self.home,self.manifest,self.args)
        before=self.snapshot();M.run_profile(self.home,self.manifest,check)
        self.assertEqual(self.snapshot(),before)
        receipt=self.base/'analysis-tools-profile.json';record=json.loads(receipt.read_text());record['rea_generation']='other'
        receipt.write_text(json.dumps(record));before=self.snapshot()
        with self.assertRaisesRegex(RuntimeError,'receipt missing/drifted'):M.run_profile(self.home,self.manifest,check)
        self.assertEqual(self.snapshot(),before)

    def test_lease_refuses_links_hardlinks_unknown_mode_and_data_without_touching_targets(self):
        lock=self.base/M.LEASE;keep=self.root/'keep';keep.write_bytes(b'owner data');lock.symlink_to(keep)
        for install in (False,True):
            with self.assertRaises(OSError):
                with M.profile_lease(self.base,install):self.fail('linked lease admitted')
        self.assertEqual(keep.read_bytes(),b'owner data');lock.unlink()
        for mode,body in ((0o644,b''),(0o600,b'unknown')):
            lock.write_bytes(body);lock.chmod(mode)
            with self.assertRaisesRegex(RuntimeError,'lease type/owner/mode'):
                with M.profile_lease(self.base,True):self.fail('unknown lease admitted')
            self.assertEqual(lock.read_bytes(),body);lock.unlink()
        keep.write_bytes(b'');keep.chmod(0o600);os.link(keep,lock)
        with self.assertRaisesRegex(RuntimeError,'lease type/owner/mode'):
            with M.profile_lease(self.base,True):self.fail('hardlinked lease admitted')
        self.assertEqual(keep.stat().st_nlink,2)

    def test_install_and_check_cannot_cross_a_partially_published_profile(self):
        context=multiprocessing.get_context('fork');paused=context.Event();release=context.Event();finished=context.Queue()
        replace=M.replace_file
        def hold_publication(path,*args,**kwargs):
            result=replace(path,*args,**kwargs)
            if path.name=='moos-rea':
                paused.set()
                if not release.wait(5):raise RuntimeError('test publication wait expired')
            return result
        def install():
            try:
                with patch.object(M,'replace_file',side_effect=hold_publication):M.run_profile(self.home,self.manifest,self.args)
                finished.put('complete')
            except Exception as error:finished.put(repr(error))
        process=context.Process(target=install);process.start()
        try:
            self.assertTrue(paused.wait(3),'installer did not reach actual launcher publication')
            self.assertTrue((self.home/'.local/bin/moos-rea').exists())
            self.assertFalse((self.base/'analysis-tools-profile.json').exists())
            lease=M.profile_lease
            with patch.object(M,'profile_lease',side_effect=lambda base,install:lease(base,install,timeout=0.1)):
                for args in (SimpleNamespace(install=False),self.args):
                    before=self.snapshot()
                    with self.assertRaisesRegex(RuntimeError,'profile busy'):M.run_profile(self.home,self.manifest,args)
                    self.assertEqual(self.snapshot(),before)
            release.set();process.join(3);self.assertEqual(process.exitcode,0)
            self.assertEqual(finished.get(timeout=1),'complete')
            M.run_profile(self.home,self.manifest,SimpleNamespace(install=False))
        finally:
            release.set()
            if process.is_alive():process.terminate();process.join()
            finished.close()


if __name__=='__main__':unittest.main()
