#!/usr/bin/env python3
"""Mo Store opens and removes apps by the ids it publishes, and opening never waits on a job.

Each class holds one promise of moos-storectl, run for real against a private HOME:

  DroppedIds            a file the person dropped whose name a catalogue app of another kind
                        already uses is listed as appdrop-<slug> (moos-store-index); that id removes,
                        opens, updates and describes it, and only a record the person dropped
                        answers to it;
  OpenBesideAJob        opening an app changes nothing, so another job or the scheduled updater
                        holding job.lock does not make Open fail, and never costs the job that holds
                        it its job.json or its cancel request;
  AndroidFromALink      `run --no-android-start` (what a moos: link asks for) never starts Android
                        app support; the person's own request still may;
  OpenWhatIsThere       an App Drop app whose folder or program is gone is not installed, not
                        "opened";
  CommandLineTools      an installed command-line tool has no window, which is not "not installed";
  InterruptedDownloads  what an interrupted job left in the downloads folder is swept by the next
                        job, with the lock held, and never by an open beside another job;
  RoutesWithTheRealBackend
                        moos-control's open and moos-open's apps/run route, driven against the real
                        backend while the scheduled updater holds the lock: the app opens, and every
                        other answer is said as what it is.

Nothing here reaches the network, a display, the session bus, Android or the person's real
home: every program the backend would start is recorded, never run.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-storectl"
CONTROL = ROOT / "system_files/usr/bin/moos-control"
OPEN = ROOT / "system_files/usr/bin/moos-open"
LOADER = importlib.machinery.SourceFileLoader("moos_storectl_open_and_ids", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop as appdrop  # noqa: E402

ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56
STOPPED = "Session:\tSTOPPED\n"
RUNNING = "Session:\tRUNNING\n"


def note_app(version: str) -> bytes:
    desktop = ("[Desktop Entry]\nType=Application\nName=Note Forge\nExec=noteforge\n"
               "Icon=noteforge\nCategories=Office;\n")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, (data, mode) in {
            f"noteforge-{version}/noteforge": (ELF + version.encode(), 0o755),
            f"noteforge-{version}/org.example.NoteForge.desktop": (desktop.encode(), 0o644),
            f"noteforge-{version}/noteforge.png": (b"\x89PNG\r\n\x1a\n" + b"0" * 64, 0o644),
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class FakeRunner:
    """Records every argv; answers `waydroid status` from `session`. Never executes anything."""

    def __init__(self, session: str = RUNNING):
        self.spawned: list[list[str]] = []
        self.commands: list[list[str]] = []
        self.probes: list[list[str]] = []
        self.guard_calls = 0
        self.session = session

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def gpu_guard(self):
        self.guard_calls += 1

    def capture(self, argv, timeout=30):
        self.probes.append(list(argv))
        return MODULE.CommandResult(0, "", False, self.session)

    def run_cancellable(self, argv, should_cancel):
        self.commands.append(list(argv))
        return MODULE.CommandResult(0)


class FakeAdapter:
    def __init__(self, *, user=()):
        self.user = set(user)
        self.launches: list[str] = []

    def is_user_installed(self, app_id):
        return app_id in self.user

    def is_system_installed(self, app_id):
        return False

    def update_refs(self):
        return []

    def launch(self, app_id):
        self.launches.append(app_id)


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

    def open(self, request, timeout=30):
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
        menu = mock.patch.object(appdrop, "_refresh_menu", lambda: None)
        menu.start()
        self.addCleanup(menu.stop)

    # ── the backend, as the window's bridge and the routes start it ──────────────────────────
    @property
    def cache(self) -> Path:
        return self.home / ".cache/moos-store"

    def store(self):
        return MODULE.JobStore(self.cache)

    def catalog(self, apps):
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        return path

    def controller(self, apps):
        return MODULE.Controller(self.store(), adapter_factory=lambda: self.adapter,
                                 runner=self.runner, catalog_path=self.catalog(apps),
                                 opener=self.opener)

    def cli(self, apps, *argv) -> tuple[int, dict]:
        """The command line: exit code and the document it printed (refusals included)."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            code = MODULE.main(["--catalog", str(self.catalog(apps)), *argv], store=self.store(),
                               adapter_factory=lambda: self.adapter, runner=self.runner)
        return code, json.loads(printed.getvalue().strip().splitlines()[-1])

    def job_document(self):
        return json.loads((self.cache / "job.json").read_text(encoding="utf-8"))

    # ── what another process holds ─────────────────────────────────────────────────────────────
    def hold_lock(self):
        """job.lock held from its own open file, as moos-flatpak-update holds it through a whole
        `flatpak update` (`exec {fd}<>job.lock; flock -n`)."""
        self.cache.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.cache / "job.lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(os.close, fd)

    def live_job(self, action="install", item="org.example.Running") -> bytes:
        """Another request's job, still being reported in job.json: its bytes, to compare."""
        store = self.store()
        job = MODULE.Job(store, action, [item])
        job.update(state="running", progress=40, current_id=item, message="Downloading")
        store.request_cancel(job.job_id)
        return store.path.read_bytes()

    def finished_job(self):
        store = self.store()
        job = MODULE.Job(store, "install", ["org.example.Earlier"])
        job.update_item("org.example.Earlier", state="done", progress=100)
        job.finish_from_items("Done", "all_ready")

    # ── recipes ─────────────────────────────────────────────────────────────────────────────────
    @staticmethod
    def webapp(app_id: str) -> dict:
        return {"id": app_id, "source": "moos", "en": app_id.title(), "ar": app_id,
                "cat": "office", "desc_en": "A web app", "desc_ar": "تطبيق ويب",
                "install": {"kind": "webapp", "url": f"https://{app_id}.example/",
                            "hosts": [f"{app_id}.example"], "permissions": ["notifications"],
                            "accent": "#336699", "risk": "web-app", "requires_review": True}}

    @staticmethod
    def android(package: str = "org.example.notes") -> dict:
        return {"id": package, "source": "moos", "en": "Notes",
                "install": {"kind": "android", "package": package}}

    @staticmethod
    def npm(app_id: str = "codex", binary: str = "codex") -> dict:
        return {"id": app_id, "source": "moos", "en": "Codex",
                "install": {"kind": "npm", "pkg": "@openai/codex", "bin": binary,
                            "risk": "runs-package-scripts", "requires_review": True}}

    def appdrop_recipe(self, version: str = "2.1") -> dict:
        body = note_app(version)
        url = f"https://publisher.example/noteforge-{version}.tar.gz"
        self.opener.files[url] = body
        return {"id": "noteforge", "source": "moos", "en": "Note Forge", "ar": "نوت فورج",
                "install": {"kind": "appdrop", "artifact": "archive", "version": version,
                            "downloads": {MODULE.running_arch(): {
                                "url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                "size": len(body)}},
                            "risk": "downloaded-executable", "requires_review": True,
                            "external": True}}

    def drop(self, file_name: str) -> dict:
        """A file the person dropped, installed by App Drop the way moos-app-drop installs it."""
        download = self.home / "Downloads" / file_name
        download.parent.mkdir(exist_ok=True)
        download.write_bytes(note_app("0.11.5"))
        return appdrop.install(appdrop.inspect(download))


class DroppedIds(Backend):
    """moos-store-index lists a dropped `figma` beside the catalogue's web app `figma` as
    `appdrop-figma` (apply_lifecycle); the window sends that id back to every verb."""

    def setUp(self):
        super().setUp()
        self.record = self.drop("figma-linux_0.11.5_linux_x86_64.tar.gz")
        self.apps = [self.webapp("figma")]

    def test_the_drop_really_takes_the_catalogue_apps_name(self):
        self.assertEqual(self.record["id"], "figma")
        self.assertNotIn("catalog_id", self.record)

    def test_appdrop_id_opens_the_dropped_app(self):
        code, result = self.controller(self.apps).run("appdrop-figma")
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual([item["id"] for item in result["items"]], ["appdrop-figma"],
                         "the window waits for the id it sent")
        self.assertEqual(self.runner.spawned, [[MODULE.GTK_LAUNCH, "org.example.NoteForge.desktop"]])

    def test_appdrop_id_removes_the_dropped_app_and_nothing_else(self):
        controller = self.controller(self.apps)
        controller.install(["figma"])                    # the catalogue's web app, installed too
        code, result = controller.remove("appdrop-figma")
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual([(item["id"], item["message_key"]) for item in result["items"]],
                         [("appdrop-figma", "removed")])
        self.assertEqual(appdrop.installed(), [])
        self.assertFalse((self.home / "Applications/figma").exists())
        self.assertTrue(self.webapp_installed("figma"), "removing the drop removed the web app")

    def test_appdrop_id_with_data_says_what_it_kept(self):
        code, result = self.controller(self.apps).remove("appdrop-figma", delete_data=True)
        self.assertEqual(result["items"][0]["message_key"], "removed_data_untracked", result)

    def test_appdrop_id_is_updated_by_a_newer_file(self):
        code, document = self.cli(self.apps, "update", "appdrop-figma")
        self.assertEqual(code, 2)
        self.assertEqual((document["message_key"], self.job_document()["message_key"]),
                         ("update_by_file", "update_by_file"))

    def test_appdrop_id_describes_the_dropped_apps_permissions(self):
        code, document = self.controller(self.apps).permissions("appdrop-figma")
        self.assertEqual((code, document["kind"], document["sandboxed"], document["note_key"]),
                         (0, "unsandboxed", False, "full_access"))
        written = json.loads((self.cache / "permissions/appdrop-figma.json").read_text(encoding="utf-8"))
        self.assertEqual(written["id"], "appdrop-figma")

    def test_only_a_dropped_record_answers_to_the_second_name(self):
        controller = self.controller([*self.apps, self.appdrop_recipe()])
        self.assertEqual(controller.install(["noteforge"])[1]["state"], "success")
        self.assertEqual(appdrop.read_record("noteforge")["catalog_id"], "noteforge")
        for app_id in ("appdrop-noteforge",          # the catalogue's own App Drop install
                       "appdrop-nothing",            # no record at all
                       "appdrop-a",                  # not an App Drop slug
                       "appdrop-Figma", "appdrop-", "appdrop-../figma"):
            with self.subTest(app_id=app_id):
                for verb in ("run", "remove", "update", "permissions"):
                    code, document = self.cli([*self.apps, self.appdrop_recipe()], verb, app_id)
                    self.assertEqual((code, document["message_key"]), (2, "invalid_id"), (verb, document))
        self.assertTrue((self.home / "Applications/noteforge").is_dir())
        self.assertTrue((self.home / "Applications/figma").is_dir())

    def webapp_installed(self, app_id: str) -> bool:
        launcher = self.home / f".local/share/applications/org.moos.webapp.{app_id}.desktop"
        return launcher.is_file() and f"\nX-MoOS-WebApp={app_id}\n" in launcher.read_text(encoding="utf-8")


class OpenBesideAJob(Backend):
    def setUp(self):
        super().setUp()
        self.apps = [self.webapp("whatsapp")]
        self.assertEqual(self.controller(self.apps).install(["whatsapp"])[1]["state"], "success")
        self.runner.spawned.clear()

    def test_the_scheduled_updater_holding_the_lock_does_not_stop_an_open(self):
        self.finished_job()
        self.hold_lock()
        code, document = self.cli(self.apps, "run", "whatsapp")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertEqual(self.runner.spawned, [[MODULE.WEBAPP_RUNTIME, "whatsapp"]])
        # The window waits for a run document with the id it sent; the updater writes none.
        published = self.job_document()
        self.assertEqual((published["action"], published["state"], published["job_id"]),
                         ("run", "success", document["job_id"]))
        self.assertEqual([item["id"] for item in published["items"]], ["whatsapp"])

    def test_a_live_job_keeps_its_document_and_its_cancel_request(self):
        before = self.live_job()
        cancel = (self.cache / "cancel").read_bytes()
        self.hold_lock()
        code, document = self.cli(self.apps, "run", "whatsapp")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertEqual(self.runner.spawned, [[MODULE.WEBAPP_RUNTIME, "whatsapp"]])
        self.assertEqual((self.cache / "job.json").read_bytes(), before,
                         "opening an app overwrote the running job's document")
        self.assertEqual((self.cache / "cancel").read_bytes(), cancel,
                         "opening an app cleared the running job's cancel request")

    def test_an_app_that_is_not_installed_is_still_said_to_be_so(self):
        self.hold_lock()
        code, document = self.cli(self.apps + [self.webapp("gmail")], "run", "gmail")
        self.assertEqual((code, document["message_key"]), (1, "not_installed"), document)
        self.assertEqual(self.runner.spawned, [])

    def test_a_flatpak_opens_beside_a_job_too(self):
        self.adapter.user.add("org.example.App")
        self.hold_lock()
        code, document = self.cli([], "run", "org.example.App")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertEqual(self.adapter.launches, ["org.example.App"])
        code, document = self.cli([], "run", "org.example.Missing")
        self.assertEqual((code, document["message_key"]), (1, "not_installed"), document)

    def test_android_opens_beside_a_job_only_into_a_running_session(self):
        apps = [self.android()]
        self.hold_lock()
        code, document = self.cli(apps, "run", "org.example.notes")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertIn([MODULE.WAYDROID, "app", "launch", "org.example.notes"], self.runner.commands)
        # Starting the session is the job's own business beside it (it may be starting it now):
        # the open waits for no one and races no one; it answers busy.
        self.runner.session = STOPPED
        self.runner.commands.clear()
        code, document = self.cli(apps, "run", "org.example.notes")
        self.assertEqual((code, document["state"], document["message_key"]), (75, "busy", "busy"))
        self.assertNotIn([MODULE.WAYDROID, "session", "start"], self.runner.spawned)
        self.assertEqual(self.runner.commands, [])

    def test_with_the_lock_free_an_open_is_a_job_like_any_other(self):
        code, document = self.cli(self.apps, "run", "whatsapp")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertEqual(self.job_document()["job_id"], document["job_id"])


class AndroidFromALink(Backend):
    APPS = [Backend.android()]

    def test_a_link_never_starts_android_app_support(self):
        self.runner.session = STOPPED
        code, document = self.cli(self.APPS, "run", "--no-android-start", "org.example.notes")
        self.assertEqual((code, document["state"]), (2, "failed"), document)
        self.assertEqual(document["message_key"], "android_not_running")
        self.assertEqual(self.job_document()["message_key"], "android_not_running")
        self.assertNotIn([MODULE.WAYDROID, "session", "start"], self.runner.spawned)
        self.assertEqual(self.runner.commands, [], "an app was launched into no session")
        self.assertEqual(self.runner.guard_calls, 0, "the GPU was cleared for an app that never opened")

    def test_a_link_opens_an_android_app_into_a_running_session(self):
        code, document = self.cli(self.APPS, "run", "--no-android-start", "org.example.notes")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertEqual(self.runner.commands, [[MODULE.WAYDROID, "app", "launch", "org.example.notes"]])
        self.assertNotIn([MODULE.WAYDROID, "session", "start"], self.runner.spawned)

    def test_a_link_beside_a_job_says_the_same(self):
        self.runner.session = STOPPED
        self.hold_lock()
        code, document = self.cli(self.APPS, "run", "--no-android-start", "org.example.notes")
        self.assertEqual((code, document["message_key"]), (2, "android_not_running"), document)
        self.assertNotIn([MODULE.WAYDROID, "session", "start"], self.runner.spawned)

    def test_the_persons_own_request_still_starts_it(self):
        self.runner.session = STOPPED
        started = []

        def spawn(argv):
            started.append(list(argv))
            self.runner.session = RUNNING                # the session comes up
        self.runner.spawn = spawn
        with mock.patch.object(MODULE.time, "sleep", lambda _seconds: None):
            code, document = self.cli(self.APPS, "run", "org.example.notes")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertIn([MODULE.WAYDROID, "session", "start"], started)

    def test_the_flag_changes_nothing_for_other_kinds(self):
        apps = [self.webapp("whatsapp")]
        self.controller(apps).install(["whatsapp"])
        code, document = self.cli(apps, "run", "--no-android-start", "whatsapp")
        self.assertEqual((code, document["state"]), (0, "success"), document)


class OpenWhatIsThere(Backend):
    def test_a_dropped_app_whose_folder_was_deleted_is_not_installed(self):
        self.drop("noteforge-2.1.tar.gz")
        (self.home / "Applications/noteforge").rename(self.home / "Trash-noteforge")
        code, document = self.cli([], "run", "noteforge")
        self.assertEqual((code, document["state"], document["message_key"]),
                         (1, "failed", "not_installed"), document)
        self.assertEqual(self.runner.spawned, [], "a launcher with no program was started")

    def test_a_dropped_app_whose_program_was_deleted_is_not_installed(self):
        record = self.drop("noteforge-2.1.tar.gz")
        Path(record["exec"]).unlink()
        code, document = self.cli([], "run", "noteforge")
        self.assertEqual((code, document["message_key"]), (1, "not_installed"), document)
        self.assertEqual(self.runner.spawned, [])

    def test_a_catalogue_app_drop_install_answers_the_same(self):
        apps = [self.appdrop_recipe()]
        self.assertEqual(self.controller(apps).install(["noteforge"])[1]["state"], "success")
        code, document = self.cli(apps, "run", "noteforge")
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.runner.spawned.clear()
        shutil.rmtree(self.home / "Applications/noteforge")
        code, document = self.cli(apps, "run", "noteforge")
        self.assertEqual((code, document["message_key"]), (1, "not_installed"), document)
        self.assertEqual(self.runner.spawned, [])


class CommandLineTools(Backend):
    def test_a_tool_that_is_not_installed_is_said_to_be_not_installed(self):
        code, document = self.cli([self.npm()], "run", "codex")
        self.assertEqual((code, document["message_key"]), (2, "not_installed"), document)

    def test_an_installed_tool_has_no_window_and_is_called_a_command_line_tool(self):
        tool = self.home / ".local/bin/codex"
        tool.parent.mkdir(parents=True)
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)
        code, document = self.cli([self.npm()], "run", "codex")
        self.assertEqual((code, document["message_key"]), (2, "unsupported_kind"), document)
        self.assertIn("command-line tool", document["message"])
        self.assertEqual(self.runner.spawned, [])


class InterruptedDownloads(Backend):
    """A reboot or a logout mid-download skips every cleanup handler: the next job sweeps."""

    def leftovers(self) -> list[Path]:
        mine = MODULE.downloads_dir()
        vendor = self.cache / "downloads"              # moos_vendor_rpm's own downloads_dir()
        work = vendor / "vendor-chatgpt-k2x9q1"
        work.mkdir(parents=True)
        (work / ".payload-abc.cpio").write_bytes(b"0" * 64)
        (work / ".chatgpt-26.1-1.x86_64.rpm.part").write_bytes(b"0" * 64)
        mine.mkdir(parents=True, exist_ok=True)
        partial = mine / ".lmstudio.q1w2e3r4.part"
        partial.write_bytes(b"0" * 64)
        return [work, partial]

    def test_the_next_job_sweeps_what_an_interrupted_one_left(self):
        left = self.leftovers()
        keep = MODULE.downloads_dir() / "README.txt"   # not a name any job writes
        keep.write_text("not the Store's\n")
        code, document = self.controller([]).update()
        self.assertEqual(document["state"], "success", document)
        self.assertEqual([path for path in left if path.exists()], [])
        self.assertTrue(keep.exists())

    def test_with_the_cache_outside_home_both_folders_are_swept(self):
        # downloads_dir() stays inside HOME; moos_vendor_rpm keeps its work folders under the
        # cache directory itself.
        os.environ["XDG_CACHE_HOME"] = str(self.base / "cache")
        mine, vendor = MODULE.downloads_dir(), self.base / "cache/moos-store/downloads"
        self.assertNotEqual(mine, vendor)
        mine.mkdir(parents=True)
        (mine / ".noteforge.a1b2c3.part").write_bytes(b"0")
        (vendor / "vendor-chatgpt-z9y8x7").mkdir(parents=True)
        controller = MODULE.Controller(MODULE.JobStore(self.base / "cache/moos-store"),
                                       adapter_factory=lambda: self.adapter, runner=self.runner,
                                       catalog_path=self.catalog([]))
        self.assertEqual(controller.update()[1]["state"], "success")
        self.assertEqual(list(mine.iterdir()) + list(vendor.iterdir()), [])

    def test_an_open_beside_another_job_sweeps_nothing(self):
        apps = [self.webapp("whatsapp")]
        self.controller(apps).install(["whatsapp"])     # a job: sweeps an empty folder
        left = self.leftovers()
        self.hold_lock()                                # that job may be writing them right now
        code, document = self.cli(apps, "run", "whatsapp")
        self.assertEqual(document["state"], "success", document)
        self.assertEqual([path for path in left if not path.exists()], [])

    def test_a_linked_downloads_folder_is_never_followed(self):
        elsewhere = self.base / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / ".kept.part").write_bytes(b"0")
        (elsewhere / "vendor-kept-1").mkdir()
        target = MODULE.downloads_dir()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(elsewhere, target_is_directory=True)
        self.controller([]).update()
        self.assertTrue((elsewhere / ".kept.part").exists())
        self.assertTrue((elsewhere / "vendor-kept-1").is_dir())


# ── moos-control and moos-open against the real backend ─────────────────────────────────────────
# The backend runs for real (its main(), its catalogue, its lock and job.json); only what it would
# START is replaced, by a runner that writes each argv down. Android support is a status file.
REAL_BACKEND = r'''#!/usr/bin/env python3
import importlib.machinery, importlib.util, json, os, sys
loader = importlib.machinery.SourceFileLoader("moos_storectl_real", os.environ["MOOS_TEST_STORECTL"])
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = module
loader.exec_module(module)
SESSION = os.environ["MOOS_TEST_SESSION"]


def note(kind, argv):
    with open(os.environ["MOOS_TEST_STARTED"], "a", encoding="utf-8") as log:
        log.write(json.dumps([kind, list(argv)]) + "\n")


class Runner(module.CommandRunner):
    def spawn(self, argv):
        note("spawn", argv)
        if list(argv[1:]) == ["session", "start"]:
            with open(SESSION, "w", encoding="utf-8") as status:
                status.write("Session:\tRUNNING\n")

    def gpu_guard(self):
        pass

    def capture(self, argv, timeout=30):
        with open(SESSION, encoding="utf-8") as status:
            return module.CommandResult(0, "", False, status.read())

    def run_cancellable(self, argv, should_cancel):
        note("run", argv)
        return module.CommandResult(0)


class Adapter:
    def is_user_installed(self, app_id):
        return False

    def is_system_installed(self, app_id):
        return False


sys.exit(module.main([*sys.argv[1:], "--catalog", os.environ["MOOS_TEST_CATALOG"]],
                     runner=Runner(), adapter_factory=Adapter))
'''

RECORDER = r'''#!/bin/sh
line="${0##*/}"
for arg in "$@"; do line="$line$(printf '\t%s' "$arg")"; done
printf '%s\n' "$line" >> "$MOOS_TEST_CALLS"
'''


class RoutesWithTheRealBackend(Backend):
    def setUp(self):
        super().setUp()
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.calls = self.base / "calls.log"
        self.started = self.base / "started.log"
        self.session = self.base / "android-session"
        self.session.write_text(STOPPED, encoding="utf-8")
        backend = self.bin / "moos-storectl"
        backend.write_text(REAL_BACKEND, encoding="utf-8")
        backend.chmod(0o755)
        # flatpak knows no such app; every other program a route could start is a recorder.
        for name, body in (("flatpak", 'case "$1" in info) exit 1;; esac\n'), ("gtk-launch", ""),
                           ("notify-send", ""), ("kdialog", "exit 1\n"), ("logger", ""),
                           ("moos-gpu-headroom", ""), ("waydroid", "")):
            stub = self.bin / name
            stub.write_text(RECORDER + body, encoding="utf-8")
            stub.chmod(0o755)
        self.apps = [self.webapp("whatsapp"), self.android(), self.npm()]
        self.catalog_path = self.catalog(self.apps)
        self.controller(self.apps).install(["whatsapp"])

    def env(self) -> dict[str, str]:
        return {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.home), "LANG": "C.UTF-8",
                "XDG_CACHE_HOME": os.environ["XDG_CACHE_HOME"],
                "XDG_DATA_HOME": os.environ["XDG_DATA_HOME"],
                "XDG_STATE_HOME": os.environ["XDG_STATE_HOME"],
                "XDG_CONFIG_HOME": os.environ["XDG_CONFIG_HOME"],
                "XDG_DATA_DIRS": os.environ["XDG_DATA_DIRS"],
                "XDG_RUNTIME_DIR": os.environ["XDG_RUNTIME_DIR"],
                "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent",
                # A name for the session check only: nothing here draws a window.
                "WAYLAND_DISPLAY": "wayland-moos-test",
                "MOOS_TEST_STORECTL": str(SCRIPT), "MOOS_TEST_CATALOG": str(self.catalog_path),
                "MOOS_TEST_SESSION": str(self.session), "MOOS_TEST_STARTED": str(self.started),
                "MOOS_TEST_CALLS": str(self.calls)}

    def control(self, *argv):
        return subprocess.run([sys.executable, str(CONTROL), *argv], env=self.env(),
                              capture_output=True, text=True, timeout=120)

    def route(self, url):
        done = subprocess.run(["bash", str(OPEN), url], env=self.env(), capture_output=True,
                              text=True, timeout=120)
        return done, self.notices()

    def notices(self) -> list[str]:
        if not self.calls.exists():
            return []
        lines = [line.split("\t") for line in self.calls.read_text(encoding="utf-8").splitlines()]
        return [line[-1] for line in lines if line[0] == "notify-send"]

    def starts(self) -> list[list]:
        if not self.started.exists():
            return []
        return [json.loads(line) for line in self.started.read_text(encoding="utf-8").splitlines()]

    def test_opening_while_the_scheduled_updater_holds_the_lock(self):
        self.hold_lock()
        done = self.control("open", "whatsapp")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("not installed", done.stdout + done.stderr)
        self.assertIn(["spawn", [MODULE.WEBAPP_RUNTIME, "whatsapp"]], self.starts())
        self.started.unlink()
        _done, notices = self.route("moos://apps/run/whatsapp")
        self.assertEqual(notices, [], "an app that opened was announced as a failure")
        self.assertIn(["spawn", [MODULE.WEBAPP_RUNTIME, "whatsapp"]], self.starts())

    def test_each_answer_is_said_as_what_it_is(self):
        self.hold_lock()
        done = self.control("open", "gmail")                    # no such app, by any kind
        self.assertEqual(done.returncode, 69)
        self.assertIn("app is not installed", done.stderr)
        done = self.control("open", "codex")                    # a command-line tool, not installed
        self.assertIn("app is not installed", done.stderr)
        tool = self.home / ".local/bin/codex"
        tool.parent.mkdir(parents=True)
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)
        done = self.control("open", "codex")
        self.assertEqual(done.returncode, 69)
        self.assertIn("command-line tools run in a terminal", done.stderr)
        self.assertNotIn("not installed", done.stderr)
        _done, notices = self.route("moos://apps/run/codex")
        self.assertEqual(len(notices), 1, notices)
        self.assertIn("command-line tools run in a terminal", notices[0])
        # Android support is not running and the updater holds the lock: starting it beside the
        # updater is not ours to do, so the person's own request hears that Mo Store is busy.
        done = self.control("open", "org.example.notes")
        self.assertEqual(done.returncode, 69)
        self.assertIn("Mo Store is busy with another operation — try again shortly", done.stderr)
        self.assertIn("متجر MoOS مشغول بعملية أخرى — حاول بعد قليل", done.stderr)
        self.assertNotIn("not installed", done.stderr)

    def test_a_link_never_starts_android_and_the_persons_request_does(self):
        _done, notices = self.route("moos://apps/run/org.example.notes")
        self.assertEqual(len(notices), 1, notices)
        self.assertIn("Android app support is not running", notices[0])
        self.assertNotIn(["spawn", [MODULE.WAYDROID, "session", "start"]], self.starts())
        self.assertEqual([start for start in self.starts() if start[0] == "run"], [])
        done = self.control("open", "org.example.notes")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(["spawn", [MODULE.WAYDROID, "session", "start"]], self.starts())
        self.assertIn(["run", [MODULE.WAYDROID, "app", "launch", "org.example.notes"]], self.starts())


if __name__ == "__main__":
    unittest.main(verbosity=2)
