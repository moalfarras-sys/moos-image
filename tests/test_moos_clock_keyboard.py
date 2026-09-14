#!/usr/bin/env python3
"""Clock activation has one owner per route and exposes keyboard focus.

Execute the shipped handler JavaScript with Plasma's toggle contract modeled
explicitly, including dismissal between mouse press and release. These tests
do not prove Qt key delivery or rendered focus; native Plasma review is still
required for release acceptance.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOCK = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.nova.clock/contents/ui/main.qml"


def compact_source():
    source = CLOCK.read_text(encoding="utf-8")
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = "\n".join(line for line in source.splitlines()
                       if not line.lstrip().startswith("//"))
    return source.split("compactRepresentation: MouseArea {", 1)[1].split(
        "fullRepresentation:", 1)[0]


def handler(source, name):
    if name.startswith("Keys."):
        match = re.search(r"        " + re.escape(name)
                          + r": event => \{(.*?)^        \}",
                          source, re.MULTILINE | re.DOTALL)
    else:
        match = re.search(r"^        " + re.escape(name) + r": (.*)$",
                          source, re.MULTILINE)
    if match is None:
        raise AssertionError(f"Missing clock handler: {name}")
    return match.group(1)


@unittest.skipUnless(shutil.which("node"), "activation execution needs Node.js")
class ClockActivation(unittest.TestCase):
    def routes(self, cases, pointer_override=None):
        source = compact_source()
        activate = re.search(r"        function activate\(\) \{(.*?)^        \}",
                             source, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(activate, "native activation route is missing")
        bodies = {name: handler(source, name) for name in (
            "onPressed", "onClicked", "Accessible.onPressAction",
            "Keys.onReturnPressed", "Keys.onEnterPressed", "Keys.onSpacePressed")}
        if pointer_override is not None:
            bodies["onClicked"] = pointer_override
        runner = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = input.cases.map(c => {
    let expanded = c.expanded;
    let assignments = 0;
    let activations = 0;
    const root = { get expanded() { return expanded; },
        set expanded(value) { expanded = value; assignments++; } };
    const compact = {wasExpanded: false};
    const context = vm.createContext({root, compact,
        event: {isAutoRepeat: c.repeat || false, accepted: false},
        Plasmoid: {activated() {activations++; root.expanded = !root.expanded;}}});
    compact.activate = () => vm.runInContext(input.activate, context, {timeout: 1000});
    const run = name => vm.runInContext(input.bodies[name], context, {timeout: 1000});
    if (c.route === 'pointer') {
        run('onPressed');
        if (c.dismiss) expanded = false;  // compositor, not the handler
        run('onClicked');
    } else run(c.route);
    return {expanded, assignments, activations, accepted: context.event.accepted};
});
process.stdout.write(JSON.stringify(output));
"""
        result = subprocess.run(
            [shutil.which("node"), "-e", runner],
            input=json.dumps({"activate": activate.group(1), "bodies": bodies,
                              "cases": cases}),
            text=True, capture_output=True, check=True, timeout=15)
        return json.loads(result.stdout)

    def test_pointer_toggles_once_without_native_signal(self):
        for initial, result in zip((False, True), self.routes([
                {"route": "pointer", "expanded": state} for state in (False, True)])):
            self.assertEqual(result["expanded"], not initial)
            self.assertEqual(result["assignments"], 1)
            self.assertEqual(result["activations"], 0)

    def test_popup_dismissal_does_not_reopen_clock(self):
        result = self.routes([{"route": "pointer", "expanded": True,
                               "dismiss": True}])[0]
        self.assertFalse(result["expanded"])
        self.assertEqual(result["assignments"], 1)
        self.assertEqual(result["activations"], 0)

    def test_old_release_time_toggle_demonstrates_regression(self):
        result = self.routes([{"route": "pointer", "expanded": True,
                               "dismiss": True}],
                             "root.expanded = !root.expanded")[0]
        self.assertTrue(result["expanded"], "the old handler must reproduce reopening")

    def test_each_key_uses_native_activation_once_and_consumes_event(self):
        for route in ("Keys.onReturnPressed", "Keys.onEnterPressed", "Keys.onSpacePressed"):
            for initial in (False, True):
                with self.subTest(route=route, expanded=initial):
                    result = self.routes([{"route": route, "expanded": initial}])[0]
                    self.assertEqual(result, {"expanded": not initial, "assignments": 1,
                                              "activations": 1, "accepted": True})

    def test_held_activation_keys_cannot_oscillate_popup(self):
        for route in ("Keys.onReturnPressed", "Keys.onEnterPressed", "Keys.onSpacePressed"):
            for initial in (False, True):
                result = self.routes([{"route": route, "expanded": initial,
                                       "repeat": True}])[0]
                self.assertEqual(result, {"expanded": initial, "assignments": 0,
                                          "activations": 0, "accepted": True})

    def test_accessibility_uses_the_same_native_activation(self):
        for initial in (False, True):
            result = self.routes([{"route": "Accessible.onPressAction",
                                   "expanded": initial}])[0]
            self.assertEqual(result["expanded"], not initial)
            self.assertEqual(result["activations"], 1)
            self.assertEqual(result["assignments"], 1)


class ClockKeyboardWiring(unittest.TestCase):
    def test_native_activation_owner_is_on_plasmoid_item(self):
        source = CLOCK.read_text(encoding="utf-8")
        self.assertEqual(source.count("activationTogglesExpanded: true"), 1)
        self.assertNotIn("Plasmoid.activationTogglesExpanded", source)

    def test_compact_has_tab_focus_and_descriptive_button_semantics(self):
        source = compact_source()
        for required in ("activeFocusOnTab: true", "Accessible.role: Accessible.Button",
                         "Accessible.checked: root.expanded",
                         'Accessible.name: root.toolTipMainText + ", " + root.toolTipSubText'):
            self.assertIn(required, source)

    def test_focus_uses_shared_ring_inside_the_panel_surface(self):
        source = compact_source()
        ring = source.split("MoUI.FocusRing {", 1)[1].split("}", 1)[0]
        for required in ("anchors.fill: clockPlate", "anchors.margins: 0",
                         "visible: compact.activeFocus"):
            self.assertIn(required, ring)

    def test_press_feedback_obeys_shared_motion_gate(self):
        source = compact_source()
        self.assertIn("MoUI.SpringFeedback {", source)
        self.assertIn("scale: clockFeedback.value", source)
        self.assertIn("motionEnabled: root.motionEnabled", source)
        self.assertIn("targetScale: !root.motionEnabled ? 1", source)
        self.assertNotIn("Animation.Infinite", source)


if __name__ == "__main__":
    unittest.main()
