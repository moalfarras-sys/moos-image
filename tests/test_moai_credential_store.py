#!/usr/bin/env python3
"""Behavioural gates for Mo AI's wallet-free credential store."""

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "system_files/usr/libexec/moai-credential-store"


class CredentialStoreTests(unittest.TestCase):
    def run_store(
        self,
        path: Path,
        action: str,
        value: bytes = b"",
    ) -> subprocess.CompletedProcess[bytes]:
        env = dict(os.environ)
        env["MOAI_CREDENTIAL_FILE"] = str(path)
        return subprocess.run(
            [str(STORE), action],
            input=value,
            capture_output=True,
            check=False,
            env=env,
        )

    def test_round_trip_is_private_and_never_enters_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "data/moai/private/cloud-api-key"
            secret = b"test-provider-key"

            self.assertEqual(self.run_store(path, "set", secret).returncode, 0)
            self.assertEqual(self.run_store(path, "get").stdout, secret)
            self.assertEqual(self.run_store(path, "has").returncode, 0)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            self.assertFalse((root / "config/moai/config.json").exists())

    def test_replacement_and_clear_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "private/cloud-api-key"
            self.assertEqual(self.run_store(path, "set", b"old").returncode, 0)
            self.assertEqual(self.run_store(path, "set", b"new").returncode, 0)
            self.assertEqual(self.run_store(path, "get").stdout, b"new")
            self.assertEqual(self.run_store(path, "set", b"").returncode, 1)
            self.assertEqual(self.run_store(path, "clear").returncode, 0)
            self.assertEqual(self.run_store(path, "has").returncode, 1)

    def test_symlink_is_never_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            private = root / "private"
            private.mkdir()
            target = root / "target"
            target.write_bytes(b"do-not-read")
            link = private / "cloud-api-key"
            link.symlink_to(target)

            self.assertEqual(self.run_store(link, "get").returncode, 1)
            self.assertEqual(target.read_bytes(), b"do-not-read")


if __name__ == "__main__":
    unittest.main(verbosity=2)
