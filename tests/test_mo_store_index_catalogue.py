#!/usr/bin/env python3
"""The signed catalogue as Mo Store's indexer reads it.

A valid catalogue must never make the whole index fail, and one bad entry must never take
every other app down with it: until 2026-10-14 a single unsafe or malformed entry raised out
of the load, and a glyph the build gate accepts (`_`) was refused here, so the Store had no
index at all. A bad entry is now left out with a logged reason; the unsafe recipe still
never reaches the index.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
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
CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_catalogue", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()


def flathub(app_id: str, **extra) -> dict:
    entry = {"id": app_id, "source": "flathub", "cat": "util", "glyph": "spark",
             "en": app_id.rsplit(".", 1)[-1], "ar": "تطبيق", "desc_en": "An app.",
             "desc_ar": "تطبيق."}
    entry.update(extra)
    return entry


def load(document: dict) -> tuple[dict, str]:
    with tempfile.TemporaryDirectory() as raw:
        path = Path(raw) / "catalog.json"
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            catalog = index.load_catalog(path)
        return catalog, stderr.getvalue()


class GlyphNamesMatchTheGate(unittest.TestCase):
    def test_hyphen_and_underscore_glyphs_are_both_names(self):
        catalog, log = load({
            "categories": [{"id": "droid", "en": "Android apps", "ar": "تطبيقات أندرويد",
                            "glyph": "android-apps"}],
            "bundles": [{"id": "start", "en": "Start", "ar": "ابدأ", "glyph": "safe_update",
                         "apps": ["org.example.One", "org.example.Two"]}],
            "apps": [flathub("org.example.One", glyph="arrow-back"),
                     flathub("org.example.Two", glyph="volume_off")],
        })
        self.assertEqual(log, "")
        self.assertEqual([app["glyph"] for app in catalog["apps"]], ["arrow-back", "volume_off"])
        self.assertEqual(catalog["categories"][0]["glyph"], "android-apps")
        self.assertEqual(catalog["bundles"][0]["glyph"], "safe_update")

    def test_the_shipped_catalogue_loads_with_nothing_skipped(self):
        catalog = index.load_catalog(CATALOG)
        self.assertEqual(catalog["skipped"], [])
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(len(catalog["apps"]), len(raw["apps"]))


class OneBadEntryIsSkippedNotFatal(unittest.TestCase):
    def test_a_bad_app_entry_is_left_out_with_its_reason(self):
        catalog, log = load({"apps": [
            flathub("org.example.Good"),
            flathub("org.example.BadGlyph", glyph="Not A Glyph"),
            "not an object",
            flathub("org.example.BadArch", arch="x86_64"),
            {"id": "web-thing", "source": "moos", "cat": "util", "glyph": "spark", "en": "W",
             "ar": "و", "install": {"kind": "web", "url": "http://insecure.example.org/"}},
            flathub("org.example.Good", en="Second copy"),
            flathub("org.example.AlsoGood"),
        ]})
        self.assertEqual([app["id"] for app in catalog["apps"]],
                         ["org.example.Good", "org.example.AlsoGood"])
        self.assertEqual(catalog["apps"][0]["en"], "Good")
        reasons = {item["id"]: item["reason"] for item in catalog["skipped"]}
        self.assertIn("org.example.BadGlyph", reasons)
        self.assertIn("#2", reasons)
        self.assertIn("org.example.BadArch", reasons)
        self.assertIn("not safe HTTPS", reasons["web-thing"])
        self.assertEqual(reasons["org.example.Good"], "duplicate id")
        for label in ("org.example.BadGlyph", "#2", "web-thing", "duplicate id"):
            with self.subTest(label=label):
                self.assertIn(label, log)

    def test_bad_groups_are_skipped_and_a_non_list_section_is_ignored(self):
        catalog, log = load({
            "categories": [{"id": "Bad Id", "en": "x", "ar": "س"},
                           {"id": "work", "en": "Work", "ar": "عمل", "glyph": "doc"}],
            "bundles": "not a list",
            "apps": [flathub("org.example.One")],
        })
        self.assertEqual([item["id"] for item in catalog["categories"]], ["work"])
        self.assertEqual(catalog["bundles"], [])
        self.assertIn("bundles is not a list", log)
        self.assertEqual({item["section"] for item in catalog["skipped"]},
                         {"categories", "bundles"})

    def test_a_catalogue_that_cannot_be_read_still_raises(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "catalog.json"
            for content in ("{", "[]", '{"apps": "none"}'):
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(index.CatalogError):
                        index.load_catalog(path)


class TheIndexSurvivesABadEntry(unittest.TestCase):
    def test_a_full_run_publishes_the_good_entries_and_logs_the_bad_one(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            (base / "appstream").mkdir()
            (base / "flatpak").mkdir()
            catalog = base / "catalog.json"
            catalog.write_text(json.dumps({"apps": [
                flathub("org.example.Good", glyph="android-apps"),
                flathub("org.example.Bad", glyph="Bad Glyph"),
            ]}), encoding="utf-8")
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
                [sys.executable, str(INDEXER), "--output", str(output), "--catalog",
                 str(catalog), "--appstream-root", str(base / "appstream"),
                 "--installation-root", str(base / "flatpak"), "--locale", "en",
                 "--engines", "all"],
                text=True, capture_output=True, check=False, env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("org.example.Bad", result.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual([app["id"] for app in data["apps"]], ["org.example.Good"])
            self.assertEqual(data["stats"]["catalog_skipped_entries"], 1)


if __name__ == "__main__":
    unittest.main()
