#!/usr/bin/env python3
"""Gate: what Mo Store's catalogue says about an app is what the app's own makers say.

WHY THIS EXISTS
build_files/verify_store_catalog.py holds the catalogue to its schema, its pins and the words
MoOS never says. It cannot know whether a description is TRUE. A review of the Store library
(2026-10-15) checked six entries against their publishers and found each one telling a person
something the publisher does not:

  Jitsi Meet   "video meetings that need no account": the app opens meet.jit.si by default
               (jitsi-meet-electron app/features/config: defaultServerURL), and since
               24 August 2023 meet.jit.si needs a Google, GitHub or Facebook sign-in to START a
               meeting (jitsi.org/blog/authentication-on-meet-jit-si); guests still join without.
  Proton VPN   the card's publisher line said "Proton AG". Flathub's own description says
               "it is not an official Proton app. It is not affiliated with or supported by
               Proton AG", the listing is unverified, and Proton's Linux guide says the Flatpak
               is "developed and maintained by third-parties". Its packaging is a volunteer's.
  ChatGPT      its card was «تشات جي بي تي» while its hero card, its web entry, What's new and
               the menu entry its own package installs all write ChatGPT: one product, two
               names in one Discover row. The transliteration stays a search word.
  PhotoCraft   the first hero card, found by «فوتوشوب»: its README badges it "Status: early
               alpha", "not yet a Photoshop replacement for daily professional work".
  Flatseal     "what each installed app is allowed to reach", in the Privacy row: it manages the
               sandboxed apps from Flathub only, not web apps, Windows programs, Android apps or
               a publisher's own download; Mo Store's own permission pages cover every kind.
  Al-Quran     «صلاحيات» where the Store's every permission word is «أذونات».

Each check below names the fact it holds. When a publisher changes, the fact changes here too.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"


def catalogue() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def app(entry_id: str) -> dict:
    return next(entry for entry in catalogue()["apps"] if entry["id"] == entry_id)


class WhatThePublishersSay(unittest.TestCase):
    def test_jitsi_promises_no_account_only_to_guests(self):
        jitsi = app("org.jitsi.jitsi-meet")
        self.assertNotIn("need no account", jitsi["desc_en"])
        self.assertNotIn("لا تحتاج إلى حساب", jitsi["desc_ar"])
        self.assertIn("guests join without an account", jitsi["desc_en"])
        self.assertIn("ينضم الضيوف دون حساب", jitsi["desc_ar"])

    def test_the_proton_vpn_build_is_not_presented_as_protons(self):
        vpn = app("com.protonvpn.www")
        self.assertNotEqual(vpn["developer"], "Proton AG")
        self.assertIn("not Proton", vpn["developer"])
        self.assertIn("unofficial build", vpn["desc_en"])
        self.assertIn("نسخة غير رسمية", vpn["desc_ar"])

    def test_chatgpt_has_one_name_in_arabic(self):
        data = catalogue()
        chatgpt = app("chatgpt")
        hero = next(card for card in data["featured"] if card["app"] == "chatgpt")
        self.assertIn("ChatGPT", hero["title_ar"])
        self.assertIn("ChatGPT", app("chatgpt-web")["ar"])
        self.assertIn("ChatGPT", chatgpt["ar"], "the card, the hero card, the web entry and the "
                                               "menu must name one product one way")
        self.assertNotIn("تشات جي بي تي", chatgpt["ar"])
        self.assertIn("تشات جي بي تي", chatgpt["keywords_ar"], "typed in Arabic, it is still found")

    def test_photocraft_says_it_is_an_early_version(self):
        photocraft = app("photocraft")
        hero = next(card for card in catalogue()["featured"] if card["app"] == "photocraft")
        for text in (photocraft["desc_en"], hero["tagline_en"]):
            self.assertIn("early", text)
        for text in (photocraft["desc_ar"], hero["tagline_ar"]):
            self.assertIn("مرحلة", text)
            self.assertIn("مبكرة", text)

    def test_flatseal_claims_only_the_apps_it_manages_and_is_not_a_privacy_pick(self):
        flatseal = app("com.github.tchx84.Flatseal")
        self.assertNotIn("each installed app", flatseal["desc_en"])
        self.assertNotIn("لكل تطبيق مثبّت", flatseal["desc_ar"])
        self.assertIn("sandboxed Linux apps", flatseal["desc_en"])
        self.assertIn("تطبيقات لينكس المعزولة", flatseal["desc_ar"])
        privacy = next(row for row in catalogue()["collections"] if row["id"] == "privacy")
        self.assertNotIn("com.github.tchx84.Flatseal", privacy["apps"])


class OneWordForPermissions(unittest.TestCase):
    """The Store's permission controls, messages and What's new say «أذونات»/«إذن»; a description
    on the same page said «صلاحيات». Search words may keep it: people type both."""

    def test_no_arabic_copy_says_salahiyat(self):
        data = catalogue()
        shown = []
        for entry in data["apps"]:
            shown += [(entry["id"], key, entry.get(key, "")) for key in ("ar", "desc_ar")]
        for row in data["collections"]:
            shown += [(row["id"], key, row.get(key, "")) for key in ("ar", "desc_ar")]
        for card in data["featured"]:
            shown += [(card["app"], key, card.get(key, "")) for key in ("title_ar", "tagline_ar")]
        for bundle in data["bundles"]:
            shown += [(bundle["id"], key, bundle.get(key, "")) for key in ("ar", "desc_ar")]
        self.assertEqual([(where, key) for where, key, text in shown if "صلاحي" in text], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
