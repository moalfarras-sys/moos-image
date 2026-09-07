#!/usr/bin/env python3
"""The MoOS Launcher must be operable with the keyboard alone.

Before THEME_REV 53 the full Launcher surface (`org.moos.brand`'s
`LauncherView.qml`) had a keyboard dead zone: the sidebar pages carried an
`activeFocus` edge in their background but no key handlers and no place in the
tab chain, and there was no route from the search field into the content of the
Home / Applications / Places / Customize pages — only the search-results list
was wired. A pointerless user could open the launcher, type a query and run a
result, and do nothing else.

The routing tests execute the actual QML JavaScript function in Node with
mocked focus targets. The remaining source checks assert keyboard wiring.
Neither proves Qt focus delivery, model normalization or rendered feedback;
that still requires an isolated Plasma session driven with Tab/arrow keys.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / (
    "system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
)


def qml_code(text: str) -> str:
    """Drop comments so a prose sentence cannot satisfy a wiring assertion."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(
        line
        for line in without_blocks.splitlines()
        if not line.lstrip().startswith("//")
    )


def focus_function(source: str) -> str:
    """Extract the root function, stopping at its own four-space closing brace."""
    match = re.search(
        r"^    function focusActivePageContent\(\) \{.*?^    \}",
        source, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError("launcher focus-routing function is missing")
    return match.group(0)


@unittest.skipUnless(shutil.which("node"), "focus-routing execution needs Node.js")
class LauncherFocusRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.function = focus_function(LAUNCHER.read_text(encoding="utf-8"))

    def routes(self, cases, function=None):
        # Only the targets and input models are mocked. The branch/selection
        # logic below comes verbatim from the shipped QML, not a second router.
        runner = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const names = ['searchResults', 'favoritesGrid', 'applicationsGrid',
               'placesList', 'homeExploreButton', 'customizeArrangeButton'];
const results = input.cases.map(c => {
    const focused = [];
    const context = { view: {
        searching: c.searching || false,
        launcher: { activePage: c.page },
        favoritesModel: { count: c.favoritesCount ?? 4 }
    }};
    for (const name of names) {
        context[name] = {
            count: c.counts?.[name] ?? 4,
            currentIndex: c.indices?.[name] ?? -1,
            forceActiveFocus() {
                focused.push({target: name, index: this.currentIndex});
            }
        };
    }
    vm.runInNewContext(input.function + '\nfocusActivePageContent();',
                       context, {timeout: 1000});
    return {focused, indices: Object.fromEntries(
        names.map(name => [name, context[name].currentIndex]))};
});
process.stdout.write(JSON.stringify(results));
"""
        result = subprocess.run(
            [shutil.which("node"), "-e", runner],
            input=json.dumps({"function": function or self.function, "cases": cases}),
            capture_output=True, text=True, timeout=15, check=True)
        return json.loads(result.stdout)

    def test_each_page_focuses_its_own_content_and_selects_first_row(self) -> None:
        targets = ("favoritesGrid", "applicationsGrid", "placesList",
                   "customizeArrangeButton")
        for page, (target, result) in enumerate(zip(
                targets, self.routes([{"page": p} for p in range(4)]))):
            with self.subTest(page=page):
                index = -1 if page == 3 else 0
                self.assertEqual(result["focused"], [{"target": target, "index": index}])
                self.assertTrue(all(value == -1 for name, value in result["indices"].items()
                                    if name != target), "unfocused pages must retain selection")

    def test_reentering_content_preserves_existing_selection(self) -> None:
        for page, target in enumerate(("favoritesGrid", "applicationsGrid", "placesList")):
            with self.subTest(page=page):
                result = self.routes([{"page": page, "indices": {target: 2}}])[0]
                self.assertEqual(result["focused"], [{"target": target, "index": 2}])

    def test_search_results_take_precedence_over_every_page(self) -> None:
        for index in (-1, 2):
            cases = [{"page": page, "searching": True,
                      "indices": {"searchResults": index}} for page in range(4)]
            for page, result in enumerate(self.routes(cases)):
                with self.subTest(page=page, index=index):
                    self.assertEqual(result["focused"], [
                        {"target": "searchResults", "index": max(0, index)}])

    def test_empty_search_does_not_focus_hidden_page_content(self) -> None:
        cases = [{"page": page, "searching": True,
                  "counts": {"searchResults": 0}} for page in range(4)]
        for page, result in enumerate(self.routes(cases)):
            with self.subTest(page=page):
                self.assertEqual(result["focused"], [])
                self.assertTrue(all(value == -1 for value in result["indices"].values()))

    def test_empty_page_models_use_their_declared_focus_fallback(self) -> None:
        cases = [
            {"page": 0, "favoritesCount": 0, "counts": {"favoritesGrid": 0}},
            {"page": 1, "counts": {"applicationsGrid": 0}},
            {"page": 2, "counts": {"placesList": 0}},
            {"page": 3, "favoritesCount": 0},
        ]
        results = self.routes(cases)
        self.assertEqual(results[0]["focused"], [{"target": "homeExploreButton", "index": -1}])
        # An empty Applications page still owns its grid focus scope; the QML
        # runtime, not these mocks, normalizes currentIndex against its model.
        self.assertEqual([x["target"] for x in results[1]["focused"]], ["applicationsGrid"])
        self.assertEqual(results[2]["focused"], [])
        self.assertEqual(results[2]["indices"]["placesList"], -1)
        self.assertEqual(results[3]["focused"], [{"target": "customizeArrangeButton", "index": -1}])


class LauncherKeyboardNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = qml_code(LAUNCHER.read_text(encoding="utf-8"))

    def test_search_field_down_key_enters_the_active_page(self) -> None:
        down = self.src.split("Keys.onDownPressed:", 1)[1].split("}", 1)[0]
        self.assertIn("view.focusActivePageContent()", down)

    # ── the sidebar is a real, ring-navigable tab strip ────────────────────
    def test_navbutton_takes_focus_and_activates_from_the_keyboard(self) -> None:
        nav = self.src.split("component NavButton:", 1)[1].split("component AppTile:", 1)[0]
        self.assertIn("activeFocusOnTab: true", nav)
        for key in ("Keys.onReturnPressed", "Keys.onEnterPressed", "Keys.onSpacePressed"):
            self.assertIn(key, nav, key)
        self.assertIn("nav.activate()", nav)
        # Up/Down walk the ring; Left/Right step into the page content.
        self.assertIn("nav.navUp.forceActiveFocus()", nav)
        self.assertIn("nav.navDown.forceActiveFocus()", nav)
        self.assertEqual(nav.count("view.focusActivePageContent()"), 2)

    def test_the_four_sidebar_pages_form_a_wrapping_ring(self) -> None:
        for wiring in (
            ("id: navHome", "navUp: navCustomize", "navDown: navApps"),
            ("id: navApps", "navUp: navHome", "navDown: navPlaces"),
            ("id: navPlaces", "navUp: navApps", "navDown: navCustomize"),
            ("id: navCustomize", "navUp: navPlaces", "navDown: navHome"),
        ):
            block = self.src.split(wiring[0], 1)[1][:280]
            self.assertIn(wiring[1], block, wiring)
            self.assertIn(wiring[2], block, wiring)

    # ── grids and lists take focus and hand it back to the search field ────
    def test_both_app_grids_route_focus(self) -> None:
        for grid, backtab in (("id: favoritesGrid", "navHome"),
                              ("id: applicationsGrid", "navApps")):
            block = self.src.split(grid, 1)[1].split("delegate: AppTile", 1)[0]
            self.assertIn("activeFocusOnTab: true", block, grid)
            self.assertIn(f"KeyNavigation.backtab: {backtab}", block, grid)
            # Top row Up leaves for the search field; deeper rows just move up.
            up = block.split("Keys.onUpPressed:", 1)[1].split("QQC2.ScrollBar", 1)[0]
            self.assertIn("currentIndex < columns", up)
            self.assertIn("view.focusSearch()", up)
            self.assertIn("moveCurrentIndexUp()", up)

    def test_places_list_is_keyboard_driven(self) -> None:
        block = self.src.split("id: placesList", 1)[1].split("delegate: PlaceRow", 1)[0]
        self.assertIn("activeFocusOnTab: true", block)
        self.assertIn("KeyNavigation.backtab: navPlaces", block)
        self.assertIn("view.focusSearch()", block)
        self.assertIn("view.launcher.triggerEntry(view.placesModel, currentIndex)", block)
        # The keyboard selection has to be visible on the row it lands on.
        place_bg = self.src.split("component PlaceRow:", 1)[1].split("component SearchResultRow:", 1)[0]
        self.assertIn("place.ListView.isCurrentItem", place_bg)

    def test_search_results_shift_tab_returns_to_the_field(self) -> None:
        block = self.src.split("id: searchResults", 1)[1][:600]
        self.assertIn("KeyNavigation.backtab: searchInput", block)


if __name__ == "__main__":
    unittest.main()
