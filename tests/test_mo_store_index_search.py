#!/usr/bin/env python3
"""What every Mo Store index entry says about itself, beyond its name.

* `search`: one folded string per app, so "VS Code", "فوتوشوب" or "photoshop" find the app
  whatever language the index was built in. The fold is the contract between the indexer,
  the Store window and MoOS Search, so it is pinned here character by character and against
  MoOS Search's own fold().
* `name_en`: the English name even when the index locale is Arabic.
* `cat`: one of the catalogue's twelve Store categories for EVERY app; Android and Windows
  apps are never left in a catch-all.
* `branding` and `content_rating` from AppStream.

Every run uses a private HOME and private XDG directories.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")
KRUNNER = ROOT / "system_files/usr/libexec/moos-store-krunner"


def load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load("moos_store_index_search", INDEXER)

FIXTURE = """<components>
  <component type="desktop-application">
    <id>com.visualstudio.code</id>
    <name>Visual Studio Code</name>
    <name xml:lang="ar">فيجوال ستوديو كود</name>
    <summary>Code editing. Redefined.</summary>
    <developer><name>Microsoft</name></developer>
    <keywords><keyword>VS Code</keyword><keyword xml:lang="ar">محرر</keyword>
      <keyword xml:lang="de">Programmierung</keyword></keywords>
    <categories><category>Development</category><category>IDE</category>
      <category>Utility</category></categories>
    <branding><color type="primary" scheme_preference="light">#E3F2FD</color>
      <color type="primary" scheme_preference="dark">#0D47A1</color></branding>
    <content_rating type="oars-1.1"><content_attribute id="social-chat">mild</content_attribute>
    </content_rating>
    <bundle type="flatpak">app/com.visualstudio.code/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Shooter</id>
    <name>Shooter</name>
    <categories><category>Network</category><category>AudioVideo</category>
      <category>Game</category></categories>
    <branding><color type="primary">#ABC</color></branding>
    <content_rating type="oars-1.1">
      <content_attribute id="violence-realistic">intense</content_attribute>
      <content_attribute id="language-profanity">moderate</content_attribute>
    </content_rating>
    <bundle type="flatpak">app/org.example.Shooter/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Chat</id>
    <name>Chat</name>
    <categories><category>Network</category><category>InstantMessaging</category></categories>
    <branding><color type="primary" scheme_preference="light">#ffeedd</color></branding>
    <content_rating type="oars-1.1">
      <content_attribute id="social-chat">moderate</content_attribute>
    </content_rating>
    <bundle type="flatpak">app/org.example.Chat/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Plain</id>
    <name>Plain</name>
    <content_rating type="oars-1.1"/>
    <bundle type="flatpak">app/org.example.Plain/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Thinker</id>
    <name>Thinker</name>
    <categories><category>ArtificialIntelligence</category><category>Science</category>
    </categories>
    <bundle type="flatpak">app/org.example.Thinker/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Photo</id>
    <name>Photo</name>
    <categories><category>Graphics</category></categories>
    <bundle type="flatpak">app/org.example.Photo/x86_64/stable</bundle>
  </component>
</components>
"""

CATALOG = {
    "categories": [],
    "bundles": [],
    "apps": [
        {"id": "org.example.Photo", "source": "flathub", "cat": "work", "glyph": "camera",
         "en": "PhotoCraft", "ar": "فوتو كرافت", "developer": "ArtCraft",
         "keywords_en": ["Photoshop", "PSD"], "keywords_ar": ["فوتوشوب"]},
        {"id": "org.example.droid", "source": "moos", "glyph": "grid", "en": "Droid",
         "ar": "درويد", "engine": "android",
         "install": {"kind": "android", "url": "https://example.org/d.apk",
                     "sha256": "a" * 64, "package": "org.example.droid"}},
        {"id": "notepad-page", "source": "moos", "glyph": "install", "en": "Notepad++",
         "ar": "نوتباد++", "engine": "windows",
         "install": {"kind": "web", "url": "https://example.org/notepad"}},
    ],
}


def build(locale: str) -> dict:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        revision = base / "flatpak/appstream/flathub/x86_64" / ("d" * 64)
        revision.mkdir(parents=True)
        (revision / "appstream.xml").write_text(FIXTURE, encoding="utf-8")
        catalog = base / "catalog.json"
        catalog.write_text(json.dumps(CATALOG, ensure_ascii=False), encoding="utf-8")
        output = base / "cache/index.json"
        home = base / "home"
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("XDG_")}
        environment.update({"HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share"),
                            "XDG_CACHE_HOME": str(home / ".cache"),
                            "XDG_STATE_HOME": str(home / ".local/state"),
                            "XDG_CONFIG_HOME": str(home / ".config"),
                            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"})
        result = subprocess.run(
            [sys.executable, str(INDEXER), "--output", str(output), "--catalog", str(catalog),
             "--appstream-root", str(base / "flatpak/appstream"),
             "--installation-root", str(base / "flatpak"), "--locale", locale,
             "--engines", "all"],
            text=True, capture_output=True, check=False, env=environment)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return {app["id"]: app for app in
                json.loads(output.read_text(encoding="utf-8"))["apps"]}


class TheFold(unittest.TestCase):
    VECTORS = {
        "Visual Studio Code": "visual studio code",
        "مُحَرِّرُ الصُّوَرِ": "محرر الصور",          # harakat and shadda
        "أداة إضافية آمنة ٱلـكتابة": "اداه اضافيه امنه الكتابه",  # alef forms, tatweel
        "مكتبة الموسيقى": "مكتبه الموسيقي",             # ta marbuta, alef maqsura
        "شاطئ مؤتمر": "شاطي موتمر",                    # hamza on ya and waw
        "إصدار ٣٫١ و ۴": "اصدار 3٫1 و 4",               # Arabic and Persian digits
        "Notepad++": "notepad",
        "com.visualstudio.code": "com visualstudio code",
        "a​b‏c‮d⁦e﻿": "abcde",  # zero-width and bidi marks
        "  GIMP  (2.10) / PSD|Photoshop · x_y ": "gimp 2 10 psd photoshop x y",
        "قرآنٰۡ": "قران",                    # superscript alef, Quranic marks
    }

    def test_every_rule_folds_as_documented(self):
        for raw, folded in self.VECTORS.items():
            with self.subTest(raw=raw):
                self.assertEqual(index.fold_search_text(raw), folded)

    def test_the_fold_agrees_with_moos_search(self):
        """MoOS Search (the KRunner plugin) folds queries with its own fold()."""
        krunner = load("moos_store_krunner_for_index", KRUNNER)
        for raw in self.VECTORS:
            if any(char in raw for char in "‮﻿۴"):
                continue            # characters only the index folds; a superset is fine
            with self.subTest(raw=raw):
                self.assertEqual(index.fold_search_text(raw), krunner.fold(raw))

    def test_a_search_string_keeps_each_term_once_and_stays_bounded(self):
        text = index.search_string(["GIMP", "gimp", "Image Editor", None, "", "x" * 700])
        self.assertTrue(text.startswith("gimp image editor"))
        self.assertLessEqual(len(text), index.SEARCH_LIMIT)
        self.assertEqual(text.count("gimp"), 1)


class SearchAndNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arabic = build("ar_SA.UTF-8")
        cls.english = build("en_US.UTF-8")

    def test_an_arabic_index_keeps_the_english_name(self):
        code = self.arabic["com.visualstudio.code"]
        self.assertEqual(code["name"], "فيجوال ستوديو كود")
        self.assertEqual(code["name_en"], "Visual Studio Code")
        self.assertEqual(self.english["com.visualstudio.code"]["name_en"], "Visual Studio Code")

    def test_search_holds_both_names_keywords_publisher_and_id_tail(self):
        for label, apps in (("arabic", self.arabic), ("english", self.english)):
            search = apps["com.visualstudio.code"]["search"]
            with self.subTest(index=label):
                for term in ("visual studio code", "فيجوال ستوديو كود", "vs code", "محرر",
                             "microsoft", "code"):
                    self.assertIn(term, search)
                self.assertNotIn("programmierung", search)

    def test_curated_names_and_search_words_are_searchable(self):
        photo = self.arabic["org.example.Photo"]
        self.assertEqual(photo["name_en"], "PhotoCraft")
        for term in ("photocraft", "فوتو كرافت", "photoshop", "psd", "فوتوشوب", "artcraft"):
            with self.subTest(term=term):
                self.assertIn(term, photo["search"])
        self.assertIn("notepad", self.arabic["notepad-page"]["search"])

    def test_every_entry_has_a_folded_search_string(self):
        for app_id, app in self.arabic.items():
            with self.subTest(app=app_id):
                self.assertEqual(app["search"], index.fold_search_text(app["search"]))
                self.assertNotIn("_search_terms", app)


class StoreCategories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apps = build("en")

    def test_every_app_has_one_of_the_twelve_store_categories(self):
        for app_id, app in self.apps.items():
            with self.subTest(app=app_id):
                self.assertIn(app["cat"], index.STORE_CATEGORIES)

    def test_metadata_places_apps_with_the_specific_rule_first(self):
        expected = {
            "com.visualstudio.code": "dev",      # Development + IDE + Utility
            "org.example.Shooter": "fun",        # Game wins over Network and AudioVideo
            "org.example.Chat": "comm",
            "org.example.Plain": "util",         # no categories: never a catch-all
            "org.example.Thinker": "edu",        # AI is editorial, never inferred
            "org.example.Photo": "work",         # the catalogue's cat wins (Graphics says art)
            "org.example.droid": "droid",        # an Android app with no cat
            "notepad-page": "win",               # a Windows program's page with no cat
        }
        self.assertEqual({app_id: self.apps[app_id]["cat"] for app_id in expected}, expected)

    def test_the_old_category_key_keeps_its_values(self):
        self.assertEqual(self.apps["com.visualstudio.code"]["category"], "development")
        self.assertEqual(self.apps["org.example.Shooter"]["category"], "games")

    def test_the_rules_one_by_one(self):
        for categories, expected in (
            (["Network", "WebBrowser"], "ess"),
            (["Network", "Email"], "comm"),
            (["Office", "Spreadsheet"], "work"),
            (["Graphics", "Photography"], "art"),
            (["AudioVideo", "Player"], "media"),
            (["Audio"], "media"),
            (["Education", "Languages"], "edu"),
            (["Science", "Math"], "edu"),
            (["System", "TerminalEmulator"], "util"),
            (["Settings"], "util"),
            (["Network", "FileTransfer", "P2P"], "util"),
            ([], "util"),
        ):
            with self.subTest(categories=categories):
                self.assertEqual(index.store_category_from_freedesktop(categories), expected)


class BrandingAndRating(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apps = build("en")

    def test_branding_per_scheme(self):
        self.assertEqual(self.apps["com.visualstudio.code"]["branding"],
                         {"light": "#e3f2fd", "dark": "#0d47a1"})
        # One colour with no scheme preference serves both.
        self.assertEqual(self.apps["org.example.Shooter"]["branding"],
                         {"light": "#aabbcc", "dark": "#aabbcc"})
        # A light-only colour is not borrowed for the dark scheme.
        self.assertEqual(self.apps["org.example.Chat"]["branding"],
                         {"light": "#ffeedd", "dark": None})
        self.assertIsNone(self.apps["org.example.Plain"]["branding"])

    def test_content_rating_from_oars(self):
        self.assertEqual(self.apps["org.example.Shooter"]["content_rating"], "mature")
        self.assertEqual(self.apps["org.example.Chat"]["content_rating"], "teen")
        self.assertEqual(self.apps["com.visualstudio.code"]["content_rating"], "all")
        self.assertEqual(self.apps["org.example.Plain"]["content_rating"], "all")
        self.assertIsNone(self.apps["org.example.Thinker"]["content_rating"])
        self.assertIsNone(self.apps["org.example.droid"]["content_rating"])


if __name__ == "__main__":
    unittest.main()
