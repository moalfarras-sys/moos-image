#!/usr/bin/env python3
"""Generate the MoOS first-party application mark family — Premium 3D Liquid Glass.

Third-party applications keep their own identity; this script owns only the
MoOS apps.  Every mark is one squircle tile plus one glyph, and **every ink is
a KDE colour role**, never a literal colour — the tile is `ColorScheme-*` and
so is the glyph.

How that reaches the user's dock is the load-bearing part, and MoOS does NOT
do it the way upstream does:

* KIconLoader can rewrite the <style id="current-color-scheme"> element from
  the live palette (kiconthemes/src/kiconloader.cpp, processSvg) — but only if
  the active icon theme sets FollowsColorScheme=true, and MoOS deliberately
  sets it to **false** on every icon theme.  With `true`, that rewrite reads
  the *application* QPalette instead of the Plasma surface's colour set and
  painted near-invisible symbols on the live dark Launcher (evidence pair in
  artwork/moos-ui2/live-tests/, and PROJECT_STATE.md records the decision).
* So MoOS **bakes** the inks instead: `generate_moos_themes.build_icon_theme`
  writes one copy of every mark into each of the 14 palette icon themes with
  that palette's own roles substituted into the stylesheet, and
  `build_files/build.sh` does the same for the two broad bases (MoOSUI2 dark,
  MoOSUI2Light).  Each look-and-feel selects its palette's icon theme, so
  changing the MoOS theme changes the app marks with it — deterministically,
  and without depending on any application getting its palette right.

The stylesheet written here is the MoOS default palette (MoOSUI2Dark): it is
what the hicolor masters and the PNG ladder carry, and what any surface that
does not re-colour (GTK, librsvg, browsers) renders.  That is why it is MoOS
teal on graphite rather than Breeze blue — a non-adaptive surface must still
show MoOS, never somebody else's brand.

Role pairing is not free choice.  KDE guarantees HighlightedText is legible on
Highlight, and Positive/Neutral/NegativeText are legible on the window
background, so the family only ever uses those two pairings (plus the
Text/Background pair for the one inverted "paper" tile).
tests/test_moos_app_icons.py re-derives the WCAG contrast of every tile/glyph
pair against all 16 shipped MoOS palettes and fails under 4:1 — the measured
minimum today is 4.4:1.

SVG is canonical; the PNG ladder is a deterministic compatibility export for
surfaces with no SVG (or no re-colouring) path.
"""

from __future__ import annotations

import configparser
import pathlib
import re
import shutil
import string
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMES = ROOT / "system_files/usr/share/color-schemes"
HICOLOR = ROOT / "system_files/usr/share/icons/hicolor"
SCALABLE = HICOLOR / "scalable/apps"
PREVIEW = ROOT / "artwork/moos-ui2/previews/moos-app-icons.png"
PALETTE_PREVIEW = ROOT / "artwork/moos-ui2/previews/moos-app-icons-palettes.png"
MOAI_MASTER = ROOT / "artwork/icons/mo-ai-1024.png"
MOAI_GENERATOR = ROOT / "artwork/generate_moai_icon.py"
REMOTE_LOGO = ROOT / "moremote/Logo.png"
LEGACY_REMOTE_SVG = ROOT / "artwork/moos-ui/icons/moos-pc-remote.svg"
LEGACY_REMOTE_PREVIEW = ROOT / "artwork/moos-ui/previews/moos-pc-remote-512.png"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)

# The MoOS default palette (system_files/usr/share/color-schemes/MoOSUI2Dark.colors),
# expressed as the KDE icon stylesheet.  KIconLoader overwrites this block
# wholesale; anything that does not re-colour renders these exact inks.
FALLBACK_STYLESHEET = {
    "Text": "#e8f1ef",
    "Background": "#1d2529",
    "Highlight": "#4ed7c8",
    "HighlightedText": "#142220",
    "PositiveText": "#69d9a5",
    "NeutralText": "#f4c56a",
    "NegativeText": "#ff7d88",
    "Accent": "#4ed7c8",
}

# One optical grid for the whole family, shared with the seated Mo AI orb
# (artwork/generate_moai_icon.py): an 880 px tile inside the 1024 px canvas.
# Softer squircle (rx/side ≈ 0.30) — still the family's 880 px optical span.
TILE = 'x="72" y="72" width="880" height="880" rx="264"'
RIM = 'x="84" y="84" width="856" height="856" rx="252"'

# Nothing below 64 canvas units survives the 16 px dock cell (1 px = 64 units),
# so every load-bearing stroke is >= 76 and every detail cut is >= 48.
MARKS: dict[str, dict[str, str]] = {
    "moos-control-center": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <g class="$INK" fill="currentColor">
    <rect x="268" y="282" width="488" height="92" rx="46" opacity=".34"/>
    <rect x="268" y="466" width="488" height="92" rx="46" opacity=".34"/>
    <rect x="268" y="650" width="488" height="92" rx="46" opacity=".34"/>
    <rect x="268" y="282" width="368" height="92" rx="46"/>
    <rect x="268" y="466" width="168" height="92" rx="46"/>
    <rect x="268" y="650" width="288" height="92" rx="46"/>
    <circle cx="636" cy="328" r="74"/>
    <circle cx="436" cy="512" r="74"/>
    <circle cx="556" cy="696" r="74"/>
  </g>
  <g class="$TILE" fill="currentColor">
    <circle cx="636" cy="328" r="34"/>
    <circle cx="436" cy="512" r="34"/>
    <circle cx="556" cy="696" r="34"/>
  </g>
""",
    },
    "moos-store": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <g class="$INK" fill="currentColor">
    <rect x="268" y="300" width="208" height="208" rx="56"/>
    <rect x="548" y="268" width="208" height="208" rx="56"/>
    <rect x="268" y="540" width="208" height="208" rx="56"/>
    <rect x="548" y="540" width="208" height="208" rx="56"/>
  </g>
  <g class="$TILE" fill="currentColor">
    <circle cx="372" cy="404" r="28"/>
    <circle cx="652" cy="372" r="28"/>
    <circle cx="372" cy="644" r="28"/>
    <circle cx="652" cy="644" r="28"/>
  </g>
""",
    },
    "moos-pc-remote": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <g class="$INK" fill="currentColor">
    <rect x="228" y="230" width="520" height="376" rx="64"/>
    <rect x="433" y="606" width="110" height="56"/>
    <rect x="352" y="662" width="272" height="62" rx="31"/>
  </g>
  <rect class="$TILE" fill="currentColor" x="296" y="298" width="384" height="240" rx="28"/>
  <rect class="$TILE" fill="currentColor" x="552" y="422" width="268" height="404" rx="80"/>
  <rect class="$INK" fill="currentColor" x="576" y="446" width="220" height="356" rx="58"/>
  <g class="$TILE" fill="currentColor">
    <rect x="656" y="488" width="60" height="18" rx="9"/>
    <rect x="646" y="742" width="80" height="18" rx="9"/>
  </g>
""",
    },
    "moos-updater": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <g class="$INK" fill="currentColor">
    <path d="M512 260A252 252 0 1 1 275 426" fill="none" stroke="currentColor"
          stroke-width="92"/>
    <path d="M512 186v148l130-74Z"/>
    <rect x="464" y="372" width="96" height="190" rx="20"/>
    <path d="M512 684 382 530h260Z" stroke="currentColor" stroke-width="36"
          stroke-linejoin="round"/>
  </g>
""",
    },
    "moos-themes": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <g class="$INK" fill="currentColor">
    <circle cx="512" cy="442" r="228" opacity=".3"/>
    <path d="M351 603A228 228 0 0 1 673 281Z"/>
    <circle cx="512" cy="442" r="228" fill="none" stroke="currentColor" stroke-width="56"/>
    <circle cx="396" cy="806" r="50"/>
    <circle cx="512" cy="806" r="50" opacity=".62"/>
    <circle cx="628" cy="806" r="50" opacity=".34"/>
  </g>
""",
    },
    "moos-installer": {
        "tile": "PositiveText",
        "ink": "Background",
        "body": """
  <g class="$INK" fill="currentColor">
    <rect x="452" y="196" width="120" height="250" rx="30"/>
    <path d="M512 686 336 458h352Z" stroke="currentColor" stroke-width="40"
          stroke-linejoin="round"/>
    <rect x="272" y="760" width="480" height="96" rx="48"/>
  </g>
""",
    },
    "moos-recovery": {
        "tile": "NegativeText",
        "ink": "Background",
        "body": """
  <path class="$INK" fill="currentColor"
        d="M512 176c96 62 196 82 268 88v236c0 200-110 268-268 324-158-56-268-124-268-324V264c72-6 172-26 268-88Z"/>
  <g class="$TILE" fill="currentColor">
    <rect x="470" y="390" width="84" height="224" rx="22"/>
    <rect x="400" y="460" width="224" height="84" rx="22"/>
  </g>
""",
    },
    "moos-welcome": {
        "tile": "Text",
        "ink": "Background",
        "body": """
  <g class="$INK" fill="currentColor">
    <path d="M320 560a192 192 0 0 1 384 0Z"/>
    <rect x="248" y="560" width="528" height="72" rx="36"/>
    <g fill="none" stroke="currentColor" stroke-width="64" stroke-linecap="round" opacity=".6">
      <path d="M294 481 215 452"/>
      <path d="M379 370 331 301"/>
      <path d="M512 328v-84"/>
      <path d="M645 370 693 301"/>
      <path d="M730 481 809 452"/>
    </g>
    <rect x="300" y="686" width="424" height="50" rx="25" opacity=".5"/>
    <rect x="356" y="772" width="312" height="50" rx="25" opacity=".32"/>
  </g>
""",
    },
    "moos-moplayer": {
        "tile": "NeutralText",
        "ink": "Background",
        "body": """
  <g class="$INK" fill="currentColor">
    <path d="M275 654V334c0-38 28-66 66-66h18c24 0 46 13 58 34l84 148 84-148c12-21 34-34 58-34h18c38 0 66 28 66 66v320h-92V434l-92 158c-9 16-24 24-42 24s-33-8-42-24l-92-158v220Z"/>
    <path d="M252 760c126 58 242 26 330-66 82-86 140-120 202-128" fill="none"
          stroke="currentColor" stroke-width="64" stroke-linecap="round" opacity=".55"/>
  </g>
""",
    },
}


def icon_svg(name: str, mark: dict[str, str]) -> str:
    """Premium 3D Liquid Glass plate + role-inked glyph.

    The premium liquid-glass material stack uses only white/black with opacity so
    it survives every palette bake.  The plate has 7 glass layers for deep 3D
    realism: top sheen, bottom depth, diagonal shimmer, radial caustic,
    bottom-right rim light, floor glow, and a bright rim edge.

    Tile and glyph colours stay on KDE colour roles — never literal brand hex
    — so Dark / Light / Blue / Purple / Green / Orange (and every MoOS family
    member) re-ink the same geometry.

    Critical for Plasma: never use clipPath over sharp rects.  Qt SVG (what
    KIconLoader uses on the live dock) does not reliably clip, so unclipped
    square glass layers paint a visible square "scratch" behind the squircle.
    Every glass fill is itself a rounded rect with the same rx as the plate.
    """
    stylesheet = "\n".join(
        f"      .ColorScheme-{role} {{ color: {value}; }}"
        for role, value in FALLBACK_STYLESHEET.items()
    )
    body = string.Template(mark["body"].strip("\n")).substitute(
        INK=f"ColorScheme-{mark['ink']}",
        TILE=f"ColorScheme-{mark['tile']}",
    )
    gid = name.replace(".", "-")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- MoOS UI — Premium 3D Liquid Glass application mark: {name}.
       Premium 3D liquid-glass plate with enhanced 7-layer glass material.
       Every ink is a KDE colour role; MoOS bakes one copy of this file per
       palette icon theme (FollowsColorScheme=false).  Glass sheens are white/black
       opacity only — theme-safe material.  No clipPath: every fill is a rounded
       rect so Plasma cannot paint a square scratch behind the squircle.
       Regenerate with artwork/generate_moos_app_icons.py. -->
  <defs>
    <style id="current-color-scheme" type="text/css">
{stylesheet}
    </style>
    <linearGradient id="{gid}-sheen" x1="512" y1="72" x2="512" y2="680"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".72"/>
      <stop offset="0.15" stop-color="#ffffff" stop-opacity=".32"/>
      <stop offset="0.35" stop-color="#ffffff" stop-opacity=".08"/>
      <stop offset="0.55" stop-color="#ffffff" stop-opacity=".02"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="{gid}-depth" x1="512" y1="320" x2="512" y2="952"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#000000" stop-opacity="0"/>
      <stop offset="0.40" stop-color="#000000" stop-opacity=".04"/>
      <stop offset="0.70" stop-color="#000000" stop-opacity=".12"/>
      <stop offset="1" stop-color="#000000" stop-opacity=".38"/>
    </linearGradient>
    <linearGradient id="{gid}-shimmer" x1="140" y1="80" x2="880" y2="820"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="0.22" stop-color="#ffffff" stop-opacity=".14"/>
      <stop offset="0.28" stop-color="#ffffff" stop-opacity=".22"/>
      <stop offset="0.34" stop-color="#ffffff" stop-opacity=".14"/>
      <stop offset="0.50" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="{gid}-refract" x1="120" y1="100" x2="860" y2="780"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="0.32" stop-color="#ffffff" stop-opacity=".20"/>
      <stop offset="0.46" stop-color="#ffffff" stop-opacity=".05"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="{gid}-caustic" gradientUnits="userSpaceOnUse"
                    cx="280" cy="220" r="460">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".68"/>
      <stop offset="0.25" stop-color="#ffffff" stop-opacity=".20"/>
      <stop offset="0.55" stop-color="#ffffff" stop-opacity=".05"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="{gid}-rimlight" gradientUnits="userSpaceOnUse"
                    cx="740" cy="760" r="520">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".25"/>
      <stop offset="0.40" stop-color="#ffffff" stop-opacity=".08"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="{gid}-floor" gradientUnits="userSpaceOnUse"
                    cx="512" cy="800" r="360">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".18"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="{gid}-rim-hi" x1="120" y1="60" x2="860" y2="860"
                    gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity=".85"/>
      <stop offset="0.18" stop-color="#ffffff" stop-opacity=".32"/>
      <stop offset="0.42" stop-color="#ffffff" stop-opacity=".10"/>
      <stop offset="0.68" stop-color="#ffffff" stop-opacity=".04"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="{gid}-aura" gradientUnits="userSpaceOnUse"
                    cx="512" cy="520" r="580">
      <stop offset="0.60" stop-color="#000000" stop-opacity="0"/>
      <stop offset="0.85" stop-color="#000000" stop-opacity=".14"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect fill="url(#{gid}-aura)" x="36" y="36" width="952" height="952" rx="292"/>
  <rect class="ColorScheme-{mark['tile']}" fill="currentColor" {TILE}/>
  <rect fill="url(#{gid}-depth)" {TILE}/>
  <rect fill="url(#{gid}-sheen)" {TILE}/>
  <rect fill="url(#{gid}-shimmer)" {TILE}/>
  <rect fill="url(#{gid}-refract)" {TILE}/>
  <rect fill="url(#{gid}-caustic)" {TILE}/>
  <rect fill="url(#{gid}-rimlight)" {TILE}/>
  <rect fill="url(#{gid}-floor)" {TILE}/>
  <rect fill="none" stroke="url(#{gid}-rim-hi)" stroke-width="18" {RIM}/>
  <rect class="ColorScheme-{mark['ink']}" fill="none" stroke="currentColor"
        stroke-opacity=".10" stroke-width="6" {RIM}/>
{body}
</svg>
"""



# --------------------------------------------------------------------------
# The substitution, in the same shape KDE uses.
#
# KIconColors::stylesheet() (kiconthemes/src/kiconcolors.cpp) builds this string
# from a palette and KIconLoaderPrivate::processSvg() swaps it into the element
# with id="current-color-scheme".  MoOS performs that substitution ahead of
# time — per palette icon theme, see the module docstring — so `recoloured()`
# below is what the theme generator, build.sh's gate and
# tests/test_moos_app_icons.py all mean by "this mark on that palette".
# --------------------------------------------------------------------------
STYLESHEET_TEMPLATE = (
    ".ColorScheme-Text {{ color:{Text}; }}"
    ".ColorScheme-Background{{ color:{Background}; }}"
    ".ColorScheme-Highlight{{ color:{Highlight}; }}"
    ".ColorScheme-HighlightedText{{ color:{HighlightedText}; }}"
    ".ColorScheme-PositiveText{{ color:{PositiveText}; }}"
    ".ColorScheme-NeutralText{{ color:{NeutralText}; }}"
    ".ColorScheme-NegativeText{{ color:{NegativeText}; }}"
    ".ColorScheme-Accent{{ color:{Accent}; }}"
)
STYLE_BLOCK = re.compile(
    r'(<style id="current-color-scheme"[^>]*>).*?(</style>)', re.DOTALL
)
PREVIEW_PALETTES = (
    "MoOSUI2Dark",
    "MoOSUI2Nova",
    "MoOSUI2Forge",
    "MoOSUI2Amethyst",
    "MoOSUI2Light",
    "MoOSUI2Daylight",
)


def palette_roles(scheme: pathlib.Path) -> dict[str, str]:
    """The eight icon colour roles KIconColors derives from a KDE palette."""
    config = configparser.ConfigParser(strict=False)
    config.read(scheme, encoding="utf-8")
    window = config["Colors:Window"]
    selection = config["Colors:Selection"]

    def hexed(value: str) -> str:
        red, green, blue = (int(part) for part in value.split(",")[:3])
        return f"#{red:02x}{green:02x}{blue:02x}"

    return {
        "Text": hexed(window["ForegroundNormal"]),
        "Background": hexed(window["BackgroundNormal"]),
        "Highlight": hexed(selection["BackgroundNormal"]),
        "HighlightedText": hexed(selection["ForegroundNormal"]),
        "PositiveText": hexed(window["ForegroundPositive"]),
        "NeutralText": hexed(window["ForegroundNeutral"]),
        "NegativeText": hexed(window["ForegroundNegative"]),
        "Accent": hexed(config["General"]["AccentColor"]),
    }


def icon_roles(roles: dict[str, str]) -> dict[str, str]:
    """The eight icon colour roles for a MoOS palette role map.

    Mirrors generate_moos_ui2.color_scheme exactly (Colors:Window +
    Colors:Selection + AccentColor), so a mark's baked inks are literally the
    same numbers as the colour scheme that ships with the same palette.
    """
    return {
        "Text": roles["text"],
        "Background": roles["surface"],
        "Highlight": roles["primary"],
        "HighlightedText": roles["selected_text"],
        "PositiveText": roles["positive"],
        "NeutralText": roles["warning"],
        "NegativeText": roles["negative"],
        "Accent": roles["primary"],
    }


def recoloured(svg: str, roles: dict[str, str]) -> str:
    """The same mark with one palette's inks baked into its stylesheet."""
    stylesheet = STYLESHEET_TEMPLATE.format(**roles)
    return STYLE_BLOCK.sub(lambda match: match[1] + stylesheet + match[2], svg, count=1)


def render_palette_matrix(magick: str) -> None:
    rows = []
    with tempfile.TemporaryDirectory(prefix="moos-app-icon-matrix-") as workspace:
        work = pathlib.Path(workspace)
        for scheme_name in PREVIEW_PALETTES:
            scheme = SCHEMES / f"{scheme_name}.colors"
            roles = palette_roles(scheme)
            cells = []
            for name in ("moos-moai", *MARKS):
                source = (SCALABLE / f"{name}.svg").read_text(encoding="utf-8")
                recoloured_svg = work / f"{scheme_name}-{name}.svg"
                recoloured_svg.write_text(recoloured(source, roles), encoding="utf-8")
                cell = work / f"{scheme_name}-{name}.png"
                subprocess.run([
                    magick, "-background", "none", str(recoloured_svg),
                    "-resize", "128x128", f"PNG32:{cell}",
                ], check=True)
                cells.append(str(cell))
            row = work / f"{scheme_name}.png"
            subprocess.run([
                magick, "montage", *cells,
                "-tile", f"{len(cells)}x1",
                "-geometry", "128x128+16+16",
                "-background", roles["Background"],
                str(row),
            ], check=True)
            rows.append(str(row))
        PALETTE_PREVIEW.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            magick, "montage", *rows,
            "-tile", "1x", "-geometry", "+0+0",
            "-background", "#000000", str(PALETTE_PREVIEW),
        ], check=True)


def export_png_ladder(magick: str, svg: pathlib.Path, name: str) -> None:
    for size in SIZES:
        output = HICOLOR / f"{size}x{size}/apps/{name}.png"
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            magick,
            "-background", "none",
            str(svg),
            "-resize", f"{size}x{size}",
            "-strip",
            f"PNG32:{output}",
        ], check=True)


def main() -> None:
    magick = shutil.which("magick")
    if magick is None:
        raise SystemExit("ImageMagick is required to export MoOS app icon PNGs")
    SCALABLE.mkdir(parents=True, exist_ok=True)

    for name, mark in MARKS.items():
        svg = SCALABLE / f"{name}.svg"
        svg.write_text(icon_svg(name, mark), encoding="utf-8", newline="\n")
        export_png_ladder(magick, svg, name)

    # Mo AI is a protected commissioned identity, not a glyph in this family.
    # Delegate to its byte-exact seating generator after all sibling tiles are
    # ready. Keeping it inside MARKS used to overwrite the protected wrapper
    # with an edge-to-edge raster every time this family generator ran.
    if not MOAI_MASTER.is_file() or not MOAI_GENERATOR.is_file():
        raise SystemExit("missing protected Mo AI master or its seating generator")
    subprocess.run([sys.executable, str(MOAI_GENERATOR)], check=True)

    # Compatibility names and vendored clients are not separate artwork. Keep
    # every copy mechanically identical to its new MoOS source of truth.
    for size in SIZES:
        source = HICOLOR / f"{size}x{size}/apps/moos-store.png"
        shutil.copyfile(source, HICOLOR / f"{size}x{size}/apps/mo-store.png")
    shutil.copyfile(HICOLOR / "512x512/apps/moos-pc-remote.png", REMOTE_LOGO)
    shutil.copyfile(SCALABLE / "moos-pc-remote.svg", LEGACY_REMOTE_SVG)
    shutil.copyfile(
        HICOLOR / "512x512/apps/moos-pc-remote.png",
        LEGACY_REMOTE_PREVIEW,
    )

    # Contact sheet is review evidence, not a runtime asset.
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

    render_palette_matrix(magick)

    master_dir = ROOT / "artwork/master_icons"
    master_dir.mkdir(parents=True, exist_ok=True)
    for name in ("moos-moai", *MARKS):
        svg = SCALABLE / f"{name}.svg"
        for dest in (
            master_dir / f"{name}.png",
            HICOLOR / f"1024x1024/apps/{name}.png",
        ):
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                magick, "-background", "none", str(svg),
                "-resize", "1024x1024", "-strip", f"PNG32:{dest}",
            ], check=True)

    print(
        f"generated {len(MARKS) + 1} MoOS app icons, "
        f"{PREVIEW.relative_to(ROOT)} and {PALETTE_PREVIEW.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
