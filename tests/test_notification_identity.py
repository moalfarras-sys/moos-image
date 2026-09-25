#!/usr/bin/env python3
"""Gate: every MoOS notification is filed under the MoOS surface it belongs to.

WHY THIS EXISTS
MoOS's notifications went out as `notify-send --app-name=MoOS` (or `--app-name=Mo AI`) and
as kdialog passive popups, with no desktop-entry hint. Measured on the station on
2026-09-24: ~/.config/plasmanotifyrc listed five other programs as notification sources and
nothing from MoOS, so System Settings › Notifications could neither show nor mute a single
MoOS message. The desktop-entry hint is how the notification server learns whose message it
is: it files it under that entry's name and icon, and the Notifications page lists it.

The owners are fixed (wave decision): MoOS Settings (`systemsettings`, the one Settings
entry) for updates, What's new and settings; Mo AI (`org.moos.moai`) for Mo AI; Mo Store
(`org.moos.store`) for App Drop and the Store.

What this proves:
  * every shipped program that calls notify-send passes a desktop-entry hint, and the hint
    names an owner from that closed list — the scanner is shown to find every sender;
  * each sender names ITS owner;
  * a kdialog passive popup is only ever the fallback behind a hinted notify-send;
  * executed: moos-open, moos-app-drop and moos-update-ready hand notify-send the hint, and
    moos-open falls back to kdialog only when notify-send fails.
Every execution runs with recording stubs, a private HOME and runtime directory and no
session bus, so nothing reaches the owner's desktop.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYSTEM = ROOT / "system_files"
APPLICATIONS = SYSTEM / "usr/share/applications"
OWNERS = {"systemsettings", "org.moos.moai", "org.moos.store"}
# Who each sender speaks for. A new sender joins this table or the gate fails.
EXPECTED = {
    "usr/bin/moos-open": {"systemsettings", "org.moos.store"},
    "usr/bin/moos-run-foreign": {"org.moos.store"},
    "usr/bin/moos-app-drop": {"org.moos.store"},
    "usr/bin/moos-health": {"org.moos.moai"},
    "usr/bin/moos-installer": {"systemsettings"},
    "usr/libexec/moos-update-ready": {"systemsettings"},
    "usr/libexec/moos-whats-new-notify": {"systemsettings"},
}
HINT = re.compile(r"desktop-entry:(?:\$\{owner\}|([A-Za-z0-9_.-]+))")


def shipped_programs():
    for folder in ("usr/bin", "usr/libexec", "usr/lib/moos", "usr/lib/moai"):
        for path in sorted((SYSTEM / folder).rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            yield path, text


def code_of(text: str) -> str:
    """Comment lines removed and shell continuations joined: one statement per line."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    return re.sub(r"\\\n\s*", " ", "\n".join(lines))


def invocations(code: str) -> list[str]:
    """Each statement that RUNS notify-send, with its arguments.

    Shell: a line where notify-send is followed by an option or a quoted word. Python: the
    argv list that starts with "notify-send". `command -v` and `shutil.which` are lookups.
    """
    found = []
    for line in code.splitlines():
        if re.search(r"""(?<![-\w])notify-send\s+(--|["'$])""", line):
            found.append(line)
    for match in re.finditer(r"""\[\s*["']notify-send["'](.*?)\]""", code, re.S):
        found.append(match.group(0))
    return found


class EverySenderIsFiled(unittest.TestCase):
    def test_the_scanner_finds_every_sender_and_each_names_its_owner(self):
        senders = {}
        for path, text in shipped_programs():
            calls = invocations(code_of(text))
            if calls:
                senders[str(path.relative_to(SYSTEM))] = calls
        self.assertEqual(sorted(senders), sorted(EXPECTED),
                         "a program sends notifications this gate does not know about "
                         "(add it to EXPECTED with its owner), or one stopped sending")
        for relative, calls in senders.items():
            for call in calls:
                with self.subTest(sender=relative, call=call[:80]):
                    self.assertRegex(call, r"""--hint=["']?string:desktop-entry:""",
                                     "a MoOS notification with no owner is anonymous in "
                                     "System Settings › Notifications")
            named = {name for call in calls for name in HINT.findall(call) if name}
            dynamic = any("${owner}" in call for call in calls)
            if dynamic:
                # The router's helper picks the owner from a closed case: read its values.
                text = (SYSTEM / relative).read_text(encoding="utf-8")
                named |= set(re.findall(r'owner="([A-Za-z0-9_.-]+)"', text))
            self.assertEqual(named, EXPECTED[relative], relative)
            self.assertLessEqual(named, OWNERS, relative)

    def test_every_owner_is_an_entry_the_notifications_page_can_list(self):
        for owner in OWNERS - {"systemsettings"}:
            entry = APPLICATIONS / f"{owner}.desktop"
            self.assertTrue(entry.is_file(), f"{owner} has no desktop entry")
            main_group = entry.read_text(encoding="utf-8").split("\n[Desktop Action", 1)[0]
            self.assertNotIn("\nNoDisplay=true", main_group,
                             f"{owner} is hidden: its notifications would have no listing")
        # systemsettings is Plasma's own entry, made the ONE visible "MoOS Settings" by
        # build.sh (wave decision D2); the image gates hold that entry.

    def test_a_passive_popup_is_only_the_fallback(self):
        for path, text in shipped_programs():
            code = code_of(text)
            if "--passivepopup" not in code:
                continue
            relative = str(path.relative_to(SYSTEM))
            with self.subTest(sender=relative):
                body = re.search(r"(?ms)^notify\(\) \{\n(.*?)^\}", code)
                self.assertIsNotNone(body, f"{relative}: the popup is not inside notify()")
                body = body.group(1)
                self.assertLess(body.find("notify-send"), body.find("--passivepopup"),
                                f"{relative}: kdialog is tried before the filed notification")
                self.assertIn("desktop-entry:", body)
                self.assertEqual(code.count("--passivepopup"), 1,
                                 f"{relative}: a popup outside the notify() helper")


class TheSendersExecuted(unittest.TestCase):
    """Executed with recording stubs and no session bus: nothing reaches a real desktop."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.sent = self.root / "sent.log"
        self.popups = self.root / "popups.log"
        self.stub("notify-send", 'for a in "$@"; do printf "%s\\t" "$a"; done >> "$SENT"\n'
                                 'printf "\\n" >> "$SENT"\nexit "${NOTIFY_EXIT:-0}"\n')
        self.stub("kdialog", 'case "$*" in *warningyesno*) exit 0;; '
                             '*passivepopup*) printf "%s\\n" "$*" >> "$POPUPS";; esac\n')
        self.stub("systemctl", "exit 0\n")
        self.stub("moai-do", 'echo "Done"\n')
        self.stub("logger", "exit 0\n")
        (self.root / "run").mkdir(mode=0o700)

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def env(self, **extra):
        return {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.root),
                "XDG_RUNTIME_DIR": str(self.root / "run"), "LANG": "C.UTF-8",
                "SENT": str(self.sent), "POPUPS": str(self.popups),
                "DBUS_SESSION_BUS_ADDRESS": f"unix:path={self.root}/no-bus", **extra}

    def wait_for(self, path, seconds=5):
        deadline = time.monotonic() + seconds
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.1)
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def open(self, url, **extra):
        return subprocess.run(["bash", str(SYSTEM / "usr/bin/moos-open"), url],
                              env=self.env(**extra), capture_output=True, text=True, timeout=30)

    def test_moos_open_files_settings_results_under_moos_settings(self):
        self.open("moos://remote/stop")
        sent = self.wait_for(self.sent)
        self.assertEqual(len(sent), 1, sent)
        self.assertIn("--hint=string:desktop-entry:systemsettings", sent[0].split("\t"))
        self.assertIn("--app-name=MoOS", sent[0].split("\t"))
        self.assertFalse(self.popups.exists(), "kdialog spoke although notify-send worked")

    def test_moos_open_files_app_updates_under_mo_store(self):
        self.open("moos://do/update-apps")
        sent = self.wait_for(self.sent)
        self.assertEqual(len(sent), 1, sent)
        self.assertIn("--hint=string:desktop-entry:org.moos.store", sent[0].split("\t"))

    def test_moos_open_falls_back_to_kdialog_only_when_notify_send_fails(self):
        self.open("moos://remote/stop", NOTIFY_EXIT="1")
        popups = self.wait_for(self.popups)
        self.assertEqual(len(popups), 1, popups)
        self.assertIn("Mo PC Remote", popups[0])

    def test_app_drop_files_its_messages_under_mo_store(self):
        done = subprocess.run([sys.executable, str(SYSTEM / "usr/bin/moos-app-drop"),
                               str(self.root / "missing.AppImage")],
                              env=self.env(), capture_output=True, text=True, timeout=60)
        self.assertEqual(done.returncode, 2, done.stderr)
        sent = self.wait_for(self.sent)
        self.assertEqual(len(sent), 1, sent)
        self.assertIn("--hint=string:desktop-entry:org.moos.store", sent[0].split("\t"))

    def test_update_ready_files_its_message_under_moos_settings(self):
        if not Path("/ostree/deploy").is_dir():
            self.skipTest("moos-update-ready speaks only on an ostree machine")
        backend = self.bin / "moos-image-update"
        backend.write_text("#!/bin/sh\necho '{\"schema\":1,\"state\":\"staged\","
                           "\"staged_version\":\"44.20260925.1\"}'\n", encoding="utf-8")
        backend.chmod(0o755)
        subprocess.run(["bash", str(SYSTEM / "usr/libexec/moos-update-ready")],
                       env=self.env(MOOS_IMAGE_UPDATE_BACKEND=str(backend),
                                    XDG_STATE_HOME=str(self.root / "state")),
                       capture_output=True, text=True, timeout=30)
        sent = self.wait_for(self.sent)
        self.assertEqual(len(sent), 1, sent)
        self.assertIn("--hint=string:desktop-entry:systemsettings", sent[0].split("\t"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
