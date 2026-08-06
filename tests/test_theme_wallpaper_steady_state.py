#!/usr/bin/env python3
"""The login reconciler must verify all containments before declaring stability."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / "system_files/usr/bin/moos-apply-theme").read_text(encoding="utf-8")
start = source.index("reconcile_wallpaper_drift() {")
end = source.index("\n}\n", start) + 3
function = source[start:end]

for required in (
    "desktop_wallpapers_complete \"$pkg\"",
    "for attempt in 1 2 3 4 5",
    "apply_desktop_scene \"$pkg\"",
    "sleep 1",
):
    if required not in function:
        raise SystemExit(f"wallpaper steady-state reconciler missing {required!r}")

if "current_desktop_wallpaper_value" not in function:
    raise SystemExit("wallpaper reconciler lost its live readback")

print("OK: wallpaper reconciliation verifies every containment and retries only until ready")
