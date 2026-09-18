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

    def test_every_build_run_the_cycle_may_use_is_one_promotion_would_accept(self):
        """A cycle must not spend an hour of CI proving a build promotion will refuse.

        promote-x86.yml validates every run id it is handed with four conditions.
        The script picks the build run with its own query, and that query used to
        omit `.event` — so it happily reused the nightly's or a push's build of the
        same revision, ran the four proofs against it, and died at the last step
        with a message that reads like someone swapped the evidence.
        """
        promote = (WORKFLOWS / "promote-x86.yml").read_text(encoding="utf-8")
        for condition in ('.conclusion == "success"', '.event == "workflow_dispatch"',
                          ".head_sha == $revision", ".run_attempt == 1"):
            self.assertIn(condition, promote, f"promote-x86.yml lost its {condition} check")
        # Both places that can hand a build run to promotion: the reuse of an existing
        # build, and the adoption of one that superseded a cancelled dispatch.
        selections = [block for block in self.text.split("gh run list --workflow")[1:]
                      if "databaseId" in block.split("\n")[0]]
        self.assertGreaterEqual(len(selections), 2, "the run-selection queries moved")
        for block in selections:
            query = block[:block.index("2>/dev/null")]
            for condition in ('.status == \\"completed\\"', '.conclusion == \\"success\\"',
                              ".attempt == 1", '.event == \\"workflow_dispatch\\"'):
                self.assertIn(condition, query,
                              f"a run-selection query accepts runs promotion refuses: {condition}")

    def test_the_x86_decision_does_not_wait_on_the_arm_proof_it_discards(self):
        """ARM never counted toward x86_ok; it should not delay the promotion either."""
        decision = self.text[self.text.index("x86_ok=1"):self.text.index("promotion=(")]
        self.assertNotIn("arm", decision,
                         "the x86 decision loop must not wait on the ARM proof")
        # It is still dispatched, still waited for, and still reported.
        self.assertIn("dispatch build-arm.yml", self.text)
        self.assertIn('wait "${pid_of[arm]}"', self.text)
        self.assertIn('cat "$work/arm.result"', self.text)

    def test_a_release_cycle_can_actually_promote_arm(self):
        """The cycle dispatches build-arm.yml; its promote job must accept a dispatch.

        It required `push` only, so every cycle built ARM, boot-proved it, and skipped
        the job that ships it — `moos-arm:latest` tracked whatever pushed last instead
        of the revision the cycle proved.
        """
        arm = (WORKFLOWS / "build-arm.yml").read_text(encoding="utf-8")
        promote = arm[arm.index("  promote:"):]
        condition = promote[promote.index("if:"):promote.index("\n", promote.index("if:"))]
        self.assertIn("workflow_dispatch", condition,
                      "build-arm.yml's promote job cannot be reached by a release cycle")
        self.assertIn("refs/heads/main", condition,
                      "build-arm.yml's promote job must stay restricted to main")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseCandidateScript))
    sys.exit(0 if result.wasSuccessful() else 1)
