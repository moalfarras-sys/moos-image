#!/usr/bin/python3
"""A pristine build transaction may retire runtime scaffolds, never owner state."""
from pathlib import Path
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'build_files'),str(ROOT/'build_files/plasma_stable')]
from runtime_state import Transaction


class RuntimeTransaction(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        (self.root/'var/tmp').mkdir(parents=True,mode=0o1777);(self.root/'var/tmp').chmod(0o1777)
        (self.root/'etc').mkdir();self.identity=self.root/'etc/machine-id';self.identity.touch(mode=0o644)
        self.authority=self.root/'usr/lib/tmpfiles.d/native.conf'
        self.authority.parent.mkdir(parents=True);self.rule=['d','/var/service','0755','root','root','-']
        self.authority.write_text(' '.join(self.rule)+'\n')
        self.records={'var/service':{'kind':'directory','mode':0o755,'user':'root','group':'root',
                      'authorities':[{'authority':'usr/lib/tmpfiles.d/native.conf','rule':self.rule}]}}
        self.tx=Transaction(self.root,copy.deepcopy(self.records))
        self.base=self.root/'var/service';self.base.mkdir()
        self.new_identity=b'0123456789abcdef0123456789abcdef\n'
        self.identity.write_bytes(self.new_identity)

    def test_bind_mount_preflight_precedes_all_tree_enumeration(self):
        with patch('runtime_state.mount_points',return_value={self.root/'var/cache/bound'}), \
                patch.object(Path,'is_mount',return_value=False), \
                patch.object(Path,'iterdir',side_effect=AssertionError('traversed bind subtree')):
            with self.assertRaisesRegex(RuntimeError,'mounted'):self.tx.finalize()
        self.assertEqual(self.identity.read_bytes(),self.new_identity)
        self.assertTrue(self.base.exists())

    def test_local_authority_override_precedes_first_mutation(self):
        for folder in ('etc/tmpfiles.d','run/tmpfiles.d','usr/local/lib/tmpfiles.d'):
            override=self.root/folder/self.authority.name;override.parent.mkdir(parents=True,exist_ok=True)
            override.symlink_to('/dev/null')
            with patch.object(Path,'unlink',side_effect=AssertionError('early delete')), \
                    patch.object(Path,'rmdir',side_effect=AssertionError('early delete')):
                self.refused('override')
            override.unlink()

    def refused(self, text):
        with self.assertRaisesRegex((RuntimeError,OSError),text):self.tx.finalize()
        self.assertEqual(self.identity.read_bytes(),self.new_identity)
        self.assertTrue(self.base.exists(),'refusal removed a known scaffold before finishing preflight')

    def test_input_populated_machine_id_is_never_reset(self):
        with self.assertRaisesRegex(RuntimeError,'input machine-id must be empty'):
            Transaction(self.root,self.records)
        self.assertEqual(self.identity.read_bytes(),self.new_identity)

    def test_input_unknown_var_is_not_a_pristine_transaction(self):
        self.identity.write_bytes(b'')
        with self.assertRaisesRegex(RuntimeError,'input /var'):Transaction(self.root,self.records)

    def test_input_tmp_payload_is_preserved(self):
        self.identity.write_bytes(b'');self.base.rmdir();p=self.root/'var/tmp/owner';p.write_text('keep')
        with self.assertRaisesRegex(RuntimeError,'tmp must be empty'):Transaction(self.root,self.records)
        self.assertEqual(p.read_text(),'keep')

    def test_native_empty_scaffold_and_generated_identity_retire_together(self):
        authority=self.authority.read_bytes();self.tx.finalize()
        self.assertEqual(self.identity.read_bytes(),b'');self.assertFalse(self.base.exists())
        self.assertEqual(self.authority.read_bytes(),authority)
        self.assertEqual([p.name for p in (self.root/'var').iterdir()],['tmp'])
        with self.assertRaisesRegex(RuntimeError,'already finalized'):self.tx.finalize()

    def test_unknown_payload_refuses_before_identity_or_scaffold_change(self):
        p=self.base/'owner-data';p.write_text('keep');self.refused('unexpected transaction state')
        self.assertEqual(p.read_text(),'keep')

    def test_unknown_empty_directory_is_still_refused(self):
        (self.root/'var/unknown').mkdir();self.refused('unexpected transaction state')

    def test_changed_authority_is_refused(self):
        self.authority.write_text('d /var/service 0777 root root -\n');self.refused('authority drifted')

    def test_extra_creator_for_same_path_is_refused(self):
        self.authority.write_text(self.authority.read_text()+'L /var/service - - - - /tmp\n')
        self.refused('authority drifted')

    def test_writable_and_fifo_authorities_refuse_without_reading(self):
        self.authority.chmod(0o666);self.refused('unsafe runtime tmpfiles authority')
        self.authority.unlink();os.mkfifo(self.authority);self.refused('unsafe runtime tmpfiles authority')

    def test_metadata_drift_refuses(self):
        self.base.chmod(0o777);self.refused('unsafe transaction metadata')

    def test_mount_refuses(self):
        original=Path.is_mount
        with patch.object(Path,'is_mount',lambda p:p==self.base or original(p)):
            self.refused('unsafe transaction metadata')

    def test_identity_alias_is_never_followed(self):
        self.identity.unlink();other=self.root/'keep';other.write_bytes(self.new_identity)
        self.identity.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,'unsafe transaction metadata'):self.tx.finalize()
        self.assertEqual(other.read_bytes(),self.new_identity);self.assertTrue(self.base.exists())

    def test_hardlinked_identity_is_never_truncated(self):
        other=self.root/'keep';os.link(self.identity,other)
        self.refused('unsafe transaction metadata')
        self.assertEqual(other.read_bytes(),self.new_identity)

    def test_exact_reviewed_runtime_alias_retires_without_touching_target(self):
        target=self.root/'keep';target.write_text('keep')
        link=self.root/'var/runtime-link';link.symlink_to('/keep')
        rule=['L','/var/runtime-link','-','-','-','-','/keep']
        self.authority.write_text(self.authority.read_text()+' '.join(rule)+'\n')
        self.tx.records['var/runtime-link']={'kind':'link','mode':0o777,'user':'root','group':'root',
          'target':'/keep','authorities':[{'authority':'usr/lib/tmpfiles.d/native.conf','rule':rule}]}
        self.tx.finalize();self.assertFalse(os.path.lexists(link));self.assertEqual(target.read_text(),'keep')

    def test_escaping_unknown_alias_refuses(self):
        (self.root/'var/other').symlink_to('/etc');self.refused('unexpected transaction state')

    def test_unknown_link_in_cache_cannot_escape(self):
        cache=self.root/'var/cache';cache.mkdir();(cache/'escape').symlink_to('/etc')
        self.refused('unsafe entry')

    def seed(self, data):
        path=self.root/'var/lib/systemd/random-seed';path.parent.mkdir(parents=True)
        path.write_bytes(data);path.chmod(0o600)
        for rel in ('var/lib','var/lib/systemd'):
            self.tx.records[rel]={'kind':'directory','mode':0o755,'user':'root','group':'root'}
        self.tx.records['var/lib/systemd/random-seed']={
            'kind':'file','mode':0o600,'user':'root','group':'root','derived':True}
        return path

    def test_new_fixed_size_random_seed_retires_with_new_identity(self):
        seed=self.seed(b'x'*32);self.tx.finalize()
        self.assertFalse(seed.exists());self.assertEqual(self.identity.read_bytes(),b'')

    def test_seed_size_drift_is_protected(self):
        seed=self.seed(b'owner-data');self.refused('unexpected transaction random seed')
        self.assertEqual(seed.read_bytes(),b'owner-data')

    def test_seed_without_generated_identity_is_protected(self):
        seed=self.seed(b'x'*32);self.identity.write_bytes(b'')
        with self.assertRaisesRegex(RuntimeError,'unexpected transaction random seed'):self.tx.finalize()
        self.assertTrue(seed.exists());self.assertTrue(self.base.exists())

    def test_conflicting_immutable_and_mutable_service_owners_refuse(self):
        for prefix,number in [('etc',123),('usr/lib',124)]:
            p=self.root/prefix/'passwd';p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(f'service:x:{number}:123::/:/bin/false\n')
        self.tx.records['var/service']['user']='service'
        self.refused('ambiguous native owner')

    def test_nonempty_declared_file_is_protected(self):
        path=self.root/'var/template';path.write_text('keep')
        rule=['f','/var/template','0644','root','root','-']
        self.authority.write_text(self.authority.read_text()+' '.join(rule)+'\n')
        self.tx.records['var/template']={'kind':'file','mode':0o644,'user':'root','group':'root',
           'authorities':[{'authority':'usr/lib/tmpfiles.d/native.conf','rule':rule}]}
        self.refused('nonempty transaction scaffold')
        self.assertEqual(path.read_text(),'keep')

    def test_reviewed_records_have_authority_or_narrow_derived_parent_role(self):
        records=json.loads((ROOT/'build_files/plasma_stable/runtime-rules.json').read_text())['records']
        for path,record in records.items():
            self.assertTrue(path.startswith('var/'))
            self.assertTrue(record.get('authorities') or record.get('implicit_parent')
                            or record.get('derived') or record.get('rpm_postin_authority'),path)
            if record.get('rpm_postin_authority'):
                self.assertEqual(path,'var/lib/.ssh-host-keys-migration')
                self.assertEqual(record,{'kind':'file','mode':0o644,'user':'root','group':'root',
                    'rpm_postin_authority':'openssh-server-10.2p1-16.fc44.x86_64'})
            if record.get('implicit_parent'):
                self.assertEqual((record['kind'],record['mode'],record['user'],record['group']),
                                 ('directory',0o755,'root','root'))
                self.assertTrue(any(p.startswith(path+'/') and r.get('authorities') for p,r in records.items()),path)
            if record.get('derived'):
                self.assertIn(path,('var/lib/systemd/random-seed','var/lib/systemd/catalog/database'))


class SSHMigrationAuthority(unittest.TestCase):
    def setUp(self):
        import hashlib
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        (self.root/'var/tmp').mkdir(parents=True);(self.root/'var/tmp').chmod(0o1777)
        (self.root/'etc/ssh').mkdir(parents=True)
        self.identity=self.root/'etc/machine-id';self.identity.touch(mode=0o644)
        rules=json.loads((ROOT/'build_files/plasma_stable/runtime-rules.json').read_text())['records']
        self.records={key:copy.deepcopy(rules[key]) for key in ('var/lib','var/lib/.ssh-host-keys-migration')}
        # Native var/lib authority is already exercised above. This fixture
        # concentrates on the distinct RPM POSTIN creator and retirement order.
        self.records['var/lib'].pop('authorities',None)
        self.tx=Transaction(self.root,self.records)
        (self.root/'var/lib').mkdir();self.marker=self.root/'var/lib/.ssh-host-keys-migration'
        self.marker.touch(mode=0o644)
        self.new_identity=b'0123456789abcdef0123456789abcdef\n';self.identity.write_bytes(self.new_identity)
        self.inputs={}
        fixture=ROOT/'tests/fixtures/compose-ssh-migration'
        for relative,name,mode in [('usr/libexec/openssh/ssh-host-keys-migration.sh','migration.sh',0o744),
                ('usr/lib/systemd/system/ssh-host-keys-migration.service','migration.service',0o644)]:
            p=self.root/relative;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes((fixture/name).read_bytes());p.chmod(mode);self.inputs[relative]=p
        self.metadata='openssh-server 10.2p1-16.fc44 x86_64 openssh-10.2p1-16.fc44.src.rpm'
        self.postin=(fixture/'postinstall.sh').read_bytes()
        self.dump='\n'.join('/'+relative+' 0 0 '+hashlib.sha256(p.read_bytes()).hexdigest()
            +' 0100644 root root 0 0 0 X' for relative,p in self.inputs.items())
        self.rpm=patch('runtime_state.subprocess.check_output',side_effect=self.query).start()
        self.addCleanup(patch.stopall)

    def query(self,args,**kwargs):
        self.assertEqual(args[:4],['rpm','--root',str(self.root),'-q'])
        self.assertEqual(args[-1],'openssh-server')
        if '--dump' in args:return self.dump
        if args[-2]=='%{POSTIN}':return self.postin
        self.assertEqual(args[-2],'%{NAME} %{VERSION}-%{RELEASE} %{ARCH} %{SOURCERPM}')
        return self.metadata

    def refused(self,message):
        with self.assertRaisesRegex((RuntimeError,OSError),message):self.tx.finalize()
        self.assertTrue(os.path.lexists(self.marker))
        self.assertEqual(self.identity.read_bytes(),self.new_identity)

    def test_reviewed_empty_marker_retires_only_after_complete_preflight(self):
        before={k:p.read_bytes() for k,p in self.inputs.items()}
        self.tx.finalize()
        self.assertFalse(self.marker.exists());self.assertEqual(self.identity.read_bytes(),b'')
        self.assertEqual({k:p.read_bytes() for k,p in self.inputs.items()},before)
        self.assertEqual([p.name for p in (self.root/'var').iterdir()],['tmp'])

    def test_original_unknown_marker_refusal_is_retained(self):
        del self.tx.records['var/lib/.ssh-host-keys-migration']
        self.refused('unexpected transaction state')

    def test_nonempty_marker_is_not_a_generated_completion(self):
        self.marker.write_bytes(b'preserve unknown state');self.refused('nonempty SSH')
        self.assertEqual(self.marker.read_bytes(),b'preserve unknown state')

    def test_target_symlink_fifo_hardlink_and_writable_modes_refuse(self):
        for kind in ('link','fifo','hardlink','writable'):
            with self.subTest(kind=kind):
                self.marker.unlink()
                other=self.root/'unknown';other.write_bytes(b'')
                if kind=='link':self.marker.symlink_to(other)
                elif kind=='fifo':os.mkfifo(self.marker)
                elif kind=='hardlink':os.link(other,self.marker)
                else:self.marker.touch(mode=0o666);self.marker.chmod(0o666)
                self.refused('unsafe transaction metadata')
                self.marker.unlink();other.unlink();self.marker.touch(mode=0o644)

    def test_package_nvr_architecture_and_source_drift_refuse(self):
        original=self.metadata
        for value in (original.replace('-16.', '-17.'),original.replace('x86_64','aarch64'),
                original.replace('openssh-10.2p1','other-10.2p1')):
            self.metadata=value;self.refused('unreviewed SSH')

    def test_postinstall_script_drift_refuses(self):
        self.postin+=b'\n# changed';self.refused('POSTIN authority drifted')

    def test_both_immutable_authorities_require_exact_bytes_and_rpm_payload(self):
        for p in self.inputs.values():
            original=p.read_bytes();p.write_bytes(original+b'\n# changed')
            self.refused('authority payload drifted');p.write_bytes(original)
        self.dump=self.dump.replace(' 0 0 ',' 0 0 0000',1)
        self.refused('authority payload drifted')

    def test_readonly_authority_hardlinks_remain_valid(self):
        os.link(next(iter(self.inputs.values())),self.root/'retained-base-hardlink')
        self.tx.finalize();self.assertFalse(self.marker.exists())

    def test_unknown_even_empty_host_key_names_remain_untouched(self):
        for kind in ('file','directory','link','fifo'):
            key=self.root/'etc/ssh/ssh_host_unknown_key'
            if kind=='file':key.touch()
            elif kind=='directory':key.mkdir()
            elif kind=='link':key.symlink_to('/missing-owner-key')
            else:os.mkfifo(key)
            self.refused('host key state must be preserved')
            if kind=='directory':key.rmdir()
            else:key.unlink()

    def test_runtime_or_administrator_unit_overrides_refuse(self):
        for prefix in ('etc/systemd/system','run/systemd/system','usr/local/lib/systemd/system'):
            p=self.root/prefix/'ssh-host-keys-migration.service';p.parent.mkdir(parents=True,exist_ok=True)
            p.touch();self.refused('unit override');p.unlink()
            p.symlink_to('/dev/null');self.refused('unit override');p.unlink()

    def test_exact_atomic_local_alias_is_preserved_without_following_unknown_links(self):
        alias=self.root/'usr/local';alias.symlink_to('../var/usrlocal')
        self.tx.finalize();self.assertEqual(os.readlink(alias),'../var/usrlocal')

    def test_atomic_mapped_unit_mask_refuses(self):
        (self.root/'usr/local').symlink_to('../var/usrlocal')
        p=self.root/'var/usrlocal/lib/systemd/system/ssh-host-keys-migration.service'
        p.parent.mkdir(parents=True);p.symlink_to('/dev/null')
        with self.assertRaisesRegex(RuntimeError,'unit override'):self.tx.ssh_migration_authority()
        self.assertTrue(self.marker.exists());self.assertEqual(self.identity.read_bytes(),self.new_identity)

    def test_unknown_local_alias_refuses(self):
        (self.root/'usr/local').symlink_to('/unknown');self.refused('unreviewed local tmpfiles prefix alias')

    def test_host_key_bind_mount_refuses_before_traversal(self):
        with patch('runtime_state.mount_points',return_value={self.root/'etc/ssh'}), \
                patch.object(Path,'glob',side_effect=AssertionError('traversed keys before mount refusal')):
            self.refused('unsafe compose mount')

    def test_unknown_sibling_preserves_reviewed_marker_too(self):
        p=self.root/'var/lib/unknown';p.write_bytes(b'preserve')
        self.refused('unexpected transaction state');self.assertEqual(p.read_bytes(),b'preserve')

    def test_absent_marker_needs_no_new_rpm_provider(self):
        self.marker.unlink();self.tx.finalize();self.rpm.assert_not_called()


if __name__=='__main__':unittest.main()
