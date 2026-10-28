#!/usr/bin/python3
"""Native RPM01770 must conform to its0750 creator without touching user state."""
from pathlib import Path
import copy,json,os,stat,subprocess,sys,tempfile,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'build_files'),str(ROOT/'build_files/plasma_stable')]
from runtime_state import Transaction
import login_state


class GreeterDirectoryState(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        (self.root/'var/tmp').mkdir(parents=True);(self.root/'var/tmp').chmod(0o1777)
        (self.root/'etc').mkdir();self.identity=self.root/'etc/machine-id';self.identity.touch(mode=0o644)
        self.owner=self.root.stat()
        (self.root/'etc/passwd').write_text(f'plasmalogin:x:{self.owner.st_uid}:{self.owner.st_gid}:fixture:/var/lib/plasmalogin:/sbin/nologin\n')
        (self.root/'etc/group').write_text(f'plasmalogin:x:{self.owner.st_gid}:\n')
        runtime=json.loads((ROOT/'build_files/plasma_stable/runtime-rules.json').read_text())['records']
        record=copy.deepcopy(runtime['var/lib'])
        for entry in record['authorities']:
            authority=self.root/entry['authority'];authority.parent.mkdir(parents=True,exist_ok=True)
            authority.write_text(' '.join(entry['rule'])+'\n')
        self.authority=self.root/login_state.AUTHORITY
        self.authority.write_bytes((ROOT/'tests/fixtures/compose/plasmalogin-6.8.1.conf').read_bytes())
        records={'var/lib':record,login_state.RELATIVE:copy.deepcopy(login_state.RECORD)}
        self.tx=Transaction(self.root,records)
        (self.root/'var/lib').mkdir()
        self.directory=self.root/login_state.RELATIVE;self.directory.mkdir();self.directory.chmod(0o1770)
        self.nvr='6.8.1-1.fc44'
        self.dump='/var/lib/plasmalogin 0 1792454400 '+'0'*64+' 041770 plasmalogin plasmalogin 0 0 0 X\n'
        self.commands=[]

    def query(self,args,**kwargs):
        self.commands.append(args)
        if '--dump' in args:return self.dump
        if '--qf' in args:return self.nvr
        raise AssertionError(args)

    def call(self):
        with patch.object(login_state.subprocess,'check_output',side_effect=self.query):
            return login_state.reconcile(self.tx)

    def refused(self,match):
        before=self.directory.lstat();identity=self.identity.read_bytes()
        with self.assertRaisesRegex((RuntimeError,OSError),match):self.call()
        after=self.directory.lstat()
        self.assertEqual((before.st_mode,before.st_uid,before.st_gid),(after.st_mode,after.st_uid,after.st_gid))
        self.assertEqual(self.identity.read_bytes(),identity)

    def test_exact_empty_native_rpm_state_conforms_and_unchanged_final_gate_passes(self):
        authority=self.authority.read_bytes();self.assertTrue(self.call())
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode),0o750)
        self.tx.finalize()
        self.assertFalse(self.directory.exists());self.assertEqual(self.identity.read_bytes(),b'')
        self.assertEqual(self.authority.read_bytes(),authority)
        self.assertEqual([p.name for p in (self.root/'var').iterdir()],['tmp'])

    def test_already_native_runtime_mode_is_idempotent(self):
        self.directory.chmod(0o750);self.assertFalse(self.call())
        self.assertFalse(any('--dump' in args for args in self.commands))
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode),0o750)

    def test_exact_beta_rpm_metadata_and_native_creator_conform_in_same_transaction(self):
        native=json.loads((ROOT/'tests/fixtures/compose/plasmalogin-6.7.91-native.json').read_text())
        self.nvr=native['nvr'];self.dump=native['rpm_dump']
        import hashlib
        self.assertEqual(hashlib.sha256(self.authority.read_bytes()).hexdigest(),native['creator_sha256'])
        self.assertTrue(self.call())
        self.tx.finalize()
        self.assertEqual(self.identity.read_bytes(),b'')
        self.assertEqual([p.name for p in (self.root/'var').iterdir()],['tmp'])

    def test_exact_682_native_metadata_and_creator_conform(self):
        self.nvr='6.8.2-1.fc44'
        self.assertTrue(self.call())
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode),0o750)
        self.assertFalse(self.call())

    def test_absent_directory_is_not_created(self):
        self.directory.rmdir();self.assertFalse(self.call());self.assertFalse(self.directory.exists())

    def test_existing_state_file_even_empty_is_never_discarded_or_repermissioned(self):
        state=self.directory/'state.conf';state.touch();self.refused('populated greeter')
        self.assertTrue(state.exists())

    def test_already_correct_mode_does_not_hide_unknown_payload(self):
        self.directory.chmod(0o750);state=self.directory/'owner-data';state.write_text('keep')
        self.refused('populated greeter');self.assertEqual(state.read_text(),'keep')

    def test_other_modes_are_not_normalized(self):
        for mode in (0o755,0o777,0o1777,0o700):
            with self.subTest(mode=oct(mode)):
                self.directory.chmod(mode);self.refused('unreviewed greeter directory mode')

    def test_wrong_owner_refuses_before_chmod(self):
        with patch.object(self.tx,'ids',return_value=(self.owner.st_uid+1,self.owner.st_gid)):
            self.refused('unsafe transaction metadata')

    def test_mounted_directory_refuses_before_chmod(self):
        original=Path.is_mount
        with patch.object(Path,'is_mount',lambda path:path==self.directory or original(path)):
            self.refused('unsafe transaction metadata')

    def test_directory_link_is_never_followed(self):
        self.directory.rmdir();other=self.root/'keep';other.mkdir();other.chmod(0o1770)
        self.directory.symlink_to(other)
        self.refused('symlink|link');self.assertEqual(stat.S_IMODE(other.stat().st_mode),0o1770)

    def test_creator_mode_drift_is_refused(self):
        self.authority.write_text(self.authority.read_text().replace('0750','0777',1))
        self.refused('authority drifted')

    def test_creator_extra_child_or_relabel_drift_is_refused(self):
        original=self.authority.read_text()
        for text in (original+'f /var/lib/plasmalogin/state.conf 0644 root root -\n',original.replace('Z\t/var/lib/plasmalogin\t-\tplasmalogin\tplasmalogin','Z\t/var/lib/plasmalogin\t-\troot\troot')):
            with self.subTest(text=text[-70:]):
                self.authority.write_text(text);self.refused('creator scope drifted')

    def test_writable_creator_is_refused(self):
        self.authority.chmod(0o666);self.refused('unsafe runtime tmpfiles authority')

    def test_creator_link_is_never_followed(self):
        data=self.authority.read_bytes();self.authority.unlink();other=self.root/'keep';other.write_bytes(data)
        self.authority.symlink_to(other);self.refused('symlink|link');self.assertEqual(other.read_bytes(),data)

    def test_unknown_package_version_refuses(self):
        for nvr in ('6.7.91-2.fc44','6.7.92-1.fc44','6.8.3-1.fc44'):
            with self.subTest(nvr=nvr):
                self.nvr=nvr;self.refused('unreviewed greeter directory package')

    def test_rpm_query_failure_remains_nonzero(self):
        with patch.object(login_state.subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,['rpm'])):
            with self.assertRaises(subprocess.CalledProcessError):login_state.reconcile(self.tx)
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode),0o1770)

    def test_missing_duplicate_wrong_mode_owner_and_nonempty_rpm_metadata_refuse(self):
        original=self.dump
        for dump in ('',original+original,original.replace('041770','040750'),original.replace('plasmalogin plasmalogin','root root'),original.replace('/var/lib/plasmalogin 0 ','/var/lib/plasmalogin 1 ')):
            with self.subTest(dump=dump[-70:]):
                self.dump=dump;self.refused('no exact native RPM metadata')

    def test_runtime_record_drift_cannot_change_the_target_policy(self):
        self.tx.records[login_state.RELATIVE]['mode']=0o777;self.refused('record drifted')

    def test_finished_transaction_is_not_a_standalone_reset_permission(self):
        self.tx.finished=True;self.refused('already finished')


if __name__=='__main__':unittest.main()
