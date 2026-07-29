#!/usr/bin/env python3
"""Mo AI's app icon: the commissioned artwork, seated on the family plate.

The owner replaced Mo AI's vector icon with commissioned raster artwork
(artwork/icons/mo-ai-1024.png) on 2026-07-16, and the UX gate requires the
scalable entry to embed that master byte-for-byte — the artwork itself is not
this script's to touch. What WAS wrong is the seating: the raw orb shipped
edge-to-edge (solid alpha spans 42..986 of 1024), so in the dock, launcher and
taskbar it rendered ~92% of its cell while every sibling icon sits on the
shared graphite squircle at ~86% — Mo AI visibly bulged out of the row and
followed none of the family's corner language.

This generator seats the exact master on the exact sibling plate (geometry and
gradient copied verbatim from moos-store/welcome/installer/updater, which are
byte-identical in those defs) and rasterises the same composition for the
hicolor ladder. One design, two encodings:

  - scalable/apps/moos-moai.svg — plate + <image> of the EXACT master
    (gate-checked byte equality survives, because the wrapper only changes
    layout around the embedded data).
  - {16..512}/apps/moos-moai.png — the identical composition rendered at 1024
    with PIL and downscaled per size (no external SVG rasteriser exists in
    this environment; the plate is redrawn from the same numbers).

Deterministic: no timestamps, no randomness — rerunning must be a no-op.
"""

from __future__ import annotations

import base64
import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
MASTER = ROOT / "artwork/icons/mo-ai-1024.png"
ICON_ROOT = ROOT / "system_files/usr/share/icons/hicolor"

# The family plate, verbatim from the sibling masters.
PLATE_XY, PLATE_WH, PLATE_RX = 72, 880, 232
PLATE_STOPS = ((0.0, (0x30, 0x43, 0x48)), (0.44, (0x1D, 0x2B, 0x2F)), (1.0, (0x10, 0x18, 0x1B)))
PLATE_AXIS = (128, 104, 900, 934)
SHADOW_DY, SHADOW_SIGMA, SHADOW_RGBA = 28, 30, (0x07, 0x10, 0x12, 128)

# The orb's box inside the 1024 canvas. The master's solid alpha spans
# 42..986 (944 px), so a 694-px box puts the visible orb at ~640 px — inside
# the plate (72..952) with ~104 px of breathing room on every side, the same
# optical weight the sibling glyphs carry on this plate.
ORB_XY, ORB_WH = 165, 694

LADDER = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)


def wrapper_svg() -> str:
    data = base64.b64encode(MASTER.read_bytes()).decode()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- Mo AI: commissioned raster master, seated on the MoOS family plate.
       The embedded PNG must stay byte-identical to artwork/icons/mo-ai-1024.png
       (gate-enforced); only the seating around it is generated. -->
  <defs>
    <linearGradient id="plate" x1="128" y1="104" x2="900" y2="934" gradientUnits="userSpaceOnUse">
      <stop stop-color="#304348"/>
      <stop offset=".44" stop-color="#1D2B2F"/>
      <stop offset="1" stop-color="#10181B"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">
      <feDropShadow dx="0" dy="28" stdDeviation="30" flood-color="#071012" flood-opacity=".50"/>
    </filter>
  </defs>
  <rect x="72" y="72" width="880" height="880" rx="232" fill="url(#plate)" filter="url(#shadow)"/>
  <image x="{ORB_XY}" y="{ORB_XY}" width="{ORB_WH}" height="{ORB_WH}" xlink:href="data:image/png;base64,{data}"/>
</svg>
"""


def plate_layer(size: int = 1024) -> Image.Image:
    """The graphite squircle with its diagonal 3-stop gradient and soft shadow."""
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (PLATE_XY, PLATE_XY, PLATE_XY + PLATE_WH, PLATE_XY + PLATE_WH),
        radius=PLATE_RX, fill=255)

    x1, y1, x2, y2 = PLATE_AXIS
    ax, ay = x2 - x1, y2 - y1
    norm = ax * ax + ay * ay
    gradient = Image.new("RGBA", (size, size))
    px = gradient.load()
    for y in range(size):
        for x in range(size):
            t = ((x - x1) * ax + (y - y1) * ay) / norm
            t = 0.0 if t < 0 else 1.0 if t > 1 else t
            for (t0, c0), (t1, c1) in zip(PLATE_STOPS, PLATE_STOPS[1:]):
                if t <= t1 or (t1, c1) == PLATE_STOPS[-1]:
                    f = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                    f = 0.0 if f < 0 else 1.0 if f > 1 else f
                    px[x, y] = tuple(round(a + (b - a) * f) for a, b in zip(c0, c1)) + (255,)
                    break

    shadow = Image.new("RGBA", (size, size))
    shadow_tint = Image.new("RGBA", (size, size), SHADOW_RGBA)
    shadow.paste(shadow_tint, (0, SHADOW_DY), mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_SIGMA))

    plate = Image.new("RGBA", (size, size))
    plate.paste(gradient, (0, 0), mask)
    return Image.alpha_composite(shadow, plate)


def main() -> None:
    if not MASTER.is_file():
        raise SystemExit(f"missing commissioned master: {MASTER}")

    svg_path = ICON_ROOT / "scalable/apps/moos-moai.svg"
    svg_path.write_text(wrapper_svg(), encoding="utf-8", newline="\n")

    orb = Image.open(MASTER).convert("RGBA").resize((ORB_WH, ORB_WH), Image.LANCZOS)
    master = plate_layer()
    master.alpha_composite(orb, (ORB_XY, ORB_XY))
    for size in LADDER:
        out = ICON_ROOT / f"{size}x{size}/apps/moos-moai.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        master.resize((size, size), Image.LANCZOS).save(out, optimize=True)

    print(f"seated Mo AI on the family plate: {svg_path.name} + {len(LADDER)} ladder sizes")


if __name__ == "__main__":
    main()
