#!/usr/bin/env python3
"""Gates for the MoOS aarch64 edition.

These are the checks that can be made without an ARM machine. They are not a
substitute for building it — .github/workflows/build-arm.yml does that, on a
native arm64 runner, and verifies the built artefact. What these catch is the
class of mistake that would otherwise be found an hour into a CI run, or worse,
after the owner has uploaded several gigabytes to Oracle:

  * building the ARM image from a base that has no ARM build,
  * configuring the x86 serial port on an ARM machine, so the provider's console
    is blank exactly when it is the only way in,
  * shipping a remote-desktop service with a credential baked into the image,
  * letting the ARM edition drift into being a second copy of the identity tree
    instead of sharing the one the x86 editions use.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTAINERFILE = ROOT / "Containerfile.arm"
BUILD = ROOT / "build_files/build-arm.sh"
ARM_VERIFY = ROOT / "build_files/verify_arm_image.py"
WORKFLOW = ROOT / ".github/workflows/build-arm.yml"
DOCS = ROOT / "docs/MOOS_ARM_ORACLE.md"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def code(text: str) -> str:
    """Strip # comments.

    Every check here is about what the file DOES. These files explain their own
    reasoning at length, and that prose necessarily names the things it is
    explaining why not to use — Containerfile.arm says the word
    "ublue-os/kinoite-main" in the paragraph about why it cannot use it. A check
    that greps the raw text fails on the explanation instead of on the code,
    which is both wrong and the kind of failure that teaches people to delete
    the comment.
    """
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        out.append(line)
    return "\n".join(out)


def build_only(text: str) -> str:
    """build-arm.sh with the runtime helpers it WRITES removed.

    build-arm.sh installs /usr/bin/moos-arm-remote via a heredoc. That helper's
    body is not build-time code — it runs later, on the owner's own instance, and
    it is where setting an RDP password is exactly the right thing to do. A check
    for "no password is set at build time" has to look at the build, not at the
    script the build lays down.
    """
    out, skipping = [], False
    for line in text.splitlines():
        if line.startswith("install -D -m0755 /dev/stdin /usr/bin/moos-arm-remote <<'REMOTE'"):
            skipping = True
            continue
        if skipping:
            if line.strip() == "REMOTE":
                skipping = False
            continue
        out.append(line)
    return "\n".join(out)


class ArmEditionTests(unittest.TestCase):
    def test_the_pieces_exist(self) -> None:
        for p in (CONTAINERFILE, BUILD, ARM_VERIFY, WORKFLOW, DOCS):
            self.assertTrue(p.is_file(), f"{p.relative_to(ROOT)} is missing")

    # ── the base ────────────────────────────────────────────────────────────
    def test_the_arm_base_is_one_that_has_an_arm_build(self) -> None:
        froms = re.findall(r"^FROM\s+(\S+)", code(read(CONTAINERFILE)), re.MULTILINE)
        self.assertTrue(froms, "Containerfile.arm has no FROM lines")
        self.assertIn("quay.io/fedora/fedora-bootc:44", froms,
                      f"the ARM image must build from a base published for aarch64; "
                      f"it builds from {froms}")
        for f in froms:
            self.assertNotIn("kinoite-main", f,
                             "kinoite-main is amd64-only — a --platform linux/arm64 build "
                             "against it cannot resolve a manifest at all")

    def test_the_identity_tree_is_shared_not_copied(self) -> None:
        # The value of the ARM edition is that it is the SAME MoOS. If someone
        # ever adds an arm-specific copy of the identity tree, the two editions
        # start looking different and nothing else notices.
        text = read(CONTAINERFILE)
        self.assertIn("COPY system_files/ /", text,
                      "Containerfile.arm must copy the shared system_files tree")
        self.assertFalse((ROOT / "system_files_arm").exists(),
                         "a forked identity tree exists; the editions will drift")

    def test_the_shared_overlay_wins_after_package_transactions(self) -> None:
        containerfile = read(CONTAINERFILE)
        build = read(BUILD)
        self.assertIn("FROM scratch AS system-files", containerfile)
        self.assertIn("from=system-files", containerfile)
        self.assertIn("target=/moos-overlay", containerfile)
        self.assertIn("cp -a /moos-overlay/. /", build,
                      "RPMs are installed after the first COPY system_files; without a "
                      "pristine final overlay, package transaction order can silently "
                      "replace the MoOS session, greeter, or theme")

    def test_the_curated_desktop_uses_fedora_44_package_names(self) -> None:
        text = code(read(BUILD))
        for current in ("kwin-libs", "plasma-breeze", "plasma-workspace"):
            self.assertIn(current, text, f"the ARM build is missing Fedora 44's {current}")
        for retired in ("kwin-wayland-libs", "\n    breeze ", "plasma-workspace-wayland"):
            self.assertNotIn(retired, text,
                             f"{retired.strip()} is not a Fedora 44 package; the native "
                             "build would fail before creating the image")

    # ── the ARM-specific things that x86 gets wrong ─────────────────────────
    def test_the_serial_console_is_the_arm_uart(self) -> None:
        text = code(read(BUILD))
        self.assertIn("console=ttyAMA0", text,
                      "Oracle's serial console on Ampere is the PL011 UART (ttyAMA0); "
                      "an image that only lists ttyS0 shows a blank console, which is "
                      "discovered exactly when it is the only way in")
        self.assertNotIn("console=ttyS0", text,
                         "ttyS0 is the x86 8250 port and does not exist on Ampere")
        self.assertIn("serial-getty@ttyAMA0", text,
                      "a getty must be enabled on the ARM console or it accepts no login")

    def test_it_refuses_to_build_on_the_wrong_architecture(self) -> None:
        text = read(BUILD)
        self.assertRegex(text, r'uname -m.*aarch64|aarch64.*uname -m',
                         "build-arm.sh must refuse to run on a non-aarch64 builder; an "
                         "emulated build silently produces a wrong-architecture "
                         "moos-qml-shell that only fails on the user's machine")

    def test_the_workflow_runs_on_a_real_arm_runner(self) -> None:
        text = read(WORKFLOW)
        self.assertIn("ubuntu-24.04-arm", text,
                      "the ARM image must be built natively; emulating a Plasma build "
                      "on x86 exceeds the job timeout")
        self.assertIn("arm64", text, "the workflow must verify the image architecture")

    def test_the_new_workflow_can_prove_a_feature_branch(self) -> None:
        text = read(WORKFLOW)
        self.assertIn("pull_request:", text,
                      "a workflow file added only on a feature branch cannot be manually "
                      "dispatched until it reaches the default branch; a pull-request "
                      "trigger is the safe first real build")
        for gate in (
            "bash -n build_files/build-arm.sh",
            "python3 tests/test_moos_arm.py",
            "python3 tests/test_boot_splash_polish.py",
        ):
            self.assertIn(gate, text, f"the ARM workflow never runs {gate}")
        pull_request_paths = text.split("  pull_request:\n", 1)[1].split(
            "\nenv:\n", 1
        )[0]
        self.assertIn(
            '"system_files/**"',
            pull_request_paths,
            "ARM consumes the complete shared system overlay, so a pull request "
            "that changes it must prove the ARM image before merge",
        )
        self.assertIn(
            '".github/workflows/build-arm.yml"',
            pull_request_paths,
            "a pull request that repairs the ARM workflow must trigger that workflow",
        )

    def test_only_main_can_publish_arm_latest_or_a_disk(self) -> None:
        text = read(WORKFLOW)
        publish_if = (
            "if: github.event_name != 'pull_request' && "
            "github.ref == 'refs/heads/main'"
        )
        for step_name in (
            "Log in to GHCR",
            "Push",
            "Install cosign",
            "Sign the ARM image by digest",
            "Verify the signature against MoOS's installed key",
        ):
            match = re.search(
                rf"^\s+- name: {re.escape(step_name)}\n(?P<body>.*?)(?=^\s+- name:|^\s{{2}}\w|\Z)",
                text,
                re.MULTILINE | re.DOTALL,
            )
            self.assertIsNotNone(match, f"ARM workflow lost the {step_name!r} step")
            self.assertIn(
                publish_if,
                match.group("body"),
                f"{step_name} can publish from a feature branch and replace main's latest",
            )

        disk_job = text.split("\n  disk:\n", 1)
        self.assertEqual(len(disk_job), 2, "ARM workflow lost its disk job")
        disk_header = disk_job[1].split("\n    runs-on:", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", disk_header)
        self.assertIn("needs.build.result == 'success'", disk_header)

    def test_workflow_has_no_unindented_shell_payload(self) -> None:
        # A heredoc body at column zero ends YAML's `run: |` scalar. GitHub then
        # creates a failed workflow run with zero jobs and no log, which is the
        # exact failure this caught on 2026-08-20. Top-level YAML content is a
        # mapping key; bare shell/TOML payload can never be valid there.
        offenders = []
        for lineno, line in enumerate(read(WORKFLOW).splitlines(), start=1):
            if not line or line[0].isspace() or line.startswith("#"):
                continue
            if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", line):
                continue
            offenders.append((lineno, line))
        self.assertEqual(
            offenders,
            [],
            f"unindented shell payload makes build-arm.yml invalid YAML: {offenders}",
        )

    def test_finished_image_gates_match_the_cloud_arm_payload(self) -> None:
        build = code(read(BUILD))
        verifier = read(ARM_VERIFY)
        self.assertIn("MOOS_IDENTITY_PROFILE=arm-cloud", build,
                      "the shared identity gate otherwise demands the Live installer "
                      "and two intentionally omitted x86 binaries")
        self.assertIn("fedora-logo-icon", build,
                      "Plasma re-ships fedora-logos; ARM must scrub those names the "
                      "same way build.sh (z2) does or identity gates fail on the "
                      "real image")
        self.assertIn("usr/bin/plasma-welcome", build,
                      "the identity gate requires the silent plasma-welcome no-op "
                      "stub even though ARM never installs the upstream binary")
        self.assertIn("org.fedoraproject.fedora.desktop", build,
                      "plasma-desktop ships Fedora Global Themes; ARM must delete "
                      "them the same way build.sh (z2a) does")
        self.assertIn("python3 /ctx/verify_arm_image.py", build)
        self.assertNotIn("python3 /ctx/verify_image_experience.py", build,
                         "the x86 finished-image gate requires hardware/gaming services "
                         "that the lightweight cloud edition intentionally omits")
        for contract in (
            "platform.machine() == \"aarch64\"",
            "cloud-init-network.service",
            "console=ttyAMA0,115200n8",
            "--query-service=rdp",
            "usr/share/xsessions",
            "startplasma-wayland",
            "plasma-workspace-x11",
        ):
            self.assertIn(contract, verifier,
                          f"the finished ARM image gate does not verify {contract}")

    def test_every_published_arm_image_is_signed_and_verified(self) -> None:
        text = read(WORKFLOW)
        self.assertIn("cosign sign", text)
        self.assertIn("cosign verify --key cosign.pub", text)
        self.assertIn("SIGNING_SECRET", text)

    def test_the_disk_image_targets_arm(self) -> None:
        text = read(WORKFLOW)
        self.assertIn("--target-arch arm64", text,
                      "bootc-image-builder must be told to produce an arm64 disk")
        self.assertIn("--type qcow2", text,
                      "Oracle imports QCOW2; the workflow must produce one")
        self.assertIn('cosign verify --key cosign.pub "${src}"', text,
                      "a disk artifact must not be built from an unsigned moved tag")
        self.assertIn("needs.build.outputs.digest", text,
                      "the disk job must consume the immutable digest emitted by its build")
        self.assertRegex(text, r'podman\s+pull\s+--authfile="\$AUTH"\s+"\$\{src\}"',
                      "--local only works after the exact GHCR reference is present in "
                      "the disk job's separate root container store")
        self.assertNotRegex(text, r'podman\s+--authfile=',
                            "Podman 5.8 rejects --authfile as a global flag; it belongs "
                            "on the pull subcommand")

    # ── security posture ────────────────────────────────────────────────────
    def test_firewall_setup_is_idempotent_and_keeps_rdp_closed(self) -> None:
        text = code(read(BUILD))
        self.assertIn("--get-default-zone", text,
                      "firewall-offline-cmd returns a non-zero ALREADY_SET code")
        self.assertIn("--query-service=ssh", text,
                      "adding an already-enabled service can abort a rebuild")
        self.assertIn("--remove-service=rdp", text,
                      "KRDP must stay behind the documented SSH tunnel")

    def test_no_remote_desktop_credential_is_baked_into_the_image(self) -> None:
        # krdp must be installed but NOT enabled, and no password set at build
        # time: a service on 3389 with an image-wide credential is a backdoor
        # shipped to everyone who ever boots it. Checked against the BUILD only —
        # the moos-arm-remote helper the build writes is runtime code, and
        # setting a password is precisely its job.
        build = build_only(code(read(BUILD)))
        offenders = [ln for ln in build.splitlines()
                     if re.search(r"systemctl\s+(--global\s+|--user\s+)?enable\S*\s+\S*krdp", ln)]
        self.assertEqual(offenders, [], f"krdp is enabled at build time: {offenders}")
        offenders = [ln for ln in build.splitlines() if "set-password" in ln or "krdprc" in ln]
        self.assertEqual(offenders, [],
                         f"a remote-desktop credential is being written at build time: {offenders}")
        self.assertIn("moos-arm-remote", read(BUILD),
                      "there must be a helper that turns the remote on with a password "
                      "the owner chooses on their own instance")

    def test_privilege_escalation_always_requires_a_password(self) -> None:
        text = code(read(BUILD))
        self.assertNotIn("NOPASSWD", text,
                         "MoOS never ships passwordless sudo or polkit; the cloud account "
                         "must receive a unique password through launch user-data")
        self.assertIn("groups: [wheel", text,
                      "the cloud account needs Fedora's normal password-authenticated "
                      "wheel policy")

    def test_krdp_uses_pam_not_a_password_in_argv_or_a_fake_cli(self) -> None:
        text = code(read(BUILD))
        self.assertIn("--key SystemUserEnabled true", text,
                      "headless KRDP must authenticate with the system account through PAM")
        self.assertIn("--file krdpserverrc", text,
                      "KRDP's real KConfig file is krdpserverrc")
        self.assertNotIn("--set-password", text,
                         "krdpserver has no --set-password option")
        self.assertNotRegex(text, r"krdpserver\s+[^\n]*\s-[up]\s",
                            "an RDP password must not be exposed in the process argv")
        self.assertIn("flatpak permission-set kde-authorized remote-desktop "
                      "org.kde.krdpserver yes", text,
                      "the headless session has nobody who can click the portal prompt")

    def test_ssh_is_keys_only(self) -> None:
        text = read(BUILD)
        self.assertIn("PasswordAuthentication no", text,
                      "the instance has a public IP; password SSH is only an attack surface")
        self.assertIn("PermitRootLogin no", text)

    def test_arm_is_wayland_only(self) -> None:
        text = code(read(BUILD))
        self.assertNotIn("plasma-workspace-x11", text)
        self.assertNotIn("--xwayland", text)
        self.assertIn("/usr/share/xsessions", text,
                      "the finished image must fail if a dependency adds an X11 session")

    def test_unsupported_x86_apps_are_not_left_as_dead_launchers(self) -> None:
        text = code(read(BUILD))
        self.assertIn("rm -f", text)
        remove_block = text.split("rm -f", 1)[1].split("install -D", 1)[0]
        for path in (
            "/usr/share/applications/org.moos.moplayer.desktop",
            "/usr/share/applications/org.moos.remote.desktop",
        ):
            self.assertIn(path, remove_block,
                          f"{path} would open a missing architecture-specific backend")

    # ── the things that make a cloud image boot at all ──────────────────────
    def test_cloud_init_is_present_and_pinned(self) -> None:
        text = read(BUILD)
        self.assertIn("cloud-init", text, "Oracle delivers the SSH key via cloud-init")
        self.assertIn("cloud-init-network.service", text,
                      "cloud-init 26 renamed its network stage from cloud-init.service")
        self.assertNotRegex(code(text), r"\bcloud-init\.service\b",
                            "Fedora 44 no longer ships the old cloud-init.service unit")
        self.assertIn("datasource_list", text,
                      "the datasource list must be pinned; probing costs seconds per boot "
                      "and can settle on None before the network is up, which locks the "
                      "owner out of their own instance")
        self.assertIn("Oracle", text, "the OCI datasource must be first")
        self.assertIn("growpart", text,
                      "Oracle attaches a boot volume larger than the image; without "
                      "growpart the root filesystem stays at the image's size")

    def test_the_initramfs_is_not_hostonly(self) -> None:
        text = read(BUILD)
        self.assertIn('hostonly="no"', text,
                      "an image built on one machine and booted on another must carry "
                      "every driver it could need; a hostonly initramfs is how a cloud "
                      "image lands in dracut's emergency shell with no root device")
        for drv in ("virtio_blk", "virtio_net"):
            self.assertIn(drv, text, f"{drv} must be in the initramfs for a cloud/VM boot")

    def test_the_boot_animation_is_gated_here_too(self) -> None:
        text = read(BUILD)
        self.assertIn("plymouth-set-default-theme moos", text)
        self.assertIn("Theme=moos", text)
        # The same derived asset check the x86 build does.
        self.assertIn("moos.script", text)
        self.assertRegex(text, r"grep -oE 'Image",
                         "build-arm.sh must gate that every image moos.script loads is "
                         "installed; a missing one drops the splash to a text console")

    # ── the documentation the owner actually needs ──────────────────────────
    def test_the_oracle_guide_covers_the_parts_that_actually_block_people(self) -> None:
        text = read(DOCS)
        for topic, why in (
            ("PARAVIRTUALIZED", "the launch mode Oracle's import needs"),
            ("VM.Standard.A1.Flex", "the Always Free ARM shape"),
            ("Out of host capacity", "the error that actually stops people"),
            ("Pre-Authenticated Request", "how the image gets into Object Storage"),
            ("ttyAMA0", "the serial console that works on ARM"),
            ("moos-arm-remote", "how the desktop is reached"),
        ):
            self.assertIn(topic, text, f"the guide must cover {topic} — {why}")

        self.assertIn("2 OCPU", text,
                      "the guide still claims Oracle's retired 4-OCPU free allowance")
        self.assertIn("12 GB", text,
                      "the current Always Free Ampere memory allowance is 12 GB")
        self.assertIn("20 GB", text,
                      "Object Storage/custom-image bytes are only free inside the "
                      "tenancy's 20 GB allowance")


if __name__ == "__main__":
    unittest.main(verbosity=2)
