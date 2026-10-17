#!/usr/bin/env python3
"""Exercise the canonical launch boundary without a desktop or owner bus.

Real systemd lifetime and native Windows controls are recorded separately;
these controls refuse manager failures instead of publishing a false Opened.
"""
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
LOADER = importlib.machinery.SourceFileLoader('managed_launch_store', str(ROOT / 'system_files/usr/bin/moos-storectl'))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
STORE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = STORE
LOADER.exec_module(STORE)


class StoreLaunch(unittest.TestCase):
    def test_app_argv_remains_data_at_the_one_launch_boundary(self):
        arguments = ['/usr/bin/gtk-launch', 'org.example.App.desktop', 'literal;$(not-a-command)']
        with mock.patch.object(STORE.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, stderr='')) as execute:
            STORE.CommandRunner().spawn(arguments)
        self.assertEqual(execute.call_args.args[0], ['/usr/bin/moai-open', '--app', *arguments])
        self.assertFalse(execute.call_args.kwargs.get('shell', False))

    def test_a_manager_refusal_cannot_become_opened(self):
        with mock.patch.object(STORE.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, stderr='fixture manager refused')), \
                contextlib.redirect_stderr(io.StringIO()) as diagnostic:
            with self.assertRaises(STORE.StoreError) as failure:
                STORE.CommandRunner().spawn(['/usr/bin/gtk-launch', 'org.example.App.desktop'])
        self.assertIn('تعذّر فتح التطبيق', str(failure.exception))
        self.assertIn('fixture manager refused', diagnostic.getvalue())

    def test_missing_or_timed_out_helper_does_not_fall_back_to_an_unowned_child(self):
        for error in (FileNotFoundError('fixture missing'), subprocess.TimeoutExpired('fixture', 15)):
            with self.subTest(error=type(error).__name__), \
                    mock.patch.object(STORE.subprocess, 'run', side_effect=error), \
                    mock.patch.object(STORE.subprocess, 'Popen') as detached:
                with self.assertRaises(STORE.StoreError):
                    STORE.CommandRunner().spawn(['/usr/bin/gtk-launch', 'org.example.App.desktop'])
                detached.assert_not_called()


def executable(path, body):
    path.write_text(body)
    path.chmod(0o755)


class CanonicalHelper(unittest.TestCase):
    def invoke(self, *, mode=True, refused=False, compositor=True):
        with tempfile.TemporaryDirectory(prefix='moos-launch-contract-') as raw:
            directory = Path(raw)
            binary = directory / 'bin'
            binary.mkdir()
            resolver = binary / 'resolver'
            executable(resolver, '#!/bin/sh\n' + ('echo wayland-fixture\n' if compositor else 'exit 1\n'))
            executable(binary / 'systemctl', '#!/bin/sh\nexit 0\n')
            executable(binary / 'systemd-run', '''#!/usr/bin/python3
import json,os,pathlib,sys
pathlib.Path(os.environ['LAUNCH_CALL']).write_text(json.dumps(sys.argv[1:]))
if os.environ['LAUNCH_REFUSED']=='1':
 print('fixture manager refusal',file=sys.stderr)
 sys.exit(1)
''')
            executable(binary / 'setsid', '#!/bin/sh\nprintf called > "$LAUNCH_FALLBACK"\nexit 0\n')
            helper = directory / 'moai-open'
            helper.write_text((ROOT / 'system_files/usr/bin/moai-open').read_text().replace(
                '/usr/libexec/moos-wayland-display', str(resolver)))
            environment = {
                **os.environ, 'PATH': str(binary) + ':/usr/bin:/bin', 'HOME': raw,
                'XDG_RUNTIME_DIR': raw, 'XDG_CONFIG_HOME': raw, 'XDG_DATA_HOME': raw,
                'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + raw + '/no-owner-bus',
                'DISPLAY': ':fixture', 'XAUTHORITY': raw + '/fixture-auth',
                'LAUNCH_CALL': raw + '/call.json', 'LAUNCH_FALLBACK': raw + '/fallback',
                'LAUNCH_REFUSED': '1' if refused else '0',
            }
            args = ['bash', str(helper), *(['--app'] if mode else []), '/usr/bin/gtk-launch', 'org.example.App.desktop']
            result = subprocess.run(args, env=environment, capture_output=True, text=True, timeout=5)
            call = json.loads((directory / 'call.json').read_text())
            return result, call, (directory / 'fallback').exists()

    def test_forking_launchers_keep_their_children_in_a_graphical_app_group(self):
        result, call, fallback = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--property=ExitType=cgroup', call)
        self.assertIn('--property=PartOf=graphical-session.target', call)
        self.assertIn('--service-type=exec', call)
        self.assertEqual(call[-3:], ['--', '/usr/bin/gtk-launch', 'org.example.App.desktop'])
        self.assertFalse(fallback)

    def test_app_mode_refuses_failed_manager_without_claiming_a_sets_id_launch(self):
        result, _, fallback = self.invoke(refused=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fixture manager refusal', result.stderr)
        self.assertNotIn('opened', result.stdout)
        self.assertFalse(fallback)

    def test_a_missing_compositor_is_not_an_unbound_shell_variable(self):
        result, call, _ = self.invoke(compositor=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--setenv=WAYLAND_DISPLAY=', call)
        self.assertIn('--setenv=DISPLAY=:fixture', call)

    def test_the_existing_generic_fallback_is_not_given_app_session_policy(self):
        result, call, fallback = self.invoke(mode=False, refused=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(fallback)
        self.assertNotIn('--property=PartOf=graphical-session.target', call)


if __name__ == '__main__':
    unittest.main(verbosity=2)
