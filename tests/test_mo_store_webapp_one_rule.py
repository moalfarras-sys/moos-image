#!/usr/bin/env python3
"""One rule for a web app's id and start page, wherever MoOS states it.

moos_webapp_policy.parse_entry opens the window and is the authority. Three other places restate
its rule and must give the same answer:

* the catalogue gate (build_files/verify_store_catalog.py) refuses a catalogue that breaks it, so
  no image ships such an entry;
* moos-store-index leaves such an entry out of the Store, so no card offers an app whose window
  would refuse to open;
* docs/MO_STORE.md tells the catalogue's authors what the rule is.

On 2026-10-15 the gate refused `1password` and `https://web.whatsapp.com/#/`, which the other
three allowed. The policy then took the gate's rule (a letter first, single hyphens, 2 to 63
characters; a start page with no query or fragment), while the indexer and the document kept the
old one. Each case plants one id or start page in a copy of WhatsApp's entry and asks all of them.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system_files"
BUILD = ROOT / "build_files"
DOC = ROOT / "docs/MO_STORE.md"
CATALOG = SYSTEM / "usr/share/moos/store/catalog.json"
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or SYSTEM / "usr/bin/moos-store-index")


def load(name: str, path: Path):
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


policy = load("moos_webapp_policy_one_rule", SYSTEM / "usr/lib/moos/moos_webapp_policy.py")
gate = load("verify_store_catalog_one_rule", BUILD / "verify_store_catalog.py")
index = load("moos_store_index_one_rule", INDEXER)
SHIPPED = json.loads(CATALOG.read_text(encoding="utf-8"))

# Each value and whether the rule accepts it.
IDS = (("whatsapp-two", True), ("ab", True), ("office365", True), ("x" * 63, True),
       ("1password", False), ("a", False), ("x" * 64, False), ("whatsapp--two", False),
       ("whatsapp-", False), ("-whatsapp", False), ("WhatsApp", False), ("whatsapp_two", False),
       ("whatsapp.two", False))
START_PAGES = (("https://web.whatsapp.com/", True), ("https://web.whatsapp.com/send", True),
               ("https://web.whatsapp.com/#/", False), ("https://web.whatsapp.com/?lang=ar", False),
               ("https://web.whatsapp.com/?", False), ("https://web.whatsapp.com/#", False),
               ("https://web.whatsapp.com/send?b#c", False))


def planted(app_id: str = "whatsapp-two", url: str = "https://web.whatsapp.com/") -> dict:
    entry = copy.deepcopy(next(app for app in SHIPPED["apps"] if app["id"] == "whatsapp"))
    entry.update(id=app_id, en="WhatsApp Two", ar="واتساب الثاني")
    entry["install"]["url"] = url
    return entry


def policy_accepts(entry: dict) -> bool:
    try:
        policy.parse_entry(entry)
    except policy.WebAppError:
        return False
    return True


def gate_accepts(entry: dict) -> bool:
    catalog = copy.deepcopy(SHIPPED)
    catalog["apps"].append(entry)
    report, _facts = gate.check_catalog(catalog, SYSTEM, BUILD)
    return not report.errors


def index_accepts(entry: dict) -> bool:
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "catalog.json"
        path.write_text(json.dumps({"apps": [entry]}, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            return bool(index.load_catalog(path)["apps"])


def documented_rule() -> str:
    """The `webapp` bullet of docs/MO_STORE.md's catalogue contract, as one line."""
    text = DOC.read_text(encoding="utf-8")
    found = re.search(r"^  - `webapp`:.*?(?=^  - `)", text, re.MULTILINE | re.DOTALL)
    if found is None:
        raise AssertionError("docs/MO_STORE.md has no `webapp` install bullet")
    return " ".join(found.group(0).split())


class EveryPlaceGivesThePolicysAnswer(unittest.TestCase):
    def assert_agree(self, entry: dict, accepted: bool) -> None:
        self.assertEqual(policy_accepts(entry), accepted, "moos_webapp_policy, the authority")
        self.assertEqual(gate_accepts(entry), accepted, "the catalogue gate")
        self.assertEqual(index_accepts(entry), accepted, "moos-store-index")

    def test_on_an_id(self):
        for app_id, accepted in IDS:
            with self.subTest(app_id=app_id):
                self.assert_agree(planted(app_id=app_id), accepted)

    def test_on_a_start_page(self):
        for url, accepted in START_PAGES:
            with self.subTest(url=url):
                self.assert_agree(planted(url=url), accepted)

    def test_the_document_states_the_policys_id_rule(self):
        rule = documented_rule()
        self.assertEqual(re.findall(r"`(\^[^`]*\$)`", rule), [policy.ID_PATTERN.pattern], rule)

    def test_the_document_states_the_start_page_and_host_rules(self):
        rule = documented_rule()
        for words in ("query", "fragment", "public suffix", "build_files/publicsuffix/"):
            with self.subTest(words=words):
                self.assertIn(words, rule)


if __name__ == "__main__":
    unittest.main(verbosity=1)
