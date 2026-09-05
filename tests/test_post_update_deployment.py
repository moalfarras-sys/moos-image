#!/usr/bin/env python3
"""Execute the real deployment diagnostic with isolated status/registry commands."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "tests/post-update-check.sh").read_text()
# Stop before the unrelated live desktop probes. This executes the same functions
# and invocation as the full checker, without inspecting or changing the host.
DEPLOYMENT_CHECK = SCRIPT.split("# The signature policy", 1)[0] + '\nexit "$fail"\n'
OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64
REPOSITORY = "ghcr.io/moalfarras-sys/moos-arm"
UNSET = object()


def status(origin=None, digest=OLD):
    booted = {"booted": True, "container-image-reference-digest": digest}
    if origin is not None:
        booted["container-image-reference"] = origin
    return {"deployments": [
        {"staged": True, "container-image-reference-digest": NEW,
         "container-image-reference": "ostree-image-signed:docker://other/staged:latest"},
        booted,
    ]}


class DeploymentCheckTests(unittest.TestCase):
    def run_check(self, payload, *, expected=UNSET, registry=OLD,
                  bootc=None, registry_exit=0):
        with tempfile.TemporaryDirectory(prefix="moos-post-update-test-") as directory:
            work = Path(directory)
            calls = work / "calls.jsonl"
            stub = """#!/usr/bin/env python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
with open(os.environ["TEST_CALLS"], "a") as stream:
    stream.write(json.dumps([name, *sys.argv[1:]]) + "\\n")
if name == "rpm-ostree":
    print(os.environ["TEST_STATUS"])
elif name == "sudo":
    payload = os.environ.get("TEST_BOOTC", "")
    if not payload:
        sys.exit(1)
    print(payload)
else:
    print(json.dumps({"Digest": os.environ["TEST_REGISTRY"]}))
    sys.exit(int(os.environ["TEST_REGISTRY_EXIT"]))
"""
            for command in ("rpm-ostree", "sudo", "skopeo"):
                target = work / command
                target.write_text(stub)
                target.chmod(0o755)
            env = os.environ.copy()
            env.pop("MOOS_EXPECTED_DIGEST", None)
            env.update(PATH=f"{work}:{env['PATH']}", TEST_CALLS=str(calls),
                       TEST_STATUS=json.dumps(payload), TEST_REGISTRY=registry,
                       TEST_REGISTRY_EXIT=str(registry_exit),
                       TEST_BOOTC=json.dumps(bootc) if bootc is not None else "")
            if expected is not UNSET:
                env["MOOS_EXPECTED_DIGEST"] = expected
            result = subprocess.run(["bash", "-c", DEPLOYMENT_CHECK], env=env,
                                    text=True, capture_output=True, timeout=10)
            commands = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
            return result, commands

    def test_pinned_arm_origin_is_not_latest_release_proof(self):
        origin = f"docker://{REPOSITORY}@{OLD}"
        result, commands = self.run_check(status("ostree-image-signed:" + origin))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("matches its pinned origin", result.stdout)
        self.assertIn("does not check for newer releases", result.stdout)
        self.assertEqual(commands, [["rpm-ostree", "status", "--json"], ["skopeo", "inspect", origin]])

    def test_each_edition_queries_only_its_own_tag(self):
        for edition in ("moos", "moos-cloud", "moos-nvidia", "moos-arm"):
            with self.subTest(edition=edition):
                origin = f"docker://ghcr.io/moalfarras-sys/{edition}:latest"
                result, commands = self.run_check(status("ostree-image-signed:" + origin))
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertIn("matches the tracked tag at check time", result.stdout)
                self.assertEqual(commands[-1], ["skopeo", "inspect", origin])

    def test_missing_origin_does_not_query_a_sibling(self):
        result, commands = self.run_check(status())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not read the booted image origin", result.stdout)
        self.assertFalse(any(call[0] == "skopeo" for call in commands))

    def test_expected_candidate_is_checked_without_registry(self):
        for expected, exit_code in ((OLD, 0), (NEW, 1)):
            with self.subTest(expected=expected):
                result, commands = self.run_check(
                    status(f"ostree-image-signed:docker://{REPOSITORY}@{OLD}"),
                    expected=expected, registry=NEW)
                self.assertEqual(result.returncode, exit_code, result.stdout)
                self.assertIn("expected candidate", result.stdout)
                self.assertFalse(any(call[0] == "skopeo" for call in commands))

    def test_invalid_expected_digest_fails_before_commands(self):
        for expected in ("", "sha256:bad", " " + OLD, OLD + "\n", "sha256:" + "A" * 64):
            with self.subTest(expected=repr(expected)):
                result, commands = self.run_check(status(), expected=expected)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("MOOS_EXPECTED_DIGEST must be", result.stdout)
                self.assertEqual(commands, [])

    def test_missing_origin_fails_even_with_expected_digest(self):
        result, commands = self.run_check(status(), expected=OLD)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("origin", result.stdout)
        self.assertFalse(any(call[0] == "skopeo" for call in commands))

    def test_missing_or_malformed_status_fails_without_registry(self):
        for payload in ({}, {"deployments": []}, {"deployments": "invalid"}):
            with self.subTest(payload=payload):
                result, commands = self.run_check(payload)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("could not read the booted image origin", result.stdout)
                self.assertFalse(any(call[0] == "skopeo" for call in commands))

    def test_invalid_booted_digest_cannot_pass_candidate_check(self):
        result, commands = self.run_check(
            status(f"ostree-image-signed:docker://{REPOSITORY}:latest", digest="invalid"),
            expected=OLD)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not read a valid booted image digest", result.stdout)
        self.assertFalse(any(call[0] == "skopeo" for call in commands))

    def test_bootc_fallback_reads_origin_and_digest_together(self):
        bootc = {"status": {"booted": {"image": {
            "imageDigest": OLD,
            "image": {"image": f"{REPOSITORY}@{OLD}", "transport": "registry"},
        }}}}
        result, commands = self.run_check({}, bootc=bootc)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(commands[-1], ["skopeo", "inspect", f"docker://{REPOSITORY}@{OLD}"])

    def test_changed_tag_does_not_claim_reboot_failure(self):
        result, _ = self.run_check(status(f"ostree-image-signed:docker://{REPOSITORY}:latest"), registry=NEW)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("currently resolves to", result.stdout)
        self.assertNotIn("reboot did not take", result.stdout)

    def test_registry_failure_cannot_pass_with_partial_output(self):
        for registry, exit_code in (("invalid", 0), (OLD, 1)):
            result, _ = self.run_check(status(f"ostree-image-signed:docker://{REPOSITORY}:latest"),
                                       registry=registry, registry_exit=exit_code)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("registry verification is unavailable", result.stdout)


if __name__ == "__main__":
    unittest.main()
