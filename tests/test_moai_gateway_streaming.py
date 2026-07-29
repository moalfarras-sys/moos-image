#!/usr/bin/env python3
"""Gate: moai-gateway must not leave a chat reply hanging when the upstream drops.

WHY THIS EXISTS

The gateway proxies the chat stream from the cloud provider (or the local engine) to the
app as HTTP/1.1 chunked SSE. Two failure modes both showed the user a "generating…"
spinner that never cleared:

  1. THE HANG. _proxy() wrote the terminating chunk `0\\r\\n\\r\\n` only on the normal-EOF
     path and swallowed every mid-stream exception with `except Exception: pass`, leaving
     close_connection False. So a provider rate-limit/overload, a local model eviction, a
     network blip, or the urlopen timeout left the chunked body half-finished and the
     socket open — the client waited for ever. The fix must close the connection (EOF)
     and emit a synthetic error + [DONE] so the app can stop.

  2. THE SILENT ERROR (Anthropic wire). anthropic_stream_to_openai only handled
     content_block_delta and message_stop; an Anthropic `{"type":"error",...}` event that
     arrives after the 200, or a stream that just stops without message_stop, fell through
     to a clean [DONE] — indistinguishable from a finished but blank reply.

This drives the REAL translator with faked streams, and reads _proxy's source to pin the
close-on-drop behaviour (a full handler is impractical to instantiate here).
"""

import importlib.util
import json
import re
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = ROOT / "system_files/usr/bin/moai-gateway"


class FakeUpstream:
    """Yields its whole payload once, then EOF — like a single read1() burst."""

    def __init__(self, data: bytes):
        self.data = data
        self.done = False

    def read1(self, _n: int) -> bytes:
        if self.done:
            return b""
        self.done = True
        return self.data


def load_gateway():
    loader = SourceFileLoader("_moai_gateway_under_test", str(GATEWAY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def translate(module, payload: bytes) -> str:
    out: list[bytes] = []
    module.anthropic_stream_to_openai(FakeUpstream(payload), out.append)
    return b"".join(out).decode("utf-8", "replace")


def main() -> int:
    if not GATEWAY.is_file():
        print(f"GATE FAIL: {GATEWAY.relative_to(ROOT)} is missing.")
        return 1

    module = load_gateway()
    errors: list[str] = []

    # 1. Anthropic error event mid-stream: surfaced as text, then [DONE].
    got = translate(module,
                    b'data: {"type":"content_block_delta","delta":{"text":"Hi"}}\n'
                    b'data: {"type":"error","error":{"type":"overloaded_error","message":"Overloaded"}}\n')
    if "Hi" not in got:
        errors.append("delta text before the error was lost")
    if "Overloaded" not in got:
        errors.append("an Anthropic error event is not surfaced to the user — it reads as a blank "
                      "but 'successful' reply")
    if "[DONE]" not in got:
        errors.append("the error path does not end the stream with [DONE]")

    # 2. Truncated stream (no message_stop): flagged, not presented as complete.
    got = translate(module, b'data: {"type":"content_block_delta","delta":{"text":"partial"}}\n')
    if "partial" not in got or "[DONE]" not in got:
        errors.append("a truncated stream did not deliver its partial text and terminate")
    if "early" not in got.lower():
        errors.append("a stream that ends without message_stop is presented as a complete reply "
                      "instead of being flagged as ended early")

    # 3. Normal completion: content, no spurious warning.
    got = translate(module,
                    b'data: {"type":"content_block_delta","delta":{"text":"done"}}\n'
                    b'data: {"type":"message_stop"}\n')
    if "done" not in got or "[DONE]" not in got:
        errors.append("a normal completion did not deliver its text and [DONE]")
    if "⚠️" in got or "early" in got.lower():
        errors.append("a normal completion wrongly shows an error/ended-early warning")

    # 3b. THE ERROR MUST BE SPEAKABLE BY THE CLIENT. Mo AI parses choices[0].delta.content and
    #     nothing else, so a chunk shaped {"error": …} is silently dropped and the user sees a
    #     half-finished answer with no hint it was cut off. Render every synthetic notice
    #     through the client's own parser and require it to produce visible text.
    def client_render(raw: bytes) -> str:
        """Exactly what main.qml does with each SSE line."""
        rendered = ""
        for line in raw.decode("utf-8", "replace").splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload in ("", "[DONE]"):
                continue
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            choice = (event.get("choices") or [None])[0]
            rendered += ((choice or {}).get("delta", {}).get("content") or "")
        return rendered

    notice = module.anthropic_chunk("\n\n⚠️ test notice")
    if "test notice" not in client_render(notice):
        errors.append("anthropic_chunk does not produce something the app can render — every "
                      "synthetic notice must arrive as choices[0].delta.content")

    # …AND IT MUST SURVIVE A MID-LINE DROP. The OpenAI passthrough forwards raw upstream
    # bytes, so a connection that dies partway through an SSE line leaves a fragment like
    # `data: {"id":"x","cho` in the client's buffer. Appending the notice straight onto that
    # glues both into one unparseable line and the notice is lost with the fragment — the
    # user gets a truncated answer and still no explanation. A blank line must close the
    # fragment first.
    fragment = b'data: {"id":"x","cho'
    if "test notice" not in client_render(fragment + notice):
        # Confirm the terminator is what fixes it, then require it in the source.
        if "test notice" not in client_render(fragment + b"\n\n" + notice):
            errors.append("even with a blank-line terminator the notice does not render — the "
                          "synthetic-notice path is broken")
        proxy_for_terminator = re.search(r"def _proxy\(self.*?(?=\n    def )",
                                         GATEWAY.read_text(encoding="utf-8"), re.S)
        if not proxy_for_terminator or not re.search(
                r'write\(\s*b"\\n\\n"\s*\)', proxy_for_terminator.group(0)):
            errors.append("_proxy does not terminate the in-flight SSE line before writing its "
                          "synthetic notice. A drop mid-line leaves a partial `data:` fragment, "
                          "and the notice concatenated onto it is unparseable — so the user sees "
                          "a truncated reply with no explanation. Write b'\\n\\n' first.")

    # 4. _proxy must close the connection on a mid-stream drop (source-level: a full handler
    #    is impractical to instantiate). The success path sets a completion flag; the except
    #    path must, when not completed, set self.close_connection = True.
    code = GATEWAY.read_text(encoding="utf-8")

    proxy = re.search(r"def _proxy\(self.*?(?=\n    def )", code, re.S)
    if not proxy:
        errors.append("could not locate _proxy() to verify close-on-drop.")
    else:
        body = proxy.group(0)
        # The OpenAI-wire failure path must not emit a bare error object the client cannot see.
        if re.search(r'write\(\s*b?[\'"]data: \{"error"', body):
            errors.append("_proxy writes a raw {\"error\": …} SSE chunk on the OpenAI wire. The app "
                          "reads only choices[0].delta.content, so that is invisible — the user "
                          "gets a truncated answer with no explanation. Use anthropic_chunk(...).")
        if "except Exception:\n            pass" in body and "close_connection" not in body:
            errors.append("_proxy still swallows a mid-stream exception with a bare pass and never "
                          "sets close_connection — the client hangs for ever.")
        if "self.close_connection = True" not in body:
            errors.append("_proxy does not set self.close_connection on the failure path, so a "
                          "half-finished chunked stream leaves the client socket open.")

    if errors:
        print("GATE FAIL: moai-gateway streaming would hang or hide errors.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: streaming errors/truncation are surfaced with [DONE], and a mid-stream drop "
          "closes the connection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
