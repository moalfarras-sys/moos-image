#!/usr/bin/env python3
"""Gate: P1.2 — boot-success health and automatic fallback, on the boot loader MoOS has.

WHY THIS EXISTS

MoOS cannot use the stock Fedora mechanism. /boot is read-only on bootc/OSTree, so
`grub2-set-bootflag boot_success` fails on every boot (build.sh masks grub-boot-success
for exactly that reason), greenboot is not installed, and bootc never reads grubenv. So the
counter lives in /var/lib/moos and the fallback is `bootc rollback`.

That makes the REFUSALS the dangerous part, not the rollback. `bootc rollback` is a toggle:
run it when a rollback is already queued and it CANCELS that rollback, making the broken
system default again. An automatic path that fires blindly after a failed boot would undo
the rescue a user just queued from the Recovery window. The cases below therefore spend more
effort on when the machine must NOT act than on when it must.

The other thing under test is what counts as a healthy boot: the default target becoming
active, and nothing else. A failed printer unit is recorded and ignored — an unrelated
failed unit must never revert somebody's operating system.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "system_files/usr/libexec/moos-boot-assess"
ARM_UNIT = ROOT / "system_files/usr/lib/systemd/system/moos-boot-assess-arm.service"
BLESS_TIMER = ROOT / "system_files/usr/lib/systemd/system/moos-boot-assess-bless.timer"

FAKE_RPM_OSTREE = """#!/usr/bin/bash
cat "$MOOS_TEST_DEPLOYMENTS"
"""

FAKE_RECORDER = """#!/usr/bin/bash
printf '%s %s\\n' "$(basename "$0")" "$*" >>"$MOOS_TEST_CALLS"
exit 0
"""

# get-default prints the target; is-active answers from a file the test controls, so a boot
# can be made to look finished or hung without waiting for one.
FAKE_SYSTEMCTL = """#!/usr/bin/bash
printf '%s %s\\n' systemctl "$*" >>"$MOOS_TEST_CALLS"
case "$1" in
  get-default) printf '%s\\n' "graphical.target" ;;
  is-active)   [ "$MOOS_TEST_TARGET_ACTIVE" = "1" ] ;;
  --failed)    cat "$MOOS_TEST_FAILED_UNITS" 2>/dev/null || true ;;
  *)           exit 0 ;;
esac
"""


def deployment(checksum: str, *, booted: bool = False, staged: bool = False,
               version: str = "44.1") -> dict:
    return {"checksum": checksum, "booted": booted, "staged": staged, "version": version}


class Machine:
    """A fake machine: a deployment list, a default target, and recorded commands."""

    def __init__(self, case: unittest.TestCase, deployments: list[dict], *,
                 target_active: bool = True, failed_units: str = "") -> None:
        self.root = Path(case.enterContext(tempfile.TemporaryDirectory(prefix="moos-boot-")))
        self.calls = self.root / "calls.txt"
        self.calls.write_text("", encoding="utf-8")
        self.deployments_file = self.root / "deployments.json"
        self.set_deployments(deployments)
        self.failed_file = self.root / "failed.txt"
        self.failed_file.write_text(failed_units, encoding="utf-8")
        self.state_file = self.root / "boot-assessment.json"

        binaries = self.root / "bin"
        binaries.mkdir()
        for name, body in (("rpm-ostree", FAKE_RPM_OSTREE), ("bootc", FAKE_RECORDER),
                           ("systemctl", FAKE_SYSTEMCTL)):
            path = binaries / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)

        self.env = os.environ | {
            "MOOS_BOOT_ASSESS_STATE": str(self.state_file),
            "MOOS_BOOT_ASSESS_RPM_OSTREE": str(binaries / "rpm-ostree"),
            "MOOS_BOOT_ASSESS_BOOTC": str(binaries / "bootc"),
            "MOOS_BOOT_ASSESS_SYSTEMCTL": str(binaries / "systemctl"),
            "MOOS_BOOT_ASSESS_MAX": "3",
            "MOOS_BOOT_ASSESS_WAIT": "0",
            "MOOS_BOOT_ASSESS_POLL": "0.01",
            "MOOS_TEST_DEPLOYMENTS": str(self.deployments_file),
            "MOOS_TEST_CALLS": str(self.calls),
            "MOOS_TEST_FAILED_UNITS": str(self.failed_file),
            "MOOS_TEST_TARGET_ACTIVE": "1" if target_active else "0",
        }

    def set_deployments(self, deployments: list[dict]) -> None:
        self.deployments_file.write_text(json.dumps({"deployments": deployments}),
                                         encoding="utf-8")

    def run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(TOOL), *args], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def boot(self, times: int = 1) -> subprocess.CompletedProcess:
        result = None
        for _ in range(times):
            result = self.run("arm")
        return result

    @property
    def state(self) -> dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    @property
    def recorded(self) -> str:
        return self.calls.read_text(encoding="utf-8")

    @property
    def rolled_back(self) -> bool:
        return "bootc rollback" in self.recorded


HEALTHY = [deployment("aaa" * 20, booted=True), deployment("bbb" * 20)]


class BootAssessment(unittest.TestCase):
    def test_three_unblessed_boots_return_to_the_previous_deployment(self):
        machine = Machine(self, HEALTHY)
        machine.boot(2)
        self.assertFalse(machine.rolled_back, "two failures must not trigger a rollback")
        self.assertEqual(machine.state["attempts"], 2)
        machine.boot()
        self.assertTrue(machine.rolled_back, "the third unblessed boot must fall back")
        self.assertIn("systemctl reboot", machine.recorded)
        self.assertEqual(machine.state["last_result"], "rolled-back")

    def test_a_blessed_boot_clears_the_counter(self):
        machine = Machine(self, HEALTHY)
        machine.boot(2)
        self.assertEqual(machine.run("bless").returncode, 0)
        self.assertEqual(machine.state["attempts"], 0)
        self.assertEqual(machine.state["last_result"], "blessed")
        machine.boot(2)
        self.assertFalse(machine.rolled_back,
                         "after a good boot the machine must get a full set of attempts again")

    def test_a_boot_that_never_reaches_its_target_is_not_blessed(self):
        machine = Machine(self, HEALTHY, target_active=False)
        machine.boot()
        self.assertEqual(machine.run("bless").returncode, 1)
        self.assertEqual(machine.state["attempts"], 1, "a hung boot must not clear the counter")

    def test_it_refuses_when_a_rollback_is_already_queued(self):
        """The toggle: acting here would CANCEL the rescue the user queued."""
        queued = [deployment("bbb" * 20), deployment("aaa" * 20, booted=True)]
        machine = Machine(self, queued)
        machine.boot(3)
        self.assertFalse(machine.rolled_back,
                         "bootc rollback with one already queued cancels it — never do that")
        self.assertIn("already queued", machine.state["last_result"])

    def test_it_refuses_when_there_is_nothing_to_roll_back_to(self):
        machine = Machine(self, [deployment("aaa" * 20, booted=True)])
        machine.boot(3)
        self.assertFalse(machine.rolled_back)
        self.assertIn("no previous deployment", machine.state["last_result"])

    def test_a_staged_update_is_not_mistaken_for_a_queued_rollback(self):
        staged = [deployment("ccc" * 20, staged=True),
                  deployment("aaa" * 20, booted=True), deployment("bbb" * 20)]
        machine = Machine(self, staged)
        machine.boot(3)
        self.assertTrue(machine.rolled_back,
                        "a pending upgrade sorts ahead of booted but is not a queued rollback")

    def test_it_never_rolls_away_from_the_same_deployment_twice(self):
        machine = Machine(self, HEALTHY)
        machine.boot(3)
        self.assertTrue(machine.rolled_back)
        machine.calls.write_text("", encoding="utf-8")
        machine.boot(3)
        self.assertFalse(machine.rolled_back,
                         "a machine must not ping-pong between two broken deployments")
        self.assertEqual(machine.state["last_result"], "exhausted")

    def test_booting_a_different_deployment_starts_the_count_over(self):
        machine = Machine(self, HEALTHY)
        machine.boot(2)
        machine.set_deployments([deployment("ddd" * 20, booted=True), deployment("aaa" * 20)])
        machine.boot()
        self.assertEqual(machine.state["attempts"], 1)
        self.assertFalse(machine.rolled_back)

    def test_failed_units_are_recorded_but_never_cause_a_rollback(self):
        machine = Machine(self, HEALTHY,
                          failed_units="cups.service loaded failed failed Printing\n")
        self.assertEqual(machine.run("bless").returncode, 0)
        self.assertEqual(machine.state["failed_units"], ["cups.service"])
        self.assertEqual(machine.state["last_result"], "blessed")
        self.assertFalse(machine.rolled_back,
                         "a printer that did not start is not a reason to revert an OS")

    def test_manual_recovery_is_left_alone(self):
        """It must not INVOKE or disable the manual path. Naming it in prose is the point:
        the docstring credits moos-rollback for the toggle semantics this relies on."""
        import ast
        source = TOOL.read_text(encoding="utf-8")
        code = source
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                documentation = ast.get_docstring(node, clean=False)
                if documentation:
                    code = code.replace(documentation, "")
        code = "\n".join(line for line in code.splitlines()
                         if not line.lstrip().startswith("#"))
        for forbidden in ("systemctl mask", "systemctl disable", "moos-rollback",
                          "rpm-ostree rollback", "moai-do"):
            self.assertNotIn(forbidden, code,
                             "automatic fallback must not touch the manual recovery path")
        self.assertIn("moos-rollback", source,
                      "the toggle semantics this depends on must stay documented")

    def test_the_units_ship_in_a_usable_shape(self):
        arm = ARM_UNIT.read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/libexec/moos-boot-assess arm", arm)
        self.assertIn("WantedBy=multi-user.target", arm,
                      "the counter must be armed on every boot or it counts nothing")
        self.assertIn("Before=display-manager.service", arm)
        timer = BLESS_TIMER.read_text(encoding="utf-8")
        self.assertIn("OnBootSec=", timer)
        self.assertIn("WantedBy=timers.target", timer)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(BootAssessment))
    sys.exit(0 if result.wasSuccessful() else 1)
