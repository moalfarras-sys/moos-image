# MoOS logo masters

The owner's official MoOS mark — the blue/cyan/violet dual-swirl "MS" orb — as
vector masters derived from the original 3D-rendered PNG.

| File | What it is | Where it is used |
|---|---|---|
| `MoOS_Logo_Vector_High_Detail.svg` | 2 756-path trace, ~2 000 distinct fills — visually closest to the original render. | The MASTER. Every shipped `moos-logo.png` is rendered from it (see below). |
| `MoOS_Logo_Vector_Animation_Optimized.svg` | 1 002-path light trace, flat posterised palette. | Shipped as `/usr/share/moos/moos-logo.svg` for QML surfaces that want vector scaling. |

## Regenerating the shipped PNGs

Render the high-detail master supersampled, then downscale (ImageMagick):

```sh
magick -background none -density 192 artwork/logo/MoOS_Logo_Vector_High_Detail.svg \
       -resize 2048x2048 /tmp/master_2048.png
for s in 1024 256 128 64 48; do
    magick /tmp/master_2048.png -resize ${s}x${s} -depth 8 -strip /tmp/logo_${s}.png
done
```

- 1024 → `system_files/usr/share/pixmaps/moos-logo.png` (the canonical mark the
  identity firewall pins), `system_files/usr/share/moos/moos-logo.png`, and every
  `look-and-feel/org.moos.ui2*/contents/splash/images/moos-logo.png`.
- 48/64/128/256 → `system_files/usr/share/icons/hicolor/<s>x<s>/apps/moos-logo.png`.
- Then `python3 artwork/generate_boot_hero.py` — the Plymouth watermark composes
  itself from the canonical pixmap.

Unlike the retired 2026-07 PNG mark, these renders are TRANSPARENT (no baked
glow square), so every surface draws its own glow/shadow to taste.
