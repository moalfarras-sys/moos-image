#!/usr/bin/env python3
"""Gate: Mo Store in Plasma's search bar suggests apps and only ever opens their Store page.

WHY THIS EXISTS
Discover's AppStream runner is disabled in MoOS (it opened a second, hidden store), so until
moos-store-krunner a person typing "gimp" or "واتساب" into MoOS Search found nothing for an app
they did not have yet. KRunner sends the runner whatever is typed and hands the chosen id back as
a string, so this gate proves:

* Arabic is matched the way people type it (no diacritics, any alef, ta marbuta, Arabic digits),
  with the index's own fold, character for character;
* installed apps are not offered again, and the result list is short;
* only an app this computer can get is offered: before the Store's first index the catalogue is
  read with the Store's own rules (processor, engine, installed), and an index row whose
  compatibility verdict is "blocked" is not offered;
* the label says what choosing it does: it opens the app's page;
* a chosen id is looked up again in the index — a tampered or unknown id starts nothing;
* the only thing a result starts is Mo Store, with `--app=<id>` as one argv element;
* the runner reads only its local index (no network), re-reads it when it changes, and its
  plugin and D-Bus activation files name the same service.
"""

from __future__ import annotations

import configparser
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "system_files/usr/libexec/moos-store-krunner"
PLUGIN = ROOT / "system_files/usr/share/krunner/dbusplugins/org.moos.store.desktop"
SERVICE = ROOT / "system_files/usr/share/dbus-1/services/org.moos.StoreRunner.service"
CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"
INDEXER = ROOT / "system_files/usr/bin/moos-store-index"

APPS = [
    {"id": "org.gimp.GIMP", "name": "GNU Image Manipulation Program", "summary": "Create images",
     "installable": True, "installed": False, "verified": True},
    {"id": "whatsapp", "en": "WhatsApp", "ar": "واتساب", "desc_en": "Messages on the computer",
     "desc_ar": "رسائلك على الحاسوب", "installable": True, "installed": False, "curated": True},
    {"id": "org.mozilla.firefox", "en": "Firefox", "ar": "فَيَرفِكس", "desc_en": "Web browser",
     "desc_ar": "متصفّح ويب", "installable": True, "installed": False, "curated": True},
    {"id": "com.visualstudio.code", "en": "VS Code", "ar": "في‌إس كود", "installable": True,
     "installed": True, "curated": True},
    {"id": "org.libreoffice.LibreOffice", "en": "LibreOffice", "ar": "ليبرأوفيس",
     "desc_en": "Full office suite", "desc_ar": "حزمة مكتبية كاملة", "installable": True,
     "installed": False, "curated": True},
    {"id": "../../etc", "en": "Evil", "installable": True, "installed": False},
]


def load(lang="en_US.UTF-8"):
    with mock.patch.dict(os.environ, {"LANG": lang, "LC_ALL": "", "LC_MESSAGES": "",
                                      "LANGUAGE": ""}):
        module = runpy.run_path(str(RUNNER), run_name="moos_store_krunner_test")
    return module


def private_machine(folder):
    """A home, Flatpak installations and XDG folders of the test's own: never the owner's."""
    base = Path(folder)
    return mock.patch.dict(os.environ, {
        "HOME": str(base / "home"), "XDG_DATA_HOME": str(base / "home/.local/share"),
        "XDG_CACHE_HOME": str(base / "home/.cache"), "XDG_CONFIG_DIRS": str(base / "xdg"),
        "FLATPAK_USER_DIR": str(base / "home/.local/share/flatpak"),
        "FLATPAK_SYSTEM_DIR": str(base / "system-flatpak")})


def pin(runner, machine, engines):
    """The machine the catalogue fallback asks the Store's indexer about. (A runner that asks no
    indexer has nothing to pin: it offers every catalogue app on every machine.)"""
    if "indexer" not in runner:
        return
    store = runner["indexer"]()
    assert store is not None, "the Store's own indexer must load beside the runner"
    store.running_arch = lambda: machine
    store.available_engines = lambda *_args, **_kwargs: set(engines)


class Runner(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "index.json"
        self.path.write_text(json.dumps({"apps": APPS}), encoding="utf-8")
        self.runner = load()
        self.index = self.runner["Index"](self.path, catalog=Path(self.folder.name) / "none.json",
                                          builtin={"org.kde.dolphin"})

    def tearDown(self):
        self.folder.cleanup()

    def ids(self, query, lang="en_US.UTF-8"):
        with mock.patch.dict(os.environ, {"LANG": lang, "LC_ALL": ""}):
            return [row[0] for row in self.runner["match"](self.index, query)]

    def test_names_in_both_languages_find_the_app(self):
        self.assertEqual(self.ids("gimp")[:1], ["app:org.gimp.GIMP"])
        self.assertEqual(self.ids("whats")[:1], ["app:whatsapp"])
        self.assertEqual(self.ids("واتساب")[:1], ["app:whatsapp"])
        self.assertEqual(self.ids("فيرفكس")[:1], ["app:org.mozilla.firefox"])  # no diacritics typed
        self.assertEqual(self.ids("ليبراوفيس")[:1], ["app:org.libreoffice.LibreOffice"])  # any alef
        self.assertEqual(self.ids("office suite")[:1], ["app:org.libreoffice.LibreOffice"])

    def test_installed_apps_short_queries_and_bad_ids_are_not_offered(self):
        self.assertEqual(self.ids("vs code"), [])
        self.assertEqual(self.ids("g"), [])
        self.assertNotIn("app:../../etc", self.ids("evil"))

    def test_labels_follow_the_session_language(self):
        # Choosing a result opens the app's page; installing stays in the Store. The Arabic label
        # said «ثبّت» (install) for that, and the English one "Get".
        with mock.patch.dict(os.environ, {"LANG": "ar_SA.UTF-8", "LC_ALL": ""}):
            first = self.runner["match"](self.index, "واتساب")[0]
        self.assertEqual(first[1], "اعرض «واتساب» في متجر MoOS")
        self.assertEqual(first[2], "moos-store")
        with mock.patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": ""}):
            first = self.runner["match"](self.index, "whatsapp")[0]
        self.assertEqual(first[1], "View WhatsApp in Mo Store")
        # Low category relevance: an app the person already has must always come first.
        self.assertEqual(first[3], 30)
        self.assertLess(max(row[3] for row in self.runner["match"](self.index, "office")), 31)

    def test_a_result_opens_only_the_store_page_of_a_known_app(self):
        calls, envs = [], []
        self.runner["open_page"].__globals__["subprocess"] = mock.Mock(
            Popen=lambda argv, env=None, **_: (calls.append(argv), envs.append(env)), DEVNULL=-3)
        self.assertTrue(self.runner["run"](self.index, "app:org.gimp.GIMP", "token-123"))
        self.assertEqual(calls, [["/usr/bin/moos-store", "--app=org.gimp.GIMP"]])
        # KRunner's activation token travels on, so an open Store comes to the front.
        self.assertEqual(envs[0]["XDG_ACTIVATION_TOKEN"], "token-123")
        self.assertTrue(self.runner["run"](self.index, "app:org.gimp.GIMP", "bad token;rm"))
        self.assertNotIn("XDG_ACTIVATION_TOKEN", envs[1])
        calls.clear()
        for forged in ("app:com.unknown.App", "app:../../etc", "app:x;rm -rf ~", "route:x",
                       "org.gimp.GIMP", "app:", 42):
            with self.subTest(forged=forged):
                self.assertFalse(self.runner["run"](self.index, forged))
        self.assertEqual(calls, [])

    def test_the_index_is_reread_when_it_changes(self):
        self.assertEqual(self.ids("krita"), [])
        apps = APPS + [{"id": "org.kde.krita", "name": "Krita", "installable": True,
                        "installed": False}]
        self.path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        os.utime(self.path, ns=(1, 2))
        self.assertEqual(self.ids("krita"), ["app:org.kde.krita"])

    def test_apps_the_image_ships_are_never_offered(self):
        apps = APPS + [{"id": "org.kde.dolphin", "name": "Dolphin", "installable": True,
                        "installed": False}]
        self.path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        os.utime(self.path, ns=(3, 4))
        self.assertEqual(self.ids("dolphin"), [])

    def test_keywords_and_the_arabic_article(self):
        apps = APPS + [{"id": "org.example.Browser", "en": "Example", "ar": "مثال",
                        "keywords_ar": ["متصفح"], "keywords_en": ["browser"],
                        "installable": True, "installed": False, "curated": True}]
        self.path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        os.utime(self.path, ns=(5, 6))
        self.assertIn("app:org.example.Browser", self.ids("المتصفح"))
        self.assertIn("app:org.example.Browser", self.ids("browser"))

    def test_before_the_first_index_the_catalogue_answers(self):
        # The signed catalogue, read the way the Store reads it (see OnlyWhatThisComputerCanGet).
        with private_machine(self.folder.name):
            pin(self.runner, "x86_64", set())
            index = self.runner["Index"](Path(self.folder.name) / "missing.json", catalog=CATALOG,
                                         builtin=set())
            self.assertIn("app:chatgpt", [row[0] for row in self.runner["match"](index, "chatgpt")])

    def test_a_blocked_app_is_not_offered(self):
        """compat.verdict "blocked" (another processor, no engine, no room, end of life): the
        Store will not install it, so the search bar does not suggest it; a warning is fine."""
        apps = APPS + [{"id": "org.example.Huge", "name": "Huge Studio", "installable": True,
                        "installed": False, "compat": {"verdict": "blocked", "reasons": ["low_disk"]}},
                       {"id": "org.example.Online", "name": "Huge Online", "installable": True,
                        "installed": False, "compat": {"verdict": "warn",
                                                       "reasons": ["needs_internet"]}}]
        self.path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        os.utime(self.path, ns=(7, 8))
        self.assertEqual(self.ids("huge"), ["app:org.example.Online"])
        self.assertFalse(self.runner["run"](self.index, "app:org.example.Huge"))

    def test_the_apps_own_icon_is_sent_as_pixels(self):
        import struct, zlib
        width = height = 2
        rows = b"".join(b"\x00" + bytes([255, 0, 0, 255]) * width for _ in range(height))
        def chunk(kind, body):
            return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
        icon = Path(self.folder.name) / "icons/128x128/app.png"
        icon.parent.mkdir(parents=True)
        icon.write_bytes(png)
        data = self.runner["icon_data"]("file://" + str(icon))
        self.assertEqual(data[:6], (2, 2, 8, True, 8, 4))
        self.assertEqual(data[6], bytes([255, 0, 0, 255]) * 4)
        self.assertIsNone(self.runner["icon_data"]("https://example.com/x.png"))

    def test_no_network_and_no_shell(self):
        source = RUNNER.read_text(encoding="utf-8")
        for word in ("urllib", "http.client", "requests", "socket", "shell=True", "os.system"):
            with self.subTest(word=word):
                self.assertNotIn(word, source)


class OnlyWhatThisComputerCanGet(unittest.TestCase):
    """Before the Store's first index the search bar answers from the signed catalogue, which
    names apps for every MoOS computer. It used to offer all of them: on a fresh account on the
    Oracle A1 (aarch64, no Windows or Android runtime) "notepad", "steam" and "f-droid" offered
    Notepad++, Steam and F-Droid, which that Store does not have, and an app already installed
    was offered again. The catalogue is now read with the Store's own rules: moos-store-index's
    load_catalog() (processor and engine), its installed scan and catalog_installable()."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        machine = private_machine(self.folder.name)
        machine.start()
        self.addCleanup(machine.stop)
        self.runner = load()

    def offered(self, machine, engines, *queries):
        pin(self.runner, machine, engines)
        index = self.runner["Index"](Path(self.folder.name) / "missing.json", catalog=CATALOG,
                                     builtin=set())
        return {query: [row[0] for row in self.runner["match"](index, query)] for query in queries}

    def test_another_processors_apps_and_engineless_apps_are_not_offered(self):
        arm = self.offered("aarch64", set(), "notepad", "steam", "f-droid", "chatgpt")
        self.assertNotIn("app:notepad-plus-plus", arm["notepad"])
        self.assertNotIn("app:com.valvesoftware.Steam", arm["steam"])
        self.assertNotIn("app:org.fdroid.fdroid", arm["f-droid"])
        self.assertIn("app:chatgpt", arm["chatgpt"], "an app every edition offers is still found")

    def test_an_x86_pc_without_the_runtimes_offers_neither(self):
        cloud = self.offered("x86_64", set(), "notepad", "steam", "f-droid")
        self.assertNotIn("app:notepad-plus-plus", cloud["notepad"])
        self.assertIn("app:com.valvesoftware.Steam", cloud["steam"])
        self.assertNotIn("app:org.fdroid.fdroid", cloud["f-droid"])

    def test_a_desktop_pc_offers_them(self):
        desktop = self.offered("x86_64", {"windows", "android"}, "notepad", "steam", "f-droid")
        self.assertIn("app:notepad-plus-plus", desktop["notepad"])
        self.assertIn("app:com.valvesoftware.Steam", desktop["steam"])
        self.assertIn("app:org.fdroid.fdroid", desktop["f-droid"])

    def test_an_installed_app_is_not_offered_again(self):
        before = self.offered("x86_64", set(), "gimp", "whatsapp")
        self.assertIn("app:org.gimp.GIMP", before["gimp"])
        self.assertIn("app:whatsapp", before["whatsapp"])
        # A Flatpak deployed for this user, and a web app MoOS installed: both are files.
        branch = Path(self.folder.name) / "home/.local/share/flatpak/app/org.gimp.GIMP/x86_64/stable"
        (branch / "0123abcd").mkdir(parents=True)
        (branch / "active").symlink_to("0123abcd")
        launcher = (Path(self.folder.name)
                    / "home/.local/share/applications/org.moos.webapp.whatsapp.desktop")
        launcher.parent.mkdir(parents=True)
        launcher.write_text("[Desktop Entry]\nName=WhatsApp\nX-MoOS-WebApp=whatsapp\n",
                            encoding="utf-8")
        self.runner = load()
        after = self.offered("x86_64", set(), "gimp", "whatsapp")
        self.assertNotIn("app:org.gimp.GIMP", after["gimp"])
        self.assertNotIn("app:whatsapp", after["whatsapp"])


class TheFold(unittest.TestCase):
    """MoOS Search folds what is typed with the index's rules, character for character.

    The index (moos-store-index fold_search_text) also strips U+061C, U+202A-U+202E and U+FEFF;
    this runner did not, so text pasted with an RTL embedding or a byte-order mark kept the
    mark, matched no folded name, and "‫واتساب‬" found nothing while "واتساب" found WhatsApp."""

    @classmethod
    def setUpClass(cls):
        loader = importlib.machinery.SourceFileLoader("moos_store_index_for_krunner_test",
                                                      str(INDEXER))
        cls.index = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(loader.name, loader))
        sys.modules[loader.name] = cls.index
        loader.exec_module(cls.index)
        cls.runner = load()

    def test_every_character_folds_as_the_index_folds_it(self):
        fold, folded = self.runner["fold"], self.index.fold_search_text
        differ = [f"U+{point:04X}" for point in range(0x110000)
                  if not 0xD800 <= point <= 0xDFFF and fold(chr(point)) != folded(chr(point))]
        self.assertEqual(differ, [])

    def test_a_query_pasted_with_direction_marks_finds_the_app(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "index.json"
            path.write_text(json.dumps({"apps": APPS}), encoding="utf-8")
            index = self.runner["Index"](path, catalog=Path(folder) / "none.json", builtin=set())
            for query in ("‫واتساب‬", "واتساب؜", "‮واتساب", "﻿whatsapp"):
                with self.subTest(query=ascii(query)):
                    self.assertEqual([row[0] for row in self.runner["match"](index, query)][:1],
                                     ["app:whatsapp"])


class Wiring(unittest.TestCase):
    def test_plugin_and_activation_name_the_same_service(self):
        plugin = configparser.ConfigParser(interpolation=None)
        plugin.optionxform = str
        plugin.read(PLUGIN, encoding="utf-8")
        entry = plugin["Desktop Entry"]
        service = configparser.ConfigParser(interpolation=None)
        service.optionxform = str
        service.read(SERVICE, encoding="utf-8")
        self.assertEqual(entry["X-Plasma-DBusRunner-Service"], service["D-BUS Service"]["Name"])
        self.assertEqual(service["D-BUS Service"]["Exec"], "/usr/libexec/moos-store-krunner")
        self.assertEqual(entry["X-Plasma-DBusRunner-Path"], "/runner")
        self.assertEqual(entry["Name[ar]"], "متجر MoOS")
        self.assertTrue(os.access(RUNNER, os.X_OK))


if __name__ == "__main__":
    unittest.main(verbosity=2)
