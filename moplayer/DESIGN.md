# MoPlayer Horizon — the design system

MoPlayer is two things that pull in opposite directions: a cinema surface, and a
MoOS app. **Horizon** (2026-09-30) is the version that stopped choosing between
them. It replaced *Glass Orange Cinema*; the reasons are below, and most of them
were measured on the owner's station rather than argued.

## What changed, and why

| | Glass Orange Cinema (was) | Horizon (is) |
|---|---|---|
| Accent | The brand ember, always | **The desktop's MoOS palette** (`kdeglobals`), live; ember as a Settings choice |
| Navigation | A floating glass dock, bottom-centre | A **rail** on the start edge; the source switcher at its foot |
| Frame | Caption bar over the page | Caption + rail are one frame; the page is an **inset panel** with a rounded leading corner |
| Live TV | Clicking a channel took over the window | Channels play on the page's own **stage**; full screen is a second click |
| Home | One hero | A **spotlight** of up to six slides, advancing on a timer |
| Material | Blur, film grain, gradient shaders | Solid fills, hairlines, **baked** gradients, no blur by default |

1. **The accent is the system's.** The owner switches MoOS between Graphite,
   Amethyst, Aurora and the rest; an app that ignores the switch looks
   installed rather than built in. `lib/core/theme/palette.dart` reads the
   explicit `[General] AccentColor` (or the scheme's selection colour), lifts
   each stop of the gradient **by luminance** until dark ink reads on it at
   4.5:1 whatever the hue (`test/palette_test.dart` pins nine awkward hues),
   and tints the near-black canvas a quarter-strength toward the palette's
   window colour. It watches `kdeglobals` and recolours while running. The
   surfaces stay near-neutral on purpose: chrome with a strong hue casts it
   onto the picture beside it.
2. **The rail, because MoOS already has a dock.** A maximised MoPlayer stacked
   its floating dock directly above the MoOS Bar — two capsules, both claiming
   to be where you go next. A rail costs no height, nothing scrolls under it,
   and it is where desktop media apps keep their destinations.
3. **The stage, because watching should not cost the list.** The owner's
   subscription allows one connection; a guide that has to tune a channel to
   show what is on it knocks the current channel off. Hovering previews the
   guide, clicking plays on the stage, clicking the playing channel (or Enter,
   or a double-click on the picture) goes full screen.

## The palette

Defined once, in `lib/core/theme/app_colors.dart`, from the active `Palette`.
Nothing in the app writes a `Color(0x…)` literal for a role that file names.

| Role | Value |
|---|---|
| Canvas / surfaces 1–3 | Ink `#0A0C11` mixed 22% toward the palette's window colour, then 3.5% / 6.5% / 11% toward white |
| Accent, bright, deep | From the palette, lifted to luminance ≥ 0.26 / 0.40 / 0.20 |
| On accent | Dark ink or white — whichever measures higher at every stop |
| Text | `#F3F5F9` / `#B4BBC8` / `#8A93A3` |
| Borders | White at 8% / 16% |
| On air | `#FF3B4E` — neither the danger colour nor the accent |
| Brand (logo, ember palette) | `#FF4400` core, `#FF8A1F` crown — measured off the mark |

## The renderer's rules — read these before you draw anything

MoPlayer runs on Impeller (OpenGL ES) inside GTK3. Three facts about that stack
were measured on the RTX 2080 SUPER at 4K on 2026-09-30, and each one is a rule:

- **Never draw a `Gradient` as a shader.** One window-sized `LinearGradient` in a
  `BoxDecoration` took the process from 360 MB of graphics memory to 1.2 GB; the
  old ambient scene's three stacked gradients cost 2.2 GB; forty poster-sized
  ones cost 0.9 GB. The driver keeps what the renderer once asked for, so an
  idle MoPlayer held **4.9 GB of an 8 GB card** and the desktop slowed down
  around it. The same gradient pre-rendered into a 96×96 image and drawn
  stretched measured at the baseline. Use `GradientFill` /
  `BakedGradients.paint` (`lib/core/theme/baked_gradient.dart`); never a
  `gradient:` in a decoration, a `Paint.shader`, or a `ShaderMask`.
- **No offscreen layers over large areas.** A window-sized `BackdropFilter` or
  `Opacity` measured ~400 MB each (4× MSAA colour and depth at the GTK surface
  size). Glass panels take `blur: 0` by default; the fill is what makes them
  legible. Cross-fades use an image's own `opacity:` or a text colour's alpha,
  never an `Opacity` or `FadeTransition` around a big subtree.
- **Every frame costs the main thread.** GTK3 uploads the window's cairo surface
  under Flutter's RGBA frame on each frame it presents (`gdkgl.c`,
  `gdk_cairo_draw_from_gl`), 4608×2427 pixels at this station's scale. A
  vsync-driven spinner therefore held the main thread at ~65% of a core while a
  playlist downloaded. Busy indicators are `CalmSpinner` (10 fps), skeletons
  breathe at 8 fps, and nothing animates forever. The GTK runner also stops GTK
  painting the window background while the window is maximised — that fill was
  half the main thread's time during playback.

After these, MoPlayer idles at ~0.6 GB of graphics memory (from 4.9 GB) and
plays 1080p at ~1.7 GB including the decoder.

## Surfaces

- **Frame** (caption + rail): `surface1`, one colour.
- **Panel** (the page): the ambient scene — a baked vertical wash, a baked
  accent bloom high on the trailing side and a baked vignette.
- **Cards**: solid `surface2`, hairline border, lift and accent ring on focus.
- **Glass** (player controls, dialogs, toasts): a fill at real opacity and a
  hairline; blur only where a panel floats over moving video and asks for it.

## Scale is not a suggestion

The maintainer's 4K panel runs at **275%**. Flutter reports that display as
`1396x785 @3.0x`, and the obvious `size / devicePixelRatio` yields a *465x261*
desktop — which is how MoPlayer once opened as a 428x240 window, laid out for a
screen that does not exist.

Window geometry is therefore read from `screen_retriever`, which answers in the
same coordinate space `window_manager` sizes windows in. Flutter's own `Display`
is not usable for this. Layout, meanwhile, is derived from `MediaQuery` and
`LayoutBuilder` — never from a hard-coded column count.

## Type

IBM Plex Sans, with **IBM Plex Sans Arabic** first in the fallback chain. Both are
already in the MoOS image, so nothing is bundled and nothing is fetched at
runtime — and an Arabic title and its English subtitle sit on the same metric
instead of one of them silently dropping to DejaVu.

Timecodes are the exception: a mono face with tabular figures, because a
proportional running clock jitters on every digit change.

## Motion

Calm, short, eased. `hover 150 · press 100 · panel 280 · page 320 · hero 550`.
A card lifts under the cursor; nothing bounces, nothing springs, nothing pulses
forever. The spotlight advances on a nine-second *timer* — one short transition
per slide, not a ticker — and pauses under the pointer.

All of it answers to **two** off switches, and both must be obeyed: the system's
(`MediaQuery.disableAnimations`, which is what a MoOS user's "Reduce animations"
toggle actually sets) and the app's own *cinematic motion* setting — because the
hover zoom on a wall of forty posters is the first thing to cost frames on a weak
GPU, and a user who wants a smooth scroll more than a lifting card should not have
to turn off the whole desktop's animations to get one. See `Motion.isReduced`.

Reduced motion makes transforms *instant*; it does not delete the 60 ms opacity
fade. Content that teleports is a worse experience than the one being avoided.
Route fades, Login tabs, Live selection and all Player control/option transitions
go through `Motion`; the options panel loses its 12% slide and the Live marker
loses its height animation when motion is reduced.

Decorative motion is never allowed to own a permanent ticker. The weather glyph
and the live indicator are static on purpose: an infinite animation on the home
screen keeps the whole Flutter scene repainting even when the user is only
reading it. The brand should feel alive when the user acts, not consume a core
while nothing happens.

## The player is a control deck, not a row of icons

The video owns the canvas; controls live on three readable glass islands rather
than one opaque bar across the picture:

- the centre deck carries previous, back 10 seconds, play/pause, forward 10
  seconds and next;
- the bottom deck carries seek, time, volume, tuning/options and fullscreen;
- the options deck slides from the trailing edge and owns aspect mode, playback
  speed, audio tracks and subtitle tracks.

Every operation has both an icon and a tooltip, every track choice shows its
current state, and the layout mirrors directionally in Arabic. Buffering and
bounded reconnection are first-class states over the picture. If automatic
recovery exhausts its attempts, the player remains alive and offers Retry; a
network failure must never collapse into a blank surface or an unhandled
exception.

## Focus is not decoration

Every interactive surface in the app is a `FocusSurface`. It exists because the
app has to be driven four ways — mouse, keyboard, D-pad/remote, touch — and the
only reliable way to get that right is to make it impossible to build a control
that handles one of them and forgets the others.

- Hover and focus are the same visual state. A remote user pointing at a card and
  a mouse user pointing at it are asking the same question.
- **Focus is never signalled by colour alone**: the ring, the lift and the bloom
  move together, so a user who cannot separate orange from grey still sees the
  card grow. (This is also why reduced motion must not remove the ring.)
- A focused card scrolls itself into view. Without that, arrowing down a grid
  walks the focus off the bottom of the screen and the app looks frozen.
- The rail is reachable from anywhere with **F6** — because a user three hundred
  posters deep must not have to arrow through all of them to reach Settings —
  and the shell holds focus from launch so Ctrl+1…5 work before anything is
  clicked.
- Login's source methods are a real keyboard tab list: Enter/Space activate,
  physical left/right arrows move to the visually adjacent choice in both
  directions, and selection/focus are exposed to assistive technology.
- An opacity-zero control is not merely invisible. Player chrome also leaves the
  pointer, focus and semantics trees through `AccessibleVisibility`; otherwise
  Tab and a screen reader can still enter controls the viewer cannot see.
- Player tuning steps and track choices expose their selected/action state and
  use a minimum **40 × 40** logical target.

## RTL is not a translation

The whole tree flips for Arabic: the rail, the shelves, the seek bar, the chevrons.
Every offset in this codebase is `EdgeInsetsDirectional` / `start` / `end` —
never `left` / `right`.

Two things do *not* flip: the timecode (a clock reads left-to-right in every
language) and the window buttons, which keep the physical position MoOS's own
decoration puts them in. A user does not re-learn where the close button is
because they switched the interface to Arabic.
