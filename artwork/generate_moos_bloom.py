#!/usr/bin/env python3
"""Build the optional Bloom finish above the existing MoOS/Plasma owners.

Curated GPL artwork supplies the Colloid frame and Fluent file vocabulary.
MoOS supplies the palette, complete native window actions and their ink.
The sixteen existing profiles are untouched.
"""
from __future__ import annotations

import configparser
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
from PIL import Image

ROOT = Path(os.environ.get("MOOS_BLOOM_TEST_ROOT", Path(__file__).resolve().parents[1]))
SHARE = ROOT / "system_files/usr/share"
VENDOR = ROOT / "artwork/vendor/bloom"
spec = importlib.util.spec_from_file_location("bloom_window_glyphs", ROOT / "artwork/generate_moos_aurorae.py")
glyphs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(glyphs)


def write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = data.encode() if isinstance(data, str) else data
    if not path.exists() or path.read_bytes() != body:
        path.write_bytes(body)


def rgb(value: str) -> tuple[int, int, int]:
    if value.startswith("#"):
        return tuple(int(value[i:i+2], 16) for i in (1, 3, 5))
    return tuple(int(c) for c in value.split(",")[:3])


def hex_color(value: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % value


def mix(ink: str, background: str, alpha: float) -> str:
    return hex_color(tuple(round(a*alpha+b*(1-alpha)) for a, b in zip(rgb(ink), rgb(background))))


def contrast(one: str, other: str) -> float:
    def luminance(value: str) -> float:
        channels = [c/255 for c in rgb(value)]
        linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(c*w for c, w in zip(linear, (.2126, .7152, .0722)))
    lo, hi = sorted((luminance(one), luminance(other)))
    return (hi+.05)/(lo+.05)


def readable_pair(background: str) -> tuple[str, str]:
    candidates = ("#14202D", "#F1F5F4")
    # Mid-luminance accents can fall between both ink choices. Move the fill
    # the smallest amount, rather than weakening the contrast requirement.
    for amount in range(26):
        fills = [background] if amount == 0 else [mix(end, background, amount/100) for end in candidates]
        pairs = [(fill, ink) for fill in fills for ink in candidates if contrast(ink, fill) >= 4.5]
        if pairs:
            return min(pairs, key=lambda pair: sum(abs(a-b) for a, b in zip(rgb(background), rgb(pair[0]))))
    raise ValueError("Bloom window action has no readable paired ink")


def button(name: str, background: str, accent: str, text: str) -> str:
    semantic = {"close": "#F36D75", "minimize": "#F2BE4F", "maximize": "#45C58A",
                "restore": "#45C58A"}.get(name, accent)
    groups = []
    for state in glyphs.BUTTON_STATES:
        disabled = state.startswith("deactivated")
        inactive = state.endswith("-inactive") or state == "inactive"
        pressed = state.startswith("pressed")
        hover = state.startswith("hover")
        alpha = .18 if disabled else (.65 if inactive else (1.0 if hover or pressed else .94))
        fill = mix(semantic, background, alpha)
        if disabled:
            ink = mix(text, fill, .36)
        else:
            fill, ink = readable_pair(fill)
        radius = 10.5 if hover else 9
        transform = 'translate(22 22) scale(.92) translate(-22 -22)' if pressed else 'translate(0 0)'
        # The transparent extent is the native 44px input target. The visible
        # 18px circle stays compact on a PC while the hit area also fits touch.
        groups.append(f'<g id="{state}-center"><rect width="44" height="44" fill="#000000" fill-opacity="0"/>'
                      f'<g transform="{transform}"><circle cx="22" cy="22" r="{radius}" fill="{fill}"/>'
                      f'<g transform="translate(12 12)">{glyphs._glyph(name, ink)}</g></g></g>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" viewBox="0 0 44 44">\n'
            + '\n'.join(groups) + '\n</svg>\n')


def frame(light: bool, profile: dict) -> None:
    name = profile["decoration"]
    mode = "light" if light else "dark"
    source = VENDOR / "colloid" / mode
    target = SHARE / "aurorae/themes" / name
    colors = configparser.ConfigParser(interpolation=None)
    colors.read(SHARE / "color-schemes" / (profile["scheme"] + ".colors"))
    background = hex_color(rgb(colors["Colors:Window"]["BackgroundNormal"]))
    text = hex_color(rgb(colors["Colors:Window"]["ForegroundNormal"]))
    secondary = next(mix(text, background, n/100) for n in range(70, 101)
                     if contrast(mix(text, background, n/100), background) >= 4.5)
    svg = (source / "decoration.svg").read_text()
    # Keep the vendor geometry, but bake the matched MoOS palette into every
    # currentColor shape. Plain QSvgRenderer and Aurorae must agree, including
    # after a maximized/restored transition and with no colour-scheme extension.
    for role, color in (("Text", text), ("Background", background),
                        ("HeaderBackground", background), ("Highlight", profile["accent"])):
        svg = re.sub(r'class="ColorScheme-'+role+r'"\s+fill="currentColor"',
                     'fill="'+color+'"', svg)
    extra = []
    for prefix, original in (("decoration-opaque", "decoration"),
                             ("decoration-opaque-inactive", "decoration-inactive")):
        for position in glyphs.FRAME_POSITIONS:
            extra.append(f'<use id="{prefix}-{position}" xlink:href="#{original}-{position}"/>')
    for prefix in ("decoration-maximized", "decoration-maximized-inactive",
                   "decoration-maximized-opaque", "decoration-maximized-opaque-inactive"):
        extra.append(f'<rect id="{prefix}-center" width="24" height="24" fill="{background}"/>')
    write(target / "decoration.svg", svg.replace("</svg>", '\n'.join(extra) + '\n</svg>'))
    rc = (source / "theme.rc").read_text()
    settings = {"ActiveTextColor": ','.join(map(str, rgb(text))),
                "InactiveTextColor": ','.join(map(str, rgb(secondary))),
                "UseTextShadow": "false", "Animation": "140", "Shadow": "true",
                "TitleHeight": "44", "TitleEdgeTop": "0", "TitleEdgeBottom": "0",
                "TitleEdgeTopMaximized": "0", "TitleEdgeBottomMaximized": "0",
                "TitleBorderLeft": "140", "TitleBorderRight": "140",
                "ButtonWidth": "44", "ButtonHeight": "44", "ButtonSpacing": "2",
                "ButtonMarginTop": "0"}
    for key, value in settings.items():
        rc, count = re.subn(r'^'+key+r'=.*$', key+'='+value, rc, flags=re.M)
        if count != 1:
            raise ValueError(f"Unexpected upstream Aurorae key {key}")
    rc += '\n# 44px target and title match in restored and maximized states.\nButtonMarginTopMaximized=0\n'
    write(target / (name+"rc"), rc)
    for action in glyphs.BUTTONS:
        write(target / (action+".svg"), button(action, background, profile["accent"], text))
    write(target / "metadata.desktop", '[Desktop Entry]\nName=MoOS UI · Bloom'+(' Light' if light else '')+'\n'
          'Comment=Soft native MoOS window frame\nX-KDE-PluginInfo-Author=MoOS; Vince Liuice\n'
          f'X-KDE-PluginInfo-Name={name}\nX-KDE-PluginInfo-Version=1.0\n'
          'X-KDE-PluginInfo-License=GPL-3.0\nX-KDE-ServiceTypes=KWin/Decoration\nType=Service\n')
    write(target / "COPYING", (VENDOR / "colloid/COPYING").read_bytes())
    write(target / "UPSTREAM.json", (VENDOR / "UPSTREAM.json").read_bytes())


def lnf_defaults(profile: dict, original: str) -> str:
    light = profile["mode"] == "light"
    suffix = ".light" if light else ""
    parent = "MoOSUI2AmethystLight" if light else "MoOSUI2Amethyst"
    title = "MoOS UI · Bloom"+(' Light' if light else '')
    old_title = "MoOS UI · Amethyst"+(' Light' if light else '')
    for old, new in (("org.moos.ui2.amethyst"+suffix, profile["id"]),
                     ("theme=__aurorae__svg__"+parent, "theme=__aurorae__svg__"+profile["decoration"]),
                     ("Theme="+parent+'\n', "Theme="+profile["icons"]+'\n'),
                     ("ColorScheme="+parent+'\n', "ColorScheme="+profile["scheme"]+'\n'),
                     ("name="+parent+'\n', "name="+profile["style"]+'\n'),
                     ("Image="+parent+'\n', "Image="+profile["wallpaper"]+'\n')):
        original = original.replace(old, new)
    return original.replace(old_title, title)


def main() -> None:
    inputs = json.loads((VENDOR / "UPSTREAM.json").read_text())
    for row in inputs["files"]:
        source = ROOT / row["target"]
        if not source.resolve().is_relative_to(VENDOR.resolve()):
            raise ValueError("Bloom vendor input escapes the curated tree")
        if hashlib.sha256(source.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Bloom vendor input differs from its pinned source: "+row["target"])
    document = json.loads((ROOT / "artwork/moos-design/theme-profiles.json").read_text())
    profiles = {p["id"]: p for p in document["profiles"]}
    master = ROOT / "artwork/moos-ui2/wallpapers/moos-bloom-master.png"
    generation = json.loads((master.parent / "bloom-generation.json").read_text())
    if hashlib.sha256(master.read_bytes()).hexdigest() != generation["sha256"]:
        raise ValueError("Bloom master no longer matches its generation provenance")
    for light in (False, True):
        suffix = ".light" if light else ""
        profile = profiles["org.moos.ui2.bloom"+suffix]
        parent = "MoOSUI2AmethystLight" if light else "MoOSUI2Amethyst"
        title = "MoOS UI · Bloom"+(' Light' if light else '')
        old_title = "MoOS UI · Amethyst"+(' Light' if light else '')
        wall = SHARE / "wallpapers" / profile["wallpaper"]
        canvas = master if light else SHARE / "wallpapers/MoOSPrismNight/contents/images/1672x941.png"
        for branch in ("images", "images_dark"):
            write(wall / "contents" / branch / "1672x941.png", canvas.read_bytes())
        write(wall / "metadata.json", json.dumps({"KPackageStructure": "Wallpaper/Images", "KPlugin": {
            "Id": profile["wallpaper"], "Name": title,
            "Name[ar]": "MoOS · بلوم"+(' الفاتح' if light else ' الداكن'),
            "License": "CC-BY-SA-4.0", "Authors": [{"Name": "MoOS"}]}}, ensure_ascii=False, indent=2)+'\n')
        write(wall / "README.md", 'Original imagegen artwork. Native1672×941; no upscale. '
              'Both standard package branches retain the exact original PNG.\n')
        # Own complete style/symbol packages, with the existing engine and
        # palette roles. The profile's scheme/style/icon names stay identical.
        source_style = SHARE / "plasma/desktoptheme" / parent
        style = SHARE / "plasma/desktoptheme" / profile["style"]
        for source in source_style.rglob("*"):
            if source.is_file():
                write(style / source.relative_to(source_style), source.read_bytes())
        metadata = json.loads((style / "metadata.json").read_text())
        metadata["KPlugin"].update(Id=profile["style"], Name=title)
        write(style / "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
        colors = (SHARE / "color-schemes" / (parent+'.colors')).read_text().replace(old_title, title)
        write(SHARE / "color-schemes" / (profile["scheme"]+'.colors'), colors)
        write(style / "colors", colors)
        plasma = (style / "plasmarc").read_text().replace(old_title, title).replace('defaultWallpaperTheme='+parent,
                    'defaultWallpaperTheme='+profile["wallpaper"]).replace('defaultFileSuffix=.jpg',
                    'defaultFileSuffix=.png').replace('defaultWidth=1920', 'defaultWidth=1672').replace(
                    'defaultHeight=1080', 'defaultHeight=941')
        write(style / "plasmarc", plasma)
        frame(light, profile)
        icon_name = profile["icons"]
        target = SHARE / "icons" / icon_name
        parent_icons = SHARE / "icons" / parent
        for source in parent_icons.rglob("*"):
            if source.is_file() and source.name != 'index.theme':
                write(target / source.relative_to(parent_icons), source.read_bytes())
        for category in ("places", "mimetypes"):
            for source in (VENDOR / "fluent" / category).rglob("*"):
                if source.is_file():
                    write(target / category / source.relative_to(VENDOR / "fluent" / category), source.read_bytes())
        index = (parent_icons / "index.theme").read_text().replace(old_title, title)
        index = index.replace('Directories=', 'Directories=places/scalable,mimetypes/scalable,', 1)
        index += ('\n[places/scalable]\nSize=64\nContext=Places\nType=Scalable\nMinSize=16\nMaxSize=512\n'
                  '[mimetypes/scalable]\nSize=64\nContext=MimeTypes\nType=Scalable\nMinSize=16\nMaxSize=512\n')
        write(target / "index.theme", index)
        write(target / "COPYING", (VENDOR / "fluent/COPYING").read_bytes())
        write(target / "UPSTREAM.json", (VENDOR / "UPSTREAM.json").read_bytes())
        lnf = SHARE / "plasma/look-and-feel" / profile["id"]
        original = SHARE / "plasma/look-and-feel" / ("org.moos.ui2.amethyst"+suffix)
        for directory in ("splash", "logout"):
            for source in (original / "contents" / directory).rglob("*"):
                if source.is_file():
                    write(lnf / "contents" / directory / source.relative_to(original / "contents" / directory), source.read_bytes())
        metadata = json.loads((original / "metadata.json").read_text())
        metadata["KPlugin"].update(Id=profile["id"], Name=title,
            **{"Name[ar]": "MoOS · بلوم"+(' الفاتح' if light else ' الداكن'),
               "Description": "إطارات ناعمة وألوان حيوية | Soft frames and lively MoOS colour",
               "Description[ar]": "إطارات ناعمة وألوان حيوية لهوية MoOS"})
        write(lnf / "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2)+'\n')
        defaults = lnf_defaults(profile, (original / "contents/defaults").read_text())
        write(lnf / "contents/defaults", defaults)
        preview = wall / "contents" / profile["wallpaperBranch"] / "1672x941.png"
        for name in ("preview.png", "lockscreen.png", "splash.png"):
            write(lnf / "contents/previews" / name, preview.read_bytes())
        with Image.open(preview) as image:
            jpeg = io.BytesIO()
            image.convert("RGB").save(jpeg, "JPEG", quality=92, subsampling=0)
        write(lnf / "contents/previews/fullscreenpreview.jpg", jpeg.getvalue())
        write(lnf / "README.md", 'Bloom is an optional MoOS finish using existing Plasma owners, '
              'MoOS Amethyst colours, a complete Aurorae action set and curated GPL artwork. '
              'Previews show the actual wallpaper. The Qt/GTK engine remains the profile engine.\n')
    print("MoOS Bloom: matched native dark/light finishes generated")


if __name__ == "__main__":
    main()
