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


POLICY = ROOT / "system_files/usr/lib/moos/moos_webapp_policy.py"
SHA = "a" * 64


def load_policy():
    loader = importlib.machinery.SourceFileLoader("moos_webapp_policy_for_index", str(POLICY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def webapp(app_id: str = "chat-example", **install) -> dict:
    recipe = {"kind": "webapp", "url": "https://chat.example.com/", "hosts":
              ["chat.example.com", "*.example-cdn.com"], "identity": ["google"],
              "permissions": ["notifications", "microphone"], "accent": "#10A37F",
              "risk": "web-app", "requires_review": True}
    recipe.update(install)
    return {"id": app_id, "source": "moos", "cat": "ai", "glyph": "spark", "en": "Chat",
            "ar": "دردشة", "developer": "Example Inc.", "install": recipe}


def appdrop(app_id: str = "photo-tool", **install) -> dict:
    recipe = {"kind": "appdrop", "artifact": "appimage", "version": "0.7.0",
              "downloads": {"x86_64": {"url": "https://example.org/photo-x86_64.AppImage",
                                       "sha256": SHA, "size": 123456789},
                            "aarch64": {"url": "https://example.org/photo-aarch64.AppImage",
                                        "sha256": "B" * 64, "size": 1234}},
              "desktop_id": "org.example.PhotoTool", "wm_class": "PhotoTool",
              "exec": "usr/bin/photo-tool", "icon": "usr/share/icons/photo.png",
              "categories": ["Graphics", "Photography"],
              "risk": "downloaded-executable", "requires_review": True, "external": True}
    recipe.update(install)
    return {"id": app_id, "source": "moos", "cat": "art", "glyph": "camera",
            "en": "Photo Tool", "ar": "أداة الصور", "arch": ["aarch64", "x86_64"],
            "install": recipe}


def windows(app_id: str = "notepad-plus-plus", **install) -> dict:
    recipe = {"kind": "windows-portable", "version": "8.7.1",
              "downloads": {"x86_64": {"url": "https://example.org/npp.portable.x64.zip",
                                       "sha256": SHA, "size": 6543210}},
              "exe": "Notepad++/notepad++.exe", "wm_class": "notepad++.exe",
              "risk": "downloaded-executable", "requires_review": True, "external": True}
    recipe.update(install)
    return {"id": app_id, "source": "moos", "cat": "win", "glyph": "install",
            "en": "Notepad++", "ar": "نوتباد++", "engine": "windows", "arch": ["x86_64"],
            "install": recipe}


def one(entry: dict) -> tuple[dict | None, str]:
    catalog, _log = load({"apps": [entry]})
    reason = catalog["skipped"][0]["reason"] if catalog["skipped"] else ""
    return (catalog["apps"][0] if catalog["apps"] else None), reason


class CatalogueV2Kinds(unittest.TestCase):
    """docs/MO_STORE.md "catalog.json (v2)": every new field survives, with type checks."""

    def test_a_web_app_keeps_its_address_hosts_identity_permissions_and_accent(self):
        app, reason = one(webapp())
        self.assertEqual(reason, "")
        install = app["install"]
        self.assertEqual(install["url"], "https://chat.example.com/")
        self.assertEqual(install["hosts"], ["chat.example.com", "*.example-cdn.com"])
        self.assertEqual(install["identity"], ["google"])
        self.assertEqual(install["permissions"], ["notifications", "microphone"])
        self.assertEqual(install["accent"], "#10a37f")
        self.assertEqual(app["developer"], "Example Inc.")
        self.assertEqual(index.catalog_kind(app), "webapp")
        self.assertTrue(index.catalog_installable(app, "x86_64"))

    def test_the_index_and_the_web_app_policy_agree_on_every_entry(self):
        """moos_webapp_policy.parse_entry is the authority; the index may not differ."""
        policy = load_policy()
        cases = {
            "valid": webapp(),
            "route start": webapp(url="https://chat.example.com/#/inbox"),
            "start outside hosts": webapp(url="https://elsewhere.example.org/"),
            "http start": webapp(url="http://chat.example.com/"),
            "port": webapp(url="https://chat.example.com:8443/"),
            "credentials": webapp(url="https://user:pw@chat.example.com/"),
            "space": webapp(url="https://chat.example.com/a b"),
            "bad host": webapp(hosts=["chat.example.com", "not a host"]),
            "no hosts": webapp(hosts=[]),
            "too many hosts": webapp(hosts=[f"h{i}.example.com" for i in range(25)]),
            "bad identity": webapp(identity=["facebook"]),
            "bad permission": webapp(permissions=["contacts"]),
            "repeated permission": webapp(permissions=["camera", "camera"]),
            "bad accent": webapp(accent="green"),
            "bad id": webapp(app_id="Chat_Example"),
            "one-letter id": webapp(app_id="c"),
        }
        for label, entry in cases.items():
            with self.subTest(case=label):
                try:
                    policy.parse_entry(entry)
                    policy_ok = True
                except policy.WebAppError:
                    policy_ok = False
                app, reason = one(entry)
                self.assertEqual(app is not None, policy_ok, reason)

    def test_an_app_drop_recipe_keeps_every_pinned_field(self):
        app, reason = one(appdrop(categories="Graphics;Photography;"))
        self.assertEqual(reason, "")
        install = app["install"]
        self.assertEqual(install["artifact"], "appimage")
        self.assertEqual(install["version"], "0.7.0")
        self.assertEqual(sorted(install["downloads"]), ["aarch64", "x86_64"])
        self.assertEqual(install["downloads"]["aarch64"]["sha256"], "b" * 64)
        self.assertEqual(install["downloads"]["x86_64"]["size"], 123456789)
        self.assertEqual(install["desktop_id"], "org.example.PhotoTool")
        self.assertEqual(install["wm_class"], "PhotoTool")
        self.assertEqual(install["exec"], "usr/bin/photo-tool")
        self.assertEqual(install["icon"], "usr/share/icons/photo.png")
        self.assertEqual(install["categories"], ["Graphics", "Photography"])
        self.assertEqual(index.catalog_kind(app), "appdrop")
        self.assertTrue(index.catalog_installable(app, "x86_64"))
        self.assertFalse(index.catalog_installable(app, "riscv64"))

    def test_an_unsafe_app_drop_recipe_is_skipped(self):
        bad = {
            "climbs out": appdrop(exec="../../bin/sh"),
            "absolute icon": appdrop(icon="/etc/passwd"),
            "control character": appdrop(exec="bin/a\nMimeType=x"),
            "plain http": appdrop(downloads={"x86_64": {"url": "http://example.org/a",
                                                         "sha256": SHA, "size": 1}}),
            "short digest": appdrop(downloads={"x86_64": {"url": "https://example.org/a",
                                                           "sha256": "abc", "size": 1}}),
            "boolean size": appdrop(downloads={"x86_64": {"url": "https://example.org/a",
                                                           "sha256": SHA, "size": True}}),
            "no size": appdrop(downloads={"x86_64": {"url": "https://example.org/a",
                                                      "sha256": SHA}}),
            "huge size": appdrop(downloads={"x86_64": {"url": "https://example.org/a",
                                                        "sha256": SHA, "size": 1 << 40}}),
            "unknown artifact": appdrop(artifact="deb"),
            "bad desktop id": appdrop(desktop_id="photo tool"),
            "bad version": appdrop(version="1.0; rm -rf"),
            "categories not text": appdrop(categories=[1, 2]),
        }
        for label, entry in bad.items():
            with self.subTest(case=label):
                app, reason = one(entry)
                self.assertIsNone(app)
                self.assertTrue(reason)

    def test_a_windows_program_is_its_own_kind_on_the_windows_engine(self):
        app, reason = one(windows())
        self.assertEqual(reason, "")
        install = app["install"]
        self.assertEqual(install["exe"], "Notepad++/notepad++.exe")
        self.assertEqual(install["version"], "8.7.1")
        self.assertEqual(install["wm_class"], "notepad++.exe")
        self.assertEqual(index.catalog_kind(app), "windows")
        self.assertEqual(index.catalog_app_engine(app), "windows")
        no_engine = dict(app)
        no_engine.pop("engine")
        self.assertEqual(index.catalog_app_engine(no_engine), "windows")
        self.assertTrue(index.catalog_installable(app, "x86_64"))
        self.assertFalse(index.catalog_installable(app, "aarch64"))

    def test_an_unsafe_windows_recipe_is_skipped(self):
        for label, entry in {
            "not a program": windows(exe="readme.txt"),
            "no program": windows(exe=None),
            "climbs out": windows(exe="../evil.exe"),
            "backslash": windows(exe="App\\app.exe"),
            "arm download": windows(downloads={"aarch64": {"url": "https://example.org/a.zip",
                                                           "sha256": SHA, "size": 1}}),
        }.items():
            with self.subTest(case=label):
                app, reason = one(entry)
                self.assertIsNone(app)
                self.assertTrue(reason)

    def test_an_android_pin_keeps_its_version_and_size(self):
        entry = {"id": "org.example.droid", "source": "moos", "cat": "droid",
                 "glyph": "grid", "en": "Droid", "ar": "درويد", "engine": "android",
                 "install": {"kind": "android", "url": "https://example.org/d.apk",
                             "sha256": SHA, "package": "org.example.droid",
                             "version": "1.2.3", "size": 4321,
                             "risk": "external-download", "requires_review": True,
                             "external": True}}
        app, reason = one(entry)
        self.assertEqual(reason, "")
        self.assertEqual((app["install"]["version"], app["install"]["size"]), ("1.2.3", 4321))
        self.assertEqual(index.catalog_kind(app), "android")
        entry["install"]["size"] = "big"
        self.assertIsNone(one(entry)[0])

    def test_retired_and_unknown_kinds_and_recipe_less_entries_are_not_offered(self):
        retired = {"id": "tool", "source": "moos", "cat": "dev", "glyph": "code", "en": "T",
                   "ar": "ت", "install": {"kind": "appimage", "url": "https://e.org/t",
                                          "bin": "tool"}}
        app, reason = one(retired)
        self.assertIsNone(app)
        self.assertIn("retired", reason)
        unknown = dict(retired, install={"kind": "snap", "url": "https://e.org/t"})
        app, reason = one(unknown)
        self.assertIsNone(app)
        self.assertIn("not supported", reason)
        recipe_less = {key: value for key, value in retired.items() if key != "install"}
        app, reason = one(recipe_less)
        self.assertIsNone(app)
        self.assertIn("no install recipe", reason)
        foreign = dict(retired, source="snapcraft", install={"kind": "web",
                                                             "url": "https://e.org/"})
        self.assertIsNone(one(foreign)[0])

    def test_curated_search_words_publisher_and_accent_are_kept_and_bounded(self):
        words = [f"word{i}" for i in range(20)]
        app, reason = one(flathub("org.example.Photo", developer="Example Studio",
                                  keywords_en=["photoshop", "psd", "photoshop"] + words,
                                  keywords_ar=["فوتوشوب"], accent="#ABCDEF"))
        self.assertEqual(reason, "")
        self.assertEqual(app["developer"], "Example Studio")
        self.assertEqual(app["keywords_en"][:2], ["photoshop", "psd"])
        self.assertEqual(len(app["keywords_en"]), 12)
        self.assertEqual(app["keywords_ar"], ["فوتوشوب"])
        self.assertEqual(app["accent"], "#abcdef")
        for label, extra in {"accent": {"accent": "blue"}, "keywords": {"keywords_en": "psd"},
                             "developer": {"developer": 7}}.items():
            with self.subTest(field=label):
                self.assertIsNone(one(flathub("org.example.Bad", **extra))[0])


class EditorialGroups(unittest.TestCase):
    def catalogue(self) -> dict:
        apps = [flathub(f"org.example.App{i}") for i in range(5)]
        apps.append(windows())
        return {
            "apps": apps,
            "collections": [
                {"id": "office-essentials", "en": "Office", "ar": "المكتب", "glyph": "doc",
                 "apps": ["org.example.App0", "org.example.App1", "org.example.App2",
                          "org.example.NotHere", "org.example.App0"]},
                {"id": "too-small", "en": "Small", "ar": "صغيرة",
                 "apps": ["org.example.App3", "org.example.NotHere", "notepad-plus-plus"]},
                {"id": "Bad Id", "en": "x", "ar": "س", "apps": []},
                {"id": "no-arabic", "en": "Only English", "apps": ["org.example.App1"]},
            ],
            "featured": [
                {"app": "org.example.App4", "title_en": "Edit", "title_ar": "حرّر",
                 "tagline_en": "Do it", "tagline_ar": "افعلها", "accent": "#112233"},
                {"app": "org.example.NotHere", "title_en": "Gone", "title_ar": "ذهب"},
                {"app": "notepad-plus-plus", "title_en": "Notes", "title_ar": "ملاحظات"},
                {"app": "org.example.App0", "title_en": "No Arabic title"},
            ],
        }

    def test_groups_are_sanitised_and_filtered_against_what_the_machine_offers(self):
        catalog, log = load(self.catalogue())
        self.assertEqual([c["id"] for c in catalog["collections"]],
                         ["office-essentials", "too-small"])
        self.assertEqual([f["app"] for f in catalog["featured"]],
                         ["org.example.App4", "org.example.NotHere", "notepad-plus-plus"])
        self.assertIn("Bad Id", log)
        self.assertIn("no-arabic", log)
        apps_by_id = {app["id"]: dict(app, installable=index.catalog_installable(app, "aarch64"))
                      for app in catalog["apps"]}
        collections, featured = index.editorial_groups(catalog, apps_by_id)
        self.assertEqual(
            collections,
            [{"id": "office-essentials", "en": "Office", "ar": "المكتب", "glyph": "doc",
              "apps": ["org.example.App0", "org.example.App1", "org.example.App2"]}])
        # On a machine where the Windows program cannot install, its hero card goes.
        self.assertEqual([card["app"] for card in featured], ["org.example.App4"])
        self.assertEqual(featured[0]["accent"], "#112233")

    def test_at_most_eight_hero_cards_survive(self):
        document = {"apps": [flathub(f"org.example.App{i}") for i in range(10)],
                    "featured": [{"app": f"org.example.App{i}", "title_en": "T",
                                  "title_ar": "ت"} for i in range(10)]}
        catalog, _log = load(document)
        apps_by_id = {app["id"]: dict(app, installable=True) for app in catalog["apps"]}
        _collections, featured = index.editorial_groups(catalog, apps_by_id)
        self.assertEqual(len(featured), 8)


def run_index(base: Path, document: dict) -> tuple[dict, str]:
    (base / "appstream").mkdir(exist_ok=True)
    (base / "flatpak").mkdir(exist_ok=True)
    catalog = base / "catalog.json"
    catalog.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
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
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(output.read_text(encoding="utf-8")), result.stderr


class EveryKindReachesTheIndex(unittest.TestCase):
    def test_kinds_versions_and_editorial_groups_are_published(self):
        android = {"id": "org.example.droid", "source": "moos", "cat": "droid",
                   "glyph": "grid", "en": "Droid", "ar": "درويد", "engine": "android",
                   "install": {"kind": "android", "url": "https://example.org/d.apk",
                               "sha256": SHA, "package": "org.example.droid",
                               "version": "1.2.3"}}
        npm = {"id": "codex", "source": "moos", "cat": "ai", "glyph": "spark", "en": "Codex",
               "ar": "كودكس", "install": {"kind": "npm", "pkg": "@openai/codex",
                                          "bin": "codex"}}
        page = {"id": "publisher-page", "source": "moos", "cat": "win", "glyph": "install",
                "en": "Page", "ar": "صفحة", "engine": "windows",
                "install": {"kind": "web", "url": "https://example.org/download"}}
        document = {
            "apps": [flathub("org.example.Editor"), webapp(), appdrop(), windows(),
                     android, npm, page],
            "collections": [{"id": "picks", "en": "Picks", "ar": "مختارات",
                             "apps": ["org.example.Editor", "chat-example", "photo-tool",
                                      "org.example.Unknown"]}],
            "featured": [{"app": "chat-example", "title_en": "Chat", "title_ar": "دردشة"}],
        }
        with tempfile.TemporaryDirectory() as raw:
            data, _log = run_index(Path(raw), document)
        apps = {app["id"]: app for app in data["apps"]}
        expected = {
            "org.example.Editor": "flatpak", "chat-example": "webapp",
            "photo-tool": "appdrop", "notepad-plus-plus": "windows",
            "org.example.droid": "android", "codex": "npm", "publisher-page": "web"}
        # The CLI filters for the actual machine, even with all engines
        # explicitly admitted. A Windows-only fixture must remain absent on ARM.
        if index.running_arch() != "x86_64":
            expected.pop("notepad-plus-plus")
        self.assertEqual({app_id: app["kind"] for app_id, app in apps.items()}, expected)
        self.assertEqual(apps["photo-tool"]["version"], "0.7.0")
        if "notepad-plus-plus" in expected:
            self.assertEqual(apps["notepad-plus-plus"]["version"], "8.7.1")
        self.assertEqual(apps["org.example.droid"]["version"], "1.2.3")
        self.assertEqual(apps["chat-example"]["install"]["hosts"],
                         ["chat.example.com", "*.example-cdn.com"])
        self.assertEqual(data["collections"][0]["apps"],
                         ["org.example.Editor", "chat-example", "photo-tool"])
        self.assertEqual(data["featured"], [{"app": "chat-example", "title_en": "Chat",
                                             "title_ar": "دردشة"}])


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
