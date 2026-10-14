#!/usr/bin/env python3
"""Gate: the Mo Store card in What's new promises only what every edition's Store offers.

WHY THIS EXISTS
The `mo-store-library` entry names no `arch`, so MoOS Settings shows it, and
moos-whats-new-notify announces it, on the x86 desktop, the NVIDIA edition, every moos-cloud
machine and the ARM edition alike; `arch` could not narrow it anyway, because moos-cloud is
x86_64 too. Its first body promised "More than 170 hand-picked apps … Windows programs and
Android apps". Read through the indexer's own load_catalog() (the filter every Store applies),
the x86 desktop offers 172 apps, moos-cloud 145 and moos-arm 119, and neither of the last two
offers one Windows program or Android app: their images ship no runtime for either (build.sh
installs wine and waydroid on desktop editions only; build-arm.sh installs neither). The Oracle
A1 would have been told about apps its Store does not have.

So the card is read the way each edition's Store reads the catalogue:
  * a number of apps it states is one the edition that offers fewest can show;
  * an app it names (by its catalogue name) is offered on every edition;
  * Windows programs and Android apps are promised only "on the PCs that can run them" while
    an edition offers none.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
WHATS_NEW = ROOT / "system_files/usr/share/moos/whats-new.json"
CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"
INDEXER = ROOT / "system_files/usr/bin/moos-store-index"
ENTRY = "mo-store-library"
# What each edition's Store can run: the x86 desktop (and NVIDIA) ship both runtimes; moos-cloud
# and moos-arm ship neither (an owner who adds the optional Windows engine to moos-cloud gains its
# Windows programs, which "on the PCs that can run them" already covers).
EDITIONS = {"x86 desktop": ("x86_64", {"windows", "android"}),
            "moos-cloud": ("x86_64", set()),
            "moos-arm": ("aarch64", set())}
# A product the card names by a shorter name than any one catalogue entry.
SHORT_NAMES = {"Antigravity": {"antigravity", "antigravity-ide"}}
CONDITION = {"en": "that can run them", "ar": "التي تستطيع تشغيلها"}
FOREIGN = {"windows": {"en": "Windows programs", "ar": "برامج ويندوز"},
           "android": {"en": "Android apps", "ar": "تطبيقات أندرويد"}}
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_editions", str(INDEXER))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()


def offered() -> dict[str, list[dict]]:
    """Each edition's curated apps, through the indexer's own filter."""
    return {name: index.load_catalog(CATALOG, arch, engines)["apps"]
            for name, (arch, engines) in EDITIONS.items()}


def card() -> dict:
    entries = json.loads(WHATS_NEW.read_text(encoding="utf-8"))["entries"]
    return next(entry for entry in entries if entry["id"] == ENTRY)


class TheStoreCardIsTrueOnEveryEdition(unittest.TestCase):
    def setUp(self):
        self.card = card()
        self.offers = offered()
        # The editions the card is shown on: an `arch` narrows by processor only.
        machines = self.card.get("arch")
        self.shown = {name: apps for name, apps in self.offers.items()
                      if not machines or EDITIONS[name][0] in machines}

    def test_the_editions_really_differ(self):
        """The premise, measured: if every edition offered the same, this gate would be idle."""
        counts = {name: len(apps) for name, apps in self.offers.items()}
        self.assertGreater(counts["x86 desktop"], counts["moos-cloud"])
        self.assertGreater(counts["moos-cloud"], counts["moos-arm"])
        for name in ("moos-cloud", "moos-arm"):
            kinds = {index.catalog_kind(app) for app in self.offers[name]}
            self.assertNotIn("windows", kinds, name)
            self.assertNotIn("android", kinds, name)

    def test_a_number_of_apps_is_one_every_edition_can_show(self):
        fewest = min(len(apps) for apps in self.shown.values())
        for language, text in self.card["body"].items():
            for number in re.findall(r"\d+", text.translate(DIGITS)):
                with self.subTest(language=language, number=number):
                    self.assertLessEqual(int(number), fewest,
                                         f"the card promises {number} apps; one edition it is "
                                         f"shown on offers {fewest}")

    def test_an_app_it_names_is_offered_on_every_edition(self):
        text = self.card["body"]["en"]
        catalogue = json.loads(CATALOG.read_text(encoding="utf-8"))["apps"]
        named: dict[str, set[str]] = {}
        for app in catalogue:
            if re.search(rf"(?<![\w-]){re.escape(app['en'])}(?![\w-])", text):
                named.setdefault(app["en"], set()).add(app["id"])
        for short, ids in SHORT_NAMES.items():
            if re.search(rf"(?<![\w-]){re.escape(short)}(?![\w-])", text):
                named.setdefault(short, set()).update(ids)
        self.assertTrue(named, "the card names no app at all; this gate would be idle")
        for name, apps in self.shown.items():
            here = {app["id"] for app in apps}
            for product, ids in named.items():
                with self.subTest(edition=name, product=product):
                    self.assertTrue(ids & here, f"the card names {product}, which {name} does "
                                                f"not offer")

    def test_windows_programs_and_android_apps_are_promised_only_where_they_run(self):
        for kind, words in FOREIGN.items():
            missing = [name for name, apps in self.shown.items()
                       if kind not in {index.catalog_kind(app) for app in apps}]
            for language, text in self.card["body"].items():
                if words[language] not in text or not missing:
                    continue
                with self.subTest(kind=kind, language=language):
                    self.assertIn(CONDITION[language], text,
                                  f"the card promises {words[language]!r} to {missing}, which "
                                  f"offer none")


if __name__ == "__main__":
    unittest.main(verbosity=2)
