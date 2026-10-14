#!/usr/bin/env python3
"""Gate: in Arabic, Mo Store is «متجر MoOS» in what Mo AI's tools say about it.

WHY THIS EXISTS
The Store's launcher (Name[ar]), its search-bar entry, its update notifications and What's new
call it «متجر MoOS». The Store library work added Arabic tool texts that called it «متجر Mo»
(install_app and uninstall_app), beside older Arabic card texts that kept the Latin "Mo Store"
inside an Arabic sentence ("يُثبَّت التطبيق لحسابك عبر Mo Store ثم يُفتح."): an Arabic speaker
met three names for one app, the card Mira shows before an install among them. English keeps
"Mo Store".

This reads every Mo AI tool the way the model and the confirmation card do: each Arabic
consequence, and the Arabic half of every description and argument description.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moai"))

from moai_tool_schemas import ALL_TOOLS, consequence  # noqa: E402

ARABIC = re.compile(r"[ء-ي]")
OTHER_NAMES = re.compile(r"Mo Store|متجر Mo(?!OS)")


def arabic_halves(text: str) -> list[str]:
    """The Arabic parts of a bilingual "English — Arabic" text."""
    return [part for part in text.split(" — ") if ARABIC.search(part)]


class TheStoreHasOneArabicName(unittest.TestCase):
    def test_every_arabic_tool_text_names_the_store_one_way(self):
        found = []
        for tool in ALL_TOOLS:
            function = tool["function"]
            name = function["name"]
            texts = [("consequence", consequence(name, "ar"))]
            texts += [("description", part) for part in arabic_halves(function["description"])]
            for argument, spec in (function.get("parameters") or {}).get("properties", {}).items():
                texts += [(argument, part) for part in arabic_halves(spec.get("description", ""))]
            found += [(name, where, text) for where, text in texts if OTHER_NAMES.search(text)]
        self.assertEqual(found, [], "the Store is «متجر MoOS» in Arabic")

    def test_the_cards_that_name_the_store_still_name_it(self):
        """The rule must not pass by dropping the name: these cards are about the Store."""
        for name in ("install_app", "uninstall_app", "update_apps"):
            with self.subTest(tool=name):
                self.assertIn("متجر MoOS", consequence(name, "ar"))
                self.assertIn("Mo Store", consequence(name, "en"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
