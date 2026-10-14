#!/usr/bin/env python3
"""Gate: Mo Store in Plasma's search bar suggests apps and only ever opens their Store page.

WHY THIS EXISTS
Discover's AppStream runner is disabled in MoOS (it opened a second, hidden store), so until
moos-store-krunner a person typing "gimp" or "واتساب" into MoOS Search found nothing for an app
they did not have yet. KRunner sends the runner whatever is typed and hands the chosen id back as
a string, so this gate proves:

* Arabic is matched the way people type it (no diacritics, any alef, ta marbuta, Arabic digits);
* installed apps are not offered again, and the result list is short;
* a chosen id is looked up again in the index — a tampered or unknown id starts nothing;
* the only thing a result starts is Mo Store, with `--app=<id>` as one argv element;
* the runner reads only its local index (no network), re-reads it when it changes, and its
  plugin and D-Bus activation files name the same service.
"""

from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "system_files/usr/libexec/moos-store-krunner"
PLUGIN = ROOT / "system_files/usr/share/krunner/dbusplugins/org.moos.store.desktop"
SERVICE = ROOT / "system_files/usr/share/dbus-1/services/org.moos.StoreRunner.service"

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


class Runner(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "index.json"
        self.path.write_text(json.dumps({"apps": APPS}), encoding="utf-8")
        self.runner = load()
        self.index = self.runner["Index"](self.path)

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
        with mock.patch.dict(os.environ, {"LANG": "ar_SA.UTF-8", "LC_ALL": ""}):
            first = self.runner["match"](self.index, "واتساب")[0]
        self.assertEqual(first[1], "ثبّت «واتساب» من متجر MoOS")
        self.assertEqual(first[2], "moos-store")
        with mock.patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": ""}):
            first = self.runner["match"](self.index, "whatsapp")[0]
        self.assertEqual(first[1], "Get WhatsApp from Mo Store")
        self.assertEqual(first[3], 100)

    def test_a_result_opens_only_the_store_page_of_a_known_app(self):
        calls = []
        self.runner["open_page"].__globals__["subprocess"] = mock.Mock(
            Popen=lambda argv, **_: calls.append(argv), DEVNULL=-3)
        self.assertTrue(self.runner["run"](self.index, "app:org.gimp.GIMP"))
        self.assertEqual(calls, [["/usr/bin/moos-store", "--app=org.gimp.GIMP"]])
        for forged in ("app:com.unknown.App", "app:../../etc", "app:x;rm -rf ~", "route:x",
                       "org.gimp.GIMP", "app:", 42):
            with self.subTest(forged=forged):
                self.assertFalse(self.runner["run"](self.index, forged))
        self.assertEqual(len(calls), 1)

    def test_the_index_is_reread_when_it_changes(self):
        self.assertEqual(self.ids("krita"), [])
        apps = APPS + [{"id": "org.kde.krita", "name": "Krita", "installable": True,
                        "installed": False}]
        self.path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        os.utime(self.path, ns=(1, 2))
        self.assertEqual(self.ids("krita"), ["app:org.kde.krita"])

    def test_no_network_and_no_shell(self):
        source = RUNNER.read_text(encoding="utf-8")
        for word in ("urllib", "http.client", "requests", "socket", "shell=True", "os.system"):
            with self.subTest(word=word):
                self.assertNotIn(word, source)


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
