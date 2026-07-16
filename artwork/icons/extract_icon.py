#!/usr/bin/env python3
"""Extract a real alpha channel from an AI-generated icon whose 'transparency'
is a BAKED-IN checkerboard preview.

The checker is two near-white neutral tones (~c0=242, c1=254, delta ~12-14).
Grid period is real-valued with jitter, so no synthetic grid: per pixel we
key against whichever tone is closer, and decide holes vs highlights by
STRUCTURE — a genuine hole shows the two-tone alternation, a metal highlight
is one uniform tone.

Outputs a trimmed, square, transparent master PNG.
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage

SRC, DST = sys.argv[1], sys.argv[2]

im = Image.open(SRC).convert('RGB')
I = np.asarray(im).astype(np.float64)
H, W, _ = I.shape

# ── the two checker tones, sampled from the borders (pure bg there) ──────────
border = np.concatenate([I[0], I[-1], I[:, 0], I[:, -1]]).reshape(-1, 3)
neutral = border[(border.max(1) - border.min(1)) < 6]
gray = neutral.mean(1)
mid = (gray.min() + gray.max()) / 2.0
c0 = float(gray[gray < mid].mean())   # darker squares
c1 = float(gray[gray >= mid].mean())  # lighter squares
tone_split = (c0 + c1) / 2.0

# ── distance from bg: neutral-gray distance to nearest tone, chroma-guarded ──
chroma = I.max(2) - I.min(2)                      # checker is neutral
g = I.mean(2)
d_tone = np.minimum(np.abs(g - c0), np.abs(g - c1))
d = np.maximum(d_tone, chroma * 1.2)              # colour can't be checker

LO, HI = 10.0, 45.0
alpha = np.clip((d - LO) / (HI - LO), 0.0, 1.0)

core = d >= HI
bgish = d < LO

# ── holes vs highlights: fill enclosed bg-ish regions unless they are checker ─
filled = ndimage.binary_fill_holes(core)
enclosed = filled & ~core                          # candidate interior regions
lab, n = ndimage.label(enclosed & bgish)
for r in range(1, n + 1):
    m = lab == r
    px = g[m]
    n0 = (px < tone_split).sum()
    n1 = (px >= tone_split).sum()
    total = px.size
    # checker structure: both tones present in force -> a REAL hole
    if total > 400 and n0 > 0.15 * total and n1 > 0.15 * total:
        continue                                   # leave transparent
    # fill only patches truly embedded in solid icon: boundary must be core,
    # not the AA ring of a real hole (that produced ragged white slivers)
    ring = ndimage.binary_dilation(m) & ~m
    if ring.sum() == 0 or core[ring].mean() < 0.85:
        continue
    # uniform bright patch enclosed by solid icon -> foreground highlight
    alpha[m] = 1.0

# ── rescue white LIGHT lost to the white checker squares ─────────────────────
# A flare over a hole is pixel-identical to a white checker square; the
# difference is the NEIGHBOURHOOD: a checker square borders dark (c0) squares,
# a flare borders its own fading glow. White patches inside holes whose rim
# shows no c0 tone are light — restore them as white glow.
hole = alpha <= 0.0
wlab, wn = ndimage.label(hole & (g >= 249) & (chroma < 8))
for r in range(1, wn + 1):
    m = wlab == r
    if m.sum() < 100:
        continue
    ring = ndimage.binary_dilation(m, iterations=4) & ~m
    ring_c0 = ((np.abs(g - c0) < 8) & (chroma < 10) & ring).sum()
    if ring_c0 > 0.02 * ring.sum():
        continue                                   # borders dark squares: checker
    alpha[m] = 1.0                                 # enclosed white light: keep it

# ── unmix the colour against the keyed bg so soft glows keep their true tint ─
B = np.where(np.abs(g - c0)[..., None] < np.abs(g - c1)[..., None], c0, c1)
a3 = alpha[..., None]
F = np.where(a3 > 0.01, (I - (1.0 - a3) * B) / np.maximum(a3, 0.01), I)
F = np.clip(F, 0, 255)

# ── defringe: partial-alpha pixels keep the NEAREST SOLID colour ─────────────
# The unmix overestimates brightness on antialiased edges mixed with the white
# squares, leaving a white fringe on dark desktops. Shape (alpha) is right;
# colour is not — so pull edge colour from the closest fully-solid pixel.
solid = alpha >= 0.98
if solid.any():
    dist, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
    # only the 1-3px AA seam hugging a solid body is a fringe; wide soft glows
    # (the flare inside Mo AI's ring) are real translucent light — keep them.
    edge = (alpha > 0) & ~solid & (dist <= 3.0)
    F[edge] = F[iy[edge], ix[edge]]
    # bright partial pixels are LIGHT (flares, glow spilling into the holes):
    # keep the original bright colour, not a dark neighbour or a dark unmix —
    # over a dark desktop they must glow, not smudge.
    lightmask = (alpha > 0) & ~solid & (g > 248) & (chroma < 30)
    F[lightmask] = I[lightmask]

# ── despeckle stray checker-AA freckles in the far field ─────────────────────
spec_lab, sn = ndimage.label(alpha > 0)
sizes = ndimage.sum(alpha > 0, spec_lab, range(sn + 1))
alpha[np.isin(spec_lab, np.where(sizes < 60)[0])] = 0.0

out = np.dstack([F, alpha * 255.0]).astype(np.uint8)
img = Image.fromarray(out, 'RGBA')

# ── trim to content, pad square with a small margin ──────────────────────────
bbox = img.getbbox()
img = img.crop(bbox)
side = max(img.size)
margin = int(side * 0.04)
canvas = Image.new('RGBA', (side + 2 * margin,) * 2, (0, 0, 0, 0))
canvas.paste(img, ((canvas.width - img.width) // 2, (canvas.height - img.height) // 2))
canvas = canvas.resize((1024, 1024), Image.LANCZOS)
canvas.save(DST)
print(DST, 'tones:', round(c0, 1), round(c1, 1), 'bbox:', bbox)
