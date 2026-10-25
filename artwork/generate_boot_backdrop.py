#!/usr/bin/env python3
"""Fixed MoOS boot identity, independent of every desktop theme and wallpaper.

The approved hero is untouched. A small procedural brand backdrop and shaped
Arabic greeting need no video decoder, font discovery or user data at boot.
"""

from pathlib import Path

import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "system_files/usr/share/plymouth/themes/moos/boot-backdrop.png"
SIZE = (1920, 1080)
FONT = Path("/usr/share/fonts/ibm-plex-sans-arabic-fonts/IBMPlexSansArabic-Regular.otf")
CAPTION = "مرحبًا بك"


def make_backdrop() -> Image.Image:
    width, height = SIZE
    y, x = np.mgrid[0:height, 0:width]
    x = x / (width - 1)
    y = y / (height - 1)
    halo = np.exp(-(((x - .5) / .30)**2 + ((y - .53) / .56)**2) * 1.8)
    cyan = np.exp(-(((x - .24) / .46)**2 + ((y - .87) / .28)**2) * 1.5)
    blue = np.exp(-(((x - .78) / .38)**2 + ((y - .81) / .36)**2) * 1.7)
    pixels = np.zeros((height, width, 3))
    for i, (base, a, b, c) in enumerate(((10, 8, 3, 5), (16, 11, 12, 3), (27, 19, 13, 19))):
        pixels[:, :, i] = base + a * halo + b * cyan + c * blue
    return Image.fromarray(np.rint(pixels).clip(0, 255).astype("uint8"))


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
