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
from unittest import mock

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
        var_tmp = root/'var/tmp'
        var_tmp.mkdir(parents=True, exist_ok=True)
        var_tmp.chmod(0o1777)

    def test_cleanup_keeps_boot_and_immutable_store_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            finalize(root)
            self.assertEqual((root/'boot/efi/EFI/moos/loader.efi').read_text(), 'fixture')
            self.assertTrue((root/'etc/flatpak/remotes.d/flathub.flatpakrepo').is_file())
            self.assertFalse((root/'var/lib/flatpak').exists())
            self.assertFalse((root/'var/lib').exists())
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
            self.assertFalse(package_state.exists())
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

    def test_unknown_directories_links_and_run_state_are_rejected(self):
        for kind in ('empty-directory', 'symlink', 'dangling-symlink', 'run-file',
                     'cleanup-file', 'cleanup-mount'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.fixture(root)
                if kind == 'empty-directory':
                    (root/'var/lib/unowned-empty').mkdir(parents=True)
                elif kind == 'symlink':
                    path = root/'var/lib/unowned-link'; path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(root/'boot')
                elif kind == 'dangling-symlink':
                    path = root/'var/lib/flatpak/unowned-link'; path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(root/'missing')
                else:
                    path = root/'run/unowned-state'; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('state')
                if kind in ('cleanup-file', 'cleanup-mount'):
                    import shutil
                    path = root/'var/lib/flatpak'
                    if kind == 'cleanup-file':
                        shutil.rmtree(path); path.write_text('must-not-delete')
                        context = mock.patch('os.path.ismount', return_value=False)
                    else:
                        context = mock.patch(
                            'os.path.ismount',
                            side_effect=lambda candidate: Path(candidate) == path,
                        )
                    with context, self.assertRaisesRegex(
                            RuntimeError, 'cleanup state|unsafe mount'):
                        finalize(root)
                    self.assertTrue(path.exists())
                else:
                    with self.assertRaisesRegex(RuntimeError, 'unexpected mutable|unsafe entry'):
                        finalize(root)

    def test_systemd_units_load_marker_file_is_compose_residue(self):
        # Native ARM run 34646190268 failed because the preflight demanded a
        # directory where systemd 259 leaves an empty regular file.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            marker = root/'run/systemd/systemd-units-load'
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text('')
            finalize(root)
            self.assertFalse(marker.exists())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            marker = root/'run/systemd/systemd-units-load'
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.symlink_to(root/'boot', target_is_directory=True)
            with self.assertRaises(RuntimeError):
                finalize(root)
            self.assertTrue((root/'boot/efi/EFI/moos/loader.efi').exists())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            import shutil
            shutil.rmtree(root/'var/lib/flatpak')
            (root/'var/lib/flatpak').write_text('must-not-delete')
            with mock.patch('os.path.ismount', return_value=False), \
                    self.assertRaisesRegex(RuntimeError, 'cleanup state is not a directory'):
                finalize(root)

    def test_contained_runtime_links_are_removed_but_escaping_links_fail(self):
        # x86 run 34646188216 stopped on cockpit-ws's tmpfiles rule
        # `L /run/cockpit/issue - - - - inactive.issue`.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            cockpit = root/'run/cockpit'
            (cockpit/'inactive.issue').write_text('issue')
            (cockpit/'issue').symlink_to('inactive.issue')
            finalize(root)
            self.assertFalse(cockpit.exists())
        for kind in ('escaping-relative', 'absolute'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); self.fixture(root)
                link = root/'run/cockpit/issue'
                link.symlink_to('../../boot' if kind == 'escaping-relative' else root/'boot')
                with self.assertRaisesRegex(RuntimeError, 'unsafe entry'):
                    finalize(root)
                self.assertTrue(link.is_symlink())
                self.assertTrue((root/'boot/efi/EFI/moos/loader.efi').exists())

    def test_every_unsafe_cleanup_entry_is_reported_at_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); self.fixture(root)
            (root/'run/cockpit/escape').symlink_to('../../boot')
            (root/'var/lib/dnf/repos/example/escape').symlink_to(root/'boot')
            with self.assertRaises(RuntimeError) as caught:
                finalize(root)
            self.assertIn('run/cockpit/escape', str(caught.exception))
            self.assertIn('var/lib/dnf/repos/example/escape', str(caught.exception))

    def test_first_boot_unit_is_wired_and_preserves_existing_config(self):
        name = 'moos-flatpak-init.service'
        source = ROOT/'system_files/usr/lib/systemd/system'/name
        text = source.read_text()
        self.assertNotIn('ConditionPathExists=', text)
        self.assertIn('ExecStart=/usr/bin/bash /usr/libexec/moos-flatpak-init', text)
        self.assertIn('Before=display-manager.service flatpak-system-helper.service', text)
        helper = (ROOT/'system_files/usr/libexec/moos-flatpak-init').read_text()
        self.assertIn('flatpak-init.pending', helper)
        self.assertIn('flatpak-init.complete', helper)
        self.assertIn('--show-disabled --columns=name,url,options', helper)
        self.assertNotIn('remote-delete --system --force', helper)
        preset = ROOT/'system_files/usr/lib/systemd/system-preset/00-moos-flatpak.preset'
        self.assertIn('enable moos-flatpak-init.service', preset.read_text())
        self.assertIn('disable flatpak-add-fedora-repos.service', preset.read_text())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); unit=root/'usr/lib/systemd/system'/name
            unit.parent.mkdir(parents=True); unit.write_text(text)
            inherited = unit.with_name('flatpak-add-fedora-repos.service')
            inherited.write_text('[Install]\nWantedBy=multi-user.target\n')
            preset_copy = root/'usr/lib/systemd/system-preset/00-moos-flatpak.preset'
            preset_copy.parent.mkdir(parents=True); preset_copy.write_text(preset.read_text())
            catch_all = preset_copy.with_name('99-default-disable.preset')
            catch_all.write_text('disable *\n')
            subprocess.run(['systemctl', '--root', directory, 'preset-all'],
                           check=True, capture_output=True)
            self.assertTrue((root/'etc/systemd/system/multi-user.target.wants'/name).is_symlink())
            self.assertFalse((root/'etc/systemd/system/multi-user.target.wants'/inherited.name).exists())
            subprocess.run(['systemctl', '--root', directory, 'mask', inherited.name],
                           check=True, capture_output=True)
            masked = subprocess.run(['systemctl', '--root', directory, 'is-enabled', inherited.name],
                                    text=True, check=False, capture_output=True)
            self.assertEqual(masked.stdout.strip(), 'masked')
            subprocess.run(['systemctl', '--root', directory, 'preset-all'],
                           check=True, capture_output=True)
            self.assertEqual((root/'etc/systemd/system'/inherited.name).readlink(), Path('/dev/null'))
        for script in ('build.sh','build-arm.sh'):
            code=(ROOT/'build_files'/script).read_text()
            self.assertIn('systemctl enable '+name,code)
            self.assertIn('systemctl disable flatpak-add-fedora-repos.service', code)
            self.assertIn('systemctl mask flatpak-add-fedora-repos.service', code)
            self.assertIn('python3 /ctx/finalize_image_state.py --root /',code)
            self.assertGreater(code.index('python3 /ctx/finalize_image_state.py'), code.rindex('dnf5 '))

    def test_store_helper_completes_fresh_state_and_migrates_only_safe_legacy(self):
        source = (ROOT/'system_files/usr/libexec/moos-flatpak-init').read_text()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root/'store'; state = root/'moos'; descriptor = root/'flathub.flatpakrepo'
            descriptor.write_text('descriptor')
            fake = root/'flatpak'; log = root/'calls'
            fake.write_text("""#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >>"$TEST_LOG"
case "$1" in
  remote-add)
    mkdir -p "$TEST_STORE/repo"
    printf 'gpg-verify=true\\n' >"$TEST_STORE/repo/config"
    printf 'key' >"$TEST_STORE/repo/flathub.trustedkeys.gpg" ;;
  config)
    if [ "${3:-}" = --get ]; then printf 'ar;en;de\\n'; fi ;;
  list) printf '%s' "${TEST_ORIGINS:-}" ;;
  remotes)
    case "$*" in
      *"--columns=name,url") printf 'flathub\\thttps://dl.flathub.org/repo/\\n' ;;
      *) printf '%s' "${TEST_REMOTES:-}" ;;
    esac ;;
  remote-delete) printf '%s\\n' "${3:-}" >>"$TEST_DELETES" ;;
esac
""")
            fake.chmod(0o755)
            code = (source.replace('/usr/bin/flatpak', str(fake))
                          .replace('/var/lib/flatpak', str(store))
                          .replace('/var/lib/moos', str(state))
                          .replace('/etc/flatpak/remotes.d/flathub.flatpakrepo', str(descriptor)))
            deletes = root/'deletes'
            env = {**os.environ, 'TEST_LOG': str(log), 'TEST_STORE': str(store),
                   'TEST_DELETES': str(deletes),
                   'TEST_REMOTES': 'flathub\thttps://dl.flathub.org/repo/\n'}
            subprocess.run(['bash', '-ec', code], env=env, check=True, capture_output=True)
            self.assertTrue((state/'flatpak-init.complete').is_file())
            self.assertFalse((state/'flatpak-init.pending').exists())
            self.assertFalse(deletes.exists())

            # Exact disabled legacy entries with no installed origin migrate.
            env['TEST_REMOTES'] = (
                'fedora\toci+https://registry.fedoraproject.org\tdisabled,oci\n'
                'fedora-testing\toci+https://registry.fedoraproject.org#testing\tdisabled,oci\n'
                'flathub\thttps://dl.flathub.org/repo/\n')
            subprocess.run(['bash', '-ec', code], env=env, check=True, capture_output=True)
            self.assertEqual(deletes.read_text().splitlines(), ['fedora', 'fedora-testing'])

            # An installed origin and a user-enabled remote are both preserved.
            deletes.unlink()
            env['TEST_ORIGINS'] = 'fedora\n'
            env['TEST_REMOTES'] = (
                'fedora\toci+https://registry.fedoraproject.org\tdisabled,oci\n'
                'fedora-testing\toci+https://registry.fedoraproject.org#testing\toci\n')
            subprocess.run(['bash', '-ec', code], env=env, check=True, capture_output=True)
            self.assertFalse(deletes.exists())

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
                    (repo/'config').write_text('gpg-verify=true\n')
                    (repo/'flathub.trustedkeys.gpg').write_text('fixture')
                    if fault == 'missing-config': (repo/'config').unlink()
                    if fault == 'missing-key': (repo/'flathub.trustedkeys.gpg').unlink()
                    flatpak = root/'flatpak'
                    languages = 'en' if fault == 'language' else 'ar;en;de'
                    remote = 'unexpected' if fault == 'remote' else 'flathub'
                    details = ('flathub\thttps://dl.flathub.org/repo/'
                               if remote == 'flathub' else 'unexpected\thttps://example.invalid/')
                    flatpak.write_text('#!/bin/sh\ncase "$*" in\n'
                                       + '"config --system --get extra-languages") printf "%s\\n" '
                                       + shlex.quote(languages)+';;\n'
                                       + '*"--columns=name,url,options"*) printf "%s\\n" '
                                       + shlex.quote(details)+';;\n'
                                       + '*"--columns=name"*) printf "%s\\n" '
                                       + shlex.quote(remote)+';;\nesac\n')
                    flatpak.chmod(0o755)
                    result = subprocess.run(['bash', '-ec', 'gate_fail() { exit 1; }\n'
                                             + check.replace('/var/lib/flatpak/repo', str(repo))],
                                            env={**os.environ, 'PATH': str(root)+':/usr/bin:/bin'},
                                            capture_output=True)
                    self.assertEqual(result.returncode == 0, fault == 'healthy', result.stderr)

    def test_arm_authselect_seed_preserves_existing_machine_checksum(self):
        code = (ROOT/'build_files/build-arm.sh').read_text()
        self.assertIn('[ -s /var/lib/authselect/checksum ]', code)
        self.assertLess(code.index('authselect check'), code.index('rm /var/lib/authselect/checksum'))
        start = code.index('[ ! -L /var/lib/authselect ]')
        end = code.index('rm /var/lib/authselect/checksum', start) + len('rm /var/lib/authselect/checksum')
        block = code[start:end]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            state=root/'var/lib/authselect/checksum'
            state.parent.mkdir(parents=True); state.write_text('applied-profile-checksum')
            (root/'usr/lib/tmpfiles.d').mkdir(parents=True)
            # Run the actual compose block against an isolated filesystem.
            subprocess.run(['bash','-ec', block.replace('/var/lib/', directory+'/var/lib/')
                            .replace('/usr/lib/', directory+'/usr/lib/')], check=True)
            self.assertFalse(state.exists())
            policy=root/'usr/lib/tmpfiles.d/moos-authselect-state.conf'
            self.assertIn('0644 root root -', policy.read_text())
            # The test runs unprivileged; retain its UID/GID while executing
            # the identical copy-if-absent operation and mode from the policy.
            policy.write_text(policy.read_text().replace(directory, '').replace('root root', '- -'))
            for expected in ('applied-profile-checksum','machine-custom-checksum'):
                subprocess.run(['systemd-tmpfiles','--root',directory,'--create',str(policy)],
                               check=True,capture_output=True)
                self.assertEqual(state.read_text(), expected)
                state.write_text('machine-custom-checksum')

if __name__ == '__main__': unittest.main()
