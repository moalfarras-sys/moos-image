#!/usr/bin/env python3
"""Render the non-sequence sprites of the MoOS Plymouth boot theme.

WHERE THE ANIMATION COMES FROM
    The boot intro is no longer synthesised here. It is a frame sequence cut
    from the owner's rendered logo sting by artwork/build_boot_frames.py — a
    plasma ring ignites, the mark's arcs tear out of it and rotate into place,
    the solid mark lands on a reflective floor and the MoOS wordmark fades up.
    That has real 3D rotation, plasma and a floor reflection in it; the previous
    version of this file tried to approximate the same idea by moving sprites
    (a ghost mark, six angular wedges, orbiting particles) and the result was
    recognisably a synthesis rather than the render.

    The splash comes to rest on the sequence's own last frame. An earlier cut
    crossfaded into a high-resolution still rebuilt from a separate reference
    render; the owner rejected it — the two renders do not match closely enough
    for the swap to be invisible, and a splash that visibly changes its own
    artwork at the end is worse than a soft one.

    So this file now produces only what the sequence does NOT carry:

      logo.png     the mark on its own. Still required: build.sh copies it over
                   Fedora's spinner watermark and then gates that the two are
                   byte-identical, which is what keeps the Fedora wordmark out
                   of the fallback splash.
      glow / ring / head
                   the three small sprites moos.script uses for the SLOW-BOOT
                   cue only — a soft breath and, after several seconds, a faint
                   orbiting head. A fast boot never shows them.

    Pure PIL and numpy, deterministic.

USAGE
    python artwork/build_boot_frames.py     # the intro sequence, from the video
    python artwork/generate_boot_splash.py  # this file
"""
from __future__ import annotations

import math
import pathlib

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOGO = ROOT / "system_files/usr/share/moos/moos-logo.png"
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"
ART = ROOT / "artwork"

CYAN = (34, 211, 238)
BLUE = (46, 123, 255)
VIOLET = (139, 92, 246)

# Sprites the theme used to ship and no longer does. Listed so a rebuild in a
# working tree that still has them removes them, instead of leaving a couple of
# megabytes of dead weight to be copied into every initramfs.
RETIRED = (
    "arc1", "arc2", "arc3", "arc4", "arc5", "arc6",
    "logo_ghost", "halo", "field", "wordmark", "ring2", "particle", "pulse",
    "settled",
)


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ── the mark, for the watermark gate ─────────────────────────────────────────
def make_logo():
    """logo.png — the canonical mark.

    Kept as the plain trace, NOT the boot render. build.sh copies this file over
    /usr/share/plymouth/themes/spinner/watermark.png and gates that the two
    match; that watermark is what Fedora's fallback splash shows, so it wants
    the flat, legible mark rather than a glossy hero render. The boot screen
    itself never draws this file any more — it draws the sequence.
    """
    img = Image.open(LOGO).convert("RGBA").resize((1024, 1024), Image.LANCZOS)
    img.save(THEME / "logo.png", optimize=True)
    return img


def _intro_frames() -> list[pathlib.Path]:
    """The intro sequence in playback order.

    Sorted NUMERICALLY. The files are intro1..intro32 without zero padding, so a
    plain lexical sort would order them 1, 10, 11, ... 2, 20 and report the wrong
    frame geometry.
    """
    fs = list(THEME.glob("intro*.png"))
    if not fs:
        raise SystemExit("FATAL: no intro frames — run artwork/build_boot_frames.py first")
    return sorted(fs, key=lambda p: int("".join(c for c in p.stem if c.isdigit())))


# ── the slow-boot cue ────────────────────────────────────────────────────────
def make_glow():
    """glow.png — the halo that breathes under the mark on a slow boot.

    Two-tone, cyan core through blue to a violet rim, the same run the mark's
    own colour has, so it reads as light coming off the mark rather than a grey
    disc behind it.
    """
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = S / 2
    for r in range(int(S * 0.49), 0, -2):
        t = r / (S * 0.49)
        col = _lerp(CYAN, BLUE, min(1.0, t * 1.45)) if t < 0.68 \
            else _lerp(BLUE, VIOLET, (t - 0.68) / 0.32)
        a = int(150 * (1 - t) ** 2.1)
        d.ellipse([c - r, c - r, c + r, c + r], fill=col + (a,))
    img.filter(ImageFilter.GaussianBlur(28)).save(THEME / "glow.png", optimize=True)


def make_ring():
    """ring.png — the track the slow-boot head runs on. Deliberately faint."""
    S = 1440
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = S * 0.06
    d.ellipse([m, m, S - m, S - m], outline=CYAN + (60,), width=5)
    img.filter(ImageFilter.GaussianBlur(2)).save(THEME / "ring.png", optimize=True)


def make_head():
    """head.png — a small comet: bright core, violet halo, short trailing tail."""
    S = 320
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = S * 0.62, S / 2
    for i in range(40):
        t = i / 39
        x = cx - t * S * 0.5
        rr = (1 - t) * S * 0.075 + 2
        d.ellipse([x - rr, cy - rr, x + rr, cy + rr],
                  fill=_lerp(CYAN, VIOLET, t) + (int(150 * (1 - t) ** 1.5),))
    for r in range(int(S * 0.16), 0, -1):
        t = r / (S * 0.16)
        d.ellipse([cx - r, cy - r, cx + r, cy + r],
                  fill=_lerp((235, 250, 255), CYAN, t) + (int(255 * (1 - t) ** 1.2),))
    img.filter(ImageFilter.GaussianBlur(4)).save(THEME / "head.png", optimize=True)


def sweep_retired() -> int:
    n = 0
    for name in RETIRED:
        p = THEME / f"{name}.png"
        if p.exists():
            p.unlink()
            n += 1
    return n


def render():
    THEME.mkdir(parents=True, exist_ok=True)
    make_logo()
    make_glow()
    make_ring()
    make_head()
    gone = sweep_retired()

    frames = _intro_frames()
    seq = sum(p.stat().st_size for p in frames)
    other = sum(p.stat().st_size for p in THEME.glob("*.png")) - seq
    print(f"theme -> {THEME}")
    fw, fh = Image.open(frames[0]).size
    print(f"  intro   : {len(frames)} frames, {fw}x{fh} each, {seq/1024:.0f} KiB")
    print(f"  cue     : glow, ring, head    (slow boots only)")
    print(f"  logo    : kept for the spinner-watermark gate in build.sh")
    if gone:
        print(f"  removed : {gone} retired sprite(s) from the previous synthesised reveal")
    print(f"  total   : {(seq + other)/1024:.0f} KiB")
    print(f"  aspect  : {fw/fh:.4f}   <- moos.script INTRO_ASPECT must match")


if __name__ == "__main__":
    render()
