#!/usr/bin/env python3
"""Gate: P1.5 — one update state machine that the UI and the journal both read.

WHY THIS EXISTS

`moos-image-update` has always owned the only validated update vocabulary
(current/available/replace-staged/staged/blocked-downgrade/busy/unknown), but it spoke that vocabulary to stdout
only. The Updater window, `moai-do update` and the automatic timer each ran their own query, and
nothing reached the journal — so "what is my machine doing about updates?" had three answers and no
record. P1.5 requires one state machine that the UI and the journal read from the same source.

This gate loads the real backend and drives it:

  * every publish writes the record atomically (os.replace) and logs the same state, so a reader
    never sees a half-written file and the journal never disagrees with the window;
  * the record carries state, edition, versions and digests — never a credential;
  * a stale record is not state: callers resolve again;
  * an unprivileged caller that cannot write /run/moos still logs, and still returns its result;
  * the Updater reads that file and validates schema and age instead of inventing a state.
"""

import importlib.util
import json
from pathlib import Path
import sys
import time
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "system_files/usr/libexec/moos-image-update"
UI = ROOT / "system_files/usr/bin/moos-update"


def load_backend():
    loader = importlib.machinery.SourceFileLoader("moos_image_update", str(BACKEND))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class UpdateStateMachine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = load_backend()

    def setUp(self):
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.state_file = self.tmp / "update-state.json"
        self.enterContext(mock.patch.object(self.backend, "STATE_DIR", str(self.tmp)))
        self.enterContext(mock.patch.object(self.backend, "STATE_FILE", str(self.state_file)))
        self.logged = []
        def fake_logger(argv, **kwargs):
            self.logged.append(argv)
            return types.SimpleNamespace(returncode=0)
        self.enterContext(mock.patch.object(self.backend.subprocess, "run", fake_logger))

    def resolved(self, **overrides):
        result = {
            "schema": 1, "state": "available", "edition": "moos-nvidia",
            "booted_version": "44.20260913.824", "staged_version": "",
            "current_digest": "sha256:" + "a" * 64, "staged_digest": "",
            "latest_digest": "sha256:" + "b" * 64, "latest_version": "44.20260916.900",
        }
        result.update(overrides)
        return result

    def test_publish_writes_the_record_and_logs_the_same_state(self):
        record = self.backend.publish_state(self.resolved(), "resolve")
        on_disk = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(on_disk, record)
        self.assertEqual(on_disk["state"], "available")
        self.assertEqual(on_disk["event"], "resolve")
        self.assertEqual(on_disk["latest_version"], "44.20260916.900")
        self.assertEqual(len(self.logged), 1)
        argv = self.logged[0]
        self.assertEqual(argv[:3], ["logger", "-t", self.backend.JOURNAL_TAG])
        self.assertIn("state=available", argv[-1])
        self.assertIn("edition=moos-nvidia", argv[-1])

    def test_record_carries_no_credentials(self):
        record = self.backend.publish_state(self.resolved(), "resolve")
        self.assertEqual(set(record) - {"schema", "updated"}, set(self.backend.STATE_KEYS))
        serialized = json.dumps(record).lower()
        for secret in ("token", "password", "secret", "key=", "authorization", "cookie"):
            self.assertNotIn(secret, serialized)

    def test_the_write_is_atomic(self):
        replaced = []
        real_replace = self.backend.os.replace
        def spy(src, dst):
            replaced.append((src, dst))
            return real_replace(src, dst)
        with mock.patch.object(self.backend.os, "replace", spy):
            self.backend.publish_state(self.resolved(), "resolve")
        self.assertEqual(len(replaced), 1, "the record must be renamed into place, never written in place")
        self.assertTrue(replaced[0][1].endswith("update-state.json"))
        self.assertFalse(Path(replaced[0][0]).exists(), "the temporary file must not survive")

    def test_a_stale_record_is_not_state(self):
        self.backend.publish_state(self.resolved(), "resolve")
        self.assertIsNotNone(self.backend.published_state())
        aged = json.loads(self.state_file.read_text(encoding="utf-8"))
        aged["updated"] = int(time.time()) - self.backend.STATE_MAX_AGE_SECONDS - 1
        self.state_file.write_text(json.dumps(aged), encoding="utf-8")
        self.assertIsNone(self.backend.published_state())

    def test_a_foreign_or_broken_record_is_refused(self):
        for payload in ('{"schema": 2, "state": "current", "updated": 99999999999}',
                        '{"state": "current"}', "not json at all", "[]"):
            self.state_file.write_text(payload, encoding="utf-8")
            self.assertIsNone(self.backend.published_state(), payload)

    def test_an_unprivileged_caller_still_logs_and_still_returns(self):
        with mock.patch.object(self.backend.os, "makedirs", side_effect=PermissionError(13, "denied")):
            record = self.backend.publish_state(self.resolved(state="current"), "resolve")
        self.assertEqual(record["state"], "current")
        self.assertFalse(self.state_file.exists())
        self.assertEqual(len(self.logged), 1, "the journal line is the unprivileged caller's contract")

    def test_resolve_and_stage_publish_through_the_same_path(self):
        source = BACKEND.read_text(encoding="utf-8")
        self.assertIn("def resolve() -> dict[str, Any]:\n    result = _resolve()\n    publish_state(result, \"resolve\")",
                      source, "resolve must publish the state it returns")
        self.assertIn('publish_state(_deployment_view(outcome), f"stage:{outcome}")', source,
                      "staging must publish its outcome")
        self.assertIn('state_parser = subparsers.add_parser("state")', source,
                      "callers need a read-only way to ask the same source")

    def test_the_updater_reads_the_published_record(self):
        ui = UI.read_text(encoding="utf-8")
        self.assertIn('UPDATE_STATE_FILE = "/run/moos/update-state.json"', ui)
        self.assertIn('record.get("schema") != 1', ui, "the window must validate the schema")
        self.assertIn("UPDATE_STATE_MAX_AGE_SECONDS", ui, "the window must refuse a stale record")
        self.assertIn("record = published_state()", ui)
        self.assertIn("UPDATE_BACKEND", ui, "the window must keep using the backend, not rpm-ostree, for updates")


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=1).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(UpdateStateMachine))
    sys.exit(0 if result.wasSuccessful() else 1)
