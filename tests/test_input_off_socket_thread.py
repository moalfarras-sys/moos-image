#!/usr/bin/env python3
"""Gate: injecting input must not block the socket that carries the pings.

THE MEASUREMENT THIS PROTECTS

Injecting input is not instantaneous and cannot be. A click must be a press, a pause and a release
or applications do not register it at all (InputInjector sleeps 25ms between them); a double-click
is 25+40+25; and text the keysym path cannot reach — Arabic, most punctuation — is typed by
borrowing the clipboard, which means spawning wl-copy and waiting for it.

When that ran on the thread reading the WebSocket, nothing else could be read while it happened.
Measured against the live agent over loopback, where the network contributes 0.7ms, by firing one
input and then fifteen pings back-to-back and timing the pongs:

    baseline            0.7 ms
    1 click            25.7 ms
    5 clicks          133.4 ms
    double-click       90.7 ms
    one Arabic word    43.2 ms

— the sleep constants exactly, plus the subprocess.

WHY IT IS WORSE THAN THE LATENCY

RemoteScreen's automatic quality ladder steps DOWN when the round trip crosses 400ms, and it reads
that round trip from these very pongs. On a cellular link with a 200ms base, a handful of clicks
and a word of Arabic push it over the line — so the picture degrades BECAUSE the user is using it,
and recovers when they stop touching it. No amount of encoder tuning can fix that, because the
encoder is not what is wrong; the measurement feeding the controller is.

WHAT MUST STAY TRUE

  1. the socket reader hands input off instead of performing it;
  2. exactly ONE consumer drains the queue, in order — a mouse-up that overtook its mouse-down
     leaves a button physically held down on the remote desktop, and a Shift-up that overtook the
     character it was shifting types the wrong thing;
  3. a full queue is never a dropped event. Dropping a mouse-up is the stuck-button bug above, so
     the enqueue site falls back to running inline rather than discarding.

Per AGENTS.md the assertions read the CODE with comments stripped.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SESSION = ROOT / "moremote/agent/Web/StreamSession.cs"


def strip_comments(src: str) -> str:
    out, in_block = [], False
    for line in src.splitlines():
        s = line.strip()
        if in_block:
            if "*/" in s: in_block = False
            continue
        if s.startswith("/*"):
            if "*/" not in s: in_block = True
            continue
        if s.startswith("//") or s.startswith("///"):
            continue
        out.append(re.sub(r"//.*$", "", line))
    return "\n".join(out)


def body_of(code: str, signature: str) -> str:
    """The text from a method signature to the start of the next member."""
    m = re.search(re.escape(signature) + r"[\s\S]*?(?=\n    (?:private|public|internal)\s)", code)
    return m.group(0) if m else ""


def main() -> int:
    if not SESSION.is_file():
        print(f"GATE FAIL: {SESSION.relative_to(ROOT)} is missing.")
        return 1

    code = strip_comments(SESSION.read_text(encoding="utf-8"))
    errors: list[str] = []

    # --- 1. the queue exists, and is a single-reader FIFO ----------------------------------------
    if "_inputQueue" not in code:
        errors.append("StreamSession has no input queue: input is injected on the thread that reads\n"
                      "        the socket, so every ping queues behind every click. The auto-quality\n"
                      "        ladder reads those pongs and will step the picture down while the user\n"
                      "        is simply using the remote.")
    else:
        if "SingleReader = true" not in code:
            errors.append("the input queue is not SingleReader. More than one consumer can reorder\n"
                          "        input: a mouse-up delivered before its mouse-down leaves a button held\n"
                          "        down on the remote desktop with nothing to release it.")
        if not re.search(r"CreateBounded", code):
            errors.append("the input queue is unbounded — a client that outruns injection would grow it\n"
                          "        without limit, which is a memory leak driven by a remote peer.")

    # --- 2. the socket reader must not perform injection -----------------------------------------
    handle = body_of(code, "private async Task HandleMessage")
    if handle:
        # The injection surface is reachable by two spellings — the local `input` alias that the
        # extracted method uses, and `_svc.Input` directly. The first version of this gate checked
        # only the first, so re-introducing the bug as `_svc.Input.MouseMove(...)` sailed straight
        # through it. A gate that misses the obvious way to write the bug is not a gate.
        stray = sorted(set(re.findall(r"(?:\binput|_svc\.Input)\.(\w+)\s*\(", handle)))
        # ExecuteInput is the handoff itself, not injection, and IsReady/LastError/BackendName are
        # property reads for the status message rather than work.
        stray = [s for s in stray if s not in {"IsReady", "LastError", "BackendName"}]
        if stray:
            errors.append("HandleMessage still injects input directly (" + ", ".join(stray) + ").\n"
                          "        That is the socket-reading thread; every one of those calls blocks the\n"
                          "        pings behind it.")
        if "_inputQueue.Writer" not in handle:
            errors.append("HandleMessage does not hand input to the queue.")

    # --- 3. a consumer exists -------------------------------------------------------------------
    if "private async Task InputLoop" not in code:
        errors.append("there is no InputLoop consumer, so anything written to the queue is never run —\n"
                      "        input would be accepted and silently never injected.")
    elif "InputLoop(ct)" not in code:
        errors.append("InputLoop is defined but never started, so the queue fills and input stops\n"
                      "        arriving entirely once it is full.")

    # --- 4. a full queue must never drop an event ------------------------------------------------
    if "_inputQueue.Writer.TryWrite" in code:
        m = re.search(r"if\s*\(!\s*_inputQueue\.Writer\.TryWrite[\s\S]{0,400}?\n\s*\}", code)
        if not m or "ExecuteInput" not in m.group(0):
            errors.append("the enqueue site does not fall back to running inline when the queue is full.\n"
                          "        Dropping input is not a safe failure: a dropped mouse-up is a button\n"
                          "        left held down on the remote desktop.")

    if errors:
        print("GATE FAIL: input injection would block the socket, or lose/reorder events.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: input is handed to a bounded single-reader FIFO, drained by InputLoop, "
          "with an inline fallback so no event can be dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
