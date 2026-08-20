#!/usr/bin/env python3
"""Login reconciliation must preserve central custom wallpaper state."""

from pathlib import Path
import re

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

# At Plasma login the first live readback can briefly see the scene that was left
# in memory before session restore finishes loading the containment config.  The
# marker fast path must therefore keep watching through that bounded settle
# window; a single green read immediately after plasmashell appears is not proof.
marker_fast_path = migrator.split('if [ -e "$marker" ]; then', 1)[1].split(
    'echo "=== moos-apply-theme', 1
)[0]
if 'moos-theme settle-lnf "$lnf"' not in marker_fast_path:
    raise SystemExit(
        "login fast path trusts one early wallpaper read and can miss session-restore drift"
    )
if marker_fast_path.index('verify-lnf "$lnf"') > marker_fast_path.index(
    'settle-lnf "$lnf"'
):
    raise SystemExit("login settle must follow the initial complete-state readback")

settle_match = re.search(r"(?ms)^settle_lnf_state\(\) \{.*?^\}$", owner)
if not settle_match:
    raise SystemExit("central theme owner has no bounded login-settle verifier")
settle = settle_match.group(0)
if "settle_desktop_scene" not in settle or "full_theme_complete state" not in settle:
    raise SystemExit("login settle does not repair and then verify the complete live state")

print("OK: login reconciliation preserves custom state through the one theme owner")
