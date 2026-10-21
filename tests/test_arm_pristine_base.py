#!/usr/bin/python3
"""Only a proven empty native ARM input may start the package transaction."""
from pathlib import Path
import json
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'build_files'),str(ROOT/'build_files/plasma_stable')]
import prepare_arm_compose_base as M
from runtime_state import Transaction


class ArmPristineBase(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        (self.root/'var/tmp').mkdir(parents=True,mode=0o1777);(self.root/'var/tmp').chmod(0o1777)
        self.library=self.root/'var/lib';self.state=self.library/'rpm-state'
        self.state.mkdir(parents=True);self.library.chmod(0o775);self.state.chmod(0o775)
        self.run=self.root/'var/run';self.run.symlink_to('../run')
        (self.root/'root').symlink_to('var/roothome')
        self.identity=self.root/'etc/machine-id';self.identity.parent.mkdir();self.identity.touch()
        self.authority=self.root/'usr/lib/tmpfiles.d/var.conf';self.authority.parent.mkdir(parents=True)
        self.authority.write_text('L /var/run - - - - ../run\n')

    def test_same_filesystem_bind_refuses_before_any_enumeration(self):
        base=self.root/'var'
        before=set(base.rglob('*'))
        with patch('prepare_arm_compose_base.mount_points', return_value={base/'private-mounted-child'}), \
                patch.object(Path, 'is_mount', return_value=False), \
                patch.object(Path, 'iterdir', side_effect=AssertionError('traversed mounted tree')):
            with self.assertRaisesRegex(RuntimeError,'mounted'):
                M.canonicalize_input(self.root)
        self.assertEqual(set(base.rglob('*')),before)

    def test_local_tmpfiles_mask_refuses_before_first_delete(self):
        authority=self.authority
        override=self.root/'etc/tmpfiles.d'/authority.name
        override.parent.mkdir(parents=True,exist_ok=True)
        override.symlink_to('/dev/null')
        with patch.object(Path,'unlink',side_effect=AssertionError('deleted before authority validation')), \
                patch.object(Path,'rmdir',side_effect=AssertionError('deleted before authority validation')):
            with self.assertRaisesRegex(RuntimeError,'override'):
                M.canonicalize_input(self.root)

    def refused(self,text):
        with self.assertRaisesRegex((OSError,RuntimeError),text):M.canonicalize_input(self.root)
        self.assertTrue(os.path.lexists(self.run));self.assertTrue(self.state.exists())

    def test_native_empty_scaffolds_retire_then_same_strict_transaction_starts(self):
        before=self.authority.read_bytes();M.canonicalize_input(self.root)
        self.assertEqual([p.name for p in (self.root/'var').iterdir()],['tmp'])
        self.assertEqual(self.identity.read_bytes(),b'');self.assertEqual(self.authority.read_bytes(),before)
        Transaction(self.root,{})

    def test_already_canonical_native_input_needs_no_extra_authority(self):
        self.run.unlink();self.state.rmdir();self.library.rmdir();self.authority.unlink()
        M.canonicalize_input(self.root);Transaction(self.root,{})

    def test_existing_machine_identity_is_never_reset(self):
        data=b'0123456789abcdef0123456789abcdef\n';self.identity.write_bytes(data)
        self.refused('input identity must be empty');self.assertEqual(self.identity.read_bytes(),data)

    def test_linked_identity_is_never_followed(self):
        self.identity.unlink();self.identity.symlink_to('/etc/machine-id')
        self.refused('unexpected symlink')

    def test_hardlinked_identity_is_never_truncated(self):
        os.link(self.identity,self.root/'keep');self.refused('unsafe.*(mount|transaction metadata)')

    def test_unknown_top_level_state_is_preserved(self):
        p=self.root/'var/owner';p.write_text('keep');self.refused('unexpected ARM base input')
        self.assertEqual(p.read_text(),'keep')

    def test_unknown_library_state_even_empty_refuses(self):
        (self.library/'unknown').mkdir();self.refused('package scaffold contains unexpected data')

    def test_existing_package_state_payload_is_preserved(self):
        p=self.state/'owner';p.write_text('keep');self.refused('package scaffold contains unexpected data')
        self.assertEqual(p.read_text(),'keep')

    def test_nonempty_tmp_is_preserved(self):
        p=self.root/'var/tmp/owner';p.touch();self.refused('tmp contains unexpected data')
        self.assertTrue(p.exists())

    def test_wrong_scaffold_mode_is_refused(self):
        self.state.chmod(0o777);self.refused('unsafe.*(mount|transaction metadata)')

    def test_escaping_run_alias_is_never_unlinked(self):
        self.run.unlink();self.run.symlink_to('/run');self.refused('run alias drifted')

    def test_changed_root_alias_is_refused(self):
        alias=self.root/'root';alias.unlink();alias.symlink_to('/var/roothome')
        self.refused('root-home alias is not canonical')

    def test_missing_or_changed_authority_refuses(self):
        self.authority.write_text('L /var/run - - - - /run\n');self.refused('authority drifted')
        self.authority.unlink();self.refused('No such file')

    def test_fifo_or_writable_authority_refuses_before_read(self):
        self.authority.chmod(0o666);self.refused('unsafe ARM base run authority')
        self.authority.unlink();os.mkfifo(self.authority);self.refused('unsafe ARM base run authority')

    def test_mount_is_not_treated_as_empty_owned_state(self):
        original=Path.is_mount
        with patch.object(Path,'is_mount',lambda p:p==self.library or original(p)):
            self.refused('unsafe.*(mount|transaction metadata)')

    def test_installed_host_is_refused_before_package_commands(self):
        with patch.object(Path,'exists',return_value=True),patch.object(M.subprocess,'check_output') as command:
            with self.assertRaisesRegex(RuntimeError,'unbooted build container'):M.main()
            command.assert_not_called()

    def test_wrong_package_architecture_refuses_before_scaffold_changes(self):
        with patch.object(M,'require_container'),patch.object(M.subprocess,'check_output',return_value='x86_64'),patch.object(M,'canonicalize_input') as cleanup:
            with self.assertRaisesRegex(RuntimeError,'native ARM package architecture'):M.main()
            cleanup.assert_not_called()

    def test_both_arm_bases_bind_dependencies_and_remove_them_before_runtime_stages(self):
        for name in ('Containerfile.arm','Containerfile.arm-recovery'):
            text=(ROOT/name).read_text();start=text.index('FROM quay.io/fedora/fedora-bootc:44 AS base')
            nextstage=text.index('\nFROM ',start+1);base=text[start:nextstage]
            for dependency in ('plasma_stable/runtime_state.py','prepare_arm_compose_base.py','arm-runtime-rules.json','finalize_image_state.py','finalize_canary_base.py','finalize_root_home.py'):
                self.assertIn(dependency,base)
            self.assertIn('python3 /moos-arm-compose/prepare_arm_compose_base.py',base)
            self.assertIn('&& ostree container commit',base);self.assertIn('&& rm -rf /moos-arm-compose',base)
        source=(ROOT/'build_files/prepare_arm_compose_base.py').read_text()
        self.assertIn("'--exclude=kernel*'",source)
        self.assertNotIn('machine-id-setup',source)

    def test_arm_metadata_has_only_explicit_native_creator_or_parent_roles(self):
        records=json.loads((ROOT/'build_files/arm-runtime-rules.json').read_text())['records']
        for name,record in records.items():
            self.assertTrue(name.startswith('var/'))
            self.assertFalse(name.startswith('var/roothome'))
            self.assertNotEqual(name,'var/lib/selinux')
            self.assertTrue(record.get('authorities') or record.get('implicit_parent') or record.get('derived'),name)
            if record.get('derived'):
                self.assertIn(name,('var/lib/systemd/random-seed','var/lib/systemd/catalog/database'))

    def arm_authority(self):
        M.canonicalize_input(self.root)
        transaction=M.ArmTransaction(self.root,{})
        path=self.root/M.RPMSTATE_AUTHORITY
        data=(ROOT/'tests/fixtures/compose/bootc-base-rpmstate.conf').read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),M.REVIEWED_RPMSTATE_SHA256)
        path.write_bytes(data);path.chmod(0o664)
        record={'authorities':[{'authority':M.RPMSTATE_AUTHORITY,
                 'rule':['d','/var/lib/rpm-state','0755','-','-','-']}]}
        return transaction,path,data,record

    def test_one_native_group_writable_authority_retains_exact_bytes_and_mode(self):
        transaction,path,data,record=self.arm_authority();transaction.authority(record)
        self.assertEqual(path.read_bytes(),data);self.assertEqual(path.stat().st_mode&0o777,0o664)

    def test_group_writable_authority_hash_drift_refuses(self):
        transaction,path,data,record=self.arm_authority();path.write_bytes(data+b'# drift\n')
        with self.assertRaisesRegex(RuntimeError,'unreviewed ARM rpm-state'):transaction.authority(record)

    def test_world_writable_or_fifo_native_authority_refuses_before_read(self):
        transaction,path,_,record=self.arm_authority();path.chmod(0o666)
        with self.assertRaisesRegex(RuntimeError,'unreviewed ARM rpm-state'):transaction.authority(record)
        path.unlink();os.mkfifo(path,0o664);path.chmod(0o664)
        with self.assertRaisesRegex(RuntimeError,'unreviewed ARM rpm-state'):transaction.authority(record)

    def test_other_group_writable_authority_gets_no_exception(self):
        transaction,path,data,record=self.arm_authority();other=path.with_name('other.conf')
        other.write_bytes(data);other.chmod(0o664);record['authorities'][0]['authority']='usr/lib/tmpfiles.d/other.conf'
        with self.assertRaisesRegex(RuntimeError,'unsafe runtime tmpfiles'):transaction.authority(record)

    def test_changed_native_authority_rule_is_not_accepted_by_a_correct_file_hash(self):
        transaction,_,_,record=self.arm_authority();record['authorities'][0]['rule'][2]='0777'
        with self.assertRaisesRegex(RuntimeError,'unreviewed ARM rpm-state'):transaction.authority(record)

    def test_native_authority_mount_is_refused(self):
        transaction,path,_,record=self.arm_authority();original=Path.is_mount
        with patch.object(Path,'is_mount',lambda p:p==path or original(p)):
            with self.assertRaisesRegex(RuntimeError,'unsafe compose mount'):transaction.authority(record)

    def test_native_arm_scaffold_uses_the_same_full_transaction_preflight(self):
        transaction,path,data,record=self.arm_authority()
        self.library.mkdir(mode=0o755);self.state.mkdir(mode=0o755)
        transaction.records={'var/lib':{'kind':'directory','mode':0o755,'user':'root','group':'root'},
          'var/lib/rpm-state':{'kind':'directory','mode':0o755,'user':'root','group':'root',**record}}
        self.identity.write_bytes(b'0123456789abcdef0123456789abcdef\n');transaction.finalize()
        self.assertFalse(self.library.exists());self.assertEqual(self.identity.read_bytes(),b'')
        self.assertEqual(path.read_bytes(),data);self.assertEqual(path.stat().st_mode&0o777,0o664)

    def generated_accounts(self):
        files={}
        for relative,(_,digest) in M.GENERATED_ACCOUNTS.items():
            name=Path(relative).name;data=(ROOT/'tests/fixtures/compose'/('bootc-usr-lib-'+name)).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(),digest)
            path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data);path.chmod(0o664);files[path]=data
        return files

    def test_reviewed_hardlinked_account_replaced_without_changing_alias_inode(self):
        files=self.generated_accounts()
        aliases={}
        for path,data in files.items():
            alias=path.with_name(path.name+'.outside');os.link(path,alias)
            aliases[path]=(alias,alias.stat().st_ino,data)
        M.canonicalize_input(self.root)
        for path,(alias,inode,data) in aliases.items():
            self.assertEqual(alias.stat().st_ino,inode)
            self.assertEqual(alias.stat().st_mode&0o777,0o664)
            self.assertEqual(alias.read_bytes(),data)
            self.assertNotEqual(path.stat().st_ino,inode)
            self.assertEqual(path.stat().st_nlink,1)
            self.assertEqual(path.stat().st_mode&0o777,0o644)
            self.assertEqual(path.read_bytes(),data)

    def test_known_native_account_bytes_survive_root_only_write_permission(self):
        files=self.generated_accounts();M.canonicalize_input(self.root)
        for path,data in files.items():
            self.assertEqual(path.read_bytes(),data);self.assertEqual(path.stat().st_mode&0o777,0o644)

    def test_changed_group_writable_account_is_refused_before_scaffold_deletion(self):
        files=self.generated_accounts();path=next(iter(files));path.write_bytes(files[path]+b'changed')
        self.refused('unreviewed writable ARM account input')
        self.assertEqual(path.stat().st_mode&0o777,0o664)

    def test_other_input_failure_does_not_change_account_metadata(self):
        files=self.generated_accounts();(self.root/'var/unknown').mkdir()
        self.refused('unexpected ARM base input')
        self.assertTrue(all(path.stat().st_mode&0o777==0o664 for path in files))

    def test_linked_or_world_writable_account_never_gets_canonicalized(self):
        files=self.generated_accounts();path=next(iter(files));path.chmod(0o666)
        self.refused('unsafe ARM native account input')
        path.unlink();path.symlink_to('/etc/passwd');self.refused('unexpected symlink')


if __name__=='__main__':unittest.main()
