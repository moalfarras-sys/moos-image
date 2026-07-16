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
import argparse, importlib.util, json, math, pathlib, random, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
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

def _roles(key: str) -> dict[str, str]:
    """Full role map for a family palette (skips the _identity annotation)."""
    base = {k: v for k, v in _PALJSON[key].items() if not k.startswith("_")}
    return base | _EXTRAS[key]

# key -> display/id/style/wallpaper metadata for each family member
THEMES = {
    "nova":     dict(name="MoOS Nova",     style="MoOSUI2Nova",     lnf="org.moos.ui2.nova",
                     wall="MoOSUI2Nova",     mood="cosmic",
                     desc="سديم كحلي بتوهّج سماوي‑بنفسجي | Cosmic navy with a cyan-violet aurora"),
    "amethyst": dict(name="MoOS Amethyst", style="MoOSUI2Amethyst", lnf="org.moos.ui2.amethyst",
                     wall="MoOSUI2Amethyst", mood="calm",
                     desc="باذنجاني دافئ بلمسة أوركيد وكهرمان | Warm aubergine with orchid and amber"),
    "midnight": dict(name="MoOS Midnight", style="MoOSUI2Midnight", lnf="org.moos.ui2.midnight",
                     wall="MoOSUI2Midnight", mood="minimal",
                     desc="أسود حقيقي عالي التباين لشاشات OLED | True-black high-contrast for OLED"),
    "aurora":   dict(name="MoOS Aurora",   style="MoOSUI2Aurora",   lnf="org.moos.ui2.aurora",
                     wall="MoOSUI2Aurora",   mood="cosmic",
                     desc="سليت نظيف بشفق تركوازي‑أزرق حديث | Clean slate with a modern teal-blue aurora"),
}

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
def color_scheme_for(key: str, meta: dict) -> str:
    gen.PALETTES[key] = {k: v for k, v in _PALJSON[key].items() if not k.startswith("_")}
    gen.EXTRAS[key] = _EXTRAS[key]
    text = gen.color_scheme(key)
    return (text.replace("MoOSUI2Dark", meta["style"])
                .replace("MoOS UI2 Dark", meta["name"]))


def konsole_scheme_for(key: str, meta: dict) -> str:
    gen.PALETTES[key] = {k: v for k, v in _PALJSON[key].items() if not k.startswith("_")}
    gen.EXTRAS[key] = _EXTRAS[key]
    return gen.konsole_scheme(key).replace("MoOS UI2 Dark", meta["name"])


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
# A complete fixed-colour SVG suite; falls back only to Breeze Dark for any
# upstream path this family does not draw.
[Settings]
FallbackTheme=breeze-dark

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
    # copy contents/{logout,splash} with SVG/QML recolour
    for sub in ("logout", "splash"):
        s = SRC_LNF / "contents" / sub
        if not s.exists():
            continue
        for src in sorted(s.rglob("*")):
            rel = src.relative_to(SRC_LNF)
            out = dst / rel
            if src.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            elif src.suffix in (".qml", ".svg"):
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
    # contents/defaults — the cascade the switcher also writes live
    write(dst / "contents/defaults", f"""# {meta['name']} matched Global Theme defaults. Generated file.
[kdeglobals][General]
ColorScheme={meta['style']}

[plasmarc][Theme]
name={meta['style']}

[ksplashrc][KSplash]
Theme={meta['lnf']}
Engine=KSplashQML

[kdeglobals][Icons]
Theme=MoOSUI2

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
cursorTheme=MoOS
""")
    write(dst / "README.md", f"# {meta['name']}\n\nGenerated by artwork/generate_moos_themes.py — a MoOS UI2-family look.\n")


# ---------------------------------------------------------------- wallpaper art
def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def make_wallpaper(key: str, mood: str = "cosmic"):
    """The theme's own designed backdrop — GLASS WAVES, not a blurred gradient.

    The first family wallpapers were heavy-blurred aurora bands over a vertical
    gradient, and next to the Graphite master (real layered glass waves) they
    read as unfinished. This renders the same design language the master
    carries, per palette: a deep gradient sky, then stacked translucent wave
    bands rising through the frame, each with a gradient fill, a soft depth
    shadow beneath its crest, a crisp luminous edge and a wide glow around it —
    dark mineral glass catching the theme's accent light. Composition varies by
    mood (cosmic/calm/minimal) and every parameter derives from a per-key seed,
    so the art is distinct per theme and byte-deterministic per run.

    Pure PIL (polygons, gradients, blurs, channel ops) — no numpy, no AI, no
    network. Returns a PIL image or None if PIL is missing."""
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

    # 1) the sky: surface(top) -> canvas(mid) -> shadow(bottom)
    col = Image.new("RGB", (1, H)); px = col.load()
    for y in range(H):
        t = y / (H - 1)
        px[0, y] = _lerp(surface, canvas, t / 0.55) if t < 0.55 else _lerp(canvas, bottom, (t - 0.55) / 0.45)
    img = col.resize((W, H))

    def screen_glow(cx, cy, radius, color, strength):
        layer = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(layer).ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=tuple(int(c * strength) for c in color))
        return ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(radius // 2)))

    def wave_curve(y0, amp, tilt, f1, f2, ph):
        """Sample one smooth crest line across the frame (every 12 px)."""
        pts = []
        for x in range(-60, W + 61, 12):
            u = x / W
            yy = (y0
                  + tilt * (u - 0.5) * H
                  + amp * math.sin(u * math.pi * 2 * f1 + ph)
                  + amp * 0.38 * math.sin(u * math.pi * 2 * f2 + ph * 2.3))
            pts.append((x, yy))
        return pts

    def glass_wave(crest, fill_top, fill_bottom, edge_color, edge_strength,
                   fill_alpha=255, shade_strength=0.5):
        """One band of dark glass: gradient fill below the crest, a depth shadow
        under the crest line, a crisp luminous edge and a wide soft glow."""
        nonlocal img
        # -- fill: vertical gradient masked to the area below the crest
        lo = int(min(y for _, y in crest)); hi = H
        grad = Image.new("RGB", (1, H)); gp = grad.load()
        for y in range(H):
            t = 0.0 if hi == lo else max(0.0, min(1.0, (y - lo) / (hi - lo)))
            gp[0, y] = _lerp(fill_top, fill_bottom, t)
        grad = grad.resize((W, H))
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(crest + [(W + 60, H + 60), (-60, H + 60)], fill=fill_alpha)
        img = Image.composite(grad, img, mask)
        # -- depth shadow: darken just below the crest so each layer separates
        if shade_strength > 0:
            sh = Image.new("L", (W, H), 0)
            ImageDraw.Draw(sh).line(crest, fill=int(150 * shade_strength), width=int(H * 0.055))
            sh = sh.filter(ImageFilter.GaussianBlur(int(H * 0.03)))
            # only inside the band
            sh = ImageChops.multiply(sh, mask)
            dark = Image.new("RGB", (W, H), tuple(int(c * 0.55) for c in fill_bottom))
            img = Image.composite(dark, img, sh)
        # -- the luminous edge: a tight bright line plus a wide soft glow
        if edge_strength > 0:
            line = Image.new("RGB", (W, H), (0, 0, 0))
            ImageDraw.Draw(line).line(crest, fill=tuple(int(c * edge_strength) for c in edge_color), width=6)
            img = ImageChops.screen(img, line.filter(ImageFilter.GaussianBlur(3)))
            glow = Image.new("RGB", (W, H), (0, 0, 0))
            ImageDraw.Draw(glow).line(crest, fill=tuple(int(c * edge_strength * 0.55) for c in edge_color), width=44)
            img = ImageChops.screen(img, glow.filter(ImageFilter.GaussianBlur(60)))

    # 2) mood-tuned composition
    ph = rng.uniform(0, math.pi * 2)
    if mood == "minimal":
        # midnight: near-black sky, two barely-there glass layers, one razor of light
        img = screen_glow(int(W * 0.5), int(H * 1.05), int(W * 0.55), primary, 0.14)
        glass_wave(wave_curve(H * 0.62, H * 0.05, 0.10, 0.9, 2.3, ph),
                   card, bottom, secondary, 0.22, shade_strength=0.35)
        glass_wave(wave_curve(H * 0.80, H * 0.04, -0.06, 1.1, 2.9, ph + 2.0),
                   surface, bottom, luminous, 0.55, shade_strength=0.45)
        stars = 150
    elif mood == "calm":
        # amethyst: soft high glow, three waves, the warm secondary low in the frame
        img = screen_glow(int(W * 0.26), int(H * 0.22), int(W * 0.34), primary, 0.30)
        img = screen_glow(int(W * 0.85), int(H * 0.86), int(W * 0.30), secondary, 0.22)
        glass_wave(wave_curve(H * 0.46, H * 0.07, 0.16, 0.8, 2.1, ph),
                   raised, canvas, luminous, 0.30, shade_strength=0.4)
        glass_wave(wave_curve(H * 0.63, H * 0.06, 0.10, 1.0, 2.7, ph + 1.4),
                   card, bottom, primary, 0.45, shade_strength=0.5)
        glass_wave(wave_curve(H * 0.82, H * 0.05, -0.08, 1.2, 3.1, ph + 3.1),
                   surface, bottom, secondary, 0.35, shade_strength=0.5)
        stars = 0
    else:  # cosmic (nova, aurora)
        img = screen_glow(int(W * 0.22), int(H * 0.20), int(W * 0.34), primary, 0.34)
        img = screen_glow(int(W * 0.86), int(H * 0.80), int(W * 0.30), secondary, 0.26)
        glass_wave(wave_curve(H * 0.40, H * 0.08, 0.20, 0.7, 1.9, ph),
                   raised, canvas, luminous, 0.26, shade_strength=0.35)
        glass_wave(wave_curve(H * 0.56, H * 0.07, 0.14, 0.9, 2.4, ph + 1.2),
                   card, canvas, primary, 0.5, shade_strength=0.45)
        glass_wave(wave_curve(H * 0.72, H * 0.06, 0.06, 1.1, 2.8, ph + 2.4),
                   surface, bottom, secondary, 0.4, shade_strength=0.5)
        glass_wave(wave_curve(H * 0.88, H * 0.05, -0.10, 1.3, 3.3, ph + 4.0),
                   card, bottom, luminous, 0.5, shade_strength=0.55)
        stars = 220

    # 3) star field — only above the waves, where the sky is darkest
    if stars:
        sd = ImageDraw.Draw(img, "RGBA")
        for _ in range(stars):
            x, y = rng.randint(0, W), rng.randint(0, int(H * 0.45))
            r = rng.choice([1, 1, 1, 2, 2, 3])
            a = rng.randint(40, 150)
            sd.ellipse([x - r, y - r, x + r, y + r], fill=(235, 242, 255, a))

    # 4) vignette toward the shadow colour
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.28, -H * 0.28, W * 1.28, H * 1.28], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(420))
    img = Image.composite(img, Image.new("RGB", (W, H), bottom), vig)

    # 5) fine grain — breaks up gradient banding, reads as premium texture
    noise = Image.effect_noise((W, H), 14).convert("L").point(lambda v: (v - 128) // 6 + 128)
    img = ImageChops.overlay(img, Image.merge("RGB", (noise, noise, noise)))
    return img


def build_gtk(key: str, meta: dict) -> None:
    """Per-theme libadwaita palette — the UI2 dark GTK-4 CSS recoloured to this
    theme, so Flatpak/GTK-4 apps carry the theme's accent, not UI2's teal."""
    if not SRC_GTK.exists():
        return
    m = hexmap(key)
    css = recolor(SRC_GTK.read_text(encoding="utf-8"), m)
    css = css.replace("MoOS UI2 (Graphite Dark)", f"{meta['name']}")
    write(SHARE / "moos/gtk" / f"moos-ui2-{key}.css", css)


def build_wallpaper(key: str, meta: dict) -> bool:
    img = make_wallpaper(key, meta.get("mood", "cosmic"))
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
    print(f"  ✓ {meta['name']:<16} style={meta['style']} lnf={meta['lnf']} "
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
