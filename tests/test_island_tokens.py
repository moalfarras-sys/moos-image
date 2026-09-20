#!/usr/bin/env python3
"""Gate: what the MoOS Island shows about Store jobs and privacy really reaches plasmashell.

WHY THIS EXISTS

Wave W5 (PR #111) gave the Island Store jobs and camera/microphone/screen-share chips. Both read
their state with `new XMLHttpRequest()` on a local file. Qt 6 refuses that unless the process
exports QML_XHR_ALLOW_FILE_READ=1 — measured on the image's own Qt 6.11.2:

    XMLHttpRequest: Using GET on a local file is disabled by default.   -> Error: Invalid state

The Store and Welcome launchers export it; plasmashell does not. Both reads sat inside
`try { … } catch (e) {}`, so:

  * Store jobs NEVER appeared in the Island on any machine;
  * the privacy chip always said "Application", and named Mo PC Remote as the owner of every
    screen share, including a browser meeting;
  * a removal would have been shown as an install ("uninstall" was compared with a backend that
    says "remove"), and `run`, `refresh-index` and `open-engine` as installs too.

Every gate was green, because the W5 test asserts that strings such as `id: storeJobPresence`
exist. The wave was promoted to ARM.

The Island's Remote chip has always worked, and it never reads a file: its state IS a file name
(`presence-active-2`) reported by a FolderListModel. Store jobs and privacy now use that proven
mechanism, and this gate checks the contract from BOTH ends with real code:

  producer  moos-storectl's JobStore and moos-privacy-monitor write real token files here;
  consumer  the shipped IslandTokens.js is executed in node on those exact names;
  shell     the Island may not construct an XMLHttpRequest at all.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISLAND = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui"
TOKENS_JS = ISLAND / "IslandTokens.js"
STORECTL = ROOT / "system_files/usr/bin/moos-storectl"
MONITOR = ROOT / "system_files/usr/libexec/moos-privacy-monitor"


def load(path: Path, name: str):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def island(expression: str):
    """Evaluate *expression* against the shipped IslandTokens.js in node; returns parsed JSON."""
    source = TOKENS_JS.read_text(encoding="utf-8").replace(".pragma library", "")
    script = source + f"\nprocess.stdout.write(JSON.stringify({expression}));\n"
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                          encoding="utf-8", check=True)
    return json.loads(done.stdout)


@unittest.skipUnless(shutil.which("node"), "node is needed to execute the shipped IslandTokens.js")
class StoreJobsReachTheIsland(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storectl = load(STORECTL, "moos_storectl_under_test")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runtime = Path(self.tmp.name) / "run"
        self.runtime.mkdir()
        self.old_runtime = os.environ.get("XDG_RUNTIME_DIR")
        os.environ["XDG_RUNTIME_DIR"] = str(self.runtime)
        self.store = self.storectl.JobStore(Path(self.tmp.name) / "cache")
        self.store.prepare()

    def tearDown(self):
        if self.old_runtime is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = self.old_runtime
        self.tmp.cleanup()

    def tokens(self) -> list[str]:
        directory = self.runtime / "moos-store"
        return sorted(p.name for p in directory.glob("job-*")) if directory.is_dir() else []

    def test_an_install_is_visible_from_start_to_finish(self):
        job = self.storectl.Job(self.store, "install", ["org.mozilla.firefox"])
        self.assertEqual(len(self.tokens()), 1, "a starting job published no presence token")
        seen = island(f"chooseStoreToken({json.dumps(self.tokens())})")
        self.assertEqual((seen["action"], seen["state"], seen["active"], seen["progress"]),
                         ("install", "starting", True, None))
        self.assertEqual(seen["name"], "Firefox", "the Island must show a name, not a reverse-DNS id")

        job.update(state="running", progress=43, current_id="org.mozilla.firefox", message="x")
        self.assertEqual(len(self.tokens()), 1, "the previous token must be replaced, not kept")
        seen = island(f"chooseStoreToken({json.dumps(self.tokens())})")
        self.assertEqual((seen["state"], seen["progress"], seen["id"]),
                         ("running", 40, "org.mozilla.firefox"))

        job.update(state="success", progress=100, current_id=None, message="Done")
        seen = island(f"chooseStoreToken({json.dumps(self.tokens())})")
        self.assertEqual((seen["state"], seen["active"], seen["finished"]), ("success", False, True))

    def test_a_removal_is_a_removal(self):
        self.storectl.Job(self.store, "remove", ["com.usebottles.bottles"])
        seen = island(f"chooseStoreToken({json.dumps(self.tokens())})")
        self.assertEqual((seen["action"], seen["name"]), ("remove", "Bottles"))

    def test_opening_running_or_indexing_is_never_shown_as_an_install(self):
        for action in ("run", "refresh-index", "open-engine"):
            with self.subTest(action=action):
                self.storectl.Job(self.store, action, ["org.example.App"])
                self.assertEqual(self.tokens(), [],
                                 f"`{action}` is not work a person waits for; W5 showed it as "
                                 "\"Installing …\"")

    def test_progress_moves_in_steps_so_the_shell_is_not_woken_per_percent(self):
        job = self.storectl.Job(self.store, "update", [])
        names = set()
        for percent in range(0, 101):
            job.update(state="running", progress=percent, message="x")
            names.update(self.tokens())
        self.assertLessEqual(len(names), 23, f"{len(names)} renames for one job is a wake-up storm")

    def test_a_hostile_id_cannot_forge_fields_or_escape_the_directory(self):
        evil = "evil-success-100-../../x y"
        job = self.storectl.Job(self.store, "install", [evil])
        job.update(state="running", progress=10, current_id=evil, message="x")
        names = self.tokens()
        self.assertEqual(len(names), 1)
        self.assertNotIn("/", names[0])
        self.assertEqual(names[0].count("-"), 4, "a '-' inside the id must not create a field")
        seen = island(f"chooseStoreToken({json.dumps(names)})")
        self.assertEqual((seen["state"], seen["progress"], seen["id"]), ("running", 10, evil))

    def test_a_view_can_never_fail_a_transaction(self):
        os.environ["XDG_RUNTIME_DIR"] = str(Path(self.tmp.name) / "missing" / "deeper")
        blocker = Path(self.tmp.name) / "missing"
        blocker.write_text("a file where a directory is expected", encoding="utf-8")
        job = self.storectl.Job(self.store, "install", ["org.example.App"])   # must not raise
        job.update(state="running", progress=5, message="x")
        self.assertTrue(self.store.path.is_file(), "job.json must still be written")
        os.environ.pop("XDG_RUNTIME_DIR")
        self.storectl.Job(self.store, "install", ["org.example.App"])          # no runtime dir


@unittest.skipUnless(shutil.which("node"), "node is needed to execute the shipped IslandTokens.js")
class PrivacyChipsNameTheRealApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.monitor = load(MONITOR, "moos_privacy_monitor_under_test")

    def test_the_app_name_travels_in_the_token_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            self.monitor.write_tokens([
                {"type": "mic", "app": "Telegram", "node_id": 61},
                {"type": "camera", "app": "متصفّح - الويب", "node_id": 57},
                {"type": "screen", "app": "Firefox", "node_id": 70},
            ], target)
            names = sorted(p.name for p in target.glob("active-*"))
            self.assertEqual(len(names), 3)
            best = island(f"choosePrivacyToken({json.dumps(names)})")
            self.assertEqual((best["type"], best["nodeId"], best["app"]), ("screen", "70", "Firefox"),
                             "screen sharing outranks camera and microphone, and names its app")
            camera = island(f"parsePrivacyToken({json.dumps([n for n in names if 'camera' in n][0])})")
            self.assertEqual(camera["app"], "متصفّح - الويب", "an Arabic name with a '-' must survive")
            # A stream that ended must leave: the chip is a privacy promise.
            self.monitor.write_tokens([], target)
            self.assertEqual(list(target.glob("active-*")), [])

    def test_an_unnamed_stream_is_not_blamed_on_mo_pc_remote(self):
        self.assertEqual(self.monitor.sanitize_app_name("", None), "")
        self.assertEqual(self.monitor.sanitize_app_name("kwin_wayland", None), "",
                         "the compositor is the source of a cast, never the app watching it")
        with tempfile.TemporaryDirectory() as tmp:
            self.monitor.write_tokens([{"type": "screen", "app": "", "node_id": 9}], Path(tmp))
            name = next(Path(tmp).glob("active-*")).name
            self.assertEqual(name, "active-screen-9")
            self.assertEqual(island(f"parsePrivacyToken({json.dumps(name)})")["app"], "")

    def test_one_dump_carries_nodes_links_and_clients(self):
        dump = [{"type": "PipeWire:Interface:Node", "id": 1}, {"type": "PipeWire:Interface:Link", "id": 2},
                {"type": "PipeWire:Interface:Client", "id": 3}, {"type": "PipeWire:Interface:Module", "id": 4},
                "not an object"]
        nodes, links, clients = self.monitor.partition_dump(dump)
        self.assertEqual(([n["id"] for n in nodes], [l["id"] for l in links], [c["id"] for c in clients]),
                         ([1], [2], [3]))
        source = MONITOR.read_text(encoding="utf-8")
        self.assertEqual(source.count('["pw-dump"'), 1,
                         "one pw-dump per round: three filtered dumps cost 12 ms against 4 ms "
                         "(pipewire 1.6.8), every 1.5 s, for the whole session")


class TheShellNeverReadsALocalFile(unittest.TestCase):
    def test_no_plasmoid_constructs_an_xmlhttprequest_on_a_file(self):
        plasmoids = ROOT / "system_files/usr/share/plasma/plasmoids"
        for path in sorted(plasmoids.glob("org.moos.*/**/*.qml")) + sorted(plasmoids.glob("org.moos.*/**/*.js")):
            code = "\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                             if not l.lstrip().startswith("//"))
            if "new XMLHttpRequest" in code and ("file:" in code or "FileUrl(" in code):
                self.fail(f"{path.relative_to(ROOT).as_posix()} reads a local file through "
                          "XMLHttpRequest. plasmashell's Qt refuses it (no QML_XHR_ALLOW_FILE_READ), "
                          "and inside a try/catch that is a feature that silently never works. "
                          "Carry the state in a file NAME and read it with a FolderListModel.")

    def test_the_island_uses_the_token_library_for_both_domains(self):
        qml = (ISLAND / "main.qml").read_text(encoding="utf-8")
        self.assertIn('import "IslandTokens.js" as IslandTokens', qml)
        self.assertIn("IslandTokens.chooseStoreToken(", qml)
        self.assertIn("IslandTokens.choosePrivacyToken(", qml)
        self.assertIn('folder: root.runtimeFileUrl("moos-store")', qml)


class TheCapsuleFitsWhatItSays(unittest.TestCase):
    def test_the_width_is_one_invariant_for_every_context(self):
        """Changing activity must not move the Horizon Bar's task targets."""
        qml = (ISLAND / "main.qml").read_text(encoding="utf-8")
        code = "\n".join(l for l in qml.splitlines() if not l.lstrip().startswith("//"))
        self.assertIn("readonly property real stableWidth:", code)
        for owner in ("implicitWidth: stableWidth", "Layout.minimumWidth: stableWidth",
                      "Layout.preferredWidth: stableWidth", "Layout.maximumWidth: stableWidth"):
            self.assertIn(owner, code)
        self.assertRegex(code, r"stableWidth:\s*Math\.round\(Kirigami\.Units\.gridUnit \* 9\.5\)")
        self.assertGreaterEqual(code.count("slotSize: 34"), 4,
                                "compact actions must stay inside the narrower frame")
        self.assertIn("readonly property bool roomForSource: root.active", code,
                      "idle Search is one clean line, not a miniature form")
        for forbidden in ("Behavior on implicitWidth", "contextTitle.length *", "baseWidth:",
                          "hoverExtra", "chipWidth"):
            self.assertNotIn(forbidden, code)


if __name__ == "__main__":
    unittest.main(verbosity=2)
