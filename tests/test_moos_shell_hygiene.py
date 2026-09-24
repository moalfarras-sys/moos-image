#!/usr/bin/env python3
"""Gate: the shell's health checks tell the truth about the bar and about home shadows.

WHY THIS EXISTS (all measured on the station, 2026-09-24)

  * `moos-bar-apply check` took the bar lock with `flock -n 9 || exit 0`. A check that lost the
    lock to a running apply exited 0 WITHOUT CHECKING, and moos-selfcheck and post-update-check
    then printed "the Horizon Bar matches". A check must never pass by not running.
  * moos-selfcheck carried its own six-item tray list, including Bluetooth and brightness, which
    moos-bar.conf deliberately moved behind the arrow; every correct desktop printed "the tray is
    missing: bluetooth brightness". moos-bar.conf is the single source; the check reads it.
  * ~/.local/share/kwin/tabbox/org.moos.ui2.switcher (a review copy) overrode the image's task
    switcher for a week while both moos-selfcheck and post-update-check said "no user-level copy
    is shadowing". Their scans did not look under kwin/.

Each check below executes the REAL code out of the shipped script against synthetic trees, with
every desktop tool stubbed and the session bus pointed at nothing, so the live desktop is never
touched and the gate cannot drift from what runs on the machine.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAR_APPLY = ROOT / "system_files/usr/bin/moos-bar-apply"
BAR_CONF = ROOT / "system_files/usr/share/moos/moos-bar.conf"
SELFCHECK = ROOT / "system_files/usr/bin/moos-selfcheck"
POST_UPDATE = ROOT / "tests/post-update-check.sh"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"

# Every tool that could reach a live desktop or user manager. Each stub records its call and
# fails, so a test also proves which tools a path did NOT run.
DESKTOP_TOOLS = ("systemctl", "gdbus", "busctl", "journalctl", "qdbus6", "qdbus-qt6",
                 "kwriteconfig6", "kreadconfig6", "plasmashell")


def isolated_env(root: Path, calls: Path) -> dict[str, str]:
    stubs = root / "stubs"
    stubs.mkdir(exist_ok=True)
    for tool in DESKTOP_TOOLS:
        stub = stubs / tool
        stub.write_text(f'#!/bin/sh\necho "{tool} $*" >> "{calls}"\nexit 1\n', encoding="utf-8")
        stub.chmod(0o755)
    runtime = root / "run"
    runtime.mkdir(mode=0o700, exist_ok=True)
    return {
        "PATH": f"{stubs}:/usr/bin:/bin",
        "HOME": str(root / "home"),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_CONFIG_HOME": str(root / "home/.config"),
        "XDG_DATA_HOME": str(root / "home/.local/share"),
        "XDG_STATE_HOME": str(root / "home/.local/state"),
        "XDG_CACHE_HOME": str(root / "home/.cache"),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root / 'no-bus'}",
        "MOOS_BAR_CONF": str(BAR_CONF),
    }


def section(path: Path, start: str, end: str) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.count(start) == 1, f"{path.name}: start marker {start!r} moved"
    assert text.count(end) == 1, f"{path.name}: end marker {end!r} moved"
    return text[text.index(start): text.index(end) + len(end)]


def report_helpers() -> str:
    return ('ok()   { printf "OK %s\\n" "$1"; }\n'
            'bad()  { printf "BAD %s\\n" "$1"; }\n'
            'note() { printf "NOTE %s\\n" "$1"; }\n'
            'head_() { :; }\n')


class TheBarCheckNeverPassesWithoutChecking(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls = self.root / "calls"
        self.env = isolated_env(self.root, self.calls)
        self.env["MOOS_BAR_LOCK_WAIT"] = "1"
        # An apply in progress: somebody else holds the bar lock.
        self.lock = open(Path(self.env["XDG_RUNTIME_DIR"]) / "moos-bar.lock", "w")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def tearDown(self):
        self.lock.close()
        self.tmp.cleanup()

    def run_bar(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([BASH, str(BAR_APPLY), *args], env=self.env, capture_output=True,
                              text=True, timeout=60)

    def test_a_check_that_cannot_take_the_lock_reports_busy_not_success(self):
        result = self.run_bar("check")
        self.assertEqual(result.returncode, 75, result.stdout + result.stderr)
        self.assertIn("busy", result.stdout)
        self.assertIn("nothing was checked", result.stdout)
        self.assertFalse(self.calls.exists(), "a busy check must not probe the desktop")

    def test_a_concurrent_apply_leaves_without_touching_anything(self):
        result = self.run_bar("apply", "86")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.calls.exists(),
                         "the second apply must not stop the shell or rewrite the bar")

    def test_get_reads_the_definition_without_the_lock(self):
        result = self.run_bar("get", "tray.shownItems")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         "org.kde.plasma.networkmanagement,org.kde.plasma.volume,"
                         "org.kde.plasma.notifications,org.kde.plasma.keyboardlayout")

    def test_both_callers_treat_busy_as_not_passed(self):
        for path in (SELFCHECK, POST_UPDATE):
            text = path.read_text(encoding="utf-8")
            with self.subTest(caller=path.name):
                self.assertIn("moos-bar-apply check >/dev/null 2>&1", text)
                block = text.split("moos-bar-apply check >/dev/null 2>&1", 1)[1][:700]
                self.assertIn("75)", block)
                self.assertNotIn("75) ok", block)


class SelfcheckTrayReadsTheBarDefinition(unittest.TestCase):
    START = '_bar_conf="${MOOS_BAR_CONF:-/usr/share/moos/moos-bar.conf}"'
    END = """        note "the tray is missing:${_tray_missing} (yours to change, so this is only a note)"
    fi
fi"""

    def run_tray(self, shown_in_profile: str, conf_line: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = isolated_env(root, root / "calls")
            conf = root / "moos-bar.conf"
            conf.write_text(f"[tray]\n{conf_line}\n", encoding="utf-8")
            env["MOOS_BAR_CONF"] = str(conf)
            appletsrc = root / "appletsrc"
            appletsrc.write_text(f"[Containments][1][Applets][2][General]\nshownItems="
                                 f"{shown_in_profile}\n", encoding="utf-8")
            script = (report_helpers() + f'appletsrc="{appletsrc}"\n'
                      + section(SELFCHECK, self.START, self.END))
            return subprocess.run([BASH, "-c", script], env=env, capture_output=True,
                                  text=True, timeout=30).stdout

    def test_the_shipped_four_icons_pass_without_bluetooth_or_brightness(self):
        shipped = next(line for line in BAR_CONF.read_text(encoding="utf-8").splitlines()
                       if line.startswith("shownItems="))
        out = self.run_tray(shipped.split("=", 1)[1], shipped)
        self.assertIn("OK the tray shows the 4 status icons moos-bar.conf pins", out)
        self.assertNotIn("bluetooth", out)

    def test_a_missing_pinned_icon_is_named(self):
        out = self.run_tray("org.kde.plasma.volume",
                            "shownItems=org.kde.plasma.volume,org.kde.plasma.notifications")
        self.assertIn("NOTE the tray is missing: org.kde.plasma.notifications", out)

    def test_no_private_list_is_left_in_the_check(self):
        tray = section(SELFCHECK, self.START, self.END)
        for stale in ("org.kde.plasma.bluetooth", "org.kde.plasma.brightness"):
            self.assertNotIn(stale, tray, "moos-bar.conf is the tray's only definition")


class HomeShadowScansCoverKWin(unittest.TestCase):
    SELF_START = 'shadows=0\nsystem_share="${MOOS_SYSTEM_SHARE:-/usr/share}"'
    SELF_END = '[ "$shadows" -eq 0 ] && ok "no user-level copy is shadowing a MoOS asset"'
    POST_START = 'plasmoid_shadows=""\n'
    POST_END = """    bad "user-local Plasma/KWin package(s) shadow the new image:$plasmoid_shadows — run moos-apply-theme"
fi"""

    def world(self, root: Path) -> dict[str, str]:
        env = isolated_env(root, root / "calls")
        user, image = Path(env["XDG_DATA_HOME"]), root / "image"
        for rel in ("kwin/tabbox/org.moos.ui2.switcher/contents/ui/main.qml",
                    "kwin/scripts/moos-arrange/contents/code/main.js"):
            for base in (user, image):
                (base / rel).parent.mkdir(parents=True, exist_ok=True)
                (base / rel).write_text("x", encoding="utf-8")
        own = user / "kwin/scripts/krohnkite/contents/code/main.js"
        own.parent.mkdir(parents=True)
        own.write_text("x", encoding="utf-8")
        retired = user / "plasma/plasmoids/org.moos.heroclock/metadata.json"
        retired.parent.mkdir(parents=True)
        retired.write_text("{}", encoding="utf-8")
        env["MOOS_SYSTEM_SHARE"] = str(image)
        return env

    def test_selfcheck_reports_each_kwin_shadow_once_and_leaves_user_scripts_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.world(Path(tmp))
            script = report_helpers() + section(SELFCHECK, self.SELF_START, self.SELF_END)
            out = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                                 timeout=30).stdout
        bad = [line for line in out.splitlines() if line.startswith("BAD ")]
        self.assertEqual(sum("kwin/tabbox/org.moos.ui2.switcher" in l for l in bad), 1, out)
        self.assertEqual(sum("kwin/scripts/moos-arrange" in l for l in bad), 1, out)
        self.assertFalse(any("krohnkite" in l for l in bad), "a user's own KWin script is theirs")
        self.assertTrue(any("org.moos.heroclock is a retired MoOS widget" in l for l in bad), out)
        self.assertNotIn("OK no user-level copy", out)

    def test_post_update_check_reports_kwin_shadows(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.world(Path(tmp))
            script = report_helpers() + section(POST_UPDATE, self.POST_START, self.POST_END)
            out = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                                 timeout=30).stdout
        self.assertIn("kwin/tabbox/org.moos.ui2.switcher", out)
        self.assertIn("kwin/scripts/moos-arrange", out)
        self.assertIn("org.moos.heroclock(retired)", out)
        self.assertNotIn("krohnkite", out)

    def test_a_clean_home_passes_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = isolated_env(root, root / "calls")
            env["MOOS_SYSTEM_SHARE"] = str(root / "image")
            for path, start, end, verdict in (
                    (SELFCHECK, self.SELF_START, self.SELF_END,
                     "OK no user-level copy is shadowing a MoOS asset"),
                    (POST_UPDATE, self.POST_START, self.POST_END,
                     "OK no user-local MoOS bar or KWin package shadows the updated image")):
                script = report_helpers() + section(path, start, end)
                out = subprocess.run([BASH, "-c", script], env=env, capture_output=True,
                                     text=True, timeout=30).stdout
                self.assertIn(verdict, out, path.name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
