#!/usr/bin/env python3
"""Inactive-store equality and empty-package authority, including refusal controls."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build_files'))
from finalize_canary_base import finalize, DERIVED


class CanaryState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.real = self.root / 'etc/selinux/targeted'
        self.old = self.root / 'var/lib/selinux/targeted'
        for parent in (self.real, self.old):
            (parent/'active/modules/100/example').mkdir(parents=True)
            (parent/'active/modules/100/example/cil').write_bytes(b'reviewed vendor module')
            for name in DERIVED:
                (parent/'active'/name).write_bytes(b'compiled' if name == 'policy.kern' else b'derived')
        (self.real/'policy').mkdir()
        (self.real/'policy/policy.35').write_bytes(b'compiled')
        (self.root/'etc/selinux/semanage.conf').write_text('module-store = direct\nstore-root=/etc/selinux\n')
        for lock in ('semanage.read.LOCK', 'semanage.trans.LOCK'):
            (self.old/lock).touch()
        (self.root/'var/lib/hp').mkdir(mode=0o755)

    def refused(self, pattern):
        with self.assertRaisesRegex(RuntimeError, pattern):
            finalize(self.root)
        self.assertTrue(self.old.exists(), 'refusal deleted the inactive store')
        self.assertTrue((self.root/'var/lib/hp').exists(), 'refusal deleted package state')

    def test_equal_inactive_inputs_retire_and_real_policy_survives(self):
        original = (self.real/'active/modules/100/example/cil').read_bytes()
        finalize(self.root)
        self.assertFalse(self.old.exists())
        self.assertEqual((self.real/'active/modules/100/example/cil').read_bytes(), original)
        self.assertEqual((self.real/'policy/policy.35').read_bytes(), b'compiled')
        self.assertIn('d /var/lib/hp 0755 root root',
                      (self.root/'usr/lib/tmpfiles.d/moos-plasma-next-state.conf').read_text())

    def test_configured_var_store_is_never_retired(self):
        (self.root/'etc/selinux/semanage.conf').write_text('module-store=direct\nstore-root=/var/lib/selinux\n')
        self.refused('not proven inactive')

    def test_changed_or_new_module_is_never_retired(self):
        (self.old/'active/modules/100/example/cil').write_bytes(b'new policy')
        self.refused('absent or different')

    def test_missing_module_is_not_a_safe_duplicate(self):
        (self.real/'active/modules/100/example/cil').unlink()
        self.refused('absent or different')

    def test_actual_boot_policy_mismatch_is_refused(self):
        (self.real/'policy/policy.35').write_bytes(b'wrong boot policy')
        self.refused('actual boot policy')

    def test_unrecognized_state_is_refused(self):
        (self.old/'active/owner-data').write_bytes(b'keep')
        self.refused('unexpected inactive')

    def test_populated_hp_state_is_refused_before_any_deletion(self):
        (self.root/'var/lib/hp/owner-data').write_bytes(b'keep')
        self.refused('not an empty owned')

    def test_linked_module_is_refused(self):
        path = self.old/'active/modules/100/example/cil'
        path.unlink()
        path.symlink_to(self.real/'active/modules/100/example/cil')
        self.refused('unexpected symlink')

    def test_native_mount_detection_refuses_cleanup(self):
        from unittest.mock import patch
        original = Path.is_mount
        def mounted(path):
            return path == self.old/'active/modules' or original(path)
        with patch.object(Path, 'is_mount', mounted):
            self.refused('unsafe owner or mount')


if __name__ == '__main__':
    unittest.main()
