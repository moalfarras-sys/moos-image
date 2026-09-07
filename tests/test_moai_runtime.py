#!/usr/bin/env python3
"""Real workspace, persistence, approval and isolated PTY regression tests."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.home / "runtime")})
        self.env.start()
        self.api = runpy.run_path(str(ROOT / "system_files/usr/bin/moai-agent-api"))["main"].__globals__
        self.api.update(HOME=self.home, DATA_HOME=self.home / "data", WORKSPACE=self.home / "workspace.json", STATE=self.home / "state.json")
        self.api["STATE"].write_text('{"tier":"project"}')
        self.project = self.home / "project"
        self.project.mkdir()
        self.pid = self.api["upsert_project"]({"path": str(self.project)})["id"]
        self.runtime = self.api["moai_runtime"].Runtime(self.api)
        self.turn = self.runtime.begin({"session": "review-session", "user": "Inspect this project"})

    def tearDown(self):
        for terminal in self.api["TERMINALS"].values():
            terminal.stop()
        self.env.stop()
        self.tmp.cleanup()

    def call(self, name, **args):
        return self.runtime.tool({**self.turn, "name": name, "arguments": args})

    def approve(self, future, decision="allow-once"):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            rows = self.runtime.approvals()
            if rows:
                self.runtime.resolve({"id": rows[0]["id"], "decision": decision})
                return future.result(timeout=65)
            if future.done():
                return future.result()
            time.sleep(.02)
        self.fail("no real approval was requested")

    def test_unknown_tool_and_forged_turn_rejected(self):
        with self.assertRaises(ValueError):
            self.call("exec_root", command="id")
        with self.assertRaises(ValueError):
            self.runtime.tool({**self.turn, "run": "forged", "name": "projects", "arguments": {}})

    def test_write_requires_approval_and_current_digest(self):
        (self.project / "code.py").write_text("before\n")
        read = self.call("read_file", project=self.pid, path="code.py")
        with concurrent.futures.ThreadPoolExecutor() as pool:
            job = pool.submit(self.call, "write_file", project=self.pid, path="code.py", content="after\n", sha256=read["sha256"])
            result = self.approve(job)
        self.assertNotIn("error", result)
        self.assertEqual((self.project / "code.py").read_text(), "after\n")
        with concurrent.futures.ThreadPoolExecutor() as pool:
            job = pool.submit(self.call, "write_file", project=self.pid, path="code.py", content="stale\n", sha256=read["sha256"])
            result = self.approve(job)
        self.assertIn("file changed", result["error"])

    def test_denied_and_read_only_actions_do_not_execute(self):
        with concurrent.futures.ThreadPoolExecutor() as pool:
            job = pool.submit(self.call, "write_file", project=self.pid, path="new.py", content="bad", sha256="")
            self.assertIn("denied", self.approve(job, "deny")["error"])
        self.assertFalse((self.project / "new.py").exists())
        self.api["STATE"].write_text('{"tier":"read"}')
        self.assertIn("read-only", self.call("run_command", project=self.pid, command="true")["error"])

    def test_project_escape_and_hidden_files_blocked(self):
        (self.home / "secret").write_text("private")
        (self.project / "link").symlink_to(self.home / "secret")
        for path in ("../secret", "link", ".env", "/etc/passwd"):
            self.assertIn("error", self.call("read_file", project=self.pid, path=path))

    def test_real_pty_sandbox_does_not_inherit_secrets(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "never-forward"}):
            with concurrent.futures.ThreadPoolExecutor() as pool:
                command = 'test -z "$OPENROUTER_API_KEY" && test ! -e /run/user && test ! -e /home/moos && printf verified'
                job = pool.submit(self.call, "run_command", project=self.pid, command=command)
                result = self.approve(job)
        self.assertNotIn("error", result)
        self.assertEqual(result["exit_code"], 0, result)
        self.assertIn("verified", result["output"])
        self.assertFalse(result["running"])

    def test_shared_session_history_survives_restart(self):
        self.call("projects")
        history = [{"role": "user", "content": "Inspect this project"}, {"role": "assistant", "content": "Inspected"}]
        self.runtime.finish({**self.turn, "history": history, "answer": "Inspected"})
        second = self.api["moai_runtime"].Runtime(self.api)
        continued = second.begin({"session": self.turn["id"], "user": "Continue from the phone"})
        self.assertEqual(continued["id"], self.turn["id"])
        self.assertEqual(continued["history"], history)
        self.assertTrue(any(row["role"] == "tool" for row in second.messages(self.turn["id"])))
        with self.assertRaises(ValueError):
            second.begin({"session": self.turn["id"], "user": "Concurrent duplicate"})


if __name__ == "__main__":
    unittest.main()
