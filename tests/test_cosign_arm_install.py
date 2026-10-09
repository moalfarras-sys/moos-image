#!/usr/bin/env python3
"""Execute the pinned verifier installer with private downloads and destination."""
import hashlib
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build_files/install_cosign_arm.sh"
PIN = "c5d324e091826b0d7a78eb16fef316450b4eb9aaec045611c08ba06f5e73220a"


class CosignArmInstall(unittest.TestCase):
    def probe(self, *, match=True, download_code=0, version="3.1.3", platform="linux/arm64"):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binary = base / "bin"
            binary.mkdir()
            asset = base / "asset"
            asset.write_text('#!/bin/sh\nprintf "executed\\n" >> "$MOOS_COSIGN_TEST_EXEC"\n'
                             'printf "GitVersion:    v' + version + '\\nPlatform:      ' + platform + '\\n"\n')
            curl = binary / "curl"
            curl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" > "$MOOS_COSIGN_TEST_ARGS"\n'
                            'while [ "$#" -gt 0 ]; do\n'
                            ' if [ "$1" = -o ]; then shift; /bin/cp "$MOOS_COSIGN_TEST_ASSET" "$1"; break; fi\n'
                            ' shift\ndone\nexit "$MOOS_COSIGN_TEST_EXIT"\n')
            curl.chmod(0o755)
            source = SOURCE.read_text()
            if match:
                # A private copy validates the synthetic asset's digest. The
                # committed pin is independently checked below and never changed.
                source = source.replace(PIN, hashlib.sha256(asset.read_bytes()).hexdigest())
            helper = base / "install.sh"
            helper.write_text(source)
            destination = base / "cosign"
            destination.write_text("original verifier")
            env = {**os.environ, "PATH": str(binary) + ":/usr/bin:/bin", "TMPDIR": str(base),
                   "MOOS_COSIGN_TEST_ASSET": str(asset), "MOOS_COSIGN_TEST_EXIT": str(download_code),
                   "MOOS_COSIGN_TEST_ARGS": str(base / "arguments"),
                   "MOOS_COSIGN_TEST_EXEC": str(base / "executed")}
            result = subprocess.run(["bash", str(helper), str(destination)], env=env,
                                    text=True, capture_output=True, timeout=5)
            return result, destination.read_text(), (base / "executed").exists(), (base / "arguments").read_text()

    def test_mismatched_bytes_are_never_executed_or_installed(self):
        result, contents, executed, _ = self.probe(match=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(executed)
        self.assertEqual(contents, "original verifier")

    def test_failed_download_never_executes_partial_bytes(self):
        result, contents, executed, _ = self.probe(download_code=7)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(executed)
        self.assertEqual(contents, "original verifier")

    def test_wrong_version_or_architecture_never_replaces_verifier(self):
        for arguments in ({"version": "2.4.1"}, {"platform": "linux/amd64"}):
            with self.subTest(arguments=arguments):
                result, contents, _, _ = self.probe(**arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(contents, "original verifier")

    def test_valid_download_uses_bounded_https_and_installs(self):
        result, contents, executed, arguments = self.probe()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(executed)
        self.assertIn("GitVersion:", contents)
        for expected in ("--connect-timeout 15", "--max-time 600", "--proto =https", "--proto-redir =https"):
            self.assertIn(expected, arguments)

    def test_both_builds_use_one_reviewed_pin(self):
        source = SOURCE.read_text()
        self.assertEqual(re.findall(r'^digest="([a-f0-9]{64})"$', source, re.M), [PIN])
        self.assertIn('version="3.1.3"', source)
        self.assertIn('bash /ctx/install_cosign_arm.sh /usr/bin/cosign', (ROOT / 'build_files/build-arm.sh').read_text())
        self.assertIn('bash /usr/libexec/moos-install-cosign-arm.sh /usr/bin/cosign', (ROOT / 'build_files/build-arm-recovery.sh').read_text())
        self.assertIn('COPY --from=ctx /install_cosign_arm.sh /usr/libexec/moos-install-cosign-arm.sh',
                      (ROOT / 'Containerfile.arm-recovery').read_text())
        for path in ('build_files/build-arm.sh', 'build_files/build-arm-recovery.sh'):
            self.assertNotIn('2.4.1', (ROOT / path).read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
