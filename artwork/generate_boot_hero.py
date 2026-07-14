#!/usr/bin/env python3
"""generate_boot_hero.py — compose the MoOS Plymouth boot hero.

The premium boot look is the brand mark as the HERO: the MoOS emblem centered
and large, the "MoOS" wordmark beneath it, on transparent so Plymouth's
two-step plugin lays it over the flat UI2-graphite background. The turquoise
throbber ring sits lower as the loading indicator (positioned in the .plymouth
config, not baked here).

Deterministic: same inputs -> same bytes. Source is the 1024px master emblem;
the wordmark is rendered from a bundled/plain sans at a fixed size. Run this to
regenerate system_files/usr/share/plymouth/themes/moos-nova/watermark.png.

Usage:
    python generate_boot_hero.py [--out PATH] [--preview PATH] [--font PATH]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

REPO = Path(__file__).resolve().parent.parent
EMBLEM = REPO / "system_files/usr/share/pixmaps/moos-logo.png"
OUT = REPO / "system_files/usr/share/plymouth/themes/moos-nova/watermark.png"

# UI2 text token — the wordmark reads as the same near-white as desktop text.
TEXT_RGB = (232, 241, 239)          # #E8F1EF
PRIMARY_RGB = (78, 215, 200)        # #4ED7C8 turquoise, for the hairline accent

# Canvas and layout (px). two-step draws at NATIVE size (no resolution scaling),
# so this is the literal on-screen size. Tuned compact so the hero reads well
# from 768p laptops (where 470px is ~61% height) up to 4K (crisp, if smaller) —
# the standard two-step tradeoff every immutable distro lives with.
W, H = 640, 470
EMBLEM_PX = 300                     # emblem square
GAP = 26                           # emblem -> wordmark
WORDMARK_PX = 66                   # cap height target for "MoOS"
TRACKING = 6                       # extra px between glyphs


def load_font(explicit: str | None, size: int) -> ImageFont.FreeTypeFont:
    candidates = [explicit] if explicit else []
    candidates += [
        # Brand font first if the build ever vendors it beside this script.
        str(REPO / "artwork/fonts/IBMPlexSans-Medium.ttf"),
        "C:/Windows/Fonts/seguisb.ttf",     # Segoe UI Semibold
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/ibm-plex/IBMPlexSans-Medium.ttf",
        "DejaVuSans.ttf",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return ImageFont.truetype(c, size)
    # Last resort: PIL default (bitmap) — still produces a valid image.
    return ImageFont.load_default()


def draw_tracked(draw, xy, text, font, fill, tracking):
    """Draw text with extra per-glyph spacing; return total width."""
    x, y = xy
    total = 0
    widths = []
    for ch in text:
        w = draw.textlength(ch, font=font)
        widths.append(w)
        total += w + tracking
    total -= tracking
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking
    return total


def compose(font_path: str | None) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Emblem, high-quality downscale from the 1024px master, with a soft glow so
    # it lifts off the graphite instead of sitting flat on it.
    emblem = Image.open(EMBLEM).convert("RGBA").resize(
        (EMBLEM_PX, EMBLEM_PX), Image.LANCZOS)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ex = (W - EMBLEM_PX) // 2
    ey = 24
    glow.paste(emblem, (ex, ey), emblem)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    glow = Image.eval(glow, lambda a: int(a * 0.55))
    canvas = Image.alpha_composite(canvas, glow)
    canvas.paste(emblem, (ex, ey), emblem)

    draw = ImageDraw.Draw(canvas)

    # Wordmark, tracked and centered under the emblem.
    font = load_font(font_path, WORDMARK_PX)
    text = "MoOS"
    # measure with tracking
    tmp = Image.new("RGBA", (10, 10))
    td = ImageDraw.Draw(tmp)
    tw = sum(td.textlength(c, font=font) + TRACKING for c in text) - TRACKING
    ascent, descent = font.getmetrics()
    wy = ey + EMBLEM_PX + GAP
    draw_tracked(draw, ((W - tw) / 2, wy), text, font, TEXT_RGB, TRACKING)

    # A short turquoise hairline under the wordmark — one restrained accent that
    # ties the blue/purple brand emblem to the desktop's turquoise.
    line_w = int(tw * 0.42)
    lx = (W - line_w) // 2
    ly = wy + ascent + 20
    draw.rounded_rectangle([lx, ly, lx + line_w, ly + 3], radius=2, fill=PRIMARY_RGB)

    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--preview", default="")
    ap.add_argument("--font", default="")
    args = ap.parse_args()

    hero = compose(args.font or None)
    hero.save(args.out)
    print(f"wrote {args.out} ({hero.size[0]}x{hero.size[1]})")

    if args.preview:
        # Flatten onto graphite to preview how it reads at boot.
        bg = Image.new("RGBA", hero.size, (20, 25, 28, 255))  # #14191C
        Image.alpha_composite(bg, hero).convert("RGB").save(args.preview)
        print(f"wrote preview {args.preview}")


if __name__ == "__main__":
    main()
