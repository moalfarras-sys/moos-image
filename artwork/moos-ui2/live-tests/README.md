# Tidal Horizon — development evidence

These JPEGs preserve the development-session captures from `/var/tmp` at quality
90, bounded to 1920×1080 without changing aspect ratio.

| Surface | Before | After |
|---|---|---|
| Desktop | [Before](tidal-horizon-before-2026-07-30.jpg) | [After — live session](tidal-horizon-desktop-after-live-session.jpg) |
| Launcher / Command Canvas | [Before](tidal-horizon-launcher-before.jpg) | [After — live session](tidal-horizon-launcher-after-live-session.jpg) · [isolated source preview](tidal-horizon-launcher-after-source-preview.jpg) |
| Session portal / Logout | [Before](tidal-horizon-portal-logout-before.jpg) | [After — source preview](tidal-horizon-portal-logout-after-source-preview.jpg) |
| Control Center / Overview | [Before](tidal-horizon-control-center-before.jpg) | [After — source preview](tidal-horizon-control-center-overview-after-source-preview.jpg) |
| Store | [Before](tidal-horizon-store-before.jpg) | [After — source preview](tidal-horizon-store-after-source-preview.jpg) |
| Mo AI | [Before](tidal-horizon-moai-before.jpg) | [After — source preview](tidal-horizon-moai-after-source-preview.jpg) |
| Recovery | No dedicated before capture exists | [After — source preview](tidal-horizon-recovery-after-source-preview.jpg) |

The files labelled **live session** were captured from the running Plasma
session after applying the generated wallpaper and temporarily installing the
working-tree Launcher package. The files labelled **source preview** are
screenshots rendered from the working-tree QML.

Neither label is proof that a signed image was published and booted. Final
deployment proof requires the signed update, reboot, live capture, and
post-update checks.

# Icon bridge round — 2026-07-30 (THEME_REV=26 working tree)

The `44.20260730.478` captures above record the **shipped** Tidal Horizon
deployment after its update reboot. The rows below are working-tree evidence
for the follow-up round: per-palette symbolic icon overlays
(`MoOSUI2<Family>` icon themes), the calmer four-column Command Canvas and the
semantic Button states.

| Proof | Capture |
|---|---|
| Defect — `FollowsColorScheme=true` let QIcon recolour with the app QPalette: near-invisible symbols on the dark session | [before](tidal-cut-arena-followscolorscheme-before.png) |
| Fix — baked per-palette inks through the real KIconLoader on the live dark Arena session (69/69 symbols legible) | [after](tidal-cut-arena-baked-inks-after.png) |
| Same geometry, light overlay: graphite ink + deep-magenta accent via `MoOSUI2ArenaLight` | [light](tidal-cut-arena-light-baked-inks.png) |
| Four-column Command Canvas live on the 4K Arabic RTL session (home override + plasmashell restart) | [launcher](launcher-four-column-live-4k.jpg) |
| Native control states (button/lineedit/list/menu/view) through the real KSvg/FrameSvg + PC3 path on the active theme, incl. RTL | [controls](native-controls-arena-kframe.png) |

All four are **working-tree previews** (home override, not a signed image);
the KIconLoader captures went through the real icon resolver of the running
session. Deployment proof still requires the signed update, reboot and
`tests/post-update-check.sh`.

# Shipped deployment proof — signed `moos-nvidia` 44.20260730.478

Captured by the previous session on the real machine after the update reboot
onto the signed image (before the icon-bridge round above was written):

| Surface | Capture |
|---|---|
| Desktop on the booted signed image | [desktop](post-update-desktop-44.20260730.478.jpg) |
| Command Canvas on the booted signed image | [launcher](post-update-launcher-44.20260730.478.jpg) · [clean](post-update-launcher-clean-44.20260730.478.jpg) |
