#!/usr/bin/env python3
"""Mo Store's backend speaks every kind of app with one set of verbs (docs/MO_STORE.md).

Each class below holds one promise of moos-storectl, run for real against a private HOME:

  PinnedDownloads   the publisher's HTTPS URL, its exact size and SHA-256, every redirect hop
                    HTTPS, saved on disk inside HOME — served by a real local TLS server;
  AppDropKind       a pinned AppImage/archive installed by App Drop under the catalogue's id,
                    opened through its launcher, updated when the pin moves, removed; and a
                    file the person dropped is removable from the Store too;
  WebAppKind        a website as an app: launcher, open, remove with and without its data;
  AndroidRecords    pinned and dropped APKs leave a record so they can be updated and removed;
  Updates           check-updates lists pins beside Flatpaks; `update` does both; one app too;
  RemoveWithData    Flatpak data, overrides and portal answers go only when asked, no link followed;
  Permissions       one closed vocabulary, fixed argv per key, a document the window reads;
  Facts             sizes, end of life and permissions from the cached summary, offline;
  Refusals          a job that never started still tells the window why — but never over a live job;
  PublisherPages    an opened page is "opened", never "ready".

Nothing here reaches the network, a display, the session bus or the person's real home.
"""
from __future__ import annotations

import contextlib
import hashlib
import http.server
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socketserver
import ssl
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-storectl"
LOADER = importlib.machinery.SourceFileLoader("moos_storectl_backend_kinds", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop as appdrop  # noqa: E402

ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56


def tarball(members: dict[str, tuple[bytes, int]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
        for name, (data, mode) in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = mode
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def note_app(version: str) -> bytes:
    desktop = ("[Desktop Entry]\nType=Application\nName=Note Forge\nExec=noteforge\n"
               "Icon=noteforge\nCategories=Office;\n")
    return tarball({
        f"noteforge-{version}/noteforge": (ELF + version.encode(), 0o755),
        f"noteforge-{version}/org.example.NoteForge.desktop": (desktop.encode(), 0o644),
        f"noteforge-{version}/noteforge.png": (b"\x89PNG\r\n\x1a\n" + b"0" * 64, 0o644),
    })


class FakeRunner:
    """Records every argv; answers probes from a table. Never executes anything."""

    def __init__(self, answers: dict[tuple[str, ...], tuple[int, str]] | None = None):
        self.spawned: list[list[str]] = []
        self.commands: list[list[str]] = []
        self.probes: list[list[str]] = []
        self.guard_calls = 0
        self.answers = answers or {}
        self.results: dict[tuple[str, ...], MODULE.CommandResult] = {}

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def gpu_guard(self):
        self.guard_calls += 1

    def capture(self, argv, timeout=30):
        self.probes.append(list(argv))
        for prefix, (code, output) in self.answers.items():
            if tuple(argv[: len(prefix)]) == prefix:
                return MODULE.CommandResult(code, "", False, output)
        return MODULE.CommandResult(0, "", False, "Session:\tRUNNING\n")

    def run_cancellable(self, argv, should_cancel):
        self.commands.append(list(argv))
        if should_cancel():
            return MODULE.CommandResult(143, "cancelled", True)
        for prefix, result in self.results.items():
            if tuple(argv[: len(prefix)]) == prefix:
                return result
        return MODULE.CommandResult(0)


class FakeAdapter:
    def __init__(self, *, user=(), system=(), updates=(), candidates=(), facts=None,
                 update_error=None):
        self.user = set(user)
        self.system = set(system)
        self.updates = list(updates)
        self.candidates = list(candidates)
        self.facts = facts
        self.update_error = update_error
        self.removes: list[str] = []
        self.updated: list[list[tuple[str, str]]] = []

    def is_user_installed(self, app_id):
        return app_id in self.user

    def is_system_installed(self, app_id):
        return app_id in self.system

    def install_many(self, ids, events, should_cancel):
        for app_id in ids:
            events.done(f"app/{app_id}/x86_64/stable")

    def remove(self, app_id, events, should_cancel):
        self.removes.append(app_id)
        self.user.discard(app_id)
        events.done(f"app/{app_id}/x86_64/stable")

    def update_refs(self):
        return list(self.updates)

    def update_candidates(self):
        return [dict(item) for item in self.candidates]

    def update_many(self, refs, events, should_cancel):
        self.updated.append(list(refs))
        if self.update_error:
            raise MODULE.StoreError(self.update_error)
        for _name, ref in refs:
            events.done(ref)

    def remote_facts(self):
        if self.facts is None:
            raise MODULE.StoreError("No verified app source is configured")
        return self.facts

    def launch(self, app_id):
        pass


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
            # Outside HOME on purpose: pinned downloads must still land inside it.
            XDG_CACHE_HOME=str(self.base / "cache"),
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
        self.opener = None

    def store(self):
        return MODULE.JobStore(self.base / "cache/moos-store")

    def catalog(self, apps):
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": apps}), encoding="utf-8")
        return path

    def controller(self, apps):
        return MODULE.Controller(self.store(), adapter_factory=lambda: self.adapter,
                                 runner=self.runner, catalog_path=self.catalog(apps),
                                 opener=self.opener)

    def cli(self, apps, *argv) -> int:
        """The command line, as the window's bridge starts it: refusals included."""
        with contextlib.redirect_stdout(io.StringIO()):
            return MODULE.main(["--catalog", str(self.catalog(apps)), *argv], store=self.store(),
                               adapter_factory=lambda: self.adapter, runner=self.runner)

    def job_document(self):
        return json.loads((self.base / "cache/moos-store/job.json").read_text(encoding="utf-8"))


# ── A real HTTPS server on 127.0.0.1, trusted only by the opener these tests build ─────────────
class _Routes(http.server.BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, dict[str, str], bytes]] = {}
    hits: list[str] = []

    def do_GET(self):  # noqa: N802 - http.server API
        self.hits.append(self.path)
        status, headers, body = self.routes.get(self.path, (404, {}, b"missing"))
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def log_message(self, *_args):
        return


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


@unittest.skipUnless(shutil.which("openssl") or Path("/usr/bin/openssl").is_file(),
                     "needs openssl to make a throwaway certificate")
class PinnedDownloads(Backend):
    @classmethod
    def setUpClass(cls):
        cls.certs = tempfile.TemporaryDirectory()
        directory = Path(cls.certs.name)
        cls.cert, key = directory / "cert.pem", directory / "key.pem"
        subprocess.run([shutil.which("openssl") or "/usr/bin/openssl", "req", "-x509", "-newkey",
                        "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cls.cert), "-days", "1",
                        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"],
                       check=True, capture_output=True, timeout=120)
        cls.https = _Server(("127.0.0.1", 0), _Routes)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cls.cert), str(key))
        cls.https.socket = context.wrap_socket(cls.https.socket, server_side=True)
        cls.http = _Server(("127.0.0.1", 0), _Routes)
        for server in (cls.https, cls.http):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.secure = f"https://127.0.0.1:{cls.https.server_address[1]}"
        cls.plain = f"http://127.0.0.1:{cls.http.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        for server in (cls.https, cls.http):
            server.shutdown()
            server.server_close()
        cls.certs.cleanup()

    def setUp(self):
        super().setUp()
        _Routes.routes = {}
        _Routes.hits = []
        context = ssl.create_default_context(cafile=str(self.cert))
        # The production opener's redirect rule, plus trust in this test's certificate only, and
        # no proxy from the environment between the test and its own server.
        self.opener = urllib.request.build_opener(
            MODULE.HttpsOnlyRedirects(), urllib.request.HTTPSHandler(context=context),
            urllib.request.ProxyHandler({}))

    def serve(self, path: str, body: bytes, *, status: int = 200, length: int | None = -1,
              headers: dict[str, str] | None = None) -> str:
        sent = dict(headers or {})
        if length == -1:
            sent["Content-Length"] = str(len(body))
        elif length is not None:
            sent["Content-Length"] = str(length)
        _Routes.routes[path] = (status, sent, body)
        return self.secure + path

    def recipe(self, url: str, body: bytes, *, size: int | None = None, sha: str | None = None,
               version: str = "2.1", **extra) -> dict:
        install = {"kind": "appdrop", "artifact": "archive", "version": version,
                   "downloads": {MODULE.running_arch(): {
                       "url": url, "sha256": sha or hashlib.sha256(body).hexdigest(),
                       "size": len(body) if size is None else size}},
                   "risk": "downloaded-executable", "requires_review": True, "external": True}
        install.update(extra)
        return {"id": "noteforge", "source": "moos", "en": "Note Forge", "ar": "نوت فورج",
                "install": install}

    def downloads(self) -> Path:
        return self.home / ".cache/moos-store/downloads"

    def test_a_pinned_archive_installs_through_app_drop_from_inside_home(self):
        body = note_app("2.1")
        recipe = self.recipe(self.serve("/noteforge-2.1.tar.gz", body), body)
        seen: list[Path] = []
        original = MODULE.Controller._download_progress

        def watch(controller, job, item_id, downloaded, size, message, key):
            seen.extend(self.downloads().glob(".noteforge.*.part"))
            return original(controller, job, item_id, downloaded, size, message, key)

        with mock.patch.object(MODULE.Controller, "_download_progress", watch):
            code, result = self.controller([recipe]).install(["noteforge"])
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual(result["items"][0]["message_key"], "installed")
        self.assertTrue(seen, "the download was never seen in ~/.cache/moos-store/downloads")
        self.assertEqual(list(self.downloads().iterdir()), [], "a download outlived its install")
        record = appdrop.read_record("noteforge")
        self.assertEqual((record["catalog_id"], record["version"], record["sha256"]),
                         ("noteforge", "2.1", hashlib.sha256(body).hexdigest()))
        self.assertEqual(record["launcher"], "org.example.NoteForge.desktop")
        launcher = (self.home / ".local/share/applications/org.example.NoteForge.desktop")
        self.assertIn("Name[ar]=نوت فورج", launcher.read_text(encoding="utf-8").splitlines())

    def test_size_and_digest_are_the_catalogues_not_the_servers(self):
        body = note_app("2.1")
        cases = {
            "declares more than the pin": (self.serve("/a.tar.gz", body, length=len(body) + 4096),
                                           body, None, "larger"),
            "sends more than the pin": (self.serve("/b.tar.gz", body + b"\0" * 9000, length=None),
                                        body, None, "larger"),
            "sends less than the pin": (self.serve("/c.tar.gz", body[:-100]), body, None, "pins"),
            "different bytes": (self.serve("/d.tar.gz", body), body, "0" * 64, "SHA-256"),
        }
        for label, (url, pinned_body, sha, words) in cases.items():
            with self.subTest(label):
                code, result = self.controller([self.recipe(url, pinned_body, sha=sha)]).install(["noteforge"])
                self.assertEqual((code, result["state"]), (1, "failed"), result)
                self.assertIn(words, result["items"][0]["message"])
                self.assertFalse((self.home / "Applications/noteforge").exists())
                self.assertEqual(list(self.downloads().iterdir()) if self.downloads().exists() else [], [])

    def test_a_body_exactly_the_pinned_size_is_accepted(self):
        body = note_app("2.2")
        code, result = self.controller([self.recipe(self.serve("/e.tar.gz", body, length=None), body)]
                                       ).install(["noteforge"])
        self.assertEqual(result["state"], "success", result)

    def test_every_redirect_hop_must_stay_https(self):
        body = note_app("2.1")
        _Routes.routes["/plain.tar.gz"] = (200, {"Content-Length": str(len(body))}, body)
        self.serve("/final.tar.gz", body)
        hop = self.serve("/hop", b"", status=302, headers={"Location": self.secure + "/final.tar.gz"})
        code, result = self.controller([self.recipe(hop, body)]).install(["noteforge"])
        self.assertEqual(result["state"], "success", result)
        appdrop.remove("noteforge")
        _Routes.hits.clear()
        downgrade = self.serve("/down", b"", status=302, headers={"Location": self.plain + "/plain.tar.gz"})
        code, result = self.controller([self.recipe(downgrade, body)]).install(["noteforge"])
        self.assertEqual(result["state"], "failed", result)
        self.assertIn("not secure", result["items"][0]["message"])
        self.assertNotIn("/plain.tar.gz", _Routes.hits, "the insecure hop was followed")

    def test_a_cancel_between_blocks_stops_the_download_and_leaves_nothing(self):
        body = note_app("2.1") + b""
        controller = self.controller([self.recipe(self.serve("/f.tar.gz", body), body)])
        calls = {"n": 0}
        original = controller._cancelled

        def cancel_on_the_second_check(job):
            calls["n"] += 1
            original(job)
            return calls["n"] >= 2

        with mock.patch.object(controller, "_cancelled", side_effect=cancel_on_the_second_check):
            code, result = controller.install(["noteforge"])
        self.assertEqual((code, result["state"]), (130, "cancelled"), result)
        self.assertEqual(list(self.downloads().iterdir()), [])
        self.assertFalse((self.home / "Applications/noteforge").exists())

    def test_the_redirect_handler_refuses_a_plain_hop_by_itself(self):
        handler = MODULE.HttpsOnlyRedirects()
        request = urllib.request.Request("https://example.test/a")
        closed = []

        class Response(io.BytesIO):
            def close(self):
                closed.append(True)
                super().close()

        with self.assertRaises(MODULE.StoreError):
            handler.redirect_request(request, Response(b""), 302, "Found", {}, "http://example.test/b")
        self.assertEqual(closed, [True], "the refused response was left open")
        for unsafe in ("https://user:pw@example.test/b", "ftp://example.test/b", "https:///nohost"):
            with self.subTest(unsafe), self.assertRaises(MODULE.StoreError):
                handler.redirect_request(request, Response(b""), 302, "Found", {}, unsafe)

    def test_the_pin_is_per_architecture_and_must_be_complete(self):
        install = {"downloads": {"riscv64": {"url": "https://example.test/x", "sha256": "a" * 64, "size": 1}}}
        with self.assertRaises(MODULE.StoreError) as refused:
            MODULE.pinned_artifact("x", install)
        self.assertEqual(refused.exception.message_key, "unsupported_arch")
        here = MODULE.running_arch()
        for bad in ({"url": "http://example.test/x", "sha256": "a" * 64, "size": 1},
                    {"url": "https://example.test/x", "sha256": "a" * 63, "size": 1},
                    {"url": "https://example.test/x", "sha256": "a" * 64},
                    {"url": "https://example.test/x", "sha256": "a" * 64, "size": 0},
                    {"url": "https://example.test/x", "sha256": "a" * 64, "size": True}):
            with self.subTest(bad), self.assertRaises(MODULE.StoreError):
                MODULE.pinned_artifact("x", {"downloads": {here: bad}})
        flat = MODULE.pinned_artifact("x", {"url": "https://example.test/a.apk", "sha256": "A" * 64},
                                      size_required=False)
        self.assertEqual((flat.size, flat.sha256), (None, "a" * 64))


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



class Kinds(Backend):
    def setUp(self):
        super().setUp()
        self.opener = FakeOpener()
        self.menu = mock.patch.object(appdrop, "_refresh_menu", lambda: None)
        self.menu.start()
        self.addCleanup(self.menu.stop)

    def pin(self, name: str, body: bytes) -> dict:
        url = f"https://publisher.example/{name}"
        self.opener.files[url] = body
        return {MODULE.running_arch(): {"url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                        "size": len(body)}}

    def appdrop_recipe(self, version: str = "2.1", **extra) -> dict:
        install = {"kind": "appdrop", "artifact": "archive", "version": version,
                   "downloads": self.pin(f"noteforge-{version}.tar.gz", note_app(version)),
                   "risk": "downloaded-executable", "requires_review": True, "external": True}
        install.update(extra)
        return {"id": "noteforge", "source": "moos", "en": "Note Forge", "ar": "نوت فورج",
                "install": install}

    def webapp_recipe(self) -> dict:
        return {"id": "chatgpt", "source": "moos", "en": "ChatGPT", "ar": "شات جي بي تي",
                "cat": "ai", "desc_en": "Chat", "desc_ar": "دردشة",
                "install": {"kind": "webapp", "url": "https://chatgpt.com/", "hosts": ["chatgpt.com",
                            "*.chatgpt.com"], "identity": ["google"],
                            "permissions": ["microphone", "notifications"], "accent": "#10a37f",
                            "risk": "web-app", "requires_review": True}}


class AppDropKind(Kinds):
    def test_install_open_and_remove_through_the_launcher(self):
        recipe = self.appdrop_recipe(exec="noteforge", wm_class="NoteForge",
                                     categories=["Office", "Utility"])
        controller = self.controller([recipe])
        code, result = controller.install(["noteforge"])
        self.assertEqual(result["state"], "success", result)
        launcher = self.home / ".local/share/applications/org.example.NoteForge.desktop"
        text = launcher.read_text(encoding="utf-8").splitlines()
        self.assertIn("StartupWMClass=NoteForge", text)
        self.assertIn("Categories=Office;Utility;", text)
        self.assertIn("X-MoOS-AppDrop=noteforge", text)

        code, result = controller.run("noteforge")
        self.assertEqual(result["state"], "success", result)
        self.assertEqual(self.runner.spawned, [[MODULE.GTK_LAUNCH, "org.example.NoteForge.desktop"]])
        self.assertEqual(self.runner.guard_calls, 1)

        code, result = controller.remove("noteforge")
        self.assertEqual((result["state"], result["items"][0]["message_key"]), ("success", "removed"))
        self.assertFalse(launcher.exists())
        self.assertFalse((self.home / "Applications/noteforge").exists())
        code, result = controller.run("noteforge")
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["items"][0]["message_key"], "not_installed")

    def test_a_download_of_the_wrong_kind_is_refused(self):
        recipe = self.appdrop_recipe()
        recipe["install"]["artifact"] = "appimage"
        code, result = self.controller([recipe]).install(["noteforge"])
        self.assertEqual(result["state"], "failed")
        self.assertIn("kind of file", result["items"][0]["message"])
        self.assertFalse((self.home / "Applications/noteforge").exists())

    def test_recipe_launcher_fields_are_checked_before_app_drop_sees_them(self):
        for field, value in (("exec", "../../bin/sh"), ("icon", "/etc/passwd"), ("wm_class", "a\nb"),
                             ("desktop_id", "two.parts"), ("categories", ["Office", "X-Evil"]),
                             ("version", "1.0\nExec=evil")):
            with self.subTest(field=field):
                recipe = self.appdrop_recipe()
                recipe["install"][field] = value
                asked = len(self.opener.requests)
                code, result = self.controller([recipe]).install(["noteforge"])
                self.assertEqual(result["state"], "failed", result)
                self.assertEqual(len(self.opener.requests), asked,
                                 "the recipe was trusted far enough to start a download")

    def test_a_pin_that_moves_is_an_update_and_the_update_swaps_it_in(self):
        controller = self.controller([self.appdrop_recipe("2.1")])
        self.assertEqual(controller.install(["noteforge"])[1]["state"], "success")
        controller = self.controller([self.appdrop_recipe("2.2")])
        code, pending = controller.check_updates()
        self.assertEqual(pending["items"], [{"id": "noteforge", "kind": "pin", "name": "Note Forge",
                                             "version": "2.2", "installed_version": "2.1"}])
        self.assertEqual((pending["count"], pending["app_count"]), (1, 1))
        code, result = controller.update("noteforge")
        self.assertEqual(result["state"], "success", result)
        self.assertEqual(result["items"][0]["message_key"], "updated")
        self.assertEqual(appdrop.read_record("noteforge")["version"], "2.2")
        self.assertTrue((self.home / "Applications/noteforge/noteforge").read_bytes().endswith(b"2.2"))
        self.assertEqual(controller.check_updates()[1]["items"], [])
        code, result = controller.update("noteforge")
        self.assertEqual((result["state"], result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("success", "skipped", "app_up_to_date"))

    def test_a_dropped_app_is_removable_and_openable_from_the_store(self):
        download = self.home / "Downloads/noteforge-2.1.tar.gz"
        download.parent.mkdir()
        download.write_bytes(note_app("2.1"))
        appdrop.install(appdrop.inspect(download))
        controller = self.controller([])
        code, result = controller.run("noteforge")
        self.assertEqual(result["state"], "success", result)
        self.assertEqual(self.runner.spawned[-1], [MODULE.GTK_LAUNCH, "org.example.NoteForge.desktop"])
        self.assertEqual(self.cli([], "update", "noteforge"), 2)
        self.assertEqual(self.job_document()["items"][0]["message_key"], "update_by_file")
        code, result = controller.remove("noteforge")
        self.assertEqual(result["state"], "success", result)
        self.assertEqual(appdrop.installed(), [])

    def test_remove_with_data_says_what_it_could_not_find(self):
        controller = self.controller([self.appdrop_recipe()])
        controller.install(["noteforge"])
        code, result = controller.remove("noteforge", delete_data=True)
        self.assertEqual(result["items"][0]["message_key"], "removed_data_untracked")
        self.assertIn("kept", result["items"][0]["message"])


class WebAppKind(Kinds):
    def test_install_open_remove_and_remove_with_data(self):
        controller = self.controller([self.webapp_recipe()])
        code, result = controller.install(["chatgpt"])
        self.assertEqual(result["state"], "success", result)
        launcher = self.home / ".local/share/applications/org.moos.webapp.chatgpt.desktop"
        self.assertIn("X-MoOS-WebApp=chatgpt", launcher.read_text(encoding="utf-8").splitlines())
        self.assertEqual(self.opener.requests, [], "a web app downloads nothing")

        code, result = controller.run("chatgpt")
        self.assertEqual(self.runner.spawned, [[MODULE.WEBAPP_RUNTIME, "chatgpt"]])

        data = self.home / ".local/share/moos/webapps/chatgpt/profile"
        data.mkdir(parents=True)
        (data / "Cookies").write_text("signed in", encoding="utf-8")
        code, result = controller.remove("chatgpt")
        self.assertEqual(result["items"][0]["message_key"], "removed")
        self.assertFalse(launcher.exists())
        self.assertTrue((data / "Cookies").exists(), "a plain remove deleted the sign-in")

        controller.install(["chatgpt"])
        code, result = controller.remove("chatgpt", delete_data=True)
        self.assertEqual(result["items"][0]["message_key"], "removed_with_data")
        self.assertFalse(data.exists())

    def test_its_permissions_are_the_catalogues_and_changeable(self):
        controller = self.controller([self.webapp_recipe()])
        controller.install(["chatgpt"])
        code, document = controller.permissions("chatgpt")
        self.assertEqual((document["kind"], document["sandboxed"]), ("webapp", True))
        self.assertEqual([(row["key"], row["state"], row["ask"]) for row in document["rows"]],
                         [("microphone", "deny", True), ("notifications", "deny", True)])
        code, result = controller.set_permission("chatgpt", "microphone", "allow")
        self.assertEqual((result["state"], result["items"][0]["message_key"]),
                         ("success", "permission_changed"))
        written = json.loads((self.base / "cache/moos-store/permissions/chatgpt.json").read_text(encoding="utf-8"))
        self.assertEqual(written["rows"][0], {"key": "microphone", "state": "allow", "changeable": True,
                                              "ask": False})
        code, result = controller.set_permission("chatgpt", "microphone", "reset")
        self.assertEqual(result["items"][0]["message_key"], "permissions_reset")
        self.assertTrue(controller.permissions("chatgpt")[1]["rows"][0]["ask"])
        self.assertEqual(self.cli([self.webapp_recipe()], "set-permission", "chatgpt", "camera", "allow"), 2,
                         "a permission the catalogue does not list is refused")
        self.assertEqual(self.job_document()["message_key"], "invalid_permission")


class AndroidRecords(Kinds):
    PACKAGE = "org.example.notes"

    def recipe(self, body: bytes) -> dict:
        return {"id": self.PACKAGE, "source": "moos", "en": "Notes",
                "install": {"kind": "android", "package": self.PACKAGE, "version": "1.0",
                            "url": f"https://f-droid.example/{self.PACKAGE}.apk",
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "risk": "external-download", "requires_review": True, "external": True}}

    def test_a_catalogue_apk_is_recorded_and_its_newer_pin_is_an_update(self):
        body = b"PK\x03\x04first apk"
        recipe = self.recipe(body)
        self.opener.files[recipe["install"]["url"]] = body
        code, result = self.controller([recipe]).install([self.PACKAGE])
        self.assertEqual(result["state"], "success", result)
        install = [argv for argv in self.runner.commands if argv[1:3] == ["app", "install"]]
        self.assertEqual(len(install), 1)
        self.assertTrue(install[0][3].startswith(str(self.home / ".cache/moos-store/downloads/")),
                        "the APK did not land on disk inside home")
        self.assertTrue(install[0][3].endswith(".apk"))
        record = json.loads((self.home / f".local/share/moos/android/{self.PACKAGE}.json").read_text())
        self.assertEqual((record["sha256"], record["source"]), (hashlib.sha256(body).hexdigest(), "catalog"))

        (self.home / f".local/share/waydroid/data/data/{self.PACKAGE}").mkdir(parents=True)
        newer = b"PK\x03\x04second apk"
        recipe = self.recipe(newer)
        recipe["install"]["version"] = "1.1"
        self.opener.files[recipe["install"]["url"]] = newer
        pending = self.controller([recipe]).check_updates()[1]["items"]
        self.assertEqual(pending, [{"id": self.PACKAGE, "kind": "pin", "name": "Notes", "version": "1.1",
                                    "installed_version": "1.0"}])

    def test_a_dropped_apk_gets_the_same_checks_and_a_record(self):
        apk = self.home / "Downloads/notes.apk"
        apk.parent.mkdir()
        apk.write_bytes(b"PK\x03\x04dropped")
        # Readiness reads before the install's before/after diff, and before run/remove.
        before = "packageName: com.other\n"
        after = f"packageName: com.other\npackageName: {self.PACKAGE}\n"
        listing = iter([before, before, after, after, after])
        self.runner.answers = {(MODULE.WAYDROID, "status"): (0, "Session:\tRUNNING\n")}
        original = self.runner.capture

        def capture(argv, timeout=30):
            if list(argv) == [MODULE.WAYDROID, "app", "list"]:
                self.runner.probes.append(list(argv))
                return MODULE.CommandResult(0, "", False, next(listing))
            return original(argv, timeout)

        self.runner.capture = capture
        code, result = self.controller([]).install_file(str(apk))
        self.assertEqual(result["state"], "success", result)
        self.assertIn([MODULE.WAYDROID, "status"], self.runner.probes, "no container readiness check")
        record = json.loads((self.home / f".local/share/moos/android/{self.PACKAGE}.json").read_text())
        self.assertEqual((record["source"], record["file"]), ("file", "notes.apk"))

        code, result = self.controller([]).run(self.PACKAGE)
        self.assertEqual(result["state"], "success", result)
        self.assertIn([MODULE.WAYDROID, "app", "launch", self.PACKAGE], self.runner.commands)

        code, result = self.controller([]).remove(self.PACKAGE)
        self.assertEqual(result["state"], "success", result)
        self.assertIn([MODULE.WAYDROID, "app", "remove", self.PACKAGE], self.runner.commands)
        self.assertFalse((self.home / f".local/share/moos/android/{self.PACKAGE}.json").exists())

    def test_a_flatpak_with_the_same_id_keeps_its_meaning(self):
        record = self.home / f".local/share/moos/android/{self.PACKAGE}.json"
        record.parent.mkdir(parents=True)
        record.write_text(json.dumps({"schema": 1, "id": self.PACKAGE, "package": self.PACKAGE}),
                          encoding="utf-8")
        self.adapter.user = {self.PACKAGE}
        code, result = self.controller([]).remove(self.PACKAGE)
        self.assertEqual(result["state"], "success", result)
        self.assertEqual(self.adapter.removes, [self.PACKAGE])
        self.assertFalse([argv for argv in self.runner.commands if argv[1:3] == ["app", "remove"]])
        self.assertTrue(record.exists(), "the Android copy's record was touched by a Flatpak removal")

    def test_an_error_on_stderr_is_a_failure_even_with_exit_zero(self):
        apk = self.home / "Downloads/bad.apk"
        apk.parent.mkdir()
        apk.write_bytes(b"PK\x03\x04bad")
        self.runner.results[(MODULE.WAYDROID, "app", "install")] = MODULE.CommandResult(
            0, "ERROR: Failed to install the package")
        code, result = self.controller([]).install_file(str(apk))
        self.assertEqual(result["state"], "failed", result)
        self.assertEqual(list((self.home / ".local/share/moos/android").glob("*.json"))
                         if (self.home / ".local/share/moos/android").exists() else [], [])


class Updates(Kinds):
    def test_update_all_does_flatpaks_and_pins_and_one_failure_spares_the_other(self):
        controller = self.controller([self.appdrop_recipe("2.1")])
        controller.install(["noteforge"])
        self.adapter.updates = [("org.example.Editor", "app/org.example.Editor/x86_64/stable")]
        self.adapter.update_error = "remote unreachable"
        code, result = self.controller([self.appdrop_recipe("2.2")]).update()
        states = {item["id"]: item["state"] for item in result["items"]}
        self.assertEqual(states, {"org.example.Editor": "failed", "noteforge": "done"}, result)
        self.assertEqual(result["state"], "partial")
        self.assertEqual(appdrop.read_record("noteforge")["version"], "2.2")

    def test_nothing_to_do_is_up_to_date(self):
        code, result = self.controller([]).update()
        self.assertEqual((code, result["message_key"]), (0, "up_to_date"))

    def test_one_flatpak_updates_alone(self):
        self.adapter.user = {"org.example.Editor", "org.example.Other"}
        self.adapter.updates = [("org.example.Editor", "app/org.example.Editor/x86_64/stable"),
                                ("org.example.Other", "app/org.example.Other/x86_64/stable")]
        code, result = self.controller([]).update("org.example.Editor")
        self.assertEqual(result["state"], "success", result)
        self.assertEqual(self.adapter.updated, [[("org.example.Editor", "app/org.example.Editor/x86_64/stable")]])
        code, result = self.controller([]).update("org.example.Missing")
        self.assertEqual(result["items"][0]["message_key"], "not_installed")

    def test_auto_updates_is_the_owners_setting_and_check_updates_reports_it(self):
        settings = self.home / ".config/moos/store.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({"other": 1}), encoding="utf-8")
        controller = self.controller([])
        self.assertTrue(controller.check_updates()[1]["auto_updates"])
        code, document = controller.set_auto_updates(False)
        self.assertEqual((code, document["auto_updates"]), (0, False))
        self.assertEqual(json.loads(settings.read_text(encoding="utf-8")),
                         {"auto_updates": False, "other": 1, "schema": 1})
        self.assertFalse(controller.check_updates()[1]["auto_updates"])
        self.assertFalse((self.base / "cache/moos-store/job.json").exists(),
                         "a setting is not a job and waits for none")
        self.assertEqual(self.cli([], "auto-updates", "on"), 0)
        self.assertTrue(MODULE.auto_updates_enabled())


class RemoveWithData(Kinds):
    APP = "org.example.Editor"

    def test_data_overrides_and_portal_answers_go_and_no_link_is_followed(self):
        self.adapter.user = {self.APP}
        data = self.home / ".var/app" / self.APP
        (data / "config").mkdir(parents=True)
        outside = self.home / "Documents/keep.txt"
        outside.parent.mkdir()
        outside.write_text("mine", encoding="utf-8")
        (data / "config/documents").symlink_to(outside.parent)
        code, result = self.controller([]).remove(self.APP, delete_data=True)
        self.assertEqual((result["state"], result["items"][0]["message_key"]), ("success", "removed_with_data"))
        self.assertFalse(data.exists())
        self.assertEqual(outside.read_text(encoding="utf-8"), "mine")
        self.assertEqual(self.runner.commands, [
            [MODULE.FLATPAK_CLI, "override", "--user", "--reset", self.APP],
            [MODULE.FLATPAK_CLI, "permission-reset", self.APP]])

    def test_without_the_flag_the_data_stays(self):
        self.adapter.user = {self.APP}
        data = self.home / ".var/app" / self.APP
        data.mkdir(parents=True)
        code, result = self.controller([]).remove(self.APP)
        self.assertEqual(result["items"][0]["message_key"], "removed")
        self.assertTrue(data.exists())
        self.assertEqual(self.runner.commands, [])

    def test_a_data_folder_that_is_a_link_is_unlinked_not_followed(self):
        self.adapter.user = {self.APP}
        target = self.home / "Elsewhere"
        target.mkdir()
        (target / "precious").write_text("x", encoding="utf-8")
        (self.home / ".var/app").mkdir(parents=True)
        (self.home / ".var/app" / self.APP).symlink_to(target)
        self.controller([]).remove(self.APP, delete_data=True)
        self.assertTrue((target / "precious").exists())
        self.assertFalse((self.home / ".var/app" / self.APP).is_symlink())

    def test_leftover_data_of_a_removed_app_can_still_be_deleted(self):
        data = self.home / ".var/app" / self.APP
        data.mkdir(parents=True)
        code, result = self.controller([]).remove(self.APP, delete_data=True)
        self.assertEqual(result["items"][0]["message_key"], "removed_with_data")
        self.assertFalse(data.exists())


class Permissions(Kinds):
    APP = "org.example.Editor"
    SHOWN = ("[Context]\nshared=ipc;network;\nsockets=x11;pulseaudio;\ndevices=dri;all;\n"
             "features=bluetooth;\nfilesystems=host;xdg-download;\n")

    def test_the_document_uses_the_closed_vocabulary(self):
        self.adapter.user = {self.APP}
        self.runner.answers = {
            (MODULE.FLATPAK_CLI, "info"): (0, self.SHOWN),
            (MODULE.FLATPAK_CLI, "permission-show"): (0, f"background\tbackground\t{self.APP}\tno\t0x00\n"),
        }
        code, document = self.controller([]).permissions(self.APP)
        rows = {row["key"]: (row["state"], row["changeable"]) for row in document["rows"]}
        self.assertEqual(rows, {"network": ("allow", True), "files-home": ("allow", False),
                                "files-all": ("allow", True), "downloads": ("allow", False),
                                "devices": ("allow", True), "sound": ("allow", True),
                                "bluetooth": ("allow", True), "background": ("deny", True)})
        self.assertEqual([MODULE.FLATPAK_CLI, "info", "--user", "--show-permissions", self.APP],
                         self.runner.probes[0])
        self.assertFalse((self.base / "cache/moos-store/job.json").exists(), "a read took a job")

    def test_each_key_has_one_fixed_command(self):
        self.adapter.user = {self.APP}
        expected = {
            ("network", "deny"): ["override", "--user", "--unshare=network"],
            ("files-home", "allow"): ["override", "--user", "--filesystem=home"],
            ("files-all", "deny"): ["override", "--user", "--nofilesystem=host"],
            ("downloads", "allow"): ["override", "--user", "--filesystem=xdg-download"],
            ("devices", "deny"): ["override", "--user", "--nodevice=all"],
            ("sound", "allow"): ["override", "--user", "--socket=pulseaudio"],
            ("bluetooth", "deny"): ["override", "--user", "--disallow=bluetooth"],
            ("background", "deny"): ["permission-set", "background", "background"],
        }
        for (key, value), words in expected.items():
            with self.subTest(key=key, value=value):
                self.runner.commands.clear()
                code, result = self.controller([]).set_permission(self.APP, key, value)
                self.assertEqual(result["state"], "success", result)
                self.assertEqual(self.runner.commands[0][:1 + len(words)], [MODULE.FLATPAK_CLI, *words])
                self.assertEqual(self.runner.commands[0][-1 if key != "background" else -2], self.APP)
        self.runner.commands.clear()
        code, result = self.controller([]).set_permission(self.APP, "network", "reset")
        self.assertEqual(self.runner.commands, [
            [MODULE.FLATPAK_CLI, "override", "--user", "--reset", self.APP],
            [MODULE.FLATPAK_CLI, "permission-reset", self.APP]])

    def test_anything_outside_the_vocabulary_is_refused_with_a_reason(self):
        self.adapter.user = {self.APP}
        for key, value in (("filesystem=/", "allow"), ("network", "maybe"), ("home;host", "allow")):
            with self.subTest(key=key, value=value):
                self.assertEqual(self.cli([], "set-permission", self.APP, key, value), 2)
                document = self.job_document()
                self.assertEqual((document["action"], document["state"], document["message_key"]),
                                 ("set-permission", "failed", "invalid_permission"))
        # An option-looking key never becomes a flag: the command line itself refuses it.
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.cli([], "set-permission", self.APP, "--reset", "allow")
        self.assertEqual(self.runner.commands, [])

    def test_unsandboxed_kinds_say_so_and_android_points_at_its_settings(self):
        recipe = self.appdrop_recipe()
        android = {"id": "org.example.notes", "source": "moos", "en": "Notes",
                   "install": {"kind": "android", "package": "org.example.notes"}}
        controller = self.controller([recipe, android])
        document = controller.permissions("noteforge")[1]
        self.assertEqual((document["sandboxed"], document["rows"], document["note_key"]),
                         (False, [], "full_access"))
        document = controller.permissions("org.example.notes")[1]
        self.assertEqual((document["sandboxed"], document["note_key"]), (True, "android_managed"))
        self.assertEqual(self.cli([recipe, android], "set-permission", "noteforge", "network", "deny"), 2)
        self.assertEqual(self.job_document()["message_key"], "unsupported_kind")


class Facts(Kinds):
    CHROME = ("[Application]\nname=com.google.Chrome\n\n[Context]\nshared=ipc;network;\n"
              "sockets=cups;pcsc;pulseaudio;wayland;x11;\ndevices=all;\n"
              "filesystems=host-etc;xdg-download;xdg-documents;\n\n"
              "[Session Bus Policy]\norg.freedesktop.Notifications=talk\n\n"
              "[Extra Data]\nname=chrome.deb\nsize=143552428\n")
    OLD_GAME = ("[Context]\nsockets=x11;\nfilesystems=home;\n"
                "[Session Bus Policy]\norg.freedesktop.Flatpak=talk\n")

    def test_one_app_in_the_closed_words(self):
        self.assertEqual(MODULE.ref_facts(self.CHROME, 153309373, 23060992, None, None), {
            "download": 153309373, "installed": 23060992, "eol": None, "eol_rebase": None,
            "permissions": ["network", "downloads", "devices", "sound"],
            "x11_only": False, "extra_data": True})
        game = MODULE.ref_facts(self.OLD_GAME, 1, 2, "No longer maintained.\n", "org.example.New")
        self.assertEqual(game["permissions"], ["files-home", "downloads", "host-commands"])
        self.assertEqual((game["x11_only"], game["eol"], game["eol_rebase"]),
                         (True, "No longer maintained.", "org.example.New"))

    def test_facts_json_is_written_and_a_missing_source_says_so(self):
        self.adapter.facts = {"com.google.Chrome": MODULE.ref_facts(self.CHROME, 1, 2, None, None)}
        code, summary = self.controller([]).facts()
        self.assertEqual((code, summary["count"], summary["state"]), (0, 1, "success"))
        written = json.loads((self.base / "cache/moos-store/facts.json").read_text(encoding="utf-8"))
        self.assertEqual(written["schema"], 1)
        self.assertIn("com.google.Chrome", written["apps"])
        self.adapter.facts = None
        code, summary = self.controller([]).facts()
        self.assertEqual((code, summary["state"]), (2, "failed"))

    def test_the_adapter_reads_only_cached_verified_sources(self):
        class Ref:
            def __init__(self, name, branch="stable", arch="x86_64", kind=0):
                self.name, self.branch, self.arch, self.kind = name, branch, arch, kind

            def get_kind(self): return self.kind
            def get_arch(self): return self.arch
            def get_name(self): return self.name
            def get_branch(self): return self.branch
            def get_download_size(self): return 10
            def get_installed_size(self): return 20
            def get_eol(self): return None
            def get_eol_rebase(self): return None

            def get_metadata(self):
                text = f"[Context]\nshared=network;\n# {self.branch}\n".encode()
                return type("Bytes", (), {"get_data": lambda _self: text})()

        class Remote:
            def __init__(self, name, url):
                self.name, self.url = name, url

            def get_name(self): return self.name
            def get_url(self): return self.url
            def get_gpg_verify(self): return True
            def get_disabled(self): return False
            def get_nodeps(self): return False

        calls = []

        class Installation:
            def __init__(self, remotes, refs):
                self.remotes, self.refs = remotes, refs

            def list_remotes(self, _cancellable):
                return self.remotes

            def list_remote_refs_sync_full(self, name, flags, _cancellable):
                calls.append((name, flags))
                return self.refs

        class FlatpakNamespace:
            class RefKind:
                APP = 0

            class QueryFlags:
                ONLY_CACHED = "ONLY_CACHED"

            @staticmethod
            def get_default_arch():
                return "x86_64"

        adapter = object.__new__(MODULE.FlatpakAdapter)
        adapter.Flatpak = FlatpakNamespace
        adapter.user = Installation([Remote("evil", "https://evil.example/repo/"),
                                     Remote("flathub", "https://dl.flathub.org/repo/")],
                                    [Ref("org.example.App", "beta"), Ref("org.example.App"),
                                     Ref("org.example.Arm", arch="aarch64"),
                                     Ref("org.example.Runtime", kind=1)])
        adapter.system = Installation([Remote("flathub", "https://dl.flathub.org/repo/")],
                                      [Ref("org.example.App", "other"), Ref("org.example.SystemOnly")])
        facts = adapter.remote_facts()
        self.assertEqual(sorted(facts), ["org.example.App", "org.example.SystemOnly"])
        self.assertEqual(calls, [("flathub", "ONLY_CACHED"), ("flathub", "ONLY_CACHED")],
                         "an unverified remote was read, or the read was not cache-only")
        self.assertEqual(facts["org.example.App"]["permissions"], ["network"])


class Refusals(Kinds):
    def test_an_invalid_id_reaches_the_window_as_a_terminal_document(self):
        self.assertEqual(self.cli([], "remove", "not an id"), 2)
        document = self.job_document()
        self.assertEqual((document["action"], document["state"], document["message_key"]),
                         ("remove", "failed", "invalid_id"))
        self.assertEqual([(item["id"], item["state"], item["message_key"]) for item in document["items"]],
                         [("not an id", "failed", "invalid_id")])

    def test_busy_is_published_unless_another_job_is_live(self):
        store = self.store()
        held = MODULE.GlobalLock(store).acquire()
        self.addCleanup(held.release)
        self.assertEqual(self.cli([], "install", "org.example.App"), 75)
        document = self.job_document()
        self.assertEqual((document["state"], document["message_key"], document["items"][0]["message_key"]),
                         ("busy", "busy", "busy"))

        live = MODULE.Job(store, "install", ["org.example.Running"])
        live.update(state="running", progress=40)
        before = store.path.read_bytes()
        self.assertEqual(self.cli([], "remove", "org.example.Other"), 75)
        self.assertEqual(store.path.read_bytes(), before, "a refusal overwrote a live job")
        self.assertEqual(self.cli([], "remove", "not an id"), 2)
        self.assertEqual(store.path.read_bytes(), before, "a refusal overwrote a live job")

    def test_a_read_only_command_never_writes_a_job(self):
        self.assertEqual(self.cli([], "permissions", "not an id"), 2)
        self.assertFalse((self.base / "cache/moos-store/job.json").exists())

    def test_a_kind_without_the_verb_is_refused_by_name(self):
        recipe = {"id": "cursor", "source": "moos", "en": "Cursor",
                  "install": {"kind": "web", "url": "https://cursor.com/downloads", "external": True,
                              "risk": "external-download", "requires_review": True}}
        self.assertEqual(self.cli([recipe], "run", "cursor"), 2)
        self.assertEqual(self.job_document()["message_key"], "unsupported_kind")
        self.assertEqual(self.runner.spawned, [])


class PublisherPages(Kinds):
    def web(self, app_id: str) -> dict:
        return {"id": app_id, "source": "moos", "en": app_id,
                "install": {"kind": "web", "url": f"https://{app_id}.example/download", "external": True,
                            "risk": "external-download", "requires_review": True}}

    def test_an_opened_page_is_opened_never_ready(self):
        code, result = self.controller([self.web("cursor")]).install(["cursor"])
        self.assertEqual((result["items"][0]["state"], result["items"][0]["message_key"]),
                         ("opened", "opened"))
        self.assertEqual(result["message_key"], "publisher_page_opened")
        self.assertNotEqual(result["message"], "All requested apps are ready")
        code, result = self.controller([self.web("cursor")]).install(["cursor", "org.example.App"])
        self.assertEqual(result["message_key"], "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
