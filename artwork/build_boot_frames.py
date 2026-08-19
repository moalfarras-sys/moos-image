#!/usr/bin/env python3
"""Turn the owner's rendered MoOS logo animation into the Plymouth boot intro.

THE DECISION THIS FILE ENCODES
    The owner supplied a rendered 10 s logo sting: a plasma ring ignites, the
    mark's arcs tear out of it and rotate into place, the solid mark settles on a
    reflective floor, and the MoOS wordmark fades up. None of that can be faked
    by moving sprites around — it has real 3D rotation, plasma, and a floor
    reflection. So the intro is a FRAME SEQUENCE, cut from that render.

    It is not the whole render. Two things are traded deliberately:

      TIME. Ten seconds is a title card; a boot screen is not. The sting is
      resampled to ~2.2 s, and the dead opening (a barely-visible ring on black)
      is dropped entirely, so the first frame the user sees already has light in
      it. On a fast machine the desktop arrives before the sequence even ends,
      which is the correct failure mode: the splash is never the thing being
      waited for.

      RESOLUTION. The source is 1024x576 and the mark inside it is only ~270 px,
      so drawn at boot size it is a ~2x upscale. That is invisible while it MOVES
      and obvious once it stops — so the sequence hands over, on its last frames,
      to the high-resolution still cut from the reference render by
      artwork/extract_boot_mark.py. moos.script crossfades between them. The
      poses are identical (checked), so what the eye reads is the mark coming
      into focus as it settles, not a substitution.

    THE GROUND. The render sits on near-black; the MoOS desktop opens on the
    #14191C graphite canvas, and a full-screen hue flip at that handoff is the
    exact defect that retiring the old navy splash fixed. So the frames are
    keyed to alpha by their own luminance — the render's black becomes
    transparent — and moos.script plays them over a soft dark "stage" that
    itself fades out to graphite well inside the screen edge. The frame border
    stays exactly #14191C and the handoff stays seamless.

USAGE
    python artwork/build_boot_frames.py                 # default source
    python artwork/build_boot_frames.py <video.mp4>
    python artwork/build_boot_frames.py --frames 56 --fps 25

Requires ffmpeg on PATH.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"

DEFAULT_SOURCE = (
    pathlib.Path.home()
    / "Desktop/MoOS PC/Neuer Ordner (2)/WhatsApp Video 2026-08-19 at 15.16.11.mp4"
)

# The sting's usable span, in source frames at 24 fps. Before FIRST the screen is
# effectively empty; after LAST the render is static and the still takes over.
FIRST_SRC_FRAME = 6
LAST_SRC_FRAME = 171

# Luminance keying. Below LO the render is its own black ground and becomes
# transparent; above HI it is the object and stays opaque. The band between is
# the glow, which is exactly what should be semi-transparent over the stage.
# The source is a compressed video: its "black" measures up to luminance 8 in
# the corners. Keying below that turns the whole frame into faint noise with
# non-zero alpha, which is both visible as grain over the stage and fatal to PNG
# compression (the first cut of this file shipped 14.5 MB of frames for exactly
# that reason). LO sits above the noise floor.
KEY_LO = 10.0
KEY_HI = 38.0

# The sting's glow spreads dimly across almost the entire source frame, so a low
# threshold "finds content" everywhere and the crop stops cropping. This is the
# level that finds the mark, its floor reflection and the wordmark, and leaves
# the far atmosphere to the stage and halo moos.script draws itself.
CONTENT_LEVEL = 72.0


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FATAL: {cmd[0]} failed:\n{r.stderr[-2000:]}")


def content_box(frames: list[Image.Image], pad_frac: float = 0.06) -> tuple[int, int, int, int]:
    """Union bounding box of everything visible across the whole sequence.

    Computed from the frames rather than typed in, so re-cutting from a
    different render cannot silently crop the animation.
    """
    w, h = frames[0].size
    acc = np.zeros((h, w), dtype=bool)
    for f in frames:
        a = np.asarray(f.convert("RGB")).astype(np.float32)
        acc |= (a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)) > CONTENT_LEVEL
    ys, xs = np.nonzero(acc)
    if len(xs) < 100:
        sys.exit("FATAL: the video appears to be blank — wrong source?")
    px, py = int(w * pad_frac), int(h * pad_frac)
    return (max(0, xs.min() - px), max(0, ys.min() - py),
            min(w, xs.max() + px), min(h, ys.max() + py))


def key_to_alpha(img: Image.Image) -> Image.Image:
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    alpha = np.clip((lum - KEY_LO) / (KEY_HI - KEY_LO), 0.0, 1.0)
    alpha = alpha * alpha * (3.0 - 2.0 * alpha)
    # Colour under fully-transparent pixels is zeroed so PNG has a flat field to
    # compress; with ~56 frames in the initramfs this is worth several MB.
    rgb = a * (alpha[..., None] > 0.004)
    out = np.concatenate([rgb, (alpha * 255.0)[..., None]], axis=-1)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default=str(DEFAULT_SOURCE))
    ap.add_argument("--frames", type=int, default=36, help="frames in the shipped intro")
    ap.add_argument("--fps", type=int, default=24, help="playback rate the script uses")
    ap.add_argument("--width", type=int, default=720,
                    help="stored frame width. THIS IS A MEMORY BUDGET, not a quality "
                         "knob: Plymouth decodes every frame into RAM inside the "
                         "initramfs, so N frames cost N*w*h*4 bytes there.")
    args = ap.parse_args()

    src = pathlib.Path(args.source)
    if not src.exists():
        sys.exit(f"FATAL: source video not found: {src}")
    if not shutil.which("ffmpeg"):
        sys.exit("FATAL: ffmpeg is not on PATH")

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        run(["ffmpeg", "-v", "error", "-i", str(src),
             "-vf", f"select='between(n,{FIRST_SRC_FRAME},{LAST_SRC_FRAME})'",
             "-vsync", "0", str(tmp / "src_%04d.png")])
        raw = sorted(tmp.glob("src_*.png"))
        if not raw:
            sys.exit("FATAL: ffmpeg produced no frames")

        # Even resample across the usable span down to the shipped count.
        idx = np.linspace(0, len(raw) - 1, args.frames).round().astype(int)
        picked = [Image.open(raw[i]).convert("RGB") for i in idx]

        box = content_box(picked)
        cw, ch = box[2] - box[0], box[3] - box[1]

        for f in THEME.glob("intro*.png"):
            f.unlink()
        total = 0
        sw = args.width
        sh_ = max(1, int(round(sw * ch / cw)))
        for n, im in enumerate(picked, start=1):
            out = key_to_alpha(im.crop(box)).resize((sw, sh_), Image.LANCZOS)
            # Unpadded on purpose: Plymouth's script language builds these
            # names by concatenating a loop counter and has no formatting, so
            # intro1..intro36 is what it can actually address.
            p = THEME / f"intro{n}.png"
            out.save(p, optimize=True)
            total += p.stat().st_size

    print(f"source   : {src.name}")
    print(f"span     : source frames {FIRST_SRC_FRAME}..{LAST_SRC_FRAME} "
          f"-> {args.frames} frames @ {args.fps} fps = {args.frames/args.fps:.2f} s")
    print(f"crop     : {cw}x{ch} (from the sequence's own content, +6% pad)")
    print(f"stored   : {sw}x{sh_} per frame")
    print(f"written  : {THEME}/intro1..{args.frames}.png  total {total/1024:.0f} KiB on disk")
    print(f"ram      : ~{args.frames * sw * sh_ * 4 / 1048576:.0f} MiB decoded in the initramfs")
    print(f"aspect   : {sw/sh_:.4f}   <- moos.script INTRO_ASPECT must match this")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
