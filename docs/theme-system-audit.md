# MoOS Theme System — Complete Audit

**Date:** 2026-08-06  
**Auditor:** Agent (full codebase + live system inspection)

## Architecture Overview

MoOS ships **one design engine** (UI2 — Liquid Glass) that is **recoloured** into a family of 16 look-and-feel packages. The engine is NOT one theme copied 16 times — it is ONE geometry/SVG/QML set + ONE Python generator that stamps out palette-specific packages.

### The Generation Chain

```
palette.json (Graphite/Tidal base)
palettes.json (Nova, Amethyst, Midnight, Aurora, Arena, Forge, Scholar + lights)
        ↓
generate_moos_ui2.py       → MoOSUI2 (dark) + MoOSUI2Light
generate_moos_themes.py    → 14 family members (Nova, Amethyst, …)
generate_moos_plasma_surfaces.py  → SVG widgets (button, frame, tasks, panel, …)
generate_moos_aurorae.py   → Aurorae window decorations
generate_moos_symbolic_icons.py   → palette-matched symbolic icon overlays
generate_moos_app_icons.py        → first-party app marks (baked per palette)
```

### Per-Theme Package Set (what a "complete theme" IS)

Each of the 16 themes ships ALL of:

| Component | Path | Example (Graphite Dark) |
|---|---|---|
| Look-and-Feel | `plasma/look-and-feel/org.moos.ui2` | metadata + defaults |
| Desktop Theme (Plasma Style) | `plasma/desktoptheme/MoOSUI2` | SVGs, colors, plasmarc |
| Color Scheme | `color-schemes/MoOSUI2Dark.colors` | KDE color groups |
| Aurorae Decoration | `aurorae/themes/MoOSUI2` | window frame SVGs |
| Icon Theme | `icons/MoOSUI2` | symbolic overlays on Breeze |
| Wallpaper | `wallpapers/MoOSUI2Graphite` | 3840×2160 master |
| Konsole Profile | `konsole/MoOSUI2.profile` | terminal colors |
| Cursor Theme | (shared) `MoOS` (dark) / `MoOSDark` (light) | cursor SVGs |

### The 16 Shipped Themes

| Family | Dark | Light |
|---|---|---|
| Base (Graphite/Tidal) | `org.moos.ui2` | `org.moos.ui2.light` |
| Nova | `org.moos.ui2.nova` | `org.moos.ui2.nova.light` |
| Amethyst | `org.moos.ui2.amethyst` | `org.moos.ui2.amethyst.light` |
| Midnight / Daylight | `org.moos.ui2.midnight` | `org.moos.ui2.midnight.light` |
| Aurora | `org.moos.ui2.aurora` | `org.moos.ui2.aurora.light` |
| Arena (Gaming) | `org.moos.ui2.gaming` | `org.moos.ui2.gaming.light` |
| Forge (Dev) | `org.moos.ui2.dev` | `org.moos.ui2.dev.light` |
| Scholar (Study) | `org.moos.ui2.study` | `org.moos.ui2.study.light` |

## Findings

### ✓ What Works Well

1. **The generation pipeline is sound.** `generate_moos_ui2.py` + `generate_moos_themes.py` + `generate_moos_plasma_surfaces.py` + `generate_moos_aurorae.py` correctly stamp out complete packages for all 16 themes from shared geometry and per-family palettes.

2. **`moos-apply-theme` is comprehensive.** It handles:
   - Versioned migration markers (THEME_REV=30)
   - Drift detection and self-healing
   - Day/night switch target pinning
   - GTK across all three sources (GSettings, xsettingsd, settings.ini)
   - Sound theme pinning
   - Konsole profile switching
   - Icon theme + KIconLoader signal
   - Cursor theme
   - Lock screen + desktop wallpaper
   - Desktop scene (wallpaper plugin)
   - Shadow cleanup (user-level overrides)

3. **`moos-theme` handles all 16 themes** with toggle/undo/auto/motion.

4. **The bar definition is clean** — single source of truth in `moos-bar.conf` with `moos-bar-apply` as the sole writer.

5. **All SVGs are generated**, not hand-edited copies, which eliminates drift between themes.

### ✗ Issues Found

#### Critical: Home Shadows Blocking Image Updates (LIVE)

The `moos-selfcheck` found **3 stale home shadows** on this machine:
- `~/.local/share/plasma/plasmoids/org.moos.nova.clock` — shadows `/usr`
- `~/.local/share/plasma/plasmoids/org.moos.brand` — shadows `/usr`
- `~/.local/share/plasma/desktoptheme/MoOSUI2` — shadows `/usr`

These were planted by a live preview session (Aug 6). `moos-apply-theme` already has the cleanup code (lines 773-795 for icons, lines 792-795 for plasmoids), but the **desktop theme shadow class is NOT covered** — the cleanup loop at line 1392 lists `plasma/desktoptheme/MoOSUI2` etc. but only fires when `[ -e "/usr/share/$rel" ]` — which is always true for MoOSUI2. The issue is that these shadows were created AFTER the last theme apply, so the marker didn't trigger a new apply.

#### Medium: Repeated Wallpaper "Healing" in Log

The apply log shows repeated `steady-state: desktop wallpaper ... != ... — healing` entries across multiple logins when the user was on NovaLight but the wallpaper showed Graphite. The wallpaper reconciler is working correctly but the fact it fires repeatedly suggests a race between Plasma's own wallpaper persistence and the reconciler.

#### Medium: Tasks SVG Hover/Focus Borders

The `tasks.svg` contains `normal`, `hover`, `focus`, `minimized`, and `attention` states. Each state has the standard 9-patch border elements. The hover and focus states have visible borders that could appear as "boxes" around task buttons — this is the SVG providing the frame art for each state.

#### Low: QML Warnings from Upstream

The journal shows `No QSGTexture provided from updateSampledImage()` warnings and `BackgroundAppItem.qml` TypeError nulls — these are **upstream Plasma 6 issues**, not MoOS QML.

#### Low: `kdedefaults/` Remnants

The `kdedefaults` directory shows `ColorScheme=MoOSUI2Dark` and `decoration=__aurorae__svg__MoOSUI2` — these match the current theme so they're correct. The AGENTS.md extensively documents how kdedefaults outranks /etc/xdg, and the fix is already in moos-apply-theme (writing directly to ~/.config/).

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    GENERATION TIME                      │
│                                                         │
│  palette.json ──→ generate_moos_ui2.py ──→ Graphite/    │
│  palettes.json ─→ generate_moos_themes.py → + 14 family│
│                      │                                  │
│         ┌────────────┼────────────┐                     │
│         ↓            ↓            ↓                     │
│  plasma_surfaces  aurorae    symbolic_icons              │
│  (SVGs ×16)     (frames ×16)  (icons ×16)               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     RUNTIME                             │
│                                                         │
│  Login ──→ moos-apply-theme (autostart)                 │
│              │                                          │
│              ├→ pin_lookandfeel_switch_targets()         │
│              ├→ pin_sound_theme()                       │
│              ├→ theme_intact() check                    │
│              ├→ reconcile_wallpaper_drift()              │
│              ├→ plasma-apply-lookandfeel                 │
│              ├→ apply_desktop_scene()                    │
│              ├→ plasma-apply-colorscheme                 │
│              ├→ cursor, konsole, kwin, gtk pins          │
│              ├→ moos-bar-apply (dock structure)          │
│              └→ marker written only after readback       │
│                                                         │
│  User ──→ moos-theme <name>                             │
│              │                                          │
│              ├→ full LNF + all pins (same as above)     │
│              └→ undo marker saved for rollback           │
└─────────────────────────────────────────────────────────┘
```
