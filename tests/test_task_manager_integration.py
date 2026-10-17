#!/usr/bin/env python3
"""One native task manager, reached from the launcher, shortcut and Store.

The real URL router runs with an inert setsid substitute; no GUI, session bus,
process termination, or real user home is contacted by this gate.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "system_files/usr/share/applications/org.kde.plasma-systemmonitor.desktop"
ROUTER = ROOT / "system_files/usr/bin/moos-open"


class TaskManager(unittest.TestCase):
    def test_native_monitor_keeps_one_upstream_launcher(self):
        self.assertFalse(DESKTOP.exists(), "native System Monitor is integrated without forking its launcher")
        self.assertFalse((DESKTOP.parent / "org.moos.task-manager.desktop").exists(),
                         "a second launcher would duplicate the same native application")

    def route(self, url):
        with tempfile.TemporaryDirectory(prefix="moos-task-manager-") as raw:
            home = Path(raw)
            bin_dir = home / "bin"
            bin_dir.mkdir()
            calls = home / "calls"
            stub = bin_dir / "setsid"
            stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$MOOS_PROBE_CALLS"\n')
            stub.chmod(0o755)
            silent = '#!/bin/sh\nexit 0\n'
            for name in ("notify-send", "kdialog"):
                p = bin_dir / name
                p.write_text(silent)
                p.chmod(0o755)
            env = {"HOME": str(home), "PATH": str(bin_dir) + ":/usr/bin:/bin",
                   "LANG": "C.UTF-8", "MOOS_PROBE_CALLS": str(calls),
                   "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + str(home / "no-bus")}
            result = subprocess.run(["bash", str(ROUTER), url], env=env,
                                    capture_output=True, text=True, timeout=5)
            end = time.monotonic() + 1
            while result.returncode == 0 and not calls.exists() and time.monotonic() < end:
                time.sleep(.01)
            return result.returncode, calls.read_text().splitlines() if calls.exists() else []

    def test_store_route_opens_the_real_native_apps_page_without_a_terminal(self):
        code, argv = self.route("moos://app/task-manager")
        self.assertEqual(code, 0)
        self.assertEqual(argv, ["plasma-systemmonitor", "--page-id", "applications.page"])

    def test_url_cannot_supply_a_process_or_arbitrary_command(self):
        code, argv = self.route("moos://app/task-manager/kill-all")
        self.assertEqual((code, argv), (2, []))

    def test_my_apps_exposes_the_same_fixed_route(self):
        ui = ROOT / "system_files/usr/share/moos/apps/store"
        self.assertIn('"task-manager": "moos://app/task-manager"', (ui / "main.qml").read_text())
        self.assertIn('openSystemRoute("task-manager")', (ui / "LibraryPage.qml").read_text())


if __name__ == "__main__":
    unittest.main()
