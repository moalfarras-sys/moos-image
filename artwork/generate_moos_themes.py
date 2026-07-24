#!/usr/bin/env python3
"""Generate the MoOS theme FAMILY.

MoOS ships one design engine (the UI2 Plasma style, Aurorae decoration, logout
QML and color math). This tool recolours that *working* engine into additional
MoOS-branded looks — Nova, Amethyst, Midnight, Aurora — each a full, self-owned
package set with its own palette and wallpaper, but the same proven geometry.

  * Source of the visual engine: the committed MoOSUI2 (dark) packages under
    system_files/ — NOT the retired UI1 templates. So this runs against the tree
    as it stands today.
  * Colour math (KDE color-scheme, Konsole scheme) is reused verbatim from
    generate_moos_ui2.py by feeding it the new palettes, so contrast handling and
    group structure match the base exactly.
  * Graphite (dark) and Tidal (light) in artwork/moos-ui2/palette.json are the
    base pair and are left untouched.

Usage:
    python3 artwork/generate_moos_themes.py [--only nova,aurora]

Every output is a NEW package; nothing existing is overwritten. Re-runnable.
"""
from __future__ import annotations
import argparse, importlib.util, json, math, os, pathlib, random, shutil, sys

# Honour the same isolated-root contract as generate_moos_ui2.py. Previously
# this wrapper imported the base generator from the test tree but still wrote
# the family packages into the real checkout, silently changing committed art.
TEST_ROOT = os.environ.get("MOOS_UI2_TEST_ROOT")
ROOT = (pathlib.Path(TEST_ROOT).resolve() if TEST_ROOT
        else pathlib.Path(__file__).resolve().parent.parent)
ART = ROOT / "artwork"
SHARE = ROOT / "system_files/usr/share"

# ---- reuse the UI2 generator's colour math (import-safe: main() is guarded) ---
_spec = importlib.util.spec_from_file_location("gen_ui2", ART / "generate_moos_ui2.py")
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

# The recolour SOURCE palette = the UI2 dark roles (canvas..panel_bottom + extras)
BASE = gen.variant_roles("dark")

# ---- load the family palettes -------------------------------------------------
_PALJSON = json.loads((ART / "moos-themes/palettes.json").read_text(encoding="utf-8"))
_EXTRAS = _PALJSON["_extras"]

# The five EXTRAS roles (deep semantic tints + the ink drawn ON an accent).
EXTRA_KEYS = ("positive_deep", "negative_deep", "warning_deep", "secondary_deep", "selected_text")

# The proven Tidal LIGHT role set — high contrast, dark ink on a mineral canvas.
# Every family's light sibling is derived FROM this so it inherits the same
# contrast structure the shipping light theme already passes its gates with.
LIGHT_BASE = gen.variant_roles("light")

# Per-family light identity: the accent trio (dark enough to read on a light
# canvas) plus the pale hue the neutral surfaces are washed toward. midnight's
# light sibling is "Daylight" — a bright sky, the true-black theme's opposite.
LIGHT_ACCENTS = {
    "nova":     dict(primary="#0E63C4", secondary="#5B4BD6", luminous="#1A76D8", tint="#2E6FD0"),
    "amethyst": dict(primary="#7C3AED", secondary="#B45309", luminous="#8B3FD4", tint="#8B5CF6"),
    "aurora":   dict(primary="#0F766E", secondary="#0369A1", luminous="#0D8577", tint="#0EA5A0"),
    "midnight": dict(primary="#0284C7", secondary="#4F46E5", luminous="#0891B2", tint="#2563EB"),
    "gaming":   dict(primary="#C81D7A", secondary="#0891B2", luminous="#7C3AED", tint="#C026D3"),
    "dev":      dict(primary="#1A7F37", secondary="#0969DA", luminous="#2DA44E", tint="#1A7F37"),
    "study":    dict(primary="#B45309", secondary="#4F7A6B", luminous="#A16207", tint="#B45309"),
}


def _hex(t: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % t


def _mix_hex(a: str, b: str, t: float) -> str:
    return _hex(_lerp(_rgbtuple(a), _rgbtuple(b), t))


def _relative_luminance(hexv: str) -> float:
    channels = []
    for channel in _rgbtuple(hexv):
        value = channel / 255
        channels.append(value / 12.92 if value <= 0.04045
                        else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(a: str, b: str) -> float:
    lighter, darker = sorted((_relative_luminance(a),
                              _relative_luminance(b)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def light_roles(base_key: str) -> dict[str, str]:
    """Derive a family's LIGHT palette: the Tidal light neutrals washed toward the
    family hue, carrying the family's own accent trio. Keeps the base light dark
    ink (text/muted/outline/shadow) so contrast stays at the shipping light
    theme's level."""
    acc = LIGHT_ACCENTS[base_key]
    wash = _mix_hex(acc["tint"], "#FFFFFF", 0.72)   # a pale breath of the family hue
    roles = dict(LIGHT_BASE)
    for r in ("canvas", "surface", "card", "raised", "panel_top", "panel_mid", "panel_bottom"):
        roles[r] = _mix_hex(LIGHT_BASE[r], wash, 0.55)
    roles["primary"] = acc["primary"]
    roles["secondary"] = acc["secondary"]
    roles["luminous"] = acc["luminous"]
    for r in ("positive_deep", "negative_deep", "warning_deep", "secondary_deep"):
        roles[r] = _mix_hex(LIGHT_BASE[r], wash, 0.25)
    # Selected ink is resolved against the ACTUAL accent. Pure white made every
    # light sibling glare, and Daylight's sky-blue primary reached only 4.10:1.
    # Prefer a soft cool white; fall back to near-black when that is the only
    # WCAG-readable side of the accent.
    soft_light_ink = "#F7FBFF"
    dark_ink = "#07111E"
    roles["selected_text"] = (
        soft_light_ink
        if _contrast_ratio(soft_light_ink, roles["primary"]) >= 4.5
        else dark_ink
    )
    return roles


# key -> display/id/style/wallpaper metadata. Each family ships a DARK identity
# and a matching LIGHT sibling; moos-theme toggles between them by appending
# ".light" to the look-and-feel id.
THEMES = {
    "nova":     dict(name="MoOS UI · Nova",     style="MoOSUI2Nova",     lnf="org.moos.ui2.nova",
                     wall="MoOSUI2Nova",     mood="cosmic", light=False, base="nova",
                     desc="سديم كحلي بتوهّج سماوي‑بنفسجي | Cosmic navy with a cyan-violet aurora"),
    "amethyst": dict(name="MoOS UI · Amethyst", style="MoOSUI2Amethyst", lnf="org.moos.ui2.amethyst",
                     wall="MoOSUI2Amethyst", mood="calm", light=False, base="amethyst",
                     desc="باذنجاني دافئ بلمسة أوركيد وكهرمان | Warm aubergine with orchid and amber"),
    "midnight": dict(name="MoOS UI · Midnight", style="MoOSUI2Midnight", lnf="org.moos.ui2.midnight",
                     wall="MoOSUI2Midnight", mood="minimal", light=False, base="midnight",
                     desc="أسود حقيقي عالي التباين لشاشات OLED | True-black high-contrast for OLED"),
    "aurora":   dict(name="MoOS UI · Aurora",   style="MoOSUI2Aurora",   lnf="org.moos.ui2.aurora",
                     wall="MoOSUI2Aurora",   mood="cosmic", light=False, base="aurora",
                     desc="سليت نظيف بشفق تركوازي‑أزرق حديث | Clean slate with a modern teal-blue aurora"),
    "nova-light":     dict(name="MoOS UI · Nova Light",     style="MoOSUI2NovaLight",
                           lnf="org.moos.ui2.nova.light",     wall="MoOSUI2NovaLight",
                           mood="cosmic", light=True, base="nova",
                           desc="نهار كوني: أزرق سماوي فاتح بشفق بنفسجي | Airy cosmic day, cyan-violet silk"),
    "amethyst-light": dict(name="MoOS UI · Amethyst Light", style="MoOSUI2AmethystLight",
                           lnf="org.moos.ui2.amethyst.light", wall="MoOSUI2AmethystLight",
                           mood="calm", light=True, base="amethyst",
                           desc="غسق أرجواني فاتح بلمسة كهرمان | Light orchid dusk with an amber wash"),
    "aurora-light":   dict(name="MoOS UI · Aurora Light",   style="MoOSUI2AuroraLight",
                           lnf="org.moos.ui2.aurora.light",   wall="MoOSUI2AuroraLight",
                           mood="cosmic", light=True, base="aurora",
                           desc="نهار نعناعي‑تركوازي منعش | Fresh mineral mint-teal daylight"),
    "daylight":       dict(name="MoOS UI · Daylight",       style="MoOSUI2Daylight",
                           lnf="org.moos.ui2.midnight.light", wall="MoOSUI2Daylight",
                           mood="cosmic", light=True, base="midnight",
                           desc="نهار صافٍ عالي التباين، نقيض Midnight | Clean high-contrast day, Midnight's opposite"),
    # ── Purpose-built editions: gaming, dev, study — each MoOS, its own energy ──
    "gaming":   dict(name="MoOS UI · Arena",   style="MoOSUI2Arena",   lnf="org.moos.ui2.gaming",
                     wall="MoOSUI2Arena",   mood="cosmic", light=False, base="gaming",
                     desc="للألعاب: نيون سينث‑ويف، ماجنتا وسماوي كهربائي | Gaming: synthwave neon, magenta + electric cyan"),
    "dev":      dict(name="MoOS UI · Forge",   style="MoOSUI2Forge",   lnf="org.moos.ui2.dev",
                     wall="MoOSUI2Forge",   mood="minimal", light=False, base="dev",
                     desc="للتطوير: سليت هادئ بضوء بناء أخضر، تركيز طويل | Dev: calm slate, a green build-light, low distraction"),
    "study":    dict(name="MoOS UI · Scholar", style="MoOSUI2Scholar", lnf="org.moos.ui2.study",
                     wall="MoOSUI2Scholar", mood="calm", light=False, base="study",
                     desc="للدراسة: دفء كهرماني وسيج هادئ، مريح للعين | Study: amber warmth + calm sage, easy on the eyes"),
    "gaming-light": dict(name="MoOS UI · Arena Light",   style="MoOSUI2ArenaLight",   lnf="org.moos.ui2.gaming.light",
                         wall="MoOSUI2ArenaLight",   mood="cosmic", light=True, base="gaming",
                         desc="للألعاب نهاراً: طاقة الماجنتا على قماشة فاتحة | Arena by day: magenta energy on a light canvas"),
    "dev-light":    dict(name="MoOS UI · Forge Light",   style="MoOSUI2ForgeLight",   lnf="org.moos.ui2.dev.light",
                         wall="MoOSUI2ForgeLight",   mood="minimal", light=True, base="dev",
                         desc="للتطوير نهاراً: سليت فاتح مركّز | Forge by day: a light, focused slate"),
    "study-light":  dict(name="MoOS UI · Scholar Light", style="MoOSUI2ScholarLight", lnf="org.moos.ui2.study.light",
                         wall="MoOSUI2ScholarLight", mood="calm", light=True, base="study",
                         desc="للدراسة نهاراً: ورق دافئ مريح للقراءة | Scholar by day: warm paper, made for reading"),
}


def _roles(key: str) -> dict[str, str]:
    """Full role map for a theme member. Light members are derived from the Tidal
    light base; dark members come from palettes.json."""
    meta = THEMES.get(key)
    if meta and meta.get("light"):
        return light_roles(meta["base"])
    base = {k: v for k, v in _PALJSON[key].items() if not k.startswith("_")}
    return base | _EXTRAS[key]

SRC_STYLE = SHARE / "plasma/desktoptheme/MoOSUI2"
SRC_AUR   = SHARE / "aurorae/themes/MoOSUI2"
SRC_LNF   = SHARE / "plasma/look-and-feel/org.moos.ui2"
SRC_GTK   = SHARE / "moos/gtk/moos-ui2-dark.css"   # libadwaita palette to recolour


def hexmap(key: str) -> dict[str, str]:
    """Single-pass substitution map: every UI2-dark role hex -> this theme's role
    hex, in both cases. Applied only to SVG/QML/rc text — never to numeric colour
    files, which are regenerated from the palette instead."""
    dst = _roles(key)
    m: dict[str, str] = {}
    for role, base_hex in BASE.items():
        if not (isinstance(base_hex, str) and base_hex.startswith("#")):
            continue
        target = dst[role]
        for form in (base_hex.upper(), base_hex.lower()):
            m[form] = target
    return m


def recolor(text: str, m: dict[str, str]) -> str:
    return gen.rewrite_text(text, m)


def _rgb(hexv: str) -> str:
    return gen.rgb(hexv)


def _rgbtuple(hexv: str) -> tuple[int, int, int]:
    h = hexv.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------- colour files
def _register_palette(key: str) -> None:
    """Feed this member's resolved roles into the shared UI2 colour math, split
    into the core palette and the five EXTRAS roles it expects separately. Works
    for both dark (palettes.json) and light (derived) members."""
    roles = _roles(key)
    gen.PALETTES[key] = {k: v for k, v in roles.items() if k not in EXTRA_KEYS}
    gen.EXTRAS[key] = {k: roles[k] for k in EXTRA_KEYS}


def color_scheme_for(key: str, meta: dict) -> str:
    _register_palette(key)
    # color_scheme() names light members "MoOS UI Light"/"MoOSUI2Light" and dark
    # ones "…Dark"; rename either to this member's own style/display name.
    text = gen.color_scheme(key)
    for scheme in ("MoOSUI2Dark", "MoOSUI2Light"):
        text = text.replace(scheme, meta["style"])
    for name in ("MoOS UI Dark", "MoOS UI Light"):
        text = text.replace(name, meta["name"])
    return text


def konsole_scheme_for(key: str, meta: dict) -> str:
    _register_palette(key)
    text = gen.konsole_scheme(key, light=meta.get("light", False))
    return text.replace("MoOS UI Dark", meta["name"]).replace("MoOS UI Light", meta["name"])


def konsole_profile_for(key: str, meta: dict) -> str:
    p = _roles(key)
    return f"""[Appearance]
ColorScheme={meta['style']}
Font=JetBrains Mono,11,-1,5,50,0,0,0,0,0
LineSpacing=2
BoldIntense=true
UseFontLineChararacters=true

[General]
Name={meta['name']}
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
CustomCursorColor={_rgb(p['primary'])}

[Terminal Features]
BlinkingCursorEnabled=true
BellMode=3

[Interaction Options]
AutoCopySelectedText=true
TrimTrailingSpacesInSelectedText=true
UnderlineLinksEnabled=true
UnderlineFilesEnabled=true
"""


# ---------------------------------------------------------------- packages
def build_desktoptheme(key: str, meta: dict) -> None:
    m = hexmap(key)
    dst = SHARE / "plasma/desktoptheme" / meta["style"]
    if dst.exists():
        shutil.rmtree(dst)
    for src in sorted(SRC_STYLE.rglob("*")):
        rel = src.relative_to(SRC_STYLE)
        out = dst / rel
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        if src.suffix == ".svg":
            write(out, recolor(src.read_text(encoding="utf-8"), m))
        # colors / metadata.json / plasmarc are rewritten below, skip copying
        elif src.name not in ("colors", "metadata.json", "plasmarc"):
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)
    # Light members render their glass through the SHARED masters instead of the
    # recoloured dark copy, so all 7 light siblings pick up the tuned LIGHT
    # opacity ramp — keeping Dark and Light ONE glass source with two profiles,
    # not a light theme forced onto the dark dock's translucency.
    if meta.get("light"):
        _register_palette(key)
        gen.render_panel(dst / "widgets/panel-background.svg", key, light=True)
        gen.render_dialog(dst / "dialogs/background.svg", key, light=True)
    # fresh metadata + plasmarc + colors
    write(dst / "metadata.json", json.dumps({
        "KPlugin": {
            "Authors": [{"Name": "Moalfarras"}], "Category": "",
            "Description": meta["desc"], "Id": meta["style"],
            "License": "GPL-3.0-or-later", "Name": meta["name"], "Version": "2.0.0",
            "Website": "https://github.com/moalfarras-sys/moos-image",
        }, "X-Plasma-API": "5.0",
    }, ensure_ascii=False, indent=4))
    write(dst / "plasmarc", f"""# Generated by artwork/generate_moos_themes.py — {meta['name']}.
# A complete fixed-colour SVG suite; falls back only to Breeze for any
# upstream path this family does not draw.
[Settings]
FallbackTheme={'breeze-light' if meta.get('light') else 'breeze-dark'}

[Wallpaper]
defaultWallpaperTheme={meta['wall']}
defaultFileSuffix=.jpg
defaultWidth=1920
defaultHeight=1080

[AdaptiveTransparency]
enabled=false
""")
    write(dst / "colors", color_scheme_for(key, meta))


def build_aurorae(key: str, meta: dict) -> None:
    m = hexmap(key)
    p = _roles(key)
    dst = SHARE / "aurorae/themes" / meta["style"]
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    for src in sorted(SRC_AUR.glob("*")):
        if src.suffix == ".svg":
            write(dst / src.name, recolor(src.read_text(encoding="utf-8"), m))
    # rc: same geometry, per-theme title colours
    write(dst / f"{meta['style']}rc", f"""[General]
# Title centred, macOS-style, rather than hugged to the button cluster.
TitleAlignment=Center
TitleVerticalAlignment=Center
Animation=120
ActiveTextColor={_rgb(p['text'])},255
InactiveTextColor={_rgb(p['muted'])},255
UseTextShadow=false
HaloActive=false
HaloInactive=false

[Layout]
BorderLeft=1
BorderRight=1
BorderBottom=1
TitleEdgeTop=5
TitleEdgeBottom=5
TitleEdgeLeft=10
TitleEdgeRight=10
TitleBorderLeft=8
TitleBorderRight=8
TitleHeight=30

TitleEdgeTopMaximized=0
TitleEdgeBottomMaximized=0
TitleEdgeLeftMaximized=10
TitleEdgeRightMaximized=10

ButtonWidth=18
ButtonHeight=18
ButtonSpacing=8
ButtonMarginTop=0

PaddingLeft=18
PaddingRight=18
PaddingTop=12
PaddingBottom=24
""")
    write(dst / "metadata.desktop", f"""[Desktop Entry]
Name={meta['name']}
Comment={meta['desc']}
X-KDE-PluginInfo-Author=Moalfarras
X-KDE-PluginInfo-Name={meta['style']}
X-KDE-PluginInfo-Version=2.0
X-KDE-PluginInfo-License=GPL-3.0-or-later
X-KDE-ServiceTypes=KWin/Decoration
Type=Service
""")


def build_lnf(key: str, meta: dict) -> None:
    m = hexmap(key)
    dst = SHARE / "plasma/look-and-feel" / meta["lnf"]
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    # One session-screen implementation across every palette. QML is copied
    # byte-for-byte so splash/logout behaviour, layout and motion cannot fork.
    # Only artwork SVGs are recoloured; QML consumes Kirigami palette roles.
    for sub in ("logout", "splash"):
        s = SRC_LNF / "contents" / sub
        if not s.exists():
            continue
        for src in sorted(s.rglob("*")):
            rel = src.relative_to(SRC_LNF)
            out = dst / rel
            if src.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            elif src.suffix == ".svg":
                write(out, recolor(src.read_text(encoding="utf-8"), m))
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, out)
    # metadata.json
    write(dst / "metadata.json", json.dumps({
        "KPlugin": {
            "Id": meta["lnf"], "Name": meta["name"], "Description": meta["desc"],
            "Authors": [{"Name": "Moalfarras"}], "Version": "2.0.0",
            "License": "GPL-3.0-or-later",
            "Website": "https://github.com/moalfarras-sys/moos-image",
            "Name[ar]": meta["name"],
        },
        "KPackageStructure": "Plasma/LookAndFeel", "X-Plasma-APIVersion": "2",
    }, ensure_ascii=False, indent=4))
    # contents/defaults — the cascade the switcher also writes live. Light
    # siblings carry the light icon theme and the dark-on-light pointer, exactly
    # as the base MoOS Light theme does.
    light = meta.get("light", False)
    icons = "MoOSUI2Light" if light else "MoOSUI2"
    cursor = "MoOSDark" if light else "MoOS"
    write(dst / "contents/defaults", f"""# {meta['name']} matched Global Theme defaults. Generated file.
[kdeglobals][General]
ColorScheme={meta['style']}

[plasmarc][Theme]
name={meta['style']}

[ksplashrc][KSplash]
Theme={meta['lnf']}
Engine=KSplashQML

[kdeglobals][Icons]
Theme={icons}

[kdeglobals][Sounds]
Enable=true
Theme=moos

[kwinrc][org.kde.kdecoration2]
library=org.kde.kwin.aurorae
theme=__aurorae__svg__{meta['style']}

[kwinrc][Plugins]
blurEnabled=true

[kwinrc][Effect-blur]
BlurStrength=8
NoiseStrength=2

[kcminputrc][Mouse]
cursorTheme={cursor}
""")
    write(dst / "README.md", f"# {meta['name']}\n\nGenerated by artwork/generate_moos_themes.py — a MoOS UI-family look.\n")


# ---------------------------------------------------------------- wallpaper art
def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def make_wallpaper(key: str, mood: str = "cosmic"):
    """The theme's own designed backdrop, v2 — LIT SILK, not line-art.

    v1 drew single crest lines filled flat to the bottom edge; honest, but
    next to the painterly Graphite master it read as a diagram. The rewrite
    keeps v1's deterministic, pure-PIL contract and changes how the light
    works, which is what actually separates the master from a diagram:

      sky        vertical colour ramp + wide accent glows + one soft beam
      aurora     (cosmic) a veil of light following a sweep curve, drawn as
                 a thick gradient-coloured stroke and blurred until it is
                 atmosphere, not a shape
      ribbons    silk bands between two curves. Each band is a dark glass
                 gradient along its length, LIT FROM ITS CREST — a falloff
                 of the theme's light colour breathing down into the glass —
                 with silk-fold filaments inside, an inner shadow along the
                 underside, and a neon crest edge screen-blended so it
                 genuinely emits
      focus      one luminous core where the composition's light gathers
      finish     stars/bokeh per mood, vignette, fine grain

    Pure PIL (polygons, gradients, blurs, channel ops) — no numpy, no AI, no
    network. Byte-deterministic per key. Returns None if PIL is missing.
    Canva art can still replace these masters later without touching
    packaging (build_wallpaper only needs a PIL image)."""
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
    except Exception:
        return None
    p = _roles(key)
    W, H = 3840, 2160
    rng = random.Random(sum(ord(c) for c in key) * 7 + 13)

    canvas = _rgbtuple(p["canvas"])
    surface = _rgbtuple(p["surface"])
    card = _rgbtuple(p["card"])
    raised = _rgbtuple(p["raised"])
    bottom = _rgbtuple(p["shadow"])
    primary = _rgbtuple(p["primary"])
    secondary = _rgbtuple(p["secondary"])
    luminous = _rgbtuple(p["luminous"])

    # ── 1. the sky ──────────────────────────────────────────────────────────
    col = Image.new("RGB", (1, H))
    px = col.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = _lerp(surface, canvas, t / 0.55) if t < 0.55 else _lerp(canvas, bottom, (t - 0.55) / 0.45)
    img = col.resize((W, H))

    def screen_glow(cx, cy, radius, color, strength):
        nonlocal img
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(layer).ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=tuple(int(c * strength) for c in color))
        img = ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(radius // 2)))

    def screen_stroke(pts, color, strength, width, blur):
        """A luminous stroke, screen-blended: real emitted light on dark glass."""
        nonlocal img
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(layer).line(pts, fill=tuple(int(c * strength) for c in color),
                                   width=width, joint="curve")
        img = ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(blur)))

    def gradient_stroke(pts, color_a, color_b, strength, width, blur):
        """screen_stroke whose colour travels a→b along the stroke's length."""
        nonlocal img
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        d = ImageDraw.Draw(layer)
        n = len(pts)
        for i in range(n - 1):
            c = _lerp(color_a, color_b, i / (n - 2 if n > 2 else 1))
            d.line([pts[i], pts[i + 1]], fill=tuple(int(v * strength) for v in c),
                   width=width, joint="curve")
        img = ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(blur)))

    # ── 2. curve sampling (every 12 px, overscanned past both edges) ────────
    ph = rng.uniform(0, math.pi * 2)

    def curve(y0, amp, tilt, f1, f2, phase, drift=0.0):
        pts = []
        for x in range(-80, W + 81, 12):
            u = x / W
            yy = (y0
                  + tilt * (u - 0.5) * H
                  + amp * math.sin(u * math.pi * 2 * f1 + phase)
                  + amp * 0.42 * math.sin(u * math.pi * 2 * f2 + phase * 2.17 + drift))
            pts.append((x, yy))
        return pts

    def aurora_veil(top_y, colors, strength=0.5, passes=3):
        """Light as weather: wide gradient strokes along drifting curves,
        blurred until nothing has an outline any more."""
        for i in range(passes):
            c = curve(top_y + i * H * 0.055, H * (0.045 + 0.02 * i), 0.10 - 0.05 * i,
                      0.7 + 0.25 * i, 2.0 + 0.4 * i, ph + i * 1.9)
            a, b = colors[i % len(colors)], colors[(i + 1) % len(colors)]
            gradient_stroke(c, a, b, strength * (1.0 - i * 0.22),
                            width=int(H * (0.10 + 0.03 * i)), blur=110 + 30 * i)

    def ribbon(top, fill_a, fill_b, light_color, *, thick0, thick1,
               light=0.55, edge=0.85, alpha=225, folds=3, depth_blur=0, sag=0.35):
        """One band of silk glass, lit from its crest.

        fill_a→fill_b is the dark glass gradient along the band's LENGTH;
        light_color breathes down from the crest into the glass (the lit-silk
        falloff), an inner shadow darkens the underside, faint filaments flow
        inside, and the crest itself emits via a screen-blended neon edge."""
        nonlocal img
        n = len(top)
        bot = []
        for i, (x, y) in enumerate(top):
            t = i / (n - 1)
            th = thick0 + (thick1 - thick0) * t
            bot.append((x, y + th + math.sin(t * math.pi) * th * sag))

        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(top + bot[::-1], fill=alpha)

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gradrow = Image.new("RGB", (W, 1))
        gp = gradrow.load()
        for x in range(W):
            gp[x, 0] = _lerp(fill_a, fill_b, x / (W - 1))
        grad = gradrow.resize((W, H)).convert("RGBA")
        grad.putalpha(mask)
        layer = Image.alpha_composite(layer, grad)

        # crest light: a wide band of the light colour hugging the top curve,
        # faded by blur, clipped to the glass — silk catching the sky
        if light > 0:
            lit = Image.new("L", (W, H), 0)
            ImageDraw.Draw(lit).line(top, fill=255, width=int(H * 0.11), joint="curve")
            lit = lit.filter(ImageFilter.GaussianBlur(int(H * 0.045)))
            lit = ImageChops.multiply(lit, mask)
            silk = Image.new("RGBA", (W, H), tuple(_lerp(light_color, (255, 255, 255), 0.18)) + (0,))
            silk.putalpha(lit.point(lambda v: int(v * light)))
            layer = Image.alpha_composite(layer, silk)

        # inner shadow along the underside, so stacked bands separate
        shl = Image.new("L", (W, H), 0)
        ImageDraw.Draw(shl).line(bot, fill=190, width=int(H * 0.05), joint="curve")
        shl = shl.filter(ImageFilter.GaussianBlur(int(H * 0.024)))
        shl = ImageChops.multiply(shl, mask)
        dark = Image.new("RGBA", (W, H), tuple(int(c * 0.4) for c in bottom) + (0,))
        dark.putalpha(shl.point(lambda v: int(v * 0.65)))
        layer = Image.alpha_composite(layer, dark)

        # silk folds: faint filaments flowing inside the glass
        fd = ImageDraw.Draw(layer, "RGBA")
        for k in range(folds):
            f = (k + 1) / (folds + 1)
            fold = []
            for i in range(n):
                tx, ty = top[i]
                by = bot[i][1]
                wobble = math.sin(i / n * math.pi * 2 * (1.3 + k * 0.7) + ph + k * 1.7)
                fold.append((tx, ty + (by - ty) * (f + wobble * 0.06)))
            fd.line(fold, fill=tuple(light_color) + (max(14, 40 - k * 8),), width=4, joint="curve")

        if depth_blur:
            layer = layer.filter(ImageFilter.GaussianBlur(depth_blur))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")

        # the crest EMITS: tight neon line + wide halo, screen-blended after
        # compositing so the light adds instead of covering
        if edge > 0:
            eb = 2 if not depth_blur else depth_blur + 2
            screen_stroke(top, light_color, edge, width=6, blur=eb)
            screen_stroke(top, light_color, edge * 0.40, width=54, blur=64)

    def bokeh(count, colors, y_lo, y_hi):
        nonlocal img
        for blur, rmin, rmax, amul in ((70, 90, 150, 0.15), (28, 40, 90, 0.21), (9, 14, 40, 0.28)):
            layer = Image.new("RGB", (W, H), (0, 0, 0))
            d = ImageDraw.Draw(layer)
            for _ in range(count // 3):
                x = rng.randint(0, W)
                y = rng.randint(int(H * y_lo), int(H * y_hi))
                r = rng.randint(rmin, rmax)
                c = rng.choice(colors)
                s = amul * rng.uniform(0.5, 1.0)
                d.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * s) for v in c))
            img = ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(blur)))

    def starfield(n, y_frac, sparkle=0.04):
        sd = ImageDraw.Draw(img, "RGBA")
        for _ in range(n):
            x, y = rng.randint(0, W), rng.randint(0, int(H * y_frac))
            r = rng.choice([1, 1, 1, 2, 2, 3])
            a = rng.randint(40, 150)
            sd.ellipse([x - r, y - r, x + r, y + r], fill=(235, 242, 255, a))
            if rng.random() < sparkle:
                fl = r * 7
                sd.line([(x - fl, y), (x + fl, y)], fill=(235, 242, 255, 46), width=2)
                sd.line([(x, y - fl), (x, y + fl)], fill=(235, 242, 255, 46), width=2)

    # tinted glass tones: the fills carry the accent's hue, not raw near-black
    def glass(tone, accent, k):
        return _lerp(tone, accent, k)

    # ── 3. mood-tuned composition ────────────────────────────────────────────
    if mood == "minimal":
        # midnight: the void, one razor arc of light low in the frame, two
        # panes of barely-tinted glass — exquisite, not empty
        screen_glow(int(W * 0.5), int(H * 1.12), int(W * 0.62), primary, 0.12)
        screen_glow(int(W * 0.84), int(H * 0.04), int(W * 0.26), secondary, 0.05)
        arc = curve(H * 0.585, H * 0.075, -0.16, 0.55, 1.6, ph + 0.4)
        ribbon(arc, glass(card, primary, 0.06), glass(surface, primary, 0.04), luminous,
               thick0=H * 0.55, thick1=H * 0.62, light=0.20, edge=1.25,
               alpha=246, folds=2, sag=0.15)
        # the razor itself: one unblurred hairline of light along the arc
        screen_stroke(arc, luminous, 0.9, width=3, blur=1)
        ribbon(curve(H * 0.815, H * 0.045, 0.07, 1.05, 2.7, ph + 2.1),
               glass(surface, secondary, 0.05), bottom, primary,
               thick0=H * 0.4, thick1=H * 0.5, light=0.12, edge=0.5,
               alpha=250, folds=2, sag=0.15)
        starfield(170, 0.52, sparkle=0.03)
    elif mood == "calm":
        # amethyst: dusk silk — orchid light from the upper left, amber
        # counter-glow, bokeh motes drifting between the layers
        screen_glow(int(W * 0.24), int(H * 0.16), int(W * 0.38), primary, 0.34)
        screen_glow(int(W * 0.90), int(H * 0.90), int(W * 0.34), secondary, 0.26)
        aurora_veil(H * 0.16, [primary, secondary], strength=0.22, passes=2)
        ribbon(curve(H * 0.42, H * 0.07, 0.18, 0.7, 1.9, ph),
               glass(raised, primary, 0.14), glass(card, secondary, 0.10), luminous,
               thick0=H * 0.24, thick1=H * 0.36, light=0.42, edge=0.35,
               alpha=170, folds=2, depth_blur=8)
        bokeh(27, [luminous, primary, secondary], 0.08, 0.72)
        ribbon(curve(H * 0.57, H * 0.065, 0.12, 0.9, 2.4, ph + 1.3),
               glass(card, primary, 0.16), glass(card, secondary, 0.12), primary,
               thick0=H * 0.26, thick1=H * 0.40, light=0.55, edge=0.9, folds=4)
        ribbon(curve(H * 0.75, H * 0.055, 0.02, 1.1, 2.8, ph + 2.6),
               glass(surface, secondary, 0.14), glass(surface, primary, 0.08), secondary,
               thick0=H * 0.34, thick1=H * 0.46, light=0.42, edge=0.7, folds=3)
        ribbon(curve(H * 0.91, H * 0.04, -0.07, 1.3, 3.2, ph + 4.1),
               glass(card, primary, 0.10), bottom, luminous,
               thick0=H * 0.28, thick1=H * 0.32, light=0.34, edge=0.75, folds=2)
        bokeh(12, [luminous, secondary], 0.30, 0.92)
        screen_glow(int(W * 0.30), int(H * 0.55), int(W * 0.17), luminous, 0.20)
    else:  # cosmic — nova, aurora
        # deep-space dusk: an aurora veil breathing across the upper sky,
        # lit silk stacked toward the viewer, one luminous core, stars
        screen_glow(int(W * 0.20), int(H * 0.14), int(W * 0.36), primary, 0.34)
        screen_glow(int(W * 0.88), int(H * 0.76), int(W * 0.32), secondary, 0.26)
        aurora_veil(H * 0.14, [primary, secondary, luminous], strength=0.46, passes=3)
        ribbon(curve(H * 0.45, H * 0.075, 0.20, 0.7, 1.9, ph),
               glass(raised, primary, 0.14), glass(card, secondary, 0.12), luminous,
               thick0=H * 0.22, thick1=H * 0.34, light=0.42, edge=0.32,
               alpha=165, folds=2, depth_blur=9)
        ribbon(curve(H * 0.585, H * 0.07, 0.14, 0.9, 2.4, ph + 1.2),
               glass(card, primary, 0.16), glass(card, secondary, 0.12), primary,
               thick0=H * 0.26, thick1=H * 0.38, light=0.55, edge=0.95, folds=4)
        ribbon(curve(H * 0.74, H * 0.06, 0.05, 1.1, 2.8, ph + 2.4),
               glass(surface, secondary, 0.14), glass(surface, primary, 0.08), secondary,
               thick0=H * 0.32, thick1=H * 0.44, light=0.45, edge=0.7, folds=3)
        ribbon(curve(H * 0.895, H * 0.045, -0.09, 1.3, 3.3, ph + 4.0),
               glass(card, primary, 0.10), bottom, luminous,
               thick0=H * 0.26, thick1=H * 0.30, light=0.35, edge=0.8, folds=2)
        screen_glow(int(W * 0.34), int(H * 0.56), int(W * 0.16), luminous, 0.22)
        starfield(240, 0.48)

    # ── 4. finish: vignette toward the shadow colour, then fine grain ───────
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.28, -H * 0.28, W * 1.28, H * 1.28], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(420))
    img = Image.composite(img, Image.new("RGB", (W, H), bottom), vig)

    noise = Image.effect_noise((W, H), 14).convert("L").point(lambda v: (v - 128) // 6 + 128)
    img = ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise)))
    return img


def make_wallpaper_light(base_key: str):
    """A LIGHT-canvas silk backdrop for a family's light sibling. The dark master
    is deep glass lit from within; the light master is the opposite discipline —
    an airy near-white sky with the family's accent silk washed across it, lit by
    soft accent glows, no starfield. Alpha/screen-composited so the bands read as
    tinted silk on daylight, not emitted light on a void. Reviewed at render
    before adoption; deterministic pure-PIL. Returns None if PIL is missing."""
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageFilter
    except Exception:
        return None
    dp = _roles(base_key)                      # the family's vivid dark accents
    tint = LIGHT_ACCENTS[base_key]["tint"]
    pri_hex, sec_hex, lum_hex = dp["primary"], dp["secondary"], dp["luminous"]
    primary, secondary, luminous = _rgbtuple(pri_hex), _rgbtuple(sec_hex), _rgbtuple(lum_hex)
    W, H = 3840, 2160
    rng = random.Random(sum(ord(c) for c in base_key) * 7 + 101)

    top    = _rgbtuple(_mix_hex("#FFFFFF", tint, 0.05))
    canvas = _rgbtuple(_mix_hex("#EEF3FA", tint, 0.10))
    low    = _rgbtuple(_mix_hex("#DDE7F2", tint, 0.16))
    edge   = _rgbtuple(_mix_hex("#CBD8E6", tint, 0.14))

    col = Image.new("RGB", (1, H)); px = col.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = _lerp(top, canvas, t / 0.5) if t < 0.5 else _lerp(canvas, low, (t - 0.5) / 0.5)
    img = col.resize((W, H))

    def soft_glow(cx, cy, r, color, strength):
        nonlocal img
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r],
            fill=tuple(int(c * strength) for c in color))
        img = ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(r // 2)))

    ph = rng.uniform(0, math.pi * 2)
    def curve(y0, amp, tilt, f1, f2, phase):
        return [(x, y0 + tilt * (x / W - 0.5) * H
                    + amp * math.sin(x / W * math.pi * 2 * f1 + phase)
                    + amp * 0.42 * math.sin(x / W * math.pi * 2 * f2 + phase * 2.17))
                for x in range(-80, W + 81, 12)]

    def ribbon(top_pts, glass_a, glass_b, crest, *, thick0, thick1, sag=0.3,
               crest_light=0.5, alpha=210):
        nonlocal img
        n = len(top_pts); bot = []
        for i, (x, y) in enumerate(top_pts):
            t = i / (n - 1); th = thick0 + (thick1 - thick0) * t
            bot.append((x, y + th + math.sin(t * math.pi) * th * sag))
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(top_pts + bot[::-1], fill=alpha)
        row = Image.new("RGB", (W, 1)); rp = row.load()
        for x in range(W):
            rp[x, 0] = _lerp(glass_a, glass_b, x / (W - 1))
        grad = row.resize((W, H)).convert("RGBA"); grad.putalpha(mask)
        img = Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")
        lit = Image.new("L", (W, H), 0)
        ImageDraw.Draw(lit).line(top_pts, fill=255, width=int(H * 0.10), joint="curve")
        lit = ImageChops.multiply(lit.filter(ImageFilter.GaussianBlur(int(H * 0.05))), mask)
        sheen = Image.new("RGB", (W, H), tuple(crest))
        img = ImageChops.screen(img, Image.composite(sheen, Image.new("RGB", (W, H), (0, 0, 0)),
                                                      lit.point(lambda v: int(v * crest_light))))
        shl = Image.new("L", (W, H), 0)
        ImageDraw.Draw(shl).line(bot, fill=120, width=int(H * 0.045), joint="curve")
        shl = ImageChops.multiply(shl.filter(ImageFilter.GaussianBlur(int(H * 0.02))), mask)
        img = Image.composite(Image.new("RGB", (W, H), edge), img, shl.point(lambda v: int(v * 0.5)))
        hair = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(hair).line(top_pts, fill=tuple(int(c * 0.9) for c in crest), width=4, joint="curve")
        img = ImageChops.screen(img, hair.filter(ImageFilter.GaussianBlur(3)))

    soft_glow(int(W * 0.22), int(H * 0.16), int(W * 0.34), primary, 0.22)
    soft_glow(int(W * 0.86), int(H * 0.82), int(W * 0.30), secondary, 0.17)
    ribbon(curve(H * 0.44, H * 0.07, 0.18, 0.7, 1.9, ph),
           _rgbtuple(_mix_hex(pri_hex, "#FFFFFF", 0.68)), _rgbtuple(_mix_hex(sec_hex, "#FFFFFF", 0.72)),
           luminous, thick0=H * 0.22, thick1=H * 0.34, crest_light=0.40, alpha=178)
    ribbon(curve(H * 0.60, H * 0.065, 0.12, 0.9, 2.4, ph + 1.2),
           _rgbtuple(_mix_hex(pri_hex, "#FFFFFF", 0.58)), _rgbtuple(_mix_hex(sec_hex, "#FFFFFF", 0.62)),
           primary, thick0=H * 0.26, thick1=H * 0.40, crest_light=0.52, alpha=205)
    ribbon(curve(H * 0.78, H * 0.055, 0.04, 1.1, 2.8, ph + 2.4),
           _rgbtuple(_mix_hex(sec_hex, "#FFFFFF", 0.56)), _rgbtuple(_mix_hex(pri_hex, "#FFFFFF", 0.60)),
           secondary, thick0=H * 0.30, thick1=H * 0.44, crest_light=0.50, alpha=222)
    soft_glow(int(W * 0.34), int(H * 0.55), int(W * 0.15), luminous, 0.20)

    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.28, -H * 0.28, W * 1.28, H * 1.28], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(int(H * 0.30)))
    img = Image.composite(img, Image.new("RGB", (W, H), edge), vig)
    noise = Image.effect_noise((W, H), 10).convert("L").point(lambda v: (v - 128) // 7 + 128)
    img = ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise)))
    return img


def build_gtk(key: str, meta: dict) -> None:
    """Per-theme libadwaita palette — the UI2 dark GTK-4 CSS recoloured to this
    theme, so Flatpak/GTK-4 apps carry the theme's accent, not UI2's teal."""
    if not SRC_GTK.exists():
        return
    m = hexmap(key)
    css = recolor(SRC_GTK.read_text(encoding="utf-8"), m)
    css = css.replace("MoOS UI (Graphite Dark)", f"{meta['name']}")
    write(SHARE / "moos/gtk" / f"moos-ui2-{key}.css", css)


def build_wallpaper(key: str, meta: dict) -> bool:
    img = (make_wallpaper_light(meta["base"]) if meta.get("light")
           else make_wallpaper(key, meta.get("mood", "cosmic")))
    if img is None:
        return False
    pkg = SHARE / "wallpapers" / meta["wall"]
    for sub in ("contents/images", "contents/images_dark"):
        (pkg / sub).mkdir(parents=True, exist_ok=True)
    for w, h in ((3840, 2160), (3440, 1440), (2560, 1600)):
        frame = img.resize((w, h))
        for sub in ("images", "images_dark"):
            frame.convert("RGB").save(pkg / "contents" / sub / f"{w}x{h}.jpg", quality=92)
    img.resize((1920, 1080)).convert("RGB").save(pkg / "contents/screenshot.png")
    write(pkg / "metadata.json", json.dumps({
        "KPlugin": {"Id": meta["wall"], "Name": meta["name"],
                    "Authors": [{"Name": "Moalfarras"}], "License": "GPL-3.0-or-later"},
    }, ensure_ascii=False, indent=4))
    # picker previews live in the lnf package
    lnf = SHARE / "plasma/look-and-feel" / meta["lnf"] / "contents/previews"
    lnf.mkdir(parents=True, exist_ok=True)
    img.resize((600, 337)).convert("RGB").save(lnf / "preview.png")
    img.resize((600, 337)).convert("RGB").save(lnf / "lockscreen.png")
    img.resize((300, 169)).convert("RGB").save(lnf / "splash.png")
    img.resize((1920, 1080)).convert("RGB").save(lnf / "fullscreenpreview.jpg", quality=90)
    return True


# ---------------------------------------------------------------- driver
def build_theme(key: str) -> None:
    meta = THEMES[key]
    build_desktoptheme(key, meta)
    build_aurorae(key, meta)
    build_lnf(key, meta)
    write(SHARE / "color-schemes" / f"{meta['style']}.colors", color_scheme_for(key, meta))
    write(SHARE / "konsole" / f"{meta['style']}.colorscheme", konsole_scheme_for(key, meta))
    write(SHARE / "konsole" / f"{meta['style']}.profile", konsole_profile_for(key, meta))
    build_gtk(key, meta)
    wp = build_wallpaper(key, meta)
    print(f"  [ok] {meta['name']:<16} style={meta['style']} lnf={meta['lnf']} "
          f"wallpaper={'yes' if wp else 'SKIPPED (no PIL)'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated subset, e.g. nova,aurora")
    args = ap.parse_args()
    keys = list(THEMES)
    if args.only:
        keys = [k.strip() for k in args.only.split(",") if k.strip() in THEMES]
    print(f"Generating MoOS theme family: {', '.join(keys)}")
    for k in keys:
        build_theme(k)
    print("done.")


if __name__ == "__main__":
    main()
