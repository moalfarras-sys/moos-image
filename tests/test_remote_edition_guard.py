#!/usr/bin/env python3
"""Gate: on the ARM edition, MoOS's own remote desktop is never treated as foreign sharing.

WHY THIS EXISTS
moos-remote-guard and moos-health exist because KDE's RDP server was found listening on
*:3389 beside Mo PC Remote on the x86 station, and "turn it off" is the right answer there.
On moos-arm (the Oracle A1 cloud desktop) the same server is how MoOS itself shows a machine
that has no monitor: build-arm.sh's `moos-arm-remote` enables it with the owner's password,
behind a closed firewall, reached through an SSH tunnel. There, the health finding offered
moos://privacy/stop-sharing and the guard stopped and un-autostarted the server — one tap
would have cut the owner off from the only screen that machine has.

Both tools now read the edition the image build writes (/usr/lib/moos/edition): on moos-arm
RDP is reported as MoOS's own, with no action, and only VNC is guarded. Every other edition
keeps the x86 behaviour exactly.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "system_files/usr/bin/moos-remote-guard"
sys.path.insert(0, str(ROOT / "tests"))
from test_moos_health import HealthMachine  # noqa: E402


class GuardByEdition(unittest.TestCase):
    def run_guard(self, edition: str, *args: str) -> tuple[subprocess.CompletedProcess, list[str]]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            log = root / "calls.log"
            for name in ("systemctl", "kwriteconfig6", "ss"):
                stub = root / "bin" / name
                body = 'case "$*" in *is-active*) exit 0;; esac\n' if name == "systemctl" else ""
                stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n{body}')
                stub.chmod(0o755)
            edition_file = root / "edition"
            edition_file.write_text(edition + "\n")
            env = {"PATH": f"{root / 'bin'}:/usr/bin:/bin", "HOME": str(root),
                   "MOOS_EDITION_FILE": str(edition_file), "LANG": "C.UTF-8"}
            done = subprocess.run(["bash", str(GUARD), *args], env=env, capture_output=True,
                                  text=True, timeout=30)
            return done, (log.read_text().splitlines() if log.exists() else [])

    def test_x86_editions_turn_off_both_foreign_servers(self):
        for edition in ("moos", "moos-nvidia", "moos-cloud", ""):
            with self.subTest(edition=edition):
                done, calls = self.run_guard(edition, "off")
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("systemctl --user stop app-org.kde.krdpserver.service", calls)
                self.assertIn("systemctl --user stop app-org.kde.krfb.service", calls)

    def test_arm_keeps_its_own_remote_desktop(self):
        done, calls = self.run_guard("moos-arm", "off")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertFalse([call for call in calls if "krdpserver" in call],
                         "on moos-arm the guard touched MoOS's own remote desktop")
        self.assertIn("systemctl --user stop app-org.kde.krfb.service", calls)
        status, _calls = self.run_guard("moos-arm", "status")
        self.assertIn("MoOS's own remote desktop", status.stdout)


class HealthByEdition(unittest.TestCase):
    def finding(self, edition: str) -> dict:
        machine = HealthMachine()
        try:
            machine.edition.write_text(edition + "\n")
            done = machine.run("scan")
            self.assertEqual(done.returncode, 0, done.stderr)
            import json
            report = json.loads((machine.state / "latest.json").read_text())
            findings = {item["id"]: item for item in report["findings"]}
            return findings["open-port-tcp-3389"]
        finally:
            machine.close()

    def test_x86_rdp_is_a_warning_with_the_off_switch(self):
        item = self.finding("moos-nvidia")
        self.assertEqual(item["severity"], "warning")
        self.assertEqual(item["action"], "moos://privacy/stop-sharing")

    def test_arm_rdp_is_information_with_nothing_to_press(self):
        item = self.finding("moos-arm")
        self.assertEqual(item["severity"], "info")
        self.assertEqual(item["action"], "", "an off switch here would cut the owner off")
        self.assertIn("SSH tunnel", item["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
