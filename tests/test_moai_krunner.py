#!/usr/bin/env python3
"""Gate: Mo AI in Plasma's search bar suggests fixed actions and runs nothing else.

WHY THIS EXISTS
MoOS is built on Plasma, and the owner wants Plasma to feel like MoOS's own,
clever shell. moai-krunner answers KRunner queries such as "volume 40",
"السطوع 70" or "dark mode" with a result, and hands questions to Mo AI. Because
KRunner sends it whatever is typed and later hands the chosen id back as a
string, this gate proves:

* only the closed grammar produces control results, with exact moos:// routes;
* out-of-range values and shell syntax produce no control result;
* a chosen id is re-validated — a tampered id runs nothing;
* a question reaches Mo AI as one argv element through `moai --ask`;
* the plugin and D-Bus activation files point at the same service.
"""
import os
import re
import runpy
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "system_files/usr/libexec/moai-krunner"


def load(lang="en_US.UTF-8"):
    with mock.patch.dict(os.environ, {"LANG": lang, "LC_ALL": "", "LC_MESSAGES": ""}):
        return runpy.run_path(str(RUNNER), run_name="moai_krunner_test")


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.runner = load()

    def routes(self, query):
        return [item[0] for item in self.runner["match"](query) if item[0].startswith("route:")]

    def test_control_phrases_in_both_languages(self):
        expected = {
            "volume 40": "route:control/volume/40",
            "Volume to 35%": "route:control/volume/35",
            "الصوت ٤٠": "route:control/volume/40",
            "الصوت إلى 25٪": "route:control/volume/25",
            "اخفض الصوت": "route:control/volume/down",
            "mute": "route:control/mute",
            "brightness 70": "route:control/brightness/70",
            "السطوع 60": "route:control/brightness/60",
            "night light": "route:control/night-light/on",
            "الضوء الليلي اطفئ": "route:control/night-light/off",
            "لقطة شاشة": "route:control/screenshot",
            "dark mode": "route:theme/dark",
            "الوضع الفاتح": "route:theme/light",
            "bluetooth off": "route:control/bluetooth/off",
            "wifi off": "route:control/wifi/off",
        }
        for query, route in expected.items():
            with self.subTest(query=query):
                self.assertEqual(self.routes(query), [route])

    def test_desktop_actions_in_both_languages(self):
        """SPEC D4: every new desktop verb has an English AND an Arabic phrase."""
        expected = {
            "do not disturb": "route:control/dnd/on",
            "dnd off": "route:control/dnd/off",
            "عدم الإزعاج": "route:control/dnd/on",
            "وضع عدم الازعاج اطفئ": "route:control/dnd/off",
            "mute the microphone": "route:control/mic/mute",
            "اكتم المايك": "route:control/mic/mute",
            "unmute mic": "route:control/mic/unmute",
            "إلغاء كتم الميكروفون": "route:control/mic/unmute",
            "switch keyboard layout": "route:control/keyboard-layout/next",
            "بدّل لغة الكيبورد": "route:control/keyboard-layout/next",
            "show all windows": "route:control/window/overview",
            "عرض النوافذ": "route:control/window/overview",
            "desktop grid": "route:control/window/grid",
            "شبكة أسطح المكتب": "route:control/window/grid",
            "show desktop": "route:control/window/show-desktop",
            "أظهر سطح المكتب": "route:control/window/show-desktop",
            "arrange windows": "route:control/arrange/halves",
            "arrange windows thirds": "route:control/arrange/thirds",
            "tile center": "route:control/arrange/centre",
            "رتب النوافذ أرباع": "route:control/arrange/quarters",
            "رتّب النوافذ رئيسية": "route:control/arrange/main",
            "next desktop": "route:control/desktop/next",
            "سطح المكتب السابق": "route:control/desktop/previous",
            "motion still": "route:control/motion/still",
            "حركة الخلفية حية": "route:control/motion/alive",
            "glass clarity solid": "route:control/clarity/solid",
            "وضوح الزجاج شفاف": "route:control/clarity/clear",
            "battery saver": "route:control/power-profile/power-saver",
            "وضع توفير الطاقة": "route:control/power-profile/power-saver",
            "performance mode": "route:control/power-profile/performance",
            "وضع الأداء": "route:control/power-profile/performance",
            "balanced power": "route:control/power-profile/balanced",
            "الوضع المتوازن": "route:control/power-profile/balanced",
        }
        for query, route in expected.items():
            with self.subTest(query=query):
                self.assertEqual(self.routes(query), [route])

    def test_settings_pages_come_from_the_one_registry(self):
        expected = {
            "display settings": "route:settings/display",
            "open window rules settings": "route:settings/window-rules",
            "settings shortcuts": "route:settings/shortcuts",
            "إعدادات الشاشة": "route:settings/display",
            "اعدادات الاختصارات": "route:settings/shortcuts",
            "إعدادات Mo AI": "route:settings/assistant",
            "إعدادات شاشة الدخول": "route:settings/login-screen",
        }
        for query, route in expected.items():
            with self.subTest(query=query):
                self.assertEqual(self.routes(query), [route])
        # A registry token NOT offered to Mo AI never becomes a result.
        self.assertEqual(self.routes("usb devices settings"), [])

    def test_every_produced_route_is_a_literal_moos_open_arm(self):
        """A result that opens a route the router does not have is a dead button."""
        router = (ROOT / "system_files/usr/bin/moos-open").read_text(encoding="utf-8")
        labels = set()
        for match in re.finditer(r"^\s{4}([a-z0-9/*|.-]+)\)", router, re.M):
            labels.update(label for label in match.group(1).split("|") if label != "*")
        literal = {label for label in labels if "*" not in label}
        queries = ["do not disturb", "dnd off", "mute mic", "unmute mic", "next layout",
                   "overview", "grid view", "show desktop", "next desktop", "previous desktop",
                   "motion still", "motion gentle", "motion alive", "clarity clear",
                   "clarity balanced", "clarity solid", "power saver", "performance mode",
                   "balanced power", "dark mode", "light mode", "mute", "unmute",
                   "screenshot", "night light", "night light off", "bluetooth on",
                   "bluetooth off", "wifi on", "wifi off", "volume up", "brightness down"]
        queries += [f"arrange {kind}" for kind in ("halves", "thirds", "quarters", "main", "centre")]
        queries += [f"{label['en'].lower()} settings"
                    for _token, label in self.runner["SETTINGS_PAGES"]]
        for query in queries:
            for route in self.routes(query):
                with self.subTest(query=query, route=route):
                    self.assertIn(route[len("route:"):], literal)

    def test_invalid_or_hostile_queries_give_no_control_result(self):
        for query in ("volume 150", "brightness 2", "volume 40; reboot", "volume $(id)",
                      "theme ../../etc", "wifi toggle", "volume", "firefox", "x"):
            with self.subTest(query=query):
                self.assertEqual(self.routes(query), [])

    def test_questions_are_offered_to_mo_ai(self):
        explicit = [item for item in self.runner["match"]("ask: why is my laptop slow") if item[0].startswith("ask:")]
        self.assertEqual(len(explicit), 1)
        self.assertEqual(explicit[0][3], 100)
        self.assertEqual(self.runner["decode"](explicit[0][0][4:]), "why is my laptop slow")
        question = [item for item in self.runner["match"]("هل يوجد تحديث للنظام؟") if item[0].startswith("ask:")]
        self.assertEqual(len(question), 1)
        self.assertEqual(question[0][3], 30)
        self.assertEqual(self.runner["match"]("firefox"), [])

    def test_arabic_session_gets_arabic_labels(self):
        # The runner reads the session language per query (it is a long-lived
        # service), so the language must be set while matching, not while loading.
        with mock.patch.dict(os.environ, {"LANG": "ar_SA.UTF-8", "LC_ALL": "", "LC_MESSAGES": ""}):
            label = self.runner["match"]("volume 40")[0][1]
        self.assertEqual(label, "الصوت 40%")


class RunTests(unittest.TestCase):
    def setUp(self):
        self.runner = load()
        self.opened, self.asked = [], []
        self.runner["open_route"].__globals__["open_route"] = self.opened.append
        self.runner["ask"].__globals__["ask"] = self.asked.append

    def test_valid_ids_open_exact_routes(self):
        self.assertTrue(self.runner["run"]("route:control/volume/40"))
        self.assertTrue(self.runner["run"]("route:theme/dark"))
        self.assertEqual(self.opened, ["control/volume/40", "theme/dark"])

    def test_tampered_ids_run_nothing(self):
        for match_id in ("route:control/volume/40;reboot", "route:control/volume/400",
                         "route:../../session/power", "route:do/update", "shell:rm -rf ~",
                         "route:control/window/close", "route:control/arrange/all",
                         "route:settings/usb", "route:settings/kcm_kscreen",
                         "route:settings/display;reboot", "route:control/dnd/toggle",
                         "ask:%%%not-base64", "ask:"):
            with self.subTest(match_id=match_id):
                self.assertFalse(self.runner["run"](match_id))
        self.assertEqual(self.opened, [])
        self.assertEqual(self.asked, [])

    def test_question_is_passed_as_one_argument(self):
        question = 'why? "$(reboot)" & rm -rf ~'
        token = self.runner["encode"](question)
        self.assertTrue(self.runner["run"]("ask:" + token))
        self.assertEqual(self.asked, [question])


class IconTests(unittest.TestCase):
    def test_every_result_icon_is_a_shipped_moos_asset(self):
        # Live KRunner showed a missing-icon glyph for two results whose names
        # ("moos-theme-dark", "moai") exist nowhere. Only shipped assets now.
        runner = load()
        icons = {rule[4] for rule in runner["RULES"]} | {runner["ASK_ICON"]}
        plugin = (ROOT / "system_files/usr/share/krunner/dbusplugins/org.moos.moai.desktop").read_text()
        icons.add(plugin.split("Icon=", 1)[1].split("\n", 1)[0])
        base = ROOT / "system_files/usr/share/icons/hicolor/scalable"
        missing = sorted(name for name in icons
                         if not (base / "actions" / f"{name}.svg").is_file()
                         and not (base / "apps" / f"{name}.svg").is_file())
        self.assertEqual(missing, [])
        for query in ("volume 40", "mute", "dark mode", "ask: hello there"):
            with self.subTest(query=query):
                for item in runner["match"](query):
                    self.assertIn(item[2], icons)


class WiringTests(unittest.TestCase):
    def test_plugin_activation_and_mo_ai_agree(self):
        plugin = (ROOT / "system_files/usr/share/krunner/dbusplugins/org.moos.moai.desktop").read_text()
        activation = (ROOT / "system_files/usr/share/dbus-1/services/org.moos.MoAIRunner.service").read_text()
        for needle in ("X-Plasma-API=DBus", "X-Plasma-DBusRunner-Service=org.moos.MoAIRunner",
                       "X-Plasma-DBusRunner-Path=/runner", "X-KDE-ServiceTypes=Plasma/Runner"):
            self.assertIn(needle, plugin)
        self.assertIn("Name=org.moos.MoAIRunner", activation)
        self.assertIn("Exec=/usr/libexec/moai-krunner", activation)
        self.assertTrue(os.access(RUNNER, os.X_OK))
        source = RUNNER.read_text()
        self.assertIn('["moai", "--panel", "chat", "--ask", question]', source)
        self.assertNotIn("shell=True", source)
        qml = (ROOT / "system_files/usr/share/moos/apps/moai/main.qml").read_text()
        self.assertIn('const askIndex = argv.indexOf("--ask")', qml)


if __name__ == "__main__":
    unittest.main(verbosity=2)
