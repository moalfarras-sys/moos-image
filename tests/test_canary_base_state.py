#!/usr/bin/env python3
"""Inactive-store equality and empty-package authority, including refusal controls."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build_files'))
from finalize_canary_base import finalize, tree, DERIVED


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

    def alias(self, target='../../etc/selinux'):
        import shutil
        shutil.rmtree(self.old.parent)
        self.old.parent.symlink_to(target)
        authority = self.root/'usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf'
        authority.parent.mkdir(parents=True, exist_ok=True)
        authority.write_text('L /var/lib/selinux - - - - ../../etc/selinux\n')
        return authority

    def test_exact_vendor_alias_retired_without_touching_real_policy(self):
        self.alias()
        from finalize_canary_base import tree
        before = tree(self.root, 'etc/selinux/targeted')
        finalize(self.root)
        self.assertFalse(self.old.parent.is_symlink())
        self.assertEqual(tree(self.root, 'etc/selinux/targeted'), before)

    def test_alias_requires_exact_target_and_authority(self):
        for target in ('/etc/selinux', '../../etc', '../../etc/selinux/targeted', '../../../outside'):
            with self.subTest(target=target):
                self.alias() if not self.old.parent.is_symlink() else None
                self.old.parent.unlink()
                self.old.parent.symlink_to(target)
                with self.assertRaisesRegex(RuntimeError, 'unreviewed SELinux'):
                    finalize(self.root)
                self.assertTrue(self.old.parent.is_symlink())
        self.old.parent.unlink()
        self.old.parent.symlink_to('../../etc/selinux')
        authority = self.root/'usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf'
        authority.write_text('# L /var/lib/selinux - - - - ../../etc/selinux\n')
        with self.assertRaisesRegex(RuntimeError, 'missing authority'):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())

    def test_alias_refuses_higher_priority_authority_before_any_retirement(self):
        self.alias()
        override = self.root/'etc/tmpfiles.d/rpm-ostree-0-integration.conf'
        override.parent.mkdir(parents=True)
        override.symlink_to('/dev/null')
        before = tree(self.root, 'etc/selinux/targeted')
        with self.assertRaisesRegex(RuntimeError, 'local tmpfiles authority override'):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())
        self.assertTrue(override.is_symlink())
        self.assertEqual(tree(self.root, 'etc/selinux/targeted'), before)

    def test_alias_never_bypasses_real_policy_or_config(self):
        self.alias()
        (self.real/'policy/policy.35').write_bytes(b'wrong boot policy')
        with self.assertRaisesRegex(RuntimeError, 'actual boot policy'):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())
        (self.real/'policy/policy.35').write_bytes(b'compiled')
        (self.root/'etc/selinux/semanage.conf').write_text('module-store=direct\nstore-root=/var/lib/selinux\n')
        with self.assertRaisesRegex(RuntimeError, 'not proven inactive'):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())

    def test_dangling_alias_and_linked_authority_are_refused(self):
        self.alias()
        import shutil
        shutil.rmtree(self.real.parent)
        with self.assertRaisesRegex(RuntimeError, 'unreviewed SELinux'):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())

    def test_alias_parent_mount_is_refused(self):
        self.alias()
        from unittest.mock import patch
        original = Path.is_mount
        def mounted(path):
            return path == self.old.parent.parent or original(path)
        with patch.object(Path, 'is_mount', mounted):
            with self.assertRaisesRegex(RuntimeError, 'parent owner or mount'):
                finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())

    def test_linked_alias_authority_is_refused(self):
        authority = self.alias()
        other = self.root/'rule'
        authority.rename(other)
        authority.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError, 'unexpected symlink'):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink())

    def test_mountinfo_same_filesystem_bind_and_authority_parent_refused(self):
        self.alias()
        import finalize_canary_base as module
        from unittest.mock import patch
        before = module.tree(self.root, 'etc/selinux/targeted')
        for mount in (self.old.parent.parent, self.root/'usr/lib', self.real/'active/modules'):
            with self.subTest(mount=mount):
                # A same-filesystem bind can report false through is_mount.
                with patch.object(Path, 'is_mount', return_value=False), \
                     patch.object(module, 'mount_points', return_value={Path('/'), mount}):
                    with self.assertRaisesRegex(RuntimeError, 'unsafe.*mount'):
                        finalize(self.root)
                self.assertTrue(self.old.parent.is_symlink())
                self.assertEqual(module.tree(self.root, 'etc/selinux/targeted'), before)

    def test_policy_descendant_mount_refused_before_rglob(self):
        self.alias()
        import finalize_canary_base as module
        from unittest.mock import patch
        before = module.tree(self.root, 'etc/selinux/targeted')
        mount = self.real/'active/modules'
        with patch.object(Path, 'is_mount', return_value=False), \
             patch.object(module, 'mount_points', return_value={Path('/'), mount}), \
             patch.object(Path, 'rglob', side_effect=AssertionError('mounted subtree inspected')) as scan:
            with self.assertRaisesRegex(RuntimeError, 'mounted policy subtree'):
                finalize(self.root)
            scan.assert_not_called()
        self.assertTrue(self.old.parent.is_symlink())
        self.assertEqual(module.tree(self.root, 'etc/selinux/targeted'), before)

    def test_mountinfo_decode_and_fail_closed(self):
        from finalize_canary_base import mount_points
        decoded = mount_points('1 0 8:1 / / rw - btrfs /dev/test rw\n'
                               r'2 1 8:1 / /tmp/a\040b\134c rw - btrfs /dev/test rw' + '\n')
        self.assertIn(Path('/tmp/a b' + chr(92) + 'c'), decoded)
        for text in ('', 'malformed', '1 0 8:1 / relative rw - btrfs /dev/test rw',
                     r'1 0 8:1 / /tmp/bad\777 rw - btrfs /dev/test rw'):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                mount_points(text)

        from unittest.mock import patch
        with patch.object(Path, "read_text", side_effect=OSError("private denied mountinfo")):
            with self.assertRaisesRegex(RuntimeError, "cannot establish"):
                mount_points()

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

    def alias_fixture(self):
        shutil.rmtree(self.old.parent)
        self.old.parent.symlink_to('../../etc/selinux')
        self.authority = self.root/'usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf'
        self.authority.parent.mkdir(parents=True)
        self.authority.write_text('# Native rpm-ostree integration\n'
                                  'L /var/lib/selinux - - - - ../../etc/selinux\n'
                                  'Z /var/lib/selinux - - - -\n')

    def alias_refused(self, pattern):
        target = os.readlink(self.old.parent)
        with self.assertRaisesRegex((RuntimeError, OSError), pattern):
            finalize(self.root)
        self.assertTrue(self.old.parent.is_symlink(), 'refusal unlinked the alias')
        self.assertEqual(os.readlink(self.old.parent), target)
        self.assertTrue((self.root/'var/lib/hp').exists(), 'refusal deleted package state')

    def test_native_tmpfiles_alias_retires_without_touching_configured_store(self):
        self.alias_fixture()
        self.old.parent.unlink()
        command = shutil.which('systemd-tmpfiles')
        self.assertIsNotNone(command, 'the native tmpfiles control must actually execute')
        result = subprocess.run([command, '--create', f'--root={self.root}',
                                 '--prefix=/var/lib/selinux'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.old.parent), '../../etc/selinux')
        before = tree(self.root, 'etc/selinux/targeted')
        authority = self.authority.read_bytes()
        finalize(self.root)
        self.assertFalse(os.path.lexists(self.old.parent))
        self.assertEqual(tree(self.root, 'etc/selinux/targeted'), before)
        self.assertEqual(self.authority.read_bytes(), authority)

    def test_unknown_absolute_and_escaping_aliases_are_refused(self):
        self.alias_fixture()
        for target in ('/etc/selinux', '../../etc/other', '../../../etc/selinux'):
            with self.subTest(target=target):
                self.old.parent.unlink()
                self.old.parent.symlink_to(target)
                self.alias_refused('unrecognized SELinux')

    def test_alias_cannot_retire_a_configured_var_store(self):
        self.alias_fixture()
        (self.root/'etc/selinux/semanage.conf').write_text('module-store=direct\nstore-root=/var/lib/selinux\n')
        self.alias_refused('not proven inactive')

    def test_alias_requires_matching_actual_boot_policy(self):
        self.alias_fixture()
        (self.real/'policy/policy.35').write_bytes(b'different actual policy')
        self.alias_refused('actual boot policy')

    def test_alias_cannot_hide_a_linked_configured_module(self):
        self.alias_fixture()
        module = self.real/'active/modules/100/example/cil'
        module.unlink()
        module.symlink_to(self.real/'policy/policy.35')
        self.alias_refused('unexpected symlink')

    def test_dangling_alias_is_refused_without_deletion(self):
        self.alias_fixture()
        shutil.rmtree(self.real.parent)
        self.alias_refused('No such file')

    def test_alias_without_module_inputs_is_refused(self):
        self.alias_fixture()
        shutil.rmtree(self.real/'active/modules')
        self.alias_refused('no verified module inputs')

    def test_alias_requires_exact_vendor_creator_rule(self):
        self.alias_fixture()
        for content in ('', 'L /var/lib/selinux - - - - /etc/selinux\n',
                        'L /var/lib/selinux - - - - ../../etc/selinux\n'
                        'p /var/lib/selinux - - - -\n'):
            with self.subTest(content=content):
                self.authority.write_text(content)
                self.alias_refused('no exact vendor tmpfiles authority')

    def test_alias_requires_existing_vendor_authority(self):
        self.alias_fixture()
        self.authority.unlink()
        self.alias_refused('No such file')

    def test_alias_rejects_writable_or_special_authority_before_reading(self):
        self.alias_fixture()
        self.authority.chmod(0o666)
        self.alias_refused('unsafe SELinux compatibility tmpfiles')
        self.authority.unlink()
        os.mkfifo(self.authority)
        self.alias_refused('unsafe SELinux compatibility tmpfiles')

    def test_alias_rejects_symlinked_authority(self):
        self.alias_fixture()
        self.authority.unlink()
        self.authority.symlink_to(self.real/'policy/policy.35')
        self.alias_refused('unexpected symlink')

    def test_alias_rejects_unowned_link(self):
        from unittest.mock import patch
        self.alias_fixture()
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == self.old.parent:
                fields = list(info)
                fields[4] += 1
                return os.stat_result(fields)
            return info
        with patch.object(Path, 'lstat', lstat):
            self.alias_refused('unrecognized SELinux')

    def test_alias_rejects_mounted_policy_inputs(self):
        from unittest.mock import patch
        self.alias_fixture()
        original = Path.is_mount
        def mounted(path):
            return path == self.real/'active/modules' or original(path)
        with patch.object(Path, 'is_mount', mounted):
            self.alias_refused('unsafe owner or mount')

    def test_alias_refuses_populated_package_state_before_unlinking(self):
        self.alias_fixture()
        (self.root/'var/lib/hp/owner-data').write_bytes(b'keep')
        self.alias_refused('not an empty owned')
        self.assertEqual((self.root/'var/lib/hp/owner-data').read_bytes(), b'keep')

    def test_alias_does_not_relax_parent_link_guard(self):
        self.alias_fixture()
        parent = self.root/'var/lib'
        parent.rename(self.root/'var/saved')
        parent.symlink_to('saved')
        self.alias_refused('unexpected symlink')


if __name__ == '__main__':
    unittest.main()
