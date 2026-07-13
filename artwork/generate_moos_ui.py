#!/usr/bin/env python3
"""Build the MoOS UI dark/light packages from the proven Nova geometry.

Nova stays installed as the rollback theme. This generator copies only its visual
contracts (FrameSvg, Aurorae and Look-and-Feel package structure), then changes the
identity selectors and palette. Run from anywhere; outputs are repository-relative.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files/usr/share"

DARK_MAP = {
    "#050A14": "#100C14", "#0B1220": "#17131D", "#111A2E": "#241D2B",
    "#16203A": "#2A2031", "#1A2740": "#312538", "#263557": "#3A2B43",
    "#03060D": "#0C0910", "#04070F": "#110D15",
    "#2E7BFF": "#A855F7", "#22D3EE": "#FB923C", "#8B5CF6": "#C084FC",
    "#38BDF8": "#D864A4", "#E6EDF7": "#EEE7F0", "#9FB0C9": "#B8AABD",
    "#FFFFFF": "#F3ECF4",
    "5,10,20": "16,12,20", "11,18,32": "23,19,29",
    "17,26,46": "36,29,43", "26,39,64": "49,37,56",
    "46,123,255": "168,85,247", "34,211,238": "251,146,60",
    "139,92,246": "192,132,252", "56,189,248": "216,100,164",
    "230,237,247": "238,231,240", "159,176,201": "184,170,189",
    "255,255,255": "243,236,244",
}

LIGHT_MAP = {
    "#FFFFFF": "#F1EBE3", "#EEF3FB": "#E7DDD2", "#E2EAF7": "#DDD0C4",
    "#111A2E": "#29212E", "#0B1220": "#211A25",
    "#2E7BFF": "#7C3AED", "#22D3EE": "#C2410C", "#8B5CF6": "#9333EA",
    "226,234,247": "231,221,210", "238,243,251": "241,235,227",
    "255,255,255": "241,235,227", "16,24,40": "41,33,46",
    "113,128,150": "117,104,120", "46,123,255": "124,58,237",
    "34,211,238": "194,65,12", "14,116,144": "147,51,15",
    "30,79,216": "124,58,237", "109,40,217": "147,51,234",
}

IDENTITY_MAP = {
    "org.moos.nova.light": "org.moos.ui.light",
    "org.moos.nova": "org.moos.ui",
    "MoOSNovaLight": "MoOSUILight",
    "MoOSNova": "MoOSUI",
    "NovaLight": "MoOSUILight",
    "NovaDark": "MoOSUIDark",
    "MoOS Nova Light": "MoOS UI Light",
    "MoOS Nova": "MoOS UI",
    "نوفا الفاتحة": "واجهة MoOS الفاتحة",
    "نوفا": "واجهة MoOS",
}


def copy_tree(src: pathlib.Path, dst: pathlib.Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def rewrite_tree(root: pathlib.Path, mapping: dict[str, str]) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in mapping.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def generated_copy(src: str, dst: str, palette: dict[str, str]) -> None:
    source, target = SHARE / src, SHARE / dst
    copy_tree(source, target)
    rewrite_tree(target, IDENTITY_MAP | palette)


def render(svg: pathlib.Path, target: pathlib.Path, width: int, height: int) -> None:
    converter = shutil.which("rsvg-convert")
    if converter is None:
        raise SystemExit("rsvg-convert is required to export MoOS UI raster assets")
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [converter, "-w", str(width), "-h", str(height), str(svg), "-o", str(target)],
        check=True,
    )


def render_jpeg(svg: pathlib.Path, target: pathlib.Path, width: int, height: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is required to export MoOS UI JPEG previews")
    intermediate = target.with_suffix(".source.png")
    render(svg, intermediate, width, height)
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(intermediate),
         "-q:v", "2", str(target)],
        check=True,
    )
    intermediate.unlink()


def main() -> None:
    generated_copy("plasma/desktoptheme/Nova", "plasma/desktoptheme/MoOSUI", DARK_MAP)
    generated_copy("plasma/desktoptheme/NovaLight", "plasma/desktoptheme/MoOSUILight", LIGHT_MAP)
    generated_copy("plasma/look-and-feel/org.moos.nova", "plasma/look-and-feel/org.moos.ui", DARK_MAP)
    generated_copy("plasma/look-and-feel/org.moos.nova.light", "plasma/look-and-feel/org.moos.ui.light", LIGHT_MAP)
    generated_copy("aurorae/themes/MoOSNova", "aurorae/themes/MoOSUI", DARK_MAP)
    generated_copy("aurorae/themes/MoOSNovaLight", "aurorae/themes/MoOSUILight", LIGHT_MAP)
    (SHARE / "aurorae/themes/MoOSUI/MoOSNovarc").rename(
        SHARE / "aurorae/themes/MoOSUI/MoOSUIrc"
    )
    (SHARE / "aurorae/themes/MoOSUILight/MoOSNovaLightrc").rename(
        SHARE / "aurorae/themes/MoOSUILight/MoOSUILightrc"
    )

    files = (
        ("color-schemes/NovaDark.colors", "color-schemes/MoOSUIDark.colors", DARK_MAP),
        ("color-schemes/NovaLight.colors", "color-schemes/MoOSUILight.colors", LIGHT_MAP),
        ("konsole/NovaDark.colorscheme", "konsole/MoOSUIDark.colorscheme", DARK_MAP),
        ("konsole/NovaLight.colorscheme", "konsole/MoOSUILight.colorscheme", LIGHT_MAP),
        ("konsole/MoOS.profile", "konsole/MoOSUI.profile", DARK_MAP),
        ("konsole/MoOSLight.profile", "konsole/MoOSUILight.profile", LIGHT_MAP),
    )
    for src, dst, palette in files:
        target = SHARE / dst
        target.write_text((SHARE / src).read_text(encoding="utf-8"), encoding="utf-8")
        text = target.read_text(encoding="utf-8")
        for old, new in (IDENTITY_MAP | palette).items():
            text = text.replace(old, new)
        target.write_text(text, encoding="utf-8")

    # Path-specific selectors that must not be changed globally (wallpaper names
    # legitimately retain Nova branding because they are shared assets).
    replacements = {
        SHARE / "plasma/desktoptheme/MoOSUI/metadata.json": {'"Id": "Nova"': '"Id": "MoOSUI"'},
        SHARE / "plasma/desktoptheme/MoOSUI/plasmarc": {
            "defaultWallpaperTheme=NovaHorizonII": "defaultWallpaperTheme=MoOSUIAtmosphere",
        },
        SHARE / "plasma/desktoptheme/MoOSUILight/metadata.json": {'"Id": "MoOSUILight"': '"Id": "MoOSUILight"'},
        SHARE / "plasma/desktoptheme/MoOSUILight/plasmarc": {
            "FallbackTheme=Nova": "FallbackTheme=MoOSUI",
            "defaultWallpaperTheme=NovaAurora": "defaultWallpaperTheme=MoOSUIAtmosphere",
        },
        SHARE / "plasma/look-and-feel/org.moos.ui/contents/defaults": {
            "name=Nova": "name=MoOSUI",
            "Image=NovaHorizonII": "Image=MoOSUIAtmosphere",
        },
        SHARE / "plasma/look-and-feel/org.moos.ui.light/contents/defaults": {
            "name=MoOSUILight": "name=MoOSUILight",
            "[kdeglobals][Icons]\nTheme=MoOSUILight": "[kdeglobals][Icons]\nTheme=NovaLight",
            "Image=NovaAurora": "Image=MoOSUIAtmosphere",
        },
        SHARE / "konsole/MoOSUI.profile": {"ColorScheme=MoOSUIDark": "ColorScheme=MoOSUIDark", "Name=MoOS": "Name=MoOS UI"},
        SHARE / "konsole/MoOSUILight.profile": {"ColorScheme=MoOSUILight": "ColorScheme=MoOSUILight", "Name=MoOS Light": "Name=MoOS UI Light"},
    }
    for path, mapping in replacements.items():
        text = path.read_text(encoding="utf-8")
        for old, new in mapping.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    # First-party app icons. The SVG is the master; PNGs are deliberate hicolor
    # fallbacks for Plasma scale factors and third-party desktop readers.
    icon_sources = {
        "moos-moai": ROOT / "artwork/moos-ui/icons/moos-moai.svg",
        "moos-pc-remote": ROOT / "artwork/moos-ui/icons/moos-pc-remote.svg",
    }
    for name, source in icon_sources.items():
        shutil.copy2(source, SHARE / f"icons/hicolor/scalable/apps/{name}.svg")
        for size in (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512):
            render(source, SHARE / f"icons/hicolor/{size}x{size}/apps/{name}.png", size, size)
    remote_512 = SHARE / "icons/hicolor/512x512/apps/moos-pc-remote.png"
    shutil.copy2(remote_512, ROOT / "moremote/Logo.png")
    # Compatibility for an old user-local desktop entry carrying the retired icon name.
    shutil.copy2(remote_512, SHARE / "icons/hicolor/512x512/apps/mo-remote-personal.png")

    # Matched wallpaper package. Plasma selects images_dark automatically for the
    # dark colour scheme, while explicit theme switching writes the exact file too.
    wallpaper = SHARE / "wallpapers/MoOSUIAtmosphere/contents"
    light_svg = ROOT / "artwork/moos-ui/wallpapers/moos-ui-light.svg"
    dark_svg = ROOT / "artwork/moos-ui/wallpapers/moos-ui-dark.svg"
    for width, height in ((3840, 2160), (3440, 1440), (2560, 1600)):
        filename = f"{width}x{height}.png"
        render(light_svg, wallpaper / "images" / filename, width, height)
        render(dark_svg, wallpaper / "images_dark" / filename, width, height)
    render(light_svg, wallpaper / "screenshot.png", 1920, 1080)

    # System Settings previews must show the new package, not the Nova screenshot
    # copied as structural input above. Otherwise the theme is correct on disk but
    # advertises the old blue desktop in the user-facing picker.
    previews = (
        ("org.moos.ui", ROOT / "artwork/moos-ui/previews/moos-ui-dark-preview.svg", dark_svg),
        ("org.moos.ui.light", ROOT / "artwork/moos-ui/previews/moos-ui-light-preview.svg", light_svg),
    )
    for package, preview_svg, background_svg in previews:
        out = SHARE / f"plasma/look-and-feel/{package}/contents/previews"
        render(preview_svg, out / "preview.png", 600, 337)
        render(background_svg, out / "lockscreen.png", 600, 337)
        render(background_svg, out / "splash.png", 300, 169)
        render_jpeg(preview_svg, out / "fullscreenpreview.jpg", 1920, 1080)

    print("generated MoOS UI dark/light packages")


if __name__ == "__main__":
    main()
