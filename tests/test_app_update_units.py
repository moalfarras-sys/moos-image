#!/usr/bin/env python3
"""Missing ARM update bases and private native systemctl wiring controls."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('app_update_gate', ROOT / 'build_files/verify_app_updates.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class AppUpdateUnits(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='moos-app-update-units-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        helper = self.root / 'usr/libexec/moos-flatpak-update'
        helper.parent.mkdir(parents=True)
        shutil.copy2(ROOT / 'system_files/usr/libexec/moos-flatpak-update', helper)
        providers = self.root / 'usr/bin'
        providers.mkdir()
        for name in ('flatpak', 'busctl', 'bash'):
            provider = providers / name
            provider.write_text('#!/bin/sh\nexit 0\n')
            provider.chmod(0o755)
        for scope in ('system', 'user'):
            directory = self.directory(scope)
            directory.mkdir(parents=True)
            (directory / 'timers.target').write_text('[Unit]\nDescription=Private timers\n')
            name = f'flatpak-{scope}-update'
            for suffix in ('service', 'timer'):
                filename = name + '.' + suffix
                shutil.copy2(ROOT / 'system_files/usr/lib/systemd' / scope / filename,
                             directory / filename)
                shutil.copytree(ROOT / 'system_files/usr/lib/systemd' / scope / (filename + '.d'),
                                directory / (filename + '.d'))
            self.enable(scope)

    def directory(self, scope):
        return self.root / 'usr/lib/systemd' / scope

    def want(self, scope):
        return self.root / 'etc/systemd' / scope / 'timers.target.wants' / f'flatpak-{scope}-update.timer'

    def enable(self, scope):
        command = ['systemctl', '--root=' + str(self.root)]
        if scope == 'user':
            command += ['--global']
        return subprocess.run(command + ['enable', f'flatpak-{scope}-update.timer'],
                              capture_output=True, text=True, check=True, timeout=15)

    def dropin(self, scope, suffix, content):
        path = self.directory(scope) / f'flatpak-{scope}-update.{suffix}.d/zz-negative.conf'
        path.write_text(content)

    def refused(self):
        with self.assertRaises((OSError, RuntimeError, ValueError)):
            policy.verify(self.root)

    def test_both_real_enable_commands_create_the_wants(self):
        for scope in ('system', 'user'):
            self.assertTrue(self.want(scope).is_symlink())
        policy.verify(self.root)

    def test_old_arm_dropins_without_base_units_are_refused(self):
        for scope in ('system', 'user'):
            for suffix in ('service', 'timer'):
                (self.directory(scope) / f'flatpak-{scope}-update.{suffix}').unlink()
        self.refused()

    def test_missing_service_is_refused_for_either_scope(self):
        for scope in ('system', 'user'):
            with self.subTest(scope=scope):
                unit = self.directory(scope) / f'flatpak-{scope}-update.service'
                original = unit.read_bytes()
                unit.unlink()
                self.refused()
                unit.write_bytes(original)

    def test_disabled_timer_is_refused_for_either_scope(self):
        for scope in ('system', 'user'):
            with self.subTest(scope=scope):
                self.want(scope).unlink()
                self.refused()
                self.enable(scope)

    def test_masked_base_is_refused(self):
        unit = self.root / 'etc/systemd/user/flatpak-user-update.service'
        unit.symlink_to('/dev/null')
        self.refused()

    def test_a_want_for_another_timer_is_refused(self):
        self.want('user').unlink()
        self.want('user').symlink_to('/usr/lib/systemd/system/flatpak-system-update.timer')
        self.refused()

    def test_enable_without_install_can_succeed_without_wiring(self):
        unit = self.directory('user') / 'flatpak-user-update.timer'
        unit.write_text(unit.read_text().split('[Install]')[0])
        self.want('user').unlink()
        self.enable('user')
        self.assertFalse(self.want('user').is_symlink())
        self.refused()

    def test_missing_executable_is_refused(self):
        (self.root / 'usr/libexec/moos-flatpak-update').chmod(0o644)
        self.refused()

    def test_missing_runtime_provider_is_refused(self):
        (self.root / 'usr/bin/flatpak').unlink()
        self.refused()

    def test_both_builders_enable_and_verify_the_finished_units(self):
        for name in ('build.sh', 'build-arm.sh'):
            text = (ROOT / 'build_files' / name).read_text()
            self.assertIn('systemctl enable flatpak-system-update.timer', text)
            self.assertIn('systemctl --global enable flatpak-user-update.timer', text)
            self.assertIn('python3 /ctx/verify_app_updates.py --root /', text)

    def test_unreviewed_executor_is_refused(self):
        self.dropin('user', 'service', '[Service]\nExecStart=\nExecStart=/bin/true\n')
        self.refused()

    def test_reset_cannot_silently_remove_daily_updates(self):
        self.dropin('user', 'timer', '[Timer]\nOnBootSec=\nOnBootSec=25min\n')
        self.refused()

    def test_appended_early_boot_trigger_is_refused(self):
        self.dropin('system', 'timer', '[Timer]\nOnBootSec=2min\n')
        self.refused()

    def test_background_priority_is_required(self):
        self.dropin('system', 'service', '[Service]\nCPUSchedulingPolicy=other\n')
        self.refused()

    def test_system_catchup_at_boot_is_refused(self):
        self.dropin('system', 'timer', '[Timer]\nPersistent=true\n')
        self.refused()

    def test_metered_network_guard_is_required(self):
        self.dropin('user', 'service', '[Service]\nExecCondition=\n')
        self.refused()

    def test_actual_fallback_metered_conditions_fail_closed(self):
        binary = self.root / 'bin/busctl'
        binary.parent.mkdir()
        binary.write_text('#!/bin/sh\nprintf "%s\\n" "$MOOS_TEST_METERED"\nexit "$MOOS_TEST_BUS_EXIT"\n')
        binary.chmod(0o755)
        env = {'PATH': str(binary.parent) + ':/usr/bin:/bin', 'HOME': str(self.root),
               'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/nonexistent-moos-test-bus'}
        for scope in ('system', 'user'):
            values = policy.configuration(self.root, scope, f'flatpak-{scope}-update.service')
            argv = shlex.split(values[('Service', 'ExecCondition')][0])
            for result, status, accepted in [('u 2', 0, True), ('u 4', 0, True),
                                             ('u 0', 0, False), ('u 1', 0, False),
                                             ('u 3', 0, False), ('', 0, False),
                                             ('s "2"', 0, False), ('u 2', 1, False)]:
                with self.subTest(scope=scope, result=result, status=status):
                    p = subprocess.run(argv, env=env | {'MOOS_TEST_METERED': result,
                            'MOOS_TEST_BUS_EXIT': str(status)}, capture_output=True, timeout=3)
                    self.assertEqual(p.returncode == 0, accepted)


if __name__ == '__main__':
    unittest.main()
