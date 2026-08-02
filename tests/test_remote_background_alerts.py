#!/usr/bin/env python3
"""Gate the private, opt-in boundary for Mo PC Remote phone alerts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
helper = (ROOT / "moremote/controller/src/lib/notifications.ts").read_text(encoding="utf-8")
screen = (ROOT / "moremote/controller/src/ui/RemoteScreen.tsx").read_text(encoding="utf-8")
worker = (ROOT / "moremote/controller/public/notification-sw.js").read_text(encoding="utf-8")

checks = {
    "alerts can silently prompt without a user gesture":
        "requestRemoteAlertPermission" in screen and "onToggle={() => void toggleBackgroundAlerts()}" in screen,
    "alerts work on an insecure origin or outside the service worker boundary":
        "window.isSecureContext" in helper and '"serviceWorker" in navigator' in helper,
    "the phone can receive arbitrary desktop or user-content notification text":
        "showRemoteAlert(kind: RemoteAlert)" in helper
        and 'RemoteAlert = "connection-interrupted" | "upload-complete"' in helper,
    "foreground use creates redundant phone notifications":
        "!document.hidden" in helper,
    "alerts introduce a polling loop while idle":
        "setInterval(" not in helper and "setInterval(" not in worker,
    "notification taps do not return to the controller":
        "notificationclick" in worker and "existing.focus()" in worker
        and 'clients.openWindow("/")' in worker and "event.notification.data" not in worker,
    "the settings copy overclaims desktop notification mirroring":
        "Desktop notifications, filenames and clipboard content never leave the PC." in screen,
}

failed = [message for message, ok in checks.items() if not ok]
if failed:
    raise SystemExit("remote background-alert gate failed:\n- " + "\n- ".join(failed))
print("remote background-alert gate passed")
