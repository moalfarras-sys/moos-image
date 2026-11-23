#!/usr/bin/env python3
"""Bake the frost the desktop Hub's glass cards sit on.

The Hub is painted INSIDE the scene wallpaper, so no compositor can blur what is
behind it: KWin blurs what lies under a window, and the Hub is part of the window.
Its cards may not carry a shader of their own either (tests/test_moos_ui2.py bans
ShaderEffect/MultiEffect there: they repaint on a 4K surface on every machine).
So the blur happens here, once, offline. Every scene master gets a small,
Gaussian-blurred copy beside it:

    <package>/contents/images/<name>.png       the master the wallpaper paints
    <package>/contents/frost/images/<name>.jpg the frost a card crops and paints

At runtime a card only crops this already-smooth image to its own rectangle
(Image.sourceClipRect) and draws it with Kirigami's rounded-texture primitive:
no blur pass, no per-frame cost, and the blur quality of a real Gaussian rather
than a smeared upscale of a few pixels.

    python3 artwork/generate_scene_frost.py           # write frost + provenance
    python3 artwork/generate_scene_frost.py --check   # verify, write nothing

Provenance (artwork/moos-design/scene-frost.json) records each master's and each
frost's SHA-256 and the parameters, so a changed master without new frost fails.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
WALLPAPERS = ROOT / "system_files/usr/share/wallpapers"
PROVENANCE = ROOT / "artwork/moos-design/scene-frost.json"
WIDTH = 640                 # the frost is upscaled ~4x on a 2560 px panel: blur hides it
RADIUS = 11                 # ≈1.7% of the width: ~44 device px of blur on that panel
QUALITY = 82
BRANCHES = ("images", "images_dark")
MASTERS = (".png", ".jpg", ".jpeg", ".webp")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def masters() -> list[Path]:
    found = []
    for package in sorted(p for p in WALLPAPERS.iterdir() if (p / "contents").is_dir()):
        for branch in BRANCHES:
            folder = package / "contents" / branch
            if folder.is_dir():
                found += sorted(p for p in folder.iterdir()
                                if p.is_file() and p.suffix.lower() in MASTERS)
    return found


def frost_path(master: Path) -> Path:
    contents = master.parent.parent
    return contents / "frost" / master.parent.name / (master.stem + ".jpg")


def frost_bytes(master: Path) -> tuple[bytes, list[int]]:
    with Image.open(master) as source:
        image = source.convert("RGB")
    height = max(1, round(WIDTH * image.height / image.width))
    small = image.resize((WIDTH, height), Image.Resampling.LANCZOS)
    blurred = small.filter(ImageFilter.GaussianBlur(RADIUS))
    out = io.BytesIO()
    blurred.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=False, subsampling=2)
    return out.getvalue(), [WIDTH, height]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="verify the shipped frost; write nothing")
    args = parser.parse_args()
    records: dict[str, dict] = {}
    problems: list[str] = []
    for master in masters():
        data, size = frost_bytes(master)
        target = frost_path(master)
        rel = target.relative_to(ROOT).as_posix()
        records[rel] = {"master": master.relative_to(ROOT).as_posix(),
                        "masterSHA256": sha256(master.read_bytes()),
                        "size": size, "sha256": sha256(data)}
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                problems.append(f"{rel} is missing or stale for {master.name}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    record = {"schema": 1,
              "about": "Gaussian frost under the desktop Hub's glass cards (generate_scene_frost.py)",
              "width": WIDTH, "gaussianRadius": RADIUS, "jpegQuality": QUALITY,
              "files": records}
    text = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not PROVENANCE.is_file() or PROVENANCE.read_text(encoding="utf-8") != text:
            problems.append(f"{PROVENANCE.relative_to(ROOT)} does not match the masters")
        for problem in problems:
            print("FROST:", problem)
        return 1 if problems else 0
    PROVENANCE.write_text(text, encoding="utf-8")
    print(f"wrote {len(records)} frost images")
    return 0


if __name__ == "__main__":
    sys.exit(main())
