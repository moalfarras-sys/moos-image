# MoOS complete design-language, visual and UX polish audit

**Audit date:** 2026-07-30
**Working branch:** `audit/commercial-visual-polish-2026-07-30`
**Reference commit:** `223c71d`
**Design system:** MoOS UI — Liquid Glass
**Target environment:** Plasma 6 on Wayland, Arabic/English, 4K at 225%

> **Implementation closeout: source and local generic image accepted.**
> This document began as the rejection record for the 2026-07-30 audit. The
> findings below were kept because they are the reasons for the implementation,
> not because they are still open. The source blockers are now closed by one
> shared QML layer, the original 69-symbol **Tidal Cut** family, the three-column
> Launcher, one-locale shell/app copy, simplified motion, live 16-palette GTK
> styling and the native MoPlayer frame. The image repository `just check` is
> green; canonical MoPlayer is clean at **176/176**, committed as `23799ad`,
> pushed, and vendored from that exact revision. The full generic `just build`
> is also green from this exact worktree, including the in-image QML, Launcher,
> desktop-scene, identity, Store, initramfs/Plymouth and bootc gates. Signed
> publication, installation update and reboot remain release evidence—not
> assumptions—and are recorded separately when they actually complete.

## Executive decision

MoOS has a recognisable identity, but the pre-audit tree did not yet express
that identity as one complete commercial design language. Wallpapers, session
screens and first-party apps shared a mood; they did not always share the same
geometry, semantic foreground rules, interaction hierarchy or accessibility
behaviour. The correct unit of work was therefore the whole system, with icons
as one downstream expression of it—not an icon replacement project.

The audit found the remaining faults concentrated at the seams:

- selection foregrounds were painted over unpaired gradient endpoints;
- first-party GTK windows understood only two of the 16 MoOS palettes;
- three QML applications carried private, mutually inconsistent SVG libraries;
- visually custom controls remained pointer-only or invisible to assistive
  technology;
- finite transitions continued after the user disabled animation;
- two privileged/status paths blocked their GTK main loops;
- inherited RTL mirroring was applied twice in shell controls; and
- MoPlayer's login/player routes did not share the desktop window, contrast,
  focus, semantics and reduced-motion contracts.

The implementation closes those seams without adding a second style engine. It
establishes one GTK palette/controller, one importable QML token/control layer,
one generated symbolic catalogue, one Flutter hidden-content seam and one
coalescing worker. Welcome and Installer now make the reduced-motion branch
unconditionally zero; Store, Welcome, Installer and Mo AI consume the same
tokens, focus, button and symbol contracts.

The rejected monoline icon checkpoint was not polished incrementally. It was
replaced wholesale by **Tidal Cut**: 69 original compound-path symbols built
around cut negative space, calm filled mass and shared corner geometry. One
manifest drives QML lookup and installed SVG output. KDE/KIconLoader, GTK4
symbolic lookup and librsvg rasterisation at 16/20/24/64/128 px are executable
gates, including clipping, empty output, semantic palette substitution and
state distinction.

At source, repository-gate and local generic-image level the result is accepted
for integration. Signed-registry and booted-machine evidence remain mandatory
before the revision is called shipped.

## Scope and method

The audit covered the user journey rather than only the theme packages:

1. boot and session hand-off: Plymouth, Plasma splash, login, lock and logout;
2. shell: desktop, wallpaper/dashboard, launcher, panel/dock, widgets,
   notifications, dialogs, tooltips and context menus;
3. first-party Qt/QML: Welcome, Installer, Store and Mo AI;
4. first-party GTK: Recovery, Updater and Mo PC Remote through the shared UI2
   layer;
5. settings integration: active KDE colour scheme, icon-theme precedence,
   theme switching, font scaling, RTL and reduced motion; and
6. MoPlayer in its canonical repository at `/var/home/moos/MoPlayerMoOS`.

Review combined:

- source and generated-output comparison;
- relationship gates across every one of the 16 `.colors` schemes;
- WCAG 2.x relative-luminance calculations;
- QML engine load probes in English and Arabic RTL;
- keyboard, focus and accessibility-tree contracts;
- deterministic SVG/XML/geometry validation;
- asynchronous-main-loop tests with controlled fake processes;
- source, widget-test and semantics-contract review in the canonical Flutter
  application, followed by an attempted full canonical gate; and
- raster review sheets used to judge—and reject—the first symbolic candidate.

No metadata-only result is treated as a boot or visual proof. Prior live evidence
is useful baseline context, but it does not prove this unbuilt worktree.

## One unified visual language

This section is the binding commercial design contract, not a claim that the
current tree already conforms. Each toolkit may express it with native
primitives; QML, GTK, Plasma SVG and Flutter do not need a new cross-toolkit
runtime. They do need to resolve the same semantic decisions and pass the same
relationship tests. The four first-party QML apps should share a small
importable/generated token and control layer; four private copies are not a
design system.

### Identity invariants

- **MoOS is the master identity.** Its mark and wordmark geometry are immutable
  brand assets. They may be recoloured for an accessible active palette, seated
  on the standard application plate, scaled or surrounded by theme-native light;
  they are not redrawn, simplified or reshaped.
- **Mo AI keeps its existing orb/mark silhouette.** The same colour-only rule
  applies: a palette can tint the supplied geometry, but the shape is not
  replaced by a generic assistant/chat glyph where the product identity is
  intended.
- **Product identity and action iconography are separate.** Launch icons may be
  full-colour brand plates. Controls, navigation and statuses are symbolic and
  inherit semantic theme roles.
- **Dark/light variants are one system, not two designs.** Geometry, spacing,
  typography, hierarchy, state and motion are identical; only semantic colour,
  material opacity and shadow density vary.
- Technical compatibility identifiers may retain historical names. They do not
  define the user-visible language and are not a reason to fork its geometry.

### Provenance

The symbolic action family in this pass is original geometry authored from
scratch in `artwork/generate_moos_symbolic_icons.py`. It is not described as an
import, trace, modification or derivative of Breeze, Material, Lucide, Fluent,
Papirus or another third-party icon family. No such provenance is claimed.

Original authorship alone did not establish identity, so the first 67/68-symbol
monoline checkpoint was rejected. The accepted family is a second construction:
69 filled compound-path glyphs with a shared **Tidal Cut**—a deliberate opening
or counterform that keeps small silhouettes breathable and recognisably MoOS.
The final manifest, installed directory and both review sheets contain the same
69 names; no hand-edited output is canonical.

Toolkit engines and protocol roles remain compatibility infrastructure; they
are not the authorship source for MoOS artwork. The design contract is stated in
MoOS terms and the repository generator is the canonical source.

### Proportion and layout

The system uses a **4 logical px base** with an **8 px working rhythm**:

| Token | Value | Use |
|---|---:|---|
| `space-1` | 4 | icon optical correction, compact internal separation |
| `space-2` | 8 | icon/label gap, adjacent compact controls |
| `space-3` | 12 | button/card internal gap |
| `space-4` | 16 | compact page gutter, grouped fields |
| `space-6` | 24 | desktop page gutter, card padding |
| `space-8` | 32 | section separation |

Major composition breaks may use 48 or 64 as multiples of the core scale; they
are not two more component-spacing choices.

Rules:

- Align text to baselines and icon centres, not to each asset's raw SVG box.
- A local exception must still land on a 4 px step unless optical correction is
  documented.
- Desktop content begins at 24 px from its owning surface; compact surfaces may
  use 16 px. Modal content does not touch a glass edge.
- One visual region has one dominant action. Repeating equally loud primary
  actions is a hierarchy failure, even if each button is individually polished.
- Navigation rails, headers and footers retain their position between routes.
  Content may reflow; the user's spatial map must not.
- Text/content follows logical start/end. Session and window controls whose
  location is learned spatially remain on their documented physical edge.
- At narrow widths, reduce columns before reducing padding, type or target size.

This scale maps to `Kirigami.Units`, the QML `fs()` helper and the Flutter
`Nova.space*` tokens at toolkit boundaries. It does not require copying a
pixel literal into every implementation.

### Typography

The shipping default is **IBM Plex Sans Arabic**, providing one coherent Arabic
and Latin UI face. First-party applications consume the user's system-selected
UI font rather than overriding it; this preserves accessibility while keeping
the default brand typography.

| Role | Nominal size | Weight | Line height |
|---|---:|---:|---:|
| caption / metadata | 11–12 | 400–500 | 1.35 |
| secondary body | 13 | 400–500 | 1.40 |
| body / control | 14 | 400–600 | 1.40 |
| emphasized label | 14–15 | 500–600 | 1.35 |
| section/page title | 20–24 | 600–700 | 1.18–1.25 |
| onboarding/hero display | 30–40 | 500–700 | 1.05–1.12 |

- Sizes are logical and scale from `Qt.application.font` or the equivalent
  Flutter accessibility scale. Containers grow with the text they own.
- Arabic and English have equal information hierarchy; Arabic is not rendered
  smaller to make a translation fit.
- `Inter` is limited to deliberately always-Latin numerals and the Latin MoOS
  wordmark where documented. It is not an Arabic UI face.
- The default monospace face is JetBrains Mono. Monospace is for code, paths,
  logs and aligned values, not headings.
- Body copy uses sentence case. Uppercase is limited to short status/brand terms
  whose translation and pronunciation remain clear.
- A first-party surface displays the user's active locale only. It does not
  place Arabic and English translations beside each other. Bilingual visible
  copy is reserved for a language chooser or a deliberate support/error path
  shown before a locale can be known. `Accessible.name` uses the same language
  as the visible control; a second translation is not hidden duplicate chrome.

### Semantic colour

All 16 themes expose the same roles:

`canvas → surface → card → raised` for depth, `text` and `muted` for
information, `primary/secondary/luminous` for selection and focus, and
`positive/warning/negative` for state.

Graphite/Tidal are reference values, not the only supported palette:

| Role | Graphite | Tidal | Contract |
|---|---|---|---|
| canvas | `#14191C` | `#D8EBE7` | application/desktop foundation |
| surface | `#1D2529` | `#C9E2DD` | persistent chrome and panels |
| card | `#232D32` | `#E1F0EC` | grouped content |
| raised | `#2C383E` | `#B8D8D2` | hover/selected/elevated control |
| primary | `#4ED7C8` | `#006D67` | focus, selection, progress |
| secondary | `#78AFFF` | `#1D6278` | links and secondary accent |
| luminous | `#A8F1E8` | `#0B6965` | restrained rim/highlight |
| positive | `#69D9A5` | `#086B4B` | success/healthy |
| warning | `#F4C56A` | `#7B520F` | caution, never generic decoration |
| negative | `#FF7D88` | `#A52F3F` | error/destructive |
| text | `#E8F1EF` | `#17302E` | primary information |
| muted | `#9CAFAC` | `#466360` | secondary information |
| outline | `#415158` | `#527F79` | boundaries and separators |

Rules:

- No runtime surface relies on pure black or pure white.
- Foreground is chosen from the role paired with the actual background; it is
  never guessed from whether the theme “looks dark”.
- Accent gradients are decorative only unless every stop is tested against one
  foreground. Primary controls use a flat, paired Selection fill.
- Positive, warning and negative colours carry meaning. They are not alternative
  accent choices and never communicate state by colour alone.
- Text is measured against the opaque underlying token. Blur/translucency is not
  used to excuse low contrast.
- The user's accent/theme can recolour symbolic controls and brand lighting.
  Logo/mark shape remains unchanged.

### Shape and radii

MoOS uses continuous, calm curvature rather than mixing sharp enterprise boxes
with fully round consumer controls:

| Radius | Value | Use |
|---|---:|---|
| `radius-s` | 8 | small fields and compact status surfaces |
| `radius-m` | 12 | buttons, menu items and list selection |
| `radius-l` | 16 | standard cards |
| `radius-xl` | 20–24 | dialogs and transient/floating surfaces |
| `pill` | half height | segmented controls, chips, dock capsule |
| `circle` | 50% | icon-only circular action, avatar/orb |

- A child radius is normally the parent radius minus its inset.
- Nested surfaces do not stack more than two visible outlines.
- A squircle application plate is identity geometry, not a generic control
  radius.
- Hit geometry and visible geometry are independent: a 14 px window-control disc
  still owns a 40 × 40 target.

### Material: glass versus solid

Liquid Glass is a hierarchy, not a blur effect applied everywhere.

| Surface class | Material |
|---|---|
| wallpaper/art | opaque image/scene |
| application canvas and long-lived window chrome | solid semantic surface |
| cards containing dense text/forms | solid or near-opaque card |
| dock, launcher, menu, notification and popover | controlled tinted glass |
| dialog/modal sheet | near-opaque raised surface plus backdrop |
| focus/selection | semantic flat fill or clear outline |
| login/lock/logout hero light | palette-native atmospheric layer behind readable solid controls |

- Persistent titlebars remain opaque. Rendering blur behind covered pixels adds
  cost without producing visible glass.
- KWin blur remains at the proven ceiling **15**, with noise **3**. Increasing
  blur for spectacle is not acceptable.
- A glass surface needs one edge, one restrained internal highlight and one
  broad shadow. Multiple glow/outline/shadow rings read as visual noise.
- Dense text and destructive confirmation never float directly on an
  unpredictable wallpaper.

### Elevation and shadows

Elevation is semantic and deliberately limited:

- **level 0:** canvas and embedded rows—no shadow;
- **card:** `0 4 12`, low opacity, plus an outline where separation matters;
- **floating:** `0 12 28`, used by popup/dock/dialog above its backdrop.

Dark themes may use up to the existing 0.42 shadow alpha; light themes use up to
0.16 for ordinary elevation. Colour comes from the palette shadow/canvas, never
an unrelated neon. A shadow must not be the only boundary: the outline still
meets the 3:1 non-text requirement where interaction depends on it.

Current conformance is open: shared GTK `.ui2-card` applies `0 10 28` broadly,
while many QML cards are almost flat. The shared-token migration must map both
to the two-level contract rather than averaging the inconsistency.

### Button and action hierarchy

1. **Primary:** one per region; flat primary/Selection fill with paired
   on-accent foreground. Minimum 44 px high for workflow actions.
2. **Secondary:** raised/card fill with normal text and outline; same target
   height, lower chroma.
3. **Tertiary:** transparent or quiet surface; visible hover/focus, never
   invisible at rest when the action is important.
4. **Destructive:** negative role only for an actual destructive/system-state
   operation; paired foreground and explicit verb.
5. **Hold-to-confirm:** reserved for irreversible/high-impact operations.
   Installer disk erase remains a real **1600 ms** hold and keyboard press/release
   preserves the same safety boundary.
6. **Icon-only:** requires tooltip, accessible name, visible focus and a minimum
   40 × 40 logical target even when the glyph is 16–20 px.

Disabled controls remain readable but clearly inactive; reducing opacity cannot
be the only signal if state would become ambiguous. Press, hover, focus,
selected, busy, success and failure are separate states, not one “active” tint.

### Icon language

- Final action icons use the original MoOS Tidal Cut symbolic family; the
  rejected first-pass geometry is retained only as decision history.
- One icon expresses one concept across shell and apps. Local private SVG
  dictionaries are prohibited.
- Stroke, cap, join, optical bound and semantic colour are invariant. Scale does
  not change line language.
- Icons accompany labels for unfamiliar, destructive or high-impact actions.
  A glyph alone is acceptable only for established controls with tooltip and
  accessible name.
- The full-colour MoOS and Mo AI identity marks keep their silhouettes. A
  symbolic “Mo AI” chat action is a control icon; it does not replace the
  product logo.

The whole-family redesign must supply recognisable MoOS DNA without damaging
universal recognition:

- a calm 24-unit construction with fewer arbitrary interior details;
- consistent large-to-small radius ratios and intentional negative space;
- a restrained orbital/comet cut or accent node only where it reinforces the
  concept, never pasted onto every glyph;
- distinctive terminal treatment and optical weight at 16 px;
- filled/outlined balance decided at family level, not icon by icon;
- silhouette tests in monochrome before the accent detail is enabled; and
- paired review of common icons—Home, Search, Settings, Close, Back, Mail,
  Power—because those expose generic-library resemblance fastest.

Acceptance requires a blind family sheet to read as one premium MoOS system
before names are shown. Passing XML, theme-colour and resolution tests is
necessary but cannot substitute for that visual decision.

### Motion language

| Class | Typical duration | Behaviour |
|---|---:|---|
| hover/colour | 120 ms | immediate, `OutCubic`/linear colour |
| press | 160 ms | small scale/ink response, no bounce |
| control geometry/state | 220 ms | one small transform plus opacity |
| page/dialog/reveal | 320 ms | one transform plus opacity |
| ambient | explicitly measured | one low-duty loop, state/visibility gated |

- `Kirigami.Units.longDuration > 1` is the QML animations-off contract.
- Finite QML transitions collapse to zero. Flutter may retain a 60 ms opacity
  cue while removing spatial lift.
- Infinite motion requires motion, visibility and state guards; an inactive
  window pauses decorative work.
- Reduced motion lands every object directly on a complete resting frame.
- No animation is used to conceal I/O latency. Real progress is shown as state,
  spinner or measured progress.

### Imagery, wallpaper and brand light

- Wallpaper is abstract, quiet and crop-safe; it reserves negative space for
  desktop content and exports by crop-to-fill at 16:9, 16:10 and ultrawide.
- Brand light is a supporting atmosphere, not a second logo. It derives from
  the active palette and stays behind readable surfaces.
- Generated/raster identity artwork has a canonical master and deterministic
  exports. It is never stretched or recoloured in a way that changes silhouette.
- Screenshots and previews are product evidence, not decoration in the source
  tree; a stale preview is a defect.

### Interaction, accessibility and RTL

- Pointer, keyboard and assistive technology activate the same action path.
- Every Tab stop has one visible focus treatment and an accessible label matching
  its visible label.
- Modal surfaces claim/contain focus, close with Escape, and keep a visible Close
  action.
- Primary custom targets are 40 px minimum; workflow actions target 44–56 px.
- Arabic is a first-class layout, not translated LTR. Text alignment and
  navigation order mirror logically once.
- Physical controls documented by spatial memory (window controls, safety
  placement) do not jump because the text language changes.
- Numeric/path fragments receive the appropriate direction/isolation.

### Radical-consistency assessment

| Dimension | Before this pass | Final source assessment |
|---|---|---|
| Brand silhouette | Strong, but product/action uses could blur | Strong: MoOS/Mo AI shapes are invariant; actions are separate |
| Palette | Strong in Plasma, binary in GTK, fixed accents in some apps | One 16-scheme semantic model; unsafe pairings removed |
| Material | Generally coherent, with temptation toward decorative blur | Shared solid/glass roles; blur reserved for transient shell surfaces |
| Geometry | Similar mood, inconsistent custom controls | Shared 4/8 px rhythm, 8/12/16/24 radii and 40–56 px action targets |
| Typography | Correct default, historic local overrides | System-font hierarchy; functional floor 11 pt; Launcher/dock density corrected |
| Icons | App plates coherent, action vocabulary fragmented | Original 69-symbol Tidal Cut family; shared manifest and backend-safe output |
| Motion | Infinite loops gated; finite transitions inconsistent | One 120 ms interaction cadence; Splash simplified; Mo AI ambient loops removed |
| RTL | Broadly supported, with double-mirrored shell seams | Logical mirroring once; physical chrome explicitly separated |
| Accessibility | Several polished pointer experiences, incomplete AT seams | Shared focus/action semantics; keyboard, AT, contrast and reduced-motion gates |
| Performance | Strong shell guards, blocking GTK/status seams | Blocking work moved out of UI loops; watchers coalesced; ambient loops removed |

**Radical-consistency verdict: accepted at source level.** The four first-party
QML apps import `usr/share/moos/apps/ui`: `Tokens`, `Button`, `FocusRing`,
`SymbolIcon` and the generated `SymbolCatalog`. Launcher and dock use system
font metrics and the same size floor; Splash, shell transitions and app
interactions converge on the same restrained cadence. MoPlayer expresses the
same decisions natively in Flutter instead of importing a fragile
cross-toolkit runtime.

This deliberately remains a small seam, not a heavyweight component framework.
Each toolkit keeps its stable native rendering and accessibility machinery;
semantic tokens, generated assets and relationship gates make their decisions
agree.

### Commercial launch blockers

| ID | Status | Resolution | Acceptance evidence |
|---|---|---|---|
| DL-01 | Closed | Shared QML type/space/radius/action/focus/symbol layer | Four apps import the canonical module; conformance gate |
| IC-01 | Closed | First checkpoint rejected; 69-glyph Tidal Cut family rebuilt | Manifest-derived 16/24 px paired review; bounds/distinction gates |
| IC-02 | Closed | Compound filled paths preserve counters under symbolic masks | GTK lookup, KDE KIconLoader and librsvg 16–128 px runtime tests |
| MO-01 | Closed | Disabled branch is always zero; enabled stagger parenthesised | Motion relationship gate |
| LN-01 | Closed in source | 720 × 590 three-column Launcher and system-font dock | Live QML load marker and 21/21 shell tests; boot capture still pending |
| SE-01 | Closed | Logout, Theme Picker and Mo AI resolve one active locale | Source/runtime locale and RTL gates |
| MP-01 | Closed | Palette-native MoOS chrome and zero-TTL boundary fix | Canonical `just check`: analyze clean, 176/176; commit `23799ad` vendored |
| PF-01 | Closed structurally | Mo AI ambient loops removed; finite motion gated | No infinite scene work; booted quiet measurement remains evidence work |
| SP-01 | Closed | One reveal plus one progress treatment; static reduced frame | All 16 generated copies identical and QML-load tested |
| IM-01 | Local image passed | Generic image and all in-image gates are green; source is not yet published | Signed CI matrix publication, update, reboot, post-update check |

P0 here means “do not call this a commercial release candidate”; it does not
authorise a shortcut around an identity, boot or safety gate.

## Acceptance measurements

| Property | Release contract |
|---|---|
| Normal text contrast | WCAG AA, at least **4.5:1** |
| Semantic text/glyph contrast | WCAG AA, at least **4.5:1** on its actual fill |
| Non-text boundary/focus contrast | At least **3:1** |
| Primary pointer target | **40 logical px** minimum in MoOS custom controls |
| Compact desktop target | May be **36 logical px** where the full row remains the hit surface; never below WCAG 2.2 AA's 24 px floor |
| Symbolic icon grid | **24 × 24**, **1.75-unit** stroke, round cap/join, nominal bounds **2.5…21.5** |
| Inline/control/header icon size | **16–20 / 20–24 / 28–36** logical px; glyph size never substitutes for target size |
| Reduced motion | `Kirigami.Units.longDuration > 1`; finite durations collapse to zero, while the Flutter path retains a short **60 ms** opacity affordance and removes transforms |
| RTL | Logical content mirrors once; physical window controls remain physical-left |
| Font scaling | First-party QML type and containing geometry follow `Qt.application.font`; no literal type or box sizing may defeat the user's setting |
| Main-loop work | No process wait or multi-command status collection on GTK's UI thread |

## Surface disposition

### Boot splash and Plasma splash

**Baseline:** Plymouth identity, palette relationship and the transition into the
desktop were already gated. This pass did not change the boot splash.

**Defect fixed:** the Plasma splash guarded infinite motion, but still started
every finite intro/outro when animations were disabled. Merely setting an
animation duration to zero was not enough: entrance-controlled objects could
remain transparent or scaled down.

**Decision:** `showStaticFrame()` now stops the intro, ring, shine, particles and
typewriter, then explicitly places the logo, orbital ring and full wordmark at
their resting values. Stage 5 also skips the animated hand-off. The same source
is generated across all 16 look-and-feel packages.

**Why:** reduced motion is a complete visual state, not only a ban on infinite
loops. The static state must remain branded and legible.

**Final decision:** the eight-loop composition was removed. The shipping source
uses one calm identity reveal and one honest progress treatment, with a complete
static reduced-motion frame. This preserves presence without turning boot into
a visual-effects reel.

**Open proof:** the generated QML relationship is tested; the current branch has
not been booted through Plymouth and the Plasma splash.

### System login

The active login implementation is Plasma Login Manager, not the retired SDDM
configuration. Its current MoOS wallpaper, Arabic-capable type, logo seating and
palette relationship were reviewed against the existing image-experience gates.
No new source defect was reproduced in this pass, so no speculative redesign was
made.

**Open proof:** a booted capture of the current worktree at 16:9, 16:10 and 21:9
is still required. Existing screenshots prove the previous shipped revision, not
this branch.

### Lock screen

**Defect fixed:** Unlock used literal white over an `accentA → accentB` gradient.
The unpaired endpoint reached **1.77:1**, and seven themes fell below 3:1.

**Decision:** use the flat Selection background (`accentA`) and its exact KDE
Selection foreground (`highlightedTextColor`). `accentB` remains only in the
focus rim. A 0.94 pressed scale preserves tactile acknowledgement without
reintroducing an unsafe fill.

**Measured floor across 16 schemes:** **4.516:1** (MoOSUI2 Nova).

**Why:** KDE defines a foreground/background relationship for Selection; it
does not define one for an arbitrary generated gradient endpoint.

### Logout and power actions

**Defect fixed:** highlighted actions used the same unpaired two-colour fill, and
destructive actions placed Selection foreground on the negative colour. The
destructive pairing reached **2.78:1** in a light scheme.

**Decision:** normal filled actions use Selection ink on flat `accentA`;
destructive actions use the Complementary background on
`ForegroundNegative`. `accentB` is rim-only.

**Measured floors across 16 schemes:** normal/selected **4.516:1**; destructive
**4.857:1**.

**Language resolution:** Logout now follows the active session locale only,
with logical alignment and no duplicated translation. Login, lock and logout
therefore share one session-language contract.

### Desktop, wallpaper and windows

The wallpaper/dashboard, persistent window material, Aurorae chrome and theme
previews were audited against the current generated-source and motion gates. No
new defect was reproduced in these surfaces. The existing material decision is
retained:

- persistent application/titlebar surfaces are solid;
- transient shell surfaces may use controlled Liquid Glass;
- blur strength remains capped at 15; and
- dashboard/wallpaper motion remains conditional on visibility and the system
  motion setting.

This pass deliberately did not add more blur, animation or decorative layers.
The desktop still needs a quiet-session performance measurement after the new
image is booted; the prior approximately 9% `plasmashell` reading was taken
during active development and remains unattributed.

### Launcher

**Defect fixed:** physical left/right anchors were selected from an RTL ternary
inside a tree Plasma already mirrors. The navigation state marker and pin
affordance therefore moved in the wrong direction.

**Decision:** express logical source order once (`left` for leading, `right` for
trailing) and let inherited `LayoutMirroring` perform the one RTL transform.

**Why:** component-local direction and shell direction must not both mirror the
same physical geometry.

**Baseline finding:** the prior live 1920 × 1080 evidence at
`test-results/live-polish-20260719/bar-v20/after-search-launcher.png` remains a
useful record of the rejected design. It showed four competing
regions—header, search, category rail and a four-column app grid—compressed into
one small surface. Functional labels are sized from
`gridUnit * 0.41 … 0.58`, approximately **7–10 px** at the captured scale, and
the result reads like a dense inherited desktop menu rather than the calmer
MoOS composition.

**Final implementation:** a **720 × 590** three-column orbital composition with
24 px outer gutters, minimum-target cells, a quiet header/search relationship,
one clear navigation hierarchy, system font metrics and Tidal Cut symbols.
Category, navigation, pin and session glyphs are owned MoOS assets rather than
inherited KDE chrome. Collapse/expand uses one 120 ms cadence and becomes static
under reduced motion.

### Dock, panel and widgets

The panel clock repeated the same double-mirroring error in its compact and
expanded `RowLayout`s. The explicit RTL direction was removed so the shell owns
the transform once. Existing width/minimum-width, date-digit and collision gates
remain in force.

The dock, brand button, Hero Clock and wallpaper dashboard otherwise keep the
current generated geometry. No new visual defect was reproduced, and no
unnecessary widget-specific fork was added.

The dock launcher label now consumes system font metrics with an 11 pt
functional floor, retaining truncation/tooltip handling. It no longer pins a
local face or falls to approximately 7 px.

### Notifications, dialogs and context menus

Native shell seams—`background`, `translucentbackground`, `tooltip`,
`viewitem`, `menubaritem`, `button` and dialog assets—are generated as one
Plasma style, so
native notifications, tooltips, context menus and system dialogs share the same
surface/outline/selection DNA in source. Older live captures are useful
baseline evidence only; this branch is unbooted, so notification stacking,
menu placement, blur and focus containment still require current-image captures
in both directions and modes.

Custom application dialogs consume the shared QML token/action/focus layer.
Mo AI's named dialog roles, claimed focus, Escape, visible Close action and
keyboard/assistive activation agree with Welcome, Installer and Store on
radius, spacing and button hierarchy.

### Settings and first-party GTK windows

Plasma System Settings remains a native upstream control surface wearing the
active MoOS colour, widget, icon and cursor layers. The dedicated MoOS Themes
picker owns the curated 16-theme choice and its existing keyboard/readback gates;
this pass did not fork System Settings or add a competing settings shell. That
is the correct consistency boundary: MoOS owns identity and semantic styling,
while familiar system configuration keeps its stable information architecture.

The Theme Picker now resolves headings, actions, wallpaper-motion choices and
accessible copy from the active locale. It displays two languages only where a
language choice itself requires it.

**Defect fixed:** `moos_ui2.py` selected one hard-coded Graphite or Tidal palette
from a dark-mode boolean. Fourteen of the 16 theme choices therefore left
Recovery, Updater and other shared GTK windows in the wrong accent family.
Suggested and destructive buttons also reused foregrounds on unsafe fills.

**Decision:** parse the active KDE `ColorScheme` from `kdeglobals`, resolve its
`.colors` file through XDG data roots, map KColorScheme roles to one semantic GTK
palette, and fall back safely when a custom scheme is incomplete or inaccessible.
A directory monitor catches atomic `kdeglobals` replacement; notifications are
debounced for **75 ms**. Suggested actions use flat Selection background, and
destructive actions use a separately measured `on_negative` role.

**Measured minima across all 16 schemes:**

| GTK relationship | Worst ratio |
|---|---:|
| text / canvas | **9.976:1** |
| text / card | **10.282:1** |
| muted / canvas | **5.492:1** |
| positive / canvas | **4.650:1** |
| warning / canvas | **4.892:1** |
| negative / canvas | **4.857:1** |
| on-accent / primary | **4.516:1** |
| on-negative / negative | **4.857:1** |
| outline / card | **3.008:1** |

Twenty simulated file-change notifications collapse into one CSS reload. Both
atomic rewrite and malformed-scheme fallback are exercised by the runtime test.

### Mo Store

The Store retains its previously completed RTL reading-start, keyboard scrolling,
focus-ring, font-scale and transaction-state work. This pass removes its private
data-URL glyph dictionary and resolves all category/action/status glyphs through
the generated Tidal Cut catalogue. Unknown catalogue values safely resolve to
the owned Spark symbol rather than generating executable SVG data. Every finite
Store transition collapses when motion is disabled.

**Why:** the same action must not acquire a different line weight or silhouette
in adjacent MoOS windows, and reduced motion applies to hover/sheet transitions
as well as endless animation.

### Mo AI

Four launch-readiness defects were fixed:

1. **Pointer-only custom controls.** Rail items, starter cards, picker rows,
   settings tabs/cards and Save now use one `ActionArea` contract: Tab focus,
   visible 2 px focus ring, Enter/Return/Space, button/radio roles, name and
   checked state. The two sheets are named dialogs, claim focus when opened,
   close on Escape, and retain visible Close buttons.
2. **Fixed ambient rasters.** Cyan/violet glow PNGs were replaced by
   palette-driven `Shape` radial gradients. All theme members now use their
   active accent pair, and two decorative raster decodes are removed per launch.
3. **Motion bypasses.** More than 30 finite motion declarations now derive their
   duration from `root.motionEnabled`; the test rejects any literal duration.
   Endless ambient motion was removed.
4. **Icon drift.** All Mo AI actions, navigation and status glyphs use the
   generated Tidal Cut resolver, including Repair and safe fallback handling.

Six raw `MouseArea`s remain by design: the internal pointer delegate of each
shared control and modal backdrop/click-swallow regions that are not standalone
actions. A regression count prevents a seventh pointer-only action from
appearing silently.

**Language/density resolution:** the 133 bilingual entries now resolve one
active locale. Functional typography uses the shared floor instead of
compressing two hierarchies into 9–11 pt.

**Performance resolution:** the six ambient loops and fixed glow rasters were
removed. The final ambient field is static and palette-native; finite
interaction transitions pause when inactive and collapse under reduced motion.
The old **12.95% of one core / 20 s** sample remains the rejected baseline, not
a number attributed to the new source. A booted quiet sample remains required.

### Installer

**Contrast defect:** fixed coral and amber were acceptable in dark themes but
measured only **2.25–2.56:1** and **1.32–1.49:1** respectively on light themes.

**Decision:** use `negativeTextColor` and `neutralTextColor`, with at most a 5%
self-tint behind semantic ink. The tight measured cases are:

- negative raw: **4.785:1**;
- neutral raw: **4.892:1**;
- negative on 5% tint: **4.538:1**; and
- neutral on 5% tint: **4.574:1**.

The erase hold surface now uses a 4 logical px progress track rather than filling
the text background. The deliberate press-and-hold remains **1600 ms** and is not
shortened by reduced-motion handling.

**Keyboard and accessibility:** disk choice is a named/checked/disabled radio;
its spoken name includes kind, model, size, contents/OS and too-small state.
Disk choice, footer Next and hold-to-erase expose focus, roles, names, assistive-
technology press actions and keyboard activation. Hold uses shared press/release
helpers for pointer, Space, Return and Enter, ignores auto-repeat, and offers no
single-press bypass.

**Target geometry:** disk card 96 high; destructive hold 56 high; primary footer
46 high, all through the font-scale helper.

**Motion resolution:** animated stagger arithmetic is parenthesised inside the
enabled branch and the disabled branch is unconditionally zero. The motion gate
checks both states.

### Welcome

Device actions, pairing-popup Close, live-session Install and footer Next/Install
now have a complete keyboard and accessibility contract: visible focus, role,
label, AT action, Return and Space. Default actions announce their default state;
disabled and live-handoff state lives on the item, not only the tap handler.

Target heights are 44 for device actions, 50 for live Install and 46 for footer
actions. The isolated popup Close action now meets the 40 × 40 contract. All
sizes scale with the shared font helper, and Welcome consumes the same Tidal Cut
resolver as Installer and Store.

**Motion resolution:** the ring stagger is parenthesised in the enabled branch;
disabled duration is always zero and covered by the shared motion relationship
gate.

### Recovery

Two trust defects were fixed:

- when a rollback was already queued, the button said Cancel while the
  confirmation and success copy still said that a rollback would be started;
- `subprocess.run(..., timeout=180)` executed from the confirmation callback,
  freezing the rescue window while Polkit and `bootc` ran.

The queued state is now captured at confirmation and drives confirmation,
progress, success/failure and next-boot copy consistently. The operation uses
`Popen` plus a GLib IO watch to stream output. Early stdout close is handled by
a low-duty **50 ms** poll without calling `wait()` on the main loop. A spinner
communicates progress and the fixed allowlisted command remains unchanged.

Tests cover staged, ordinary, multiple, queued, single and same-version
deployments plus command failure, missing command, timeout, malformed JSON and
missing-booted cases. A controlled fake process proves the helper returns before
poll/wait, streams output, handles early EOF and completes through GLib.

### Mo PC Remote

**Performance defect:** the three-second status refresh could execute as many as
seven commands serially on GTK's main loop, each with a five-second timeout.
One slow service could therefore freeze hover, click and paint for tens of
seconds.

**Decision:** collect a snapshot on one daemon worker, marshal the immutable
result with `GLib.idle_add`, and coalesce bursts into one trailing refresh.
QR filenames are keyed by the URL so stale codes are not reused. The panel also
uses the shared live 16-palette GTK controller.

The runtime test requires a refresh request to return in under **50 ms**. Twenty-
five overlapping requests produce only the current run plus one trailing run,
and all UI delivery is verified on the main thread. The apply path is statically
checked to contain no process, file or network collection.

### MoPlayer

MoPlayer was completed in its canonical repository,
`/var/home/moos/MoPlayerMoOS`, committed as `23799ad`, pushed to canonical
`main`, and vendored into this image with `just sync-moplayer`. The vendored
tree is therefore generated from a clean, reviewable source revision.

The final application provides:

- one `FramelessWindowFrame` for both login/source setup and the catalogue;
- caption, compositor drag and eight resize edges on the login route;
- three palette-native Tidal Cut window controls fixed to a physical-left
  **128 px** strip in LTR and RTL, inside **40 × 40** targets;
- keyboard/semantics-complete source-method tabs, including direction-aware
  adjacent arrows and Enter activation;
- `AccessibleVisibility`, which removes hidden player chrome from pointer,
  focus and semantics trees together;
- an `onEmber` token for the full three-stop primary gradient: literal white
  measured **1.78:1 / 2.36:1 / 3.45:1**, while `#070809` measures
  **11.79:1 / 8.91:1 / 6.08:1**;
- reduced-motion routing through the existing `Motion` abstraction at the seven
  audited login/live/player transition sites; transforms disappear while a
  60 ms opacity affordance remains;
- the localized application tagline instead of a hard-coded English byline; and
- localized semantics and **40 × 40** targets for player tuning and track
  choices.

The rejected traffic-light metaphor is gone. Neutral controls inherit the
active palette; negative colour appears only for the close action's explicit
interactive state. The zero-TTL comparison was made deterministic and the full
canonical gate is green: `flutter analyze` reports no issues and all
**176/176** Flutter tests pass.

## Symbolic icon system: accepted Tidal Cut implementation

### Architecture

Application launch icons remain full-colour identity plates. Interface chrome
uses one owned layer:

`/usr/share/icons/hicolor/scalable/actions/moos-*-symbolic.svg`

`artwork/generate_moos_symbolic_icons.py` emits **69** symbols
deterministically. The image path installs them through hicolor and both
MoOSUI2 light/dark theme overlays. Welcome, Installer, Store, Mo AI and the
Launcher resolve the same names through the generated `SymbolCatalog.js`;
private data-URL libraries and legacy unsuffixed action names are removed.

The first monoline checkpoint was rejected because its geometry was generic,
Database clipped, Settings/Sun converged at 16 px and GTK masks destroyed
counters. Tidal Cut is a full-family replacement, not a patch: compound filled
paths retain their holes under GTK symbolic masking while `ColorScheme-*`
classes retain KDE semantic palette substitution.

### Geometry and colour contract

- 24 × 24 viewBox with calm filled mass and shared corner construction;
- nominal geometry within 2.5…21.5, leaving optical air at 16 px;
- no background plate, shadow, raster, gradient, filter or image;
- meaning remains clear in one colour;
- normal foreground uses `ColorScheme-Text`;
- an active detail may use `ColorScheme-Highlight`;
- warning uses `ColorScheme-NeutralText`; and
- KDE/Kirigami substitutes live theme roles at render time.

The family remains symbolic rather than 69 miniature illustrations. Consistency
comes from optical bounds, filled weight, corner geometry and the recognisable
cut counterform—not from attaching the logo to every action.

### Evidence

`artwork/moos-ui2/previews/moos-symbolic-icons.png` is a **1442 × 852** paired
light/dark sheet derived from the canonical 69-name manifest at 24 and 16 px.
`artwork/moos-ui2/previews/moos-symbolic-icons-runtime.png` is a
**2520 × 923** KIconLoader capture from the active palette. The harness and
sheets no longer maintain a private icon list.

The gates verify exact generator output, XML, dimensions, semantic roles,
fixed-paint absence, manifest/output equality, clipping, counters, non-empty
raster output, state distinction, palette recolouring, theme lookup and
resolution of every first-party QML `moos-*` reference. GTK resolver,
KDE `kiconfinder` and librsvg 16/20/24/64/128 px paths are all exercised.

**Negative proof:** replacing generated semantic paint with a fixed colour made
the deterministic gate fail with status 1; regeneration restored the canonical
source and returned the suite to green.

## RTL, type, focus and assistive technology

- Arabic and English QML launch probes are separate; Arabic runs with RTL locale
  environment rather than a source-text assumption.
- Shell components inherit mirroring once. Physical window chrome is explicitly
  outside language direction where spatial memory matters.
- First-party surfaces show one active locale; duplicate bilingual visible copy
  is a defect, not an RTL solution. Accessible names use that same language.
- Each Tab stop in first-party QML must have an accessible name and one visible
  shared `FocusRing`; a role without a label is not accepted.
- Custom action rectangles expose keyboard and AT activation. Destructive hold
  semantics preserve the safety duration.
- First-party QML type sizes and their containers share the `fs()` scale derived
  from the application font, with an 11 pt functional floor.
- Hidden Flutter player controls leave paint, hit-test, focus and semantics trees
  together.

## Motion and performance decisions

The design contract distinguishes three classes:

1. **ambient/infinite:** requires visibility/state and motion gates, and pauses
   when an inactive window can do so;
2. **finite spatial:** collapses to zero when reduced motion is requested; and
3. **essential feedback:** may retain a very short opacity change, never a lift,
   slide or orbit.

Performance changes are bounded and observable:

- Mo AI stops decoding two fixed ambient glow rasters and removes its six-loop
  ambient scene in favour of a static theme-native field;
- Mo PC Remote removes status I/O from the GTK loop and coalesces refreshes;
- Recovery removes the privileged operation from the GTK loop;
- GTK style bursts coalesce behind a 75 ms debounce; and
- no new service, renderer, shader framework or polling loop was introduced.

No exact CPU or GPU saving is claimed until measured on the booted image.
Structural main-loop, loop-removal and request-count results are claimed because
they are exercised directly. The existing Mo AI 20-second sample—12.95% of one
core while active—is the rejected baseline, not a claimed final measurement.

## Verification ledger

### Passed for the final source candidate

- baseline CI-equivalent repository gates before editing;
- final image-repository `just check`: **exit 0** after all combined edits;
- `tests/test_moos_symbolic_icons.py`: **6/6**;
- `tests/test_moos_symbolic_runtime.py`: **5/5**, including GTK, KDE and
  librsvg 16/20/24/64/128 px paths;
- `tests/test_moos_app_icons.py`: **3/3**;
- `tests/test_moos_app_visual_polish.py`: **5/5**;
- `tests/test_moos_gtk_runtime.py`: **6/6**;
- `tests/test_moos_visual_system.py`: **13/13**;
- `tests/test_moos_motion_gate.py`: **3/3**;
- `tests/test_recovery_rollback_target.py`: pass;
- `tests/test_moos_ui2.py`: **21/21**;
- `tests/verify_user_experience.py`: **10/10**;
- QML load probes for Welcome and Installer in English and Arabic RTL: all
  remained alive to the expected 8-second timeout, with no QML error output;
- lock/logout QML/runtime smoke: pass, with all 16 generated copies matching;
- build/launcher shell syntax, Python syntax and `git diff --check`: pass; and
- the icon fixed-paint mutation was observed failing before restoration; and
- canonical MoPlayer `just check`: analyze clean and **176/176** tests green.

### Local image evidence

- full generic `just build`: **exit 0** from this exact source candidate;
- produced `localhost/moos:latest` at
  `5e64dbf3373a88f3812a1d7f8a63b4d6a8d2b776cc692414fea8075220c23454`;
- MoRemote mapping/Unicode suite: **21/21** inside its build stage;
- MoPlayer release bundle built and passed its in-image binary, ICU, asset,
  desktop-entry, shared-library and application-ID checks;
- all four first-party QML applications remained alive through the real
  offscreen shell smoke; Launcher emitted
  `MOOS_LAUNCHER_FULL_READY size=720x590`; the desktop scene smoke passed;
- final initramfs: **122 MB**, `lsinitrd` exit 0, with
  `ostree-prepare-root`, the MoOS Plymouth script/renderer and all required
  MoOS splash assets;
- `verify_identity.py`, `verify_image_experience.py`,
  `verify_store_catalog.py` and `verify_no_foreign_identity.py`: pass; and
- `bootc container lint`: 9 checks passed, 1 skipped, 4 known non-blocking
  content/sysusers warnings, exit 0.

### Release evidence still pending

- CI signed publication of the resulting main revision;
- update staging and first boot on the installed machine; and
- booted surface capture/quiet-performance measurement. These are not source
  failures and are not claimed before they happen.

### Adversarial fixtures versus mutation proof

Recovery process/deployment cases, contrast matrices, RTL widgets and semantic
trees are executable adversarial fixtures. The icon determinism gate was also
source-mutation tested. The Installer/Welcome accessibility and contrast gates
were **not** source-mutation tested in this pass; they were exercised through
their positive/negative fixture matrices. This distinction is intentional and
kept explicit.

## Honest limitations and open release gates

- The generic local image is proven; no local NVIDIA or cloud result is
  claimed. Their matrix builds must pass in CI before daily-driver adoption.
- The branch has not been committed or pushed, and no CI result exists for it.
- The installed machine has not booted these changes.
- Plymouth, login, lock, logout, desktop, launcher, dock and widget changes have
  not been captured from a booted image.
- The 1442 × 852 paired sheet and 2520 × 923 live-Wayland KIconLoader sheet
  cover the complete 69-glyph manifest. Installed theme precedence still
  requires the image gate.
- QML timeout probes prove loading, not final pixel composition.
- The current pass did not perform new 16:10/21:9, multi-monitor, touch, real
  screen-reader or colour-vision simulation sessions.
- A quiet-session `plasmashell` CPU baseline remains required.
- Real-hardware audio, Bluetooth, Wi-Fi, suspend and multi-monitor coverage is
  unchanged from `PROJECT_STATE.md`.
- MoPlayer is committed/pushed at canonical revision `23799ad`, vendored and
  built into the successful local generic image; booted execution is still
  pending.

## Release-closing checklist

- [x] Redesign and review the complete 69-symbol family as one original MoOS
      language; preserve MoOS and Mo AI logo silhouettes, derive the harness
      from the canonical manifest, fix clipping/distinction, and prove KDE/GTK
      plus 16/20/24/64/128 px raster output.
- [x] Introduce a minimal shared QML token/control layer, migrate Store, Mo AI,
      Welcome and Installer to the same type/space/radius/material/button scale,
      and add conformance gates rather than another style runtime.
- [x] Redesign Launcher density to a legible three-column composition; move
      Launcher/dock labels to system font metrics and the commercial size floor.
- [x] Simplify Splash to one reveal plus one progress treatment; remove Mo AI
      ambient loops and keep finite interaction motion state-aware.
- [x] Fix and test the Welcome/Installer ternary precedence; require
      disabled durations to equal zero and enabled ring staggering to differ.
- [x] Make Logout, Theme Picker and Mo AI visible/accessible copy follow the
      active locale; keep bilingual display only in a language chooser or
      justified pre-locale support error.
- [x] Replace MoPlayer traffic-light chrome with palette-native MoOS controls.
- [x] Finish source edits and rerun the exact `build.yml` repository
      gate list from a clean command transcript.
- [x] Strengthen the icon gate with pixel bounds, holes/empty-output and
      similarity checks; render every glyph with KIconLoader and GTK4.
- [x] Strengthen the motion gate to evaluate both ternary branches at
      `motionEnabled=false/true`; lint functional type below 11 and isolated
      targets below 40; lint bilingual visible separators outside allowed
      language/support surfaces.
- [x] Resolve the canonical MoPlayer zero-TTL boundary, then rerun `just check`
      and require analyze clean plus the complete Flutter suite green.
- [x] With explicit owner authorization, commit canonical MoPlayer, then run
      `just sync-moplayer` and verify the exact vendored commit.
- [x] Build the generic local image from the final worktree. Require the NVIDIA
      CI matrix edition to pass before daily-driver adoption.
- [x] Run every in-image identity, QML, icon, initramfs and bootc gate.
- [ ] Boot a disposable VM/image and capture splash, login, lock, logout,
      desktop, launcher, dock, widgets, settings, Store, Mo AI, Welcome,
      Installer, Recovery, MoPlayer, notifications, dialogs and context menus in
      English and Arabic RTL.
- [ ] Inspect 1280 × 720 and 4K at 100%, 125%, 225% and 275%; font scale 100%
      and 150%; dark/light; 16:10 and 21:9; focus, hover, disabled and error.
- [ ] Measure a quiet desktop and inactive Mo AI/Store/Remote window after the
      new image boots.
- [x] Keep a canonical MoPlayer commit and refuse dirty-source vendoring; record
      the exact clean revision in this closeout.
- [ ] Only after signed publication and reboot, run `tests/post-update-check.sh`
      before describing the revision as shipped.

Current handoff: **the unified implementation, repository/canonical application
gates and full generic local image are green. The remaining work is release
execution: publish/sign the matrix images, update, reboot and verify the running
machine.**
