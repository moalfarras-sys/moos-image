"""v19 polish — fixes the two audited visual gaps:

1. Plymouth throbber: the old frames read as a generic light-gray ring. New
   design "Nova comet": a cyan->blue->violet gradient arc with a glowing
   near-white comet head sweeping a barely-there navy track, on transparency.
   60 frames, 96x96 (same contract as the old set), drawn 4x supersampled.

2. NovaHorizon LIGHT wallpaper: audited as washed-out/flat next to the dark
   variant. Enhance in place: richer saturation, a real cyan/violet horizon
   glow at the lower third, and a soft ice-blue grade so the field is not
   bare white. Geometry is proportional so all three sizes stay consistent.

Deterministic (no randomness) — safe to re-run.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files" / "usr" / "share"
PLY = SHARE / "plymouth" / "themes" / "moos"
HORIZON_LIGHT = SHARE / "wallpapers" / "NovaHorizon" / "contents" / "images"

CYAN = (34, 211, 238)
BLUE = (46, 123, 255)
VIOLET = (139, 92, 246)
HEAD = (224, 251, 255)
NAVY = (11, 18, 32)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient3(t: float):
    """cyan -> blue -> violet along the tail (t: 0 head .. 1 tail end)."""
    return lerp(CYAN, BLUE, t / 0.5) if t < 0.5 else lerp(BLUE, VIOLET, (t - 0.5) / 0.5)


def throbber_frame(angle_deg: float, size: int = 96, ss: int = 4) -> Image.Image:
    s = size * ss
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = s / 2
    r = s * 0.36
    width = s * 0.085

    # Barely-there navy track: reads as machined depth on the navy splash,
    # never as a light ring (the audited flaw of the old frames).
    d.arc(
        (cx - r, cy - r, cx + r, cy + r),
        0, 360, fill=(*NAVY, 110), width=round(width),
    )

    # Comet tail: 96 segments over 264 degrees, fading alpha + Nova gradient.
    tail_span = 264.0
    segs = 96
    for i in range(segs):
        t = i / (segs - 1)              # 0 = head, 1 = tail tip
        a0 = angle_deg - t * tail_span
        seg = tail_span / segs + 0.8    # slight overlap kills seams
        color = gradient3(t)
        alpha = round(255 * (1.0 - t) ** 1.6)
        d.arc(
            (cx - r, cy - r, cx + r, cy + r),
            a0 - seg, a0, fill=(*color, alpha), width=round(width),
        )

    # Glowing comet head.
    ha = math.radians(angle_deg)
    hx, hy = cx + r * math.cos(ha), cy + r * math.sin(ha)
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dg = ImageDraw.Draw(glow)
    gr = width * 1.9
    dg.ellipse((hx - gr, hy - gr, hx + gr, hy + gr), fill=(*CYAN, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s * 0.03)))
    hr = width * 0.62
    d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(*HEAD, 255))

    return img.resize((size, size), Image.Resampling.LANCZOS)


def regenerate_throbber() -> None:
    frames = sorted(PLY.glob("throbber-*.png"))
    n = len(frames) or 60
    for idx in range(n):
        # Start at 12 o'clock (-90°), sweep clockwise.
        ang = -90 + idx * (360.0 / n)
        throbber_frame(ang).save(PLY / f"throbber-{idx + 1:04d}.png")
    print(f"throbber: {n} Nova-comet frames written")


def radial_glow(size, center, radius, color, peak_alpha):
    w, h = size
    glow = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(glow)
    cx, cy, r = center[0] * w, center[1] * h, radius * min(w, h)
    steps = 48
    for i in range(steps, 0, -1):
        a = round(peak_alpha * (1 - i / steps) ** 2 * 255 / 255)
        rr = r * i / steps
        d.ellipse((cx - rr * 1.6, cy - rr, cx + rr * 1.6, cy + rr), fill=a)
    layer = Image.new("RGBA", (w, h), (*color, 0))
    layer.putalpha(glow.filter(ImageFilter.GaussianBlur(min(w, h) * 0.02)))
    return layer


def enhance_light(path: Path) -> None:
    img = Image.open(path).convert("RGB")
    img = ImageEnhance.Color(img).enhance(1.22)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = img.convert("RGBA")
    w, h = img.size
    # Real horizon presence at the lower third (the audited gap).
    img.alpha_composite(radial_glow((w, h), (0.42, 0.74), 0.55, CYAN, 52))
    img.alpha_composite(radial_glow((w, h), (0.68, 0.70), 0.38, VIOLET, 40))
    # Soft ice-blue grade from the top so the field is not bare white.
    grade = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dg = ImageDraw.Draw(grade)
    for y in range(h):
        t = y / h
        a = round(38 * max(0.0, 1 - t * 1.8))
        dg.line((0, y, w, y), fill=(199, 221, 248, a))
    img.alpha_composite(grade)
    img.convert("RGB").save(path)
    print(f"light wallpaper enhanced: {path.name} ({w}x{h})")


if __name__ == "__main__":
    regenerate_throbber()
    for p in sorted(HORIZON_LIGHT.glob("*.png")):
        enhance_light(p)
    print("DONE v19 polish")
