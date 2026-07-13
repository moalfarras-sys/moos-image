# Nova Cinema — the design system

MoPlayer for MoOS has to be two things that pull in opposite directions: a
MoPlayer, and a MoOS app. This document is the record of where each one won, and
why.

## The conflict

**MoPlayer is ember on black.** `#FF7A18` on `#07070B`. The black is not a taste
decision: a video surface is the brightest thing on the screen, and any tint in
the chrome around it bleeds into the picture. Every serious player is near-black
for the same reason.

**Nova is cool navy with a cyan focus ring.** `surface-0` is `#0B1220` — a navy.
Fill a player window with it and every frame the app renders gets a blue cast.

Neither could simply win. So:

| | Winner | Why |
|---|---|---|
| Surfaces | **MoPlayer** (near-black), with Nova's hue | Nova's ladder (`0B1220 → 111A2E → 16233A → 263A5C`) pulled down to cinema levels: `07090F → 0E121C → 151B29 → 1F2739`. The blue channel still leads the red, so the greys stay *cool* — the app looks like it belongs to Nova without tinting the video. |
| Accent | **MoPlayer** (ember) | It is the brand. It is the only colour that ever means "this is MoPlayer". |
| Focus ring | **Nova** (`#4FC3FF`), verbatim | Focus is a *system* affordance. A MoOS user's eye already knows what that cyan ring means; giving it a different colour here would be a small lie about how the desktop works. |
| Text ramp | **Nova**, verbatim | `#F4F8FF / #9FB0C9 / #7F94B5`. Cool greys, and they pair with orange better than the iOS app's neutral ones did. |
| Spacing, radii, type scale | **Nova**, verbatim | 4/8/12/16/24/32 · 10/14/18/22 · IBM Plex Sans. This is the rhythm the MoOS shell and Mo AI move in; matching it is most of what "native" actually means. |
| State colours | **Nova**, verbatim | Success `#35D39A`, warning `#F4B860`, danger `#FF6B7A`. |
| `LIVE` badge | **Neither** — `#FF3B30` | Deliberately *not* the danger colour. An on-air badge is not an error, and on a wall of channel tiles the two must not be confusable. |

## The Nova gradient appears exactly once

`#22D3EE → #2E7BFF → #8B5CF6` is MoOS's identity, and it is used **only** on
surfaces that speak for the system rather than for the app: the MoOS badges in
Settings. Using it as a second accent would leave the interface with two
identities and no hierarchy. Ember leads; Nova signs.

## Type

IBM Plex Sans is the interface face, with **IBM Plex Sans Arabic** first in the
fallback chain. Both are already in the MoOS image, so nothing is bundled — and
an Arabic title and its English subtitle sit on the same metric instead of one of
them silently dropping to DejaVu.

Timecodes are the exception: they are set in a mono face with tabular figures,
because a proportional running clock jitters on every digit change.

## Motion

Nova is calm. 120 ms / 220 ms / 420 ms, eased, never bouncy. A card lifts under
the cursor; nothing bounces, nothing springs. All of it is behind the *cinematic
motion* setting, because the hover zoom is the first thing to cost frames on the
integrated GPU a MoOS laptop is likely to have.

## Glass is for chrome, not for content

Nova asks for translucent panels with a 1 px inner border and a soft shadow — and
one hard rule: *no text on a variable background without an opaque-enough surface
beneath it*. Here the "variable background" is worse than a wallpaper; it is a
moving video frame.

So: the fill is a real colour at real opacity, and the blur is decoration on top
of it. Turn the blur off and the panel is still legible. And glass is used only
where something floats **over video** — the player overlay, the mini bar. Cards
in a scrolling grid are solid, because every `BackdropFilter` is a save-layer and
forty of them in a poster wall is how you drop frames.

## Desktop, not a big phone

- Hover is a first-class state. At rest a poster is artwork and a title; the play
  button, the favourite heart and the rating appear when the pointer arrives.
  That is what keeps a wall of forty of them readable.
- No ink splashes. They are a touch idiom; on a mouse they lag the cursor and
  look broken. `NoSplash.splashFactory`, hover instead.
- Rails have arrows. A mouse wheel scrolls vertically; a horizontal rail with no
  arrows is a rail most users cannot move.
- Everything is reachable from the keyboard, and the player is fully drivable
  without touching the mouse.

## RTL is not a translation

The whole tree flips for Arabic: the nav rail, the rails, the seek bar, the
chevrons. Every offset in this codebase is `EdgeInsetsDirectional` / `start` /
`end` — never `left` / `right`. The rail arrows swap their glyphs, because "back"
in Arabic is on the right.

Two things do *not* flip: the timecode (a clock reads left-to-right in every
language) and the `by Moalfarras` signature, which is part of the logo.
