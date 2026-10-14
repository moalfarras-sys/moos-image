#!/usr/bin/env python3
"""Mo Store offers a catalogue pin only to what it installed itself.

moos-storectl's check-updates and update and moos-store-index's update_available answer "is
there an update?" by one rule (docs/MO_STORE.md). Each class holds one part of it, run for real
against a private HOME:

  AdoptedAppDrop  a file the person dropped into a catalogue app's slot (App Drop's record has
                  no catalog_id) is theirs: never a pin row, never replaced by Update all, and
                  `update <id>` says to install a newer file instead of putting the pin back.

Nothing here reaches the network, a display, the session bus or the person's real home.
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
import sys
import tarfile
import tempfile
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


if __name__ == "__main__":
    unittest.main()
