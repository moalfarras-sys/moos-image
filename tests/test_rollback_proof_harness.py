#!/usr/bin/env python3
"""Gate: the P0.4 rollback proof harness keeps its contract.

WHY THIS EXISTS

DEVELOPMENT_PLAN P0.4 requires a disposable-VM proof that a user can go back after an update:
"bad candidate and rollback; user data intact; old deployment boots". Until now nothing exercised
`bootc rollback` against a booted MoOS disk at all; Recovery only had a unit test for which
deployment it names. tests/rollback_x86_qcow2.sh boots the exact sealed QCOW2 on an overlay, writes
user data, boots a second deployment, runs the user-facing `bootc rollback`, and reads the result
back from the booted userspace.

The properties below are what make that evidence honest. Each one is a way the proof could pass
without proving anything: writing to the published artifact, reading state from the guest agent's
own mount namespace instead of the booted system, "rolling back" to the same deployment, or losing
/var and not checking it.
"""

from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests/rollback_x86_qcow2.sh"
BOOT_GATE = ROOT / "tests/boot_x86_qcow2.sh"


class RollbackProofHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = HARNESS.read_text(encoding="utf-8")

    def test_shell_and_embedded_python_are_valid(self):
        subprocess.run(["bash", "-n", str(HARNESS)], check=True)
        blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", self.text, re.S)
        self.assertEqual(len(blocks), 2, "expected the port allocator and the proof driver")
        for block in blocks:
            compile(block, str(HARNESS), "exec")

    def test_published_artifact_is_never_written(self):
        self.assertIn('qemu-img create -f qcow2 -F qcow2 -b "$qcow" "$work/overlay.qcow2"', self.text)
        self.assertIn('file=$work/overlay.qcow2', self.text)
        self.assertNotIn('file=$qcow', self.text)
        self.assertNotIn("qemu-img commit", self.text)
        self.assertIn('[ "$before_sha" = "$after_sha" ]', self.text)

    def test_only_an_exact_official_digest_is_accepted(self):
        self.assertIn(r"(moos|moos-nvidia|moos-cloud)@sha256:[0-9a-f]{64}$", self.text)

    def test_root_transactions_are_fixed_and_state_is_read_from_the_booted_system(self):
        self.assertIn('root_exec("create-new-deployment", ["/usr/bin/rpm-ostree", "kargs", f"--append={PROBE_KARG}"])',
                      self.text)
        self.assertIn('root_exec("bootc-rollback", ["/usr/bin/bootc", "rollback"])', self.text)
        self.assertEqual(self.text.count("root_exec(\""), 2, "no other root command may be added silently")
        self.assertIn('"mo@127.0.0.1", "/usr/bin/bash", "-s"', self.text)
        self.assertIn('"rpm-ostree", "status", "--json"', self.text)
        self.assertIn('"/proc/sys/kernel/random/boot_id"', self.text)

    def test_every_rollback_claim_is_checked(self):
        for claim in ("previous deployment booted", "same signed commit as before", "probe karg gone",
                      "newer deployment retained for roll-forward", "user data intact",
                      "signed origin", "no failed units"):
            self.assertIn(f'"{claim}"', self.text)
        self.assertIn('newer["booted_id"] == first["booted_id"]', self.text,
                      "a rollback to the deployment that was already booted proves nothing")
        self.assertIn("secrets.token_hex(16)", self.text)

    def test_each_phase_requires_a_new_boot(self):
        self.assertIn('wait_for_boot("after-new-deployment", first["boot_id"])', self.text)
        self.assertIn('wait_for_boot("after-rollback", newer["boot_id"])', self.text)

    def test_release_boot_gate_stays_ssh_only(self):
        self.assertNotIn("guest-exec", BOOT_GATE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RollbackProofHarness))
    sys.exit(0 if result.wasSuccessful() else 1)
