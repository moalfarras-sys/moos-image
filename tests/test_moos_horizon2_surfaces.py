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
SEARCH_VIEW = SHARE / "plasmoids/org.moos.search/contents/ui/SearchView.qml"
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
        cls.view = code(SEARCH_VIEW)

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
        self.assertIn("root.queryRevision === requestedRevision", self.qml,
                      "clearing and retyping identical text must invalidate a deferred Enter")
        self.assertIn("if (!root.expanded", self.qml,
                      "a deferred result must never launch after its popup closed")
        self.assertIn("onQueryingChanged: root.runQueued()", self.qml)

    def test_the_surface_is_a_popup_not_a_permanent_input_grab(self):
        self.assertIn("FocusScope {", self.view)
        self.assertIn("activationTogglesExpanded: true", self.qml)
        self.assertNotIn("AcceptingInputStatus", self.qml,
                         "holding panel input would steal keys from every window")
        self.assertIn("Keys.onEscapePressed", self.view)

    def test_mo_ai_hand_off_uses_a_declared_route_with_one_argv_element(self):
        self.assertIn('"moos://ai/ask/" + encodeURIComponent(question)', self.qml)
        self.assertIn("event.modifiers & Qt.ControlModifier", self.view)
        router = MOOS_OPEN.read_text(encoding="utf-8")
        self.assertRegex(router, r"(?m)^\s*ai/ask/\*\)")
        self.assertIn('gui moai --panel chat --ask "$query"', router,
                      "the question must reach Mo AI as one quoted argument, never evaluated")

    def test_empty_state_shows_real_destinations_and_isolated_key_hints(self):
        self.assertIn("shownItems: Kicker.RecentUsageModel.OnlyApps", self.qml)
        self.assertIn("recentApps.trigger(row", self.qml)
        for route in ("moos://app/settings", "moos://app/store", "moos://app/updater"):
            self.assertIn(route, self.view)
            self.assertRegex(MOOS_OPEN.read_text(encoding="utf-8"),
                             r"(?m)^\s*" + re.escape(route.removeprefix("moos://")) + r"\)")
        self.assertNotRegex(self.view, r"Enter للفتح",
                            "a mixed Arabic/Latin hint sentence is reordered by bidi")
        self.assertIn('{ keys: "Esc", ar: "إغلاق", en: "Close" }', self.view)
        self.assertIn('function bidi(value) { return "\\u2068" + value + "\\u2069"; }',
                      self.view)
        self.assertIn('surface.bidi("Mo AI:', self.view,
                      "the Arabic AI hand-off must isolate its Latin/query run")

    def test_motion_is_finite_and_gated(self):
        for source in (self.qml, self.view):
            self.assertIn("MoUI.SpringFeedback", source)
            self.assertNotIn("Animation.Infinite", source)
        self.assertIn("readonly property bool motionEnabled: Kirigami.Units.longDuration > 1",
                      self.qml)
        self.assertIn("root.motionEnabled", self.view)


class RemoteIsland(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qml = code(ISLAND)
        cls.control = code(ISLAND.with_name("MediaControl.qml"))

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
        width_block = self.qml.split("implicitWidth: root.active", 1)[1].split(
            "implicitHeight:", 1)[0]
        self.assertIn("readonly property real chipWidth: 72", self.qml)
        self.assertIn("root.remoteSettled ? chipWidth", self.qml)
        self.assertIn(": 1", width_block)
        self.assertIn('root.remoteMode === "paused"', self.qml)
        self.assertIn("root.remoteSessions > 1", self.qml)

    def test_remote_keeps_privacy_priority_but_popup_can_inspect_media(self):
        self.assertIn('property string detailContext: "remote"', self.qml)
        self.assertIn("readonly property bool multipleContexts:", self.qml)
        self.assertIn("readonly property bool showRemoteDetails:", self.qml)
        self.assertIn('root.detailContext = "remote"', self.qml)
        self.assertIn('root.detailContext = "media"', self.qml)

    def test_media_controls_are_stationary_native_targets(self):
        self.assertIn("Controls.AbstractButton", self.control)
        self.assertIn("property real slotSize: control.primary ? 52 : 40", self.control)
        self.assertIn("focusPolicy: Qt.StrongFocus", self.control)
        self.assertIn("Accessible.onPressAction", self.control)
        self.assertIn("Keys.onReturnPressed", self.control)
        self.assertIn("scale: feedback.value", self.control)
        self.assertNotIn("scale: control.revealProgress", self.control,
                         "revealing a control must not shrink its interactive target")

    def test_media_polling_stops_when_nobody_can_see_progress(self):
        timer = self.qml.split("id: positionSync", 1)[1].split("}", 1)[0]
        self.assertIn("root.expanded || root.compactHovered", timer)
        self.assertIn("!root.showRemoteDetails", timer)


class LocalizedHub(unittest.TestCase):
    # ClockCard.qml is a composition of two faces since the card gained a second
    # page; the text lives in the faces, so they are what this checks.
    CARDS = ("ClockFace.qml", "WeekStrip.qml", "SystemCard.qml", "WeatherCard.qml",
             "MetricRing.qml")

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
        for card in ("ClockFace.qml", "WeekStrip.qml", "SystemCard.qml",
                     "WeatherCard.qml"):
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


class HubControls(unittest.TestCase):
    """The owner could not hide or change MoOS Hub: it is painted by the wallpaper, so Plasma's
    widget handles never appear on it. Its controls live in the desktop right-click menu."""

    @classmethod
    def setUpClass(cls):
        cls.scene = code(HUB / "main.qml")
        cls.bento = code(HUB / "DashboardBento.qml")
        cls.page = code(HUB / "config.qml")
        cls.schema = (HUB.parent / "config/main.xml").read_text(encoding="utf-8")

    def test_every_control_is_a_real_configuration_key(self):
        for key in ("ShowDashboard", "HubClock", "HubWeather", "HubSystem"):
            self.assertIn(f'<entry name="{key}" type="Bool">', self.schema, key)
            self.assertIn(f"cfg_{key}", self.page, f"the wallpaper page must own {key} too")
        self.assertIn("root.configuration.writeConfig()", self.scene)

    def test_the_desktop_menu_offers_show_and_per_card_toggles(self):
        actions = self.scene.split("contextualActions: [", 1)[1].split("\n    ]\n", 1)[0]
        # Four checkable toggles (the hub and its three cards) plus one action per
        # card that turns it over — a command rather than a state, which is why it
        # is not checkable.
        self.assertEqual(actions.count("PlasmaCore.Action {"), 7)
        self.assertEqual(actions.count("checkable: true"), 4)
        for key in ("ShowDashboard", "HubClock", "HubWeather", "HubSystem"):
            self.assertIn(f'root.setHubKey("{key}"', actions)
        self.assertIn('MoUI.Locale.local("إظهار لوحة MoOS", "Show MoOS Hub")', actions)

    def test_every_card_has_a_second_face_and_the_menu_turns_each(self):
        """One rule for all three: the wallpaper takes no clicks, so the menu turns them."""
        for key in ("HubClockPage", "HubWeatherPage", "HubSystemPage"):
            self.assertIn(f'<entry name="{key}" type="Int">', self.schema, key)
        actions = self.scene.split("contextualActions: [", 1)[1].split("\n    ]\n", 1)[0]
        for key in ("HubClockPage", "HubWeatherPage", "HubSystemPage"):
            self.assertIn(f'root.setHubKey("{key}"', actions, key)
        # A card nobody can see must not offer a way to turn it.
        self.assertIn("visible: root.hubShown && root.hubWeather", actions)
        self.assertIn("visible: root.hubShown && root.hubSystem", actions)
        for page in ("clockPage: root.hubClockPage", "weatherPage: root.hubWeatherPage",
                     "systemPage: root.hubSystemPage"):
            self.assertIn(page, self.scene)

    def test_the_hourly_face_rides_the_forecast_the_card_already_asks_for(self):
        """No second service and no extra poll: one more parameter on one request."""
        self.assertIn("&hourly=temperature_2m,weather_code&forecast_hours=12", self.bento)
        hourly = code(HUB / "HourlyStrip.qml")
        self.assertNotIn("XMLHttpRequest", hourly, "the face fetches nothing itself")
        self.assertIn("required property var kindForCode", hourly,
                      "one weather code must not mean two pictures on one card")

    def test_the_device_face_gates_every_figure_on_its_own_sensor(self):
        """A machine that does not expose a sensor shows a dash, never a confident zero."""
        network = code(HUB / "NetworkFace.qml")
        for sensor in ("network/all/download", "network/all/upload", "disk/all/free"):
            self.assertIn(sensor, network)
        self.assertEqual(network.count("Sensors.Sensor.Ready"), 3,
                         "each figure is present-gated like the rings")

    def test_the_clock_card_has_two_faces_and_the_menu_turns_it(self):
        """A wallpaper cannot be clicked: the desktop containment takes the event.

        Measured on the station on 2026-09-18 — neither a click nor a wheel over the
        hub reached it, which is the same property that lets the hub live under the
        icons without ever covering anything. So the card is turned from the menu
        that already carries every other hub control, and the face is remembered in
        a real configuration key.
        """
        self.assertIn('<entry name="HubClockPage" type="Int">', self.schema)
        actions = self.scene.split("contextualActions: [", 1)[1].split("\n    ]\n", 1)[0]
        self.assertIn('root.setHubKey("HubClockPage"', actions)
        self.assertIn('MoUI.Locale.local("لوحة MoOS: أرني الأسبوع", "MoOS Hub: show the week")',
                      actions)
        self.assertIn("visible: root.hubShown && root.hubClock", actions,
                      "turning a card nobody can see is a dead menu entry")
        self.assertIn("clockPage: root.hubClockPage", self.scene)
        self.assertIn("page: root.clockPage", self.bento)

    def test_the_card_never_turns_itself_and_takes_no_input(self):
        """Two rules, both from where the hub lives.

        It is painted by the wallpaper, so no pointer event reaches it (the desktop
        containment takes them) — an input handler here would be dead code pretending
        to be a feature, and the dashboard's passivity is a shipped contract. And it
        never rotates on its own: a desktop that changes while nobody is looking is a
        distraction, and on a 4K wallpaper also a permanent repaint.
        """
        stack = code(HUB / "CardStack.qml")
        for forbidden in ("Timer {", "running: true", "SequentialAnimation", "loops:",
                          "MouseArea", "HoverHandler", "TapHandler", "WheelHandler",
                          "Keys."):
            self.assertNotIn(forbidden, stack,
                             "the stack neither turns itself nor takes input")
        self.assertIn("property int page: 0", stack,
                      "the face is chosen by the wallpaper's configuration")

    def test_the_week_face_is_drawn_from_the_clock_it_shares(self):
        week = code(HUB / "WeekStrip.qml")
        self.assertIn("required property date now", week)
        for forbidden in ("XMLHttpRequest", "Timer {", "Qt.openUrlExternally"):
            self.assertNotIn(forbidden, week,
                             "the week face fetches nothing and starts nothing")
        self.assertIn("Qt.locale().firstDayOfWeek", week,
                      "the week starts where the owner's own locale starts")

    def test_no_card_selection_leaves_an_invisible_running_hub(self):
        self.assertIn("readonly property bool hubAnyCard:", self.scene)
        self.assertIn("&& root.hubAnyCard", self.scene)
        self.assertIn("readonly property bool dashboardRequested: root.hubShown", self.scene)
        self.assertIn('if (key === "ShowDashboard" && value && !root.hubAnyCard)', self.scene)

    def test_hidden_cards_take_no_width_and_keep_no_divider(self):
        for card, flag in (("ClockCard {", "root.showClock"), ("WeatherCard {", "root.showWeather"),
                           ("SystemCard {", "root.showSystem")):
            # Each card now also carries its face and, for weather, the data that
            # face needs, so the visibility rule sits further down its block.
            block = self.bento.split(card, 1)[1][:420]
            self.assertIn(f"visible: {flag}", block, card)
        self.assertIn("visible: root.showClock && (root.showWeather || root.showSystem)", self.bento)
        self.assertIn("visible: root.showWeather && root.showSystem", self.bento)
        self.assertIn("visibleCards === 3", self.bento,
                      "with every card shown the designed width must not change")

    def test_review_shadows_of_the_scene_and_search_are_retired_on_update(self):
        apply = (ROOT / "system_files/usr/bin/moos-apply-theme").read_text(encoding="utf-8")
        self.assertIn("org.moos.island org.moos.search; do", apply)
        self.assertIn('rm -rf "${local_wallpapers:?}/org.moos.ui2.wallpaper"', apply)


if __name__ == "__main__":
    suite = unittest.TestSuite()
    for case in (MoOSSearch, RemoteIsland, LocalizedHub, HubControls):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
