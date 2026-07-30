#!/usr/bin/env python3
"""Render the complete MoOS Tidal Cut family for visual sign-off.

Every tile shows the same source at 24 px and 16 px.  The paired rows inject
the reviewed Tidal/Graphite semantic roles into the SVG style block, so this
sheet exposes both small-size collapse and light/dark contrast without keeping
a second set of artwork.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import sys
from pathlib import Path

import cairo
import gi
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "artwork/generate_moos_symbolic_icons.py"
DEFAULT_OUTPUT = ROOT / "artwork/moos-ui2/previews/moos-symbolic-icons.png"
FONT_REGULAR = Path("/usr/share/fonts/ibm-plex-sans-fonts/IBMPlexSans-Regular.otf")
FONT_SEMIBOLD = Path("/usr/share/fonts/ibm-plex-sans-fonts/IBMPlexSans-SemiBold.otf")

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg

spec = importlib.util.spec_from_file_location("moos_symbolic_sheet_generator", GENERATOR)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {GENERATOR}")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)

PALETTES = (
    {
        "name": "Light · Tidal",
        "background": "#f4f8f7",
        "tile": "#ffffff",
        "outline": "#b9cfcc",
        "caption": "#536b6d",
        "roles": {
            "#243238": "#203034",
            "#147d72": "#006d67",
            "#8a5a00": "#8a5a00",
            "#a9364b": "#a9364b",
        },
    },
    {
        "name": "Dark · Graphite",
        "background": "#10181b",
        "tile": "#263438",
        "outline": "#49615f",
        "caption": "#9ab2ae",
        "roles": {
            "#243238": "#e1f0ec",
            "#147d72": "#43e0c1",
            "#8a5a00": "#ffd166",
            "#a9364b": "#ff8296",
        },
    },
)


def font(path: Path, size: int):
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def recolour(source: str, roles: dict[str, str]) -> str:
    for current, replacement in roles.items():
        source = source.replace(f"color: {current}", f"color: {replacement}")
    return source


def render_svg(source: str, size: int) -> Image.Image:
    handle = Rsvg.Handle.new_from_data(source.encode())
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    context = cairo.Context(surface)
    viewport = Rsvg.Rectangle()
    viewport.x = viewport.y = 0
    viewport.width = viewport.height = size
    if not handle.render_document(context, viewport):
        raise RuntimeError("librsvg did not render the symbol")
    output = io.BytesIO()
    surface.write_to_png(output)
    output.seek(0)
    return Image.open(output).convert("RGBA")


def render_sheet(output: Path) -> None:
    names = tuple(generator.SYMBOLS)
    columns = 17
    rows = (len(names) + columns - 1) // columns
    margin = 24
    title_height = 42
    tile_width = 82
    tile_height = 72
    palette_height = title_height + rows * tile_height + margin
    width = margin * 2 + columns * tile_width
    height = palette_height * len(PALETTES)
    sheet = Image.new("RGB", (width, height), PALETTES[0]["background"])
    draw = ImageDraw.Draw(sheet)
    title_font = font(FONT_SEMIBOLD, 20)
    caption_font = font(FONT_REGULAR, 8)
    size_font = font(FONT_REGULAR, 8)

    for palette_index, palette in enumerate(PALETTES):
        top = palette_index * palette_height
        draw.rectangle((0, top, width, top + palette_height), fill=palette["background"])
        draw.text(
            (margin, top + 10),
            f"{palette['name']}  ·  24 / 16 px",
            font=title_font,
            fill=palette["caption"],
        )
        for index, name in enumerate(names):
            row, column = divmod(index, columns)
            left = margin + column * tile_width
            tile_top = top + title_height + row * tile_height
            tile_box = (left + 4, tile_top + 3, left + tile_width - 4, tile_top + tile_height - 3)
            draw.rounded_rectangle(
                tile_box,
                radius=12,
                fill=palette["tile"],
                outline=palette["outline"],
                width=1,
            )
            source = (
                generator.OUTPUT / f"moos-{name}-symbolic.svg"
            ).read_text(encoding="utf-8")
            source = recolour(source, palette["roles"])
            large = render_svg(source, 24)
            small = render_svg(source, 16)
            sheet.paste(large, (left + 15, tile_top + 10), large)
            sheet.paste(small, (left + 51, tile_top + 14), small)
            draw.text(
                (left + 11, tile_top + 35),
                "24",
                font=size_font,
                fill=palette["caption"],
            )
            draw.text(
                (left + 50, tile_top + 35),
                "16",
                font=size_font,
                fill=palette["caption"],
            )
            caption = name if len(name) <= 14 else name[:13] + "…"
            caption_width = draw.textlength(caption, font=caption_font)
            draw.text(
                (left + (tile_width - caption_width) / 2, tile_top + 51),
                caption,
                font=caption_font,
                fill=palette["caption"],
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    print(f"rendered {len(names)} symbols at 24/16px to {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render_sheet(args.output)


if __name__ == "__main__":
    main()
