#!/usr/bin/env python3
"""Independent safety and behavior tests for /usr/bin/moos-storectl."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-storectl"
LOADER = importlib.machinery.SourceFileLoader("moos_storectl_tested", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)


class FakeRunner:
    def __init__(self, result=None):
        self.spawned: list[list[str]] = []
        self.commands: list[list[str]] = []
        self.guard_calls = 0
        self.result = result or MODULE.CommandResult(0)

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def gpu_guard(self):
        self.guard_calls += 1

    def run_cancellable(self, argv, should_cancel):
        self.commands.append(list(argv))
        if should_cancel():
            return MODULE.CommandResult(143, "cancelled", True)
        return self.result


class FakeAdapter:
    def __init__(
        self,
        *,
        user=(),
        system=(),
        fail=(),
        updates=(),
    ):
        self.user = set(user)
        self.system = set(system)
        self.fail = set(fail)
        self.updates = list(updates)
        self.installs: list[list[str]] = []
        self.removes: list[str] = []
        self.launches: list[str] = []
        self.refreshes = 0

    def is_user_installed(self, app_id):
        return app_id in self.user

    def is_system_installed(self, app_id):
        return app_id in self.system

    def install_many(self, ids, events, should_cancel):
        ids = list(ids)
        self.installs.append(ids)
        events.plan(len(ids))
        for index, app_id in enumerate(ids):
            if should_cancel():
                raise MODULE.CancelledError("cancelled")
            ref = f"app/{app_id}/x86_64/stable"
            events.started(ref, "Downloading")
            events.progress(ref, 50, "Downloading", int(index * 100 / len(ids) + 25))
            if app_id in self.fail:
                events.error(ref, "network failed")
            else:
                events.done(ref)

    def remove(self, app_id, events, should_cancel):
        self.removes.append(app_id)
        ref = f"app/{app_id}/x86_64/stable"
        events.plan(1)
        events.started(ref, "Removing")
        events.progress(ref, 70, "Removing", 70)
        events.done(ref)

    def update_refs(self):
        return list(self.updates)

    def update_many(self, refs, events, should_cancel):
        events.plan(len(refs))
        for name, ref in refs:
            events.started(ref, "Updating")
            events.progress(ref, 80, "Updating", 80)
            events.done(ref)

    def refresh_index(self, events, should_cancel):
        self.refreshes += 1
        events.plan(1)
        events.started("app/flathub/current/index", "Refreshing")
        events.progress("app/flathub/current/index", 64, "Refreshing", 64)
        events.done("app/flathub/current/index")

    def launch(self, app_id):
        self.launches.append(app_id)


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.old_home = os.environ.get("HOME")
        self.old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["HOME"] = str(self.base / "home")
        os.environ["XDG_CACHE_HOME"] = str(self.base / "cache")
        (self.base / "home").mkdir()
        self.addCleanup(self._restore_environment)

    def _restore_environment(self):
        if self.old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.old_home
        if self.old_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self.old_cache

    def store(self):
        return MODULE.JobStore(self.base / "cache/moos-store")

    def catalog(self, apps):
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        return path

    def controller(self, apps, adapter=None, runner=None):
        selected = adapter or FakeAdapter()
        return (
            MODULE.Controller(
                self.store(),
                adapter_factory=lambda: selected,
                runner=runner or FakeRunner(),
                catalog_path=self.catalog(apps),
            ),
            selected,
        )

    def assert_schema(self, document):
        self.assertEqual(
            set(document),
            {
                "schema",
                "job_id",
                "action",
                "state",
                "progress",
                "current_id",
                "message",
                "items",
                "started_at",
                "updated_at",
            },
        )
        self.assertEqual(document["schema"], 1)
        for item in document["items"]:
            self.assertEqual(set(item), {"id", "state", "progress", "message"})


class ValidationTests(StoreTestCase):
    def test_reverse_dns_validation_is_strict_and_compatible(self):
        valid = (
            "org.mozilla.firefox",
            "io.podman_desktop.PodmanDesktop",
            "com.jetbrains.IntelliJ-IDEA-Community",
            "org.telegram.desktop",
            "com.mattermost.Desktop",
            "com.VK.Messenger",
        )
        invalid = (
            "firefox",
            "org.firefox",
            "org..Firefox",
            "org.example.-App",
            "org.example.App/",
            "org.example.App//stable",
            "org.example.App;touch",
            "org.example." + "a" * 244,
        )
        for app_id in valid:
            self.assertTrue(MODULE.validate_flatpak_id(app_id), app_id)
        for app_id in invalid:
            self.assertFalse(MODULE.validate_flatpak_id(app_id), app_id)

    def test_batch_limit_is_enforced_before_an_adapter_exists(self):
        controller, adapter = self.controller([])
        with self.assertRaises(MODULE.StoreError):
            controller.install(["org.example.App"] * 65)
        self.assertEqual(adapter.installs, [])

    def test_subprocess_calls_never_enable_a_shell(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("shell" + "=True", source)

    def test_transaction_continues_only_for_nonfatal_operation_errors(self):
        self.assertFalse(
            MODULE.continue_after_transaction_error(
                details=0, nonfatal_flag=1, cancelled=False
            )
        )
        self.assertTrue(
            MODULE.continue_after_transaction_error(
                details=1, nonfatal_flag=1, cancelled=False
            )
        )
        self.assertFalse(
            MODULE.continue_after_transaction_error(
                details=1, nonfatal_flag=1, cancelled=True
            )
        )

    def test_fake_remote_named_flathub_is_never_trusted(self):
        class Remote:
            def __init__(self, name, url, verified):
                self.name, self.url, self.verified = name, url, verified

            def get_name(self):
                return self.name

            def get_url(self):
                return self.url

            def get_gpg_verify(self):
                return self.verified

            def get_disabled(self):
                return False

            def get_nodeps(self):
                return False

        class UserInstallation:
            def __init__(self):
                self.remotes = [
                    Remote("flathub", "https://attacker.invalid/repo/", True)
                ]
                self.added = []

            def list_remotes(self, _cancellable):
                return list(self.remotes)

            def add_remote(self, remote, _if_needed, _cancellable):
                self.remotes.append(remote)
                self.added.append(remote)
                return True

            def get_remote_by_name(self, name, _cancellable):
                return next(remote for remote in self.remotes if remote.name == name)

        class RemoteFactory:
            @staticmethod
            def new_from_file(name, _data):
                return Remote(name, MODULE.FLATHUB_REPO_BASE, True)

        class BytesFactory:
            @staticmethod
            def new(data):
                return data

        class FlatpakNamespace:
            Remote = RemoteFactory

        class GLibNamespace:
            Bytes = BytesFactory

        adapter = object.__new__(MODULE.FlatpakAdapter)
        adapter.user = UserInstallation()
        adapter.Flatpak = FlatpakNamespace
        adapter.GLib = GLibNamespace
        adapter._repo_data = lambda: b"trusted flatpakrepo"

        selected = adapter.ensure_flathub()
        self.assertEqual(selected, "moos-flathub")
        self.assertEqual([remote.name for remote in adapter.user.added], ["moos-flathub"])

    def test_libflatpak_install_is_queued_with_a_resolved_full_ref(self):
        class Ref:
            def __init__(self, branch):
                self.branch = branch

            def get_name(self):
                return "org.example.App"

            def get_kind(self):
                return 0

            def get_arch(self):
                return "x86_64"

            def get_branch(self):
                return self.branch

            def format_ref(self):
                return f"app/org.example.App/x86_64/{self.branch}"

        class User:
            def list_remote_refs_sync(self, remote, _cancellable):
                self.remote = remote
                return [Ref("beta"), Ref("stable")]

        class FlatpakNamespace:
            class RefKind:
                APP = 0

            @staticmethod
            def get_default_arch():
                return "x86_64"

        queued = []

        class Transaction:
            def add_install(self, remote, ref, subpaths):
                queued.append((remote, ref, subpaths))
                return True

        adapter = object.__new__(MODULE.FlatpakAdapter)
        adapter.user = User()
        adapter.Flatpak = FlatpakNamespace
        adapter.ensure_flathub = lambda: "flathub"
        adapter._transaction = (
            lambda configure, _events, _cancel: configure(Transaction())
        )
        adapter.install_many(["org.example.App"], object(), lambda: False)
        self.assertEqual(
            queued,
            [("flathub", "app/org.example.App/x86_64/stable", None)],
        )

    def test_libflatpak_remove_is_queued_with_the_installed_full_ref(self):
        class Installed:
            @staticmethod
            def format_ref():
                return "app/org.example.App/x86_64/stable"

        class User:
            @staticmethod
            def get_current_installed_app(_app_id, _cancellable):
                return Installed()

        queued = []

        class Transaction:
            @staticmethod
            def add_uninstall(ref):
                queued.append(ref)
                return True

        adapter = object.__new__(MODULE.FlatpakAdapter)
        adapter.user = User()
        adapter._transaction = (
            lambda configure, _events, _cancel: configure(Transaction())
        )
        adapter.remove("org.example.App", object(), lambda: False)
        self.assertEqual(queued, ["app/org.example.App/x86_64/stable"])


class StatusAndLockTests(StoreTestCase):
    def test_atomic_job_file_is_never_observed_as_partial_json(self):
        store = self.store()
        job = MODULE.Job(store, "install", ["org.example.App"])
        errors = []
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                try:
                    json.loads(store.path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    continue
                except Exception as error:  # pragma: no cover - failure payload
                    errors.append(error)
                    return

        thread = threading.Thread(target=reader)
        thread.start()
        for percent in range(101):
            job.update(
                state="running",
                progress=percent,
                current_id="org.example.App",
                message=f"{percent}%",
            )
        stop.set()
        thread.join()
        self.assertEqual(errors, [])
        self.assert_schema(store.read())
        leftovers = list(store.directory.glob(".job.json.*.tmp"))
        self.assertEqual(leftovers, [])

    def test_global_lock_is_nonblocking_and_does_not_clobber_job(self):
        store = self.store()
        first = MODULE.GlobalLock(store).acquire()
        self.addCleanup(first.release)
        MODULE.Job(store, "install", ["org.example.First"])
        before = store.path.read_bytes()
        with self.assertRaises(MODULE.BusyError):
            MODULE.GlobalLock(store).acquire()
        self.assertEqual(store.path.read_bytes(), before)

    def test_cancel_marker_is_scoped_to_job_id(self):
        store = self.store()
        store.request_cancel("abc")
        self.assertTrue(store.cancel_requested("abc"))
        self.assertFalse(store.cancel_requested("other"))


class InstallTests(StoreTestCase):
    def test_system_install_is_treated_as_installed_without_user_duplicate(self):
        adapter = FakeAdapter(system={"org.example.App"})
        controller, _ = self.controller([], adapter=adapter)
        code, result = controller.install(["org.example.App"])
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "success")
        self.assertEqual(result["items"][0]["state"], "skipped")
        self.assertIn("system-wide", result["items"][0]["message"])
        self.assertEqual(adapter.installs, [])

    def test_duplicate_ids_are_transacted_once_and_partial_is_honest(self):
        adapter = FakeAdapter(fail={"org.example.Bad"})
        controller, _ = self.controller([], adapter=adapter)
        code, result = controller.install(
            ["org.example.Good", "org.example.Bad", "org.example.Good"]
        )
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "partial")
        self.assertEqual(adapter.installs, [["org.example.Good", "org.example.Bad"]])
        self.assertEqual(
            [item["state"] for item in result["items"]], ["done", "failed"]
        )
        self.assert_schema(result)

    def test_npm_uses_catalog_allowlist_user_prefix_and_no_invented_progress(self):
        runner = FakeRunner()
        recipe = {
            "id": "codex",
            "source": "moos",
            "install": {
                "kind": "npm",
                "pkg": "@openai/codex",
                "bin": "codex",
                "requires_review": True,
                "risk": "runs-package-scripts",
            },
        }
        controller, _ = self.controller([recipe], runner=runner)
        code, result = controller.install(["codex"])
        self.assertEqual(code, 0)
        self.assertEqual(
            runner.commands,
            [
                [
                    "/usr/bin/npm",
                    "install",
                    "--global",
                    "--prefix",
                    str(self.base / "home/.local"),
                    "--no-audit",
                    "--no-fund",
                    "--",
                    "@openai/codex",
                ]
            ],
        )
        self.assertEqual(result["items"][0]["progress"], 100)
        self.assertIn("runs-package-scripts", result["items"][0]["message"])

    def test_web_opens_only_fixed_catalog_url_and_reports_opened(self):
        runner = FakeRunner()
        recipe = {
            "id": "cursor",
            "source": "moos",
            "install": {
                "kind": "web",
                "url": "https://www.cursor.com/downloads",
                "requires_review": True,
                "risk": "external-download",
                "external": True,
            },
        }
        controller, _ = self.controller([recipe], runner=runner)
        code, result = controller.install(["cursor"])
        self.assertEqual(code, 0)
        self.assertEqual(
            runner.spawned,
            [["/usr/bin/xdg-open", "https://www.cursor.com/downloads"]],
        )
        self.assertEqual(result["items"][0]["state"], "opened")
        self.assertIn("external-download", result["items"][0]["message"])

    def test_unpinned_appimage_is_rejected(self):
        recipe = {
            "id": "cursor",
            "source": "moos",
            "install": {
                "kind": "appimage",
                "url": "https://example.test/Cursor.AppImage",
                "bin": "cursor",
                "external": True,
                "requires_review": True,
                "risk": "external-download",
            },
        }
        controller, _ = self.controller([recipe])
        code, result = controller.install(["cursor"])
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "failed")
        self.assertIn("not pinned", result["items"][0]["message"])


class LifecycleTests(StoreTestCase):
    def test_remove_refuses_system_only_install(self):
        adapter = FakeAdapter(system={"org.example.App"})
        controller, _ = self.controller([], adapter=adapter)
        code, result = controller.remove("org.example.App")
        self.assertEqual(code, 1)
        self.assertEqual(result["state"], "failed")
        self.assertIn("system-wide", result["message"])
        self.assertEqual(adapter.removes, [])

    def test_run_is_flatpak_only_and_calls_fixed_gpu_guard_boundary(self):
        runner = FakeRunner()
        adapter = FakeAdapter(user={"org.example.App"})
        controller, _ = self.controller([], adapter=adapter, runner=runner)
        code, result = controller.run("org.example.App")
        self.assertEqual(code, 0)
        self.assertEqual(runner.guard_calls, 1)
        self.assertEqual(adapter.launches, ["org.example.App"])
        self.assertEqual(result["state"], "success")

    def test_refresh_rebuilds_the_unified_index_with_fixed_argv(self):
        runner = FakeRunner()
        adapter = FakeAdapter()
        controller, _ = self.controller([], adapter=adapter, runner=runner)
        code, result = controller.refresh_index()
        self.assertEqual(code, 0)
        self.assertEqual(adapter.refreshes, 1)
        self.assertEqual(
            runner.commands,
            [
                [
                    "/usr/bin/moos-store-index",
                    "--catalog",
                    str(controller.catalog_path),
                    "--output",
                    str(controller.store.directory / "index.json"),
                ]
            ],
        )
        self.assertEqual(result["state"], "success")

    def test_open_engine_commands_are_fixed_argv(self):
        for name, expected in MODULE.ENGINE_COMMANDS.items():
            with self.subTest(name=name):
                runner = FakeRunner()
                adapter = FakeAdapter(
                    user={"com.github.tchx84.Flatseal"}
                    if name == "permissions"
                    else set()
                )
                controller, _ = self.controller(
                    [], adapter=adapter, runner=runner
                )
                code, result = controller.open_engine(name)
                self.assertEqual(code, 0)
                if name == "bazaar":
                    self.assertEqual(adapter.installs, [[MODULE.BAZAAR_ID]])
                    self.assertEqual(adapter.launches, [MODULE.BAZAAR_ID])
                    self.assertEqual(runner.commands, [[MODULE.ONE_STORE]])
                    self.assertEqual(runner.spawned, [])
                else:
                    self.assertEqual(runner.spawned, [list(expected)])
                self.assertEqual(result["items"][0]["state"], "opened")
        controller, _ = self.controller(
            [], adapter=FakeAdapter(), runner=FakeRunner()
        )
        code, result = controller.open_engine("permissions")
        self.assertEqual(code, 1)
        self.assertIn("not installed", result["message"])
        controller, _ = self.controller([])
        with self.assertRaises(MODULE.StoreError):
            controller.open_engine("../../bin/sh")


if __name__ == "__main__":
    unittest.main(verbosity=2)
