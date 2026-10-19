#!/usr/bin/env python3
"""Local biometric login must retain all vendor account/session/password rules."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
import ctypes
import ctypes.util
import re

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
SYSTEM_AUTH = """# generated fixture
auth required pam_env.so
auth required pam_faildelay.so delay=2000000
auth sufficient pam_fprintd.so
auth sufficient pam_unix.so nullok
auth required pam_deny.so
account required pam_unix.so
password sufficient pam_unix.so yescrypt shadow
session required pam_unix.so
"""


class LocalBiometricLogin(unittest.TestCase):
    def test_only_local_auth_substack_changes(self):
        result = module.local_login(VENDOR)
        self.assertEqual(result.replace("substack      " + module.GREETER_STACK, "substack      password-auth"), VENDOR)
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
        self.assertEqual(module.local_login(text), text.replace("substack\tpassword-auth", "substack\t" + module.GREETER_STACK))

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

    def test_previous_managed_system_auth_override_can_migrate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "usr/lib/pam.d/plasmalogin"
            target = root / "etc/pam.d/plasmalogin"
            vendor.parent.mkdir(parents=True)
            target.parent.mkdir(parents=True)
            vendor.write_text(VENDOR)
            target.write_text(VENDOR.replace("substack      password-auth", "substack      system-auth"))
            self.assertEqual(module.plan(root), (target, module.local_login(VENDOR)))

    def test_only_the_adjacent_sufficient_alternatives_move(self):
        result = module.greeter_auth(SYSTEM_AUTH)
        body = result[result.index("# generated fixture"):]
        expected = SYSTEM_AUTH.replace("auth sufficient pam_fprintd.so\nauth sufficient pam_unix.so nullok\n",
                                       "auth sufficient pam_unix.so nullok\nauth sufficient pam_fprintd.so max_tries=1 timeout=8\n")
        self.assertEqual(body, expected)
        self.assertNotIn("pam_permit.so", result)

    def test_unknown_missing_duplicate_required_or_lockout_policy_is_refused(self):
        for text in (SYSTEM_AUTH.rstrip(),
                     SYSTEM_AUTH.replace("pam_fprintd.so", "custom-reader.so"),
                     SYSTEM_AUTH.replace("sufficient pam_unix", "required pam_unix"),
                     SYSTEM_AUTH + "auth sufficient pam_unix.so\n",
                     SYSTEM_AUTH + "auth [success=1 default=ignore] pam_unix.so\n",
                     SYSTEM_AUTH.replace("pam_fprintd.so", "pam_fprintd.so timeout=30"),
                     SYSTEM_AUTH + "auth required pam_faillock.so authfail\n",
                     SYSTEM_AUTH + "auth sufficient pam_sss.so\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                module.greeter_auth(text)

    def test_derived_stack_preserves_customization_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pam = root / "etc/pam.d"
            pam.mkdir(parents=True)
            (pam / "system-auth").write_text(SYSTEM_AUTH)
            target = pam / module.GREETER_STACK
            self.assertEqual(module.stack_plan(root), (target, module.greeter_auth(SYSTEM_AUTH)))
            target.write_text(module.greeter_auth(SYSTEM_AUTH, bounded=False))
            self.assertEqual(module.stack_plan(root), (target, module.greeter_auth(SYSTEM_AUTH)))
            target.write_text("site-specific policy\n")
            with self.assertRaisesRegex(ValueError, "customized"):
                module.stack_plan(root)
            self.assertEqual(target.read_text(), "site-specific policy\n")
            target.unlink()
            target.symlink_to(pam / "system-auth")
            with self.assertRaisesRegex(ValueError, "symlink"):
                module.stack_plan(root)

    def test_readonly_policy_check_requires_both_exact_current_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "usr/lib/pam.d/plasmalogin"
            pam = root / "etc/pam.d"
            vendor.parent.mkdir(parents=True)
            pam.mkdir(parents=True)
            vendor.write_text(VENDOR)
            (pam / "system-auth").write_text(SYSTEM_AUTH)
            target = pam / "plasmalogin"
            derived = pam / module.GREETER_STACK
            target.write_text(module.local_login(VENDOR))
            derived.write_text(module.greeter_auth(SYSTEM_AUTH))
            before = {p: p.read_bytes() for p in (vendor, target, derived, pam / "system-auth")}
            module.check_configuration(root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            for contents in (module.greeter_auth(SYSTEM_AUTH, bounded=False), "custom policy\n", ""):
                with self.subTest(contents=contents):
                    derived.write_text(contents)
                    with self.assertRaises(ValueError):
                        module.check_configuration(root)
                    self.assertEqual(derived.read_text(), contents)
            derived.unlink()
            with self.assertRaises(ValueError):
                module.check_configuration(root)
            derived.write_text(module.greeter_auth(SYSTEM_AUTH))
            target.write_text(VENDOR)
            with self.assertRaises(ValueError):
                module.check_configuration(root)


class NativePamOrdering(unittest.TestCase):
    """Exercise the real PAM control engine on private, synthetic module results."""

    @classmethod
    def setUpClass(cls):
        library = ctypes.util.find_library("pam")
        if not library:
            raise unittest.SkipTest("native libpam is unavailable")
        cls.pam = ctypes.CDLL(library)
        if not hasattr(cls.pam, "pam_start_confdir"):
            raise unittest.SkipTest("native PAM lacks private confdir support")
        paths = [Path(p) for p in ("/usr/lib64/security/pam_exec.so", "/lib/x86_64-linux-gnu/security/pam_exec.so",
                                  "/lib/aarch64-linux-gnu/security/pam_exec.so", "/usr/lib/security/pam_exec.so")]
        cls.pam_exec = next((p for p in paths if p.is_file()), None)
        if cls.pam_exec is None:
            raise unittest.SkipTest("native pam_exec fixture module is unavailable")

    def authenticate(self, stack, password_ok, fingerprint_ok):
        with tempfile.TemporaryDirectory(prefix="moos-private-pam-") as directory:
            root = Path(directory)
            events = root / "events"
            helper = root / "module-result"
            helper.write_text('#!/bin/sh\nprintf "%s\\n" "$2" >> "$1"\nexit "$3"\n')
            helper.chmod(0o700)
            results = {"unix": int(not password_ok), "fprintd": int(not fingerprint_ok), "deny": 1}
            def replace(match):
                name = match[1]
                return f"{self.pam_exec} quiet {helper} {events} {name} {results.get(name, 0)}"
            private = re.sub(r"pam_(\w+)\.so[^\n]*", replace, stack)
            (root / module.GREETER_STACK).write_text(private)
            # Only our substack is exercised. No real account, password, reader,
            # environment, host configuration or system authentication is accessed.
            (root / "moos-fixture").write_text(f"auth substack {module.GREETER_STACK}\n")
            callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_void_p,
                                            ctypes.c_void_p, ctypes.c_void_p)
            callback = callback_type(lambda *args: 19)  # no secret prompts allowed
            class Conversation(ctypes.Structure):
                _fields_ = [("conv", callback_type), ("data", ctypes.c_void_p)]
            conv = Conversation(callback, None)
            handle = ctypes.c_void_p()
            self.pam.pam_start_confdir.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                                 ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p]
            self.pam.pam_authenticate.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.pam.pam_end.argtypes = [ctypes.c_void_p, ctypes.c_int]
            result = self.pam.pam_start_confdir(b"moos-fixture", b"synthetic-owner", ctypes.byref(conv),
                                               str(root).encode(), ctypes.byref(handle))
            self.assertEqual(result, 0)
            try:
                result = self.pam.pam_authenticate(handle, 0)
            finally:
                self.pam.pam_end(handle, result)
            return result, events.read_text().splitlines() if events.exists() else []

    def test_valid_supplied_password_never_starts_reader(self):
        result, events = self.authenticate(module.greeter_auth(SYSTEM_AUTH), True, True)
        self.assertEqual(result, 0, events)
        self.assertEqual(events, ["env", "faildelay", "unix"])

    def test_valid_password_succeeds_even_when_reader_cannot_authenticate(self):
        result, events = self.authenticate(module.greeter_auth(SYSTEM_AUTH), True, False)
        self.assertEqual(result, 0, events)
        self.assertNotIn("fprintd", events)

    def test_old_order_starts_reader_even_with_valid_supplied_password(self):
        result, events = self.authenticate(SYSTEM_AUTH, True, True)
        self.assertEqual(result, 0, events)
        self.assertIn("fprintd", events)
        self.assertNotIn("unix", events)

    def test_empty_or_incorrect_password_can_use_fingerprint_alone(self):
        result, events = self.authenticate(module.greeter_auth(SYSTEM_AUTH), False, True)
        self.assertEqual(result, 0, events)
        self.assertEqual(events, ["env", "faildelay", "unix", "fprintd"])

    def test_both_methods_failing_never_authenticate(self):
        result, events = self.authenticate(module.greeter_auth(SYSTEM_AUTH), False, False)
        self.assertNotEqual(result, 0, events)
        self.assertEqual(events, ["env", "faildelay", "unix", "fprintd", "deny"])


if __name__ == "__main__":
    unittest.main()
