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

from test_arm_appstream_refresh import AppStreamImageTests
# /boot is 974 MiB and holds two deployments; the initramfs has to fit.
from test_arm_initramfs_size import ArmInitramfsFits

ROOT = Path(__file__).resolve().parents[1]
CONTAINERFILE = ROOT / "Containerfile.arm"
BUILD = ROOT / "build_files/build-arm.sh"
X86_BUILD = ROOT / "build_files/build.sh"
ARM_VERIFY = ROOT / "build_files/verify_arm_image.py"
DESKTOP_FINALIZER = ROOT / "build_files/finalize_moos_desktop.sh"
IMAGE_VERIFY = ROOT / "build_files/verify_image_experience.py"
HWDB_COMPILE = ROOT / "build_files/compile_system_hwdb.sh"
WORKFLOW = ROOT / ".github/workflows/build-arm.yml"
DOCS = ROOT / "docs/MOOS_ARM_ORACLE.md"
RUNTIME_GATE = ROOT / "tests/verify_arm_runtime.sh"
BOOT_GATE = ROOT / "tests/boot_arm_qcow2.sh"
BLOCK_COLDPLUG = ROOT / "system_files/usr/libexec/moos-arm-block-coldplug"
BLOCK_COLDPLUG_UNIT = (
    ROOT / "system_files/usr/lib/systemd/system/moos-arm-block-coldplug.service"
)


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
        for p in (
            CONTAINERFILE, BUILD, X86_BUILD, ARM_VERIFY, IMAGE_VERIFY,
            DESKTOP_FINALIZER,
            HWDB_COMPILE, WORKFLOW, DOCS,
            RUNTIME_GATE, BOOT_GATE,
            BLOCK_COLDPLUG, BLOCK_COLDPLUG_UNIT,
        ):
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

    def test_finished_arm_runs_the_generated_desktop_contract(self) -> None:
        build = code(read(BUILD))
        finalizer = code(read(DESKTOP_FINALIZER))
        verifier = code(read(ARM_VERIFY))
        self.assertIn("bash /ctx/finalize_moos_desktop.sh", build)
        self.assertIn("bash /ctx/finalize_moos_desktop.sh", code(read(X86_BUILD)),
                      "x86 and ARM must share the same final desktop authority")
        self.assertGreater(
            build.index("bash /ctx/finalize_moos_desktop.sh"),
            build.index("cp -a /moos-overlay/. /"),
            "package payloads must be overlaid before generated desktop assets are sealed",
        )
        for contract in (
            "COLLOID_COMMIT=",
            "BIBATA_VERSION=",
            "/usr/share/icons/MoOSUI2/index.theme",
            "/usr/share/icons/MoOSDark/cursors",
            "sed -i '/^prefer /d'",
            "/usr/share/moos/plasmalogin/kdeglobals",
            "/usr/lib/tmpfiles.d/moos-plasmalogin-greeter.conf",
        ):
            self.assertIn(contract, finalizer,
                          f"shared finished-desktop finalizer lacks {contract}")
        for outcome in (
            '"MoOSUI2", "MoOSUI2Light"',
            '"MoOS", "MoOSDark"',
            'line.startswith("prefer ")',
            "/usr/share/moos/plasmalogin/kdeglobals",
        ):
            self.assertIn(outcome, verifier,
                          f"finished ARM image never proves visual runtime outcome {outcome}")

    def test_clean_boot_does_not_rebuild_hwdb_before_udevd(self) -> None:
        helper = code(read(HWDB_COMPILE))
        self.assertIn("systemd-hwdb --usr update", helper)
        self.assertIn("rm -f /etc/udev/hwdb.bin", helper)
        self.assertIn("systemd-hwdb query", helper,
                      "the compiled hwdb must be queried, not trusted by file size")
        for build in (BUILD, X86_BUILD):
            self.assertIn(
                "bash /ctx/compile_system_hwdb.sh",
                code(read(build)),
                f"{build.name} does not move the compiled hardware database into /usr",
            )
        for gate in (ARM_VERIFY, IMAGE_VERIFY):
            gate_text = code(read(gate))
            self.assertIn("usr/lib/udev/hwdb.bin", gate_text)
            self.assertIn("etc/udev/hwdb.bin", gate_text)

    def test_arm_republishes_boot_partition_links_before_local_mounts(self) -> None:
        helper = code(read(BLOCK_COLDPLUG))
        unit = read(BLOCK_COLDPLUG_UNIT)
        build = code(read(BUILD))
        verifier = code(read(ARM_VERIFY))
        for contract in (
            "--subsystem-match=block",
            "--action=change",
            "--settle",
            "/dev/disk/by-uuid/",
        ):
            self.assertIn(contract, helper)
        for contract in (
            "ConditionArchitecture=arm64",
            "After=systemd-udev-trigger.service",
            "Before=local-fs-pre.target boot.mount boot-efi.mount",
            "ExecStart=/usr/libexec/moos-arm-block-coldplug",
        ):
            self.assertIn(contract, unit)
            self.assertIn(contract, verifier)
        self.assertIn("systemctl enable moos-arm-block-coldplug.service", build)
        self.assertIn("DefaultDeviceTimeoutSec=120", build)
        self.assertIn("moos-arm-block-coldplug.service", verifier)
        self.assertIn("emergency\\.service|emergency\\.target", read(BOOT_GATE))

    def test_the_curated_desktop_uses_fedora_44_package_names(self) -> None:
        """These names must be the ones Fedora 44 actually ships.

        This list is about SPELLING, not policy: a package renamed upstream
        fails the native build before it can produce an image, and that is what
        this test catches. `ramalama` left the list when Mo AI went cloud-only
        (docs/MOAI_CLOUD_ONLY_PLAN.md, stage C5) — the engine is no longer
        installed in any edition, so requiring its name here would assert a
        product decision this test was never about. That it is ABSENT is
        asserted by tests/test_moai_cloud_only.py, which also checks x86 and ARM
        agree; keeping the two concerns in separate files is deliberate.
        """
        text = code(read(BUILD))
        for current in (
            "kwin-libs", "plasma-breeze", "plasma-workspace",
            "plasma-discover", "kinfocenter", "bluedevil",
            "plasma-print-manager", "flatpak-kcm", "gwenview", "haruna",
            "kf6-baloo-file",
        ):
            self.assertIn(current, text, f"the ARM build is missing Fedora 44's {current}")
        for retired in ("kwin-wayland-libs", "\n    breeze ", "plasma-workspace-wayland"):
            self.assertNotIn(retired, text,
                             f"{retired.strip()} is not a Fedora 44 package; the native "
                             "build would fail before creating the image")

    def test_arm_first_party_surfaces_have_live_backends(self) -> None:
        build = code(read(BUILD))
        verifier = code(read(ARM_VERIFY))
        self.assertIn("tailscale", build,
                      "ARM ships Mo PC Remote but lacks the private HTTPS transport")
        self.assertIn("tailscaled.service", build,
                      "the private remote transport is installed but never starts")
        self.assertIn('"tailscale"', verifier,
                      "the finished ARM image never proves Tailscale is installed")
        self.assertIn('"tailscaled.service"', verifier,
                      "the finished ARM image never proves Tailscale is enabled")
        for unit in (
            "moai-gateway.service",
            "moai-control.service",
            "moai-agent-api.service",
            "moai-wake.service",
            "moos-cloud-audio.service",
            "moai-idle.timer",
            "openclaw-idle.timer",
            "moos-ensure-brain.timer",
            "moos-update-ready.timer",
            "moos-reclaim-disk.timer",
            "moos-theme-sync.path",
        ):
            self.assertIn(unit, build, f"ARM never enables the shared authority {unit}")
            self.assertIn(unit, verifier,
                          f"the finished ARM image never proves {unit} is enabled")
        # Every route the ARM UI offers must have a backend the FINISHED image
        # proves is present. `"ramalama"` left this list with Mo AI's local
        # brain: there is no longer a route that reaches a local engine, so
        # requiring the image to prove one would demand a backend for a door
        # that no longer exists (docs/MOAI_CLOUD_ONLY_PLAN.md, stages C2/C5).
        for backend in (
            '"plasma-discover"', '"kinfocenter"',
            '"bluedevil"', '"plasma-print-manager"', '"flatpak-kcm"',
        ):
            self.assertIn(backend, verifier,
                          f"finished ARM image does not prove route backend {backend}")

    def test_arm_installs_every_declared_icon_fallback(self) -> None:
        build = code(read(BUILD))
        verifier = code(read(ARM_VERIFY))
        self.assertIn("papirus-icon-theme", build,
                      "MoOSUI2 inherits Papirus but ARM never installs it")
        self.assertIn('"papirus-icon-theme"', verifier,
                      "the finished ARM image never proves its icon fallback exists")

    def test_arm_has_one_storefront(self) -> None:
        build = code(read(BUILD))
        for contract in (
            "org.kde.discover.desktop",
            "Name=Mo Store",
            "Icon=mo-store",
            "NoDisplay=true",
        ):
            self.assertIn(contract, build,
                          f"ARM does not enforce the one-storefront contract: {contract}")

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
        self.assertIn("MOOS_ARM_DISPLAY: gtk", text,
                      "the final ARM disk needs a mapped-window visual proof")
        self.assertNotIn("MOOS_ARM_SKIP_VISUAL_GATE", text,
                         "a release ARM run must never bypass its visual gate")

    def test_arm_greeter_selects_the_real_utm_scanout(self) -> None:
        build = read(BUILD)
        launcher = read(ROOT / "system_files/usr/libexec/moos-arm-greeter-kwin")
        self.assertIn("ExecStart=/usr/libexec/moos-arm-greeter-kwin", build)
        self.assertIn("/sys/class/drm/card*-*/status", launcher)
        self.assertIn('KWIN_DRM_DEVICES="$dri_node"', launcher)
        self.assertIn('[ -r "$dri_node" ] && [ -w "$dri_node" ]', launcher,
                      "KWin must wait until plasmalogin can open the scanout")
        self.assertIn("--virtual --width 1920 --height 1080", launcher)
        self.assertIn("QT_QUICK_BACKEND=software", build)
        self.assertIn('OWNER="plasmalogin", GROUP="video", MODE="0660"', build)
        self.assertIn('OWNER="plasmalogin", GROUP="render", MODE="0660"', build)
        self.assertIn("ExecStartPre=/usr/libexec/moos-greeter-gl-env", build)
        self.assertIn("/usr/bin/setfacl -m u:plasmalogin:rw", read(
            ROOT / "system_files/usr/libexec/moos-greeter-gl-env"
        ))

    def test_the_new_workflow_can_prove_a_feature_branch(self) -> None:
        text = read(WORKFLOW)
        self.assertIn("pull_request:", text,
                      "a workflow file added only on a feature branch cannot be manually "
                      "dispatched until it reaches the default branch; a pull-request "
                      "trigger is the safe first real build")
        for gate in (
            "bash -n build_files/build-arm.sh",
            "bash -n build_files/seal_arm_qcow2.sh",
            "bash -n tests/boot_arm_qcow2.sh",
            "python3 tests/test_moos_arm.py",
            "python3 tests/test_boot_splash_polish.py",
            "python3 tests/test_seal_arm_deployment.py",
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
        self.assertIn('"build_files/**"', pull_request_paths,
                      "Containerfile.arm copies all build_files, so every change is an ARM input")
        self.assertIn('"cosign.pub"', pull_request_paths,
                      "changing the key enforced by ARM must trigger an ARM build")
        self.assertIn(
            '".github/workflows/build-arm.yml"',
            pull_request_paths,
            "a pull request that repairs the ARM workflow must trigger that workflow",
        )

    def test_only_main_or_an_explicit_dispatch_can_publish_and_boot_a_disk(self) -> None:
        text = read(WORKFLOW)
        publish_if = "github.event_name == 'workflow_dispatch'"
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
                f"{step_name} cannot build a manually requested signed candidate",
            )
            self.assertIn("github.event_name == 'push'", match.group("body"))
            self.assertIn("github.ref == 'refs/heads/main'", match.group("body"))

        disk_job = text.split("\n  disk:\n", 1)
        self.assertEqual(len(disk_job), 2, "ARM workflow lost its disk job")
        disk_header = disk_job[1].split("\n    runs-on:", 1)[0]
        self.assertIn("github.ref == 'refs/heads/main'", disk_header)
        self.assertIn("github.event_name == 'workflow_dispatch'", disk_header)
        self.assertIn("needs.build.result == 'success'", disk_header)
        self.assertIn('publish_tag="candidate-${{ github.run_id }}-', text,
                      "manual branch proof must not overwrite ARM latest")
        self.assertNotIn('publish_tag=latest', text,
                         "the initial ARM push must always remain a candidate")

        push = text.index("- name: Push")
        sign = text.index("- name: Sign the ARM image by digest")
        verify = text.index("- name: Verify the signature against MoOS's installed key")
        promote = text.index("- name: Promote the verified ARM digest to production tags")
        self.assertLess(push, sign)
        self.assertLess(sign, verify)
        self.assertLess(verify, promote)
        self.assertLess(text.index("\n  disk:\n"), promote)
        promotion = text[promote:]
        self.assertIn('for tag in "$DATE_TAG" latest', promotion)
        self.assertIn("skopeo copy --preserve-digests", promotion)
        self.assertIn('if [ "$resolved" != "$DIGEST" ]', promotion)
        self.assertIn('cosign verify --key cosign.pub "$target_ref"', promotion)

        promote_job = text.split("\n  promote:\n", 1)
        self.assertEqual(len(promote_job), 2, "ARM workflow lost its promotion job")
        promote_header = promote_job[1].split("\n    steps:\n", 1)[0]
        self.assertIn("needs: [build, disk]", promote_header)
        self.assertIn("github.event_name == 'push'", promote_header)
        self.assertIn("github.ref == 'refs/heads/main'", promote_header)
        self.assertIn("needs.build.result == 'success'", promote_header)
        self.assertIn("needs.disk.result == 'success'", promote_header)
        self.assertIn(
            "cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}", text
        )
        before_promote = text.split("\n  promote:\n", 1)[0]
        self.assertNotIn("skopeo copy --preserve-digests", before_promote)
        self.assertEqual(text.count("skopeo copy --preserve-digests"), 1)

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
            "usr/libexec/moos-image-update",
            "moos-auto-update.timer",
            '"skopeo"',
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
        for proof in (
            "seal_arm_qcow2.sh",
            "boot_arm_qcow2.sh",
            "moos-arm-boot-proof",
            "sha256sum \"$MOOS_ARM_QCOW\"",
            "arm-boot-proof/proof-manifest.json",
            '"boot_proven_raw_qcow2_sha256": qcow_sha',
            "if-no-files-found: error",
        ):
            self.assertIn(proof, text, f"the final ARM disk path lacks {proof}")
        self.assertLess(
            text.index("Boot the final QCOW2 through UEFI"),
            text.index("Package the boot-proven ARM releases"),
            "the workflow packages the disk before proving it boots",
        )

    def test_arm_boot_proof_has_an_explicit_visual_development_mode(self) -> None:
        boot_gate = code(read(BOOT_GATE))
        self.assertIn("MOOS_ARM_DISPLAY", boot_gate)
        self.assertIn("gtk,gl=off", boot_gate)
        self.assertIn("MOOS_ARM_VISUAL_HOLD", boot_gate)
        self.assertIn("secrets.token_urlsafe", boot_gate,
                      "visual QA must not use a shared guest password")
        self.assertIn("plain_text_passwd", boot_gate,
                      "cloud-init must unlock the visual account in the same user record")
        self.assertNotIn("chpasswd:", boot_gate,
                         "a later chpasswd module makes cloud-init 26 report degraded")
        self.assertIn("ARM VISUAL FAILED", boot_gate,
                      "a failed visible VM must stay open for diagnosis")
        self.assertIn('"${qemu_display[@]}"', boot_gate)
        self.assertIn("-device virtio-keyboard-pci", boot_gate,
                      "the visual ARM VM must accept real keyboard input")
        self.assertIn("-device virtio-tablet-pci", boot_gate,
                      "the visual ARM VM must expose an absolute pointer")
        runtime_gate = code(read(RUNTIME_GATE))
        self.assertIn("QEMU Virtio Keyboard", runtime_gate)
        self.assertIn("QEMU Virtio Tablet", runtime_gate)
        self.assertIn("interactive_input=virtio-keyboard+tablet", runtime_gate)
        self.assertIn("touch '$continue_file'", boot_gate)
        self.assertIn("-display none", boot_gate,
                      "developers must retain a headless diagnostic mode")
        self.assertIn("screendump", boot_gate,
                      "headless diagnostics need a QEMU monitor fallback")
        self.assertIn("gtk_window_title", boot_gate,
                      "release evidence must target the exact mapped QEMU window")
        self.assertIn("xwininfo", boot_gate)
        self.assertIn("assert_visual_frame.py", boot_gate,
                      "ARM must share the black-plus-cursor pixel gate with x86")
        self.assertIn("sendkey shift", boot_gate,
                      "ARM visual proof must wake the idle Plasma Login Manager "
                      "before capturing the greeter")
        self.assertNotIn("MOOS_ARM_SKIP_VISUAL_GATE", boot_gate)

    def test_arm_enforces_the_same_signed_registry_policy(self) -> None:
        build = read(BUILD)
        verifier = read(ARM_VERIFY)
        for proof in (
            "sigstoreSigned",
            "/etc/pki/containers/moos.pub",
            "ghcr.io/moalfarras-sys",
            "containers-storage",
        ):
            self.assertIn(proof, build)
            self.assertIn(proof, verifier)
        self.assertNotIn("lsinitrd produced nothing", build,
                         "an unreadable ARM initramfs must fail, not warn and publish")
        for payload in ("ostree-prepare-root", "virtio_blk", "virtio_net", "virtio_gpu"):
            self.assertIn(payload, build)
        self.assertIn('modinfo -k "${kver}" -F filename', build,
                      "the driver gate must distinguish kernel built-ins from loadable modules")
        self.assertIn('modules.builtin', build,
                      "built-in ARM virtio drivers are valid only when the kernel inventory proves them")
        self.assertIn('_driver_basename', build,
                      "loadable virtio drivers must still be proven inside the initramfs archive")
        self.assertIn("rm -f /usr/lib/bootc/kargs.d/30-moos-latency.toml", build)

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

    def test_krdp_is_a_required_build_contract(self) -> None:
        text = read(BUILD)
        self.assertNotIn("no-krdp", text)
        self.assertNotIn("SSH only and no graphical remote", text)
        self.assertRegex(text, r"dnf5[^\n]*install[^\n]*krdp")

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
        self.assertIn(
            "kwin_wayland_wrapper --virtual --width 1920 --height 1080 --xwayland",
            text,
            "the ARM session stays Wayland-native, but ksmserver and compatibility "
            "apps need KWin's Xwayland bridge instead of crashing at login",
        )
        self.assertIn("/usr/share/xsessions", text,
                      "the finished image must fail if a dependency adds an X11 session")

    def test_first_party_apps_build_natively_for_arm64(self) -> None:
        container = read(CONTAINERFILE)
        build = read(BUILD)
        verifier = read(ARM_VERIFY)
        for contract in (
            "dotnet publish agent-linux/MoRemoteLinux.csproj",
            "-r linux-arm64",
            "flutter analyze --no-fatal-infos",
            "flutter test",
            "flutter build linux --release",
            'ENV TAR_OPTIONS="--no-same-owner"',
            "flutter precache --linux --no-universal",
            "build/linux/arm64/release/bundle",
            "COPY --from=moremote-build /out/ /usr/lib/mo-remote/",
            "COPY --from=moplayer-build /out/ /usr/lib/moplayer/",
        ):
            self.assertIn(contract, container)
        self.assertNotIn("Intentionally omitted from MoOS ARM", build)
        self.assertIn("/usr/lib/mo-remote/MoRemotePersonal", build)
        self.assertIn("/usr/bin/moplayer", build)
        self.assertIn("int.from_bytes(header[18:20]", verifier)
        self.assertIn("H264_ENCODERS", verifier)
        self.assertIn('"codec": "jpeg"', verifier)
        runtime = read(RUNTIME_GATE)
        self.assertIn("/usr/lib/moplayer/moplayer", runtime)
        self.assertIn("/usr/lib/mo-remote/MoRemotePersonal", runtime)
        self.assertIn("first_party_arch=aarch64", runtime)
        self.assertIn("first_party_linkage=resolved", runtime)

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
        self.assertIn("bootc-generic-growpart.service", text,
                      "Oracle attaches a boot volume larger than the image; bootc needs "
                      "a grow path that targets /sysroot rather than composefs at /")
        self.assertIn("resize_rootfs: false", text,
                      "cloud-init must not try to resize the composefs root")
        self.assertIn("groups: [wheel]", text,
                      "minimal ARM images do not guarantee legacy device groups; naming "
                      "them makes cloud-init abort before installing the SSH key")
        self.assertIn("preserve_hostname: true", text,
                      "the local cloud-init stage has no D-Bus for hostnamectl")
        self.assertIn("moos-cloud-hostname.service", text,
                      "provider hostnames still need one post-D-Bus authority")
        self.assertIn("moos-cloud-account-ready.service", text,
                      "the greeter must wait until AccountsService publishes the cloud user")

    def test_bootc_is_the_only_cloud_disk_growth_authority(self) -> None:
        build = read(BUILD)
        verifier = read(ARM_VERIFY)
        runtime = read(RUNTIME_GATE)
        boot_gate = read(BOOT_GATE)

        self.assertIn("systemctl enable bootc-generic-growpart.service", build)
        self.assertNotIn("systemctl enable moos-cloud-grow-root", build)
        self.assertIn('mode: "off"', build)
        self.assertNotRegex(build, r"(?m)^\s*mode:\s+off\s*$")
        for retired in (
            ROOT / "system_files/usr/libexec/moos-cloud-grow-root",
            ROOT / "system_files/usr/lib/systemd/system/moos-cloud-grow-root.service",
            ROOT / "system_files/usr/lib/systemd/system/moos-cloud-grow-root.timer",
        ):
            self.assertFalse(retired.exists(), f"duplicate grow authority remains: {retired}")
        self.assertIn("yaml.safe_load", verifier)
        self.assertIn('type(grow_mode) is str and grow_mode == "off"', verifier)
        for contract in (
            "ConditionVirtualization=vm",
            "ConditionPathExists=/usr/bin/growpart",
            "findmnt -vno SOURCE /sysroot",
            "/usr/lib/systemd/systemd-growfs /sysroot",
            "candidate.resolve(strict=True)",
        ):
            self.assertIn(contract, verifier)
        self.assertIn("growth_deadline", runtime)
        self.assertIn("bootc-generic-growpart.service", runtime)
        self.assertIn("cloud_grow=bootc-success", runtime)
        self.assertIn("runtime-${phase}-diagnostics.txt", boot_gate)
        self.assertIn("journalctl --no-pager -b -u bootc-generic-growpart.service", boot_gate)

    def test_the_runtime_gate_needs_no_root(self) -> None:
        # The boot gate pipes verify_arm_runtime.sh over SSH as the provisioned
        # user, whose sudoers entry allows ONLY reboot/poweroff. The 2026-08-20
        # release run booted a perfect disk and then died at
        # "blockdev: cannot open /dev/vda: Permission denied". Every fact this
        # gate needs must therefore come from unprivileged sources (sysfs via
        # lsblk, ioctls on mounted paths via btrfs) — never root-only
        # block-device tools.
        runtime = read(RUNTIME_GATE)
        runtime_code = code(runtime)
        for forbidden in ("blockdev", "sfdisk", "sgdisk", "partx", "fdisk", "wipefs"):
            self.assertNotRegex(
                runtime_code, rf"\b{forbidden}\b",
                f"the runtime gate runs as the provisioned SSH user; "
                f"'{forbidden}' needs root and will fail the release boot proof",
            )
        for required in (
            'disk_size="$(lsblk -bdnro SIZE "$disk")"',
            'partition_size="$(lsblk -bdnro SIZE "$device")"',
        ):
            self.assertIn(required, runtime,
                          "disk/partition sizes must be read through lsblk/sysfs")

    def test_arm_has_exactly_one_os_image_update_authority(self) -> None:
        text = read(BUILD)
        self.assertIn("systemctl enable moos-auto-update.timer", text)
        for rival in ("rpm-ostreed-automatic.timer", "bootc-fetch-apply-updates.timer"):
            self.assertIn(
                f"systemctl disable {rival}", text,
                f"{rival} would bypass the signed exact-digest ARM update backend",
            )

    def test_the_initramfs_is_not_hostonly(self) -> None:
        text = read(BUILD)
        self.assertIn('hostonly="no"', text,
                      "an image built on one machine and booted on another must carry "
                      "every driver it could need; a hostonly initramfs is how a cloud "
                      "image lands in dracut's emergency shell with no root device")
        for drv in ("virtio_blk", "virtio_pci", "virtio_scsi", "virtio_net",
                    "virtio_gpu", "virtio_console"):
            self.assertIn(drv, text, f"{drv} must be in the initramfs for a cloud/VM boot")
        self.assertIn('sysloglvl="0"', text,
                      "image composition must not request a missing syslog socket")

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
