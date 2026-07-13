#!/usr/bin/env python3
"""Generate the LIGHT half of the MoOS Nova theme from the dark original.

MoOS shipped one look: Nova Dark. The user asked for a light theme too — one
that is genuinely restful, not a dark theme with the lightness inverted.

Three things had to be built, and only one of them needed new art:

  * The Plasma style (desktoptheme). Nova's SVGs already carry Plasma's
    ColorScheme stylesheet, so they recolour themselves from whichever `colors`
    file the active theme ships. A light style is therefore metadata + a light
    `colors` file + a plasmarc that falls back to Nova for the SVGs. No SVG is
    copied, and there is exactly one set of widget art to maintain.

  * The window decoration (Aurorae). This one DOES have hardcoded colours —
    Aurorae has no ColorScheme stylesheet — so the light decoration is generated
    here, from the dark one, by an explicit colour map. Generating it (rather
    than hand-copying 20 KB of SVG) is what keeps the two decorations from
    drifting apart the next time the dark one is touched.

  * Konsole. Its colour scheme is not a KDE colour scheme and does not follow
    one; it needs its own file.

Run from the repo root:  python3 artwork/generate_nova_light.py
Idempotent — it rewrites its outputs from scratch every time.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHARE = REPO / "system_files/usr/share"

AURORAE = SHARE / "aurorae/themes"
DESKTOPTHEME = SHARE / "plasma/desktoptheme"
KONSOLE = SHARE / "konsole"

# ── The colour map ───────────────────────────────────────────────────────────
# Dark hex → light hex, applied to the Aurorae SVGs. Every entry is a colour the
# dark decoration actually uses; anything not listed here (the drop shadows, the
# traffic-light red/amber/green) is DELIBERATELY left alone — a shadow is dark in
# both themes, and the close button is red in both.
DECORATION_COLORS = {
    # Active title bar gradient: navy → white-on-porcelain.
    "#263557": "#FFFFFF",
    "#161F38": "#EDF2FA",
    # Inactive title bar gradient.
    "#1B2540": "#F7F9FD",
    "#131B31": "#E9EFF8",
    # Frame / border fill (the 1px sides and bottom of the window).
    "#0B1220": "#E2EAF7",
    # The inactive button dot. The only button colour that is not shared: a mid
    # slate reads as "off" on navy and as a smudge on porcelain.
    "#46536B": "#C4CFDF",
}

# The hairlines. In the dark theme the top edge is a white highlight over navy
# and the inner edge is a near-black shade. On porcelain both must invert their
# roles or the title bar grows a black rim.
#
# Keyed on (colour, opacity) because #04070F and #FFFFFF each appear at several
# opacities and mean something different at each.
DECORATION_HAIRLINES = {
    ("#04070F", "0.55"): ("#0B1220", "0.10"),   # inner shade, active
    ("#04070F", "0.35"): ("#0B1220", "0.07"),   # inner shade, inactive
    ("#FFFFFF", "0.11"): ("#FFFFFF", "0.85"),   # top highlight, active
    ("#FFFFFF", "0.05"): ("#FFFFFF", "0.65"),   # top highlight, inactive
}


def light_svg(text: str) -> str:
    """Recolour one Aurorae SVG from dark to light."""
    # Hairlines first: they are (fill, fill-opacity) pairs, and rewriting the
    # bare colour first would destroy the information needed to tell them apart.
    def hairline(match: re.Match) -> str:
        colour, opacity = match.group(1).upper(), match.group(2)
        new = DECORATION_HAIRLINES.get((colour, opacity))
        if new is None:
            return match.group(0)
        return f'fill="{new[0]}" fill-opacity="{new[1]}"'

    text = re.sub(
        r'fill="(#[0-9A-Fa-f]{6})" fill-opacity="([0-9.]+)"', hairline, text
    )

    for dark, light in DECORATION_COLORS.items():
        text = re.sub(re.escape(dark), light, text, flags=re.IGNORECASE)
    return text


def build_decoration() -> None:
    src = AURORAE / "MoOSNova"
    dst = AURORAE / "MoOSNovaLight"
    dst.mkdir(parents=True, exist_ok=True)

    for svg in sorted(src.glob("*.svg")):
        (dst / svg.name).write_text(light_svg(svg.read_text()), encoding="utf-8")

    # The rc: same geometry, inverted text. Aurorae takes its title colour from
    # here, not from the colour scheme, so a light decoration with the dark rc
    # writes near-white text onto a near-white title bar.
    rc = (src / "MoOSNovarc").read_text(encoding="utf-8")
    rc = rc.replace(
        "ActiveTextColor=230,237,247,255", "ActiveTextColor=16,24,40,255"
    ).replace(
        "InactiveTextColor=150,166,190,255", "InactiveTextColor=113,128,150,255"
    )
    (dst / "MoOSNovaLightrc").write_text(rc, encoding="utf-8")

    meta = (src / "metadata.desktop").read_text(encoding="utf-8")
    meta = re.sub(r"^Name=.*$", "Name=MoOS Nova Light", meta, flags=re.MULTILINE)
    meta = re.sub(
        r"^X-KDE-PluginInfo-Name=.*$",
        "X-KDE-PluginInfo-Name=MoOSNovaLight",
        meta,
        flags=re.MULTILINE,
    )
    (dst / "metadata.desktop").write_text(meta, encoding="utf-8")
    print(f"decoration → {dst.relative_to(REPO)}")


def build_plasma_style() -> None:
    """NovaLight: metadata + colours + a fallback to Nova. No SVGs, on purpose."""
    dst = DESKTOPTHEME / "NovaLight"
    dst.mkdir(parents=True, exist_ok=True)

    (dst / "metadata.json").write_text(
        """{
    "KPlugin": {
        "Authors": [
            {
                "Name": "Moalfarras"
            }
        ],
        "Category": "",
        "Description": "زجاج Nova الفاتح وهوية MoOS للنظام | Nova light glass and MoOS identity for the desktop",
        "Id": "NovaLight",
        "License": "GPL-3.0-or-later",
        "Name": "MoOS Nova Light",
        "Version": "0.1.0",
        "Website": "https://github.com/moalfarras-sys/moos-image"
    },
    "X-Plasma-API": "5.0"
}
""",
        encoding="utf-8",
    )

    (dst / "plasmarc").write_text(
        """# MoOS Nova Light — Plasma Style per-theme config.
#
# FallbackTheme=Nova is the whole trick, and it is why this directory holds no
# SVG at all. Plasma's ThemePrivate::setThemeName() follows the FallbackTheme
# chain for SVG LOOKUP but keeps the ACTIVE theme's `colors` file for the
# palette — and every Nova SVG is written against Plasma's ColorScheme
# stylesheet. So NovaLight borrows Nova's artwork and paints it with the light
# palette below. One set of widget art, two themes; they cannot drift apart.
#
# Chain: NovaLight (colors) -> Nova (SVGs) -> breeze-dark -> default (Breeze
# geometry). Nothing in that chain hardcodes a dark fill.
[Settings]
FallbackTheme=Nova

[Wallpaper]
defaultWallpaperTheme=NovaAurora
defaultFileSuffix=.png
defaultWidth=1920
defaultHeight=1080

[AdaptiveTransparency]
enabled=true
""",
        encoding="utf-8",
    )

    # The Plasma style's palette IS the colour scheme — same file, so a popup and
    # a window can never disagree about what "light" means.
    colors = (SHARE / "color-schemes/NovaLight.colors").read_text(encoding="utf-8")
    header = (
        "# MoOS Nova Light — Plasma Style (desktoptheme) colour stylesheet.\n"
        "#\n"
        "# Generated by artwork/generate_nova_light.py from\n"
        "# /usr/share/color-schemes/NovaLight.colors. It is a copy on purpose: the\n"
        "# Plasma style and the colour scheme must agree exactly, or a notification\n"
        "# popup ends up a different shade of white from the window behind it.\n"
        "# Edit NovaLight.colors and re-run the generator; do not edit this by hand.\n"
        "\n"
    )
    (dst / "colors").write_text(header + colors, encoding="utf-8")
    print(f"plasma style → {dst.relative_to(REPO)}")


def build_konsole_scheme() -> None:
    """A light terminal that is not a white wall.

    Konsole colour schemes are not KDE colour schemes and do not follow one, so
    a light desktop with the dark profile still gives a black terminal. The
    background here is #F7F9FD rather than pure white: at a terminal's contrast
    ratio, #FFF against near-black text is what makes people's eyes ache.
    """
    (KONSOLE / "NovaLight.colorscheme").write_text(
        """[Background]
Color=247,249,253

[BackgroundIntense]
Color=255,255,255

[BackgroundFaint]
Color=238,243,251

[Foreground]
Color=16,24,40

[ForegroundIntense]
Color=5,10,20

[ForegroundFaint]
Color=113,128,150

[Color0]
Color=226,234,247

[Color0Intense]
Color=203,215,233

[Color1]
Color=200,30,30

[Color1Intense]
Color=220,38,38

[Color2]
Color=4,120,87

[Color2Intense]
Color=5,150,105

[Color3]
Color=161,98,7

[Color3Intense]
Color=180,120,0

[Color4]
Color=30,79,216

[Color4Intense]
Color=46,123,255

[Color5]
Color=109,40,217

[Color5Intense]
Color=139,92,246

[Color6]
Color=14,116,144

[Color6Intense]
Color=8,145,178

[Color7]
Color=16,24,40

[Color7Intense]
Color=5,10,20

[General]
Blur=false
ColorRandomization=false
Description=Nova Light
Opacity=1
Wallpaper=
""",
        encoding="utf-8",
    )

    profile = (KONSOLE / "MoOS.profile").read_text(encoding="utf-8")
    profile = profile.replace("ColorScheme=NovaDark", "ColorScheme=NovaLight")
    profile = profile.replace("Name=MoOS", "Name=MoOS Light")
    (KONSOLE / "MoOSLight.profile").write_text(profile, encoding="utf-8")
    print("konsole → NovaLight.colorscheme + MoOSLight.profile")


if __name__ == "__main__":
    build_decoration()
    build_plasma_style()
    build_konsole_scheme()
