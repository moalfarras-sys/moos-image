#!/usr/bin/env python3
"""Gate: "About this device" is a MoOS page that answers as MoOS, from measured facts.

WHY THIS EXISTS

`moos://settings/about` — the System section's "About this device" tile, the Overview's "Device
details" button, Mo AI's `open_settings about` — opened the desktop project's own About module.
That page is correct for what it is, and wrong for MoOS: it lists the toolkit and the desktop
projects MoOS is built from, by name and version, under a heading the owner reads as "my
system". The identity contract says a person who asks their computer what it is running gets one
answer. Every identity gate was green, because those gates read MoOS's files and that page is
not one of them.

The page is now drawn by MoOS Settings from the same live status document the Overview reads.
This gate holds what makes it true rather than merely branded:

  * the router and the status helper agree that `about` is MoOS Settings' own section, and
    nothing in the router opens the desktop's About module any more;
  * the helper derives the EDITION and BUILD DATE from the booted deployment's own record and
    answers "" / 0 for an origin it does not recognise — never a guess;
  * the kernel is shown as the kernel's number. `uname -r` continues with the packager's build
    tag (`-200.fc44.x86_64`), which would put another distribution's name on MoOS's own page;
  * an in-app page is available without the status feed, opens without leaving the window, and
    every fact row shows "Unknown" in words when its value is missing.
"""

from __future__ import annotations

import json
import re
import runpy
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "system_files/usr/share/moos/apps/settings/main.qml"
STATUS = ROOT / "system_files/usr/libexec/moos-settings-status"
ROUTER = ROOT / "system_files/usr/bin/moos-open"
NODE = shutil.which("node")


def qml_function(qml: str, name: str) -> str:
    start = qml.index("    function " + name + "(")
    end = qml.index("{", start) + 1
    depth = 1
    while depth:
        depth += {"{": 1, "}": -1}.get(qml[end], 0)
        end += 1
    return qml[start:end]


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

    def test_the_snapshot_carries_architecture_and_session(self) -> None:
        scope = runpy.run_path(str(STATUS))
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}):
            state = scope["full_state"]()
        self.assertEqual(state["session"], "wayland")
        self.assertRegex(state["arch"], r"^[a-z0-9_]+$")


@unittest.skipUnless(NODE, "Node required to execute the page's JavaScript")
class PageLogic(unittest.TestCase):
    def run_js(self, body: str, *, rtl: bool = False) -> None:
        qml = APP.read_text(encoding="utf-8")
        names = ("local", "isolated", "editionLabel", "kernelLabel", "archLabel", "sessionLabel",
                 "routeAvailable", "routeReason", "openRoute", "selectSection", "activateRequested",
                 "argValue", "inAppPage")
        in_app = re.search(r"readonly property var inAppRoutes: \((\{[^}]*\})\)", qml).group(1)
        about = re.search(r"readonly property var aboutSection: \((\{.*?\n    \})\)", qml, re.S).group(1)
        news = re.search(r"readonly property var whatsNewSection: \((\{.*?\n    \})\)", qml, re.S).group(1)
        script = f"""
const assert = require('node:assert/strict');
let rtl = {str(rtl).lower()}, statusLoaded = false, statusError = '', launchError = '';
let status = {{destinations: {{}}}}, searchQuery = 'x', activeSection = 'home';
let contentFlick = {{contentY: 9}}, calls = [];
const Qt = {{openUrlExternally: url => {{ calls.push(url); return true }}, application: {{arguments: []}}}};
const inAppRoutes = {in_app};
const aboutSection = {about};
const whatsNewSection = {news};
const inAppPages = [aboutSection, whatsNewSection];
const sections = [{{id: 'home'}}, {{id: 'system'}}];
""" + "\n".join(qml_function(qml, name) for name in names) + "\n" + body
        result = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])

    def test_the_kernel_is_shown_as_the_kernels_number(self) -> None:
        self.run_js("""
assert.equal(kernelLabel('7.2.5-200.fc44.x86_64'), 'Linux 7.2.5');
assert.equal(kernelLabel('6.12.0-55.el10.aarch64'), 'Linux 6.12.0');
assert.equal(kernelLabel('7.3-rc2'), 'Linux 7.3');
for (const missing of ['', '—', undefined, null]) assert.equal(kernelLabel(missing), '');
for (const release of ['7.2.5-200.fc44.x86_64', '6.17.1-300.fc43.aarch64'])
    assert.ok(!/fc\\d|el\\d|fedora/i.test(kernelLabel(release)), kernelLabel(release));
""")

    def test_an_edition_is_named_in_words_or_not_at_all(self) -> None:
        self.run_js("""
for (const edition of ['moos', 'moos-nvidia', 'moos-cloud', 'moos-arm']) {
    const label = editionLabel(edition);
    assert.ok(label.startsWith('MoOS'), label);
    assert.ok(!label.includes('moos-'), 'an image address is not a product name: ' + label);
}
for (const unknown of ['', 'kinoite', 'moos-nvidia-extra', undefined]) assert.equal(editionLabel(unknown), '');
assert.equal(archLabel('x86_64'), '64-bit · x86');
assert.equal(archLabel('riscv64'), 'riscv64');
assert.ok(sessionLabel('wayland').startsWith('MoOS desktop'));
assert.ok(sessionLabel('').startsWith('MoOS desktop'));
""")
        self.run_js("""
assert.ok(editionLabel('moos-nvidia').includes('NVIDIA') && /[\\u0600-\\u06FF]/.test(editionLabel('moos-nvidia')));
assert.ok(/[\\u0600-\\u06FF]/.test(sessionLabel('wayland')));
""", rtl=True)

    def test_the_page_opens_inside_the_window_and_needs_no_status(self) -> None:
        self.run_js("""
assert.equal(statusLoaded, false);
assert.equal(routeAvailable('moos://settings/about'), true, 'an in-app page does not wait for the feed');
assert.equal(routeReason('moos://settings/about'), '');
assert.equal(routeAvailable('moos://settings/display'), false);
openRoute('moos://settings/about');
assert.deepEqual(calls, [], 'the About page must not leave the window');
assert.equal(activeSection, 'about'); assert.equal(searchQuery, ''); assert.equal(contentFlick.contentY, 0);
activeSection = 'home';
activateRequested(['moos-settings', '--section=about']);
assert.equal(activeSection, 'about', 'moos-open settings/about lands on the page in a running window');
activateRequested(['moos-settings', '--section=system']); assert.equal(activeSection, 'system');
activateRequested(['moos-settings', '--section=nonsense']); assert.equal(activeSection, 'system');
openRoute('moos://settings/whats-new');
assert.deepEqual(calls, [], "What's new is a page of this window too");
assert.equal(activeSection, 'whats-new');
assert.equal(inAppPage('whats-new').parent, 'system'); assert.equal(inAppPage('display'), null);
activateRequested(['moos-settings', '--section=whats-new']); assert.equal(activeSection, 'whats-new');
""")


class PageSource(unittest.TestCase):
    def test_every_fact_is_a_field_of_the_status_document(self) -> None:
        qml = code_only(APP.read_text(encoding="utf-8"), "//")
        view = qml[qml.index("id: aboutView"):]
        view = view[:view.index("id: whatsNewView")]
        rows = re.findall(r"FactRow \{(.*?)\n {32}\}", view, re.S)
        self.assertGreaterEqual(len(rows), 12, "the About page lost fact rows")
        for row in rows:
            value = re.search(r"value: (.*?)(?:\n {36}[a-z]+:|\Z)", row, re.S).group(1)
            self.assertIn("win.statusLoaded", value, f"a fact is shown before the feed is read: {row[:80]}")
            self.assertIn("win.status.", value, f"a fact that is not a measured field: {row[:80]}")
        # The strings a person would recognise from the module this page replaced.
        for foreign in ("KDE", "Plasma", "Qt ", "Frameworks", "Fedora", "Kinoite"):
            self.assertNotIn(foreign, view, f"the About page names {foreign.strip()}")
        self.assertIn("win.kernelLabel(win.status.kernel)", view,
                      "the raw kernel release carries the packager's build tag")
        self.assertNotRegex(view, r"value: [^\n]*win\.status\.kernel\b(?!\))")

    def test_unknown_is_said_in_words(self) -> None:
        qml = APP.read_text(encoding="utf-8")
        row = qml[qml.index("component FactRow"):qml.index("component FactCard")]
        self.assertIn(": win.unknownLabel", row)
        self.assertIn('Accessible.name: label + ": " + (value || win.unknownLabel)', row)


if __name__ == "__main__":
    unittest.main(verbosity=2)
