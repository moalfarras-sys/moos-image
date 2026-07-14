# MoOS UI2 — Graphite / Tidal Glass visual contract

Status: **implemented and live-proven; default in the working tree, awaiting signed image rollout**
Owner: visual-system workstream
Started: 2026-07-14
Baseline image: signed MoOS `44.20260713.112`

This is the hand-off point for every agent touching MoOS UI2. Read it with
`AGENTS.md`, `PROJECT_STATE.md`, and `artwork/MOOS_UI_DESIGN.md`. UI2 is a new,
isolated visual family. It must not overwrite or rename Nova or MoOS UI (UI1),
which remain installed fallbacks.

## Why UI2 exists

The first real-hardware review of MoOS UI revision 15 found that it loaded and
worked, but did not meet the visual target. The desktop widget was a large,
muted square, its weather glyph read as flat 2D artwork, the aubergine wallpaper
made the whole desktop feel like one dark block, and first-party QML apps still
carried hard-coded Nova colours instead of the running desktop palette.

The proof was captured from the running Plasma containment, not inferred from
repository files:

- `/var/home/mo/Pictures/MoOS-UI2-audit/baseline-containment-ui1-v2.png`
- active deployment `44.20260713.112`, signed origin, digest
  `sha256:26ea315ef8eb69731bb8f9d906d6a4a5bf69079c73eb018b68df45c76c664891`
- active selectors: `org.moos.ui`, `MoOSUIDark`, `MoOSUI`
- active desktop widget: `org.moos.nova.deskclock`, geometry
  `x=48 y=32 w=496 h=400` on the 1397×786 logical desktop

GTK intentionally names the `Breeze` stylesheet: Plasma's gtkconfig-generated
palette feeds that stylesheet. UI2 must verify the *runtime colours*, not reject
the stylesheet name.

## Identity and isolation

| Surface | Dark | Light |
|---|---|---|
| Global Theme | `org.moos.ui2` | `org.moos.ui2.light` |
| Plasma Style | `MoOSUI2` | `MoOSUI2Light` |
| KDE colour scheme | `MoOSUI2Dark` | `MoOSUI2Light` |
| Aurorae decoration | `MoOSUI2` | `MoOSUI2Light` |
| Konsole profile | `MoOSUI2.profile` | `MoOSUI2Light.profile` |
| Wallpaper | `MoOSUI2Graphite` | `MoOSUI2Tide` |
| Desktop widget | `org.moos.ui2.dashboard` | same adaptive package |

UI1 selectors and `org.moos.nova.deskclock` stay byte-for-byte available. UI2
theme switching may replace the visible desktop widget with the UI2 dashboard,
but switching back must restore the UI1 widget without leaving duplicates.

Revision 16's completion marker distinguishes migration from rollback. Before
the marker exists, an inherited UI1 Light/Dark desktop migrates to the matching
UI2 half. After it exists, UI1 can only be an explicit rollback choice, so a
later self-heal repairs that same UI1 half and its per-containment dashboard; it
must never use drift as a reason to pull the user silently back into UI2.

Plasma's built-in automatic Look-and-Feel switch does not reliably carry the
wallpaper and does not own Konsole or GTK's light/dark preference. The globally
enabled `moos-theme-sync.path` watches the effective `~/.config/kdeglobals` only
during `plasma-workspace.target` and runs `moos-theme sync-auto` after a stable
UI2 selector is observed twice. The sync writes only those non-LNF supplements,
checks every desktop wallpaper plus lock screen, Konsole and GTK, and never
writes `kdeglobals`; therefore it cannot trigger its own path unit. UI1 and
foreign themes are ignored. A shared runtime lock serialises it with manual and
first-login theme transitions.

## Palette

No runtime surface uses pure black or pure white.

| Token | Graphite Dark | Tidal Light | Purpose |
|---|---|---|---|
| canvas | `#14191C` | `#D8EBE7` | desktop/app foundation |
| surface | `#1D2529` | `#C9E2DD` | windows, menus and dock |
| card | `#232D32` | `#E1F0EC` | primary bento cards |
| raised | `#2C383E` | `#B8D8D2` | controls and selected rows |
| primary | `#4ED7C8` | `#006D67` | focus, progress and active state |
| secondary | `#78AFFF` | `#1D6278` | links and secondary motion |
| luminous | `#A8F1E8` | `#0B6965` | restrained highlights |
| positive | `#69D9A5` | `#086B4B` | healthy state |
| warning | `#F4C56A` | `#7B520F` | caution |
| negative | `#FF7D88` | `#A52F3F` | destructive/error |
| text | `#E8F1EF` | `#17302E` | primary text |
| muted text | `#9CAFAC` | `#466360` | secondary text |
| outline | `#415158` | `#527F79` | separators and card edges |

Contrast is checked against the opaque colour tokens; translucent glass is not
used as an excuse for low-contrast text.

## Visual language

UI2 is **Tidal Glass**: quiet graphite mechanics in Dark and mineral turquoise
mist in Light. It uses offset bento cards, soft inner highlights, deep but broad
shadows, one luminous edge, and large calm negative space. Avoid white slabs,
neon cyberpunk, purple/orchid from UI1, excessive blur, fake macOS traffic-light
buttons, and animation on every object.

The dock keeps one proven Plasma panel. Dark and Light use identical FrameSvg
geometry: a low floating capsule, translucent tinted fill, one-pixel inner edge,
and a soft turquoise active shelf. They own separate, fully generated SVG suites;
Light must never inherit a fixed-colour Dark SVG. Adaptive transparency stays
disabled in both variants so a maximised window cannot turn only the Light dock
opaque.

KDE, Qt, GTK, Konsole, Plasma popups, window decorations and first-party cards
must draw from the active colour scheme. Mo AI and Welcome must stop treating
hard-coded Nova navy/cyan as their canvas and instead derive semantic tokens from
their QML `palette`; brand art can retain its own identity colours.

## Wallpaper contract

Each variant owns a distinct 16:9 source and exports 3840×2160, 3440×1440 and
2560×1600. The upper-left region stays quiet enough for the dashboard. There is
no text, logo, UI mock-up, fake window, pure white, pure black, purple or visible
banding.

Dark prompt:

> Use case: stylized-concept. Asset type: 4K operating-system wallpaper. Abstract
> graphite architectural landscape made from broad frosted mineral-glass ribbons
> and a distant turquoise tidal glow, charcoal grey foundation, restrained cool
> blue depth, premium soft volumetric light, large quiet negative space in the
> upper-left for a desktop widget, subtle fine grain, elegant and calm. 16:9,
> edge-to-edge, no text, no logo, no objects, no UI, no purple, no pure black, no
> neon cyberpunk, no watermark.

Light prompt:

> Use case: stylized-concept. Asset type: 4K operating-system wallpaper. Abstract
> tidal-mist landscape in mineral turquoise, sea-glass and pale graphite, layered
> translucent sculpted waves with soft daylight and restrained blue-green depth,
> premium frosted material, large quiet negative space in the upper-left for a
> desktop widget, subtle fine grain, airy but never white. 16:9, edge-to-edge, no
> text, no logo, no objects, no UI, no purple, no pure white, no neon, no
> watermark.

The built-in image generator is used for the raster masters. Generated output is
inspected, cropped to 16:9 without stretching, then exported deterministically by
`artwork/generate_moos_ui2.py`. Runtime packages never reference a file left only
under `$CODEX_HOME`.

The lossless image-generator PNG masters remain at their native 1672×941
resolution under `artwork/moos-ui2/wallpapers/`; Lanczos scale-and-crop creates
the 4K and ultrawide runtime exports. The six installed resolutions are
deterministic high-quality 4:4:4 JPEG files.
This reduces the two installed wallpaper packages from roughly 97 MB to 11 MB;
normalised pixel error against the lossless exports is below 0.6%. Both 4K JPEGs
were applied and read back through the installed Plasma session before the
original UI1 wallpaper was restored.

## Desktop dashboard contract

`org.moos.ui2.dashboard` is a new plasmoid, not an in-place rewrite of UI1. It is
one passive desktop widget containing three internal bento cards:

1. **Time card** — rolling HH:mm digits, Arabic and locale date, quiet minute pulse.
2. **Weather card** — generated 3D weather art, temperature/condition/high/low,
   slow float and condition-specific rain/snow/fog/storm motion in QML.
3. **System card** — compact CPU/RAM/GPU bars and a breathing health beacon using
   the verified sensor IDs.

Target geometry is a wide 31×12 grid-unit composition, materially shorter than
UI1's 27×14 square-like dashboard. It contains no `MouseArea`, does not intercept
desktop gestures, keeps the keyless ipwho.is + Open-Meteo path, does not poll more
often than UI1, and hides failed weather data cleanly.

Weather art covers sun, moon, partly cloudy day/night, cloud, rain, snow, fog and
storm. The shipping assets are local, licence-owned MoOS artwork. Only one weather
PNG is decoded at a time. Motion comes from QML transforms/particles/shapes; no
network-loaded animation and no Lottie runtime dependency enter plasmashell.

Weather-art provenance (2026-07-14): the built-in image generator produced two
lossless source atlases: the RGBA `weather-atlas-alpha.png` and the RGB
`weather-atlas-chroma.png`, both retained under `artwork/moos-ui2/weather/`.
The nine named 512×512 RGBA masters were isolated from those atlases, visually
inspected on both UI2 wallpapers, and remain beside them; no LottieFiles or
third-party weather pack was used.
The project-bound generation prompt was:

> Use case: stylized-concept. Asset type: transparent 3D weather-icon atlas for
> a premium operating-system desktop widget. Create a coherent family containing
> clear day, clear night, partly cloudy day, partly cloudy night, overcast cloud,
> rain, snow, fog and thunderstorm. Sculpted frosted sea-glass forms, soft pearl
> clouds, mineral turquoise and restrained cool-blue highlights, rounded modern
> silhouettes, subtle depth and broad soft shadows, readable at 96 px, consistent
> three-quarter lighting and scale. Arrange isolated icons on a clean grid with
> generous separation and transparent background; no text, labels, UI, border,
> watermark, purple, neon cyberpunk, pure black or pure white background.

`artwork/generate_moos_ui2.py` copies the nine owned masters into the dashboard,
so the runtime weather set is reproducible rather than a hand-maintained duplicate;
the dashboard QML itself remains normal source code and is not generator output.
The generator preflights every raster input and `ffmpeg`, moves existing outputs
to a same-filesystem temporary backup, and restores them byte-for-byte on any
generation or validation failure. A failed regeneration therefore cannot leave
the repository with a half-deleted UI2 family.

## Motion system

- card entrance: one 420ms stagger after creation;
- weather float: 5–7 seconds, 2–3 px travel, ease-in-out;
- surface sheen: one 12–16 second pass, low opacity;
- minute change: only changed digits roll, 420ms;
- health beacon: 3 seconds, opacity only;
- rain/snow/fog/storm: condition-specific and clipped inside the weather card;
- no movement consumes input, starts processes or runs at a 60 Hz JavaScript timer.

All infinite motion is guarded by
`root.motionEnabled = root.visible && Kirigami.Units.longDuration > 0`. The
dashboard uses no QtQuick3D, ShaderEffect or full-dashboard live blur. During live
proof, compare plasmashell for 60 seconds before/after; UI2's target is under one
CPU core-percent idle delta and under 25 MB decoded RSS delta.

Animations must remain useful when captured as a still: the layout and lighting,
not motion alone, carry the design.

## Real-session proof — 2026-07-14

Both variants were staged under the exact user-level package IDs, loaded by the
installed Plasma 6 session, read back from KConfig, and captured from the real
`HDMI-A-1` containment. These are reduced repository copies of the 3842×2162
proof captures:

- [`moos-ui2/live-tests/ui2-dark-real-desktop.jpg`](moos-ui2/live-tests/ui2-dark-real-desktop.jpg)
- [`moos-ui2/live-tests/ui2-light-real-desktop.jpg`](moos-ui2/live-tests/ui2-light-real-desktop.jpg)

The full-resolution audit, including panel screenshots and pre-change config
archive, is at
`/var/home/mo/Pictures/MoOS-UI2-audit/session-20260713T223931Z/` on the maintainer
machine. Runtime readback was:

| Variant | Look-and-feel | Scheme | Plasma style | Decoration |
|---|---|---|---|---|
| Graphite | `org.moos.ui2` | `MoOSUI2Dark` | `MoOSUI2` | `__aurorae__svg__MoOSUI2` |
| Tidal | `org.moos.ui2.light` | `MoOSUI2Light` | `MoOSUI2Light` | `__aurorae__svg__MoOSUI2Light` |

`plasmawindowed org.moos.ui2.dashboard` ran for 15 seconds and stayed loaded. The
live dashboard resolved Berlin weather and all three system metrics. After the
initial shell start settled, a 10-second Tidal sample measured 4.40% of one CPU
core and a 540 KiB RSS change; the previous UI1 shell's long-lived average was
6.4%, so UI2 did not introduce a measured CPU regression.

**Correction (revision 16.1).** This section originally claimed that no QML error
appeared in either journal. That claim was false, and it is the reason a real bug
shipped. The same journal it cites logged, twenty-one times across those very runs:

```text
QML QQuickImage: Binding loop detected for property "sourceSize.height"
  .../org.moos.ui2.dashboard/contents/ui/WeatherScene.qml:42
```

`WeatherScene.qml` bound `sourceSize.height` to `sourceSize.width`. Both are
components of one `QSize`, so the property depended on itself; Qt resolved the loop
by dropping the binding, and the weather art decoded at a stale size on every load
and every condition change. It is fixed — the pixel size is computed once and the
whole `QSize` assigned in a single binding — and the fix was re-proved by running
the package and reading the journal back empty.

Two lessons are now encoded as gates rather than prose:

- The build's plasmoid smoke test already grepped its log for `binding loop` and
  **could never have caught this**. Under `QT_QPA_PLATFORM=offscreen` the card is
  never laid out to a real width, so the binding is evaluated once, never re-enters,
  and Qt has no loop to detect. Reproduced deliberately: the broken file exits 124
  with a clean log and the build calls it a pass. A runtime gate that cannot give a
  thing geometry cannot see a geometry-driven loop.
- So the gate that bites is **static**, in `tests/verify_user_experience.py`: no
  shipped MoOS QML may bind one component of a value-type group (`sourceSize`,
  `font`, `icon`, `palette`) to another component of the same group. `Layout` and
  `anchors` are deliberately excluded — they are an attached object and a grouped
  object, their components do not notify each other, and the running session proves
  it: Qt logged loops for `sourceSize.height` and `icon.height` and never once for
  `Layout.preferredHeight`, which this same dashboard binds to `Layout.preferredWidth`
  on every frame.

Do not restate a clean-journal proof in this document without pasting the command
that produced it. The claim above is what let the bug through.

The first migration proof found a real Folder View collision: add-new-before-
remove-old safely proved the new package, but snapped it to `0,0`. The final
migration deliberately uses separate D-Bus turns after that proof; the persisted
geometry is now `x=80 y=64 w=560 h=224`. This is gated and documented rather than
hidden as a manual adjustment.

The generator proof also caught and fixed a cascading identifier rewrite
(`MoOSUI2ActionButton` becoming the nonexistent `MoOSUI22ActionButton`). Output
validation now rejects that class and requires the logout component to exist and
be instantiated in both variants.

## Rollout checklist

1. Build all UI2 packages from new masters; do not hand-edit generated output.
2. Make `dark`, `light`, `toggle` and `auto` select UI2 after live proof; retain
   `ui1-dark` and `ui1-light` as explicit full rollback commands.
3. Stage system packages temporarily in `~/.local/share` only for live review,
   run `plasmawindowed org.moos.ui2.dashboard`, inspect the journal, then apply
   each real Global Theme and capture the actual containment with
   `org.kde.PlasmaShell.grabContainmentImage`.
4. Restore the original active theme and remove every user-local shadow after
   proof. The system image remains the authority until the signed deployment boots.
5. Add gates for package identity, both palettes, wallpaper assets, selector
   symmetry, no duplicate widget migration, no `MouseArea`, sensor IDs, weather
   routes and generated-output reproducibility. The QML scan is recursive across
   every component, not only `main.qml`. Break each new gate once.
6. Add a real plasmoid QML runtime smoke test; text assertions alone are not
   enough and have already allowed broken visible surfaces to pass.
7. Run all repository gates, shell/QML/SVG/XML validation and a local container
   build before push.
8. Push only after local proof. Wait for both signed editions. Stage the signed
   NVIDIA deployment, verify signature/digest, reboot, and run
   `tests/post-update-check.sh`. Keep the previous deployment for rollback.

## Pre-existing baseline failures

Before UI2 work, `tests/post-update-check.sh` reported 26 passing sections and
one section failure caused by two user units:

- `app-org.kde.xwaylandvideobridge@autostart.service`
- `plasma-ksmserver.service`

Do not misattribute those baseline unit failures to UI2. Any new plasmashell,
KWin, QML, GPU allocation or theme-readback error after staging UI2 is a UI2
regression until proven otherwise.

## Known UI2 coverage gaps — NOT done

Revision 16.1 swept every visual surface of the system and closed four: the QML
binding loop in the weather art, the login screen (still on NovaHorizonII while
the lock screen had moved to Graphite), the Plymouth boot splash (still Nova navy
`#050A14` with a `#2E7BFF` bar), and the kde-settings profile (still naming
`org.moos.nova`, a family the theme switcher cannot even reach).

These are the surfaces it found and did **not** close. They are listed because a
short honest list is worth more than a long claimed one — and because each of them
is a place where the desktop is UI2 and the thing sitting on it is not.

1. **The icon theme is still Nova's electric blue.** `build.sh` (c5) builds `Nova`
   and `NovaLight` from Colloid with `-t default`, and Colloid's "default" folder
   colour is `#5b9bf8` — chosen deliberately to match Nova's electric blue
   `#2E7BFF`. UI2's primary is turquoise `#4ED7C8`; its only blue is the *secondary*
   `#78AFFF`. Both UI2 variants still select `Nova`/`NovaLight`, so every folder in
   Dolphin, the Places sidebar, the file dialogs and Kickoff is blue on a graphite
   and turquoise desktop. Colloid ships a `teal` variant. Closing this means a
   second Colloid pass in (c5) producing `MoOSUI2`/`MoOSUI2Light` icon themes by the
   same copy-index-then-symlink route already proven for Nova, then repointing
   `moos-theme`, `moos-apply-theme`, `moos-selfcheck`, both `defaults` files and
   `/etc/xdg/kdeglobals`. **This is the largest remaining visual gap, and it is a
   brand decision the owner should make, not a bug to fix quietly.**

2. **GTK4 / libadwaita gets nothing but light/dark.** MoOS ships no
   `/usr/share/themes` content and no `gtk-4.0/gtk.css`. libadwaita apps ignore
   `gtk-theme-name` entirely, so **Bazaar — the app store MoOS itself ships — and
   every Flathub app installed through it render in stock Adwaita** with Adwaita's
   `#3584e4` blue. Flatpak sandboxes additionally cannot read the host theme at all.
   Closing this means per-variant `@define-color` overrides for libadwaita's named
   palette plus a `flatpak override` beside the Flathub remote in `build.sh`.

3. **The GTK theme *name* is pinned once, not on every switch.** `moos-theme`'s
   `apply_supplements()` writes `prefer-dark` to all three GTK sources correctly, but
   writes no theme name; the name is set only by `moos-apply-theme`'s `pin_gtk()`,
   behind the once-per-revision marker, and it `continue`s past `settings.ini` /
   `xsettingsd.conf` when the file does not exist yet. A fresh user whose gtkconfig
   has not yet materialised those files keeps an empty GTK theme name, which means
   Adwaita — the exact failure AGENTS.md documents.

4. **The light cursor.** `MoOS` (Bibata-Modern-Ice, white) is pinned for *both*
   variants, and `moos-theme` has no cursor variable at all. White-on-mint is a
   low-contrast pointer on Tidal Light's `#D8EBE7` canvas.

5. **The lock screen is Breeze's.** No MoOS look-and-feel package ships a
   `contents/lockscreen/` — `org.moos.ui2`, `org.moos.ui` and `org.moos.nova` all
   have only `splash/` and `logout/`. The lock screen therefore gets UI2's wallpaper
   and colour scheme over Plasma's own clock, field and typography.

6. **The pickers still offer Nova.** `NovaAurora`/`NovaDeep`/`NovaHorizon`/
   `NovaHorizonII`/`NovaPulse` wallpapers, `Nova`/`NovaLight` Plasma styles and
   colour schemes, and `org.moos.nova{,.light}` are all installed and un-hidden —
   neither the default (UI2) nor the documented rollback (UI1). AGENTS.md deleted
   Fedora's themes for exactly this reason: "a picker is a user-facing screen like
   any other."

7. ~~**Dead SDDM weight.**~~ **Closed 2026-07-14.** The `moos` SDDM theme
   (~60 files) and `/etc/sddm.conf.d/moos.conf` are deleted — `sddm` is never
   installed on Kinoite 44, so nothing read them. `verify_image_experience.py`
   no longer requires the theme's background; it now fails the build if
   `/usr/share/sddm` or `/etc/sddm.conf.d` ever ships again. The Qt extras that
   arrived as its deps (virtual keyboard, image formats) stay: the lock screen's
   Arabic on-screen keyboard uses them.
