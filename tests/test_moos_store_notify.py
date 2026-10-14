#!/usr/bin/env python3
"""Gate: Mo Store says once, by name, when automatic app updates could not finish.

moos-store-notify reads the background updater's record (~/.local/state/moos/app-updates.json)
whenever it changes. This proves, with a private HOME, a recording notify-send and a recording
moos-store on PATH (nothing reaches the owner's desktop):
  * success, a run still going, a damaged record and a failure with no valid app id say nothing;
  * a failed run is announced once, filed under Mo Store, naming the apps the way the Store
    names them (Arabic or English), and the same run is never announced twice;
  * a notification that never reached anyone (notify-send failed at once) is not remembered,
    so the next rewrite tries again;
  * the one button opens Mo Store's Updates page, and nothing else.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NOTIFIER = ROOT / "system_files/usr/libexec/moos-store-notify"
PATH_UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-store-notify.path"
SERVICE_UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-store-notify.service"
BUILD = ROOT / "build_files/build.sh"


class Notifier(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.jsonl"
        for name in ("notify-send", "moos-store"):
            script = self.bin / name
            script.write_text(
                "#!/usr/bin/python3\nimport json, os, sys\n"
                f"open({str(self.calls)!r}, 'a').write(json.dumps([{name!r}] + sys.argv[1:]) + '\\n')\n"
                "if sys.argv[0].endswith('notify-send'):\n"
                "    if os.environ.get('NOTIFY_FAIL'): sys.exit(1)\n"
                "    print(os.environ.get('NOTIFY_ANSWER', ''))\n",
                encoding="utf-8")
            script.chmod(0o755)
        self.state = self.root / "state"
        self.cache = self.root / "cache"
        (self.state / "moos").mkdir(parents=True)
        (self.cache / "moos-store").mkdir(parents=True)
        (self.cache / "moos-store/index.json").write_text(json.dumps({"apps": [
            {"id": "org.gimp.GIMP", "name": "GIMP", "name_en": "GIMP", "ar": "جيمب"},
        ]}), encoding="utf-8")

    def tearDown(self):
        self.folder.cleanup()

    def record(self, state="failed", updated=1000, failures=None):
        failures = [{"app": "org.gimp.GIMP", "reason": "404"},
                    {"app": "org.example.Broken", "reason": "x"}] if failures is None else failures
        (self.state / "moos/app-updates.json").write_text(
            json.dumps({"schema": 1, "updated": updated, "state": state, "failures": failures}),
            encoding="utf-8")

    def run_notifier(self, lang="en_US.UTF-8", **extra):
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.root / "home"),
               "XDG_STATE_HOME": str(self.state), "XDG_CACHE_HOME": str(self.cache),
               "LANG": lang, "LC_ALL": "", "LC_MESSAGES": ""} | extra
        done = subprocess.run(["python3", "-I", str(NOTIFIER)], env=env, capture_output=True,
                              text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()]

    def test_success_running_damaged_and_empty_say_nothing(self):
        for state in ("ok", "running"):
            self.record(state=state)
            self.assertEqual(self.run_notifier(), [], state)
        (self.state / "moos/app-updates.json").write_text("{broken", encoding="utf-8")
        self.assertEqual(self.run_notifier(), [])
        self.record(failures=[{"app": "../../etc", "reason": "x"}, {"reason": "no app"}])
        self.assertEqual(self.run_notifier(), [])

    def test_a_failed_run_is_announced_once_under_mo_store(self):
        self.record()
        calls = self.run_notifier()
        self.assertEqual(len(calls), 1)
        argv = calls[0]
        self.assertEqual(argv[0], "notify-send")
        self.assertIn("--hint=string:desktop-entry:org.moos.store", argv)
        self.assertIn("Some apps could not be updated", argv)
        self.assertIn("GIMP, Broken. Open Mo Store to try again.", argv)
        self.assertEqual(self.run_notifier(), calls, "the same failed run was announced twice")
        self.record(updated=2000)
        self.assertEqual(len(self.run_notifier()), 2, "a new failed run must be announced")

    def test_arabic_names_and_words(self):
        self.record()
        argv = self.run_notifier(lang="ar_SA.UTF-8")[0]
        self.assertIn("تعذّر تحديث بعض التطبيقات", argv)
        self.assertIn("جيمب، Broken. افتح متجر MoOS لتجربة التحديث مرّة أخرى.", argv)

    def test_a_message_that_never_went_out_is_tried_again(self):
        self.record()
        self.run_notifier(NOTIFY_FAIL="1")
        self.assertFalse((self.state / "moos/store-notify.json").exists())
        self.assertEqual(len(self.run_notifier()), 2)

    def test_the_button_opens_the_updates_page_and_nothing_else(self):
        import time

        self.record()
        self.run_notifier(NOTIFY_ANSWER="open")
        deadline = time.monotonic() + 10
        calls = []
        while time.monotonic() < deadline:   # the Store is started detached
            calls = [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()]
            if calls[-1][0] == "moos-store":
                break
            time.sleep(0.05)
        self.assertEqual(calls[-1], ["moos-store", "--page=updates"])
        self.record(updated=3000)
        calls = self.run_notifier(NOTIFY_ANSWER="something-else")
        self.assertNotEqual(calls[-1][0], "moos-store")


class Wiring(unittest.TestCase):
    def test_units_and_the_build_enable_agree(self):
        path = PATH_UNIT.read_text(encoding="utf-8")
        self.assertIn("PathChanged=%h/.local/state/moos/app-updates.json", path)
        self.assertIn("Unit=moos-store-notify.service", path)
        self.assertIn("WantedBy=plasma-workspace.target", path)
        self.assertIn("ExecStart=/usr/libexec/moos-store-notify", SERVICE_UNIT.read_text(encoding="utf-8"))
        build = BUILD.read_text(encoding="utf-8")
        self.assertIn("systemctl --global enable moos-store-notify.path", build)
        self.assertIn("/usr/lib/systemd/user/moos-store-notify.path", build)
        self.assertTrue(os.access(NOTIFIER, os.X_OK))


if __name__ == "__main__":
    unittest.main(verbosity=2)
