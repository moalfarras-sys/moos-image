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

Mo AI jobs (THEME_REV 86) use the same mechanism: moai-control names one token per confirmed job
`job-<id8hex>-<running|done|failed>-<tool>` in $XDG_RUNTIME_DIR/moai-jobs and RENAMES it as the
job moves. A same-count rename changes no count: Qt 6.11's FolderListModel reports it as
dataChanged plus a Loading -> Ready status cycle (measured), so a model that synced on count alone
would freeze on "running". The producer end below writes the contract's names into a real
directory; when a Qt runtime is present, a real FolderListModel wired like the Island's watches
that directory and the shipped parser reads it.

Two traps the review of THEME_REV 86 measured, both invisible to a fixture that set the stage:

  * A FolderListModel started on a folder that does not exist yet never notices it appear, and
    every producer creates its folder lazily, hours after plasmashell loaded the Island. The
    folders are therefore created at login by usr/share/user-tmpfiles.d/moos-island.conf; the
    real-model probe starts BEFORE the first job, in a runtime directory that conf prepared.
  * The directory also holds tokens of jobs that ended earlier. The chip announces only the end
    of a job the Island watched run, never a leftover failure for a retry that succeeded.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ISLAND = ROOT / "system_files/usr/share/plasma/plasmoids/org.moos.island/contents/ui"
TOKENS_JS = ISLAND / "IslandTokens.js"
STORECTL = ROOT / "system_files/usr/bin/moos-storectl"
MONITOR = ROOT / "system_files/usr/libexec/moos-privacy-monitor"
SCHEMAS = ROOT / "system_files/usr/lib/moai/moai_tool_schemas.py"
MOOS_OPEN = ROOT / "system_files/usr/bin/moos-open"
# Creates every folder the Island watches at login, before plasmashell (review of rev 86).
TMPFILES = ROOT / "system_files/usr/share/user-tmpfiles.d/moos-island.conf"
QML_RUNTIME = next((name for name in ("qml6", "qml-qt6", "qml", "moos-qml-shell")
                    if shutil.which(name)), None)


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


class MoaiJobs:
    """The producer contract of spec D6, written into a real runtime directory.

    Like moai-control's _publish_job_token, the folder is created LAZILY, by the first job. An
    earlier version of this fixture created it up front, and so hid that a FolderListModel started
    on a missing folder never notices it appear (see IslandFoldersExistBeforeTheShell)."""

    def __init__(self, runtime: Path):
        self.directory = runtime / "moai-jobs"

    def start(self, job_id: str, tool: str) -> Path:
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        token = self.directory / f"job-{job_id}-running-{tool}"
        token.touch()
        return token

    def finish(self, job_id: str, tool: str, state: str) -> Path:
        old = self.directory / f"job-{job_id}-running-{tool}"
        new = self.directory / f"job-{job_id}-{state}-{tool}"
        os.rename(old, new)                       # a rename: the count does not change
        return new

    def names(self) -> list[str]:
        return sorted(p.name for p in self.directory.glob("job-*"))


def island_session(snapshots: list[list[str]]) -> list[str | None]:
    """Replay directory snapshots through the shipped library exactly as the Island's syncMoaiJob
    does: each call receives the previous call's runningIds. Returns what each sync would show."""
    return island(
        "(function () { var watched = []; return " + json.dumps(snapshots) + ".map("
        "function (names) { var job = chooseMoaiJobToken(names, watched);"
        " watched = job ? job.runningIds : [];"
        " return job ? job.state + ':' + job.id + ':' + job.tool : null; }); })()")


def schema_tools():
    spec = importlib.util.spec_from_file_location("moai_tool_schemas_under_island_test", SCHEMAS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(shutil.which("node"), "node is needed to execute the shipped IslandTokens.js")
class MoaiJobsReachTheIsland(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs = MoaiJobs(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_confirmed_job_is_visible_from_start_to_finish(self):
        self.jobs.start("0a1b2c3d", "install_app")
        seen = island(f"chooseMoaiJobToken({json.dumps(self.jobs.names())}, [])")
        self.assertEqual((seen["id"], seen["state"], seen["tool"], seen["active"], seen["running"],
                          seen["runningIds"]),
                         ("0a1b2c3d", "running", "install_app", True, 1, ["0a1b2c3d"]))
        self.jobs.finish("0a1b2c3d", "install_app", "done")
        self.assertEqual(len(self.jobs.names()), 1, "a rename keeps one token")
        seen = island(f"chooseMoaiJobToken({json.dumps(self.jobs.names())}, "
                      f"{json.dumps(seen['runningIds'])})")
        self.assertEqual((seen["state"], seen["active"], seen["finished"], seen["running"],
                          seen["runningIds"]),
                         ("done", False, True, 0, []))

    def test_a_running_job_outranks_a_finished_one_and_is_counted(self):
        self.jobs.start("00000001", "update_apps")
        self.jobs.finish("00000001", "update_apps", "failed")
        self.jobs.start("00000002", "fix_audio")
        self.jobs.start("00000003", "system_update")
        seen = island(f"chooseMoaiJobToken({json.dumps(self.jobs.names())}, ['00000001'])")
        self.assertTrue(seen["active"], "work in progress outranks a finished job")
        self.assertEqual(seen["running"], 2)
        self.assertEqual(seen["runningIds"], ["00000002", "00000003"])
        self.assertEqual(seen["id"], "00000003", "ties resolve the same way on every render")
        # Two watched jobs that ended together: the failure is the one that needs the person.
        other = island('chooseMoaiJobToken(["job-000000aa-done-fix_audio",'
                       ' "job-00000001-failed-update_apps"], ["000000aa", "00000001"])')
        self.assertEqual((other["state"], other["tool"]), ("failed", "update_apps"))

    def test_a_lingering_token_never_speaks_for_the_job_that_ended(self):
        # Review of THEME_REV 86, measured on the station: C's confirmation-flow test left
        # *-failed-fix_audio and *-done-optimize_system tokens in the owner's runtime directory.
        # Chosen among ALL finished tokens, the next successful job would have read "failed".
        stale_failure = "job-0000000b-failed-fix_audio"
        self.assertEqual(island_session([
            [stale_failure],                                          # before any job: quiet
            [stale_failure, "job-0000000a-running-fix_audio"],        # the retry runs
            [stale_failure, "job-0000000a-done-fix_audio"],           # ... and succeeds
            [stale_failure, "job-0000000a-done-fix_audio"],           # the model re-reports
        ]), [None, "running:0000000a:fix_audio", "done:0000000a:fix_audio", None])
        # The same with a different tool: the chip names the action that ran, not a leftover.
        self.assertEqual(island_session([
            ["job-ffffffff-done-install_app", "job-0000000a-running-fix_audio"],
            ["job-ffffffff-done-install_app", "job-0000000a-done-fix_audio"],
        ]), ["running:0000000a:fix_audio", "done:0000000a:fix_audio"])
        # The reviewer's direct calls, now with what the Island watched.
        seen = island(f'chooseMoaiJobToken(["{stale_failure}", "job-0000000a-done-fix_audio"],'
                      ' ["0000000a"])')
        self.assertEqual((seen["id"], seen["state"]), ("0000000a", "done"))
        self.assertIsNone(island(f'chooseMoaiJobToken(["{stale_failure}"], [])'),
                          "a job this Island never saw run is never announced")
        self.assertIsNone(island(f'chooseMoaiJobToken(["{stale_failure}"])'),
                          "without a watched list nothing finished is announced")

    def test_parallel_jobs_announce_the_one_that_ended_last(self):
        self.assertEqual(island_session([
            ["job-00000001-running-update_apps", "job-00000002-running-fix_audio"],
            # 1 ends while 2 still runs: the chip keeps showing the work in progress ...
            ["job-00000001-done-update_apps", "job-00000002-running-fix_audio"],
            # ... and when 2 ends, it is 2 that is announced — 1's lingering success is old news.
            ["job-00000001-done-update_apps", "job-00000002-failed-fix_audio"],
        ]), ["running:00000002:fix_audio", "running:00000002:fix_audio",
             "failed:00000002:fix_audio"])

    def test_an_ended_token_older_than_its_linger_is_old_news(self):
        """Done/failed tokens older than 20 s are ignored; running ones never age out."""
        now = 1_800_000_000_000
        entries = [
            {"name": "job-00000001-done-update_apps", "modified": now - 21_000},
            {"name": "job-00000002-failed-fix_audio", "modified": now - 19_000},
            {"name": "job-00000003-running-system_update", "modified": now - 3_600_000},
            {"name": "job-00000004-done-install_app", "modified": "not a time"},
            {"name": "job-00000005-failed-install_app"},
            {"name": "job-00000006-done-optimize_system", "modified": now - 20_000},
            {"name": "presence-active-1", "modified": now},
        ]
        self.assertEqual(island(f"recentMoaiJobNames({json.dumps(entries)}, {now})"),
                         ["job-00000002-failed-fix_audio", "job-00000003-running-system_update",
                          "job-00000006-done-optimize_system"])
        # A Date, as FolderListModel's fileModified is, reads the same as milliseconds.
        self.assertEqual(island("recentMoaiJobNames([{name: 'job-00000001-done-fix_audio', "
                                f"modified: new Date({now - 25_000})}}], {now})"), [])
        self.assertEqual(island("MOAI_JOB_LINGER_MS"), 20_000,
                         "the Island's linger must equal moai-control's JOB_TOKEN_LINGER")
        # Even a job the Island watched run is not announced from a token that aged out.
        stale = [{"name": "job-00000001-done-update_apps", "modified": now - 60_000}]
        self.assertIsNone(island(f"chooseMoaiJobToken(recentMoaiJobNames({json.dumps(stale)}, "
                                 f"{now}), ['00000001'])"))

    def test_the_island_ages_tokens_by_the_models_file_time(self):
        qml = "\n".join(l for l in (ISLAND / "main.qml").read_text(encoding="utf-8").splitlines()
                        if not l.lstrip().startswith("//"))
        sync = qml.split("function syncMoaiJob() {", 1)[1].split("\n    }\n", 1)[0]
        read = 'moaiJobPresence.get(i, "fileModified")'
        age = "IslandTokens.recentMoaiJobNames(entries, Date.now());"
        self.assertIn(read, sync, "the age must come from the model, never from reading a file")
        self.assertIn(age, sync)
        self.assertLess(sync.index(age), sync.index("IslandTokens.chooseMoaiJobToken("))
        control = (ROOT / "system_files/usr/bin/moai-control").read_text(encoding="utf-8")
        self.assertIn("JOB_TOKEN_LINGER = 20.0", control,
                      "the producer's linger changed: keep MOAI_JOB_LINGER_MS equal to it")

    def test_the_island_feeds_back_what_it_watched(self):
        qml = "\n".join(l for l in (ISLAND / "main.qml").read_text(encoding="utf-8").splitlines()
                        if not l.lstrip().startswith("//"))
        sync = qml.split("function syncMoaiJob() {", 1)[1].split("\n    }\n", 1)[0]
        call = "IslandTokens.chooseMoaiJobToken(names, root.moaiWatchedJobs);"
        feed = "root.moaiWatchedJobs = job ? job.runningIds : [];"
        self.assertIn("property var moaiWatchedJobs: []", qml)
        self.assertIn(call, sync, "the Island must tell the library which jobs it watched run")
        self.assertIn(feed, sync, "... and remember the ones running now for the next sync")
        self.assertLess(sync.index(call), sync.index(feed))
        self.assertLess(sync.index(feed), sync.index("if (!job)"),
                        "the watched list must be updated on every sync, including an empty one")

    def test_a_name_outside_the_contract_is_never_shown(self):
        for name in ("job-0a1b2c3d-running-install_app-extra",   # a smuggled field
                     "job-0A1B2C3D-running-install_app",         # the id is lowercase hex
                     "job-0a1b2c3-running-install_app",          # and exactly eight digits
                     "job-0a1b2c3d-success-install_app",         # an unknown state
                     "job-0a1b2c3d-running-Install_App",         # the tool is [a-z_]
                     "job-0a1b2c3d-running-" + "a" * 41,         # of at most 40 characters
                     "job-0a1b2c3d-running-",
                     "job-0a1b2c3d-running-../../x",
                     "presence-active-1", "", "job-"):
            with self.subTest(name=name):
                self.assertIsNone(island(f"parseMoaiJobToken({json.dumps(name)})"))
        self.assertIsNone(island('chooseMoaiJobToken(["job-zz-running-x", "active-mic-3"])'))

    def test_every_confirmed_tool_has_words_in_both_languages(self):
        schemas = schema_tools()
        confirmed = sorted(schemas.CONFIRM_NAMES)
        self.assertTrue(confirmed, "the schema module no longer lists confirmed tools")
        labels = island("MOAI_JOB_LABELS")
        missing = [tool for tool in confirmed if tool not in labels]
        self.assertEqual(missing, [], "a confirmed Mo AI job the Island can only call "
                         "\"A Mo AI action\": give it words in IslandTokens.js MOAI_JOB_LABELS")
        known = set(schemas.TOOL_META)
        self.assertEqual(sorted(set(labels) - known), [],
                         "a label for a tool the schema does not declare is dead text")
        for tool, (arabic, english) in labels.items():
            with self.subTest(tool=tool):
                self.assertRegex(arabic, r"[\u0600-\u06ff]", "the Arabic label must be Arabic")
                self.assertRegex(english, r"^[A-Z][A-Za-z ]+$")
        self.assertEqual(island('moaiJobLabel("some_future_tool")'),
                         ["إجراء من Mo AI", "A Mo AI action"])

    def test_the_island_watches_the_directory_and_opens_mo_ai(self):
        qml = "\n".join(l for l in (ISLAND / "main.qml").read_text(encoding="utf-8").splitlines()
                        if not l.lstrip().startswith("//"))
        model = qml.split("id: moaiJobPresence", 1)[1].split("\n    }\n", 1)[0]
        self.assertIn('folder: root.runtimeFileUrl("moai-jobs")', model)
        self.assertIn('nameFilters: ["job-*"]', model)
        self.assertIn("onCountChanged: root.syncMoaiJob()", model)
        self.assertIn("onDataChanged: root.syncMoaiJob()", model,
                      "the producer RENAMES its token; a rename changes no count")
        self.assertIn("root.syncMoaiJob();", model.split("onStatusChanged:", 1)[1])
        self.assertIn("IslandTokens.chooseMoaiJobToken(", qml)
        self.assertIn('Qt.openUrlExternally("moos://app/moai")', qml)
        self.assertRegex(MOOS_OPEN.read_text(encoding="utf-8"), r"(?m)^\s*app/moai\)")
        # Below Remote, privacy and the Store; above media.
        active = qml.split("readonly property bool active:", 1)[1].split("releaseGrace.running", 1)[0]
        order = [active.index(name) for name in ("root.remotePresent", "root.privacyPresent",
                                                 "root.storeJobPresent", "root.moaiJobPresent",
                                                 "root.mediaPresent")]
        self.assertEqual(order, sorted(order), "Mo AI jobs rank below Remote, privacy and Store")
        title = qml.split("readonly property string contextTitle:", 1)[1].split("readonly property", 1)[0]
        self.assertLess(title.index("root.storeJobTitle"), title.index("root.moaiJobTitle"))
        self.assertLess(title.index("root.moaiJobTitle"), title.index("root.displayTrack"))

    def test_every_token_model_reacts_to_a_rename(self):
        qml = (ISLAND / "main.qml").read_text(encoding="utf-8")
        models = qml.split("FolderListModel {")[1:]
        self.assertGreaterEqual(len(models), 4, "remote, privacy, Store and Mo AI presence")
        for block in models:
            block = block.split("\n    }\n", 1)[0]
            model_id = re.search(r"id:\s*(\w+)", block).group(1)
            with self.subTest(model=model_id):
                for handler in ("onCountChanged:", "onDataChanged:",
                                "onStatusChanged: if (status === FolderListModel.Ready)"):
                    self.assertIn(handler, block,
                                  f"{model_id} must sync on count, data and status: a "
                                  "same-count rename (running -> done, active -> paused) "
                                  "changes no count")


def island_folders() -> list[str]:
    """Every runtime folder a FolderListModel in the Island watches, read from the shipped QML."""
    qml = (ISLAND / "main.qml").read_text(encoding="utf-8")
    return sorted(re.findall(r'folder:\s*root\.runtimeFileUrl\("([a-z-]+)"\)', qml))


def prepare_runtime(runtime: Path, conf: Path = TMPFILES) -> None:
    """What the user manager's systemd-tmpfiles-setup.service does at login, with the shipped
    conf, into a private runtime directory (%t resolves to XDG_RUNTIME_DIR under --user)."""
    runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(runtime.parent / "home"),
           "XDG_RUNTIME_DIR": str(runtime),
           "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime.parent / 'no-bus'}"}
    subprocess.run(["systemd-tmpfiles", "--user", "--create", str(conf)], env=env, check=True,
                   capture_output=True, text=True, timeout=60)


class IslandFoldersExistBeforeTheShell(unittest.TestCase):
    """Review of THEME_REV 86: a FolderListModel started on a MISSING folder goes to status Null,
    installs no watch and never notices the folder appear (measured with moos-qml-shell: folder
    and token created 1.5 s after start, nothing seen after 4 s; created before start, seen).
    Every producer creates its folder lazily, long after plasmashell loaded the Island, so a
    user-tmpfiles.d entry creates each watched folder at login, before the shell starts."""

    LINE = re.compile(r"^d\s+%t/([a-z-]+)\s+0700\s+-\s+-\s+-(?:\s+-)?\s*$")

    def declared(self) -> list[str]:
        folders = []
        for line in TMPFILES.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            match = self.LINE.match(line)
            self.assertIsNotNone(match, f"{TMPFILES.name}: only private 'd %t/<folder>' lines "
                                 f"belong here, got {line!r}")
            folders.append(match.group(1))
        return folders

    def test_every_watched_folder_is_created_at_login(self):
        watched = island_folders()
        self.assertEqual(watched, ["mo-remote", "moai-jobs", "moos-privacy", "moos-store"],
                         "the Island's FolderListModels changed: review this gate")
        declared = self.declared()
        self.assertEqual(len(declared), len(set(declared)), "a folder is declared twice")
        self.assertEqual(sorted(declared), watched,
                         "every folder the Island watches must exist before plasmashell starts "
                         "(and a declared folder the Island does not watch is dead)")

    @unittest.skipUnless(shutil.which("systemd-tmpfiles"), "systemd-tmpfiles is not installed")
    def test_the_shipped_conf_creates_private_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "run"
            runtime.mkdir(mode=0o700)
            (runtime / "moos-privacy").mkdir(mode=0o755)     # what moos-privacy-monitor makes
            prepare_runtime(runtime)
            for folder in island_folders():
                with self.subTest(folder=folder):
                    path = runtime / folder
                    self.assertTrue(path.is_dir())
                    self.assertEqual(path.stat().st_mode & 0o777, 0o700,
                                     "presence tokens name apps and actions: owner only")


class ProbeOutput:
    """Lines the QML probe prints, readable with a deadline (the probe reports, the test acts)."""

    def __init__(self, stream):
        self.queue: queue.Queue = queue.Queue()
        self.seen: list[str] = []
        self.thread = threading.Thread(target=self.pump, args=(stream,), daemon=True)
        self.thread.start()

    def pump(self, stream) -> None:
        for line in stream:
            self.queue.put(line.rstrip("\n"))
        self.queue.put(None)

    def wait_for(self, needle: str, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                line = self.queue.get(timeout=remaining)
            except queue.Empty:
                return False
            if line is None:
                return False
            self.seen.append(line)
            if needle in line:
                return True
        return False


@unittest.skipUnless(QML_RUNTIME and shutil.which("systemd-tmpfiles"),
                     "a Qt QML runtime and systemd-tmpfiles are needed to run a real "
                     "FolderListModel in a login-prepared runtime directory")
class ARealFolderListModelSeesTheRename(unittest.TestCase):
    """The consumer half with Qt itself, in the order a real session has: the runtime directory is
    prepared at login by the shipped user-tmpfiles.d conf, the model starts (plasmashell), and only
    THEN does the producer write its first token and rename it. The probe syncs exactly like the
    Island's syncMoaiJob, feeding back the ids it watched run, and prints every state it shows."""

    PROBE = """
import QtQuick
import Qt.labs.folderlistmodel
import "@TOKENS@" as IslandTokens
Item {
    property var watched: []
    property string shown: ""
    FolderListModel {
        id: jobs
        folder: "@FOLDER@"
        nameFilters: ["job-*"]
        showDirs: false
        onCountChanged: sync()
        onDataChanged: sync()
        onStatusChanged: if (status === FolderListModel.Ready) { sync() }
    }
    function sync() {
        const entries = [];
        for (let i = 0; i < jobs.count; ++i) {
            entries.push({ name: String(jobs.get(i, "fileName")),
                           modified: jobs.get(i, "fileModified") });
        }
        const names = IslandTokens.recentMoaiJobNames(entries, Date.now());
        const job = IslandTokens.chooseMoaiJobToken(names, watched);
        watched = job ? job.runningIds : [];
        const now = job ? job.state + ":" + job.id : "";
        if (now !== shown) { console.warn("probe-state " + (now || "none")); }
        // A job ended (or its chip went away): the Island has said everything this probe
        // measures. Leaving by itself lets dbus-run-session stop its private bus daemon.
        if ((job && !job.active) || (!job && shown !== "")) { finished.restart(); }
        shown = now;
    }
    Component.onCompleted: console.warn("probe-ready")
    Timer { id: finished; interval: 300; onTriggered: Qt.exit(0) }
    Timer { interval: 30000; running: true; onTriggered: Qt.exit(90) }
}
"""

    def run_session(self, before_start=None):
        """Yields (jobs, output) with the probe running; the caller drives the producer."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "home").mkdir()
        prepare_runtime(root / "run")
        jobs = MoaiJobs(root / "run")
        if before_start:
            before_start(jobs)
        probe = root / "probe.qml"
        probe.write_text(self.PROBE.replace("@TOKENS@", TOKENS_JS.as_uri())
                         .replace("@FOLDER@", jobs.directory.as_uri()), encoding="utf-8")
        env = {key: value for key, value in os.environ.items()
               if key not in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
                              "JOURNAL_STREAM", "QT_MESSAGE_PATTERN")}
        env.update({"QT_QPA_PLATFORM": "offscreen", "QT_FORCE_STDERR_LOGGING": "1",
                    "QT_LOGGING_RULES": "js.warning=true;qml.warning=true;default.warning=true",
                    "HOME": str(root / "home"), "XDG_RUNTIME_DIR": str(root / "run"),
                    "XDG_CONFIG_HOME": str(root / "home/.config"),
                    "XDG_CACHE_HOME": str(root / "home/.cache"),
                    "XDG_DATA_HOME": str(root / "home/.local/share")})
        command = ([QML_RUNTIME, "--app-id", "org.moos.island.review", "--qml", str(probe)]
                   if QML_RUNTIME == "moos-qml-shell" else [QML_RUNTIME, str(probe)])
        if shutil.which("dbus-run-session"):
            command = ["dbus-run-session", "--"] + command
        # Its own session: dbus-run-session cannot forward a SIGKILL, so killing only it once
        # orphaned the private dbus-daemon for good (measured: one leaked daemon per probe). The
        # probe normally exits by itself; the process group is the safety net for a red run.
        process = subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)

        def stop():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    break
                time.sleep(0.5)
            process.wait(timeout=30)
            output.thread.join(timeout=5)          # EOF once the whole group is gone
            process.stderr.close()
        output = ProbeOutput(process.stderr)
        self.addCleanup(stop)
        self.assertTrue(output.wait_for("probe-ready", 60),
                        "the QML probe did not start:\n" + "\n".join(output.seen[-20:]))
        return jobs, output

    def test_a_model_started_at_login_sees_the_first_job_and_its_end(self):
        jobs, output = self.run_session()
        jobs.start("0a1b2c3d", "install_app")        # moai-control's first job: mkdir exist_ok
        self.assertTrue(output.wait_for("probe-state running:0a1b2c3d", 10),
                        "the Island never saw the first Mo AI job: its folder did not exist when "
                        "the shell started (usr/share/user-tmpfiles.d/moos-island.conf)\n"
                        + "\n".join(output.seen[-20:]))
        jobs.finish("0a1b2c3d", "install_app", "done")
        self.assertTrue(output.wait_for("probe-state done:0a1b2c3d", 10),
                        "the model missed the same-count running -> done rename\n"
                        + "\n".join(output.seen[-20:]))

    def test_a_lingering_failure_never_speaks_for_a_success(self):
        def stale(jobs: MoaiJobs) -> None:
            jobs.start("0000000b", "fix_audio")
            jobs.finish("0000000b", "fix_audio", "failed")
        jobs, output = self.run_session(before_start=stale)
        jobs.start("0000000a", "fix_audio")
        self.assertTrue(output.wait_for("probe-state running:0000000a", 10),
                        "\n".join(output.seen[-20:]))
        jobs.finish("0000000a", "fix_audio", "done")
        self.assertTrue(output.wait_for("probe-state done:0000000a", 10),
                        "the retry succeeded, but the Island showed another job's end\n"
                        + "\n".join(output.seen[-20:]))
        self.assertFalse([line for line in output.seen if "0000000b" in line],
                         "a failure the Island never watched run was announced")


    def test_a_late_sync_never_announces_an_aged_out_end(self):
        """A real FolderListModel: the job's end arrives with a file time older than the linger
        (the stamp a producer that died long ago left). The chip goes away; nothing is announced."""
        jobs, output = self.run_session()
        running = jobs.start("0c0c0c0c", "update_apps")
        self.assertTrue(output.wait_for("probe-state running:0c0c0c0c", 10),
                        "\n".join(output.seen[-20:]))
        # A running token never ages out; stamping it first makes the rename below carry the old
        # time atomically (a rename keeps the mtime), so the model never sees a fresh "done".
        long_ago = time.time() - 60
        os.utime(running, (long_ago, long_ago))
        jobs.finish("0c0c0c0c", "update_apps", "done")
        self.assertTrue(output.wait_for("probe-state none", 10),
                        "\n".join(output.seen[-20:]))
        self.assertFalse([line for line in output.seen if "done:0c0c0c0c" in line],
                         "an end older than the producer's linger was announced")


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

    def test_the_island_uses_the_token_library_for_every_domain(self):
        qml = (ISLAND / "main.qml").read_text(encoding="utf-8")
        self.assertIn('import "IslandTokens.js" as IslandTokens', qml)
        self.assertIn("IslandTokens.chooseStoreToken(", qml)
        self.assertIn("IslandTokens.choosePrivacyToken(", qml)
        self.assertIn("IslandTokens.chooseMoaiJobToken(", qml)
        self.assertIn('folder: root.runtimeFileUrl("moos-store")', qml)
        self.assertIn('folder: root.runtimeFileUrl("moai-jobs")', qml)


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
