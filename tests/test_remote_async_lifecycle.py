#!/usr/bin/env python3
"""Prevent delayed UI work from resurrecting a signed-out Remote screen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
screen = (ROOT / "moremote/controller/src/ui/RemoteScreen.tsx").read_text(encoding="utf-8")

checks = {
    "Refresh still uses an unowned connect timeout":
        "refreshTimerRef.current = window.setTimeout" in screen
        and "window.clearTimeout(refreshTimerRef.current)" in screen,
    "Disconnect does not cancel the pending Refresh reconnect":
        "const disconnect = () => {" in screen
        and screen[screen.index("const disconnect = () => {"):].split("};", 1)[0].count("refreshTimerRef") >= 2,
    "audio ticket completion can start playback after Stop/unmount":
        "audioGenerationRef" in screen
        and screen.count("generation !== audioGenerationRef.current") >= 3,
    "audio cleanup leaves the media response and encoder alive":
        'a.removeAttribute("src")' in screen and "audioRetryRef.current = null" in screen,
    "toast and first-run hint timers can update an unmounted component":
        "toastTimer.current" in screen and "gestureHintTimer" in screen,
}
failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote async lifecycle gate failed:\n- " + "\n- ".join(failed))
print("remote async lifecycle gate passed")
