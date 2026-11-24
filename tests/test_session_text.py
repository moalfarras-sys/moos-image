#!/usr/bin/env python3
"""The login and lock screens speak current Arabic, presentation only.

Executes the real org.moos.ui SessionText.js in a Qt JS engine:
* pam_fprintd's English prompts (the login daemon runs PAM in the C locale)
  and its half-translated ones are presented in Arabic on an Arabic session;
* plasma_login's dated captions agree with the MoOS power screen;
* unknown text, every non-Arabic session and empty input pass unchanged;
* a notice joined with " • " is presented part by part.
The mapped plasma_login strings are checked against the installed Arabic
catalogue when it exists, so a vendor translation change is noticed.
"""
import gettext
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui/SessionText.js"


class SessionText(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (1, 1))  # never a host crash report
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            raise unittest.SkipTest("Qt JS engine unavailable")
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.engine = QJSEngine()
        result = cls.engine.evaluate(SOURCE.read_text(encoding="utf-8").replace(".pragma library", ""))
        assert not result.isError(), result.toString()

    def present(self, text, arabic=True):
        import json
        value = self.engine.evaluate(f"present({json.dumps(text)}, {'true' if arabic else 'false'})")
        self.assertFalse(value.isError(), value.toString())
        return value.toString()

    def test_fingerprint_prompts_are_arabic_on_an_arabic_session(self):
        self.assertEqual(self.present("Place your right index finger on the fingerprint reader"),
                         "ضع سبابتك اليمنى على قارئ البصمة")
        self.assertEqual(self.present("Swipe your left thumb across the fingerprint reader"),
                         "مرّر إبهامك الأيسر على قارئ البصمة")
        self.assertEqual(self.present("Place your finger on the fingerprint reader"),
                         "ضع إصبعك على قارئ البصمة")
        self.assertEqual(self.present("Failed to match fingerprint"), "لم تتطابق البصمة، حاول مرة أخرى")
        self.assertEqual(self.present("ضع سبابتك اليمنى على the fingerprint reader"),
                         "ضع سبابتك اليمنى على قارئ البصمة")
        # A device name that is not the generic phrase is kept as the reader's name.
        self.assertEqual(self.present("Place your right thumb on Goodix MOC"), "ضع إبهامك الأيمن على Goodix MOC")

    def test_every_pam_fprintd_message_with_a_finger_is_covered(self):
        module = Path("/usr/lib64/security/pam_fprintd.so")
        if not module.is_file():
            self.skipTest("pam_fprintd not installed here")
        import subprocess
        strings = subprocess.run(["strings", str(module)], capture_output=True, text=True).stdout.splitlines()
        prompts = [s for s in strings if re.match(r"^(Place|Swipe) your .+ (on|across) the fingerprint reader$", s)]
        self.assertGreaterEqual(len(prompts), 20)
        for prompt in prompts:
            with self.subTest(prompt=prompt):
                self.assertRegex(self.present(prompt), r"[؀-ۿ]")
                self.assertNotIn("finger", self.present(prompt))

    def test_session_captions_match_the_power_screen(self):
        expected = {
            "أعد التّشغيل": "إعادة التشغيل", "أطفئ": "إيقاف التشغيل", "علّق": "السكون",
            "أسبِت": "إسبات", "مستخدم أخر…": "مستخدم آخر…", "فشل الولوج": "تعذّر تسجيل الدخول",
        }
        for vendor, modern in expected.items():
            self.assertEqual(self.present(vendor), modern)
        power = (ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui/SessionPower.qml").read_text(encoding="utf-8")
        for word in ("إعادة التشغيل", "إيقاف التشغيل", "السكون", "إسبات"):
            self.assertIn(word, power, "the login and power screens must use the same words")

    def test_only_arabic_locales_select_arabic_text(self):
        for name in ("ar", "ar_SA", "ar-EG", "he_IL", "fa_IR", "ur_PK", "en_US"):
            actual = self.engine.evaluate("isArabic('" + name + "')")
            self.assertFalse(actual.isError())
            self.assertEqual(actual.toBool(), name.startswith("ar"), name)

    def test_unknown_text_and_non_arabic_sessions_pass_unchanged(self):
        for text in ("", "Login Failed", "Place your right index finger on the fingerprint reader", "Caps Lock is on"):
            self.assertEqual(self.present(text, arabic=False), text)
        self.assertEqual(self.present("Some other PAM message"), "Some other PAM message")
        self.assertEqual(self.present("MoOS"), "MoOS")
        unknown = "عطل آخر في the fingerprint reader"
        self.assertEqual(self.present(unknown), unknown)

    def test_a_joined_notice_is_presented_part_by_part(self):
        self.assertEqual(self.present("مفتاح Caps Lock مفعّل • Failed to match fingerprint"),
                         "مفتاح Caps Lock مفعّل • لم تتطابق البصمة، حاول مرة أخرى")

    def test_mapped_captions_are_the_installed_vendor_arabic(self):
        try:
            catalog = gettext.translation("plasma_login", "/usr/share/locale", languages=["ar"])
        except OSError:
            self.skipTest("plasma_login Arabic catalogue not installed here")
        vendor = {
            catalog.gettext("Restart"), catalog.gettext("Shut Down"), catalog.gettext("Login Failed"),
            catalog.pgettext("Suspend to RAM", "Sleep"), catalog.pgettext("Suspend to disk", "Hibernate"),
            catalog.pgettext("For switching to a username and password prompt", "Other…"),
        }
        for text in vendor:
            with self.subTest(vendor=text):
                self.assertNotEqual(self.present(text), text,
                                    "plasma_login's Arabic changed; review SessionText's mapping")


if __name__ == "__main__":
    unittest.main()
