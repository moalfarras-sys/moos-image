# Unified MoOS Design Audit

Updated: 2026-08-08

This is the repository- and runtime-grounded ownership map for the MoOS unified
experience work. Generated files, old plans and a green source gate are not
treated as proof that a surface is used by the running session.

## Implementation outcome on this branch

The audit below was the before-state. It has now been resolved into one generated
architecture:

```
MoOS Design Core sources
  artwork/moos-design/tokens.json
  artwork/moos-design/theme-profiles.json
        |
        +--> artwork/generate_moos_design_core.py
        |      -> /usr/lib64/qt6/qml/org/moos/ui
        |
        +--> artwork/generate_moos_theme_profiles.py
               -> /usr/share/moos/theme-profiles.{json,tsv}
                        |
                        v
                 /usr/bin/moos-theme
          transaction + exact readback + undo
                        |
        shell / sessions / Qt / GTK / Konsole / apps
```

- All first-party and shell QML uses the installed `org.moos.ui` module; the
  former app-local `system_files/usr/share/moos/apps/ui` fork was deleted.
- Sixteen looks are data profiles, not sixteen UX implementations. The profile
  source now owns palette family, surface treatment, wallpaper, icons, cursor,
  decoration, Konsole, `qtWidgetStyle` and `gtkTheme`.
- `moos-theme` is the sole cascade writer. It snapshots files, GSettings and the
  exact live desktop scene, applies under one lock, reads every owner back and
  either commits schema-2 state/undo or restores the exact snapshot.
- Theme Picker and Control Center use the same transaction, including a safe
  custom-wallpaper token that keeps the MoOS wallpaper plugin and survives login
  reconciliation. `moos-apply-theme` owns revision/cache/layout migration only.
- Horizon Hub is one wallpaper-layer instrument below desktop icons; launcher,
  bar, settings, notifications and session portals use the same material,
  radius, type and motion roles.
- Qt and GTK deliberately keep Breeze as an internal renderer. MoOS owns what is
  visible through its generated palettes/CSS/icons/cursor/decoration; both engine
  names are now explicit profile data and are verified from the live desktop.

### Runtime and visual proof

- Dark/light Qt and GTK were launched and inspected; GTK4 computed the expected
  Graphite roles (`#4ED7C8`, `#1D2529`, `#E8F1EF`, `#232D32`) and Tidal roles
  (`#006D67`, `#C9E2DD`, `#17302E`, `#E1F0EC`).
- Lock, power/logout and splash loaded from the branch sources in their real
  Plasma hosts; plasmalogin overrides loaded without a fallback component.
- Real output QA covered 3840x2160 at 100%, 125%, 150% and 200%, then restored
  the owner's 225%; no bar/hub clipping or overlap appeared. Arabic RTL and a
  separately restarted English LTR shell both mirrored exactly once.
- The notification service was absent before the fix because the tray did not
  instantiate its applet. A real `org.freedesktop.Notifications` owner and popup
  were observed after the inventory repair.
- Wallpaper performance before: 10.25% `plasmashell` in Gentle and 11.3% in
  Alive. After replacing all endless animation with sparse finite bursts and
  slowing telemetry: 0.70% Gentle/Still and 2.85% Alive including a pulse; fresh
  RSS was ~513 MiB versus ~741 MiB before reload.
- Fast Remote was exercised live from Alive with the local brain active and a
  non-US keyboard. ON retained `org.moos.ui2.wallpaper`, selected Still, disabled
  the three captured KWin effects, wrote the duration to `kdeglobals`, suspended
  only the selected engine and selected US. OFF restored Alive, the exact
  present/missing KConfig values, layout index 0 and the active engine. That
  exercise exposed and fixed a parser that read the `32` in D-Bus's `uint32`
  type name instead of the returned layout value.

The initial unified branch was subsequently released as signed
`44.20260808.567` images, its exact NVIDIA digest was booted on the owner
machine, and the post-update suite passed 49/49. UEFI disk and offline-live ISO
boots also passed. Post-boot journal inspection then exposed a negative
launcher stagger delay during `DelegateModel index=-1` teardown; THEME_REV 47
clamps it to zero and is held by a regression gate. Four real 4K RTL launcher
open/close cycles now produce zero related warnings. Focused gates, `just
check`, and the corrected complete local `just build` are green; the corrected
local image is
`e1ef941cce6048cebde68cadff11383438683a20e5d676bebca516e3c980defe`.
Signed publication and boot proof of this corrective follow-up remain separate
release gates at the time of this audit update.

## Baseline actually inspected

- Repository baseline: clean `main` at `79dae9ad`; work continues on
  `feature/unified-moos-experience-2026-08-08`.
- Booted system: signed `moos-nvidia` `44.20260807.565`, with signed `.564`
  retained as the rollback deployment.
- Runtime: Wayland, one 3840x2160 output at 225%, system state `running`, zero
  failed system or user units.
- Effective theme readback: `org.moos.ui2`, `MoOSUI2Dark`, Plasma style and
  icons `MoOSUI2`, cursor `MoOS`, Aurorae `MoOSUI2`.
- Display manager: `/usr/lib/systemd/system/plasmalogin.service` from
  `plasma-login-manager-6.7.4`; neither `sddm` nor `sddm-wayland-plasma` is
  installed and no SDDM file exists in `system_files`.
- Baseline screenshots: full desktop and the real `org.moos.brand` full
  representation were captured at native 4K. Baseline `just check` completed
  successfully before the first source change.

## Effective owners

| Surface | Effective source | Generated/runtime relationship |
|---|---|---|
| Design palette and metrics | `artwork/moos-design/tokens.json` | `generate_moos_design_core.py` validates and produces the system-wide `org.moos.ui` module consumed by apps, shell and session surfaces. |
| Theme profiles | `artwork/moos-design/theme-profiles.json` | `generate_moos_theme_profiles.py` produces JSON/TSV runtime databases for all sixteen profiles. |
| First-party GTK palette | `system_files/usr/lib/moos/moos_ui2.py` | Reads the live KDE color scheme; `Breeze` is the internal GTK stylesheet engine, while MoOS owns the rendered palette through generated CSS. |
| Theme transaction | `system_files/usr/bin/moos-theme` | Reads the generated database, owns the full cascade, exact snapshot/rollback and complete live readback. |
| Theme state | `~/.local/state/moos/theme/theme-state.json` schema 2 | Records committed/rollback status, active/previous profiles and exact encoded profile/custom wallpaper identity; `undo/` is the exact previous snapshot. |
| Login | `plasmalogin` + `system_files/usr/lib/plasmalogin/defaults.conf` + `org.moos.ui2.greeter` | The compiled greeter consumes MoOS overrides of the Breeze component module. SDDM is not an owner. |
| Lock | `system_files/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen` | Authentication remains Plasma-owned; MoOS replaces the visual shell and shared login components. |
| Logout/power | `artwork/tidal-portal/Logout.qml` and generated LNF copies | All sixteen `Logout.qml` files and all sixteen action-button files are byte-identical generated outputs. |
| Splash | `artwork/tidal-portal/Splash.qml` and generated LNF copies | All sixteen shipped `Splash.qml` files are byte-identical generated outputs. |
| Desktop scene | `org.moos.ui2.wallpaper` + `moos-theme` | The custom plugin owns image + passive bento below icons. Every MoOS-owned wallpaper route preserves it through the transactional image token; the stock KCM remains an explicit external escape hatch and is repaired only when a MoOS profile is reapplied. |
| Panel/dock | `system_files/usr/share/moos/moos-bar.conf` | `layout.js` is the new-profile seed; `moos-bar-apply` is the existing-profile reconciler. One bottom containment is the enforced runtime shape. |
| Launcher | `org.moos.brand` | A first-party Kicker/Milou face; Kickoff is only a favorites migration source. |
| Clock popup | `org.moos.nova.clock` | First-party compact clock and MonthView popup; the historical package id is load-bearing. |
| Notifications | stock Plasma notification applet over MoOS Plasma SVGs | MoOS owns material/palette but has no shared QML notification composition. |
| Alt-Tab/Overview | stock KWin effects configured by MoOS | They inherit theme roles but are not MoUI consumers. |
| Theme Picker | `system_files/usr/share/moos/theme-picker/main.qml` | Uses MoUI, executes the one transaction and waits for the owner's complete verification. |
| Control Center | `system_files/usr/share/moos/apps/settings/main.qml` | Uses MoUI and routes supported wallpaper/theme actions to the same owner rather than replacing the scene plugin. |

## Baseline duplication and hardcoding (before implementation)

The source tree contains 85 shipped QML files. Across the first-party apps and
Plasma packages, the audit found 79 literal radii, 118 literal durations and
190 literal opacity values; only 11 files instantiate the current `Tokens.qml`.
Several literals are legitimate geometry (for example a circle radius derived
from its size), but identity values are mixed with those geometry values and no
gate currently distinguishes the two.

The largest independent design owners are:

- `org.moos.brand`: 2,606 lines of QML, with its own motion, sizes, state
  opacities and type choices.
- `org.moos.nova.clock`: 333 lines with a second shell token set.
- Theme Picker: 882 lines with a third focus/button/material implementation.
- `moos-theme`: 1,240 lines and `moos-apply-theme`: 1,728 lines; both write
  color scheme, Plasma style, icons, cursor, decoration, splash, lock,
  wallpaper, Konsole and GTK state.

## Baseline ownership conflicts and disposition

1. **Resolved — no single Theme State.** A generated sixteen-profile manifest is
   now the expectation source. Schema-2 state records the committed and previous
   profiles plus exact profile/custom wallpaper identity only after complete
   live readback; `undo/` retains the exact pre-change snapshot.
2. **Resolved — two cascade writers.** `moos-theme` owns the cascade and lock.
   `moos-apply-theme` now owns revision migration, cache/layout repair and a
   delegated call to that owner; it contains no independent theme mapping.
3. **Resolved — wallpaper had competing writers.** Theme Picker and Control
   Center now send an encoded local-image token to `moos-theme`. The transaction
   changes only the MoOS scene's image configuration, verifies every containment
   and rolls back exactly; no MoOS-owned route invokes the stock Wallpaper KCM.
4. **Resolved — Fast Remote bypassed both owners.** Fast Remote now holds the
   shared appearance lock, preserves `org.moos.ui2.wallpaper`, requests Still
   through `moos-theme`, snapshots exact KConfig present/missing values and marks
   the recovery transaction before its first mutation. OFF retains all snapshot
   files until KWin, motion, engine and layout restoration have each succeeded.
5. **Resolved — Design Core was application-local.** The installed
   `org.moos.ui` module is generated from one token source and is imported by
   apps, Plasma applets, login/lock, logout, splash and Theme Picker. The old
   app-local module was removed and its absence is gated.
6. **Resolved — Picker verification was partial.** The Picker waits for
   `moos-theme verify-lnf`, which reads back the full profile cascade, every
   desktop scene, lock, splash, Konsole, GTK/GSettings and the committed state;
   partial LNF/color-scheme success is no longer presented as completion.

## Legacy and non-owners

- SDDM is fully retired and must not be reintroduced.
- The metadata-less `system_files/usr/share/plasma/desktoptheme/Nova`, its two
  orphaned generators, two tracked `*.bak` generators and
  `artwork/master_icons/test.png` were confirmed consumer-free and removed.
  Source and image gates now require their absence; rollback belongs to Git,
  OSTree and `moos-theme undo`, not a second dormant visual system.
- `org.moos.heroclock` remains an optional installable widget and must not be
  auto-placed. The dashboard/deskclock names in migration code are compatibility
  cleanup targets only.
- Breeze remains a technical dependency for Plasma/GTK/login internals. Its
  package name is not itself a user-visible foreign identity and must not be
  removed merely to rename an engine.
- Technical identifiers containing `Nova` are load-bearing and are not legacy
  unless a complete gated migration explicitly replaces them.

## Completed implementation order derived from the audit

1. Promote tokens/primitives into a globally importable `org.moos.ui` module
   and migrate the current app-local consumers without changing their UX.
2. Generate one machine-readable profile manifest and make `moos-theme` the
   sole transactional cascade writer with complete readback and persisted state.
3. Reduce `moos-apply-theme` to migration/default repair plus delegation to the
   transaction owner; make Fast Remote snapshot/restore through the same lock.
4. Add a supported custom-wallpaper transaction that preserves the MoOS scene
   plugin, and expose it through Theme Picker/Control Center.
5. Migrate launcher, clock, picker and session masters to the Design Core; then
   do the visual redesign on those effective sources and regenerate all family
   outputs.
6. Remove proven dead runtime artifacts and add gates that fail if they return.
7. Validate in the live session and in booted images at the required palettes,
   directions and scales before release.
