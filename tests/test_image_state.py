#!/usr/bin/env python3
"""Compose cleanup must preserve boot assets and reject unexpected user state."""
import runpy
from pathlib import Path
import tempfile
import unittest
import subprocess
import os
import shlex
import pwd
import grp

ROOT = Path(__file__).resolve().parents[1]
finalize = runpy.run_path(str(ROOT / 'build_files/finalize_image_state.py'))['finalize']

class ImageStateTests(unittest.TestCase):
    def fixture(self, root):
        for name in ('etc/flatpak/remotes.d/flathub.flatpakrepo',
                     'usr/lib/systemd/system/moos-flatpak-init.service',
                     'var/lib/flatpak/repo/config', 'var/lib/dnf/repos/example/countme',
                     'var/lib/xkb/README.compiled',
                     'var/lib/dnf/system-repo.lock', 'run/cockpit/active.issue',
                     'boot/efi/EFI/moos/loader.efi'):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')

    def test_cleanup_keeps_boot_and_immutable_store_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            finalize(root)
            self.assertEqual((root/'boot/efi/EFI/moos/loader.efi').read_text(), 'fixture')
            self.assertTrue((root/'etc/flatpak/remotes.d/flathub.flatpakrepo').is_file())
            self.assertFalse((root/'var/lib/flatpak').exists())
            self.assertFalse((root/'run/cockpit').exists())
            self.assertEqual((root/'usr/share/doc/moos-xkb/README.compiled').read_text(), 'fixture')
            finalize(root)  # idempotent

    def test_unknown_state_fails_instead_of_being_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            unknown = root/'var/lib/customer-data'; unknown.write_text('keep')
            with self.assertRaisesRegex(RuntimeError, 'unexpected mutable'):
                finalize(root)
            self.assertEqual(unknown.read_text(), 'keep')

    def test_package_directory_modes_survive_through_tmpfiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            package_state = root/'var/lib/lxc'
            package_state.mkdir(mode=0o750)
            runtime = root/'run/systemd/ask-password'; runtime.mkdir(parents=True)
            finalize(root)
            policy = root/'usr/lib/tmpfiles.d/moos-image-state.conf'
            self.assertIn('d /var/lib/lxc 0750 ', policy.read_text())
            self.assertNotIn('winbindd_privileged', policy.read_text())
            self.assertFalse(runtime.exists())
            package_state.rmdir()
            account = pwd.getpwuid(os.getuid())
            group = grp.getgrgid(os.getgid())
            (root/'etc/passwd').write_text(
                f'{account.pw_name}:x:{os.getuid()}:{os.getgid()}:fixture:/:/bin/sh\n')
            (root/'etc/group').write_text(f'{group.gr_name}:x:{os.getgid()}:\n')
            subprocess.run(['systemd-tmpfiles', '--root', directory, '--create',
                            str(policy)], check=True, capture_output=True)
            self.assertTrue(package_state.is_dir())
            self.assertEqual(package_state.stat().st_mode & 0o777, 0o750)

    def test_installed_apps_and_missing_bootstrap_are_rejected(self):
        for invalid in ('app', 'runtime', 'refs', 'missing-bootstrap'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.fixture(root)
                if invalid == 'missing-bootstrap':
                    (root/'usr/lib/systemd/system/moos-flatpak-init.service').unlink()
                elif invalid == 'refs':
                    path = root/'var/lib/flatpak/repo/refs/remotes/flathub/app/org.example.App'
                    path.parent.mkdir(parents=True)
                    path.write_text('committed-ref')
                else:
                    path = root/'var/lib/flatpak'/invalid/'org.example.App'
                    path.mkdir(parents=True)
                with self.assertRaises(RuntimeError): finalize(root)
                self.assertTrue((root/'var/lib/flatpak/repo/config').is_file())

    def test_symlink_target_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.fixture(root)
            path=root/'var/lib/dnf/repos'
            import shutil
            shutil.rmtree(path)
            path.symlink_to(root/'boot', target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'unexpected symlink'): finalize(root)
            self.assertTrue((root/'boot/efi/EFI/moos/loader.efi').exists())

    def test_first_boot_unit_is_wired_and_preserves_existing_config(self):
        name = 'moos-flatpak-init.service'
        source = ROOT/'system_files/usr/lib/systemd/system'/name
        text = source.read_text()
        self.assertIn('ConditionPathExists=!/var/lib/flatpak/repo/config', text)
        self.assertIn('ExecStart=/usr/bin/flatpak config --system --set extra-languages "ar;en;de"', text)
        self.assertIn('Before=display-manager.service flatpak-system-helper.service', text)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); unit=root/'usr/lib/systemd/system'/name
            unit.parent.mkdir(parents=True); unit.write_text(text)
            subprocess.run(['systemctl', '--root', directory, 'enable', name], check=True, capture_output=True)
            self.assertTrue((root/'etc/systemd/system/multi-user.target.wants'/name).is_symlink())
        for script in ('build.sh','build-arm.sh'):
            code=(ROOT/'build_files'/script).read_text()
            self.assertIn('systemctl enable '+name,code)
            self.assertIn('python3 /ctx/finalize_image_state.py --root /',code)
            self.assertGreater(code.index('python3 /ctx/finalize_image_state.py'), code.rindex('dnf5 '))

    def test_artifact_boot_checks_reject_missing_or_wrong_store_state(self):
        for script, end in (('boot_x86_qcow2.sh', "printf 'store=initialized"),
                            ('verify_arm_runtime.sh', "printf 'store=initialized"),
                            ('install_live_iso.sh', 'stage passed store-initialized')):
            code = (ROOT/'tests'/script).read_text()
            start = code.index('[ -s /var/lib/flatpak/repo/config ]')
            check = code[start:code.index(end, start)]
            for fault in ('healthy', 'missing-config', 'missing-key', 'language', 'remote'):
                with self.subTest(script=script, fault=fault), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    repo = root/'repo'; repo.mkdir()
                    for name in ('config', 'flathub.trustedkeys.gpg'):
                        (repo/name).write_text('fixture')
                    if fault == 'missing-config': (repo/'config').unlink()
                    if fault == 'missing-key': (repo/'flathub.trustedkeys.gpg').unlink()
                    flatpak = root/'flatpak'
                    languages = 'en' if fault == 'language' else 'ar;en;de'
                    remote = 'unexpected' if fault == 'remote' else 'flathub'
                    flatpak.write_text('#!/bin/sh\ncase "$1" in\n'
                                       + 'config) printf "%s\\n" '+shlex.quote(languages)+';;\n'
                                       + 'remotes) printf "%s\\n" '+shlex.quote(remote)+';;\nesac\n')
                    flatpak.chmod(0o755)
                    result = subprocess.run(['bash', '-ec', 'gate_fail() { exit 1; }\n'
                                             + check.replace('/var/lib/flatpak/repo', str(repo))],
                                            env={**os.environ, 'PATH': str(root)+':/usr/bin:/bin'},
                                            capture_output=True)
                    self.assertEqual(result.returncode == 0, fault == 'healthy', result.stderr)

if __name__ == '__main__': unittest.main()
