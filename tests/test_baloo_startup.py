#!/usr/bin/env python3
"""Baloo startup and live indexed-directory identity must both be trustworthy."""
import configparser
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DROPIN = ROOT / 'system_files/usr/lib/systemd/user/kde-baloo.service.d/30-moos-session-ordering.conf'


class BalooStartup(unittest.TestCase):
    def test_indexer_waits_for_core_not_its_own_parent(self):
        config = configparser.ConfigParser(interpolation=None)
        config.read(DROPIN)
        after = config.get('Unit', 'After').split()
        self.assertIn('plasma-core.target', after)
        # kde-baloo is Before=plasma-workspace.target; waiting for that same
        # parent would create an ordering cycle and discard a startup job.
        self.assertNotIn('plasma-workspace.target', after)
        self.assertNotIn('graphical-session.target', after)

    def test_vendor_index_and_idle_integration_remain_owned_upstream(self):
        text = DROPIN.read_text()
        for override in ('ExecStart=', 'Environment=', 'Restart=', 'WantedBy=', 'Requires='):
            self.assertNotIn(override, text)
        self.assertTrue((ROOT / 'system_files/usr/lib/systemd/user/kde-baloo.service.d/20-moos-regexp-stability.conf').is_file())


class BalooIdentity(unittest.TestCase):
    """Execute the exact acceptance block with private CLI evidence, never the host DB."""

    def run_check(self, variant, command_status=0):
        script = (ROOT / 'tests/post-update-check.sh').read_text()
        block = script.split('# BEGIN BALOO IDENTITY CHECK', 1)[1].split('# END BALOO IDENTITY CHECK', 1)[0]
        with tempfile.TemporaryDirectory(prefix='moos-baloo-identity-') as directory:
            work = Path(directory)
            home = work / 'منزل المستخدم'
            home.mkdir()
            device, inode = 1531017502, 489812
            identifier = int.from_bytes(struct.pack('=II', device, inode), sys.byteorder)
            row = f'{identifier:x} {device} {inode} {home}\n'
            if variant == 'valid':
                evidence = row + '\tMtime: 123\nInternal Info\n'
            elif variant == 'mismatch':
                # Retained native failure class: the tool still returned0.
                evidence = ('The document IDs of the Baloo DB and the filesystem are different:\n'
                            f'Url: {home}\nDeviceID: 1531015437 (DB) <-> {device} (FS)\n' + row)
            elif variant == 'changed_diagnostic':
                evidence = f'ID: 100 (DB) <-> 200 (FS)\n' + row
            elif variant == 'empty':
                evidence = ''
            elif variant == 'wrong_home':
                evidence = row.replace(str(home), str(work / 'another-home'))
            elif variant == 'invalid_id':
                evidence = row.replace(f'{identifier:x}', 'not-an-id', 1)
            elif variant == 'inconsistent_id':
                evidence = row.replace(f'{identifier:x}', f'{identifier+1:x}', 1)
            elif variant == 'duplicate':
                evidence = row + row
            elif variant == 'symlink':
                alias = work / 'home-alias'
                alias.symlink_to(home, target_is_directory=True)
                evidence = row.replace(str(home), str(alias))
            else:
                raise AssertionError(variant)
            calls = work / 'calls.jsonl'
            stub = work / 'balooshow6'
            stub.write_text(f'#!{sys.executable}\n'
                            'import json, os, pathlib, sys\n'
                            'pathlib.Path(os.environ["TEST_CALLS"]).write_text(json.dumps(sys.argv[1:]))\n'
                            'print(os.environ["TEST_IDENTITY_OUTPUT"], end="")\n'
                            'sys.exit(int(os.environ["TEST_IDENTITY_EXIT"]))\n')
            stub.chmod(0o755)
            env = os.environ.copy()
            env.update(HOME=str(home), PATH=f'{work}:{env["PATH"]}',
                       DBUS_SESSION_BUS_ADDRESS='unix:path=/moos-test/no-session-bus',
                       TEST_CALLS=str(calls), TEST_IDENTITY_OUTPUT=evidence,
                       TEST_IDENTITY_EXIT=str(command_status))
            prefix = 'fail=0\nok() { echo "PASS $1"; }\nbad() { echo "FAIL $1"; fail=$((fail+1)); }\n'
            result = subprocess.run(['bash', '-c', prefix + block + '\nexit "$fail"\n'],
                                    env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(json.loads(calls.read_text()), ['-x', str(home)])
            return result

    def test_valid_native_shape_and_canonical_alias_pass(self):
        for variant in ('valid', 'symlink'):
            with self.subTest(variant=variant):
                result = self.run_check(variant)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('PASS Baloo indexes HOME', result.stdout)

    def test_zero_exit_with_db_filesystem_disagreement_fails(self):
        for variant in ('mismatch', 'changed_diagnostic'):
            with self.subTest(variant=variant):
                result = self.run_check(variant)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn('stale or unavailable', result.stdout)

    def test_empty_wrong_and_malformed_success_cannot_pass(self):
        for variant in ('empty', 'wrong_home', 'invalid_id', 'inconsistent_id', 'duplicate'):
            with self.subTest(variant=variant):
                result = self.run_check(variant)
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_failed_command_cannot_pass_its_success_shaped_output(self):
        for status in (1, 127):
            with self.subTest(status=status):
                result = self.run_check('valid', status)
                self.assertNotEqual(result.returncode, 0, result.stdout)


if __name__ == '__main__':
    unittest.main()
