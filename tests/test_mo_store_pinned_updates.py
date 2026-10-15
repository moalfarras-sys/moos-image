#!/usr/bin/env python3
"""Mo Store offers a catalogue pin only where it is an update the app can take, never over what
the person installed themselves, and one app that cannot install here fails alone.

moos-storectl's check-updates and update answer "is there an update?" by the rule that
moos-store-index's update_available has to share (docs/MO_STORE.md); for Android that rule is
usr/lib/moos/moos_android_apk.py's pin_is_update(), which both programs call. Each class holds
one part of it, run for real against a private HOME:

  AdoptedAppDrop  a file the person dropped into a catalogue app's slot (App Drop's record has
                  no catalog_id) is theirs: never a pin row, never replaced by Update all, and
                  `update <id>` says to install a newer file instead of putting the pin back;
  LegacyAndroid   an Android app with no record (the earlier Mo Store wrote none, or another
                  installer put it there) is installed while its data directory exists. The APK
                  Android keeps decides: an older build of the same signer is offered the pin
                  and updated in place (the record is written then), the pin itself, a newer
                  build, another signer or the same version are left alone, and so is an APK
                  that cannot be read;
  StoreRecord     the Store's own record names what it installed, but what Android keeps comes
                  first: a build the app's own library moved past the pin is never offered the
                  older pin; only when Android cannot be read does the record decide;
  DroppedApk      an APK the person dropped is theirs, like a dropped file: no row, Update all
                  leaves it, `update <package>` says to install a newer file;
  UpdateReadBack  waydroid's `app install` exits 0 even when Android refuses the APK: an update
                  is read back from what Android keeps (a short, bounded wait), and a refused
                  one fails in the window's words with the record as it was;
  FlatpakBatch    one picked app with no build for this computer fails alone (in the window's
                  words when the catalogue names other computers only) and the rest of the batch
                  still installs in one transaction. This runs the real install() and the real
                  FlatpakAdapter; only libflatpak, GLib and Gio are stand-ins.

The Android stand-in keeps APKs where Android does and refuses them as Android does. Nothing here
reaches the network, a display, the session bus, the Android runtime or the person's real home.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from typing import Any
import unittest
from unittest import mock
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-storectl"
LOADER = importlib.machinery.SourceFileLoader("moos_storectl_pinned_updates", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop as appdrop  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Real APKs in miniature (a compiled manifest in a zip, a signing block), and what each one says.
import test_moos_android_apk as apkfix  # noqa: E402

ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56


def note_app(version: str) -> bytes:
    """A portable archive of one small app whose program's bytes end with its version."""
    desktop = ("[Desktop Entry]\nType=Application\nName=Note Forge\nExec=noteforge\n"
               "Icon=noteforge\nCategories=Office;\n")
    members = {
        f"noteforge-{version}/noteforge": (ELF + version.encode(), 0o755),
        f"noteforge-{version}/org.example.NoteForge.desktop": (desktop.encode(), 0o644),
        f"noteforge-{version}/noteforge.png": (b"\x89PNG\r\n\x1a\n" + b"0" * 64, 0o644),
    }
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, (data, mode) in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class FakeRunner:
    """Records every argv; the Android runtime always answers that its session runs."""

    def __init__(self):
        self.spawned: list[list[str]] = []
        self.commands: list[list[str]] = []

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def gpu_guard(self):
        pass

    def capture(self, argv, timeout=30):
        return MODULE.CommandResult(0, "", False, "Session:\tRUNNING\n")

    def run_cancellable(self, argv, should_cancel):
        self.commands.append(list(argv))
        if should_cancel():
            return MODULE.CommandResult(143, "cancelled", True)
        return MODULE.CommandResult(0)


class FakeAdapter:
    """No Flatpak is installed and none has an update."""

    def is_user_installed(self, app_id):
        return False

    def is_system_installed(self, app_id):
        return False

    def update_refs(self):
        return []

    def update_candidates(self):
        return []


class FakeResponse(io.BytesIO):
    def __init__(self, url: str, body: bytes):
        super().__init__(body)
        self.url = url
        self.headers = {"Content-Length": str(len(body))}

    def geturl(self):
        return self.url


class FakeOpener:
    """Serves pinned bytes by URL, in memory; the download helper's checks still all apply."""

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.requests: list[str] = []

    def open(self, request, timeout=30):
        self.requests.append(request.full_url)
        if request.full_url not in self.files:
            raise urllib.error.URLError("no such file")
        return FakeResponse(request.full_url, self.files[request.full_url])


class Backend(unittest.TestCase):
    ISOLATED = ("HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "XDG_DATA_HOME", "XDG_STATE_HOME",
                "XDG_CONFIG_HOME", "XDG_DATA_DIRS", "DBUS_SESSION_BUS_ADDRESS", "DISPLAY",
                "WAYLAND_DISPLAY", "PATH")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        saved = {name: os.environ.get(name) for name in self.ISOLATED}

        def restore():
            for name, value in saved.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
        self.addCleanup(restore)
        os.environ.update(
            HOME=str(self.home),
            XDG_CACHE_HOME=str(self.home / ".cache"),
            XDG_RUNTIME_DIR=str(self.base / "run"),
            XDG_DATA_HOME=str(self.home / ".local/share"),
            XDG_STATE_HOME=str(self.home / ".local/state"),
            XDG_CONFIG_HOME=str(self.home / ".config"),
            XDG_DATA_DIRS=str(self.base / "system-share"),
            DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent",
            PATH=str(self.base / "no-tools"),
        )
        os.environ.pop("DISPLAY", None)
        os.environ.pop("WAYLAND_DISPLAY", None)
        (self.base / "run").mkdir(mode=0o700)
        self.runner = FakeRunner()
        self.adapter = FakeAdapter()
        self.opener = FakeOpener()
        self.catalogs = 0
        # App Drop would ask the desktop to re-read its menu; nothing here may reach the desktop.
        menu = mock.patch.object(appdrop, "_refresh_menu", lambda: None)
        menu.start()
        self.addCleanup(menu.stop)
        # The command line builds its own opener: it gets the in-memory one, never the network.
        network = mock.patch.object(MODULE, "build_opener", lambda: self.opener)
        network.start()
        self.addCleanup(network.stop)

    def store(self):
        return MODULE.JobStore(self.home / ".cache/moos-store")

    def catalog(self, apps):
        # One file per controller: a controller made earlier keeps reading its own catalogue.
        self.catalogs += 1
        path = self.base / f"catalog-{self.catalogs}.json"
        path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        return path

    def controller(self, apps):
        return MODULE.Controller(self.store(), adapter_factory=lambda: self.adapter,
                                 runner=self.runner, catalog_path=self.catalog(apps),
                                 opener=self.opener)

    def cli(self, apps, *argv) -> int:
        """The command line, as the window's bridge and moai-do start it."""
        with contextlib.redirect_stdout(io.StringIO()):
            return MODULE.main(["--catalog", str(self.catalog(apps)), *argv], store=self.store(),
                               adapter_factory=lambda: self.adapter, runner=self.runner)

    def job_document(self):
        return json.loads((self.home / ".cache/moos-store/job.json").read_text(encoding="utf-8"))

    def pin(self, name: str, body: bytes) -> dict:
        url = f"https://publisher.example/{name}"
        self.opener.files[url] = body
        return {MODULE.running_arch(): {"url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                        "size": len(body)}}


# ── App Drop: the Store's own install, and a file the person dropped into the same slot ────────
class AdoptedAppDrop(Backend):
    def recipe(self, version: str) -> dict:
        return {"id": "noteforge", "source": "moos", "en": "Note Forge", "ar": "نوت فورج",
                "install": {"kind": "appdrop", "artifact": "archive", "version": version,
                            "downloads": self.pin(f"noteforge-{version}.tar.gz", note_app(version)),
                            "risk": "downloaded-executable", "requires_review": True,
                            "external": True}}

    def program(self) -> bytes:
        return (self.home / "Applications/noteforge/noteforge").read_bytes()

    def drop(self, version: str) -> None:
        """The person drops their own newer build: moos-app-drop hands it to install-file."""
        download = self.home / f"Downloads/noteforge-{version}.tar.gz"
        download.parent.mkdir(exist_ok=True)
        download.write_bytes(note_app(version))
        code, result = self.controller([]).install_file(str(download))
        self.assertEqual(result["state"], "success", result)

    def test_the_stores_own_install_is_offered_the_pin_and_a_dropped_file_is_not(self):
        self.assertEqual(self.controller([self.recipe("2.1")]).install(["noteforge"])[1]["state"],
                         "success")
        self.assertEqual(appdrop.read_record("noteforge")["catalog_id"], "noteforge")
        # The catalogue moves on: the Store's own install is offered the newer pin.
        controller = self.controller([self.recipe("2.2")])
        self.assertEqual(controller.check_updates()[1]["items"],
                         [{"id": "noteforge", "kind": "pin", "name": "Note Forge",
                           "version": "2.2", "installed_version": "2.1"}])
        # The person drops a newer build of their own into the same slot ("Update Note Forge?").
        self.drop("2.3")
        record = appdrop.read_record("noteforge")
        self.assertFalse(record.get("catalog_id"), record)
        self.assertTrue(self.program().endswith(b"2.3"))

        document = controller.check_updates()[1]
        self.assertEqual(document["items"], [], "the older pin was offered over the person's file")
        self.assertEqual((document["count"], document["app_count"]), (0, 0))

    def test_update_all_never_puts_the_pin_over_a_file_the_person_dropped(self):
        self.controller([self.recipe("2.1")]).install(["noteforge"])
        self.drop("2.3")
        before = appdrop.read_record("noteforge")
        asked = len(self.opener.requests)
        code, result = self.controller([self.recipe("2.2")]).update()
        self.assertEqual((code, result["state"], result["message_key"]), (0, "success", "up_to_date"),
                         result)
        self.assertEqual(result["items"], [])
        self.assertTrue(self.program().endswith(b"2.3"), "Update all replaced the person's build")
        self.assertEqual(appdrop.read_record("noteforge"), before)
        self.assertEqual(len(self.opener.requests), asked, "Update all downloaded the pin")

    def test_updating_a_dropped_file_by_id_says_to_install_a_newer_file(self):
        self.controller([self.recipe("2.1")]).install(["noteforge"])
        self.drop("2.3")
        before = appdrop.read_record("noteforge")
        asked = len(self.opener.requests)
        code, result = self.controller([self.recipe("2.2")]).update("noteforge")
        self.assertEqual(result["state"], "failed", result)
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("failed", "update_by_file"))
        self.assertTrue(self.program().endswith(b"2.3"), "the pin was installed over the person's build")
        self.assertEqual(appdrop.read_record("noteforge"), before)
        self.assertEqual(len(self.opener.requests), asked)
        # As the window's bridge and moai-do run it.
        self.assertNotEqual(self.cli([self.recipe("2.2")], "update", "noteforge"), 0)
        self.assertEqual(self.job_document()["items"][0]["message_key"], "update_by_file")
        self.assertTrue(self.program().endswith(b"2.3"))


# ── Android: what Android keeps decides, and the Store's own record when it cannot be read ────
class FakeAndroid(FakeRunner):
    """The Android container as moos-storectl drives it, keeping what it installs where Android
    does: <data>/app/~~<random>/<package>-<random>/base.apk, with the package's <data>/data folder.

    `app install` answers as waydroid's does on the station. Android refuses an APK with a lower
    version code than the build it keeps, or signed by another key, or of a package in `refuses`;
    the command still exits 0 and prints nothing, because waydroid's install() never reads the
    container's answer (/usr/lib/waydroid/tools/actions/app_manager.py). With `defer`, an APK
    Android takes lands only when land() is called: an install that answered before Android had
    moved the APK into place.
    """

    def __init__(self, data: Path):
        super().__init__()
        self.data = data
        self.refuses: set[str] = set()
        self.defer = False
        self.pending: list[bytes] = []
        self.serial = 0

    def kept(self) -> dict[str, Path]:
        found = {}
        if (self.data / "app").is_dir():
            for folder in (self.data / "app").glob("*/*"):
                found[folder.name.split("-", 1)[0]] = folder / "base.apk"   # no "-" in a package
        return found

    def keep(self, body: bytes) -> Path:
        package = apkfix.FACTS[hashlib.sha256(body).hexdigest()][0]
        old = self.kept().get(package)
        if old is not None:
            shutil.rmtree(old.parent.parent)
        self.serial += 1
        path = self.data / "app" / f"~~{self.serial}==" / f"{package}-{self.serial}==" / "base.apk"
        path.parent.mkdir(parents=True)
        path.write_bytes(body)
        (self.data / "data" / package).mkdir(parents=True, exist_ok=True)
        return path

    def land(self) -> None:
        for body in self.pending:
            self.keep(body)
        self.pending.clear()

    def capture(self, argv, timeout=30):
        if list(argv[1:3]) == ["app", "list"]:
            return MODULE.CommandResult(0, "", False, "".join(
                f"Name: {package}\npackageName: {package}\n\n" for package in sorted(self.kept())))
        return super().capture(argv, timeout)

    def run_cancellable(self, argv, should_cancel):
        result = super().run_cancellable(argv, should_cancel)
        if list(argv[1:3]) != ["app", "install"] or result.cancelled:
            return result
        body = Path(argv[3]).read_bytes()
        package, code, signer = apkfix.FACTS[hashlib.sha256(body).hexdigest()]
        old = self.kept().get(package)
        _package, old_code, old_signer = (apkfix.FACTS[hashlib.sha256(old.read_bytes()).hexdigest()]
                                          if old is not None else (None, None, None))
        if package in self.refuses or (old_code is not None and code < old_code) \
                or (old_signer and signer and old_signer != signer):
            return result                       # refused by Android, and waydroid says nothing
        if self.defer:
            self.pending.append(body)
        else:
            self.keep(body)
        return result


class Android(Backend):
    PACKAGE = "org.example.maps"
    KEY = b"the maps publisher's key"
    OLD, PIN, NEW = 26082718, 26092932, 26100101   # what the station has, the pin, F-Droid's next

    def setUp(self):
        super().setUp()
        self.runner = self.android = FakeAndroid(self.home / ".local/share/waydroid/data")

    def build(self, code: int, *, key: bytes | None = KEY, payload: bytes = b"",
              package: str | None = None) -> bytes:
        """A real APK of this version code; the same arguments give the same bytes."""
        return apkfix.apk(package or self.PACKAGE, code, f"{code // 10000}.{code % 10000}",
                          signer=key, payload=payload)

    def recipe(self, body: bytes, *, package: str | None = None, sized: bool = True) -> dict:
        """The catalogue entry pinning `body`, named as the main repository names its files."""
        package = package or self.PACKAGE
        facts = apkfix.FACTS[hashlib.sha256(body).hexdigest()]
        url = f"https://f-droid.org/repo/{package}_{facts[1]}.apk"
        self.opener.files[url] = body
        install = {"kind": "android", "package": package, "version": f"v{facts[1]}", "url": url,
                   "sha256": hashlib.sha256(body).hexdigest(), "signer": facts[2],
                   "risk": "external-download", "requires_review": True, "external": True}
        if sized:                               # as the shipped catalogue pins every APK
            install["size"] = len(body)
        return {"id": package, "source": "moos", "en": package.rsplit(".", 1)[-1].title(),
                "install": install}

    def record_path(self, package: str | None = None) -> Path:
        return self.home / ".local/share/moos/android" / f"{package or self.PACKAGE}.json"

    def write_record(self, body: bytes, version: str) -> bytes:
        """The record the Store writes when it installs a pin; its exact bytes."""
        self.record_path().parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps({"schema": 1, "id": self.PACKAGE, "package": self.PACKAGE,
                           "catalog_id": self.PACKAGE, "version": version,
                           "sha256": hashlib.sha256(body).hexdigest(), "source": "catalog",
                           "file": "", "installed_at": 1}).encode()
        self.record_path().write_bytes(data)
        return data

    def kept_code(self, package: str | None = None) -> int | None:
        path = self.android.kept().get(package or self.PACKAGE)
        return None if path is None else apkfix.FACTS[hashlib.sha256(path.read_bytes()).hexdigest()][1]

    def installs(self) -> list[list[str]]:
        return [argv for argv in self.runner.commands if argv[1:3] == ["app", "install"]]

    def rows(self, controller) -> list[tuple]:
        return [(row["id"], row["version"], row["installed_version"])
                for row in controller.check_updates()[1]["items"]]


class LegacyAndroid(Android):
    """No record: the Mo Store before this one wrote none, or another installer put the app there."""

    def test_an_older_build_an_earlier_store_installed_is_offered_its_pin(self):
        # Organic Maps on the owner's station: Android keeps the earlier pin, no record exists.
        self.android.keep(self.build(self.OLD))
        controller = self.controller([self.recipe(self.build(self.PIN))])
        document = controller.check_updates()[1]
        self.assertEqual(document["items"], [{"id": self.PACKAGE, "kind": "pin", "name": "Maps",
                                              "version": f"v{self.PIN}", "installed_version": "2608.2718"}])
        self.assertEqual((document["count"], document["app_count"]), (1, 1))
        self.assertFalse(self.record_path().exists(), "checking for updates wrote a record")

    def test_updating_it_installs_the_pin_in_place_and_writes_the_record(self):
        self.android.keep(self.build(self.OLD))
        pin = self.build(self.PIN)
        controller = self.controller([self.recipe(pin)])
        code, result = controller.update(self.PACKAGE)
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("done", "updated"))
        self.assertEqual(len(self.installs()), 1)
        self.assertFalse([argv for argv in self.runner.commands if argv[1:3] == ["app", "remove"]],
                         "an update removed the app, and Android would have deleted its data")
        self.assertEqual(self.kept_code(), self.PIN)
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual((record["sha256"], record["catalog_id"], record["version"]),
                         (hashlib.sha256(pin).hexdigest(), self.PACKAGE, f"v{self.PIN}"))
        self.assertEqual(self.rows(controller), [])
        code, result = controller.update(self.PACKAGE)
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("skipped", "app_up_to_date"))
        self.assertEqual(len(self.installs()), 1)

    def test_update_all_includes_it(self):
        self.android.keep(self.build(self.OLD))
        pin = self.build(self.PIN)
        code, result = self.controller([self.recipe(pin)]).update()
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual([(item["id"], item["state"]) for item in result["items"]],
                         [(self.PACKAGE, "done")])
        self.assertEqual(json.loads(self.record_path().read_text(encoding="utf-8"))["sha256"],
                         hashlib.sha256(pin).hexdigest())

    def test_a_build_newer_than_the_pin_is_never_offered_the_older_pin(self):
        # The F-Droid client (a catalogue app) moved the app past the catalogue's pin.
        self.android.keep(self.build(self.NEW))
        controller = self.controller([self.recipe(self.build(self.PIN))])
        self.assertEqual(self.rows(controller), [], "the older pin was offered over a newer build")
        code, result = controller.update()
        self.assertEqual((code, result["state"], result["message_key"]), (0, "success", "up_to_date"),
                         result)
        code, result = controller.update(self.PACKAGE)
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("skipped", "app_up_to_date"), result)
        self.assertEqual((self.opener.requests, self.installs()), ([], []))
        self.assertEqual(self.kept_code(), self.NEW)
        self.assertFalse(self.record_path().exists(), "a record now claims the older pin")

    def test_a_build_android_would_refuse_the_pin_over_is_left_alone(self):
        for case, kept in (("signed by another key", self.build(self.OLD, key=b"another key")),
                           ("the same version in other bytes", self.build(self.PIN, payload=b"x"))):
            with self.subTest(case):
                self.android.keep(kept)
                self.assertEqual(self.rows(self.controller([self.recipe(self.build(self.PIN))])), [])
        self.assertEqual(self.opener.requests, [])

    def test_an_app_whose_apk_already_is_the_pin_is_up_to_date(self):
        # The station's VLC and F-Droid: no record, and Android keeps exactly today's pin.
        pin = self.build(self.PIN)
        self.android.keep(pin)
        controller = self.controller([self.recipe(pin)])
        self.assertEqual(self.rows(controller), [], "the pin was offered to an app that already is it")
        self.assertEqual(controller.update()[1]["message_key"], "up_to_date")
        code, result = controller.update(self.PACKAGE)
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("skipped", "app_up_to_date"), result)
        self.assertEqual((self.opener.requests, self.installs()), ([], []))
        self.assertFalse(self.record_path().exists())

    def test_without_a_record_an_apk_that_cannot_be_read_is_left_alone(self):
        apps = self.home / ".local/share/waydroid/data/app"
        old = self.build(self.OLD)

        def no_apk_at_all():
            (self.home / ".local/share/waydroid/data/data" / self.PACKAGE).mkdir(parents=True)

        def two_copies():                       # Android replacing the app: old and new side by side
            self.android.keep(old)
            second = apps / "~~b==" / f"{self.PACKAGE}-b==" / "base.apk"
            second.parent.mkdir(parents=True)
            second.write_bytes(old)

        def a_linked_folder():
            real = self.base / "elsewhere"
            real.mkdir()
            (real / "base.apk").write_bytes(old)
            (apps / "~~a==").mkdir(parents=True)
            (apps / "~~a==" / f"{self.PACKAGE}-a==").symlink_to(real)
            (self.home / ".local/share/waydroid/data/data" / self.PACKAGE).mkdir(parents=True)

        def no_zip_inside():
            self.android.keep(old)
            self.android.kept()[self.PACKAGE].write_bytes(b"PK\x03\x04 not an archive")

        recipe = self.recipe(self.build(self.PIN))
        for case in (no_apk_at_all, two_copies, a_linked_folder, no_zip_inside):
            with self.subTest(case.__name__):
                shutil.rmtree(self.home / ".local/share/waydroid", ignore_errors=True)
                shutil.rmtree(self.base / "elsewhere", ignore_errors=True)
                case()
                controller = self.controller([recipe])
                self.assertEqual(self.rows(controller), [])
                code, result = controller.update(self.PACKAGE)
                self.assertEqual(result["items"][0]["message_key"], "app_up_to_date", result)
        self.assertEqual((self.opener.requests, self.installs()), ([], []))

    @unittest.skipIf(os.geteuid() == 0, "root reads every account's files")
    def test_without_a_record_android_data_another_account_owns_is_left_alone(self):
        # Android's system account owns /data/app (0771): another login account cannot list it.
        self.android.keep(self.build(self.OLD))
        apps = self.home / ".local/share/waydroid/data/app"
        apps.chmod(0o111)
        self.addCleanup(apps.chmod, 0o755)
        self.assertEqual(self.rows(self.controller([self.recipe(self.build(self.PIN))])), [])

    def test_a_record_without_the_data_directory_is_no_installed_app(self):
        self.write_record(self.build(self.OLD), f"v{self.OLD}")
        controller = self.controller([self.recipe(self.build(self.PIN))])
        self.assertEqual(self.rows(controller), [])
        code, result = controller.update(self.PACKAGE)
        self.assertEqual((result["state"], result["items"][0]["message_key"]),
                         ("failed", "not_installed"), result)
        self.assertEqual(self.installs(), [])

    def test_the_station_offers_only_the_app_whose_apk_moved(self):
        # The owner's station: VLC and F-Droid are their pins byte for byte, Organic Maps is the
        # earlier pin (another size); no records.
        apps = []
        for package, kept, pinned in (("org.example.player", 13070108, 13070108),
                                      ("org.example.maps", self.OLD, self.PIN),
                                      ("org.example.repo", 1023052, 1023052)):
            self.android.keep(self.build(kept, package=package))
            apps.append(self.recipe(self.build(pinned, package=package), package=package))
        controller = self.controller(apps)
        self.assertEqual([row[0] for row in self.rows(controller)], ["org.example.maps"])
        code, result = controller.update()
        self.assertEqual([(item["id"], item["state"]) for item in result["items"]],
                         [("org.example.maps", "done")], result)
        self.assertEqual(self.opener.requests,
                         [f"https://f-droid.org/repo/org.example.maps_{self.PIN}.apk"])


class StoreRecord(Android):
    """The Store's own record names the bytes it installed; what Android keeps still comes first."""

    def test_a_recorded_app_on_its_pin_is_up_to_date(self):
        pin = self.build(self.PIN)
        self.android.keep(pin)
        self.write_record(pin, f"v{self.PIN}")
        controller = self.controller([self.recipe(pin)])
        self.assertEqual(self.rows(controller), [])
        code, result = controller.update(self.PACKAGE)
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("skipped", "app_up_to_date"))
        self.assertEqual(self.installs(), [])

    def test_an_older_recorded_pin_is_offered_while_android_cannot_be_read(self):
        old = self.build(self.OLD)
        self.write_record(old, f"v{self.OLD}")
        (self.home / ".local/share/waydroid/data/data" / self.PACKAGE).mkdir(parents=True)
        self.assertEqual(self.rows(self.controller([self.recipe(self.build(self.PIN))])),
                         [(self.PACKAGE, f"v{self.PIN}", f"v{self.OLD}")])

    def test_a_record_of_an_older_pin_yields_to_what_android_keeps(self):
        # The app reached today's pin outside the Store: the repository serves the same file.
        pin = self.build(self.PIN)
        self.android.keep(pin)
        self.write_record(self.build(self.OLD), f"v{self.OLD}")
        controller = self.controller([self.recipe(pin)])
        self.assertEqual(self.rows(controller), [])
        self.assertEqual(controller.update()[1]["message_key"], "up_to_date")
        self.assertEqual(self.installs(), [])

    def test_a_build_the_apps_own_library_moved_past_the_pin_is_left_alone(self):
        # The Store installed the earlier pin; the F-Droid client has since moved the app past
        # today's pin. The record's older bytes do not make the pin an update.
        self.android.keep(self.build(self.NEW))
        self.write_record(self.build(self.OLD), f"v{self.OLD}")
        controller = self.controller([self.recipe(self.build(self.PIN))])
        self.assertEqual(self.rows(controller), [])
        self.assertEqual(controller.update()[1]["message_key"], "up_to_date")
        self.assertEqual((self.opener.requests, self.installs()), ([], []))
        self.assertEqual(self.kept_code(), self.NEW)


class DroppedApk(Android):
    """An APK the person dropped (App Drop -> install-file) is theirs, as a dropped file is."""

    def drop(self, body: bytes) -> None:
        download = self.home / "Downloads/Maps-26.10.apk"
        download.parent.mkdir(parents=True, exist_ok=True)
        download.write_bytes(body)
        code, result = self.controller([]).install_file(str(download))
        self.assertEqual(result["state"], "success", result)
        record = json.loads(self.record_path().read_text(encoding="utf-8"))
        self.assertEqual((record["source"], record["catalog_id"]), ("file", ""))

    def test_an_apk_the_person_installed_is_never_offered_the_pin(self):
        self.drop(self.build(self.NEW))
        before = self.record_path().read_bytes()
        controller = self.controller([self.recipe(self.build(self.PIN))])
        self.assertEqual(self.rows(controller), [], "the catalogue's older pin was offered")
        asked, installs = len(self.opener.requests), len(self.installs())
        code, result = controller.update()
        self.assertEqual((code, result["state"], result["message_key"]), (0, "success", "up_to_date"),
                         result)
        self.assertEqual((len(self.opener.requests), len(self.installs())), (asked, installs),
                         "Update all put the pin over the person's own APK")
        self.assertEqual(self.record_path().read_bytes(), before)
        self.assertEqual(self.kept_code(), self.NEW)

    def test_updating_it_by_id_says_to_install_a_newer_file(self):
        self.drop(self.build(self.OLD))           # older than the pin: still theirs
        before = self.record_path().read_bytes()
        apps = [self.recipe(self.build(self.PIN))]
        self.assertEqual(self.rows(self.controller(apps)), [])
        code, result = self.controller(apps).update(self.PACKAGE)
        self.assertEqual((result["state"], result["items"][0]["message_key"]),
                         ("failed", "update_by_file"), result)
        # As the window's bridge and moai-do run it.
        self.assertNotEqual(self.cli(apps, "update", self.PACKAGE), 0)
        self.assertEqual(self.job_document()["items"][0]["message_key"], "update_by_file")
        self.assertEqual((self.record_path().read_bytes(), self.kept_code()), (before, self.OLD))
        self.assertEqual(len(self.installs()), 1, "only the drop itself was installed")


class UpdateReadBack(Android):
    """waydroid's `app install` exits 0 whatever Android answers: an update is what Android keeps."""

    def setUp(self):
        super().setUp()
        # The read-back's pauses advance a private clock instead of the test's: a refusal is
        # asked about for ANDROID_READBACK_SECONDS, and no test waits that long.
        self.clock = [0.0]

        def pause(seconds):
            self.clock[0] += seconds
        patch = mock.patch.multiple(MODULE.time, sleep=pause, monotonic=lambda: self.clock[0])
        patch.start()
        self.addCleanup(patch.stop)

    def test_an_update_android_refuses_fails_and_keeps_the_record(self):
        old = self.build(self.OLD)
        self.android.keep(old)
        before = self.write_record(old, f"v{self.OLD}")
        self.android.refuses.add(self.PACKAGE)      # e.g. an app made for a newer Android
        apps = [self.recipe(self.build(self.PIN))]
        code, result = self.controller(apps).update()
        item = result["items"][0]
        self.assertEqual((item["id"], item["state"], item["message_key"]),
                         (self.PACKAGE, "failed", "android_update_refused"), result)
        self.assertNotIn("waydroid", item["message"].lower())
        self.assertEqual((code, result["state"]), (1, "failed"), result)
        self.assertEqual(self.record_path().read_bytes(), before, "the record claims the pin")
        self.assertEqual(self.kept_code(), self.OLD)
        # It is still an update that has not happened, and `update <id>` says so in the same words.
        self.assertEqual([row[0] for row in self.rows(self.controller(apps))], [self.PACKAGE])
        self.assertNotEqual(self.cli(apps, "update", self.PACKAGE), 0)
        document = self.job_document()
        self.assertEqual((document["state"], document["message_key"],
                          document["items"][0]["state"], document["items"][0]["message_key"]),
                         ("failed", "android_update_refused", "failed", "android_update_refused"))
        self.assertEqual(self.record_path().read_bytes(), before)

    def test_without_a_record_a_refused_update_leaves_none(self):
        self.android.keep(self.build(self.OLD))
        self.android.refuses.add(self.PACKAGE)
        code, result = self.controller([self.recipe(self.build(self.PIN))]).update(self.PACKAGE)
        self.assertEqual((result["state"], result["items"][0]["message_key"]),
                         ("failed", "android_update_refused"), result)
        self.assertFalse(self.record_path().exists(), "a record now claims the pin")

    def test_an_apk_android_moves_into_place_a_moment_later_is_an_update(self):
        self.android.keep(self.build(self.OLD))
        self.android.defer = True
        pauses = []

        def pause(seconds):
            pauses.append(seconds)
            self.clock[0] += seconds
            if len(pauses) == 3:
                self.android.land()
        with mock.patch.object(MODULE.time, "sleep", pause):
            code, result = self.controller([self.recipe(self.build(self.PIN))]).update(self.PACKAGE)
        self.assertEqual((code, result["items"][0]["state"], result["items"][0]["message_key"]),
                         (0, "done", "updated"), result)
        self.assertEqual(len(pauses), 3)
        self.assertEqual(self.kept_code(), self.PIN)

    def test_the_read_back_is_bounded(self):
        self.android.keep(self.build(self.OLD))
        self.android.defer = True                   # never lands
        code, result = self.controller([self.recipe(self.build(self.PIN))]).update(self.PACKAGE)
        self.assertEqual(result["items"][0]["message_key"], "android_update_refused", result)
        self.assertGreaterEqual(self.clock[0], MODULE.ANDROID_READBACK_SECONDS)
        self.assertLess(self.clock[0], MODULE.ANDROID_READBACK_SECONDS + 1)

    @unittest.skipIf(os.geteuid() == 0, "root reads every account's files")
    def test_when_android_cannot_be_read_waydroids_answer_stands_as_before(self):
        # Another account's Android data: the record decides what is offered, and nothing can be
        # read back, so the install's exit status is all there is.
        old = self.build(self.OLD)
        self.android.keep(old)
        self.write_record(old, f"v{self.OLD}")
        self.android.defer = True
        apps = self.home / ".local/share/waydroid/data/app"
        apps.chmod(0o111)
        self.addCleanup(apps.chmod, 0o755)
        code, result = self.controller([self.recipe(self.build(self.PIN))]).update()
        self.assertEqual([(item["id"], item["state"], item["message_key"]) for item in result["items"]],
                         [(self.PACKAGE, "done", "updated")], result)


# ── Flatpak: the real install() and FlatpakAdapter over a stand-in libflatpak ─────────────────
class GLibError(Exception):
    def __init__(self, domain: str, code: str):
        super().__init__(f"{domain}: {code}")
        self.domain, self.code = domain, code

    def matches(self, domain, code) -> bool:
        return (self.domain, self.code) == (domain, code)


class GLib:
    Error = GLibError


class Cancellable:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def is_cancelled(self):
        return self.cancelled


class Gio:
    Cancellable = Cancellable


class Ref:
    """One app ref of the remote's listing for one architecture."""

    def __init__(self, name: str, arch: str):
        self.name, self.arch = name, arch

    def get_name(self):
        return self.name

    def get_kind(self):
        return "app"

    def get_arch(self):
        return self.arch

    def get_branch(self):
        return "stable"

    def format_ref(self):
        return f"app/{self.name}/{self.arch}/stable"


class Remote:
    """The verified Flathub remote, as libflatpak describes it."""

    def get_name(self):
        return "flathub"

    def get_url(self):
        return MODULE.FLATHUB_REPO_BASE

    def get_gpg_verify(self):
        return True

    def get_disabled(self):
        return False

    def get_nodeps(self):
        return False


class Progress:
    def set_update_frequency(self, _milliseconds):
        pass

    def get_status(self):
        return "Installing"

    def get_is_estimating(self):
        return False

    def get_progress(self):
        return 100

    def connect(self, _signal, _callback):
        pass


class Operation:
    def __init__(self, ref: str):
        self.ref = ref

    def get_ref(self):
        return self.ref


class Transaction:
    """Runs what was queued: ready, then each operation starts and completes."""

    def __init__(self, libflatpak: "Libflatpak", installation: "Installation"):
        self.libflatpak, self.installation = libflatpak, installation
        self.queued: list[str] = []
        self.handlers: dict[str, Any] = {}

    def set_no_interaction(self, _value):
        pass

    def add_install(self, remote, ref, _subpaths):
        self.queued.append(ref)
        return True

    def connect(self, signal, callback):
        self.handlers[signal] = callback

    def get_operations(self):
        return [Operation(ref) for ref in self.queued]

    def run(self, _cancellable):
        self.libflatpak.transactions.append(list(self.queued))
        if not self.handlers["ready"](self):
            return False
        for operation in self.get_operations():
            self.handlers["new-operation"](self, operation, Progress())
            self.installation.installed.add(operation.get_ref().split("/")[1])
            self.handlers["operation-done"](self, operation, "commit", None)
        return True


class Libflatpak:
    """The `Flatpak` namespace FlatpakAdapter calls, for one machine and one remote listing."""

    class RefKind:
        APP = "app"

    class Error:
        NOT_INSTALLED = "not-installed"

    class TransactionErrorDetails:
        FATAL = 1

    def __init__(self, arch: str, refs: list[Ref]):
        self.arch, self.refs = arch, refs
        self.transactions: list[list[str]] = []
        outer = self

        class TransactionFactory:
            @staticmethod
            def new_for_installation(installation, _cancellable):
                return Transaction(outer, installation)

        self.Transaction = TransactionFactory

    def get_default_arch(self):
        return self.arch

    @staticmethod
    def error_quark():
        return "flatpak-error-quark"


class Installation:
    def __init__(self, libflatpak: Libflatpak, remotes=()):
        self.libflatpak = libflatpak
        self.remotes = list(remotes)
        self.installed: set[str] = set()

    def list_remotes(self, _cancellable):
        return list(self.remotes)

    def list_remote_refs_sync(self, _remote, _cancellable):
        return list(self.libflatpak.refs)

    def get_current_installed_app(self, app_id, _cancellable):
        if app_id not in self.installed:
            raise GLibError(Libflatpak.error_quark(), Libflatpak.Error.NOT_INSTALLED)
        return object()


# Welcome's first run with the Office direction: the two preselected apps, then the bundle.
WELCOME_OFFICE = ["org.gnome.Snapshot", "org.kde.krecorder", "org.libreoffice.LibreOffice",
                  "org.onlyoffice.desktopeditors", "org.mozilla.thunderbird",
                  "com.github.jeromerobert.pdfarranger", "us.zoom.Zoom", "com.slack.Slack"]
# As the shipped catalogue has them: Flathub publishes these three for x86_64 only.
X86_ONLY = {"org.mozilla.thunderbird", "us.zoom.Zoom", "com.slack.Slack"}


class FlatpakBatch(Backend):
    def catalog_apps(self) -> list[dict]:
        apps = []
        for app_id in WELCOME_OFFICE:
            app = {"id": app_id, "source": "flathub", "en": app_id.rsplit(".", 1)[-1]}
            if app_id in X86_ONLY:
                app["arch"] = ["x86_64"]
            apps.append(app)
        return apps

    def machine(self, arch: str, refs: list[Ref]) -> Libflatpak:
        """This computer's libflatpak and remote; the controller gets the REAL adapter over it."""
        libflatpak = Libflatpak(arch, refs)
        adapter = object.__new__(MODULE.FlatpakAdapter)
        adapter.Flatpak, adapter.Gio, adapter.GLib = libflatpak, Gio, GLib
        adapter.user = Installation(libflatpak, remotes=[Remote()])
        adapter.system = Installation(libflatpak)
        self.launched: list[str] = []
        adapter.launch = self.launched.append      # never a real launch from a test
        self.adapter = adapter
        arch_patch = mock.patch.object(MODULE, "running_arch", lambda: arch)
        arch_patch.start()
        self.addCleanup(arch_patch.stop)
        return libflatpak

    @staticmethod
    def flathub(arch: str, names) -> list[Ref]:
        return [Ref(name, arch) for name in names]

    def test_on_arm_the_apps_with_a_build_install_and_the_others_fail_alone(self):
        here = [name for name in WELCOME_OFFICE if name not in X86_ONLY]
        libflatpak = self.machine("aarch64", self.flathub("x86_64", WELCOME_OFFICE)
                                  + self.flathub("aarch64", here))
        code, result = self.controller(self.catalog_apps()).install(WELCOME_OFFICE)
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(libflatpak.transactions, [[f"app/{name}/aarch64/stable" for name in here]],
                         "the apps that exist for this computer were not installed in one transaction")
        for name in here:
            self.assertEqual(items[name]["state"], "done", items[name])
        for name in X86_ONLY:
            self.assertEqual((items[name]["state"], items[name].get("message_key")),
                             ("failed", "unsupported_arch"), items[name])
            others = [other for other in WELCOME_OFFICE if other != name]
            self.assertFalse([other for other in others if other in items[name]["message"]],
                             f"{name}'s reason names another app: {items[name]['message']}")
        self.assertEqual((code, result["state"]), (1, "partial"), result)
        self.assertEqual(self.adapter.user.installed, set(here))

    def test_an_id_flathub_has_only_for_other_computers_fails_alone_in_honest_words(self):
        # Not a catalogue entry: an id Mo AI or a person typed. Flathub lists it for x86_64 only.
        libflatpak = self.machine("aarch64", self.flathub("aarch64", ["org.gnome.Snapshot"])
                                  + self.flathub("x86_64", ["org.example.Elsewhere"]))
        code, result = self.controller(self.catalog_apps()).install(
            ["org.example.Elsewhere", "org.gnome.Snapshot"])
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(libflatpak.transactions, [["app/org.gnome.Snapshot/aarch64/stable"]])
        self.assertEqual(items["org.gnome.Snapshot"]["state"], "done", items)
        # A failure without a key reaches the window in its own words (tests/test_store_job_language).
        failed = items["org.example.Elsewhere"]
        self.assertEqual((failed["state"], failed.get("message_key")), ("failed", None), failed)
        self.assertIn("org.example.Elsewhere", failed["message"])
        self.assertIn("Flathub", failed["message"])
        self.assertNotIn("flatpak", failed["message"].lower(), "the engine said its name")
        self.assertEqual(result["state"], "partial", result)

    def test_when_nothing_has_a_build_here_no_transaction_runs_and_each_says_why(self):
        libflatpak = self.machine("aarch64", self.flathub("x86_64", sorted(X86_ONLY)))
        code, result = self.controller(self.catalog_apps()).install(
            ["org.example.Elsewhere", "com.slack.Slack"])
        self.assertEqual(libflatpak.transactions, [])
        self.assertEqual((code, result["state"]), (1, "failed"), result)
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(items["com.slack.Slack"].get("message_key"), "unsupported_arch")
        self.assertIn("org.example.Elsewhere", items["org.example.Elsewhere"]["message"])
        self.assertNotIn("com.slack.Slack", items["org.example.Elsewhere"]["message"])

    def test_the_optional_engine_still_fails_when_it_has_no_build_here(self):
        # open-engine asks install_many for one app and then opens it: an id it cannot install
        # must still stop it, never open an app that is not there.
        libflatpak = self.machine("aarch64", self.flathub("x86_64", [MODULE.BAZAAR_ID]))
        code, result = self.controller([]).open_engine("bazaar")
        self.assertEqual(result["state"], "failed", result)
        self.assertIn(MODULE.BAZAAR_ID, result["items"][0]["message"])
        self.assertEqual(libflatpak.transactions, [])
        self.assertEqual(self.launched, [])
        self.assertEqual(self.runner.commands, [], "the engine's launcher was prepared anyway")

    def test_on_a_pc_the_same_picks_install_together(self):
        libflatpak = self.machine("x86_64", self.flathub("x86_64", WELCOME_OFFICE)
                                  + self.flathub("aarch64", WELCOME_OFFICE))
        code, result = self.controller(self.catalog_apps()).install(WELCOME_OFFICE)
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual(libflatpak.transactions,
                         [[f"app/{name}/x86_64/stable" for name in WELCOME_OFFICE]])


if __name__ == "__main__":
    unittest.main()
