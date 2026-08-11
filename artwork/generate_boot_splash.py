#!/usr/bin/env python3
"""Render the MoOS premium boot-splash SPRITES for the Plymouth Script theme.

The animation is driven by moos.script at boot — it MOVES a few small sprites
(rotates the energy head around the ring, gives the logo one finite scale/fade
entrance, and moves a few small energy sprites), rather than playing
hundreds of pre-baked frames. That keeps the theme ~1 MB instead of tens of MB,
so the initramfs stays small and boot stays fast. The logo is his 1024px master.

Sprites written to system_files/usr/share/plymouth/themes/moos/:
  logo.png     — the crisp MoOS mark at its native 1024 px master size
  ring.png     — primary circular track the energy head runs on
  ring2.png    — secondary inner orbital ring for 3D parallax depth
  head.png     — the cyan→violet energy head (a glowing comet blob)
  glow.png     — a soft ambient bloom that sits behind the mark
  particle.png — small energy sprite for 3D elliptical particle orbits
  pulse.png    — radial shockwave ring for periodic pulse waves

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
    img = Image.open(LOGO).convert("RGBA").resize((1024, 1024), Image.LANCZOS)
    img.save(THEME / "logo.png")
    return img


def make_glow():
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    # radial bloom: bright blue-cyan core fading out
    for r in range(int(S * 0.48), 0, -2):
        t = r / (S * 0.48)
        col = _lerp(CYAN, BLUE, t)
        a = int(46 * (1 - t) ** 1.7)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (a,))
    img = img.filter(ImageFilter.GaussianBlur(20))
    img.save(THEME / "glow.png")


def make_ring():
    # 0.62 of a 2160 px 4K frame is 1339 px. A 1440 px source therefore
    # downscales on the reference display instead of Plymouth enlarging a
    # 720 px ring and softening its edge.
    S = 1440
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = S * 0.06
    d.ellipse([m, m, S - m, S - m], outline=CYAN + (60,), width=5)
    img = img.filter(ImageFilter.GaussianBlur(2))
    img.save(THEME / "ring.png")


def make_ring2():
    """Inner secondary ring for 3D parallax depth."""
    S = 1440
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = S * 0.12
    d.ellipse([m, m, S - m, S - m], outline=VIOLET + (80,), width=4)
    img = img.filter(ImageFilter.GaussianBlur(2))
    img.save(THEME / "ring2.png")


def make_head():
    """The energy head: a bright cyan core in a violet halo with a short trailing
    comet tail, so its motion around the ring reads as a comet, not a dot."""
    S = 320
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
    img = img.filter(ImageFilter.GaussianBlur(4))
    img.save(THEME / "head.png")


def make_particle():
    """Small energy particle for 3D elliptical orbits."""
    S = 96
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    for r in range(int(S * 0.45), 0, -1):
        t = r / (S * 0.45)
        col = _lerp((240, 253, 255), CYAN, t)
        a = int(220 * (1 - t) ** 1.8)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (a,))
    img = img.filter(ImageFilter.GaussianBlur(2))
    img.save(THEME / "particle.png")


def make_pulse():
    """Pulse wave ring for expanding shockwave effect."""
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = S * 0.10
    d.ellipse([m, m, S - m, S - m], outline=CYAN + (120,), width=6)
    img = img.filter(ImageFilter.GaussianBlur(4))
    img.save(THEME / "pulse.png")


def preview():
    """A static composite so the look can be eyeballed without booting."""
    S = 720
    graphite = (20, 25, 28)
    bg = Image.new("RGBA", (S, S), graphite + (255,))
    glow = Image.open(THEME / "glow.png").resize((int(S * 0.6), int(S * 0.6)))
    bg.alpha_composite(glow, (int(S / 2 - glow.width / 2), int(S / 2 - glow.height / 2)))
    ring = Image.open(THEME / "ring.png").resize((S, S), Image.LANCZOS)
    bg.alpha_composite(ring, (0, 0))
    ring2 = Image.open(THEME / "ring2.png").resize((S, S), Image.LANCZOS)
    bg.alpha_composite(ring2, (0, 0))
    head = Image.open(THEME / "head.png").resize((220, 220), Image.LANCZOS)
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
    make_ring2()
    make_head()
    make_particle()
    make_pulse()
    preview()
    total = sum(p.stat().st_size for p in THEME.glob("*.png"))
    print(f"sprites -> {THEME}  (logo, ring, ring2, head, glow, particle, pulse) total {total/1024:.0f} KiB")
    print(f"preview: {ART/'boot-splash-grid.png'}")


if __name__ == "__main__":
    render()
