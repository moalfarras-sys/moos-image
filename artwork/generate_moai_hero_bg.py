#!/usr/bin/env python3
"""Generate Mo AI's empty-state hero backgrounds — a premium mesh-gradient aurora,
in a DARK and a LIGHT variant so the (theme-adaptive) Mo AI hero looks right on
both Graphite/Midnight and Tidal/Daylight. Original MoOS art (no third-party
assets): soft blurred colour blobs on the theme canvas, a faint grain and a
vignette so foreground cards/text stay crisp.

Output: system_files/usr/share/moos/apps/moai/hero-bg.png        (dark)
        system_files/usr/share/moos/apps/moai/hero-bg-light.png  (light)
Regenerate:  python3 artwork/generate_moai_hero_bg.py
"""
import pathlib
from PIL import Image, ImageDraw, ImageFilter

W, H = 1600, 1000
APP = pathlib.Path(__file__).resolve().parent.parent / \
    "system_files/usr/share/moos/apps/moai"

# (cx, cy, radius-frac, (r,g,b), alpha) — same accent geometry for both variants
BLOBS = [
    (0.30, 0.24, 0.42, (34, 211, 238)),   # cyan
    (0.72, 0.30, 0.46, (45, 212, 191)),   # teal
    (0.60, 0.72, 0.50, (99, 102, 241)),   # indigo
    (0.14, 0.74, 0.36, (139, 92, 246)),   # violet
    (0.86, 0.82, 0.34, (37, 99, 235)),    # deep blue
    (0.48, 0.05, 0.30, (125, 235, 255)),  # luminous top glow
]


def aurora(base, alpha, blend, core_alpha, grain_amp, vignette_to, out):
    img = Image.new("RGB", (W, H), base)
    glow = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(glow, "RGBA")
    for cx, cy, rr, col in BLOBS:
        x, y, r = cx * W, cy * H, rr * min(W, H)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(col[0], col[1], col[2], alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=210))
    img = Image.blend(img, glow, blend)

    core = Image.new("RGB", (W, H), base)
    dc = ImageDraw.Draw(core, "RGBA")
    cx, cy, r = 0.5 * W, 0.34 * H, 0.20 * min(W, H)
    dc.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(34, 211, 238, core_alpha))
    core = core.filter(ImageFilter.GaussianBlur(radius=150))
    img = Image.blend(img, core, 0.5)

    # subtle deterministic grain
    px = img.load()
    seed = 1
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            seed = (seed * 1103515245 + 12345) & 0x7fffffff
            n = (seed % (2 * grain_amp + 1)) - grain_amp
            r0, g0, b0 = px[x, y]
            px[x, y] = (max(0, min(255, r0 + n)), max(0, min(255, g0 + n)), max(0, min(255, b0 + n)))

    # vignette toward `vignette_to`
    vig = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse([-W * 0.25, -H * 0.25, W * 1.25, H * 1.25], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(radius=200))
    edge = Image.new("RGB", (W, H), vignette_to)
    img = Image.composite(img, edge, vig)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    print("wrote", out.name, img.size)


def main():
    # DARK: near-black canvas, strong glows, dark edges
    aurora(base=(7, 10, 18), alpha=74, blend=0.92, core_alpha=60,
           grain_amp=4, vignette_to=(7, 10, 18), out=APP / "hero-bg.png")
    # LIGHT: pale canvas, softer glows, light edges — for Tidal/Daylight
    aurora(base=(232, 238, 246), alpha=42, blend=0.62, core_alpha=26,
           grain_amp=3, vignette_to=(238, 242, 248), out=APP / "hero-bg-light.png")


if __name__ == "__main__":
    main()
