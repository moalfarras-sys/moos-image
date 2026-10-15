#!/usr/bin/env python3
"""The Store window says what Mo Store now says, for the words that were corrected.

moos-storectl emits a stable message key and the window owns the words: jobText() shows the
window's phrase for a key whenever it has one, and the backend's English only when it has none
(tests/test_store_job_language.py holds the two key lists equal). So a corrected backend sentence
reaches nobody until the window's phrase changes with it. Each of these did not, while every gate
stayed green (one even pinned the false words):

  vendor_no_space         "installing this app briefly needs about three times its download size":
                          ChatGPT needs 7.5 times its 0.56 GB download on disk at once (package,
                          unpacked payload and installed tree), and 1.67 GB of it stays;
  downloading_file,       "Downloading a verified file" / "Downloading verified app": the size and
  downloading_android     digest are compared only after the last byte, and "Verified" is the
                          window's word for Flathub's own flag (docs/MO_STORE.md);
  removed_data_untracked  "Settings the app saved elsewhere ... were kept": its sign-in stays too
                          (ChatGPT's in its config folder, Claude Code's in ~/.claude), which is
                          what someone removing an app with its data to sign out must be told;
  android_not_running     new: a moos: link never starts Android app support.

And the window names the Store in Arabic as its launcher's Name[ar] does, «متجر MoOS»: not
«متجر Mo», and not a Latin "Mo Store" inside an Arabic sentence.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "system_files/usr/share/moos/apps/store"
QML = STORE / "main.qml"
ARABIC = re.compile(r"[؀-ۿ]")


def job_phrases() -> dict[str, tuple[str, str]]:
    """main.qml's jobPhrases, read as tests/test_store_job_language.py reads them."""
    block = re.search(r"readonly property var jobPhrases: \(\{(.*?)\n    \}\)",
                      QML.read_text(encoding="utf-8"), re.S)
    if block is None:
        raise AssertionError("main.qml lost the jobPhrases map")
    return {match.group(1): (match.group(2), match.group(3))
            for match in re.finditer(r'"([a-z_]+)":\s*\["([^"]+)",\s*"([^"]+)"\]', block.group(1))}


PHRASES = job_phrases()


class CorrectedWords(unittest.TestCase):
    def phrase(self, key: str) -> tuple[str, str]:
        self.assertIn(key, PHRASES, f"the window has no words for {key}")
        return PHRASES[key]

    def test_no_space_names_no_false_multiple_and_no_briefly(self):
        arabic, english = self.phrase("vendor_no_space")
        for false in ("three times", "briefly"):
            self.assertNotIn(false, english)
        for false in ("ثلاثة أضعاف", "مؤقت"):
            self.assertNotIn(false, arabic)

    def test_a_download_is_not_called_verified_before_it_is(self):
        for key in ("downloading_file", "downloading_android"):
            with self.subTest(key=key):
                arabic, english = self.phrase(key)
                self.assertNotIn("verified", english.lower())
                self.assertIsNone(re.search(r"موث[ّ]?ق", arabic), arabic)

    def test_remove_with_data_names_the_sign_in_it_kept(self):
        arabic, english = self.phrase("removed_data_untracked")
        self.assertIn("sign-in", english)
        self.assertIn("تسجيل دخول", arabic)

    def test_a_link_that_cannot_start_android_says_so(self):
        arabic, english = self.phrase("android_not_running")
        self.assertIn("not running", english)
        self.assertIn("غير مشغّل", arabic)


class TheStoresArabicName(unittest.TestCase):
    def test_every_arabic_string_of_the_window_says_mo_store_as_its_launcher_does(self):
        files = sorted(path for path in STORE.rglob("*") if path.suffix in (".qml", ".js"))
        self.assertIn(QML, files)
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for text in re.findall(r'"([^"\n]*)"', line):
                    if not ARABIC.search(text):
                        continue
                    with self.subTest(file=path.relative_to(ROOT).as_posix(), line=number):
                        self.assertIsNone(re.search(r"متجر Mo(?!OS)", text), text)
                        self.assertNotIn("Mo Store", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
