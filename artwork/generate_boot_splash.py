#!/usr/bin/env python3
"""Render the MoOS premium boot-splash SPRITES for the Plymouth Script theme.

The animation is driven by moos.script at boot — it MOVES a few small sprites
(rotates the energy head around the ring, scales/fades the logo, breathes the
glow), rather than playing hundreds of pre-baked frames. That keeps the theme a
few hundred KB instead of tens of MB, so the initramfs stays small and boot
stays fast. The logo is his 1024px master, never redrawn/recoloured/cropped.

Sprites written to system_files/usr/share/plymouth/themes/moos/:
  logo.png   — the crisp MoOS mark (his master, downscaled to 512)
  ring.png   — a faint circular track the energy head runs on
  head.png   — the cyan→violet energy head (a glowing comet blob)
  glow.png   — a soft ambient bloom that sits behind the mark

Also writes artwork/boot-splash-grid.png (a static preview of the composed look).
Pure PIL, deterministic.
"""
from __future__ import annotations
import math, pathlib
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOGO = ROOT / "system_files/usr/share/moos/moos-logo.png"
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"
ART = ROOT / "artwork"

CYAN = (34, 211, 238)
BLUE = (46, 123, 255)
VIOLET = (139, 92, 246)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def make_logo():
    img = Image.open(LOGO).convert("RGBA").resize((512, 512), Image.LANCZOS)
    img.save(THEME / "logo.png")
    return img


def make_glow():
    S = 512
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    # radial bloom: bright blue-cyan core fading out
    for r in range(int(S * 0.48), 0, -2):
        t = r / (S * 0.48)
        col = _lerp(CYAN, BLUE, t)
        a = int(46 * (1 - t) ** 1.7)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (a,))
    img = img.filter(ImageFilter.GaussianBlur(10))
    img.save(THEME / "glow.png")


def make_ring():
    S = 720
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = S * 0.06
    d.ellipse([m, m, S - m, S - m], outline=CYAN + (60,), width=3)
    img = img.filter(ImageFilter.GaussianBlur(1))
    img.save(THEME / "ring.png")


def make_head():
    """The energy head: a bright cyan core in a violet halo with a short trailing
    comet tail, so its motion around the ring reads as a comet, not a dot."""
    S = 220
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = S * 0.62, S / 2
    # tail: a fading violet→cyan streak to the left of the head
    for i in range(40):
        t = i / 39
        x = cx - t * S * 0.5
        rr = (1 - t) * S * 0.075 + 2
        col = _lerp(CYAN, VIOLET, t)
        a = int(150 * (1 - t) ** 1.5)
        d.ellipse([x - rr, cy - rr, x + rr, cy + rr], fill=col + (a,))
    # bright core
    for r in range(int(S * 0.16), 0, -1):
        t = r / (S * 0.16)
        col = _lerp((235, 250, 255), CYAN, t)
        a = int(255 * (1 - t) ** 1.2)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (a,))
    img = img.filter(ImageFilter.GaussianBlur(3))
    img.save(THEME / "head.png")


def preview():
    """A static composite so the look can be eyeballed without booting."""
    S = 720
    navy = (7, 11, 22)
    bg = Image.new("RGBA", (S, S), navy + (255,))
    glow = Image.open(THEME / "glow.png").resize((int(S * 0.6), int(S * 0.6)))
    bg.alpha_composite(glow, (int(S / 2 - glow.width / 2), int(S / 2 - glow.height / 2)))
    ring = Image.open(THEME / "ring.png")
    bg.alpha_composite(ring, (0, 0))
    head = Image.open(THEME / "head.png")
    # place head at top of ring
    hx, hy = S / 2, S * 0.08
    bg.alpha_composite(head, (int(hx - head.width / 2), int(hy - head.height / 2)))
    logo = Image.open(THEME / "logo.png").resize((int(S * 0.36), int(S * 0.36)))
    bg.alpha_composite(logo, (int(S / 2 - logo.width / 2), int(S / 2 - logo.height / 2)))
    bg.convert("RGB").save(ART / "boot-splash-grid.png")


def render():
    THEME.mkdir(parents=True, exist_ok=True)
    make_logo()
    make_glow()
    make_ring()
    make_head()
    preview()
    total = sum(p.stat().st_size for p in THEME.glob("*.png"))
    print(f"sprites -> {THEME}  (logo, ring, head, glow) total {total/1024:.0f} KiB")
    print(f"preview: {ART/'boot-splash-grid.png'}")


if __name__ == "__main__":
    render()
