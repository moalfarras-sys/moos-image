#!/usr/bin/env python3
"""Real workspace, persistence, approval and isolated PTY regression tests."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import runpy
import tempfile
import threading
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

    def test_an_answer_at_the_very_edge_is_honoured(self):
        # resolve() accepts an answer until the wall-clock expiry, while the waiting side gives up
        # on its own clock. An answer that lands after its last poll was already confirmed to the
        # owner ({ok: true}): it must decide, never be overwritten by "expired".
        runtime_time = self.api["moai_runtime"].time
        real_monotonic = runtime_time.monotonic
        for decision in ("allow-once", "deny"):
            with self.subTest(decision=decision):
                calls = []

                def edge_clock():
                    calls.append(1)
                    return 0.0 if len(calls) == 1 else 10_000.0   # the loop never polls

                def owner_answers(sid, role, text, status=""):
                    rows = self.runtime.approvals()
                    self.assertEqual(self.runtime.resolve({"id": rows[0]["id"], "decision": decision})["ok"], True)

                with patch.object(self.runtime, "event", owner_answers), \
                        patch.object(runtime_time, "monotonic", edge_clock):
                    if decision == "allow-once":
                        self.runtime.approval("review-session", "write_file", {"path": "x"}, self.project)
                    else:
                        with self.assertRaisesRegex(PermissionError, "denied"):
                            self.runtime.approval("review-session", "write_file", {"path": "x"}, self.project)
                self.assertIs(runtime_time.monotonic, real_monotonic)
        # …and with no answer at all it still expires, and nothing runs.
        with patch.object(self.runtime, "event", lambda *a, **k: None), \
                patch.object(runtime_time, "monotonic", iter([0.0] + [10_000.0] * 5).__next__):
            with self.assertRaisesRegex(PermissionError, "expired"):
                self.runtime.approval("review-session", "write_file", {"path": "x"}, self.project)

    def test_project_escape_and_hidden_files_blocked(self):
        (self.home / "secret").write_text("private")
        (self.project / "link").symlink_to(self.home / "secret")
        for path in ("../secret", "link", ".env", "/etc/passwd"):
            self.assertIn("error", self.call("read_file", project=self.pid, path=path))

    def test_real_pty_sandbox_does_not_inherit_secrets(self):
        """Isolation when bwrap exists; a refusal, never a fallback, when it does not.

        This ran green on a workstation and red in CI, because the source-gate
        step executes on a bare runner where /usr/bin/bwrap is absent while the
        MoOS image carries it. Asserting only the happy path made the gate
        environment-dependent; skipping it outright would have hidden the more
        important property. So both branches assert something.

        The absent branch is the security-critical one: run_command must REFUSE
        when it cannot sandbox. Silently executing unsandboxed would hand the
        model the very environment -- OPENROUTER_API_KEY, /home/moos -- that the
        present branch proves it cannot see.
        """
        sandboxed = Path("/usr/bin/bwrap").is_file()
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "never-forward"}):
            with concurrent.futures.ThreadPoolExecutor() as pool:
                command = 'test -z "$OPENROUTER_API_KEY" && test ! -e /run/user && test ! -e /home/moos && printf verified'
                job = pool.submit(self.call, "run_command", project=self.pid, command=command)
                result = self.approve(job)
        if not sandboxed:
            self.assertIn("error", result)
            self.assertIn("sandbox is unavailable", result["error"])
            self.assertNotIn("output", result)
            return
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

    def task_result(self, task_id, state="running", seconds=5):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            task = next(row for row in self.api["list_tasks"]() if row["id"] == task_id)
            if task["status"] != state:
                return task
            time.sleep(.01)
        self.fail("private task worker did not settle")

    def task_turn(self, key, prompt, *, fail=False):
        """A scripted model; the broker, Git and sandboxed jobs are real and private."""
        turn = self.runtime.begin({"session": key, "user": prompt})
        self.task_tools = []
        calls = [("run_command", {"project": self.pid, "command": "printf unrelated-check"}),
                 ("git_diff", {"project": self.pid})]
        if fail:
            calls.append(("run_command", {"project": self.pid, "command": "exit 7"}))
        for name, arguments in calls:
            self.task_tools.append((name, self.runtime.tool({**turn, "name": name, "arguments": arguments})))
        answer = "The model says the task is complete."
        self.runtime.finish({**turn, "history": [], "answer": answer})
        return answer

    def test_successful_command_and_diff_do_not_verify_an_unspecified_requirement(self):
        subprocess = self.api["subprocess"]
        subprocess.run(["git", "init", "-q", str(self.project)], check=True)
        task = self.api["create_task"]({"title": "Improve this project", "project": self.pid})
        with patch.object(self.runtime, "chat", self.task_turn), \
                patch.object(self.runtime, "approval", lambda *args: None):
            self.runtime.task_action({"id": task["id"], "action": "start"})
            result = self.task_result(task["id"])
        self.assertEqual(result["status"], "paused")
        self.assertIn("requirements still need review", result["error"])
        self.assertEqual(result["result"], "The model says the task is complete.")
        self.assertEqual(result["steps"], [])
        if Path("/usr/bin/bwrap").is_file():
            command = self.task_tools[0][1]
            self.assertEqual(command["exit_code"], 0)
            self.assertFalse(command["running"])
            self.assertNotIn("error", self.task_tools[1][1])
        # The real tool results stay in the same session for the owner to inspect.
        messages = self.runtime.messages("moai-task-" + task["id"])
        self.assertTrue(any(row["text"].startswith("run_command\n") for row in messages))
        self.assertTrue(any(row["text"].startswith("git_diff\n") for row in messages))

    def test_later_failed_command_cannot_complete_pending_required_steps(self):
        self.api["subprocess"].run(["git", "init", "-q", str(self.project)], check=True)
        task = self.api["create_task"]({"title": "Fix the project", "project": self.pid,
                                        "steps": ["Make the requested change", "Verify it"]})
        with patch.object(self.runtime, "chat", lambda key, prompt: self.task_turn(key, prompt, fail=True)), \
                patch.object(self.runtime, "approval", lambda *args: None):
            self.runtime.task_action({"id": task["id"], "action": "start"})
            result = self.task_result(task["id"])
        self.assertEqual(result["status"], "paused")
        self.assertEqual([step["status"] for step in result["steps"]], ["pending", "pending"])
        if Path("/usr/bin/bwrap").is_file():
            self.assertEqual(self.task_tools[-1][1]["exit_code"], 7)
            self.assertIn("error", self.task_tools[-1][1])
        messages = self.runtime.messages("moai-task-" + task["id"])
        self.assertTrue(any(row["status"] == "error" and row["text"].startswith("run_command\n")
                            for row in messages))

    def test_earlier_same_second_receipts_and_new_prose_are_not_task_evidence(self):
        # The former timestamp/text heuristic accepted the previous turn's
        # unrelated checks beside a new success claim from the model.
        task = self.api["create_task"]({"title": "Do a different change", "project": self.pid})
        key = "moai-task-" + task["id"]
        with patch.object(self.api["moai_runtime"].time, "time", return_value=1234567890):
            old = self.runtime.begin({"session": key, "user": "Earlier unrelated question"})
            self.runtime.event(old["id"], "tool", 'run_command\n{"exit_code": 0, "output": "earlier unrelated check"}', "success")
            self.runtime.event(old["id"], "tool", 'git_diff\n{"unstaged": ""}', "success")
            self.runtime.finish({**old, "history": [], "answer": "Earlier reply"})
            with patch.object(self.runtime, "chat", return_value="All requested work is complete."):
                self.runtime.task_action({"id": task["id"], "action": "start"})
                result = self.task_result(task["id"])
        self.assertEqual(result["status"], "paused")

    def test_declared_step_states_stay_visible_after_an_unverified_reply(self):
        for step_status in ("failed", "skipped", "running", "pending", "completed"):
            with self.subTest(step_status=step_status):
                task = self.api["create_task"]({"title": "Review a required step", "project": self.pid,
                                                "steps": ["Required result"]})
                self.api["update_task"]({"id": task["id"], "step": 1, "step_status": step_status,
                                         "error": "required result is not verified"})
                with patch.object(self.runtime, "chat", return_value="Everything succeeded."):
                    self.runtime.task_action({"id": task["id"], "action": "start"})
                    result = self.task_result(task["id"])
                self.assertEqual(result["status"], "paused")
                self.assertEqual(result["steps"][0]["status"], step_status)
                self.assertEqual(result["steps"][0]["error"], "required result is not verified")

    def test_cancel_or_pause_during_the_turn_keeps_the_owners_decision(self):
        for action, expected in (("cancel", "cancelled"), ("pause", "paused")):
            with self.subTest(action=action):
                entered, release, returned, checked = (threading.Event() for _ in range(4))
                task = self.api["create_task"]({"title": "A cancellable private task", "project": self.pid})
                original_list = self.api["list_tasks"]
                def observed_list(*args, **kwargs):
                    rows = original_list(*args, **kwargs)
                    if returned.is_set() and threading.current_thread() is not threading.main_thread():
                        checked.set()
                    return rows
                def delayed_chat(*args):
                    entered.set()
                    release.wait(5)
                    returned.set()
                    return "Late model success"
                with patch.object(self.runtime, "chat", delayed_chat), \
                        patch.dict(self.api, {"list_tasks": observed_list}):
                    self.runtime.task_action({"id": task["id"], "action": "start"})
                    self.assertTrue(entered.wait(5))
                    self.runtime.task_action({"id": task["id"], "action": action})
                    release.set()
                    self.assertTrue(returned.wait(5))
                    self.assertTrue(checked.wait(5))
                    # Serialise with the worker's status check/write.
                    with self.api["CONFIG_WRITE_LOCK"]:
                        result = next(row for row in self.api["list_tasks"]() if row["id"] == task["id"])
                    self.assertEqual(result["status"], expected)
                    self.assertNotEqual(result["result"], "Late model success")

    def test_a_failed_agent_turn_remains_failed(self):
        task = self.api["create_task"]({"title": "Private failed turn", "project": self.pid})
        with patch.object(self.runtime, "chat", side_effect=RuntimeError("private test failure")):
            self.runtime.task_action({"id": task["id"], "action": "start"})
            result = self.task_result(task["id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("completed results remain", result["error"])


if __name__ == "__main__":
    unittest.main()
