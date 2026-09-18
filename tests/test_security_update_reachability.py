#!/usr/bin/env python3
"""How a base security update actually reaches a MoOS machine — said once, checked.

`build.yml` rebuilds nightly at 06:00 UTC and its comment said that picked up
Fedora/uBlue base security updates "promptly". It does not, and it cannot:

  * `build.yml` pushes ONLY a run/SHA-bound candidate tag and says so itself —
    "This workflow never moves production tags".
  * `promote-x86.yml` validates every run it is handed with `.event ==
    "workflow_dispatch"` and refuses anything else, so a `schedule` run's digests can
    never become `:latest`.

So a base security update reaches a fielded machine only through a release cycle, which
is what puts it through three QCOW2 boots and an ISO install first. That is the safety
model working — nothing ships unproven — and it means THE CADENCE OF RELEASE CYCLES IS
THE SECURITY CADENCE OF MoOS. An owner who does not run one does not get base security
updates, however many nights the rebuild is green.

This gate does not argue with that design. It holds the two halves together so the
claim and the mechanism cannot drift apart again, and so the day someone decides a
scheduled build MAY promote, they have to come here and say so.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
ARM = (ROOT / ".github/workflows/build-arm.yml").read_text(encoding="utf-8")
PROMOTE = (ROOT / ".github/workflows/promote-x86.yml").read_text(encoding="utf-8")


class SecurityUpdateReachability(unittest.TestCase):
    def test_both_architectures_are_rebuilt_against_a_moving_base(self):
        """A base change that breaks the tree should surface the next morning."""
        for name, text in (("build.yml", BUILD), ("build-arm.yml", ARM)):
            self.assertRegex(text, r"schedule:\s*(?:\n\s*#[^\n]*)*\n\s*- cron:",
                             f"{name} has no scheduled rebuild, so a broken base stays "
                             f"invisible until someone happens to touch it")

    def test_a_scheduled_build_still_cannot_reach_production(self):
        """The safety model: only a dispatched, boot-proven build is promotable."""
        self.assertIn('.event == "workflow_dispatch"', PROMOTE)
        self.assertIn("never moves production tags", BUILD)

    def test_the_workflow_does_not_claim_the_nightly_ships_anything(self):
        """The exact false sentence that was here, and its shape."""
        schedule = BUILD[BUILD.index("  schedule:"):BUILD.index('- cron: "0 6 * * *"')]
        self.assertNotIn("promptly", schedule,
                         "the nightly cannot deliver anything promptly or otherwise")
        for required in ("cannot", "release cycle", "P6.3"):
            self.assertIn(required, schedule,
                          f"the schedule comment no longer explains {required!r}")

    def test_the_gap_is_recorded_where_work_is_chosen(self):
        plan = (ROOT / "docs/DEVELOPMENT_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("cadence of release cycles", plan,
                      "the plan does not say that release cadence is security cadence")


if __name__ == "__main__":
    unittest.main()
