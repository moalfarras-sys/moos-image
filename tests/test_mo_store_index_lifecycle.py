#!/usr/bin/env python3
"""What is installed, for every kind of app Mo Store knows, read from files only.

Measured on the station on 2026-10-14: the index said 8 apps were installed, the real number
was 10. PhotoCraft (an App Drop install) and cn.navclub.ldbfx (a system Flatpak that Flathub
retired) were missing from the Store's Installed page, so neither could be found or removed.

Kinds and the file each one is read from (docs/MO_STORE.md, "Kinds of app"):
  webapp    ~/.local/share/applications/org.moos.webapp.<id>.desktop with X-MoOS-WebApp=<id>
  appdrop   ~/.local/share/moos/appdrop/<id>.json carrying catalog_id=<id>
  windows   ~/.local/share/moos/windows-apps/<id>.json
  android   the Android runtime's per-package data directory
  npm       ~/.local/bin/<command> (+ the package's own package.json for its version)
  web       never installed
  dropped   an App Drop record with no catalogue id
  flatpak   deployments in both scopes; flatpak's own deploy data gives the version and EOL

A pinned app's update in index.json is the same answer moos-storectl gives (PinnedUpdates).
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
  android   the executor's shared APK rule: no downgrade or different signer, no replacement of
            a file the owner installed. Unknown APK bytes without a Store receipt do not offer
            an update. A readable older APK can be updated without a receipt; the real binary
            manifest/signing cases are in test_mo_store_index_android_policy.py. A record whose
            data directory is gone is not installed. APK facts are remembered by file identity.

Every update index.json offers is one `moos-storectl update <id>` performs: the window's Update
button runs it, so any other answer is a button that does nothing (PinnedUpdates).

Every run uses a private HOME, private XDG directories (the runtime directory too, where a
Store job announces itself to the Island) and fixture installations; nothing is installed or
downloaded, and moos-storectl may run no command.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")
STORECTL = Path(os.environ.get("MOOS_STORECTL_UNDER_TEST")
                or ROOT / "system_files/usr/bin/moos-storectl")


def load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


def load_indexer():
    return load("moos_store_index_lifecycle", INDEXER)


index = load_indexer()
storectl = load("moos_storectl_lifecycle", STORECTL)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop  # noqa: E402 - manifest_dir() reads XDG_DATA_HOME when it is called

# /var/lib/flatpak/app/cn.navclub.ldbfx/x86_64/stable/active/deploy on the station, 2026-10-14:
# a real retired Flathub app (public metadata only), 488 bytes with 2-byte framing offsets.
REAL_EOL_DEPLOY = base64.b64decode(
    "ZmxhdGh1YgA4ZTQ1N2JhNmY0MjJlYWJkNzc2NTlkNTU4MDIwN2ZmNzU4M2Y3NzlmYWU1ZWRlMTUyZTdjZWU2"
    "MTlkNmMxYjg0AAAAAAAAAAAAAAAAAIasAHByZXZpb3VzLWlkcwAAAAAAYXMNAAAAAGVvbAAAAAAAVGhpcyBh"
    "cHBsaWNhdGlvbiBpcyBubyBsb25nZXIgbWFpbnRhaW5lZC4AAHMEAAAAYXBwZGF0YS1zdW1tYXJ5AFZpc3Vh"
    "bCBkYXRhYmFzZSBtYW5hZ2VtZW50IHRvb2wAAHMQAAAAAABhcHBkYXRhLW5hbWUAAAAAbGRiZngAAHMNAAAA"
    "AAAAAGFwcGRhdGEtdmVyc2lvbgAxLjAuMAAAcxAAAAAAAAAAcnVudGltZQBvcmcuZ25vbWUuU2RrL3g4Nl82"
    "NC80MgAAcwgAAAAAAGFwcGRhdGEtY29udGVudC1yYXRpbmcAAG9hcnMtMS4xAAkAKHNhe3NzfSkXAAAAAHRp"
    "bWVzdGFtcAAAAAAAAADx2ZRiAAAAAAB0CgAAAAAAZGVwbG95LXZlcnNpb24AAAQAAAAAaQ8AYXBwZGF0YS1s"
    "aWNlbnNlAEFwYWNoZS0yLjAAAHMQFABNAIMAoQDBAOsAHAE7AVcBdgFJAEkACAA="
)


def _offset_size(body: int, offsets: int) -> int:
    for size, limit in ((1, 0xFF), (2, 0xFFFF), (4, 0xFFFFFFFF)):
        if body + size * offsets <= limit:
            return size
    return 8


def _pad(data: bytes, alignment: int) -> bytes:
    return data + b"\0" * (-len(data) % alignment)


def encode_deploy(origin: str, commit: str, size: int, metadata: dict[str, str]) -> bytes:
    """A GVariant (ssasta{sv}) with string metadata, serialised like GLib does."""

    body = origin.encode() + b"\0"
    origin_end = len(body)
    body += commit.encode() + b"\0"
    commit_end = subpaths_end = len(body)
    body = _pad(_pad(body, 8) + size.to_bytes(8, "big"), 8)
    array, ends = b"", []
    for key, value in metadata.items():
        entry = key.encode() + b"\0"
        key_end = len(entry)
        entry = _pad(entry, 8) + value.encode() + b"\0" + b"\0s"
        entry += key_end.to_bytes(_offset_size(len(entry), 1), "little")
        array = _pad(array, 8) + entry
        ends.append(len(array))
    if ends:
        width = _offset_size(len(array), len(ends))
        array += b"".join(end.to_bytes(width, "little") for end in ends)
    body += array
    width = _offset_size(len(body), 3)
    return body + b"".join(value.to_bytes(width, "little")
                           for value in (subpaths_end, commit_end, origin_end))


class DeployData(unittest.TestCase):
    def test_a_real_retired_deployment_reads_back_exactly(self):
        data = index.parse_deploy_data(REAL_EOL_DEPLOY)
        self.assertEqual(data["origin"], "flathub")
        self.assertEqual(data["commit"],
                         "8e457ba6f422eabd77659d5580207ff7583f779fae5ede152e7cee619d6c1b84")
        self.assertEqual(data["installed_size"], 8825856)
        metadata = data["metadata"]
        self.assertEqual(metadata["eol"], "This application is no longer maintained.")
        self.assertEqual(metadata["appdata-name"], "ldbfx")
        self.assertEqual(metadata["appdata-version"], "1.0.0")
        self.assertEqual(metadata["appdata-license"], "Apache-2.0")
        self.assertNotIn("timestamp", metadata)        # not a string: ignored
        self.assertTrue(index.deploy_end_of_life(data))

    def test_every_framing_width_is_read(self):
        for label, metadata in (
            ("1-byte offsets", {"appdata-version": "2.0"}),
            ("2-byte offsets", {"appdata-name": "N" * 300, "appdata-version": "2.1"}),
            ("4-byte offsets", {"appdata-summary": "S" * 70000, "appdata-version": "2.2",
                                "eolr": "app/org.example.New/x86_64/stable"}),
        ):
            with self.subTest(width=label):
                blob = encode_deploy("flathub", "c" * 64, 123, metadata)
                data = index.parse_deploy_data(blob)
                self.assertEqual(data["metadata"], metadata)
                self.assertEqual(data["installed_size"], 123)
        self.assertTrue(index.deploy_end_of_life(index.parse_deploy_data(
            encode_deploy("flathub", "c" * 64, 1, {"eolr": "app/x/y/z"}))))

    def test_damaged_data_never_raises_out_of_the_reader(self):
        generator = random.Random(20261014)
        with tempfile.TemporaryDirectory() as raw:
            active = Path(raw)
            for case in range(400):
                blob = bytearray(REAL_EOL_DEPLOY)
                if case < 200:
                    blob = blob[:generator.randrange(len(blob))]
                else:
                    for _ in range(generator.randrange(1, 8)):
                        blob[generator.randrange(len(blob))] = generator.randrange(256)
                (active / "deploy").write_bytes(bytes(blob))
                result = index.read_deploy_data(active)
                self.assertIsInstance(result, dict)
            (active / "deploy").write_bytes(b"\0" * (index.DEPLOY_DATA_LIMIT + 1))
            self.assertEqual(index.read_deploy_data(active), {})


class Versions(unittest.TestCase):
    def test_version_order(self):
        for newer, older in (("1.10", "1.9"), ("2.0", "1.99.9"), ("1.0.1", "1.0"),
                             ("1.0", "1.0-beta"), ("0.8.0", "0.7.0"), ("v2", "v1")):
            with self.subTest(newer=newer, older=older):
                self.assertTrue(index.version_newer(newer, older))
                self.assertFalse(index.version_newer(older, newer))
        self.assertFalse(index.version_newer("1.2.3", "1.2.3"))


SHA = "a" * 64
PIN = "b" * 64

APPSTREAM = """<components>
  <component type="desktop-application"><id>org.example.Listed</id><name>Listed</name>
    <bundle type="flatpak">app/org.example.Listed/x86_64/stable</bundle></component>
  <component type="console-application"><id>org.example.Tool</id><name>Tool</name>
    <bundle type="flatpak">app/org.example.Tool/x86_64/stable</bundle></component>
</components>"""


def catalogue() -> dict:
    def entry(app_id, kind, **install):
        recipe = {"kind": kind, **install}
        return {"id": app_id, "source": "moos", "cat": "util", "glyph": "spark",
                "en": app_id.title(), "ar": "تطبيق", "install": recipe}
    downloads = {index.running_arch(): {"url": "https://example.org/a.AppImage", "sha256": PIN,
                            "size": 1000}}
    return {"apps": [
        entry("chat", "webapp", url="https://chat.example.com/", hosts=["chat.example.com"]),
        entry("chat-later", "webapp", url="https://later.example.com/",
              hosts=["later.example.com"]),
        entry("photo", "appdrop", artifact="appimage", version="0.8.0", downloads=downloads),
        entry("adopted", "appdrop", artifact="appimage", version="2.0", downloads=downloads),
        dict(entry("notepad", "windows-portable", version="8.7.1", exe="npp/notepad++.exe",
                   downloads={"x86_64": {"url": "https://example.org/n.zip", "sha256": SHA,
                                         "size": 10}}), engine="windows"),
        dict(entry("org.example.droid", "android", url="https://example.org/d.apk",
                   sha256=SHA, package="org.example.droid"), engine="android"),
        entry("codex", "npm", pkg="@openai/codex", bin="codex"),
        entry("page", "web", url="https://example.org/page"),
    ]}


class Machine:
    """One fixture machine: a private home, a user Flatpak installation, AppStream."""

    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        self.data = self.home / ".local/share"
        self.installation = base / "flatpak"
        self.appstream = self.installation / "appstream"
        revision = self.appstream / "flathub/x86_64" / ("e" * 64)
        revision.mkdir(parents=True)
        self.xml = revision / "appstream.xml"
        self.xml.write_text(APPSTREAM, encoding="utf-8")
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps(catalogue()), encoding="utf-8")
        self.output = base / "cache/index.json"

    def write(self, relative: str, text: str) -> Path:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def record(self, slug: str, **fields) -> None:
        self.write(f".local/share/moos/appdrop/{slug}.json",
                   json.dumps({"schema": 1, "id": slug, "kind": "appimage", **fields}))

    def launcher(self, name: str, icon: str, extra: str = "") -> str:
        path = self.write(f".local/share/applications/{name}",
                          f"[Desktop Entry]\nType=Application\nName=X\nIcon={icon}\n{extra}")
        return str(path)

    def icon(self, relative: str) -> str:
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        return str(path)

    def deploy(self, app_id: str, metadata: dict[str, str], *, desktop: str = "",
               scope_root: Path | None = None) -> Path:
        root = scope_root or self.installation
        commit = (app_id.encode().hex() + "0" * 64)[:64]
        deployment = root / f"app/{app_id}/x86_64/stable" / commit
        deployment.mkdir(parents=True)
        (deployment.parent / "active").symlink_to(commit, target_is_directory=True)
        (deployment / "deploy").write_bytes(encode_deploy("flathub", commit, 1, metadata))
        if desktop:
            applications = deployment / "export/share/applications"
            applications.mkdir(parents=True)
            (applications / f"{app_id}.desktop").write_text(desktop, encoding="utf-8")
            icon = deployment / f"export/share/icons/hicolor/128x128/apps/{app_id}.png"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"\x89PNG\r\n\x1a\nicon")
        return deployment

    def run(self) -> dict:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("XDG_", "FLATPAK_"))}
        environment.update({
            "HOME": str(self.home), "XDG_DATA_HOME": str(self.data),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
            "FLATPAK_USER_DIR": str(self.installation),
            "FLATPAK_SYSTEM_DIR": str(self.base / "system-flatpak"),
        })
        result = subprocess.run(
            [sys.executable, str(INDEXER), "--output", str(self.output), "--catalog",
             str(self.catalog), "--appstream-root", str(self.appstream),
             "--installation-root", str(self.installation), "--locale", "ar",
             "--engines", "all"],
            text=True, capture_output=True, check=False, env=environment)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(self.output.read_text(encoding="utf-8"))


def populate(machine: Machine) -> None:
    # Web app: installed by its launcher; its own icon under the home.
    machine.launcher("org.moos.webapp.chat.desktop", "/x",
                     "X-MoOS-WebApp=chat\n")
    machine.icon(".local/share/moos/webapps/chat/icon.png")
    # A launcher with the right name but no marker line is somebody else's file.
    machine.launcher("org.moos.webapp.chat-later.desktop", "/x", "X-MoOS-WebApp=other\n")
    # App Drop from the catalogue, one version behind the pin.
    photo_icon = machine.icon("Applications/photo/photo.png")
    machine.record("photo", catalog_id="photo", version="0.7.0", name="Photo",
                   desktop=machine.launcher("appdrop-photo.desktop", photo_icon,
                                            "X-MoOS-AppDrop=photo\n"))
    # Dropped by hand into a catalogue app's slot, byte-identical to the pin.
    machine.record("adopted", name="Adopted", sha256=PIN)
    # Windows program: its record and its program folder, as moos-storectl leaves them, the
    # pinned bytes installed.
    machine.write(".local/share/moos/windows-apps/notepad.json",
                  json.dumps({"id": "notepad", "version": "8.7.1", "sha256": SHA}))
    (machine.home / ".local/share/moos/windows-apps/notepad/app").mkdir(parents=True)
    # The program's own icon, which moos-storectl extracts beside its folder (not a record key).
    machine.icon(".local/share/moos/windows-apps/notepad/icon.png")
    # Android package data directory; npm command and package manifest.
    (machine.home / ".local/share/waydroid/data/data/org.example.droid").mkdir(parents=True)
    machine.write(".local/bin/codex", "#!/bin/sh\n")
    machine.write(".local/lib/node_modules/@openai/codex/package.json",
                  json.dumps({"name": "@openai/codex", "version": "0.46.0"}))
    # Dropped apps: PhotoCraft-like, one whose icon is outside the home, one whose
    # catalogue app is not offered any more, one that collides with a web app id,
    # and two records that are not App Drop installs at all.
    craft_icon = machine.icon("Applications/photocraft/craft.png")
    machine.record("photocraft", name="PhotoCraft", kind="appimage",
                   desktop=machine.launcher("appdrop-photocraft.desktop", craft_icon,
                                            "Comment=Edit photos\nCategories=Graphics;\n"))
    machine.record("outside", name="Outside",
                   desktop=machine.launcher("appdrop-outside.desktop", "/etc/passwd"))
    machine.record("retired-pick", name="Retired Pick", catalog_id="no-longer-offered",
                   version="1.0")
    machine.record("chat", name="Chat (hand-installed)")
    machine.record("mismatch", id_override=True)
    machine.write(".local/share/moos/appdrop/mismatch.json", json.dumps({"id": "other"}))
    machine.write(".local/share/moos/appdrop/declined.json", "[]")
    # Flatpaks: one listed, one retired and gone from AppStream, one console tool.
    machine.deploy("org.example.Listed", {"appdata-version": "3.1"})
    machine.deploy("cn.example.Retired",
                   {"appdata-name": "Retired", "appdata-name@ar": "متقاعد",
                    "appdata-version": "1.0.0", "appdata-summary": "Old tool",
                    "eol": "This application is no longer maintained."},
                   desktop="[Desktop Entry]\nName=Retired\nIcon=cn.example.Retired\n"
                           "Categories=Development;\n")
    machine.deploy("org.example.Tool", {"appdata-name": "Tool", "appdata-version": "9"})


class EveryKindIsSeen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.machine = Machine(Path(cls.temporary.name))
        populate(cls.machine)
        cls.data = cls.machine.run()
        cls.apps = {app["id"]: app for app in cls.data["apps"]}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_catalogue_kinds_report_their_real_state(self):
        apps = self.apps
        self.assertTrue(apps["chat"]["installed"])
        self.assertTrue(apps["chat"]["icon"].endswith("/moos/webapps/chat/icon.png"))
        self.assertFalse(apps["chat-later"]["installed"])
        self.assertIsNone(apps["chat-later"]["icon"])
        self.assertTrue(apps["photo"]["installed"])
        self.assertEqual(apps["photo"]["installed_version"], "0.7.0")
        self.assertTrue(apps["photo"]["update_available"])
        self.assertTrue(apps["photo"]["icon"].endswith("/Applications/photo/photo.png"))
        self.assertTrue(apps["adopted"]["installed"])
        self.assertEqual(apps["adopted"]["installed_version"], "2.0")
        self.assertFalse(apps["adopted"]["update_available"])
        self.assertTrue(apps["notepad"]["installed"])
        self.assertEqual(apps["notepad"]["installed_version"], "8.7.1")
        self.assertFalse(apps["notepad"]["update_available"])
        self.assertTrue((apps["notepad"]["icon"] or "").endswith("/windows-apps/notepad/icon.png"))
        self.assertTrue(apps["org.example.droid"]["installed"])
        self.assertIsNone(apps["org.example.droid"]["installed_version"])
        # No receipt or readable APK: there is no acceptable update to advertise.
        self.assertFalse(apps["org.example.droid"]["update_available"])
        self.assertTrue(apps["codex"]["installed"])
        self.assertEqual(apps["codex"]["installed_version"], "0.46.0")
        self.assertFalse(apps["page"]["installed"])

    def test_an_app_drop_install_outside_the_catalogue_is_its_own_app(self):
        craft = self.apps["photocraft"]
        self.assertEqual((craft["kind"], craft["source"]), ("dropped", "local"))
        self.assertEqual((craft["installed"], craft["installable"], craft["listed"]),
                         (True, False, False))
        self.assertEqual(craft["name"], "PhotoCraft")
        self.assertEqual(craft["slug"], "photocraft")
        self.assertEqual(craft["summary"], "Edit photos")
        self.assertTrue(craft["icon"].startswith("file://"))
        self.assertTrue(craft["icon"].endswith("/Applications/photocraft/craft.png"))
        self.assertEqual(craft["cat"], "art")
        self.assertIn("photocraft", craft["search"])
        self.assertIsNone(craft["details"])
        # An icon that is not a file under the person's home is never published.
        self.assertIsNone(self.apps["outside"]["icon"])
        # A record whose catalogue app is not offered here stays findable.
        self.assertEqual(self.apps["retired-pick"]["kind"], "dropped")
        self.assertEqual(self.apps["retired-pick"]["installed_version"], "1.0")
        # A hand install whose slug is a catalogue web app's id keeps a name of its own.
        self.assertEqual(self.apps["appdrop-chat"]["slug"], "chat")
        self.assertEqual(self.apps["chat"]["kind"], "webapp")
        # Records the catalogue owns are not listed twice; broken ones not at all.
        for app_id in ("photo", "adopted"):
            self.assertEqual(self.apps[app_id]["kind"], "appdrop")
        self.assertNotIn("mismatch", self.apps)
        self.assertNotIn("declined", self.apps)

    def test_installed_flatpaks_appstream_does_not_list_are_still_there(self):
        retired = self.apps["cn.example.Retired"]
        self.assertEqual((retired["installed"], retired["installable"], retired["listed"]),
                         (True, False, False))
        self.assertTrue(retired["eol"])
        self.assertEqual(retired["name"], "متقاعد")
        self.assertEqual(retired["name_en"], "Retired")
        self.assertEqual(retired["installed_version"], "1.0.0")
        self.assertEqual(retired["installed_scope"], "user")
        self.assertTrue(retired["icon"].endswith(
            "/active/export/share/icons/hicolor/128x128/apps/cn.example.Retired.png"))
        self.assertEqual(retired["cat"], "dev")
        # A console tool is not offered, but an installed one can still be removed.
        tool = self.apps["org.example.Tool"]
        self.assertEqual((tool["installed"], tool["listed"]), (True, False))
        listed = self.apps["org.example.Listed"]
        self.assertEqual((listed["installed"], listed["listed"]), (True, True))
        self.assertEqual(listed["installed_version"], "3.1")
        self.assertFalse(listed["update_available"])
        self.assertFalse(listed["eol"])

    def test_every_entry_has_the_lifecycle_keys(self):
        for app_id, app in self.apps.items():
            with self.subTest(app=app_id):
                for key in ("installed", "installed_version", "update_available", "eol",
                            "listed", "kind", "cat", "search"):
                    self.assertIn(key, app)
        stats = self.data["stats"]
        self.assertEqual(stats["dropped_apps"], 4)
        self.assertEqual(stats["unlisted_installed_apps"], 2)
        self.assertEqual(stats["installed_apps"],
                         sum(bool(app["installed"]) for app in self.data["apps"]))


class TheRefreshPathAgrees(unittest.TestCase):
    def test_an_install_and_a_removal_are_seen_without_parsing_appstream(self):
        with tempfile.TemporaryDirectory() as raw:
            machine = Machine(Path(raw))
            populate(machine)
            first = machine.run()
            unchanged = machine.output.stat().st_mtime_ns
            self.assertEqual(machine.run()["generation"], first["generation"])
            self.assertEqual(machine.output.stat().st_mtime_ns, unchanged)
            # From here on AppStream cannot be read: only the refresh path can succeed.
            machine.xml.chmod(0)
            try:
                machine.launcher("org.moos.webapp.chat-later.desktop", "/x",
                                 "X-MoOS-WebApp=chat-later\n")
                (machine.home / ".local/share/moos/appdrop/photocraft.json").unlink()
                machine.deploy("org.example.Fresh", {"appdata-name": "Fresh",
                                                     "appdata-version": "0.1"})
                second = machine.run()
            finally:
                machine.xml.chmod(0o644)
            apps = {app["id"]: app for app in second["apps"]}
            self.assertEqual(second["generation"]["metadata_token"],
                             first["generation"]["metadata_token"])
            self.assertNotEqual(second["generation"]["installed_token"],
                                first["generation"]["installed_token"])
            # AppStream's entry survived: a full build could not have read it.
            self.assertTrue(apps["org.example.Listed"]["listed"])
            self.assertEqual(apps["org.example.Listed"]["installed_version"], "3.1")
            self.assertTrue(apps["chat-later"]["installed"])
            self.assertNotIn("photocraft", apps)
            self.assertEqual(apps["org.example.Fresh"]["name"], "Fresh")
            self.assertFalse(apps["org.example.Fresh"]["listed"])
            self.assertEqual(second["stats"]["dropped_apps"], 3)


# ── A pinned app's update: the answer index.json and check-updates share ──
ARCH = index.running_arch()
PINNED = "1" * 64       # the bytes the catalogue pins now
EARLIER = "0" * 64      # the bytes an earlier pin installed
REVIEW = {"external": True, "risk": "downloaded-executable", "requires_review": True}


def pinned_appdrop(app_id: str) -> dict:
    downloads = {arch: {"url": f"https://example.org/{app_id}-{arch}.AppImage", "sha256": PINNED,
                        "size": 1000} for arch in ("x86_64", "aarch64")}
    return {"id": app_id, "source": "moos", "cat": "util", "glyph": "spark", "en": app_id.title(),
            "ar": "تطبيق", "install": {"kind": "appdrop", "artifact": "appimage",
                                       "version": "0.9.0", "downloads": downloads, **REVIEW}}


def pinned_windows(app_id: str) -> dict:
    return {"id": app_id, "source": "moos", "cat": "win", "glyph": "spark", "en": app_id.title(),
            "ar": "برنامج", "engine": "windows",
            "install": {"kind": "windows-portable", "version": "8.7.1", "exe": "app/app.exe",
                        "downloads": {"x86_64": {"url": f"https://example.org/{app_id}.zip",
                                                 "sha256": PINNED, "size": 1000}}, **REVIEW}}


def pinned_android(package: str, sha256: str = PINNED, size: int = 1000) -> dict:
    return {"id": package, "source": "moos", "cat": "droid", "glyph": "grid", "en": "Droid",
            "ar": "درويد", "engine": "android",
            "install": {"kind": "android", "url": f"https://example.org/{package}.apk",
                        "sha256": sha256, "package": package, "version": "0.29.1", "size": size,
                        **REVIEW}}


# An APK whose bytes the catalogue pins, and another build of the same size.
APK = b"PK\x03\x04" + bytes(range(256)) * 4
OTHER_APK = b"PK\x03\x04" + bytes(reversed(range(256))) * 4
APK_SHA256 = hashlib.sha256(APK).hexdigest()
KEPT = ("org.example.kept", "org.example.caughtup", "org.example.other", "org.example.twice",
        "org.example.linked")

PINNED_APPS = [
    *(pinned_appdrop(app_id) for app_id in ("repinned", "current", "renamed", "adopted",
                                            "adopted-same", "garbled")),
    *(pinned_windows(app_id) for app_id in ("notepad", "sumatra", "folderless", "scrambled")),
    *(pinned_android(package) for package in ("org.example.repin", "org.example.current",
                                              "org.example.legacy", "org.example.gone",
                                              "org.example.garbled")),
    *(pinned_android(package, APK_SHA256, len(APK)) for package in KEPT),
]

# These fixtures have no compiled manifest to compare. Unknown bytes without a Store receipt
# do not identify an acceptable update, exactly as the executor's shared rule says.
RECORDLESS = ("org.example.legacy", "org.example.other", "org.example.twice",
              "org.example.linked")

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
    "org.example.legacy": (True, None, False),    # no record and no APK: bytes unknown
    "org.example.gone": (False, None, False),   # the container no longer has it
    # The APK Android keeps names the bytes when no record of the pin does.
    "org.example.kept": (True, "0.29.1", False),       # no record: the older Store's install
    "org.example.caughtup": (True, "0.29.1", False),   # a record of an earlier pin
    "org.example.other": (True, None, False),        # another build of the pin's size
    "org.example.twice": (True, None, False),        # two copies: Android is replacing it
    "org.example.linked": (True, None, False),       # a link, never followed
    # An invalid UTF-8 receipt is unreadable by the executor too.
    "garbled": (False, None, False),
    "scrambled": (False, None, False),
    "org.example.garbled": (True, None, False),
}
if ARCH != "x86_64":
    # Windows programs are pinned for x86_64 only: there is no pin for this machine to offer.
    EXPECTED.update({"notepad": (True, "8.7.1", False)})
# The pinned-update and index branches are integrated. Compare every fixture against the
# real backend now; none may retain the temporary exclusion used during independent work.
AWAITING_STORECTL = frozenset()


def lifecycle(app: dict) -> tuple:
    return app["installed"], app["installed_version"], app["update_available"]


class NoFlatpakUpdates:
    def update_candidates(self):
        return []


class NoCommands(storectl.CommandRunner):
    """moos-storectl's command boundary, refusing: nothing here may reach the host."""

    def spawn(self, argv):
        raise AssertionError(f"moos-storectl tried to start {list(argv)}")

    def gpu_guard(self):
        raise AssertionError("moos-storectl tried to run its GPU guard")

    def capture(self, argv, timeout=30):
        raise AssertionError(f"moos-storectl tried to run {list(argv)}")

    def run_cancellable(self, argv, should_cancel):
        raise AssertionError(f"moos-storectl tried to run {list(argv)}")


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
            # A Store job names itself to the Island in $XDG_RUNTIME_DIR/moos-store (and
            # removes every other token there): never the person's own.
            "XDG_RUNTIME_DIR": str(base / "run"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
        }
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": PINNED_APPS}), encoding="utf-8")
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

    def kept_apk(self, package: str, data: bytes, *, layout: str = "current",
                 link: bool = False) -> Path:
        """The APK Android keeps for an installed package: /data/app/~~<random>/<package>-<random>
        since Android 11, /data/app/<package>-<n> before."""
        with self.environ():
            app = storectl.data_home() / "waydroid/data/app"
        folder = (app / "~~bWVkaWE=" / f"{package}-c3RvcmU=" if layout == "current"
                  else app / f"{package}-1")
        folder.mkdir(parents=True, exist_ok=True)
        apk = folder / "base.apk"
        if link:
            (folder / "real.apk").write_bytes(data)
            apk.symlink_to(folder / "real.apk")
        else:
            apk.write_bytes(data)
        return apk

    def populate(self) -> None:
        self.appdrop_record("repinned", EARLIER, "0.9.0", catalogued=True)
        self.appdrop_record("current", PINNED, "0.9.0", catalogued=True)
        self.appdrop_record("renamed", PINNED, "0.9", catalogued=True)
        self.appdrop_record("adopted", EARLIER, None, catalogued=False)
        self.appdrop_record("adopted-same", PINNED, None, catalogued=False)
        self.windows_record("notepad", EARLIER, folder=True)
        self.windows_record("sumatra", PINNED, folder=True)
        self.windows_record("folderless", EARLIER, folder=False)
        self.android_state("org.example.repin", sha256=EARLIER, version="0.28.0")
        self.android_state("org.example.current", sha256=PINNED, version="1.7.0")
        self.android_state("org.example.legacy", sha256=None)
        self.android_state("org.example.gone", sha256=EARLIER, version="0.28.0", data=False)
        for package in KEPT:
            record = {"sha256": EARLIER, "version": "0.28.0"} \
                if package == "org.example.caughtup" else {"sha256": None}
            self.android_state(package, **record)
        self.kept_apk("org.example.kept", APK)
        self.kept_apk("org.example.caughtup", APK, layout="older")
        self.kept_apk("org.example.other", OTHER_APK)
        self.kept_apk("org.example.twice", APK)
        self.kept_apk("org.example.twice", APK, layout="older")
        self.kept_apk("org.example.linked", APK, link=True)
        self.appdrop_record("garbled", EARLIER, "0.9.0", catalogued=True)
        self.windows_record("scrambled", EARLIER, folder=True)
        self.android_state("org.example.garbled", sha256=EARLIER, version="0.28.0")
        with self.environ():
            for record in (moos_appdrop.manifest_dir() / "garbled.json",
                           storectl.windows_paths("scrambled").record,
                           storectl.android_record_path("org.example.garbled")):
                self.garble(record)

    @staticmethod
    def garble(record: Path) -> None:
        """One byte that is not UTF-8 in the record's version, as a damaged disk or a hand
        edit leaves it."""

        data = record.read_bytes()
        garbled = data.replace(b'"version": "', b'"version": "\xff', 1)
        assert garbled != data, record
        record.write_bytes(garbled)

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

    def index_here(self, output: Path) -> dict:
        """run_index() in this process, where a test can switch one of the indexer's rules."""

        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("XDG_", "FLATPAK_"))}
        environment.update(self.environment)
        with mock.patch.dict(os.environ, environment, clear=True), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            code = index.main(["--output", str(output), "--catalog", str(self.catalog),
                               "--appstream-root", str(self.base / "flatpak/appstream"),
                               "--installation-root", str(self.base / "flatpak"),
                               "--locale", "en", "--engines", "all"])
        if code != 0:
            raise AssertionError(errors.getvalue())
        return json.loads(output.read_text(encoding="utf-8"))

    def controller(self):
        return storectl.Controller(storectl.JobStore(self.base / "store-cache"),
                                   adapter_factory=NoFlatpakUpdates, runner=NoCommands(),
                                   catalog_path=self.catalog)

    def check_updates(self) -> set[str]:
        """The pin rows moos-storectl's own check-updates lists for this home."""

        with self.environ(), contextlib.redirect_stdout(io.StringIO()):
            code, document = self.controller().check_updates()
        if code != 0:
            raise AssertionError(document)
        return {item["id"] for item in document["items"] if item.get("kind") == "pin"}

    def update(self, app_id: str) -> tuple[list[str], dict]:
        """What moos-storectl's `update <app_id>` does here, the window's Update button: the
        pins it puts in place (recorded, not downloaded) and its job."""

        performed: list[str] = []
        with self.environ(), contextlib.redirect_stdout(io.StringIO()):
            controller = self.controller()
            controller._reinstall_pin = lambda _job, pin_id, _recipe: performed.append(pin_id)
            _code, document = controller.update(app_id)
        return performed, document


class PinnedUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.home = Home(Path(cls.temporary.name))
        cls.home.populate()
        cls.data = cls.home.run_index()
        cls.apps = {app["id"]: app for app in cls.data["apps"]}
        cls.rows = cls.home.check_updates()

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def state(self, app_id: str) -> tuple:
        return lifecycle(self.apps[app_id])

    def test_every_update_the_index_offers_is_one_moos_storectl_performs(self):
        """The window's Update button runs `moos-storectl update <id>`. An update offered here
        that it refuses ("App is not installed") or finds up to date is a button that does
        nothing, and no entry of AWAITING_STORECTL excuses it. Until 2026-10-15 the index
        offered the pin to Android apps an earlier Store installed, which this moos-storectl
        does not find."""

        offered = sorted(app_id for app_id in EXPECTED if self.apps[app_id]["update_available"])
        self.assertTrue(offered, "no fixture offers an update: this would check nothing")
        for app_id in offered:
            with self.subTest(app=app_id):
                performed, job = self.home.update(app_id)
                self.assertEqual(performed, [app_id], job.get("items"))

    def test_nothing_waiting_for_moos_storectl_is_an_update_the_index_offers(self):
        for app_id in sorted(AWAITING_STORECTL):
            with self.subTest(app=app_id):
                self.assertFalse(EXPECTED[app_id][2],
                                 "an update the index offers and check-updates does not list "
                                 "is an Update button that does nothing: nothing may excuse it")

    def test_unknown_apk_bytes_without_a_receipt_are_not_offered_as_an_update(self):
        self.assertNotIn("org.example.legacy", self.rows)
        self.assertFalse(self.apps["org.example.legacy"]["update_available"])

    def test_unparseable_missing_ambiguous_and_linked_apks_match_the_executor(self):
        for app_id in RECORDLESS:
            with self.subTest(app=app_id):
                self.assertEqual(lifecycle(self.apps[app_id]), (True, None, False))
                self.assertNotIn(app_id, self.rows)
        self.assertEqual(lifecycle(self.apps["org.example.kept"]), (True, "0.29.1", False))
        self.assertEqual(lifecycle(self.apps["org.example.caughtup"]), (True, "0.29.1", False))

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
        compared = set(EXPECTED) - AWAITING_STORECTL
        flags = {app_id for app_id in compared if self.apps[app_id]["update_available"]}
        self.assertEqual(self.rows & compared, flags,
                         "index.json and updates.json disagree about the same apps")

    def test_no_case_waits_for_a_rule_moos_storectl_already_applies(self):
        agreeing = sorted(app_id for app_id in AWAITING_STORECTL
                          if (app_id in self.rows) == self.apps[app_id]["update_available"])
        self.assertEqual(agreeing, [], "moos-storectl now gives the index's answer for these: "
                         "take them off AWAITING_STORECTL, so check-updates is compared for "
                         "them too")


class RecordsLiveWhereTheBackendWritesThem(unittest.TestCase):
    def test_paths_agree_under_a_relocated_data_home(self):
        """XDG_DATA_HOME elsewhere than ~/.local/share: both sides follow it (so does the
        Android container, whose data lives under $XDG_DATA_HOME/waydroid)."""
        with tempfile.TemporaryDirectory() as raw:
            home = Home(Path(raw))
            home.environment["XDG_DATA_HOME"] = str(Path(raw) / "elsewhere")
            home.data = Path(raw) / "elsewhere"
            home.windows_record("notepad", EARLIER, folder=True)
            home.android_state("org.example.repin", sha256=EARLIER, version="0.28.0")
            apps = {app["id"]: app for app in home.run_index()["apps"]}
            self.assertTrue(apps["notepad"]["installed"])
            self.assertEqual(apps["org.example.repin"]["installed_version"], "0.28.0")
            self.assertTrue(apps["org.example.repin"]["update_available"])


class AnApkIsReadOnce(unittest.TestCase):
    """Every launch reads what is installed; an APK is hashed again only when it changed."""

    def test_the_digest_is_kept_while_the_file_is_the_same_one(self):
        other = hashlib.sha256(OTHER_APK).hexdigest()
        with tempfile.TemporaryDirectory() as raw:
            apk = Path(raw) / "base.apk"
            apk.write_bytes(APK)
            memo = Path(raw) / "android-apks.json"
            with mock.patch.object(index.hashlib, "sha256", wraps=hashlib.sha256) as hashing:
                first = index.ApkDigests(memo)
                self.assertEqual(first.sha256(apk, len(APK)), APK_SHA256)
                first.save()
                again = index.ApkDigests(memo)
                self.assertEqual(again.sha256(apk, len(APK)), APK_SHA256)
                self.assertEqual(hashing.call_count, 1, "an unchanged APK was read again")
                written = memo.stat().st_mtime_ns
                again.save()
                self.assertEqual(memo.stat().st_mtime_ns, written,
                                 "nothing changed, and the memo was written again")
                # Rewritten in place, the same size: its times are not the ones remembered.
                apk.write_bytes(OTHER_APK)
                later = apk.stat().st_mtime_ns + 10 ** 9
                os.utime(apk, ns=(later, later))
                self.assertEqual(index.ApkDigests(memo).sha256(apk, len(APK)), other)
                self.assertEqual(hashing.call_count, 2)
            # Only a file of the pin's size is read at all.
            self.assertIsNone(index.ApkDigests().sha256(apk, len(APK) + 1))

    def test_a_launch_follows_android_replacing_the_app(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Home(Path(raw))
            home.android_state("org.example.kept", sha256=None)
            kept = home.kept_apk("org.example.kept", APK)
            memo = home.output.parent / "android-apks.json"
            first = {app["id"]: app for app in home.run_index()["apps"]}
            self.assertEqual(first["org.example.kept"]["installed_version"], "0.29.1")
            self.assertFalse(first["org.example.kept"]["update_available"])
            remembered = json.loads(memo.read_text(encoding="utf-8"))["apks"]
            self.assertEqual({name: value[5] for name, value in remembered.items()},
                             {str(kept): APK_SHA256})
            written = memo.stat().st_mtime_ns
            home.run_index()
            self.assertEqual(memo.stat().st_mtime_ns, written)
            # Android installs another build in a folder of its own and drops the old one.
            kept.unlink()
            kept.parent.rmdir()
            newer = home.kept_apk("org.example.kept", OTHER_APK, layout="older")
            second = {app["id"]: app for app in home.run_index()["apps"]}
            self.assertIsNone(second["org.example.kept"]["installed_version"])
            self.assertEqual(second["org.example.kept"]["update_available"], False)
            remembered = json.loads(memo.read_text(encoding="utf-8"))["apks"]
            self.assertEqual(list(remembered), [str(newer)])


class AppDropReceiptOwnership(unittest.TestCase):
    """The index and executor accept the same receipt; the positive comes from install()."""

    def setUp(self):
        import zipfile

        self.temporary = tempfile.TemporaryDirectory(prefix="appdrop-index-receipt-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.environment = unittest.mock.patch.dict(os.environ, {
            "HOME": str(self.home), "XDG_DATA_HOME": str(self.base / "data"),
            "XDG_CACHE_HOME": str(self.base / "cache"),
            "XDG_CONFIG_HOME": str(self.base / "config"),
            "XDG_STATE_HOME": str(self.base / "state"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
            "DISPLAY": "", "WAYLAND_DISPLAY": "",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        archive = self.home / "notes.zip"
        with zipfile.ZipFile(archive, "w") as output:
            binary = zipfile.ZipInfo("notes")
            binary.external_attr = 0o100755 << 16
            output.writestr(binary, "#!/bin/sh\nexit 0\n")
            output.writestr("notes.desktop", "[Desktop Entry]\nType=Application\nName=Notes\n"
                            "Exec=notes\nCategories=Office;\n")
        plan = moos_appdrop.inspect(archive)
        with mock.patch.object(moos_appdrop, "_refresh_menu", lambda: None):
            self.receipt = moos_appdrop.install(plan)
        self.slug = self.receipt["id"]
        self.path = moos_appdrop.manifest_dir() / f"{self.slug}.json"
        self.recipe = {"id": self.slug, "source": "moos", "install": {
            "kind": "appdrop", "artifact": "archive", "version": "1.0",
            "downloads": {index.running_arch(): {"url": "https://example.org/notes.zip",
                                                 "size": archive.stat().st_size,
                                                 "sha256": self.receipt["sha256"]}}}}

    def assert_readers_agree(self, accepted):
        self.assertEqual(bool(moos_appdrop.read_record(self.slug)), accepted)
        state = index.catalog_install_state(self.recipe, index.running_arch())
        inventory = {record["slug"] for record in index.dropped_records(set())}
        self.assertEqual((state["installed"], self.slug in inventory), (accepted, accepted))

    def test_the_real_archive_installs_receipt_remains_manageable(self):
        self.assertEqual((self.receipt["schema"], self.receipt["kind"]), (1, "archive"))
        self.assert_readers_agree(True)

    def test_partial_or_wrong_kind_receipts_are_not_installed_apps(self):
        for changes, absent in (({"schema": 2}, None), ({}, "schema"),
                                ({"kind": "webapp"}, None), ({}, "kind"),
                                ({"kind": ["archive"]}, None)):
            with self.subTest(changes=changes, absent=absent):
                receipt = self.receipt | changes
                if absent:
                    receipt.pop(absent)
                self.path.write_text(json.dumps(receipt), encoding="utf-8")
                self.assert_readers_agree(False)

    def test_a_linked_receipt_is_not_an_installed_app(self):
        elsewhere = self.base / "copied-receipt.json"
        self.path.rename(elsewhere)
        self.path.symlink_to(elsewhere)
        self.assert_readers_agree(False)


if __name__ == "__main__":
    unittest.main()
