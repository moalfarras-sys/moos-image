#!/usr/bin/env python3
"""ARM and x86 must enable the same MoOS user units, or say why not.

WHY THIS GATE EXISTS
--------------------
The four editions -- moos, moos-nvidia, moos-cloud (build.sh) and moos-arm
(build-arm.sh) -- share one filesystem overlay and one set of user units. What
they do NOT share is the code that turns those units on: each build script has
its own `systemctl --global enable` list. A unit added to one list and not the
other is invisible drift. Nothing fails, nothing is logged, and the feature
simply does not exist on the other editions.

That is not hypothetical. Mo PC Remote's recovery watchdog lived in one
machine's ~/.config/systemd/user from 2026-08-30 to 2026-09-08 and was in no
image at all, so a crashed Remote stayed dead until reboot on every edition. It
is now enabled in both scripts, which is what this gate keeps true.

The two lists are currently identical (14 units). This locks that in: adding a
unit to one script now fails the build unless it is also added to the other, or
declared below with a reason. The allowlist is deliberately empty -- an empty
exception list is the honest starting point, and the failure message tells you
exactly which list to add to.
"""
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Units an edition may legitimately enable alone, each with the reason it is
# not shared. Keep this empty unless a unit genuinely cannot exist elsewhere
# (e.g. hardware only one edition has). "It was easier" is not a reason.
EDITION_ONLY: dict[str, str] = {}


def enabled_units(script: Path) -> set[str]:
    """Every unit passed to `systemctl --global enable`, across line continuations."""
    text = script.read_text(encoding="utf-8")
    found = set()
    for match in re.finditer(r"systemctl --global enable((?:[^\n\\]|\\\n)*)", text):
        body = match.group(1).replace("\\\n", " ")
        for token in body.split():
            if re.fullmatch(r"[\w.@-]+\.(service|timer|path|socket)", token):
                found.add(token)
    return found


class EditionParity(unittest.TestCase):
    def setUp(self) -> None:
        self.x86 = enabled_units(REPO / "build_files/build.sh")
        self.arm = enabled_units(REPO / "build_files/build-arm.sh")

    def test_the_parser_found_something(self) -> None:
        """A regex that matches nothing turns every assertion below into a
        tautology -- the exact way test_x86_nvidia_is_deliberately_untouched
        guarded the NVIDIA boot path while inspecting zero blocks."""
        self.assertGreaterEqual(len(self.x86), 10,
                                "no --global enables parsed out of build.sh")
        self.assertGreaterEqual(len(self.arm), 10,
                                "no --global enables parsed out of build-arm.sh")

    def test_x86_enables_nothing_arm_misses(self) -> None:
        missing = {u for u in self.x86 - self.arm if u not in EDITION_ONLY}
        self.assertFalse(missing, (
            f"build.sh enables {sorted(missing)} and build-arm.sh does not. "
            "Add them to the ARM list (both its presence check and its "
            "`systemctl --global enable`), or declare them in EDITION_ONLY "
            "with the reason they cannot be shared."))

    def test_arm_enables_nothing_x86_misses(self) -> None:
        missing = {u for u in self.arm - self.x86 if u not in EDITION_ONLY}
        self.assertFalse(missing, (
            f"build-arm.sh enables {sorted(missing)} and build.sh does not. "
            "Add them to build.sh, or declare them in EDITION_ONLY with the "
            "reason they cannot be shared."))

    def test_arm_proves_shared_units_exist_before_enabling_them(self) -> None:
        """ARM fails the build with a named FATAL if a shared unit is missing.
        `systemctl --global enable` on a missing unit is a poor substitute for
        that message, and the presence loop is what makes a rename obvious."""
        arm = (REPO / "build_files/build-arm.sh").read_text(encoding="utf-8")
        presence = arm.split("for unit in", 1)[1].split("; do", 1)[0]
        listed = {t for t in presence.replace("\\\n", " ").split()
                  if re.fullmatch(r"[\w.@-]+\.(service|timer|path|socket)", t)}
        unproven = self.arm - listed - set(EDITION_ONLY)
        self.assertFalse(unproven, (
            f"build-arm.sh enables {sorted(unproven)} without listing them in "
            "the presence check above, so a renamed unit would fail later and "
            "less clearly."))

    def test_every_enabled_unit_actually_ships(self) -> None:
        """The strongest of the four: a unit nobody ships cannot be enabled."""
        units = REPO / "system_files/usr/lib/systemd/user"
        for unit in sorted(self.x86 | self.arm):
            with self.subTest(unit=unit):
                self.assertTrue((units / unit).exists(),
                                f"{unit} is enabled by a build script but is "
                                f"not in system_files/usr/lib/systemd/user")


if __name__ == "__main__":
    unittest.main(verbosity=2)
