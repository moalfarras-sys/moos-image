#!/usr/bin/env python3
"""Measure the canonical MoOS mark without changing semantic/user palettes.

The shipped transparent raster is rendered from the attributed SVG master.
Hue-sector means describe the artwork, not accessible foreground/background
pairs; consumers must still qualify their composed contrast separately.
"""
from __future__ import annotations

import argparse
import colorsys
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "artwork/logo/MoOS_Logo_Vector_High_Detail.svg"
RASTER = ROOT / "system_files/usr/share/pixmaps/moos-logo.png"
OUTPUT = ROOT / "artwork/moos-design/brand-palette.json"


def measure() -> dict:
    counts = {key: 0 for key in ("cyan", "blue", "violet", "other")}
    sums = {key: [0, 0, 0] for key in counts}
    with Image.open(RASTER) as source:
        image = source.convert("RGBA")
        # Pixel access keeps the same measurement on older/newer Pillow.
        for y in range(image.height):
            for x in range(image.width):
                r, g, b, a = image.getpixel((x, y))
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if a < 128 or s < .35 or v < .25:
                    continue
                family = ("cyan" if .45 <= h < .55 else
                          "blue" if .55 <= h < .70 else
                          "violet" if .70 <= h < .84 else "other")
                counts[family] += 1
                for i, value in enumerate((r, g, b)):
                    sums[family][i] += value
    return {
        "schema": 1,
        "scope": "artwork reference only; semantic palettes and personal accents retain their owners",
        "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (MASTER, RASTER)},
        "method": {"alpha_min": 128, "hsv_saturation_min": .35, "hsv_value_min": .25,
                   "hue_sectors": {"cyan": [.45, .55], "blue": [.55, .70], "violet": [.70, .84]},
                   "aggregation": "unweighted sRGB channel mean; round-to-even; hue upper bound exclusive"},
        "swatches": {key: {"pixels": count,
                           "srgb": "#" + "".join(f"{round(value / count):02X}" for value in sums[key])}
                     for key, count in counts.items() if count},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = json.dumps(measure(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text() != expected:
            parser.exit(1, "MoOS logo palette differs; regenerate and review the artwork inputs\n")
    else:
        OUTPUT.write_text(expected)
    print("MoOS logo palette: canonical inputs and measured swatches match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
