#!/usr/bin/env python3
"""Execute actual compose helper with a private fake producer, never host dracut."""
import importlib.util
import contextlib
import io
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'build_files/compose_arm_initramfs.py'
sys.path.insert(0, str(ROOT / 'build_files'))
spec = importlib.util.spec_from_file_location('arm_compose', HELPER)
compose = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compose)


class ArmDracutHome(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='moos-dracut-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('var', 'tmp', 'run', 'usr/lib/modules/test-kernel'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        self.home = self.root / 'var/roothome'
        self.receipt = self.root / 'producer-receipt.json'
        self.fake = self.root / 'fake-dracut'
        self.fake.write_text(f'#!{sys.executable}\n' + '''import json,os,pathlib,sys,time
root=pathlib.Path(os.environ['COMPOSE_FIXTURE_ROOT'])
home=pathlib.Path(os.environ['HOME']); (home/'.cache').mkdir(exist_ok=True)
(home/'.cache/generated').write_text('private cache')
if os.environ.get('COMPOSE_UNKNOWN'):
    (root/'var/roothome/unknown-owner-file').write_text('unknown bytes must survive')
(root/'producer-receipt.json').write_text(json.dumps({'argv':sys.argv[1:], 'HOME':str(home),
    'xdg':{k:v for k,v in os.environ.items() if k.startswith('XDG_') and k.endswith(('_HOME','_DIR'))}}))
for number in range(25): print('compose-line-'+str(number))
if os.environ.get('COMPOSE_SLEEP'): time.sleep(float(os.environ['COMPOSE_SLEEP']))
raise SystemExit(int(os.environ.get('COMPOSE_STATUS','0')))
''')
        self.fake.chmod(0o755)

    def run_helper(self, compose_timeout=None, **env):
        argv = [sys.executable, str(HELPER), '--root', str(self.root),
                '--dracut', str(self.fake), 'test-kernel']
        if compose_timeout is not None:
            argv += ['--timeout', str(compose_timeout)]
        return subprocess.run(argv,
                              env={**os.environ, 'HOME': str(self.home),
                                   'COMPOSE_FIXTURE_ROOT': str(self.root), **env},
                              capture_output=True, text=True, timeout=10)

    def seed_vendor_home(self):
        self.home.mkdir(mode=0o700)
        for relative, mode in compose.VENDOR_DIRECTORIES.items():
            path = self.home / relative
            path.mkdir(parents=True, exist_ok=True)
            path.chmod(mode)
        for relative in compose.VENDOR_FILES:
            (self.home / relative).touch(mode=0o644)
        rules = self.root / 'usr/lib/tmpfiles.d'
        rules.mkdir(parents=True, exist_ok=True)
        for name, lines in compose.VENDOR_RULES.items():
            path = rules / name
            path.write_text('\n'.join(sorted(lines)) + '\n')
            path.chmod(compose.VENDOR_AUTHORITY_MODES[name])

    def vendor_snapshot(self):
        import stat
        result = {}
        for path in [self.home, *self.home.rglob('*')]:
            info = path.lstat()
            result[str(path.relative_to(self.home))] = (
                info.st_mode, info.st_uid, info.st_gid, info.st_nlink,
                path.read_bytes() if stat.S_ISREG(info.st_mode) else
                os.readlink(path) if stat.S_ISLNK(info.st_mode) else None)
        return result

    def test_exact_empty_vendor_tree_is_retired_before_unchanged_empty_guard(self):
        self.seed_vendor_home()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            compose.empty_owned_home(self.home)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Retired exact empty vendor', result.stdout)
        self.assertFalse(self.home.exists())
        self.assertEqual(list((self.root / 'tmp').iterdir()), [])

    def test_vendor_state_negatives_preserve_entire_tree_before_first_unlink(self):
        mutations = ('absent-rule', 'changed-rule', 'populated-labels', 'authorized-key', 'empty-authorized-key',
                     'hardlink', 'symlink', 'extra-entry', 'directory-mode', 'partial-tree')
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.seed_vendor_home()
                labels = self.home / 'buildinfo/labels.json'
                rule = self.root / 'usr/lib/tmpfiles.d/konflux-buildinfo-contentsets.conf'
                if mutation == 'absent-rule':
                    rule.unlink()
                elif mutation == 'changed-rule':
                    rule.write_text(rule.read_text().replace('0755', '0700'))
                elif mutation == 'populated-labels':
                    labels.write_text('vendor or owner data must remain')
                elif mutation == 'authorized-key':
                    (self.home / '.ssh/authorized_keys').write_text('private fixture key')
                elif mutation == 'empty-authorized-key':
                    (self.home / '.ssh/authorized_keys').touch()
                elif mutation == 'hardlink':
                    os.link(labels, self.root / 'linked-labels')
                elif mutation == 'symlink':
                    labels.unlink()
                    labels.symlink_to(self.root / 'outside-labels')
                    (self.root / 'outside-labels').touch()
                elif mutation == 'extra-entry':
                    (self.home / 'unknown-extra').touch()
                elif mutation == 'directory-mode':
                    (self.home / 'buildinfo').chmod(0o700)
                elif mutation == 'partial-tree':
                    (self.home / '.ssh').rmdir()
                before = self.vendor_snapshot()
                result = self.run_helper()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.receipt.exists())
                self.assertEqual(self.vendor_snapshot(), before)
                self.assertIn('metadata', result.stdout)
                self.assertNotIn('private fixture key', result.stdout)
                shutil.rmtree(self.home)  # entirely owned fixture, no real mounts
                for path in ('linked-labels', 'outside-labels'):
                    (self.root / path).unlink(missing_ok=True)

    def test_vendor_descendant_mount_is_refused_before_unlink(self):
        self.seed_vendor_home()
        before = self.vendor_snapshot()
        with patch.object(compose, 'mountpoints', return_value={str(self.home / 'buildinfo')}), \
             contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            compose.retire_empty_vendor_home(self.root, self.home)
        self.assertEqual(self.vendor_snapshot(), before)

    def test_old_home_writer_fails_rmdir_fixed_writer_stays_in_private_scratch(self):
        # The exact former producer/rmdir structure, rooted wholly in this fixture.
        old = subprocess.run(['bash', '-c',
            'set -euo pipefail; install -d -m0700 "$1"; "$2" --no-hostonly --force '
            '--reproducible --add "ostree plymouth" "$3" test-kernel 2>&1 | tail -20; rmdir "$1"',
            'old-compose', str(self.home), str(self.fake),
            str(self.root / 'usr/lib/modules/test-kernel/initramfs.img')],
            env={**os.environ, 'HOME': str(self.home), 'COMPOSE_FIXTURE_ROOT': str(self.root)},
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(old.returncode, 0)
        self.assertIn('Directory not empty', old.stderr)
        self.assertTrue((self.home / '.cache/generated').exists())
        # Retire only known test bytes, then run the actual new helper.
        (self.home / '.cache/generated').unlink()
        (self.home / '.cache').rmdir()
        self.home.rmdir()
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.home.exists())
        self.assertEqual(list((self.root / 'tmp').iterdir()), [])
        receipt = json.loads(self.receipt.read_text())
        self.assertTrue(receipt['HOME'].startswith(str(self.root / 'tmp/moos-dracut-')))
        self.assertTrue(all(v.startswith(str(self.root / 'tmp/moos-dracut-'))
                            for v in receipt['xdg'].values()))
        self.assertEqual(receipt['argv'], ['--no-hostonly', '--force', '--reproducible',
                         '--add', 'ostree plymouth',
                         str(self.root / 'usr/lib/modules/test-kernel/initramfs.img'), 'test-kernel'])
        self.assertNotIn('compose-line-4\n', result.stdout)
        self.assertIn('compose-line-5\n', result.stdout)
        self.assertIn('compose-line-24\n', result.stdout)

    def test_producer_nonzero_is_preserved(self):
        result = self.run_helper(COMPOSE_STATUS='7')
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertFalse(self.home.exists())
        self.assertEqual(list((self.root / 'tmp').iterdir()), [])

    def test_timeout_fails_and_owned_scratch_is_cleaned(self):
        result = self.run_helper(compose_timeout=0.2, COMPOSE_SLEEP='3')
        self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
        self.assertFalse(self.home.exists())
        self.assertEqual(list((self.root / 'tmp').iterdir()), [])

    def test_cleanup_error_preserves_producer_exit_and_never_turns_zero_green(self):
        for producer_status in ('0', '7'):
            with self.subTest(status=producer_status), \
                 patch.dict(os.environ, {'COMPOSE_FIXTURE_ROOT': str(self.root),
                                         'COMPOSE_STATUS': producer_status}), \
                 patch.object(compose, 'cleanup_scratch', side_effect=OSError('injected cleanup refusal')), \
                 contextlib.redirect_stdout(io.StringIO()):
                status = compose.main(['--root', str(self.root), '--dracut', str(self.fake), 'test-kernel'])
                self.assertEqual(status, 1 if producer_status == '0' else 7)
                self.assertFalse(self.home.exists())
        self.assertEqual(len(list((self.root / 'tmp').iterdir())), 2)

    def test_log_read_error_preserves_producer_exit(self):
        original = Path.open
        def unreadable_log(path, *args, **kwargs):
            if path.name == 'dracut.log' and (not args or args[0] != 'wb'):
                raise OSError('injected log-read refusal')
            return original(path, *args, **kwargs)
        with patch.dict(os.environ, {'COMPOSE_FIXTURE_ROOT': str(self.root), 'COMPOSE_STATUS': '7'}), \
             patch.object(Path, 'open', unreadable_log), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(compose.main(['--root', str(self.root), '--dracut', str(self.fake), 'test-kernel']), 7)
        self.assertFalse(self.home.exists())
        self.assertEqual(list((self.root / 'tmp').iterdir()), [])

    def test_scratch_descendant_mount_refuses_cleanup_before_any_walk(self):
        scratch = self.root / 'tmp/private-scratch'
        mounted = scratch / 'mounted'
        mounted.mkdir(parents=True)
        marker = mounted / 'outside-owner-data'
        marker.write_text('must survive')
        with patch.object(compose, 'mountpoints', return_value={str(mounted)}), \
             patch.object(compose.os, 'walk') as walk, \
             patch.object(compose.shutil, 'rmtree') as remove:
            with self.assertRaises(RuntimeError):
                compose.cleanup_scratch(self.root, scratch)
            walk.assert_not_called()
            remove.assert_not_called()
        self.assertEqual(marker.read_text(), 'must survive')

    def test_unknown_existing_bytes_refused_before_producer_and_unchanged(self):
        self.home.mkdir()
        unknown = self.home / 'unknown-owner-file'
        unknown.write_bytes(b'private bytes never printed')
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(unknown.read_bytes(), b'private bytes never printed')
        self.assertIn('unknown-owner-file', result.stdout)
        self.assertNotIn('private bytes never printed', result.stdout + result.stderr)

    def test_unknown_new_bytes_refused_and_nonzero_producer_still_preserved(self):
        for producer_status in ('0', '7'):
            with self.subTest(status=producer_status):
                result = self.run_helper(COMPOSE_UNKNOWN='1', COMPOSE_STATUS=producer_status)
                self.assertEqual(result.returncode, 1 if producer_status == '0' else 7)
                unknown = self.home / 'unknown-owner-file'
                self.assertEqual(unknown.read_text(), 'unknown bytes must survive')
                self.assertIn('unknown-owner-file', result.stdout)
                self.assertNotIn('unknown bytes must survive', result.stdout)
                unknown.unlink()  # exact owned fixture bytes only
                self.home.rmdir()

    def test_symlink_mount_foreign_owner_and_booted_host_are_refused(self):
        outside = self.root / 'outside'
        outside.mkdir()
        self.home.symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertTrue(self.home.is_symlink())
        self.home.unlink()
        self.home.mkdir()
        with patch.object(compose, 'mountpoints', return_value={str(self.home)}):
            with self.assertRaises(RuntimeError):
                compose.empty_owned_home(self.home)
        with patch.object(compose.os, 'geteuid', return_value=os.geteuid() + 1):
            with self.assertRaises(RuntimeError):
                compose.empty_owned_home(self.home)
        (self.root / 'run/ostree-booted').touch()
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertFalse(self.receipt.exists())
        self.assertTrue(self.home.is_dir())

    def test_parent_symlink_or_mount_is_refused_without_touching_outside(self):
        outside = self.root / 'outside'
        outside.mkdir()
        marker = outside / 'private-file'
        marker.write_text('must stay')
        (self.root / 'var').rmdir()
        (self.root / 'var').symlink_to(outside, target_is_directory=True)
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(marker.read_text(), 'must stay')
        self.assertFalse((outside / 'roothome').exists())
        (self.root / 'var').unlink()
        (self.root / 'var').mkdir()
        with patch.object(compose, 'mountpoints', return_value={str(self.root / 'var')}):
            with self.assertRaises(RuntimeError):
                compose.build_path(self.root, 'var/roothome')

    def test_native_root_requires_unbooted_container(self):
        with patch.object(compose.Path, 'exists', return_value=False):
            with self.assertRaises(RuntimeError):
                compose.validate_root(Path('/'))
        with patch.object(compose.Path, 'exists', return_value=True):
            with self.assertRaises(RuntimeError):
                compose.validate_root(Path('/'))

    def test_metadata_never_descends_into_child_mount(self):
        self.home.mkdir()
        mounted = self.home / 'mounted'
        mounted.mkdir()
        (mounted / 'hidden-child-name').write_text('not inspected')
        output = io.StringIO()
        with patch.object(compose, 'mountpoints', return_value={str(mounted)}), contextlib.redirect_stdout(output):
            compose.describe(self.home)
        self.assertIn('mounted', output.getvalue())
        self.assertNotIn('hidden-child-name', output.getvalue())

    def test_unknown_metadata_listing_is_bounded(self):
        self.home.mkdir()
        for number in range(70):
            (self.home / f'private-name-{number}').touch()
        result = self.run_helper()
        records = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        self.assertEqual(len(records), 64)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(list(self.home.iterdir())), 70)

    def test_both_arm_builds_call_shared_helper(self):
        for name in ('build-arm.sh', 'build-arm-recovery.sh'):
            code = (ROOT / 'build_files' / name).read_text()
            self.assertIn('python3 /ctx/compose_arm_initramfs.py "${kver}"', code)
            self.assertNotIn('rmdir /var/roothome', code)
        for name in ('Containerfile.arm', 'Containerfile.arm-recovery'):
            containerfile = (ROOT / name).read_text()
            self.assertIn('COPY build_files /', containerfile)
            self.assertIn('RUN --mount=type=bind,from=ctx,source=/,target=/ctx', containerfile)

    def test_staged_ctx_imports_helper_and_requires_finalizer_dependency(self):
        ctx = self.root / 'ctx'
        ctx.mkdir()
        for name in ('compose_arm_initramfs.py', 'finalize_image_state.py'):
            shutil.copyfile(ROOT / 'build_files' / name, ctx / name)
        argv = [sys.executable, '-B', str(ctx / 'compose_arm_initramfs.py'), '--help']
        result = subprocess.run(argv, env={'PATH': os.defpath}, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        (ctx / 'finalize_image_state.py').unlink()
        missing = subprocess.run(argv, env={'PATH': os.defpath}, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('finalize_image_state', missing.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
