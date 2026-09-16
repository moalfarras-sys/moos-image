#!/usr/bin/env python3
"""Gate: Horizon 2 — MoOS Search, the Remote island chip and the localized desktop hub.

WHY THIS EXISTS

Each property below was measured on the station's live Arabic 4K session before it became a
rule, and each is the kind of regression a static review misses:

  * MoOS Search is ONE surface. The old bar field handed its query to KRunner at the top of the
    screen. The surface must run results through the model that produced them, refuse to run a
    stale row while the runners are still answering, and hand a question to Mo AI only through
    the declared `moos://ai/ask/` route, which passes it as a single argv element.
  * The Remote island announces and then settles. A connected phone used to hold a ~230 px
    sentence on the bar for hours. The announcement timer must be one-shot, and the handler must
    read its inputs directly: reading the derived `remotePresent` binding inside a change handler
    saw the old value and cancelled the announcement at the moment it should have started.
  * The desktop hub speaks the session language. Its cards mixed English eyebrows with Arabic
    words; temperatures inside Arabic labels rendered as "°18" until they were bidi-isolated.
"""

from pathlib import Path
import re
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files/usr/share/plasma"
SEARCH = SHARE / "plasmoids/org.moos.search/contents/ui/main.qml"
ISLAND = SHARE / "plasmoids/org.moos.island/contents/ui/main.qml"
HUB = SHARE / "wallpapers/org.moos.ui2.wallpaper/contents/ui"
MOOS_OPEN = ROOT / "system_files/usr/bin/moos-open"


def code(path: Path) -> str:
    """QML without // comment lines, so prose cannot satisfy or trip a rule."""
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("//"))


class MoOSSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qml = code(SEARCH)

    def test_results_come_from_plasma_search_and_run_through_their_own_model(self):
        self.assertIn("Milou.ResultsModel", self.qml)
        self.assertIn("results.run(results.index(row, 0))", self.qml,
                      "a result must be executed by the model that produced it")
        self.assertNotIn("gui krunner", self.qml)
        self.assertNotIn('"moos://search/', self.qml,
                         "the bar no longer hands its query to a second, detached window")

    def test_enter_never_runs_a_row_from_an_older_query(self):
        self.assertIn("if (results.querying || results.rowCount() < 1 || row < 0)", self.qml)
        self.assertIn("root.queuedRun === root.query", self.qml)
        self.assertIn("onQueryingChanged: root.runQueued()", self.qml)

    def test_the_surface_is_a_popup_not_a_permanent_input_grab(self):
        self.assertIn("fullRepresentation: FocusScope", self.qml)
        self.assertIn("activationTogglesExpanded: true", self.qml)
        self.assertNotIn("AcceptingInputStatus", self.qml,
                         "holding panel input would steal keys from every window")
        self.assertIn("Keys.onEscapePressed", self.qml)

    def test_mo_ai_hand_off_uses_a_declared_route_with_one_argv_element(self):
        self.assertIn('"moos://ai/ask/" + encodeURIComponent(question)', self.qml)
        self.assertIn("event.modifiers & Qt.ControlModifier", self.qml)
        router = MOOS_OPEN.read_text(encoding="utf-8")
        self.assertRegex(router, r"(?m)^\s*ai/ask/\*\)")
        self.assertIn('gui moai --panel chat --ask "$query"', router,
                      "the question must reach Mo AI as one quoted argument, never evaluated")

    def test_empty_state_shows_real_destinations_and_isolated_key_hints(self):
        self.assertIn("shownItems: Kicker.RecentUsageModel.OnlyApps", self.qml)
        self.assertIn("recentApps.trigger(row", self.qml)
        for route in ("moos://app/settings", "moos://app/store", "moos://app/updater"):
            self.assertIn(route, self.qml)
            self.assertRegex(MOOS_OPEN.read_text(encoding="utf-8"),
                             r"(?m)^\s*" + re.escape(route.removeprefix("moos://")) + r"\)")
        self.assertNotRegex(self.qml, r"Enter للفتح",
                            "a mixed Arabic/Latin hint sentence is reordered by bidi")
        self.assertIn('{ keys: "Esc", ar: "إغلاق", en: "Close" }', self.qml)

    def test_motion_is_finite_and_gated(self):
        self.assertIn("MoUI.SpringFeedback", self.qml)
        self.assertNotIn("Animation.Infinite", self.qml)
        self.assertIn("readonly property bool motionEnabled: Kirigami.Units.longDuration > 1",
                      self.qml)


class RemoteIsland(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qml = code(ISLAND)

    def test_announcement_is_one_shot_and_settles(self):
        timer = self.qml.split("id: remoteAnnounce", 1)[1].split("}", 1)[0]
        self.assertIn("repeat: false", timer)
        self.assertIn("onTriggered: root.remoteAnnouncing = false", timer)
        self.assertIn("readonly property bool remoteSettled: root.remotePresent && !root.remoteAnnouncing",
                      self.qml)
        self.assertIn("&& !root.compactHovered && !root.expanded", self.qml)

    def test_the_handler_reads_inputs_not_the_stale_binding(self):
        handler = self.qml.split("function announceRemote()", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn("root.remoteSessions > 0", handler)
        self.assertNotIn("root.remotePresent", handler,
                         "the derived binding can still hold the previous value here")

    def test_settled_chip_keeps_live_state_and_the_idle_pixel(self):
        self.assertIn("readonly property real chipWidth: 72", self.qml)
        self.assertIn("root.remoteSettled ? chipWidth", self.qml)
        self.assertIn(": 1\n", self.qml.split("implicitWidth: root.active", 1)[1][:200])
        self.assertIn('root.remoteMode === "paused"', self.qml)
        self.assertIn("root.remoteSessions > 1", self.qml)


class LocalizedHub(unittest.TestCase):
    CARDS = ("ClockCard.qml", "SystemCard.qml", "WeatherCard.qml", "MetricRing.qml")

    def test_every_card_uses_the_locale_authority(self):
        for card in self.CARDS:
            source = code(HUB / card)
            self.assertIn("import org.moos.ui as MoUI", source, card)
            self.assertIn("MoUI.Locale", source, card)

    def test_no_bare_english_eyebrow_is_left(self):
        for card in self.CARDS:
            source = code(HUB / card)
            for label in ('"LOCAL TIME"', '"SYSTEM"', '"HEALTHY"', '"FEELS "', '"HIGH  "',
                          '"LOW  "', '"LOCAL FORECAST"', 'label: "CPU"'):
                for line in source.splitlines():
                    if label in line:
                        self.assertIn("local(", line,
                                      f"{card}: {label} must come through MoUI.Locale")

    def test_arabic_is_never_letter_spaced_and_temperatures_are_isolated(self):
        weather = code(HUB / "WeatherCard.qml")
        self.assertIn('function degrees(value) { return "\\u2066" + value + "°\\u2069" }', weather)
        self.assertEqual(weather.count("weatherCard.degrees("), 3)
        # Only localized labels can be Arabic; the "MoOS" wordmark and palette names are Latin
        # brand strings and keep their tracking.
        checked = 0
        for card in ("ClockCard.qml", "SystemCard.qml", "WeatherCard.qml"):
            for block in code(HUB / card).split("Text {")[1:]:
                block = block.split("\n            }", 1)[0]
                if "local(" not in block or "font.letterSpacing" not in block:
                    continue
                spacing = re.search(r"font\.letterSpacing:\s*([^\n]+)", block).group(1)
                self.assertIn("rtl ? 0", spacing, f"{card}: Arabic must not be letter-spaced")
                checked += 1
        self.assertGreaterEqual(checked, 4, "expected the four localized, letter-spaced eyebrows to be checked")

    def test_condition_names_follow_the_session(self):
        bento = code(HUB / "DashboardBento.qml")
        self.assertNotIn("conditionNameArabic", bento)
        self.assertIn('L.local("أمطار", "Rain")', bento)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    for case in (MoOSSearch, RemoteIsland, LocalizedHub):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
