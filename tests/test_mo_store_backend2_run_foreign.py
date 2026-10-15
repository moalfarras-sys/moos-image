#!/usr/bin/env python3
"""moos-run-foreign never lets the Windows runtime write menu entries or file associations.

Double-clicking any .exe runs it in one shared prefix (~/.local/share/moos/windows). Wine's own
menu builder runs whenever a prefix is made or updated ("winemenubuilder.exe -a -r" in its
RunServices) and writes wine-extension-*.desktop launchers and MIME packages into the person's
home: an earlier audit found .vbs and .crt files opening with the Windows runtime because of
them. Every runtime start in moos-run-foreign now carries the same override set, with
`winemenubuilder.exe=d` — the shared prefix, the density step that creates it, a Store
program's own prefix and the 32-bit compatibility probe alike. The set is spelled out at each
start: other gates run single functions of the script on their own under `set -u`, where a
top-level variable would be unbound (tests/test_app_engines.py went red on exactly that).

  EveryStart       the script's own text: each runtime start carries the one set, which disables
                   the menu builder; the functions still run on their own under `set -u`;
  WithAStubRuntime the double-click path and a Store program's path, run for real with a
                   recording runtime on PATH: every start carried the override;
  WhenItFails      what the person is told when a program fails or is missing, with a stub
                   runtime and a recording notify-send: only what is known, and the Store is
                   «متجر MoOS» in Arabic;
  RealMenuBuilder  opt-in (MOOS_WINE_MENU_PROOF=<a scratch folder>): Wine's own menu builder in a
                   private HOME, headless — without the override it writes the wine-extension
                   launchers (.vbs and .crt among them), with the script's overrides it writes
                   nothing. No third-party program exists or runs.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "system_files/usr/bin/moos-run-foreign"
INSPECT = ROOT / "system_files/usr/bin/moos-inspect"
SOURCE = RUNNER.read_text(encoding="utf-8")


def runtime_starts() -> list[str]:
    """Each command line (continuations joined) that starts the Windows runtime."""
    joined = re.sub(r"\\\n\s*", " ", SOURCE)
    return [line.strip() for line in joined.splitlines()
            if not line.lstrip().startswith("#") and re.search(r"(?:^|\s)wine\s", line)]


def overrides() -> str:
    """The one override set every runtime start carries."""
    values = {value for start in runtime_starts()
              for value in re.findall(r'WINEDLLOVERRIDES="([^"]*)"', start)}
    assert len(values) == 1, f"the runtime starts do not carry one override set: {values}"
    return values.pop()


def function(name: str) -> str:
    start = SOURCE.index(f"{name}() {{")
    return SOURCE[start:SOURCE.index("\n}\n", start) + 3]


def inspect_reads_foreign_logs() -> bool:
    """Whether a Mo AI tool can read a Windows program's own log yet (moos-inspect's LOGS)."""
    logs = re.search(r"^LOGS = \{(.*?)^\}", INSPECT.read_text(encoding="utf-8"), re.S | re.M)
    return bool(logs) and "moos-foreign" in logs.group(1)


class EveryStart(unittest.TestCase):
    def test_the_override_set_disables_the_menu_builder(self):
        parts = overrides().split(";")
        self.assertIn("winemenubuilder.exe=d", parts)
        self.assertIn("mscoree,mshtml=", parts)

    def test_every_runtime_start_carries_it_and_nothing_else(self):
        starts = runtime_starts()
        # The density step (which also creates a new prefix), the double-click run, a Store
        # program's run and the 32-bit compatibility probe.
        self.assertGreaterEqual(len(starts), 4, starts)
        for start in starts:
            with self.subTest(start=start[:80]):
                self.assertIn(f'WINEDLLOVERRIDES="{overrides()}"', start)
                self.assertEqual(start.count("WINEDLLOVERRIDES="), 1, "a second override set")
        for probe in ('wine reg add', 'wine "$target"', 'wine "$real"', 'wine "$probe"'):
            self.assertTrue(any(probe in start for start in starts), f"{probe} is not covered")

    def test_each_function_still_runs_on_its_own_under_set_u(self):
        """Other gates run single functions of this script; nothing they use may live outside."""
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            (base / "bin").mkdir()
            stubs = {"wine": 'printf "%s\\n" "$WINEDLLOVERRIDES" >>"$CALLS"\n',
                     "xrdb": 'printf "Xft.dpi:\\t96\\n"\n'}
            for name, body in stubs.items():
                (base / "bin" / name).write_text("#!/bin/sh\n" + body, encoding="utf-8")
                (base / "bin" / name).chmod(0o755)
            (base / "prefix").mkdir()
            harness = ("set -uo pipefail\n" + function("wine_display_dpi") + function("wine_prepare_display")
                       + f'wine_prepare_display "{base / "prefix"}" "{base}"\n')
            done = subprocess.run(["bash", "-c", harness], capture_output=True, text=True, timeout=30,
                                  env={"PATH": f"{base / 'bin'}:/usr/bin:/bin", "CALLS": str(base / "calls")})
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual((base / "calls").read_text().split(), [overrides()])


@unittest.skipUnless(Path("/bin/bash").exists(), "needs bash")
class WithAStubRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.bindir = base / "bin"
        self.bindir.mkdir()
        self.calls = base / "calls.log"
        stubs = {
            "wine": 'printf "wine|%s|%s|%s\\n" "$WINEPREFIX" "$WINEDLLOVERRIDES" "$*" >>"$CALLS"\n'
                    'mkdir -p "$WINEPREFIX"; touch "$WINEPREFIX/user.reg"\n',
            "xrdb": 'printf "Xft.dpi:\\t144\\n"\n',
            "notify-send": "exit 0\n",
            "kdialog": "exit 1\n",
        }
        for name, body in stubs.items():
            (self.bindir / name).write_text("#!/bin/bash\n" + body, encoding="utf-8")
            (self.bindir / name).chmod(0o755)

    def run_foreign(self, *argv: str) -> subprocess.CompletedProcess:
        environment = {"HOME": str(self.home), "PATH": f"{self.bindir}:/usr/bin:/bin",
                       "XDG_DATA_HOME": str(self.home / ".local/share"),
                       "XDG_STATE_HOME": str(self.home / ".local/state"),
                       "XDG_CACHE_HOME": str(self.home / ".cache"), "CALLS": str(self.calls)}
        return subprocess.run(["bash", str(RUNNER), *argv], env=environment, text=True,
                              capture_output=True, timeout=60)

    def starts(self) -> list[list[str]]:
        lines = self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []
        return [line.split("|", 3) for line in lines if line.startswith("wine|")]

    def test_the_double_click_path_in_the_shared_prefix(self):
        program = self.home / "Downloads/setup.exe"
        program.parent.mkdir()
        program.write_bytes(b"MZ")
        done = self.run_foreign("--wine-run", str(program))
        self.assertEqual(done.returncode, 0, done.stderr)
        starts = self.starts()
        self.assertEqual([args.split()[0] for _tag, _prefix, _overrides, args in starts],
                         ["reg", str(program)], "the density step (which creates the prefix) and the run")
        for _tag, prefix, given, _args in starts:
            self.assertEqual(prefix, str(self.home / ".local/share/moos/windows"))
            self.assertEqual(given, overrides())

    def test_a_store_programs_own_prefix(self):
        app = "tinyterm"
        base = self.home / ".local/share/moos/windows-apps" / app
        (base / "app").mkdir(parents=True)
        (base / "app/tinyterm.exe").write_bytes(b"MZ")
        (base / "prefix").mkdir()
        (base / "prefix/system.reg").write_text("WINE REGISTRY Version 2\n")
        (base.parent / f"{app}.json").write_text(json.dumps({"schema": 1, "id": app, "exe": "tinyterm.exe"}))
        done = self.run_foreign("--app", app)
        self.assertEqual(done.returncode, 0, done.stderr)
        starts = self.starts()
        self.assertEqual(len(starts), 2, starts)
        for _tag, prefix, given, _args in starts:
            self.assertEqual((prefix, given), (str(base / "prefix"), overrides()))


@unittest.skipUnless(Path("/bin/bash").exists(), "needs bash")
class WhenItFails(unittest.TestCase):
    """What a person is told when a Windows program does not run is true.

    A Windows program that exits with an error (a Store-installed one, or a double-clicked .exe)
    raised "This program could not be opened. Mo AI can inspect the problem." Neither half held:

      * the program's output goes only to ~/.local/state/moos-foreign/<id>.log (windows-last.log
        for a double-clicked file), and no Mo AI tool reads it: moos-inspect's named logs are
        moai, theme, store and remote, the output never reaches the journal, and no skill names
        it — so the inspection the notice promised could not happen;
      * the notice fires on ANY non-zero exit of the program itself, so a program that opened,
        ran and then closed with an error was reported as one that "could not be opened".

    The notices now say "could not be opened, or it closed with an error" and promise no
    inspection while moos-inspect has no log for these files (checked here, so the promise can
    come back with the tool). The double-click notice also no longer says "Nothing was installed":
    the program it reports on may be an installer that ran. And the Store is called by its Arabic
    name, «متجر MoOS», as its launcher, notifications and search entry call it. A private home, a
    recording notify-send and a stub Windows runtime: nothing of the owner's is touched.
    """

    CLOSED = ("أُغلق بخطأ", "or it closed with an error")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.home = base / "home"
        self.home.mkdir()
        self.bindir = base / "bin"
        self.bindir.mkdir()
        self.notices = base / "notices.log"
        stubs = {
            # The program itself fails (exit 3) after the runtime started it.
            "wine": 'case "$1" in reg) mkdir -p "$WINEPREFIX"; touch "$WINEPREFIX/user.reg"; exit 0 ;; esac\n'
                    'echo "the program wrote this" >&2\nexit 3\n',
            "xrdb": 'printf "Xft.dpi:\\t96\\n"\n',
            "notify-send": f'for last in "$@"; do :; done\nprintf "%s\\n" "$last" >> "{self.notices}"\n',
            "kdialog": "exit 1\n",
        }
        for name, body in stubs.items():
            (self.bindir / name).write_text("#!/bin/bash\n" + body, encoding="utf-8")
            (self.bindir / name).chmod(0o755)

    def run_foreign(self, *argv: str) -> tuple[subprocess.CompletedProcess, list[str]]:
        environment = {"HOME": str(self.home), "PATH": f"{self.bindir}:/usr/bin:/bin",
                       "XDG_DATA_HOME": str(self.home / ".local/share"),
                       "XDG_STATE_HOME": str(self.home / ".local/state"),
                       "XDG_CACHE_HOME": str(self.home / ".cache")}
        done = subprocess.run(["bash", str(RUNNER), *argv], env=environment, text=True,
                              capture_output=True, timeout=60)
        said = self.notices.read_text(encoding="utf-8").splitlines() if self.notices.exists() else []
        return done, said

    def store_program(self, app: str, *, files: bool = True) -> None:
        base = self.home / ".local/share/moos/windows-apps" / app
        (base / "app").mkdir(parents=True)
        if files:
            (base / "app/tinyterm.exe").write_bytes(b"MZ")
        (base / "prefix").mkdir()
        (base / "prefix/system.reg").write_text("WINE REGISTRY Version 2\n")
        (base.parent / f"{app}.json").write_text(json.dumps({"schema": 1, "id": app,
                                                             "exe": "tinyterm.exe"}))

    def check_failure_notice(self, said: list[str]) -> None:
        self.assertEqual(len(said), 1, said)
        for words in self.CLOSED:
            self.assertIn(words, said[0])
        if not inspect_reads_foreign_logs():
            self.assertNotIn("Mo AI", said[0], "no Mo AI tool can read this program's log")

    def test_a_store_program_that_fails_says_so_truthfully(self):
        self.store_program("tinyterm")
        done, said = self.run_foreign("--app", "tinyterm")
        self.assertEqual(done.returncode, 3, done.stderr)
        self.check_failure_notice(said)
        self.assertEqual(said[0], "تعذّر فتح البرنامج أو أُغلق بخطأ. | "
                                  "This program could not be opened, or it closed with an error.")
        log = self.home / ".local/state/moos-foreign/tinyterm.log"
        self.assertIn("the program wrote this", log.read_text(encoding="utf-8"),
                      "the program's own output is still kept for whoever looks")

    def test_a_double_clicked_program_that_fails_says_so_truthfully(self):
        program = self.home / "Downloads/setup.exe"
        program.parent.mkdir()
        program.write_bytes(b"MZ")
        done, said = self.run_foreign("--wine-run", str(program))
        self.assertEqual(done.returncode, 3, done.stderr)
        self.check_failure_notice(said)
        self.assertNotIn("Nothing was installed", said[0], "an installer may have run")
        self.assertNotIn("لم يُثبّت شيء", said[0])

    def test_the_store_is_called_by_its_arabic_name(self):
        done, said = self.run_foreign("--app", "notinstalled")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertEqual(said, ["هذا البرنامج غير مثبّت. ثبّته من متجر MoOS. | "
                                "This program is not installed. Install it from Mo Store."])
        self.notices.unlink()
        self.store_program("emptyprog", files=False)
        done, said = self.run_foreign("--app", "emptyprog")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertEqual(said, ["ملفات هذا البرنامج ناقصة. أعد تثبيته من متجر MoOS. | "
                                "This program's files are incomplete. Reinstall it from Mo Store."])

    def test_no_notice_in_the_script_promises_an_inspection_nobody_can_do(self):
        notices = re.findall(r'notify "([^"]*)"', SOURCE)
        self.assertGreaterEqual(len(notices), 6, notices)
        if not inspect_reads_foreign_logs():
            self.assertEqual([text for text in notices if "Mo AI" in text], [])
        self.assertEqual([text for text in notices if re.search(r"متجر Mo(?!OS)", text)], [])


@unittest.skipUnless(shutil.which("wine") and shutil.which("wineserver"), "needs the Windows runtime")
@unittest.skipUnless(__import__("os").environ.get("MOOS_WINE_MENU_PROOF"),
                     "opt-in: MOOS_WINE_MENU_PROOF=<a scratch folder on disk>")
class RealMenuBuilder(unittest.TestCase):
    """Headless, in a private HOME: Wine's own menu builder, with and without the override."""

    def build_menus(self, given: str) -> list[str]:
        import os
        where = Path(os.environ["MOOS_WINE_MENU_PROOF"])
        base = Path(tempfile.mkdtemp(prefix="menu-proof-", dir=where))
        self.addCleanup(shutil.rmtree, base, ignore_errors=True)
        home = base / "home"
        prefix = home / ".local/share/moos/windows"
        prefix.mkdir(parents=True)
        environment = {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                       "XDG_DATA_HOME": str(home / ".local/share"), "XDG_CONFIG_HOME": str(home / ".config"),
                       "XDG_CACHE_HOME": str(home / ".cache"), "WINEPREFIX": str(prefix),
                       "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent", "WINEDEBUG": "-all"}
        headless = ";winex11.drv,winewayland.drv=d"
        setup = dict(environment, WINEDLLOVERRIDES=overrides() + headless)
        subprocess.run(["timeout", "--kill-after=10", "300", "wine", "wineboot", "--init"], env=setup,
                       capture_output=True)
        subprocess.run(["timeout", "120", "wineserver", "-w"], env=setup)
        run = dict(environment, WINEDLLOVERRIDES=given + headless)
        subprocess.run(["timeout", "--kill-after=10", "120", "wine", "winemenubuilder.exe", "-a", "-r"],
                       env=run, capture_output=True)
        subprocess.run(["timeout", "120", "wineserver", "-w"], env=run)
        return sorted(path.name for path in home.rglob("wine-extension-*"))

    def test_the_override_is_what_stops_the_menu_builder(self):
        written = self.build_menus("mscoree,mshtml=")
        self.assertIn("wine-extension-vbs.desktop", written, "the control did not reproduce the audit")
        self.assertIn("wine-extension-crt.desktop", written)
        self.assertEqual(self.build_menus(overrides()), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
