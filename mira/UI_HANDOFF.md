# Mira visual refinement · 2026-09-28

## Five-screen review

Rendered all five workspaces at 1440×960 and 600×960, and scrolled to the bottom of compact settings. Fixed inherited button padding that hid search/face/attachment/send glyphs; added disabled slider/button and keyboard-focus treatment. Empty conversation/inspection views explain their next action. Home controls hide irrelevant capabilities until a device is selected. Both face assets remain unchanged. 39 targeted route/voice/home/memory tests pass using simulated device responses; this is not physical all-device acceptance or a full contrast audit.

Preserve the two existing sprite sets and desktop Qt implementation. The core is the face, state feedback and conversation; device controls remain immediately accessible.

## Design tokens

| Role | Value |
|---|---|
| Background | #050816 / #0A0E24 |
| Interaction | cyan #00D4FF, violet #8B5CF6, rose #FF6EB8 |
| Text | #F0EAFF / #8B9CC0 |
| Typeface | Noto Sans Arabic; body 13, heading 18–28 |
| Spacing | 4 / 8 / 12 / 16 / 24 / 32 |
| Radius | 8 / 12 / 16 / 20 / 24 |
| Depth | translucent navy, restrained halo rather than opaque card shadows |
| Motion | 240ms face crossfade, small portrait drift and pointer follow; settings toggle stops face/background timers |

## Components and evidence

- Orb: original Rose/Holo expressions preserved, portrait and halo fit within stage, real phase labels replace fabricated frequency/sync numbers.
- DockWave: amplitude is driven by incoming level; zero level is a still baseline.
- Settings: persistent visual-motion choice.
- Context / conversation: 260px context and 300–360px conversation on desktop; stacked on compact widths.
- Verified offscreen renders at 1600×1000 and 760×1000, both faces. 24 UI/voice tests pass. Full accessibility contrast audit and GPU profiling remain outstanding; Qt painter rendering is not claimed GPU-only. Live speech lip synchronisation still depends on supplied audio-level events.
