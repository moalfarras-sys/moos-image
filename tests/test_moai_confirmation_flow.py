#!/usr/bin/env python3
"""Gate: Mo AI tool execution flow, confirmation requirements, and readback.

WHY THIS EXISTS

Task P3.4 requires explicit confirmation cards and execution readback:
- Read-only and status tools execute directly.
- State-changing tools require explicit confirmation before execution.
- If confirmation is missing, the execution bridge rejects with confirmation_required.
- When confirmed, the fixed executor runs and returns structured status, exit code,
  and output.
- All requests require the CSRF guard header (X-Moai-Control: 1).
"""

from __future__ import annotations

import json
import os
import runpy
import stat
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROL_SCRIPT = ROOT / "system_files/usr/bin/moai-control"
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moai"))
import moai_tool_schemas as tool_schemas


class TestMoaiConfirmationFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Doubles for the executors whose REAL run would change this machine. They sit first on
        # PATH, which is where moai-control's resolve_tool_binary looks first. The read-only
        # executors stay real.
        cls.tmp = tempfile.TemporaryDirectory()
        bindir = Path(cls.tmp.name)
        cls.calls = bindir / "calls.log"
        doubles = {
            # A job that outlives W4's 90 s budget in miniature: slow, then a result on its LAST line.
            "moai-do": ("#!/bin/sh\n"
                        f'printf "%s\\n" "moai-do $*" >> "{cls.calls}"\n'
                        'case "$*" in *optimize*) sleep 2; echo "freed 1.2 GB"; exit 0 ;;\n'
                        '              *fix-audio*) echo "pipewire would not restart"; exit 3 ;; esac\n'
                        # Everything else is the REAL executor: the read-only tools stay real.
                        f'exec bash "{ROOT / "system_files/usr/bin/moai-do"}" "$@"\n'),
            # REAL, but this repository's copy rather than whatever is installed.
            #
            # moai-control's resolve_tool_binary() calls shutil.which() first and only
            # then falls back to a sibling of its own path. On a CI runner nothing is
            # installed, so the fallback found the source and the gate tested the source.
            # On a MoOS workstation /usr/bin/moos-inspect exists, so which() won only
            # there and the gate tested the INSTALLED image instead - which is always
            # older than the tree between releases. On 2026-09-17 that failed this gate
            # on the station alone: the source had grown `moos-inspect skills` for
            # P3.10 and the running 44.20260917.858 had not. The inverse is worse and
            # silent: a station whose installed binary still satisfies a check the
            # source has broken would go green.
            "moos-inspect": ("#!/bin/sh\n"
                             f'exec python3 "{ROOT / "system_files/usr/bin/moos-inspect"}" "$@"\n'),
        }
        for name, body in doubles.items():
            (bindir / name).write_text(body, encoding="utf-8")
            (bindir / name).chmod(0o755)
        cls.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bindir}{os.pathsep}{cls.old_path}"
        # A confirmed job publishes an Island token in $XDG_RUNTIME_DIR/moai-jobs (SPEC D6).
        # With the owner's real runtime directory, every gate run on the station left
        # "job done/failed" tokens the live Island would show. The directory is this test's own.
        cls.old_runtime = os.environ.get("XDG_RUNTIME_DIR")
        cls.runtime = bindir / "runtime"
        cls.runtime.mkdir(mode=0o700)
        os.environ["XDG_RUNTIME_DIR"] = str(cls.runtime)
        cls.ns = runpy.run_path(str(CONTROL_SCRIPT), run_name="moai_control_test")
        handler_cls = cls.ns["H"]

        # Start a test server on an ephemeral port
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        os.environ["PATH"] = cls.old_path
        if cls.old_runtime is None:
            os.environ.pop("XDG_RUNTIME_DIR", None)
        else:
            os.environ["XDG_RUNTIME_DIR"] = cls.old_runtime
        cls.tmp.cleanup()

    def _wait(self, job_id: str, seconds: float = 20.0) -> dict:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            status, body = self._req("GET", f"/tool/job?id={job_id}")
            self.assertEqual(status, 200)
            if body["status"] != "running":
                return body
            time.sleep(0.2)
        self.fail("the job never finished")

    def _req(self, method: str, path: str, data: dict | None = None, headers: dict | None = None):
        url = f"http://127.0.0.1:{self.port}{path}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Moai-Control", "1")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                parsed = json.loads(raw.decode("utf-8"))
            except Exception:
                parsed = {"raw": raw.decode("utf-8", "replace")}
            return e.code, parsed

    def test_csrf_guard_blocks_requests_without_header(self):
        url = f"http://127.0.0.1:{self.port}/tools"
        req = urllib.request.Request(url)
        # Omit X-Moai-Control header
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 403)

    def test_get_tools_endpoint_returns_schemas(self):
        status, body = self._req("GET", "/tools")
        self.assertEqual(status, 200)
        self.assertIn("tools", body)
        self.assertIn("metadata", body)
        tools = body["tools"]
        self.assertGreaterEqual(len(tools), 25)
        names = {t["function"]["name"] for t in tools}
        self.assertIn("system_update", names)
        self.assertIn("get_system_status", names)
        self.assertIn("gpu_report", names)

    def test_read_only_tool_executes_without_confirmation(self):
        status, body = self._req("POST", "/tool/execute", {
            "name": "get_system_status",
            "arguments": {},
            "confirmed": False,
        })
        self.assertEqual(status, 200)
        self.assertIn("status", body)
        self.assertIn("output", body)
        self.assertIn("duration_ms", body)

    def test_state_changing_tool_rejected_without_confirmation(self):
        status, body = self._req("POST", "/tool/execute", {
            "name": "system_update",
            "arguments": {},
            "confirmed": False,
        })
        self.assertEqual(status, 403)
        self.assertEqual(body.get("error"), "confirmation_required")
        self.assertEqual(body.get("tool"), "system_update")
        self.assertEqual(body.get("category"), tool_schemas.PRIV_CONFIRM)

    def test_install_app_rejected_without_confirmation(self):
        status, body = self._req("POST", "/tool/execute", {
            "name": "install_app",
            "arguments": {"app_id": "org.mozilla.firefox"},
            "confirmed": False,
        })
        self.assertEqual(status, 403)
        self.assertEqual(body.get("error"), "confirmation_required")
        self.assertEqual(body.get("category"), tool_schemas.USER_CONFIRM)

    def test_unknown_tool_returns_404(self):
        status, body = self._req("POST", "/tool/execute", {
            "name": "make_coffee",
            "arguments": {},
        })
        self.assertEqual(status, 404)
        self.assertIn("unknown tool", body.get("error", ""))

    def test_invalid_arguments_rejected(self):
        status, body = self._req("POST", "/tool/execute", {
            "name": "set_volume",
            "arguments": {},  # missing required 'value'
        })
        self.assertEqual(status, 400)
        self.assertIn("invalid arguments", body.get("error", ""))

    def test_a_read_only_tool_auto_executes_and_reads_back(self):
        """Was `diagnose_services`, which the P3.3 measurement retired: it returned the
        same two `systemctl --failed` lists as the inspector's `list_failed_units` under
        an indistinguishable description, so a free model could only guess between them.
        `list_failed_units` is the one that stayed, and it exercises the same path."""
        status, body = self._req("POST", "/tool/execute", {
            "name": "list_failed_units",
            "arguments": {},
        })
        self.assertEqual(status, 200)
        self.assertIn(body.get("status"), ("ok", "error"))
        self.assertIsInstance(body.get("output"), str)


    # ── confirmed actions are JOBS: they answer at once and report when they really end ─────
    def test_a_confirmed_action_runs_as_a_job_and_reads_back_its_real_result(self):
        started = time.monotonic()
        status, body = self._req("POST", "/tool/execute",
                                 {"name": "optimize_system", "arguments": {}, "confirmed": True})
        self.assertEqual(status, 202, body)
        self.assertLess(time.monotonic() - started, 1.5,
                        "a confirmed action must answer at once; W4 held the request for up to "
                        "90 s and then KILLED moai-do mid-transaction")
        self.assertEqual(body["status"], "running")
        # A second state change while one runs is refused, not queued behind the person's back.
        status, busy = self._req("POST", "/tool/execute",
                                 {"name": "fix_audio", "arguments": {}, "confirmed": True})
        self.assertEqual(status, 409, busy)
        done = self._wait(body["job"])
        self.assertEqual((done["status"], done["exit_code"]), ("ok", 0))
        self.assertIn("freed 1.2 GB", done["output"])
        self.assertIn("moai-do --confirmed optimize", self.calls.read_text(encoding="utf-8"))

    def test_a_failed_job_is_reported_as_failed(self):
        status, body = self._req("POST", "/tool/execute",
                                 {"name": "fix_audio", "arguments": {}, "confirmed": True})
        self.assertEqual(status, 202, body)
        done = self._wait(body["job"])
        self.assertEqual((done["status"], done["exit_code"]), ("error", 3))
        self.assertIn("would not restart", done["output"])

    def test_an_unknown_job_is_not_invented(self):
        status, body = self._req("GET", "/tool/job?id=feedfacefeedface")
        self.assertEqual(status, 404)

    def test_confirmation_is_decided_by_the_executor_not_by_the_client(self):
        # `confirmed` must be the JSON boolean true. W4 used bool(), so the string "false" confirmed.
        for forged in ("true", "false", 1, "yes"):
            status, body = self._req("POST", "/tool/execute",
                                     {"name": "system_update", "arguments": {}, "confirmed": forged})
            self.assertEqual(status, 403, f"confirmed={forged!r} must not count as confirmation")

    def test_turning_the_radio_off_needs_confirmation_but_on_does_not(self):
        status, body = self._req("POST", "/tool/execute",
                                 {"name": "toggle_wifi", "arguments": {"value": "off"}})
        self.assertEqual(status, 403, "Wi-Fi OFF can cut the owner off from a remotely driven machine")
        self.assertEqual(body.get("error"), "confirmation_required")
        status, body = self._req("POST", "/tool/execute",
                                 {"name": "toggle_bluetooth", "arguments": {"value": "off"}})
        self.assertEqual(status, 403)

    def test_an_inspector_tool_runs_without_a_card_and_is_redacted(self):
        status, body = self._req("POST", "/tool/execute",
                                 {"name": "top_processes", "arguments": {"by": "memory"}})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["status"], "ok")
        self.assertIn("top processes by memory", body["output"])
        self.assertNotIn(str(Path.home()), body["output"], "the inspector's output must be redacted")

    def test_a_skill_is_read_without_a_card_and_an_invented_one_never_reaches_the_reader(self):
        status, body = self._req("POST", "/tool/execute", {"name": "list_skills", "arguments": {}})
        self.assertEqual((status, body.get("status")), (200, "ok"), body)
        self.assertIn("no-sound — ", body["output"])
        status, body = self._req("POST", "/tool/execute",
                                 {"name": "read_skill", "arguments": {"name": "no-sound"}})
        self.assertEqual((status, body.get("status")), (200, "ok"), body)
        self.assertIn("`fix_audio`", body["output"], "the playbook must arrive as written")
        for invented in ("../../etc/passwd", "reset-everything", "no-sound; id", ""):
            status, body = self._req("POST", "/tool/execute",
                                     {"name": "read_skill", "arguments": {"name": invented}})
            self.assertEqual(status, 400, f"{invented!r} must be refused by the schema: {body}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
