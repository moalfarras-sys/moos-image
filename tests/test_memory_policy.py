#!/usr/bin/env python3
"""Positive image fixture and absent, inert, linked and changed vendor controls."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('memory_policy', ROOT / 'build_files/verify_memory_policy.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MemoryPolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for relative, (section, values) in module.POLICIES.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'[{section}]\n' + ''.join(f'{k}={v}\n' for k, v in values.items()))
        for relative in ('usr/lib/systemd/systemd-oomd', 'usr/lib/systemd/system/systemd-oomd.service'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        helper = self.root / 'usr/libexec/moos-memory-policy-check'
        helper.parent.mkdir(parents=True, exist_ok=True)
        helper.write_text('#!/usr/bin/bash\n')
        helper.chmod(0o755)
        source = self.root / module.SYSCTL_POLICY
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text((ROOT / 'system_files' / module.SYSCTL_POLICY).read_text())
        alias = self.root / module.SYSCTL_ALIAS
        alias.parent.mkdir(parents=True, exist_ok=True)
        alias.symlink_to(module.SYSCTL_LINK)

    def test_reviewed_vendor_defaults(self):
        module.verify(self.root)

    def test_shipped_bridge_keeps_one_policy(self):
        module.verify_sysctl_bridge(ROOT / 'system_files')

    def test_vendor_only_cannot_survive_tuned_reapplication(self):
        (self.root / module.SYSCTL_ALIAS).unlink()
        with self.assertRaisesRegex(RuntimeError, 'canonical TuneD sysctl alias'):
            module.verify(self.root)

    def test_copied_policy_is_not_a_canonical_bridge(self):
        alias = self.root / module.SYSCTL_ALIAS
        policy = alias.read_text()
        alias.unlink()
        alias.write_text(policy)
        with self.assertRaisesRegex(RuntimeError, 'canonical TuneD sysctl alias'):
            module.verify(self.root)

    def test_unknown_bridge_target_is_refused(self):
        alias = self.root / module.SYSCTL_ALIAS
        alias.unlink()
        alias.symlink_to('/etc/sysctl.conf')
        with self.assertRaisesRegex(RuntimeError, 'canonical TuneD sysctl alias'):
            module.verify(self.root)

    def test_vendor_policy_cannot_be_a_second_alias(self):
        source = self.root / module.SYSCTL_POLICY
        saved = source.with_suffix('.saved')
        source.rename(saved)
        source.symlink_to(saved.name)
        with self.assertRaisesRegex(RuntimeError, 'regular canonical desktop'):
            module.verify(self.root)

    def test_edition_without_tuned_needs_no_new_power_daemon(self):
        with patch.object(module, 'probe_native_tuned', side_effect=AssertionError('unexpected provider')):
            self.assertIsNone(module.verify_native_tuned(self.root))

    def test_installed_tuned_cannot_silently_skip_a_missing_parser(self):
        authority = self.root / 'usr/lib/systemd/system/tuned.service'
        authority.write_text('[Service]\nExecStart=/usr/sbin/tuned\n')
        with patch.object(module, 'probe_native_tuned', side_effect=ImportError('missing native provider')):
            with self.assertRaisesRegex(ImportError, 'missing native provider'):
                module.verify_native_tuned(self.root)

    @unittest.skipUnless(importlib.util.find_spec('tuned'),
                         'Native TuneD unavailable; finished-image gate requires its actual parser')
    def test_installed_tuned_parser_and_priority_controls(self):
        results = module.probe_native_tuned((ROOT / 'system_files' / module.SYSCTL_POLICY).read_text())
        self.assertEqual(len(results), 6)

    def test_running_binary_without_policy_is_not_enough(self):
        (self.root / next(iter(module.POLICIES))).unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing regular vendor'):
            module.verify(self.root)

    def test_every_policy_can_refuse_an_inert_daemon(self):
        for relative in list(module.POLICIES)[1:]:
            path = self.root / relative
            original = path.read_text()
            path.write_text(original.replace('Pressure=kill', 'Pressure=auto'))
            with self.assertRaisesRegex(RuntimeError, 'unreviewed vendor'):
                module.verify(self.root)
            path.write_text(original)

    def test_changed_pressure_budget_needs_review(self):
        path = self.root / list(module.POLICIES)[1]
        path.write_text(path.read_text().replace('80%', '10%'))
        with self.assertRaisesRegex(RuntimeError, 'unreviewed vendor'):
            module.verify(self.root)

    def test_missing_executable(self):
        (self.root / 'usr/lib/systemd/systemd-oomd').unlink()
        with self.assertRaisesRegex(RuntimeError, 'missing memory policy runtime'):
            module.verify(self.root)

    def test_unusable_native_readback_is_refused(self):
        (self.root / 'usr/libexec/moos-memory-policy-check').chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, 'missing executable native'):
            module.verify(self.root)

    def test_policy_symlink_is_refused(self):
        path = self.root / next(iter(module.POLICIES))
        saved = self.root / 'saved'
        path.rename(saved)
        path.symlink_to(saved)
        with self.assertRaisesRegex(RuntimeError, 'missing regular vendor'):
            module.verify(self.root)

    def test_both_finished_images_run_gate(self):
        for name in ('build.sh', 'build-arm.sh'):
            text = (ROOT / 'build_files' / name).read_text()
            self.assertIn('python3 /ctx/verify_memory_policy.py --root /', text)
            self.assertGreater(text.index('python3 /ctx/verify_memory_policy.py --root /'),
                               text.rindex('dnf5 clean all'))
        arm = (ROOT / 'build_files/build-arm.sh').read_text()
        self.assertIn('systemd-oomd-defaults', arm.split('_PLASMA=(')[1].split('\n)')[0])


if __name__ == '__main__':
    unittest.main()
