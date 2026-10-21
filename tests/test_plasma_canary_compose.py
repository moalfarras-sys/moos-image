#!/usr/bin/python3
"""Executable command/failure controls for the experimental package transaction.

The shared transaction's filesystem/authority negatives have their own native
controls. These prove that the beta path cannot run package mutations before
that snapshot or report cleanup success after a failed command/preflight.
"""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'build_files'),str(ROOT/'build_files/plasma_stable')]
spec=importlib.util.spec_from_file_location('canary_compose',ROOT/'build_files/prepare_plasma_canary_base.py')
composer=importlib.util.module_from_spec(spec);spec.loader.exec_module(composer)


class CanaryTransactionControls(unittest.TestCase):
    def execute(self,optional=1,arch='x86_64',failure=None):
        self.events=[]
        self.log_dirs=set()
        def event(name):
            self.events.append(name)
            if failure==name:raise RuntimeError('planted '+name)
        def snapshot():
            event('snapshot');self.transaction=SimpleNamespace(finalize=lambda:event('finalize'))
            return self.transaction
        def login_state(transaction):
            self.assertIs(transaction,self.transaction)
            self.assertTrue(all(not path.exists() for path in self.log_dirs))
            event('login-state')
        def query(args,**kwargs):event('architecture');return arch+'\n'
        def command(args,**kwargs):
            if args[0]=='dnf5':
                self.assertTrue(args[1].startswith('--setopt=logdir=/tmp/moos-canary-dnf-'))
                logdir=Path(args[1].split('=',2)[2]);self.log_dirs.add(logdir)
                self.assertTrue(logdir.is_dir());self.assertEqual(logdir.stat().st_mode&0o777,0o700)
                (logdir/'dnf5.log.1').write_text('planted temporary build log')
                args=[args[0],*args[2:]]
            name=' '.join(args);event(name)
            if args[:2]==['rpm','-q']:return SimpleNamespace(returncode=optional)
            self.assertTrue(kwargs.get('check'),name)
            return SimpleNamespace(returncode=0)
        with patch.object(composer,'Transaction',side_effect=snapshot), \
             patch.object(composer.subprocess,'check_output',side_effect=query), \
             patch.object(composer.subprocess,'run',side_effect=command), \
             patch.object(composer,'reconcile_login_state',side_effect=login_state), \
             patch.object(composer,'finalize_canary',side_effect=lambda root:event('canary')), \
             patch.object(composer,'finalize_root_home',side_effect=lambda root:event('root-home')):
            composer.compose()

    def test_pristine_snapshot_precedes_every_package_command_and_cleanup_follows_them(self):
        self.execute()
        self.assertEqual(self.events,['snapshot','architecture','dnf5 -y copr enable @kdesig/kde-beta',
            'rpm -q kcm-fcitx5','dnf5 -y distro-sync --refresh --allowerasing --best --exclude=kernel*',
            'dnf5 clean all','login-state','canary','root-home','finalize'])
        self.assertEqual(len(self.log_dirs),1)
        self.assertFalse(next(iter(self.log_dirs)).exists())

    def test_only_the_installed_optional_input_module_is_removed_without_autoremove(self):
        self.execute(optional=0)
        removals=[e for e in self.events if ' remove ' in e]
        self.assertEqual(removals,['dnf5 -y remove --no-autoremove kcm-fcitx5'])
        self.assertLess(self.events.index(removals[0]),self.events.index('dnf5 -y distro-sync --refresh --allowerasing --best --exclude=kernel*'))

    def test_unsafe_input_refuses_before_any_package_query_or_mutation(self):
        with self.assertRaisesRegex(RuntimeError,'snapshot'):self.execute(failure='snapshot')
        self.assertEqual(self.events,['snapshot'])

    def test_arm_input_cannot_reach_x86_beta_repository(self):
        with self.assertRaisesRegex(RuntimeError,'x86_64'):self.execute(arch='aarch64')
        self.assertEqual(self.events,['snapshot','architecture'])

    def test_query_error_is_not_treated_as_optional_package_absence(self):
        with self.assertRaisesRegex(RuntimeError,'query failed'):self.execute(optional=2)
        self.assertNotIn('dnf5 -y distro-sync --refresh --allowerasing --best --exclude=kernel*',self.events)
        self.assertNotIn('finalize',self.events)

    def test_each_package_failure_stops_before_cleanup(self):
        for command in ('dnf5 -y copr enable @kdesig/kde-beta','dnf5 -y remove --no-autoremove kcm-fcitx5',
                        'dnf5 -y distro-sync --refresh --allowerasing --best --exclude=kernel*','dnf5 clean all'):
            with self.subTest(command=command),self.assertRaises(RuntimeError):self.execute(optional=0,failure=command)
            self.assertNotIn('canary',self.events);self.assertNotIn('finalize',self.events)
            self.assertTrue(all(not path.exists() for path in self.log_dirs))

    def test_each_cleanup_failure_remains_nonzero_and_cannot_reach_later_cleanup(self):
        for stage in ('login-state','canary','root-home','finalize'):
            with self.subTest(stage=stage),self.assertRaises(RuntimeError):self.execute(failure=stage)
            if stage!='finalize':self.assertNotIn('finalize',self.events)


if __name__=='__main__':unittest.main()
