#!/usr/bin/env python3
"""Isolated transaction failures must restore the vendor converter exactly."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'build_files/install_language_packs.sh'

class TransactionRecovery(unittest.TestCase):
    def run_case(self, transaction, container=True):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binary = root/'convert'
            original = b'#!/bin/bash\nexit 0\n'
            binary.write_bytes(original)
            binary.chmod(0o751)
            marker = root/'container'
            if container: marker.touch()
            # Substitute only filesystem authority paths; execute the real helper.
            script = SOURCE.read_text().replace('/run/.containerenv', str(marker)).replace('/.dockerenv', str(root/'absent'))
            script = script.replace('/usr/lib64/qt6/libexec/qwebengine_convert_dict', str(binary))
            script = script.replace('/tmp/moos-dictionary-transaction.', str(root/'transaction.'))
            helper = root/'helper'; helper.write_text(script)
            fake = root/'dnf5'; fake.write_text('#!/bin/bash\n'+transaction+'\n'); fake.chmod(0o700)
            before = binary.stat()
            env = dict(os.environ, PATH=str(root)+':/usr/bin:/bin', HOME=str(root),
                       DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent', DISPLAY='', WAYLAND_DISPLAY='')
            result = subprocess.run(['bash', str(helper)], env=env, capture_output=True, timeout=10)
            self.assertEqual(binary.read_bytes(), original)
            self.assertEqual(binary.stat().st_mode, before.st_mode)
            self.assertEqual(binary.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertFalse(list(root.glob('transaction.*')))
            return result

    def test_failed_transaction_preserves_exit_and_restores_vendor(self):
        self.assertEqual(self.run_case('exit 61').returncode, 61)
    def test_success_restores_vendor(self):
        self.assertEqual(self.run_case('exit 0').returncode, 0)
    def test_unexpected_package_replacement_fails_and_restores_vendor(self):
        self.assertNotEqual(self.run_case('printf changed > "'+ '${0%/*}/convert' +'"').returncode, 0)
    def test_noncontainer_refuses_before_transaction(self):
        self.assertNotEqual(self.run_case('exit 0', container=False).returncode, 0)

if __name__ == '__main__': unittest.main(verbosity=2)
