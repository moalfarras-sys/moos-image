#!/usr/bin/env python3
"""Regression tests for BIB layouts with an optional BIOS partition first."""

from pathlib import Path
import json
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "build_files" / "resolve_release_partitions.py"


class ReleasePartitionRoleTests(unittest.TestCase):
    def run_resolver(self, children: list[dict[str, str]]) -> subprocess.CompletedProcess[str]:
        layout = {
            "blockdevices": [
                {"name": "/dev/nbd7", "type": "disk", "fstype": None, "children": children}
            ]
        }
        return subprocess.run(
            ["python3", str(RESOLVER), "--nbd", "/dev/nbd7"],
            input=json.dumps(layout),
            text=True,
            capture_output=True,
            check=False,
        )

    def test_bios_first_partition_does_not_shift_release_roles(self) -> None:
        result = self.run_resolver(
            [
                {"name": "/dev/nbd7p1", "type": "part", "fstype": None},
                {"name": "/dev/nbd7p2", "type": "part", "fstype": "vfat"},
                {"name": "/dev/nbd7p3", "type": "part", "fstype": "ext4"},
                {"name": "/dev/nbd7p4", "type": "part", "fstype": "btrfs"},
            ]
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.splitlines(),
            ["/dev/nbd7p2", "/dev/nbd7p3", "/dev/nbd7p4"],
        )

    def test_ambiguous_filesystem_fails_closed(self) -> None:
        result = self.run_resolver(
            [
                {"name": "/dev/nbd7p1", "type": "part", "fstype": "vfat"},
                {"name": "/dev/nbd7p2", "type": "part", "fstype": "vfat"},
                {"name": "/dev/nbd7p3", "type": "part", "fstype": "ext4"},
                {"name": "/dev/nbd7p4", "type": "part", "fstype": "btrfs"},
            ]
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected exactly one EFI", result.stderr)


if __name__ == "__main__":
    unittest.main()
