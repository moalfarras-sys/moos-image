#!/usr/bin/env python3
"""Behavioral regression tests for Mo AI's loopback HTTP boundaries.

Binding to 127.0.0.1 does not prevent browser CSRF: a foreign page can still
submit requests to localhost.  These tests start the real request handlers on
ephemeral loopback ports and replace only their dangerous operations with
recording stubs.  A rejected request therefore proves both its HTTP status and
that it never reached config writes, agent execution, or a model/provider.
"""

from __future__ import annotations

import contextlib
import http.client
import json
import os
import runpy
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
AGENT_API = ROOT / "system_files/usr/bin/moai-agent-api"
CONTROL_API = ROOT / "system_files/usr/bin/moai-control"
GATEWAY = ROOT / "system_files/usr/bin/moai-gateway"
CONSOLE = ROOT / "system_files/usr/share/moos/apps/moai-agent/console.html"
MOAI_QML = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"


def load_script(path: Path, home: str) -> dict:
    env = {
        "HOME": home,
        "MOAI_AGENT_PORT": "8077",
        "MOAI_GATEWAY_PORT": "8080",
    }
    with mock.patch.dict(os.environ, env, clear=False):
        return runpy.run_path(
            str(path), run_name=path.name.replace("-", "_") + "_http_security_test"
        )


@contextlib.contextmanager
def running(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def request(port: int, method: str, path: str, body=None, headers=None):
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode("utf-8")
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, payload
    finally:
        connection.close()


def oversized_request(port: int, limit: int):
    """Declare an oversized body without sending it; the handler must not read it."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.putrequest("POST", "/api/config")
        connection.putheader("X-Moai-Agent", "1")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(limit + 1))
        connection.endheaders()
        response = connection.getresponse()
        payload = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, payload
    finally:
        connection.close()


def oversized_control_request(port: int, limit: int):
    """Prove moai-control rejects before waiting for declared body bytes."""
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        connection.putrequest("POST", "/config")
        connection.putheader("X-Moai-Control", "1")
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(limit + 1))
        connection.endheaders()
        response = connection.getresponse()
        payload = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, payload
    finally:
        connection.close()


class AgentApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.module = load_script(AGENT_API, self.home.name)
        self.handler = self.module["H"]
        self.calls = []
        scope = self.handler.do_GET.__globals__
        scope["status"] = lambda: self.calls.append(("status",)) or {"ok": True}
        scope["read_config"] = lambda: self.calls.append(("read_config",)) or {"ok": True}
        scope["list_sessions"] = lambda: self.calls.append(("sessions",)) or []
        scope["read_session"] = (
            lambda sid: self.calls.append(("session", sid)) or []
        )
        scope["write_config"] = (
            lambda body: self.calls.append(("write_config", body)) or {"ok": True}
        )

    def tearDown(self):
        self.home.cleanup()

    def test_every_api_route_requires_agent_header(self):
        with running(self.handler) as port:
            for path in (
                "/api/status",
                "/api/config",
                "/api/sessions",
                "/api/session?id=00000000-0000-0000-0000-000000000000",
                "/api/unknown",
            ):
                with self.subTest(path=path):
                    status, headers, _ = request(port, "GET", path)
                    self.assertEqual(status, 403)
                    self.assertNotIn("access-control-allow-origin", headers)

            for path in ("/api/config",):
                with self.subTest(path=path):
                    status, headers, _ = request(
                        port,
                        "POST",
                        path,
                        {},
                        {"Content-Type": "application/json"},
                    )
                    self.assertEqual(status, 403)
                    self.assertNotIn("access-control-allow-origin", headers)

        self.assertEqual(self.calls, [])

    def test_rejects_non_json_foreign_origin_options_and_oversized_body(self):
        with running(self.handler) as port:
            local_origin = f"http://127.0.0.1:{port}"
            base = {"X-Moai-Agent": "1"}

            status, _, _ = request(
                port,
                "POST",
                "/api/config",
                b'{"mode":"local"}',
                {**base, "Content-Type": "text/plain", "Origin": local_origin},
            )
            self.assertEqual(status, 415)

            status, _, _ = request(
                port,
                "POST",
                "/api/config",
                {"mode": "local"},
                {
                    **base,
                    "Content-Type": "application/json",
                    "Origin": "https://attacker.invalid",
                },
            )
            self.assertEqual(status, 403)

            status, headers, _ = request(
                port,
                "OPTIONS",
                "/api/config",
                headers={
                    "Origin": "https://attacker.invalid",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-Moai-Agent",
                },
            )
            self.assertEqual(status, 405)
            self.assertFalse(any(name.startswith("access-control-") for name in headers))

            status, _, _ = oversized_request(port, self.module["MAX_BODY_BYTES"])
            self.assertEqual(status, 413)

        self.assertEqual(self.calls, [])

    def test_legitimate_same_origin_requests_reach_only_safe_stubs(self):
        with running(self.handler) as port:
            origin = f"http://localhost:{port}"
            headers = {"X-Moai-Agent": "1", "Origin": origin}

            status, _, payload = request(port, "GET", "/api/status", headers=headers)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(payload), {"ok": True})

            body = {"mode": "local"}
            status, _, payload = request(
                port,
                "POST",
                "/api/config",
                body,
                {**headers, "Content-Type": "application/json; charset=utf-8"},
            )
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(payload), {"ok": True})

        self.assertEqual(self.calls, [("status",), ("write_config", body)])


class ControlApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.module = load_script(CONTROL_API, self.home.name)
        self.handler = self.module["H"]
        self.calls = []
        scope = self.handler.do_GET.__globals__
        scope["load"] = lambda: {
            "mode": "local",
            "cloud_base": "",
            "cloud_model": "",
            "cloud_wire": "openai",
        }
        scope["save"] = lambda body: self.calls.append(("save", body))
        scope["get_secret"] = lambda: ""
        scope["store_secret"] = lambda value: self.calls.append(
            ("secret", value)
        ) or True
        scope["user_unit_active"] = lambda unit: True
        scope["sysctl"] = lambda *args: self.calls.append(("sysctl", args))
        scope["quick"] = lambda: self.calls.append(("quick",)) or {"ok": True}

    def tearDown(self):
        self.home.cleanup()

    def test_rejects_before_body_read_and_before_any_control_action(self):
        with running(self.handler) as port:
            status, _, _ = request(
                port,
                "POST",
                "/config",
                {"mode": "cloud"},
                {"Content-Type": "application/json"},
            )
            self.assertEqual(status, 403)

            status, _, _ = request(
                port,
                "POST",
                "/config",
                b'{"mode":"cloud"}',
                {
                    "X-Moai-Control": "1",
                    "Content-Type": "text/plain",
                },
            )
            self.assertEqual(status, 415)

            status, _, _ = request(
                port,
                "POST",
                "/config",
                {"mode": "cloud"},
                {
                    "X-Moai-Control": "1",
                    "Content-Type": "application/json",
                    "Origin": "https://attacker.invalid/?localhost",
                },
            )
            self.assertEqual(status, 403)

            status, _, _ = oversized_control_request(
                port, self.module["MAX_BODY_BYTES"]
            )
            self.assertEqual(status, 413)

        self.assertEqual(self.calls, [])

    def test_retired_config_routes_are_gone_and_options_never_grants_cors(self):
        with running(self.handler) as port:
            origin = f"http://127.0.0.1:{port}"
            headers = {
                "X-Moai-Control": "1",
                "Content-Type": "application/json; charset=utf-8",
                "Origin": origin,
            }
            status, response_headers, _ = request(
                port, "POST", "/config", {"mode": "local"}, headers)
            self.assertEqual(status, 404)
            self.assertNotIn("access-control-allow-origin", response_headers)

            status, _, _ = request(
                port, "GET", "/config", headers={"X-Moai-Control": "1"})
            self.assertEqual(status, 404)
            status, _, _ = request(
                port, "GET", "/providers", headers={"X-Moai-Control": "1"})
            self.assertEqual(status, 404)

            status, response_headers, _ = request(
                port,
                "OPTIONS",
                "/config",
                headers={
                    "Origin": "https://attacker.invalid",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "X-Moai-Control",
                },
            )
            self.assertEqual(status, 405)
            self.assertFalse(
                any(name.startswith("access-control-") for name in response_headers)
            )

        self.assertEqual(self.calls, [])


class GatewaySecurityTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.module = load_script(GATEWAY, self.home.name)
        self.handler = self.module["Handler"]
        self.calls = []
        scope = self.handler.do_POST.__globals__
        scope["load_cfg"] = lambda: {"mode": "local"}
        scope["load_product_cfg"] = lambda: {"mode": "local"}

        calls = self.calls

        def safe_cloud(instance, req, raw, model, cfg):
            calls.append((req, model))
            return instance._send_json(200, {"ok": True})

        self.handler._to_cloud = safe_cloud

    def tearDown(self):
        self.home.cleanup()

    def test_post_rejects_non_json_foreign_origin_and_bad_json(self):
        with running(self.handler) as port:
            status, _, _ = request(
                port,
                "POST",
                "/v1/chat/completions",
                b'{"model":"local"}',
                {"Content-Type": "text/plain"},
            )
            self.assertEqual(status, 415)

            status, _, _ = request(
                port,
                "POST",
                "/v1/chat/completions",
                {"model": "local"},
                {
                    "Content-Type": "application/json",
                    "Origin": "https://attacker.invalid",
                },
            )
            self.assertEqual(status, 403)

            status, _, _ = request(
                port,
                "POST",
                "/v1/chat/completions",
                b"{broken",
                {"Content-Type": "application/json"},
            )
            self.assertEqual(status, 400)

            status, _, _ = request(
                port,
                "POST",
                "/v1/chat/completions",
                [],
                {"Content-Type": "application/json"},
            )
            self.assertEqual(status, 400)

        self.assertEqual(self.calls, [])

    def test_openai_client_needs_no_custom_header_and_options_has_no_cors(self):
        with running(self.handler) as port:
            body = {"model": "cloud", "messages": []}
            status, headers, payload = request(
                port,
                "POST",
                "/v1/chat/completions",
                body,
                {"Content-Type": "application/json"},
            )
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(payload), {"ok": True})
            self.assertNotIn("access-control-allow-origin", headers)

            status, headers, _ = request(
                port,
                "OPTIONS",
                "/v1/chat/completions",
                headers={
                    "Origin": "https://attacker.invalid",
                    "Access-Control-Request-Method": "POST",
                },
            )
            self.assertGreaterEqual(status, 400)
            self.assertFalse(any(name.startswith("access-control-") for name in headers))

        self.assertEqual(self.calls, [(body, "openrouter/free")])

    def test_foreign_origin_get_is_rejected_before_any_gateway_work(self):
        with running(self.handler) as port:
            status, headers, _ = request(
                port,
                "GET",
                "/healthz",
                headers={"Origin": "https://attacker.invalid"},
            )
            self.assertEqual(status, 403)
            self.assertFalse(any(name.startswith("access-control-") for name in headers))
        self.assertEqual(self.calls, [])


class AgentClientHeaderTests(unittest.TestCase):
    def test_second_composer_endpoint_stays_removed(self):
        # POST /api/send was the second chat composer's server half: a
        # synchronous, non-streaming `openclaw agent -m` runner with no
        # remaining callers once the one-chat redesign landed. Like the
        # browser console, it must not quietly return.
        api_source = AGENT_API.read_text(encoding="utf-8")
        self.assertNotIn("/api/send", api_source,
                         "the second composer endpoint must stay deleted — one chat")
        self.assertNotIn("def send(", api_source,
                         "the synchronous agent-turn runner must stay deleted")

    def test_browser_console_stays_removed(self):
        # The hidden browser console was a THIRD chat surface over the same
        # backend, with its own half-connected settings. It was removed when
        # the product went one-chat; the API must never serve HTML again, and
        # the page must not quietly return to the image.
        self.assertFalse(
            CONSOLE.exists(),
            "the moai-agent browser console must stay deleted — one chat")
        api_source = AGENT_API.read_text(encoding="utf-8")
        self.assertNotIn("text/html", api_source,
                         "moai-agent-api is an API, not a web page server")

    def test_every_qml_agent_api_request_adds_agent_header(self):
        lines = MOAI_QML.read_text(encoding="utf-8").splitlines()
        opens = [
            index
            for index, line in enumerate(lines)
            if "xhr.open(" in line and "agentApi" in line
        ]
        # Keep a floor so accidentally deleting the agent client still bites,
        # but inspect every request dynamically: adding a legitimate endpoint
        # must require the header, not require editing a brittle route count.
        self.assertGreaterEqual(len(opens), 6)
        for index in opens:
            with self.subTest(request=lines[index].strip()):
                nearby = "\n".join(lines[index : index + 4])
                self.assertIn(
                    'xhr.setRequestHeader("X-Moai-Agent", "1")',
                    nearby,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
