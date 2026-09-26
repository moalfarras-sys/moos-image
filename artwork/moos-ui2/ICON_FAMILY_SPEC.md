# MoOS application icon family

## Visual contract

First-party application marks use an 880 × 880 optical plate inside a 1024 ×
1024 SVG canvas. Each app keeps its own legible glyph. The plate uses the same
nine-layer Liquid Glass material and KDE colour roles in every MoOS theme.
The active Global Theme chooses the finish:

| Finish | Plate radius | Themes | Character |
| --- | ---: | --- | --- |
| Liquid | 264 | Graphite, Tidal, Aurora | Soft glass squircle |
| Orbit | 440 | Nova, Amethyst, Midnight, Daylight | Circular glass |
| Facet | 128 | Arena, Forge, Scholar | Firm rounded square |

Light and dark siblings share geometry. Every finish keeps the 72 px canvas
margin, glyph placement, colour-role pairings and 16 px legibility. Mo AI's
commissioned orb remains its own mark. Third-party icons are untouched.

## Implementation and handoff

`artwork/generate_moos_app_icons.py` owns the plate geometry. The default
hicolor master remains Liquid; `artwork/generate_moos_themes.py` selects Orbit
or Facet when it bakes each palette's first-party icon overlay. Rebuild those
overlays after changing a finish, then render the palette matrix with
`render_palette_matrix()` and inspect 16 px and 128 px exports. Run
`tests/test_moos_app_icons.py` for geometry, identity, palette and contrast
checks. Theme changes in installed MoOS are applied through `moos-apply-theme`
so the icon cache is cleared before KDE reads the new files.
