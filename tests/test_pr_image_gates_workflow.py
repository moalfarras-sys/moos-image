#!/usr/bin/env python3
"""Gate: a pull request builds the x86 image and runs its in-image gates — and can publish nothing.

WHY THIS EXISTS

The gates that read a finished image run only inside the x86 image build, and that build ran only
on pushes to `main`. Wave W5 was green on every pull-request check and turned all three x86
editions red the moment it merged; with `main` red nothing could be released, and four finished
waves waited behind it (plan row P0.9).

.github/workflows/pr-image-gates.yml builds the generic edition on pull requests. Two things must
stay true of it, and neither is visible in a green run:

  * it must build THE SAME image the release builds — same Containerfile, same build arguments as
    build.yml's generic matrix row, same disk-space step — or it proves a different system;
  * it runs on code nobody has reviewed yet, so it must not be ABLE to publish: no package
    permission, no secret, no login, push, tag copy or signature.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PR = (ROOT / ".github/workflows/pr-image-gates.yml").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
ARM = (ROOT / ".github/workflows/build-arm.yml").read_text(encoding="utf-8")


def code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


class SameImage(unittest.TestCase):
    def test_it_runs_before_the_merge_for_everything_that_reaches_the_image(self) -> None:
        workflow = code(PR)
        trigger = workflow[workflow.index("on:"):workflow.index("concurrency:")]
        self.assertIn("pull_request:", trigger)
        for path in ('"Containerfile"', '"build_files/**"', '"system_files/**"',
                     '"moos-settings-kcm/**"'):
            self.assertIn(path, trigger, f"a change under {path} would merge without an image build")
        self.assertNotIn("paths-ignore", trigger)

    def test_the_settings_modules_are_an_image_input_on_both_architectures(self) -> None:
        """moos-settings-kcm/ compiles in the qmlshell-build stage of BOTH Containerfiles.

        The native System Settings modules (kcm_moos and the MoOS group's pages) are built from
        that tree and gated inside both image builds, yet neither the pull-request image build
        nor the ARM build listed it. A change to a module alone merged without building the
        image that ships it, on either architecture.
        """
        for containerfile in ("Containerfile", "Containerfile.arm"):
            self.assertIn("COPY moos-settings-kcm/",
                          (ROOT / containerfile).read_text(encoding="utf-8"),
                          f"{containerfile} no longer builds moos-settings-kcm; revisit this gate")
        arm = code(ARM)
        trigger = arm[arm.index("on:"):arm.index("\nenv:")]
        push = trigger[trigger.index("  push:"):trigger.index("  pull_request:")]
        pull_request = trigger[trigger.index("  pull_request:"):]
        for name, block in (("push", push), ("pull_request", pull_request)):
            self.assertIn('"moos-settings-kcm/**"', block,
                          f"build-arm.yml's {name} trigger misses moos-settings-kcm/**")

    def test_it_builds_what_the_release_builds(self) -> None:
        workflow = code(PR)
        self.assertIn("containerfiles: ./Containerfile", workflow)
        self.assertIn("containerfiles: ./Containerfile", code(RELEASE))
        # build.yml's generic row: image_name moos, nvidia "false" -> AKMODS_IMAGE=scratch.
        self.assertRegex(code(RELEASE), r'- image_name: moos\n\s+nvidia: "false"')
        self.assertIn('echo "image=scratch" >> "$GITHUB_OUTPUT"', RELEASE)
        self.assertIn("IMAGE_NAME=moos\n", workflow)
        self.assertIn("AKMODS_IMAGE=scratch\n", workflow)
        self.assertIn("oci: false", workflow)

        def pin(text: str, action: str) -> str:
            return re.search(rf"uses: {re.escape(action)}@(\S+)", text).group(1)

        for action in ("redhat-actions/buildah-build", "jlumbroso/free-disk-space", "actions/checkout"):
            self.assertEqual(pin(code(PR), action), pin(code(RELEASE), action),
                             f"{action} drifted between the pull-request build and the release build")


class CannotPublish(unittest.TestCase):
    def test_it_has_no_way_to_push_sign_or_tag(self) -> None:
        workflow = code(PR)
        permissions = re.findall(r"^\s*([a-z-]+): (read|write|none)\s*$", workflow, flags=re.M)
        self.assertEqual(permissions, [("contents", "read")],
                         "a build of unreviewed code must hold no permission but reading the checkout")
        for forbidden in ("secrets.", "podman-login", "push-to-registry", "cosign", "skopeo copy",
                          "docker login", "ghcr.io", "id-token", "packages:"):
            self.assertNotIn(forbidden, workflow, f"the pull-request image build mentions {forbidden}")
        self.assertNotIn("pull_request_target", workflow,
                         "pull_request_target runs with the base repository's secrets")


if __name__ == "__main__":
    unittest.main(verbosity=2)
