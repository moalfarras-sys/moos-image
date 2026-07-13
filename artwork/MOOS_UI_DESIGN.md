# MoOS UI — visual development contract

Status: **implemented in the working tree; local image build still required**  
Owner: visual-system workstream  
Started: 2026-07-13

This file is the hand-off point for any agent touching MoOS visuals. Read it with
`PROJECT_STATE.md` before editing the theme, dock, first-party app icons, or desktop
widgets. The existing Nova packages remain installed as the known-good fallback;
MoOS UI is added as a new matched dark/light pair and must be proven before it can
become the default.

Rebuild every generated theme, icon and wallpaper output with:

```bash
python3 artwork/generate_moos_ui.py
```

## Direction

MoOS UI is warm, calm glass rather than Nova's cyan/navy glass:

| Token | Dark | Light | Purpose |
|---|---|---|---|
| canvas | `#17131D` | `#F1EBE3` | deep aubergine / warm pearl, never pure black or white |
| surface | `#241D2B` | `#E7DDD2` | windows and dock glass |
| raised | `#312538` | `#DDD0C4` | controls and hover surfaces |
| primary | `#C084FC` | `#7C3AED` | orchid focus and selection |
| secondary | `#FB923C` | `#C2410C` | warm interaction accent |
| positive | `#6EE7B7` | `#047857` | healthy system state |
| text | `#EEE7F0` | `#29212E` | soft ink, not glaring white |
| muted text | `#B8AABD` | `#756878` | secondary copy |

The dock keeps the proven single floating-panel architecture. Its visual changes
are confined to Plasma Style SVGs: warmer translucent glass, a quieter orchid
active underline, and a brief hover lift handled by Plasma's own task state. No
second panel and no unverified layout API are introduced.

## First-party icon language

- **Mo AI:** an intelligent system core: four-point neural spark inside two
  asymmetric orbits. It says “intelligence governing the system,” not robot or
  chat bubble. The generated concept is in
  `artwork/moos-ui/concepts/mo-ai-concept.png`; the shipping master is SVG.
- **Mo PC Remote:** a phone-to-display gesture, condensed into a monitor, phone,
  flowing connection and pointer. The generated concept is in
  `artwork/moos-ui/concepts/mo-pc-remote-concept.png`; the shipping master is SVG.
- Shipping icons must survive 16 px, contain no text, and have PNG fallbacks
  generated from the SVG master for consumers that do not resolve scalable icons.

## Desktop widget

Keep the existing one-applet invariant: weather, clock, CPU, RAM and GPU stay in
`org.moos.nova.deskclock` so Plasma cannot separate their persisted geometry.
MoOS UI evolves it with a passive translucent glass lens, original QML vector
weather animation and a soft minute transition. It
must continue to contain no `MouseArea`, use the verified sensor IDs, and keep the
keyless ipwho.is + Open-Meteo path.

No third-party Lottie file is vendored. Original QML/SVG motion avoids a runtime
dependency, uncertain animation licensing, and network-loaded UI in the desktop
shell.

## Rollout and gates

1. Add the two icon masters, PNG sizes and launcher wiring.
2. Add `org.moos.ui` / `org.moos.ui.light`, `MoOSUI` / `MoOSUILight`, matching
   Aurorae decorations and KDE/Konsole colour schemes.
3. Teach `moos-theme` and `moos-apply-theme` to recognize both MoOS UI variants
   without deleting Nova fallback support.
4. Apply the widget update and bump the visual revision so OSTree-era QML/SVG
   caches are dropped for existing users.
5. Extend `verify_user_experience.py`; deliberately break each new selector once
   during development to prove the gate fails.
6. Run the Python gates, shell syntax checks, SVG/XML validation and QML load
   checks available locally. A local image build remains required before push.

## Live hardware proof

Both variants were staged temporarily into the maintainer's real Plasma 6.7.2
session on 2026-07-13, applied through the real Look-and-Feel/KWin/KConfig paths,
read back with `kreadconfig6`, and captured at 3840×2160:

- [`live-tests/moos-ui-dark-v2.png`](moos-ui/live-tests/moos-ui-dark-v2.png)
- [`live-tests/moos-ui-light-v2.png`](moos-ui/live-tests/moos-ui-light-v2.png)

The proof covers the actual wallpaper renderer, dark/light palette, Aurorae
decoration selector, Plasma Style, dock, first-party app icons, animated weather,
clock glass lens and verified CPU/RAM/GPU sensors. No QML or MoOS UI load errors
appeared in the live plasmashell journal. The temporary `~/.local/share` packages
were removed after capture and the installed session was restored to system Nova;
there are no user-local MoOS UI shadows left to hide the image after an update.

## Revision 2 — direct visual review

The first live pass proved the packages loaded, but it also exposed two design
regressions that a gate could not judge: the desktop widget still read as Nova's
narrow vertical clock with a pane behind it, and Plasma's adaptive transparency
turned the Light dock into a bright opaque slab. Revision 2 therefore makes these
visual contracts explicit:

- the desk widget is a 27-grid-unit horizontal live dashboard, with an animated
  status beacon, independent rolling clock, enlarged animated weather orb and a
  single machine-pulse rail;
- Dark and Light docks use the exact same FrameSvg geometry and both disable
  adaptive transparency;
- Light owns a generated warm-mauve `panel-background.svg` rather than inheriting
  a surface that Plasma may repaint white.

The generator creates the Light panel from the Dark master and recolours only its
glass palette, so later geometry changes cannot make the two docks diverge.

## Generated prompts

The concepts were generated with the built-in image generator using the
`logo-brand` taxonomy. Mo AI requested a neural spark plus orbiting system core,
midnight/indigo/cyan/violet glass, no text, face, robot or brain cliché. Mo PC
Remote requested a compact phone-to-monitor touch gesture in teal/cobalt glass
with a small warm interaction point, no text or Wi-Fi-only symbol. The PNGs are
design references; deterministic SVG masters are the runtime source of truth.
