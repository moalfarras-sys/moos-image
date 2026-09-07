#!/usr/bin/env python3
"""A person who cannot see the screen must be able to use MoOS.

MEASURED ON THE LIVE ARM MACHINE (2026-09-06), and this is the whole reason the
gate exists:

    at-spi-dbus-bus.service          active
    org.a11y.Bus GetAddress          unix:path=/run/user/1000/at-spi/bus_0
    orca                             NOT installed
    speech-dispatcher                NOT installed
    espeak-ng / espeak / festival    NOT installed
    QT_ACCESSIBILITY                 unset

The accessibility PLUMBING was running and led nowhere. The bus was up, so
anything that probed for "is accessibility available" would have said yes, while
there was no screen reader to connect to it and no speech engine to make a
sound. A blind user could not use this operating system at all.

Two halves, and both are needed:

1. The stack must SHIP. A bus with nothing behind it is not accessibility.
2. Qt must expose its tree. Every first-party MoOS app — Mo AI, Mo Store, Mo
   Settings, the Launcher, the greeter — is Qt/QML, and Qt publishes to AT-SPI
   only when the bridge is enabled. A screen reader could otherwise connect to
   the bus and read nothing from any MoOS surface.

Arabic is not optional here. espeak-ng ships /usr/share/espeak-ng-data/ar_dict;
on an OS whose engineering skill calls Arabic first-class, an English-only
screen reader would not have been a fix.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BUILDS = ("build_files/build.sh", "build_files/build-arm.sh")
ENV_DROPIN = REPO / "system_files/usr/lib/environment.d/60-moos-accessibility.conf"

# The screen reader, the speech bridge it talks to, and an engine that can speak.
# Any one of the three missing makes the other two useless.
REQUIRED = ("orca", "speech-dispatcher", "espeak-ng")


def code(text: str) -> str:
    """Strip comments — both builds now EXPLAIN this in prose."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


class TheStackShips(unittest.TestCase):
    def test_every_edition_installs_the_accessibility_stack(self) -> None:
        for relative in BUILDS:
            body = code((REPO / relative).read_text(encoding="utf-8"))
            for package in REQUIRED:
                with self.subTest(build=relative, package=package):
                    self.assertRegex(
                        body, rf"(?m)(^|\s){re.escape(package)}(\s|$)",
                        f"{relative} does not install {package}. The AT-SPI bus "
                        f"runs regardless, so its absence looks like working "
                        f"accessibility and is not.")

    def test_the_editions_agree(self) -> None:
        """x86 and ARM diverging here decides whether a person can use the
        computer. That is not a difference any edition gets to have."""
        answers = {}
        for relative in BUILDS:
            body = code((REPO / relative).read_text(encoding="utf-8"))
            answers[relative] = tuple(
                bool(re.search(rf"(?m)(^|\s){re.escape(p)}(\s|$)", body))
                for p in REQUIRED)
        self.assertEqual(len(set(answers.values())), 1,
                         f"editions disagree about accessibility: {answers}")


class QtIsVisibleToScreenReaders(unittest.TestCase):
    def test_the_bridge_is_enabled_for_the_session(self) -> None:
        self.assertTrue(ENV_DROPIN.is_file(),
                        "the Qt accessibility bridge drop-in is missing")
        text = ENV_DROPIN.read_text(encoding="utf-8")
        self.assertRegex(code(text), r"(?m)^QT_ACCESSIBILITY=1\s*$")

    def test_it_is_a_systemd_environment_drop_in_not_a_shell_profile(self) -> None:
        """The session's services are started by systemd, not a login shell, so
        a variable exported by a profile script never reaches plasmashell, the
        launcher or any Mo app."""
        self.assertIn("environment.d", str(ENV_DROPIN))
        self.assertTrue(str(ENV_DROPIN).endswith(".conf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
