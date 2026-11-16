#!/usr/bin/env python3
"""Private package fixtures: unknown upstream, damaged payloads and gaps fail closed."""
import contextlib
import hashlib
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
source_spec = importlib.util.spec_from_file_location('tray_source', ROOT / 'build_files/plasma_logout/prepare_control_center.py')
tray_source = importlib.util.module_from_spec(source_spec)
source_spec.loader.exec_module(tray_source)


class NativePackageBoundary(unittest.TestCase):
    base = '6.7.5-1.fc44'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / 'packages'
        self.folder.mkdir()
        self.owned = set(rpms.CORE)
        self.installed = False
        self.review = rpms.source_review(self.base)
        self.fixed = self.review['fixed']
        self.current = self.base
        self.worker = self.root / 'usr/bin/plasma-shutdown'
        self.worker.parent.mkdir(parents=True)
        self.worker.write_bytes(b'private native worker fixture')
        self.activation = self.root / 'usr/share/dbus-1/services/org.kde.Shutdown.service'
        self.activation.parent.mkdir(parents=True)
        self.activation.write_text('[D-BUS Service]\nName=org.kde.Shutdown\nExec=/usr/bin/plasma-shutdown\n')
        self.manifest = {'schema': 1, 'base': self.base, 'fixed': self.fixed,
                         'arch': 'x86_64', 'source_sha256': self.review['source_sha256'], 'packages': []}
        self.tray = self.root / rpms.TRAY
        self.tray.parent.mkdir(parents=True)
        self.tray.write_bytes(b'private native tray plugin fixture')
        self.center_source = self.root / 'native-tray-source.json'
        if 'control_center' in self.review:
            proof = {'enabled': True, 'base': self.base,
                     'upstream_sha256': self.review['control_center']['upstream_sha256'],
                     'qml_sha256': {name: hashlib.sha256(name.encode()).hexdigest() for name in rpms.TRAY_QML},
                     'cmake_sha256': 'a' * 64}
            self.manifest['control_center_source'] = proof
            self.center_source.write_text(json.dumps(proof))
        receipt_patch = patch.object(rpms, 'TRAY_SOURCE_RECEIPT', self.center_source)
        receipt_patch.start(); self.addCleanup(receipt_patch.stop)
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
            if argv[3] == 'plasma-workspace':
                return f'/usr/bin/plasma-shutdown 20 0 {rpms.sha(self.worker)} 0100755 root root 0 0 0 X'
            self.assertEqual(argv[3], 'plasma-workspace-libs')
            return f'/{rpms.TRAY} 20 0 {rpms.sha(self.tray)} 0100755 root root 0 0 0 X'
        if argv[:3] == ['rpm', '-q', '--qf']:
            if argv[3] == '%{SOURCERPM}':
                return f'plasma-workspace-{self.base}.src.rpm'
            return self.fixed if self.installed else self.current
        raise AssertionError(argv)

    def metadata(self, path):
        return [path.stem, self.fixed, 'x86_64']

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

    def test_other_stable_and_beta_nvrs_remain_unreviewed(self):
        for base in ('6.8.0-2.fc44', '6.8.4-1.fc44', '6.7.90-1.fc44', '6.7.91-2.fc44'):
            with self.assertRaisesRegex(AssertionError, 'unreviewed Plasma source NVR'):
                rpms.source_review(base)


class NextNativePackageBoundary(NativePackageBoundary):
    base = '6.7.91-1.fc44'


class StableNativePackageBoundary(NativePackageBoundary):
    base = '6.8.0-1.fc44'


class Stable681NativePackageBoundary(NativePackageBoundary):
    base = '6.8.1-1.fc44'


class Stable682NativePackageBoundary(NativePackageBoundary):
    base = '6.8.2-1.fc44'


class Stable683NativePackageBoundary(NativePackageBoundary):
    base = '6.8.3-1.fc44'

    def test_missing_native_tray_source_proof_is_refused(self):
        del self.manifest['control_center_source']
        self.rejected()

    def test_changed_native_tray_upstream_identity_is_refused(self):
        self.manifest['control_center_source']['upstream_sha256'] = {'main.qml': '0' * 64}
        self.rejected()

    def test_tray_plugin_change_after_transaction_is_refused(self):
        self.install()
        self.tray.write_bytes(b'changed native tray bytes')
        with self.assertRaisesRegex(AssertionError, 'tray plugin changed'):
            rpms.verify(self.root)

    def test_native_rpm_must_own_the_delivered_tray_bytes(self):
        self.install()
        original = self.command
        def changed_dump(argv):
            if argv == ['rpm', '-q', '--dump', 'plasma-workspace-libs']:
                return f'/{rpms.TRAY} 20 0 ' + '0' * 64 + ' 0100755 root root 0 0 0 X'
            return original(argv)
        with patch.object(rpms, 'command', changed_dump):
            with self.assertRaisesRegex(AssertionError, 'tray plugin differs'):
                rpms.verify(self.root)


class NativeTraySourceAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = self.root / 'tree/applets/systemtray'
        self.qml = self.native / 'qml'
        self.qml.mkdir(parents=True)
        self.payload = self.root / 'payload'
        self.payload.mkdir()
        for name in tray_source.REPLACED:
            (self.qml / name).write_text('native original ' + name)
        self.cmake = self.native / 'CMakeLists.txt'
        self.cmake.write_text('native parent flags\n    RESOURCES\n        main.xml\n')
        for name in tray_source.REPLACED | tray_source.ADDED:
            (self.payload / name).write_text('MoOS source ' + name)
        self.review = {'base': '6.8.3-1.fc44', 'control_center': {
            'upstream_sha256': {name: rpms.sha(self.qml / name) for name in tray_source.REPLACED},
            'cmake_sha256': rpms.sha(self.cmake)}}
        self.original = self.snapshot()

    def snapshot(self):
        return {str(p.relative_to(self.native)): p.read_bytes() for p in self.native.rglob('*') if p.is_file()}

    def prepare(self):
        return tray_source.prepare(self.root / 'tree', self.payload, self.review)

    def refused_without_writes(self, message):
        before = self.snapshot()
        with self.assertRaisesRegex(AssertionError, message):
            self.prepare()
        self.assertEqual(self.snapshot(), before)

    def test_exact_native_inputs_replace_only_the_reviewed_two_and_add_qrc_members(self):
        (self.qml / 'PlasmoidPopupsContainer.qml').write_text('native lifetime owner')
        proof = self.prepare()
        rpms.validate_center_source(self.review, proof)
        self.assertEqual((self.qml / 'PlasmoidPopupsContainer.qml').read_text(), 'native lifetime owner')
        for name in tray_source.REPLACED | tray_source.ADDED:
            self.assertEqual((self.qml / name).read_bytes(), (self.payload / name).read_bytes())
        text = self.cmake.read_text()
        self.assertIn('native parent flags', text)
        for name in tray_source.ADDED:
            self.assertEqual(text.count('        qml/' + name + '\n'), 1)

    def test_changed_native_source_refuses_before_any_mutation(self):
        (self.qml / 'main.qml').write_text('unknown native change')
        self.refused_without_writes('unreviewed native tray source')

    def test_changed_native_parent_refuses_before_any_mutation(self):
        self.cmake.write_text(self.cmake.read_text() + 'unknown native change')
        self.refused_without_writes('unreviewed native tray CMake')

    def test_unknown_base_never_receives_a_known_version_patch(self):
        self.review['base'] = '6.8.4-1.fc44'
        self.refused_without_writes('unreviewed native tray version')

    def test_missing_and_extra_payload_refuse_before_any_mutation(self):
        (self.payload / 'main.qml').unlink()
        self.refused_without_writes('unexpected or missing')
        (self.payload / 'main.qml').write_text('MoOS source')
        (self.payload / 'unknown.qml').write_text('unknown source')
        self.refused_without_writes('unexpected or missing')

    def test_native_collision_and_payload_symlink_are_refused(self):
        name = next(iter(tray_source.ADDED))
        (self.qml / name).write_text('native source owns this name')
        self.refused_without_writes('source collision')
        (self.qml / name).unlink()
        (self.payload / name).unlink()
        (self.payload / name).symlink_to(self.qml / 'main.qml')
        self.refused_without_writes('unsafe MoOS')

    def test_explicit_older_logout_reviews_keep_their_native_tray(self):
        for base in ('6.7.5-1.fc44', '6.7.91-1.fc44', '6.8.0-1.fc44', '6.8.1-1.fc44', '6.8.2-1.fc44'):
            record = tray_source.prepare(self.root / 'tree', self.payload, rpms.source_review(base))
            self.assertIs(record['enabled'], False)
            self.assertEqual(self.snapshot(), self.original)

    def test_both_architecture_recipes_admit_source_inside_the_original_build(self):
        build = (ROOT / 'build_files/plasma_logout/build.sh').read_text()
        self.assertIn("review['fixed'].split('-', 1)[1]", build)
        self.assertIn('python3 /src/prepare_control_center.py "$PWD"', build)
        self.assertLess(build.index('prepared_shutdown_sha256'), build.index('python3 /src/prepare_control_center.py'))
        for name in ('Containerfile', 'Containerfile.arm'):
            recipe = (ROOT / name).read_text()
            self.assertEqual(recipe.count('COPY build_files/plasma_logout/control-center/ /src/control-center/'), 1)
            self.assertLess(recipe.index('COPY build_files/plasma_logout/control-center/ /src/control-center/'), recipe.index('RUN bash /src/build.sh prepare'))


if __name__ == '__main__':
    unittest.main()
