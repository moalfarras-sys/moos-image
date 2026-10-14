#!/usr/bin/env python3
"""Gate: what moos-run-foreign tells a person when a Windows program does not run is true.

WHY THIS EXISTS
A Windows program that exits with an error (a Store-installed one, or a double-clicked .exe)
raised "This program could not be opened. Mo AI can inspect the problem." Neither half held:

  * the program's output goes only to ~/.local/state/moos-foreign/<id>.log (windows-last.log
    for a double-clicked file), and no Mo AI tool reads it: moos-inspect's named logs are moai,
    theme, store and remote, the output never reaches the journal, and no skill names it — so
    the inspection the notice promised could not happen;
  * the notice fires on ANY non-zero exit of the program itself, so a program that opened, ran
    and then closed with an error was reported as one that "could not be opened".

The notices now say "could not be opened, or it closed with an error" and promise no
inspection while moos-inspect has no log for these files (checked below, so the promise can
come back with the tool). The double-click notice also no longer says "Nothing was installed":
the program it reports on may be an installer that ran. And the Store is called by its Arabic
name, «متجر MoOS», as its launcher, notifications and search entry call it.

Everything runs in a private home with a recording notify-send and a stub Windows runtime;
no program, runtime or session of the owner's is touched.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "system_files/usr/bin/moos-run-foreign"
INSPECT = ROOT / "system_files/usr/bin/moos-inspect"
SOURCE = RUNNER.read_text(encoding="utf-8")
CLOSED = ("أُغلق بخطأ", "or it closed with an error")


def inspect_reads_foreign_logs() -> bool:
    """Whether a Mo AI tool can read a Windows program's own log yet (moos-inspect's LOGS)."""
    logs = re.search(r"^LOGS = \{(.*?)^\}", INSPECT.read_text(encoding="utf-8"), re.S | re.M)
    return bool(logs) and "moos-foreign" in logs.group(1)


class WhenAWindowsProgramDoesNotRun(unittest.TestCase):
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
        for words in CLOSED:
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
