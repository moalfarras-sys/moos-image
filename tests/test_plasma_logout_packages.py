#!/usr/bin/env python3
"""Private package fixtures: unknown upstream, damaged payloads and gaps fail closed."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('logout_rpms', ROOT / 'build_files/plasma_logout/rpms.py')
rpms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpms)


class NativePackageBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'packages'
        self.folder.mkdir()
        self.owned = set(rpms.CORE)
        self.installed = False
        self.current = rpms.BASE
        self.worker = self.root / 'usr/bin/plasma-shutdown'
        self.worker.parent.mkdir(parents=True)
        self.worker.write_bytes(b'private native worker fixture')
        self.activation = self.root / 'usr/share/dbus-1/services/org.kde.Shutdown.service'
        self.activation.parent.mkdir(parents=True)
        self.activation.write_text('[D-BUS Service]\nName=org.kde.Shutdown\nExec=/usr/bin/plasma-shutdown\n')
        self.manifest = {'schema': 1, 'base': rpms.BASE, 'fixed': rpms.FIXED,
                         'arch': 'x86_64', 'source_sha256': rpms.SOURCE, 'packages': []}
        for name in sorted(self.owned | {'plasma-workspace-doc'}):
            p = self.folder / (name + '.rpm')
            p.write_bytes(name.encode())
            self.manifest['packages'].append({'name': name, 'file': p.name,
                                              'arch': 'x86_64', 'sha256': rpms.sha(p)})
        self.command_patch = patch.object(rpms, 'command', self.command)
        self.metadata_patch = patch.object(rpms, 'metadata', self.metadata)
        self.run_patch = patch.object(rpms.subprocess, 'run', self.transaction)
        for p in (self.command_patch, self.metadata_patch, self.run_patch):
            p.start(); self.addCleanup(p.stop)

    def command(self, argv):
        if argv == ['rpm', '--eval', '%{_arch}']:
            return 'x86_64'
        if argv[:2] == ['rpm', '-qa']:
            return '\n'.join(sorted(self.owned))
        if argv[:3] == ['rpm', '-q', '--dump']:
            return f'/usr/bin/plasma-shutdown 20 0 {rpms.sha(self.worker)} 0100755 root root 0 0 0 X'
        if argv[:3] == ['rpm', '-q', '--qf']:
            if argv[3] == '%{SOURCERPM}':
                return f'plasma-workspace-{rpms.BASE}.src.rpm'
            return rpms.FIXED if self.installed else self.current
        raise AssertionError(argv)

    def metadata(self, path):
        return [path.stem, rpms.FIXED, 'x86_64']

    def transaction(self, argv, check):
        self.assertTrue(check)
        self.assertEqual(argv[:4], ['dnf5', '-y', 'install', '--setopt=install_weak_deps=False'])
        self.assertEqual(argv[4], '--exclude=kernel,kernel-core,kernel-modules,kernel-modules-core,kernel-modules-extra')
        self.assertEqual({Path(p).stem for p in argv[5:]}, self.owned)
        self.installed = True

    def install(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))
        with contextlib.redirect_stdout(io.StringIO()):
            rpms.install(self.folder, self.root)

    def rejected(self):
        with self.assertRaises(AssertionError):
            self.install()
        self.assertFalse(self.installed, 'a rejected fixture reached the package transaction')

    def test_exact_owned_packages_install_and_final_bytes_verify(self):
        self.install()
        with contextlib.redirect_stdout(io.StringIO()):
            rpms.verify(self.root)

    def test_x86_vendor_install_precedes_the_authoritative_overlay(self):
        recipe = (ROOT / 'Containerfile').read_text().split('FROM base\n', 1)[1]
        install = 'python3 /ctx/plasma_logout/rpms.py install /plasma-logout-rpms'
        self.assertEqual(recipe.count(install), 1)
        self.assertLess(recipe.index(install), recipe.index('COPY system_files/ /'))
        self.assertNotIn(install, (ROOT / 'build_files/build.sh').read_text())

    def test_complete_vendor_split_collects_runtime_and_skips_compilers(self):
        for name in rpms.VENDOR_PACKAGES | {'plasma-workspace-devel', 'libkworkspace6-debuginfo'}:
            (self.folder / (name + '.rpm')).write_bytes(name.encode())
        output = self.root / 'collected'
        output.mkdir()
        rpms.collect(self.folder, output)
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual({p['name'] for p in manifest['packages']}, rpms.VENDOR_PACKAGES)

    def test_unreviewed_vendor_output_is_rejected(self):
        (self.folder / 'unexpected-subpackage.rpm').write_bytes(b'unreviewed')
        output = self.root / 'collected'
        output.mkdir()
        with self.assertRaises(AssertionError):
            rpms.collect(self.folder, output)

    def test_scrubbed_vendor_theme_is_not_in_the_runtime_receipt(self):
        name = 'plasma-lookandfeel-fedora'
        self.owned.add(name)
        p = self.folder / (name + '.rpm')
        p.write_bytes(name.encode())
        self.manifest['packages'].append({'name': name, 'file': p.name,
                                          'arch': 'x86_64', 'sha256': rpms.sha(p)})
        self.install()
        receipt = (self.root / 'usr/share/moos/plasma-logout-transaction.json').read_text()
        self.assertNotIn('fedora', receipt)
        self.assertEqual(set(json.loads(receipt)['packages']), rpms.CORE)

    def test_later_vendor_version_is_never_downgraded(self):
        self.current = '6.7.6-1.fc44'
        self.rejected()

    def test_unreviewed_same_version_release_is_rejected(self):
        self.current = '6.7.5-2.fc44'
        self.rejected()

    def test_missing_owned_subpackage_is_rejected(self):
        self.manifest['packages'] = self.manifest['packages'][1:]
        self.rejected()

    def test_duplicate_owned_subpackage_is_rejected(self):
        self.manifest['packages'].append(self.manifest['packages'][0])
        self.rejected()

    def test_damaged_payload_is_rejected(self):
        (self.folder / 'plasma-workspace.rpm').write_bytes(b'damaged')
        self.rejected()

    def test_libkworkspace_must_move_with_the_worker(self):
        self.manifest['packages'] = [p for p in self.manifest['packages'] if p['name'] != 'libkworkspace6']
        self.rejected()

    def test_same_nvr_from_an_unreviewed_source_is_rejected(self):
        original = self.command
        def changed_source(argv):
            if argv[:4] == ['rpm', '-q', '--qf', '%{SOURCERPM}']:
                return 'unreviewed.src.rpm'
            return original(argv)
        with patch.object(rpms, 'command', changed_source):
            self.rejected()

    def test_wrong_architecture_is_rejected(self):
        self.manifest['arch'] = 'aarch64'
        self.rejected()

    def test_unreviewed_source_is_rejected(self):
        self.manifest['source_sha256'] = '0' * 64
        self.rejected()

    def test_path_escape_is_rejected(self):
        self.manifest['packages'][0]['file'] = '../escaped.rpm'
        self.rejected()

    def test_worker_change_after_transaction_is_rejected(self):
        self.install()
        self.worker.write_bytes(b'changed after install')
        with self.assertRaisesRegex(AssertionError, 'worker changed'):
            rpms.verify(self.root)

    def test_activation_of_a_different_worker_is_rejected(self):
        self.install()
        self.activation.write_text('[D-BUS Service]\nName=org.kde.Shutdown\nExec=/usr/bin/other-worker\n')
        with self.assertRaisesRegex(AssertionError, 'does not launch'):
            rpms.verify(self.root)

    def test_install_receipt_cannot_hide_foreign_rpm_bytes(self):
        self.install()
        original = self.command
        def changed_dump(argv):
            if argv[:3] == ['rpm', '-q', '--dump']:
                return '/usr/bin/plasma-shutdown 20 0 ' + '0' * 64 + ' 0100755 root root 0 0 0 X'
            return original(argv)
        with patch.object(rpms, 'command', changed_dump):
            with self.assertRaisesRegex(AssertionError, 'differs from its native RPM'):
                rpms.verify(self.root)


if __name__ == '__main__':
    unittest.main()
