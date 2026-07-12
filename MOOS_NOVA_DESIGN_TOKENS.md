# MoOS Nova design tokens

Nova uses a compact, calm scale shared by the shell and first-party apps. Values
are logical pixels and therefore follow Qt/Plasma scaling at 100–200%.

## Spacing

`space-1` 4 · `space-2` 8 · `space-3` 12 · `space-4` 16 · `space-5` 24 ·
`space-6` 32. Dense shell controls use 4/8; cards use 12/16; sections use 24/32.

## Radius

`radius-control` 10 · `radius-card` 14 · `radius-panel` 18 ·
`radius-overlay` 22. A nested surface uses a smaller radius than its parent.

## Type

IBM Plex Sans is the interface face and JetBrains Mono the code face.
`type-caption` 10–11 · `type-body` 13–14 · `type-control` 14–15 ·
`type-title` 19–22 · `type-display` 28–32. Dates and metadata use caption size
and 66–72% opacity; interactive labels never use display size.

## Surfaces and text

- `surface-0` `#0B1220`: canvas.
- `surface-1` `#111A2E`: primary surface.
- `surface-2` `#16233A`: raised control.
- `surface-3` `#263A5C`: hover/selected surface.
- `border-subtle` `#263852`; `border-focus` `#4FC3FF`.
- `text-primary` `#F4F8FF`; `text-secondary` `#9FB0C9`;
  `text-muted` `#7F94B5`.

## Accent and state

Nova's identity gradient runs `#22D3EE → #2E7BFF → #8B5CF6`.
Success `#35D39A`, warning `#F4B860`, danger `#FF6B7A`. Disabled content uses
42% opacity; hover uses `surface-3`; pressed reduces brightness by 8%.

## Shadows and glass

Panels use a 1 px translucent inner border and a soft 18–28 px dark shadow.
Overlays use 94–96% navy when blur is unavailable, preserving readable contrast.
No text is placed directly on a variable wallpaper without an opaque-enough
surface.
