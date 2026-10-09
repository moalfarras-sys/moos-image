#!/usr/bin/env python3
"""Exercise real installer admission and private diagnostics without any disk."""

from pathlib import Path
import fcntl
import os
import re
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "system_files/usr/bin/moos-install-to-disk").read_text()
START = SOURCE.index('command -v flock >/dev/null 2>&1 || fail "busy"')
END = SOURCE.index('IMGREF_FILE=')
PREAMBLE = SOURCE[START:END]
MATCH = re.search(r'^prepare_install_log\(\) \{\n.*?^\}\n', SOURCE, re.M | re.S)
assert MATCH, "installer lost private log preparation"
FUNCTION = MATCH.group(0)
assert SOURCE.index('|| fail "not-root"') < START
assert START < SOURCE.index('find_recipe()')
assert 'LOG_DIR=/run/moos-installer' in PREAMBLE
assert '/tmp/moos-install-to-disk.log' not in SOURCE


class PrivateState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="moos-install-state-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / "private"
        self.log = self.directory / "install.log"

    def prepare(self):
        script = ('set -u\nLOG_DIR=$1\nLOG=$2\n' + FUNCTION +
                  '\nprepare_install_log\n')
        return subprocess.run(['bash', '-s', '--', str(self.directory), str(self.log)],
                              input=script, text=True, capture_output=True)

    def test_private_directory_and_file_modes(self):
        self.assertEqual(self.prepare().returncode, 0)
        self.assertEqual(stat.S_IMODE(self.directory.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)
        self.assertEqual(self.log.stat().st_uid, os.geteuid())

    def test_existing_regular_log_is_private_and_reset(self):
        self.directory.mkdir(mode=0o755)
        self.log.write_text('prior diagnostics')
        self.log.chmod(0o644)
        self.assertEqual(self.prepare().returncode, 0)
        self.assertEqual(self.log.read_text(), '')
        self.assertEqual(stat.S_IMODE(self.log.stat().st_mode), 0o600)

    def test_directory_link_cannot_redirect_writes(self):
        victim = self.root / 'other'
        victim.mkdir()
        (victim / 'install.log').write_text('preserve')
        self.directory.symlink_to(victim, target_is_directory=True)
        self.assertNotEqual(self.prepare().returncode, 0)
        self.assertEqual((victim / 'install.log').read_text(), 'preserve')

    def test_file_link_cannot_truncate_another_file(self):
        victim = self.root / 'other-file'
        victim.write_text('preserve')
        self.directory.mkdir()
        self.log.symlink_to(victim)
        self.assertNotEqual(self.prepare().returncode, 0)
        self.assertEqual(victim.read_text(), 'preserve')

    def test_hard_link_cannot_truncate_another_file(self):
        victim = self.root / 'other-file'
        victim.write_text('preserve')
        self.directory.mkdir()
        os.link(victim, self.log)
        self.assertNotEqual(self.prepare().returncode, 0)
        self.assertEqual(victim.read_text(), 'preserve')

    def test_non_file_log_is_refused(self):
        self.directory.mkdir()
        self.log.mkdir()
        self.assertNotEqual(self.prepare().returncode, 0)

    def admission(self, lock, *, prefix=''):
        status = self.root / 'status'
        status.write_text('active progress\n')
        self.directory.mkdir(exist_ok=True)
        self.log.write_text('active diagnostics\n')
        body = PREAMBLE.replace('/run/moos-install.lock', str(lock)).replace(
            'LOG_DIR=/run/moos-installer', 'LOG_DIR=' + str(self.directory))
        script = ('set -u\nSTATUS=$1\n'
                  'emit() { printf "%s\\n" "$*" >> "$STATUS"; }\n'
                  'fail() { emit "FAIL $1"; exit 1; }\n' + prefix + body)
        result = subprocess.run(['bash', '-s', '--', str(status)], input=script,
                                text=True, capture_output=True)
        return result, status.read_text(), self.log.read_text()

    def test_busy_real_lock_preserves_progress_and_diagnostics(self):
        lock = self.root / 'lock'
        with lock.open('w') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result, status, log = self.admission(lock)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL busy', result.stderr)
        self.assertEqual(status, 'active progress\n')
        self.assertEqual(log, 'active diagnostics\n')

    def test_unopenable_lock_cannot_continue(self):
        lock = self.root / 'lock-directory'
        lock.mkdir()
        result, status, log = self.admission(lock)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL busy', status)
        self.assertEqual(log, 'active diagnostics\n')

    def test_missing_flock_cannot_continue(self):
        prefix = ('command() { if [ "$*" = "-v flock" ]; then return 1; '
                  'else builtin command "$@"; fi; }\n')
        result, status, log = self.admission(self.root / 'lock', prefix=prefix)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('FAIL busy', status)
        self.assertEqual(log, 'active diagnostics\n')


if __name__ == '__main__':
    unittest.main()
