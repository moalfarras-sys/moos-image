#!/usr/bin/env python3
"""Arabic spell-check must exist in EVERY edition, from one shared implementation.

MEASURED ON THE LIVE ORACLE A1 (2026-09-06):

    /usr/share/qt6/qtwebengine_dictionaries/   24 en_*.bdic, ZERO ar_*.bdic
    coredumpctl                                6 x qwebengine_convert_dict SIGTRAP
    crash argv                                 .../ar_SD.dic -> .../ar_SD.bdic

The Arabic-speaking owner's own machine had no Arabic spell-check, on an OS
whose engineering skill calls Arabic first-class and whose AGENTS.md describes
this as a build-enforced contract. It WAS enforced — on x86 only.

Root cause of the crash, already documented by the x86 block: Chromium's
converter aborts on the hunspell IGNORE command ("We don't support the IGNORE
command yet", aff_reader.cc), and every Arabic .aff uses it to ignore tashkeel
(`IGNORE ًٌٍَُِّْـٰ` in ar_SD.aff, read off the live machine). x86 strips that
line into a temp copy and converts from there. ARM never got the block.

Root cause of the DIVERGENCE: the block was copied, not shared. So the fix is a
script both builds call, and this gate holds that shape — an inline copy growing
back in either build is the regression, not just a missing Arabic dictionary.

Proven live before shipping: the shared script run on the A1 built 50
dictionaries, 26 of them Arabic, and exited 0 through its own both-languages
assertion.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SHARED = REPO / "build_files/convert_webengine_dictionaries.sh"
BUILDS = ("build_files/build.sh", "build_files/build-arm.sh")


def code(text: str) -> str:
    """Drop shell comments; these files explain the bug in prose."""
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


class SharedImplementation(unittest.TestCase):
    def test_the_shared_script_exists_and_is_executable(self) -> None:
        self.assertTrue(SHARED.is_file(), "the shared converter script is missing")
        self.assertTrue(SHARED.stat().st_mode & 0o111,
                        "the shared converter script must be executable")

    def test_every_edition_calls_it(self) -> None:
        """x86 had this and ARM did not. Both must, or Arabic is edition-dependent."""
        for relative in BUILDS:
            body = code((REPO / relative).read_text(encoding="utf-8"))
            self.assertIn(
                "bash /ctx/convert_webengine_dictionaries.sh", body,
                f"{relative} must build the spell-check dictionaries; ARM went "
                f"months without this and shipped zero Arabic dictionaries")

    def test_no_edition_keeps_a_private_inline_copy(self) -> None:
        """The COPY is the bug. A second implementation is how they drifted."""
        for relative in BUILDS:
            body = code((REPO / relative).read_text(encoding="utf-8"))
            self.assertNotIn(
                "qwebengine_convert_dict", body,
                f"{relative} must not re-implement the converter inline — that "
                f"is exactly how x86 got the Arabic fix and ARM did not")


class TheScriptItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = SHARED.read_text(encoding="utf-8")
        cls.src = code(cls.raw)

    def test_it_strips_the_IGNORE_line_that_crashes_the_converter(self) -> None:
        self.assertIn('grep -q "^IGNORE"', self.src,
                      "without detecting IGNORE, every Arabic locale SIGTRAPs")
        self.assertIn('grep -v "^IGNORE"', self.src,
                      "the converter must read an .aff with IGNORE removed")

    def test_it_runs_the_converter_headless_and_unsandboxed(self) -> None:
        self.assertIn("QTWEBENGINE_DISABLE_SANDBOX=1", self.src)
        self.assertIn("QT_QPA_PLATFORM=offscreen", self.src,
                      "an image build has no display")

    def test_it_asserts_BOTH_languages_before_exiting(self) -> None:
        """English-only is the exact state ARM shipped, and it exits 0 silently."""
        self.assertRegex(self.src, r'en_US\.bdic[^\n]*\n[^\n]*exit 1')
        self.assertRegex(self.src, r'ar_\*\.bdic[^\n]*\n[^\n]*exit 1')

    def test_it_fails_loudly_rather_than_returning_a_count(self) -> None:
        self.assertIn("set -euo pipefail", self.src)
        self.assertIn("FATAL: no Arabic spell-check dictionary was produced.", self.src)

    def test_it_does_not_hardcode_the_output_directory(self) -> None:
        """It was verified live by writing to /var/tmp; keep that possible."""
        self.assertRegex(self.src, r'out="\$\{1:-')


if __name__ == "__main__":
    unittest.main(verbosity=2)
