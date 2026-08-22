# MoOS UI — Liquid Glass design system

Status: current authoritative visual contract. Historical UI1, Nova and session
audit journals live in Git history, not in HEAD.

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

Avoid:

- pure black/white, neon cyberpunk, random purple/blue gradients;
- stacked translucent cards with no readable hierarchy;
- copied macOS traffic lights or Windows/ChromeOS silhouettes;
- stock or mixed icon families on a MoOS-owned surface;
- blur as the only source of contrast;
- ambient motion that consumes CPU or hides state;
- hard-coded LTR ordering, bilingual labels, or a second Arabic fallback face.

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
- code/terminal: IBM Plex Mono;
- primary body: 13–15 logical px; captions: 10–12; section title: 18–24;
- large clock numerals may use ExtraLight, but controls never use display type;
- time is a semantic LTR island even inside Arabic RTL;
- expose plain localized labels to accessibility APIs—never raw mnemonic marks.

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

## Localization, scaling and accessibility

Required representative visual classes:

- 1920×1080, 2560×1440, 3840×2160;
- 100%, 125%, 150%, 200%, 225%;
- English LTR, German LTR, Arabic RTL;
- dark and light; software-rendered fallback where relevant.

Every class needs a real screenshot from a running surface. Inspect clipping,
overlap, elision, minimum targets, RTL order, focus, keyboard navigation,
accessible names, reduced motion and contrast. Automation may reduce redundant
combinations but cannot replace looking at each distinct responsive/RTL class.

## Change and proof workflow

1. Modify the authoritative token/source/generator, never a generated sibling.
2. Regenerate and run deterministic checks; bump `THEME_REV` when an existing
   user's cache or persisted state must be migrated.
3. Run SVG/XML/QML/source gates and deliberately prove new regressions bite.
4. Load the real surface, interact with it and inspect its journal/process state.
5. Capture temporary evidence outside the repository; retain only selected,
   current evidence with a release purpose.
6. Build the image and boot the exact artifact. A source screenshot does not
   prove the installed image and a parser does not prove the pixels.
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
