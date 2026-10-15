#!/usr/bin/env python3
"""A portable Windows program from Mo Store's catalogue: its own folder, its own prefix, no window.

  WindowsPortable   moos-storectl's windows-portable kind with a recording runtime: the pinned
                    download, the PE32+ check (a 32-bit program is refused by name), a prefix
                    created once with a clean environment that cannot reach a display or the
                    session bus, the density, the launcher, the record, updates that keep the
                    prefix, and a removal that never follows the prefix's links into home;
  RunForeignApp     `moos-run-foreign --app <id>` itself, with a stub runtime on PATH: every
                    path recomputed from the id, the program confined to its folder, its own log;
  RealRuntimeProof  opt-in (MOOS_WINDOWS_PROOF_EXE=<a 64-bit .exe>): the real runtime creates and
                    removes a prefix in a private home. The program itself is never started.
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
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-storectl"
RUNNER = ROOT / "system_files/usr/bin/moos-run-foreign"
LOADER = importlib.machinery.SourceFileLoader("moos_storectl_backend_windows", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[LOADER.name] = MODULE
LOADER.exec_module(MODULE)
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_appdrop as appdrop  # noqa: E402

APP = "tinyterm"


def pe(machine: int = 0x8664, magic: int = 0x20b, tail: bytes = b"") -> bytes:
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, machine)
    struct.pack_into("<H", data, 84, 2)          # the optional header's size: its magic, no more
    struct.pack_into("<H", data, 88, magic)
    return bytes(data) + tail


def zipped(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in members.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


class Response(io.BytesIO):
    def __init__(self, url: str, body: bytes):
        super().__init__(body)
        self.url = url
        self.headers = {"Content-Length": str(len(body))}

    def geturl(self):
        return self.url


class Opener:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def open(self, request, timeout=30):
        return Response(request.full_url, self.files[request.full_url])


class Runtime:
    """Records the runtime's argv. `wineboot` makes the prefix files a real one would leave; the
    template's copy is made by the real `cp`, exactly as the backend asked for it."""

    def __init__(self, dpi: str = "240", version: str = "wine-11.0 (Staging)"):
        self.commands: list[list[str]] = []
        self.probes: list[list[str]] = []
        self.spawned: list[list[str]] = []
        self.cancel_on: str | None = None
        self.dpi = dpi
        self.version = version

    @staticmethod
    def environment(argv: list[str]) -> dict[str, str]:
        start = argv.index("-i") + 1
        values = {}
        for part in argv[start:]:
            if "=" not in part or part.startswith("/"):
                break
            key, _, value = part.partition("=")
            values[key] = value
        return values

    def run_cancellable(self, argv, should_cancel):
        argv = list(argv)
        self.commands.append(argv)
        if self.cancel_on and self.cancel_on in argv:
            return MODULE.CommandResult(143, "cancelled", True)
        if argv[0] == MODULE.CP_TOOL:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=60)
            return MODULE.CommandResult(done.returncode, done.stderr.strip())
        if "wineboot" in argv:
            prefix = Path(self.environment(argv)["WINEPREFIX"])
            (prefix / "drive_c/users/me").mkdir(parents=True, exist_ok=True)
            (prefix / "drive_c/windows/system32").mkdir(parents=True, exist_ok=True)
            (prefix / "drive_c/windows/system32/kernel32.dll").write_bytes(b"MZ" + b"\0" * 4094)
            for name in ("system.reg", "user.reg", "userdef.reg"):
                (prefix / name).write_text("WINE REGISTRY Version 2\n", encoding="utf-8")
        return MODULE.CommandResult(0)

    def capture(self, argv, timeout=30):
        self.probes.append(list(argv))
        if argv[0] == MODULE.XRDB:
            return MODULE.CommandResult(0, "", False, f"Xft.dpi:\t{self.dpi}\n")
        if argv[-2:] == [MODULE.WINE, "--version"]:
            return MODULE.CommandResult(0, "", False, f"{self.version}\n")
        return MODULE.CommandResult(0, "", False, "")

    def spawn(self, argv):
        self.spawned.append(list(argv))

    def gpu_guard(self):
        pass


class Isolated(unittest.TestCase):
    ISOLATED = ("HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "XDG_DATA_HOME", "XDG_STATE_HOME",
                "XDG_CONFIG_HOME", "XDG_DATA_DIRS", "DBUS_SESSION_BUS_ADDRESS", "DISPLAY",
                "WAYLAND_DISPLAY", "PATH", "LANG")

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
            HOME=str(self.home), XDG_CACHE_HOME=str(self.home / ".cache"),
            XDG_RUNTIME_DIR=str(self.base / "run"), XDG_DATA_HOME=str(self.home / ".local/share"),
            XDG_STATE_HOME=str(self.home / ".local/state"), XDG_CONFIG_HOME=str(self.home / ".config"),
            XDG_DATA_DIRS=str(self.base / "system-share"),
            DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent",
            # What the Store window would pass on: these must NOT reach the runtime's setup.
            DISPLAY=":0", WAYLAND_DISPLAY="wayland-0", LANG="ar_SA.UTF-8",
            PATH=str(self.base / "no-tools"),
        )
        (self.base / "run").mkdir(mode=0o700)
        self.windows = self.home / ".local/share/moos/windows-apps"


class WindowsPortable(Isolated):
    def setUp(self):
        super().setUp()
        tools = self.base / "image-tools"
        tools.mkdir()
        patches = {}
        for name in ("WINE", "WINESERVER", "TIMEOUT_TOOL", "ENV_TOOL", "XRDB"):
            path = tools / name.lower()
            path.write_text("#!/bin/false\n", encoding="utf-8")
            patches[name] = str(path)
        for name, value in patches.items():
            patcher = mock.patch.object(MODULE, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for target, value in ((MODULE, "running_arch"), (appdrop, "_refresh_menu")):
            patcher = mock.patch.object(target, value, (lambda: "x86_64") if value == "running_arch"
                                        else (lambda: None))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.opener = Opener()
        self.runtime = Runtime()

    def recipe(self, body: bytes, *, exe: str = "TinyTerm/tinyterm.exe", version: str = "1.0",
               **extra) -> dict:
        url = f"https://publisher.example/tinyterm-{version}-{len(body)}.bin"
        self.opener.files[url] = body
        install = {"kind": "windows-portable", "version": version, "exe": exe,
                   "downloads": {"x86_64": {"url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                            "size": len(body)}},
                   "risk": "downloaded-executable", "requires_review": True, "external": True}
        install.update(extra)
        return {"id": APP, "source": "moos", "en": "Tiny Term", "ar": "تايني تيرم", "cat": "win",
                "engine": "windows", "arch": ["x86_64"], "install": install}

    def controller(self, recipe: dict) -> MODULE.Controller:
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": [recipe]}), encoding="utf-8")
        return MODULE.Controller(MODULE.JobStore(self.home / ".cache/moos-store"),
                                 adapter_factory=lambda: None, runner=self.runtime,
                                 catalog_path=path, opener=self.opener)

    def test_a_64bit_program_gets_its_own_prefix_launcher_and_record(self):
        recipe = self.recipe(zipped({"TinyTerm/tinyterm.exe": pe(), "TinyTerm/readme.txt": b"hi"}))
        code, result = self.controller(recipe).install([APP])
        self.assertEqual((code, result["state"]), (0, "success"), result)
        base = self.windows / APP
        self.assertTrue((base / "app/TinyTerm/tinyterm.exe").is_file())
        self.assertTrue((base / "prefix/system.reg").is_file())

        runtime_calls = [argv for argv in self.runtime.commands if MODULE.ENV_TOOL in argv]
        self.assertEqual([argv[argv.index(MODULE.ENV_TOOL) + 2 + len(Runtime.environment(argv)):][:2]
                          for argv in runtime_calls],
                         [[MODULE.WINE, "wineboot"], [MODULE.WINE, "reg"], [MODULE.WINESERVER, "--wait"]])
        # The settings folder is made ONCE, as the template, in a staging folder; the program's own
        # folder is a copy of it that can share its extents.
        version_probe = next(argv for argv in self.runtime.probes if argv[-1:] == ["--version"])
        self.assertEqual(version_probe[3:5], [MODULE.ENV_TOOL, "-i"])
        self.assertIn([MODULE.CP_TOOL, "-a", "--reflink=auto", "--no-target-directory", "--",
                       str(self.windows / ".template"), str(base / "prefix")], self.runtime.commands)
        self.assertEqual(json.loads((self.windows / ".template.json").read_text())["wine"],
                         "wine-11.0 (Staging)")
        for argv in runtime_calls + [version_probe]:
            self.assertEqual(argv[:4], [MODULE.TIMEOUT_TOOL, "--kill-after=10", argv[2], MODULE.ENV_TOOL])
            self.assertEqual(argv[4], "-i", "the runtime inherited the session's environment")
            environment = Runtime.environment(argv)
            for leaked in ("DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR"):
                self.assertNotIn(leaked, environment, f"{leaked} reached the runtime's setup")
            self.assertEqual(environment["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/nonexistent")
        for argv in runtime_calls:
            environment = Runtime.environment(argv)
            self.assertEqual(environment["WINEPREFIX"], str(self.windows / ".template.new"))
            self.assertEqual(environment["HOME"], str(self.home))
            self.assertIn("winemenubuilder.exe=d", environment["WINEDLLOVERRIDES"])
            self.assertIn("mscoree,mshtml=", environment["WINEDLLOVERRIDES"])
            self.assertIn("winex11.drv,winewayland.drv=d", environment["WINEDLLOVERRIDES"])
            self.assertEqual((environment["WINEDEBUG"], environment["LANG"]), ("-all", "ar_SA.UTF-8"))
        density = next(argv for argv in runtime_calls if "reg" in argv)
        self.assertEqual(density[-7:], ["/v", "LogPixels", "/t", "REG_DWORD", "/d", "192", "/f"])
        self.assertEqual((self.home / f".local/state/moos-foreign/{APP}/windows-dpi").read_text(), "192\n")

        launcher = (self.home / f".local/share/applications/org.moos.windows.{APP}.desktop")
        lines = launcher.read_text(encoding="utf-8").splitlines()
        for expected in (f"Exec=/usr/bin/moos-run-foreign --app {APP}", "Name=Tiny Term",
                         "Name[ar]=تايني تيرم", "StartupWMClass=tinyterm.exe",
                         f"Icon={MODULE.WINDOWS_FALLBACK_ICON}", f"X-MoOS-WindowsApp={APP}"):
            self.assertIn(expected, lines)
        self.assertFalse(any(line.startswith("Exec=") and "tinyterm.exe" in line for line in lines),
                         "the launcher names a file to run instead of the id")
        record = json.loads((self.windows / f"{APP}.json").read_text(encoding="utf-8"))
        self.assertEqual({key: record[key] for key in ("schema", "id", "version", "sha256", "exe")},
                         {"schema": 1, "id": APP, "version": "1.0",
                          "sha256": recipe["install"]["downloads"]["x86_64"]["sha256"],
                          "exe": "TinyTerm/tinyterm.exe"})
        self.assertIn("installed_at", record)
        self.assertEqual(list((self.home / ".cache/moos-store/downloads").iterdir()), [])

        code, opened = self.controller(recipe).run(APP)
        self.assertEqual(self.runtime.spawned, [[MODULE.GTK_LAUNCH, f"org.moos.windows.{APP}.desktop"]])

    def test_a_single_exe_download_works_too(self):
        recipe = self.recipe(pe(), exe="tinyterm.exe", wm_class="TinyTerm")
        code, result = self.controller(recipe).install([APP])
        self.assertEqual(result["state"], "success", result)
        self.assertTrue((self.windows / APP / "app/tinyterm.exe").is_file())
        self.assertIn("StartupWMClass=TinyTerm", (self.home / f".local/share/applications/"
                      f"org.moos.windows.{APP}.desktop").read_text(encoding="utf-8").splitlines())

    def test_an_exe_name_with_plus_signs_is_its_window_class(self):
        # Found live on 2026-10-14: Notepad++'s default window class, "notepad++.exe", was
        # refused as invalid, so the catalogue's Notepad++ could not be installed at all.
        recipe = self.recipe(pe(), exe="notepad++.exe")
        code, result = self.controller(recipe).install([APP])
        self.assertEqual(result["state"], "success", result)
        self.assertIn("StartupWMClass=notepad++.exe", (self.home / f".local/share/applications/"
                      f"org.moos.windows.{APP}.desktop").read_text(encoding="utf-8").splitlines())

    def test_a_32bit_program_is_refused_by_name_and_leaves_nothing(self):
        recipe = self.recipe(zipped({"TinyTerm/tinyterm.exe": pe(0x14c, 0x10b)}))
        code, result = self.controller(recipe).install([APP])
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["items"][0]["message_key"], "windows_legacy_program")
        self.assertFalse((self.windows / APP).exists())
        self.assertFalse((self.windows / f"{APP}.json").exists())
        self.assertFalse((self.home / f".local/share/applications/org.moos.windows.{APP}.desktop").exists())
        self.assertFalse(any("wineboot" in argv for argv in self.runtime.commands),
                         "a prefix was created for a program that cannot run")

    def test_a_program_path_outside_its_folder_is_refused(self):
        for exe, body in (("../tinyterm.exe", pe()), ("TinyTerm/missing.exe", zipped({"TinyTerm/x.exe": pe()})),
                          ("TinyTerm/notes.txt", zipped({"TinyTerm/notes.txt": b"hi"})),
                          ("/tinyterm.exe", pe())):
            with self.subTest(exe=exe):
                code, result = self.controller(self.recipe(body, exe=exe)).install([APP])
                self.assertEqual(result["state"], "failed", result)
                self.assertFalse((self.windows / APP).exists())
        link = io.BytesIO()
        with zipfile.ZipFile(link, "w") as bundle:
            info = zipfile.ZipInfo("TinyTerm/tinyterm.exe")
            info.external_attr = (0o120777 << 16)
            bundle.writestr(info, "../../../../etc/passwd")
        code, result = self.controller(self.recipe(link.getvalue())).install([APP])
        self.assertEqual(result["state"], "failed")
        self.assertIn("unsafe_archive", result["items"][0]["message"])

    def test_an_update_keeps_the_prefix_and_swaps_the_program(self):
        first = self.recipe(zipped({"TinyTerm/tinyterm.exe": pe(tail=b"one")}))
        self.controller(first).install([APP])
        settings = self.windows / APP / "prefix/user.reg"
        settings.write_text("the person's settings\n", encoding="utf-8")
        second = self.recipe(zipped({"TinyTerm/tinyterm.exe": pe(tail=b"two")}), version="1.1")
        controller = self.controller(second)
        with mock.patch.object(controller, "_adapter", type("NoFlatpaks", (), {
                "update_candidates": staticmethod(lambda: [])})()):
            pending = controller.check_updates()[1]["items"]
        self.assertEqual(pending, [{"id": APP, "kind": "pin", "name": "Tiny Term", "version": "1.1",
                                    "installed_version": "1.0"}])
        self.runtime.commands.clear()
        code, result = controller.update(APP)
        self.assertEqual((result["state"], result["items"][0]["message_key"]), ("success", "updated"), result)
        self.assertTrue((self.windows / APP / "app/TinyTerm/tinyterm.exe").read_bytes().endswith(b"two"))
        self.assertEqual(settings.read_text(encoding="utf-8"), "the person's settings\n")
        self.assertFalse(any("wineboot" in argv for argv in self.runtime.commands),
                         "an update recreated the prefix and lost the program's settings")
        self.assertEqual(json.loads((self.windows / f"{APP}.json").read_text())["version"], "1.1")

    def test_remove_ends_its_processes_and_follows_no_link_into_home(self):
        self.controller(self.recipe(pe(), exe="tinyterm.exe")).install([APP])
        documents = self.home / "Documents"
        documents.mkdir()
        (documents / "letter.txt").write_text("keep me", encoding="utf-8")
        users = self.windows / APP / "prefix/drive_c/users/me"
        (users / "Documents").symlink_to(documents)
        (self.windows / APP / "prefix/dosdevices").mkdir()
        (self.windows / APP / "prefix/dosdevices/z:").symlink_to("/")
        self.runtime.commands.clear()
        code, result = self.controller(self.recipe(pe(), exe="tinyterm.exe")).remove(APP, delete_data=True)
        self.assertEqual((result["state"], result["items"][0]["message_key"]), ("success", "removed_with_data"), result)
        kill = self.runtime.commands[0]
        self.assertEqual(kill[-2:], [MODULE.WINESERVER, "--kill"])
        self.assertEqual(Runtime.environment(kill)["WINEPREFIX"], str(self.windows / APP / "prefix"))
        self.assertEqual((documents / "letter.txt").read_text(encoding="utf-8"), "keep me")
        self.assertFalse((self.windows / APP).exists())
        self.assertFalse((self.windows / f"{APP}.json").exists())
        self.assertFalse((self.home / f".local/share/applications/org.moos.windows.{APP}.desktop").exists())
        self.assertFalse((self.home / f".local/state/moos-foreign/{APP}").exists())

    def test_remove_keeps_prefix_documents_until_deleting_data_is_chosen(self):
        recipe = self.recipe(pe(), exe="tinyterm.exe")
        controller = self.controller(recipe)
        code, result = controller.install([APP])
        self.assertEqual((code, result["state"]), (0, "success"), result)
        saved = self.windows / APP / "prefix/drive_c/users/me/saved-document.txt"
        saved.write_text("the person's document", encoding="utf-8")
        code, result = controller.remove(APP)
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual(saved.read_text(encoding="utf-8"), "the person's document")
        self.assertFalse((self.windows / APP / "app").exists())
        self.assertFalse((self.windows / f"{APP}.json").exists())
        self.runtime.commands.clear()
        code, result = controller.install([APP])
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertEqual(saved.read_text(encoding="utf-8"), "the person's document")
        self.assertFalse(any("wineboot" in argv for argv in self.runtime.commands))
        code, result = controller.remove(APP, delete_data=True)
        self.assertEqual((code, result["state"]), (0, "success"), result)
        self.assertFalse(saved.exists())

    def test_remove_does_not_adopt_an_unmarked_application_directory(self):
        manual = self.windows / APP
        manual.mkdir(parents=True)
        canary = manual / "owner-handmade-file.txt"
        canary.write_text("not written by Mo Store", encoding="utf-8")
        code, result = self.controller(self.recipe(pe(), exe="tinyterm.exe")).remove(APP)
        self.assertEqual((code, result["items"][0]["message_key"]), (0, "not_installed"), result)
        self.assertEqual(canary.read_text(encoding="utf-8"), "not written by Mo Store")
        self.assertEqual(self.runtime.commands, [])

    def test_a_failed_second_rename_restores_the_working_program(self):
        first = self.recipe(pe(tail=b"working-v1"), exe="tinyterm.exe")
        self.controller(first).install([APP])
        app = self.windows / APP / "app"
        before = (app / "tinyterm.exe").read_bytes()
        second = self.recipe(pe(tail=b"new-v2"), exe="tinyterm.exe", version="2.0")
        original = Path.rename
        def fail_staging(path, target):
            if path.name == ".app.installing":
                raise OSError("private injected second rename failure")
            return original(path, target)
        with mock.patch.object(Path, "rename", fail_staging):
            code, result = self.controller(second).install([APP])
        self.assertEqual((code, result["state"]), (1, "failed"), result)
        self.assertEqual((app / "tinyterm.exe").read_bytes(), before)
        self.assertFalse((self.windows / APP / ".app.previous").exists())

    def test_an_interrupted_swap_is_recovered_before_a_failed_download(self):
        recipe = self.recipe(pe(tail=b"working-v1"), exe="tinyterm.exe")
        controller = self.controller(recipe)
        controller.install([APP])
        app = self.windows / APP / "app"
        previous = self.windows / APP / ".app.previous"
        before = (app / "tinyterm.exe").read_bytes()
        app.rename(previous)
        with mock.patch.object(controller, "_download_pinned", side_effect=MODULE.StoreError("offline")):
            code, result = controller.install([APP])
        self.assertEqual((code, result["state"]), (1, "failed"), result)
        self.assertEqual((app / "tinyterm.exe").read_bytes(), before)
        self.assertFalse(previous.exists())

    def test_a_cancelled_first_setup_leaves_nothing_behind(self):
        self.runtime.cancel_on = "wineboot"
        code, result = self.controller(self.recipe(pe(), exe="tinyterm.exe")).install([APP])
        self.assertEqual((code, result["state"]), (130, "cancelled"), result)
        self.assertFalse((self.windows / APP).exists())
        self.assertFalse((self.home / f".local/share/applications/org.moos.windows.{APP}.desktop").exists())
        self.assertEqual(sorted(path.name for path in self.windows.iterdir()), [],
                         "a half-made template or its record was left behind")

    def test_only_a_64bit_pc_installs_windows_programs(self):
        recipe = self.recipe(pe(), exe="tinyterm.exe")
        controller = self.controller(recipe)
        job = MODULE.Job(controller.store, "install", [APP])
        with mock.patch.object(MODULE, "running_arch", lambda: "aarch64"), \
                self.assertRaises(MODULE.StoreError) as refused:
            controller._install_windows_portable(job, APP, recipe)
        self.assertEqual(refused.exception.message_key, "unsupported_arch")

    def test_the_density_follows_moos_run_foreign_exactly(self):
        source = RUNNER.read_text(encoding="utf-8")
        start = source.index("wine_display_dpi() {")
        function = source[start:source.index("\n}\n", start) + 3]
        bindir = self.base / "dpi-bin"
        bindir.mkdir()
        (bindir / "xrdb").write_text('#!/bin/sh\nprintf "Xft.dpi:\\t%s\\n" "$XFT_DPI"\n', encoding="utf-8")
        (bindir / "xrdb").chmod(0o755)
        controller = self.controller(self.recipe(pe(), exe="tinyterm.exe"))
        for raw in ("72", "96", "120", "144", "168.4", "240", "254"):
            with self.subTest(dpi=raw):
                shell = subprocess.run(["bash", "-c", function + "\nwine_display_dpi\n"], text=True,
                                       capture_output=True, check=True,
                                       env={"PATH": f"{bindir}:/usr/bin:/bin", "XFT_DPI": raw})
                self.runtime.dpi = raw
                self.assertEqual(controller._display_dpi(), int(shell.stdout.strip()))


@unittest.skipUnless(Path("/bin/bash").exists() and shutil.which("python3", path="/usr/bin:/bin"),
                     "needs bash and python3")
class RunForeignApp(Isolated):
    def setUp(self):
        super().setUp()
        self.bindir = self.base / "bin"
        self.bindir.mkdir()
        self.calls = self.base / "calls.log"
        stubs = {
            "wine": 'printf "wine|%s|%s|%s|%s\\n" "$WINEPREFIX" "$WINEDLLOVERRIDES" "$PWD" "$*" >>"$CALLS"\n'
                    'touch "$WINEPREFIX/user.reg"\nexit "${WINE_EXIT:-0}"\n',
            "xrdb": 'printf "Xft.dpi:\\t240\\n"\n',
            "notify-send": 'printf "notify|%s\\n" "${@: -1}" >>"$CALLS"\n',
        }
        for name, body in stubs.items():
            (self.bindir / name).write_text("#!/bin/bash\n" + body, encoding="utf-8")
            (self.bindir / name).chmod(0o755)

    def install_layout(self, exe: str = "TinyTerm/tinyterm.exe", identifier: str = APP) -> Path:
        base = self.windows / identifier
        (base / "app/TinyTerm").mkdir(parents=True)
        (base / "app/TinyTerm/tinyterm.exe").write_bytes(pe())
        (base / "prefix").mkdir()
        (base / "prefix/system.reg").write_text("x", encoding="utf-8")
        (self.windows / f"{identifier}.json").write_text(
            json.dumps({"schema": 1, "id": identifier, "exe": exe}), encoding="utf-8")
        return base

    def run_app(self, *argv: str, **extra) -> subprocess.CompletedProcess:
        environment = {"HOME": str(self.home), "PATH": f"{self.bindir}:/usr/bin:/bin",
                       "XDG_DATA_HOME": str(self.home / ".local/share"),
                       "XDG_STATE_HOME": str(self.home / ".local/state"),
                       "CALLS": str(self.calls), **extra}
        return subprocess.run(["bash", str(RUNNER), *argv], env=environment, text=True,
                              capture_output=True, timeout=60)

    def logged(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []

    def test_the_program_runs_in_its_own_prefix_from_its_own_folder(self):
        base = self.install_layout()
        done = self.run_app("--app", APP)
        self.assertEqual(done.returncode, 0, done.stderr)
        runs = [line for line in self.logged() if line.startswith("wine|") and "LogPixels" not in line]
        self.assertEqual(len(runs), 1, self.logged())
        _tag, prefix, overrides, cwd, args = runs[0].split("|", 4)
        self.assertEqual(prefix, str(base / "prefix"))
        self.assertIn("winemenubuilder.exe=d", overrides)
        self.assertEqual(cwd, str((base / "app/TinyTerm").resolve()))
        self.assertEqual(args, str((base / "app/TinyTerm/tinyterm.exe").resolve()))
        self.assertTrue((self.home / f".local/state/moos-foreign/{APP}.log").exists())
        density = [line for line in self.logged() if "LogPixels" in line]
        self.assertEqual(len(density), 1)
        self.assertTrue(density[0].endswith("/d 192 /f"))
        self.run_app("--app", APP)
        self.assertEqual(len([line for line in self.logged() if "LogPixels" in line]), 1,
                         "the density was rewritten although it had not changed")

    def test_every_path_is_recomputed_and_confined(self):
        for label, exe in (("escape", "../prefix/system.reg"), ("absolute", "/usr/bin/true"),
                           ("missing", "TinyTerm/gone.exe")):
            with self.subTest(label):
                shutil.rmtree(self.windows, ignore_errors=True)
                self.calls.unlink(missing_ok=True)
                self.install_layout(exe)
                done = self.run_app("--app", APP)
                self.assertEqual(done.returncode, 2)
                self.assertFalse([line for line in self.logged() if line.startswith("wine|")
                                  and "LogPixels" not in line], "a program outside its folder ran")
        shutil.rmtree(self.windows, ignore_errors=True)
        base = self.install_layout()
        (base / "app/TinyTerm/tinyterm.exe").unlink()
        (base / "app/TinyTerm/tinyterm.exe").symlink_to("/usr/bin/true")
        self.assertEqual(self.run_app("--app", APP).returncode, 2)
        # Each bad id names a complete, runnable layout: only the id check stands in the way.
        for bad in ("../escape", "Tiny", "a b", "x" * 70):
            with self.subTest(identifier=bad):
                shutil.rmtree(self.windows, ignore_errors=True)
                shutil.rmtree(self.home / ".local/share/moos/escape", ignore_errors=True)
                self.calls.unlink(missing_ok=True)
                self.install_layout(identifier=bad)
                self.assertEqual(self.run_app("--app", bad).returncode, 2)
                self.assertFalse([line for line in self.logged() if line.startswith("wine|")],
                                 f"a program ran for the id {bad!r}")
        self.assertEqual(self.run_app("--app", "-x").returncode, 2)
        self.assertEqual(self.run_app("--app").returncode, 2)

    def test_a_program_that_is_not_installed_is_said_plainly(self):
        done = self.run_app("--app", APP)
        self.assertEqual(done.returncode, 2)
        notices = [line for line in self.logged() if line.startswith("notify|")]
        self.assertEqual(len(notices), 1)
        self.assertIn("Mo Store", notices[0])
        for word in ("wine", "prefix", "bottles"):
            self.assertNotIn(word, notices[0].lower())

    def test_a_failing_program_says_so_without_naming_the_runtime(self):
        self.install_layout()
        done = self.run_app("--app", APP, WINE_EXIT="3")
        self.assertEqual(done.returncode, 3)
        notices = [line for line in self.logged() if line.startswith("notify|")]
        self.assertEqual(len(notices), 1)
        self.assertNotIn("wine", notices[0].lower())


@unittest.skipUnless(os.environ.get("MOOS_WINDOWS_PROOF_EXE"),
                     "opt-in: MOOS_WINDOWS_PROOF_EXE=<a 64-bit .exe> runs the real runtime")
class RealRuntimeProof(Isolated):
    """Install and remove a real portable program with the image's own runtime, headless.

    The program is never started: only its prefix is created, its icon read in the sandbox, and
    everything removed again. Run on a MoOS host inside a private HOME; see the report for the
    measured times and sizes.
    """

    def test_install_and_remove_for_real(self):
        exe = Path(os.environ["MOOS_WINDOWS_PROOF_EXE"])
        body = exe.read_bytes()
        os.environ.pop("DISPLAY", None)
        os.environ.pop("WAYLAND_DISPLAY", None)
        os.environ["PATH"] = "/usr/bin:/bin"
        url = "https://publisher.example/" + exe.name
        opener = Opener()
        opener.files[url] = body
        recipe = {"id": APP, "source": "moos", "en": "Proof", "ar": "إثبات", "cat": "win",
                  "engine": "windows", "arch": ["x86_64"],
                  "install": {"kind": "windows-portable", "version": "1", "exe": exe.name,
                              "downloads": {"x86_64": {"url": url, "sha256": hashlib.sha256(body).hexdigest(),
                                                       "size": len(body)}},
                              "risk": "downloaded-executable", "requires_review": True, "external": True}}
        path = self.base / "catalog.json"
        path.write_text(json.dumps({"apps": [recipe]}), encoding="utf-8")
        controller = MODULE.Controller(MODULE.JobStore(self.home / ".cache/moos-store"),
                                       adapter_factory=lambda: None, catalog_path=path, opener=opener)
        started = time.monotonic()
        with mock.patch.object(appdrop, "_refresh_menu", lambda: None):
            code, result = controller.install([APP])
        took = time.monotonic() - started
        self.assertEqual(result["state"], "success", result)
        base = self.windows / APP
        size = subprocess.run(["du", "-sm", str(base / "prefix")], capture_output=True, text=True).stdout.split()[0]
        launcher = (self.home / f".local/share/applications/org.moos.windows.{APP}.desktop").read_text(encoding="utf-8")
        icon = base / "icon.png"
        print(f"\nreal install: {took:.1f}s, prefix {size} MB, icon extracted: {icon.is_file()}",
              file=sys.stderr)
        self.assertTrue((base / "prefix/system.reg").is_file())
        self.assertIn(f"Exec=/usr/bin/moos-run-foreign --app {APP}", launcher)
        if icon.is_file():
            self.assertEqual(icon.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertIn(f"Icon={icon}", launcher)
        with mock.patch.object(appdrop, "_refresh_menu", lambda: None):
            code, result = controller.remove(APP)
        self.assertEqual(result["state"], "success", result)
        self.assertFalse(base.exists())
        leftovers = subprocess.run(["pgrep", "-f", str(base)], capture_output=True, text=True).stdout
        self.assertEqual(leftovers.strip(), "", "a runtime process outlived the removal")


if __name__ == "__main__":
    unittest.main(verbosity=2)
