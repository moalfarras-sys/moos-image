#!/usr/bin/env python3
"""Gate: a headless account can choose the size of its desktop, and choosing never costs it the screen.

WHY THIS EXISTS

A machine with no monitor has no native resolution: its compositor draws whatever size it was
started with. That was 1920x1080 for every cloud account, written in three places and changeable
in none — while Mo PC Remote on Auto sends 1280 px wide on a machine without a GPU. So the picture
on the owner's phone was a 1080p desktop pushed through a 1.5:1 bilinear scaler, and the scaler
was most of the encode path. Measured on the Oracle A1 on 2026-10-04, same busy window:

    desktop 1920x1080, scaled to 1280x720   37.7 frames/s   encode path 64.6% of a core
    desktop 1280x720,  sent as it is        47.3 frames/s   encode path 41.5%

`moos-cloud-desktop display` writes the size into the account's own compositor drop-in.

WHAT IT MUST NEVER DO

On that machine the compositor is the owner's only screen, and restarting it closes every window
they have open. So the one thing this command may tell systemd is `daemon-reload`. It must also
leave a hand-written compositor override alone, refuse anything that is not a size, and keep
recognising the drop-ins that `own` and the ARM image actually write — the day one of those
changes shape, this gate fails instead of the command quietly refusing on every machine.

The real script is run with bash against a scratch HOME; `systemctl` and `id` are stand-ins.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "system_files/usr/bin/moos-cloud-desktop"
ARM_BUILD = ROOT / "build_files/build-arm.sh"
BASH = shutil.which("bash") or "/bin/bash"

ARM_DROPIN = """[Service]
Environment=LIBGL_ALWAYS_SOFTWARE=1
ExecStart=
ExecStart=/usr/bin/kwin_wayland_wrapper --virtual --width 1920 --height 1080 --xwayland
"""
FORBIDDEN = ("restart", "stop", "start", "kill", "isolate", "reload-or-restart", "try-restart",
             "terminate-session", "reboot", "poweroff")


class DisplaySize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        self.bin = Path(self.tmp.name) / "bin"
        self.dropdir = self.home / ".config/systemd/user/plasma-kwin_wayland.service.d"
        self.dropdir.mkdir(parents=True)
        self.bin.mkdir()
        self.log = Path(self.tmp.name) / "systemctl.log"
        self.stub("systemctl", f'#!/bin/sh\necho "$@" >> "{self.log}"\n')
        self.uid = "1000"
        self.dropin = self.dropdir / "20-moos-arm-virtual-output.conf"
        self.dropin.write_text(ARM_DROPIN, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)

    def run_tool(self, *args):
        self.stub("id", f'#!/bin/sh\n[ "$1" = "-u" ] && echo {self.uid} || exec /usr/bin/id "$@"\n')
        env = {"HOME": str(self.home), "PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin",
               "XDG_STATE_HOME": str(self.home / ".local/state"), "LANG": "C.UTF-8"}
        return subprocess.run([BASH, str(TOOL), "display", *args], env=env, capture_output=True,
                              text=True, timeout=30)

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def start_line(self, path=None):
        lines = [l for l in (path or self.dropin).read_text(encoding="utf-8").splitlines()
                 if l.startswith("ExecStart=/")]
        self.assertEqual(len(lines), 1)
        return lines[0]

    def test_asking_changes_nothing_and_says_what_auto_will_do(self):
        state = self.home / ".local/state"
        state.mkdir(parents=True)
        (state / "moos-visual-tier.json").write_text(
            '{"tier": "essential", "budget": {"remote_encode": "1280x720@30"}}', encoding="utf-8")
        done = self.run_tool()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("1920x1080", done.stdout)
        self.assertIn("scaled down", done.stdout, "a 1920 desktop under a 1280 budget is not 1:1")
        self.assertIn("phone", done.stdout)
        self.assertEqual(self.dropin.read_text(encoding="utf-8"), ARM_DROPIN)
        self.assertFalse([c for c in self.calls() if "daemon-reload" in c], "a question is not a change")

    def test_phone_rewrites_only_the_two_numbers_and_restarts_nothing(self):
        done = self.run_tool("phone")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.start_line(),
                         "ExecStart=/usr/bin/kwin_wayland_wrapper --virtual --width 1280 --height 720 --xwayland")
        self.assertEqual(self.dropin.read_text(encoding="utf-8"),
                         ARM_DROPIN.replace("--width 1920 --height 1080", "--width 1280 --height 720"),
                         "everything but the size must survive: the software-GL environment line and "
                         "the empty ExecStart= that clears the stock command are what keep the screen up")
        self.assertIn("next sign-in", done.stdout)
        self.assertIn("--user daemon-reload", self.calls())
        for call in self.calls():
            words = call.split()
            self.assertFalse([w for w in words if w in FORBIDDEN],
                             f"systemctl {call}: the compositor is the owner's only screen")
        # asking afterwards reports 1:1 for the same budget
        state = self.home / ".local/state"
        state.mkdir(parents=True)
        (state / "moos-visual-tier.json").write_text(
            '{"budget": {"remote_encode": "1280x720@30"}}', encoding="utf-8")
        self.assertIn("1:1", self.run_tool().stdout)

    def test_desk_brings_the_original_file_back_byte_for_byte(self):
        self.assertEqual(self.run_tool("phone").returncode, 0)
        self.assertEqual(self.run_tool("desk").returncode, 0)
        self.assertEqual(self.dropin.read_text(encoding="utf-8"), ARM_DROPIN)

    def test_an_explicit_size_is_taken_and_the_same_size_twice_is_not_a_change(self):
        self.assertEqual(self.run_tool("1600x900").returncode, 0)
        self.assertIn("--width 1600 --height 900 --xwayland", self.start_line())
        before = len(self.calls())
        again = self.run_tool("1600x900")
        self.assertEqual(again.returncode, 0)
        self.assertIn("already", again.stdout)
        self.assertEqual(len(self.calls()), before)

    def test_what_is_not_a_size_is_refused_and_nothing_is_written(self):
        for bad in ("100x100", "9999x9999", "1281x720", "1280x721", "1280", "x720", "phone;id",
                    "1280x720;reboot", "--width", "$(id)", "1280x720 --replace", "tablet", "-h"):
            done = self.run_tool(bad)
            self.assertNotEqual(done.returncode, 0, f"{bad!r} was accepted")
            self.assertEqual(self.dropin.read_text(encoding="utf-8"), ARM_DROPIN, f"{bad!r} wrote")
        self.assertEqual(self.calls(), [], "a refusal must not touch systemd")

    def test_a_hand_written_override_is_somebody_elses_decision(self):
        mine = ("[Service]\nExecStart=\n"
                "ExecStart=/usr/bin/kwin_wayland --virtual --width 1920 --height 1080 --scale 2\n")
        self.dropin.write_text(mine, encoding="utf-8")
        done = self.run_tool("phone")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("virtual display", done.stderr)
        self.assertEqual(self.dropin.read_text(encoding="utf-8"), mine)

    def test_a_desktop_with_a_real_screen_is_told_why_and_left_alone(self):
        self.dropin.unlink()
        done = self.run_tool("phone")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("real screen", done.stderr)
        self.assertEqual(list(self.dropdir.iterdir()), [])

    def test_the_drop_in_that_own_writes_is_recognised_too(self):
        self.dropin.unlink()
        own = self.dropdir / "20-moos-virtual-output.conf"
        own.write_text(ARM_DROPIN, encoding="utf-8")
        self.assertEqual(self.run_tool("phone").returncode, 0)
        self.assertIn("--width 1280 --height 720", self.start_line(own))

    def test_root_is_sent_back_to_the_account(self):
        self.uid = "0"
        done = self.run_tool("phone")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("without sudo", done.stderr)
        self.assertEqual(self.dropin.read_text(encoding="utf-8"), ARM_DROPIN)


class TheGeneratorsStillWriteWhatItRecognises(unittest.TestCase):
    """`display` edits only a drop-in it recognises. If `own` or the ARM image starts writing a
    different command line, every cloud account would be refused — silently, on the machine."""

    def test_both_generated_drop_ins_match_the_recognised_form(self):
        tool = TOOL.read_text(encoding="utf-8")
        found = re.search(r"^DISPLAY_START='(.+)'$", tool, re.M)
        self.assertIsNotNone(found, "the recognised form is no longer one declared pattern")
        recognised = re.compile(found.group(1))
        written = [line for source in (tool, ARM_BUILD.read_text(encoding="utf-8"))
                   for line in source.splitlines()
                   if line.startswith("ExecStart=/usr/bin/kwin_wayland_wrapper --virtual")]
        self.assertGreaterEqual(len(written), 2, "neither generator writes a virtual compositor any more")
        for line in written:
            self.assertRegex(line, recognised)

    def test_the_command_is_documented_where_help_prints_it(self):
        done = subprocess.run([BASH, str(TOOL), "--help"], capture_output=True, text=True, timeout=30)
        self.assertIn("display [phone|desk|WIDTHxHEIGHT]", done.stdout)
        self.assertIn("grant-input", done.stdout, "the help window dropped a line when one was added")


if __name__ == "__main__":
    unittest.main(verbosity=1)
