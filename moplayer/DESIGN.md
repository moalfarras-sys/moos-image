# Glass Orange Cinema — the design system

MoPlayer for MoOS has to be two things that pull in opposite directions: a
MoPlayer, and a MoOS app. This document is the record of where each one won, and
why.

## What changed from "Nova Cinema", and why

The first version of this system was called **Nova Cinema**, and it resolved the
conflict by giving MoOS most of the argument: cool navy-tinted greys, and Nova's
**cyan focus ring**, adopted verbatim on the grounds that focus is a *system*
affordance and a MoOS user's eye already knows what that colour means.

That was a defensible call and it is no longer the one this app makes.

| | Nova Cinema (was) | Glass Orange Cinema (is) |
|---|---|---|
| Surfaces | Cool navy-black (`#07090F`, blue channel leading) | **Warm** near-black (`#070809 → #0D0F12 → #14171B`, plus `#1A1714`) |
| Focus ring | Nova cyan `#4FC3FF` | **Ember-gold `#FFB347`** |
| Glass | Chrome only, and rare | Chrome only, and the primary material of the dock, caption and player |
| Navigation | A left rail | A **floating glass dock**, bottom-centre |
| Window | KWin's decoration | **Frameless**, with the app's own caption bar |

The reasons, in order of how much they cost to learn:

1. **Warm, because orange is the brand.** Ember on cool grey reads as a
   *warning*; ember on warm graphite reads as *light*. The accent is the one
   colour that ever means "this is MoPlayer", and the surface under it decides
   whether it looks like a brand or an alert.
2. **The focus ring is a deliberate divergence, and it is the only one.** Every
   other app in the MoOS image glows Nova cyan when focused, and MoPlayer does
   not. This app is frequently a full-screen cinema surface where the focus ring
   is the *only* chrome on top of a moving picture, and a cyan ring over a warm
   film grade reads as a defect in the video rather than as a control. That is
   worth breaking the system convention for. Nothing else is.
3. **Cool colour survives in exactly two places**, and both are the *system*
   speaking rather than the app: `novaGradient` on the MoOS badge in Settings,
   and `info` on a network state. Ember leads; Nova signs.

If you are here to "restore consistency" by putting the cyan ring back, read
point 2 again, then look at the app in fullscreen. The tension is real and it was
priced.

## The palette

Defined once, in `lib/core/theme/app_colors.dart`. Nothing in the app may write a
`Color(0x…)` literal of its own.

| Role | Value |
|---|---|
| Canvas / the player's void | `#070809` |
| Panels | `#0D0F12` |
| Cards | `#14171B` |
| Hover / selected | `#1F2329` |
| Warm surface (under glass, hero base) | `#1A1714` |
| Primary (ember) | `#FF8A1F` |
| Bright amber | `#FFB347` |
| Gold | `#D9A441` |
| Highlight gold | `#FFD27A` |
| Text | `#FFF7ED` / `#B9B1A6` / `#8A8377` |
| Focus ring | `#FFB347` |
| LIVE badge | `#FF3B30` |

The canvas is *near*-black, not black. A pure `#000000` has no shading left below
it: every panel above it has to be lighter, and the interface flattens. `#070809`
keeps one step in reserve.

The `LIVE` badge is deliberately neither the danger colour nor the brand: an
on-air badge is not an error and not a selection, and on a wall of channel tiles
all three must stay distinguishable at a glance.

## Glass is the material of chrome, and only chrome

The recipe (see `GlassPanel`): a soft dark shadow, a real blur, **a dark fill at
real opacity**, a warm hairline border, and an inner highlight on the top edge
only — because real glass catches light on the edge that faces it and nowhere
else.

Two hard rules, and the first one is load-bearing:

- **The fill is what makes text readable; the blur is decoration on top of it.**
  Nova's rule — *no text on a variable background without an opaque-enough surface
  beneath it* — is stricter here than anywhere else in MoOS, because the "variable
  background" is a moving video frame. Turn the blur off and the panel must still
  be legible.
- **Never on a card in a scrolling grid.** Every `BackdropFilter` is a save-layer,
  and forty of them in a poster wall is how you drop frames on the integrated GPU
  a MoOS laptop is likely to have. Cards are `SolidCard`. Glass is for the dock,
  the caption bar, the player's controls, the mini player, a dashboard widget, a
  dialog — the things that float *over* something.

## The dock is the signature

A floating, blurred, warm-bordered pane at the bottom centre, with exactly six
destinations: **Search · Live · Movies · Series · Favourites · Settings**.

Home is *not* one of them. The dashboard is reached by the MoPlayer logo in the
caption bar (and `Ctrl+Home`), because six destinations plus a seventh "Home" is
the layout of a website's navigation bar, and this is not a website.

The content scrolls *under* the dock and is given the dock's height as bottom
padding by the shell — so nothing is ever unreachable beneath it, and the glass
has something real to blur. That padding arrives as
`MediaQuery.paddingOf(context).bottom`; a screen that ignores it will hide its own
last row.

## The window is frameless, and it costs something

MoPlayer draws its own caption bar: the logo, the connected source, the window
buttons. A second, system-drawn title bar above it would be a duplicated header on
the one app in the image that is supposed to look like a *screen* rather than a
window.

The bill: server-side decoration provides resize borders, a drop shadow and KWin's
snapping for free, and going frameless means the app implements the first two
itself (`ResizeEdges`, `WindowCaption`). `MOPLAYER_SSD=1` hands the window back to
KWin.

**And the trap, which cost an afternoon:** on Wayland,
`gtk_window_set_decorated(FALSE)` does *nothing*. A GTK3 window with no titlebar
widget asks KWin for a server-side decoration, and KWin draws one. The way to go
frameless is to give the window an **empty titlebar widget**, which switches it to
client-side decoration — at which point KWin stands down and GTK keeps drawing the
shadow and the invisible resize border for us. See
`linux/runner/my_application.cc`. On X11 the naive call would have worked, which
is exactly why it looked correct until someone ran it.

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
forever.

All of it answers to **two** off switches, and both must be obeyed: the system's
(`MediaQuery.disableAnimations`, which is what a MoOS user's "Reduce animations"
toggle actually sets) and the app's own *cinematic motion* setting — because the
hover zoom on a wall of forty posters is the first thing to cost frames on a weak
GPU, and a user who wants a smooth scroll more than a lifting card should not have
to turn off the whole desktop's animations to get one. See `Motion.isReduced`.

Reduced motion makes transforms *instant*; it does not delete the 60 ms opacity
fade. Content that teleports is a worse experience than the one being avoided.

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
- The dock is reachable from anywhere with **F6** — because a user three hundred
  posters deep must not have to arrow through all of them to reach Settings.

## RTL is not a translation

The whole tree flips for Arabic: the dock, the rails, the seek bar, the chevrons.
Every offset in this codebase is `EdgeInsetsDirectional` / `start` / `end` —
never `left` / `right`.

Two things do *not* flip: the timecode (a clock reads left-to-right in every
language) and the window buttons, which keep the physical position MoOS's own
decoration puts them in. A user does not re-learn where the close button is
because they switched the interface to Arabic.
