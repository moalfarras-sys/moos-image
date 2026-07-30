#!/usr/bin/env python3
"""Generate the MoOS first-party application mark family.

Third-party applications keep their own identity; this script owns only the
MoOS apps.  The MoOS app icons are now static, hyper-realistic PNGs.

SVG is no longer canonical; the PNG masters in artwork/master_icons/ are the source of truth.
The PNG ladder is a deterministic compatibility export for surfaces that require
specific sizes.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
HICOLOR = ROOT / "system_files/usr/share/icons/hicolor"
PREVIEW = ROOT / "artwork/moos-ui2/previews/moos-app-icons.png"
MOAI_MASTER = ROOT / "artwork/icons/mo-ai-1024.png"
MOAI_GENERATOR = ROOT / "artwork/generate_moai_icon.py"
MASTER_ICONS = ROOT / "artwork/master_icons"
REMOTE_LOGO = ROOT / "moremote/Logo.png"
LEGACY_REMOTE_PREVIEW = ROOT / "artwork/moos-ui/previews/moos-pc-remote-512.png"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)

MARKS = (
    "moos-control-center",
    "moos-store",
    "moos-pc-remote",
    "moos-updater",
    "moos-themes",
    "moos-installer",
    "moos-recovery",
    "moos-welcome",
    "moos-moplayer",
)

def export_png_ladder(magick: str, source_png: pathlib.Path, name: str) -> None:
    for size in SIZES:
        output = HICOLOR / f"{size}x{size}/apps/{name}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            magick,
            "-background", "none",
            str(source_png),
            "-resize", f"{size}x{size}",
            "-strip",
            f"PNG32:{output}",
        ], check=True)


def main() -> None:
    magick = shutil.which("magick")
    if magick is None:
        raise SystemExit("ImageMagick is required to export MoOS app icon PNGs")
        
    for name in MARKS:
        source_png = MASTER_ICONS / f"{name}.png"
        if not source_png.is_file():
            raise SystemExit(f"Missing master PNG for {name}: {source_png}")
        export_png_ladder(magick, source_png, name)

    if not MOAI_MASTER.is_file() or not MOAI_GENERATOR.is_file():
        raise SystemExit("missing protected Mo AI master or its seating generator")
    subprocess.run([sys.executable, str(MOAI_GENERATOR)], check=True)

    # Compatibility names and vendored clients
    for size in SIZES:
        source = HICOLOR / f"{size}x{size}/apps/moos-store.png"
        dest = HICOLOR / f"{size}x{size}/apps/mo-store.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
    
    REMOTE_LOGO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(HICOLOR / "512x512/apps/moos-pc-remote.png", REMOTE_LOGO)
    
    LEGACY_REMOTE_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        HICOLOR / "512x512/apps/moos-pc-remote.png",
        LEGACY_REMOTE_PREVIEW,
    )

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    for stale in PREVIEW.parent.glob(f"{PREVIEW.stem}-*{PREVIEW.suffix}"):
        stale.unlink()
        
    subprocess.run([
        magick,
        "montage",
        *[
            str(HICOLOR / f"256x256/apps/{name}.png")
            for name in ("moos-moai", *MARKS)
        ],
        "-tile", "5x2",
        "-geometry", "220x220+22+22",
        "-background", "#151d21",
        str(PREVIEW),
    ], check=True)

    print(
        f"generated {len(MARKS) + 1} MoOS app icons, "
        f"{PREVIEW.relative_to(ROOT)}"
    )

if __name__ == "__main__":
    main()
