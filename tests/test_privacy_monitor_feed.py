#!/usr/bin/env python3
"""Gate: the privacy monitor follows PipeWire through one live feed, and is still never wrong.

WHAT THIS PREVENTS, MEASURED ON A REAL MACHINE

moos-privacy-monitor asked PipeWire for its whole graph every 1.5 s, for the whole session, on
every machine. On an x86 desktop that measured 0.66% of a core and was left alone. On the Oracle
A1 (2 vCPU), read from the unit's cgroup 61 hours after boot, it had used 52.1 CPU-minutes — more
than the compositor — and spawned about 145,000 processes to learn that nothing had changed.

It also fed a leak that was not its own: every one-shot pw-dump is three registry events for every
other PipeWire client, and Mo PC Remote had left 67 clients that never read theirs.

The monitor now keeps ONE `pw-dump --monitor` running and applies what it prints. That trades a
simple loop for a stream, so the trade has to be gated on both sides:

  * the saving is real — an idle graph causes no dump between resyncs, and a capture is published
    from the feed alone;
  * the chip is still a privacy promise — a stream that ended leaves, a feed that died falls back
    to the poll, a delta that was missed is corrected by the next full read, and text that is not
    JSON cannot grow without bound.

`pw-dump` here is a stand-in on PATH that logs every time it is started. Nothing touches the
session's PipeWire.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONITOR = ROOT / "system_files/usr/libexec/moos-privacy-monitor"

FAKE_PW_DUMP = r'''#!/usr/bin/env python3
"""pw-dump, as far as moos-privacy-monitor can tell."""
import os, sys, time
state = os.environ["FAKE_PW_STATE"]
monitor = "--monitor" in sys.argv
with open(os.path.join(state, "spawns.log"), "a") as log:
    log.write(("monitor" if monitor else "oneshot") + "\n")
out = sys.stdout.buffer
if not monitor:
    with open(os.path.join(state, "graph.json"), "rb") as graph:
        out.write(graph.read())
    sys.exit(0)
with open(os.path.join(state, "graph.json"), "rb") as graph:
    out.write(graph.read())
out.flush()
sent = 0
while True:
    path = os.path.join(state, "delta-%d" % sent)
    if not os.path.exists(path):
        time.sleep(0.01)
        continue
    with open(path, "rb") as delta:
        data = delta.read()
    sent += 1
    if data.startswith(b"EXIT"):
        sys.exit(0)
    if data.startswith(b"SPLIT"):
        # one array in two writes, cut in the middle of a multi-byte character
        body = data[len(b"SPLIT"):]
        cut = body.index("ص".encode()) + 1
        out.write(body[:cut]); out.flush(); time.sleep(0.15)
        out.write(body[cut:]); out.flush()
        continue
    out.write(data); out.flush()
'''

CLIENT = {"id": 40, "type": "PipeWire:Interface:Client",
          "info": {"props": {"application.name": "Telegram"}}}
MIC = {"id": 61, "type": "PipeWire:Interface:Node",
       "info": {"state": "running",
                "props": {"media.class": "Stream/Input/Audio", "client.id": 40}}}
IDLE_GRAPH = [{"id": 0, "type": "PipeWire:Interface:Core", "info": {"props": {}}},
              {"id": 31, "type": "PipeWire:Interface:Node",
               "info": {"state": "suspended", "props": {"media.class": "Audio/Sink"}}}]


def load():
    name = "moos_privacy_monitor_feed_under_test"
    loader = importlib.machinery.SourceFileLoader(name, str(MONITOR))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FeedText(unittest.TestCase):
    """GraphFeed.feed(): text in, graph out — no process involved."""

    def setUp(self):
        self.monitor = load()

    def test_an_array_cut_anywhere_is_applied_exactly_when_it_closes(self):
        text = (json.dumps(IDLE_GRAPH, indent=2) + "\n"
                + json.dumps([CLIENT, MIC], indent=2) + "\n"
                + json.dumps([{"id": 31, "info": None}]) + "\n")
        want = {0: IDLE_GRAPH[0], 40: CLIENT, 61: MIC}
        for width in (1, 2, 3, 7, 64, len(text)):
            feed = self.monitor.GraphFeed()
            for at in range(0, len(text), width):
                feed.feed(text[at:at + width])
            self.assertEqual(feed.objects, want, f"fed {width} characters at a time")

    def test_a_change_replaces_the_object_and_null_info_removes_it(self):
        feed = self.monitor.GraphFeed()
        feed.replace(IDLE_GRAPH + [CLIENT, MIC])
        stopped = json.loads(json.dumps(MIC))
        stopped["info"]["state"] = "idle"
        self.assertTrue(feed.feed(json.dumps([stopped])))
        self.assertEqual(feed.objects[61]["info"]["state"], "idle")
        self.assertTrue(feed.feed(json.dumps([{"id": 61, "info": None}])))
        self.assertNotIn(61, feed.objects)
        self.assertFalse(feed.feed("  \n"), "whitespace between arrays is not a change")

    def test_half_an_array_changes_nothing_yet(self):
        feed = self.monitor.GraphFeed()
        whole = json.dumps([CLIENT, MIC])
        self.assertFalse(feed.feed(whole[:20]))
        self.assertEqual(feed.objects, {})
        self.assertTrue(feed.feed(whole[20:]))
        self.assertEqual(set(feed.objects), {40, 61})


class TheLoop(unittest.TestCase):
    """Watch.step() against a pw-dump that can be told what to say."""

    def setUp(self):
        self.monitor = load()
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.state = base / "state"
        self.tokens = base / "tokens"
        self.state.mkdir()
        bindir = base / "bin"
        bindir.mkdir()
        fake = bindir / "pw-dump"
        fake.write_text(FAKE_PW_DUMP, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.graph(IDLE_GRAPH)
        self.saved = {k: os.environ.get(k) for k in ("PATH", "FAKE_PW_STATE")}
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"
        os.environ["FAKE_PW_STATE"] = str(self.state)
        self.assertEqual(shutil.which("pw-dump"), str(fake))
        # Short enough for a test, long enough that a resync never hides behind an event.
        self.monitor.RESYNC_SECONDS = 3.0
        self.monitor.SETTLE_SECONDS = 0.05
        self.monitor.POLL_SECONDS = 0.02
        self.deltas = 0
        self.watch = self.monitor.Watch(self.monitor.GraphFeed(), self.tokens)

    def tearDown(self):
        self.watch.feed.stop()
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def graph(self, objects):
        tmp = self.state / "graph.json.tmp"
        tmp.write_text(json.dumps(objects, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state / "graph.json")

    def say(self, payload):
        """Make the running monitor print one more thing."""
        data = payload if isinstance(payload, bytes) else \
            json.dumps(payload, indent=2, ensure_ascii=False).encode() + b"\n"
        tmp = self.state / f".delta-{self.deltas}"
        tmp.write_bytes(data)
        tmp.replace(self.state / f"delta-{self.deltas}")
        self.deltas += 1

    def spawns(self, kind):
        log = self.state / "spawns.log"
        return log.read_text().split().count(kind) if log.exists() else 0

    def names(self):
        return sorted(p.name for p in self.tokens.glob("active-*")) if self.tokens.exists() else []

    def step_until(self, done, seconds=2.5):
        deadline = time.monotonic() + seconds
        while not done():
            if time.monotonic() > deadline:
                return False
            self.watch.step()
        return True

    def test_an_idle_graph_is_read_once_per_resync_and_never_between(self):
        self.monitor.RESYNC_SECONDS = 0.4
        resyncs = []
        real = self.monitor.full_dump
        self.monitor.full_dump = lambda: resyncs.append(1) or real()
        end = time.monotonic() + 1.5
        steps = 0
        while time.monotonic() < end:
            self.watch.step()
            steps += 1
        self.assertEqual(self.spawns("monitor"), 1, "one feed for the whole session")
        self.assertEqual(self.spawns("oneshot"), len(resyncs))
        self.assertLessEqual(len(resyncs), 5, "1.5 s at one resync per 0.4 s")
        self.assertLess(steps, 25, "an idle round must SLEEP in the feed, not spin")
        self.assertEqual(self.names(), [])

    def test_a_capture_is_published_from_the_feed_without_another_dump(self):
        self.watch.step()
        # the stand-in logs its own start a few milliseconds after it is spawned
        deadline = time.monotonic() + 3
        while self.spawns("monitor") < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual((self.spawns("monitor"), self.spawns("oneshot")), (1, 1))
        self.say([CLIENT, MIC])
        self.assertTrue(self.step_until(lambda: self.names() == ["active-mic-61-Telegram"]),
                        f"the microphone never reached the Island: {self.names()}")
        self.assertEqual(self.spawns("oneshot"), 1,
                         "the capture was learned from a resync, not from the feed")
        # ... and a stream that ended must leave: the chip is a privacy promise.
        self.say([{"id": 61, "info": None}])
        self.assertTrue(self.step_until(lambda: self.names() == []),
                        f"an ended stream stayed on the Island: {self.names()}")
        self.assertEqual(self.spawns("oneshot"), 1)

    def test_a_change_rings_the_islands_bell_twice_and_no_more(self):
        """The Island's FolderListModel can lose a directory event that lands while it is reading.
        A change is therefore written again a moment later — and then left alone."""
        self.monitor.RETOUCH_SECONDS = 0.3
        self.monitor.RESYNC_SECONDS = 60.0          # no resync in this test: it rewrites by design
        self.watch.step()
        self.graph(IDLE_GRAPH + [CLIENT, MIC])
        self.say([CLIENT, MIC])
        token = self.tokens / "active-mic-61-Telegram"
        self.assertTrue(self.step_until(token.exists))
        first = token.stat().st_ino
        self.assertTrue(self.step_until(lambda: token.exists() and token.stat().st_ino != first, 2.0),
                        "the token was written once: a lost event would leave the chip wrong "
                        "until the next resync")
        second = token.stat().st_ino
        self.assertEqual(self.spawns("oneshot"), 1, "the second write must not cost a dump")
        for other in range(9000, 9006):             # graph events that change no stream
            self.say([{"id": other, "type": "PipeWire:Interface:Client", "info": {"props": {}}}])
            self.assertTrue(self.step_until(lambda: other in self.watch.feed.objects))
        self.assertEqual(token.stat().st_ino, second, "an unchanged token must not be rewritten "
                                                      "by every graph event")
        # a stream that ended is rung twice as well: the directory is touched again while empty
        self.graph(IDLE_GRAPH)
        self.say([{"id": 61, "info": None}])
        self.assertTrue(self.step_until(lambda: self.names() == []))
        self.assertIsNotNone(self.watch.retouch_at)

    def test_an_array_cut_inside_an_arabic_name_arrives_whole(self):
        self.watch.step()
        client = json.loads(json.dumps(CLIENT))
        client["info"]["props"]["application.name"] = "متصفّح - الويب"
        self.say(b"SPLIT" + json.dumps([client, MIC], ensure_ascii=False).encode() + b"\n")
        self.assertTrue(self.step_until(lambda: len(self.names()) == 1), self.names())
        token = self.monitor.token_name({"type": "mic", "app": "متصفّح - الويب", "node_id": 61}, 0)
        self.assertEqual(self.names(), [token])

    def test_a_feed_that_ends_falls_back_to_the_poll(self):
        self.watch.step()
        self.say(b"EXIT")
        self.assertTrue(self.step_until(lambda: not self.watch.feed.alive()))
        self.graph(IDLE_GRAPH + [CLIENT, MIC])          # a capture starts with no feed to say so
        before = self.spawns("oneshot")
        self.assertTrue(self.step_until(lambda: self.names() == ["active-mic-61-Telegram"]),
                        "with the feed gone the monitor must poll, as it always did")
        self.assertGreater(self.spawns("oneshot"), before)
        self.assertEqual(self.spawns("monitor"), 1,
                         "a feed that died is left alone for FEED_RETRY_SECONDS, not respawned "
                         "every round")

    def test_a_feed_is_started_again_after_the_retry_interval(self):
        self.monitor.FEED_RETRY_SECONDS = 0.3
        self.watch.step()
        self.say(b"EXIT")
        self.assertTrue(self.step_until(lambda: not self.watch.feed.alive()))
        (self.state / "delta-0").unlink()               # the next feed does not inherit the exit
        self.assertTrue(self.step_until(lambda: self.spawns("monitor") == 2))
        self.assertTrue(self.watch.feed.alive())

    def test_a_resync_corrects_what_the_feed_never_said(self):
        self.monitor.RESYNC_SECONDS = 0.3
        self.watch.step()
        self.graph(IDLE_GRAPH + [CLIENT, MIC])          # changed, and the feed stays silent
        self.assertTrue(self.step_until(lambda: self.names() == ["active-mic-61-Telegram"]))
        self.assertEqual(self.spawns("monitor"), 1)

    def test_a_resync_repairs_a_token_directory_that_was_cleaned(self):
        self.monitor.RESYNC_SECONDS = 0.3
        self.graph(IDLE_GRAPH + [CLIENT, MIC])
        self.watch.step()
        self.assertEqual(self.names(), ["active-mic-61-Telegram"])
        shutil.rmtree(self.tokens)
        self.assertTrue(self.step_until(lambda: self.names() == ["active-mic-61-Telegram"]))

    def test_text_that_never_becomes_json_ends_the_feed(self):
        self.monitor.FEED_BUFFER_LIMIT = 4096
        self.watch.step()
        self.say(b"[ " + b"x" * 20000)
        self.assertTrue(self.step_until(lambda: not self.watch.feed.alive()),
                        "an unbounded buffer is how a monitor becomes the leak")

    def test_no_pw_dump_at_all_is_an_empty_answer_not_a_crash(self):
        os.environ["PATH"] = str(Path(self.tmp.name) / "nowhere")
        for _ in range(3):
            self.watch.step()
        self.assertEqual(self.names(), [])
        self.assertFalse(self.watch.feed.alive())


class TheService(unittest.TestCase):
    def test_once_still_reads_one_dump_and_exits(self):
        source = MONITOR.read_text(encoding="utf-8")
        self.assertEqual(source.count('["pw-dump"'), 1, "one one-shot reader, shared by every path")
        self.assertIn('("pw-dump", "--monitor", "--no-colors")', source)
        self.assertNotIn("time.sleep(1.5)", source, "the unconditional 1.5 s poll is back")


if __name__ == "__main__":
    unittest.main(verbosity=1)
