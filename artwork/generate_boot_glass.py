#!/usr/bin/env python3
"""Build the MoOS "Liquid Glass" boot layers (Blender + deterministic Pillow).

Owner steering 2026-11-19: a short, premium boot scene in Liquid Glass — keep
the MoOS mark itself, improve its rendering and the typography. This pipeline:

  1. renders the owner's high-detail vector master (artwork/logo) at 2048 px;
  2. cleans the trace speckle with an edge-preserving guided filter that keeps
     the design's own internal lines, and derives a bevel height map in which
     those lines become grooves (same silhouette, same colours);
  3. renders artwork/blender/moos_boot_glass.py headless into a PRIVATE work
     directory: the glass-coated emblem, a glass bezel, the sheen that flows
     over it and three liquid glass droplets;
  4. keys the light layers to straight alpha, sets the Meyar Sans wordmark
     letters and the Meyar Arabic captions (libraqm shaping), and writes the
     theme assets with provenance.

Usage:
    python3 artwork/generate_boot_glass.py --work test-results/blender-boot/glass
    python3 artwork/generate_boot_glass.py --work DIR --compose-only
    MOOS_BLENDER="blender" python3 artwork/generate_boot_glass.py --work DIR
    python3 artwork/generate_boot_glass.py --captions-only

--captions-only rewrites just the Meyar Arabic captions and their provenance:
an Arabic outline change reaches only the shaped captions, while every rendered
layer and the rest of the provenance stay byte-identical.

Output is source artwork. Native Plymouth pixels, image gates and a signed boot
remain separate proofs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"
SCENE = ROOT / "artwork/blender/moos_boot_glass.py"
LOGO_SVG = ROOT / "artwork/logo/MoOS_Logo_Vector_High_Detail.svg"
PROVENANCE = ROOT / "artwork/moos-design/boot-glass.json"
CAPTION_PROVENANCE = ROOT / "artwork/moos-design/boot-caption.json"
LATIN = ROOT / "system_files/usr/share/fonts/meyar/MeyarSans[wght].ttf"
ARABIC = ROOT / "system_files/usr/share/fonts/meyar/MeyarArabic-Regular.ttf"
DEFAULT_BLENDER = "flatpak run --unshare=network --die-with-parent org.blender.Blender"

HERO_SIZE = 640                  # intro1.png: the improved emblem
LENS_SIZE = 640                  # bezel/sheen cover 1.3x the emblem image
DROP_SIZE = 128
GLINT_SIZE = 96
WORDMARK = "MoOS"
LETTER_FILES = ("mark-letter-1.png", "mark-letter-2.png", "mark-letter-3.png", "mark-letter-4.png")
LETTER_FONT_PX = 132
LETTER_PAD = 0.08                # transparent margin, fraction of letter image height
CAPTIONS = {
    "welcome": ("مرحبًا بك", "welcome-ar.png"),
    "farewell": ("إلى اللقاء", "farewell-ar.png"),
}
CAPTION_FONT_PX = 104


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── numeric helpers (numpy only; no SciPy in the artwork toolchain) ─────────
def box(a, r, axis):
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode="edge"), axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def mean(a, r):
    return box(box(a, r, 0), r, 1)


def blur(a, sigma):
    r = max(1, int(round(sigma * 0.93)))
    for _ in range(3):
        a = mean(a, r)
    return a


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def guided(p, guide, r, eps):
    """He et al. guided filter: smooths texture, keeps the guide's edges."""
    m_i, m_p = mean(guide, r), mean(p, r)
    a = (mean(guide * p, r) - m_i * m_p) / (mean(guide * guide, r) - m_i * m_i + eps)
    b = m_p - a * m_i
    return mean(a, r) * guide + mean(b, r)


LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


# ── 1-2. emblem maps ────────────────────────────────────────────────────────
def emblem_maps(work: Path) -> dict:
    master = work / "logo-master-2048.png"
    subprocess.run(["magick", "-background", "none", "-density", "192", str(LOGO_SVG),
                    "-resize", "2048x2048", str(master)], check=True)
    im = np.asarray(Image.open(master).convert("RGBA")).astype(np.float32) / 255
    alpha = im[..., 3]
    ys, xs = np.nonzero(alpha > 0.5)
    cy, cx = (ys.min() + ys.max()) / 2, (xs.min() + xs.max()) / 2
    # The mark's radius is 0.96 of the square's half (EMBLEM_RADIUS in the scene).
    half = int(max(ys.max() - ys.min(), xs.max() - xs.min()) / 2 / 0.96)
    pad = 64
    canvas = np.zeros((2 * half + 2 * pad, 2 * half + 2 * pad, 4), np.float32)
    y0, x0 = int(cy - half) - pad, int(cx - half) - pad
    src = im[max(0, y0):y0 + canvas.shape[0], max(0, x0):x0 + canvas.shape[1]]
    canvas[max(0, -y0):max(0, -y0) + src.shape[0], max(0, -x0):max(0, -x0) + src.shape[1]] = src
    rgb, alpha = canvas[..., :3], canvas[..., 3]

    a_clean = smoothstep(0.32, 0.68, blur(alpha, 2.2))
    lum = rgb @ LUMA
    colour = np.stack([guided(rgb[..., i] * a_clean, lum * a_clean, 6, 2e-3) for i in range(3)], -1)
    colour = np.clip(colour / np.maximum(a_clean, 1e-4)[..., None], 0, 1)
    colour = np.where(a_clean[..., None] > 0.02, colour, 0)
    lum2 = colour @ LUMA
    colour = np.clip(lum2[..., None] + (colour - lum2[..., None]) * 1.10, 0, 1)

    edge = smoothstep(0.30, 1.0, blur(a_clean, 5.0))
    ribs = smoothstep(0.10, 0.42, blur(lum2, 2.0))
    dome = blur(a_clean, 60.0)
    height = (0.55 * edge * (0.35 + 0.65 * ribs) + 0.25 * blur(ribs * a_clean, 6.0)
              + 0.20 * dome) * a_clean
    height /= max(float(height.max()), 1e-6)

    maps = work / "maps"
    maps.mkdir(exist_ok=True)
    size = 1536
    rgba = (np.dstack([colour, a_clean]) * 255).round().astype(np.uint8)
    Image.fromarray(rgba, "RGBA").resize((size, size), Image.Resampling.LANCZOS) \
        .save(maps / "emblem-colour.png")
    Image.fromarray((height * 65535).round().astype(np.uint16)) \
        .resize((size, size), Image.Resampling.BILINEAR).save(maps / "emblem-height.png")
    return {"svgSHA256": sha256(LOGO_SVG.read_bytes()),
            "magick": subprocess.run(["magick", "-version"], capture_output=True, text=True)
            .stdout.splitlines()[0]}


# ── 3. Blender ──────────────────────────────────────────────────────────────
def run_blender(work: Path, samples: int, save_blend: bool) -> str:
    command = shlex.split(os.environ.get("MOOS_BLENDER", DEFAULT_BLENDER))
    command += ["-b", "--factory-startup", "-noaudio", "-P", str(SCENE), "--",
                "--out", str(work / "renders"), "--maps", str(work / "maps"),
                "--samples", str(samples)]
    if save_blend:
        command += ["--save-blend", str(work / "blend")]
    print("+", " ".join(shlex.quote(c) for c in command), flush=True)
    log = work / "blender.log"
    with log.open("w") as stream:
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
    text = log.read_text(errors="replace")
    # Blender exits 0 after a Python exception; require the completion marker.
    if result.returncode != 0 or "MOOS_GLASS_COMPLETE" not in text:
        sys.stderr.write(text[-4000:])
        raise SystemExit(f"Blender failed (exit {result.returncode}); log: {log}")
    return next((line.strip() for line in text.splitlines() if line.startswith("Blender ")),
                "Blender (version line absent)")


# ── 4. compose ──────────────────────────────────────────────────────────────
def keyed(rgb: np.ndarray) -> Image.Image:
    """Light rendered on black -> straight alpha; alpha = max(R, G, B)."""
    alpha = rgb.max(axis=2)
    alpha_out = np.clip((alpha - 2.0) * 255.0 / 253.0, 0, 255)
    colour = np.where(alpha[..., None] > 0, rgb * 255.0 / np.maximum(alpha, 1.0)[..., None], 0)
    out = np.dstack([np.clip(colour, 0, 255), alpha_out]).round().astype(np.uint8)
    out[alpha_out == 0] = 0
    return Image.fromarray(out, "RGBA")


def load_rgb(path: Path, size: int) -> np.ndarray:
    with Image.open(path) as source:
        return np.asarray(source.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)) \
            .astype(np.float32)


def crescent(rgb: np.ndarray) -> np.ndarray:
    """Let the dome's reflections fade towards the centre of the mark."""
    n = rgb.shape[0]
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    units = 2.6 / n
    r = np.hypot((x + 0.5 - n / 2) * units, (y + 0.5 - n / 2) * units) / (0.96 * 1.08)
    return rgb * smoothstep(0.42, 0.92, r)[..., None]


def glint() -> Image.Image:
    n = GLINT_SIZE
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) - (n - 1) / 2
    core = np.exp(-(x * x + y * y) / (2 * 2.4 ** 2))
    halo = 0.35 * np.exp(-(x * x + y * y) / (2 * 9.0 ** 2))
    rays = (np.exp(-np.abs(x) / 11.0) * np.exp(-(y * y) / (2 * 0.9 ** 2))
            + np.exp(-np.abs(y) / 11.0) * np.exp(-(x * x) / (2 * 0.9 ** 2)))
    light = np.clip(core + halo + 0.8 * rays, 0, 1)
    edge = smoothstep(n / 2, n / 2 - 8, np.maximum(np.abs(x), np.abs(y)))
    light *= edge
    tint = np.array([236, 252, 255], np.float32)
    return keyed(light[..., None] * tint)


def letters() -> list[Image.Image]:
    """One image per letter, all sharing the wordmark's ink rows and baseline.

    Width is the glyph advance plus LETTER_PAD x height on each side, so the
    script can butt the images together and add its own tracking.
    """
    font = ImageFont.truetype(str(LATIN), LETTER_FONT_PX)
    font.set_variation_by_name(b"Light")
    top = min(font.getbbox(ch)[1] for ch in WORDMARK)
    bottom = max(font.getbbox(ch)[3] for ch in WORDMARK)
    ink = bottom - top
    pad = round(ink * LETTER_PAD / (1 - 2 * LETTER_PAD))
    height = ink + 2 * pad
    gradient = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    light, cool = np.array([255, 255, 255], np.float32), np.array([196, 222, 255], np.float32)
    images = []
    for ch in WORDMARK:
        advance = round(font.getlength(ch))
        box_ = font.getbbox(ch)
        if box_[0] < -pad or box_[2] > advance + pad:
            raise SystemExit(f"glyph {ch!r} ink exceeds its padded advance")
        mask = Image.new("L", (advance + 2 * pad, height), 0)
        ImageDraw.Draw(mask).text((pad, pad - top), ch, font=font, fill=255)
        colour = light * (1 - gradient) + cool * gradient
        rgb = np.broadcast_to(colour[:, None, :], (height, advance + 2 * pad, 3))
        a = np.asarray(mask).astype(np.float32) * 0.97
        images.append(Image.fromarray(np.dstack([rgb, a]).round().astype(np.uint8), "RGBA"))
    return images


def caption(text: str) -> Image.Image:
    font = ImageFont.truetype(str(ARABIC), CAPTION_FONT_PX, layout_engine=ImageFont.Layout.RAQM)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    # The shaped ink box includes stacked marks (tanween above alef, hamza
    # below); a margin keeps them clear of the image edge.
    box_ = probe.textbbox((0, 0), text, font=font, direction="rtl", language="ar")
    top, bottom = box_[1], box_[3]
    pad = round((bottom - top) * 0.16)
    width, height = box_[2] - box_[0] + 2 * pad, bottom - top + 2 * pad
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).text((pad - box_[0], pad - top), text, font=font, fill=255,
                              direction="rtl", language="ar")
    rgb = np.empty((height, width, 3), np.float32)
    rgb[...] = (226, 238, 246)
    a = np.asarray(mask).astype(np.float32) * 0.92
    return Image.fromarray(np.dstack([rgb, a]).round().astype(np.uint8), "RGBA")


def write_captions() -> None:
    caption_records = {}
    for key, (text, name) in CAPTIONS.items():
        image = caption(text)
        image.save(THEME / name, optimize=True)
        caption_records[key] = dict(caption=text, size=list(image.size),
                                    pixelSHA256=sha256(image.tobytes()))

    welcome = caption_records["welcome"]
    CAPTION_PROVENANCE.write_text(json.dumps(dict(
        caption=welcome["caption"], font="Meyar Arabic Regular",
        fontSource=str(ARABIC.relative_to(ROOT)), fontSHA256=sha256(ARABIC.read_bytes()),
        shaping="Pillow libraqm (HarfBuzz/FriBiDi), direction rtl, language ar",
        size=welcome["size"], pixelSHA256=welcome["pixelSHA256"], captions=caption_records,
    ), ensure_ascii=False, indent=2) + "\n")


def theme_assets() -> dict:
    assets = {}
    for path in sorted(THEME.glob("*.png")):
        with Image.open(path) as image:
            assets[path.name] = dict(size=list(image.size), mode=image.mode,
                                     bytes=path.stat().st_size,
                                     decodedBytes=image.width * image.height * 4,
                                     sha256=sha256(path.read_bytes()))
    return assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--work", type=Path,
                        help="private real-disk directory, never the theme or /tmp")
    parser.add_argument("--samples", type=int, default=160)
    parser.add_argument("--compose-only", action="store_true")
    parser.add_argument("--save-blend", action="store_true")
    parser.add_argument("--captions-only", action="store_true",
                        help="rewrite only the Arabic captions and refresh the asset records")
    args = parser.parse_args()
    if args.captions_only:
        write_captions()
        record = json.loads(PROVENANCE.read_text())
        record["assets"] = theme_assets()
        PROVENANCE.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        return
    if args.work is None:
        parser.error("--work is required unless --captions-only is given")
    work = args.work.resolve()
    if THEME.resolve() in (work, *work.parents) or work == ROOT.resolve():
        raise SystemExit("refusing a work directory inside the theme or at the repository root")
    (work / "renders").mkdir(parents=True, exist_ok=True)
    if shutil.which("magick") is None:
        raise SystemExit("ImageMagick (magick) is required to rasterise the vector master")

    previous = json.loads(PROVENANCE.read_text()) if PROVENANCE.is_file() else {}
    source = emblem_maps(work)
    blender = previous.get("renderer", "unknown")
    if not args.compose_only:
        blender = run_blender(work, args.samples, args.save_blend)
    renders = work / "renders"

    with Image.open(renders / "emblem.png") as emblem:
        emblem.convert("RGBA").resize((HERO_SIZE, HERO_SIZE), Image.Resampling.LANCZOS) \
            .save(THEME / "intro1.png", optimize=True)
    keyed(load_rgb(renders / "bezel.png", LENS_SIZE)).save(THEME / "glass-bezel.png", optimize=True)
    keyed(crescent(load_rgb(renders / "sheen.png", LENS_SIZE))).save(THEME / "glass-sheen.png",
                                                                     optimize=True)
    for index in (1, 2, 3):
        keyed(load_rgb(renders / f"drop-{index}.png", DROP_SIZE)) \
            .save(THEME / f"glass-drop-{index}.png", optimize=True)
    glint().save(THEME / "glass-glint.png", optimize=True)
    for image, name in zip(letters(), LETTER_FILES):
        image.save(THEME / name, optimize=True)
    write_captions()
    assets = theme_assets()
    PROVENANCE.write_text(json.dumps(dict(
        schema=1,
        concept="MoOS Liquid Glass: droplets gather into a glass lens and the mark resolves",
        renderer=blender, scene=str(SCENE.relative_to(ROOT)), sceneSHA256=sha256(SCENE.read_bytes()),
        samples=args.samples if not args.compose_only else previous.get("samples"),
        logo=source, wordmarkFont="Meyar Sans Light", wordmarkFontSHA256=sha256(LATIN.read_bytes()),
        assets=assets,
    ), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: (v["size"], v["bytes"]) for k, v in assets.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
