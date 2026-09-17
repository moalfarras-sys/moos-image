#!/usr/bin/env python3
"""Gate: MoOS tells a person what an update brought — truthfully, once, and only where it can take them.

WHY THIS EXISTS

On 2026-09-17 the owner updated the station and the A1 across six waves and said "I felt no
change". Each wave had shipped something a person can use; nothing on the desktop said so.
`/usr/share/moos/whats-new.json` is the answer: a short bilingual list of what a person can see
or do, shown by MoOS Settings → System → What's new and announced once after an update by
`moos-whats-new-notify`. A list like that rots in three ways, and this gate is here for each:

  * IT LIES BY OMISSION. The reader drops an entry it cannot validate — the right thing to do
    with hostile data, and the wrong thing to do silently with our own. Every shipped entry must
    survive the reader, so a typo in the file is a red gate and not a missing card.
  * IT POINTS NOWHERE. "Try it" may only name a route that `moos-open` really has AND that MoOS
    Settings is allowed to open (its own pages, or a destination the status helper probes). A
    glyph must exist in the symbol catalogue, or the card draws the fallback spark.
  * IT NAGS OR STAYS MUTE. The notification must fire once per version for a returning user,
    never for a brand-new one, never for an update that brought nothing visible, and a message
    that did not go out must be retried at the next login rather than recorded as delivered.

The notifier runs END TO END here, not as a copy: under bubblewrap it gets an /ostree/deploy, a
recording `rpm-ostree`, `notify-send` and `moos-open`, and a private home.
"""

from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SYS = ROOT / "system_files"
DATA = SYS / "usr/share/moos/whats-new.json"
READER = SYS / "usr/lib/moos/moos_whats_new.py"
STATUS = SYS / "usr/libexec/moos-settings-status"
NOTIFIER = SYS / "usr/libexec/moos-whats-new-notify"
AUTOSTART = SYS / "etc/xdg/autostart/org.moos.whats-new.desktop"
ROUTER = SYS / "usr/bin/moos-open"
SETTINGS = SYS / "usr/share/moos/apps/settings/main.qml"
CATALOG = SYS / "usr/lib64/qt6/qml/org/moos/ui/SymbolCatalog.js"

ARABIC = re.compile(r"[\u0600-\u06FF]")
W1_BUILT = 1789516800          # 2026-09-16 00:00 UTC: the image both machines ran before W2


def reader():
    return runpy.run_path(str(READER))


def shipped() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))["entries"]


class TheListIsTrueToItsContract(unittest.TestCase):
    def test_every_shipped_entry_survives_the_reader(self) -> None:
        raw = shipped()
        self.assertGreaterEqual(len(raw), 1)
        state = reader()["whats_new_state"](W1_BUILT, DATA)
        self.assertEqual([entry["id"] for entry in state["entries"]], [entry["id"] for entry in raw],
                         "an entry the reader drops is a card that silently never appears, and the "
                         "file's order must already be the order shown: newest first")
        for before, after in zip(raw, state["entries"]):
            self.assertEqual(after["route"], before.get("route", ""),
                             f"{before['id']}: the reader refused this route")
            self.assertEqual(after["keys"], before.get("keys", []),
                             f"{before['id']}: the reader refused these keys")

    def test_each_entry_is_written_for_a_person_in_both_languages(self) -> None:
        identity = runpy.run_path(str(ROOT / "tests/test_user_visible_identity.py"))
        for entry in shipped():
            for field, limit in (("title", 60), ("body", 320)):
                arabic, english = entry[field]["ar"], entry[field]["en"]
                self.assertRegex(arabic, ARABIC, f"{entry['id']}.{field}.ar is not Arabic")
                self.assertNotRegex(english, ARABIC, f"{entry['id']}.{field}.en contains Arabic")
                for text in (arabic, english):
                    self.assertLessEqual(len(text), limit, f"{entry['id']}.{field} is too long to read")
                    self.assertIsNone(identity["hit"](text),
                                      f"{entry['id']}.{field} names another system or desktop: {text!r}")
            for text in entry["body"].values():
                self.assertTrue(text.rstrip().endswith((".", "؟", "?")),
                                f"{entry['id']}: a body is a sentence and ends like one")

    def test_merged_times_are_real_and_newest_first(self) -> None:
        epochs = [reader()["merged_epoch"](entry["merged"]) for entry in shipped()]
        self.assertTrue(all(epochs), "every entry names the moment it reached main, to the second, in UTC")
        self.assertEqual(epochs, sorted(epochs, reverse=True), "the file is read in the order it is shown")
        self.assertLess(max(epochs), time.time() + 7 * 86400, "a merge time in the far future is a typo")
        self.assertGreater(min(epochs), reader()["merged_epoch"]("2026-09-01T00:00:00Z"))

    def test_a_glyph_is_one_the_catalogue_has(self) -> None:
        names = set(re.findall(r'^\s*"([a-z-]+)": true', CATALOG.read_text(encoding="utf-8"), re.M))
        self.assertIn("spark", names)
        for entry in shipped():
            self.assertIn(entry["glyph"], names,
                          f"{entry['id']}: glyph {entry['glyph']!r} would draw the fallback")

    def test_try_it_only_names_a_route_that_exists_and_that_settings_may_open(self) -> None:
        routed = set(re.findall(r"^    settings/([a-z-]+)\)", ROUTER.read_text(encoding="utf-8"), re.M))
        destinations = set(runpy.run_path(str(STATUS))["DESTINATIONS"])
        qml = SETTINGS.read_text(encoding="utf-8")
        in_app = set(re.findall(r'"moos://settings/([a-z-]+)":',
                                re.search(r"readonly property var inAppRoutes: \((\{[^}]*\})\)", qml).group(1)))
        for entry in shipped():
            route = entry.get("route")
            if not route:
                continue
            self.assertTrue(route.startswith("moos://settings/"), f"{entry['id']}: {route}")
            name = route[len("moos://settings/"):]
            self.assertIn(name, routed, f"{entry['id']}: moos-open has no settings/{name}")
            self.assertTrue(name in destinations or name in in_app,
                            f"{entry['id']}: MoOS Settings cannot open {route}")

    def test_the_page_is_reachable_every_way_the_others_are(self) -> None:
        qml = SETTINGS.read_text(encoding="utf-8")
        router = ROUTER.read_text(encoding="utf-8")
        self.assertIn("settings/whats-new)         gui moos-settings --section=whats-new ;;", router)
        self.assertIn('"moos://settings/whats-new": "whats-new"', qml)
        self.assertIn('{ section: "system", route: "moos://settings/whats-new", glyph: "spark",', qml,
                      "the page must be a row of the System section, so search finds it")
        self.assertIn("readonly property var inAppPages: [aboutSection, whatsNewSection]", qml)
        self.assertIn('onClicked: win.openRoute("moos://settings/whats-new")', qml,
                      "About this device must lead to What's new")
        # A status document from before this page existed must not break the window.
        self.assertIn("statusLoaded && status.whatsNew && status.whatsNew.entries", qml)


class TheImageGate(unittest.TestCase):
    def test_the_image_gates_own_check_passes_on_this_tree_and_can_fail(self) -> None:
        """The image build runs whats_new_is_readable(""); run the SAME code here first (plan P0.9)."""
        import ast

        gate = (ROOT / "build_files/verify_image_experience.py").read_text(encoding="utf-8")
        function = next(node for node in ast.parse(gate).body
                        if isinstance(node, ast.FunctionDef) and node.name == "whats_new_is_readable")
        scope: dict = {"os": os}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "verify_image_experience.py", "exec"), scope)
        check = scope["whats_new_is_readable"]
        self.assertIn('whats_new_is_readable("")', gate, "the image build no longer calls the check")
        problems = check(str(SYS))
        if sys.platform == "win32":
            problems = [p for p in problems if "not executable" not in p]
        self.assertEqual(problems, [])

        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw)
            for part in ("usr/share/moos", "usr/lib/moos", "usr/libexec", "etc/xdg/autostart"):
                (tree / part).mkdir(parents=True)
            shutil.copy(READER, tree / "usr/lib/moos/moos_whats_new.py")
            shutil.copy(NOTIFIER, tree / "usr/libexec/moos-whats-new-notify")
            shutil.copy(AUTOSTART, tree / "etc/xdg/autostart/org.moos.whats-new.desktop")
            broken = {"schema": 1, "entries": [{"id": "fine", "merged": "2026-09-17T10:00:00Z", "glyph": "spark",
                                                "title": {"ar": "أ", "en": "A"}, "body": {"ar": "ب.", "en": "B."}},
                                               {"id": "BROKEN", "merged": "soon"}]}
            (tree / "usr/share/moos/whats-new.json").write_text(json.dumps(broken), encoding="utf-8")
            self.assertTrue(any("drops" in problem for problem in check(str(tree))),
                            "an entry the installed reader cannot read must fail the image")


class TheReaderTreatsTheFileAsData(unittest.TestCase):
    def state(self, document, previous=W1_BUILT):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "whats-new.json"
            if isinstance(document, (bytes, bytearray)):
                path.write_bytes(document)
            else:
                path.write_text(json.dumps(document), encoding="utf-8")
            return reader()["whats_new_state"](previous, path)

    @staticmethod
    def entry(identifier="a", merged="2026-09-17T10:00:00Z", **extra):
        return {"id": identifier, "merged": merged, "glyph": "spark",
                "title": {"ar": "عنوان", "en": "Title"}, "body": {"ar": "نص.", "en": "Text."}, **extra}

    def test_fresh_means_newer_than_the_system_this_machine_ran_before(self) -> None:
        document = {"schema": 1, "entries": [
            self.entry("new", "2026-09-17T22:36:04Z"), self.entry("old", "2026-09-17T10:34:56Z")]}
        between = reader()["merged_epoch"]("2026-09-17T18:00:00Z")
        state = self.state(document, between)
        self.assertEqual([(e["id"], e["fresh"]) for e in state["entries"]], [("new", True), ("old", False)])
        self.assertEqual(state["fresh"], 1)
        self.assertEqual(self.state(document, W1_BUILT)["fresh"], 2, "a jump of several releases marks all of them")
        self.assertEqual(self.state(document, 0)["fresh"], 0, "a fresh install had nothing change under it")

    def test_newest_first_whatever_order_the_file_is_in(self) -> None:
        document = {"schema": 1, "entries": [
            self.entry("old", "2026-09-01T00:00:00Z"), self.entry("new", "2026-09-17T00:00:00Z")]}
        self.assertEqual([e["id"] for e in self.state(document)["entries"]], ["new", "old"])

    def test_a_missing_or_malformed_file_is_an_empty_list_not_an_error(self) -> None:
        module = reader()
        empty = {"entries": [], "fresh": 0}
        self.assertEqual(module["whats_new_state"](W1_BUILT, Path("/nonexistent/whats-new.json")), empty)
        for document in (b"not json", b"[]", {"schema": 2, "entries": []}, {"schema": 1, "entries": {}}):
            self.assertEqual(self.state(document), empty)
        self.assertEqual(self.state(b" " * (module["MAX_BYTES"] + 1)), empty, "an oversized file is refused unread")

    def test_one_bad_entry_is_dropped_and_the_rest_stay(self) -> None:
        good = self.entry("good")
        bad = [
            "text", self.entry("UPPER"), self.entry("good"),                     # not an object, bad id, duplicate
            self.entry("no-date", "yesterday"), {**self.entry("no-ar"), "title": {"en": "Only"}},
            {**self.entry("long"), "body": {"ar": "ن" * 400, "en": "x"}},
            {**self.entry("glyph"), "glyph": "../etc"},
        ]
        state = self.state({"schema": 1, "entries": [good, *bad]})
        self.assertEqual([e["id"] for e in state["entries"]], ["good"])

    def test_a_route_outside_settings_is_removed_and_the_entry_kept(self) -> None:
        for route in ("https://example.org", "moos://apps/install/firefox", "moos://do/smart-setup",
                      "moos://settings/../do/x", "file:///etc/passwd", 7):
            state = self.state({"schema": 1, "entries": [self.entry(route=route)]})
            self.assertEqual(state["entries"][0]["route"], "", route)
        state = self.state({"schema": 1, "entries": [self.entry(route="moos://settings/about")]})
        self.assertEqual(state["entries"][0]["route"], "moos://settings/about")

    def test_the_list_is_bounded(self) -> None:
        module = reader()
        many = [self.entry(f"e{index}", f"2026-09-{index % 28 + 1:02d}T00:00:00Z") for index in range(60)]
        self.assertEqual(len(self.state({"schema": 1, "entries": many})["entries"]), module["MAX_ENTRIES"])


class TheStatusDocumentCarriesIt(unittest.TestCase):
    def test_the_previous_system_is_the_one_kept_for_rollback(self) -> None:
        scope = runpy.run_path(str(STATUS))
        deployments = {"deployments": [
            {"staged": True, "version": "44.3", "timestamp": 300},
            {"booted": True, "version": "44.2", "timestamp": 200,
             "container-image-reference": "ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos:latest"},
            {"version": "44.1", "timestamp": 100},
        ]}
        probe = scope["deployment_state"]
        with patch.dict(probe.__globals__, command=lambda *a, **kw: json.dumps(deployments)):
            state = probe()
        self.assertEqual((state["previousVersion"], state["previousBuiltAt"]), ("44.1", 100))
        with patch.dict(probe.__globals__, command=lambda *a, **kw: '{"deployments":[{"booted":true}]}'):
            state = probe()
        self.assertEqual((state["previousVersion"], state["previousBuiltAt"]), ("", 0))

    def test_full_state_publishes_the_list(self) -> None:
        state = runpy.run_path(str(STATUS))["full_state"]()
        self.assertEqual([entry["id"] for entry in state["whatsNew"]["entries"]],
                         [entry["id"] for entry in shipped()])


class TheNotificationSpeaksOnce(unittest.TestCase):
    def test_the_message_is_one_language_and_counts_like_that_language(self) -> None:
        module = runpy.run_path(str(NOTIFIER))
        fresh = [{"title": {"ar": f"عنوان {n}", "en": f"Title {n}"}} for n in range(1, 12)]
        for count, arabic in ((1, "تغيير واحد جديد"), (2, "تغييران جديدان"),
                              (5, "5 تغييرات جديدة"), (11, "11 تغييرًا جديدًا")):
            title, body, action = module["message"]("44.20260918.870", fresh[:count], "ar")
            self.assertEqual((title, action), ("تم تحديث MoOS", "ما الجديد"))
            self.assertIn(arabic, body)
            self.assertTrue(body.startswith("\u200f"), "a sentence that starts with a version stays right-to-left")
            self.assertNotIn("Title", body)
        title, body, action = module["message"]("44.20260918.870", fresh[:5], "en")
        self.assertEqual((title, action), ("MoOS was updated", "What's new"))
        self.assertIn("5 new things. Title 1, Title 2, Title 3…", body)
        self.assertNotRegex(title + body + action, ARABIC)
        self.assertIn("1 new thing.", module["message"]("44.1", fresh[:1], "en")[1])

    def test_it_is_started_with_the_session_and_nowhere_in_a_menu(self) -> None:
        entry = AUTOSTART.read_text(encoding="utf-8")
        self.assertIn("Exec=/usr/libexec/moos-whats-new-notify\n", entry)
        for line in ("OnlyShowIn=KDE;", "NoDisplay=true", "X-KDE-autostart-phase=2", "Name[ar]="):
            self.assertIn(line, entry)
        self.assertTrue(os.access(NOTIFIER, os.X_OK) or sys.platform == "win32",
                        "the notifier must be executable")


@unittest.skipUnless(sys.platform.startswith("linux") and shutil.which("bwrap"),
                     "the end-to-end run needs bubblewrap to supply /ostree/deploy")
class TheNotifierEndToEnd(unittest.TestCase):
    BOOTED_BUILT = 1789700000          # after every shipped entry

    def run_notifier(self, *, returning: bool, previous_built: int | None = W1_BUILT,
                     seen: str = "", sender: str = 'echo open', language: str = "ar_EG.UTF-8"):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            stubs, home = work / "bin", work / "home"
            stubs.mkdir()
            (home / ".config").mkdir(parents=True)
            if returning:
                marker = home / ".config/moos-firstrun-done"
                marker.touch()
                os.utime(marker, (86400, 86400))
            if seen:
                (home / ".local/state/moos").mkdir(parents=True)
                (home / ".local/state/moos/whats-new-seen").write_text(seen + "\n")
            deployments = [{"booted": True, "version": "44.20260918.870", "timestamp": self.BOOTED_BUILT}]
            if previous_built is not None:
                deployments.append({"version": "44.20260916.848", "timestamp": previous_built})
            (work / "status.json").write_text(json.dumps({"deployments": deployments}))

            def stub(name: str, body: str) -> None:
                path = stubs / name
                path.write_text("#!/bin/sh\n" + textwrap.dedent(body).strip() + "\n")
                path.chmod(0o755)
            stub("rpm-ostree", f'cat "{work}/status.json"')
            stub("notify-send", f"""
                for argument in "$@"; do printf '%s\\n' "$argument"; done >> "{work}/sent"
                {sender}
            """)
            stub("moos-open", f'echo "$@" >> "{work}/opened"')

            command = ["bwrap", "--ro-bind", "/usr", "/usr", "--ro-bind", "/etc", "/etc",
                       "--symlink", "usr/bin", "/bin", "--symlink", "usr/lib", "/lib",
                       "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/sbin", "/sbin",
                       "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                       "--dir", "/ostree/deploy",
                       "--bind", str(work), str(work), "--ro-bind", str(ROOT), str(ROOT),
                       "--setenv", "PATH", f"{stubs}:/usr/bin:/bin", "--setenv", "HOME", str(home),
                       "--setenv", "LC_ALL", language, "--unsetenv", "XDG_STATE_HOME",
                       "--unsetenv", "XDG_CONFIG_HOME",
                       sys.executable if sys.executable.startswith("/usr/") else "/usr/bin/python3",
                       str(NOTIFIER)]
            done = subprocess.run(command, text=True, capture_output=True, timeout=60, check=False)
            if done.returncode != 0 and re.search(
                    r"bwrap: .*(namespace|Operation not permitted|Permission denied|setting up uid map)",
                    done.stderr):
                self.skipTest("this kernel forbids unprivileged user namespaces")
            self.assertEqual(done.returncode, 0, done.stderr)

            def read(name: str) -> str:
                path = work / name
                return path.read_text(encoding="utf-8") if path.exists() else ""
            recorded = home / ".local/state/moos/whats-new-seen"
            # moos-open is started detached; give it a moment to write.
            for _ in range(20):
                if read("opened") or "echo open" not in sender:
                    break
                time.sleep(0.05)
            return read("sent"), read("opened").strip(), (
                recorded.read_text(encoding="utf-8").strip() if recorded.exists() else "")

    def test_a_returning_user_is_told_once_and_taken_to_the_page(self) -> None:
        sent, opened, recorded = self.run_notifier(returning=True)
        self.assertIn("تم تحديث MoOS", sent)
        self.assertIn("--action=open=ما الجديد", sent)
        self.assertIn("44.20260918.870", sent)
        self.assertIn(f"{len(shipped())} ", sent, "every shipped entry is newer than the W1 image")
        self.assertEqual(opened, "moos://settings/whats-new")
        self.assertEqual(recorded, "44.20260918.870")

    def test_the_same_version_is_never_announced_twice(self) -> None:
        sent, opened, _ = self.run_notifier(returning=True, seen="44.20260918.870")
        self.assertEqual((sent, opened), ("", ""))

    def test_a_new_user_is_not_told_about_an_update_that_never_happened_to_them(self) -> None:
        sent, _, recorded = self.run_notifier(returning=False)
        self.assertEqual(sent, "")
        self.assertEqual(recorded, "44.20260918.870", "their version is recorded so the NEXT update speaks")

    def test_an_update_that_brought_nothing_visible_says_nothing(self) -> None:
        for previous in (self.BOOTED_BUILT - 1, None):
            sent, _, recorded = self.run_notifier(returning=True, previous_built=previous, seen="44.1")
            self.assertEqual(sent, "", previous)
            self.assertEqual(recorded, "44.20260918.870")

    def test_a_message_that_did_not_go_out_is_retried_next_login(self) -> None:
        sent, opened, recorded = self.run_notifier(returning=True, seen="44.1", sender="exit 1")
        self.assertIn("MoOS", sent)
        self.assertEqual((opened, recorded), ("", "44.1"))

    def test_dismissing_it_opens_nothing(self) -> None:
        sent, opened, recorded = self.run_notifier(returning=True, sender="exit 0", language="en_US.UTF-8")
        self.assertIn("MoOS was updated", sent)
        self.assertIn("--action=open=What's new", sent)
        self.assertEqual((opened, recorded), ("", "44.20260918.870"))


if __name__ == "__main__":
    unittest.main()
