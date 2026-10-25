#!/usr/bin/env python3
"""Fixed MoOS boot identity, independent of every desktop theme and wallpaper.

The approved hero is untouched. A small procedural brand backdrop and shaped
Arabic greeting need no video decoder, font discovery or user data at boot.
"""

from pathlib import Path

import hashlib
import json
from math import exp
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "system_files/usr/share/plymouth/themes/moos/boot-backdrop.png"
SIZE = (1920, 1080)
FONT = Path("/usr/share/fonts/ibm-plex-sans-arabic-fonts/IBMPlexSansArabic-Regular.otf")
CAPTION = "مرحبًا بك"


def make_backdrop() -> Image.Image:
    width, height = SIZE
    # Precompute the horizontal terms; use the standard library so source
    # verification and asset generation need only the existing Pillow tool.
    x = [i / (width - 1) for i in range(width)]
    square = lambda value: value * value
    hx = [square((v - .5) / .30) for v in x]
    cx = [square((v - .24) / .46) for v in x]
    bx = [square((v - .78) / .38) for v in x]
    pixels = bytearray(width * height * 3)
    offset = 0
    for row in range(height):
        y = row / (height - 1)
        hy = square((y - .53) / .56)
        cy = square((y - .87) / .28)
        by = square((y - .81) / .36)
        for column in range(width):
            halo = exp(-(hx[column] + hy) * 1.8)
            cyan = exp(-(cx[column] + cy) * 1.5)
            blue = exp(-(bx[column] + by) * 1.7)
            pixels[offset] = round(10 + 8 * halo + 3 * cyan + 5 * blue)
            pixels[offset + 1] = round(16 + 11 * halo + 12 * cyan + 3 * blue)
            pixels[offset + 2] = round(27 + 19 * halo + 13 * cyan + 19 * blue)
            offset += 3
    return Image.frombytes("RGB", SIZE, bytes(pixels))


def make_caption() -> Image.Image:
    font = ImageFont.truetype(str(FONT), 80, layout_engine=ImageFont.Layout.RAQM)
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = draw.textbbox((0, 0), CAPTION, font=font, direction="rtl", language="ar")
    image = Image.new("RGBA", (box[2] - box[0] + 16, box[3] - box[1] + 16))
    ImageDraw.Draw(image).text((8 - box[0], 8 - box[1]), CAPTION, font=font,
                              direction="rtl", language="ar", fill="#DCEAF6")
    return image


def main() -> None:
    backdrop = make_backdrop()
    backdrop.save(OUTPUT, format="PNG", optimize=True)
    caption = make_caption()
    target = OUTPUT.with_name("welcome-ar.png")
    caption.save(target, optimize=True)
    provenance = dict(caption=CAPTION, font="IBM Plex Sans Arabic Regular",
                      fontSHA256=hashlib.sha256(FONT.read_bytes()).hexdigest(),
                      size=list(caption.size), pixelSHA256=hashlib.sha256(caption.tobytes()).hexdigest())
    (ROOT / "artwork/moos-design/boot-caption.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote fixed boot backdrop and shaped Arabic greeting: {OUTPUT.parent}")


if __name__ == "__main__":
    main()
