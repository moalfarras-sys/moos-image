#!/usr/bin/env python3
"""Check the real install invocation; no namespace, disk or firmware is opened."""

from pathlib import Path
import json
import os
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'system_files/usr/bin/moos-install-to-disk').read_text()
MATCH = re.search(r'^run_install\(\) \{\n.*?^\}\n', SOURCE, re.M | re.S)
assert MATCH, 'installer lost run_install'
FUNCTION = MATCH.group(0)
V3_FUNCTION = re.search(r'^v3_splash_target\(\) \{\n.*?^\}\n', SOURCE, re.M | re.S).group(0)
MOUNT_MATCH = re.search(r'^check_prepared_mount\(\) \{\n.*?^\}\n', SOURCE, re.M | re.S)
assert MOUNT_MATCH, 'installer lost target mount readback'
MOUNT_FUNCTION = MOUNT_MATCH.group(0)
assert SOURCE.index('if ! verify_prepared_target; then') < SOURCE.index('attempt_install; rc=$?')


class NamespaceInvocation(unittest.TestCase):
    def test_mount_readback_refuses_missing_foreign_and_ambiguous_layouts(self):
        cases = [
            ('/dev/fixture[/root] btrfs /root', 0, True),
            ('/dev/fixture[/root] btrfs /root', 1, False),
            ('/dev/other[/root] btrfs /root', 0, False),
            ('/dev/fixture ext4 /root', 0, False),
            ('/dev/fixture[/bootc-stage] btrfs /bootc-stage', 0, False),
            ('/dev/fixture[/root] btrfs /root extra', 0, False),
            ('/dev/fixture[/root] btrfs /root\n/dev/other btrfs /root', 0, False),
            ('', 0, False),
        ]
        script = ('set -u\nLOG=$1\n'
                  'findmnt() { printf "%s\\n" "$RECORD"; return "$FINDMNT_RESULT"; }\n'
                  + MOUNT_FUNCTION +
                  '\ncheck_prepared_mount /private-target /dev/fixture btrfs /root\n')
        with tempfile.TemporaryDirectory(prefix='moos-mount-readback-') as directory:
            log = str(Path(directory) / 'log')
            for record, status, expected in cases:
                with self.subTest(record=record, status=status):
                    result = subprocess.run(['bash', '-s', '--', log], input=script,
                                            text=True, capture_output=True,
                                            env={**os.environ, 'RECORD': record,
                                                 'FINDMNT_RESULT': str(status)})
                    self.assertEqual(result.returncode == 0, expected, result.stderr)

    def test_exact_source_target_and_staging_survive_the_private_namespace(self):
        with tempfile.TemporaryDirectory(prefix='moos-install-mount-') as directory:
            root = Path(directory)
            recorder = root / 'record.json'
            shim = root / 'unshare'
            shim.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                            'from pathlib import Path\n'
                            'Path(os.environ["RECORD"]).write_text(json.dumps('
                            '{"args":sys.argv[1:],"tmpdir":os.environ.get("TMPDIR")}))\n'
                            'sys.exit(int(os.environ.get("UNSHARE_RESULT","0")))\n')
            shim.chmod(0o700)
            environment = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                           'RECORD': str(recorder)}
            script = ('set -u\nSRC=containers-storage:fixture\n'
                      'TARGET_IMGREF=ghcr.io/moalfarras-sys/moos:latest\n'
                      'TARGET_STAGE=/private-target-stage\nTARGET_ROOT=/private-target-root\n'
                      + 'v3_splash_target() { return 1; }\n' + FUNCTION + '\nrun_install\n')
            result = subprocess.run(['bash'], input=script, text=True,
                                    env=environment, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(recorder.read_text()), {
                'tmpdir': '/private-target-stage',
                'args': ['--mount', '--propagation', 'private', '--', 'bootc', 'install',
                         'to-filesystem', '--source-imgref', 'containers-storage:fixture',
                         '--target-transport', 'registry', '--target-imgref',
                         'ghcr.io/moalfarras-sys/moos:latest', '--skip-fetch-check',
                         '--skip-finalize', '--generic-image', '/private-target-root'],
            })
            environment['UNSHARE_RESULT'] = '23'
            failed = subprocess.run(['bash'], input=script, text=True,
                                    env=environment, capture_output=True)
            self.assertEqual(failed.returncode, 23)

    def test_v3_display_arguments_are_specific_to_the_generic_v3(self):
        with tempfile.TemporaryDirectory() as directory:
            dmi = Path(directory)
            for name, value in [('sys_vendor', 'Micro Computer (HK) Tech Limited'),
                                ('product_name', 'V3'), ('board_name', 'HPPAC')]:
                (dmi / name).write_text(value + '\n')
            def invocation(edition):
                script = ('set -u\nTARGET_STAGE=/tmp TARGET_ROOT=/target SRC=fixture TARGET_IMGREF=$2\n'
                          + V3_FUNCTION + FUNCTION.replace('v3_splash_target /sys/class/dmi/id',
                                                           'v3_splash_target "$1"')
                          + 'unshare() { printf "%s\\n" "$@"; }\nrun_install "$1"\n')
                return subprocess.check_output(['bash', '-s', '--', directory,
                                                'ghcr.io/moalfarras-sys/' + edition],
                                               input=script, text=True).splitlines()
            expected = ['--karg-delete=plymouth.use-simpledrm', '--karg=plymouth.use-simpledrm=2',
                        '--karg=video=efifb:2560x1600']
            self.assertEqual([a for a in invocation('moos:latest') if a.startswith('--karg')], expected)
            for edition in ('moos-nvidia:latest', 'moos-arm:latest', 'moos-cloud:latest'):
                self.assertFalse(any(a.startswith('--karg') for a in invocation(edition)))
            (dmi / 'product_name').write_text('V3 SE\n')
            self.assertFalse(any(a.startswith('--karg') for a in invocation('moos:latest')))
            (dmi / 'sys_vendor').unlink()
            self.assertFalse(any(a.startswith('--karg') for a in invocation('moos:latest')))

    def test_missing_namespace_tool_stops_before_target_preparation(self):
        admission = SOURCE[SOURCE.index('command -v unshare'):SOURCE.index('# Truncate')]
        with tempfile.TemporaryDirectory(prefix='moos-install-admission-') as directory:
            marker = Path(directory) / 'continued'
            script = ('command() { return 1; }\nfail() { exit 19; }\n' + admission +
                      '\nprintf continued > "$1"\n')
            result = subprocess.run(['bash', '-s', '--', str(marker)], input=script,
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 19)
            self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
