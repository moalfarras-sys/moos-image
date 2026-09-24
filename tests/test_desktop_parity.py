#!/usr/bin/env python3
"""Gate: the ARM edition asks by name for what x86 inherits, and the image gate proves it.

WHY THIS EXISTS

build_files/verify_desktop_parity.py checks capabilities on the finished image of both
architectures: Arabic RTL detection, pw-dump for the privacy chip, Breeze GTK and gtkconfig for
the look moos-theme selects, the Sonnet spell-check plugin, the ALSA route into PipeWire, and
every applet and pinned status item the MoOS Bar template names, and the kdialog App Drop asks
with. On the A1 (44.20260923.568) all eight capabilities were missing, while the published x86
image (44.20260923.920) had every one.

This test is the source half: both build scripts run the gate, build-arm.sh installs a package
for every capability (x86 gets them from kinoite-main), and the gate is proven to refuse a root
that lacks each one.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build_files"))
import verify_desktop_parity as parity  # noqa: E402

TEMPLATE = ROOT / "system_files" / parity.LAYOUT

# The ARM package that supplies each capability's first path.
ARM_PACKAGE = {
    "usr/share/qt6/translations/qtbase_ar.qm": "qt6-qttranslations",
    "usr/bin/pw-dump": "pipewire-utils",
    "usr/share/themes/Breeze/gtk-3.0/gtk.css": "breeze-gtk-gtk3",
    "usr/share/themes/Breeze/gtk-4.0/gtk.css": "breeze-gtk-gtk4",
    "usr/lib64/qt6/plugins/kf6/kded/gtkconfig.so": "kde-gtk-config",
    "usr/lib64/qt6/plugins/kf6/sonnet/sonnet_hunspell.so": "kf6-sonnet-hunspell",
    "usr/share/alsa/alsa.conf.d/99-pipewire-default.conf": "pipewire-alsa",
    "usr/bin/kdialog": "kdialog",
}


def code(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def full_root(tmp: Path, skip: set[str] = frozenset(), extra_applet_missing: str = "") -> Path:
    for _loss, alternatives in parity.CAPABILITIES:
        if alternatives[0] in skip:
            continue
        path = tmp / alternatives[0]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    layout = tmp / parity.LAYOUT
    layout.parent.mkdir(parents=True, exist_ok=True)
    layout.write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    placed, pinned = parity.bar_applets(layout.read_text(encoding="utf-8"))
    for plugin in placed + pinned:
        if plugin == extra_applet_missing:
            continue
        so = tmp / f"usr/lib64/qt6/plugins/plasma/applets/{plugin}.so"
        so.parent.mkdir(parents=True, exist_ok=True)
        so.write_text("x", encoding="utf-8")
    return tmp


class BothBuildsRunIt(unittest.TestCase):
    def test_both_build_scripts_run_the_gate(self):
        for script in ("build.sh", "build-arm.sh"):
            text = code((ROOT / "build_files" / script).read_text(encoding="utf-8"))
            self.assertIn("python3 /ctx/verify_desktop_parity.py --root /", text, script)

    def test_arm_installs_a_package_for_every_capability(self):
        text = code((ROOT / "build_files/build-arm.sh").read_text(encoding="utf-8"))
        firsts = [alternatives[0] for _loss, alternatives in parity.CAPABILITIES]
        self.assertEqual(sorted(firsts), sorted(ARM_PACKAGE), "a capability has no ARM package")
        for path, package in ARM_PACKAGE.items():
            self.assertRegex(text, rf"(?<![\w-]){package}(?![\w-])",
                             f"build-arm.sh never installs {package}, so ARM lacks /{path}")


class TheGateReadsTheRealBar(unittest.TestCase):
    def test_the_parser_finds_the_bar_the_template_draws(self):
        placed, pinned = parity.bar_applets(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(placed[0], "org.moos.brand")
        self.assertIn("org.kde.plasma.systemtray", placed)
        self.assertIn("org.moos.nova.clock", placed)
        self.assertIn("org.kde.plasma.networkmanagement", pinned)
        self.assertIn("org.kde.plasma.volume", pinned)
        self.assertEqual(len(placed), 6)
        self.assertEqual(len(pinned), 4)


class TheGateRefuses(unittest.TestCase):
    def test_a_complete_root_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(parity.problems(full_root(Path(raw))), [])

    def test_each_missing_capability_is_named(self):
        for _loss, alternatives in parity.CAPABILITIES:
            with self.subTest(path=alternatives[0]), tempfile.TemporaryDirectory() as raw:
                found = parity.problems(full_root(Path(raw), skip={alternatives[0]}))
                self.assertEqual(len(found), 1, found)
                self.assertIn(alternatives[0], found[0])

    def test_a_bar_applet_the_edition_lacks_is_named(self):
        with tempfile.TemporaryDirectory() as raw:
            found = parity.problems(full_root(Path(raw), extra_applet_missing="org.kde.plasma.volume"))
            self.assertEqual(found, ["the MoOS Bar pins status item org.kde.plasma.volume, "
                                     "which this edition does not ship"])

    def test_the_command_fails_on_an_empty_root(self):
        with tempfile.TemporaryDirectory() as raw:
            self.assertEqual(parity.main(["--root", raw]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
