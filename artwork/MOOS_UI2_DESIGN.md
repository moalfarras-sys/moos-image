# MoOS UI — Liquid Glass design system

Status: current authoritative visual contract. Historical UI1, Nova and session
audit journals live in Git history, not in HEAD.

This file defines appearance and interaction, not completion status or a second
task queue. `docs/DEVELOPMENT_PLAN.md` schedules the work; `PROJECT_STATE.md`
records what source, a candidate image and the installed machine actually prove.

## Authority

MoOS has one visual implementation with palette variants, not several themes
that may drift independently.

- semantic dark/light core: `artwork/moos-ui2/palette.json`;
- family tokens: `artwork/moos-themes/palettes.json`;
- deterministic package/artwork generator: `artwork/generate_moos_ui2.py`;
- shared Qt/Kirigami tokens: `system_files/usr/lib64/qt6/qml/org/moos/ui/`;
- runtime selector/migration: `moos-theme`, `moos-apply-theme`,
  `moos-ui-migrate`;
- current migration revision: `THEME_REV` in `moos-apply-theme`;
- action icon geometry: `generate_moos_symbolic_icons.py` and
  `MOOS_UI_SYMBOL_MAP.md`.

Graphite/Tidal is the base pair. Amethyst, Aurora, Dev, Gaming, Midnight, Nova
and Study are colour families generated through the same engine; each has a
dark and light package. A variant may change semantic colour values and
wallpaper exposure, never component geometry, typography, spacing, interaction
or ownership.

## Product character

MoOS is calm, clear and materially rich. Liquid Glass communicates hierarchy;
it is not decoration applied to every rectangle. The product signature is the
Tidal Horizon: broad mineral-glass planes that settle into a quiet horizon,
plus a short Tidal Cut used as a controlled luminous edge.

The user should not see where Plasma ends and MoOS begins. Login, lock, power,
desktop, launcher, panel, popups, Qt/GTK applications and first-party apps share
one palette, type system, corner system, icon language and motion rhythm.

Plasma owns the shell, KWin owns composition/window management, and Wayland is
the display/input protocol. MoOS composes their supported interfaces into one
product. Product naming does not rename packages, D-Bus interfaces, plugin IDs,
license notices or recovery diagnostics. Identity is enforced by the existing
image and migration gates; it is not code obfuscation, disk encryption or a
restriction on the owner's ability to repair their computer.

Avoid:

- pure black/white, neon cyberpunk, random purple/blue gradients;
- stacked translucent cards with no readable hierarchy;
- copied macOS traffic lights or Windows/ChromeOS silhouettes;
- stock or mixed icon families on a MoOS-owned surface;
- blur as the only source of contrast;
- ambient motion that consumes CPU or hides state;
- hard-coded LTR ordering, bilingual labels, or a second Arabic fallback face.

## Product names and implementation owners

These names describe user-facing experiences. They do not authorize technical
ID changes or assert that the proposed interactions below already ship.

| Product name | Scope and existing owner |
| --- | --- |
| **MoOS UI** | The shared design system: palette generators, `org/moos/ui`, Plasma Style and Aurorae assets |
| **MoOS Bar** | One floating Horizon panel; `usr/share/moos/moos-bar.conf`, `usr/bin/moos-bar-apply`, the Plasma layout template and stock task manager |
| **MoOS Search** | The separate `org.moos.search` field and `org.moos.brand/contents/ui/LauncherView.qml`; use existing KDE search models and routes |
| **MoOS Island** | The contextual `org.moos.island` panel zone; MPRIS owns media state and Remote owns session state |
| **MoOS Workspace** | The desktop/window experience: stock KWin overview, desktops, tiling, KScreen and generated MoOS decorations |
| **MoOS Intro** | One visual journey through Plymouth, the resolved Plasma Login Manager, shell splash and welcome application |
| **MoOS Hub** | The desktop scene's time, weather and device-health instrument in `org.moos.ui2.wallpaper`; controlled from the desktop right-click menu and the wallpaper page, drawn below icons and windows |
| **MoOS Motion** | Finite spring feedback and transition rhythm: `SpringFeedback.qml`, `Tokens.qml`, KWin durations; Reduced Motion stops all of it |
| **MoOS Sound** | Original event sounds in `usr/share/sounds/moos/` mapped to KDE notification events |

The complete vocabulary, including MoOS Shield and MoOS Speed, and the wave
plan live in `docs/DEVELOPMENT_PLAN.md` ("MoOS Experience Program").

Paths in this table are under `system_files/` unless otherwise stated. Existing
IDs such as `org.moos.nova.clock`, `MoOSUI2*` and `org.moos.ui2.*` remain stable.
"Horizon" names the composition; "Nova" is a palette, not another desktop.

## Core semantic palette

| Token | Graphite dark | Tidal light | Purpose |
|---|---:|---:|---|
| canvas | `#14191C` | `#D8EBE7` | desktop/app foundation |
| surface | `#1D2529` | `#C9E2DD` | windows, menus, panel |
| card | `#232D32` | `#E1F0EC` | primary groups |
| raised | `#2C383E` | `#B8D8D2` | controls and selection |
| primary | `#4ED7C8` | `#006D67` | focus and active state |
| secondary | `#78AFFF` | `#1D6278` | links and secondary state |
| positive | `#69D9A5` | `#086B4B` | healthy state |
| warning | `#F4C56A` | `#7B520F` | caution |
| negative | `#FF7D88` | `#A52F3F` | destructive/error |
| text | `#E8F1EF` | `#17302E` | primary ink |
| muted | `#9CAFAC` | `#466360` | secondary ink |
| outline | `#415158` | `#527F79` | edges and separators |

Text contrast is judged against the effective fallback fill, not an ideal blur
sample. Every important edge must remain legible with compositing disabled.

## Geometry and rhythm

- spacing rhythm: 4 / 8 / 12 / 16 / 24 / 32 logical px;
- minimum interactive target: 40×40 logical px; touch-first controls: 44×44;
- nested radii: controls 8–12, cards 12–16, panels 16–20, dialogs 20–24;
- a nested surface uses a smaller radius than its parent;
- panel/dock stays one bottom floating capsule. Do not add a second bar;
- the Tidal Horizon is physical geometry and does not mirror in RTL. Logical
  content, navigation and text do mirror;
- wallpaper geometry is shared across palettes and preserves quiet upper space
  for work and desktop content.

Responsive layout is based on logical width/height, not one owner's 4K screen.
Login controls in particular must fit the 640×480 firmware/TCG mode while
remaining full-sized at normal desktop resolutions.

## Typography

- interface: IBM Plex Sans; Arabic: IBM Plex Sans Arabic;
- code/terminal: JetBrains Mono, with Kawkab Mono for joined Arabic glyphs;
- primary body: 13–15 logical px; captions: 10–12; section title: 18–24;
- large clock numerals may use ExtraLight, but controls never use display type;
- time is a semantic LTR island even inside Arabic RTL;
- expose plain localized labels to accessibility APIs—never raw mnemonic marks.

The font authority is `system_files/etc/fonts/conf.d/61-moos-brand.conf`,
`etc/xdg/kdeglobals` and the generated Konsole profiles. Verify the effective
font cascade and mixed Arabic/Latin rendering on the installed system; a
configured family alone does not prove glyph fallback.

## Icons

MoOS action icons use the Tidal Cut symbolic set. They are filled silhouettes
with one deliberate counter, readable in one colour at 16 px and bound to KDE
semantic colour roles. Full-colour marks are reserved for product/application
identity. Do not recolour or mask the MoOS or Mo AI identity marks as actions.

Application launchers, settings routes, notifications, dialogs and system
actions must resolve to a real icon at every shipped size. A missing icon that
falls back to a generic placeholder is a release defect.

## Material

A Liquid Glass surface has:

1. a palette-tinted fallback fill that works without blur;
2. one restrained hairline/inner highlight;
3. one soft depth shadow where elevation is meaningful;
4. a focus/active edge using the semantic primary role;
5. no more layers than needed to explain containment.

Software rendering uses opaque or near-opaque fallbacks. Cloud/TCG/weak-device
profiles reduce effects through capability detection, not a separate design.

## Motion

Motion communicates entrance, focus, selection, progress or state change.

- interaction feedback: about 120 ms;
- normal geometry transition: 180–240 ms;
- emphasized finite transition: 320–420 ms;
- boot animation yields immediately when the system is ready;
- Reduced Motion makes decorative transitions exactly zero, not one millisecond;
- infinite motion must be visible, state-bearing, low-frequency and guarded by
  `visible && Kirigami.Units.longDuration > 1` or an equivalent shared token;
- no 60 Hz JavaScript timers, ShaderEffect theatre, or process-spawning motion.

## Surface contracts

### Boot → login → desktop

Plymouth's final composition, Plasma Login Manager and the first desktop frame
share logo scale, horizon position and background family. Normal boot shows no
foreign identity, text console, cursor flash or avoidable black/white frame.
The animation never delays a ready login/desktop.

Plasma Login Manager owns two intentional states: MoOS idle clock and password
form. Its upstream ten-second timeout hides the form; therefore `ShowClock=true`
is required. Any key/pointer action restores authentication immediately.

### Panel and launcher

The Horizon panel is one quiet bottom command island. Its active applet is a lit
slot, never a bordered box. The launcher presents primary destinations once;
secondary actions stay visually quiet. Popups inherit the same material and
must not fall back to Breeze artwork.

The search field has its own space and hit target; it never overlays the MoOS
button. Preserve stock task grouping, pinning, previews and drag/reorder.
MoOS Island is currently a horizontal panel applet with a one-pixel idle
footprint, keeping its representation instantiated. Do not move its wide media
content into a square tray cell or return to a zero-width initial state.

### First-party apps

Settings, Store, Updater, Recovery, Mo AI, Installer, MoPlayer and Mo PC Remote
share the token module. Each surface needs honest loading, success, error and
recovery states. The UI never reports success before the backend confirms it.
Privilege prompts and error dialogs belong to the same language and remain
usable with blur/effects disabled.

### Dashboard and wallpaper

The dashboard is one passive plasmoid with time, weather and system groups. It
must not intercept desktop gestures. Weather artwork is local and MoOS-owned;
failed network data disappears or explains itself without stale false values.
Only the active asset is decoded, and idle CPU/RSS is measured after changes.

## Experience goals for coherent implementation batches

The following are design goals for the development plan, not claims of shipped
capability. Extend the existing components. Deliver a complete user journey in
each batch, with controls, motion, error states and accessibility reviewed
together before producing its release candidate.

1. **A composed MoOS Bar and Search.** The bar reads as three regions within
   one surface: entry/search, running work, and system state. Search opens a
   single focused results surface for applications, settings and permitted
   local content, with an explicit handoff to Mo AI. Results reveal their type
   and action before activation. Work in `moos-bar.conf`, `moos-bar-apply`,
   `org.moos.search`, `org.moos.brand` and `org.moos.nova.clock`. Acceptance:
   no overlaps at the smallest supported logical width, two separate entry
   targets, real keyboard search/launch/Escape, preserved app pins/reordering,
   readable localized date/time and correct RTL order.

2. **A useful MoOS Island.** A small state-bearing area grows into context,
   then settles when the work ends. Start from existing media and Remote
   states; expose progress/cancel/retry for other work only after its owner
   supplies a real job contract. Keep one foreground state, deterministic
   priorities and a discoverable way to inspect background work. Work in
   `org.moos.island`, MPRIS integration and the owning job APIs. Acceptance:
   idle → active → changed → complete/error → idle transitions, simultaneous
   media/Remote cases, keyboard-equivalent controls, and no stale success or
   invisible running progress animation.

3. **A spatial MoOS Workspace.** Windows, task previews, desktop switching
   and overview share focus colour and a restrained directional rhythm.
   Provide discoverable overview and tiling through supported KWin actions;
   preserve user's shortcuts, focus and application state. Own appearance in
   the artwork generators/Aurorae; own policy in `etc/xdg/kwinrc`,
   `moos-apply-theme` and `moos-visual-tier`. Acceptance: real minimize/restore,
   maximize/tile/overview/full-screen flows, correct exclusive effect groups,
   fractional-scale and output-hotplug checks, no stolen focus and no dropped
   input during repeated transitions. A custom compositor fork is not required.

4. **A continuous MoOS Intro.** Carry the same horizon and logo composition
   from the boot screen into authentication and the first desktop frame.
   Fade between meaningful states; never wait for an animation to finish when
   the next state is ready. Work in the Plymouth generator/assets,
   `org.moos.ui2.greeter`, generated look-and-feel splash and `apps/welcome`.
   Acceptance: recorded cold boot and login at normal and 640×480 fallback
   sizes, no foreign identity or avoidable blank flash, immediate password
   entry, and successful first-run/repeated-login paths. Still screenshots
   alone cannot prove the handoff.

5. **One system interaction language.** Settings, Updater, Recovery, Store,
   Mo AI and Remote use shared controls and page structure. Progress lives in
   the same place across surfaces; every operation has a truthful pending,
   success, error and retry/cancel state appropriate to its backend. Extend
   `org/moos/ui`, `usr/share/moos/apps/` and existing service routes. Mo AI
   confirmations name the actual action, then show the executor's result.
   Acceptance: complete install/update/device/provider journeys, shared
   dark/light controls, accessible state changes and backend readback. A
   decorative card or a model's answer cannot stand in for an executed action.

6. **Physical feedback and original sound.** Finite springs add a small
   compression/release to controls; geometry settles without moving hit
   targets. Page transitions explain direction, and sound marks meaningful
   outcomes rather than every hover. Reuse `SpringFeedback.qml`, `Tokens.qml`,
   `Button.qml`, `usr/share/sounds/moos/` and KDE event mappings. Acceptance:
   interruption/reversal/rapid-input tests, immediate stop when hidden or
   Reduced Motion is enabled, stable targets, real event playback, mute and
   custom-sound preservation. No animation timer may run merely to decorate
   an idle desktop.

7. **Responsive clarity and measured speed.** Complete every goal above for
   Arabic, English and German, light/dark, keyboard and pointer before adding
   further visual layers. Use the existing locale authority, visual-tier
   policy and native review harnesses. Acceptance: the representative matrix
   below, screen-reader names/order, visible focus, contrast against opaque
   fallbacks, and recorded launch latency/frame pacing/idle CPU/PSS against
   the same workload before the batch. Regressions require a measured cause
   and resolution; "lighter" is not a property inferred from fewer files or
   stronger hardware. Weak-GPU/software rendering keeps the same layout with
   cheaper materials.

## Localization, scaling and accessibility

Required representative visual classes:

- 1920×1080, 2560×1440, 3840×2160;
- 100%, 125%, 150%, 200%, 225%, 250%;
- English LTR, German LTR, Arabic RTL;
- dark and light; software-rendered fallback where relevant.

Every class needs a real screenshot from a running surface. Inspect clipping,
overlap, elision, minimum targets, RTL order, focus, keyboard navigation,
accessible names, reduced motion and contrast. Automation may reduce redundant
combinations but cannot replace looking at each distinct responsive/RTL class.

## Executable design reference

`artwork/moos-ui2/DesignStudio.qml` imports the real `org.moos.ui` components,
the official MoOS mark and shipped palettes. Its arrangement, opacity and motion
controls affect sample content only; it is not a system settings window.
`python3 scripts/review/design-studio.py` runs it with isolated HOME, XDG config
and session bus, including host delegation from VS Code Flatpak.

```sh
python3 scripts/review/design-studio.py --language ar --scheme MoOSUI2AuroraLight
python3 scripts/review/design-studio.py --language en --scheme MoOSUI2Dark \
  --width 1440 --height 1080 --capture test-results/design-studio/dark.png
python3 scripts/review/design-studio.py --language ar --width 1920 --height 1080 \
  --scale 2 --capture test-results/design-studio/arabic-4k.png
```

Capture uses real Qt with software rendering. A 4K PNG proves source rasterisation,
not desktop GPU/blur/scale qualification. Native Wayland review is separate.
German and screen-reader coverage remain open; the reference supports Arabic/English.

Carry these decisions into production surfaces:

- Lead with one task and one primary action. Use space before adding nested cards.
- Keep the official mark uncropped, with no baked glow rectangle. Workspace
  previews distinguish sample content from live windows explicitly.
- Stack groups at narrow widths; keep 40–44 px actions and vertical scrolling.
  Never shrink text to hide overflow.
- Read glass policy from the effective user/system configuration without writing
  defaults into the user's file. Startup preference is not runtime effect or
  per-window blur availability; the live clarity control still needs that bridge.
- Geometry settles after input; Reduced Motion stops geometry/button feedback.

Task ownership and acceptance live in the plan's “Design completion handoff”.

## Change and proof workflow

1. Modify the authoritative token/source/generator, never a generated sibling.
2. Regenerate and run deterministic checks; bump `THEME_REV` when an existing
   user's cache or persisted state must be migrated.
3. Run SVG/XML/QML/source gates and deliberately prove new regressions bite.
4. Load the real surface, interact with it and inspect its journal/process state.
5. Capture temporary evidence outside the repository; retain only selected,
   current evidence with a release purpose.
6. Finish the coherent batch and its fast component/live checks, then freeze
   the candidate revision and run the matching complete local image build.
   Rebuild after source fixes or a demonstrated image-level failure, not after
   every cosmetic edit. Boot the exact artifact through `RELEASE.md` before
   promotion. A source screenshot does not prove the installed image and a
   parser does not prove the pixels.
7. Remove every user-local package/cache shadow used for live development so
   `/usr` remains the runtime authority after update.

Core checks:

```bash
python3 artwork/generate_moos_ui2.py --check
python3 artwork/generate_moos_symbolic_icons.py --check
python3 tests/test_moos_ui2.py
python3 tests/test_tidal_portals.py
python3 tests/test_moos_symbolic_icons.py
python3 tests/test_moos_symbolic_runtime.py
python3 tests/verify_user_experience.py
```

The release decision still requires clean-VM and upgraded-real-host visual proof.
