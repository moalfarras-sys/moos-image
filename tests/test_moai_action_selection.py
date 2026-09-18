#!/usr/bin/env python3
"""P3.3's gate: the case set is real, and the runner scores it honestly.

The MEASUREMENT needs a cloud brain and money-free quota, so it cannot run in CI. What
CI can prove is everything around it, and those are the parts that quietly rot:

  * every tool name in the case set exists in the schema the model is actually sent —
    a case expecting a tool MoOS does not ship measures nothing and always misses;
  * both languages are present for every case, because a rate measured in one language
    is not the number P3.3 asks for;
  * the runner counts a wrong tool, an unrelated tool and a refusal-to-call as misses,
    and does not execute anything;
  * the threshold is 95% and the runner's exit code follows it.
"""
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_ISOLATED = tempfile.TemporaryDirectory()
os.environ["XDG_STATE_HOME"] = str(Path(_ISOLATED.name) / "state")

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "system_files/usr/share/moos/moai-action-cases.json"


def load(name: str, path: str):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


schemas = load("moai_tool_schemas", "system_files/usr/lib/moai/moai_tool_schemas.py")
runner = load("moai_measure_actions", "system_files/usr/bin/moai-measure-actions")
DOCUMENT = json.loads(CASES.read_text(encoding="utf-8"))
SHIPPED = {tool["function"]["name"] for tool in schemas.get_schemas_for_model()}


class TheCaseSet(unittest.TestCase):
    def test_every_expected_tool_is_one_mo_ai_actually_offers(self):
        for case in DOCUMENT["cases"]:
            for field in ("accept", "confused_with"):
                for name in case.get(field) or []:
                    self.assertIn(name, SHIPPED,
                                  f"{case['id']}.{field} names {name!r}, which MoOS does not ship")
            self.assertTrue(case["accept"], f"{case['id']} accepts no tool")

    def test_each_case_is_one_instruction_in_both_languages(self):
        seen = set()
        for case in DOCUMENT["cases"]:
            self.assertNotIn(case["id"], seen, f"duplicate case id {case['id']!r}")
            seen.add(case["id"])
            for language in ("ar", "en"):
                self.assertTrue(case[language].strip(), f"{case['id']}.{language} is empty")
            # An Arabic case that is not Arabic measures English twice.
            self.assertRegex(case["ar"], r"[؀-ۿ]", f"{case['id']}.ar is not Arabic")
            self.assertNotRegex(case["en"], r"[؀-ۿ]", f"{case['id']}.en contains Arabic")
            self.assertNotIn(case["ar"], case["en"])
        self.assertGreaterEqual(len(DOCUMENT["cases"]), 30,
                                "a set this small cannot distinguish 95% from luck")

    def test_the_set_covers_more_than_one_family_of_tool(self):
        """Forty inspection cases would measure one skill and call it the whole thing."""
        accepted = {name for case in DOCUMENT["cases"] for name in case["accept"]}
        families = {
            "inspect": {"list_failed_units", "unit_status", "read_journal", "top_processes",
                        "memory_status", "disk_status", "network_status", "list_installed_apps",
                        "os_state", "read_moos_log"},
            "control": {"set_volume", "set_mute", "set_brightness", "toggle_night_light",
                        "toggle_wifi", "toggle_bluetooth", "set_theme_mode", "take_screenshot",
                        "open_app", "open_settings"},
            "repair": {"fix_audio", "net_doctor", "optimize_system",
                       "check_drivers", "gpu_report", "inspect_boot", "support_bundle"},
            "apps": {"install_app", "uninstall_app", "update_apps"},
            "system": {"system_update", "system_rollback", "install_nvidia", "update_firmware",
                       "setup_gaming", "setup_windows", "setup_waydroid", "remote_anywhere"},
        }
        for family, names in families.items():
            self.assertTrue(accepted & names, f"no case measures the {family} tools")

    def test_the_threshold_is_the_one_the_plan_states(self):
        self.assertEqual(DOCUMENT["threshold"], 0.95)


class TheRunner(unittest.TestCase):
    CASE = {"id": "mute", "ar": "اكتم صوت الجهاز الآن.", "en": "Mute the speakers now.",
            "accept": ["set_mute"], "confused_with": ["set_volume"]}

    def score(self, called, error=""):
        with patch.object(runner, "ask", lambda *a, **k: (0.5, called, error)):
            return runner.measure_case("m/x:free", self.CASE, "ar", [])

    def test_the_right_tool_is_a_hit_and_everything_else_is_a_miss(self):
        self.assertTrue(self.score(["set_mute"])["correct"])
        # A neighbour, an unrelated tool, silence, and an upstream failure.
        neighbour = self.score(["set_volume"])
        self.assertFalse(neighbour["correct"])
        self.assertEqual(neighbour["why"], "reached for a neighbour")
        self.assertEqual(self.score(["disk_status"])["why"], "chose an unrelated tool")
        self.assertEqual(self.score([])["why"], "called nothing — answered in words")
        self.assertEqual(self.score([], "HTTP 429")["why"], "HTTP 429")

    def test_only_the_first_call_counts(self):
        """A model that calls three tools has not chosen one."""
        self.assertFalse(self.score(["set_volume", "set_mute"])["correct"])
        self.assertTrue(self.score(["set_mute", "set_volume"])["correct"])

    def test_it_sends_the_whole_shipped_schema_and_never_forces_a_choice(self):
        sent = {}

        def ask(model, prompt, tools):
            sent["tools"] = tools
            return 0.1, ["set_mute"], ""

        with patch.object(runner, "ask", ask):
            runner.measure_case("m/x:free", self.CASE, "ar",
                                schemas.get_schemas_for_model())
        self.assertEqual({tool["function"]["name"] for tool in sent["tools"]}, SHIPPED)

        # What actually goes on the wire — forcing `tool_choice` would measure whether
        # the model can read a forced schema, not whether it decides to act, and a
        # refusal to call is a real, countable failure this measurement must keep.
        posted = {}

        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return json.dumps({"choices": [{"message": {"tool_calls": []}}]}).encode()

        def urlopen(request, timeout=0):
            posted["url"] = request.full_url
            posted["body"] = json.loads(request.data)
            return Reply()

        with patch.object(runner.urllib.request, "urlopen", urlopen):
            runner.ask("m/x:free", "اكتم الصوت", schemas.get_schemas_for_model())
        self.assertNotIn("tool_choice", posted["body"])
        self.assertEqual(posted["body"]["model"], "cloud:m/x:free")
        self.assertIs(posted["body"]["stream"], False)
        self.assertEqual(posted["body"]["temperature"], 0)
        self.assertEqual({tool["function"]["name"] for tool in posted["body"]["tools"]}, SHIPPED)
        self.assertTrue(posted["url"].endswith("/v1/chat/completions"))

        # And it must never run what it measured: no executor, no shell, no job route.
        source = (ROOT / "system_files/usr/bin/moai-measure-actions").read_text(encoding="utf-8")
        for forbidden in ("build_command", "subprocess", "tool/execute", "os.system"):
            self.assertNotIn(forbidden, source,
                             f"the measurement must not be able to execute a tool ({forbidden})")

    def test_the_run_writes_the_rate_and_exits_on_the_threshold(self):
        cases = {"schema": 1, "threshold": 0.95, "cases": [
            dict(self.CASE, id=f"c{index}") for index in range(4)]}
        with tempfile.TemporaryDirectory() as home:
            path = Path(home) / "cases.json"
            path.write_text(json.dumps(cases), encoding="utf-8")
            result = Path(home) / "action-accuracy.json"
            answers = iter([["set_mute"]] * 7 + [["set_volume"]])
            with patch.object(runner, "RESULT", result), \
                    patch.object(runner, "ask", lambda *a, **k: (0.2, next(answers), "")), \
                    patch.object(runner.policy, "automatic_model", return_value="m/x:free"), \
                    patch.object(runner.sys, "argv", ["moai-measure-actions", "--cases", str(path)]):
                code = runner.main()
            document = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual((document["correct"], document["total"]), (7, 8))
        self.assertEqual(document["rate"], 0.875)
        self.assertEqual(code, 1, "a rate below the threshold must be visible in the exit code")
        self.assertEqual([miss["case"] for miss in document["misses"]], ["c3"])
        self.assertEqual(document["languages"], ["ar", "en"])


if __name__ == "__main__":
    unittest.main()
