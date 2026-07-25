#!/usr/bin/env python3
"""Generate the canonical MoOS UI Graphite/Tidal visual family.

The committed Graphite UI2 packages are the maintained geometry source.
Generation is transactional, and Plasma Dark and Light each receive a complete
SVG suite; Light never inherits UI2 Dark's fixed-colour artwork.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile


# Tests may point the generator at a synthetic repository tree.  Production
# runs deliberately ignore the failure-injection knob unless that isolated root
# is present, so an inherited environment variable can never damage the real
# working tree.
TEST_ROOT = os.environ.get("MOOS_UI2_TEST_ROOT")
ROOT = (pathlib.Path(TEST_ROOT).resolve() if TEST_ROOT
        else pathlib.Path(__file__).resolve().parents[1])
SHARE = ROOT / "system_files/usr/share"
ART = ROOT / "artwork/moos-ui2"
PALETTES = json.loads((ART / "palette.json").read_text(encoding="utf-8"))
# The dashboard bento lives INSIDE the scene wallpaper plugin now (it used to
# be a desktop applet, which always drew over the icons). Writing the retired
# plasmoid path would recreate a package two gates forbid.
DASHBOARD_WEATHER = (SHARE / "plasma/wallpapers/org.moos.ui2.wallpaper"
                     / "contents/images/weather")
WEATHER_KINDS = (
    "clear-day", "clear-night", "partly-day", "partly-night", "cloudy",
    "rain", "snow", "fog", "storm",
)

OUTPUTS = (
    SHARE / "plasma/desktoptheme/MoOSUI2",
    SHARE / "plasma/desktoptheme/MoOSUI2Light",
    SHARE / "plasma/look-and-feel/org.moos.ui2",
    SHARE / "plasma/look-and-feel/org.moos.ui2.light",
    SHARE / "aurorae/themes/MoOSUI2",
    SHARE / "aurorae/themes/MoOSUI2Light",
    SHARE / "color-schemes/MoOSUI2Dark.colors",
    SHARE / "color-schemes/MoOSUI2Light.colors",
    SHARE / "konsole/MoOSUI2Dark.colorscheme",
    SHARE / "konsole/MoOSUI2Light.colorscheme",
    SHARE / "konsole/MoOSUI2.profile",
    SHARE / "konsole/MoOSUI2Light.profile",
    SHARE / "wallpapers/MoOSUI2Graphite",
    SHARE / "wallpapers/MoOSUI2Tide",
    DASHBOARD_WEATHER,
)

# UI1 was intentionally removed from the shipped image in July 2026.  The
# generator nevertheless kept reading that deleted tree and became impossible
# to run.  UI2 Graphite is now the canonical visual source.  During generation
# these three packages are moved into the transaction backup and read from
# there, so the process remains deterministic and can still restore every byte
# if a later export fails.
CANONICAL_SOURCES = (
    SHARE / "plasma/desktoptheme/MoOSUI2",
    SHARE / "plasma/look-and-feel/org.moos.ui2",
    SHARE / "aurorae/themes/MoOSUI2",
)

# UI1's Plasma SVGs contain older Nova colours as literal fills. Every source
# colour is assigned a semantic role here so UI2 cannot reproduce the Light
# inherits-Dark regression by accident.
SOURCE_HEX_ROLE = {
    "#0C0910": "shadow", "#100C14": "shadow",
    "#0E1728": "canvas", "#110D15": "canvas", "#17131D": "canvas",
    "#131B31": "surface", "#13213A": "surface", "#241D2B": "surface",
    "#161F38": "card", "#162743": "card", "#2A2031": "card",
    "#163059": "raised", "#1B2540": "raised", "#312538": "raised",
    "#3A2B43": "outline", "#46536B": "outline",
    "#4B6287": "muted", "#7F94B5": "muted", "#B8AABD": "muted",
    "#1E4FD8": "secondary", "#6D28D9": "secondary", "#FB923C": "secondary",
    "#4FC3FF": "luminous", "#76DDF7": "luminous", "#7DEBFF": "luminous",
    "#A855F7": "primary", "#C084FC": "luminous", "#FF00FF": "primary",
    "#EEE7F0": "text", "#F3ECF4": "text",
    "#34D399": "positive", "#F87171": "negative", "#FBBF24": "warning",
    "#06291D": "positive_deep", "#2A1113": "negative_deep",
    "#2E2205": "warning_deep",
}

SOURCE_RGB_ROLE = {
    "16,12,20": "shadow", "23,19,29": "canvas", "36,29,43": "surface",
    "49,37,56": "raised", "91,107,133": "muted", "91,107,140": "muted",
    "150,166,190": "muted", "184,170,189": "muted",
    "168,85,247": "primary", "192,132,252": "luminous",
    "216,100,164": "secondary", "251,146,60": "secondary",
    "30,79,216": "secondary_deep", "125,235,255": "luminous",
    "238,231,240": "text", "243,236,244": "selected_text",
    "226,234,247": "selected_text", "226,213,255": "selected_text",
    "52,211,153": "positive", "190,255,225": "selected_text",
    "248,113,113": "negative", "255,205,205": "selected_text",
    "251,191,36": "warning", "255,228,160": "selected_text",
    "103,232,249": "luminous", "106,166,255": "secondary",
    "110,231,183": "positive", "126,140,166": "muted",
    "154,70,70": "negative_deep", "163,126,28": "warning_deep",
    "167,139,250": "secondary", "199,211,232": "selected_text",
    "23,140,158": "primary", "252,165,165": "negative",
    "252,211,77": "warning", "31,138,100": "positive_deep",
    "31,83,168": "secondary_deep", "93,62,166": "secondary_deep",
}

EXTRAS = {
    "dark": {
        "positive_deep": "#1D4538", "negative_deep": "#49282D",
        "warning_deep": "#493B22", "secondary_deep": "#315C8E",
        "selected_text": "#142220",
    },
    "light": {
        "positive_deep": "#B7D9C9", "negative_deep": "#E7C3C7",
        "warning_deep": "#E4D3B1", "secondary_deep": "#78A8B8",
        "selected_text": "#E1F0EC",
    },
}


def rgb(value: str) -> str:
    value = value.lstrip("#")
    return ",".join(str(int(value[i:i + 2], 16)) for i in (0, 2, 4))


def variant_roles(variant: str) -> dict[str, str]:
    return PALETTES[variant] | EXTRAS[variant]


def palette_map(variant: str) -> dict[str, str]:
    roles = variant_roles(variant)
    mapping = {source: roles[role] for source, role in SOURCE_HEX_ROLE.items()}
    mapping |= {source: rgb(roles[role]) for source, role in SOURCE_RGB_ROLE.items()}
    # The maintained template is the current Graphite package rather than the
    # retired UI1 package.  Map every dark semantic role into the requested
    # half so Light inherits the exact same geometry, spacing, and motion while
    # still owning a distinct palette.
    dark = variant_roles("dark")
    mapping |= {
        dark[role]: roles[role]
        for role in dark.keys() & roles.keys()
    }
    mapping |= {
        rgb(dark[role]): rgb(roles[role])
        for role in dark.keys() & roles.keys()
    }
    return mapping


def rewrite_text(text: str, mapping: dict[str, str]) -> str:
    # Replace in one pass. Sequential ``str.replace`` is unsafe for identity
    # migrations because a replacement can itself contain another source key:
    # NovaActionButton -> MoOSUI2ActionButton -> MoOSUI22ActionButton. The bad
    # component name leaves the logout greeter with a QML type that does not
    # exist even though all generated files and metadata are otherwise present.
    pattern = re.compile("|".join(re.escape(old) for old in sorted(mapping, key=len, reverse=True)))
    return pattern.sub(lambda match: mapping[match.group(0)], text)


def rewrite_tree(root: pathlib.Path, mapping: dict[str, str]) -> None:
    binary = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in binary:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        path.write_text(rewrite_text(text, mapping), encoding="utf-8")


def copy_generated(source: pathlib.Path, target: pathlib.Path, variant: str) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    # The canonical source is already UI2. Re-applying the retired UI1 identity
    # substitutions would turn MoOSUI2 into MoOSUI22 and break QML types.
    rewrite_tree(target, palette_map(variant))


def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


# Glass translucency, per half. Dark and Light are ONE material with two
# profiles, not one dark-tuned value forced onto both: a light glass needs a
# denser floor so dark tray icons / clock / text stay legible over wallpaper.
# The DARK values are byte-identical to the shipped Liquid Glass — do not touch
# them (that is the maintainer's proven dock). Only Light diverges.
OPACITY = {
    "dark": {
        "@GLASS_P0@": "0.70", "@GLASS_P1@": "0.76", "@GLASS_P2@": "0.84", "@GLASS_P3@": "0.88",
        "@RIM_LUM@": "0.62", "@RIM_ACCENT@": "0.42", "@RIM_OUTLINE@": "0.28",
        "@DLG_P0@": "0.70", "@DLG_P1@": "0.74", "@DLG_P2@": "0.78", "@DLG_P3@": "0.80",
        "@DLG_RIM_LUM@": "0.60", "@DLG_RIM_OUTLINE@": "0.24", "@DLG_RIM_ACCENT@": "0.34",
    },
    "light": {
        # Capped at 0.93 so the light dock stays denser than dark (legible dark
        # icons over wallpaper) yet never crosses the 0.93 ceiling above which
        # KWin's frost stops showing (enforced by test_glass_surfaces_*).
        "@GLASS_P0@": "0.82", "@GLASS_P1@": "0.87", "@GLASS_P2@": "0.91", "@GLASS_P3@": "0.93",
        "@RIM_LUM@": "0.46", "@RIM_ACCENT@": "0.14", "@RIM_OUTLINE@": "0.30",
        "@DLG_P0@": "0.82", "@DLG_P1@": "0.85", "@DLG_P2@": "0.90", "@DLG_P3@": "0.92",
        "@DLG_RIM_LUM@": "0.44", "@DLG_RIM_OUTLINE@": "0.26", "@DLG_RIM_ACCENT@": "0.22",
    },
}


def _glass_opacity(variant: str, light: bool | None) -> dict[str, str]:
    if light is None:
        light = variant == "light"
    return OPACITY["light" if light else "dark"]


def render_panel(target: pathlib.Path, variant: str, light: bool | None = None) -> None:
    tokens = variant_roles(variant)
    text = (ART / "plasma/panel-background.svg.in").read_text(encoding="utf-8")
    substitutions = {
        "@SURFACE@": tokens["surface"], "@PRIMARY@": tokens["primary"],
        "@TEXT@": tokens["text"], "@LUMINOUS@": tokens["luminous"],
        "@OUTLINE@": tokens["outline"], "@PANEL_TOP@": tokens["panel_top"],
        "@PANEL_MID@": tokens["panel_mid"], "@PANEL_BOTTOM@": tokens["panel_bottom"],
        **_glass_opacity(variant, light),
    }
    write(target, rewrite_text(text, substitutions))


def render_dialog(target: pathlib.Path, variant: str, light: bool | None = None) -> None:
    """Render the popup FrameSvg and its rounded KWin blur mask.

    Unlike ordinary fixed-colour assets, the mask is a structural contract:
    Plasma reads the nine mask-* elements to delimit the frosted region.  Keep
    the reviewed geometry in artwork and render only semantic palette tokens.
    """
    tokens = variant_roles(variant)
    text = (ART / "plasma/dialog-background.svg.in").read_text(encoding="utf-8")
    substitutions = {
        "@CANVAS@": tokens["canvas"], "@SURFACE@": tokens["surface"],
        "@CARD@": tokens["card"], "@PRIMARY@": tokens["primary"],
        "@TEXT@": tokens["text"], "@LUMINOUS@": tokens["luminous"],
        "@OUTLINE@": tokens["outline"],
        **_glass_opacity(variant, light),
    }
    write(target, rewrite_text(text, substitutions))


def desktop_metadata(style: str, light: bool) -> str:
    description = ("تركواز معدني هادئ لسطح MoOS | Mineral turquoise glass for MoOS"
                   if light else
                   "زجاج غرافيتي حديث لسطح MoOS | Modern graphite glass for MoOS")
    return json.dumps({
        "KPlugin": {
            "Authors": [{"Name": "Moalfarras"}], "Category": "",
            "Description": description, "Id": style,
            "License": "GPL-3.0-or-later",
            "Name": "MoOS UI Light" if light else "MoOS UI",
            "Name[ar]": "MoOS UI الفاتح" if light else "MoOS UI",
            "Version": "2.0.0",
            "Website": "https://github.com/moalfarras-sys/moos-image",
        },
        "X-Plasma-API": "5.0",
    }, ensure_ascii=False, indent=4)


def desktop_plasmarc(wallpaper: str, light: bool) -> str:
    fallback = "default" if light else "breeze-dark"
    return f"""# Generated by artwork/generate_moos_ui2.py.
# Each UI2 variant owns a complete fixed-colour SVG suite. Light never falls
# back to UI2 Dark; only missing upstream paths use the matching Breeze side.
[Settings]
FallbackTheme={fallback}

[Wallpaper]
defaultWallpaperTheme={wallpaper}
defaultFileSuffix=.jpg
defaultWidth=1920
defaultHeight=1080

[AdaptiveTransparency]
enabled=false
"""


def color_scheme(variant: str) -> str:
    p = variant_roles(variant)
    selected = p["selected_text"]

    def group(name: str, normal: str, alternate: str, inactive: str | None = None) -> str:
        muted = inactive or p["muted"]
        return f"""[{name}]
BackgroundAlternate={rgb(alternate)}
BackgroundNormal={rgb(normal)}
DecorationFocus={rgb(p['primary'])}
DecorationHover={rgb(p['luminous'])}
ForegroundActive={rgb(p['primary'])}
ForegroundInactive={rgb(muted)}
ForegroundLink={rgb(p['secondary'])}
ForegroundNegative={rgb(p['negative'])}
ForegroundNeutral={rgb(p['warning'])}
ForegroundNormal={rgb(p['text'])}
ForegroundPositive={rgb(p['positive'])}
ForegroundVisited={rgb(p['luminous'])}
"""

    selection = f"""[Colors:Selection]
BackgroundAlternate={rgb(p['secondary'])}
BackgroundNormal={rgb(p['primary'])}
DecorationFocus={rgb(p['luminous'])}
DecorationHover={rgb(p['luminous'])}
ForegroundActive={rgb(selected)}
ForegroundInactive={rgb(selected)}
ForegroundLink={rgb(selected)}
ForegroundNegative={rgb(selected)}
ForegroundNeutral={rgb(selected)}
ForegroundNormal={rgb(selected)}
ForegroundPositive={rgb(selected)}
ForegroundVisited={rgb(selected)}
"""
    scheme_name = "MoOSUI2Light" if variant == "light" else "MoOSUI2Dark"
    display_name = "MoOS UI Light" if variant == "light" else "MoOS UI Dark"
    return f"""# Generated from artwork/moos-ui2/palette.json. Do not hand-edit.
[ColorEffects:Disabled]
Color={rgb(p['raised'])}
ColorAmount=0.3
ColorEffect=2
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color={rgb(p['raised'])}
ColorAmount=0.5
ColorEffect=3
ContrastAmount=0
ContrastEffect=0
Enable=true
IntensityAmount=0
IntensityEffect=0

{group('Colors:Button', p['raised'], p['card'])}
{group('Colors:Complementary', p['canvas'], p['surface'])}
{group('Colors:Header', p['surface'], p['card'])}
{group('Colors:Header][Inactive', p['surface'], p['surface'], p['muted'])}
{selection}
{group('Colors:Tooltip', p['card'], p['raised'])}
{group('Colors:View', p['canvas'], p['card'])}
{group('Colors:Window', p['surface'], p['card'])}
[General]
AccentColor={rgb(p['primary'])}
ColorScheme={scheme_name}
Name={display_name}
shadeSortColumn=true

[KDE]
contrast=4

[WM]
activeBackground={rgb(p['card'])}
activeBlend={rgb(p['text'])}
activeForeground={rgb(p['text'])}
inactiveBackground={rgb(p['surface'])}
inactiveBlend={rgb(p['muted'])}
inactiveForeground={rgb(p['muted'])}
"""


def konsole_scheme(variant: str, light: bool | None = None) -> str:
    p = variant_roles(variant)
    # Family light siblings register under keys like "nova-light", so the name
    # test alone would mis-detect them as dark and swap ANSI 0/7. Callers pass
    # light explicitly; the default preserves the base Graphite/Tidal behaviour.
    if light is None:
        light = variant == "light"
    name = "MoOS UI Light" if light else "MoOS UI Dark"
    background = p["card"] if light else p["canvas"]
    base0 = p["text"] if light else p["raised"]
    base7 = p["muted"] if light else p["text"]
    terminal = {
        0: (base0, p["surface"], p["muted"]),
        1: (p["negative"], p["negative_deep"], p["negative"]),
        2: (p["positive"], p["positive_deep"], p["positive"]),
        3: (p["warning"], p["warning_deep"], p["warning"]),
        4: (p["secondary"], p["secondary_deep"], p["secondary"]),
        5: (p["primary"], p["secondary_deep"], p["luminous"]),
        6: (p["luminous"], p["primary"], p["luminous"]),
        # Intense (bold) white must stay on the foreground side of the palette.
        # It used to be p["selected_text"] — the ink for text drawn ON an accent
        # highlight, which is dark in the dark theme and light in the light one —
        # so bold white came out near-invisible against the terminal background.
        7: (base7, p["muted"], base7),
    }
    blocks = []
    for number, values in terminal.items():
        blocks.append(f"""[Color{number}]
Color={rgb(values[0])}

[Color{number}Faint]
Color={rgb(values[1])}

[Color{number}Intense]
Color={rgb(values[2])}
""")
    return f"""# Generated from artwork/moos-ui2/palette.json. Do not hand-edit.
[Background]
Color={rgb(background)}

[BackgroundFaint]
Color={rgb(p['surface'])}

[BackgroundIntense]
Color={rgb(p['canvas'])}

{''.join(blocks)}
[Foreground]
Color={rgb(p['text'])}

[ForegroundFaint]
Color={rgb(p['muted'])}

[ForegroundIntense]
Color={rgb(p['text'])}

[General]
Description={name}
Opacity=1
Blur=false
Wallpaper=
"""


def konsole_profile(variant: str) -> str:
    p = variant_roles(variant)
    light = variant == "light"
    scheme = "MoOSUI2Light" if light else "MoOSUI2Dark"
    name = "MoOS UI Light" if light else "MoOS UI"
    return f"""# Generated by artwork/generate_moos_ui2.py. Do not hand-edit.
[Appearance]
ColorScheme={scheme}
Font=JetBrains Mono,11,-1,5,50,0,0,0,0,0
LineSpacing=2
BoldIntense=true
UseFontLineChararacters=true

[General]
Name={name}
Parent=FALLBACK/
TerminalMargin=14
TerminalCenter=false
ShowTerminalSizeHint=false

[Scrolling]
ScrollBarPosition=2
HistoryMode=1
HistorySize=20000

[Cursor Options]
CursorShape=0
UseCustomCursorColor=true
CustomCursorColor={rgb(p['primary'])}

[Terminal Features]
BlinkingCursorEnabled=true
BellMode=3

[Interaction Options]
AutoCopySelectedText=true
TrimTrailingSpacesInSelectedText=true
UnderlineLinksEnabled=true
UnderlineFilesEnabled=true
"""


def lnf_defaults(variant: str) -> str:
    light = variant == "light"
    scheme = "MoOSUI2Light" if light else "MoOSUI2Dark"
    style = "MoOSUI2Light" if light else "MoOSUI2"
    package = "org.moos.ui2.light" if light else "org.moos.ui2"
    wallpaper = "MoOSUI2Tide" if light else "MoOSUI2Graphite"
    icons = "MoOSUI2Light" if light else "MoOSUI2"
    # A white pointer disappears on Tidal Light's mint canvas; each half gets
    # the cursor that reads against ITS canvas (both are rebranded Bibata).
    cursor = "MoOSDark" if light else "MoOS"
    deco = "MoOSUI2Light" if light else "MoOSUI2"
    # NO [Wallpaper] section, deliberately. LookAndFeelManager applies a theme's
    # [Wallpaper] Image= by forcing every desktop containment back onto
    # org.kde.image — which would silently replace org.moos.ui2.wallpaper (the
    # scene that carries the dashboard bento BELOW the icons) on every theme
    # apply and every sunrise/sunset switch. moos-theme / moos-apply-theme own
    # the desktop wallpaper instead, per half. (`wallpaper` stays a parameter
    # so the generator's call sites don't churn: {wallpaper} is the half's package.)
    return f"""# MoOS UI matched Global Theme defaults. Generated file.
[kdeglobals][General]
ColorScheme={scheme}

[kdeglobals][KDE]
widgetStyle=Breeze

[plasmarc][Theme]
name={style}

[ksplashrc][KSplash]
Theme={package}
Engine=KSplashQML

[kdeglobals][Icons]
Theme={icons}

[kdeglobals][Sounds]
Enable=true
Theme=moos

[kwinrc][org.kde.kdecoration2]
library=org.kde.kwin.aurorae
theme=__aurorae__svg__{deco}

[kwinrc][Plugins]
blurEnabled=true

[kwinrc][Effect-blur]
BlurStrength=15
NoiseStrength=3

[kcminputrc][Mouse]
cursorTheme={cursor}
"""


def lnf_metadata(package: str, light: bool) -> str:
    return json.dumps({
        "KPlugin": {
            "Id": package,
            "Name": "MoOS UI Light" if light else "MoOS UI",
            "Name[ar]": "MoOS UI الفاتح" if light else "MoOS UI",
            "Description": ("سمة MoOS UI التركواز الفاتحة | MoOS UI tidal light global theme"
                            if light else
                            "سمة MoOS UI الغرافيتية الداكنة | MoOS UI graphite dark global theme"),
            "Authors": [{"Name": "Moalfarras"}], "Version": "2.0.0",
            "License": "GPL-3.0-or-later",
            "Website": "https://github.com/moalfarras-sys/moos-image",
        },
        "KPackageStructure": "Plasma/LookAndFeel",
        "X-Plasma-APIVersion": "2",
    }, ensure_ascii=False, indent=4)


def lnf_readme(package: str, light: bool) -> str:
    variant = "Tidal Light" if light else "Graphite Dark"
    scheme = "MoOSUI2Light" if light else "MoOSUI2Dark"
    style = "MoOSUI2Light" if light else "MoOSUI2"
    wallpaper = "MoOSUI2Tide" if light else "MoOSUI2Graphite"
    return f"""# {package} — MoOS UI {variant}

حزمة MoOS UI المتكاملة لـ KDE Plasma 6.  تطبق لوحة الألوان والـPlasma Style
والزخرفة والخلفية وشاشة البدء المتطابقة، مع إبقاء MoOS UI1 مثبتًا للرجوع.

| Surface | Selector |
|---|---|
| Look-and-feel | `{package}` |
| Colour scheme | `{scheme}` |
| Plasma style | `{style}` |
| Wallpaper | `{wallpaper}` |

## Runtime verification

```bash
plasma-apply-lookandfeel -a {package}
/usr/libexec/ksmserver-logout-greeter --windowed --lookandfeel {package}
```

Generated by `artwork/generate_moos_ui2.py`; do not hand-edit this package.
"""


def logout_readme(package: str, light: bool) -> str:
    variant = "Tidal Light" if light else "Graphite Dark"
    return f"""# MoOS UI logout — {variant}

واجهة الخروج الرسمية للحزمة `{package}`. تحافظ على إشارات وقدرات مضيف
KDE Plasma 6 الفعلية (logout, lock, suspend, hibernate, restart, shutdown)
وتستخدم مكوّن `MoOSUI2ActionButton.qml` المحلي المطابق للوحة {variant}.

```bash
/usr/libexec/ksmserver-logout-greeter --windowed --lookandfeel {package}
```

`Logout.qml` و`MoOSUI2ActionButton.qml`: GPL-2.0-or-later. عقد المضيف مشتق
من KDE Breeze؛ التنفيذ البصري لـ MoOS، © 2026 Moalfarras.
"""


def wallpaper_metadata(package: str, light: bool) -> str:
    return json.dumps({
        "KPlugin": {
            "Id": package,
            "Name": "MoOS Tidal Mist" if light else "MoOS Quiet Horizon",
            "Name[ar]": "ضباب MoOS التركوازي" if light else "أفق MoOS الهادئ",
            "Description": ("Mineral turquoise daylight for MoOS UI"
                            if light else "A calm graphite horizon with restrained cyan and emerald light"),
            "Description[ar]": ("تركواز معدني هادئ لسمة MoOS UI الفاتحة"
                                if light else "أفق غرافيتي هادئ بإضاءة سماوية وزمردية محسوبة"),
            "Authors": [{"Name": "Moalfarras"}], "License": "CC-BY-SA-4.0",
        }
    }, ensure_ascii=False, indent=2)


def scale_crop(source: pathlib.Path, target: pathlib.Path, width: int, height: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required to export MoOS UI raster assets")
    vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={width}:{height}")
    command = [ffmpeg, "-y", "-loglevel", "error", "-i", str(source),
               "-vf", vf, "-frames:v", "1"]
    if target.suffix.lower() in {".jpg", ".jpeg"}:
        # 4:4:4 avoids turquoise edge/chroma smearing on a 4K desktop while q=2
        # is visually transparent against the lossless master. Shipping the
        # textured image as PNG was ~97 MiB for the two packages; JPEG keeps the
        # source masters lossless in artwork/ and the runtime image lean.
        command += ["-q:v", "2", "-pix_fmt", "yuvj444p"]
    else:
        command += ["-update", "1"]
    command.append(str(target))
    subprocess.run(command, check=True)


def source_from_backup(backup_root: pathlib.Path, shipped_path: pathlib.Path) -> pathlib.Path:
    source = backup_root / shipped_path.relative_to(ROOT)
    if not source.exists():
        raise SystemExit(f"missing canonical UI2 source in transaction backup: {source}")
    return source


def generate_desktop_theme(variant: str, backup_root: pathlib.Path) -> None:
    light = variant == "light"
    style = "MoOSUI2Light" if light else "MoOSUI2"
    wallpaper = "MoOSUI2Tide" if light else "MoOSUI2Graphite"
    target = SHARE / f"plasma/desktoptheme/{style}"
    source = source_from_backup(
        backup_root, SHARE / "plasma/desktoptheme/MoOSUI2"
    )
    copy_generated(source, target, variant)
    write(target / "metadata.json", desktop_metadata(style, light))
    write(target / "plasmarc", desktop_plasmarc(wallpaper, light))
    scheme = color_scheme(variant)
    write(target / "colors", scheme)
    render_panel(target / "widgets/panel-background.svg", variant)
    render_dialog(target / "dialogs/background.svg", variant)


def generate_aurorae(variant: str, backup_root: pathlib.Path) -> None:
    light = variant == "light"
    name = "MoOSUI2Light" if light else "MoOSUI2"
    target = SHARE / f"aurorae/themes/{name}"
    source = source_from_backup(
        backup_root, SHARE / "aurorae/themes/MoOSUI2"
    )
    copy_generated(source, target, variant)
    # rewrite_tree changes selectors inside files, not filesystem names.  The
    # canonical Graphite source already uses the UI2 name, so rename whichever
    # single rc file was copied to the requested sibling name.
    target_rc = target / f"{name}rc"
    source_rcs = [path for path in target.glob("*rc") if path != target_rc]
    if len(source_rcs) > 1:
        raise SystemExit(f"{name} contains multiple Aurorae rc files")
    if source_rcs:
        source_rcs[0].rename(target_rc)
    metadata = target / "metadata.desktop"
    text = metadata.read_text(encoding="utf-8")
    text = re.sub(r"^Name=.*$", f"Name={'MoOS UI Light' if light else 'MoOS UI'}", text, flags=re.M)
    text = re.sub(r"^Comment=.*$", ("Comment=Mineral turquoise glass window decoration for MoOS"
                                      if light else
                                      "Comment=Graphite glass window decoration for MoOS"), text, flags=re.M)
    text = re.sub(r"^X-KDE-PluginInfo-Name=.*$", f"X-KDE-PluginInfo-Name={name}", text, flags=re.M)
    text = re.sub(r"^X-KDE-PluginInfo-Version=.*$", "X-KDE-PluginInfo-Version=2.0", text, flags=re.M)
    metadata.write_text(text, encoding="utf-8")


def generate_lnf(variant: str, backup_root: pathlib.Path) -> None:
    light = variant == "light"
    package = "org.moos.ui2.light" if light else "org.moos.ui2"
    target = SHARE / f"plasma/look-and-feel/{package}"
    source = source_from_backup(
        backup_root, SHARE / "plasma/look-and-feel/org.moos.ui2"
    )
    copy_generated(source, target, variant)
    button = target / "contents/logout/NovaActionButton.qml"
    if button.exists():
        button.rename(target / "contents/logout/MoOSUI2ActionButton.qml")
    write(target / "metadata.json", lnf_metadata(package, light))
    write(target / "contents/defaults", lnf_defaults(variant))
    write(target / "README.md", lnf_readme(package, light))
    write(target / "contents/logout/README.md", logout_readme(package, light))


def generate_wallpaper(variant: str) -> None:
    light = variant == "light"
    package = "MoOSUI2Tide" if light else "MoOSUI2Graphite"
    source = ART / "wallpapers" / ("moos-ui2-tide-master.png" if light else
                                    "moos-ui2-quiet-horizon-master-v2.png")
    target = SHARE / f"wallpapers/{package}"
    if target.exists():
        shutil.rmtree(target)
    for width, height in ((3840, 2160), (3440, 1440), (2560, 1600)):
        filename = f"{width}x{height}.jpg"
        for folder in ("images", "images_dark"):
            scale_crop(source, target / f"contents/{folder}/{filename}", width, height)
    scale_crop(source, target / "contents/screenshot.png", 1920, 1080)
    write(target / "metadata.json", wallpaper_metadata(package, light))
    title = "MoOS Tidal Mist" if light else "MoOS Quiet Horizon"
    write(target / "README.md", f"""# {title}

Original MoOS wallpaper generated from the project-bound raster master under
`artwork/moos-ui2/wallpapers/`. Runtime crops are exported deterministically
for 16:9, 16:10 and ultrawide displays.

Copyright © 2026 Moalfarras. CC-BY-SA-4.0.
""")


def generate_weather_runtime() -> None:
    DASHBOARD_WEATHER.mkdir(parents=True, exist_ok=True)
    for kind in WEATHER_KINDS:
        source = ART / f"weather/{kind}.png"
        if not source.is_file():
            raise SystemExit(f"missing owned UI2 weather master: {source}")
        shutil.copyfile(source, DASHBOARD_WEATHER / f"{kind}.png")


def preflight() -> None:
    """Fail before touching any shipped output when an input/tool is missing."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required to export MoOS UI raster assets")
    for source in CANONICAL_SOURCES:
        if not source.exists():
            raise SystemExit(f"missing canonical UI2 source: {source}")
    for master in (
        ART / "wallpapers/moos-ui2-quiet-horizon-master-v2.png",
        ART / "wallpapers/moos-ui2-tide-master.png",
        ART / "plasma/dialog-background.svg.in",
        ART / "plasma/panel-background.svg.in",
    ):
        if not master.is_file():
            raise SystemExit(f"missing UI2 visual master: {master}")
    for kind in WEATHER_KINDS:
        master = ART / f"weather/{kind}.png"
        if not master.is_file():
            raise SystemExit(f"missing owned UI2 weather master: {master}")


def remove_output(path: pathlib.Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def generate_previews(variant: str) -> None:
    light = variant == "light"
    package = "org.moos.ui2.light" if light else "org.moos.ui2"
    source = ART / "wallpapers" / ("moos-ui2-tide-master.png" if light else
                                    "moos-ui2-quiet-horizon-master-v2.png")
    target = SHARE / f"plasma/look-and-feel/{package}/contents/previews"
    scale_crop(source, target / "preview.png", 600, 337)
    scale_crop(source, target / "lockscreen.png", 600, 337)
    scale_crop(source, target / "splash.png", 300, 169)
    scale_crop(source, target / "fullscreenpreview.jpg", 1920, 1080)


def validate_outputs() -> None:
    for output in OUTPUTS:
        if not output.exists():
            raise SystemExit(f"missing generated UI2 output: {output}")

    legacy_hex = set(SOURCE_HEX_ROLE)
    legacy_rgb = set(SOURCE_RGB_ROLE)
    for root in OUTPUTS:
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            remaining = sorted((legacy_hex | legacy_rgb) & set(re.findall(
                r"#[0-9A-Fa-f]{6}|(?<![\d.])(?:[0-9]{1,3},){2}[0-9]{1,3}(?![\d.])", text
            )))
            if remaining:
                raise SystemExit(f"legacy UI1 colour in {path}: {remaining[0]}")
            if "MoOSUI22" in text:
                raise SystemExit(f"cascaded UI2 identity replacement in {path}")

    for variant in ("dark", "light"):
        style = "MoOSUI2Light" if variant == "light" else "MoOSUI2"
        widgets = SHARE / f"plasma/desktoptheme/{style}/widgets"
        required = {"button.svg", "line.svg", "lineedit.svg", "listitem.svg",
                    "panel-background.svg", "plasmoidheading.svg", "tasks.svg", "viewitem.svg"}
        actual = {path.name for path in widgets.glob("*.svg")}
        missing = required - actual
        if missing:
            raise SystemExit(f"{style} is missing its own SVG: {sorted(missing)[0]}")

        dialog = SHARE / f"plasma/desktoptheme/{style}/dialogs/background.svg"
        dialog_text = dialog.read_text(encoding="utf-8")
        required_masks = {
            "mask-topleft", "mask-top", "mask-topright", "mask-left",
            "mask-center", "mask-right", "mask-bottomleft", "mask-bottom",
            "mask-bottomright",
        }
        dialog_ids = set(re.findall(r'\bid="([^"]+)"', dialog_text))
        missing_masks = required_masks - dialog_ids
        if missing_masks:
            raise SystemExit(
                f"{style} popup is missing its rounded blur mask: "
                f"{sorted(missing_masks)[0]}"
            )

        package = "org.moos.ui2.light" if variant == "light" else "org.moos.ui2"
        logout = SHARE / f"plasma/look-and-feel/{package}/contents/logout"
        if not (logout / "MoOSUI2ActionButton.qml").is_file():
            raise SystemExit(f"{package} is missing its logout action component")
        if "MoOSUI2ActionButton {" not in (logout / "Logout.qml").read_text(encoding="utf-8"):
            raise SystemExit(f"{package} logout screen does not instantiate its action component")


def main() -> None:
    preflight()

    # Generation is transactional. A missing encoder was once able to delete
    # every working UI2 package and fail halfway through recreating them. Move
    # the current outputs aside on the same filesystem, validate the complete
    # replacement, then discard the backup; any exception restores the exact
    # pre-run tree.
    with tempfile.TemporaryDirectory(prefix=".moos-ui2-backup-", dir=ROOT) as tmp:
        backup_root = pathlib.Path(tmp)
        backups: dict[pathlib.Path, pathlib.Path] = {}
        backup_complete = False
        try:
            # Keep the backup phase inside the same recovery boundary as
            # generation.  A permission error, interrupt, or failed later
            # rename must restore every output already moved aside before the
            # TemporaryDirectory is cleaned up.
            fail_backup_at = (int(os.environ.get("MOOS_UI2_TEST_FAIL_BACKUP_AT", "0"))
                              if TEST_ROOT else 0)
            moved = 0
            for output in OUTPUTS:
                if not output.exists():
                    continue
                backup = backup_root / output.relative_to(ROOT)
                backup.parent.mkdir(parents=True, exist_ok=True)
                # Register the intended backup before rename. If rename itself
                # fails the missing backup is ignored during recovery; if an
                # interrupt lands immediately after rename, recovery still
                # knows where the moved output went.
                backups[output] = backup
                if fail_backup_at and moved + 1 == fail_backup_at:
                    raise OSError(f"injected UI2 backup rename failure at output {moved + 1}")
                output.rename(backup)
                moved += 1
            backup_complete = True

            for variant in ("dark", "light"):
                generate_desktop_theme(variant, backup_root)
                generate_aurorae(variant, backup_root)
                generate_lnf(variant, backup_root)
                scheme_name = "MoOSUI2Light" if variant == "light" else "MoOSUI2Dark"
                write(SHARE / f"color-schemes/{scheme_name}.colors", color_scheme(variant))
                write(SHARE / f"konsole/{scheme_name}.colorscheme", konsole_scheme(variant))
                profile = "MoOSUI2Light.profile" if variant == "light" else "MoOSUI2.profile"
                write(SHARE / f"konsole/{profile}", konsole_profile(variant))
                generate_wallpaper(variant)
                generate_previews(variant)

            generate_weather_runtime()
            validate_outputs()
        except BaseException:
            # During generation, remove every partial output (including paths
            # that did not exist before the run). During an interrupted backup,
            # untouched later outputs are still the originals and must not be
            # deleted; clear only locations whose backup actually exists.
            if backup_complete:
                for output in OUTPUTS:
                    remove_output(output)
            else:
                for output, backup in backups.items():
                    if backup.exists():
                        remove_output(output)
            for output, backup in backups.items():
                if backup.exists():
                    output.parent.mkdir(parents=True, exist_ok=True)
                    backup.rename(output)
            raise
    print("generated unified MoOS UI Graphite/Tidal packages from the canonical UI2 source")


if __name__ == "__main__":
    main()
