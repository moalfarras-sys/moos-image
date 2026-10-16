#!/usr/bin/env python3
"""Mo Store catalogue v2: the shipped catalogue passes, and every new gate rule bites.

build_files/verify_store_catalog.py is the gate for the catalogue (docs/MO_STORE.md). A rule
that cannot fail protects nothing (AGENTS.md: "Prove a new gate bites by breaking the thing it
guards"), so each rule added for catalogue v2 has a negative control here: one bad value is
planted in a deep copy of the shipped catalogue and the exact refusal is asserted.

The chain half of the gate reads install paths another component owns (moos-storectl's
dispatch and handlers, the vendor-package helper). Its negative controls break one path in a
copy of the backend in the tree; its positive controls are that backend unchanged, so a backend
refactor fails here by name rather than silently.
"""

import ast
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "build_files/verify_store_catalog.py"
SYSTEM = ROOT / "system_files"
BUILD = ROOT / "build_files"
CATALOG = SYSTEM / "usr/share/moos/store/catalog.json"


def load_gate():
    sys.dont_write_bytecode = True
    loader = importlib.machinery.SourceFileLoader("verify_store_catalog_under_test",
                                                  str(GATE_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


gate = load_gate()
SHIPPED = json.loads(CATALOG.read_text(encoding="utf-8"))


def app(catalog, app_id):
    return next(entry for entry in catalog["apps"] if entry["id"] == app_id)


def errors_for(mutate, root=SYSTEM, build=BUILD):
    catalog = copy.deepcopy(SHIPPED)
    mutate(catalog)
    report, _facts = gate.check_catalog(catalog, root, build)
    return report.errors


def mirror_root(base: Path, overrides: dict[str, str | None] | None = None) -> Path:
    """A private image root: every file the gate reads, linked from system_files.

    `overrides` maps an image path to replacement text (or None to leave it absent).
    """
    overrides = overrides or {}
    root = base / "root"
    paths = [gate.CATALOG, gate.STORE_QML, gate.WELCOME_QML, gate.SYMBOL_CATALOG,
             gate.MOOS_STORECTL, gate.MOOS_STORE_INDEX, gate.MOOS_OPEN, gate.MOOS_STORE,
             gate.MOOS_WELCOME, gate.MOOS_SELFCHECK, gate.WEBAPP_POLICY, gate.VENDOR_RPM_HELPER,
             *(entry[2] for entry in gate.VENDOR_RPM_ALLOWLIST.values())]
    for image_path in paths:
        target = root / image_path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if image_path in overrides:
            if overrides[image_path] is not None:
                target.write_text(overrides[image_path], encoding="utf-8")
            continue
        source = SYSTEM / image_path.lstrip("/")
        if source.exists():
            target.symlink_to(source)
    return root


class TheShippedCatalogue(unittest.TestCase):
    def test_it_passes_every_catalogue_rule(self):
        report, facts = gate.check_catalog(copy.deepcopy(SHIPPED), SYSTEM, BUILD)
        self.assertEqual(report.errors, [])
        self.assertLessEqual({"webapp", "appdrop", "windows-portable", "android", "vendor-rpm",
                              "npm"}, facts["used_kinds"])

    def test_it_has_the_v2_shape(self):
        self.assertEqual({c["id"] for c in SHIPPED["categories"]}, gate.CATEGORY_IDS)
        self.assertTrue(8 <= len(SHIPPED["collections"]) <= 14)
        self.assertLessEqual({"craft-family", "instead-of-adobe"},
                             {row["id"] for row in SHIPPED["collections"]})
        self.assertTrue(5 <= len(SHIPPED["featured"]) <= 7)
        self.assertEqual(len(SHIPPED["bundles"]), 5)
        self.assertLessEqual({"game-starter", "dev-starter", "study-starter", "office-starter"},
                             {b["id"] for b in SHIPPED["bundles"]})
        self.assertGreaterEqual(len(SHIPPED["apps"]), 140)

    def test_every_android_pin_records_its_signer_and_every_download_its_size(self):
        android = [a for a in SHIPPED["apps"] if (a.get("install") or {}).get("kind") == "android"]
        self.assertEqual(len(android), 48)
        for entry in android:
            with self.subTest(app=entry["id"]):
                self.assertRegex(entry["install"]["signer"], r"^[0-9a-f]{64}$")
                self.assertGreater(entry["install"]["size"], 0)

    def test_newpipe_is_pinned_to_its_developer_signed_file(self):
        newpipe = app(SHIPPED, "org.schabi.newpipe")["install"]
        self.assertTrue(newpipe["url"].endswith("org.schabi.newpipe_1015_cb84069.apk"))
        self.assertTrue(newpipe["signer"].startswith("cb84069"))

    def test_the_trusted_vendor_key_is_the_one_the_catalogue_names(self):
        key = (SYSTEM / "etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt").read_text(encoding="utf-8")
        self.assertEqual(gate.pgp_v4_fingerprint(key), "3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4")
        self.assertEqual(app(SHIPPED, "chatgpt")["install"]["key_fingerprint"],
                         gate.pgp_v4_fingerprint(key))


class ThePublicSuffixList(unittest.TestCase):
    """The list the gate vendors and the algorithm it runs on it (https://publicsuffix.org/list/)."""

    @classmethod
    def setUpClass(cls):
        cls.suffixes = gate.load_public_suffixes(gate.PUBLIC_SUFFIX_LIST)

    def test_the_vendored_list_is_the_published_one_its_readme_names(self):
        raw = gate.PUBLIC_SUFFIX_LIST.read_bytes()
        text = raw.decode("utf-8")
        self.assertTrue(text.startswith("// This Source Code Form is subject to the terms of the "
                                        "Mozilla Public\n// License, v. 2.0."), "MPL-2.0 header")
        self.assertIn("// ===END PRIVATE DOMAINS===", text, "the list is cut short")
        version = re.search(r"(?m)^// VERSION: (\S+)$", text).group(1)
        readme = (gate.PUBLIC_SUFFIX_LIST.parent / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"VERSION: {version}", readme, "README.md describes another version")
        self.assertIn(hashlib.sha256(raw).hexdigest(), readme,
                      "README.md records another file: refresh its table with the list")

    def test_the_algorithm(self):
        for name in ("com", "co.uk", "github.io", "notion.site", "microsoft",
                     "foo.ck",            # *.ck: every name under ck is a suffix …
                     "x.kawasaki.jp",     # … and every name under kawasaki.jp
                     "xn--55qx5d.cn"):    # 公司.cn, compared as its A-label
            with self.subTest(name=name):
                self.assertTrue(self.suffixes.is_public_suffix(name))
        for name in ("secure-login.notion.site", "bbc.co.uk", "cloud.microsoft", "claude.ai",
                     "www.ck",            # !www.ck: the exception to *.ck
                     "city.kawasaki.jp",  # !city.kawasaki.jp
                     "compute.amazonaws.com", "site.example"):
            with self.subTest(name=name):
                self.assertFalse(self.suffixes.is_public_suffix(name))
        self.assertEqual(self.suffixes.public_suffix("a.b.foo.ck"), "foo.ck")
        self.assertEqual(self.suffixes.public_suffix("a.www.ck"), "ck")
        self.assertEqual(self.suffixes.public_suffix("site.example"), "example")
        self.assertIn("*.compute.amazonaws.com", self.suffixes.rules_under("compute.amazonaws.com"))
        self.assertEqual(self.suffixes.rules_under("notion.so"), [])

    def test_without_its_list_the_gate_fails(self):
        with tempfile.TemporaryDirectory() as raw:
            planted = Path(raw) / "public_suffix_list.dat"
            with mock.patch.object(gate, "PUBLIC_SUFFIX_LIST", planted):
                errors = errors_for(lambda c: None)
            self.assertTrue(any("cannot read the Public Suffix List" in e for e in errors), errors)
            planted.write_text("// a list cut short\ncom\nnotion.site\n", encoding="utf-8")
            with mock.patch.object(gate, "PUBLIC_SUFFIX_LIST", planted):
                errors = errors_for(lambda c: None)
            self.assertTrue(any("the list is truncated" in e for e in errors), errors)

    def test_a_rule_the_gate_would_misread_is_refused(self):
        text = gate.PUBLIC_SUFFIX_LIST.read_text(encoding="utf-8") + "\nfoo.*.example\n"
        with self.assertRaises(ValueError):
            gate.PublicSuffixes(text)


class EveryNewCatalogueRuleBites(unittest.TestCase):
    def refused(self, mutate, fragment, **kwargs):
        errors = errors_for(mutate, **kwargs)
        self.assertTrue(any(fragment in error for error in errors),
                        f"expected a refusal containing {fragment!r}; the gate said: {errors}")

    # ── structure ──────────────────────────────────────────────────────────────────────────
    def test_unknown_top_level_key(self):
        self.refused(lambda c: c.update(editorial=[]), "unknown top-level key 'editorial'")

    def test_categories_must_be_exactly_the_contract(self):
        self.refused(lambda c: c["categories"].pop(), "the categories must be exactly")
        self.refused(lambda c: c["categories"].append(
            {"id": "misc", "en": "Misc", "ar": "متفرقات", "glyph": "grid"}),
            "the categories must be exactly")

    def test_a_glyph_must_be_a_symbol_catalog_name(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(glyph="gamepad"),
                     "'gamepad' is not a SymbolCatalog name")
        self.refused(lambda c: c["categories"][0].update(glyph="doc"),
                     "is not a SymbolCatalog name")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(glyph="snake_case"),
                     "glyph is not canonical")

    def test_an_unknown_app_key_is_refused(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(keyword_en=["photoshop"]),
                     "has unknown key 'keyword_en'")

    # ── words ─────────────────────────────────────────────────────────────────────────────
    def test_two_apps_cannot_share_a_name(self):
        self.refused(lambda c: app(c, "org.kde.krita").update(en="GIMP"), "is also the name of")
        self.refused(lambda c: app(c, "org.kde.krita").update(ar="جيمب"), "is also the name of")

    def test_each_field_is_in_its_own_language(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(ar="GIMP"),
                     "must be written in Arabic")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(desc_en="محرر صور."),
                     "must not contain Arabic letters")

    def test_a_description_is_one_short_sentence_with_a_full_stop(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(desc_en="A" * 140 + "."),
                     "the limit is 140")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(desc_en="Edits photos"),
                     "must end with a full stop")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(desc_en="Edits photos. And more."),
                     "must be one sentence")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(desc_ar="يحرر الصور. وأكثر."),
                     "must be one sentence")

    def test_moos_never_names_machinery_or_another_system(self):
        for text in ("Runs through Wine.", "A Flatpak of GIMP.", "Packaged on Flathub.",
                     "From F-Droid.", "Built for KDE Plasma.", "Made by Red Hat.",
                     "Works like on Fedora.", "Uses Chromium inside."):
            with self.subTest(text=text):
                self.refused(lambda c, t=text: app(c, "org.gimp.GIMP").update(desc_en=t),
                             "names machinery or another system")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(desc_ar="يعمل عبر فلاتباك."),
                     "names machinery or another system")
        self.refused(lambda c: c["featured"][0].update(tagline_en="Now on Flathub."),
                     "names machinery or another system")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(en="GIMP for Ubuntu"),
                     "names machinery or another system")

    def test_the_developer_is_named_and_never_another_system(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").pop("developer"),
                     "developer must be a non-empty canonical string")
        self.refused(lambda c: app(c, "org.kde.kdenlive").update(developer="KDE"),
                     "developer names another system or desktop")
        self.refused(lambda c: app(c, "com.github.marhkb.Pods").update(developer="Red Hat, Inc."),
                     "developer names another system or desktop")

    def test_search_words_are_few_unique_and_clean(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(keywords_en=[f"w{i}" for i in range(13)]),
                     "must be a list of 1 to 12 search words")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(keywords_en=["paint", "Paint"]),
                     "repeats")
        self.refused(lambda c: app(c, "com.usebottles.bottles").update(keywords_en=["wine"]),
                     "names machinery")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(keywords_ar=["photoshop"]),
                     "must be written in Arabic")

    # ── colour, platform, selection ───────────────────────────────────────────────────────
    def test_an_accent_is_required_canonical_and_readable(self):
        self.refused(lambda c: app(c, "claude").pop("accent"), "needs an accent")
        self.refused(lambda c: app(c, "putty").update(accent="#2B5797"), "accent is not canonical")
        self.refused(lambda c: app(c, "putty").update(accent="#ffeb3b"), "against white text")

    def test_architecture_and_engine_values(self):
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(arch=["armv7"]),
                     "arch must be a non-empty list drawn from")
        self.refused(lambda c: app(c, "putty").update(engine="dos"),
                     "engine must be 'windows' or 'android'")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(engine="windows"),
                     "must not declare an engine")

    def test_preselection_is_sandboxed_and_universal(self):
        self.refused(lambda c: app(c, "com.valvesoftware.Steam").update(preselect=True),
                     "must run on every architecture")
        self.refused(lambda c: app(c, "claude").update(preselect=True),
                     "must be a sandboxed Flatpak")

    def test_a_card_is_the_platform_it_installs(self):
        self.refused(lambda c: app(c, "putty").update(cat="dev"),
                     "a Windows program needs engine 'windows'")
        self.refused(lambda c: app(c, "claude").update(cat="win"),
                     "only a windows-portable recipe belongs to Windows programs")
        self.refused(lambda c: app(c, "app.organicmaps").update(cat="util"),
                     "an Android app needs engine 'android' and cat 'droid'")
        self.refused(lambda c: app(c, "claude").update(cat="droid"),
                     "only an android recipe belongs to Android apps")

    # ── kinds ─────────────────────────────────────────────────────────────────────────────
    def test_the_bare_appimage_kind_is_retired(self):
        self.refused(lambda c: app(c, "photocraft")["install"].update(kind="appimage"),
                     "uses retired install kind 'appimage'")
        self.refused(lambda c: app(c, "photocraft")["install"].update(kind="snap"),
                     "has unknown install kind 'snap'")

    def test_each_recipe_holds_exactly_its_keys_and_risk(self):
        self.refused(lambda c: app(c, "putty")["install"].pop("exe"), "is missing ['exe']")
        self.refused(lambda c: app(c, "putty")["install"].update(referer="https://x.example/"),
                     "has unknown keys ['referer']")
        self.refused(lambda c: app(c, "putty")["install"].update(risk="external-download"),
                     ".risk must be 'downloaded-executable'")
        self.refused(lambda c: app(c, "claude")["install"].update(risk="external-download"),
                     ".risk must be 'web-app'")
        self.refused(lambda c: app(c, "putty")["install"].update(external=False),
                     "install.external must be true")

    # ── pinned downloads (appdrop, windows-portable) ──────────────────────────────────────
    def test_a_download_is_the_publishers_exact_file(self):
        def mirror(c):
            item = app(c, "putty")["install"]["downloads"]["x86_64"]
            item["url"] = "https://mirror.example.org/putty/0.85/w64/putty.exe"
        self.refused(mirror, "is not the publisher's x86_64 download for version 0.85")

        def new_version_old_url(c):
            app(c, "notepad-plus-plus")["install"]["version"] = "8.9.9"
        self.refused(new_version_old_url, "is not the publisher's x86_64 download for version 8.9.9")

        def swapped_architectures(c):
            downloads = app(c, "photocraft")["install"]["downloads"]
            downloads["x86_64"]["url"], downloads["aarch64"]["url"] = (
                downloads["aarch64"]["url"], downloads["x86_64"]["url"])
        self.refused(swapped_architectures, "is not the publisher's x86_64 download")

        def unknown_app(c):
            entry = app(c, "putty")
            entry["id"], entry["en"], entry["ar"] = "kitty-ssh", "KiTTY", "كيتي"
        self.refused(unknown_app, "has no exact download rule")

    def test_a_catalogue_url_never_carries_a_query_or_fragment(self):
        for suffix in ("?raw=1", "#top", "?", "#"):
            with self.subTest(suffix=suffix):
                def plant(c, s=suffix):
                    item = app(c, "putty")["install"]["downloads"]["x86_64"]
                    item["url"] += s
                self.refused(plant, "url must not carry a query or fragment")

    def test_a_download_carries_a_canonical_digest_and_a_real_size(self):
        for size in (True, 0, -1, 5 * 1024 ** 3, "1706136"):
            with self.subTest(size=size):
                self.refused(lambda c, s=size: app(c, "putty")["install"]["downloads"]["x86_64"]
                             .update(size=s), "size must be an integer byte count")
        self.refused(lambda c: app(c, "putty")["install"]["downloads"]["x86_64"].update(
            sha256="D01FDB5AAE8F112526040A39B0BFB9E27D813003178645E65F8D1CFDB2A26C87"),
            "sha256 is not canonical")
        self.refused(lambda c: app(c, "putty")["install"]["downloads"]["x86_64"].update(md5="x"),
                     "must hold exactly url, sha256 and size")

        def copied(c):
            downloads = app(c, "photocraft")["install"]["downloads"]
            downloads["aarch64"]["sha256"] = downloads["x86_64"]["sha256"]
        self.refused(copied, "two architectures pin the same SHA-256")

    def test_a_windows_program_is_one_64_bit_exe(self):
        self.refused(lambda c: app(c, "putty")["install"]["downloads"].update(
            aarch64=dict(app(c, "putty")["install"]["downloads"]["x86_64"])),
            "is pinned for x86_64 only")
        self.refused(lambda c: app(c, "notepad-plus-plus")["install"].update(exe="notepad++.bat"),
                     "must be a .exe file")
        for exe in ("../notepad++.exe", "/notepad++.exe", "-notepad++.exe"):
            with self.subTest(exe=exe):
                self.refused(lambda c, e=exe: app(c, "notepad-plus-plus")["install"].update(exe=e),
                             "must be a relative path inside the download")
        self.refused(lambda c: app(c, "putty")["install"].update(exe="pageant.exe"),
                     "a single-file download's exe is its own file name")

    def test_an_appdrop_recipe_is_complete_and_consistent(self):
        self.refused(lambda c: app(c, "photocraft").update(arch=["x86_64"]),
                     "arch must equal the sorted download architectures")
        self.refused(lambda c: app(c, "photocraft")["install"].update(artifact="deb"),
                     "artifact must be 'appimage' or 'archive'")
        self.refused(lambda c: app(c, "antigravity")["install"].pop("exec"),
                     "an archive must name its program")
        self.refused(lambda c: app(c, "photocraft")["install"].update(exec="AppRun"),
                     "exec and icon belong to archives")
        self.refused(lambda c: app(c, "antigravity-ide")["install"].update(icon="code.ico"),
                     "must be a .png or .svg file")
        self.refused(lambda c: app(c, "photocraft")["install"].update(desktop_id="photocraft"),
                     "desktop_id is not canonical")
        self.refused(lambda c: app(c, "photocraft")["install"].update(
            desktop_id="org.moos.store"), "must never shadow a MoOS launcher")
        self.refused(lambda c: app(c, "photocraft")["install"].update(categories=["Photos"]),
                     "must be freedesktop main categories")
        self.refused(lambda c: app(c, "photocraft")["install"].update(wm_class="photo;craft"),
                     "wm_class is not canonical")
        self.refused(lambda c: app(c, "photocraft").pop("arch"),
                     "must say which architectures it exists for")

    # ── Android ───────────────────────────────────────────────────────────────────────────
    def test_an_android_pin_comes_from_the_main_repository(self):
        self.refused(lambda c: app(c, "app.organicmaps")["install"].update(
            url="https://ftp.gwdg.de/pub/android/fdroid/repo/app.organicmaps_26092932.apk"),
            "must be app.organicmaps's own file in https://f-droid.org/repo/")
        self.refused(lambda c: app(c, "app.organicmaps")["install"].update(
            url="https://f-droid.org/repo/org.wikipedia_50610.apk"),
            "must be app.organicmaps's own file")

    def test_an_android_pin_records_signer_and_size(self):
        self.refused(lambda c: app(c, "app.organicmaps")["install"].pop("signer"),
                     "is missing ['signer']")
        self.refused(lambda c: app(c, "app.organicmaps")["install"].update(signer="E216FC38"),
                     "signer is not canonical")
        self.refused(lambda c: app(c, "app.organicmaps")["install"].pop("size"),
                     "is missing ['size']")
        self.refused(lambda c: app(c, "app.organicmaps")["install"].update(version="r/1"),
                     "version is not canonical")

    def test_a_developer_signed_file_keeps_its_developer_signer(self):
        # F-Droid's own key for NewPipe, recorded against the developer-signed file.
        self.refused(lambda c: app(c, "org.schabi.newpipe")["install"].update(
            signer="964dfa41" + "0" * 56), "the file is signed by cb84069")

    def test_the_package_is_the_id(self):
        self.refused(lambda c: app(c, "app.organicmaps")["install"].update(
            package="app.organicmaps.debug"), "must use its package id as the app id")

    # ── icons ─────────────────────────────────────────────────────────────────────────────
    def test_icon_urls_come_from_allowlisted_publishers_only(self):
        self.refused(lambda c: app(c, "claude").update(icon_url="https://claude.ai/icon.png"),
                     "a web app takes its icon from its own site")
        self.refused(lambda c: app(c, "putty").update(icon_url="https://the.earth.li/putty.png"),
                     "is not an allowlisted publisher host")
        self.refused(lambda c: app(c, "app.organicmaps").update(
            icon_url="https://f-droid.org/repo/org.wikipedia/en-US/icon_x.png"),
            "must be the signed index's own icon")
        self.refused(lambda c: app(c, "photocraft").update(
            icon_url="https://raw.githubusercontent.com/storytold/photocraft/main/icon.png"),
            "is not the publisher icon allowed for photocraft at its pinned version")
        self.refused(lambda c: app(c, "org.gimp.GIMP").update(
            icon_url="https://f-droid.org/repo/x.png"), "must not carry icon_url")

    # ── vendor RPM ────────────────────────────────────────────────────────────────────────
    def test_a_vendor_repository_package_and_key_are_allowlisted(self):
        self.refused(lambda c: app(c, "chatgpt")["install"].update(
            repo="https://example.com/rpm/$basearch"), "is not an allowlisted vendor repository")
        self.refused(lambda c: app(c, "chatgpt")["install"].update(package="codex"),
                     "is allowlisted for package 'chatgpt' only")
        self.refused(lambda c: app(c, "chatgpt")["install"].update(
            key_fingerprint="0" * 40), "is signed by 3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4")
        self.refused(lambda c: app(c, "chatgpt")["install"].update(install_root="/usr/bin"),
                     "install_root is not canonical")
        self.refused(lambda c: app(c, "chatgpt")["install"].update(exec="../../bin/sh"),
                     "must be a relative path")
        self.refused(lambda c: app(c, "chatgpt")["install"].update(desktop="/etc/xdg/a.desktop"),
                     "desktop is not canonical")
        self.refused(lambda c: app(c, "chatgpt").pop("arch"),
                     "must say which architectures it exists for")

    def test_the_vendor_key_must_be_one_the_image_trusts(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            build = base / "build"
            build.mkdir()
            for script in ("build.sh", "build-arm.sh"):
                text = (BUILD / script).read_text(encoding="utf-8")
                cut = re.sub(r"(?m)^\s*rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt\s*$",
                             "# import removed", text)
                (build / script).write_text(cut, encoding="utf-8")
            errors = errors_for(lambda c: None, build=build)
            self.assertTrue(any("build.sh does not trust" in e for e in errors), errors)
            self.assertTrue(any("build-arm.sh does not trust" in e for e in errors), errors)

            other_key = (SYSTEM / "etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt").read_text(
                encoding="utf-8")
            # A different, valid-looking key: flip one base64 character in the key body.
            lines = other_key.splitlines()
            lines[3] = ("A" if lines[3][0] != "A" else "B") + lines[3][1:]
            root = mirror_root(base / "keyswap", {
                "/etc/pki/rpm-gpg/RPM-GPG-KEY-openai-chatgpt": "\n".join(lines) + "\n"})
            errors = errors_for(lambda c: None, root=root)
            self.assertTrue(any("has fingerprint" in e or "cannot read the trusted key" in e
                                for e in errors), errors)

    # ── npm, web, webapp ──────────────────────────────────────────────────────────────────
    def test_npm_recipes_are_the_exact_allowlist(self):
        self.refused(lambda c: app(c, "gemini-cli")["install"].update(bin="gemini-cli"),
                     "must use exact recipe pkg='@google/gemini-cli'")
        self.refused(lambda c: app(c, "gemini-cli").update(id="gemini-tool"),
                     "is not in the exact recipe allowlist")

    def test_a_web_link_says_it_only_opens_the_publishers_page(self):
        def plant(c):
            c["apps"].append({
                "id": "seven-zip", "source": "moos", "cat": "util", "glyph": "folder",
                "en": "7-Zip", "ar": "سفن زيب", "desc_en": "Compresses files.",
                "desc_ar": "يضغط الملفات.", "developer": "Igor Pavlov", "accent": "#2b5797",
                "install": {"kind": "web", "url": "https://www.7-zip.org/download.html",
                            "external": True, "risk": "external-download",
                            "requires_review": True}})
        self.refused(plant, "must say so")
        self.refused(plant, "uses non-allowlisted domain 'www.7-zip.org'")

    def test_a_web_app_is_valid_for_the_web_app_policy(self):
        self.refused(lambda c: app(c, "claude")["install"].update(accent="#000000"),
                     "install.accent must equal the app's accent")
        self.refused(lambda c: app(c, "claude")["install"].update(url="https://evil.example/"),
                     "is refused by moos_webapp_policy")
        self.refused(lambda c: app(c, "claude")["install"].update(permissions=["root"]),
                     "is refused by moos_webapp_policy")

    def test_a_web_app_never_claims_other_peoples_sites(self):
        # Every Notion user's published page, every GitHub Pages site, every .co.uk company.
        self.refused(lambda c: app(c, "notion")["install"]["hosts"].append("*.notion.site"),
                     "'*.notion.site' covers every site under the public suffix 'notion.site'")
        self.refused(lambda c: app(c, "photopea")["install"]["hosts"].append("*.github.io"),
                     "'*.github.io' covers every site under the public suffix 'github.io'")
        self.refused(lambda c: app(c, "photopea")["install"]["hosts"].append("*.co.uk"),
                     "the public suffix 'co.uk'")
        self.refused(lambda c: app(c, "notion")["install"]["hosts"].append("github.io"),
                     "'github.io' is a public suffix")
        # Not a suffix itself, but the list hands out names inside it: every compute host is
        # another customer's.
        self.refused(lambda c: app(c, "photopea")["install"]["hosts"].append(
            "*.compute.amazonaws.com"), "spans sites of different owners")

    def test_one_owners_site_under_a_public_suffix_is_its_own(self):
        """Positive control: the planted value, not the wildcard syntax, is what is refused."""
        self.assertEqual(errors_for(lambda c: app(c, "notion")["install"]["hosts"].extend(
            ["*.notion.so", "moos.github.io"])), [])

    # ── collections, featured, bundles ────────────────────────────────────────────────────
    def test_collections(self):
        self.refused(lambda c: c["collections"][0].update(apps=c["collections"][0]["apps"][:3]),
                     "must list 4 to 24 apps")
        self.refused(lambda c: c["collections"][0]["apps"].extend(
            a["id"] for a in c["apps"][:30]), "must list 4 to 24 apps")
        self.refused(lambda c: c["collections"][0]["apps"].append("no.such.App"),
                     "references undefined app 'no.such.App'")
        self.refused(lambda c: c["collections"][0]["apps"].append({"id": "org.gimp.GIMP"}),
                     "references undefined app {'id'")
        self.refused(lambda c: c["collections"][0]["apps"].append(c["collections"][0]["apps"][0]),
                     "repeats an app")
        self.refused(lambda c: c["collections"][0].pop("desc_ar"),
                     "must describe itself in both languages or in neither")
        self.refused(lambda c: c["collections"][0].update(position=1), "has unknown key")
        self.refused(lambda c: c["collections"][0].update(glyph="sparkles"),
                     "is not a SymbolCatalog name")

    def test_featured_cards(self):
        self.refused(lambda c: c.update(featured=c["featured"][:2]), "must hold 3 to 8 hero cards")
        self.refused(lambda c: c["featured"].extend(copy.deepcopy(c["featured"][:2]) * 1
                                                    + copy.deepcopy(c["featured"][:2])),
                     "must hold 3 to 8 hero cards")
        self.refused(lambda c: c["featured"][0].update(app="no.such.App"),
                     "features undefined app")
        self.refused(lambda c: c["featured"].append(copy.deepcopy(c["featured"][0])), "twice")
        self.refused(lambda c: c["featured"][0].update(tagline_en="A" * 100 + "."),
                     "the limit is 100")
        self.refused(lambda c: c["featured"][0].update(accent="#10a37f"), "it needs 4.5:1")

        def only_x86(c):
            c["featured"] = [{"app": i, "title_en": "T", "title_ar": "ع",
                              "tagline_en": "Play.", "tagline_ar": "العب."}
                             for i in ("com.valvesoftware.Steam", "com.spotify.Client",
                                       "com.discordapp.Discord")]
        self.refused(only_x86, "at least three hero cards")

    def test_a_bundle_holds_sandboxed_apps_only(self):
        self.refused(lambda c: c["bundles"][0]["apps"].append("cursor"),
                     "bundles hold sandboxed apps only")
        self.refused(lambda c: c["bundles"][0].update(desc_en="Editors and databases"),
                     "must end with a full stop")


class TheGateAndTheWebAppPolicyAgree(unittest.TestCase):
    """One rule for a web app's id and for a query or fragment on its start page.

    The gate once refused `1password` and `https://web.whatsapp.com/#/` while
    moos_webapp_policy (and the contract) accepted both. Each case plants a second WhatsApp entry
    and asks both: the gate's whole report (the shipped catalogue has none) and parse_entry.
    moos-store-index answers to the same policy in tests/test_mo_store_index_catalogue.py
    (CatalogueV2Kinds), so the Store never lists an app whose window would refuse to open.
    """

    policy = gate.load_source_module("moos_webapp_policy_under_test",
                                     SYSTEM / gate.WEBAPP_POLICY.lstrip("/"))

    def verdicts(self, app_id: str, url: str) -> tuple[bool, bool]:
        planted = copy.deepcopy(app(SHIPPED, "whatsapp"))
        planted.update(id=app_id, en="WhatsApp Two", ar="واتساب الثاني")
        planted["install"]["url"] = url
        errors = errors_for(lambda c: c["apps"].append(planted))
        try:
            self.policy.parse_entry(planted)
            policy_refuses = False
        except self.policy.WebAppError:
            policy_refuses = True
        return bool(errors), policy_refuses

    def test_on_the_id(self):
        for app_id, refused in (("whatsapp-two", False), ("ab", False), ("office365", False),
                                ("x" * 63, False), ("1password", True), ("a", True),
                                ("x" * 64, True), ("whatsapp--two", True), ("whatsapp-", True),
                                ("-whatsapp", True), ("WhatsApp", True), ("whatsapp_two", True),
                                ("whatsapp.two", True)):
            with self.subTest(app_id=app_id):
                self.assertEqual(self.verdicts(app_id, "https://web.whatsapp.com/"),
                                 (refused, refused))

    def test_on_a_query_or_fragment(self):
        for url, refused in (("https://web.whatsapp.com/", False),
                             ("https://web.whatsapp.com/send", False),
                             ("https://web.whatsapp.com/#/", True),
                             ("https://web.whatsapp.com/?lang=ar", True),
                             ("https://web.whatsapp.com/?", True),
                             ("https://web.whatsapp.com/#", True),
                             ("https://web.whatsapp.com/send?b#c", True)):
            with self.subTest(url=url):
                self.assertEqual(self.verdicts("whatsapp-two", url), (refused, refused))


def without_vendor_rpm(catalog):
    """The catalogue minus its vendor-rpm entry, so an indexer that predates that kind can
    still be asked about everything else (the gate itself still checks the full file)."""
    vendor = {a["id"] for a in catalog["apps"] if (a.get("install") or {}).get("kind") == "vendor-rpm"}
    catalog["apps"] = [a for a in catalog["apps"] if a["id"] not in vendor]
    for group in catalog["collections"] + catalog["bundles"]:
        group["apps"] = [i for i in group["apps"] if i not in vendor]
    catalog["featured"] = [f for f in catalog["featured"] if f["app"] not in vendor]
    return catalog


class TheIndexAndTheGateAgree(unittest.TestCase):
    def cross_check(self, catalog):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "catalog.json"
            path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
            report, _ = gate.check_catalog(catalog, SYSTEM, BUILD, path)
        return [e for e in report.errors if "moos-store-index" in e]

    def test_a_catalogue_the_indexer_refuses_fails_the_gate(self):
        planted = without_vendor_rpm(copy.deepcopy(SHIPPED))
        app(planted, "org.gimp.GIMP")["arch"] = "x86_64"   # a string, not a list
        refusals = self.cross_check(planted)
        self.assertTrue(any("moos-store-index refuses the catalogue" in e
                            and "org.gimp.GIMP" in e for e in refusals), refusals)

    def test_the_indexer_accepts_every_other_entry(self):
        """Positive control: the planted value, not the rest of the catalogue, is refused."""
        self.assertEqual(self.cross_check(without_vendor_rpm(copy.deepcopy(SHIPPED))), [])


NEW_KIND_TOKENS = ("_install_webapp", "_install_appdrop", "_install_windows_portable",
                   "_install_vendor_app")
STORECTL = (SYSTEM / "usr/bin/moos-storectl").read_text(encoding="utf-8")


def storectl_with(tokens: bool) -> str:
    """The backend in the tree; without `tokens`, the same file minus the v2 install paths and
    the web-app review risk. (A name merely mentioned somewhere no longer counts: the gate
    follows install()'s dispatch to each path.)"""
    if tokens:
        return STORECTL
    text = STORECTL
    for token in NEW_KIND_TOKENS:
        text = text.replace(token, "_install_unrelated")
    return text.replace('"web-app"', '"unrelated-risk"')


def in_method(source: str, method: str, pattern: str, replacement: str) -> str:
    """`source` with the one match of `pattern` inside moos-storectl's Controller.<method>
    replaced: the same text elsewhere in the file (another method's call) stays."""
    backend = next(node for node in ast.parse(source).body
                   if isinstance(node, ast.ClassDef) and node.name == "Controller")
    found = next(item for item in backend.body
                 if isinstance(item, ast.FunctionDef) and item.name == method)
    lines = source.splitlines(keepends=True)
    start, end = found.lineno - 1, found.end_lineno
    body, count = re.subn(pattern, replacement, "".join(lines[start:end]))
    if count != 1:
        raise AssertionError(f"{pattern!r} matches {count} times in {method}()")
    return "".join(lines[:start]) + body + "".join(lines[end:])


class TheChainNamesTheNewKinds(unittest.TestCase):
    def facts(self):
        return gate.check_catalog(copy.deepcopy(SHIPPED), SYSTEM, BUILD)[1]

    def test_a_backend_without_the_v2_install_paths_fails(self):
        with tempfile.TemporaryDirectory() as raw:
            root = mirror_root(Path(raw), {gate.MOOS_STORECTL: storectl_with(False),
                                           gate.VENDOR_RPM_HELPER: None})
            errors = gate.check_chain(self.facts(), root, BUILD).errors
        for token in NEW_KIND_TOKENS:
            self.assertTrue(any(f"lacks required handler token {token!r}" in e for e in errors),
                            (token, errors))
        self.assertTrue(any("never names that review risk" in e for e in errors), errors)
        self.assertTrue(any("never runs `rpmkeys --checksig`" in e for e in errors), errors)

    def test_a_backend_with_them_satisfies_the_whole_chain(self):
        helper = "import subprocess\nsubprocess.run(['rpmkeys', '--checksig', 'x'])\n"
        with tempfile.TemporaryDirectory() as raw:
            root = mirror_root(Path(raw), {gate.MOOS_STORECTL: storectl_with(True),
                                           gate.VENDOR_RPM_HELPER: helper})
            errors = gate.check_chain(self.facts(), root, BUILD).errors
        self.assertEqual(errors, [])

    def test_a_checksig_mentioned_only_in_a_comment_does_not_count(self):
        helper = "# we should run rpmkeys --checksig here\nprint('later')\n"
        with tempfile.TemporaryDirectory() as raw:
            root = mirror_root(Path(raw), {gate.MOOS_STORECTL: storectl_with(True),
                                           gate.VENDOR_RPM_HELPER: helper})
            errors = gate.check_chain(self.facts(), root, BUILD).errors
        self.assertTrue(any("never runs `rpmkeys --checksig`" in e for e in errors), errors)


FACTS = gate.check_catalog(copy.deepcopy(SHIPPED), SYSTEM, BUILD)[1]


def chain_errors(storectl: str) -> list[str]:
    """The chain half of the gate, run on a mirror whose moos-storectl is `storectl`."""
    with tempfile.TemporaryDirectory() as raw:
        root = mirror_root(Path(raw), {gate.MOOS_STORECTL: storectl})
        return gate.check_chain(FACTS, root, BUILD).errors


def refusal(kind: str, method: str = "install") -> str:
    """The gate's words when Controller.<method> no longer hands `kind` to its installer."""
    purpose = "install" if method == "install" else "update"
    handler = (gate.KIND_HANDLER[kind][0] if method == "install" else gate.UPDATE_HANDLER[kind])
    return (f"the catalog uses install kind {kind!r} but moos-storectl's Controller.{method} does "
            f"not hand it to self.{handler}(), so those apps would never {purpose}")


# Both fixed calls reach the same installer; update carries the prior receipt
# so confirmation precedes publication. Preserve all two-direction mutations.
ANDROID_CALL = r"self\._install_pinned_android\(job, app_id, recipe(?:, updating=True, prior_record=before)?\)"


class TheChainNamesTheAndroidPath(unittest.TestCase):
    """The catalogue holds 48 Android recipes; nothing checked the backend could install one.

    Two mutations went unseen. Review, 2026-10-15: both calls of the Android installer replaced
    by a refusal, while the method itself stayed, so its NAME was still in the file. Verification
    of that fix: only install()'s call replaced, while the update path's call kept the CALL in the
    file; the gate printed "chain consistent" for an image whose Store refused every Android app.
    The gate now follows install()'s and _reinstall_pin()'s own branch for the kind.
    """

    def test_only_the_install_branch_refusing_fails(self):
        cut = in_method(STORECTL, "install", ANDROID_CALL, 'raise StoreError("no Android install")')
        self.assertEqual(len(re.findall(ANDROID_CALL, cut)), 1,
                         "the update path's call must survive, as in the mutation that went unseen")
        self.assertEqual(chain_errors(cut), [refusal("android")])

    def test_an_install_without_an_android_branch_fails(self):
        cut = in_method(STORECTL, "install",
                        r'\n[ \t]*elif kind == "android":\n[ \t]*' + ANDROID_CALL + r"\n", "\n")
        self.assertEqual(chain_errors(cut), [
            "the catalog uses install kind 'android' but moos-storectl's Controller.install has "
            "no branch for it, so those apps would never install"])

    def test_only_the_update_branch_refusing_fails(self):
        cut = in_method(STORECTL, "_reinstall_pin", ANDROID_CALL,
                        'raise StoreError("no Android update")')
        self.assertEqual(chain_errors(cut), [refusal("android", "_reinstall_pin")])

    def test_every_call_refusing_fails(self):
        """The review's own mutation."""
        cut, calls = re.subn(ANDROID_CALL, 'raise StoreError("no Android install")', STORECTL)
        self.assertEqual(calls, 2)
        self.assertEqual(chain_errors(cut),
                         [refusal("android"), refusal("android", "_reinstall_pin")])

    def test_each_android_token_is_required(self):
        self.assertEqual(gate.KIND_HANDLER["android"][0], "_install_pinned_android")
        for token in gate.KIND_HANDLER["android"]:
            with self.subTest(token=token):
                errors = chain_errors(STORECTL.replace(token, "_unrelated("))
                self.assertTrue(any(f"lacks required handler token {token!r}" in e for e in errors),
                                errors)

    def test_the_backend_as_shipped_satisfies_the_android_path(self):
        """Positive control: the real moos-storectl, unchanged, raises nothing for the kind."""
        self.assertIn("android", FACTS["used_kinds"])
        self.assertEqual([e for e in chain_errors(STORECTL) if "'android'" in e], [])


class EveryKindReachesItsInstaller(unittest.TestCase):
    """Every kind the catalogue uses, broken in its own branch of the real backend, one at a time:
    install() for all of them and _reinstall_pin() for the pinned ones."""

    def test_each_kind_needs_its_install_branch(self):
        kinds = sorted(FACTS["used_kinds"] & gate.KIND_HANDLER.keys())
        self.assertLessEqual({"android", "appdrop", "npm", "vendor-rpm", "webapp",
                              "windows-portable"}, set(kinds))
        for kind in kinds:
            with self.subTest(kind=kind):
                call = rf"self\.{gate.KIND_HANDLER[kind][0]}\(job, app_id, recipe\)"
                cut = in_method(STORECTL, "install", call, 'raise StoreError("refused")')
                self.assertEqual(chain_errors(cut), [refusal(kind)])

    def test_each_pinned_kind_needs_its_update_branch(self):
        kinds = sorted(FACTS["used_kinds"] & gate.UPDATE_HANDLER.keys())
        self.assertLessEqual({"android", "appdrop", "vendor-rpm", "windows-portable"}, set(kinds))
        for kind in kinds:
            with self.subTest(kind=kind):
                call = (ANDROID_CALL if kind == "android" else
                        rf"self\.{gate.UPDATE_HANDLER[kind]}\(job, app_id, recipe\)")
                # `None`, not a raise: the vendor branch calls its installer inside a condition.
                cut = in_method(STORECTL, "_reinstall_pin", call, "None")
                self.assertEqual(chain_errors(cut), [refusal(kind, "_reinstall_pin")])

    def test_a_call_in_a_comment_or_a_string_does_not_count(self):
        for label, replacement in (
                ("comment", "pass  # self._install_webapp(job, app_id, recipe)"),
                ("string", '"self._install_webapp(job, app_id, recipe)"')):
            with self.subTest(form=label):
                cut = in_method(STORECTL, "install", r"self\._install_webapp\(job, app_id, recipe\)",
                                replacement)
                self.assertEqual(chain_errors(cut), [refusal("webapp")])

    def test_the_installer_must_be_a_method_of_the_backend(self):
        cut = STORECTL.replace("def _install_pinned_android(", "def _install_pinned_android_v1(")
        self.assertNotEqual(cut, STORECTL)
        self.assertEqual(chain_errors(cut), [
            "the catalog uses install kind 'android' but moos-storectl's Controller has no "
            "method '_install_pinned_android' to install it",
            "the catalog uses install kind 'android' but moos-storectl's Controller has no "
            "method '_install_pinned_android' to update it"])

    def test_a_backend_the_parser_cannot_read_fails_once(self):
        errors = chain_errors(STORECTL + "\ndef broken(:\n")
        self.assertEqual(errors, ["moos-storectl has no Controller class the parser can read, so "
                                  "nothing shows where the catalog's kinds are installed"])

    def test_a_backend_without_an_update_path_fails_once(self):
        cut = STORECTL.replace("def _reinstall_pin(", "def _reinstall_pin_retired(")
        pinned = ", ".join(sorted(FACTS["used_kinds"] & gate.UPDATE_HANDLER.keys()))
        self.assertEqual(chain_errors(cut), [
            f"the catalog uses install kinds {pinned} but moos-storectl's "
            "Controller._reinstall_pin is missing, so none of them can update"])

    def test_the_backend_as_shipped_reaches_every_installer(self):
        """Positive control: the real moos-storectl, unchanged, satisfies the whole chain."""
        self.assertEqual(chain_errors(STORECTL), [])


class TheScriptFailsTheBuild(unittest.TestCase):
    """End to end: the gate script, its exit status and its message, on a planted mirror."""

    def run_gate(self, catalog: dict, storectl: str = STORECTL) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as raw:
            root = mirror_root(Path(raw), {
                gate.CATALOG: json.dumps(catalog, ensure_ascii=False, indent=1),
                gate.MOOS_STORECTL: storectl,
                gate.VENDOR_RPM_HELPER: "subprocess.run(['rpmkeys', '--checksig', p])\n"})
            env = dict(os.environ, MOOS_TEST_ROOT=str(root), PYTHONDONTWRITEBYTECODE="1")
            return subprocess.run([sys.executable, str(GATE_PATH)], env=env, text=True,
                                  capture_output=True, timeout=120)

    def test_a_planted_mirror_url_stops_the_build(self):
        planted = copy.deepcopy(SHIPPED)
        app(planted, "putty")["install"]["downloads"]["x86_64"]["url"] = \
            "https://mirror.example.org/~sgtatham/putty/0.85/w64/putty.exe"
        baseline = self.run_gate(copy.deepcopy(SHIPPED))
        bad = self.run_gate(planted)
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertIn("GATE FAIL", bad.stdout)
        self.assertIn("is not the publisher's x86_64 download for version 0.85", bad.stdout)
        self.assertNotIn("is not the publisher's x86_64 download", baseline.stdout)

    def test_a_store_that_refuses_every_android_install_stops_the_build(self):
        """The verification's mutation, end to end: install()'s Android call alone refuses."""
        cut = in_method(STORECTL, "install", ANDROID_CALL, 'raise StoreError("no Android install")')
        baseline = self.run_gate(copy.deepcopy(SHIPPED))
        bad = self.run_gate(copy.deepcopy(SHIPPED), cut)
        self.assertEqual(baseline.returncode, 0, baseline.stdout + baseline.stderr)
        self.assertIn("chain consistent", baseline.stdout)
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertIn("GATE FAIL: the MoOS Store chain is inconsistent", bad.stdout)
        self.assertIn(refusal("android"), bad.stdout)


class WhatThePublishersSay(unittest.TestCase):
    """What the shipped catalogue says about an app is what the app's own makers say.

    The gate holds the catalogue to its schema, its pins and the words MoOS never says; it cannot
    know whether a description is TRUE. A review of the Store library (2026-10-15) checked these
    five entries against their publishers and found each one telling a person something the
    publisher does not:

      Jitsi Meet   "video meetings that need no account": the app opens meet.jit.si by default
                   (jitsi-meet-electron app/features/config: defaultServerURL), and since
                   24 August 2023 meet.jit.si needs a Google, GitHub or Facebook sign-in to START
                   a meeting (jitsi.org/blog/authentication-on-meet-jit-si); guests still join
                   without one.
      Proton VPN   the card's publisher line said "Proton AG". Flathub's own description says "it
                   is not an official Proton app. It is not affiliated with or supported by
                   Proton AG", the listing is unverified, and Proton's Linux guide says the
                   Flatpak is "developed and maintained by third-parties".
      ChatGPT      its card was «تشات جي بي تي» while its hero card, its web entry, What's new
                   and the menu entry its own package installs all write ChatGPT: one product, two
                   names in one Discover row. The transliteration stays a search word.
      PhotoCraft   the first hero card, found by «فوتوشوب»: its README badges it "Status: early
                   alpha", "not yet a Photoshop replacement for daily professional work".
      Flatseal     "what each installed app is allowed to reach", in the Privacy row: it manages
                   the sandboxed apps from Flathub only, not web apps, Windows programs, Android
                   apps or a publisher's own download; Mo Store's own permission pages cover
                   every kind.

    Each check names the fact it holds. When a publisher changes, the fact changes here too.
    """

    def featured(self, app_id: str) -> dict:
        return next(card for card in SHIPPED["featured"] if card["app"] == app_id)

    def test_jitsi_promises_no_account_only_to_guests(self):
        jitsi = app(SHIPPED, "org.jitsi.jitsi-meet")
        self.assertNotIn("need no account", jitsi["desc_en"])
        self.assertNotIn("لا تحتاج إلى حساب", jitsi["desc_ar"])
        self.assertIn("guests join without an account", jitsi["desc_en"])
        self.assertIn("ينضم الضيوف دون حساب", jitsi["desc_ar"])

    def test_the_proton_vpn_build_is_not_presented_as_protons(self):
        vpn = app(SHIPPED, "com.protonvpn.www")
        self.assertNotEqual(vpn["developer"], "Proton AG")
        self.assertIn("not Proton", vpn["developer"])
        self.assertIn("unofficial build", vpn["desc_en"])
        self.assertIn("نسخة غير رسمية", vpn["desc_ar"])

    def test_chatgpt_has_one_name_in_arabic(self):
        chatgpt = app(SHIPPED, "chatgpt")
        self.assertIn("ChatGPT", self.featured("chatgpt")["title_ar"])
        self.assertIn("ChatGPT", app(SHIPPED, "chatgpt-web")["ar"])
        self.assertIn("ChatGPT", chatgpt["ar"], "the card, the hero card, the web entry and the "
                                               "menu must name one product one way")
        self.assertNotIn("تشات جي بي تي", chatgpt["ar"])
        self.assertIn("تشات جي بي تي", chatgpt["keywords_ar"], "typed in Arabic, it is still found")

    def test_photocraft_says_it_is_an_early_version(self):
        photocraft = app(SHIPPED, "photocraft")
        hero = self.featured("photocraft")
        for text in (photocraft["desc_en"], hero["tagline_en"]):
            self.assertIn("early", text)
        for text in (photocraft["desc_ar"], hero["tagline_ar"]):
            self.assertIn("مرحلة", text)
            self.assertIn("مبكرة", text)
        # The hero draws its tagline in two lines and cuts the rest (HeroCarousel.qml:
        # maximumLineCount 2, ElideRight). Its text column is about 440 px in the Store's smallest
        # window, and about 320 px on a screen 800 px wide, where a line holds some 35 to 40
        # characters at 16 px and fewer with a larger font. The notice comes first, inside the
        # first 30 characters, so no window size or font scale can cut it off.
        for text, word in ((hero["tagline_en"], "early"), (hero["tagline_ar"], "مبكرة")):
            self.assertLessEqual(text.index(word) + len(word), 30,
                                 f"the early-version notice must open the hero tagline: {text}")

    def test_flatseal_claims_only_the_apps_it_manages_and_is_not_a_privacy_pick(self):
        flatseal = app(SHIPPED, "com.github.tchx84.Flatseal")
        self.assertNotIn("each installed app", flatseal["desc_en"])
        self.assertNotIn("لكل تطبيق مثبّت", flatseal["desc_ar"])
        self.assertIn("sandboxed Linux apps", flatseal["desc_en"])
        self.assertIn("تطبيقات لينكس المعزولة", flatseal["desc_ar"])
        privacy = next(row for row in SHIPPED["collections"] if row["id"] == "privacy")
        self.assertNotIn("com.github.tchx84.Flatseal", privacy["apps"])


class OneWordForPermissions(unittest.TestCase):
    """The Store's permission controls, messages and What's new say «أذونات»/«إذن»; Al-Quran's
    description on the same page said «صلاحيات». Search words may keep it: people type both."""

    def test_no_arabic_copy_says_salahiyat(self):
        shown = []
        for entry in SHIPPED["apps"]:
            shown += [(entry["id"], key, entry.get(key, "")) for key in ("ar", "desc_ar")]
        for row in SHIPPED["collections"]:
            shown += [(row["id"], key, row.get(key, "")) for key in ("ar", "desc_ar")]
        for card in SHIPPED["featured"]:
            shown += [(card["app"], key, card.get(key, "")) for key in ("title_ar", "tagline_ar")]
        for bundle in SHIPPED["bundles"]:
            shown += [(bundle["id"], key, bundle.get(key, "")) for key in ("ar", "desc_ar")]
        self.assertEqual([(where, key) for where, key, text in shown if "صلاحي" in text], [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
