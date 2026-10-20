#!/usr/bin/env python3
"""Vendor-empty scaffolds may retire; credentials and unknown state must survive."""
import os
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build_files'))
from finalize_root_home import finalize, RULES, KONFLUX, PROVISION, SCAFFOLDS, REVIEWED_KONFLUX_SHA256


class RootHome(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root/'var/roothome'
        self.home.mkdir(parents=True, mode=0o700)
        (self.root/'root').symlink_to('var/roothome')
        for name, (mode, _) in SCAFFOLDS.items():
            path = self.home/name
            if mode & 0o170000 == 0o040000:
                path.mkdir(mode=mode & 0o777)
            else:
                path.touch(mode=mode & 0o777)
        for name, rules in RULES.items():
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# Native vendor authority\n'+'\n'.join(rules)+'\n')
        self.authorities = {name:(self.root/name).read_bytes() for name in RULES}

    def refused(self, text):
        paths = {str(p.relative_to(self.home)) for p in self.home.rglob('*')}
        with self.assertRaisesRegex((RuntimeError, OSError), text):
            finalize(self.root)
        self.assertTrue(self.home.exists())
        self.assertEqual({str(p.relative_to(self.home)) for p in self.home.rglob('*')}, paths)

    def test_empty_vendor_scaffolds_retire_with_authorities_unchanged(self):
        sentinel = self.root/'preserved';sentinel.write_bytes(b'not compose state')
        finalize(self.root)
        self.assertFalse(self.home.exists())
        self.assertTrue((self.root/'root').is_symlink())
        self.assertEqual(sentinel.read_bytes(), b'not compose state')
        self.assertEqual({name:(self.root/name).read_bytes() for name in RULES}, self.authorities)

    def test_absent_or_empty_home_needs_no_child_authorities(self):
        shutil.rmtree(self.home)
        shutil.rmtree(self.root/'usr')
        finalize(self.root)
        self.home.mkdir(mode=0o700)
        finalize(self.root)
        self.assertFalse(self.home.exists())

    def test_even_empty_authorized_keys_is_never_removed(self):
        for contents in (b'', b'ssh-ed25519 owner-credential'):
            with self.subTest(empty=not contents):
                key = self.home/'.ssh/authorized_keys';key.write_bytes(contents)
                self.refused('unexpected root-home compose state')
                self.assertEqual(key.read_bytes(), contents)

    def test_unknown_root_payload_is_never_removed(self):
        (self.home/'owner-notes').write_bytes(b'keep')
        self.refused('unexpected root-home compose state')
        self.assertEqual((self.home/'owner-notes').read_bytes(), b'keep')

    def test_populated_vendor_json_is_never_removed(self):
        (self.home/'buildinfo/labels.json').write_bytes(b'{"vendor":"metadata"}')
        self.refused('not empty owned vendor state')

    def test_linked_scaffold_never_follows_target(self):
        target = self.root/'outside';target.write_bytes(b'keep outside')
        path = self.home/'buildinfo/labels.json';path.unlink();path.symlink_to(target)
        self.refused('unexpected symlink')
        self.assertEqual(target.read_bytes(), b'keep outside')

    def test_root_alias_drift_is_refused(self):
        alias = self.root/'root';alias.unlink();alias.symlink_to('/var/roothome')
        self.refused('reviewed bootc alias')

    def test_linked_root_home_is_refused(self):
        self.home.rename(self.root/'saved-home');self.home.symlink_to('../saved-home')
        self.refused('unexpected symlink')

    def test_wrong_mode_is_refused_before_any_deletion(self):
        (self.home/'.ssh').chmod(0o755)
        self.refused('not empty owned vendor state')

    def test_wrong_owner_is_refused_before_any_deletion(self):
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            info = original(path, *args, **kwargs)
            if path == self.home/'buildinfo/labels.json':
                fields = list(info);fields[4] += 1;return os.stat_result(fields)
            return info
        with patch.object(Path, 'lstat', lstat):
            self.refused('not empty owned vendor state')

    def test_mount_is_refused_before_directory_traversal(self):
        original = Path.is_mount
        def mounted(path):return path == self.home/'.ssh' or original(path)
        with patch.object(Path, 'is_mount', mounted):
            self.refused('not empty owned vendor state')

    def test_missing_authority_is_refused(self):
        (self.root/PROVISION).unlink()
        self.refused('No such file')

    def test_changed_or_extended_vendor_rules_are_refused(self):
        for name in (KONFLUX, PROVISION):
            with self.subTest(authority=name):
                path = self.root/name
                path.write_bytes(self.authorities[name]+b'f /var/roothome/new-state 0644 - - -\n')
                self.refused('authority drifted')
                path.write_bytes(self.authorities[name])

    def test_symlinked_authority_is_refused(self):
        path = self.root/KONFLUX;path.unlink();path.symlink_to(self.root/PROVISION)
        self.refused('unexpected symlink')

    def test_writable_or_fifo_authority_is_refused_before_read(self):
        path = self.root/KONFLUX;path.chmod(0o666)
        self.refused('unsafe root-home tmpfiles')
        path.unlink();os.mkfifo(path)
        self.refused('unsafe root-home tmpfiles')

    def test_native_root_group_writable_authority_requires_exact_reviewed_bytes(self):
        path = self.root/KONFLUX;path.chmod(0o664)
        self.refused('unreviewed root-group-writable')
        data = (b'# Workaround for https://github.com/konflux-ci/build-tasks-dockerfiles/pull/243\n'
                b'd /var/roothome/buildinfo 0755 - - -\n'
                b'd /var/roothome/buildinfo/content_manifests 0755 - - -\n'
                b"# Note we don't actually try to recreate the content; this just makes the linter ignore it\n"
                b'f /var/roothome/buildinfo/content_manifests/content-sets.json 0644 - - -\n'
                b'f /var/roothome/buildinfo/labels.json 0644 - - -\n')
        self.assertEqual(hashlib.sha256(data).hexdigest(), REVIEWED_KONFLUX_SHA256)
        path.write_bytes(data)
        finalize(self.root)
        self.assertFalse(self.home.exists())
        self.assertEqual(path.read_bytes(), data)
        self.assertEqual(path.stat().st_mode & 0o777, 0o664)


if __name__ == '__main__':
    unittest.main()
