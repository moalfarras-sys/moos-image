#!/usr/bin/env python3
"""Gate: the Plasma-next canary builds the release's image on the next Plasma — and can publish nothing.

WHY THIS EXISTS (plan row P6.7)

.github/workflows/plasma-next-canary.yml layers the Fedora KDE SIG's beta repository onto the release
base and builds the release Containerfile on top with `buildah build --from`, so a new Plasma meets
MoOS's seams weeks before the mutable base tag delivers it. Two properties make that evidence and
neither is visible in a green run:

  * it must build THE SAME image the release builds, on THE SAME base with only Plasma moved —
    same Containerfile, same generic build arguments, a base composed FROM the Containerfile's own
    first FROM — or it proves a different system;
  * it pulls packages from a third-party beta repository, so it must not be ABLE to publish: no
    permission but reading the checkout, no secret, no login, push or signature.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY = (ROOT / ".github/workflows/plasma-next-canary.yml").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
CONTAINERFILE = (ROOT / "Containerfile").read_text(encoding="utf-8")


def code(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


class SameImageNextPlasma(unittest.TestCase):
    def test_it_runs_weekly_on_demand_and_on_changes_to_the_seams(self):
        workflow = code(CANARY)
        trigger = workflow[workflow.index("on:"):workflow.index("concurrency:")]
        self.assertIn("schedule:", trigger)
        self.assertIn("workflow_dispatch:", trigger)
        for path in ('"build_files/plasma-seams/**"', '"build_files/plasma_seams.py"',
                     '".github/workflows/plasma-next-canary.yml"'):
            self.assertIn(path, trigger)
        self.assertNotIn("pull_request_target", workflow)

    def test_the_base_is_the_release_base_with_only_plasma_moved(self):
        first_from = re.search(r"^FROM\s+(\S+)", code(CONTAINERFILE), flags=re.M).group(1)
        workflow = code(CANARY)
        composed = re.search(r"^\s*FROM\s+(\S+)", workflow, flags=re.M)
        self.assertIsNotNone(composed, "the canary composes no base")
        self.assertEqual(composed.group(1), first_from,
                         "the canary's base is not the release base: it would prove another system")
        self.assertIn("dnf5 -y copr enable @kdesig/kde-beta", workflow)
        self.assertIn("dnf5 -y distro-sync --refresh --allowerasing", workflow)

    def test_a_base_that_did_not_reach_the_next_plasma_fails(self):
        # PR #161's first run: a soname bump blocked the move, distro-sync skipped it
        # silently, and the "next Plasma" canary built 6.7.5.
        workflow = code(CANARY)
        self.assertIn("--repo 'copr:copr.fedorainfracloud.org:group_kdesig:kde-beta' plasma-workspace", workflow)
        self.assertRegex(workflow, r'if \[ -n "\$next" \] && \[ "\$have" != "\$next" \]; then')
        self.assertIn("::error::the canary base did not reach Plasma", workflow)
        tag = re.search(r"-t (localhost/moos-plasma-next-base:\S+)", workflow).group(1)
        self.assertIn(f"--from {tag}", workflow, "the MoOS build does not use the composed base")

    def test_it_builds_what_the_release_builds(self):
        workflow = code(CANARY)
        self.assertIn("-f ./Containerfile", workflow)
        self.assertIn("containerfiles: ./Containerfile", code(RELEASE))
        # the generic row exactly: `moos`, not `moos-nvidia`/`moos-cloud`, and no NVIDIA stage
        self.assertRegex(workflow, r"--build-arg IMAGE_NAME=moos\s")
        self.assertRegex(workflow, r"--build-arg AKMODS_IMAGE=scratch\s")

        def pin(text: str, action: str) -> str:
            return re.search(rf"uses: {re.escape(action)}@(\S+)", text).group(1)

        for action in ("jlumbroso/free-disk-space", "actions/checkout"):
            self.assertEqual(pin(code(CANARY), action), pin(code(RELEASE), action),
                             f"{action} drifted between the canary and the release build")

    def test_it_keeps_the_seam_verdict(self):
        workflow = code(CANARY)
        self.assertIn("MoOS seams:", workflow)
        self.assertIn("actions/upload-artifact@", workflow)


class CannotPublish(unittest.TestCase):
    def test_it_has_no_way_to_push_sign_or_tag(self):
        workflow = code(CANARY)
        permissions = re.findall(r"^\s*([a-z-]+): (read|write|none)\s*$", workflow, flags=re.M)
        self.assertEqual(permissions, [("contents", "read")],
                         "a build on third-party beta packages must hold no permission but reading the checkout")
        for forbidden in ("secrets.", "podman-login", "push-to-registry", "cosign", "skopeo copy",
                          "docker login", "buildah push", "podman push", "buildah login",
                          "id-token", "packages:"):
            self.assertNotIn(forbidden, workflow, f"the canary mentions {forbidden}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
