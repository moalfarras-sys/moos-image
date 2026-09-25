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

And from the review of THEME_REV 86:

  * Both checks tell a person with a home copy of a RETIRED widget to "run moos-apply-theme
    once", but the retired sweep sat after the once-per-revision fast path, so once the v86
    marker existed that advice removed nothing. The sweep now runs first, on every invocation;
    the gate runs the WHOLE script with the marker present and watches the copy go.
  * The tray verdict counted the icons from moos-bar.conf but named them from a literal, a
    second copy of the list inside the check. It now names what it checked.

Each check below executes the REAL code out of the shipped script against synthetic trees, with
every desktop tool stubbed and the session bus pointed at nothing, so the live desktop is never
touched and the gate cannot drift from what runs on the machine.
"""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAR_APPLY = ROOT / "system_files/usr/bin/moos-bar-apply"
BAR_CONF = ROOT / "system_files/usr/share/moos/moos-bar.conf"
SELFCHECK = ROOT / "system_files/usr/bin/moos-selfcheck"
POST_UPDATE = ROOT / "tests/post-update-check.sh"
APPLY = ROOT / "system_files/usr/bin/moos-apply-theme"
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
    # The SHIPPED bar tool, never the host's installed copy of an older revision.
    shim = stubs / "moos-bar-apply"
    shim.write_text(f'#!/bin/sh\nexec "{BASH}" "{BAR_APPLY}" "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
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
        self.assertIn("OK the tray shows the 4 status icons moos-bar.conf pins: "
                      "networkmanagement, volume, notifications, keyboardlayout", out)
        self.assertNotIn("bluetooth", out)

    def test_the_verdict_names_what_the_conf_pins_not_a_remembered_list(self):
        conf = "shownItems=org.kde.plasma.volume,org.kde.plasma.battery"
        out = self.run_tray("org.kde.plasma.battery,org.kde.plasma.volume", conf)
        self.assertIn("OK the tray shows the 2 status icons moos-bar.conf pins: volume, battery",
                      out)
        for other in ("network", "notifications", "language", "keyboardlayout"):
            self.assertNotIn(other, out, "the verdict may only name icons it checked")

    def test_a_missing_pinned_icon_is_named(self):
        out = self.run_tray("org.kde.plasma.volume",
                            "shownItems=org.kde.plasma.volume,org.kde.plasma.notifications")
        self.assertIn("NOTE the tray is missing: org.kde.plasma.notifications", out)

    def test_no_private_list_is_left_in_the_check(self):
        tray = section(SELFCHECK, self.START, self.END)
        for stale in ("org.kde.plasma.bluetooth", "org.kde.plasma.brightness"):
            self.assertNotIn(stale, tray, "moos-bar.conf is the tray's only definition")


RETIRED = ("org.moos.heroclock", "org.moos.search", "org.moos.nova.deskclock",
           "org.moos.ui2.dashboard")


def retired_list(text: str, anchor: str) -> list[str]:
    """The plasmoid ids of the first `for rel in … ; do` list after *anchor*."""
    block = text.split(anchor, 1)[1].split("; do", 1)[0]
    return sorted(re.findall(r"plasma/plasmoids/(org\.moos\.[a-z0-9.]+)", block))


class TheRetiredAdviceWorksOnTheSpot(unittest.TestCase):
    """Runs the WHOLE moos-apply-theme, as `run moos-apply-theme once` would, on a home that
    already holds this revision's marker: the case in which the sweep used to be skipped."""

    # Tools the script may reach once past the fast path. Each is a failing, recording stub, so
    # a regression that falls through to the full apply still touches nothing real.
    MORE_TOOLS = ("kbuildsycoca6", "balooctl6", "plasma-apply-lookandfeel",
                  "plasma-apply-colorscheme", "plasma-apply-desktoptheme",
                  "plasma-apply-wallpaperimage", "plasma-apply-cursortheme", "lookandfeeltool",
                  "kquitapp6", "kstart", "kstart6", "dbus-send", "fc-cache", "notify-send",
                  "qdbus", "xdg-open", "flatpak")

    def run_apply(self, lookandfeel_known: bool) -> tuple[subprocess.CompletedProcess, Path, str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        calls = root / "calls"
        env = isolated_env(root, calls)
        stubs = root / "stubs"
        for tool in self.MORE_TOOLS:
            (stubs / tool).write_text(f'#!/bin/sh\necho "{tool} $*" >> "{calls}"\nexit 1\n',
                                      encoding="utf-8")
            (stubs / tool).chmod(0o755)
        # The desktop wears a MoOS look and the appearance owner verifies it: the fast path.
        kread = ('echo org.moos.ui2' if lookandfeel_known else 'exit 1')
        (stubs / "kreadconfig6").write_text(
            f'#!/bin/sh\necho "kreadconfig6 $*" >> "{calls}"\n{kread}\n', encoding="utf-8")
        (stubs / "moos-theme").write_text(
            f'#!/bin/sh\necho "moos-theme $*" >> "{calls}"\nexit 0\n', encoding="utf-8")
        for tool in ("kreadconfig6", "moos-theme"):
            (stubs / tool).chmod(0o755)
        env["MOOS_SYSTEM_SHARE"] = str(root / "image")          # ships no retired id
        rev = re.search(r"(?m)^THEME_REV=(\d+)$", APPLY.read_text(encoding="utf-8")).group(1)
        state = Path(env["XDG_STATE_HOME"])
        state.mkdir(parents=True)
        (state / f"moos-ui2-theme-applied.v{rev}").touch()
        share = Path(env["XDG_DATA_HOME"])
        for plugin in RETIRED + ("com.example.weather",):
            (share / "plasma/plasmoids" / plugin / "contents").mkdir(parents=True)
            (share / "plasma/plasmoids" / plugin / "metadata.json").write_text("{}")
        result = subprocess.run([BASH, str(APPLY)], env=env, capture_output=True, text=True,
                                timeout=120)
        return result, share, calls.read_text(encoding="utf-8") if calls.exists() else ""

    def check(self, lookandfeel_known: bool, route: str) -> None:
        result, share, calls = self.run_apply(lookandfeel_known)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = (share.parent.parent / ".cache/moos-apply-theme.log").read_text(encoding="utf-8")
        self.assertNotIn("=== moos-apply-theme", log,
                         "the fixture must exercise the marker fast path, not a full apply")
        self.assertIn(route, calls, "the run left by a different door than this case covers")
        for plugin in RETIRED:
            with self.subTest(plugin=plugin):
                self.assertFalse((share / "plasma/plasmoids" / plugin).exists(),
                                 f"`run moos-apply-theme once` left the retired {plugin} "
                                 "in place: the sweep must run before the fast path")
                self.assertIn(f"removed the user-level copy of retired plasma/plasmoids/{plugin}",
                              log)
        self.assertTrue((share / "plasma/plasmoids/com.example.weather/metadata.json").exists(),
                        "a widget the person installed is theirs")
        for tool in ("plasmashell", "systemctl", "kquitapp6", "kbuildsycoca6", "busctl"):
            self.assertNotIn(f"{tool} ", calls, f"the fast path must not run {tool}")

    def test_the_verified_fast_path_removes_retired_copies(self):
        self.check(True, "moos-theme settle-lnf org.moos.ui2")

    def test_the_cannot_tell_fast_path_removes_retired_copies(self):
        self.check(False, "kreadconfig6 --file kdeglobals --group KDE --key LookAndFeelPackage")

    def test_the_advice_and_the_sweep_name_the_same_ids(self):
        sweep = retired_list(APPLY.read_text(encoding="utf-8"), "remove_retired_moos_packages() {")
        self.assertEqual(sweep, sorted(RETIRED))
        selfcheck = SELFCHECK.read_text(encoding="utf-8")
        self.assertEqual(retired_list(selfcheck, "# A RETIRED MoOS package has no image copy"),
                         sweep, "moos-selfcheck names a retired id moos-apply-theme keeps")
        self.assertEqual(retired_list(POST_UPDATE.read_text(encoding="utf-8"),
                                      "# Retired packages have no image copy to compare with"),
                         sweep, "post-update-check names a different retired list")
        apply = APPLY.read_text(encoding="utf-8")
        call = apply.index("\nremove_retired_moos_packages\n")
        self.assertLess(call, apply.index('migration_completed=false\nif [ -e "$marker" ]; then'),
                        "the retired sweep must run before the marker fast path")


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
