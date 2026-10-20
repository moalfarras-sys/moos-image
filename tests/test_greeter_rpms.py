#!/usr/bin/env python3
"""Reject unreviewed native login packages before any package transaction."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('greeter_rpms', ROOT / 'build_files/plasma_login/rpms.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativePackagePreflight(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='moos-greeter-rpms-')
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.source = module.review('6.8.0-1.fc44')
        self.manifest = copy.deepcopy(self.source)
        self.manifest['packages'] = []
        for name in sorted(module.PACKAGES):
            path = self.folder / (name + '.rpm')
            path.write_bytes(b'private fixture: metadata is supplied by the test')
            self.manifest['packages'].append({'name': name, 'file': path.name, 'sha256': module.sha(path)})

    def command(self, arguments):
        if arguments == ['rpm', '--eval', '%{_arch}']:
            return 'x86_64'
        if arguments[:3] == ['rpm', '-q', '--qf']:
            self.assertIn(arguments[-1], module.PACKAGES)
            return '6.8.0-1.fc44 plasma-login-manager-6.8.0-1.fc44.src.rpm'
        if arguments[:3] == ['rpm', '-qp', '--qf']:
            name = Path(arguments[-1]).stem
            return name + ' 6.8.0-1.1.moos1.fc44 x86_64'
        self.fail('unexpected package inspection: ' + repr(arguments))

    def write(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_reviewed_pair_passes_read_only_preflight(self):
        self.write()
        with patch.object(module, 'command', side_effect=self.command), \
                patch.object(module.subprocess, 'run', side_effect=RuntimeError('no mutation')) as mutation:
            data, selected = module.validate_manifest(self.folder)
        mutation.assert_not_called()
        self.assertEqual(data, self.source)
        self.assertEqual({Path(p).name for p in selected}, {p['file'] for p in self.manifest['packages']})

    def refused(self, inspect=None):
        self.write()
        with patch.object(module, 'command', side_effect=inspect or self.command), \
                patch.object(module.subprocess, 'run', side_effect=RuntimeError('no mutation')) as mutation:
            with self.assertRaises((AssertionError, KeyError, ValueError, FileNotFoundError)):
                module.install(self.folder)
        mutation.assert_not_called()

    def test_manifest_source_drift_is_refused_before_dnf(self):
        original = copy.deepcopy(self.manifest)
        for key, value in [('base', '6.8.1-1.fc44'), ('fixed', 'unreviewed'),
                           ('source_sha256', '0' * 64), ('source_signer', '0' * 40),
                           ('authentication_source_sha256', '0' * 64), ('arch', 'aarch64')]:
            with self.subTest(key=key):
                self.manifest = copy.deepcopy(original)
                self.manifest[key] = value
                self.refused()

    def test_missing_duplicate_and_extra_packages_are_refused_before_dnf(self):
        original = copy.deepcopy(self.manifest)
        for packages in [original['packages'][:1], original['packages'] * 2,
                         original['packages'] + [{'name': 'kernel', 'file': 'kernel.rpm', 'sha256': '0' * 64}]]:
            with self.subTest(packages=packages):
                self.manifest = copy.deepcopy(original)
                self.manifest['packages'] = packages
                self.refused()

    def test_replaced_rpm_path_and_symlink_are_refused_before_dnf(self):
        original = copy.deepcopy(self.manifest)
        for filename in ('../outside.rpm', '/outside.rpm', 'subdir/../package.rpm'):
            with self.subTest(filename=filename):
                self.manifest = copy.deepcopy(original)
                self.manifest['packages'][0]['file'] = filename
                self.refused()
        self.manifest = copy.deepcopy(original)
        target = self.folder / self.manifest['packages'][0]['file']
        target.write_bytes(b'replaced')
        self.refused()
        target.unlink()
        target.symlink_to(self.folder / self.manifest['packages'][1]['file'])
        self.refused()

    def test_actual_rpm_metadata_and_installed_origin_must_match_review(self):
        for wrong in ('newer-installed-base', 'different-source-rpm', 'wrong-package-nvr', 'wrong-architecture'):
            def inspect(arguments):
                value = self.command(arguments)
                if arguments[:2] == ['rpm', '-q']:
                    if wrong == 'newer-installed-base':
                        return value.replace('6.8.0', '6.8.1')
                    if wrong == 'different-source-rpm':
                        return value.replace('plasma-login-manager-6.8.0-1.fc44.src.rpm', 'other.src.rpm')
                if arguments[:2] == ['rpm', '-qp']:
                    if wrong == 'wrong-package-nvr':
                        return value.replace('1.1.moos1', '1')
                    if wrong == 'wrong-architecture':
                        return value.replace('x86_64', 'aarch64')
                return value
            with self.subTest(wrong=wrong):
                self.refused(inspect)


if __name__ == '__main__':
    unittest.main()
