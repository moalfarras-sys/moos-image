# MoOS Horizon Bar — design

The dock is not a floating panel anymore. It is a sliver of the **Tidal Horizon** — the
same contract the wallpaper renders (left/right shoulders at 0.11/0.89W, a quiet middle)
re-drawn inside the dock glass, so the desk reads as one horizon: wallpaper above,
crest below. This is the MoOS identity answer to "what is that bar?" — not macOS, not
Windows 11, not ChromeOS: it is MoOS's own horizon, and the home button answers "where
is home" by holding the sun over the line.

## The one change and the two proofs

- **One single bottom floating capsule** — `floating=true, alignment=center,
  lengthMode=fit`. This is the maintainer's proven dock geometry (measured live:
  ~967×105 px physical ≈ 430×47 logical, 32 px floor gap on 4K@225%). It is unchanged.
- The alternative — a second top bar + dock — is **documented as broken** in
  `layout.js` for this layout. Do not resurrect it.
- The dock now carries two horizon signatures: a **crest band** running the top of the
  glass, and a **sunrise bloom** resting behind the home logo.

## Horizon crest (panel-background.svg.in)

The dock's top edge carries the horizon: a **luminous crest band** — a 3 px bright
hairline over a soft glow that fades down into the glass for ~11 logical px. It runs
the whole bar, glows at its two shoulders, and settles to a quiet accent in the
middle. First version shipped the hairline alone at 2 px — on a 4K@225% desk it read
as nothing. The band is what the eye catches.

Rules that keep the gates green:

- **Inside the top tile, stretched not tiled** — the crest spans the bar between the
  corner arcs and stops where they start. No corner path is touched
  (`test_dock_corner_bands_are_annuli_with_no_stray_run` stays green).
- **Filled bands only** — no outlined paths, no inflated bounds. The
  `verify_user_experience.py` fill-only gate greps the *generated* SVG for `stroke`,
  so even the word must not appear in comments (it did; it failed the gate once).
- **Every stop ≤ 0.93** — the frost ceiling `test_glass_surfaces_*` enforces.
- **userSpaceOnUse across 18..158** — the horizontal gradient maps to the full bar
  width, so the stretch factor cannot smear it or tear seams.
- **Symmetric by construction** — RTL mirroring changes nothing.

Tokens (generator `OPACITY`), all emitted through `render_panel`:

| token | dark | light | meaning |
|---|---|---|---|
| `@CREST_SL@` | 0.70 | 0.55 | shoulder luminous |
| `@CREST_SS@` | 0.45 | 0.32 | shoulder skirt |
| `@CREST_M@` | 0.35 | 0.22 | quiet middle (accent) |
| `@CREST_OP@` | 0.95 | 0.9 | hairline presence |
| `@CREST_GLOW_T@` | 0.55 | 0.40 | glow top stop |
| `@CREST_GLOW@` | 1.0 | 0.85 | glow band presence |

Light dials every value back because porcelain glass carries its own luminance; at the
dark values the light dock's shoulder glow turns minty.

## Sunrise bloom (org.moos.brand)

The glow behind the home logo is now the sun: it **rests** at `highlightColor` α 0.10
(was 0.0), gathers to 0.20 on hover/expanded (was 0.15), and blooms to 0.34 when
pressed (was 0.30). Motion stays behind the existing `root.motionMedium` seam.

## Verified (all on the live 4K@225% shell)

- Gates: `test_moos_ui2.py` (29 OK), `verify_user_experience.py` passed,
  `test_device_plan.py` passed, `build.sh` syntax OK.
- Live pixel read: the crest band renders turquoise-luminous (G>R) directly under the
  rim — at the line (139,200,193) on glass (38,58,61) — fading down ~11 logical px;
  continuous across the full bar with no seam drops; capsule geometry and floor gap
  unchanged.
- **Cache caveat**: Plasma serves `~/.cache/plasma_theme_MoOSUI2.kcache`; the file on
  disk is not what renders until the cache is cleared and plasmashell restarted. Delete
  it after touching the SVG. Also: a `y` attribute was once missing on the crest rect —
  it drew at y=0 onto the rim and was invisible while the gate stayed green. The crest
  is only real if pixel-diffed against the previous file.
- Live deploy path: `~/.local/share/plasma/desktoptheme/MoOSUI2/widgets/panel-background.svg`
  then `rm ~/.cache/plasma_theme_MoOSUI2.kcache ~/.cache/ksvg-elements`, `killall
  plasmashell`, relaunch. (User-level `org.moos.brand/main.qml` does **not** override
  the system plasmoid on this machine — the system copy wins; QML changes are only
  visible after an image rebuild.)

## The open-applet slot (2026-08-06)

When a panel applet's popup is open, Plasma's shell paints a frame behind it —
`CompactApplet.qml`'s `expandedItem`, a `KSvg.FrameSvgItem` on `widgets/tabbar`
whose prefix comes from the panel edge. A bottom dock asks for
`south-active-tab`. This is not the applet's own art and no applet can opt out of
it, so it is the THEME's job to make it belong to the bar.

It shipped as `raised` @ 0.84 with a `primary` @ 0.88 rim on all four edges at
radius 9 — a near-opaque slab with a bright border, drawn the full height of the
dock behind the button. Opening the MoOS launcher put a bordered rectangle on the
dock glass, which is what the owner reported as "المربع الي بالبار".

The bar's answer is a **lit slot**: the applet's slice of the dock glows, it does
not get boxed.

| property | value | why |
|---|---|---|
| fill | `primary` @ 0.12 | accent tint says "this is what's open"; still glass |
| rim | none (0.0) | a border is what made it read as a rectangle |
| radius | 20 of a 56 px block | ~40% of the block, so it reads as a capsule at dock height |

The same four prefixes are a PlasmaComponents `TabBar`'s active tab, so the change
also turns MoOS tab bars into a soft segmented control. One piece of art, two
roles, both improved. Held by
`tests/test_moos_ui2.py::test_open_applet_slot_is_never_a_bordered_box` across all
sixteen packages.

## Deliberately not done (v1)

- **No height change.** 54 logical is proven; the capsule reads 47 logical already.
  A slimmer 50 can be A/B'd live and adopted only if it looks right.
- No corner, side or bottom edits. No text, so Arabic/German/English need nothing.
- `moos-apply-theme` and `moos-selfcheck` untouched: nothing about the crest is a
  config key, and `moos-ui-migrate`'s theme rev is unchanged.
