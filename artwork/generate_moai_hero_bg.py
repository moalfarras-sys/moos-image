#!/usr/bin/env python3
"""Generate the Mo AI empty-state hero background — a premium dark mesh-gradient
aurora. Original MoOS art (no third-party assets): soft blurred colour blobs on a
near-black canvas, a faint grain and a vignette so foreground text stays crisp.

Output: system_files/usr/share/moos/apps/moai/hero-bg.png
Regenerate:  python3 artwork/generate_moai_hero_bg.py
"""
import pathlib
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 1000
OUT = pathlib.Path(__file__).resolve().parent.parent / \
    "system_files/usr/share/moos/apps/moai/hero-bg.png"

# MoOS Midnight-family accents (the app's default context)
BASE = (7, 10, 18)          # near-black canvas
BLOBS = [
    # (cx, cy, radius, (r,g,b), alpha)
    (0.30, 0.24, 0.42, (34, 211, 238), 78),    # cyan
    (0.72, 0.30, 0.46, (45, 212, 191), 66),    # teal
    (0.60, 0.72, 0.50, (99, 102, 241), 58),    # indigo/violet
    (0.14, 0.74, 0.36, (139, 92, 246), 40),    # violet
    (0.86, 0.82, 0.34, (37, 99, 235), 34),     # deep blue
    (0.48, 0.05, 0.30, (125, 235, 255), 30),   # luminous top glow
]

def main():
    img = Image.new("RGB", (W, H), BASE)
    glow = Image.new("RGB", (W, H), BASE)
    d = ImageDraw.Draw(glow, "RGBA")
    for cx, cy, rr, col, a in BLOBS:
        x, y, r = cx * W, cy * H, rr * min(W, H)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(col[0], col[1], col[2], a))
    # heavy blur turns the discs into one smooth mesh
    glow = glow.filter(ImageFilter.GaussianBlur(radius=210))
    img = Image.blend(img, glow, 0.92)

    # a second, tighter pass for a luminous core near the brand (upper-centre)
    core = Image.new("RGB", (W, H), BASE)
    dc = ImageDraw.Draw(core, "RGBA")
    cx, cy, r = 0.5 * W, 0.34 * H, 0.20 * min(W, H)
    dc.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(34, 211, 238, 60))
    core = core.filter(ImageFilter.GaussianBlur(radius=150))
    img = Image.blend(img, core, 0.5)

    # subtle grain for a premium, non-flat surface
    import hashlib
    px = img.load()
    seed = 0
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            # cheap deterministic dither from a hash — no Math.random dependency
            seed = (seed * 1103515245 + 12345) & 0x7fffffff
            n = (seed % 9) - 4
            r, g, b = px[x, y]
            px[x, y] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))

    # vignette: darken toward the edges so cards/text read cleanly
    vig = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse([-W * 0.25, -H * 0.25, W * 1.25, H * 1.25], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(radius=200))
    dark = Image.new("RGB", (W, H), BASE)
    img = Image.composite(img, dark, vig)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG")
    print("wrote", OUT, img.size)

if __name__ == "__main__":
    main()
