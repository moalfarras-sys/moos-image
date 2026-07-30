#!/usr/bin/env python3
"""Generate the MoOS first-party application mark family.

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
TILE = 'x="72" y="72" width="880" height="880" rx="232"'
RIM = 'x="82" y="82" width="860" height="860" rx="222"'

# Nothing below 64 canvas units survives the 16 px dock cell (1 px = 64 units),
# so every load-bearing stroke is >= 76 and every detail cut is >= 48.
MARKS: dict[str, dict[str, str]] = {
    "moos-control-center": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <!-- Drop shadow for the control center glyph -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <rect x="268" y="282" width="488" height="92" rx="46"/>
    <rect x="268" y="466" width="488" height="92" rx="46"/>
    <rect x="268" y="650" width="488" height="92" rx="46"/>
    <circle cx="636" cy="328" r="74"/>
    <circle cx="396" cy="512" r="74"/>
    <circle cx="556" cy="696" r="74"/>
  </g>

  <g class="$INK" fill="currentColor">
    <rect x="268" y="282" width="488" height="92" rx="46" opacity="0.25"/>
    <rect x="268" y="466" width="488" height="92" rx="46" opacity="0.25"/>
    <rect x="268" y="650" width="488" height="92" rx="46" opacity="0.25"/>
    <!-- Active track -->
    <rect x="268" y="282" width="368" height="92" rx="46" fill="url(#${NAME}-glyph-gradient)"/>
    <rect x="268" y="466" width="128" height="92" rx="46" fill="url(#${NAME}-glyph-gradient)"/>
    <rect x="268" y="650" width="288" height="92" rx="46" fill="url(#${NAME}-glyph-gradient)"/>
    
    <!-- Knobs -->
    <circle cx="636" cy="328" r="74" fill="url(#${NAME}-glyph-gradient)"/>
    <circle cx="396" cy="512" r="74" fill="url(#${NAME}-glyph-gradient)"/>
    <circle cx="556" cy="696" r="74" fill="url(#${NAME}-glyph-gradient)"/>
  </g>

  <!-- Knob Inner Bevel / Reflection -->
  <g fill="url(#{name}-white)" opacity="0.3">
    <circle cx="636" cy="320" r="64"/>
    <circle cx="396" cy="504" r="64"/>
    <circle cx="556" cy="688" r="64"/>
  </g>
  <g class="$INK" fill="currentColor">
    <circle cx="636" cy="324" r="64" opacity="0.8"/>
    <circle cx="396" cy="508" r="64" opacity="0.8"/>
    <circle cx="556" cy="692" r="64" opacity="0.8"/>
  </g>

  <g class="$TILE" fill="currentColor">
    <circle cx="636" cy="328" r="34"/>
    <circle cx="396" cy="512" r="34"/>
    <circle cx="556" cy="696" r="34"/>
  </g>
  <!-- Knob indent shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.25">
    <circle cx="636" cy="334" r="34"/>
    <circle cx="396" cy="518" r="34"/>
    <circle cx="556" cy="702" r="34"/>
  </g>
""",
    },
    "moos-store": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <!-- Drop shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <path d="M424 452v-22c0-49 39-88 88-88s88 39 88 88v22" fill="none" stroke="url(#${NAME}-black)" stroke-width="44" stroke-linecap="round"/>
    <path d="M292 452h440l44 330c6 41-26 76-67 76H315c-41 0-73-35-67-76Z"/>
  </g>

  <!-- Back of handle -->
  <g class="$INK" fill="currentColor">
    <path d="M424 452v-22c0-49 39-88 88-88s88 39 88 88v22" fill="none" stroke="currentColor" stroke-width="44" stroke-linecap="round" opacity="0.85"/>
  </g>
  
  <!-- Bag body -->
  <g class="$INK" fill="currentColor">
    <path d="M292 452h440l44 330c6 41-26 76-67 76H315c-41 0-73-35-67-76Z" fill="url(#${NAME}-glyph-gradient)"/>
  </g>

  <!-- 3D Bag Details (glass highlights & folds) -->
  <path d="M312 472h400l40 300c3 20-13 40-40 40H312c-27 0-43-20-40-40Z" fill="url(#{name}-white)" opacity="0.15"/>
  <path d="M322 482h380l36 270c3 20-13 30-36 30H322c-23 0-39-10-36-30Z" fill="url(#{name}-white)" opacity="0.1"/>
""",
    },
    "moos-pc-remote": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <!-- Drop Shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <rect x="228" y="230" width="520" height="376" rx="64"/>
    <rect x="433" y="606" width="110" height="56"/>
    <rect x="352" y="662" width="272" height="62" rx="31"/>
    <rect x="552" y="422" width="268" height="404" rx="80"/>
  </g>

  <!-- Desktop Monitor -->
  <g class="$INK" fill="currentColor">
    <rect x="228" y="230" width="520" height="376" rx="64" fill="url(#${NAME}-glyph-gradient)"/>
    <rect x="433" y="606" width="110" height="56"/>
    <rect x="352" y="662" width="272" height="62" rx="31"/>
  </g>
  <!-- Desktop Screen Bevel/Glow -->
  <rect fill="url(#{name}-white)" opacity="0.15" x="244" y="246" width="488" height="344" rx="48"/>
  <rect class="$TILE" fill="currentColor" x="296" y="298" width="384" height="240" rx="28"/>
  <rect fill="url(#${NAME}-black)" opacity="0.15" x="296" y="298" width="384" height="240" rx="28"/>

  <!-- Phone shadow on monitor -->
  <rect fill="url(#${NAME}-black)" opacity="0.25" x="536" y="414" width="284" height="420" rx="88"/>

  <!-- Phone Body -->
  <rect class="$TILE" fill="currentColor" x="552" y="422" width="268" height="404" rx="80"/>
  <rect class="$INK" fill="currentColor" x="576" y="446" width="220" height="356" rx="58" opacity="0.9"/>
  <!-- Phone Glass Reflection -->
  <rect fill="url(#{name}-white)" opacity="0.12" x="584" y="454" width="204" height="340" rx="50"/>

  <g class="$TILE" fill="currentColor">
    <rect x="656" y="488" width="60" height="18" rx="9"/>
    <rect x="646" y="742" width="80" height="18" rx="9"/>
  </g>
  <g fill="url(#${NAME}-black)" opacity="0.2">
    <rect x="656" y="492" width="60" height="18" rx="9"/>
    <rect x="646" y="746" width="80" height="18" rx="9"/>
  </g>
""",
    },
    "moos-updater": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <!-- Drop Shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <path d="M512 260A252 252 0 1 1 275 426" fill="none" stroke="url(#${NAME}-black)" stroke-width="92"/>
    <path d="M512 186v148l130-74Z"/>
    <rect x="464" y="372" width="96" height="190" rx="20"/>
    <path d="M512 684 382 530h260Z" stroke="url(#${NAME}-black)" stroke-width="36" stroke-linejoin="round"/>
  </g>

  <!-- Ring and Arrow head -->
  <g class="$INK" fill="currentColor">
    <!-- Ring -->
    <path d="M512 260A252 252 0 1 1 275 426" fill="none" stroke="currentColor" stroke-width="92" opacity="0.85"/>
    <path d="M512 260A252 252 0 1 1 275 426" fill="none" stroke="url(#{name}-white)" stroke-width="24" opacity="0.2"/>
    <!-- Outer Triangle -->
    <path d="M512 186v148l130-74Z" fill="url(#${NAME}-glyph-gradient)"/>
  </g>

  <!-- Arrow Body -->
  <g class="$INK" fill="currentColor">
    <rect x="464" y="372" width="96" height="190" rx="20" fill="url(#${NAME}-glyph-gradient)"/>
    <path d="M512 684 382 530h260Z" fill="url(#${NAME}-glyph-gradient)" stroke="currentColor" stroke-width="36" stroke-linejoin="round"/>
  </g>
  
  <g fill="url(#{name}-white)" opacity="0.2">
    <rect x="472" y="380" width="80" height="174" rx="12"/>
    <path d="M512 654 402 546h220Z"/>
  </g>
""",
    },
    "moos-themes": {
        "tile": "Highlight",
        "ink": "HighlightedText",
        "body": """
  <!-- Drop Shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <circle cx="512" cy="442" r="228"/>
    <circle cx="396" cy="806" r="50"/>
    <circle cx="512" cy="806" r="50"/>
    <circle cx="628" cy="806" r="50"/>
  </g>

  <!-- Base Circle -->
  <g class="$INK" fill="currentColor">
    <circle cx="512" cy="442" r="228" opacity=".2"/>
    <!-- Diagonal Slash -->
    <path d="M351 603A228 228 0 0 1 673 281Z" fill="url(#${NAME}-glyph-gradient)"/>
    
    <circle cx="512" cy="442" r="228" fill="none" stroke="currentColor" stroke-width="56" opacity="0.9"/>
    <!-- Inner Ring Bevel -->
    <circle cx="512" cy="442" r="200" fill="none" stroke="url(#{name}-white)" stroke-width="12" opacity="0.2"/>
    <circle cx="512" cy="442" r="256" fill="none" stroke="url(#${NAME}-black)" stroke-width="12" opacity="0.1"/>

    <!-- Bottom Dots -->
    <circle cx="396" cy="806" r="50" fill="url(#${NAME}-glyph-gradient)"/>
    <circle cx="512" cy="806" r="50" opacity=".62"/>
    <circle cx="628" cy="806" r="50" opacity=".34"/>
  </g>
  <g fill="url(#{name}-white)" opacity="0.2">
    <circle cx="396" cy="796" r="34"/>
    <circle cx="512" cy="796" r="34"/>
    <circle cx="628" cy="796" r="34"/>
  </g>
""",
    },
    "moos-installer": {
        "tile": "PositiveText",
        "ink": "Background",
        "body": """
  <!-- Drop Shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <rect x="452" y="196" width="120" height="250" rx="30"/>
    <path d="M512 686 336 458h352Z" stroke="url(#${NAME}-black)" stroke-width="40" stroke-linejoin="round"/>
    <rect x="272" y="760" width="480" height="96" rx="48"/>
  </g>

  <g class="$INK" fill="currentColor">
    <rect x="452" y="196" width="120" height="250" rx="30" fill="url(#${NAME}-glyph-gradient)"/>
    <path d="M512 686 336 458h352Z" fill="url(#${NAME}-glyph-gradient)" stroke="currentColor" stroke-width="40" stroke-linejoin="round"/>
    <rect x="272" y="760" width="480" height="96" rx="48" fill="url(#${NAME}-glyph-gradient)"/>
  </g>

  <g fill="url(#{name}-white)" opacity="0.2">
    <rect x="464" y="208" width="96" height="226" rx="18"/>
    <path d="M512 636 386 478h252Z"/>
    <rect x="284" y="772" width="456" height="48" rx="24"/>
  </g>
""",
    },
    "moos-recovery": {
        "tile": "NegativeText",
        "ink": "Background",
        "body": """
  <!-- Drop Shadow for Shield -->
  <g fill="url(#${NAME}-black)" opacity="0.25" transform="translate(0, 16)">
    <path d="M512 176c96 62 196 82 268 88v236c0 200-110 268-268 324-158-56-268-124-268-324V264c72-6 172-26 268-88Z"/>
  </g>

  <!-- Shield -->
  <path class="$INK" fill="url(#${NAME}-glyph-gradient)"
        d="M512 176c96 62 196 82 268 88v236c0 200-110 268-268 324-158-56-268-124-268-324V264c72-6 172-26 268-88Z"/>
  <!-- Shield Edge Highlight -->
  <path fill="none" stroke="url(#{name}-white)" stroke-width="16" stroke-opacity="0.25"
        d="M512 192c88 56 182 76 250 82v226c0 186-104 248-250 298-146-50-250-112-250-298V274c68-6 162-26 250-82Z"/>

  <!-- Cross Shadow inside Shield -->
  <g fill="url(#${NAME}-black)" opacity="0.15" transform="translate(0, 12)">
    <rect x="470" y="390" width="84" height="224" rx="22"/>
    <rect x="400" y="460" width="224" height="84" rx="22"/>
  </g>
  <!-- Cross -->
  <g class="$TILE" fill="currentColor">
    <rect x="470" y="390" width="84" height="224" rx="22"/>
    <rect x="400" y="460" width="224" height="84" rx="22"/>
  </g>
  <g fill="url(#{name}-white)" opacity="0.2">
    <rect x="478" y="398" width="68" height="208" rx="14"/>
    <rect x="408" y="468" width="208" height="68" rx="14"/>
  </g>
""",
    },
    "moos-welcome": {
        "tile": "Text",
        "ink": "Background",
        "body": """
  <!-- Drop Shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.15" transform="translate(0, 16)">
    <path d="M320 560a192 192 0 0 1 384 0Z"/>
    <rect x="248" y="560" width="528" height="72" rx="36"/>
    <g fill="none" stroke="url(#${NAME}-black)" stroke-width="64" stroke-linecap="round">
      <path d="M294 481 215 452"/>
      <path d="M379 370 331 301"/>
      <path d="M512 328v-84"/>
      <path d="M645 370 693 301"/>
      <path d="M730 481 809 452"/>
    </g>
    <rect x="300" y="686" width="424" height="50" rx="25"/>
    <rect x="356" y="772" width="312" height="50" rx="25"/>
  </g>

  <g class="$INK" fill="currentColor">
    <!-- Sun -->
    <path d="M320 560a192 192 0 0 1 384 0Z" fill="url(#${NAME}-glyph-gradient)"/>
    <!-- Horizon -->
    <rect x="248" y="560" width="528" height="72" rx="36" fill="url(#${NAME}-glyph-gradient)"/>
    <!-- Rays -->
    <g fill="none" stroke="currentColor" stroke-width="64" stroke-linecap="round" opacity=".6">
      <path d="M294 481 215 452"/>
      <path d="M379 370 331 301"/>
      <path d="M512 328v-84"/>
      <path d="M645 370 693 301"/>
      <path d="M730 481 809 452"/>
    </g>
    <!-- Ocean Waves -->
    <rect x="300" y="686" width="424" height="50" rx="25" opacity=".6" fill="url(#${NAME}-glyph-gradient)"/>
    <rect x="356" y="772" width="312" height="50" rx="25" opacity=".4" fill="url(#${NAME}-glyph-gradient)"/>
  </g>
  <!-- Highlights -->
  <g fill="url(#{name}-white)" opacity="0.2">
    <path d="M336 544a176 176 0 0 1 352 0Z"/>
    <rect x="256" y="568" width="512" height="40" rx="20"/>
  </g>
""",
    },
    "moos-moplayer": {
        "tile": "NeutralText",
        "ink": "Background",
        "body": """
  <!-- Drop Shadow -->
  <g fill="url(#${NAME}-black)" opacity="0.2" transform="translate(0, 16)">
    <path d="M275 654V334c0-38 28-66 66-66h18c24 0 46 13 58 34l84 148 84-148c12-21 34-34 58-34h18c38 0 66 28 66 66v320h-92V434l-92 158c-9 16-24 24-42 24s-33-8-42-24l-92-158v220Z"/>
    <path d="M252 760c126 58 242 26 330-66 82-86 140-120 202-128" fill="none" stroke="url(#${NAME}-black)" stroke-width="64" stroke-linecap="round"/>
  </g>

  <g class="$INK" fill="currentColor">
    <!-- The M -->
    <path d="M275 654V334c0-38 28-66 66-66h18c24 0 46 13 58 34l84 148 84-148c12-21 34-34 58-34h18c38 0 66 28 66 66v320h-92V434l-92 158c-9 16-24 24-42 24s-33-8-42-24l-92-158v220Z" fill="url(#${NAME}-glyph-gradient)"/>
    <!-- The Current -->
    <path d="M252 760c126 58 242 26 330-66 82-86 140-120 202-128" fill="none"
          stroke="currentColor" stroke-width="64" stroke-linecap="round" opacity=".7"/>
    <path d="M252 760c126 58 242 26 330-66 82-86 140-120 202-128" fill="none"
          stroke="url(#{name}-white)" stroke-width="16" stroke-linecap="round" opacity=".2"/>
  </g>
""",
    },
}


def icon_svg(name: str, mark: dict[str, str]) -> str:
    stylesheet = "\n".join(
        f"      .ColorScheme-{role} {{ color: {value}; }}"
        for role, value in FALLBACK_STYLESHEET.items()
    )
    body = string.Template(mark["body"].strip("\n")).substitute(
        INK=f"ColorScheme-{mark['ink']}",
        TILE=f"ColorScheme-{mark['tile']}",
        NAME=name,
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <!-- MoOS UI — Liquid Glass application mark: {name}.
       Original vector geometry. Every ink is a KDE colour role, and MoOS bakes
       one copy of this file per palette icon theme — MoOS pins
       FollowsColorScheme=false, so nothing re-colours it at runtime. The
       stylesheet below is the MoOS default palette (MoOSUI2Dark) and is what
       every renderer outside those themes shows.
       Regenerate with artwork/generate_moos_app_icons.py. -->
  <defs>
    <style id="current-color-scheme" type="text/css">
{stylesheet}
    </style>
    <linearGradient id="{name}-tile-light" x1="512" y1="72" x2="512" y2="952" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.45"/>
      <stop offset="0.25" stop-color="#ffffff" stop-opacity="0.10"/>
      <stop offset="0.75" stop-color="#000" stop-opacity="0.10"/>
      <stop offset="1" stop-color="#000" stop-opacity="0.45"/>
    </linearGradient>
    <linearGradient id="{name}-rim-light" x1="512" y1="72" x2="512" y2="952" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.9"/>
      <stop offset="0.4" stop-color="#ffffff" stop-opacity="0.1"/>
      <stop offset="0.8" stop-color="#000" stop-opacity="0.2"/>
      <stop offset="1" stop-color="#000" stop-opacity="0.6"/>
    </linearGradient>
    <radialGradient id="{name}-glow" cx="512" cy="200" r="700" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.3"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="{name}-glyph-gradient" x1="512" y1="200" x2="512" y2="800" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="currentColor" stop-opacity="1.0"/>
      <stop offset="1" stop-color="currentColor" stop-opacity="0.7"/>
    </linearGradient>
    <linearGradient id="{name}-black">
      <stop offset="0" stop-color="#000"/>
      <stop offset="1" stop-color="#000"/>
    </linearGradient>
    <linearGradient id="{name}-white">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#ffffff"/>
    </linearGradient>
  </defs>

  <!-- 3D Drop Shadows (Rendered beneath the tile) -->
  <rect fill="url(#{name}-black)" opacity="0.05" x="72" y="104" width="880" height="880" rx="232"/>
  <rect fill="url(#{name}-black)" opacity="0.10" x="72" y="92" width="880" height="880" rx="232"/>
  <rect fill="url(#{name}-black)" opacity="0.15" x="72" y="80" width="880" height="880" rx="232"/>

  <!-- Base Color -->
  <rect class="ColorScheme-{mark['tile']}" fill="currentColor" {TILE}/>
  
  <!-- Liquid Glass Shading -->
  <rect fill="url(#{name}-tile-light)" {TILE}/>
  <rect fill="url(#{name}-glow)" {TILE}/>
  
  <!-- Outer Bevel/Rim -->
  <rect fill="none" stroke="url(#{name}-rim-light)" stroke-width="12" {RIM}/>
  <rect fill="none" stroke="url(#{name}-white)" stroke-opacity="0.3" stroke-width="4" x="76" y="76" width="872" height="872" rx="228"/>
  
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
            "-background", "#000", str(PALETTE_PREVIEW),
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
    # ImageMagick numbers output files when an older tile layout spills onto
    # multiple pages.  Remove only those known contact-sheet shards so changing
    # the grid cannot leave stale review evidence beside the current preview.
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

    # Second sheet: the same marks with six real MoOS palettes baked in, each
    # row on that palette's own window colour. This is the evidence that "the
    # marks follow the theme" is a rendered fact, not a claim about markup —
    # every row is what the matching icon theme actually installs.
    render_palette_matrix(magick)
    print(
        f"generated {len(MARKS) + 1} MoOS app icons, "
        f"{PREVIEW.relative_to(ROOT)} and {PALETTE_PREVIEW.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
