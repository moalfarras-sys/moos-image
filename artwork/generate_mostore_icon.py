#!/usr/bin/env python3
"""Compatibility entry point for the unified MoOS application-icon generator.

The canonical Mo Store vector now lives in ``generate_moos_app_icons.py`` with
the rest of the first-party family. Keeping this historical command as a
delegate prevents an old maintenance note from silently restoring a competing
store icon.

Usage: python generate_mostore_icon.py   # writes into system_files hicolor dirs
"""
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
HICOLOR = REPO / "system_files/usr/share/icons/hicolor"
# Two stems, one artwork: `moos-store` is the standalone Mo Store app's icon
# (org.moos.store.desktop — the moos- prefix is what verify_identity.py demands
# of every org.moos.* launcher); `mo-store` remains for the hidden Discover
# engine entry that legacy configs may still reference.
NAMES = ("moos-store", "mo-store")
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# UI2 palette
GRAPHITE_TOP = (44, 56, 62)     # #2C383E raised
GRAPHITE_BOT = (20, 25, 28)     # #14191C canvas
TURQUOISE = (78, 215, 200)      # #4ED7C8 primary
TURQUOISE_HI = (168, 241, 232)  # #A8F1E8 luminous
INK = (18, 22, 25)


def render(px: int) -> Image.Image:
    # Supersample for crisp edges at small sizes.
    s = px * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded tile with a vertical graphite gradient.
    margin = int(s * 0.06)
    radius = int(s * 0.235)
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (1, s), (0, 0, 0, 0))
    for y in range(s):
        t = y / max(1, s - 1)
        r = int(GRAPHITE_TOP[0] + (GRAPHITE_BOT[0] - GRAPHITE_TOP[0]) * t)
        g = int(GRAPHITE_TOP[1] + (GRAPHITE_BOT[1] - GRAPHITE_TOP[1]) * t)
        b = int(GRAPHITE_TOP[2] + (GRAPHITE_BOT[2] - GRAPHITE_TOP[2]) * t)
        grad.putpixel((0, y), (r, g, b, 255))
    grad = grad.resize((s, s))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [margin, margin, s - margin, s - margin], radius=radius, fill=255)
    tile.paste(grad, (0, 0), mask)

    # Soft turquoise inner glow, lower-centre (matches the desktop's tidal glow).
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([int(s*0.28), int(s*0.5), int(s*0.72), int(s*0.95)],
               fill=TURQUOISE + (70,))
    glow = glow.filter(ImageFilter.GaussianBlur(int(s*0.06)))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a)))
    tile = Image.alpha_composite(tile, Image.composite(glow, Image.new("RGBA",(s,s),(0,0,0,0)), mask))

    img = Image.alpha_composite(img, tile)
    d = ImageDraw.Draw(img)

    # One-pixel inner top highlight (the UI2 glass tell).
    hl = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle(
        [margin, margin, s - margin, s - margin], radius=radius,
        outline=(255, 255, 255, 40), width=max(1, s // 220))
    img = Image.alpha_composite(img, hl)
    d = ImageDraw.Draw(img)

    # The shopping-bag mark, centred, turquoise.
    cx = s // 2
    bag_w = int(s * 0.40)
    bag_h = int(s * 0.34)
    bx0 = cx - bag_w // 2
    by0 = int(s * 0.40)
    bx1 = cx + bag_w // 2
    by1 = by0 + bag_h
    bag_r = int(bag_w * 0.16)
    lw = max(2, int(s * 0.028))

    # Bag body (rounded), turquoise outline with a faint fill.
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=bag_r,
                        outline=TURQUOISE, width=lw,
                        fill=(TURQUOISE[0], TURQUOISE[1], TURQUOISE[2], 30))
    # Handle arc.
    hw = int(bag_w * 0.42)
    hx0 = cx - hw // 2
    hx1 = cx + hw // 2
    hy0 = by0 - int(bag_h * 0.42)
    hy1 = by0 + int(bag_h * 0.20)
    d.arc([hx0, hy0, hx1, hy1], start=180, end=360, fill=TURQUOISE, width=lw)

    # The MoOS spark on the bag — an elegant tapered four-point star in luminous
    # mint (the same "spark" language as Mo AI), drawn as two crossed diamonds so
    # the points are pointed, not a plain plus.
    spx, spy = cx, int((by0 + by1) / 2)
    v = int(bag_w * 0.20)   # vertical reach
    h = int(bag_w * 0.20)   # horizontal reach
    waist = int(bag_w * 0.055)
    star = [
        (spx, spy - v), (spx + waist, spy - waist),
        (spx + h, spy), (spx + waist, spy + waist),
        (spx, spy + v), (spx - waist, spy + waist),
        (spx - h, spy), (spx - waist, spy - waist),
    ]
    d.polygon(star, fill=TURQUOISE_HI)

    return img.resize((px, px), Image.LANCZOS)


def main():
    subprocess.run(
        [sys.executable, str(REPO / "artwork/generate_moos_app_icons.py")],
        check=True,
    )


if __name__ == "__main__":
    main()
