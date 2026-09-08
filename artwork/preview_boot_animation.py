#!/usr/bin/env python3
"""Render what the MoOS Plymouth splash actually looks like, without booting.

WHY THIS EXISTS
    A boot splash is the one surface that cannot be opened and looked at. The
    only honest test is a real boot, and a real boot costs an image build plus a
    VM — far too slow to iterate against. Worse, the failure mode is silent:
    every gate in build.sh checks that the theme is *configured* (Theme=moos,
    assets present, script in the initramfs) and all of them stay green while
    the screen is black or the composition is wrong.

    So this composes the splash on the host, frame for frame, from the SAME
    files and the SAME geometry the shipped theme uses.

WHAT IT DOES AND DOES NOT PROVE
    It proves the composition: what is on screen, at what size, in what order,
    and what the frame looks like at the moment the desktop takes over. It does
    NOT prove that Plymouth's script plugin will parse moos.script — nothing on
    a Windows host can, and that is what the QEMU boot test is for.

    Every geometry number is parsed out of moos.script rather than repeated
    here; if a name it needs disappears, this exits non-zero instead of quietly
    describing a theme that no longer exists.

USAGE
    python artwork/preview_boot_animation.py
    python artwork/preview_boot_animation.py --height 768 --out DIR
"""
from __future__ import annotations

import argparse
import math
import pathlib
import re
import sys

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"
SCRIPT = THEME / "moos.script"
BACKDROP = THEME / "boot-backdrop.png"

# The UI2 canvas token moos.script pins beneath the shared login backdrop.
GRAPHITE = (20, 25, 28)


def load_constants() -> dict[str, float]:
    if not SCRIPT.exists():
        sys.exit(f"FATAL: {SCRIPT} is missing — nothing to preview")
    text = SCRIPT.read_text(encoding="utf-8")
    found = {k: float(v) for k, v in re.findall(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(-?[0-9]*\.?[0-9]+)\s*;", text, re.MULTILINE)}
    needed = [
        "INTRO_COUNT", "INTRO_HOLD", "INTRO_ASPECT", "CUE_DELAY",
        "BACKDROP_W", "BACKDROP_H",
    ]
    missing = [n for n in needed if n not in found]
    if missing:
        sys.exit(f"FATAL: moos.script no longer defines {', '.join(missing)} — "
                 "the preview and the theme have diverged")
    # stage_w = fmin(sw * A, sh * B * INTRO_ASPECT)
    m = re.search(r"stage_w\s*=\s*fmin\(sw\s*\*\s*([0-9.]+)\s*,\s*sh\s*\*\s*([0-9.]+)", text)
    if not m:
        sys.exit("FATAL: could not read the stage rectangle out of moos.script")
    found["stage_sw"], found["stage_sh"] = float(m.group(1)), float(m.group(2))
    return found


def frames() -> list[pathlib.Path]:
    fs = list(THEME.glob("intro*.png"))
    if not fs:
        sys.exit("FATAL: no intro frames — run artwork/build_boot_frames.py")
    return sorted(fs, key=lambda p: int("".join(c for c in p.stem if c.isdigit())))


def with_opacity(img: Image.Image, op: float) -> Image.Image:
    if op >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * op)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--width", type=int, default=0, help="default: 16:9 of --height")
    ap.add_argument("--out", default=str(ROOT / "artwork/generated"))
    args = ap.parse_args()

    h = args.height
    w = args.width or int(h * 16 / 9)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    c = load_constants()
    fs = frames()
    if len(fs) != int(c["INTRO_COUNT"]):
        sys.exit(f"FATAL: moos.script says INTRO_COUNT={int(c['INTRO_COUNT'])} but "
                 f"{len(fs)} intro frames are on disk — they must agree, or the script "
                 f"loads a file that is not there and Plymouth drops to its text splash")

    stage_w = min(w * c["stage_sw"], h * c["stage_sh"] * c["INTRO_ASPECT"])
    stage_h = stage_w / c["INTRO_ASPECT"]
    sx, sy = int((w - stage_w) / 2), int((h - stage_h) / 2)
    size = (int(stage_w), int(stage_h))

    if not BACKDROP.is_file():
        sys.exit(f"FATAL: {BACKDROP} is missing — run artwork/generate_boot_backdrop.py")

    intro = [Image.open(p).convert("RGBA").resize(size, Image.LANCZOS) for p in fs]
    backdrop = ImageOps.fit(
        Image.open(BACKDROP).convert("RGBA"), (w, h), method=Image.LANCZOS
    )

    glow_size = int(h * 1.05)
    ring_size = int(h * 1.02)
    head_size = int(h * 0.075)
    ring_radius = ring_size * 0.44
    glow = Image.open(THEME / "glow.png").convert("RGBA").resize(
        (glow_size, glow_size), Image.LANCZOS
    )
    ring = Image.open(THEME / "ring.png").convert("RGBA").resize(
        (ring_size, ring_size), Image.LANCZOS
    )
    head = Image.open(THEME / "head.png").convert("RGBA").resize(
        (head_size, head_size), Image.LANCZOS
    )

    def compose(layers) -> Image.Image:
        f = Image.new("RGBA", (w, h), GRAPHITE + (255,))
        f.alpha_composite(backdrop)
        for img, op, xy in layers:
            if op > 0.002:
                f.alpha_composite(with_opacity(img, op), xy)
        return f

    hold = int(c["INTRO_HOLD"])
    gif: list[Image.Image] = []
    strip: list[Image.Image] = []
    cue_delay = int(c["CUE_DELAY"])
    # Long enough to show that a slow boot remains alive, while still keeping
    # the preview compact. Plymouth itself keeps running until userspace wins.
    preview_ticks = cue_delay + 125
    marks = {0, 18, 38, 62, cue_delay, cue_delay + 45, preview_ticks - 1}

    for tick in range(preview_ticks):
        frame_index = min(len(intro) - 1, tick // hold)
        layers = []
        if tick > cue_delay:
            t = (tick - cue_delay) / 50.0
            into = max(0.0, min(1.0, t))
            glow_opacity = into * (
                0.16 + 0.05 * math.sin(t * 2 * math.pi / 4.5)
            )
            angle = math.radians(t * 130 - 90)
            hx = int(w / 2 + ring_radius * math.cos(angle) - head_size / 2)
            hy = int(h / 2 + ring_radius * math.sin(angle) - head_size / 2)
            layers.extend([
                (glow, glow_opacity, ((w - glow_size) // 2, (h - glow_size) // 2)),
                (ring, into * 0.35, ((w - ring_size) // 2, (h - ring_size) // 2)),
                (head, into * 0.85, (hx, hy)),
            ])
        layers.append((intro[frame_index], 1.0, (sx, sy)))
        frame = compose(layers)
        if tick in marks:
            strip.append(frame)
        if tick % 4 == 0:
            gif.append(frame)

    # quit_callback hides every moving cue and pins this deliberately composed
    # handoff frame; include it as the eighth storyboard panel.
    rest = compose([(intro[-1], 1.0, (sx, sy))])
    strip.append(rest)

    cw, ch = w // 4, h // 4
    sheet = Image.new("RGB", (cw * 4, ch * 2), GRAPHITE)
    for n, im in enumerate(strip[:8]):
        sheet.paste(im.convert("RGB").resize((cw, ch), Image.LANCZOS),
                    ((n % 4) * cw, (n // 4) * ch))
    sheet.save(out / "boot-animation-filmstrip.png")
    rest.convert("RGB").save(out / "boot-animation-settled.png")

    small = [g.convert("RGB").resize((w // 4, h // 4), Image.LANCZOS) for g in gif]
    small[0].save(out / "boot-animation.gif", save_all=True, append_images=small[1:],
                  duration=80, loop=0, optimize=True)

    total = (len(intro) * hold) / 50.0
    print(f"stage     : {int(stage_w)}x{int(stage_h)} at ({sx}, {sy}) on {w}x{h}")
    print(f"intro     : {len(intro)} frames x {hold} refreshes = {total:.2f} s to rest")
    print(f"cue after : {c['CUE_DELAY']/50.0:.1f} s (slow boots only; included in preview)")
    print(f"filmstrip : {out/'boot-animation-filmstrip.png'}")
    print(f"settled   : {out/'boot-animation-settled.png'}   <- the frame --retain-splash holds")
    print(f"gif       : {out/'boot-animation.gif'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
