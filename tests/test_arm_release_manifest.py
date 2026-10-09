#!/usr/bin/env python3
"""ARM recovery targets stay identical, immutable and traceable to promotion."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ArmReleaseManifest(unittest.TestCase):
    def test_remote_and_bundled_metadata_are_the_same_signed_target(self):
        external = json.loads((ROOT / "release/arm-latest.json").read_text())
        internal = json.loads((ROOT / "system_files/usr/share/moos/release/arm-latest.json").read_text())
        self.assertEqual(external, internal)
        self.assertEqual(external["schema"], 1)
        self.assertEqual(external["edition"], "moos-arm")
        self.assertEqual(external["repository"], "ghcr.io/moalfarras-sys/moos-arm")
        self.assertRegex(external["digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(external["product_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(external["version"], r"^44\.\d{8}\.\d+$")
        self.assertIsInstance(external["proof_run"], int)
        self.assertGreater(external["proof_run"], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
