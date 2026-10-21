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
            self.assertTrue(record.get('authorities') or record.get('implicit_parent') or record.get('derived'),path)
            if record.get('implicit_parent'):
                self.assertEqual((record['kind'],record['mode'],record['user'],record['group']),
                                 ('directory',0o755,'root','root'))
                self.assertTrue(any(p.startswith(path+'/') and r.get('authorities') for p,r in records.items()),path)
            if record.get('derived'):
                self.assertIn(path,('var/lib/systemd/random-seed','var/lib/systemd/catalog/database'))


if __name__=='__main__':unittest.main()
