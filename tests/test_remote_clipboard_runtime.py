#!/usr/bin/env python3
"""Gate the Remote clipboard bridge's bounded subprocess and honest API contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
linux = (ROOT / "moremote/agent-linux/ClipboardBridge.cs").read_text(encoding="utf-8")
injector = (ROOT / "moremote/agent-linux/InputInjector.cs").read_text(encoding="utf-8")
windows = (ROOT / "moremote/agent/Core/ClipboardBridge.cs").read_text(encoding="utf-8")
api = (ROOT / "moremote/agent/Web/WebApi.cs").read_text(encoding="utf-8")
tests = (ROOT / "moremote/tests/MoRemote.Tests/Program.cs").read_text(encoding="utf-8")

checks = {
    "Linux clipboard output is still read synchronously before its timeout can fire":
        "WaitForExitAsync(deadline.Token)" in linux
        and "ReadBoundedAsync(process.StandardOutput.BaseStream" in linux,
    "a timed-out clipboard helper can survive and retain the request":
        "process.Kill(entireProcessTree: true)" in linux,
    "clipboard reads can allocate an unbounded payload":
        "MaxClipboardBytes = 25_000_000" in linux
        and 'throw new InvalidDataException("Clipboard exceeds its size limit")' in linux,
    "subprocess arguments can be reinterpreted through shell-style string splitting":
        "start.ArgumentList.Add(arg)" in linux,
    "Linux clipboard writes still discard the helper exit status":
        "return process.ExitCode == 0" in linux
        and "public static bool SetText" in linux,
    "Windows clipboard writes still cannot report timeout or failure":
        "public static bool SetText" in windows and "return t.Join(5000) && result" in windows,
    "the phone API still claims clipboard success after the platform rejected it":
        api.count('error = "clipboard_unavailable"') == 2
        and "ClipboardBridge.SetText" in api and "ClipboardBridge.SetImagePng" in api,
    "remote Unicode typing pastes even when wl-copy rejected its payload":
        "if (!ClipboardBridge.SetTextConfirmed(text))" in injector
        and "Clipboard typing aborted" in injector and "ScheduleClipboardReturn(gen);" in injector,
    # LIVE-PROVEN on the Cloud session, 2026-08-03: wl-copy returns as soon as it has forked the
    # process that will SERVE the selection, not when the compositor hands that content to readers.
    # Three Arabic words injected with an immediate Shift+Insert produced " في مشكلة " — the first
    # word gone. The same three with the read-back below produced "لسى في مشكلة ", intact. That
    # race IS "Arabic types scrambled and letters go missing".
    "the paste still races the copy — wl-copy returns before the selection is servable":
        "SetTextConfirmed" in linux and "ConfirmAttempts" in linux
        and "GetText()" in linux
        and "if (!ClipboardBridge.SetText(text))" not in injector,
    # A space is ON the fast keysym path, so while Arabic waited in the paste buffer the space was
    # injected immediately and landed a letter early ("لسى في" -> "لس ىف"). Whatever is gathering
    # owns the order until it is delivered.
    "a fast-path character can still overtake text already gathering for a paste":
        injector.index("_pending.Length > 0") < injector.index("TryDirectStrokes(text, out var events)")
        and all("FlushPendingText" in injector.split(member, 1)[1][:420]
                for member in ("public void KeyTap", "public void KeyDown", "public void Combo")),
    "no behavioural proof exercises a genuinely hung helper and an oversized result":
        '"sleep 20"' in tests and "clipboard timeout is real and bounded" in tests
        and "oversized clipboard output is rejected" in tests,
    # 2026-08-03: "paste anyway" after a failed confirm delivered whatever the clipboard held —
    # the previous clipboard, or a manager's rewrite — into the middle of the user's sentence.
    # An unconfirmed copy now SKIPS its paste: a dropped word the user retypes beats a wrong
    # word they never typed. Broken once by restoring `return true;` after the budget.
    "an unconfirmed clipboard copy still pastes stale content":
        "skipping the paste rather than delivering stale content" in linux
        and "pasting anyway" not in linux,
    # 2026-08-03, from the live agent log: at the owner's real typing cadence the phone's 220 ms
    # window loses its race and text arrives letter-by-letter — and the agent then held EVERY
    # chunk, even a client-coalesced whole word, for its own fixed 140 ms gather. A fixed tax on
    # every word of Arabic. Multi-character chunks now flush at once (the gather exists to merge
    # single letters), and the agent's gather carries the same 700 ms age cap as the client's,
    # which was the half of the shipped "240 chars / 700 ms" bound that only existed client-side.
    "the agent still taxes already-coalesced words with its own gather delay":
        injector.count("text.Length > 1 ||") == 2
        and "PasteMaxHoldMs = 700" in injector
        and "_pendingSince" in injector,
}

failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote clipboard runtime gate failed:\n- " + "\n- ".join(failed))
print("remote clipboard runtime gate passed")
