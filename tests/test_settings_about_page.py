#!/usr/bin/env python3
"""Gate: "About this device" is a MoOS page that answers as MoOS, from measured facts.

WHY THIS EXISTS

`moos://settings/about` — the Overview's facts, Mo AI's `open_settings about` — opened the
desktop project's own About module. That page is correct for what it is, and wrong for MoOS:
it lists the toolkit and the desktop projects MoOS is built from, by name and version, under a
heading the owner reads as "my system". The identity contract says a person who asks their
computer what it is running gets one answer. Every identity gate was green, because those
gates read MoOS's files and that page is not one of them.

The page is now kcm_moos, the first module of System Settings' MoOS group, drawn from the
status document moos-settings-status publishes. This gate holds what makes it true rather
than merely branded:

  * the router and the status helper agree that `about` is MoOS Settings' own section, which
    `moos-settings` opens as kcm_moos, and nothing opens the desktop's About module any more;
  * the helper derives the EDITION and BUILD DATE from the booted deployment's own record and
    answers "" / 0 for an origin it does not recognise — never a guess;
  * identity is normalised ONCE, at the source: the helper publishes kernelLabel ("Linux
    7.2.7" — `uname -r` continues with the packager's build tag `-200.fc44.x86_64`, another
    distribution's name), editionLabel, archLabel and sessionLabel, and the page binds only
    those labels (moved here from the retired Command Center's JavaScript);
  * the page needs no status feed to be reachable, and every fact row shows "Unknown" in
    words when its value is missing.
"""

from __future__ import annotations

import json
import re
import runpy
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "moos-settings-kcm/modules/overview/ui/main.qml"
FACT_ROW = ROOT / "moos-settings-kcm/common/MoosFactRow.qml"
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
ROUTER = ROOT / "system_files/usr/bin/moos-open"
LAUNCHER = ROOT / "system_files/usr/bin/moos-settings"
ARABIC = re.compile(r"[؀-ۿ]")


def code_only(text: str, marker: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(marker))


class RouterAndHelper(unittest.TestCase):
    def test_about_is_a_section_of_moos_settings_on_both_sides(self) -> None:
        router = code_only(ROUTER.read_text(encoding="utf-8"), "#")
        self.assertRegex(router, r"(?m)^    settings/about\)\s+gui moos-settings --section=about\s*;;")
        self.assertNotIn("kcm_about-distro", router,
                         "a route opens the desktop's own About module again; it names the "
                         "projects MoOS is built from as if they were the owner's system")
        scope = runpy.run_path(str(STATUS))
        self.assertEqual(scope["DESTINATIONS"]["about"], ("moos-settings", "--section=about"))
        self.assertNotIn("kcm_about-distro", code_only(STATUS.read_text(encoding="utf-8"), "#"))
        launcher = code_only(LAUNCHER.read_text(encoding="utf-8"), "#")
        self.assertRegex(launcher, r"--section=about\)\s*module=kcm_moos\s*;;",
                         "moos-settings --section=about must open MoOS's own module")
        self.assertNotIn("kcm_about-distro", launcher)

    def test_an_option_is_not_mistaken_for_a_settings_module(self) -> None:
        probe = runpy.run_path(str(STATUS))["destinations_state"]
        with patch.dict(probe.__globals__, command=lambda *a, **kw: ""), \
                patch.object(shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"):
            state = probe()
        self.assertTrue(state["about"], "`--section=about` was looked up as a KCM plugin")
        self.assertFalse(state["display"], "with no plugin directory a KCM route must stay unavailable")
        with patch.dict(probe.__globals__, command=lambda *a, **kw: ""), \
                patch.object(shutil, "which", return_value=None):
            self.assertFalse(probe()["about"], "no launcher, no page")

    def test_edition_and_build_date_come_from_the_booted_deployment(self) -> None:
        probe = runpy.run_path(str(STATUS))["deployment_state"]
        official = "ostree-image-signed:docker://ghcr.io/moalfarras-sys/"
        cases = (
            (official + "moos:latest", 1789646400, "moos", 1789646400),
            (official + "moos-nvidia@sha256:" + "a" * 64, 1789646400, "moos-nvidia", 1789646400),
            (official + "moos-cloud:20260917", 1, "moos-cloud", 1),
            (official + "moos-arm:latest", None, "moos-arm", 0),
            # Not MoOS's registry path: no edition is claimed, whatever the name looks like.
            ("ostree-image-signed:docker://example.org/moos-nvidia:latest", 5, "", 5),
            (official + "moos-nvidia-extra:latest", 5, "", 5),
            (official + "moos:latest", True, "moos", 0),
            (official + "moos:latest", -4, "moos", 0),
            (official + "moos:latest", "yesterday", "moos", 0),
        )
        for reference, timestamp, edition, built in cases:
            booted = {"booted": True, "container-image-reference": reference, "version": "44.1"}
            if timestamp is not None:
                booted["timestamp"] = timestamp
            raw = json.dumps({"deployments": [booted]})
            with self.subTest(reference=reference, timestamp=timestamp), \
                    patch.dict(probe.__globals__, command=lambda *a, **kw: raw):
                state = probe()
            self.assertEqual((state["edition"], state["builtAt"]), (edition, built))
        with patch.dict(probe.__globals__, command=lambda *a, **kw: ""):
            state = probe()
        self.assertEqual((state["edition"], state["builtAt"], state["known"]), ("", 0, False))

    def test_the_snapshot_carries_architecture_session_and_their_labels(self) -> None:
        scope = runpy.run_path(str(STATUS))
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
            state = scope["full_state"]()
        self.assertEqual(state["session"], "wayland")
        self.assertRegex(state["arch"], r"^[a-z0-9_]+$")
        self.assertEqual(state["kernelLabel"], scope["kernel_label"](state["kernel"]))
        self.assertEqual(state["editionLabel"], scope["edition_label"](state["deployment"]["edition"]))
        self.assertEqual(state["archLabel"], scope["arch_label"](state["arch"]))
        self.assertEqual(state["sessionLabel"], scope["session_label"]("wayland"))


class TheLabels(unittest.TestCase):
    """The Command Center's kernelLabel/editionLabel/archLabel/sessionLabel, now at the source."""

    scope = runpy.run_path(str(STATUS))

    def test_the_kernel_is_shown_as_the_kernels_number(self) -> None:
        kernel_label = self.scope["kernel_label"]
        self.assertEqual(kernel_label("7.2.5-200.fc44.x86_64"), "Linux 7.2.5")
        self.assertEqual(kernel_label("6.12.0-55.el10.aarch64"), "Linux 6.12.0")
        self.assertEqual(kernel_label("7.3-rc2"), "Linux 7.3")
        for missing in ("", "—", None, 7):
            self.assertEqual(kernel_label(missing), "")
        for release in ("7.2.5-200.fc44.x86_64", "6.17.1-300.fc43.aarch64"):
            self.assertNotRegex(kernel_label(release), r"(?i)fc\d|el\d|fedora|x86_64|aarch64")

    def test_an_edition_is_named_in_words_or_not_at_all(self) -> None:
        edition_label = self.scope["edition_label"]
        for edition in ("moos", "moos-nvidia", "moos-cloud", "moos-arm"):
            label = edition_label(edition)
            with self.subTest(edition=edition):
                self.assertTrue(label["en"].startswith("MoOS"), label)
                self.assertTrue(label["ar"].startswith("MoOS") and ARABIC.search(label["ar"]), label)
                self.assertNotIn("moos-", label["en"] + label["ar"],
                                 "an image address is not a product name")
        self.assertIn("NVIDIA", edition_label("moos-nvidia")["ar"])
        for unknown in ("", "kinoite", "moos-nvidia-extra", None):
            self.assertEqual(edition_label(unknown), {"ar": "", "en": ""})

    def test_architecture_and_session_are_said_in_the_owners_words(self) -> None:
        arch_label, session_label = self.scope["arch_label"], self.scope["session_label"]
        self.assertEqual(arch_label("x86_64"), {"ar": "64 بت · x86", "en": "64-bit · x86"})
        self.assertEqual(arch_label("aarch64")["en"], "64-bit · ARM")
        self.assertEqual(arch_label("riscv64"), {"ar": "riscv64", "en": "riscv64"})
        for session in ("wayland", "", None):
            label = session_label(session)
            self.assertTrue(label["en"].startswith("MoOS desktop"), label)
            self.assertRegex(label["ar"], ARABIC)
            self.assertNotRegex(label["en"] + label["ar"], r"(?i)wayland",
                                "the display protocol is not the desktop's name")
        self.assertEqual(session_label("x11")["en"], "MoOS desktop · X11")


class PageSource(unittest.TestCase):
    def test_every_fact_is_a_field_of_the_status_document(self) -> None:
        qml = code_only(PAGE.read_text(encoding="utf-8"), "//")
        view = qml[qml.index("id: systemFacts"):]
        rows = re.findall(r"MoosFactRow \{(.*?)\n            \}", view, re.S)
        self.assertGreaterEqual(len(rows), 12, "the About facts lost rows")
        for row in rows:
            value = re.search(r"value: (.*?)(?:\n {16}[a-zA-Z.]+:|\Z)", row, re.S).group(1)
            self.assertIn("root.ready", value, f"a fact is shown before the feed is read: {row[:80]}")
            self.assertRegex(value, r"kcm\.status\.|root\.(?:deployment|memory|storage)\.",
                             f"a fact that is not a measured field: {row[:80]}")
        # The strings a person would recognise from the module this page replaced.
        for foreign in ("KDE", "Plasma", "Qt ", "Frameworks", "Fedora", "Kinoite"):
            self.assertNotIn(foreign, view, f"the About facts name {foreign.strip()}")
        self.assertIn("kcm.status.kernelLabel", view,
                      "the raw kernel release carries the packager's build tag")
        for label in ("editionLabel", "sessionLabel", "archLabel"):
            self.assertIn(f"kcm.status.{label}", view)
        self.assertNotRegex(qml, r"status\.kernel\b(?!Label)")
        self.assertNotRegex(qml, r"deployment\.edition\b", "bind editionLabel, not the image name")
        self.assertNotRegex(qml, r"status\.(?:arch|session)\b(?!Label)")

    def test_the_page_needs_no_status_to_be_reached_or_to_link_on(self) -> None:
        qml = PAGE.read_text(encoding="utf-8")
        own = re.search(r"readonly property var ownPages: \[([^\]]*)\]", qml).group(1)
        for page in ("about", "overview", "whats-new", "update"):
            self.assertIn(f'"{page}"', own)
        self.assertIn('root.open("moos://settings/whats-new")', qml,
                      "About this device must lead to What's new")
        self.assertIn("function aboutReport()", qml)
        self.assertIn("clipboard.copy()", qml, "Copy details must reach the clipboard")

    def test_unknown_is_said_in_words(self) -> None:
        row = FACT_ROW.read_text(encoding="utf-8")
        self.assertIn('readonly property string unknownText: MoUI.Locale.local("غير معروف", "Unknown")', row)
        self.assertIn(": fact.unknownText", row)
        self.assertIn('Accessible.name: label + ": " + (value || unknownText)', row)


if __name__ == "__main__":
    unittest.main(verbosity=2)
