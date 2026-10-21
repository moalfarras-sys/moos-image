#!/usr/bin/env python3
"""The runtime D-Bus alias may retire; machine identity and unknown data survive."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build_files'))
from finalize_dbus_state import finalize, RULES
from finalize_image_state import finalize as image_finalize


class DBusState(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.base = self.root/'var/lib/dbus';self.base.mkdir(parents=True, mode=0o755)
        self.link = self.base/'machine-id';self.link.symlink_to('/etc/machine-id')
        self.target = self.root/'etc/machine-id';self.target.parent.mkdir();self.target.touch()
        self.authority = self.root/'usr/lib/tmpfiles.d/dbus.conf';self.authority.parent.mkdir(parents=True)
        self.authority.write_text('# Native runtime policy\n'+'\n'.join(' '.join(r) for r in RULES)+'\n')

    def test_same_filesystem_bind_refuses_before_any_enumeration(self):
        base=self.base
        before=set(base.rglob('*'))
        with patch('finalize_dbus_state.mount_points', return_value={base/'private-mounted-child'}), \
                patch.object(Path, 'is_mount', return_value=False), \
                patch.object(Path, 'iterdir', side_effect=AssertionError('traversed mounted tree')):
            with self.assertRaisesRegex(RuntimeError,'mounted'):
                finalize(self.root)
        self.assertEqual(set(base.rglob('*')),before)

    def test_local_tmpfiles_mask_refuses_before_first_delete(self):
        authority=self.authority
        override=self.root/'etc/tmpfiles.d'/authority.name
        override.parent.mkdir(parents=True,exist_ok=True)
        override.symlink_to('/dev/null')
        with patch.object(Path,'unlink',side_effect=AssertionError('deleted before authority validation')), \
                patch.object(Path,'rmdir',side_effect=AssertionError('deleted before authority validation')):
            with self.assertRaisesRegex(RuntimeError,'override'):
                finalize(self.root)

    def refused(self, text):
        with self.assertRaisesRegex((RuntimeError, OSError), text):finalize(self.root)
        self.assertTrue(os.path.lexists(self.link), 'refusal deleted the machine-id entry')

    def test_only_alias_retires_and_unmodified_image_gate_then_passes(self):
        for name in ('etc/flatpak/remotes.d/flathub.flatpakrepo',
                     'usr/lib/systemd/system/moos-flatpak-init.service'):
            p=self.root/name;p.parent.mkdir(parents=True, exist_ok=True);p.write_text('fixture')
        (self.root/'var/tmp').mkdir(mode=0o1777);(self.root/'var/tmp').chmod(0o1777)
        (self.root/'run').mkdir(mode=0o755)
        with self.assertRaisesRegex(RuntimeError, 'expected empty package state directory: var/lib/dbus'):
            image_finalize(self.root)
        original = self.authority.read_bytes()
        finalize(self.root)
        self.assertFalse(os.path.lexists(self.link));self.assertTrue(self.base.is_dir())
        self.assertEqual(self.target.read_bytes(), b'')
        self.assertEqual(self.authority.read_bytes(), original)
        image_finalize(self.root)
        self.assertFalse(self.base.exists())

    def test_missing_or_uninitialized_image_identity_is_preserved(self):
        self.target.write_bytes(b'uninitialized\n');finalize(self.root)
        self.assertEqual(self.target.read_bytes(), b'uninitialized\n')
        self.link.symlink_to('/etc/machine-id');self.target.unlink();finalize(self.root)
        self.assertFalse(self.target.exists())

    def test_unknown_sibling_refuses_before_unlink(self):
        (self.base/'owner-data').write_bytes(b'keep')
        self.refused('unexpected D-Bus compose state')
        self.assertEqual((self.base/'owner-data').read_bytes(), b'keep')

    def test_regular_machine_id_even_empty_is_not_an_alias(self):
        self.link.unlink();self.link.write_bytes(b'')
        self.refused('unrecognized D-Bus machine-id alias')

    def test_changed_target_link_is_refused(self):
        self.link.unlink();self.link.symlink_to('../../../etc/machine-id')
        self.refused('unrecognized D-Bus machine-id alias')

    def test_populated_image_identity_is_preserved_and_refused(self):
        data=b'0123456789abcdef0123456789abcdef\n';self.target.write_bytes(data)
        self.refused('not a pristine image file')
        self.assertEqual(self.target.read_bytes(), data)

    def test_linked_image_target_is_refused_without_following(self):
        self.target.unlink();self.target.symlink_to('/etc/machine-id')
        self.refused('unexpected symlink')

    def test_missing_or_drifted_vendor_authority_refuses(self):
        self.authority.write_text('L /var/lib/dbus/machine-id - - - - /tmp/machine-id\n')
        self.refused('authority drifted')
        self.authority.unlink();self.refused('No such file')

    def test_writable_or_fifo_authority_refuses_before_read(self):
        self.authority.chmod(0o666);self.refused('unsafe D-Bus tmpfiles')
        self.authority.unlink();os.mkfifo(self.authority);self.refused('unsafe D-Bus tmpfiles')

    def test_link_owner_drift_is_refused(self):
        original=Path.lstat
        def lstat(path, *args, **kwargs):
            info=original(path, *args, **kwargs)
            if path==self.link:
                fields=list(info);fields[4]+=1;return os.stat_result(fields)
            return info
        with patch.object(Path,'lstat',lstat):self.refused('unrecognized D-Bus machine-id alias')

    def test_mount_refuses_without_deleting_alias(self):
        original=Path.is_mount
        with patch.object(Path,'is_mount',lambda p:p==self.base or original(p)):
            self.refused('unsafe.*(mount|D-Bus compose directory)')


if __name__ == '__main__':unittest.main()
