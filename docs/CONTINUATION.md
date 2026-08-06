# Theme System Continuation

Date: 2026-08-06
Branch: `feat/moos-horizon-bar`
Rollback point: `backup/theme-system-2026-08-06` and `backup-theme-system-2026-08-06`

## Completed

- Added marker-independent, idempotent quarantine for MoOS-owned user data shadows. New shadows are discovered from the package namespace and moved to a dated backup before the marker fast path.
- The live `~/.local/share/plasma/desktoptheme/MoOSUI2Arena` preview was quarantined to `~/.local/share/MoOS/theme-shadow-backups/20260806T202217Z/`.
- Refined the shared task surface generation so hover does not claim pinned applications are running. `normal`, `minimized`, and `focus` retain palette-owned running indicators.
- Regenerated the 16 UI2 family packages and updated the legacy Nova generator contract.
- Added wallpaper steady-state regression coverage. Reconciliation now checks every desktop containment and retries only while the live scene is not ready.
- Created the missing plan and continuation documents.

## Live Validation

- Active session: Wayland; `plasma-plasmashell.service` and `plasma-kwin_wayland.service` active.
- `systemctl --user --failed` returned zero failed units.
- Switched live desktop to `org.moos.ui2.nova.light` and read back `MoOSUI2NovaLight` for the color scheme and Plasma style.
- Read back `/usr/share/wallpapers/MoOSUI2NovaLight` from `plasma-org.kde.plasma.desktop-appletsrc`.
- Ran the repository `moos-apply-theme` script successfully and captured a live screenshot with `moai-screenshot`.
- No new crash or plasmashell restart was observed during the final switch. Existing upstream QML/system-tray warnings remain documented in `PROJECT_STATE.md`.

## Tests

Passed:

- `python3 tests/test_theme_shadow_cleanup.py`
- `python3 tests/test_theme_wallpaper_steady_state.py`
- `python3 tests/test_theme_wallpaper_readback.py`
- `python3 tests/test_moos_theme_safety.py`
- `python3 tests/test_moos_ui2.py`
- `bash -n system_files/usr/bin/moos-apply-theme system_files/usr/bin/moos-selfcheck system_files/usr/bin/moos-theme`
- `python3 artwork/generate_moos_ui2.py`
- `python3 artwork/generate_moos_themes.py`

The full `tests/verify_user_experience.py` gate passed after the final generator and shadow changes.

## Files

Theme runtime: `system_files/usr/bin/moos-apply-theme`, `system_files/usr/bin/moos-selfcheck`.

Generators: `artwork/generate_moos_plasma_surfaces.py`, `artwork/generate_moos_ui2.py`, `artwork/generate_moos_themes.py`, `artwork/tools/gen-nova-plasma-svgs.py`.

Tests: `tests/test_theme_shadow_cleanup.py`, `tests/test_theme_wallpaper_steady_state.py`, `tests/test_theme_wallpaper_readback.py`, `tests/test_moos_ui2.py`, `tests/verify_user_experience.py`.

## Remaining

- Install the changed runtime tools into a disposable live image or build the image, then repeat the login/reboot test against `/usr/bin` rather than the repository copy.
- Run visual checks at 100%, 125%, 150%, and 200%, and test launcher, clock/calendar, tray, RTL/LTR, and window decoration after a real session restart.
- Run the complete CI-equivalent gate list and the appropriate image build.

## Handoff

The next agent should inspect `git status` and the existing parallel Horizon Bar changes before staging. Do not reset them. First run `python3 tests/verify_user_experience.py` after reconciling its expected revision and bar contracts, then run the complete theme-specific suite. Keep the backup branch/tag intact. The live user currently wears Nova Light; restore it with `moos-theme nova-light` or use `moos-theme undo` after testing.
