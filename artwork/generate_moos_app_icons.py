#!/usr/bin/env python3
import xml.etree.ElementTree as ET
from pathlib import Path
import subprocess

# Paths
ARTWORK = Path(__file__).resolve().parent
ROOT = ARTWORK.parent
ICONS = ROOT / "system_files/usr/share/icons/hicolor"
MASTER_DIR = ARTWORK / "master_icons"

# Icons to process (all squircle-based apps, plus KDE system apps)
MARKS = (
    "moos-control-center",
    "moos-installer",
    "moos-moplayer",
    "moos-pc-remote",
    "moos-recovery",
    "moos-store",
    "moos-themes",
    "moos-updater",
    "moos-welcome",
    "org.kde.dolphin",
    "org.kde.konsole",
    "org.kde.gwenview",
    "firefox",
)

ICON_SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <image width="1024" height="1024" href="data:image/png;base64,{b64}" />
</svg>
"""

def generate_png_ladder(master_png: Path, name: str) -> None:
    for size in ICON_SIZES:
        out_dir = ICONS / f"{size}x{size}/apps"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_png = out_dir / f"{name}.png"
        subprocess.run([
            "magick", str(master_png),
            "-resize", f"{size}x{size}",
            str(out_png)
        ], check=True)

def generate_svg_wrapper(master_png: Path, name: str) -> None:
    import base64
    b64 = base64.b64encode(master_png.read_bytes()).decode("utf-8")
    svg = SVG_TEMPLATE.format(b64=b64)
    out_dir = ICONS / "scalable/apps"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_svg = out_dir / f"{name}.svg"
    out_svg.write_text(svg)

def main():
    print(f"Generating MoOS app icons from 3D PNG masters...")
    for mark in MARKS:
        master_png = MASTER_DIR / f"{mark}.png"
        if master_png.exists():
            generate_png_ladder(master_png, mark)
            generate_svg_wrapper(master_png, mark)
        else:
            print(f"Warning: {master_png} not found!")
    
    print(f"generated {len(MARKS)} MoOS app icons from PNG masters")

if __name__ == "__main__":
    main()
