#!/usr/bin/env python3
"""Gate: the second desktop server MoOS finds is one the owner can actually turn off.

WHAT WAS MEASURED

On the owner's station on 2026-09-18, `moos-health scan` reported one warning:

    سطح المكتب البعيد (RDP) مفتوح للشبكة | Remote Desktop (RDP) is open to the network
    tcp *:3389 — krdpserver — MoOS's remote desktop is Mo PC Remote

KDE's own RDP server was running with `Autostart=true` and `SystemUserEnabled=true`,
listening on every interface, beside Mo PC Remote (private tailnet, PIN, on-screen
indicator). The finding was right and its action opened Mo PC Remote — which does not
close the port. A warning with nothing to press is a warning people learn to scroll past.

`moos-remote-guard off` is that action: two NAMED user services and one autostart key
each, no argument from the caller, no administrator rights and nothing removed (on x86 KRDP's
Settings page is hidden too, since Mo PC Remote is MoOS's remote desktop — see
tests/test_settings_kiosk.py). This gate keeps it narrow — a helper
that can stop "whatever the caller names" is a remote-control tool, not a guard.
"""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "system_files/usr/bin/moos-remote-guard"
OPEN = ROOT / "system_files/usr/bin/moos-open"
HEALTH = ROOT / "system_files/usr/bin/moos-health"
BASH = "/usr/bin/bash" if Path("/usr/bin/bash").exists() else "bash"


class RemoteGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = GUARD.read_text(encoding="utf-8")

    def test_it_is_a_shipped_executable_that_parses(self):
        self.assertTrue(GUARD.exists())
        self.assertTrue(GUARD.stat().st_mode & 0o111, "the route runs it directly")
        done = subprocess.run([BASH, "-n", str(GUARD)], capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_only_the_two_named_servers_can_be_touched(self):
        units = set(re.findall(r"app-org\.kde\.[a-z]+\.service", self.guard))
        self.assertEqual(units, {"app-org.kde.krdpserver.service", "app-org.kde.krfb.service"})
        # Nothing may reach systemctl or kwriteconfig6 from the argument vector.
        for line in self.guard.splitlines():
            if "systemctl --user stop" in line or "systemctl --user disable" in line:
                self.assertNotIn("$1", line)
                self.assertNotIn("$@", line)
            if "kwriteconfig6" in line and "--file" in line:
                self.assertNotIn("$1", line)
                self.assertNotIn("$@", line)

    def test_it_needs_no_administrator_rights(self):
        for forbidden in ("pkexec", "sudo", "systemctl --system", "rpm-ostree"):
            self.assertNotIn(forbidden, self.guard,
                             "turning off a user service must never ask for root")

    def test_it_only_understands_status_and_off(self):
        done = subprocess.run([BASH, str(GUARD), "delete-everything"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 2)
        self.assertIn("usage:", done.stderr)

    def test_status_never_changes_anything(self):
        body = self.guard[self.guard.index("status() {"):self.guard.index("off() {")]
        for forbidden in ("systemctl --user stop", "systemctl --user disable", "kwriteconfig6"):
            self.assertNotIn(forbidden, body)


class TheFindingHasSomethingToPress(unittest.TestCase):
    def test_health_points_at_the_route_that_closes_the_port(self):
        health = HEALTH.read_text(encoding="utf-8")
        self.assertIn('"moos://privacy/stop-sharing" if desktop_share else ""', health)

    def test_the_route_exists_confirms_and_takes_no_argument(self):
        routes = OPEN.read_text(encoding="utf-8")
        self.assertIn("privacy/stop-sharing)", routes)
        body = routes[routes.index("privacy/stop-sharing)"):]
        body = body[:body.index(";;") + 2]
        self.assertIn("confirm ", body, "a state change asks first")
        self.assertIn("moos-remote-guard off", body)
        self.assertNotIn("$tgt", body, "the public scheme may not pass an argument through")


if __name__ == "__main__":
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite([loader.loadTestsFromTestCase(RemoteGuard),
                                loader.loadTestsFromTestCase(TheFindingHasSomethingToPress)])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
