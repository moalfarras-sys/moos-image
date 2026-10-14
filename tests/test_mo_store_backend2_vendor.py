#!/usr/bin/env python3
"""Mo Store's `vendor-rpm` kind, end to end through moos-storectl: a publisher's own signed Linux
package (the official ChatGPT app is the first), run from the person's home.

usr/lib/moos/moos_vendor_rpm.py does the careful work and has its own gate
(tests/test_moos_vendor_rpm.py). This one holds the Store's half of the contract
(docs/MO_STORE.md, kind `vendor`):

  Install       one job: resolving -> downloading -> verifying the publisher's signature ->
                unpacking (indeterminate while the payload is written out) -> integrating, each
                with a message key the window owns; only what MoOS writes is written; an intact,
                current install is not downloaded again;
  Refusals      every code the module can raise reaches the window as a key with Arabic and
                English words, and the real refusals (signature, network, digest, free space,
                a folder that is not MoOS's, cancel) leave nothing behind;
  Open          `gtk-launch org.moos.vendor.<id>.desktop`, only while the install is whole;
  Remove        what MoOS wrote, never the app's own settings, said honestly with --delete-data;
  Updates       check-updates asks the publisher (offline or slow: no row, no failure), update
                <id> swaps atomically and keeps the version that worked, update-all includes it;
  Permissions   not sandboxed: sandboxed=false, note_key full_access;
  Orphans       an app the catalogue stopped offering stays openable and removable by its id.

Nothing here reaches the network, the image's rpm tools, a display or the person's real home: the
repository is served from bytes, the tools answer from recordings, HOME is private.
"""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
# The vendor module's own fixtures: a repository served from bytes, newc payloads, the recorded
# rpm tool outputs. Importing them also lists their test repository as a reviewed one.
import test_moos_vendor_rpm as rpmfix  # noqa: E402

vendor = rpmfix.vendor
SCRIPT = ROOT / "system_files/usr/bin/moos-storectl"
LOADER = importlib.machinery.SourceFileLoader("moos_storectl_backend2_vendor", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)
QML = ROOT / "system_files/usr/share/moos/apps/store/main.qml"
PHRASES = dict(
    (match.group(1), (match.group(2), match.group(3)))
    for match in re.finditer(r'"([a-z_]+)":\s*\["([^"]+)",\s*"([^"]+)"\]',
                             re.search(r"readonly property var jobPhrases: \(\{(.*?)\n    \}\)",
                                       QML.read_text(encoding="utf-8"), re.S).group(1)))

APP = "app"
LAUNCHER = f"org.moos.vendor.{APP}.desktop"


def recipe(**install_changes) -> dict:
    install = {"kind": "vendor-rpm", **rpmfix.ENTRY, "risk": "downloaded-executable",
               "requires_review": True, "external": True}
    install.update(install_changes)
    return {"id": APP, "source": "moos", "en": "App Studio", "ar": "استوديو التطبيق", "cat": "ai",
            "arch": ["x86_64", "aarch64"], "install": install}


class Runner:
    """Records what would be started; starts nothing."""

    def __init__(self):
        self.spawned: list[list[str]] = []
        self.guard_calls = 0

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def gpu_guard(self):
        self.guard_calls += 1

    def capture(self, argv, timeout=30):
        return MODULE.CommandResult(1, "not in this test")

    def run_cancellable(self, argv, should_cancel):
        raise AssertionError(f"the vendor kind runs no command of its own: {argv}")


class NoFlatpaks:
    def update_candidates(self):
        return []

    def update_refs(self):
        return []

    def is_user_installed(self, app_id):
        return False

    def is_system_installed(self, app_id):
        return False


class RecordingStore(MODULE.JobStore):
    def __init__(self, directory: Path):
        super().__init__(directory)
        self.history: list[dict] = []

    def write(self, document):
        self.history.append(json.loads(json.dumps(document)))
        super().write(document)


class Vendor(unittest.TestCase):
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
        for name in ("XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CONFIG_HOME",
                     "DISPLAY", "WAYLAND_DISPLAY"):
            os.environ.pop(name, None)
        os.environ.update(HOME=str(self.home), XDG_RUNTIME_DIR=str(self.base / "run"),
                          XDG_DATA_DIRS=str(self.base / "system-share"),
                          DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent",
                          # No menu tools: the module's menu refresh is a no-op here.
                          PATH=str(self.base / "no-tools"))
        (self.base / "run").mkdir(mode=0o700)
        for target, name, value in ((vendor, "machine_arch", lambda: "x86_64"),
                                    (MODULE, "running_arch", lambda: "x86_64")):
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        saved_margin = vendor.SPACE_MARGIN
        self.addCleanup(setattr, vendor, "SPACE_MARGIN", saved_margin)
        self.opener = rpmfix.Opener({})
        self.tools = rpmfix.Tools()
        self.runner = Runner()
        self.payload = b""
        self.during_unpack: dict | None = None
        self.proc_sys = self.base / "proc-sys"
        (self.proc_sys / "user").mkdir(parents=True)
        (self.proc_sys / "user/max_user_namespaces").write_text("62503\n")
        self.store = RecordingStore(self.home / ".cache/moos-store")

    # ── fixtures ────────────────────────────────────────────────────────────────────────────
    def serve(self, version: str, marker: bytes = b"", *, tools: rpmfix.Tools | None = None) -> None:
        content = b"rpm:" + version.encode() + os.urandom(64)
        packages = [rpmfix.package("app", "1.0"), rpmfix.package("app", version, content=content)]
        routes = rpmfix.repo_routes(packages)
        routes[f"{rpmfix.BASE}/app-{version}-1.x86_64.rpm"] = content
        self.opener.routes = routes
        self.payload = rpmfix.app_payload(marker or version.encode())
        self.tools = tools or rpmfix.Tools(header=("app", "0", version, "1", "x86_64", "cpio"))

    def convert(self, rpm: Path, cpio: Path, cancelled, limit: int) -> None:
        # What the window sees while the payload is being written out.
        self.during_unpack = self.job()
        cpio.write_bytes(self.payload)

    def controller(self, apps: list | None = None) -> MODULE.Controller:
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": [recipe()] if apps is None else apps}), encoding="utf-8")
        controller = MODULE.Controller(self.store, adapter_factory=NoFlatpaks, runner=self.runner,
                                       catalog_path=path, opener=self.opener)
        controller.vendor_options = {"run": self.tools, "convert": self.convert,
                                     "proc_sys": self.proc_sys}
        return controller

    def job(self) -> dict:
        return json.loads((self.home / ".cache/moos-store/job.json").read_text(encoding="utf-8"))

    def install(self, version: str = "2.0", **serve) -> dict:
        self.serve(version, **serve)
        code, document = self.controller().install([APP])
        return document

    def app_dir(self) -> Path:
        return self.home / "Applications" / APP

    def launcher(self) -> Path:
        return self.home / ".local/share/applications" / LAUNCHER

    def record(self) -> Path:
        return self.home / ".local/share/moos/vendor" / f"{APP}.json"

    def downloads(self) -> list[str]:
        folder = self.home / ".cache/moos-store/downloads"
        return sorted(path.name for path in folder.iterdir()) if folder.is_dir() else []

    def assertNothingInstalled(self) -> None:
        self.assertFalse(self.app_dir().exists())
        self.assertFalse(self.launcher().exists())
        self.assertFalse(self.record().exists())
        self.assertEqual(self.downloads(), [], "a download or work folder was left behind")
        self.assertEqual(sorted(path.name for path in (self.home / "Applications").iterdir())
                         if (self.home / "Applications").is_dir() else [], [])

    def item(self, document: dict) -> dict:
        return document["items"][0]


class Install(Vendor):
    def test_one_job_says_each_step_and_writes_only_what_moos_owns(self):
        document = self.install("2.0")
        self.assertEqual((document["state"], self.item(document)["message_key"]), ("success", "installed"),
                         document)
        self.assertIn("reviewed risk: downloaded-executable", self.item(document)["message"])
        keys = [entry.get("message_key") for entry in self.store.history]
        order = ["vendor_resolving", "vendor_downloading", "vendor_verifying", "extracting_file",
                 "integrating_app"]
        positions = [keys.index(key) for key in order]
        self.assertEqual(positions, sorted(positions), f"the steps arrived out of order: {keys}")
        for key in order + ["installed", "all_ready"]:
            self.assertIn(key, PHRASES, f"{key} has no words in the window")
        # Unpacking is indeterminate while the payload is written out: nothing measures it.
        self.assertEqual((self.during_unpack["message_key"], self.during_unpack["progress"]),
                         ("extracting_file", None))
        downloading = [entry["progress"] for entry in self.store.history
                       if entry.get("message_key") == "vendor_downloading"]
        self.assertTrue(downloading and all(isinstance(value, int) for value in downloading))
        # What MoOS writes, and nothing else.
        self.assertTrue((self.app_dir() / "App").read_bytes().endswith(b"2.0"))
        self.assertEqual((self.app_dir() / ".moos-vendor").read_text(), f"{APP}\n")
        lines = self.launcher().read_text(encoding="utf-8").splitlines()
        self.assertIn(f"X-MoOS-Vendor={APP}", lines)
        self.assertIn(f'Exec="{self.app_dir()}/App" %U', lines)
        record = json.loads(self.record().read_text(encoding="utf-8"))
        self.assertEqual((record["version"], record["release"], record["kind"]), ("2.0", "1", "vendor-rpm"))
        self.assertEqual(self.downloads(), [])
        self.assertEqual(sorted(path.name for path in (self.home / "Applications").iterdir()), [APP])
        self.assertTrue(vendor.intact(APP))

    def test_an_intact_current_install_is_not_downloaded_again(self):
        self.install("2.0")
        self.opener.requests.clear()
        code, document = self.controller().install([APP])
        self.assertEqual((document["state"], self.item(document)["message_key"]),
                         ("success", "already_installed_user"), document)
        self.assertFalse([url for url in self.opener.requests if url.endswith(".rpm")],
                         "the same build was downloaded again")
        # Incomplete (its launcher is gone): Install repairs it instead of saying "installed".
        self.launcher().unlink()
        code, document = self.controller().install([APP])
        self.assertEqual(self.item(document)["message_key"], "installed", document)
        self.assertTrue(vendor.intact(APP))

    def test_the_review_metadata_and_its_honest_label_are_required(self):
        self.serve("2.0")
        unreviewed = recipe()
        unreviewed["install"].pop("requires_review")
        # A program downloaded from its publisher and run unsandboxed is not a "web-app".
        for broken in (unreviewed, recipe(risk="web-app")):
            code, document = self.controller([broken]).install([APP])
            self.assertEqual(document["state"], "failed")
            self.assertIn("review metadata", self.item(document)["message"])
        self.assertEqual(self.opener.requests, [], "the publisher was asked before the review check")
        self.assertNothingInstalled()

    def test_a_stalled_publisher_keeps_the_job_alive_and_cancellable(self):
        self.serve("2.0")
        release = threading.Event()
        self.addCleanup(release.set)
        polls = []

        class Stalled:
            requests: list = []

            def open(self, request, timeout=None):
                release.wait(30)
                raise urllib.error.URLError("stalled")

        self.opener = Stalled()
        controller = self.controller()
        heartbeat = MODULE.Job.heartbeat

        def counted(job):
            polls.append(time.monotonic())
            if len(polls) == 4:
                controller.store.request_cancel(job.job_id)
            return heartbeat(job)

        started = time.monotonic()
        with mock.patch.object(MODULE.Job, "heartbeat", counted):
            code, document = controller.install([APP])
        self.assertEqual((code, document["state"]), (130, "cancelled"), document)
        self.assertLess(time.monotonic() - started, 10, "cancel waited for the stalled publisher")
        self.assertGreaterEqual(len(polls), 4, "nothing kept the job's heartbeat while it waited")
        self.assertNothingInstalled()


class Refusals(Vendor):
    def failed_key(self, document: dict) -> str | None:
        self.assertEqual(document["state"], "failed", document)
        return self.item(document)["message_key"]

    def test_every_code_the_module_raises_has_words_in_both_languages(self):
        for code in sorted(vendor.ERROR_CODES):
            with self.subTest(code=code):
                error = MODULE.Controller._vendor_failure(vendor.VendorError(code, "a detail for the log"))
                if code == "cancelled":
                    self.assertIsInstance(error, MODULE.CancelledError)
                    continue
                self.assertIsInstance(error, MODULE.StoreError)
                self.assertIn(error.message_key, PHRASES)
                arabic, english = PHRASES[error.message_key]
                self.assertRegex(arabic, "[؀-ۿ]")
                self.assertIn(code, str(error), "the log loses which refusal it was")
                for word in ("rpm", "dnf", "flatpak", "wine"):
                    self.assertNotIn(word, (arabic + english).lower())

    def test_an_untrusted_signature_installs_nothing(self):
        document = self.install("2.0", tools=rpmfix.Tools(
            checksig=rpmfix.CHECKSIG_NOKEY, status=1, header=("app", "0", "2.0", "1", "x86_64", "cpio")))
        self.assertEqual(self.failed_key(document), "vendor_signature_failed")
        self.assertNothingInstalled()

    def test_a_key_the_image_does_not_hold(self):
        document = self.install("2.0", tools=rpmfix.Tools(
            keys=rpmfix.KEYRING_WITHOUT, header=("app", "0", "2.0", "1", "x86_64", "cpio")))
        self.assertEqual(self.failed_key(document), "vendor_key_missing")
        self.assertNothingInstalled()

    def test_no_network_and_no_such_package(self):
        self.serve("2.0")
        self.opener.routes = {}
        code, document = self.controller().install([APP])
        self.assertEqual(self.failed_key(document), "vendor_network")
        self.serve("2.0")
        code, document = self.controller([recipe(package="other")]).install([APP])
        self.assertEqual(self.failed_key(document), "vendor_package_not_found")
        self.assertNothingInstalled()

    def test_a_download_that_is_not_what_the_publisher_announced(self):
        self.serve("2.0")
        url = f"{rpmfix.BASE}/app-2.0-1.x86_64.rpm"
        self.opener.routes[url] = b"X" * len(self.opener.routes[url])
        code, document = self.controller().install([APP])
        self.assertEqual(self.failed_key(document), "vendor_download_mismatch")
        self.assertNothingInstalled()

    def test_too_little_free_space_is_refused_before_downloading(self):
        self.serve("2.0")
        vendor.SPACE_MARGIN = 2 ** 62
        code, document = self.controller().install([APP])
        self.assertEqual(self.failed_key(document), "vendor_no_space")
        self.assertIn("three times", PHRASES["vendor_no_space"][1])
        self.assertFalse([url for url in self.opener.requests if url.endswith(".rpm")])
        self.assertNothingInstalled()

    def test_a_folder_moos_did_not_write_is_left_alone(self):
        dropped = self.app_dir() / "bin"                 # an App Drop app with the same name
        dropped.mkdir(parents=True)
        (dropped / "run").write_text("#!/bin/sh\n")
        self.serve("2.0")
        code, document = self.controller().install([APP])
        self.assertEqual(self.failed_key(document), "vendor_name_taken")
        self.assertEqual((dropped / "run").read_text(), "#!/bin/sh\n")
        self.assertFalse([url for url in self.opener.requests if url.endswith(".rpm")])
        self.assertFalse(self.launcher().exists())

    def test_a_program_that_cannot_start_its_sandbox_is_not_installed(self):
        (self.proc_sys / "user/max_user_namespaces").write_text("0\n")
        document = self.install("2.0")
        self.assertEqual(self.failed_key(document), "vendor_sandbox_unavailable")
        self.assertNothingInstalled()

    def test_cancel_while_unpacking_leaves_nothing(self):
        self.serve("2.0")
        controller = self.controller()
        payload = self.payload

        def convert(rpm, cpio, cancelled, limit):
            controller.store.request_cancel(self.job()["job_id"])
            cpio.write_bytes(payload)

        controller.vendor_options["convert"] = convert
        code, document = controller.install([APP])
        self.assertEqual((code, document["state"], document["message_key"]), (130, "cancelled", "cancelled"))
        self.assertNothingInstalled()

    def test_an_unsupported_processor(self):
        self.serve("2.0")

        def refuse():
            raise vendor.VendorError("unsupported_arch", "riscv64")

        with mock.patch.object(vendor, "machine_arch", refuse):
            code, document = self.controller().install([APP])
        self.assertEqual(self.failed_key(document), "unsupported_arch")
        self.assertEqual(self.opener.requests, [])
        # A catalogue entry for other processors is not offered here at all.
        code, document = self.controller([dict(recipe(), arch=["aarch64"])]).install([APP])
        self.assertEqual(document["state"], "failed")
        self.assertEqual(self.opener.requests, [])


class OpenAndRemove(Vendor):
    def test_open_starts_moos_own_launcher_only_while_the_install_is_whole(self):
        self.install("2.0")
        code, document = self.controller().run(APP)
        self.assertEqual((code, document["state"]), (0, "success"), document)
        self.assertEqual(self.runner.spawned, [[MODULE.GTK_LAUNCH, LAUNCHER]])
        self.assertEqual(self.runner.guard_calls, 1)
        self.launcher().unlink()
        code, document = self.controller().run(APP)
        self.assertEqual((document["state"], self.item(document)["message_key"]), ("failed", "not_installed"))
        self.assertEqual(len(self.runner.spawned), 1, "a launcher that is gone was started")

    def test_remove_takes_what_moos_wrote_and_says_the_app_keeps_its_settings(self):
        settings = self.home / ".config/App"
        settings.mkdir(parents=True)
        (settings / "sign-in.json").write_text("{}")
        self.install("2.0")
        code, document = self.controller().remove(APP, delete_data=True)
        self.assertEqual((document["state"], self.item(document)["message_key"]),
                         ("success", "removed_data_untracked"), document)
        self.assertIn("kept", PHRASES["removed_data_untracked"][1])
        self.assertFalse(self.app_dir().exists())
        self.assertFalse(self.launcher().exists())
        self.assertFalse(self.record().exists())
        self.assertEqual((settings / "sign-in.json").read_text(), "{}", "the app's own data was deleted")
        code, document = self.controller().remove(APP)
        self.assertEqual(self.item(document)["message_key"], "not_installed")
        self.install("2.0")
        code, document = self.controller().remove(APP)
        self.assertEqual(self.item(document)["message_key"], "removed")

    def test_permissions_say_it_is_not_sandboxed(self):
        self.install("2.0")
        for controller in (self.controller(), self.controller([])):     # listed, then an orphan
            code, document = controller.permissions(APP)
            self.assertEqual((document["sandboxed"], document["rows"], document["note_key"]),
                             (False, [], "full_access"))

    def test_an_app_the_catalogue_stopped_offering_stays_openable_and_removable(self):
        self.install("2.0")
        orphaned = self.controller([])
        code, document = orphaned.run(APP)
        self.assertEqual(document["state"], "success", document)
        self.assertEqual(self.runner.spawned[-1], [MODULE.GTK_LAUNCH, LAUNCHER])
        with self.assertRaises(MODULE.StoreError) as refused:
            orphaned.update(APP)
        self.assertEqual(refused.exception.message_key, "unsupported_kind")
        code, document = orphaned.remove(APP)
        self.assertEqual(self.item(document)["message_key"], "removed", document)
        self.assertNothingInstalled()


class Updates(Vendor):
    def check(self) -> dict:
        return self.controller().check_updates()[1]

    def test_check_updates_asks_the_publisher(self):
        self.install("2.0")
        self.serve("2.1")
        document = self.check()
        self.assertEqual(document["state"], "success")
        self.assertEqual(document["items"], [{"id": APP, "kind": "pin", "name": "App Studio",
                                              "version": "2.1-1", "installed_version": "2.0-1"}])
        self.serve("2.0")
        self.assertEqual(self.check()["items"], [])

    def test_offline_or_slow_is_no_row_and_no_failure(self):
        self.install("2.0")

        class Offline:
            requests: list = []

            def open(self, request, timeout=None):
                raise urllib.error.URLError("Temporary failure in name resolution")

        self.opener = Offline()
        document = self.check()
        self.assertEqual((document["state"], document["items"]), ("success", []))
        release = threading.Event()
        self.addCleanup(release.set)

        class Stalled:
            def open(self, request, timeout=None):
                release.wait(20)
                raise urllib.error.URLError("stalled")

        self.opener = Stalled()
        with mock.patch.object(MODULE, "VENDOR_CHECK_SECONDS", 0.3):
            started = time.monotonic()
            document = self.check()
            took = time.monotonic() - started
        self.assertEqual((document["state"], document["items"]), ("success", []))
        self.assertLess(took, 5, "an update check waited on a stalled publisher")

    def test_update_swaps_atomically_and_keeps_the_version_that_worked(self):
        self.install("2.0")
        self.serve("2.1", tools=rpmfix.Tools(checksig=rpmfix.CHECKSIG_NOKEY, status=1,
                                             header=("app", "0", "2.1", "1", "x86_64", "cpio")))
        code, document = self.controller().update(APP)
        self.assertEqual((document["state"], self.item(document)["message_key"]),
                         ("failed", "vendor_signature_failed"), document)
        self.assertTrue((self.app_dir() / "App").read_bytes().endswith(b"2.0"))
        self.assertEqual(json.loads(self.record().read_text())["version"], "2.0")
        self.assertTrue(vendor.intact(APP))
        self.serve("2.1")
        code, document = self.controller().update(APP)
        self.assertEqual((document["state"], self.item(document)["message_key"]), ("success", "updated"),
                         document)
        self.assertTrue((self.app_dir() / "App").read_bytes().endswith(b"2.1"))
        self.assertEqual(sorted(path.name for path in (self.home / "Applications").iterdir()), [APP])
        code, document = self.controller().update(APP)
        self.assertEqual(self.item(document)["message_key"], "app_up_to_date")

    def test_update_all_includes_a_newer_build(self):
        self.install("2.0")
        self.serve("2.1")
        code, document = self.controller().update()
        self.assertEqual(document["state"], "success", document)
        self.assertEqual([(item["id"], item["message_key"]) for item in document["items"]],
                         [(APP, "updated")])
        self.assertTrue((self.app_dir() / "App").read_bytes().endswith(b"2.1"))

    def test_update_of_an_app_that_is_not_installed(self):
        self.serve("2.0")
        code, document = self.controller().update(APP)
        self.assertEqual((document["state"], self.item(document)["message_key"]), ("failed", "not_installed"))


class Language(Vendor):
    def test_each_module_stage_has_its_own_words(self):
        job = MODULE.Job(self.store, "install", [APP])
        progress = self.controller()._vendor_progress(job, APP)
        seen = {}
        for stage in vendor.STAGES:
            progress(stage, None)
            seen[stage] = job.document["message_key"]
            self.assertIn(seen[stage], PHRASES, stage)
        self.assertEqual(len(set(seen.values())), len(vendor.STAGES), seen)

    def test_the_command_line_publishes_a_refusal_the_window_can_read(self):
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": [recipe()]}), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            code = MODULE.main(["--catalog", str(path), "run", APP], store=self.store,
                               adapter_factory=NoFlatpaks, runner=self.runner)
        self.assertEqual(code, 1)
        document = json.loads(printed.getvalue())
        self.assertEqual((document["state"], document["message_key"]), ("failed", "not_installed"))
        self.assertEqual(self.job()["job_id"], document["job_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
