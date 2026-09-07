#!/usr/bin/env python3
"""Execute the /usr/local build repair against Atomic and bootc layouts.

x86 run 769 failed in every edition: /usr/local is a dangling symlink into
machine-local /var, so installing /usr/local/sbin at compose time fails.
ARM has a real immutable /usr/local directory and needs that install.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def repair_block(script: str) -> str:
    source = (ROOT / "build_files" / script).read_text()
    start = source.index("# ── /usr/local/sbin:")
    end = source.index("# ── The Plasma shell overlay", start)
    return source[start:end]


class UsrLocalLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="moos-usr-local-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "usr/lib/tmpfiles.d").mkdir(parents=True)
        (self.root / "var").mkdir()
        self.local = self.root / "usr/local"
        self.rules = self.root / "usr/lib/tmpfiles.d/rpm-ostree-0-integration.conf"
        self.rules.write_text(f"d {self.local}/sbin 0755 root root -\n")
        self.parent_rules = self.root / "usr/lib/tmpfiles.d/rpm-ostree-0-integration-opt-usrlocal.conf"
        self.parent_rules.write_text("d /var/usrlocal 0755 root root -\n")

    def run_repair(self, script="build.sh"):
        # Only filesystem operands are redirected; execute the shipping shell
        # block with real install/readlink/grep, never a copied implementation.
        block = repair_block(script)
        block = block.replace("/usr/lib/tmpfiles.d/", str(self.root / "usr/lib/tmpfiles.d") + "/")
        block = block.replace("/usr/local", str(self.local))
        return subprocess.run(
            ["bash", "-eu", "-c", block], capture_output=True, text=True,
            env=os.environ | {"LC_ALL": "C"},
        )

    def test_atomic_dangling_symlink_keeps_var_empty(self):
        self.local.symlink_to("../var/usrlocal")
        result = self.run_repair()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(os.readlink(self.local), "../var/usrlocal")
        self.assertEqual(list((self.root / "var").iterdir()), [])

    def test_atomic_populated_symlink_preserves_local_content(self):
        target = self.root / "var/usrlocal"
        target.mkdir()
        (target / "owner-file").write_text("preserve\n")
        self.local.symlink_to("../var/usrlocal")
        result = self.run_repair()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(os.readlink(self.local), "../var/usrlocal")
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["owner-file"])
        self.assertEqual((target / "owner-file").read_text(), "preserve\n")

    @unittest.skipUnless(shutil.which("systemd-tmpfiles"), "systemd-tmpfiles unavailable")
    def test_atomic_sbin_is_created_at_boot(self):
        self.local.symlink_to("../var/usrlocal")
        result = self.run_repair()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(list((self.root / "var").iterdir()), [])
        # Now boot the tmpfiles rule with systemd's real symlink resolution.
        # --root confines even absolute paths to this disposable filesystem.
        # Preserve the invoking user's ownership so the test needs no root.
        self.parent_rules.write_text("d /var/usrlocal 0755 - - -\n")
        self.rules.write_text("d /usr/local/sbin 0755 - - -\n")
        result = subprocess.run(
            ["systemd-tmpfiles", f"--root={self.root}", "--create"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(os.readlink(self.local), "../var/usrlocal")
        self.assertEqual((self.root / "var/usrlocal/sbin").stat().st_mode & 0o777, 0o755)

    def test_real_directory_gets_sbin_on_both_build_paths(self):
        self.local.mkdir()
        (self.local / "bin").mkdir()
        for script in ("build.sh", "build-arm.sh"):
            with self.subTest(script=script):
                result = self.run_repair(script)
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertFalse(self.local.is_symlink())
                self.assertEqual((self.local / "sbin").stat().st_mode & 0o777, 0o755)
                self.assertTrue((self.local / "bin").is_dir())
                (self.local / "sbin").rmdir()

    def test_unexpected_symlink_fails_closed(self):
        self.local.symlink_to("../unexpected")
        result = self.run_repair()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(self.local), "../unexpected")

    def test_missing_boot_time_sbin_rule_fails_closed(self):
        self.local.symlink_to("../var/usrlocal")
        self.rules.write_text(f"# d {self.local}/sbin 0755 root root -\n")
        result = self.run_repair()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list((self.root / "var").iterdir()), [])

    def test_missing_boot_time_parent_rule_fails_closed(self):
        self.local.symlink_to("../var/usrlocal")
        self.parent_rules.unlink()
        result = self.run_repair()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list((self.root / "var").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
