#!/usr/bin/env python3
"""Keep display failures fatal without inventing their cause or hiding journal errors."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "tests/post-update-check.sh").read_text()
SECTION = SOURCE.split("# BEGIN session-display diagnostics", 1)[1].split(
    "# END session-display diagnostics", 1)[0]


class DisplayJournal(unittest.TestCase):
    def probe(self, rows="", code=0):
        with tempfile.TemporaryDirectory(prefix="moos-display-journal-") as raw:
            path = Path(raw)
            setup = r'''
set -uo pipefail
fail=0
ok() { printf 'OK %s\n' "$*"; }
bad() { printf 'BAD %s\n' "$*"; fail=$((fail+1)); }
journalctl() {
    printf '%s\n' "$*" >> "$CALLS"
    printf '%s' "$ROWS"
    return "$STATUS"
}
'''
            env = {"PATH": "/usr/bin:/bin", "HOME": raw, "XDG_RUNTIME_DIR": raw,
                   "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + raw + "/no-owner-bus",
                   "ROWS": rows, "STATUS": str(code), "CALLS": str(path / "calls")}
            result = subprocess.run(["bash", "-c", setup + SECTION + '\nexit "$fail"'],
                                    env=env, text=True, capture_output=True, timeout=5)
            self.assertEqual((path / "calls").read_text().splitlines(),
                             ["--user -b --no-pager -o short-monotonic"])
            return result

    def test_readable_journal_without_display_failures(self):
        for rows in ("", "[ 3.000] host plasmashell[12]: ready\n"):
            with self.subTest(rows=rows):
                result = self.probe(rows)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("OK no display-connection failures", result.stdout)

    def test_original_startup_and_later_app_failures_both_remain_fatal(self):
        for stamp, name, count in (("3.5", "plasmashell", 8), ("1563.377", "kdialog", 30)):
            with self.subTest(name=name):
                result = self.probe(
                    f"[ {stamp}] host {name}[12]: could not connect to display :0\n" * count)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f"BAD {count} display-connection failure(s)", result.stdout)
                self.assertIn(name, result.stdout)
                self.assertNotIn("compositor lost its race", result.stdout)
                self.assertNotIn("were restarted", result.stdout)

    def test_failed_and_partial_journal_queries_never_report_healthy(self):
        for code in (1, 7, 124):
            for rows in ("", "[ 3.000] host app[12]: ready\n",
                         "[ 3.000] host app[12]: could not connect to display :0\n"):
                with self.subTest(code=code, rows=rows):
                    result = self.probe(rows, code)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("journal is unavailable", result.stdout)
                    self.assertNotIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
