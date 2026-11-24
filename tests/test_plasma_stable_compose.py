#!/usr/bin/env python3
"""A desktop source transition must refuse installed hosts, wrong CPUs and key drift."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('stable_compose',ROOT/'build_files/plasma_stable/compose.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
class CompositionBoundary(unittest.TestCase):
    def test_an_installed_ostree_host_is_refused_before_any_package_command(self):
        with mock.patch.object(Path,'exists',return_value=True),mock.patch.object(M,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'unbooted'):M.compose()
            run.assert_not_called()

    def test_a_noncontainer_host_is_refused_before_any_package_command(self):
        with mock.patch.object(Path,'exists',return_value=False),mock.patch.object(M,'run') as run:
            with self.assertRaisesRegex(RuntimeError,'unbooted'):M.compose()
            run.assert_not_called()

    def environment(self):
        return mock.patch.object(Path,'exists',lambda p:str(p)=='/run/.containerenv')

    def test_the_x86_only_source_is_never_used_for_arm(self):
        with self.environment(),mock.patch.object(M,'run',return_value='aarch64') as run, \
             mock.patch.object(Path,'write_bytes') as write:
            with self.assertRaisesRegex(RuntimeError,'x86_64'):M.compose()
            write.assert_not_called()
            self.assertEqual(run.call_count,1)

    def test_a_different_key_is_refused_before_import_or_repository_write(self):
        with self.environment(),mock.patch.object(M,'run',return_value='x86_64') as run, \
             mock.patch.object(Path,'read_bytes',return_value=b'replaced signing key'), \
             mock.patch.object(Path,'write_text') as write:
            with self.assertRaisesRegex(RuntimeError,'signing key'):M.compose()
            write.assert_not_called()
            self.assertEqual(run.call_count,1)

    def test_an_unreviewed_base_version_is_not_silently_downgraded(self):
        with self.environment(),mock.patch.object(M,'run',side_effect=['x86_64','6.9.0']) as run, \
             mock.patch.object(Path,'write_bytes') as write:
            with self.assertRaisesRegex(RuntimeError,'unreviewed'):M.compose()
            write.assert_not_called()
            self.assertEqual(run.call_count,2)

class PackageCommandLogs(unittest.TestCase):
    def execute(self,failure=None,drift=False,overrides=None):
        self.commands=[];self.directories=set();self.queries=[]
        def command(args,**kwargs):
            self.assertEqual(args[0],'dnf5')
            self.assertTrue(args[1].startswith('--setopt=logdir=/tmp/moos-stable-dnf-'))
            path=Path(args[1].split('=',2)[2]);self.directories.add(path)
            self.assertEqual(path.stat().st_mode&0o777,0o700)
            (path/'dnf5.log.1').write_text('native rotation remains build-private')
            self.assertTrue(kwargs.get('check'))
            plain=[args[0],*args[2:]];self.commands.append(plain)
            if failure==plain[1]:raise subprocess.CalledProcessError(2,args)
        def query(*args):
            self.queries.append(args)
            self.assertEqual(args[:4],('rpm','-q','--qf','%{VERSION}-%{RELEASE}'))
            return ('6.8.4-1.fc44' if drift else
                    (overrides or {}).get(args[-1],M.EXPECTED[args[-1]]))
        with mock.patch.object(M.subprocess,'run',side_effect=command),mock.patch.object(M,'run',side_effect=query):
            return M.sync_packages()

    def test_all_package_commands_share_one_private_log_directory_removed_after_success(self):
        self.assertEqual(self.execute(),M.EXPECTED)
        self.assertEqual(self.commands,[['dnf5','-y','distro-sync','--refresh','--best',
            '--setopt=install_weak_deps=False','--exclude=kernel*'],['dnf5','clean','all']])
        self.assertEqual(len(self.directories),1)
        self.assertTrue(all(not p.exists() for p in self.directories))
        self.assertEqual({args[-1] for args in self.queries},set(M.EXPECTED))

    def test_distro_sync_failure_propagates_and_private_rotated_log_is_retired(self):
        with self.assertRaises(subprocess.CalledProcessError):self.execute(failure='-y')
        self.assertEqual(len(self.commands),1);self.assertEqual(self.queries,[])
        self.assertTrue(all(not p.exists() for p in self.directories))

    def test_clean_failure_is_not_reported_as_a_successful_package_transaction(self):
        with self.assertRaises(subprocess.CalledProcessError):self.execute(failure='clean')
        self.assertEqual(len(self.commands),2)
        self.assertTrue(all(not p.exists() for p in self.directories))

    def test_unreviewed_packages_still_refuse_before_success_and_retire_only_private_logs(self):
        with self.assertRaisesRegex(RuntimeError,'inputs drifted'):self.execute(drift=True)
        self.assertEqual(len(self.commands),1)
        self.assertTrue(all(not p.exists() for p in self.directories))

    def test_only_the_reviewed_kwin_rebuild_changes_the_exact_package_set(self):
        expected={name:'6.8.3-1.fc44' for name in ('plasma-workspace','plasma-desktop',
            'kwin','libplasma','kscreenlocker','plasma-login-manager')}
        expected['kwin']='6.8.3-2.fc44'
        self.assertEqual(self.execute(overrides=expected),expected)

    def test_older_and_unknown_kwin_rebuilds_still_refuse_before_cleanup_success(self):
        for release in ('6.8.2-1.fc44','6.8.2-3.fc44','6.8.3-1.fc44','6.8.3-3.fc44','6.8.4-1.fc44'):
            with self.subTest(release=release),self.assertRaisesRegex(RuntimeError,'inputs drifted'):
                self.execute(overrides={'kwin':release})
            self.assertEqual(len(self.commands),1)
            self.assertTrue(all(not p.exists() for p in self.directories))

    def test_the_kwin_review_does_not_admit_another_package_rebuild(self):
        with self.assertRaisesRegex(RuntimeError,'inputs drifted'):
            self.execute(overrides={'libplasma':'6.8.3-2.fc44'})
        self.assertEqual(len(self.commands),1)

import sys
sys.path.insert(0, str(ROOT/'build_files'))
fspec=importlib.util.spec_from_file_location('finalize_canary_base',ROOT/'build_files/finalize_canary_base.py')
F=importlib.util.module_from_spec(fspec);fspec.loader.exec_module(F)


class SelinuxStoreBinding(unittest.TestCase):
    """The transaction writes selinux-policy where a booted MoOS reads it (2026-11-24)."""
    # The rules the real rpm-ostree-0-integration.conf holds for these paths (V3, 2026-11-24).
    VENDOR=('d /var/home 0755 root root -\n'
            'L /var/lib/rpm - - - - ../../usr/share/rpm\n'
            'L /var/lib/selinux - - - - ../../etc/selinux\n'
            '# /var/lib/selinux -> /etc/selinux equivalence. Z does not follow symlinks.\n'
            'Z /var/lib/selinux - - - -\n')

    def fake_root(self, tmp, rule=VENDOR):
        root=Path(tmp)
        (root/'etc/selinux/targeted').mkdir(parents=True)
        (root/'usr/lib/tmpfiles.d').mkdir(parents=True)
        (root/'usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf').write_text(rule)
        (root/'var').mkdir()
        return root

    def test_the_real_vendor_rule_creates_exactly_the_store_alias(self):
        import os, shutil, tempfile
        if not shutil.which('systemd-tmpfiles'):
            self.skipTest('systemd-tmpfiles is not installed')
        with tempfile.TemporaryDirectory() as tmp:
            root=self.fake_root(tmp)
            with mock.patch.object(F.subprocess,'run',wraps=F.subprocess.run) as run:
                F.bind_selinux_store(root)
            # The verified file inside the given root, never the caller's own copy.
            self.assertEqual(run.call_args.args[0][-1], str(root/'usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf'))
            store=root/'var/lib/selinux'
            self.assertTrue(store.is_symlink())
            self.assertEqual(os.readlink(store),'../../etc/selinux')

    def test_an_existing_store_is_refused_before_tmpfiles_runs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=self.fake_root(tmp)
            (root/'var/lib/selinux/targeted').mkdir(parents=True)
            with mock.patch.object(F.subprocess,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'already exists'):F.bind_selinux_store(root)
                run.assert_not_called()

    def test_a_missing_or_changed_vendor_rule_is_refused(self):
        import tempfile
        for rule in ('', 'L /var/lib/selinux - - - - /tmp/elsewhere\n',
                     'L /var/lib/selinux - - - - ../../etc/selinux\nL+ /var/lib/selinux - - - - x\n',
                     'L /var/lib/selinux - - - - ../../etc/selinux\nd /var/lib/selinux 0755 root root -\n',
                     'L /var/lib/selinux - - - - ../../etc/selinux\nZ /var/lib/selinux - - - - extra\n'):
            with self.subTest(rule=rule),tempfile.TemporaryDirectory() as tmp:
                root=self.fake_root(tmp, rule)
                with mock.patch.object(F.subprocess,'run') as run:
                    with self.assertRaisesRegex(RuntimeError,'no exact vendor tmpfiles rule'):
                        F.bind_selinux_store(root)
                    run.assert_not_called()

    def test_a_different_result_than_the_exact_alias_is_refused(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root=self.fake_root(tmp)
            def wrong(args, **kwargs):
                (root/'var/lib').mkdir(parents=True, exist_ok=True)
                os.symlink('../../tmp', root/'var/lib/selinux')
            with mock.patch.object(F.subprocess,'run',side_effect=wrong):
                with self.assertRaisesRegex(RuntimeError,'did not create the exact'):F.bind_selinux_store(root)

    def test_both_transactions_bind_the_store_after_the_pristine_snapshot_and_before_packages(self):
        for path, snapshot, first_package in (
                ('build_files/plasma_stable/compose.py', 'transaction = Transaction()', 'actual=sync_packages()'),
                ('build_files/prepare_plasma_canary_base.py', 'transaction=Transaction()', "dnf(logs,'-y','copr'")):
            with self.subTest(path=path):
                body=(ROOT/path).read_text()
                body=body[body.index('def compose('):]
                self.assertLess(body.index(snapshot), body.index('bind_selinux_store()'))
                self.assertLess(body.index('bind_selinux_store()'), body.index(first_package))

if __name__=='__main__':unittest.main(verbosity=2)
