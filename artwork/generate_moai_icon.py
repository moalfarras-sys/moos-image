#!/usr/bin/env python3
"""Mo AI's app icon: the commissioned orb, seated on the family's optical grid.

The owner replaced Mo AI's vector icon with commissioned raster artwork
(artwork/icons/mo-ai-1024.png) on 2026-07-16, and the UX gate requires the
scalable entry to embed that master byte for byte — the artwork itself is not
this script's to touch.  Only its SEATING is generated here, and seating is the
part that has gone wrong twice.

Mo AI is the one mark in the family with no tile.  Every sibling is a
palette-coloured squircle (artwork/generate_moos_app_icons.py) that gets
re-inked for each of the 16 MoOS palettes; the orb is commissioned artwork with
its own light, so tinting it is not on the table and a plate under it would put
a second, competing colour behind the assistant on every theme.  Floating, it
reads as the flagship and it sits correctly on every palette — dark or light —
without carrying one.

What a tile-less mark still owes the family is optical weight.  The siblings'
plate spans 880 px of the 1024 canvas, so the orb's VISIBLE footprint is scaled
to that same 880 px span: the master's solid alpha spans 949 px of its own
canvas (measured, not assumed), so it is drawn at 950 px and the two shapes
share one bounding grid.  Shipping the raw master instead spans 949 px of the
cell — Mo AI bulged out of the dock row, which is the regression the earlier
plate was invented to fix.

tests/test_moos_app_icons.py measures that footprint on the rendered 512 px
raster and fails if it drifts from the siblings' plate by more than 2%.

Deterministic: no timestamps, no randomness — rerunning must be a no-op.
"""

from __future__ import annotations

import base64
import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
MASTER = ROOT / "artwork/icons/mo-ai-1024.png"
ICON_ROOT = ROOT / "system_files/usr/share/icons/hicolor"

# The family plate spans 880 of 1024 (artwork/generate_moos_app_icons.TILE).
# The master's solid alpha spans 949 px, so 880/949 * 1024 = 950 px puts the
# visible orb on exactly that span, centred.
PLATE_SPAN = 880
MASTER_INK_SPAN = 949
ORB_WH = round(1024 * PLATE_SPAN / MASTER_INK_SPAN)
ORB_XY = (1024 - ORB_WH) // 2

LADDER = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)


def wrapper_svg() -> str:
    data = base64.b64encode(MASTER.read_bytes()).decode()
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- Mo AI: the commissioned raster master, floating on the family's optical
       grid. The embedded PNG must stay byte-identical to
       artwork/icons/mo-ai-1024.png (gate-enforced); only the seating around it
       is generated. No tile and no colour role: the orb carries its own light
       and must not be re-inked per palette like its siblings.
       Regenerate with artwork/generate_moai_icon.py. -->
  <image x="{ORB_XY}" y="{ORB_XY}" width="{ORB_WH}" height="{ORB_WH}"
         xlink:href="data:image/png;base64,{data}"/>
</svg>
"""


def main() -> None:
    if not MASTER.is_file():
        raise SystemExit(f"missing commissioned master: {MASTER}")

    svg_path = ICON_ROOT / "scalable/apps/moos-moai.svg"
    svg_path.write_text(wrapper_svg(), encoding="utf-8", newline="\n")

    orb = Image.open(MASTER).convert("RGBA").resize((ORB_WH, ORB_WH), Image.LANCZOS)
    seated = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    seated.alpha_composite(orb, (ORB_XY, ORB_XY))

    for size in LADDER:
        out = ICON_ROOT / f"{size}x{size}/apps/moos-moai.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        seated.resize((size, size), Image.LANCZOS).save(out, optimize=True)

    print(
        f"seated Mo AI on the family grid ({ORB_WH}px orb, {PLATE_SPAN}px footprint): "
        f"{svg_path.name} + {len(LADDER)} ladder sizes"
    )


if __name__ == "__main__":
    main()
