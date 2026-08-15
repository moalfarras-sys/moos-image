#!/usr/bin/env python3
"""Hold release-critical CI invariants that have failed in production."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"


class ReleaseWorkflowSafetyTests(unittest.TestCase):
    def test_heavy_sbom_scan_stays_out_of_image_release_jobs(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        forbidden = ("anchore/sbom-action", "syft scan", "cosign attest")
        for token in forbidden:
            self.assertNotIn(token, text, f"{token!r} can kill the image release runner")

    def test_all_three_images_are_signed_then_verified(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for image in ("moos", "moos-nvidia", "moos-cloud"):
            self.assertIn(f"image_name: {image}", text)
        sign = text.index("- name: Sign image with cosign")
        verify = text.index("- name: Verify signature against the OS-enforced public key")
        self.assertLess(sign, verify)
        self.assertIn("cosign sign -y --key env://COSIGN_PRIVATE_KEY", text)
        self.assertIn("cosign verify --key cosign.pub", text)

    def test_release_timeout_covers_measured_final_commit_io_but_stays_bounded(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        timeout = re.search(r"(?m)^\s*timeout-minutes:\s*(\d+)\s*$", text)
        self.assertIsNotNone(timeout, "the image release job needs an explicit timeout")
        minutes = int(timeout.group(1))
        self.assertGreaterEqual(minutes, 180)
        self.assertLessEqual(minutes, 240, "a release must still fail instead of holding a runner for 6h")
        for evidence in ("31897887537", "COMMIT moos:latest", "Copying blob"):
            self.assertIn(evidence, text, "the timeout must stay tied to the measured CI failure")


if __name__ == "__main__":
    unittest.main()
