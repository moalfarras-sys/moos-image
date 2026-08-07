# Unified MoOS Design Audit

Updated: 2026-08-07

This is the repository-grounded ownership map for the unified design work. It
does not treat generated files, old plans, or a green source gate as proof that
a surface is used by the running session.

## Effective Owners

| Surface | Effective source | Notes |
|---|---|---|
| First-party QML tokens | `system_files/usr/share/moos/apps/ui/Tokens.qml` | Shared rhythm, type, shape, motion and surface rails. |
| Plasma palette family | `artwork/moos-ui2/palette.json` and `artwork/moos-themes/palettes.json` | Generators produce the Plasma, GTK, Konsole, wallpaper and Aurorae outputs. |
| First-party GTK palette | `system_files/usr/lib/moos/moos_ui2.py` | Runtime fallback; its light muted role now matches the canonical palette. |
| Theme selection | `~/.config/kdeglobals` `[KDE] LookAndFeelPackage` | `moos-theme` is the cascade writer; `moos-theme-sync` reconciles external KDE changes. |
| Desktop scene | `org.moos.ui2.wallpaper` plus `moos-theme` | Plasma scene state is separate from the LNF package and must be read back. |
| Panel and dock | `moos-bar.conf` + `moos-bar-apply` | Existing users are migrated through the live Plasma scripting API. |
| Launcher | `org.moos.brand` | Kickoff is a migration source only, not the active launcher. |
| Login | `plasmalogin` and `org.moos.ui2.greeter` | SDDM is not installed or shipped. |
| Lock/logout/power | Plasma lock shell and MoOS look-and-feel logout QML | Native authentication and power signals remain load-bearing. |

## Confirmed Conflicts

- `moos-theme` and `moos-apply-theme` both own large portions of the theme
  cascade. They are serialized by a lock in the main switcher, but the state is
  still distributed across KDE, GTK, Konsole, lock and live Plasma files.
- LNF defaults contain a wallpaper image while the MoOS scene plugin is the
  intended desktop wallpaper owner. The current reconcile is repair-after-write,
  not a single writer contract.
- `moos-fast-remote` writes wallpaper/KWin state outside the main theme lock.
- Panel policy is mirrored in `moos-bar.conf`, the layout template and the
  migration script. The layout template remains a required new-profile seed.
- Stock Plasma still owns notifications, Alt-Tab and Overview. MoOS supplies
  themed surfaces and activation, not replacement implementations.

## Legacy And Non-Owners

- SDDM files are absent and must not be reintroduced.
- Kickoff is used only to migrate favorites into `org.moos.brand`.
- `org.moos.heroclock` is shipped as an optional widget but is not auto-placed;
  the retired dashboard/deskclock applets are cleanup compatibility only.
- Breeze remains a technical Plasma dependency for login/lock components. It is
  not a user-visible MoOS identity leak by itself and must not be removed.
- MoPlayer keeps a separately documented Flutter palette because its video
  surface has different contrast and layout constraints.

## Changes In This Slice

- Extended the shared QML token contract with Liquid Glass state opacities,
  panel/dialog dimensions, icon sizes, disabled state and the blur ceiling.
- Added reusable `MoSurface`, `MoGlass`, `MoCard`, `MoIconButton` and
  `MoSeparator` primitives without changing existing screen UX.
- Made shared `Button` consume the centralized state and disabled tokens.
- Fixed greeter light/dark palette selection for every Light, Tide and Daylight
  wallpaper package, not only Tide.
- Fixed the GTK light `muted` fallback drift against `artwork/moos-ui2/palette.json`.
- Fixed stale panel readback after replacing the Plasma digital clock and made
  `moos-bar-apply check` reject duplicate launcher, tray or clock applets.

## Deferred Work

- A single transactional theme manifest and complete readback across GTK,
  Konsole, lock, splash and scene remain the next engine-level slice.
- Existing application files still contain local geometry helpers; migrate them
  incrementally to the new primitives rather than mass-rewriting QML.
- Notification, Alt-Tab and Overview remain stock Plasma surfaces with MoOS
  theme integration; replacing them requires live performance and accessibility
  review.
- Visual screenshot QA at 100/125/150/200% scaling and live login/lock/power
  walkthrough are not claimed by this source-only change.
