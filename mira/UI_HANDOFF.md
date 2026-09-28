# Mira Neural OS v4 — interface handoff (2026-09-29)

Qt Quick on the GPU (`qml/Main.qml`, module `qml/Mira/`). Both original faces are kept as drawn; the
portrait is framed by `faces.json` so every expression shares one alignment.

## Structure

| Surface | File | Notes |
|---|---|---|
| Space | `Nebula.qml` + `shaders/nebula.frag` | half-resolution aurora; brightens around the core with the state colour |
| Mira core | `MiraCore.qml`, `FaceFrames.qml`, `shaders/aura.frag`, `shaders/portal.frag` | face portal, ring of light, orbiting motes, pointer-follow tilt, never-looping idle sway |
| Under the face | `StageCaption.qml` | state label + live words (yours while listening, hers while speaking, errors in rose-red) |
| Context | `ContextRail.qml` | clock, real Open-Meteo weather, lights at a glance with All on/off, TV, one-tap requests |
| Conversation | `ConversationPanel.qml`, `MessageDelegate.qml` | bubbles (selectable text, right-click copies) and verified action cards ✓ / ⏱ / ! |
| Command dock | `CommandDock.qml` | microphone with a live level ring (becomes Stop while active), field, text-file attach, send |
| Workspaces | `SideSheet.qml` + `HomeSheet.qml`, `ComputerSheet.qml`, `SettingsSheet.qml` | slide in from the trailing edge; Esc closes |
| Top bar | `TopBar.qml`, `ServicePill.qml`, `Avatar.qml` | identity, live Echo / Home / Mo AI status, destinations, face and language |
| Controls | `IconButton`, `PillButton`, `MiraSwitch`, `MiraSlider`, `MiraField`, `Icon` (+ `icons.js`) | own line-icon set; RTL mirrored switches and sliders |

Layout: ≥1180 px three columns (rail · core · conversation); 760–1180 core + conversation;
<760 face above the conversation, dock below, workspaces full width. Arabic mirrors everything
through `LayoutMirroring`; text alignment follows the text.

## States

| Phase | Ring | Face |
|---|---|---|
| idle | rose (holo: cyan→violet), slow breathing | mood (neutral, happy, proud… from the last reply) |
| listening | mint→cyan, radius and glow follow the microphone | attentive; blinks more often |
| thinking | violet→blue, two comets chase, scan line | thinking (eyes up) |
| speaking | rose→violet, energy follows her voice | mouth band follows the playback level |
| executing | amber segmented orbit | curious |
| error | dim red, slow pulse | sad; message under the face |
| offline (voice off) | grey, still | sleepy |

## Tokens (`Theme.qml`)

Canvas `#04050D` / `#080B1C`; glass fill `rgba(19,23,48,.72)` with one hairline and one inner
highlight; ink `#F4F1FF` (secondary at 72 %, tertiary at 50 % alpha); cyan `#35D8F4`, mint
`#3DF2C4`, violet `#9B7BFF`, rose `#FF6FB5`, amber `#FFC46B`, danger `#FF5C7A`, ok `#48E0A0`.
Type IBM Plex Sans Arabic 11/12/14/17/22/30, JetBrains Mono for readings. Radii 10/14/22/30.
Motion 120 / 220 / 360 ms; Reduced Motion (the app switch, or Plasma's animation speed at 0)
makes them exactly zero.

## Energy

One shared clock drives every living surface: display rate only while Mira is listening,
thinking, speaking or acting (or the pointer is on her face); 30 Hz for 45 s after use; 12 Hz
after that; still after two minutes (blinks stay; they are short). Hidden or minimised: nothing
runs. Measured on the station at 3330×1935: ~11 % of one core in the first minute, ~5 % at 12 Hz.

## Evidence

Rendered on the live KWin session with stand-in data (`review_fakes.py`) in every state, both
faces, Arabic and English, at 1600, 1000 and 600 px, and the installed app was captured from its
own window (`snapshot:` on the instance socket). `test_qml.py` loads the interface, opens every
workspace, switches language, face and all states at three widths and fails on any QML error; it
also fails any `mira.<route>()` the controller does not implement and any missing string.
