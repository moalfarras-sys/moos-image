#!/usr/bin/env python3
"""Execute the real installer main with private fake tools; never access a disk."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "system_files/usr/libexec/moos-utm-net-install"


class InstallWriteOrder(unittest.TestCase):
    def run_case(self, signature=0, wipe=0, repair=False, occupied=0, allow=True):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binary = base / "bin"
            binary.mkdir()
            for command in ("cosign", "wipefs", "bootc", "lsblk"):
                path = binary / command
                code = signature if command == "cosign" else wipe if command == "wipefs" else 0
                path.write_text('#!/bin/sh\nprintf "%s\\n" "' + command + '" >> "$MOOS_INSTALL_TEST_CALLS"\nexit ' + str(code) + '\n')
                path.chmod(0o755)
            key = base / "public.key"
            key.write_text("synthetic public test key; fake cosign never reads it")
            source = SOURCE.read_text().rsplit('main "$@"', 1)[0]
            # Replace only host authority/read probes, preserving the production main.
            source += "\npick_target_disk() { printf '/dev/private-test-disk\\n'; }\n"
            source += "target_has_moos() { return 0; }\n"
            source += "target_has_data() { return " + str(occupied) + "; }\n"
            source += "resolve_digest() { printf 'sha256:" + "a" * 64 + "|44.20261008.1\\n'; }\n"
            source += "status() { printf '%s\\n' \"$1\" >&2; }\nlog() { :; }\nmain\n"
            helper = base / "probe.sh"
            helper.write_text(source)
            env = {**os.environ, "PATH": str(binary) + ":/usr/bin:/bin",
                   "MOOS_UTM_COSIGN_KEY": str(key), "MOOS_UTM_INSTALL_LOG": str(base / "install.log"),
                   "MOOS_UTM_ALLOW_REINSTALL": "0" if repair or not allow else "1",
                   "MOOS_UTM_REPAIR": "1" if repair else "0",
                   "MOOS_INSTALL_TEST_CALLS": str(base / "calls")}
            result = subprocess.run(["bash", str(helper)], env=env, text=True,
                                    capture_output=True, timeout=10)
            calls = (base / "calls").read_text().splitlines() if (base / "calls").exists() else []
            return result, calls

    def test_signature_failure_never_wipes_or_installs(self):
        result, calls = self.run_case(signature=9)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ["cosign"])

    def test_wipe_failure_stops_before_bootc(self):
        result, calls = self.run_case(wipe=7)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ["cosign", "wipefs"])

    def test_successful_reinstall_verifies_then_clears_then_installs(self):
        result, calls = self.run_case()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["cosign", "wipefs", "bootc"])

    def test_unimplemented_repair_is_not_success(self):
        result, calls = self.run_case(repair=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not implemented", result.stderr)
        self.assertEqual(calls, [])

    def test_existing_data_without_erase_consent_never_installs(self):
        result, calls = self.run_case(allow=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Existing target data", result.stderr)
        self.assertEqual(calls, [])

    def test_unreadable_layout_is_not_an_empty_disk(self):
        result, calls = self.run_case(occupied=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not be read", result.stderr)
        self.assertEqual(calls, [])

    def test_empty_disk_installs_without_a_preemptive_wipe(self):
        result, calls = self.run_case(occupied=1, allow=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, ["cosign", "bootc"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
