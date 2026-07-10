# Mo AI — Nova Companion visual contract

`Nova Companion` is the original Mo AI mascot. It uses only the official Nova
palette and deliberately avoids Android, Copilot, Apple, KDE, Fedora, emoji,
font glyphs, and stock robot marks.

## Installed assets

The seven `512×512` RGBA/sRGB states ship at:

```text
/usr/share/moos/branding/moai/mascot/
  idle.png
  attentive.png
  thinking.png
  success.png
  warning.png
  error.png
  offline.png
```

Every state has the same canvas, registration point, and alpha footprint, so a
QML opacity cross-fade cannot move the character. `success`, `warning`, and
`error` use `nova.success`, `nova.warning`, and `nova.error` exactly. There is
no `listening` state until Mo AI has a real microphone/STT path.

The launcher family has pixel-tuned `16/22/24/32` masters, full-detail
`48/64/128/256` exports, and a dependency-free scalable SVG. The editable
mascot source is `mascot-master.svg`; `nova-companion-states.png` is the visual
QA contact sheet.

## WIRED (v19, 2026-07-10) — contract implemented in main.qml

Claude owns `/usr/share/moos/apps/moai/main.qml`; Codex does not modify it.
All seven states are preloaded as stacked `Image` items with 160 ms
opacity-only cross-fades, the idle breathe / thinking wobble run exactly per
§2 (and stop when the window hides), the header shows the transparent mascot,
assistant/typing bubbles carry the 24 px avatar (typing = thinking), the six
quick actions resolve `moos-*` symbols by theme name, `LayoutMirroring`
follows the application layout direction, bilingual text uses
`font.families: ["IBM Plex Sans", "IBM Plex Sans Arabic"]`, and `queueAction`
fires an attentive pulse only (no fake success — §7). The original contract:

```text
!serverUp                         -> offline (local brain unavailable; not Internet status)
busy                              -> thinking
input.activeFocus && input.text   -> attentive
otherwise                         -> idle
successful response               -> success for 1400 ms
failed request                    -> error for 1400 ms
queueAction requested              -> attentive pulse + honest clipboard toast
```

Implementation constraints:

1. Preload the seven images as same-geometry stacked `Image` items. Cross-fade
   only `opacity` over 160 ms; do not repeatedly replace `source` and do not use
   GIF or animated SVG.
2. Animate scene-graph properties only: idle scale `1.0↔1.018` over 2800 ms;
   thinking scale `1.0↔1.025` plus rotation `-1.2↔1.2°` over 1500 ms. Stop loops
   when the window is not visible and respect reduced-motion when that setting
   is exposed.
3. Replace the square-in-square header icon with the transparent mascot. Add a
   24 px assistant avatar to assistant/typing bubbles; typing uses `thinking`.
4. Pair the six quick actions with `moos-safe-update`, `moos-install`,
   `moos-audio`, `moos-gpu`, `moos-optimize`, and `moos-report` via the theme
   icon resolver. Do not use absolute hicolor paths.
5. Add `LayoutMirroring.enabled` from the application layout direction and
   `LayoutMirroring.childrenInherit: true`; use IBM Plex Sans Arabic for Arabic
   text and keep English in IBM Plex Sans.
6. Replace direct ad-hoc colors with the canonical Nova tokens already defined
   by `branding/PALETTE.md`.
7. Keep copy-command actions labelled honestly until the daemon/MCP/polkit path
   exists. A hidden `TextEdit.copy()` has no success callback, so it must not
   trigger the success state. Reserve `warning` for a real daemon signal such
   as a confirmation-required tool or low-resource condition. When the typed
   execution path exists, drive all states from lifecycle signals rather than
   optimistic timers.

Qt's official `Image` documentation notes that changing `source` reloads the
resource, while opacity/transform animations stay cheap on the scene graph:
<https://doc.qt.io/qt-6/qml-qtquick-image.html> and
<https://doc.qt.io/qt-6/qtquick-statesanimations-topic.html>. Kirigami guidance:
<https://develop.kde.org/docs/getting-started/kirigami/>.
