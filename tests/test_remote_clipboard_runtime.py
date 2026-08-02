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
        "if (!ClipboardBridge.SetText(text))" in injector
        and "Clipboard typing aborted" in injector and "ScheduleClipboardReturn(gen);" in injector,
    "no behavioural proof exercises a genuinely hung helper and an oversized result":
        '"sleep 20"' in tests and "clipboard timeout is real and bounded" in tests
        and "oversized clipboard output is rejected" in tests,
}

failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote clipboard runtime gate failed:\n- " + "\n- ".join(failed))
print("remote clipboard runtime gate passed")
