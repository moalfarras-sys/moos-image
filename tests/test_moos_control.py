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
import re
import shutil
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

# The desktop's own services, isolated: every D-Bus answer comes from this stub, and the two
# states a verb changes (do not disturb, the power profile) live in files under the stub root,
# so a test proves the READ-BACK as well as the call. Nothing here reaches a real bus.
STUBS = {
    "wpctl": '''case "$1 $2" in
  "get-volume @DEFAULT_AUDIO_SOURCE@") echo "Volume: 1.00 [MUTED]";;
  get-volume*) echo "Volume: 0.40";;
esac
''',
    "busctl": '''case "$*" in
  *DisplaysDBusNames*) echo '{"type":"as","data":["display0"]}';;
  *MaxBrightness*) echo '{"type":"i","data":10000}';;
  *get-property*Brightness*) echo '{"type":"i","data":5000}';;
  *NightLight*running*) echo '{"type":"b","data":true}';;
  *NameHasOwner*org.bluez*) echo '{"type":"b","data":[true]}';;
  *"/component/kwin"*shortcutNames*) echo '{"type":"as","data":[["Overview","Grid View","Show Desktop","MoOS Arrange: halves","MoOS Arrange: thirds","MoOS Arrange: quarters","MoOS Arrange: main","MoOS Arrange: centre"]]}';;
  *"/component/plasmashell"*shortcutNames*) echo '{"type":"as","data":[["activate application launcher","toggle do not disturb"]]}';;
  *"toggle do not disturb"*) dnd=0; read -r dnd < "$STUB_ROOT/dnd" 2>/dev/null
                              if [ "$dnd" = 1 ]; then echo 0 > "$STUB_ROOT/dnd"; else echo 1 > "$STUB_ROOT/dnd"; fi;;
  *Notifications*Inhibited*) dnd=0; read -r dnd < "$STUB_ROOT/dnd" 2>/dev/null
                             if [ "$dnd" = 1 ]; then echo '{"type":"b","data":true}'; else echo '{"type":"b","data":false}'; fi;;
  *getLayoutsList*) echo '{"type":"a(sss)","data":[[["ara","ع","Arabic"],["de","DE","German"]]]}';;
  *getLayout*) echo '{"type":"u","data":[0]}';;
  *profileChoices*) echo '{"type":"as","data":[["power-saver","balanced","performance"]]}';;
  *setProfile*) for last in "$@"; do :; done; echo "$last" > "$STUB_ROOT/profile";;
  *currentProfile*) profile=balanced; read -r profile < "$STUB_ROOT/profile" 2>/dev/null
                    echo "{\\"type\\":\\"s\\",\\"data\\":[\\"$profile\\"]}";;
esac
''',
    "kwriteconfig6": "",
    "kreadconfig6": '''case "$*" in
  *AutomaticLookAndFeel*) echo false;;
  *LookAndFeelPackage*) echo org.moos.ui2.nova.light;;
esac
''',
    "nmcli": 'case "$*" in "radio wifi") echo enabled;; esac\n',
    "bluetoothctl": 'case "$1" in show) echo "Powered: yes";; esac\n',
    "rfkill": "",
    "spectacle": "",
    "logger": "",
    "moos-theme": "",
    "gtk-launch": "",
    "flatpak": 'case "$1 $2" in "info org.mozilla.firefox") exit 0;; info*) exit 1;; esac\n'
               'case "$1" in run) exit "${STUB_APP_EXIT:-0}";; esac\n',
    # The pages' own hosts, as the settings registry names them. STUB_PAGE_EXIT makes the
    # window die at once, STUB_PAGE_STAYS keeps it open past moos-control's settle window.
    "systemsettings": '[ -n "$STUB_PAGE_STAYS" ] && sleep "$STUB_PAGE_STAYS"\n'
                      'exit "${STUB_PAGE_EXIT:-0}"\n',
    "moos-settings": 'exit "${STUB_PAGE_EXIT:-0}"\n',
    "kinfocenter": 'exit "${STUB_PAGE_EXIT:-0}"\n',
    "notify-send": "",
    "xdg-user-dir": 'echo "$STUB_PICTURES"\n',
    "moos-control": "",
    "moos-open": "",
    "kdialog": 'case "$*" in *warningyesno*) exit "${KDIALOG_ANSWER:-1}";; esac\n',
}


# A display name for the tests that need a desktop session. It names no real display, and no
# test runs a real window: every program that could draw one is a recording stub.
DISPLAY_NAME = "wayland-moos-test"


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
            "STUB_ROOT": str(self.root),
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

    def control(self, *args, machine=None, **env):
        machine = machine or self.machine
        return subprocess.run([sys.executable, str(CONTROL), *args], env=machine.env(**env),
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
        result = self.control("screenshot", WAYLAND_DISPLAY=DISPLAY_NAME)
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
        opened = self.control("open", "org.mozilla.firefox", WAYLAND_DISPLAY=DISPLAY_NAME)
        self.assertEqual(opened.returncode, 0, opened.stderr)
        calls = self.machine.calls(settle=1.0)
        self.assertIn(["moos-theme", "nova"], calls)
        self.assertIn(["flatpak", "run", "org.mozilla.firefox"], calls)
        missing = self.control("open", "org.example.NotInstalled", WAYLAND_DISPLAY=DISPLAY_NAME)
        self.assertEqual(missing.returncode, 69)

    def test_settings_opens_only_the_pages_mo_ai_offers(self):
        """Each page opens with the registry's own command — the one moos-open's arm runs."""
        for page, argv in (("night-light", ["systemsettings", "kcm_nightlight"]),
                           ("update", ["moos-settings", "--section=update"]),
                           ("storage", ["kinfocenter", "kcm_block_devices"])):
            with self.subTest(page=page):
                self.machine.log.write_text("")
                result = self.control("settings", page, WAYLAND_DISPLAY=DISPLAY_NAME)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(argv, self.machine.calls(settle=0.5))
        self.machine.log.write_text("")
        for page in ("kcm/../x", "reboot", "Display", "display;reboot", "full"):
            with self.subTest(page=page):
                self.assertEqual(self.control("settings", page,
                                              WAYLAND_DISPLAY=DISPLAY_NAME).returncode, 2)
        opened = [call for call in self.machine.calls(settle=0.5)
                  if call[0] in ("moos-open", "systemsettings", "moos-settings", "kinfocenter")]
        self.assertEqual(opened, [])

    def test_windows_fail_loudly_without_a_desktop_session(self):
        """Neither WAYLAND_DISPLAY nor DISPLAY: nothing is started and the verb says no.

        Mo AI's tool runner once started before the session and had neither variable; the
        page, the app and the screenshot each died looking for a display while the detached
        start printed "Opening…" (measured on the station, 2026-09-24).
        """
        for args in (("settings", "display"), ("open", "org.mozilla.firefox"), ("screenshot",)):
            with self.subTest(args=args):
                self.machine.log.write_text("")
                result = self.control(*args)
                self.assertEqual(result.returncode, 69, (result.stdout, result.stderr))
                self.assertIn("no desktop session", result.stderr)
                self.assertEqual(result.stdout, "", "a refusal must not also claim success")
                started = [call for call in self.machine.calls(settle=0.3)
                           if call[0] in ("systemsettings", "spectacle", "gtk-launch", "logger")
                           or call[:2] == ["flatpak", "run"]]
                self.assertEqual(started, [], "a window was started with no desktop to show it")
        # An X11-only session (DISPLAY without WAYLAND_DISPLAY) is still a desktop session.
        self.assertEqual(self.control("settings", "display", DISPLAY=":0").returncode, 0)

    def test_a_window_that_dies_at_once_is_a_failure_not_a_success(self):
        page = self.control("settings", "display", WAYLAND_DISPLAY=DISPLAY_NAME,
                            STUB_PAGE_EXIT="1")
        self.assertEqual(page.returncode, 69, page.stderr)
        self.assertIn("stopped at once", page.stderr)
        self.assertEqual(page.stdout, "")
        app = self.control("open", "org.mozilla.firefox", WAYLAND_DISPLAY=DISPLAY_NAME,
                           STUB_APP_EXIT="1")
        self.assertEqual(app.returncode, 69, app.stderr)
        self.assertIn("stopped at once", app.stderr)
        # A window that is still open after the settle window has opened: answered at once,
        # without waiting for the person to close it.
        began = time.monotonic()
        stays = self.control("settings", "display", WAYLAND_DISPLAY=DISPLAY_NAME,
                             STUB_PAGE_STAYS="4")
        self.assertEqual(stays.returncode, 0, stays.stderr)
        self.assertLess(time.monotonic() - began, 3.5, "moos-control waited for the window")

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
            "night_light": True, "wifi": True, "bluetooth": True,
            "theme": "nova-light", "dnd": False, "mic_muted": True,
            "power_profile": "balanced"})
        self.assertFalse([call for call in self.machine.calls() if call[0] == "logger"],
                         "status must not write an audit entry")

    def test_status_never_waits_on_a_probe_that_does_not_answer(self):
        """A hanging probe must cost the budget, not the answer.

        Measured on the Oracle A1 (2026-09-17): that host has no Bluetooth
        hardware, `bluetoothctl show` activated bluez and then waited for an
        adapter that never appeared, and `moos-control status` did not return.
        Every other probe answered in under 20 ms. The old gate could not see
        this because its bluetoothctl stub answers instantly -- a stub is not
        evidence that the real command returns.
        """
        machine = StubMachine()
        try:
            # An absolute path: the stub PATH holds only the stub directory,
            # so a bare `sleep` would simply not be found and the probe would
            # fail fast -- passing this test without ever hanging.
            sleep = shutil.which("sleep")
            self.assertIsNotNone(sleep, "this test needs a real sleep to hang on")
            for name in ("bluetoothctl", "nmcli", "wpctl"):
                hang = machine.bin / name
                hang.write_text(f"#!/bin/sh\nexec {sleep} 600\n")
                hang.chmod(0o755)
            started = time.monotonic()
            result = subprocess.run([sys.executable, str(CONTROL), "status"],
                                    env=machine.env(), capture_output=True,
                                    text=True, timeout=120)
            elapsed = time.monotonic() - started
        finally:
            machine.close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 30, f"status took {elapsed:.1f}s; it must stay bounded")
        # Unanswered is unknown, never an invented value.
        self.assertEqual(json.loads(result.stdout)["bluetooth"], None)
        self.assertEqual(json.loads(result.stdout)["wifi"], None)

    def test_status_reports_a_machine_without_bluez_as_unknown(self):
        """No bluez on the bus means no Bluetooth to report -- not "off".

        "off" would have Mo AI offer a switch that turns nothing on, and it must
        not run bluetoothctl at all: that is the call that hangs.
        """
        machine = StubMachine()
        try:
            busctl = machine.bin / "busctl"
            busctl.write_text(RECORDER + '''case "$*" in
  *NameHasOwner*org.bluez*) echo '{"type":"b","data":[false]}';;
  *NightLight*running*) echo '{"type":"b","data":true}';;
esac
''')
            busctl.chmod(0o755)
            result = subprocess.run([sys.executable, str(CONTROL), "status"],
                                    env=machine.env(), capture_output=True,
                                    text=True, timeout=60)
            calls = machine.calls()
        finally:
            machine.close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["bluetooth"], None)
        self.assertFalse([call for call in calls if call[0] == "bluetoothctl"],
                         "status asked bluetoothctl although bluez is not on the bus")


class DesktopVerbTests(unittest.TestCase):
    """SPEC D4: the window manager and the desktop, through their own fixed actions."""

    def setUp(self):
        self.machine = StubMachine()

    def tearDown(self):
        self.machine.close()

    def control(self, *args):
        return subprocess.run([sys.executable, str(CONTROL), *args], env=self.machine.env(),
                              capture_output=True, text=True, timeout=30)

    def acting(self):
        return [call for call in self.machine.calls()
                if call[0] != "logger" and "shortcutNames" not in call
                and "get-property" not in call and "getLayoutsList" not in call
                and "getLayout" not in call and "currentProfile" not in call
                and "profileChoices" not in call]

    def invoke(self, component, name):
        return ["busctl", "--user", "call", "org.kde.kglobalaccel", f"/component/{component}",
                "org.kde.kglobalaccel.Component", "invokeShortcut", "s", name]

    def test_window_and_arrange_invoke_exact_named_actions(self):
        for args, name in ((("window", "overview"), "Overview"),
                           (("window", "grid"), "Grid View"),
                           (("window", "show-desktop"), "Show Desktop"),
                           (("arrange", "halves"), "MoOS Arrange: halves"),
                           (("arrange", "thirds"), "MoOS Arrange: thirds"),
                           (("arrange", "quarters"), "MoOS Arrange: quarters"),
                           (("arrange", "main"), "MoOS Arrange: main"),
                           (("arrange", "centre"), "MoOS Arrange: centre")):
            with self.subTest(args=args):
                self.machine.log.write_text("")
                result = self.control(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.acting(), [self.invoke("kwin", name)])

    def test_an_action_the_desktop_does_not_list_is_unavailable_not_invoked(self):
        busctl = self.machine.bin / "busctl"
        busctl.write_text(RECORDER + '''case "$*" in
  *shortcutNames*) echo '{"type":"as","data":[["Overview"]]}';;
esac
''')
        busctl.chmod(0o755)
        result = self.control("arrange", "halves")
        self.assertEqual(result.returncode, 69, result.stderr)
        self.assertFalse([call for call in self.machine.calls() if "invokeShortcut" in call])

    def test_desktop_steps_call_the_two_fixed_methods(self):
        for value, method in (("next", "nextDesktop"), ("previous", "previousDesktop")):
            with self.subTest(value=value):
                self.machine.log.write_text("")
                self.assertEqual(self.control("desktop", value).returncode, 0)
                self.assertEqual(self.acting(), [["busctl", "--user", "call", "org.kde.KWin",
                                                  "/KWin", "org.kde.KWin", method]])

    def test_dnd_presses_the_applets_toggle_only_when_the_state_differs(self):
        toggle = self.invoke("plasmashell", "toggle do not disturb")
        self.assertEqual(self.control("dnd", "off").returncode, 0)
        self.assertEqual(self.acting(), [], "already off: a toggle would turn it ON")
        result = self.control("dnd", "on")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.acting(), [toggle])
        self.assertEqual((self.machine.root / "dnd").read_text().strip(), "1",
                         "the state was not read back on")
        self.machine.log.write_text("")
        self.assertEqual(self.control("dnd", "on").returncode, 0)
        self.assertEqual(self.acting(), [], "already on: pressing the toggle would turn it OFF")
        self.assertEqual(self.control("dnd", "off").returncode, 0)
        self.assertEqual(self.acting(), [toggle])
        self.assertEqual((self.machine.root / "dnd").read_text().strip(), "0")

    def test_dnd_that_does_not_change_is_reported_not_claimed(self):
        busctl = self.machine.bin / "busctl"
        busctl.write_text(RECORDER + '''case "$*" in
  *"/component/plasmashell"*shortcutNames*) echo '{"type":"as","data":[["toggle do not disturb"]]}';;
  *Inhibited*) echo '{"type":"b","data":false}';;
esac
''')
        busctl.chmod(0o755)
        result = self.control("dnd", "on")
        self.assertEqual(result.returncode, 69)
        self.assertIn("did not change", result.stderr)

    def test_mic_keyboard_motion_clarity_use_their_owners(self):
        expected = {
            ("mic", "mute"): [["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1"]],
            ("mic", "unmute"): [["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0"]],
            ("keyboard-layout", "next"): [["busctl", "--user", "call", "org.kde.keyboard",
                                           "/Layouts", "org.kde.KeyboardLayouts",
                                           "switchToNextLayout"]],
            ("motion", "still"): [["moos-theme", "motion", "still"]],
            ("clarity", "solid"): [["moos-theme", "clarity", "solid"]],
        }
        for args, calls in expected.items():
            with self.subTest(args=args):
                self.machine.log.write_text("")
                result = self.control(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.acting(), calls)
        self.assertIn("Arabic", self.control("keyboard-layout", "next").stdout)

    def test_power_profile_is_set_and_read_back(self):
        result = self.control("power-profile", "power-saver")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(["busctl", "--user", "call", "org.kde.Solid.PowerManagement",
                       "/org/kde/Solid/PowerManagement/Actions/PowerProfile",
                       "org.kde.Solid.PowerManagement.Actions.PowerProfile",
                       "setProfile", "s", "power-saver"], self.machine.calls())
        self.assertEqual((self.machine.root / "profile").read_text().strip(), "power-saver")

    def test_invalid_desktop_requests_run_nothing(self):
        for args in (("window", "close"), ("window", "Overview"), ("arrange", "grid"),
                     ("arrange", "halves;reboot"), ("desktop", "3"), ("dnd", "toggle"),
                     ("mic", "off"), ("keyboard-layout", "previous"), ("keyboard-layout", "de"),
                     ("motion", "fast"), ("clarity", "opaque"), ("power-profile", "turbo"),
                     ("window",), ("dnd", "on", "now")):
            with self.subTest(args=args):
                self.assertEqual(self.control(*args).returncode, 2, args)
        self.assertEqual(self.acting(), [], "an invalid request reached a real command")

    def test_nothing_can_load_a_script_close_a_window_or_replace_the_compositor(self):
        code = "\n".join(line for line in CONTROL.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        for forbidden in ("loadScript", "/Scripting", "killWindow", '"replace"', "unloadScript",
                          "showDebugConsole", "shell=True"):
            self.assertNotIn(forbidden, code)


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
                          ("moos://control/bluetooth/on", ["bluetooth", "on"]),
                          ("moos://control/mute", ["mute"]),
                          ("moos://control/screenshot", ["screenshot"]),
                          ("moos://control/window/overview", ["window", "overview"]),
                          ("moos://control/window/show-desktop", ["window", "show-desktop"]),
                          ("moos://control/arrange/centre", ["arrange", "centre"]),
                          ("moos://control/desktop/previous", ["desktop", "previous"]),
                          ("moos://control/dnd/on", ["dnd", "on"]),
                          ("moos://control/mic/mute", ["mic", "mute"]),
                          ("moos://control/keyboard-layout/next", ["keyboard-layout", "next"]),
                          ("moos://control/motion/gentle", ["motion", "gentle"]),
                          ("moos://control/clarity/balanced", ["clarity", "balanced"]),
                          ("moos://control/power-profile/performance",
                           ["power-profile", "performance"])):
            with self.subTest(url=url):
                self.machine.log.write_text("")
                self.open(url)
                self.assertEqual(self.control_calls(), [argv])

    def test_malformed_routes_never_reach_moos_control(self):
        for url in ("moos://control/volume/350", "moos://control/volume/35;reboot",
                    "moos://control/volume/", "moos://control/brightness/-5",
                    "moos://control/night-light/party", "moos://control/reboot",
                    "moos://control/window/close", "moos://control/arrange/halves/extra",
                    "moos://control/dnd", "moos://control/keyboard-layout/de",
                    "moos://control/power-profile/turbo", "moos://control/motion/$(id)"):
            with self.subTest(url=url):
                self.open(url)
        self.assertEqual(self.control_calls(), [])

    # Wi-Fi off cuts the owner off, Bluetooth off cuts a wireless keyboard, and turning the
    # microphone back on undoes a privacy choice. moos: is a public scheme, so a web page or
    # a link can hand any of these to the router: each one waits for the person's yes.
    ASKS_FIRST = (("moos://control/wifi/off", ["wifi", "off"]),
                  ("moos://control/bluetooth/off", ["bluetooth", "off"]),
                  ("moos://control/mic/unmute", ["mic", "unmute"]))

    def test_disruptive_values_require_the_users_yes(self):
        for url, argv in self.ASKS_FIRST:
            with self.subTest(url=url):
                self.machine.log.write_text("")
                self.open(url, KDIALOG_ANSWER="1")
                self.assertEqual(self.control_calls(), [], f"{url} ran without confirmation")
                self.open(url, KDIALOG_ANSWER="0")
                self.assertEqual(self.control_calls(), [argv])

    def test_disruptive_values_fail_closed_without_a_dialog_tool(self):
        (self.machine.bin / "kdialog").unlink()
        environment = self.machine.env()
        environment["PATH"] = str(self.machine.bin)
        for url, _argv in self.ASKS_FIRST:
            with self.subTest(url=url):
                subprocess.run(["/bin/bash", str(OPEN), url], env=environment,
                               capture_output=True, text=True, timeout=30)
                self.assertEqual(self.control_calls(), [])

    def test_the_router_asks_for_exactly_what_mo_ai_asks_for(self):
        """One list of values that need a yes: Mo AI's confirm_values ARE the router's asks.

        Bluetooth off shipped confirmed in Mo AI and instant on the public scheme; a second
        hand-kept list is how that happens. Every control arm that asks, and every schema
        value that needs a card, must be the same route.
        """
        sys.path.insert(0, str(ROOT / "system_files/usr/lib/moai"))
        import moai_tool_schemas as schemas
        code = "\n".join(line for line in OPEN.read_text(encoding="utf-8").splitlines()
                         if not line.lstrip().startswith("#"))
        asking, instant = set(), set()
        for labels, body in re.findall(r"(?ms)^    (control/[^\s)]+)\)(.*?);;", code):
            for label in labels.split("|"):
                (asking if re.search(r"\bconfirm\s", body) else instant).add(label)
        self.assertIn("control/wifi/off", asking, "the arm parser found nothing")
        carded = set()
        for tool in schemas.ALL_TOOLS:
            meta = tool["_moos"]
            if meta["executor"] != "moos-control":
                continue
            for values in (meta.get("confirm_values") or {}).values():
                carded.update(f"control/{meta['command']}/{value}" for value in values)
        self.assertEqual(sorted(asking), sorted(carded))
        self.assertEqual(sorted(carded & instant), [], "a carded value also has an instant arm")


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

    def test_settings_pages_agree_across_grammar_prompt_control_and_moos_open(self):
        # Review of PR #85: the prompt taught `moos-control settings <page>`, which
        # moos-control did not implement; the button worked and the command did not.
        # The pages are the ONE registry's Mo AI tokens (SPEC D3); Mo AI's text grammar is
        # still a hand copy of them, so it must name exactly those pages.
        import runpy
        pages = set(runpy.run_path(str(CONTROL), run_name="moos_control_pages")["SETTINGS_PAGES"])
        self.assertGreaterEqual(len(pages), 45, "the settings registry was not read")
        grammar = re.search(r"settings\\s\+\(\?:([a-z|-]+)\)", self.qml)
        self.assertIsNotNone(grammar, "Mo AI's control grammar lost its settings pages")
        self.assertEqual(set(grammar.group(1).split("|")), pages)
        start = self.qml.index("settings <page>` for the exact settings page (")
        listed = self.qml[start:self.qml.index(")", start)].split("(", 1)[1]
        listed = re.sub(r'"\s*\+\s*"', "", listed)
        self.assertLessEqual({page.strip() for page in listed.split(",")}, pages)
        opener = OPEN.read_text(encoding="utf-8")
        for page in sorted(pages):
            self.assertRegex(opener, rf"\n\s*settings/{re.escape(page)}\)", page)


if __name__ == "__main__":
    unittest.main(verbosity=2)
