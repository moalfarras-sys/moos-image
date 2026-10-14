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
import os
import re
import subprocess
import sys
import tempfile
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
        self.assertIn('[ "$(gh_read run view "$id" --json headSha --jq .headSha)" = "$revision" ]', self.text)

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
        selections = [block for block in self.text.split("gh_read run list --workflow")[1:]
                      if "databaseId" in block.split("\n")[0] and "build-arm.yml" not in block.split("\n")[0]]
        self.assertGreaterEqual(len(selections), 2, "the run-selection queries moved")
        for block in selections:
            query = block[:block.index('][0].databaseId"')]
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

    def test_arm_reuse_rechecks_metadata_and_refuses_stale_or_unproven_runs(self):
        """Execute the actual selection block without a network or live dispatch."""
        block = self.text[self.text.index("# ARM's main-push run"):self.text.index('echo "proofs:')]
        valid = "abc main push 1 in_progress pending"
        cases = [
            (valid, True), ("abc main workflow_dispatch 1 completed success", True),
            ("abc main push 1 queued pending", True),
            ("abc main push 1 waiting pending", True),
            ("other main push 1 in_progress pending", False),
            ("abc other push 1 in_progress pending", False),
            ("abc main push 2 completed success", False),
            ("abc main schedule 1 completed success", False),
            ("abc main pull_request 1 completed success", False),
            ("abc main push 1 completed failure", False),
            ("abc main push 1 completed cancelled", False),
        ]
        for metadata, accepted in cases:
            with self.subTest(metadata=metadata):
                stub = ('revision=abc; ref=main\n'
                        'gh() { if [ "$2" = list ]; then echo 71; '
                        'else printf "%s\\n" "$MOOS_ARM_TEST_METADATA"; fi; }\n'
                        'gh_read() { gh "$@"; }\n'
                        'dispatch() { echo "unexpected dispatch" >&2; return 99; }\n')
                result = subprocess.run(["bash", "-eu", "-c", stub + block],
                                        env={**os.environ, "MOOS_ARM_TEST_METADATA": metadata},
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, accepted, result.stderr)
        fallback = ('revision=abc; ref=main\n'
                    'gh() { echo null; }\n'
                    'gh_read() { gh "$@"; }\n'
                    'dispatch() { [ "$1" = build-arm.yml ] || return 99; echo 72; }\n')
        result = subprocess.run(["bash", "-eu", "-c", fallback + block + '\necho "$arm_id"'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "72")

    def metadata_fixture(self, command, failures=1, error="gh: HTTP 500", status=1):
        """Run real retry/dispatch functions; no network, Actions mutation or host changes."""
        helper = self.text[self.text.index('gh_read() {'):self.text.index('\n# wait_run')]
        with tempfile.TemporaryDirectory(prefix="moos-release-read-test-") as work:
            env = {**os.environ, "MOOS_READ_TEST_WORK": work,
                   "MOOS_READ_TEST_FAILURES": str(failures), "MOOS_READ_TEST_ERROR": error,
                   "MOOS_READ_TEST_STATUS": str(status)}
            stub = r'''
set -euo pipefail
work="$MOOS_READ_TEST_WORK"; revision=abc; ref=main
gh() {
    printf '%s %s\n' "$1" "$2" >> "$work/calls"
    if [ "$1:$2" = workflow:run ]; then
        echo https://github.com/example/moos/actions/runs/71
        return 0
    fi
    local count=0
    [ ! -f "$work/count" ] || count="$(cat "$work/count")"
    count=$((count + 1)); echo "$count" > "$work/count"
    if [ "$count" -le "$MOOS_READ_TEST_FAILURES" ]; then
        echo discarded-partial-output
        printf '%s\n' "$MOOS_READ_TEST_ERROR" >&2
        return "$MOOS_READ_TEST_STATUS"
    fi
    echo abc
}
timeout() {
    [ "$1" = --kill-after=5s ] || return 99
    shift
    [ "$1" = 30s ] || return 99
    shift; "$@"
}
sleep() { printf 'sleep %s\n' "$1" >> "$work/calls"; }
'''
            result = subprocess.run(["bash", "-c", stub + helper + '\n' + command],
                                    env=env, capture_output=True, text=True, timeout=10)
            calls = Path(work, 'calls').read_text().splitlines() if Path(work, 'calls').exists() else []
            leftovers = list(Path(work).glob('read.*'))
            self.assertEqual(leftovers, [], "private retry scratch must be retired")
            return result, calls

    def test_dispatch_recovers_metadata_read_without_another_post(self):
        result, calls = self.metadata_fixture('dispatch build.yml', failures=2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "71")
        self.assertEqual(calls, ['workflow run', 'run view', 'sleep 2',
                                'run view', 'sleep 4', 'run view'])
        self.assertIn('dispatched build.yml run 71:', result.stderr)
        # The previous single GET loses the already-created run on the first 500.
        old = self.text[self.text.index('dispatch() {'):self.text.index('\n# wait_run')]
        old = old.replace('gh_read run view', 'gh run view')
        result, calls = self.metadata_fixture(old + '\ndispatch build.yml', failures=2)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ['workflow run', 'run view'])

    def test_read_retries_are_bounded_and_discard_failed_stdout(self):
        for error, status in [('gh: HTTP 503', 1), ('gh: HTTP 429', 1),
                              ('dial tcp: i/o timeout', 1), ('', 124), ('', 137)]:
            with self.subTest(error=error, status=status):
                result, calls = self.metadata_fixture('gh_read run view 71', 9, error, status)
                self.assertEqual(result.returncode, status)
                self.assertEqual(result.stdout, '')
                self.assertEqual(calls, ['run view', 'sleep 2', 'run view', 'sleep 4', 'run view'])
        result, calls = self.metadata_fixture('gh_read run view 71', 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'abc')
        self.assertEqual(calls, ['run view', 'sleep 2', 'run view'])

    def test_authentication_errors_and_mutations_are_never_retried(self):
        result, calls = self.metadata_fixture('gh_read run view 71', 9, 'gh: HTTP 403')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls, ['run view'])
        result, calls = self.metadata_fixture('gh_read workflow run build.yml')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [])

    def test_a_successful_read_of_the_wrong_revision_still_refuses_the_run(self):
        result, calls = self.metadata_fixture('revision=other; dispatch build.yml', failures=0)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ['workflow run', 'run view'])
        self.assertIn('is not on other', result.stderr)

    def test_failed_private_directory_creation_stops_before_any_api_call(self):
        result, calls = self.metadata_fixture('mktemp() { return 1; }; gh_read run view 71')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls, [])

    def test_unreadable_build_listing_cannot_create_a_duplicate_build(self):
        begin = self.text.index('build_id="$(gh_read run list --workflow build.yml')
        end = self.text.index('\n# If the dispatched build was superseded', begin)
        block = self.text[begin:end]
        result, calls = self.metadata_fixture(block, failures=9)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('workflow run', calls)
        self.assertIn('refusing duplicate dispatch', result.stderr)
        # Restore the former failure-to-empty fallback: it mutates despite no
        # readable evidence that a signed build is absent.
        old = block.replace('gh_read run list', 'gh run list')
        old = old.replace('|| {\n    echo "release-candidate: signed build listing is unreadable; refusing duplicate dispatch" >&2\n    exit 1\n}', '|| build_id=""')
        result, calls = self.metadata_fixture('wait_run() { return 0; }\n' + old, failures=9)
        self.assertIn('workflow run', calls, 'the restored old fallback must expose duplicate dispatch')


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReleaseCandidateScript))
    sys.exit(0 if result.wasSuccessful() else 1)
