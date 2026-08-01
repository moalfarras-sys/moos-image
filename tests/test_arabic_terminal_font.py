#!/usr/bin/env python3
"""Arabic terminal/editor font chain gates.

An Arabic user's terminal text must come out as connected cursive, not a row of
detached letters.  JetBrains Mono (the font every MoOS Konsole profile asks for
by name) has no Arabic glyphs at all, and every Arabic font Fedora ships is
proportional — so without a fixed-advance Arabic font in the fallback chain a
word like ``الطرفية`` renders as ``ا ل ط ر ف ي ة``, a word shattered into loose
letters (see the comment in system_files/etc/fonts/conf.d/61-moos-brand.conf).

The live contract is a chain, and a break at any link is invisible to the
source-only gates:

  * the rule file must be installed at /etc/fonts/conf.d/61-moos-brand.conf
  * ``fc-match -s "JetBrains Mono"`` must place Kawkab Mono in the fallback
  * the Kawkab Mono family must actually be resolvable on the system

The profile half (Konsole must keep asking for JetBrains Mono BY NAME so the
weak ``accept`` alias engages) is asserted from the repository side.
"""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]

FONTCONF_RULE = "/etc/fonts/conf.d/61-moos-brand.conf"
KONSOLE_DIR = ROOT / "system_files/usr/share/konsole"
ARABIC_FAMILY = "Kawkab Mono"


def fc_match_s(family: str) -> str:
    return subprocess.run(
        ["fc-match", "-s", family],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


class TestFontConfigRuleInstalled(unittest.TestCase):
    def test_rule_file_is_present(self) -> None:
        if not Path(FONTCONF_RULE).exists():
            self.skipTest("fontconfig rule not on this system (off-image host)")
        text = Path(FONTCONF_RULE).read_text(encoding="utf-8")
        self.assertIn("Kawkab Mono", text)
        self.assertIn("JetBrains Mono", text)

    def test_jetbrains_mono_falls_back_to_kawkab(self) -> None:
        if shutil.which("fc-match") is None:
            self.skipTest("fc-match not available")
        if not Path(FONTCONF_RULE).exists():
            self.skipTest("fontconfig rule not on this system (off-image host)")
        fallback = fc_match_s("JetBrains Mono")
        self.assertIn(
            ARABIC_FAMILY,
            fallback,
            f"fc-match -s 'JetBrains Mono' must list {ARABIC_FAMILY} so Arabic "
            "glyphs resolve to a fixed-advance face instead of detaching",
        )

    def test_arabic_family_is_resolvable(self) -> None:
        if shutil.which("fc-list") is None:
            self.skipTest("fc-list not available")
        out = subprocess.run(
            ["fc-list", f":lang=ar", "family"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertIn(ARABIC_FAMILY, out)


class TestKonsoleProfiles(unittest.TestCase):
    def test_profiles_ask_for_jetbrains_mono_by_name(self) -> None:
        profiles = sorted(KONSOLE_DIR.glob("*.profile"))
        self.assertGreaterEqual(len(profiles), 1, "expected MoOS Konsole profiles")
        for profile in profiles:
            text = profile.read_text(encoding="utf-8")
            match = re.search(r"^Font=([^,]+),", text, re.MULTILINE)
            self.assertIsNotNone(match, f"{profile.name}: missing Font= line")
            self.assertEqual(
                match.group(1),
                "JetBrains Mono",
                f"{profile.name}: font must be JetBrains Mono by name so the "
                f"weak fontconfig accept of {ARABIC_FAMILY} engages",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
