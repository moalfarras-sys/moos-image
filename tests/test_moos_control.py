#!/usr/bin/env python3
"""Gate: everyday control — moos-control, its moos:// routes and Mo AI's buttons.

WHY THIS EXISTS
Mo AI could repair, update and install, but could not do what people ask an
assistant for every day: turn the volume down, dim the screen, night light on,
take a screenshot. `moos-control` adds those as fixed, reversible, user-level
actions. Three promises are gated here:

1. Every action runs ONE fixed argv, and any other input — out of range, extra
   words, shell syntax — is refused before a single command runs.
2. moos-open accepts only the exact route shapes, and Wi-Fi OFF (which cuts the
   internet, Mo AI and remote control) never runs without the user's Yes — with
   no dialog tool it fails closed.
3. Mo AI shows control commands as buttons and never runs model text by itself.

Measured live on the daily driver, 2026-09-12: `moos-control volume 40` read back
0.40, `moos://control/volume/35` read back 0.35, `moos://control/volume/35;reboot`
exited 2 with the volume unchanged, and `brightness 95` set the Philips monitor
to 9500/10000 over Plasma's ScreenBrightness service.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "system_files/usr/bin/moos-control"
OPEN = ROOT / "system_files/usr/bin/moos-open"
MOAI = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"

# One write per call: detached actions (a theme, an app) record while the next
# command records, and three separate appends interleaved into "moos-themelogger".
RECORDER = r'''#!/bin/sh
line="${0##*/}"
for arg in "$@"; do line="$line$(printf '\t%s' "$arg")"; done
printf '%s\n' "$line" >> "$STUB_LOG"
'''

STUBS = {
    "wpctl": 'case "$1" in get-volume) echo "Volume: 0.40";; esac\n',
    "busctl": '''case "$*" in
  *DisplaysDBusNames*) echo '{"type":"as","data":["display0"]}';;
  *MaxBrightness*) echo '{"type":"i","data":10000}';;
  *get-property*Brightness*) echo '{"type":"i","data":5000}';;
  *NightLight*running*) echo '{"type":"b","data":true}';;
esac
''',
    "kwriteconfig6": "",
    "nmcli": 'case "$*" in "radio wifi") echo enabled;; esac\n',
    "bluetoothctl": 'case "$1" in show) echo "Powered: yes";; esac\n',
    "rfkill": "",
    "spectacle": "",
    "logger": "",
    "moos-theme": "",
    "gtk-launch": "",
    "flatpak": 'case "$1 $2" in "info org.mozilla.firefox") exit 0;; info*) exit 1;; esac\n',
    "xdg-user-dir": 'echo "$STUB_PICTURES"\n',
    "moos-control": "",
    "kdialog": 'case "$*" in *warningyesno*) exit "${KDIALOG_ANSWER:-1}";; esac\n',
}


class StubMachine:
    def __init__(self, omit=()):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls.log"
        self.log.touch()
        self.pictures = self.root / "Pictures"
        for name, body in STUBS.items():
            if name in omit:
                continue
            path = self.bin / name
            path.write_text(RECORDER + body)
            path.chmod(0o755)

    def env(self, **extra):
        return {
            "PATH": str(self.bin),
            "HOME": str(self.root),
            "STUB_LOG": str(self.log),
            "STUB_PICTURES": str(self.pictures),
            "XDG_DATA_HOME": str(self.root / "share"),
            "XDG_DATA_DIRS": str(self.root / "system-share"),
            "LANG": "C.UTF-8",
            **extra,
        }

    def calls(self, settle=0.0):
        deadline = time.monotonic() + settle
        while True:
            lines = [line.split("\t") for line in self.log.read_text().splitlines()]
            if time.monotonic() >= deadline:
                return lines
            time.sleep(0.05)

    def close(self):
        self.dir.cleanup()


class MoosControlTests(unittest.TestCase):
    def setUp(self):
        self.machine = StubMachine()

    def tearDown(self):
        self.machine.close()

    def control(self, *args, machine=None):
        machine = machine or self.machine
        return subprocess.run([sys.executable, str(CONTROL), *args], env=machine.env(),
                              capture_output=True, text=True, timeout=30)

    def test_volume_sets_exact_level_unmutes_and_audits(self):
        result = self.control("volume", "40")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.machine.calls()
        self.assertIn(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "0.40"], calls)
        self.assertIn(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], calls)
        self.assertIn(["logger", "-t", "moos-control", "volume 40"], calls)
        self.assertIn("40%", result.stdout)

    def test_volume_steps_are_relative_and_capped(self):
        self.assertEqual(self.control("volume", "down").returncode, 0)
        self.assertIn(["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", "10%-"],
                      self.machine.calls())

    def test_invalid_requests_run_nothing(self):
        for args in (("volume", "101"), ("volume", "-1"), ("volume", "4O"),
                     ("volume", "30;reboot"), ("volume", "30", "extra"), ("brightness", "4"),
                     ("night-light", "maybe"), ("wifi", "toggle"), ("theme", "rm"),
                     ("open", "../etc"), ("reboot",), ()):
            with self.subTest(args=args):
                result = self.control(*args)
                self.assertEqual(result.returncode, 2, (args, result.stdout, result.stderr))
        acting = [call for call in self.machine.calls() if call[0] != "flatpak"]
        self.assertEqual(acting, [], "an invalid request reached a real command")

    def test_brightness_targets_every_display_through_screen_brightness(self):
        self.assertEqual(self.control("brightness", "70").returncode, 0)
        self.assertIn(["busctl", "--user", "call", "org.kde.ScreenBrightness",
                       "/org/kde/ScreenBrightness/display0", "org.kde.ScreenBrightness.Display",
                       "SetBrightness", "iu", "7000", "0"], self.machine.calls())

    def test_brightness_up_is_relative_to_the_current_level(self):
        self.assertEqual(self.control("brightness", "up").returncode, 0)
        sets = [call for call in self.machine.calls() if "SetBrightness" in call]
        self.assertEqual(sets[-1][-2:], ["6000", "0"])

    def test_night_light_modes_write_kwin_config_and_reconfigure(self):
        write = ["kwriteconfig6", "--file", "kwinrc", "--group", "NightColor"]
        reconfigure = ["busctl", "--user", "--expect-reply=no", "call", "org.kde.KWin",
                       "/KWin", "org.kde.KWin", "reconfigure"]
        expected = {
            "on": [[*write, "--key", "Active", "--type", "bool", "true"],
                   [*write, "--key", "Mode", "Constant"], reconfigure],
            "auto": [[*write, "--key", "Active", "--type", "bool", "true"],
                     [*write, "--key", "Mode", "DarkLight"], reconfigure],
            "off": [[*write, "--key", "Active", "--type", "bool", "false"], reconfigure],
        }
        for mode, calls in expected.items():
            with self.subTest(mode=mode):
                self.machine.log.write_text("")
                self.assertEqual(self.control("night-light", mode).returncode, 0)
                acting = [call for call in self.machine.calls() if call[0] != "logger"]
                self.assertEqual(acting, calls)

    def test_radios_and_screenshot_use_fixed_commands(self):
        self.assertEqual(self.control("wifi", "off").returncode, 0)
        self.assertEqual(self.control("bluetooth", "on").returncode, 0)
        result = self.control("screenshot")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.machine.calls()
        self.assertIn(["nmcli", "radio", "wifi", "off"], calls)
        self.assertIn(["rfkill", "unblock", "bluetooth"], calls)
        self.assertIn(["bluetoothctl", "power", "on"], calls)
        shot = [call for call in calls if call[0] == "spectacle"][0]
        self.assertEqual(shot[1:5], ["--background", "--nonotify", "--fullscreen", "--output"])
        self.assertTrue(shot[5].startswith(str(self.machine.pictures / "Screenshots" / "MoOS-")))

    def test_theme_and_open_reuse_the_existing_fixed_actions(self):
        self.assertEqual(self.control("theme", "nova").returncode, 0)
        self.assertEqual(self.control("open", "org.mozilla.firefox").returncode, 0)
        calls = self.machine.calls(settle=1.0)
        self.assertIn(["moos-theme", "nova"], calls)
        self.assertIn(["flatpak", "run", "org.mozilla.firefox"], calls)
        missing = self.control("open", "org.example.NotInstalled")
        self.assertEqual(missing.returncode, 69)

    def test_missing_tool_is_reported_as_unavailable(self):
        bare = StubMachine(omit=("wpctl",))
        try:
            result = self.control("volume", "40", machine=bare)
            self.assertEqual(result.returncode, 69)
            self.assertIn("wpctl", result.stderr)
        finally:
            bare.close()

    def test_status_is_read_only_json(self):
        result = self.control("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "volume": 40, "muted": False, "brightness": 50,
            "night_light": True, "wifi": True, "bluetooth": True})
        self.assertFalse([call for call in self.machine.calls() if call[0] == "logger"],
                         "status must not write an audit entry")


class MoosOpenControlRouteTests(unittest.TestCase):
    def setUp(self):
        self.machine = StubMachine()

    def tearDown(self):
        self.machine.close()

    def open(self, url, **env):
        environment = self.machine.env(**env)
        environment["PATH"] = f"{self.machine.bin}:/usr/bin:/bin"
        return subprocess.run(["bash", str(OPEN), url], env=environment,
                              capture_output=True, text=True, timeout=30)

    def control_calls(self):
        return [call[1:] for call in self.machine.calls() if call[0] == "moos-control"]

    def test_exact_routes_reach_moos_control(self):
        for url, argv in (("moos://control/volume/35", ["volume", "35"]),
                          ("moos://control/volume/up", ["volume", "up"]),
                          ("moos://control/brightness/80", ["brightness", "80"]),
                          ("moos://control/night-light/auto", ["night-light", "auto"]),
                          ("moos://control/bluetooth/off", ["bluetooth", "off"]),
                          ("moos://control/mute", ["mute"]),
                          ("moos://control/screenshot", ["screenshot"])):
            with self.subTest(url=url):
                self.machine.log.write_text("")
                self.open(url)
                self.assertEqual(self.control_calls(), [argv])

    def test_malformed_routes_never_reach_moos_control(self):
        for url in ("moos://control/volume/350", "moos://control/volume/35;reboot",
                    "moos://control/volume/", "moos://control/brightness/-5",
                    "moos://control/night-light/party", "moos://control/reboot"):
            with self.subTest(url=url):
                self.open(url)
        self.assertEqual(self.control_calls(), [])

    def test_wifi_off_requires_the_users_yes(self):
        self.open("moos://control/wifi/off", KDIALOG_ANSWER="1")
        self.assertEqual(self.control_calls(), [], "Wi-Fi off ran without confirmation")
        self.open("moos://control/wifi/off", KDIALOG_ANSWER="0")
        self.assertEqual(self.control_calls(), [["wifi", "off"]])

    def test_wifi_off_fails_closed_without_a_dialog_tool(self):
        (self.machine.bin / "kdialog").unlink()
        environment = self.machine.env()
        environment["PATH"] = str(self.machine.bin)
        subprocess.run(["/bin/bash", str(OPEN), "moos://control/wifi/off"], env=environment,
                       capture_output=True, text=True, timeout=30)
        self.assertEqual(self.control_calls(), [])


class MoaiControlButtonTests(unittest.TestCase):
    def setUp(self):
        self.qml = MOAI.read_text(encoding="utf-8")

    def test_control_commands_become_buttons_not_automatic_actions(self):
        self.assertIn("const ctl = /moos-control\\s+(volume", self.qml)
        self.assertIn('return "moos://control/" + parts.join("/")', self.qml)
        self.assertIn("root.launch(root.controlUrl(modelData), root.controlLabel(modelData))",
                      self.qml)
        # The only caller of controlUrl is a button's onClicked: model text never
        # turns into an action on its own.
        callers = [line for line in self.qml.splitlines()
                   if "controlUrl(" in line and "function controlUrl" not in line]
        self.assertTrue(callers)
        self.assertTrue(all("root.launch(root.controlUrl(modelData)" in line for line in callers),
                        callers)
        self.assertNotIn("autoRunControls", self.qml)

    def test_prompt_teaches_the_same_closed_grammar(self):
        self.assertIn("`moos-control volume 40`", self.qml)
        self.assertIn("`moos-control wifi on|off` (Wi-Fi off also asks first", self.qml)


if __name__ == "__main__":
    unittest.main(verbosity=2)
