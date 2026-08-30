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
PROMOTE_WORKFLOW = ROOT / ".github" / "workflows" / "promote-x86.yml"
BOOT_VM = ROOT / "tests" / "boot-in-vm.sh"
X86_BOOT = ROOT / "tests" / "boot_x86_qcow2.sh"


def workflow_run_script(text: str, step_name: str) -> str:
    """Return one workflow step's literal run script without parsing YAML."""
    remainder = text.split(f"- name: {step_name}", 1)[1]
    remainder = remainder.split("        run: |\n", 1)[1]
    lines: list[str] = []
    for line in remainder.splitlines():
        if not line:
            lines.append("")
            continue
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
            ROOT / "tests" / "install_live_iso.sh",
            X86_BOOT,
        ):
            self.assertTrue(
                path.stat().st_mode & stat.S_IXUSR,
                f"release workflow invokes a non-executable helper: {path}",
            )

    def test_disk_proofs_for_different_editions_do_not_cancel_each_other(self) -> None:
        text = DISK_WORKFLOW.read_text(encoding="utf-8")
        concurrency = text.split("concurrency:", 1)[1].split("\njobs:", 1)[0]
        self.assertIn("inputs['image-ref']", concurrency)
        self.assertIn("cancel-in-progress: true", concurrency)

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

    def test_production_tags_require_exact_build_disk_and_iso_proof(self) -> None:
        build = WORKFLOW.read_text(encoding="utf-8")
        promote = PROMOTE_WORKFLOW.read_text(encoding="utf-8")
        push = build.index("- name: Push to GHCR")
        sign = build.index("- name: Sign image with cosign")
        verify = build.index("- name: Verify signature against the OS-enforced public key")
        record = build.index("- name: Record the signed candidate identity")
        upload = build.index("- name: Upload the signed candidate identity")
        self.assertLess(push, sign)
        self.assertLess(sign, verify)
        self.assertLess(verify, record)
        self.assertLess(record, upload)
        self.assertIn("moos-candidate-proof-${{ matrix.image_name }}", build)
        self.assertNotIn("skopeo copy --preserve-digests", build)
        self.assertEqual(build.count("uses: redhat-actions/push-to-registry@v3"), 1)

        required_order = (
            "Prove the candidate is the exact tree on main",
            "Validate all workflow runs",
            "Download immutable candidate and boot evidence",
            "Validate candidate manifests and artifact runtime proof",
            "Verify every digest before any production mutation",
            "Promote the boot-proven release",
        )
        positions = [promote.index(f"- name: {name}") for name in required_order]
        self.assertEqual(positions, sorted(positions))
        for proof in (
            "if: github.ref == 'refs/heads/main'",
            "cancel-in-progress: false",
            'git rev-parse "${REVISION}^{tree}"',
            ".github/workflows/build.yml",
            ".github/workflows/build-disk.yml",
            ".github/workflows/build-iso.yml",
            ".run_attempt == 1",
            "moos-x86-qcow2-boot-proof",
            "NVIDIA_DISK_RUN_ID",
            "CLOUD_DISK_RUN_ID",
            'prove_disk moos "$generic_ref"',
            'prove_disk moos-nvidia "$nvidia_ref"',
            'prove_disk moos-cloud "$cloud_ref"',
            "moos-live-iso-boot-proof",
            "moos-iso-install-proof",
            'candidate-${BUILD_RUN_ID}-${REVISION:0:12}',
            'origin=ostree-image-signed:docker://${ref}',
            'offline-digest=${generic_ref##*@}',
            "source=embedded-offline",
            "login=plasma-login-manager",
            "for app in dolphin konsole moos-settings mo-ai mo-store updater recovery themes moplayer mo-pc-remote; do",
            'grep -Fx "${app}=opened-closed-reopened"',
            "second-boot=healthy",
            "skopeo copy --preserve-digests",
            'promote_tag "$ref" "$DATE_TAG"',
            'promote_tag "$ref" latest',
            'cosign verify --key cosign.pub "$target_ref"',
            'previous_latest="$RUNNER_TEMP/moos-previous-latest"',
            "trap rollback_latest ERR",
            "production latest tags restored after failed promotion",
        ):
            self.assertIn(proof, promote, f"x86 promotion lost proof: {proof}")
        self.assertEqual(promote.count("skopeo copy --preserve-digests"), 2)

        script = workflow_run_script(promote, "Promote the boot-proven release")
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            log = temp_path / "calls.log"
            for name, body in (
                (
                    "git",
                    """#!/bin/sh
if [ "$1" = fetch ]; then exit 0; fi
if [ "$1" = rev-parse ]; then printf '%s\\n' fixed-tree; exit 0; fi
exit 1
""",
                ),
                (
                    "skopeo",
                    """#!/bin/sh
printf 'skopeo %s\\n' "$*" >> "$LOG_FILE"
last=""
for arg in "$@"; do last="$arg"; done
if [ "$1" = copy ]; then
    source_ref="${3#docker://}"
    target_ref="${4#docker://}"
    digest="${source_ref##*@}"
    if [ "${FAIL_NVIDIA_LATEST:-0}" = 1 ] && \
       [ "$target_ref" = ghcr.io/example/moos-nvidia:latest ] && \
       [ "$digest" = "$ACTUAL_DIGEST" ]; then
        exit 9
    fi
    key=$(printf '%s' "$target_ref" | tr '/:' '__')
    printf '%s\\n' "$digest" > "$STATE_DIR/$key"
elif [ "$1" = inspect ]; then
    target_ref="${last#docker://}"
    key=$(printf '%s' "$target_ref" | tr '/:' '__')
    if [ "$target_ref" = ghcr.io/example/moos-nvidia:20260820 ] && \
         [ -n "${NVIDIA_DATE_DIGEST:-}" ]; then
        printf '%s\\n' "$NVIDIA_DATE_DIGEST"
    elif [ -f "$STATE_DIR/$key" ]; then
        cat "$STATE_DIR/$key"
    elif [ "${target_ref##*:}" = latest ]; then
        printf '%s\\n' "$OLD_DIGEST"
    else
        printf '%s\\n' "$ACTUAL_DIGEST"
    fi
fi
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
            old_digest = "sha256:" + "c" * 64
            state_dir = temp_path / "state"
            state_dir.mkdir()
            env = os.environ.copy()
            env.update(
                PATH=f"{temp_path}:/usr/bin",
                LOG_FILE=str(log),
                RUNNER_TEMP=str(temp_path),
                STATE_DIR=str(state_dir),
                ACTUAL_DIGEST=digest,
                OLD_DIGEST=old_digest,
                MOOS_REF=f"ghcr.io/example/moos@{digest}",
                NVIDIA_REF=f"ghcr.io/example/moos-nvidia@{digest}",
                CLOUD_REF=f"ghcr.io/example/moos-cloud@{digest}",
                DATE_TAG="20260820",
                REVISION="c" * 40,
            )
            subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", script],
                check=True,
                env=env,
            )
            calls = log.read_text(encoding="utf-8").splitlines()
            first_dated = next(
                i for i, call in enumerate(calls)
                if call.startswith("skopeo copy ") and ":20260820" in call
            )
            for image in ("moos", "moos-nvidia", "moos-cloud"):
                latest = f"ghcr.io/example/{image}:latest"
                snapshot = f"skopeo inspect --format {{{{.Digest}}}} docker://{latest}"
                self.assertIn(snapshot, calls[:first_dated])
                self.assertIn(f"cosign verify --key cosign.pub {latest}", calls[:first_dated])
            for tag in ("20260820", "latest"):
                for image in ("moos", "moos-nvidia", "moos-cloud"):
                    source = f"docker://ghcr.io/example/{image}@{digest}"
                    target = f"ghcr.io/example/{image}:{tag}"
                    self.assertIn(
                        f"skopeo copy --preserve-digests {source} docker://{target}",
                        calls,
                    )

            log.unlink()
            for state in state_dir.iterdir():
                state.unlink()
            env["NVIDIA_DATE_DIGEST"] = "sha256:" + "b" * 64
            failed = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", script],
                check=False,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            failed_calls = log.read_text(encoding="utf-8").splitlines()
            self.assertTrue(any("moos-nvidia:20260820" in call for call in failed_calls))
            self.assertFalse(any(" copy " in f" {call} " and ":latest" in call for call in failed_calls))

            log.unlink()
            for state in state_dir.iterdir():
                state.unlink()
            env.pop("NVIDIA_DATE_DIGEST")
            env["FAIL_NVIDIA_LATEST"] = "1"
            mid_latest = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", script],
                check=False,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(mid_latest.returncode, 0)
            rollback_calls = log.read_text(encoding="utf-8").splitlines()
            for image in ("moos", "moos-nvidia", "moos-cloud"):
                restore = (
                    f"skopeo copy --preserve-digests "
                    f"docker://ghcr.io/example/{image}@{old_digest} "
                    f"docker://ghcr.io/example/{image}:latest"
                )
                self.assertIn(restore, rollback_calls)
                key = f"ghcr.io_example_{image}_latest"
                self.assertEqual((state_dir / key).read_text().strip(), old_digest)

    def test_promotion_rejects_reruns_and_mismatched_runtime_evidence(self) -> None:
        promote = PROMOTE_WORKFLOW.read_text(encoding="utf-8")
        revision = "c" * 40
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            gh = temp_path / "gh"
            gh.write_text(
                """#!/bin/sh
case "$*" in
  *actions/runs/11) path=.github/workflows/build.yml ;;
  *actions/runs/12|*actions/runs/13|*actions/runs/14) path=.github/workflows/build-disk.yml ;;
  *actions/runs/15) path=.github/workflows/build-iso.yml ;;
  *) exit 2 ;;
esac
printf '{"conclusion":"success","event":"workflow_dispatch","head_sha":"%s","path":"%s","run_attempt":%s}\\n' "$REVISION" "$path" "$ATTEMPT"
""",
                encoding="utf-8",
            )
            gh.chmod(0o755)
            env = os.environ.copy()
            env.update(
                PATH=f"{temp_path}:/usr/bin",
                GITHUB_REPOSITORY="example/moos-image",
                REVISION=revision,
                BUILD_RUN_ID="11",
                DISK_RUN_ID="12",
                NVIDIA_DISK_RUN_ID="13",
                CLOUD_DISK_RUN_ID="14",
                ISO_RUN_ID="15",
                ATTEMPT="1",
            )
            run_validator = workflow_run_script(promote, "Validate all workflow runs")
            subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", run_validator],
                check=True,
                env=env,
            )
            env["ATTEMPT"] = "2"
            rerun = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", run_validator],
                check=False,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rerun.returncode, 0)

            proof = temp_path / "proof"
            digest = "sha256:" + "a" * 64
            for image in ("moos", "moos-nvidia", "moos-cloud"):
                directory = proof / "build" / image
                directory.mkdir(parents=True)
                (directory / "candidate.txt").write_text(
                    f"repository=ghcr.io/example/{image}\n"
                    f"digest={digest}\n"
                    f"revision={revision}\n"
                    "date-tag=20260820\n"
                    f"candidate-tag=candidate-11-{revision[:12]}\n"
                    "signature=verified\n",
                    encoding="utf-8",
                )
            generic = f"ghcr.io/example/moos@{digest}"
            (proof / "disk").mkdir()
            (proof / "iso").mkdir()
            (proof / "iso-install").mkdir()
            for image in ("moos", "moos-nvidia", "moos-cloud"):
                disk = proof / "disk" / image
                disk.mkdir()
                ref = f"ghcr.io/example/{image}@{digest}"
                (disk / "manifest.txt").write_text(
                    f"image={ref}\n", encoding="utf-8"
                )
                (disk / "runtime-first-boot.txt").write_text(
                    f"origin=ostree-image-signed:docker://{ref}\n", encoding="utf-8"
                )
                (disk / "runtime-second-boot.txt").write_text(
                    f"origin=ostree-image-signed:docker://{ref}\nshutdown=clean\n",
                    encoding="utf-8",
                )
                (disk / "graphical-first-boot.png").write_bytes(b"not-empty")
                (disk / "graphical-second-boot.png").write_bytes(b"not-empty")
            (proof / "iso" / "manifest.txt").write_text(
                f"image={generic}\n", encoding="utf-8"
            )
            iso_runtime = proof / "iso" / "runtime.txt"
            iso_runtime.write_text(
                f"offline-digest={digest}\nboot=live\nshutdown=clean\n",
                encoding="utf-8",
            )
            iso_install = proof / "iso-install"
            (iso_install / "manifest.txt").write_text(
                f"image={generic}\n", encoding="utf-8"
            )
            (iso_install / "install.status").write_text(
                "install=done\nsource=embedded-offline\nnetwork=disabled\n",
                encoding="utf-8",
            )
            (iso_install / "installer-status.raw").write_text(
                "PROGRESS 100\nDONE\n", encoding="utf-8"
            )
            (iso_install / "installer.log").write_text(
                "source: local containers-storage (offline)\n", encoding="utf-8"
            )
            (iso_install / "installed-first-boot.txt").write_text(
                f"origin={generic}\n", encoding="utf-8"
            )
            (iso_install / "desktop-session.txt").write_text(
                "login=plasma-login-manager\ndesktop=usable\n", encoding="utf-8"
            )
            (iso_install / "app-smoke.txt").write_text(
                "dolphin=opened-closed-reopened\n"
                "konsole=opened-closed-reopened\n"
                "moos-settings=opened-closed-reopened\n"
                "mo-ai=opened-closed-reopened\n"
                "mo-store=opened-closed-reopened\n"
                "updater=opened-closed-reopened\n"
                "recovery=opened-closed-reopened\n"
                "themes=opened-closed-reopened\n"
                "moplayer=opened-closed-reopened\n"
                "mo-pc-remote=opened-closed-reopened\n",
                encoding="utf-8",
            )
            (iso_install / "installed-second-boot.txt").write_text(
                f"origin={generic}\nreboot=clean\nsecond-boot=healthy\npoweroff=clean\n",
                encoding="utf-8",
            )
            (iso_install / "installed-login.png").write_bytes(b"not-empty")
            (iso_install / "installed-desktop-apps.png").write_bytes(b"not-empty")
            output = temp_path / "github-output"
            env.update(
                GITHUB_REPOSITORY_OWNER="Example",
                GITHUB_OUTPUT=str(output),
                ATTEMPT="1",
            )
            evidence_validator = workflow_run_script(
                promote, "Validate candidate manifests and artifact runtime proof"
            )
            subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", evidence_validator],
                check=True,
                cwd=temp_path,
                env=env,
            )
            outputs = output.read_text(encoding="utf-8")
            self.assertIn(f"moos_ref={generic}\n", outputs)

            iso_runtime.write_text(
                "offline-digest=sha256:" + "b" * 64 + "\nboot=live\nshutdown=clean\n",
                encoding="utf-8",
            )
            mismatch = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", evidence_validator],
                check=False,
                cwd=temp_path,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(mismatch.returncode, 0)

            iso_runtime.write_text(
                f"offline-digest={digest}\nboot=live\nshutdown=clean\n",
                encoding="utf-8",
            )
            (iso_install / "app-smoke.txt").write_text(
                "dolphin=opened-closed-reopened\n", encoding="utf-8"
            )
            missing_app = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", evidence_validator],
                check=False,
                cwd=temp_path,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing_app.returncode, 0)

            (iso_install / "app-smoke.txt").write_text(
                "dolphin=opened-closed-reopened\n"
                "konsole=opened-closed-reopened\n"
                "moos-settings=opened-closed-reopened\n"
                "mo-ai=opened-closed-reopened\n"
                "mo-store=opened-closed-reopened\n"
                "updater=opened-closed-reopened\n"
                "recovery=opened-closed-reopened\n"
                "themes=opened-closed-reopened\n"
                "moplayer=opened-closed-reopened\n"
                "mo-pc-remote=opened-closed-reopened\n",
                encoding="utf-8",
            )
            nvidia_first = proof / "disk" / "moos-nvidia" / "runtime-first-boot.txt"
            nvidia_first.write_text(
                f"origin=ostree-image-signed:docker://{generic}\n",
                encoding="utf-8",
            )
            wrong_edition = subprocess.run(
                ["/usr/bin/bash", "-eu", "-o", "pipefail", "-c", evidence_validator],
                check=False,
                cwd=temp_path,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(wrong_edition.returncode, 0)

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
        seal = (
            'sudo build_files/seal_x86_qcow2.sh \\\n'
            '            "$qcow" "$expected" --enable-ci-runtime-proof'
        )
        boot = (
            'tests/boot_x86_qcow2.sh \\\n'
            '            "$MOOS_X86_QCOW" "$EXPECTED_IMAGE" "$EVIDENCE_DIR" "$MOOS_X86_SSH_KEY"'
        )
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
            "getent passwd plasmalogin",
            'pgrep -u "$login_uid" -x kwin_wayland',
            "systemctl list-units --state=failed --full --no-pager --no-legend",
            "greeter-processes:",
            "display-manager-journal:",
            "/dev/dri/card*",
            "origin-digest",
            "guest-sync-delimited",
            "hostfwd=tcp:127.0.0.1:",
            '"BatchMode=yes"',
            '"IdentitiesOnly=yes"',
            "ssh=ephemeral-key",
            'send_shutdown("reboot")',
            'send_shutdown("powerdown")',
            "graphical-first-boot.ppm",
            "graphical-second-boot.ppm",
            "after_sha=",
        ):
            self.assertIn(proof, script, f"x86 QCOW2 gate lost proof: {proof}")
        self.assertNotIn("-no-reboot", script)
        self.assertNotIn("guest-exec", script)
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
        install = 'tests/install_live_iso.sh "$FINAL_ISO" "$EXPECTED_IMAGE" "$EVIDENCE_DIR"'
        self.assertIn(boot, iso)
        self.assertIn(install, iso)
        self.assertIn("FINAL_ISO: ${{ steps.embed.outputs.iso }}", iso)
        final_upload = iso.index("- name: Upload ISO as workflow artifact")
        self.assertLess(iso.index(boot), final_upload)
        self.assertLess(iso.index(install), final_upload)
        self.assertEqual(iso.count("\n          name: moos-live-iso\n"), 1)
        diagnostic = iso.split(
            "- name: Upload unproven ISO for failure diagnosis", 1
        )[1].split("      - name:", 1)[0]
        self.assertIn("name: moos-live-iso-unproven-debug", diagnostic)
        final_step = iso.split("- name: Upload ISO as workflow artifact", 1)[1]
        self.assertNotIn("if: always()", final_step)
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
            "install-source-digest",
            "guest-shutdown",
            "screendump",
        ):
            self.assertIn(proof, script, f"final ISO gate lost runtime proof: {proof}")
        self.assertIn('after_sha', script)

    def test_cloud_disk_uses_the_shared_x86_boot_proof(self) -> None:
        script = X86_BOOT.read_text(encoding="utf-8")
        self.assertIn("moos|moos-nvidia|moos-cloud", script)
        self.assertIn("runtime-gate=%s", script)
        self.assertIn("system-state=%s", script)
        self.assertIn("root-mount=%s", script)
        self.assertIn("booted-origin=", script)

    def test_disk_runtime_proof_uses_only_ephemeral_ssh_credentials(self) -> None:
        workflow = DISK_WORKFLOW.read_text(encoding="utf-8")
        config = (ROOT / "bib/config.toml").read_text(encoding="utf-8")
        script = X86_BOOT.read_text(encoding="utf-8")
        self.assertIn('__MOOS_CI_SSH_PUBLIC_KEY__', config)
        self.assertNotIn("customizations.services", config)
        self.assertIn("--enable-ci-runtime-proof", workflow)
        self.assertNotIn("customizations.firewall", config)
        self.assertIn("ssh-keygen -q -t ed25519", workflow)
        self.assertIn("moos-ci-runtime-key", workflow)
        self.assertIn("rm -f --", workflow)
        self.assertIn("MOOS_X86_SSH_KEY", workflow)
        self.assertIn('grep -Fq "blueprint validation failed"', workflow)
        self.assertIn("StrictHostKeyChecking=no", script)
        self.assertIn("UserKnownHostsFile=/dev/null", script)
        self.assertNotIn("/proc/1/root", script)
        self.assertNotIn("guest-exec-status", script)

        proof_helper = (
            ROOT / "system_files/usr/libexec/moos-ci-runtime-proof-firewall"
        ).read_text(encoding="utf-8")
        proof_unit = (
            ROOT / "system_files/usr/lib/systemd/system/moos-ci-runtime-proof.service"
        ).read_text(encoding="utf-8")
        self.assertIn("10.0.2.2/32", proof_helper)
        self.assertIn("moos-ci-runtime-proof", proof_helper)
        self.assertIn("moos.ci-runtime-proof=1", proof_helper)
        self.assertIn("systemctl --no-block start firewalld.service sshd.service", proof_helper)
        self.assertIn("systemd-detect-virt", proof_helper)
        self.assertIn("ConditionKernelCommandLine=moos.ci-runtime-proof=1", proof_unit)
        self.assertIn("ConditionPathExists=/home/mo/.ssh/authorized_keys", proof_unit)
        for target in ("multi-user.target.wants", "graphical.target.wants"):
            self.assertFalse(
                (ROOT / "system_files/etc/systemd/system" / target /
                 "moos-ci-runtime-proof.service").exists()
            )

    def test_live_iso_waits_for_desktop_after_early_qga_start(self) -> None:
        script = (ROOT / "tests" / "boot_live_iso.sh").read_text(encoding="utf-8")
        self.assertIn("for _ in $(seq 1 120)", script)
        self.assertIn("stable_samples=$((stable_samples + 1))", script)
        self.assertIn('[ "$stable_samples" -ge 6 ]', script)
        self.assertIn("theme_marker=", script)
        self.assertIn('[ -e "$theme_marker" ]', script)
        self.assertLess(script.index('[ -e "$theme_marker" ]'), script.index("stable_samples=$((stable_samples + 1))"))
        self.assertIn("desktop_ready=1", script)
        self.assertIn("live-runtime-gate=%s", script)
        self.assertIn("theme-marker=%s", script)
        self.assertIn("plasma-plasmashell.service", script)
        self.assertIn("liveuser-journal:", script)
        self.assertIn("deadline = time.monotonic() + 720", script)
        self.assertLess(script.index("desktop_ready=0"), script.index("[ \"$desktop_ready\" -eq 1 ]"))

    def test_installed_only_services_do_not_fail_the_live_iso(self) -> None:
        units = (
            ROOT / "system_files/usr/lib/systemd/system/moos-firewall-migrate.service",
            ROOT / "system_files/usr/lib/systemd/system/bootloader-update.service.d/50-moos-installed-only.conf",
            ROOT / "system_files/usr/lib/systemd/system/tuned.service.d/50-moos-installed-only.conf",
        )
        for unit in units:
            self.assertIn(
                "ConditionPathExists=/run/ostree-booted",
                unit.read_text(encoding="utf-8"),
                f"{unit.name} must stay out of the disposable LiveOS session",
            )


if __name__ == "__main__":
    unittest.main()
