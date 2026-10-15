#!/usr/bin/env python3
"""The app page and executor agree about real private APK version/signer facts.

No runtime, network, bus or owner home is used. APKs come from the maintained
binary-manifest/signing-block fixture; receipts come from the actual writer.
"""
from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


index = load("index_android_policy_under_test", INDEXER)
backend = load("backend_android_policy_executor", ROOT / "system_files/usr/bin/moos-storectl")
fixture = load("apk_binary_policy_fixtures", ROOT / "tests/test_moos_android_apk.py")
apk_module = fixture.apkfacts
PACKAGE = "org.example.notes"
PUBLISHER = b"publisher certificate"
OTHER_PUBLISHER = b"another publisher certificate"
SIGNER = hashlib.sha256(PUBLISHER).hexdigest()


class AndroidUpdatePolicy(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="android-policy-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.data = self.base / "relocated-data"
        self.environment = mock.patch.dict(os.environ, {
            "HOME": str(self.home), "XDG_DATA_HOME": str(self.data),
            "XDG_CACHE_HOME": str(self.base / "cache"),
            "XDG_CONFIG_HOME": str(self.base / "config"),
            "XDG_STATE_HOME": str(self.base / "state"),
            "FLATPAK_USER_DIR": str(self.base / "flatpak"),
            "FLATPAK_SYSTEM_DIR": str(self.base / "system-flatpak"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent", "DISPLAY": "",
            "WAYLAND_DISPLAY": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.pin = fixture.apk(PACKAGE, 100, "1.0", signer=PUBLISHER, payload=b"the pin")
        self.recipe = {
            "id": PACKAGE, "source": "moos", "engine": "android", "glyph": "grid",
            "cat": "droid", "en": "Notes", "ar": "ملاحظات",
            "install": {"kind": "android", "package": PACKAGE, "version": "1.0",
                        "url": f"https://f-droid.org/repo/{PACKAGE}_100.apk",
                        "size": len(self.pin), "sha256": hashlib.sha256(self.pin).hexdigest(),
                        "signer": SIGNER},
        }
        (self.data / "waydroid/data/data" / PACKAGE).mkdir(parents=True)
        self.kept_path = self.data / "waydroid/data/app" / f"{PACKAGE}-fixture/base.apk"
        self.kept_path.parent.mkdir(parents=True)
        self.controller = object.__new__(backend.Controller)
        self.catalog = self.base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": [self.recipe]}), encoding="utf-8")
        self.machine = self.base / "machine.json"
        self.machine.write_text(json.dumps({"arch": index.running_arch(), "engines": ["android"]}),
                                encoding="utf-8")
        self.appstream = self.base / "appstream"
        self.appstream.mkdir()
        self.flatpak = self.base / "flatpak"
        self.flatpak.mkdir()
        self.output = self.base / "cache/index.json"

    def put(self, code, name=None, *, signer=PUBLISHER):
        body = fixture.apk(PACKAGE, code, name or str(code), signer=signer, payload=b"other")
        self.kept_path.write_bytes(body)

    def receipt(self, *, source="catalog"):
        backend.Controller._write_android_record(
            PACKAGE, sha256="a" * 64, source=source,
            catalog_id=PACKAGE if source == "catalog" else "", version="0.9")
        return backend.android_record_path(PACKAGE)

    def agreed(self, expected, *, version=None):
        state = index.catalog_install_state(self.recipe, index.running_arch())
        row = self.controller._pin_update_row(PACKAGE, self.recipe)
        self.assertEqual(state["update"], row is not None,
                         "app page and executor disagree about the same installed APK")
        self.assertEqual(state["update"], expected)
        if version is not None:
            self.assertEqual(state["version"], version)
        return state

    def test_an_older_store_build_is_offered_the_pin(self):
        self.receipt()
        self.put(99, "0.9")
        self.agreed(True, version="0.9")

    def test_a_newer_build_is_not_offered_a_downgrade(self):
        self.receipt()
        self.put(200, "2.0")
        self.agreed(False, version="2.0")

    def test_equal_version_codes_with_other_bytes_are_not_an_update(self):
        self.receipt()
        self.put(100, "1.0")
        self.agreed(False, version="1.0")

    def test_a_different_signer_is_not_an_update(self):
        self.receipt()
        self.put(99, "0.9", signer=OTHER_PUBLISHER)
        self.agreed(False)

    def test_a_file_the_owner_installed_is_never_replaced_by_the_pin(self):
        self.receipt(source="file")
        self.put(99, "0.9")
        state = self.agreed(False)
        self.assertTrue(state["adopted"])

    def test_an_older_build_without_a_receipt_is_an_update(self):
        self.put(99, "0.9")
        self.agreed(True, version="0.9")

    def test_a_newer_build_without_a_receipt_is_left_alone(self):
        self.put(200, "2.0")
        self.agreed(False, version="2.0")

    def test_unknown_bytes_without_a_receipt_are_not_an_update(self):
        self.agreed(False)

    def test_an_unreadable_apk_still_uses_the_stores_own_receipt(self):
        self.receipt()
        self.agreed(True, version="0.9")

    def test_the_pins_exact_apk_replaces_a_stale_display_version(self):
        self.receipt()
        self.kept_path.write_bytes(self.pin)
        self.agreed(False, version="1.0")

    def test_the_catalogue_keeps_a_valid_signer_and_rejects_a_malformed_one(self):
        install = dict(self.recipe["install"], signer=SIGNER.upper())
        self.assertEqual(index.sanitize_install({"install": install}, PACKAGE).get("signer"), SIGNER)
        for invalid in (SIGNER + "a", "x" * 64, True, None):
            with self.subTest(signer=invalid), self.assertRaises(index.CatalogError):
                index.sanitize_install({"install": dict(install, signer=invalid)}, PACKAGE)

    def test_a_malformed_receipt_cannot_supply_version_or_update_metadata(self):
        path = self.receipt()
        original = json.loads(path.read_text(encoding="utf-8"))
        for changes in ({"schema": True}, {"id": "org.example.other"},
                        {"package": "org.example.other"}, {"version": "1.0\nInjected=yes"},
                        {"source": "file", "catalog_id": PACKAGE}, {"sha256": "x" * 64}):
            with self.subTest(changes=changes):
                path.write_text(json.dumps(original | changes), encoding="utf-8")
                state = index.catalog_install_state(self.recipe, index.running_arch())
                self.assertTrue(state["installed"])
                self.assertIsNone(state["version"])
                self.assertFalse(state["update"])

    def run_index(self):
        code = index.main([
            "--catalog", str(self.catalog), "--output", str(self.output),
            "--appstream-root", str(self.appstream), "--installation-root", str(self.flatpak),
            "--machine", str(self.machine), "--engines", "all", "--locale", "en",
        ])
        self.assertEqual(code, 0)
        return json.loads(self.output.read_text(encoding="utf-8"))

    def app(self, payload):
        return next(app for app in payload["apps"] if app["id"] == PACKAGE)

    def test_cached_lifecycle_refresh_uses_the_same_eligibility(self):
        self.receipt()
        self.put(200, "2.0")
        first = self.run_index()
        self.assertFalse(self.app(first)["update_available"])
        self.put(99, "0.9")
        with mock.patch.object(index, "build_index", side_effect=AssertionError("metadata rebuilt")):
            second = self.run_index()
            self.assertTrue(self.app(second)["update_available"])
            self.assertEqual(self.app(second)["installed_version"], "0.9")
            self.put(100, "1.0")
            third = self.run_index()
        self.assertFalse(self.app(third)["update_available"])
        self.assertEqual(self.app(third)["installed_version"], "1.0")
        self.assertEqual(first["generation"]["metadata_token"],
                         second["generation"]["metadata_token"])
        self.assertNotEqual(first["generation"]["installed_token"],
                            second["generation"]["installed_token"])

    def test_an_unchanged_launch_reuses_complete_apk_facts_and_writes_nothing(self):
        self.receipt()
        self.put(99, "0.9")
        first = self.run_index()
        memo = self.output.parent / index.APK_DIGESTS_NAME
        output_time, memo_time = self.output.stat().st_mtime_ns, memo.stat().st_mtime_ns
        with mock.patch.object(apk_module, "_manifest", side_effect=AssertionError("manifest reread")), \
                mock.patch.object(apk_module, "_signer", side_effect=AssertionError("signer reread")), \
                mock.patch.object(index, "build_index", side_effect=AssertionError("metadata rebuilt")):
            second = self.run_index()
        self.assertEqual(first, second)
        self.assertEqual(self.output.stat().st_mtime_ns, output_time)
        self.assertEqual(memo.stat().st_mtime_ns, memo_time)

    def test_a_changed_shared_reader_invalidates_its_parsed_facts(self):
        self.receipt()
        self.put(99, "0.9")
        self.run_index()
        memo = self.output.parent / index.APK_DIGESTS_NAME
        document = json.loads(memo.read_text(encoding="utf-8"))
        document["facts_reader"] = "0" * 64
        memo.write_text(json.dumps(document), encoding="utf-8")
        with mock.patch.object(apk_module, "_manifest", wraps=apk_module._manifest) as parse:
            self.run_index()
        self.assertEqual(parse.call_count, 1)

    def test_old_digest_only_memos_do_not_supply_unparsed_version_or_signer(self):
        self.receipt()
        self.put(99, "0.9")
        self.run_index()
        memo = self.output.parent / index.APK_DIGESTS_NAME
        document = json.loads(memo.read_text(encoding="utf-8"))
        document.pop("facts", None)
        document.pop("facts_reader", None)
        memo.write_text(json.dumps(document), encoding="utf-8")
        with mock.patch.object(apk_module, "_manifest", wraps=apk_module._manifest) as parse:
            self.run_index()
        self.assertEqual(parse.call_count, 1)

    def test_a_linked_receipt_does_not_supply_metadata(self):
        path = self.receipt()
        elsewhere = self.base / "copied-receipt.json"
        path.rename(elsewhere)
        path.symlink_to(elsewhere)
        state = index.catalog_install_state(self.recipe, index.running_arch())
        self.assertIsNone(state["version"])
        self.assertFalse(state["update"])


if __name__ == "__main__":
    unittest.main()
