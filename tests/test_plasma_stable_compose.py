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
    def execute(self,failure=None,drift=False):
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
            return '6.8.3-1.fc44' if drift else M.EXPECTED[args[-1]]
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

if __name__=='__main__':unittest.main(verbosity=2)
