#!/usr/bin/env python3
"""Gate: scripts/release-candidate.sh stays in step with the release workflows it drives.

WHY THIS EXISTS

Release work moved to batches (RELEASE.md, "دفعات الإصدار"): slices merge after the fast gates and
one command runs the expensive candidate proofs once per batch. That command is only safe while it
names the real workflow files, their real dispatch inputs and the real candidate-proof artifacts,
and while it keeps the promotion contract: exact signed digests from the same revision, no re-runs,
and a tree check against main before promoting. A renamed input would make it dispatch a proof on
the wrong image — or none — while still printing a promotion command.
"""

from pathlib import Path
import re
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/release-candidate.sh"
WORKFLOWS = ROOT / ".github/workflows"


def dispatch_inputs(workflow: str) -> set[str]:
    text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
    block = re.search(r"(?ms)^  workflow_dispatch:\n(.*?)(?=^  [a-z_]+:|^\S)", text)
    if not block:
        return set()
    return set(re.findall(r"(?m)^      ([A-Za-z0-9_-]+):\s*$", block.group(1)))


class ReleaseCandidateScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_shell_is_valid_and_executable(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        self.assertTrue(SCRIPT.stat().st_mode & 0o111, "the release command must be executable")

    def test_every_dispatched_input_exists_in_its_workflow(self):
        for workflow, name in (("build-disk.yml", "image-ref"), ("build-iso.yml", "image_ref")):
            self.assertIn(name, dispatch_inputs(workflow), f"{workflow} has no {name} input")
            self.assertIn(f'dispatch {workflow} -f "{name}=', self.text)
        promote_inputs = dispatch_inputs("promote-x86.yml")
        for name in ("revision", "build_run_id", "disk_run_id", "nvidia_disk_run_id",
                     "cloud_disk_run_id", "iso_run_id"):
            self.assertIn(name, promote_inputs, f"promote-x86.yml lost input {name}")
            self.assertIn(f'"{name}=', self.text)
        self.assertIn("dispatch build.yml", self.text)
        self.assertIn("dispatch build-arm.yml", self.text)

    def test_candidate_digests_come_from_the_signed_build_of_the_same_revision(self):
        build = (WORKFLOWS / "build.yml").read_text(encoding="utf-8")
        self.assertIn("moos-candidate-proof-${{ matrix.image_name }}", build)
        self.assertIn('-n "moos-candidate-proof-$edition"', self.text)
        self.assertIn('= "$revision" ]', self.text)
        self.assertIn("= verified ]", self.text)
        self.assertIn('[ "$(gh run view "$id" --json headSha --jq .headSha)" = "$revision" ]', self.text)

    def test_promotion_contract_is_kept(self):
        self.assertIn("--exit-status", self.text)
        self.assertNotIn("gh run rerun", self.text, "promotion accepts run_attempt 1 only")
        self.assertIn('--promote is only valid for main', self.text)
        self.assertIn("\"$(git rev-parse 'origin/main^{tree}')\"", self.text)
        self.assertIn('if [ "$x86_ok" -ne 1 ]; then', self.text)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseCandidateScript))
    sys.exit(0 if result.wasSuccessful() else 1)
