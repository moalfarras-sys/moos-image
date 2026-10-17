#!/usr/bin/env python3
"""Basic control painting must not disconnect MoOS apps from Plasma motion."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('platform_gate', ROOT / 'build_files/verify_qml_host_platform.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PlatformContract(unittest.TestCase):
    def test_shared_host_selects_kde_before_loading_any_app(self):
        text = (ROOT / 'build_files/moos-qml-shell.cpp').read_text()
        selection = 'engine.setProperty("_kirigamiTheme", QStringLiteral("org.kde.desktop"));'
        self.assertEqual(text.count(selection), 1)
        self.assertLess(text.index(selection), text.index('engine.load('))
        for name in ('build.sh', 'build-arm.sh'):
            source = (ROOT / 'build_files' / name).read_text()
            self.assertEqual(source.count('python3 /ctx/verify_qml_host_platform.py'), 1)

    def run_gate(self, broken=None):
        seen = []
        def command(argv, **kwargs):
            if argv[0] == 'kwriteconfig6':
                return subprocess.CompletedProcess(argv, 0, '', '')
            env = kwargs['env']
            self.assertEqual(env['QT_QUICK_CONTROLS_STYLE'], 'Basic')
            self.assertEqual(env['QT_QPA_PLATFORM'], 'offscreen')
            self.assertTrue(env['DBUS_SESSION_BUS_ADDRESS'].endswith('/no-bus'))
            duration = (1, 100)[len(seen)]
            seen.append(duration)
            if broken == 'old-basic': duration = 200
            marker = f'qml: MOOS_KDE_MOTION={duration}\n'
            if broken == 'silent': marker = ''
            if broken == 'conflicting': marker += 'qml: MOOS_KDE_MOTION=200\n'
            return subprocess.CompletedProcess(argv, duration, '', marker)
        with patch.object(gate.subprocess, 'run', side_effect=command):
            gate.verify('/private/review-host', ROOT / 'system_files/etc/xdg/kdeglobals')
        return seen

    def test_both_real_settings_are_required(self):
        self.assertEqual(self.run_gate(), [1, 100])

    def test_old_basic_fallback_or_silent_or_conflicting_readback_fails(self):
        for fault in ('old-basic', 'silent', 'conflicting'):
            with self.subTest(fault=fault), self.assertRaises(RuntimeError):
                self.run_gate(fault)


if __name__ == '__main__': unittest.main()
