#!/usr/bin/env python3
"""Prove the prepared stock-context patch reproduces the accepted whole transport.

This test does not build, sign, install or load a kernel module.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/hardware/patches/smocf05"
MANIFEST = json.loads((PACKET / "manifest.json").read_text())
SOURCE = ROOT / "tests/fixtures/smocf05/stock-i2c.c"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RotationBackport(unittest.TestCase):
    def test_pinned_original_and_patch_bytes(self):
        self.assertEqual(sha(SOURCE), MANIFEST["stock_source_sha256"])
        self.assertEqual(sha(PACKET / "0001-upstream-smocf05.patch"),
                         MANIFEST["upstream_patch_sha256"])
        self.assertEqual(sha(PACKET / "0002-stock-context-backport.patch"),
                         MANIFEST["backport_patch_sha256"])
        original = (PACKET / "0001-upstream-smocf05.patch").read_text()
        for author in ("Samuel Dionne-Riel", "Jared Wuerzburger", "Jonathan Cameron"):
            self.assertIn("Signed-off-by: " + author, original)
        self.assertIn(MANIFEST["upstream_commit"], original)

    def test_actual_patch_matches_entire_accepted_upstream_source(self):
        with tempfile.TemporaryDirectory(prefix="moos-sensor-backport-") as temp:
            source = Path(temp) / "drivers/iio/imu/st_lsm6dsx/st_lsm6dsx_i2c.c"
            source.parent.mkdir(parents=True)
            shutil.copyfile(SOURCE, source)
            patch = str(PACKET / "0002-stock-context-backport.patch")
            result = subprocess.run(["git", "apply", "--whitespace=nowarn", patch],
                                    cwd=temp, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(sha(source), MANIFEST["accepted_source_sha256"])
            fixed = source.read_text()
            for identifier, hardware in (("SMO8B30", "ST_LSM6DS3TRC_ID"),
                                         ("SMOCF00", "ST_LSM6DSO_ID"),
                                         ("SMOCF05", "ST_LSM6DS3TRC_ID")):
                self.assertIn(f'.id = "{identifier}", .driver_data = {hardware}', fixed)
            again = subprocess.run(["git", "apply", "--whitespace=nowarn", patch], cwd=temp,
                                   capture_output=True, text=True, timeout=10)
            self.assertNotEqual(again.returncode, 0, "an already patched transport must refuse")
            self.assertEqual(sha(source), MANIFEST["accepted_source_sha256"])


if __name__ == "__main__":
    unittest.main()
