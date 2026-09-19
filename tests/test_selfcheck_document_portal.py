#!/usr/bin/env python3
"""A running portal with a missing FUSE mount broke real app launches."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DocumentPortal(unittest.TestCase):
    def probe(self, active="0", filesystem="fuse.portal", reachable="0"):
        source = (ROOT / "system_files/usr/bin/moos-selfcheck").read_text()
        block = source.split('portal_path=', 1)[1].split('# ── The lock screen', 1)[0]
        mocks = '''
ok() { echo "OK $*"; }
bad() { echo "BAD $*"; }
note() { echo "NOTE $*"; }
systemctl() { return "$ACTIVE"; }
findmnt() { echo "$FILESYSTEM"; }
timeout() { return "$REACHABLE"; }
'''
        env = dict(os.environ, ACTIVE=active, FILESYSTEM=filesystem,
                   REACHABLE=reachable, XDG_RUNTIME_DIR="/nonexistent/moos-test",
                   DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent/moos-test")
        return subprocess.run(["bash", "-c", mocks + '\nportal_path=' + block],
                              env=env, text=True, capture_output=True, check=True).stdout

    def test_mounted_and_reachable(self):
        self.assertIn("OK", self.probe())

    def test_active_without_mount(self):
        self.assertIn("BAD", self.probe(filesystem="tmpfs"))

    def test_disconnected_mount(self):
        self.assertIn("BAD", self.probe(reachable="1"))

    def test_stat_timeout(self):
        self.assertIn("BAD", self.probe(reachable="124"))

    def test_inactive_is_not_a_broken_on_demand_service(self):
        self.assertIn("NOTE", self.probe(active="3"))


if __name__ == "__main__":
    unittest.main()
