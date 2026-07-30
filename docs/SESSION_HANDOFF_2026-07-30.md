# Session handoff — Tidal Horizon Product Design (2026-07-30)

**Purpose:** this records the implementation that follows the accepted
commercial Visual & UX audit. It does not start, repeat or reinterpret that
audit. Claims below distinguish source-preview evidence from signed,
boot-proven evidence.

| Fact | Value at this handoff |
|---|---|
| Working branch | `product/tidal-horizon-2026-07-30` |
| Baseline commit | `c1d425e8ec9922a5ed53242424729d7afbe10674` |
| Release migration | **THEME_REV=25** |
| Booted baseline | signed `moos-nvidia` **44.20260730.477** |
| Booted digest | `sha256:87ed100fd2289985faf510e9a262c87e76c3eff520b9b2365c830126aab8af76` |
| Baseline post-update proof | **48 passed / 0 failed**, no failed system or user units |
| Tidal Horizon release state | generated, live-session proven and locally image-built; **not yet published, staged or booted** |
| Local generic image | `13ce8105e9fd…`; manifest `sha256:28e93f5b8546…`; OSTree `a568b31c85c4…` |
| Design-system name | **MoOS UI — Liquid Glass Design System** |
| Product signature | **Tidal Horizon / Tidal Cut** |
| Protected brand assets | MoOS and Mo AI logo geometry unchanged |

The `.477` result proves the accepted commercial baseline from which this work
started. It does **not** prove the Tidal Horizon working tree. That proof requires
the exact source to pass the gates and image build, be committed/pushed, published
and signed by CI, staged by digest, booted, and checked again.

---

## 1. Outcome

MoOS now has one recognisable spatial signature instead of a set of individually
polished surfaces. Two low mineral-glass membranes rise toward a precise central
concave cut. The upper field stays calm enough for work, content and typography.
The same silhouette seats the brand at the four session doorways, defines the
wallpaper, shapes the Launcher, and anchors Store, Mo AI and Control Center.

This pass deliberately avoids another icon churn. The accepted original
69-symbol **Tidal Cut** SVG family remains the symbolic language, with semantic
theme roles and light/dark adaptation. The MoOS and Mo AI marks keep their exact
geometry. Only seating, surrounding material and dynamic colour integration
change.

MoPlayer also remains on its already accepted state: canonical `23799ad`, native
MoOS chrome, clean analysis and 176/176 tests. Reworking it again would have
discarded proven work without improving the cross-system identity.

---

## 2. The visual contract

### 2.1 Horizon geometry

The normal geometry is shared by full and hero surfaces:

| Measure | Value |
|---|---|
| Left/right anchors | `0.11W` / `0.89W` |
| Horizon | `0.82H` |
| Crest | `0.12H` |
| Shoulder | `0.22W` |
| Half-cut | `max(11px, 0.013W)` |
| Precision rim | `max(1.25px, 0.0024H)` |
| Optical under-stroke | `max(8px, 0.018H)`, 48% intensity |

Compact surfaces use `0.04/0.96W`, `0.78H`, `0.19H` and `0.18W`.
This geometry is physical, so it does not mirror in RTL. Labels, rails and
controls still use logical start/end.

The canonical portal component SHA256 is:

```text
11a0ddbd40ae617a2ff7ac25204ceb9cf63fd42795fa373d531b5fb6caa82705
```

`artwork/generate_login_scene.py` synchronises those exact component bytes
through the 16 theme-family doorway packages, the lock shell and the login
wallpaper.

### 2.2 Material hierarchy

- Persistent surfaces remain solid so text and window captions have stable
  contrast.
- Liquid Glass is reserved for transient shell surfaces, thresholds and hero
  seating.
- A surface gets one broad shadow, one fine rim and one optical under-stroke;
  glass is not stacked on glass.
- The palette changes material and lighting, not geometry. Tidal Light uses
  alabaster/mineral turquoise; Graphite Dark uses smoked graphite and a
  controlled teal edge.
- There are no pure-white slabs, pure-black voids, fake traffic lights,
  neon cyberpunk effects or decorative blur whose only purpose is to look busy.

### 2.3 Spacing, radii and targets

The shared radius scale is `8/12/16/24px`. The Command Canvas uses a `24px`
outer rhythm and a `68px` command bar. Its interactive targets are at least
`40px`; Control Center uses at least `48px`. Calm negative space is a component
of the language, not leftover room.

### 2.4 Typography and direction

Arabic-capable session text uses IBM Plex Sans Arabic. Always-Latin clock digits
and the MoOS wordmark retain their documented faces. Portal copy follows the
active locale only; the clock remains LTR inside RTL and the date is shown once.
Selection text and its flat selection role are paired, so authentication and
session choices retain contrast in every palette.

### 2.5 Motion

Motion expresses hierarchy and state; it is not ambient decoration:

| Context | Duration / rule |
|---|---|
| Interaction feedback | `120ms` |
| Command Canvas entrance / structural transition | `240ms` |
| Application Horizon reveal | `320ms` |
| Splash | reveal `460ms`, progress `260ms` |
| Logout | background `480ms`, sheet `420ms` |
| Login wallpaper | static |
| Lock | finite state transitions + minute-event pulse only |

Every duration collapses to zero when
`Kirigami.Units.longDuration <= 1`. The shared components use no Timer,
ShaderEffect, input handler or infinite loop. Hero Clock updates once per minute
and no longer animates seconds.

---

## 3. Surface implementation

### Wallpaper and theme family

The two accepted lossless masters are both 1672×941:

| Master | SHA256 |
|---|---|
| `artwork/moos-ui2/wallpapers/moos-ui-tidal-horizon-master-v1.png` | `b09a5a71e68dba187b58b2f4c6f96743c0c6af67d38521dbcc81361db1682a28` |
| `artwork/moos-ui2/wallpapers/moos-ui-graphite-horizon-master-v1.png` | `4402f755df0cef84caa4d8740fc524d84b9cb4d71083162e6edc731de7829f00` |

The light master was generated as an original bitmap; the dark sibling was an
edit that preserved the accepted composition exactly and changed only material
and light. `artwork/generate_moos_ui2.py` produces crop-safe runtime packages,
and `artwork/generate_moos_themes.py` maps the same luminance/edge geometry
across the 16 semantic palettes. The family proof sheet is
`artwork/moos-ui2/previews/tidal-horizon-family-v1.jpg`.

### Launcher / Command Canvas

The old menu composition is replaced by an `828×630` logical-pixel Command
Canvas (`46×35` grid units). It presents Mo AI, Store and Settings exactly once,
then quieter contextual actions and a separate Session Edge. The Tidal Cut
silhouette is recognisable before reading a label. It preserves Plasma search,
keyboard navigation and RTL mirroring while removing the duplicate footer
destinations that made the launcher read like a themed menu.

### Desktop, Dock and Hero Clock

The desktop takes the same wallpaper silhouette as the doorways. The Dock keeps
the proven Plasma panel engine and receives the Command Canvas identity instead
of introducing a second shell. Hero Clock retains its useful information but
updates by minute, uses Latin digits inside RTL chrome, and has no seconds loop
or infinite animation.

### Splash, Login, Lock and Logout

All four doorways share one pure `QtQuick.Shapes` horizon component: cubic crest,
precise aperture, rim, under-stroke and ground line. Host/theme semantic colours
remain dynamic. Authentication, unlock, session selection, logout countdown and
action wiring are unchanged; this is a visual/product integration, not a
security-route rewrite.

### Store

The generic hero circle is gone. The shared horizon sits low enough not to cross
copy, and semantic theme colours carry it in light and dark modes. The page
keeps the store's real catalogue, transaction and keyboard paths.

### Mo AI

Four unrelated glow/aurora layers were replaced by the shared horizon. The
commissioned Mo AI orb itself is untouched and is seated at the crest. The
secondary doodle is deliberately quiet, so the chat and actions remain the
visual priority.

### Control Center / Settings / Recovery

The new native MoOS Control Center replaces a generic settings destination with
one bilingual/RTL product shell for Overview, Appearance, Connectivity,
Hardware, Privacy, Updates and Recovery. Its Overview uses a device orbit seated
on the horizon; Recovery uses the same chrome instead of looking like a separate
utility.

The implementation uses a read-only status helper and **34 explicit safe routes**.
There is no wildcard route. Storage is read from `/var`, the real bootc/OSTree
filesystem, not composefs `/`. The control-center icon is generated as part of
the owned MoOS application family; the MoOS logo is not redrawn.

---

## 4. Before / after evidence

The durable index is
[`artwork/moos-ui2/live-tests/README.md`](../artwork/moos-ui2/live-tests/README.md).
All files below were captured on the real 3840×2160 / 225% session and bounded
to 1920×1080 without changing aspect ratio. Desktop and Launcher are
**live-session** captures from the running Plasma shell; the other After files
are working-tree source previews. They prove that the generated assets/QML
rendered; they do not prove a signed deployment.

| Surface | Before | After |
|---|---|---|
| Desktop | [`tidal-horizon-before-2026-07-30.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-before-2026-07-30.jpg) | [`tidal-horizon-desktop-after-live-session.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-desktop-after-live-session.jpg) |
| Launcher / Command Canvas | [`tidal-horizon-launcher-before.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-launcher-before.jpg) | [`tidal-horizon-launcher-after-live-session.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-launcher-after-live-session.jpg) (live) · [`isolated source preview`](../artwork/moos-ui2/live-tests/tidal-horizon-launcher-after-source-preview.jpg) |
| Session portal / Logout | [`tidal-horizon-portal-logout-before.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-portal-logout-before.jpg) | [`tidal-horizon-portal-logout-after-source-preview.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-portal-logout-after-source-preview.jpg) |
| Control Center | [`tidal-horizon-control-center-before.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-control-center-before.jpg) | [`tidal-horizon-control-center-overview-after-source-preview.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-control-center-overview-after-source-preview.jpg) |
| Store | [`tidal-horizon-store-before.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-store-before.jpg) | [`tidal-horizon-store-after-source-preview.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-store-after-source-preview.jpg) |
| Mo AI | [`tidal-horizon-moai-before.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-moai-before.jpg) | [`tidal-horizon-moai-after-source-preview.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-moai-after-source-preview.jpg) |
| Recovery | no dedicated Before capture | [`tidal-horizon-recovery-after-source-preview.jpg`](../artwork/moos-ui2/live-tests/tidal-horizon-recovery-after-source-preview.jpg) |

Additional final portal captures retained during development:

- `/var/tmp/moos-portal-after-login-wallpaper-qml-final.png`
- `/var/tmp/moos-portal-after-login-components-final.png`
- `/var/tmp/moos-portal-after-lock-final.png`
- `/var/tmp/moos-portal-after-lock-auth-final-v2.png`

These `/var/tmp` paths are development evidence only and are not durable release
artifacts.

---

## 5. Performance evidence

All values are measured source-preview samples, not estimates:

| Surface | Measurement |
|---|---|
| Command Canvas idle | **0 process ticks / 0.000% CPU over 20s** |
| Hero Clock idle | **0 process ticks / 0.000% CPU over 20s** |
| Store idle | **0 process ticks / 0.000% CPU over 20s** |
| Control Center after minutes | **55.8 MiB current / 58.8 MiB peak**, **0.427s accumulated CPU** |

The portal component has zero infinite loops. Splash and Logout run only their
bounded entrance/state transitions; Login is static; Lock's only repeating
change is the real minute event. A quiet `plasmashell` measurement must still be
repeated after booting the signed image because source-preview process samples
cannot measure the final compositor/session cost.

---

## 6. Verification completed so far

The following results were actually run during this implementation:

- `tests/test_tidal_portals.py`: **6/6 passed**.
- `tests/test_moos_ui2.py`: **22/22 passed** after the portal synchronisation.
- `tests/verify_user_experience.py`: passed for the portal handoff.
- `qmllint` for the portal surfaces: exit 0; remaining messages were
  host-context warnings, not load failures.
- Launcher/Hero Clock focused checks: **25/25 passed**; QML lint exit 0 with
  only the two already-known font warnings.
- Store/Mo AI visual-polish and motion gates passed after adopting the shared
  application component.
- Baseline installed image: `bash tests/post-update-check.sh` returned
  **48 passed / 0 failed** on signed `.477`.
- Final `just check`, now including `test_tidal_horizon.py` and
  `test_tidal_portals.py`, passed.
- Final `just build` completed and produced local generic image
  `13ce8105e9fd5256f2629bf39863677ae08b515f92372217115f77b794a6c199`,
  manifest digest
  `sha256:28e93f5b8546256374a5f4cab44efd845ad2eb7c6d9538eba731ba819ef33e0f`,
  OSTree commit
  `a568b31c85c4eb6b77bb5c3e3315052cee08c3405281673b9a05ae70f8316339`.
  A readback from inside that image proved `NAME/ID/PRETTY_NAME=MoOS`,
  `THEME_REV=25`, the Control Center helpers, Tidal wallpaper, and identical
  `11a0ddbd…` portal components.

These source and local-image gates are complete. They still do not replace CI
signing or the post-reboot proof below.

---

## 7. Image-generation provenance

The generated masters are original MoOS assets. No third-party OS wallpaper or
icon was copied.

**Light master — `mode=generate`:**

> Create an original premium operating-system wallpaper called Tidal Horizon:
> two low sculpted translucent sea-glass membranes approach a precise central
> concave cut, airy alabaster and mineral turquoise daylight, restrained
> teal/plum edge light, tactile micro-texture, broad calm upper negative space,
> cinematic but minimal. Exact 16:9 edge-to-edge composition; no text, logo,
> objects, UI, watermark, copied interface, pure white, neon or cheap gradient.

Generated source:

```text
/var/home/moos/.codex/generated_images/019fb034-0e28-7e42-b0a7-23719f3167e5/call_nzDdl5Usbr7GOpyGz1pM97t5.png
```

**Dark sibling — `mode=edit`, accepted light master as reference:**

> Preserve the exact composition, membrane silhouette and central concave cut.
> Convert only its material and lighting into smoked graphite sea glass with a
> controlled luminous teal edge and deep mineral atmosphere. Keep the same
> camera, crop, negative space and micro-texture; add no objects, text, logo,
> UI, watermark, neon or new geometry.

Generated source:

```text
/var/home/moos/.codex/generated_images/019fb034-0e28-7e42-b0a7-23719f3167e5/call_wNh9naeuyIu0gHeeF8FVQkgV.png
```

Runtime and family output must come from the two committed masters, not from
these environment-owned paths.

---

## 8. Release gates still open

Do not call Tidal Horizon shipped until every item is closed in this order:

1. [x] Regenerate UI2 and all family outputs from the final masters and portal
   component.
2. [x] Verify the migration is exactly **THEME_REV=25**.
3. [x] Run the focused Horizon, portal, shell, settings, icon-runtime, motion,
   accessibility and route-contract tests from the final source.
4. [x] Run the complete CI-equivalent repository gates, including
   `bash -n build_files/build.sh`,
   `python3 tests/verify_user_experience.py` and
   `python3 tests/test_device_plan.py`.
5. [x] Run the full local generic image build (`just build`) and record its
   exact image ID/digest.
6. [ ] Commit only the intentional tree, push it, and wait for the complete CI
   matrix—including `moos-nvidia`—to publish and cosign the image.
7. [ ] Run `moai-do update`; verify the staged version/digest equals the CI
   publication and the origin remains `ostree-image-signed`.
8. [ ] Reboot. Then run `bash tests/post-update-check.sh`, inspect failed units,
   capture the final Launcher/Portal/Control Center/Store/Mo AI from the booted
   image, and take a quiet-session 60s `plasmashell` sample.

The previous `.477` deployment must remain available for rollback throughout.

---

## 9. Explicitly not changed or not yet proven

- No kernel, driver, initramfs, bootc origin, signature policy or update-service
  architecture change belongs to this Product Design pass.
- MoOS and Mo AI logo geometry was not redesigned.
- The accepted Tidal Cut symbolic family was not replaced or bulk-edited.
- MoPlayer's canonical application source was not edited in this pass.
- Source previews do not prove Login/Lock/Logout after a signed reboot.
- Real-hardware installation remains unverified beyond the existing documented
  VM install path.
- Rollback is still not tested against a deliberately broken update.
- Audio/Bluetooth/Wi-Fi/suspend/multi-monitor coverage beyond the maintainer's
  desktop remains as documented in `AGENTS.md`.
