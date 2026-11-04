#!/usr/bin/python3
"""Native RPM candidate ordering and final-image refusal controls."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build_files/plasma_canary_version.py'
spec = importlib.util.spec_from_file_location('canary_version', SCRIPT)
version = importlib.util.module_from_spec(spec); spec.loader.exec_module(version)


@unittest.skipUnless(importlib.util.find_spec('rpm'), 'Native python3-rpm unavailable outside image')
class NativeVersionControls(unittest.TestCase):
    def test_absent_equal_and_older_offers_are_unavailable_not_qualified(self):
        for offered in ('', '6.8.2', '6.7.91', '6.8.2~rc1'):
            for final in (False, True):
                with self.subTest(offered=offered, final=final):
                    row = version.evaluate('6.8.2', offered, '6.8.2', image_gates_passed=final)
                    self.assertEqual(row['status'], 'unavailable')
                    self.assertFalse(row['qualifiedNextImage'])

    def test_rpm_numeric_and_snapshot_ordering_require_actual_new_image(self):
        for baseline, offered in (('6.9.2', '6.10.0'), ('6.8.2', '6.8.2^git1'), ('6.8.2', '6.8.3')):
            with self.subTest(offered=offered):
                row = version.evaluate(baseline, offered, baseline)
                self.assertEqual(row['status'], 'failed'); self.assertFalse(row['qualifiedNextImage'])
                row = version.evaluate(baseline, offered, offered)
                self.assertEqual(row['status'], 'ready-for-image-gates'); self.assertFalse(row['qualifiedNextImage'])
                row = version.evaluate(baseline, offered, offered, image_gates_passed=True)
                self.assertEqual(row['status'], 'image-gates-passed'); self.assertTrue(row['qualifiedNextImage'])
                row = version.evaluate(baseline, offered, baseline, image_gates_passed=True)
                self.assertEqual(row['status'], 'failed'); self.assertFalse(row['qualifiedNextImage'])

    def test_ambiguous_empty_and_invalid_readbacks_are_refused(self):
        for values in (('', '', '6.8.2'), ('6.8.2', '6.8.3\n6.8.4', '6.8.3'), ('6.8.2', '6.8.3', ''),
                       ('6.8.2', 'error: failed query', '6.8.2')):
            with self.subTest(values=values), self.assertRaises(ValueError): version.evaluate(*values)

    def test_native_cli_stale_and_mismatch_have_distinct_exit_and_receipt(self):
        import json
        for offered, expected_exit, state in (('6.7.91', 0, 'unavailable'), ('6.8.3', 1, 'failed')):
            result = subprocess.run([sys.executable, str(SCRIPT), '6.8.2', offered, '6.8.2'], capture_output=True, text=True)
            self.assertEqual(result.returncode, expected_exit, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], state)


if __name__ == '__main__': unittest.main()
