#!/usr/bin/env python3
"""Local biometric login must retain all vendor account/session/password rules."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fingerprint_login", ROOT / "build_files/configure_fingerprint_login.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
VENDOR = """auth     [success=done ignore=ignore default=bad] pam_selinux_permit.so
auth        substack      password-auth
-auth        optional      pam_kwallet5.so
auth        include       postlogin
account     required      pam_nologin.so
account     include       password-auth
password    include       password-auth
session     required      pam_selinux.so close
session     required      pam_loginuid.so
session     required      pam_selinux.so open
session     include       password-auth
session     include       postlogin
"""


class LocalBiometricLogin(unittest.TestCase):
    def test_only_local_auth_substack_changes(self):
        result = module.local_login(VENDOR)
        self.assertEqual(result.replace("substack      system-auth", "substack      password-auth"), VENDOR)
        self.assertNotIn("pam_permit.so", result)

    def test_missing_or_ambiguous_vendor_auth_refused(self):
        for text in (VENDOR.replace("password-auth", "custom-auth"),
                     VENDOR + "auth substack password-auth\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                module.local_login(text)

    def test_missing_account_password_or_session_rules_refused(self):
        for facility in ("account", "password", "session"):
            text = "\n".join(line for line in VENDOR.splitlines()
                             if not line.startswith(facility))
            with self.subTest(facility=facility), self.assertRaises(ValueError):
                module.local_login(text)

    def test_vendor_spacing_and_extra_rules_preserved(self):
        text = VENDOR.replace("auth        substack      password-auth", "auth\tsubstack\tpassword-auth  ")
        text += "session optional pam_limits.so\n"
        self.assertEqual(module.local_login(text), text.replace("substack\tpassword-auth", "substack\tsystem-auth"))

    def test_image_wires_setup_only_for_desktop(self):
        build = (ROOT / "build_files/build.sh").read_text()
        self.assertIn("if is_desktop; then\n    python3 /ctx/configure_fingerprint_login.py --apply --image", build)

    def test_custom_or_symlink_override_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "usr/lib/pam.d/plasmalogin"
            target = root / "etc/pam.d/plasmalogin"
            vendor.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            vendor.write_text(VENDOR)
            target.write_text("site-specific PAM\n")
            with self.assertRaisesRegex(ValueError, "customized"):
                module.plan(root)
            self.assertEqual(target.read_text(), "site-specific PAM\n")
            target.unlink()
            target.symlink_to(vendor)
            with self.assertRaisesRegex(ValueError, "symlink"):
                module.plan(root)

    def test_missing_vendor_and_already_configured_plans(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "usr/lib/pam.d/plasmalogin"
            target = root / "etc/pam.d/plasmalogin"
            vendor.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            vendor.write_text(VENDOR)
            self.assertEqual(module.plan(root), (target, module.local_login(VENDOR)))
            target.write_text(module.local_login(VENDOR))
            self.assertEqual(module.plan(root)[1], target.read_text())
            with self.assertRaisesRegex(ValueError, "actual OS root"):
                module.apply(root, run=lambda *a, **k: self.fail("host PAM must never run"))


if __name__ == "__main__":
    unittest.main()
