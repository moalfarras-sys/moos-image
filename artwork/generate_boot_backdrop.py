#!/usr/bin/env python3
"""Build the lightweight Plymouth backdrop from the login scene.

The first graphical boot surface and Plasma Login Manager deliberately share
the Graphite dark wallpaper. Plymouth cannot afford to decode the 4K master
inside the initramfs, so it ships a deterministic 1920x1080 derivative. The
composition is unchanged: at handoff the background remains in place and only
the authentication surface replaces the boot mark.

Deterministic: same master + Pillow version -> same pixels. No randomness,
timestamps, colour effects, or generated artwork are involved.
"""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
SOURCE = (
    ROOT
    / "system_files/usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"
)
OUTPUT = ROOT / "system_files/usr/share/plymouth/themes/moos/boot-backdrop.png"
SIZE = (1920, 1080)


def main() -> None:
    with Image.open(SOURCE) as source:
        backdrop = source.convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)
    backdrop.save(OUTPUT, format="PNG", optimize=True)
    print(f"wrote {OUTPUT} ({SIZE[0]}x{SIZE[1]})")


if __name__ == "__main__":
    main()
