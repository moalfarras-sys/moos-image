#!/usr/bin/env python3
"""Mo AI's old terminal settings names only open the Mo AI page of System Settings.

`moai-config` was a kdialog wizard over moai-agent-api — a second front end for the brain and its
write-only key — and `moai-start` / `moai-brain-mode` ran it. Mo AI's settings are ONE page now
(SPEC D1/D5: System Settings → MoOS → Mo AI, kcm_moos_ai). The three names stay for the scripts and
habits that call them, and each does exactly one thing: `moos-settings --section=assistant`.

Each is EXECUTED here, with every program it could reach replaced by a recorder, in a private HOME,
runtime directory and bus address, so nothing reaches the owner's desktop, journal or config: the
only thing it may start is the settings page, and it may not ask for a key, write a file or log.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "system_files/usr/bin"
NAMES = ("moai-config", "moai-start", "moai-brain-mode")
# Programs a settings helper could have reached: each is a recorder, so a call is a failure.
FORBIDDEN = ("kdialog", "systemctl", "openclaw", "curl", "python3", "logger", "podman",
             "ramalama", "konsole", "notify-send")


def code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def head(text: str) -> str:
    """What runs: everything up to and including the first `exec` line."""
    lines = []
    for line in code(text).splitlines():
        lines.append(line)
        if line.lstrip().startswith("exec "):
            break
    return "\n".join(lines)


class TheOldNamesOpenTheOnePage(unittest.TestCase):
    def run_tool(self, name: str) -> tuple[subprocess.CompletedProcess, str, list[str], list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            stubs = work / "bin"
            stubs.mkdir()
            calls = work / "calls"
            opened = work / "opened"
            for program in FORBIDDEN:
                stub = stubs / program
                stub.write_text(f'#!/bin/sh\necho "{program} $*" >> "{calls}"\nexit 0\n', encoding="utf-8")
                stub.chmod(0o755)
            settings = stubs / "moos-settings"
            settings.write_text(f'#!/bin/sh\necho "$*" >> "{opened}"\nexit 0\n', encoding="utf-8")
            settings.chmod(0o755)
            runtime = work / "run"
            runtime.mkdir(mode=0o700)
            home = work / "home"
            home.mkdir()
            env = {"PATH": f"{stubs}:/usr/bin:/bin", "HOME": str(home), "XDG_RUNTIME_DIR": str(runtime),
                   "XDG_CONFIG_HOME": str(home / ".config"), "XDG_DATA_HOME": str(home / ".local/share"),
                   "XDG_STATE_HOME": str(home / ".local/state"), "LANG": "C.UTF-8",
                   "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/absent-bus"}
            result = subprocess.run(["bash", str(BIN / name)], env=env, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=20)
            opened_text = opened.read_text(encoding="utf-8") if opened.exists() else ""
            called = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
            written = sorted(str(p.relative_to(home)) for p in home.rglob("*"))
            return result, opened_text, called, written

    def test_each_name_opens_the_mo_ai_page_and_nothing_else(self) -> None:
        for name in NAMES:
            with self.subTest(tool=name):
                result, opened, called, written = self.run_tool(name)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(opened, "--section=assistant\n")
                self.assertEqual(called, [], "a settings name reached another program")
                self.assertEqual(written, [], "a settings name wrote into the home folder")
                self.assertIn("System Settings", result.stdout, "the terminal must say where settings went")
                self.assertRegex(result.stdout, r"[؀-ۿ]", "Arabic is first-class in the terminal too")

    def test_the_wizard_and_the_second_config_writer_are_gone(self) -> None:
        for name in NAMES:
            with self.subTest(tool=name):
                path = BIN / name
                self.assertTrue(os.access(path, os.X_OK), f"{name} must stay executable for its callers")
                ran = head(path.read_text(encoding="utf-8"))
                self.assertTrue(ran.rstrip().endswith("exec moos-settings --section=assistant"), ran[-300:])
                for forbidden in ("kdialog", "/api/config", "openclaw.json", "config.json", "apiKey",
                                  "botToken", "read -", "systemctl", "curl", "urllib"):
                    self.assertNotIn(forbidden, ran)
        # moai-config and moai-brain-mode carry nothing after the hand-off; moai-start's retired
        # local-brain body is dead code that other gates still read (see its header).
        for name in ("moai-config", "moai-brain-mode"):
            text = (BIN / name).read_text(encoding="utf-8")
            self.assertEqual(code(text).strip(), head(text).strip(),
                             f"{name} still carries code after its hand-off")

    def test_nothing_sends_the_owner_to_the_wizard_any_more(self) -> None:
        # The places that opened the wizard — moos-open's brain/start and do/setup-brain, and
        # moai-do setup-brain — must reach the Mo AI page themselves.
        router = code((BIN / "moos-open").read_text(encoding="utf-8"))
        for route in ("brain/start", "do/setup-brain"):
            arm = re.search(rf"(?m)^\s+{re.escape(route)}\)\s*(.*?);;", router)
            self.assertIsNotNone(arm, route)
            self.assertIn("moos-settings --section=assistant", arm.group(1), route)
            self.assertNotIn("moai-config", arm.group(1))
        moai_do = code((BIN / "moai-do").read_text(encoding="utf-8"))
        setup = moai_do.split("do_setup_brain() {", 1)[1].split("return $?", 1)[0]
        self.assertIn("open_assistant_settings", setup)
        self.assertNotIn("moai-config", setup)


if __name__ == "__main__":
    unittest.main(verbosity=2)
