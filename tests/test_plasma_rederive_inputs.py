#!/usr/bin/python3
"""Historical review inputs require exact metadata and trusted RPM signatures."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rederive',ROOT/'scripts/plasma-next/rederive_seams.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class HistoricalInputs(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.rpm=self.root/'plasma-desktop-6.8.1-1.fc44.x86_64.rpm';self.rpm.write_bytes(b'fixture')
        self.metadata='plasma-desktop 6.8.1 x86_64';self.signature='Header RSA signature, key fingerprint: trusted: OK\n'
    def inspect(self,args,**kwargs):return self.metadata if args[0]=='rpm' else self.signature
    def call(self):
        with patch.object(M.subprocess,'check_output',side_effect=self.inspect):
            return M.local_rpm(self.root,'plasma-desktop','6.8.1')
    def test_exact_trusted_input(self):self.assertEqual(self.call(),self.rpm.as_uri())
    def test_unsigned_digest_success_is_refused(self):
        self.signature='Header SHA256 digest: OK\n'
        with self.assertRaisesRegex(RuntimeError,'signature'):self.call()
    def test_missing_trust_key_is_refused(self):
        self.signature='Header signature: NOKEY\n'
        with self.assertRaisesRegex(RuntimeError,'signature'):self.call()
    def test_wrong_version_or_architecture_is_refused(self):
        for metadata in ('plasma-desktop 6.8.0 x86_64','plasma-desktop 6.8.1 aarch64','other 6.8.1 x86_64'):
            self.metadata=metadata
            with self.subTest(metadata=metadata),self.assertRaisesRegex(RuntimeError,'metadata'):self.call()
    def test_linked_input_is_refused(self):
        self.rpm.unlink();self.rpm.symlink_to('/etc/passwd')
        with self.assertRaisesRegex(RuntimeError,'regular'):self.call()
    def test_missing_and_ambiguous_releases_refuse(self):
        extra=self.root/'plasma-desktop-6.8.1-2.fc44.x86_64.rpm';extra.touch()
        with self.assertRaisesRegex(RuntimeError,'ambiguous'):self.call()
        self.rpm.unlink();extra.unlink()
        with self.assertRaisesRegex(RuntimeError,'missing'):self.call()
if __name__=='__main__':unittest.main()
