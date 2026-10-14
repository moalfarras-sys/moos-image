#!/usr/bin/env python3
"""Mo Store catalogue v2: the shipped catalogue passes, and every new gate rule bites.

build_files/verify_store_catalog.py is the gate for the catalogue (docs/MO_STORE.md). A rule
that cannot fail protects nothing (AGENTS.md: "Prove a new gate bites by breaking the thing it
guards"), so each rule added for catalogue v2 has a negative control here: one bad value is
planted in a deep copy of the shipped catalogue and the exact refusal is asserted.

The chain half of the gate names install paths another component owns (moos-storectl's
handlers, the vendor-package helper). Those checks are exercised against stub copies of the
backend, so this suite proves the RULE whichever backend revision is in the tree; the gate
itself is what proves the real backend.
"""

import copy
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
        self.assertTrue(8 <= len(SHIPPED["collections"]) <= 12)
        self.assertTrue(5 <= len(SHIPPED["featured"]) <= 7)
        self.assertEqual(len(SHIPPED["bundles"]), 5)
        self.assertLessEqual({"game-starter", "dev-starter", "study-starter", "office-starter"},
                             {b["id"] for b in SHIPPED["bundles"]})
        self.assertGreaterEqual(len(SHIPPED["apps"]), 140)

    def test_every_android_pin_records_its_signer_and_every_download_its_size(self):
        android = [a for a in SHIPPED["apps"] if (a.get("install") or {}).get("kind") == "android"]
        self.assertEqual(len(android), 21)
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
                   "_install_vendor_rpm")


def storectl_with(tokens: bool) -> str:
    text = (SYSTEM / "usr/bin/moos-storectl").read_text(encoding="utf-8")
    for token in NEW_KIND_TOKENS:
        text = text.replace(token, "_install_unrelated")
    text = text.replace('"web-app"', '"unrelated-risk"')
    if tokens:
        text += ("\n_V2_INSTALL_PATHS = (" + ", ".join(NEW_KIND_TOKENS) + ")\n"
                 '_V2_RISKS = {"web-app"}\n')
    return text


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


class TheScriptFailsTheBuild(unittest.TestCase):
    """End to end: the gate script, its exit status and its message, on a planted mirror."""

    def run_gate(self, catalog: dict) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as raw:
            root = mirror_root(Path(raw), {
                gate.CATALOG: json.dumps(catalog, ensure_ascii=False, indent=1),
                gate.MOOS_STORECTL: storectl_with(True),
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


if __name__ == "__main__":
    unittest.main(verbosity=1)
