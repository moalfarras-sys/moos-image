#!/usr/bin/env python3
"""Generate original MoOS Nova visual assets from the official palette.

The script is deterministic and intentionally keeps all runtime output under
``system_files/usr/share``. Large wallpaper fields are constructed directly at
native 4K. Icons and installer artwork are rendered at 4x and downsampled once
with LANCZOS for clean edges.
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageCms, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files" / "usr" / "share"
LOGO = SHARE / "moos" / "moos-logo.png"

P = {
    "deepest": "#050A14",
    "navy": "#0B1220",
    "surface": "#111A2E",
    "raised": "#1A2740",
    "blue": "#2E7BFF",
    "blue_deep": "#1E4FD8",
    "cyan": "#22D3EE",
    "ice": "#7DEBFF",
    "violet": "#8B5CF6",
    "violet_deep": "#6D28D9",
    "magenta": "#C026D3",
    "light": "#EEF3FB",
    "white": "#FFFFFF",
    "text": "#E6EDF7",
    "secondary": "#9FB0C9",
    "success": "#34D399",
    "warning": "#FBBF24",
    "error": "#F87171",
}

RESAMPLE = Image.Resampling.LANCZOS


def stable_srgb_profile() -> bytes:
    """Return Pillow's standard sRGB profile with a fixed ICC creation date.

    LittleCMS writes the current second into bytes 24..35 of an otherwise
    identical profile. Normalizing only that ICC header field keeps every PNG
    standards-compliant while making repeated generator runs byte-for-byte.
    """

    profile = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    profile[24:36] = struct.pack(">6H", 2026, 1, 1, 0, 0, 0)
    return bytes(profile)


SRGB = stable_srgb_profile()


def rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*rgb(value), alpha)


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        path,
        format="PNG",
        optimize=True,
        compress_level=9,
        icc_profile=SRGB,
    )


def save_jpeg(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(
        path,
        format="JPEG",
        quality=92,
        optimize=True,
        progressive=True,
        subsampling=0,
        icc_profile=SRGB,
    )


def vertical_gradient(size: tuple[int, int], stops: list[tuple[float, str]]) -> Image.Image:
    width, height = size
    positions = np.array([s[0] for s in stops], dtype=np.float32)
    colors = np.array([rgb(s[1]) for s in stops], dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)
    rows = np.empty((height, 3), dtype=np.float32)
    for channel in range(3):
        rows[:, channel] = np.interp(y, positions, colors[:, channel])
    data = np.broadcast_to(rows[:, None, :], (height, width, 3)).astype(np.uint8)
    return Image.fromarray(data, "RGB").convert("RGBA")


def gradient_fill(mask: Image.Image, stops: list[tuple[float, str]]) -> Image.Image:
    fill = vertical_gradient(mask.size, stops)
    fill.putalpha(mask)
    return fill


def radial_glow(
    base: Image.Image,
    center: tuple[float, float],
    radius: float,
    color: str,
    strength: float,
) -> Image.Image:
    width, height = base.size
    yy, xx = np.ogrid[:height, :width]
    cx, cy = center[0] * width, center[1] * height
    r = radius * max(width, height)
    distance = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / max(r, 1.0)
    alpha = np.clip(1.0 - distance, 0.0, 1.0) ** 2 * strength
    overlay = np.empty((height, width, 4), dtype=np.uint8)
    overlay[..., :3] = rgb(color)
    overlay[..., 3] = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    return Image.alpha_composite(base.convert("RGBA"), Image.fromarray(overlay, "RGBA"))


def bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    count: int = 220,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(count + 1):
        t = index / count
        u = 1.0 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def glowing_path(
    base: Image.Image,
    points: list[tuple[float, float]],
    color: str,
    width: int,
    alpha: int,
    blur: int,
) -> None:
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.line(points, fill=rgba(color, alpha), width=width, joint="curve")
    base.alpha_composite(glow.filter(ImageFilter.GaussianBlur(blur)))
    crisp = Image.new("RGBA", base.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(crisp)
    cd.line(points, fill=rgba(color, min(255, alpha + 45)), width=max(1, width // 5), joint="curve")
    base.alpha_composite(crisp)


def add_particles(base: Image.Image, seed: int, dark: bool, amount: int = 90) -> None:
    rng = random.Random(seed)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    width, height = base.size
    palette = [P["cyan"], P["blue"], P["violet"]]
    for _ in range(amount):
        x = rng.randint(int(width * 0.04), int(width * 0.96))
        y = rng.randint(int(height * 0.05), int(height * 0.90))
        radius = rng.choice([1, 1, 2, 2, 3])
        opacity = rng.randint(24, 105) if dark else rng.randint(12, 52)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rgba(rng.choice(palette), opacity))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.35)))


def place_logo(base: Image.Image, dark: bool, scale: float, position: tuple[float, float]) -> None:
    master = Image.open(LOGO).convert("RGBA")
    target = max(256, int(min(base.size) * scale))
    emblem = master.resize((target, target), RESAMPLE)
    alpha = emblem.getchannel("A").point(lambda value: int(value * (0.84 if dark else 0.62)))
    emblem.putalpha(alpha)
    x = int(base.width * position[0] - target / 2)
    y = int(base.height * position[1] - target / 2)
    halo = Image.new("RGBA", base.size, (0, 0, 0, 0))
    halo_mask = Image.new("L", base.size, 0)
    hm = ImageDraw.Draw(halo_mask)
    pad = int(target * 0.09)
    hm.ellipse((x - pad, y - pad, x + target + pad, y + target + pad), fill=110 if dark else 46)
    halo_color = Image.new("RGBA", base.size, rgba(P["blue"], 255))
    halo_color.putalpha(halo_mask.filter(ImageFilter.GaussianBlur(max(24, target // 7))))
    base.alpha_composite(halo_color)
    base.alpha_composite(emblem, (x, y))


def wallpaper_master(style: str, dark: bool) -> Image.Image:
    size = (3840, 2160)
    if dark:
        image = vertical_gradient(size, [(0.0, P["deepest"]), (0.52, P["navy"]), (1.0, P["deepest"])])
        glow_strength = 0.34
    else:
        image = vertical_gradient(size, [(0.0, P["white"]), (0.55, P["light"]), (1.0, P["white"])])
        glow_strength = 0.13

    if style == "aurora":
        image = radial_glow(image, (0.23, 0.26), 0.55, P["cyan"], glow_strength)
        image = radial_glow(image, (0.72, 0.20), 0.50, P["violet"], glow_strength * 0.78)
        image = radial_glow(image, (0.54, 0.76), 0.42, P["blue"], glow_strength * 0.62)
        ribbons = [
            ((-180, 1680), (650, 140), (1260, 210), (1800, 1360), P["cyan"], 145),
            ((330, 2190), (990, 720), (1800, 10), (2360, 1260), P["blue"], 128),
            ((980, 2230), (1710, 870), (2590, 80), (3150, 1140), P["violet"], 112),
            ((1900, 2210), (2430, 1100), (3440, 360), (4080, 970), P["cyan"], 72),
        ]
        for p0, p1, p2, p3, color, width in ribbons:
            glowing_path(image, bezier(p0, p1, p2, p3), color, width, 48 if dark else 24, width // 2)
        place_logo(image, dark, 0.29, (0.78, 0.55))
        add_particles(image, 1107, dark, 110)

    elif style == "deep":
        image = radial_glow(image, (0.70, 0.52), 0.55, P["blue"], glow_strength * 0.88)
        image = radial_glow(image, (0.78, 0.45), 0.34, P["violet"], glow_strength * 0.62)
        orbit = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(orbit)
        cx, cy = 2780, 1090
        for idx, (color, start, span) in enumerate(
            [(P["cyan"], 196, 226), (P["blue"], 32, 238), (P["violet"], 116, 242), (P["ice"], 228, 166)]
        ):
            rx = 540 + idx * 155
            ry = 410 + idx * 106
            box = (cx - rx, cy - ry, cx + rx, cy + ry)
            draw.arc(box, start=start, end=start + span, fill=rgba(color, 110 if dark else 55), width=10 + idx * 4)
        image.alpha_composite(orbit.filter(ImageFilter.GaussianBlur(28)))
        image.alpha_composite(orbit)
        place_logo(image, dark, 0.31, (0.72, 0.52))
        add_particles(image, 2026, dark, 78)

    elif style == "pulse":
        image = radial_glow(image, (0.50, 0.88), 0.60, P["violet"], glow_strength * 0.72)
        image = radial_glow(image, (0.38, 0.72), 0.47, P["blue"], glow_strength * 0.78)
        for index in range(11):
            y0 = 1450 + index * 54
            amplitude = 235 - index * 12
            points = []
            for x in range(-80, 3921, 14):
                taper = math.exp(-((x - 1940) / 1680) ** 2)
                y = y0 - math.sin((x / 360.0) + index * 0.37) * amplitude * taper
                points.append((x, y))
            color = [P["cyan"], P["blue"], P["violet"]][index % 3]
            glowing_path(image, points, color, 14 + (10 - index), 70 if dark else 33, 18)
        horizon = bezier((-120, 1670), (900, 1330), (2800, 1280), (4030, 1620))
        glowing_path(image, horizon, P["cyan"], 34, 105 if dark else 46, 58)
        place_logo(image, dark, 0.27, (0.50, 0.42))
        add_particles(image, 4404, dark, 64)
    else:
        raise ValueError(f"Unknown wallpaper style: {style}")

    return image.convert("RGB")


def crop_variant(master: Image.Image, target: tuple[int, int]) -> Image.Image:
    target_ratio = target[0] / target[1]
    source_ratio = master.width / master.height
    if source_ratio > target_ratio:
        crop_width = round(master.height * target_ratio)
        left = (master.width - crop_width) // 2
        crop = master.crop((left, 0, left + crop_width, master.height))
    else:
        crop_height = round(master.width / target_ratio)
        top = (master.height - crop_height) // 2
        crop = master.crop((0, top, master.width, top + crop_height))
    return crop.resize(target, RESAMPLE)


def generate_wallpapers() -> None:
    packages = {
        "NovaAurora": "aurora",
        "NovaDeep": "deep",
        "NovaPulse": "pulse",
    }
    for package, style in packages.items():
        root = SHARE / "wallpapers" / package / "contents"
        dark_preview: Image.Image | None = None
        for dark in (False, True):
            master = wallpaper_master(style, dark)
            folder = root / ("images_dark" if dark else "images")
            save_png(master, folder / "3840x2160.png")
            save_png(crop_variant(master, (3440, 1440)), folder / "3440x1440.png")
            save_png(crop_variant(master, (2560, 1600)), folder / "2560x1600.png")
            if dark:
                dark_preview = master.resize((1920, 1080), RESAMPLE)
        assert dark_preview is not None
        save_png(dark_preview, root / "screenshot.png")


def icon_base(accent: str) -> Image.Image:
    size = (1024, 1024)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    outer = Image.new("L", size, 0)
    od = ImageDraw.Draw(outer)
    od.rounded_rectangle((52, 44, 972, 980), radius=218, fill=255)

    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow.putalpha(outer.filter(ImageFilter.GaussianBlur(38)))
    shadow_color = Image.new("RGBA", size, (0, 0, 0, 128))
    shadow_color.putalpha(shadow.getchannel("A").point(lambda value: int(value * 0.65)))
    image.alpha_composite(shadow_color, (0, 18))

    shell = gradient_fill(
        outer,
        [(0.0, P["ice"]), (0.17, P["cyan"]), (0.56, P["blue"]), (1.0, accent)],
    )
    image.alpha_composite(shell)

    inner = Image.new("L", size, 0)
    ImageDraw.Draw(inner).rounded_rectangle((96, 132, 928, 902), radius=166, fill=255)
    panel = gradient_fill(inner, [(0.0, P["raised"]), (0.42, P["surface"]), (1.0, P["deepest"])])
    image.alpha_composite(panel)

    highlight = Image.new("RGBA", size, (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    hd.ellipse((118, 120, 906, 535), fill=(255, 255, 255, 26))
    highlight.putalpha(ImageChops.multiply(highlight.getchannel("A"), inner))
    image.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(9)))

    outline = ImageDraw.Draw(image)
    outline.rounded_rectangle((52, 44, 972, 980), radius=218, outline=rgba(P["white"], 220), width=8)
    outline.rounded_rectangle((96, 132, 928, 902), radius=166, outline=rgba(P["white"], 195), width=8)
    outline.line((176, 930, 848, 930), fill=rgba(P["violet"], 210), width=10)
    return image


def symbol_layer(mask: Image.Image, stops: list[tuple[float, str]], glow_color: str) -> Image.Image:
    layer = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    glow = Image.new("RGBA", mask.size, rgba(glow_color, 255))
    glow.putalpha(mask.filter(ImageFilter.GaussianBlur(34)).point(lambda value: int(value * 0.55)))
    layer.alpha_composite(glow)
    layer.alpha_composite(gradient_fill(mask, stops))
    return layer


def draw_hardware(image: Image.Image) -> None:
    mask = Image.new("L", image.size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((322, 292, 702, 710), radius=86, fill=255)
    for p in (352, 430, 508, 586, 664):
        d.rounded_rectangle((250, p - 18, 326, p + 18), radius=12, fill=255)
        d.rounded_rectangle((698, p - 18, 774, p + 18), radius=12, fill=255)
        d.rounded_rectangle((p - 18, 220, p + 18, 296), radius=12, fill=255)
        d.rounded_rectangle((p - 18, 706, p + 18, 782), radius=12, fill=255)
    image.alpha_composite(symbol_layer(mask, [(0.0, P["ice"]), (0.50, P["cyan"]), (1.0, P["blue"])], P["cyan"]))
    d = ImageDraw.Draw(image)
    d.arc((392, 390, 632, 630), 205, 338, fill=rgba(P["text"], 245), width=22)
    d.line((512, 512, 592, 448), fill=rgba(P["violet"], 255), width=24)
    d.ellipse((494, 494, 530, 530), fill=rgba(P["white"], 255))


def draw_compat(image: Image.Image) -> None:
    # Cross-platform compatibility: a desktop "tiles" panel (left) bridged by a
    # two-way arrow to a rounded "app" panel (right, mobile) carrying a run
    # glyph. Reads as interop/"run Windows & Android apps", and its silhouette
    # is deliberately UNLIKE the updater's circular loop so the two never blur.
    left = Image.new("L", image.size, 0)
    right = Image.new("L", image.size, 0)
    dl, dr = ImageDraw.Draw(left), ImageDraw.Draw(right)
    # Left: 2x2 grid of rounded tiles (desktop surface). Geometry upsized 22%
    # after the v19 audit: the old group filled only ~55% of the tile and read
    # thin at 16-32px next to its siblings.
    cell, gap, lx, ly = 112, 32, 207, 394
    for gx in (0, 1):
        for gy in (0, 1):
            x0 = lx + gx * (cell + gap)
            y0 = ly + gy * (cell + gap)
            dl.rounded_rectangle((x0, y0, x0 + cell, y0 + cell), radius=26, fill=255)
    # Right: a single rounded app tile (mobile surface).
    dr.rounded_rectangle((617, 411, 832, 626), radius=58, fill=255)
    image.alpha_composite(symbol_layer(left, [(0.0, P["ice"]), (0.5, P["cyan"]), (1.0, P["blue"])], P["cyan"]))
    image.alpha_composite(symbol_layer(right, [(0.0, P["blue"]), (1.0, P["violet"])], P["violet"]))
    d = ImageDraw.Draw(image)
    # Two-way bridge arrow between the panels = bidirectional compatibility.
    y = 518
    d.line((497, y, 588, y), fill=rgba(P["text"], 245), width=30)
    d.polygon([(478, y), (520, y - 38), (520, y + 38)], fill=rgba(P["text"], 245))
    d.polygon([(607, y), (565, y - 38), (565, y + 38)], fill=rgba(P["text"], 245))
    # A small run/play glyph inside the app tile hints "launch apps here".
    d.polygon([(695, 478), (695, 558), (761, 518)], fill=rgba(P["white"], 235))


def draw_updater(image: Image.Image) -> None:
    first = Image.new("L", image.size, 0)
    second = Image.new("L", image.size, 0)
    a, b = ImageDraw.Draw(first), ImageDraw.Draw(second)
    a.arc((260, 260, 764, 764), 188, 352, fill=255, width=72)
    a.polygon([(747, 290), (824, 356), (714, 388)], fill=255)
    b.arc((260, 260, 764, 764), 8, 172, fill=255, width=72)
    b.polygon([(277, 734), (200, 668), (310, 636)], fill=255)
    image.alpha_composite(symbol_layer(first, [(0.0, P["cyan"]), (1.0, P["blue"])], P["cyan"]))
    image.alpha_composite(symbol_layer(second, [(0.0, P["blue"]), (1.0, P["violet"])], P["violet"]))
    d = ImageDraw.Draw(image)
    d.line((512, 618, 512, 410), fill=rgba(P["text"], 250), width=28)
    d.polygon([(512, 360), (450, 438), (574, 438)], fill=rgba(P["text"], 250))
    d.rounded_rectangle((438, 624, 586, 652), radius=14, fill=rgba(P["success"], 245))


def draw_recovery(image: Image.Image) -> None:
    shield = Image.new("L", image.size, 0)
    d = ImageDraw.Draw(shield)
    d.polygon([(512, 224), (742, 322), (710, 630), (512, 790), (314, 630), (282, 322)], fill=255)
    image.alpha_composite(symbol_layer(shield, [(0.0, P["ice"]), (0.46, P["blue"]), (1.0, P["violet"])], P["violet"]))
    inner = Image.new("RGBA", image.size, (0, 0, 0, 0))
    di = ImageDraw.Draw(inner)
    di.arc((374, 390, 650, 660), 75, 323, fill=rgba(P["text"], 250), width=30)
    di.polygon([(364, 470), (388, 374), (452, 446)], fill=rgba(P["text"], 250))
    di.line((512, 470, 512, 548, 568, 588), fill=rgba(P["text"], 250), width=26, joint="curve")
    image.alpha_composite(inner)


def star_points(cx: int, cy: int, outer: int, inner: int, count: int = 4) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(count * 2):
        angle = -math.pi / 2 + index * math.pi / count
        radius = outer if index % 2 == 0 else inner
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    return points


def draw_welcome(image: Image.Image) -> None:
    main = Image.new("L", image.size, 0)
    d = ImageDraw.Draw(main)
    d.polygon(star_points(512, 498, 250, 72, 4), fill=255)
    d.polygon(star_points(690, 330, 76, 24, 4), fill=230)
    d.polygon(star_points(330, 670, 60, 20, 4), fill=210)
    image.alpha_composite(symbol_layer(main, [(0.0, P["white"]), (0.38, P["cyan"]), (0.72, P["blue"]), (1.0, P["violet"])], P["cyan"]))
    ring = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ring)
    d.arc((280, 310, 744, 730), 18, 144, fill=rgba(P["violet"], 170), width=15)
    d.arc((280, 310, 744, 730), 198, 320, fill=rgba(P["cyan"], 170), width=15)
    image.alpha_composite(ring.filter(ImageFilter.GaussianBlur(8)))
    image.alpha_composite(ring)


def generate_icons() -> None:
    specs = {
        "moos-hardware": (P["blue_deep"], draw_hardware),
        "moos-compat": (P["violet"], draw_compat),
        "moos-updater": (P["blue"], draw_updater),
        "moos-recovery": (P["violet_deep"], draw_recovery),
        "moos-welcome": (P["violet"], draw_welcome),
    }
    sizes = (16, 22, 24, 32, 48, 64, 128, 256)
    for name, (accent, painter) in specs.items():
        master = icon_base(accent)
        painter(master)
        for size in sizes:
            icon = master.resize((size, size), RESAMPLE)
            save_png(icon, SHARE / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{name}.png")

    # Mo AI has a separate state-aware source and pixel-tuned small masters.
    # Keep it owned by generate_moai_companion.py so a general icon refresh
    # cannot collapse the 16/22/24/32 px exports back to a naive resize.


def generate_installer() -> None:
    out = SHARE / "anaconda" / "pixmaps"
    canonical = SHARE / "moos" / "branding" / "anaconda"
    work = vertical_gradient((800, 3200), [(0.0, P["deepest"]), (0.48, P["navy"]), (1.0, P["surface"])])
    work = radial_glow(work, (0.18, 0.18), 0.44, P["cyan"], 0.28)
    work = radial_glow(work, (0.76, 0.74), 0.55, P["violet"], 0.20)
    for index, color in enumerate((P["cyan"], P["blue"], P["violet"])):
        points = bezier((-80, 2500 + index * 170), (220, 1900), (560, 1520 + index * 90), (900, 760 + index * 120))
        glowing_path(work, points, color, 34 - index * 6, 82, 52)
    edge = Image.new("RGBA", work.size, (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    ed.line((796, 0, 796, 3200), fill=rgba(P["cyan"], 210), width=4)
    work.alpha_composite(edge.filter(ImageFilter.GaussianBlur(16)))
    work.alpha_composite(edge)
    sidebar_bg = work.resize((200, 800), RESAMPLE)
    save_png(sidebar_bg, out / "sidebar-bg.png")
    save_png(sidebar_bg, canonical / "sidebar-bg.png")

    logo_canvas = Image.new("RGBA", (800, 640), (0, 0, 0, 0))
    logo = Image.open(LOGO).convert("RGBA").resize((520, 520), RESAMPLE)
    glow_mask = Image.new("L", logo_canvas.size, 0)
    ImageDraw.Draw(glow_mask).ellipse((118, 42, 682, 606), fill=132)
    glow = Image.new("RGBA", logo_canvas.size, rgba(P["blue"], 255))
    glow.putalpha(glow_mask.filter(ImageFilter.GaussianBlur(84)))
    logo_canvas.alpha_composite(glow)
    logo_canvas.alpha_composite(logo, (140, 58))
    sidebar_logo = logo_canvas.resize((200, 160), RESAMPLE)
    save_png(sidebar_logo, out / "sidebar-logo.png")
    save_png(sidebar_logo, canonical / "sidebar-logo.png")

    top = vertical_gradient((3600, 256), [(0.0, P["raised"]), (0.52, P["surface"]), (1.0, P["navy"])])
    top = radial_glow(top, (0.15, 0.10), 0.44, P["cyan"], 0.18)
    top = radial_glow(top, (0.92, 0.55), 0.50, P["violet"], 0.15)
    line = Image.new("RGBA", top.size, (0, 0, 0, 0))
    ImageDraw.Draw(line).line((0, 250, 3600, 250), fill=rgba(P["blue"], 180), width=6)
    top.alpha_composite(line.filter(ImageFilter.GaussianBlur(14)))
    top.alpha_composite(line)
    topbar_bg = top.resize((900, 64), RESAMPLE)
    save_png(topbar_bg, out / "topbar-bg.png")
    save_png(topbar_bg, canonical / "topbar-bg.png")


def generate_grub() -> None:
    # Render at 2x and downsample once. The central-left menu-safe zone remains
    # intentionally quiet; the emblem sits in the lower-right corner.
    size = (3840, 2160)
    image = vertical_gradient(size, [(0.0, P["deepest"]), (0.66, P["navy"]), (1.0, P["deepest"])])
    image = radial_glow(image, (0.88, 0.82), 0.42, P["blue"], 0.30)
    image = radial_glow(image, (0.95, 0.78), 0.28, P["violet"], 0.22)
    horizon = bezier((-200, 1960), (1180, 1840), (2780, 1920), (4100, 1510))
    glowing_path(image, horizon, P["cyan"], 18, 86, 46)
    place_logo(image, True, 0.235, (0.86, 0.74))
    add_particles(image, 707, True, 34)
    save_png(image.convert("RGB").resize((1920, 1080), RESAMPLE), SHARE / "moos" / "grub-theme" / "background.png")


def generate_sddm() -> None:
    theme = SHARE / "sddm" / "themes" / "moos-nova"
    background = Image.open(theme / "backgrounds" / "nova-dark.png").convert("RGB")
    save_jpeg(background, theme / "backgrounds" / "default.jpg")
    source = ROOT / "artwork" / "nova-session-icon.svg"
    for name in (
        "awesome",
        "bspwm",
        "cinnamon",
        "default",
        "dwm",
        "gnome",
        "hyprland",
        "i3",
        "moos",
        "niri",
        "plasma",
        "qtile",
        "sway",
        "ubuntu",
        "xfce",
    ):
        target = theme / "icons" / "sessions" / f"{name}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


FRAME_POSITIONS = (
    "top",
    "topright",
    "right",
    "bottomright",
    "bottom",
    "bottomleft",
    "left",
    "topleft",
    "center",
)


def _frame_id(prefix: str, position: str) -> str:
    return f"{prefix}-{position}" if prefix else position


def _frame_gradients(
    prefix: str,
    x: int,
    y: int,
    fill: str,
    fill_opacity: float,
    border: str,
    border_opacity: float,
    border_size: int = 10,
    center_size: int = 32,
) -> list[str]:
    """Return gradients for one rounded FrameSvg atlas frame.

    Each edge fades from a one-pixel Nova accent into the glass surface. The
    corner gradients are centered on the inner corner, so the accent follows
    the actual rounded silhouette instead of producing a square neon block.
    """

    key = prefix.replace("+", "_plus_").replace("-", "_")
    inner_left = x + border_size
    inner_top = y + border_size
    inner_right = inner_left + center_size
    inner_bottom = inner_top + center_size
    outer_right = inner_right + border_size
    outer_bottom = inner_bottom + border_size
    fo = f"{fill_opacity:.3f}"
    bo = f"{border_opacity:.3f}"

    def linear(name: str, x1: int, y1: int, x2: int, y2: int, reverse: bool = False) -> str:
        stops = (
            f'<stop offset="0" stop-color="{fill}" stop-opacity="{fo}"/>\n'
            f'      <stop offset="0.72" stop-color="{fill}" stop-opacity="{fo}"/>\n'
            f'      <stop offset="0.90" stop-color="{border}" stop-opacity="{bo}"/>\n'
            f'      <stop offset="1" stop-color="{border}" stop-opacity="{bo}"/>'
        )
        if reverse:
            stops = (
                f'<stop offset="0" stop-color="{border}" stop-opacity="{bo}"/>\n'
                f'      <stop offset="0.10" stop-color="{border}" stop-opacity="{bo}"/>\n'
                f'      <stop offset="0.28" stop-color="{fill}" stop-opacity="{fo}"/>\n'
                f'      <stop offset="1" stop-color="{fill}" stop-opacity="{fo}"/>'
            )
        return (
            f'    <linearGradient id="{key}-{name}" gradientUnits="userSpaceOnUse" '
            f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">\n'
            f"      {stops}\n"
            "    </linearGradient>"
        )

    def radial(name: str, cx: int, cy: int) -> str:
        return (
            f'    <radialGradient id="{key}-{name}" gradientUnits="userSpaceOnUse" '
            f'cx="{cx}" cy="{cy}" r="{border_size}">\n'
            f'      <stop offset="0" stop-color="{fill}" stop-opacity="{fo}"/>\n'
            f'      <stop offset="0.72" stop-color="{fill}" stop-opacity="{fo}"/>\n'
            f'      <stop offset="0.90" stop-color="{border}" stop-opacity="{bo}"/>\n'
            f'      <stop offset="1" stop-color="{border}" stop-opacity="{bo}"/>\n'
            "    </radialGradient>"
        )

    return [
        linear("top-gradient", inner_left, inner_top, inner_left, y, reverse=False),
        linear("right-gradient", inner_right, inner_top, outer_right, inner_top, reverse=False),
        linear("bottom-gradient", inner_left, inner_bottom, inner_left, outer_bottom, reverse=False),
        linear("left-gradient", inner_left, inner_top, x, inner_top, reverse=False),
        radial("topleft-gradient", inner_left, inner_top),
        radial("topright-gradient", inner_right, inner_top),
        radial("bottomright-gradient", inner_right, inner_bottom),
        radial("bottomleft-gradient", inner_left, inner_bottom),
    ]


def _frame_elements(
    prefix: str,
    x: int,
    y: int,
    fill: str,
    fill_opacity: float,
    border: str,
    border_opacity: float,
    border_size: int = 10,
    center_size: int = 32,
) -> tuple[list[str], list[str]]:
    """Create a complete rounded nine-part Plasma FrameSvg frame."""

    key = prefix.replace("+", "_plus_").replace("-", "_")
    b = border_size
    c = center_size
    il = x + b
    it = y + b
    ir = il + c
    ib = it + c
    right = ir + b
    bottom = ib + b
    fo = f"{fill_opacity:.3f}"
    gradients = _frame_gradients(prefix, x, y, fill, fill_opacity, border, border_opacity, b, c)
    elements = [
        f'  <rect id="{_frame_id(prefix, "top")}" x="{il}" y="{y}" width="{c}" height="{b}" fill="url(#{key}-top-gradient)"/>',
        f'  <path id="{_frame_id(prefix, "topright")}" d="M {ir},{y} A {b},{b} 0 0 1 {right},{it} L {ir},{it} Z" fill="url(#{key}-topright-gradient)"/>',
        f'  <rect id="{_frame_id(prefix, "right")}" x="{ir}" y="{it}" width="{b}" height="{c}" fill="url(#{key}-right-gradient)"/>',
        f'  <path id="{_frame_id(prefix, "bottomright")}" d="M {right},{ib} A {b},{b} 0 0 1 {ir},{bottom} L {ir},{ib} Z" fill="url(#{key}-bottomright-gradient)"/>',
        f'  <rect id="{_frame_id(prefix, "bottom")}" x="{il}" y="{ib}" width="{c}" height="{b}" fill="url(#{key}-bottom-gradient)"/>',
        f'  <path id="{_frame_id(prefix, "bottomleft")}" d="M {x},{ib} A {b},{b} 0 0 0 {il},{bottom} L {il},{ib} Z" fill="url(#{key}-bottomleft-gradient)"/>',
        f'  <rect id="{_frame_id(prefix, "left")}" x="{x}" y="{it}" width="{b}" height="{c}" fill="url(#{key}-left-gradient)"/>',
        f'  <path id="{_frame_id(prefix, "topleft")}" d="M {il},{y} L {il},{it} L {x},{it} A {b},{b} 0 0 1 {il},{y} Z" fill="url(#{key}-topleft-gradient)"/>',
        f'  <rect id="{_frame_id(prefix, "center")}" x="{il}" y="{it}" width="{c}" height="{c}" fill="{fill}" fill-opacity="{fo}"/>',
    ]
    return gradients, elements


def _margin_hints(prefix: str, x: int, y: int, margin: float) -> list[str]:
    """Create the four exact FrameSvg margin hint IDs."""

    value = f"{margin:g}"
    return [
        f'  <rect id="{prefix}-hint-top-margin" x="{x + 8}" y="{y}" width="2" height="{value}" fill="#FF00FF" fill-opacity="0.004"/>',
        f'  <rect id="{prefix}-hint-right-margin" x="{x + 18}" y="{y + 8}" width="{value}" height="2" fill="#FF00FF" fill-opacity="0.004"/>',
        f'  <rect id="{prefix}-hint-bottom-margin" x="{x + 8}" y="{y + 18}" width="2" height="{value}" fill="#FF00FF" fill-opacity="0.004"/>',
        f'  <rect id="{prefix}-hint-left-margin" x="{x}" y="{y + 8}" width="{value}" height="2" fill="#FF00FF" fill-opacity="0.004"/>',
    ]


def _plasma_svg_document(width: int, height: int, gradients: list[str], elements: list[str]) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        "  <!-- Original MoOS Nova art. Frame IDs follow the official Plasma 6.7.2 contract. -->\n"
        "  <style id=\"current-color-scheme\" type=\"text/css\">\n"
        f"    .ColorScheme-Background {{ color: {P['surface']}; }}\n"
        f"    .ColorScheme-Highlight {{ color: {P['blue']}; }}\n"
        f"    .ColorScheme-Text {{ color: {P['text']}; }}\n"
        "  </style>\n"
        "  <defs>\n"
        + "\n".join(gradients)
        + "\n  </defs>\n"
        + "\n".join(elements)
        + "\n</svg>\n"
    )


def generate_plasma_style() -> None:
    """Generate the first low-risk original Nova Plasma FrameSvg surfaces.

    Button and view-item contracts were verified against libplasma v6.7.2.
    Top-level panel/dialog SVGs remain inherited until these state surfaces are
    live-tested in Plasma; a malformed top-level mask can clip an entire popup.
    """

    widgets = SHARE / "plasma" / "desktoptheme" / "Nova" / "widgets"
    widgets.mkdir(parents=True, exist_ok=True)

    view_states = (
        ("normal", P["surface"], 0.004, P["secondary"], 0.08),
        ("hover", P["raised"], 0.88, P["cyan"], 0.62),
        ("selected", P["blue_deep"], 0.72, P["ice"], 0.88),
        ("selected+hover", P["violet_deep"], 0.78, P["cyan"], 0.96),
    )
    gradients: list[str] = []
    elements: list[str] = []
    for index, (prefix, fill, fill_opacity, border, border_opacity) in enumerate(view_states):
        frame_gradients, frame_elements = _frame_elements(
            prefix,
            10 + index * 64,
            10,
            fill,
            fill_opacity,
            border,
            border_opacity,
        )
        gradients.extend(frame_gradients)
        elements.extend(frame_elements)
    elements.append('  <rect id="hint-tile-center" x="270" y="10" width="1" height="1" fill="#FF00FF" fill-opacity="0.004"/>')
    (widgets / "viewitem.svg").write_text(
        _plasma_svg_document(282, 74, gradients, elements),
        encoding="utf-8",
        newline="\n",
    )

    button_states = (
        ("shadow", P["deepest"], 0.12, P["deepest"], 0.28),
        ("normal", P["surface"], 0.94, P["secondary"], 0.24),
        ("mask-normal", P["white"], 1.0, P["white"], 1.0),
        ("hover", P["raised"], 0.96, P["cyan"], 0.74),
        ("focus", P["surface"], 0.004, P["blue"], 0.98),
        ("pressed", P["blue_deep"], 0.94, P["violet"], 0.96),
        ("toolbutton-hover", P["raised"], 0.72, P["cyan"], 0.62),
        ("toolbutton-focus", P["surface"], 0.004, P["blue"], 0.96),
        ("toolbutton-pressed", P["violet_deep"], 0.80, P["cyan"], 0.90),
    )
    gradients = []
    elements = []
    for index, (prefix, fill, fill_opacity, border, border_opacity) in enumerate(button_states):
        col = index % 3
        row = index // 3
        frame_gradients, frame_elements = _frame_elements(
            prefix,
            10 + col * 64,
            10 + row * 64,
            fill,
            fill_opacity,
            border,
            border_opacity,
        )
        gradients.extend(frame_gradients)
        elements.extend(frame_elements)

    margins = {
        "shadow": 3.0,
        "normal": 6.0,
        "hover": 0.001,
        "focus": 2.0,
        "pressed": 6.0,
        "toolbutton-hover": 4.0,
        "toolbutton-focus": 2.0,
        "toolbutton-pressed": 4.0,
    }
    for index, (prefix, margin) in enumerate(margins.items()):
        elements.extend(_margin_hints(prefix, 208 + (index % 2) * 30, 10 + (index // 2) * 38, margin))
    elements.extend(
        [
            '  <rect id="normal-hint-compose-over-border" x="270" y="166" width="1" height="1" fill="#FF00FF" fill-opacity="0.004"/>',
            '  <rect id="pressed-hint-compose-over-border" x="274" y="166" width="1" height="1" fill="#FF00FF" fill-opacity="0.004"/>',
        ]
    )
    (widgets / "button.svg").write_text(
        _plasma_svg_document(282, 202, gradients, elements),
        encoding="utf-8",
        newline="\n",
    )


def glass_panel(base: Image.Image, box: tuple[int, int, int, int], radius: int, opacity: int = 206) -> None:
    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, radius=radius, fill=opacity)
    panel = Image.new("RGBA", base.size, rgba(P["surface"], 255))
    panel.putalpha(mask)
    base.alpha_composite(panel)
    edge = ImageDraw.Draw(base)
    edge.rounded_rectangle(box, radius=radius, outline=rgba(P["white"], 30), width=2)


def generate_previews() -> None:
    out = SHARE / "plasma" / "look-and-feel" / "org.moos.nova" / "contents" / "previews"
    wallpaper = Image.open(
        SHARE / "wallpapers" / "NovaHorizon" / "contents" / "images_dark" / "3840x2160.png"
    ).convert("RGBA").resize((1920, 1080), RESAMPLE)
    desktop = wallpaper.copy()

    # Edge-attached status bar and floating application dock mirror the v14
    # shell while remaining a static, dependency-free preview.
    top = Image.new("RGBA", desktop.size, (0, 0, 0, 0))
    ImageDraw.Draw(top).rectangle((0, 0, 1920, 34), fill=rgba(P["surface"], 218))
    ImageDraw.Draw(top).line((0, 34, 1920, 34), fill=rgba(P["cyan"], 70), width=1)
    desktop.alpha_composite(top)
    logo = Image.open(LOGO).convert("RGBA").resize((27, 27), RESAMPLE)
    desktop.alpha_composite(logo, (13, 4))
    status = ImageDraw.Draw(desktop)
    for x in (1810, 1842, 1874):
        status.ellipse((x, 12, x + 10, 22), fill=rgba(P["text"], 210))

    dock_box = (585, 970, 1335, 1055)
    glass_panel(desktop, dock_box, 26, 224)
    icon_names = (
        "moos-moai",
        "moos-welcome",
        "moos-hardware",
        "moos-compat",
        "moos-updater",
        "moos-recovery",
    )
    x = 675
    for name in icon_names:
        icon = Image.open(SHARE / "icons" / "hicolor" / "64x64" / "apps" / f"{name}.png").convert("RGBA")
        desktop.alpha_composite(icon, (x, 981))
        x += 104
    active = ImageDraw.Draw(desktop)
    active.rounded_rectangle((686, 1044, 728, 1048), radius=2, fill=rgba(P["cyan"], 235))

    save_jpeg(desktop.convert("RGB"), out / "fullscreenpreview.jpg")
    save_png(desktop.convert("RGB").resize((600, 337), RESAMPLE).convert("RGBA"), out / "preview.png")

    lock = Image.open(SHARE / "sddm" / "themes" / "moos-nova" / "backgrounds" / "nova-dark.png").convert("RGBA")
    lock = lock.resize((1200, 674), RESAMPLE).filter(ImageFilter.GaussianBlur(8))
    shade = Image.new("RGBA", lock.size, rgba(P["deepest"], 90))
    lock.alpha_composite(shade)
    glass_panel(lock, (420, 128, 780, 562), 48, 220)
    emblem = Image.open(LOGO).convert("RGBA").resize((150, 150), RESAMPLE)
    lock.alpha_composite(emblem, (525, 175))
    ld = ImageDraw.Draw(lock)
    ld.rounded_rectangle((490, 390, 710, 442), radius=26, fill=rgba(P["raised"], 235), outline=rgba(P["blue"], 170), width=3)
    ld.ellipse((674, 403, 700, 429), fill=rgba(P["cyan"], 235))
    save_png(lock.resize((600, 337), RESAMPLE), out / "lockscreen.png")

    splash = vertical_gradient((600, 338), [(0.0, P["deepest"]), (1.0, P["navy"])])
    emblem = Image.open(LOGO).convert("RGBA").resize((190, 190), RESAMPLE)
    splash.alpha_composite(emblem, (205, 54))
    sd = ImageDraw.Draw(splash)
    sd.rounded_rectangle((215, 284, 385, 292), radius=4, fill=rgba(P["raised"], 255))
    sd.rounded_rectangle((215, 284, 336, 292), radius=4, fill=rgba(P["cyan"], 255))
    save_png(splash.convert("RGB").resize((300, 169), RESAMPLE), out / "splash.png")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icons", action="store_true", help="Generate Nova app icons")
    parser.add_argument("--installer", action="store_true", help="Generate Anaconda artwork")
    parser.add_argument("--wallpapers", action="store_true", help="Generate Nova wallpaper set")
    parser.add_argument("--grub", action="store_true", help="Generate GRUB artwork")
    parser.add_argument("--sddm", action="store_true", help="Generate safe SDDM fallback and session art")
    parser.add_argument("--previews", action="store_true", help="Generate Plasma Global Theme previews")
    parser.add_argument("--plasma-style", action="store_true", help="Generate low-risk Nova Plasma FrameSvg surfaces")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = (
        args.icons
        or args.installer
        or args.wallpapers
        or args.grub
        or args.sddm
        or args.previews
        or args.plasma_style
    )
    if args.icons or not selected:
        generate_icons()
    if args.installer or not selected:
        generate_installer()
    if args.wallpapers or not selected:
        generate_wallpapers()
    if args.grub or not selected:
        generate_grub()
    if args.sddm or not selected:
        generate_sddm()
    if args.previews or not selected:
        generate_previews()
    if args.plasma_style or not selected:
        generate_plasma_style()


if __name__ == "__main__":
    main()
