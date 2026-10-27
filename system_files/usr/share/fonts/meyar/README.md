# Meyar — مِعيار

Meyar is MoOS's Arabic-first type family, developed from explicitly attributed
OFL sources after the owner rejected the experimental skeleton construction.
It is a derivative, with source-level design changes; it is not claimed to be a
from-scratch type design. The earlier rejected construction remains separate
under `fonts/meyar/` for its actual contrary controls.

The family has four native owners:

| Family | Source | Purpose |
| --- | --- | --- |
| Meyar Sans | Noto Sans LGC | Latin, Greek, Cyrillic, IPA and extended phonetic text |
| Meyar Arabic | Noto Sans Arabic | Arabic and its supported script extensions,100–900 |
| Meyar Mono | Noto Sans Mono LGC | Matching Latin/phonetic code face,700-unit cell |
| Meyar Mono Arabic | Kawkab Mono | Actual Arabic fixed-cell joining, authored Regular/Bold |

`upstream-lgc-lock.json` pins Noto sources to
`0ef94805d19e98ed658543a7c48c0a4f19cc0ac0`.
`upstream-kawkab-lock.json` pins Kawkab sources to
`45630ed78bfdbc5c7cf1dc8aab15f6385a396aed`. Arabic reuses the single checked
source under `../meyar-arabic/`, pinned to
`f1ba474be91d6a5d2cfcc4374bb03cc5f1011088`.
Every source byte and original OFL/author notice is retained. Builders refuse
drift instead of silently downloading another input.

The design shares soft terminal fillets and rounded-square dot shoulders.
Latin M has a raised central rhythm; double-storey a/g and phonetic distinctions
remain. Arabic retains contextual shaping, bearings and joins, with reviewed
dot/meem/upper-terminal changes. The mono pair uses matching700-unit cells.
Its source Arabic marks are compacted and attached to actual ink bounds;
the installed upstream control reproduces1932UPM above alef/hamza/shadda/fatha,
while the new Bold source reaches1523UPM inside1600/−768 line metrics.
The252 explicit LGC source cell adjustments in `terminal-cells.json` fit wide
digraphs, Greek accents and symbols to native Konsole Unicode15 widths. All
characters remain present. Dependent components are snapshotted before these
changes. The actual two-cell arrow control paints over the following letter;
corrected outlines and advances fit their native one-cell allocation.
Arabic additionally corrects13 encoded spacing symbols: ten authored dots keep
700-unit advances instead of being zeroed as inferred marks; two wide icons
retain their proportions in two cells. U+FDF2 gets one explicit cmap variant,
while the original four-cell Allah word ligature and ordinary joining remain.
Both mono families are exposed as fixed-cell fonts to Qt/KDE's native font
chooser by exact-family Fontconfig scan metadata; no glyph is raster-scaled by
that policy. Native old90/fixed100 chooser controls are retained.

The Latin and mono sources retain complete IPA U+0250–02AF, Phonetic Extensions
U+1D00–1DBF, combining marks U+0300–036F and Latin1/ExtendedA letter coverage.
This is measured Unicode coverage, not a claim that one binary contains every
writing system. Script-aware native Noto fallbacks remain necessary for other
alphabets. Terminal fallbacks must stay fixed-cell; proportional UI Arabic is
not a substitute for the native mono owner.

Build with the existing pinned development tool environment:

```sh
python fonts/meyar-family/build.py sans --otf --output test-results/meyar-family/sans
python fonts/meyar-family/build.py arabic --otf --output test-results/meyar-family/arabic
python fonts/meyar-family/build.py mono --otf --output test-results/meyar-family/mono
python fonts/meyar-family/build.py mono-arabic --otf --output test-results/meyar-family/mono-arabic
# Same commands with --control and output KIND-control build actual upstream controls.
python fonts/meyar-family/verify.py test-results/meyar-family \
  --output test-results/meyar-family/verification.json
```

OTF exports use the canonical static variable instances: their quadratic curves
are converted exactly to cubic curves, keeping cmap/layout/advances identical.
This avoids the observed one-unit width drift in separate CFF interpolation.
Unreviewed TrueType point-based attachments remain a refusal.

Kawkab's legacy OpenStep source needs precisely190 internal feature-label quotes
escaped before parsing. Literal dollars in feature labels use FEA escapes with
the same decoded names. No shaping feature or foreign letter is removed.
Native runtime, system defaults, four-edition image qualification and signed
delivery are distinct evidence; current execution is tracked only in the
[development plan](https://github.com/moalfarras-sys/moos-image/blob/main/docs/DEVELOPMENT_PLAN.md).

Package the runtime overlay after verification with `python fonts/meyar-family/package.py test-results/meyar-family system_files/usr/share/fonts/meyar`. The image gate uses only the standard library and checks the same manifest, Unicode maps, embedding flags and native cell policy.
