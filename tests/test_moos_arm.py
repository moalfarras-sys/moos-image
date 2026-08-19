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
        for p in (CONTAINERFILE, BUILD, WORKFLOW, DOCS):
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

    def test_the_disk_image_targets_arm(self) -> None:
        text = read(WORKFLOW)
        self.assertIn("--target-arch arm64", text,
                      "bootc-image-builder must be told to produce an arm64 disk")
        self.assertIn("--type qcow2", text,
                      "Oracle imports QCOW2; the workflow must produce one")

    # ── security posture ────────────────────────────────────────────────────
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

    def test_ssh_is_keys_only(self) -> None:
        text = read(BUILD)
        self.assertIn("PasswordAuthentication no", text,
                      "the instance has a public IP; password SSH is only an attack surface")
        self.assertIn("PermitRootLogin no", text)

    # ── the things that make a cloud image boot at all ──────────────────────
    def test_cloud_init_is_present_and_pinned(self) -> None:
        text = read(BUILD)
        self.assertIn("cloud-init", text, "Oracle delivers the SSH key via cloud-init")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
