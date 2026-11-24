#!/usr/bin/env python3
"""A timer that fires every few minutes must not fill the journal with nothing.

MoOS caps the journal at 500 MB, and on 2026-11-24 the V3 held 490.7 MB: the
previous boot's evidence is the first thing a full journal loses (AGENTS.md,
"The journal may not reach back one boot"). The two loudest user-manager units
were MoOS's own minute-scale timers: mo-remote-watchdog (804 lines in one boot)
and openclaw-idle (338), each firing a oneshot whose Starting/Finished pair says
nothing.

LogLevelMax=notice drops the manager's info-level lines about the unit, and
SyslogLevel=notice keeps the script's own stdout/stderr above that limit.
Measured on the V3 user manager with transient units: `logger` (user.notice),
stdout and stderr survived; Starting/Finished did not. A failure or timeout is
logged above notice and still appears.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
UNIT_DIRS = [REPO / "system_files/usr/lib/systemd/user",
             REPO / "system_files/usr/lib/systemd/system"]
FREQUENT_SECONDS = 10 * 60
UNITS = {"s": 1, "sec": 1, "min": 60, "m": 60, "h": 3600, "hr": 3600, "d": 86400}


def seconds(value: str):
    total = 0
    for number, unit in re.findall(r"(\d+)\s*([a-z]*)", value.strip()):
        total += int(number) * UNITS.get(unit or "s", 0)
    return total or None


def frequent_timers():
    for directory in UNIT_DIRS:
        for timer in sorted(directory.glob("*.timer")):
            text = timer.read_text(encoding="utf-8")
            periods = [seconds(v) for v in re.findall(
                r"(?m)^OnUnit(?:Active|Inactive)Sec=(.+)$", text)]
            if any(p is not None and p <= FREQUENT_SECONDS for p in periods):
                unit = re.search(r"(?m)^Unit=(.+)$", text)
                service = unit.group(1).strip() if unit else timer.stem + ".service"
                yield timer, directory / service


class FrequentTimerJournal(unittest.TestCase):
    def test_parser_reads_the_periods(self):
        self.assertEqual(seconds("1min"), 60)
        self.assertEqual(seconds("5min"), 300)
        self.assertEqual(seconds("1h 30min"), 5400)
        self.assertEqual(seconds("45s"), 45)

    def test_the_known_minute_timers_are_found(self):
        found = {timer.name for timer, _ in frequent_timers()}
        for name in ("mo-remote-watchdog.timer", "openclaw-idle.timer"):
            self.assertIn(name, found, "the scan must see the units it was written for")

    def test_frequent_oneshots_keep_only_their_own_messages(self):
        offenders = []
        for timer, service in frequent_timers():
            self.assertTrue(service.is_file(), f"{timer.name} activates missing {service.name}")
            body = service.read_text(encoding="utf-8").split("\n[Service]\n", 1)
            section = body[1] if len(body) == 2 else ""
            if not re.search(r"(?m)^LogLevelMax=notice$", section):
                offenders.append(f"{service.name}: no LogLevelMax=notice")
            if not re.search(r"(?m)^SyslogLevel=notice$", section):
                offenders.append(f"{service.name}: script output at info would be dropped")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
