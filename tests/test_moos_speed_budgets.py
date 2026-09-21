#!/usr/bin/env python3
"""P5.4's gate: the budgets are a contract, and the runner reads reality.

The MEASUREMENT needs a booted MoOS with a compositor, so CI cannot take it. What CI
can hold is the shape of the promise:

  * every tier `moos-visual-tier` can report has a budget for every row, and each one
    carries the measurement that justifies it — a budget with no provenance is a wish;
  * a probe that cannot run reports "not measured" and is excluded from the verdict,
    never counted as a zero;
  * a measured row over its budget fails, and the exit code says so;
  * the idle row measures MoOS's OWN processes, not the whole machine — the whole
    machine includes the owner's browser and says nothing about MoOS.
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
BUDGETS = ROOT / "system_files/usr/share/moos/speed-budgets.json"
TIER_TOOL = ROOT / "system_files/usr/bin/moos-visual-tier"


def load(name: str, path: str):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


speed = load("moos_measure_speed", "system_files/usr/bin/moos-measure-speed")
DOCUMENT = json.loads(BUDGETS.read_text(encoding="utf-8"))
ROWS = {key for _probe, _field, key, _en, _ar in speed.ROWS}


class TheBudgets(unittest.TestCase):
    def test_every_tier_the_classifier_can_report_has_every_budget(self):
        tiers = load("moos_visual_tier", "system_files/usr/bin/moos-visual-tier").TIERS
        self.assertEqual(set(DOCUMENT["tiers"]), set(tiers),
                         "a tier with no budgets measures nothing on the machines in it")
        for tier, budgets in DOCUMENT["tiers"].items():
            for row in ROWS:
                self.assertIn(row, budgets, f"{tier} has no budget for {row}")
                self.assertGreater(budgets[row], 0, f"{tier}.{row} is not a positive budget")
            self.assertTrue(budgets.get("measured", "").strip(),
                            f"{tier} does not say where its numbers came from")

    def test_a_looser_tier_is_never_stricter_than_a_faster_one(self):
        """essential ≥ balanced ≥ flagship, or the tiers mean nothing."""
        for row in ROWS:
            values = [DOCUMENT["tiers"][tier][row] for tier in ("flagship", "balanced", "essential")]
            self.assertEqual(values, sorted(values),
                             f"{row} is not monotonic across tiers: {values}")

    def test_every_row_is_explained_in_the_file_the_owner_reads(self):
        for row in ROWS:
            self.assertIn(row, DOCUMENT["rows"], f"{row} has no explanation")


class TheVerdict(unittest.TestCase):
    BUDGETS = {"boot_userspace_s": 9.0, "session_ready_s": 3.0,
               "app_launch_s": 4.0, "idle_busy_percent": 8.0}

    def test_a_probe_that_could_not_run_is_not_a_zero(self):
        rows = speed.verdicts({"boot": {"measured": False, "why": "no systemd"}}, self.BUDGETS)
        boot = next(row for row in rows if row["row"] == "boot")
        self.assertEqual((boot["verdict"], boot["measured"]), ("not measured", False))
        self.assertEqual(boot["why"], "no systemd")
        self.assertNotIn("value", boot)

    def test_over_budget_is_over_budget_and_within_is_within(self):
        rows = speed.verdicts({
            "boot": {"measured": True, "userspace_s": 6.0},
            "idle": {"measured": True, "moos_busy_percent": 9.1},
        }, self.BUDGETS)
        verdicts = {row["row"]: row["verdict"] for row in rows}
        self.assertEqual(verdicts["boot"], "within budget")
        self.assertEqual(verdicts["idle"], "over budget")
        self.assertEqual(verdicts["session"], "not measured")

    def test_the_run_exits_on_a_measured_failure_only(self):
        with tempfile.TemporaryDirectory() as home:
            result = Path(home) / "speed.json"
            probes = {
                "boot": {"measured": True, "userspace_s": 6.0},
                "session": {"measured": True, "ready_s": 1.1},
                "idle": {"measured": True, "moos_busy_percent": 2.6},
                "launch": {"measured": False, "why": "no KWin session to ask"},
            }
            with patch.object(speed, "RESULT", result), \
                    patch.object(speed, "tier", return_value="flagship"), \
                    patch.object(speed, "boot", lambda: probes["boot"]), \
                    patch.object(speed, "session", lambda: probes["session"]), \
                    patch.object(speed, "idle", lambda: probes["idle"]), \
                    patch.object(speed, "launch", lambda *a, **k: probes["launch"]), \
                    patch.object(speed.sys, "argv",
                                 ["moos-measure-speed", "--budgets", str(BUDGETS)]):
                self.assertEqual(speed.main(), 0,
                                 "a probe that could not run must not fail the machine")
                probes["idle"] = {"measured": True, "moos_busy_percent": 99.0}
                self.assertEqual(speed.main(), 1)
            document = json.loads(result.read_text(encoding="utf-8"))
        self.assertEqual(document["tier"], "flagship")
        self.assertEqual(next(row for row in document["rows"] if row["row"] == "idle")["verdict"],
                         "over budget")

    def test_idle_measures_what_moos_owns_and_reports_the_machine_beside_it(self):
        """A browser and an IDE are the owner's CPU, not MoOS's.

        Measured on the station: the whole machine read 9.03% busy with Chrome, VS Code
        and Steam open while MoOS's own processes cost 2.6%. Budgeting the first would
        fail on every machine anyone actually uses.
        """
        _probe, field, budget_key, _en, _ar = next(
            row for row in speed.ROWS if row[0] == "idle")
        self.assertEqual((field, budget_key), ("moos_busy_percent", "idle_busy_percent"))
        self.assertIn("kwin_wayland", speed.MOOS_PROCESSES)
        self.assertIn("moai-gateway", speed.MOOS_PROCESSES)
        for foreign in ("chrome", "code", "steam", "firefox"):
            self.assertNotIn(foreign, speed.MOOS_PROCESSES)

    def test_systemd_durations_are_read_in_every_unit_it_prints(self):
        self.assertEqual(speed._seconds("6.100s"), 6.1)
        self.assertEqual(speed._seconds("903ms"), 0.903)
        self.assertEqual(speed._seconds("1min 4.203s"), 64.203)
        self.assertEqual(speed._seconds("nothing here"), 0.0)


class TheLaunchProbeBlamesTheRightThing(unittest.TestCase):
    """A dead channel must not be reported as a dead app.

    Measured on the ARM station 2026-09-21: plasmashell owns org.kde.klipper but exposes
    no /klipper object when the clipboard applet is not in the tray, and MoOS curates its
    tray. Every _klipper() read then returns '', the 60 s wait times out, and the probe
    said "the window never reached KWin" — about apps that had just opened and rendered.
    """

    def _run(self, klipper_answers):
        calls = []

        def fake_klipper(*args):
            calls.append(args)
            return klipper_answers(*args)

        with patch.object(speed, "_klipper", side_effect=fake_klipper), \
             patch.object(speed, "run", return_value="/usr/bin/moai"), \
             patch.object(speed, "_kwin", return_value="") as kwin:
            return speed.launch("moai"), calls, kwin

    def test_a_klipper_that_never_answers_is_named_instead_of_the_app(self):
        outcome, _, kwin = self._run(lambda *args: "")
        self.assertFalse(outcome["measured"])
        self.assertIn("clipboard channel", outcome["why"])
        self.assertIn("org.kde.klipper", outcome["why"])
        # It must not have blamed the window, and must not have waited 60 s to do it.
        self.assertNotIn("never reached KWin", outcome["why"])
        kwin.assert_not_called()

    def test_a_working_channel_is_not_mistaken_for_a_broken_one(self):
        held = {"value": ""}

        def answer(*args):
            if args[0] == "setClipboardContents":
                held["value"] = args[1]
                return ""
            return held["value"]

        outcome, calls, _ = self._run(answer)
        # The round trip succeeded, so the probe went on to do its real work rather than
        # returning the channel excuse.
        self.assertNotIn("clipboard channel", outcome.get("why", ""))
        self.assertTrue(any(a[0] == "setClipboardContents" for a in calls))


if __name__ == "__main__":
    unittest.main()
