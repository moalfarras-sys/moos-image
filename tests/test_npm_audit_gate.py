#!/usr/bin/env python3
""""npm could not answer" may never be spelled the same way as "nothing found".

On 2026-09-19 the signed build failed for all three x86 editions on this line in
build.yml:

    npm audit --audit-level=high

npm's registry returned 400 on an endpoint it was in the middle of retiring, and
said so: "This endpoint is being retired. Use the bulk advisory endpoint
instead." The package tree was fine — `npm ci` had installed 378 packages and
`tsc --noEmit` had passed — and the same command on the maintainer's station
reported "found 0 vulnerabilities".

That red looks exactly like a vulnerability, which makes the obvious repair
`|| true`. Do that and the check still appears in every build log, still costs
three seconds, and can never fail again.

So the gate distinguishes the two cases and this test holds the distinction. It
runs the real script against fixture reports with a stub `npm`, so it needs no
network and cannot pass by accident on a machine that happens to be online.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts/npm-audit-gate.sh"
WORKFLOW = ROOT / ".github/workflows/build.yml"

# The two shapes, measured from npm 10.9.8 rather than assumed.
CLEAN = {"auditReportVersion": 2, "vulnerabilities": {},
         "metadata": {"vulnerabilities": {"info": 0, "low": 0, "moderate": 0,
                                          "high": 0, "critical": 0, "total": 0}}}
HIGH = {"auditReportVersion": 2,
        "vulnerabilities": {"tar-fs": {"severity": "high", "via": ["CVE-0000-0000"]}},
        "metadata": {"vulnerabilities": {"info": 0, "low": 0, "moderate": 0,
                                         "high": 1, "critical": 0, "total": 1}}}
# What a retiring or unreachable endpoint actually returns: no metadata at all.
UNANSWERED = {"error": {"summary": "", "detail": ""}, "message": "audit endpoint returned an error"}


@unittest.skipIf(not GATE.is_file(), "the audit gate is missing")
class TheGateTellsTheTwoApartest(unittest.TestCase):
    def run_gate(self, payload, *, exit_code: int = 0, attempts: int = 2):
        """Run the real script with a stub npm that prints `payload`."""
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            stub = work / "npm"
            stub.write_text(
                "#!/bin/sh\n"
                f"cat <<'REPORT'\n{json.dumps(payload)}\nREPORT\n"
                f"exit {exit_code}\n",
                encoding="utf-8")
            stub.chmod(0o755)
            result = subprocess.run(
                ["bash", str(GATE), "high"],
                capture_output=True, text=True, timeout=120,
                env={**os.environ,
                     "PATH": f"{work}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                     "NPM_AUDIT_ATTEMPTS": str(attempts)})
            return result

    def test_a_clean_report_passes(self):
        result = self.run_gate(CLEAN)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no high-or-worse", result.stdout)

    def test_a_high_advisory_fails_and_names_it(self):
        result = self.run_gate(HIGH, exit_code=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("npm audit found", result.stdout)
        self.assertIn("tar-fs", result.stdout,
                      "the build log must name what it refused to ship")

    def test_an_unanswered_audit_fails_and_does_not_claim_to_be_clean(self):
        """The defect this whole file exists for."""
        result = self.run_gate(UNANSWERED, exit_code=1)
        self.assertEqual(
            result.returncode, 1,
            "an audit that never happened must not be reported as a pass")
        combined = result.stdout + result.stderr
        self.assertIn("REGISTRY failure", combined)
        self.assertIn("has NOT been cleared", combined)
        self.assertNotIn("no high-or-worse", combined,
                         "an unanswered audit must never print the clean message")

    def test_it_retries_before_giving_up(self):
        """A single transient 400 should not cost a release cycle."""
        result = self.run_gate(UNANSWERED, exit_code=1, attempts=3)
        self.assertEqual(result.stderr.count("did not return a report"), 3)


class TheWorkflowUsesIt(unittest.TestCase):
    def test_build_yml_calls_the_gate_and_not_bare_npm_audit(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("scripts/npm-audit-gate.sh", workflow,
                      "build.yml must run the gate that tells the two cases apart")
        for line in workflow.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "npm-audit-gate" in stripped:
                continue
            self.assertNotRegex(
                stripped, r"^npm audit\b",
                "a bare `npm audit` is back in build.yml; it cannot tell a retiring "
                "endpoint from a vulnerability, which is how it failed three signed "
                "builds on 2026-09-19")

    def test_the_gate_is_executable_like_every_other_script(self):
        self.assertTrue(os.access(GATE, os.X_OK), f"{GATE.name} is not executable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
