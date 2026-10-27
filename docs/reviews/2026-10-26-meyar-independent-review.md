# Meyar independent review — 2026-10-26

Owner instruction: review/test the concurrent implementation; do not compete for source ownership. Findings below concern the frozen snapshot in `test-results/meyar/independent-review/source-hashes.json`, not every later working-tree edit. Private images remain local.

Review in progress. Early reproducible findings for the implementation owner:

1. **Weight interpolation silently drops eight glyphs.** An actual complete build exits 0 but prints `glyph … has incompatible masters; skipping` for `uni0025 uni030A uni064C uni064F uni0652 uni00A9 uni00AE uni066A`. Their `gvar` variation arrays are empty. Example: damma has 176 points in Thin and 178 in Regular/Bold/Black; sukun has 128 vs 130. This affects %/٪, combining ring, dammatan/damma/sukun and ©/®. Fail compilation on a skipped glyph and retain a native old/fixed control. Preliminary reproduction used fontTools4.63; exact declared4.67 replay also emits the same warnings.

2. **Repeated builds change bytes.** Two complete independent exports differ in20 of29 binaries; examined examples differ only in `head.modified` and resulting checksums. Fixed timestamp assignment before save is not sufficient while `recalcTimestamp` remains enabled. Receipts: `test-results/meyar/independent-review/reproducibility.json` and the two builds.

3. **Original stroke joins taper Latin M/N.** The reviewed chord-normal offset collapses the stroke across sharp direction changes; native Qt regular specimen shows hairline M strokes next to ordinary-width E/Y/A. The live writer has subsequently changed its joins to offset intersections; that newer change needs separate rendered and contour verification.

4. **Coverage is narrower than a complete European inventory.** The initial compiled cmap lacks35 code points in Latin1/ExtendedA, including inverted Spanish punctuation and common signs. This is an inventory/claimed-scope issue, not permission to alias them to unrelated shapes. Several letters have subsequently been added by the live writer; review must use new source hashes.

Positive controls on the frozen build: ordinary Arabic initial/medial/final GSUB, lam–alef isolated/final, ZWNJ/ZWJ, decomposed/precomposed alef hamza/madda, Latin e-acute, zero-advance marks and shadda/fatha stacking execute with HarfBuzz. Native Qt loads the Regular TTF and paints Arabic/Latin/German/Persian/numbers at11–44px. These scoped controls do not prove installed default integration, hinting quality, authentication surfaces or signed image delivery.

No owner theme, system font default, signed deployment, rollback or authentication setting was changed by this review.

## Corrected snapshot v3 and remaining findings

Frozen source build `3996a742…` / geometry `2a1da543…` compiles29 exports,843 glyphs/890 encoded characters with the exact declared tool versions. Sixteen independent technical controls pass: required AR/EN/German/Persian characters, export presence/parsing/table parity, metadata/embedding, wght100–900, all master topologies and nonconstant gvar deltas, zero-advance marks, OpenType features, contextual joining/ligatures/control characters, canonical equivalence, language ar/fa/ur and identical second-build bytes. The old skipped-glyph and20/29 nondeterminism controls remain preserved; the new v2 fail-closed builder also correctly refuses its still-incompatible dammatan before the subsequent v3 fix.

**New P1: ordinary stacked marks exceed actual Qt line metrics and are clipped by a fitted text row.** At64px native QTextLayout returns ascent69.109375 and lineHeight96 for `أَّ`; actual shaped ink reaches1242UPM versus1080 ascent (1264UPM atBlack; even WinAscent1240 is exceeded). An actual Qt raster comparison at100px, with/without a natural-height line clip, loses67 pixels/16px of top ink for Regular `أَّ`,172 pixels/18px for Black `آَّ`, and12 pixels/3px for Regular `Ǻ`. Retain `test-results/meyar/current-review-v3/line-clipping.{png,json}`; require the fixed font to fit the natural native line, without widening every product card or hiding the marks. An unshaped head bounding box alone misses this.

**New P1: infinity loses its counters.** Native Qt proof paints U+221E as two filled lozenges rather than a recognisable infinity. The closed self-intersecting stroke is offset as two global outer/inner contours; that classification is invalid for a figure-eight. `test-results/meyar/current-review-v3/symbols-crop.png` preserves the rendered result. Keep a native fixed-glyph counter/shape control; merely having the code point in cmap is not semantic coverage.

The corrected snapshot still lacks23 Latin1/ExtendedA characters (including Spanish `¡¿`, cent, section, fractions and spacing accents); see `review-result.json`. This is separate from the passing requested German text control.

Actual physical V3 kfontview loads the frozen file under transient unit `moai-open-278431-28836.service` and paints its real preview. Verified native pointer opens the preview catalogue and Change Text dialog; Escape returns to the viewer. The initial absolute-pointer attempt landed at1,1 and is preserved as a failed coordinate control; the subsequent measured relative move is used. These are a local font-file journey, not installed-default proof. QtWebEngine independently accepts both static and variable WOFF2 with browser sanitization and returns measured text width98.7999267578125. It emits an unrelated installed MIME cache warning, which is retained.

Scoped review cleanup: the viewer closes through actual Alt+F4 on its verified owned window; KWin reports no remaining viewer windows and the transient unit returns inactive/dead, Result=success. System/user failed-unit listings are empty. The accessibility probe encountered an existing stale AT-SPI socket; it did not change accessibility settings and was not counted as a font failure or a successful input route.

## Owner rejects the Arabic and changes design direction

The owner explicitly rejects the Arabic drawing as incorrect and asks for a modification of an open-source Arabic typeface. This supersedes the original from-scratch-only direction. Development now proceeds separately in `fonts/meyar-arabic/`; no source rewrite of the concurrent experimental construction is implied.

Correction to the provisional infinity finding: a later isolated native raster probe on both v3 and v4 proves one connected stroke and two counters at280px, and the32px controlled replay also paints the proper infinity. The earlier proof screenshot's two solid lozenges remains a real contrary frame, but the claimed source cause is withdrawn; possible same-family font/cache ambiguity is unproven. Do not report infinity as a proven current source failure. V4 fills all Latin1/ExtendedA cmap holes and preserves topology/weight deltas. The stacked-mark clipping is independently reproduced and remains a valid refusal for that snapshot.
