#!/usr/bin/env python3
"""A pinned app's update in index.json is the same answer moos-storectl gives.

docs/MO_STORE.md ("As built"): an update is available when a record's SHA-256 differs from the
pin for the running architecture. moos-storectl's check-updates, Update all and `update <id>`
follow it; until 2026-10-15 the index compared version strings instead and never read the
Android record at all, so for the same app index.json and updates.json disagreed:

  * an Android app one pin behind (record 0.28.0, data directory present) had
    installed_version null and no update in the index, and a pin row in updates.json;
  * a re-pinned build that kept its version (PhotoCraft 0.9.0, other bytes) was no update in
    the index and a pin row in updates.json;
  * a record of the very bytes the catalogue pins, written as "0.9" against "0.9.0", was an
    update in the index and "This app is up to date" from `update <id>`.

The rule, per kind, with the records where moos-storectl and App Drop write them:
  appdrop   only a record whose catalog_id is the catalogue id is the Store's own install; its
            update is a digest that is not the pin's. A record with no catalog_id is the
            person's own file in that slot (adopted): the pin is never offered over it;
  windows   record and program folder (<id>/app): an update when the digest is not the pin's;
  android   record and the per-package data directory: an update when the digest is not the
            pin's. The data directory with no record (the older Store wrote none) is installed,
            version unknown, and offered the pin; a record whose data directory is gone is not
            installed.

Every run uses a private HOME and private XDG directories; nothing is installed or downloaded.
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
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")
STORECTL = ROOT / "system_files/usr/bin/moos-storectl"


def load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load("moos_store_index_pinned_updates", INDEXER)
storectl = load("moos_storectl_pinned_updates", STORECTL)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop  # noqa: E402 - manifest_dir() reads XDG_DATA_HOME when it is called

ARCH = index.running_arch()
PIN = "1" * 64          # the bytes the catalogue pins now
OLD = "0" * 64          # the bytes an earlier pin installed
REVIEW = {"external": True, "risk": "downloaded-executable", "requires_review": True}


def appdrop(app_id: str) -> dict:
    downloads = {arch: {"url": f"https://example.org/{app_id}-{arch}.AppImage", "sha256": PIN,
                        "size": 1000} for arch in ("x86_64", "aarch64")}
    return {"id": app_id, "source": "moos", "cat": "util", "glyph": "spark", "en": app_id.title(),
            "ar": "تطبيق", "install": {"kind": "appdrop", "artifact": "appimage",
                                       "version": "0.9.0", "downloads": downloads, **REVIEW}}


def windows(app_id: str) -> dict:
    return {"id": app_id, "source": "moos", "cat": "win", "glyph": "spark", "en": app_id.title(),
            "ar": "برنامج", "engine": "windows",
            "install": {"kind": "windows-portable", "version": "8.7.1", "exe": "app/app.exe",
                        "downloads": {"x86_64": {"url": f"https://example.org/{app_id}.zip",
                                                 "sha256": PIN, "size": 1000}}, **REVIEW}}


def android(package: str) -> dict:
    return {"id": package, "source": "moos", "cat": "droid", "glyph": "grid", "en": "Droid",
            "ar": "درويد", "engine": "android",
            "install": {"kind": "android", "url": f"https://example.org/{package}.apk",
                        "sha256": PIN, "package": package, "version": "0.29.1", "size": 1000,
                        **REVIEW}}


APPS = [appdrop("repinned"), appdrop("current"), appdrop("renamed"), appdrop("adopted"),
        appdrop("adopted-same"), windows("notepad"), windows("sumatra"), windows("folderless"),
        android("org.example.repin"), android("org.example.current"),
        android("org.example.legacy"), android("org.example.gone")]

# The rule's answer for every fixture: (installed, installed_version, update_available).
EXPECTED = {
    "repinned": (True, "0.9.0", True),          # same version, other bytes: re-pinned
    "current": (True, "0.9.0", False),
    "renamed": (True, "0.9", False),            # the pin's bytes, whatever the string says
    "adopted": (True, None, False),             # the person's own file: never the pin
    "adopted-same": (True, "0.9.0", False),     # the pin's own bytes name its version
    "notepad": (True, "8.7.1", True),
    "sumatra": (True, "8.7.1", False),
    "folderless": (False, None, False),         # the program folder is gone
    "org.example.repin": (True, "0.28.0", True),
    "org.example.current": (True, "1.7.0", False),
    "org.example.legacy": (True, None, True),   # no record yet: the pin is offered
    "org.example.gone": (False, None, False),   # the container no longer has it
}
if ARCH != "x86_64":
    # Windows programs are pinned for x86_64 only: there is no pin for this machine to offer.
    EXPECTED.update({"notepad": (True, "8.7.1", False)})
# Where the base moos-storectl already applies the rule: check-updates must agree exactly.
# ("adopted" and "org.example.legacy" are the two cases the rule adds on that side too.)
SHARED = sorted(set(EXPECTED) - {"adopted", "org.example.legacy"})


class Home:
    """A private home holding the records exactly where moos-storectl and App Drop write them."""

    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        self.data = self.home / ".local/share"
        self.environment = {
            "HOME": str(self.home), "XDG_DATA_HOME": str(self.data),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
        }
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": APPS}), encoding="utf-8")
        revision = base / "flatpak/appstream/flathub/x86_64" / ("e" * 64)
        revision.mkdir(parents=True)
        (revision / "appstream.xml").write_text("<components/>", encoding="utf-8")
        self.output = base / "cache/index.json"

    @contextlib.contextmanager
    def environ(self):
        with mock.patch.dict(os.environ, self.environment):
            yield

    def write(self, path: Path, document: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document), encoding="utf-8")

    def appdrop_record(self, slug: str, sha256: str, version: str | None, catalogued: bool) -> None:
        record = {"schema": 1, "id": slug, "name": slug.title(), "kind": "appimage",
                  "source": "download.AppImage", "sha256": sha256, "launcher": "",
                  "installed_at": 1}
        if catalogued:
            record.update(catalog_id=slug, version=version, url="https://example.org/x")
        with self.environ():
            self.write(moos_appdrop.manifest_dir() / f"{slug}.json", record)

    def windows_record(self, app_id: str, sha256: str, folder: bool) -> None:
        with self.environ():
            paths = storectl.windows_paths(app_id)
            self.write(paths.record, {"schema": 1, "id": app_id, "name": app_id, "version": "8.7.1",
                                      "sha256": sha256, "url": "https://example.org/x",
                                      "exe": "app/app.exe", "wm_class": "app.exe",
                                      "launcher": paths.launcher.name, "installed_at": 1})
            if folder:
                paths.app.mkdir(parents=True)

    def android_state(self, package: str, *, sha256: str | None, version: str = "",
                      data: bool = True) -> None:
        with self.environ():
            if sha256 is not None:
                self.write(storectl.android_record_path(package), {
                    "schema": 1, "id": package, "package": package, "catalog_id": package,
                    "version": version, "sha256": sha256, "source": "catalog", "file": "",
                    "installed_at": 1})
            if data:
                # Where the container keeps an installed package: $XDG_DATA_HOME/waydroid.
                (storectl.data_home() / "waydroid/data/data" / package).mkdir(parents=True)

    def populate(self) -> None:
        self.appdrop_record("repinned", OLD, "0.9.0", catalogued=True)
        self.appdrop_record("current", PIN, "0.9.0", catalogued=True)
        self.appdrop_record("renamed", PIN, "0.9", catalogued=True)
        self.appdrop_record("adopted", OLD, None, catalogued=False)
        self.appdrop_record("adopted-same", PIN, None, catalogued=False)
        self.windows_record("notepad", OLD, folder=True)
        self.windows_record("sumatra", PIN, folder=True)
        self.windows_record("folderless", OLD, folder=False)
        self.android_state("org.example.repin", sha256=OLD, version="0.28.0")
        self.android_state("org.example.current", sha256=PIN, version="1.7.0")
        self.android_state("org.example.legacy", sha256=None)
        self.android_state("org.example.gone", sha256=OLD, version="0.28.0", data=False)

    def run_index(self) -> dict:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("XDG_", "FLATPAK_"))}
        environment.update(self.environment)
        result = subprocess.run(
            [sys.executable, str(INDEXER), "--output", str(self.output), "--catalog",
             str(self.catalog), "--appstream-root", str(self.base / "flatpak/appstream"),
             "--installation-root", str(self.base / "flatpak"), "--locale", "en",
             "--engines", "all"],
            text=True, capture_output=True, check=False, env=environment)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(self.output.read_text(encoding="utf-8"))

    def check_updates(self) -> set[str]:
        """The pin rows moos-storectl's own check-updates lists for this home."""

        class NoFlatpakUpdates:
            def update_candidates(self):
                return []

        with self.environ(), contextlib.redirect_stdout(io.StringIO()):
            controller = storectl.Controller(storectl.JobStore(self.base / "store-cache"),
                                             adapter_factory=NoFlatpakUpdates,
                                             catalog_path=self.catalog)
            code, document = controller.check_updates()
        if code != 0:
            raise AssertionError(document)
        return {item["id"] for item in document["items"] if item.get("kind") == "pin"}


class PinnedUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.home = Home(Path(cls.temporary.name))
        cls.home.populate()
        cls.data = cls.home.run_index()
        cls.apps = {app["id"]: app for app in cls.data["apps"]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def state(self, app_id: str) -> tuple:
        app = self.apps[app_id]
        return app["installed"], app["installed_version"], app["update_available"]

    def test_every_kind_follows_the_digest_rule(self):
        for app_id, expected in EXPECTED.items():
            with self.subTest(app=app_id):
                self.assertEqual(self.state(app_id), expected)

    def test_an_adopted_file_is_still_the_persons_own(self):
        adopted = self.apps["adopted"]
        self.assertEqual((adopted["kind"], adopted["listed"]), ("appdrop", True))
        self.assertNotIn("appdrop-adopted", self.apps, "an adopted record was listed twice")

    def test_the_counter_counts_the_same_updates(self):
        self.assertEqual(self.data["stats"]["updates_known"],
                         sum(expected[2] for expected in EXPECTED.values()))

    def test_check_updates_lists_the_same_pins(self):
        rows = self.home.check_updates()
        flags = {app_id for app_id in SHARED if self.apps[app_id]["update_available"]}
        self.assertEqual(rows & set(SHARED), flags,
                         "index.json and updates.json disagree about the same apps")


class RecordsLiveWhereTheBackendWritesThem(unittest.TestCase):
    def test_paths_agree_under_a_relocated_data_home(self):
        """XDG_DATA_HOME elsewhere than ~/.local/share: both sides follow it (so does the
        Android container, whose data lives under $XDG_DATA_HOME/waydroid)."""
        with tempfile.TemporaryDirectory() as raw:
            home = Home(Path(raw))
            home.environment["XDG_DATA_HOME"] = str(Path(raw) / "elsewhere")
            home.data = Path(raw) / "elsewhere"
            home.windows_record("notepad", OLD, folder=True)
            home.android_state("org.example.repin", sha256=OLD, version="0.28.0")
            apps = {app["id"]: app for app in home.run_index()["apps"]}
            self.assertTrue(apps["notepad"]["installed"])
            self.assertEqual(apps["org.example.repin"]["installed_version"], "0.28.0")
            self.assertTrue(apps["org.example.repin"]["update_available"])


if __name__ == "__main__":
    unittest.main()
