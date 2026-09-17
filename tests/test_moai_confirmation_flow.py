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
import sys
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

    def test_diagnose_services_auto_executes_and_reads_back(self):
        status, body = self._req("POST", "/tool/execute", {
            "name": "diagnose_services",
            "arguments": {},
        })
        self.assertEqual(status, 200)
        self.assertIn(body.get("status"), ("ok", "error"))
        self.assertIsInstance(body.get("output"), str)
        self.assertIn("failed", body.get("output").lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
