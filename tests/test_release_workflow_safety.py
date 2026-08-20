#!/usr/bin/env python3
"""Hold release-critical CI invariants that have failed in production."""

from pathlib import Path
import os
import re
import stat
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
DISK_WORKFLOW = ROOT / ".github" / "workflows" / "build-disk.yml"
ISO_WORKFLOW = ROOT / ".github" / "workflows" / "build-iso.yml"
ARM_WORKFLOW = ROOT / ".github" / "workflows" / "build-arm.yml"
BOOT_VM = ROOT / "tests" / "boot-in-vm.sh"
X86_BOOT = ROOT / "tests" / "boot_x86_qcow2.sh"


def workflow_run_script(text: str, step_name: str) -> str:
    """Return one workflow step's literal run script without parsing YAML."""
    remainder = text.split(f"- name: {step_name}", 1)[1]
    remainder = remainder.split("        run: |\n", 1)[1]
    lines: list[str] = []
    for line in remainder.splitlines():
        if not line.startswith("          "):
            break
        lines.append(line[10:])
    return "\n".join(lines) + "\n"


class ReleaseWorkflowSafetyTests(unittest.TestCase):
    def test_release_helpers_are_executable(self) -> None:
        for path in (
            ROOT / "build_files" / "seal_arm_qcow2.sh",
            ROOT / "build_files" / "seal_release_qcow2.sh",
            ROOT / "build_files" / "seal_x86_qcow2.sh",
            ROOT / "tests" / "boot_live_iso.sh",
            X86_BOOT,
        ):
            self.assertTrue(
                path.stat().st_mode & stat.S_IXUSR,
                f"release workflow invokes a non-executable helper: {path}",
            )

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

    def test_every_build_is_a_run_and_revision_bound_candidate(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        script = workflow_run_script(text, "Resolve registry and tags")
        for ref in ("refs/heads/main", "refs/heads/feature", "refs/tags/v1"):
            with self.subTest(ref=ref), tempfile.NamedTemporaryFile() as output:
                env = os.environ.copy()
                env.update(
                    GITHUB_OUTPUT=output.name,
                    GITHUB_REF=ref,
                    GITHUB_REPOSITORY_OWNER="MoAlfarras-Sys",
                    GITHUB_RUN_ID="12345",
                    GITHUB_SHA="abcdef0123456789abcdef0123456789abcdef01",
                )
                subprocess.run(
                    ["bash", "-eu", "-o", "pipefail", "-c", script],
                    check=True,
                    env=env,
                )
                output.seek(0)
                values = dict(
                    line.decode().rstrip("\n").split("=", 1) for line in output
                )
                self.assertEqual(values["registry"], "ghcr.io/moalfarras-sys")
                self.assertEqual(
                    values["build_tag"], "candidate-12345-abcdef012345"
                )
        self.assertIn("tags: ${{ steps.meta.outputs.build_tag }}", text)
        self.assertNotIn("tags: latest", text)

    def test_production_tags_move_only_after_digest_signature_verification(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        push = text.index("- name: Push to GHCR")
        sign = text.index("- name: Sign image with cosign")
        verify = text.index("- name: Verify signature against the OS-enforced public key")
        promote = text.index("- name: Promote verified digest to production tags")
        self.assertLess(push, sign)
        self.assertLess(sign, verify)
        self.assertLess(verify, promote)
        promotion = text[promote:].split("      - name:", 1)[0]
        self.assertIn("if: github.ref == 'refs/heads/main'", promotion)
        self.assertIn('for tag in "$DATE_TAG" latest', promotion)
        self.assertIn("skopeo copy --preserve-digests", promotion)
        self.assertIn('if [ "$resolved" != "$DIGEST" ]', promotion)
        self.assertIn('cosign verify --key cosign.pub "$target_ref"', promotion)
        self.assertEqual(text.count("uses: redhat-actions/push-to-registry@v2"), 1)
        self.assertEqual(text.count("skopeo copy --preserve-digests"), 1)

        script = workflow_run_script(text, "Promote verified digest to production tags")
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            log = temp_path / "calls.log"
            for name, body in (
                (
                    "skopeo",
                    """#!/bin/sh
printf 'skopeo %s\\n' "$*" >> "$LOG_FILE"
if [ "$1" = inspect ]; then printf '%s\\n' "$ACTUAL_DIGEST"; fi
""",
                ),
                (
                    "cosign",
                    """#!/bin/sh
printf 'cosign %s\\n' "$*" >> "$LOG_FILE"
""",
                ),
            ):
                helper = temp_path / name
                helper.write_text(body, encoding="utf-8")
                helper.chmod(0o755)
            digest = "sha256:" + "a" * 64
            env = os.environ.copy()
            env.update(
                PATH=str(temp_path),
                LOG_FILE=str(log),
                EXPECTED_DIGEST=digest,
                ACTUAL_DIGEST=digest,
                IMAGE_REGISTRY="ghcr.io/example",
                IMAGE_NAME="moos",
                DIGEST=digest,
                DATE_TAG="20260820",
            )
            subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", script],
                check=True,
                env=env,
            )
            calls = log.read_text(encoding="utf-8").splitlines()
            source = f"docker://ghcr.io/example/moos@{digest}"
            self.assertEqual(
                calls,
                [
                    f"skopeo copy --preserve-digests {source} docker://ghcr.io/example/moos:20260820",
                    "skopeo inspect --format {{.Digest}} docker://ghcr.io/example/moos:20260820",
                    "cosign verify --key cosign.pub ghcr.io/example/moos:20260820",
                    "skopeo inspect --format {{.Digest}} docker://ghcr.io/example/moos:20260820",
                    f"skopeo copy --preserve-digests {source} docker://ghcr.io/example/moos:latest",
                    "skopeo inspect --format {{.Digest}} docker://ghcr.io/example/moos:latest",
                    "cosign verify --key cosign.pub ghcr.io/example/moos:latest",
                    "skopeo inspect --format {{.Digest}} docker://ghcr.io/example/moos:latest",
                ],
            )

            log.unlink()
            env["ACTUAL_DIGEST"] = "sha256:" + "b" * 64
            failed = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", script],
                check=False,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            failed_calls = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                failed_calls,
                [
                    f"skopeo copy --preserve-digests {source} docker://ghcr.io/example/moos:20260820",
                    "skopeo inspect --format {{.Digest}} docker://ghcr.io/example/moos:20260820",
                ],
            )

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
        script = X86_BOOT.read_text(encoding="utf-8")
        self.assertIn("CI verification fixture, not an end-user login image", text)
        self.assertIn("name: moos-ci-verified-disk-qcow2", text)
        seal = 'sudo build_files/seal_x86_qcow2.sh "$qcow" "$expected"'
        boot = 'tests/boot_x86_qcow2.sh "$MOOS_X86_QCOW" "$EXPECTED_IMAGE" "$EVIDENCE_DIR"'
        self.assertIn(seal, text)
        self.assertIn(boot, text)
        self.assertLess(text.index(seal), text.index(boot))
        self.assertLess(text.index(boot), text.index("Publish the pristine qcow2"))
        self.assertIn('qemu-img create -q -f qcow2 -F qcow2 -b "$qcow"', script)
        self.assertIn('file=$work/overlay.qcow2', script)
        self.assertIn('after_sha=', script)
        self.assertNotIn("moos-disk-serial-test.qcow2", text)
        self.assertNotIn("sed -i -E 's/\\bquiet", text)

    def test_disk_gate_requires_firmware_and_the_graphical_path(self) -> None:
        text = DISK_WORKFLOW.read_text(encoding="utf-8")
        script = X86_BOOT.read_text(encoding="utf-8")
        for proof in (
            "no matching OVMF CODE/VARS",
            "/run/ostree-booted",
            "rd.live.image",
            "plasmalogin.service",
            "pgrep -u plasmalogin -x kwin_wayland",
            "/dev/dri/card*",
            "container-image-reference-digest",
            "guest-sync-delimited",
            'send_shutdown("reboot")',
            'send_shutdown("powerdown")',
            "graphical-first-boot.ppm",
            "graphical-second-boot.ppm",
            "after_sha=",
        ):
            self.assertIn(proof, script, f"x86 QCOW2 gate lost proof: {proof}")
        self.assertNotIn("-no-reboot", script)
        evidence = text.split("- name: Upload x86 QCOW2 boot evidence", 1)[1].split(
            "      - name:", 1
        )[0]
        self.assertIn("if: always()", evidence)

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

    def test_disk_builder_is_one_immutable_multiarch_object(self) -> None:
        expected = (
            "quay.io/centos-bootc/bootc-image-builder@sha256:"
            "2b52843ea2bfda73b0a08d97e76b734393b1d3a804681b9fabb26723bd3a2f0b"
        )
        for name, path in (
            ("x86 release disk", DISK_WORKFLOW),
            ("ARM release disk", ARM_WORKFLOW),
            ("developer VM smoke", BOOT_VM),
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn(expected, text, f"{name} drifted from the audited builder")
            self.assertNotIn(
                "quay.io/centos-bootc/bootc-image-builder:latest",
                text,
                f"{name} executes a mutable disk builder",
            )

    def test_final_iso_must_boot_before_it_can_be_uploaded(self) -> None:
        iso = ISO_WORKFLOW.read_text(encoding="utf-8")
        script = (ROOT / "tests" / "boot_live_iso.sh").read_text(encoding="utf-8")
        boot = 'tests/boot_live_iso.sh "$FINAL_ISO" "$EXPECTED_IMAGE" "$EVIDENCE_DIR"'
        self.assertIn(boot, iso)
        self.assertIn("FINAL_ISO: ${{ steps.embed.outputs.iso }}", iso)
        self.assertLess(iso.index(boot), iso.index("Upload ISO as workflow artifact"))
        boot_step = iso.split("- name: Boot and prove the exact final live ISO", 1)[1].split(
            "      - name:", 1
        )[0]
        self.assertNotIn("continue-on-error", boot_step)
        for proof in (
            "rd.live.image",
            "graphical.target",
            "display-manager.service",
            "plasmashell",
            'podman image exists "$offline_ref"',
            "guest-shutdown",
            "screendump",
        ):
            self.assertIn(proof, script, f"final ISO gate lost runtime proof: {proof}")
        self.assertIn('after_sha', script)


if __name__ == "__main__":
    unittest.main()
