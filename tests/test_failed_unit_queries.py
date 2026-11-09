#!/usr/bin/env python3
# Execute both diagnostic sections with private service-manager responses.
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("system_files/usr/bin/moos-selfcheck", "tests/post-update-check.sh")

def section(text, path):
    if "# BEGIN failed-unit diagnostics" in text:
        return text.split("# BEGIN failed-unit diagnostics", 1)[1].split(
            "# END failed-unit diagnostics", 1)[0]
    if path.endswith("moos-selfcheck"):
        return text[text.index("failed_units() {"):text.index("# ── The look")]
    return text[text.index('head_ "Failed units"'):text.index('head_ "The session')]

class FailedUnitQueries(unittest.TestCase):
    def probe(self, path, system="", user="", system_rc=0, user_rc=0):
        with tempfile.TemporaryDirectory() as tmp:
            calls = Path(tmp) / "calls"
            env = {"PATH": "/usr/bin:/bin", "HOME": tmp,
                   "XDG_CONFIG_HOME": tmp, "XDG_DATA_HOME": tmp,
                   "XDG_CACHE_HOME": tmp, "XDG_RUNTIME_DIR": tmp,
                   "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent/moos-test",
                   "SYSTEM_ROWS": system, "USER_ROWS": user,
                   "SYSTEM_RC": str(system_rc), "USER_RC": str(user_rc),
                   "CALLS": str(calls)}
            setup = r'''
set -uo pipefail
fail=0
ok() { printf 'OK %s\n' "$*"; }
bad() { printf 'BAD %s\n' "$*"; fail=$((fail+1)); }
head_() { :; }
systemctl() {
    case " $* " in
        *" --user "*) echo user >> "$CALLS"
            printf '%s' "$USER_ROWS"; return "$USER_RC" ;;
        *) echo system >> "$CALLS"
            printf '%s' "$SYSTEM_ROWS"; return "$SYSTEM_RC" ;;
    esac
}
'''
            r = subprocess.run(["bash", "-c", setup + section(
                (ROOT / path).read_text(), path) + '\nexit "$fail"\n'],
                env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(calls.read_text().splitlines(), ["system", "user"])
            return r

    def test_successful_empty_managers(self):
        for path in SOURCES:
            with self.subTest(path=path):
                r = self.probe(path)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.count("OK no failed"), 2)

    def test_unavailable_manager_is_not_healthy(self):
        for path in SOURCES:
            for scope in ("system", "user"):
                for code in (1, 7, 124):
                    with self.subTest(path=path, scope=scope, code=code):
                        r = self.probe(path, **{scope + "_rc": code})
                        self.assertNotEqual(r.returncode, 0)
                        self.assertIn("BAD", r.stdout)
                        self.assertNotIn("OK no failed " + scope, r.stdout)

    def test_partial_output_on_failure_is_not_accepted(self):
        for path in SOURCES:
            with self.subTest(path=path):
                r = self.probe(path, system="a.service loaded failed failed A\n",
                               system_rc=1)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("state is unavailable", r.stdout)

    def test_real_failures_and_narrow_handler_exclusion(self):
        for path in SOURCES:
            for scope in ("system", "user"):
                with self.subTest(path=path, scope=scope):
                    r = self.probe(path, **{scope:
                        "drkonqi-coredump-processor@12.service loaded failed failed Handler\n"
                        "kwallet.service loaded failed failed Wallet\n"
                        "not-drkonqi-coredump.service loaded failed failed Other\n"})
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn("2 failed " + scope, r.stdout)
                    self.assertIn("kwallet.service", r.stdout)
                    self.assertIn("not-drkonqi-coredump.service", r.stdout)

    def test_handler_only_is_excluded(self):
        for path in SOURCES:
            with self.subTest(path=path):
                r = self.probe(path, system=
                    "drkonqi-coredump-processor@12.service loaded failed failed Handler\n")
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_malformed_success_is_not_clean(self):
        for path in SOURCES:
            with self.subTest(path=path):
                r = self.probe(path, user="unreadable output\n")
                self.assertNotEqual(r.returncode, 0)
                self.assertNotIn("OK no failed user", r.stdout)

if __name__ == "__main__":
    unittest.main()
