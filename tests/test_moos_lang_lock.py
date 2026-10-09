#!/usr/bin/env python3
"""A failed language lock must not change KDE, Flatpak or the owner's session."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class LanguageLock(unittest.TestCase):
    def test_busy_language_transaction_has_no_partial_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binary = base / "bin"
            binary.mkdir()
            for name in ("kwriteconfig6", "flatpak", "systemctl", "dbus-update-activation-environment"):
                path = binary / name
                path.write_text('#!/bin/sh\nprintf "%s\\n" "$0 $*" >> "$MOOS_LANG_TEST_CALLS"\n')
                path.chmod(0o755)
            lock = binary / "flock"
            lock.write_text("#!/bin/sh\nexit 1\n")
            lock.chmod(0o755)
            env = {**os.environ, "PATH": str(binary) + ":/usr/bin:/bin",
                   "MOOS_LANG_TEST_CALLS": str(base / "calls")}
            for suffix in ("CONFIG", "DATA", "STATE", "CACHE", "RUNTIME"):
                path = base / suffix.lower()
                path.mkdir()
                env["XDG_" + suffix + ("_DIR" if suffix == "RUNTIME" else "_HOME")] = str(path)
            result = subprocess.run(["bash", str(ROOT / "system_files/usr/bin/moos-lang"), "ar"],
                                    env=env, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((base / "calls").exists(), "a refused lock still changes the active session")
            self.assertFalse((base / "config/plasma-locale-settings.sh").exists())
            self.assertFalse((base / "state/moos-language").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
