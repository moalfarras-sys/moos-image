#!/usr/bin/env python3
"""The MoOS Launcher must be operable with the keyboard alone.

Before THEME_REV 53 the full Launcher surface (`org.moos.brand`'s
`LauncherView.qml`) had a keyboard dead zone: the sidebar pages carried an
`activeFocus` edge in their background but no key handlers and no place in the
tab chain, and there was no route from the search field into the content of the
Home / Applications / Places / Customize pages — only the search-results list
was wired. A pointerless user could open the launcher, type a query and run a
result, and do nothing else.

This is a source gate (the CI runner has no Qt, like `test_moos_motion_gate`).
It asserts the wiring is present, not that a rendered widget moves focus; the
live proof is a `plasmawindowed org.moos.brand` session driven with Tab/arrow
keys. To confirm it bites, revert any single hunk of the THEME_REV 53 change to
`LauncherView.qml` and re-run — one assertion below turns red for each.
"""

import re
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


class LauncherKeyboardNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.src = qml_code(LAUNCHER.read_text(encoding="utf-8"))

    # ── the single owner of "enter the content the user is looking at" ──────
    def test_focus_active_page_content_helper_exists_and_covers_every_page(self) -> None:
        self.assertIn("function focusActivePageContent()", self.src)
        helper = self.src.split("function focusActivePageContent()", 1)[1]
        helper = helper.split("function navForPage", 1)[0]
        # searching -> results; otherwise a real target for each of the 4 pages.
        self.assertIn("view.searching", helper)
        self.assertIn("searchResults.forceActiveFocus()", helper)
        for target in (
            "favoritesGrid.forceActiveFocus()",
            "homeExploreButton.forceActiveFocus()",
            "applicationsGrid.forceActiveFocus()",
            "placesList.forceActiveFocus()",
            "customizeArrangeButton.forceActiveFocus()",
        ):
            self.assertIn(target, helper, target)
        for page in ("case 0:", "case 1:", "case 2:", "case 3:"):
            self.assertIn(page, helper, page)

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
