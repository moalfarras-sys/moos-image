# Meyar | مِعيار

Original Arabic–Latin sans-serif construction for MoOS. Version0.100 is an
engineering development, **not an accepted production system default**. Its
authored paths are in `sources/arabic.py` and `sources/latin.py`; no existing
font is read, renamed, traced or used as an outline input. The source and its
exports are under [SIL OFL1.1](OFL.txt), with the reserved name Meyar.

Regular and Bold share compatible original geometry with Thin/Black optical
masters. The100–900 `wght` axis has nine named instances. Arabic includes
contextual joining, lam–alef, a final-yeh contextual alternate, cursive anchors,
mark-to-base/ligature/mark positioning and Arabic/Persian figures. Latin1 and
ExtendedA are complete, with additional canonical European accents, distinct
I/l/1, tabular figures, currency, punctuation and common mathematical signs.
Syrian currency uses the normal Unicode text `ل.س`; no invented currency code
point replaces another Unicode character. Unsupported scripts use the normal
system fallback; this is not a claim to cover every Arabic Unicode extension.

## Build and test

Use a private development environment, not system package layering:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-build.txt
.venv/bin/python build.py --output dist --ufo
.venv/bin/python verify.py dist --receipt dist/verification.json
QT_QPA_PLATFORM=offscreen .venv/bin/python proof.py dist dist/specimen.png
```

`native_metrics.py` additionally checks actual Qt text ink against its natural
line and counts the joined ink/counters. It needs the host's PySide6. Run it
with a private Fontconfig file containing **only the exact candidate font**;
an application-font registration can replace Regular while the system still
supplies old named Thin/Bold/Black faces. The harness refuses mismatched native
line-metric bytes. Pixel controls complement HarfBuzz, not vice versa.

`dist` contains29 TTF/CFF-OTF/WOFF2 binaries, four compatible TTF masters, an
editable Regular/Bold UFO pair, designspace, OpenType features and checksums.
The built variation tables must include every nonconstant glyph: compilation
refuses an incompatible master instead of accepting varLib's silent skip.
Timestamps are fixed with `recalcTimestamp=False`; complete second builds must
match every exported binary. CFF files have CFF outlines, not renamed TTFs.

## Current acceptance

The physical V3's Qt6.11.2 and HarfBuzz execute1843 binary/shaping checks and64
isolated native ink controls successfully on the corrected v9 snapshot. The
old skipped variations, changing timestamps, tapered diagonals, mark clipping,
stale-font mix and first harness lifetime fault remain in private evidence.
Dots are optically separated at heavy weights; vowel marks have their own
lighter progression. Accented i/j lose their dot, and bottom accents follow
the letter rather than a distant baseline offset.

The owner rejects the earlier Arabic appearance. That feedback remains a
design refusal even where technical controls pass. A separate concurrent
open-source Arabic experiment does not become this original design's source
or provenance. Default integration, broader language/human proofreading,
native Settings/launcher/application journeys, hinting/readability review,
final repeat-build proof and signed delivery must qualify the chosen design.
The temporary v5 user font was exactly retired to private recovery; the
owner's system font configuration remains unchanged.

Technical references: [Arabic OpenType shaping](https://learn.microsoft.com/en-us/typography/script-development/arabic),
[fontTools variation builder](https://fonttools.readthedocs.io/en/latest/varLib/),
[SIL OFL](https://openfontlicense.org/open-font-license-official-text/).
