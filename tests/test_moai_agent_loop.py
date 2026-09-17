#!/usr/bin/env python3
"""Gate: Mo AI's native tool loop really loops — on a machine with no Hermes — and reports what
the executors reported.

WHY THIS EXISTS

Wave W4 (PR #110) was announced as "Mo AI as the system harness". As merged:

  * the tools were attached only when `!agentMode`; agentMode defaults to TRUE and its switch is
    visible only when Hermes is installed. On every fresh system the native tools were never sent
    to the model at all. The feature did not run.
  * where they did run, ONE tool call was handled per answer and the follow-up request carried no
    tools, so "look, then repair, then check" was impossible;
  * a follow-up that returned nothing left the "…" row on screen forever;
  * `history.slice(-12)` could keep a `tool` message while dropping the assistant `tool_calls`
    message it answers — an HTTP 400 from every OpenAI-compatible provider;
  * a confirmed action was run with `subprocess.run(timeout=90)`, which KILLED moai-do in the
    middle of an update or an install and told the model it had failed.

Every gate was green, because they assert the presence of strings.

This gate runs the behaviour:

  1. AgentLoop.js (the pure half) in node: stream assembly, several calls per answer, malformed
     arguments, confirmation rules, provider-valid history and group-safe trimming, display text.
  2. The REAL window (qml-qt6, offscreen) against a scripted provider and the REAL moai-control,
     with agentMode left at its default and no Hermes: the provider must RECEIVE the tools, the
     inspector runs with no card, the repair waits for the card, its real exit status reaches the
     model, and the conversation the provider sees is valid at every step.

Part 2 needs a Qt QML runtime and skips where there is none (the repo-gates runner); part 1 runs
wherever node does.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOOP_JS = ROOT / "system_files/usr/share/moos/apps/moai/AgentLoop.js"
MAIN_QML = ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
HARNESS = ROOT / "tests/qml/moai-tools-review.qml"
CONTROL = ROOT / "system_files/usr/bin/moai-control"
QML_RUNTIME = shutil.which("qml-qt6") or shutil.which("qml6") or shutil.which("qml")


def node(expression: str):
    source = LOOP_JS.read_text(encoding="utf-8").replace(".pragma library", "")
    done = subprocess.run(["node", "-e", source + f"\nprocess.stdout.write(JSON.stringify({expression}));"],
                          capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def sse(*events: dict) -> str:
    return "".join("data: " + json.dumps(e) + "\n\n" for e in events) + "data: [DONE]\n\n"


def call_delta(index: int, call_id: str, name: str, arguments: str) -> dict:
    return {"choices": [{"delta": {"tool_calls": [
        {"index": index, "id": call_id, "type": "function",
         "function": {"name": name, "arguments": arguments}}]}}]}


@unittest.skipUnless(shutil.which("node"), "node is needed to execute the shipped AgentLoop.js")
class ThePureHalf(unittest.TestCase):
    def test_a_streamed_answer_with_two_calls_is_assembled_from_fragments(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"Let me "}}]}',
            'data: {"choices":[{"delta":{"content":"look."}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"a1","function":{"name":"read_jou","arguments":"{\\"unit\\":"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"name":"rnal","arguments":"\\"pipewire.service\\"}"}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":1,"id":"b2","function":{"name":"memory_status","arguments":""}}]}}]}',
            "data: [DONE]", ": keep-alive", "",
        ]
        result = node("(function(){var s=newStream();" + "".join(f"feed(s,{json.dumps(l)});" for l in lines)
                      + "return {text:s.text, calls:finishedCalls(s)};})()")
        self.assertEqual(result["text"], "Let me look.")
        self.assertEqual([(c["id"], c["name"], c["args"]) for c in result["calls"]],
                         [("a1", "read_journal", {"unit": "pipewire.service"}), ("b2", "memory_status", {})])

    def test_malformed_and_excess_calls_are_answered_not_dropped(self):
        calls = node("finishedCalls({toolCalls:["
                     "{id:'1',name:'a',arguments:'{not json'},{id:'2',name:'b',arguments:'[1]'},"
                     "{id:'3',name:'c',arguments:'{}'},{id:'4',name:'d',arguments:''},"
                     "{id:'5',name:'e',arguments:'{}'},{id:'6',name:'',arguments:'{}'}]})")
        self.assertEqual([c["name"] for c in calls], ["a", "b", "c", "d", "e"], "a nameless call is noise")
        self.assertEqual([c["invalid"] for c in calls], [True, True, False, False, False])
        self.assertEqual([c["skipped"] for c in calls], [False, False, False, False, True],
                         "the fifth call is told it was not run; it is never silently lost")

    def test_the_stream_reports_an_upstream_error_event(self):
        stream = node("(function(){var s=newStream();"
                      "feed(s,'data: {\"choices\":[{\"delta\":{\"content\":\"half\"}}]}');"
                      "feed(s,'data: {\"error\":{\"message\":\"upstream stream ended early\"}}');return s;})()")
        self.assertEqual((stream["text"], stream["error"]), ("half", "upstream stream ended early"))

    def test_confirmation_follows_the_category_and_the_dangerous_value(self):
        wifi = {"category": "control", "confirm_values": {"value": ["off"]}}
        self.assertTrue(node(f"needsConfirmation({json.dumps(wifi)}, {{value:'off'}})"))
        self.assertFalse(node(f"needsConfirmation({json.dumps(wifi)}, {{value:'on'}})"))
        self.assertTrue(node("needsConfirmation({category:'privileged_confirm'}, {})"))
        self.assertTrue(node("needsConfirmation({category:'user_confirm'}, {})"))
        self.assertFalse(node("needsConfirmation({category:'read_only'}, {})"))
        self.assertTrue(node("needsConfirmation(null, {})"), "an unknown tool is never auto-run")

    def test_history_is_the_shape_a_provider_accepts(self):
        messages = node("toolMessages('', [{id:'a',name:'x',args:{k:1}},{id:'b',name:'y',args:{}}], ['one','two'])")
        self.assertEqual(messages[0]["role"], "assistant")
        self.assertIsNone(messages[0]["content"])
        self.assertEqual([c["id"] for c in messages[0]["tool_calls"]], ["a", "b"])
        self.assertEqual(json.loads(messages[0]["tool_calls"][0]["function"]["arguments"]), {"k": 1})
        self.assertEqual([(m["role"], m["tool_call_id"], m["content"]) for m in messages[1:]],
                         [("tool", "a", "one"), ("tool", "b", "two")])

    def test_trimming_never_leaves_a_tool_message_without_its_call(self):
        history = []
        for turn in range(12):
            history.append({"role": "user", "content": f"q{turn}"})
            history.append({"role": "assistant", "content": None,
                            "tool_calls": [{"id": f"c{turn}", "type": "function",
                                            "function": {"name": "x", "arguments": "{}"}}]})
            history.append({"role": "tool", "tool_call_id": f"c{turn}", "name": "x", "content": "r"})
            history.append({"role": "assistant", "content": f"a{turn}"})
        for limit in range(1, 30):
            kept = node(f"trimHistory({json.dumps(history)}, {limit})")
            open_calls: set[str] = set()
            for message in kept:
                for call in message.get("tool_calls") or []:
                    open_calls.add(call["id"])
                if message["role"] == "tool":
                    self.assertIn(message["tool_call_id"], open_calls,
                                  f"limit={limit}: a tool result survived without the assistant "
                                  "message that called it — every provider answers HTTP 400")
            self.assertNotEqual(kept[0]["role"], "tool", f"limit={limit}")
            if any(m["role"] == "user" for m in history[-limit:]):
                self.assertEqual(kept[0]["role"], "user",
                                 f"limit={limit}: a window that contains the person's turn opens on it")

    def test_a_tool_row_shows_one_language_and_no_emoji(self):
        raw = "\U0001F50A الصوت 40% | Volume 40%\n\x1b[32m✓ اكتمل | Done\x1b[0m\n\nplain line"
        self.assertEqual(node(f"forDisplay({json.dumps(raw)}, false, 40)"), "Volume 40%\nDone\n\nplain line")
        arabic = node(f"forDisplay({json.dumps(raw)}, true, 40)")
        self.assertIn("الصوت 40%", arabic)
        self.assertNotIn("Volume", arabic)
        long = "\n".join(f"line {i}" for i in range(100))
        shown = node(f"forDisplay({json.dumps(long)}, false, 10)").splitlines()
        self.assertEqual((len(shown), shown[-1]), (11, "line 99"), "a long log keeps its NEWEST lines")


class _Provider(BaseHTTPRequestHandler):
    """A scripted OpenAI-compatible provider. It records every request it receives."""
    script: list[str] = []
    received: list[dict] = []

    def log_message(self, *_args):                     # keep the test output readable
        pass

    def do_GET(self):
        body = json.dumps({"status": "ok", "cost_policy": "free"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        type(self).received.append(json.loads(self.rfile.read(length) or b"{}"))
        step = len(type(self).received) - 1
        body = (type(self).script[step] if step < len(type(self).script)
                else sse({"choices": [{"delta": {"content": "unexpected extra request"}}]})).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("X-MoAI-Agent", "direct")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@unittest.skipUnless(QML_RUNTIME and shutil.which("xvfb-run") and sys.platform.startswith("linux"),
                     "needs a Qt QML runtime and Xvfb (absent on the repo-gates runner)")
class TheRealWindow(unittest.TestCase):
    maxDiff = None

    def drive(self, *, decline: bool, repair_exit: int):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        work = Path(tmp.name)
        (work / "bin").mkdir()
        # The repair is doubled (it would restart this machine's audio); everything else is real.
        (work / "bin/moai-do").write_text(
            "#!/bin/sh\n"
            f'case "$*" in *fix-audio*) echo "restarted pipewire | أُعيد تشغيل الصوت"; exit {repair_exit} ;; esac\n'
            f'exec bash "{ROOT / "system_files/usr/bin/moai-do"}" "$@"\n', encoding="utf-8")
        (work / "bin/moai-do").chmod(0o755)

        _Provider.received = []
        _Provider.script = [
            sse(call_delta(0, "call_look", "top_processes", '{"by":"memory"}')),
            sse({"choices": [{"delta": {"content": "Audio looks stuck; I will restart it."}}]},
                call_delta(0, "call_fix", "fix_audio", "{}")),
            sse({"choices": [{"delta": {"content": "FINAL ANSWER"}}]}),
        ]
        provider = ThreadingHTTPServer(("127.0.0.1", 0), _Provider)
        threading.Thread(target=provider.serve_forever, daemon=True).start()
        self.addCleanup(provider.shutdown)

        control_port, agent_port = free_port(), free_port()
        env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(work / "config"),
                   XDG_CACHE_HOME=str(work / "cache"), XDG_RUNTIME_DIR=str(work / "run"),
                   PATH=f"{work / 'bin'}{os.pathsep}{os.environ['PATH']}",
                   MOAI_CONTROL_PORT=str(control_port), MOAI_GATEWAY_PORT=str(provider.server_port),
                   QML_IMPORT_PATH=str(ROOT / "system_files/usr/lib64/qt6/qml"),
                   QML_DISABLE_DISK_CACHE="1", QT_QUICK_CONTROLS_STYLE="Basic", LIBGL_ALWAYS_SOFTWARE="1")
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
            env.pop(name, None)                        # a gate must never reach a live desktop
        (work / "run").mkdir(mode=0o700)
        control = subprocess.Popen([sys.executable, str(CONTROL)], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(lambda: (control.terminate(), control.wait(timeout=10)))
        for _ in range(100):
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", control_port)) == 0:
                    break
            threading.Event().wait(0.1)
        else:
            self.fail("moai-control never started listening")

        out = work / "shots"
        out.mkdir()
        argv = ["xvfb-run", "-a", "-s", "-screen 0 1600x1000x24", QML_RUNTIME, str(HARNESS), "--",
                "--gateway-port", str(provider.server_port), "--control-port", str(control_port),
                "--agent-port", str(agent_port), f"--out={out}"] + (["--decline"] if decline else [])
        done = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
        line = next((l for l in (done.stderr + done.stdout).splitlines() if "REVIEW-RESULT " in l), "")
        self.assertTrue(line, f"the window reported nothing (rc={done.returncode}):\n{done.stderr[-1500:]}")
        report = json.loads(line.split("REVIEW-RESULT ", 1)[1])
        keep = os.environ.get("MOOS_REVIEW_SHOTS")
        if keep:
            for shot in out.glob("*.png"):
                shutil.copy(shot, Path(keep) / f"{'decline' if decline else 'run'}-{shot.name}")
        return report, _Provider.received

    def check_conversation_is_valid(self, requests: list[dict]):
        for number, request in enumerate(requests, 1):
            open_calls: set[str] = set()
            for message in request["messages"]:
                for call in message.get("tool_calls") or []:
                    open_calls.add(call["id"])
                if message["role"] == "tool":
                    self.assertIn(message["tool_call_id"], open_calls,
                                  f"request {number} carries a tool result with no matching call")

    def test_look_then_repair_then_answer_on_a_machine_without_hermes(self):
        report, requests = self.drive(decline=False, repair_exit=0)
        self.assertEqual(report["verdict"], "ok", report)
        self.assertTrue(report["agentMode"], "agentMode must stay at its shipped default for this proof")
        self.assertFalse(report["hermesReady"])
        self.assertEqual(len(requests), 3, "look → repair → answer is three provider requests")
        for number, request in enumerate(requests, 1):
            self.assertGreaterEqual(len(request.get("tools") or []), 30,
                                    f"request {number} reached the provider WITHOUT tools — W4's defect")
        self.check_conversation_is_valid(requests)
        roles = [m["role"] for m in requests[2]["messages"]]
        self.assertEqual(roles[-4:], ["assistant", "tool", "assistant", "tool"])
        looked = requests[1]["messages"][-1]
        self.assertEqual(looked["name"], "top_processes")
        self.assertIn("top processes by memory", looked["content"], "the REAL inspector must have run")
        repaired = requests[2]["messages"][-1]
        self.assertEqual(repaired["name"], "fix_audio")
        self.assertIn("restarted pipewire", repaired["content"])
        self.assertNotIn("did NOT succeed", repaired["content"])
        shown = [r["role"] for r in report["rows"]]
        self.assertEqual(shown.count("tool-success"), 2, report["rows"])
        self.assertEqual(report["rows"][-1], {"role": "assistant", "text": "FINAL ANSWER"})
        self.assertFalse(report["busy"])

    def test_a_failed_repair_reaches_the_model_as_a_failure(self):
        report, requests = self.drive(decline=False, repair_exit=3)
        self.assertEqual(report["verdict"], "ok", report)
        repaired = requests[2]["messages"][-1]
        self.assertIn("exit code 3", repaired["content"])
        self.assertIn("did NOT succeed", repaired["content"],
                      "P3.7: a failed tool result must make a task-wide success impossible")
        self.assertIn("tool-error", [r["role"] for r in report["rows"]])

    def test_declining_runs_nothing_and_tells_the_model_so(self):
        report, requests = self.drive(decline=True, repair_exit=0)
        self.assertEqual(report["verdict"], "ok", report)
        declined = requests[2]["messages"][-1]
        self.assertEqual(declined["name"], "fix_audio")
        self.assertIn("declined", declined["content"])
        self.assertNotIn("restarted pipewire", json.dumps(requests),
                         "a declined action must never reach the executor")


class TheWiring(unittest.TestCase):
    def test_tools_are_attached_whenever_the_request_is_not_hermes(self):
        qml = MAIN_QML.read_text(encoding="utf-8")
        self.assertNotIn("root.availableTools.length > 0 && !root.agentMode", qml,
                         "W4's condition: with agentMode defaulting to true the tools were never sent")
        self.assertIn("!(root.agentMode && root.hermesReady)", qml)
        self.assertEqual(qml.count("request.tools = root.availableTools"), 2,
                         "the first request AND the follow-up must carry the tools")
        self.assertIn('import "AgentLoop.js" as AgentLoop', qml)

    def test_no_emoji_stands_in_for_an_icon_in_the_loop(self):
        qml = MAIN_QML.read_text(encoding="utf-8")
        body = qml[qml.index("function beginToolBatch"):qml.index("function openPicker")]
        offenders = sorted({ch for ch in body if 0x1F000 <= ord(ch) <= 0x1FAFF or 0x2600 <= ord(ch) <= 0x27BF})
        self.assertEqual(offenders, [], "tool rows use MoOS symbolic icons, never emoji")


if __name__ == "__main__":
    unittest.main(verbosity=2)
