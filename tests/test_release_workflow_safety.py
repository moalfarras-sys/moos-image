#!/usr/bin/env python3
"""Hold release-critical CI invariants that have failed in production."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
DISK_WORKFLOW = ROOT / ".github" / "workflows" / "build-disk.yml"
ISO_WORKFLOW = ROOT / ".github" / "workflows" / "build-iso.yml"


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

    def test_disk_boot_proof_never_mutates_the_published_qcow(self) -> None:
        text = DISK_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("moos-disk-serial-test.qcow2", text)
        self.assertRegex(text, r"qemu-img create[^\n]*-q -f qcow2")
        self.assertIn('-b "$(realpath "$QCOW")" "$TEST_QCOW"', text)
        self.assertIn('qemu-nbd --connect=/dev/nbd0 -f qcow2 "$TEST_QCOW"', text)
        self.assertIn('-drive file="$TEST_QCOW",format=qcow2,if=virtio', text)
        self.assertIn("moos-qcow.pristine.sha256", text)
        self.assertNotIn('qemu-nbd --connect=/dev/nbd0 -f qcow2 "$QCOW"; sleep 3\n          MNT=', text)

    def test_disk_gate_requires_firmware_and_the_graphical_path(self) -> None:
        text = DISK_WORKFLOW.read_text(encoding="utf-8")
        missing_firmware = text.split('if [ -z "$OVMF_CODE" ]', 1)[1].split(
            "          fi\n", 1
        )[0]
        self.assertIn("exit 1", missing_firmware)
        positive = text.split("# Positive gate:", 1)[1]
        self.assertNotIn("Basic System", positive)
        self.assertNotIn("Multi-User", positive)
        self.assertRegex(positive, r"Graphical|Display Manager|plasma-login-manager|plasmalogin")

    def test_iso_builder_is_immutable_and_both_artifacts_use_verified_digests(self) -> None:
        iso = ISO_WORKFLOW.read_text(encoding="utf-8")
        disk = DISK_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "uses: ublue-os/titanoboa@5c457c3d0518bd17e754be0fd98a60d29d26abb4",
            iso,
        )
        self.assertNotIn("ublue-os/titanoboa@main", iso)
        for name, text in (("ISO", iso), ("disk", disk)):
            self.assertIn('docker-manifest-digest', text, name)
            self.assertIn('cosign verify --key cosign.pub "${pinned_ref}"', text, name)
            self.assertIn("steps.pin.outputs.image_ref", text, name)
            self.assertRegex(text, r"sha256:\[0-9a-f\]\{64\}")
        self.assertIn("image-ref: ${{ steps.pin.outputs.image_ref }}", iso)
        self.assertIn('IMAGE_REF: ${{ steps.pin.outputs.image_ref }}', iso)
        self.assertIn('podman pull "${{ steps.pin.outputs.image_ref }}"', disk)
        self.assertIn('"${{ steps.pin.outputs.image_ref }}"', disk)


if __name__ == "__main__":
    unittest.main()
