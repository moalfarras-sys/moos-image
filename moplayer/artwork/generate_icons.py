#!/usr/bin/env python3
"""Generate the MoPlayer MoOS icon set from the MoPlayer brand mark.

The source `assets/branding/logo.png` is the full MoPlayer lockup: the orange
"M + swoosh + play" mark on top, and a *black* "MoPlayer / by Moalfarras"
wordmark underneath. The wordmark is black-on-transparent, so it is invisible on
a dark UI and unusable as an icon — the app draws its own gradient wordmark
instead. Only the mark is extracted here.

Outputs:
  assets/branding/mark.png                                    the bare mark, trimmed and squared
  packaging/moos/icons/hicolor/<size>/apps/moos-moplayer.png  the raster set
  packaging/moos/icons/hicolor/scalable/apps/moos-moplayer.svg the scalable one

The shipped icon is a *tile*: the mark on a rounded, warm near-black surface with
an ember glow. A bare orange mark would vanish against an orange-ish or light
panel; the tile keeps the icon legible on every MoOS surface — dark panel, Nova
Light, the Kickoff grid, and the Alt-Tab switcher — which is what the Plasma
icon guidelines mean by "works on any background".

## Why the icon is called `moos-moplayer` and not `org.moos.moplayer`

MoOS gates its own applications: `build_files/verify_identity.py` requires every
first-party launcher's `Icon=` to begin with `moos-`, which is how the image
proves at build time that no app is quietly wearing an inherited Fedora icon. An
icon named after the app id passes nothing.

The icon *name* and the Wayland *app_id* are independent: Plasma matches a window
to its `.desktop` file by app_id (`org.moos.moplayer`, unchanged — it is also the
MPRIS bus name), and only then reads `Icon=` out of that file. So the app keeps
its id and the icon takes the name the gate can see.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "branding" / "logo.png"
MARK_OUT = ROOT / "assets" / "branding" / "mark.png"
ICON_DIR = ROOT / "packaging" / "moos" / "icons" / "hicolor"

ICON_NAME = "moos-moplayer"
SIZES = (16, 22, 24, 32, 48, 64, 72, 96, 128, 192, 256, 512)

# Glass Orange Cinema surfaces (see DESIGN.md) — the tile is the app's own canvas
# colour, so the icon reads as a small window of the app itself.
TILE_TOP = (26, 23, 20, 255)      # #1A1714 — the warm surface
TILE_BOTTOM = (7, 8, 9, 255)      # #070809 — the canvas
EMBER = (255, 138, 31)            # #FF8A1F — MoPlayer primary


def extract_mark(src: Image.Image) -> Image.Image:
    """Crop the orange mark out of the lockup and trim it to its own bounds."""
    # The wordmark sits below the mark and is nearly black; select on luminance
    # so it cannot leak into the crop even if the layout shifts a little.
    w, h = src.size
    mark_band = src.crop((0, 0, w, int(h * 0.62)))

    px = mark_band.load()
    bw, bh = mark_band.size
    min_x, min_y, max_x, max_y = bw, bh, 0, 0
    for y in range(bh):
        for x in range(bw):
            r, g, b, a = px[x, y]
            if a > 40 and (r + g + b) > 120:
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
    if min_x >= max_x or min_y >= max_y:
        raise SystemExit("generate_icons: found no mark pixels in the source logo")

    mark = mark_band.crop((min_x, min_y, max_x + 1, max_y + 1))

    # Square it on a transparent canvas, keeping the aspect ratio.
    side = max(mark.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(mark, ((side - mark.width) // 2, (side - mark.height) // 2), mark)
    return square


def rounded_tile(size: int, radius_ratio: float = 0.225) -> Image.Image:
    """A rounded-square Nova surface with a vertical gradient and an inner edge."""
    ss = 4  # supersample; Pillow has no antialiased rounded_rectangle
    s = size * ss
    radius = int(s * radius_ratio)

    gradient = Image.new("RGBA", (1, s))
    gd = gradient.load()
    for y in range(s):
        t = y / max(1, s - 1)
        gd[0, y] = tuple(
            int(TILE_TOP[i] + (TILE_BOTTOM[i] - TILE_TOP[i]) * t) for i in range(4)
        )
    gradient = gradient.resize((s, s))

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=255)

    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    tile.paste(gradient, (0, 0), mask)

    # A 1px translucent inner border — the Nova panel signature.
    edge = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        (0, 0, s - 1, s - 1), radius=radius, outline=(255, 255, 255, 28), width=max(2, ss)
    )
    tile = Image.alpha_composite(tile, edge)
    return tile.resize((size, size), Image.LANCZOS)


def compose(mark: Image.Image, size: int) -> Image.Image:
    tile = rounded_tile(size)

    # Ember glow behind the mark, so the icon has depth at large sizes and still
    # reads as a warm blob at 16px where the mark itself is only a few pixels.
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    inset = size * 0.22
    gd.ellipse(
        (inset, inset, size - inset, size - inset),
        fill=(*EMBER, 90 if size >= 48 else 120),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(1, size * 0.09)))
    tile = Image.alpha_composite(tile, glow)

    # The mark, inset so the tile's corners breathe (Plasma's icons keep ~12%).
    pad = round(size * 0.13)
    inner = size - 2 * pad
    m = mark.resize((inner, inner), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(tile, (0, 0), tile)
    out.paste(m, (pad, pad), m)
    return out


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"generate_icons: missing source {SOURCE}")

    src = Image.open(SOURCE).convert("RGBA")
    mark = extract_mark(src)
    MARK_OUT.parent.mkdir(parents=True, exist_ok=True)
    mark.save(MARK_OUT)
    print(f"mark  -> {MARK_OUT.relative_to(ROOT)}  {mark.size[0]}x{mark.size[1]}")

    for size in SIZES:
        icon = compose(mark, size)
        out = ICON_DIR / f"{size}x{size}" / "apps" / f"{ICON_NAME}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        icon.save(out)
        print(f"icon  -> {out.relative_to(ROOT)}")

    svg = write_scalable(mark)
    print(f"icon  -> {svg.relative_to(ROOT)}")

    return 0


def write_scalable(mark: Image.Image) -> Path:
    """The scalable icon.

    The tile is real vector — a rounded rect, a gradient and an ember bloom — so
    it stays crisp at any size a 4K Kickoff or a HiDPI Alt-Tab asks for. The mark
    itself is the artwork the brand actually is (a raster lockup), embedded at
    512px: tracing it into paths would be a redrawing of the logo, and an icon
    generator is not the place to redesign a brand.
    """
    import base64
    import io

    buffer = io.BytesIO()
    mark.resize((512, 512), Image.LANCZOS).save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="512" height="512" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1A1714"/>
      <stop offset="100%" stop-color="#070809"/>
    </linearGradient>
    <radialGradient id="ember" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#FF8A1F" stop-opacity="0.38"/>
      <stop offset="100%" stop-color="#FF8A1F" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="0" y="0" width="512" height="512" rx="115" ry="115" fill="url(#tile)"/>
  <rect x="0.5" y="0.5" width="511" height="511" rx="115" ry="115"
        fill="none" stroke="#FFF3E0" stroke-opacity="0.11"/>
  <circle cx="256" cy="256" r="150" fill="url(#ember)"/>
  <image x="67" y="67" width="378" height="378"
         xlink:href="data:image/png;base64,{encoded}"/>
</svg>
"""
    out = ICON_DIR / "scalable" / "apps" / f"{ICON_NAME}.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    return out


if __name__ == "__main__":
    sys.exit(main())
