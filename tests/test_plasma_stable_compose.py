#!/usr/bin/env python3
"""A desktop source transition must refuse installed hosts, wrong CPUs and key drift."""
import importlib.util
from pathlib import Path
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

if __name__=='__main__':unittest.main(verbosity=2)
