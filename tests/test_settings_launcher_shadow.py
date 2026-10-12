#!/usr/bin/env python3
"""XDG precedence and recoverable legacy migration without the owner's desktop."""
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("launcher_tested", ROOT / "system_files/usr/lib/moos/moos_settings_launcher.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)
ENTRY = "[Desktop Entry]\nType=Application\nName=MoOS Settings\nName[ar]=إعدادات MoOS\nExec=moos-settings\nIcon=moos-control-center\nStartupWMClass=systemsettings\n"


class LauncherShadow(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.roots = [Path(temporary.name) / "user", Path(temporary.name) / "image"]
        for root in self.roots:
            (root / "applications").mkdir(parents=True)
        self.official = self.roots[1] / "applications" / M.CANONICAL
        self.official.write_text(ENTRY)
        self.shadow = self.roots[0] / "applications" / M.CANONICAL

    def test_image_visibility_is_not_account_visibility(self):
        M.check(self.roots)
        self.shadow.write_text(ENTRY + "NoDisplay=true\n")
        M.check(self.roots[1:])  # The old image-only gate stays green.
        with self.assertRaisesRegex(ValueError, "hidden"):
            M.check(self.roots)

    def test_second_visible_alias_and_wrong_identity_fail(self):
        alias = self.roots[0] / "applications" / M.ALIASES[0]
        alias.write_text(ENTRY)
        with self.assertRaisesRegex(ValueError, "second"):
            M.check(self.roots)
        alias.write_text(ENTRY + "NoDisplay=true\n")
        M.check(self.roots)
        self.shadow.write_text(ENTRY.replace("Exec=moos-settings", "Exec=systemsettings"))
        with self.assertRaisesRegex(ValueError, "bypasses"):
            M.check(self.roots)

    def test_reviewed_shadow_is_preserved_and_repair_is_idempotent(self):
        legacy = b"[Desktop Entry]\nName=System Settings\nExec=systemsettings\nNoDisplay=true\n"
        self.shadow.write_bytes(legacy)
        reviewed = frozenset({hashlib.sha256(legacy).hexdigest()})
        with patch.object(M, "LEGACY_HIDDEN", reviewed):
            backup = M.repair(self.roots)
            self.assertEqual(backup.read_bytes(), legacy)
            self.assertFalse(self.shadow.exists())
            M.check(self.roots)
            self.assertIsNone(M.repair(self.roots))
        self.assertEqual(backup.parent.stat().st_mode & 0o777, 0o700)

    def test_unknown_override_is_preserved_and_missing_replacement_refuses(self):
        self.shadow.write_text(ENTRY + "NoDisplay=true\n")
        self.assertIsNone(M.repair(self.roots))
        self.assertTrue(self.shadow.exists())
        self.official.unlink()
        with self.assertRaises(ValueError):
            M.repair(self.roots)
        self.assertTrue(self.shadow.exists())

    def test_fifo_broken_link_and_oversized_entry_fail_without_blocking(self):
        os.mkfifo(self.shadow)
        with self.assertRaises(ValueError):
            M.check(self.roots)
        self.shadow.unlink()
        self.shadow.symlink_to(self.roots[0] / "missing")
        with self.assertRaises(OSError):
            M.check(self.roots)
        self.shadow.unlink()
        self.shadow.write_bytes(b" " * (M.MAX_ENTRY + 1))
        with self.assertRaises(ValueError):
            M.check(self.roots)

    def test_migration_precedes_the_applied_revision_fast_path(self):
        source = (ROOT / "system_files/usr/bin/moos-apply-theme").read_text()
        self.assertLess(source.index('python3 "$settings_launcher_helper" repair'),
                        source.index('\nmigration_completed=false\n'))
        selfcheck = (ROOT / "system_files/usr/bin/moos-selfcheck").read_text()
        self.assertIn('python3 "$settings_launcher_helper" check', selfcheck)


if __name__ == "__main__":
    unittest.main(verbosity=2)
