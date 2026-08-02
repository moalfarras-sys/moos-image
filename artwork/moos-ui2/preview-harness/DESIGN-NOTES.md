# MoOS Session Surfaces — redesign 2026-08-02 (working notes)

Direction: keep the Liquid Glass / Tidal identity, but give every session
surface a REAL center of mass — the **Glass Island** — instead of controls
floating on an empty field.

## Verdict on the shipped portal (before-restart-scholar-light.png)
- island is a barely-visible flat sheet: no material depth, no rim, no shadow
- the Tidal arc cuts THROUGH the island → reads as a stray line, not a frame
- naked hairline countdown + floating number
- one small action key + smaller Cancel → tiny interactive footprint at 1080p
- clock floats unanchored; no date; brand emblem renders as a faint blur

## New composition (Logout/Restart/Shutdown; same language later for Lock+Login)
1. Backdrop: theme wallpaper, FastBlur 54 (kept) + existing tri-stop scrim.
2. TidalHorizon: BEHIND the island, lower intensity, geometry framed so the
   crest passes ABOVE the island and the horizon line BELOW it — never through.
3. GlassIsland (new component): tinted surface (bg 0.60), vertical sheen,
   1px neutral border + accent top-rim, soft wide shadow (gate-safe method),
   radius 28. Width ~560 focused / ~760 picker.
4. Content stack inside the island:
   - header: small emblem + clock (Thin 84, accent colon) + full date line
   - title 26 DemiBold (bilingual as today) + user chip (avatar ring + name)
   - action dock: tiles 104×96 r24, icon 30, label 13; grid ≤4 cols
   - primary tile wears CountdownRing (replaces hairline+number)
   - armed danger: negative-gradient fill + "press again" hint line
   - foot: hairline, full-width quiet Cancel (44px)
5. Motion (all zero when longDuration <= 1): backdrop 320 → island 260
   (y+12, scale .97→1) → tiles stagger 40. Countdown ring sweep Behavior 250.
6. Contracts preserved byte-for-byte in behavior: signals, armOrFire,
   moveFocus arrows + RTL mirroring, Escape, Accessible role/name/pressed/
   onPressAction, focusInitialAction, remainingTime countdown semantics.
