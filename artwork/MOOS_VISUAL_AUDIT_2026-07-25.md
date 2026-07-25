# MoOS visual-system audit — 2026-07-25

Status: implementation and both local image builds are complete; signed CI
rollout and post-reboot proof remain release gates until their results are
recorded below.

This audit covers the repository and the running Plasma session. It does not
replace the identity gates, and it does not treat a generated file as proof of
what Plasma actually renders.

## Running-session baseline

- Plasma 6.7.3 / Qt 6.11.1 / Wayland.
- One 3840×2160 output at 225% fractional scale, with HDR/WCG enabled.
- Active half at the start of the audit: `org.moos.ui2.light`, with
  `MoOSUI2Light` colours, Plasma Style and icons, `MoOSUI2Light` Aurorae,
  `MoOSUI2Tide`, and the MoOS scene wallpaper.
- Effective KWin frost profile: BlurStrength 15, NoiseStrength 3.
- Zero failed system or user units and no KWin/plasmashell crash in the sampled
  journal.
- VS Code did not crash during the review: both earlier exits were clean
  `code=0` shutdowns caused by the synthetic Alt+F4 used to close test windows.
  That input method is retired; test windows are now stopped by their exact
  transient unit. There was no OOM event or coredump.
- Codex's visible “Reconnecting” state was a separate WebSocket stream closure.
  Five retries fell back to HTTP and the session continued without restarting
  VS Code. Plasma and the portals are not implicated.
- An older boot did contain a KWin assertion in `BlurEffect::blur`. The current
  boot completed the full Dark/Light review without repeating it; this is
  additional evidence for keeping every family member at the bounded 15/3
  frost profile instead of increasing blur for spectacle.
- A short idle sample showed the machine 87–93% idle, GPU near 20%, KWin using
  roughly 17–25% of one CPU core, and plasmashell roughly 15–17%. This is a
  noisy point sample, not a benchmark. It is why the new ambient wallpaper
  transition runs for 1.8 seconds only once per 90 seconds rather than driving
  a permanent full-screen animation.
- The booted deployment was a local containers-storage origin, not the signed
  registry deployment. It is useful visual evidence but cannot satisfy the
  release/update gate.

The full desktop capture is intentionally kept outside the repository because
it may contain personal session state. Public evidence must be captured from a
clean desktop or VM.

## Installed theme inventory

MoOS owns eight coordinated dark/light pairs (16 Global Themes):

| Pair | Dark | Light |
|---|---|---|
| Base | Graphite | Tidal |
| Nova | Nova | Nova Light |
| Amethyst | Amethyst | Amethyst Light |
| Aurora | Aurora | Aurora Light |
| Midnight | Midnight | Daylight |
| Gaming | Arena | Arena Light |
| Development | Forge | Forge Light |
| Study | Scholar | Scholar Light |

Each member has a Global Theme, colour scheme, Plasma Style, Aurorae package,
Konsole scheme/profile mapping, wallpaper and preview. The stable internal
package IDs retain `ui2` for compatibility; the user-visible family name is
simply **MoOS UI**.

Plasma/Breeze remains the toolkit and emergency fallback. MoOS does not patch
Breeze artwork in place. Stock Global Themes are hidden non-destructively from
the normal chooser, while the dedicated MoOS Themes app exposes the coherent
16-theme family. Third-party application icons retain their own identity.

## Gaps found in the repository

The pre-audit MoOS Plasma Style owned only a small visible subset of Plasma's
SVG vocabulary and silently inherited most controls from Breeze. Family
members also disagreed on KWin blur (15/3 for the base pair, 8/2 elsewhere),
Aurorae defaults named an obsolete plugin seam, first-party icons were not one
designed family, the Light wallpaper exporter could stretch non-16:9 outputs,
and existing-user migration revisions would not have refreshed the new assets.

The running Light desktop additionally exposed three integration details:

- the compact clock date did not follow the Arabic display locale in RTL;
- early/default cursor resolution could fall through to Adwaita;
- a bare QML runner made the Theme Picker appear as a generic Qt application in
  the task manager.

The warning audit did **not** justify local Plasma overrides: the QDateTime
warning comes from an old user `plasmanotifyrc` Do-Not-Disturb value; the
notification Grid warning is in Plasma 6.7.3's own history delegate; and the
KWallet portal warning follows the user's explicit KWallet disablement. No
direct `.onPressed()`/`.onClicked()`/`.onTapped()` call exists in MoOS QML, and
`qmllint-qt6` passed all 12 MoOS Plasma QML files checked. These warnings should
not be hidden by shipping a conflicting shell copy.

## Unified MoOS design system implemented

- **Plasma surfaces:** every one of the 16 Plasma Styles owns the high-visibility
  controls for backgrounds, translucent backgrounds, tooltips, buttons, arrows,
  checks, radio buttons, switches, sliders, scrollbars, tabs, toolbars, menu
  items, pagers, frames and busy state. Rounded blur masks, semantic focus,
  hover, pressed and inactive states are generated from the palette.
- **Window chrome:** every Aurorae package now has complete translucent,
  opaque, inactive and maximized frames plus ten functional button types and
  eight interaction states. The visual is an original MoOS squircle/glyph
  system, not macOS traffic lights. The live Plasma 6 seam is
  `org.kde.kwin.aurorae.v2`.
- **Dark and Light:** Graphite and Tidal share geometry, spacing and motion but
  use distinct owned artwork and accessible semantic colours. The other seven
  pairs reuse the same engine and receive their own palette-rendered assets.
- **Wallpaper:** the new project-bound Graphite Frost and Tidal Frost masters
  are crop-to-fill exported with Lanczos for 4K, ultrawide and 16:10; no output
  is stretched. A low-duty mineral-light wash gives the desktop subtle life
  while remaining idle about 98% of the time.
  They were created in brand-new bitmap-generation mode without a reference
  image. The prompt requested a matched dark/light pair of abstract MoOS
  Graphite/Tidal frosted mineral glass wallpapers, premium depth and restrained
  teal light, with no text or logo. The normalized project masters are
  `artwork/moos-ui2/wallpapers/moos-ui-graphite-frost-master-v3.png` and
  `artwork/moos-ui2/wallpapers/moos-ui-tidal-frost-master-v2.png`.
- **Icons and cursors:** eight visible first-party applications have new
  original SVG adaptive plates; Mo AI preserves the owner's commissioned
  byte-exact master. All nine have deterministic PNG exports from 16 through
  512 px. Both MoOS icon themes place this owned layer before their broad
  Colloid fallback. Cursor display names are MoOS-branded, and the generic early
  cursor inherits MoOS instead of Adwaita.
- **Qt, GTK and Flatpak:** Breeze remains the Qt/GTK widget engine, while MoOS
  owns the semantic palette. Theme switching now writes and reads back the exact
  colour, icon, cursor and font settings through GSettings as well as KDE
  configuration. The KDE portal keeps its Settings fallback and preserves the
  KWallet, Plasma notification and KDE file-chooser routes.
- **RTL and scaling:** the Theme Picker mirrors its complete layout, the compact
  clock uses an explicit Arabic display locale in RTL, wallpaper decoding uses
  the real device-pixel ratio, and generated raster/vector assets cover 4K and
  fractional scaling without fixed physical-pixel layout.
- **Existing users:** `THEME_REV=22` reapplies the complete system once;
  `MOOS_THEME_REV=10` invalidates only the relevant Plasma SVG/QML caches.

## Gates added or strengthened

- all 16 themes own the same safe 15/3 KWin frost profile;
- all 16 Plasma and Aurorae packages have valid XML, required surface assets,
  masks, frames, buttons and interaction states;
- family wallpapers crop rather than stretch;
- ambient wallpaper motion is guarded and cannot use a sub-minute timer;
- the compact clock's RTL locale is explicit;
- first-party icons are valid owned vectors, take theme precedence, and the
  Theme Picker has the correct desktop identity;
- the default cursor cannot silently resolve to a foreign theme;
- the image build converts and gates Qt WebEngine dictionaries instead of
  accepting the RPM scriptlet's silent failure; both local editions produced 50
  dictionaries including Arabic and English;
- generators load sibling helpers from their own directory, validate outputs
  fail-loud, and must be byte-identical when run twice.

## Release proof still required

- [x] all repository, identity, QML and shell gates pass together;
- [x] both generators pass the byte-for-byte idempotence check;
- [x] Dark and Light are applied to the running session, read back, captured and
      restored without leaving user-local package shadows;
- [x] full local `moos` and `moos-nvidia` images built from
      `7.1.4-204.fc44.x86_64`; both passed identity, experience, bootc,
      initramfs/OSTree and Plymouth gates, and NVIDIA proved its matching
      610.43.03 open driver and eight initramfs module entries. Final local
      image IDs are `23cac443e954` and `8eaece6d8ee4`; both override inherited
      Artifact Hub links with MoOS-owned documentation and artwork;
- [x] the branch is reviewed, merged and pushed — `moos-ui-unify` merged into
      `main` as `1e7991b`, and the follow-up build-resilience work as `5823f93`;
      `origin/main` carries both;
- [x] CI publishes and signs the resulting image — run `30152979451` on
      `5823f93` finished green in 17m37s, publishing and cosign-signing
      `moos:latest` and `moos-nvidia:latest`;
- [x] the machine stages that signed origin, reboots, and the live post-update
      checks remain green — staged
      `ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia:latest`,
      digest `sha256:12b44aba…` (byte-identical to what the registry publishes),
      version `44.20260725.347`; rebooted; `tests/post-update-check.sh` returned
      **48 passed, 0 failed** on the live desktop, including the deployment line
      that had been red on every previous boot. Kernel `7.1.4-204` with the
      matching NVIDIA `610.43.03`, `BlurStrength=15`, layered `code` preserved,
      no failed system or user units. `moos-selfcheck`: 46 passed.

Every item above now has real output. This is an MoOS release.

## Follow-up pass — 2026-07-25 (session J)

Two defects the audit's own evidence pointed at, fixed at the source rather than
described:

- **The scene ignored "animations off".** `motionEnabled` in the wallpaper's
  `main.qml` consulted only the plugin's `AmbientMotion` key, so a user who
  disables animations in System Settings (or lands there through an
  accessibility profile) still got a permanently breathing 4K desktop. The bento
  already honoured Plasma's zero-duration signal; the scene layer now honours it
  too, and `test_moos_ui2.py` fails if that guard is ever dropped again.
- **The second unpriced updater.** `flatpak-system-update` was moved to idle CPU
  and I/O in an earlier session precisely because a background updater must not
  be something the user can feel — but `uupd` was left at normal priority, and on
  this machine it is now the most expensive unit of the boot (1min 16.195s, top
  of `systemd-analyze blame`). Its `OnCalendar=04:00 Persistent=true` timer fires
  inside the first fifteen minutes of any desktop that was off at 4 AM. It now
  ships the same `moos-idle.conf` treatment, gated by `verify_user_experience.py`.
  Scope is stated honestly in the drop-in: the ostree fetch itself runs in
  rpm-ostreed's own cgroup and is deliberately left fast, because the same daemon
  serves the user's own interactive updates.
