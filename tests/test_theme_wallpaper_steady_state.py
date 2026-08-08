#!/usr/bin/env python3
"""Login reconciliation must preserve central custom wallpaper state."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
owner = (ROOT / "system_files/usr/bin/moos-theme").read_text(encoding="utf-8")
migrator = (ROOT / "system_files/usr/bin/moos-apply-theme").read_text(encoding="utf-8")

for required in (
    "load_wallpaper_expectation state",
    "custom_wallpapers_complete",
    "apply_desktop_scene_token",
    "settle_desktop_scene",
    "wallpaperMode",
    "wallpaperEncoded",
):
    if required not in owner:
        raise SystemExit(f"central wallpaper reconciler missing {required!r}")

for retired_duplicate in (
    "reconcile_wallpaper_drift",
    "lnf_wallpaper_package",
    "current_desktop_wallpaper_value",
    "apply_desktop_scene()",
):
    if retired_duplicate in migrator:
        raise SystemExit(
            f"revision migrator regained wallpaper ownership: {retired_duplicate}"
        )

if 'moos-theme verify-lnf "$lnf"' not in migrator:
    raise SystemExit("login fast path no longer delegates full state verification")

print("OK: login reconciliation preserves custom state through the one theme owner")
