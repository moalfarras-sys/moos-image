#!/usr/bin/env python3
"""Generate the coherent first-party MoOS application icon family.

Third-party applications keep their own identity.  This script owns only MoOS
apps and gives them one adaptive vector plate, one optical grid, and distinct
glyphs.  SVG is canonical; PNG exports are deterministic compatibility assets.
"""

from __future__ import annotations

import base64
import pathlib
import shutil
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
HICOLOR = ROOT / "system_files/usr/share/icons/hicolor"
SCALABLE = HICOLOR / "scalable/apps"
PREVIEW = ROOT / "artwork/moos-ui2/previews/moos-app-icons.png"
MOAI_MASTER = ROOT / "artwork/icons/mo-ai-1024.png"
REMOTE_LOGO = ROOT / "moremote/Logo.png"
LEGACY_REMOTE_SVG = ROOT / "artwork/moos-ui/icons/moos-pc-remote.svg"
LEGACY_REMOTE_PREVIEW = ROOT / "artwork/moos-ui/previews/moos-pc-remote-512.png"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)


GLYPHS = {
    "moos-moai": {
        "accent": "#4ED7C8",
        "secondary": "#78AFFF",
        "body": """
  <path d="M322 520C322 378 408 292 512 292s190 86 190 228-86 212-190 212-190-70-190-212Z"
        fill="none" stroke="url(#accent)" stroke-width="42"/>
  <path d="M390 594 452 430l60 112 62-112 62 164" fill="none"
        stroke="#EAF8F6" stroke-width="38" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="362" cy="356" r="28" fill="#78AFFF"/>
  <circle cx="664" cy="350" r="22" fill="#4ED7C8"/>
  <circle cx="690" cy="620" r="26" fill="#A8F1E8"/>
  <path d="M512 226v54M485 253h54" stroke="#EAF8F6" stroke-width="22" stroke-linecap="round"/>
""",
    },
    "moos-moplayer": {
        "accent": "#4ED7C8",
        "secondary": "#9B8CFF",
        "body": """
  <circle cx="512" cy="504" r="218" fill="none" stroke="url(#accent)" stroke-width="38"/>
  <path d="m462 392 170 112-170 112Z" fill="#EAF8F6" stroke="#78AFFF" stroke-width="18" stroke-linejoin="round"/>
  <path d="M312 708c58-38 98 38 156 0s98 38 156 0 98 38 116 22"
        fill="none" stroke="#4ED7C8" stroke-width="28" stroke-linecap="round"/>
""",
    },
    "moos-pc-remote": {
        "accent": "#38BDF8",
        "secondary": "#4ED7C8",
        "body": """
  <rect x="278" y="324" width="388" height="286" rx="58" fill="none" stroke="url(#accent)" stroke-width="38"/>
  <path d="M422 660h100l18 64H402l20-64Z" fill="#78AFFF"/>
  <rect x="606" y="410" width="150" height="326" rx="48" fill="#18262B" stroke="#EAF8F6" stroke-width="28"/>
  <path d="M352 526c78-76 136 78 222 0 62-56 102-38 142-10"
        fill="none" stroke="#4ED7C8" stroke-width="32" stroke-linecap="round"/>
  <circle cx="700" cy="654" r="13" fill="#4ED7C8"/>
""",
    },
    "moos-store": {
        "accent": "#4ED7C8",
        "secondary": "#F4C56A",
        "body": """
  <path d="M324 406h376l-30 330H354Z" fill="#1C3335" stroke="url(#accent)" stroke-width="38" stroke-linejoin="round"/>
  <path d="M416 426v-54c0-64 40-106 96-106s96 42 96 106v54"
        fill="none" stroke="#EAF8F6" stroke-width="34" stroke-linecap="round"/>
  <rect x="416" y="506" width="72" height="72" rx="22" fill="#4ED7C8"/>
  <rect x="536" y="506" width="72" height="72" rx="22" fill="#78AFFF"/>
  <rect x="416" y="620" width="72" height="72" rx="22" fill="#F4C56A"/>
  <rect x="536" y="620" width="72" height="72" rx="22" fill="#A8F1E8"/>
""",
    },
    "moos-installer": {
        "accent": "#4ED7C8",
        "secondary": "#78AFFF",
        "body": """
  <path d="M300 372h424v310H300Z" fill="#1C3335" stroke="url(#accent)"
        stroke-width="38" stroke-linejoin="round"/>
  <path d="M354 372v-74h316v74" fill="none" stroke="#EAF8F6"
        stroke-width="34" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M512 420v150m-66-62 66 66 66-66" fill="none"
        stroke="#EAF8F6" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M372 730h280" fill="none" stroke="#4ED7C8" stroke-width="34"
        stroke-linecap="round"/>
  <circle cx="664" cy="626" r="24" fill="#78AFFF"/>
""",
    },
    "moos-updater": {
        "accent": "#4ED7C8",
        "secondary": "#78AFFF",
        "body": """
  <path d="M342 458c28-106 124-180 238-164 70 10 128 50 166 104"
        fill="none" stroke="url(#accent)" stroke-width="42" stroke-linecap="round"/>
  <path d="m728 300 20 108-108-8" fill="none" stroke="#78AFFF" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M682 566c-28 106-124 180-238 164-70-10-128-50-166-104"
        fill="none" stroke="url(#accent)" stroke-width="42" stroke-linecap="round"/>
  <path d="m296 724-20-108 108 8" fill="none" stroke="#4ED7C8" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M512 398v208m-72-72 72 72 72-72" fill="none"
        stroke="#EAF8F6" stroke-width="34" stroke-linecap="round" stroke-linejoin="round"/>
""",
    },
    "moos-recovery": {
        "accent": "#4ED7C8",
        "secondary": "#F4C56A",
        "body": """
  <path d="M512 256c78 64 156 78 228 84v170c0 126-82 218-228 268-146-50-228-142-228-268V340c72-6 150-20 228-84Z"
        fill="#193034" stroke="url(#accent)" stroke-width="38" stroke-linejoin="round"/>
  <path d="M360 526h82l34-78 62 166 44-88h82" fill="none"
        stroke="#EAF8F6" stroke-width="34" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="512" cy="360" r="26" fill="#F4C56A"/>
""",
    },
    "moos-welcome": {
        "accent": "#4ED7C8",
        "secondary": "#78AFFF",
        "body": """
  <circle cx="512" cy="492" r="212" fill="none" stroke="url(#accent)" stroke-width="34" stroke-dasharray="20 28"/>
  <path d="M312 590c100-118 188-22 278-112 54-54 96-48 130-30"
        fill="none" stroke="#4ED7C8" stroke-width="42" stroke-linecap="round"/>
  <path d="M512 328v118m-58-58h116" stroke="#EAF8F6" stroke-width="32" stroke-linecap="round"/>
  <circle cx="352" cy="360" r="24" fill="#78AFFF"/>
  <circle cx="682" cy="620" r="22" fill="#A8F1E8"/>
""",
    },
    "moos-themes": {
        "accent": "#4ED7C8",
        "secondary": "#9B8CFF",
        "body": """
  <rect x="286" y="330" width="310" height="360" rx="72" fill="#1B3034" stroke="#78AFFF" stroke-width="32"/>
  <rect x="430" y="286" width="310" height="360" rx="72" fill="#233A3D" stroke="url(#accent)" stroke-width="36"/>
  <circle cx="540" cy="416" r="48" fill="#4ED7C8"/>
  <circle cx="650" cy="416" r="48" fill="#9B8CFF"/>
  <path d="M526 548h130M591 506v84" stroke="#EAF8F6" stroke-width="30" stroke-linecap="round"/>
  <path d="m316 730 32-66 66-32-66-32-32-66-32 66-66 32 66 32Z" fill="#F4C56A"/>
""",
    },
}


def icon_svg(name: str, spec: dict[str, str]) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- Original MoOS adaptive application icon: {name}. -->
  <defs>
    <linearGradient id="plate" x1="128" y1="104" x2="900" y2="934" gradientUnits="userSpaceOnUse">
      <stop stop-color="#304348"/>
      <stop offset=".44" stop-color="#1D2B2F"/>
      <stop offset="1" stop-color="#10181B"/>
    </linearGradient>
    <linearGradient id="accent" x1="300" y1="280" x2="744" y2="744" gradientUnits="userSpaceOnUse">
      <stop stop-color="{spec['secondary']}"/>
      <stop offset=".55" stop-color="{spec['accent']}"/>
      <stop offset="1" stop-color="#A8F1E8"/>
    </linearGradient>
    <radialGradient id="glow" cx=".22" cy=".12" r=".9">
      <stop stop-color="#A8F1E8" stop-opacity=".22"/>
      <stop offset="1" stop-color="#A8F1E8" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">
      <feDropShadow dx="0" dy="28" stdDeviation="30" flood-color="#071012" flood-opacity=".50"/>
    </filter>
  </defs>
  <rect x="72" y="72" width="880" height="880" rx="232" fill="url(#plate)" filter="url(#shadow)"/>
  <rect x="88" y="88" width="848" height="848" rx="216" fill="url(#glow)"/>
  <rect x="86" y="86" width="852" height="852" rx="218" fill="none" stroke="url(#accent)" stroke-width="12" stroke-opacity=".68"/>
  <path d="M178 246c126-120 292-146 442-96" fill="none" stroke="#EAF8F6" stroke-opacity=".11" stroke-width="18" stroke-linecap="round"/>
{spec['body'].rstrip()}
</svg>
"""


def raster_wrapper(path: pathlib.Path) -> str:
    """Keep the owner's commissioned Mo AI master byte-exact inside SVG."""
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="1024" height="1024" viewBox="0 0 1024 1024">
  <image width="1024" height="1024"
         xlink:href="data:image/png;base64,{payload}"/>
</svg>
"""


def main() -> None:
    magick = shutil.which("magick")
    if magick is None:
        raise SystemExit("ImageMagick is required to export MoOS app icon PNGs")
    SCALABLE.mkdir(parents=True, exist_ok=True)

    for name, spec in GLYPHS.items():
        svg = SCALABLE / f"{name}.svg"
        if name == "moos-moai":
            if not MOAI_MASTER.is_file():
                raise SystemExit(f"missing commissioned Mo AI master: {MOAI_MASTER}")
            svg.write_text(raster_wrapper(MOAI_MASTER), encoding="utf-8")
            render_source = MOAI_MASTER
        else:
            svg.write_text(icon_svg(name, spec), encoding="utf-8")
            render_source = svg
        for size in SIZES:
            output = HICOLOR / f"{size}x{size}/apps/{name}.png"
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                magick,
                "-background", "none",
                str(render_source),
                "-resize", f"{size}x{size}",
                "-strip",
                f"PNG32:{output}",
            ], check=True)

    # Compatibility names and vendored clients are not separate artwork. Keep
    # every copy mechanically identical to its new MoOS source of truth.
    for size in SIZES:
        source = HICOLOR / f"{size}x{size}/apps/moos-store.png"
        shutil.copyfile(source, HICOLOR / f"{size}x{size}/apps/mo-store.png")
    shutil.copyfile(
        HICOLOR / "512x512/apps/moos-pc-remote.png",
        REMOTE_LOGO,
    )
    shutil.copyfile(SCALABLE / "moos-pc-remote.svg", LEGACY_REMOTE_SVG)
    shutil.copyfile(
        HICOLOR / "512x512/apps/moos-pc-remote.png",
        LEGACY_REMOTE_PREVIEW,
    )

    # Contact sheet is review evidence, not a runtime asset.
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    # ImageMagick numbers output files when an older tile layout spills onto
    # multiple pages.  Remove only those known contact-sheet shards so changing
    # the grid cannot leave stale review evidence beside the current preview.
    for stale in PREVIEW.parent.glob(f"{PREVIEW.stem}-*{PREVIEW.suffix}"):
        stale.unlink()
    subprocess.run([
        magick,
        "montage",
        *[str(HICOLOR / f"256x256/apps/{name}.png") for name in GLYPHS],
        "-tile", "3x3",
        "-geometry", "220x220+24+24",
        "-background", "#10181B",
        str(PREVIEW),
    ], check=True)
    print(f"generated {len(GLYPHS)} MoOS app icons and {PREVIEW.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
