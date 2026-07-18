#!/usr/bin/env python3
"""MoOS UI2 visual-family gate.

This is deliberately a repository test, not a screenshot assertion.  It proves
that both UI2 variants are complete, separately rendered packages and that the
passive dashboard keeps its local artwork, safe QML surface, and reduced-motion
seam.  Set MOOS_UI2_TEST_ROOT to exercise the same checks against a temporary
copy without touching the working tree.
"""

from __future__ import annotations

import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("MOOS_UI2_TEST_ROOT", DEFAULT_ROOT)).resolve()
SHARE = ROOT / "system_files/usr/share"
ART = ROOT / "artwork/moos-ui2"
# The dashboard bento lives INSIDE the wallpaper plugin (the scene renders image
# + bento as one layer BELOW the desktop icons). It used to be a desktop applet,
# and as an applet it always drew on top of the Folder View icons.
DASHBOARD = SHARE / "plasma/wallpapers/org.moos.ui2.wallpaper"

VARIANTS = {
    "dark": {
        "look_and_feel": "org.moos.ui2",
        "desktop_theme": "MoOSUI2",
        "scheme": "MoOSUI2Dark",
        "aurorae": "MoOSUI2",
        "aurorae_rc": "MoOSUI2rc",
        "konsole_profile": "MoOSUI2.profile",
        "konsole_scheme": "MoOSUI2Dark.colorscheme",
        "wallpaper": "MoOSUI2Graphite",
        "icons": "MoOSUI2",
        "fallback": "breeze-dark",
    },
    "light": {
        "look_and_feel": "org.moos.ui2.light",
        "desktop_theme": "MoOSUI2Light",
        "scheme": "MoOSUI2Light",
        "aurorae": "MoOSUI2Light",
        "aurorae_rc": "MoOSUI2Lightrc",
        "konsole_profile": "MoOSUI2Light.profile",
        "konsole_scheme": "MoOSUI2Light.colorscheme",
        "wallpaper": "MoOSUI2Tide",
        "icons": "MoOSUI2Light",
        "fallback": "default",
    },
}

REQUIRED_DESKTOP_SVGS = {
    "dialogs/background.svg",
    "icons/start.svg",
    "widgets/branding.svg",
    "widgets/button.svg",
    "widgets/line.svg",
    "widgets/lineedit.svg",
    "widgets/listitem.svg",
    "widgets/panel-background.svg",
    "widgets/plasmoidheading.svg",
    "widgets/tasks.svg",
    "widgets/viewitem.svg",
}

REQUIRED_AURORAE_SVGS = {
    "close.svg",
    "decoration.svg",
    "maximize.svg",
    "minimize.svg",
    "restore.svg",
}

WEATHER_KINDS = {
    "clear-day",
    "clear-night",
    "cloudy",
    "fog",
    "partly-day",
    "partly-night",
    "rain",
    "snow",
    "storm",
}

BANNED_DASHBOARD_TYPES = (
    "MouseArea",
    "TapHandler",
    "ShaderEffect",
    "QtQuick3D",
    "MultiEffect",
    "Lottie",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_kconfig(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def png_info(path: Path) -> tuple[int, int, int, int]:
    """Return width, height, bit depth and colour type from a PNG IHDR."""
    with path.open("rb") as image:
        header = image.read(26)
    if len(header) != 26 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    if header[12:16] != b"IHDR":
        raise AssertionError(f"PNG has no leading IHDR: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height, header[24], header[25]


def jpeg_dimensions(path: Path) -> tuple[int, int]:
    """Read JPEG width/height from its SOF marker without an image dependency."""
    data = path.read_bytes()
    if not data.startswith(b"\xff\xd8"):
        raise AssertionError(f"not a JPEG: {path}")
    offset = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
           0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset + 4 <= len(data):
        while offset < len(data) and data[offset] != 0xFF:
            offset += 1
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset:offset + 2], "big")
        if length < 2 or offset + length > len(data):
            break
        if marker in sof and length >= 7:
            height = int.from_bytes(data[offset + 3:offset + 5], "big")
            width = int.from_bytes(data[offset + 5:offset + 7], "big")
            return width, height
        offset += length
    raise AssertionError(f"JPEG has no SOF dimensions: {path}")


def parse_rgb(value: str) -> tuple[int, int, int]:
    parts = tuple(int(part.strip()) for part in value.split(","))
    if len(parts) != 3 or any(part < 0 or part > 255 for part in parts):
        raise AssertionError(f"invalid RGB colour: {value!r}")
    return parts


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for channel in rgb:
        value = channel / 255
        channels.append(value / 12.92 if value <= 0.04045
                        else math.pow((value + 0.055) / 1.055, 2.4))
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast_ratio(first: tuple[int, int, int],
                   second: tuple[int, int, int]) -> float:
    lighter, darker = sorted((relative_luminance(first),
                              relative_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def hex_rgb(value: str) -> tuple[int, int, int]:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise AssertionError(f"invalid six-digit colour: {value!r}")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


class TestMoOSUI2(unittest.TestCase):
    maxDiff = None

    def assert_files(self, base: Path, relative_paths: set[str]) -> None:
        for relative in sorted(relative_paths):
            path = base / relative
            self.assertTrue(path.is_file(), f"missing UI2 file: {path}")
            self.assertGreater(path.stat().st_size, 0, f"empty UI2 file: {path}")

    def test_variant_packages_are_complete_and_cross_linked(self) -> None:
        for variant, names in VARIANTS.items():
            with self.subTest(variant=variant):
                look_and_feel = SHARE / "plasma/look-and-feel" / names["look_and_feel"]
                desktop = SHARE / "plasma/desktoptheme" / names["desktop_theme"]
                aurorae = SHARE / "aurorae/themes" / names["aurorae"]
                scheme = SHARE / "color-schemes" / f"{names['scheme']}.colors"
                profile = SHARE / "konsole" / names["konsole_profile"]
                terminal_scheme = SHARE / "konsole" / names["konsole_scheme"]
                wallpaper = SHARE / "wallpapers" / names["wallpaper"]

                self.assert_files(look_and_feel, {
                    "metadata.json",
                    "contents/defaults",
                    "contents/splash/Splash.qml",
                    "contents/splash/images/moos-logo.png",
                    "contents/logout/Logout.qml",
                    "contents/logout/MoOSUI2ActionButton.qml",
                    "contents/previews/preview.png",
                    "contents/previews/lockscreen.png",
                    "contents/previews/splash.png",
                    "contents/previews/fullscreenpreview.jpg",
                })
                self.assert_files(desktop, {"metadata.json", "plasmarc", "colors"})
                self.assert_files(aurorae, {
                    "metadata.desktop",
                    names["aurorae_rc"],
                    *REQUIRED_AURORAE_SVGS,
                })
                self.assert_files(wallpaper, {"metadata.json", "contents/screenshot.png"})
                self.assertTrue(scheme.is_file(), f"missing colour scheme: {scheme}")
                self.assertTrue(profile.is_file(), f"missing Konsole profile: {profile}")
                self.assertTrue(terminal_scheme.is_file(),
                                f"missing Konsole scheme: {terminal_scheme}")

                look_metadata = load_json(look_and_feel / "metadata.json")
                self.assertEqual(look_metadata["KPlugin"]["Id"], names["look_and_feel"])
                self.assertEqual(look_metadata["KPackageStructure"], "Plasma/LookAndFeel")

                desktop_metadata = load_json(desktop / "metadata.json")
                self.assertEqual(desktop_metadata["KPlugin"]["Id"], names["desktop_theme"])
                wallpaper_metadata = load_json(wallpaper / "metadata.json")
                self.assertEqual(wallpaper_metadata["KPlugin"]["Id"], names["wallpaper"])

                defaults = (look_and_feel / "contents/defaults").read_text(encoding="utf-8")
                for selector in (
                    f"ColorScheme={names['scheme']}",
                    f"name={names['desktop_theme']}",
                    f"Theme={names['look_and_feel']}",
                    f"Theme={names['icons']}",
                    f"theme=__aurorae__svg__{names['aurorae']}",
                ):
                    self.assertIn(selector, defaults,
                                  f"{look_and_feel} does not select {selector}")
                # NO [Wallpaper] section, deliberately: LookAndFeelManager applies
                # it by forcing org.kde.image onto every desktop containment, which
                # would replace org.moos.ui2.wallpaper (the scene that draws the
                # dashboard below the icons) on every theme apply. moos-theme /
                # moos-apply-theme own the desktop wallpaper per half instead.
                self.assertNotIn("[Wallpaper]", defaults,
                                 f"{look_and_feel} must not carry a [Wallpaper] section — "
                                 "it would erase the MoOS scene on every apply")

                plasmarc = (desktop / "plasmarc").read_text(encoding="utf-8")
                self.assertIn(f"FallbackTheme={names['fallback']}", plasmarc)
                self.assertIn(f"defaultWallpaperTheme={names['wallpaper']}", plasmarc)
                self.assertIn("[AdaptiveTransparency]\nenabled=false", plasmarc)

                colour_config = load_kconfig(scheme)
                self.assertEqual(colour_config["General"]["ColorScheme"], names["scheme"])
                self.assertEqual((desktop / "colors").read_bytes(), scheme.read_bytes(),
                                 "desktop palette must equal the standalone KDE scheme")

                profile_config = load_kconfig(profile)
                self.assertEqual(profile_config["Appearance"]["ColorScheme"],
                                 Path(names["konsole_scheme"]).stem)

                aurorae_metadata = (aurorae / "metadata.desktop").read_text(encoding="utf-8")
                self.assertIn(f"X-KDE-PluginInfo-Name={names['aurorae']}",
                              aurorae_metadata)

        dark_defaults = (SHARE / "plasma/look-and-feel/org.moos.ui2/contents/defaults")
        light_defaults = (SHARE / "plasma/look-and-feel/org.moos.ui2.light/contents/defaults")
        self.assertNotEqual(dark_defaults.read_bytes(), light_defaults.read_bytes(),
                            "Dark and Light must remain independently selectable")

        light_readme = (SHARE / "plasma/look-and-feel/org.moos.ui2.light/README.md")
        light_readme_text = light_readme.read_text(encoding="utf-8")
        for light_identity in ("org.moos.ui2.light", "MoOSUI2Light", "MoOSUI2Tide"):
            self.assertIn(
                light_identity, light_readme_text,
                f"light package README must document its own {light_identity} identity",
            )
        self.assertNotRegex(
            light_readme_text,
            r"(?m)^.*(?:--apply|--lookandfeel)\s+org\.moos\.ui2\s*$",
            "light package README must not tell maintainers to apply the dark package",
        )

        generator = (ROOT / "artwork/generate_moos_ui2.py").read_text(encoding="utf-8")
        for transaction_guard in (
            "def preflight()", "tempfile.TemporaryDirectory",
            "backups: dict", "except BaseException", "backup.rename(output)",
            "generate_weather_runtime()",
        ):
            self.assertIn(
                transaction_guard, generator,
                "the UI2 generator must validate inputs and restore all previous "
                "outputs if generation fails midway",
            )

    def test_generator_restores_outputs_when_backup_phase_fails(self) -> None:
        """A later backup rename failure must not delete earlier outputs."""
        generator = DEFAULT_ROOT / "artwork/generate_moos_ui2.py"
        palette = DEFAULT_ROOT / "artwork/moos-ui2/palette.json"

        with tempfile.TemporaryDirectory(prefix="moos-ui2-transaction-test-") as tmp:
            fixture = Path(tmp)
            share = fixture / "system_files/usr/share"
            art = fixture / "artwork/moos-ui2"
            art.mkdir(parents=True)
            (art / "palette.json").write_bytes(palette.read_bytes())

            # protected_snapshot() only needs each protected path to exist for
            # this backup-phase test; generation is intentionally never reached.
            protected = (
                share / "plasma/desktoptheme/MoOSUI",
                share / "plasma/desktoptheme/MoOSUILight",
                share / "plasma/look-and-feel/org.moos.ui",
                share / "plasma/look-and-feel/org.moos.ui.light",
                share / "aurorae/themes/MoOSUI",
                share / "aurorae/themes/MoOSUILight",
                share / "color-schemes/MoOSUIDark.colors",
                share / "color-schemes/MoOSUILight.colors",
                share / "konsole/MoOSUIDark.colorscheme",
                share / "konsole/MoOSUILight.colorscheme",
                share / "wallpapers/MoOSUIAtmosphere",
                share / "plasma/plasmoids/org.moos.nova.deskclock",
            )
            protected_files = {
                share / "color-schemes/MoOSUIDark.colors",
                share / "color-schemes/MoOSUILight.colors",
                share / "konsole/MoOSUIDark.colorscheme",
                share / "konsole/MoOSUILight.colorscheme",
            }
            for path in protected:
                if path in protected_files:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"protected:{path.name}\n", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
                    (path / "sentinel").write_text(
                        f"protected:{path.name}\n", encoding="utf-8"
                    )

            # preflight() runs before any rename. Raster validity is irrelevant
            # here because the injected fifth backup failure happens first.
            for master in (
                art / "wallpapers/moos-ui2-graphite-master.png",
                art / "wallpapers/moos-ui2-tide-master.png",
            ):
                master.parent.mkdir(parents=True, exist_ok=True)
                master.write_bytes(b"fixture-png")
            for kind in WEATHER_KINDS:
                weather = art / "weather" / f"{kind}.png"
                weather.parent.mkdir(parents=True, exist_ok=True)
                weather.write_bytes(b"fixture-png")

            outputs = (
                share / "plasma/desktoptheme/MoOSUI2",
                share / "plasma/desktoptheme/MoOSUI2Light",
                share / "plasma/look-and-feel/org.moos.ui2",
                share / "plasma/look-and-feel/org.moos.ui2.light",
                share / "aurorae/themes/MoOSUI2",
                share / "aurorae/themes/MoOSUI2Light",
                share / "color-schemes/MoOSUI2Dark.colors",
                share / "color-schemes/MoOSUI2Light.colors",
                share / "konsole/MoOSUI2Dark.colorscheme",
                share / "konsole/MoOSUI2Light.colorscheme",
                share / "konsole/MoOSUI2.profile",
                share / "konsole/MoOSUI2Light.profile",
                share / "wallpapers/MoOSUI2Graphite",
                share / "wallpapers/MoOSUI2Tide",
                share / "plasma/wallpapers/org.moos.ui2.wallpaper/contents/images/weather",
            )
            output_files = set(outputs[6:12])
            for index, path in enumerate(outputs):
                if path in output_files:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"output-file:{index}\n", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
                    (path / "sentinel").write_text(
                        f"output-directory:{index}\n", encoding="utf-8"
                    )

            def snapshot(path: Path) -> tuple[str, bytes]:
                if path.is_file():
                    return "file", path.read_bytes()
                members = []
                for item in sorted(candidate for candidate in path.rglob("*")
                                   if candidate.is_file()):
                    members.append(str(item.relative_to(path)).encode())
                    members.append(b"\0")
                    members.append(item.read_bytes())
                    members.append(b"\0")
                return "directory", b"".join(members)

            before = {path: snapshot(path) for path in outputs}
            fake_bin = fixture / "test-bin"
            fake_bin.mkdir()
            fake_ffmpeg = fake_bin / "ffmpeg"
            fake_ffmpeg.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            fake_ffmpeg.chmod(0o755)
            environment = os.environ.copy()
            environment.update({
                "MOOS_UI2_TEST_ROOT": str(fixture),
                "MOOS_UI2_TEST_FAIL_BACKUP_AT": "5",
                # preflight only checks availability before the injected backup
                # failure. Keep this regression independent of the host runner's
                # multimedia packages; the fake encoder must never be executed.
                "PATH": f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}",
            })
            result = subprocess.run(
                [sys.executable, "-B", str(generator)],
                cwd=DEFAULT_ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("injected UI2 backup rename failure at output 5", result.stdout)
            self.assertEqual(
                {path: snapshot(path) for path in outputs}, before,
                "backup-phase failure did not restore every UI2 output byte-for-byte",
            )
            self.assertEqual(
                list(fixture.glob(".moos-ui2-backup-*")), [],
                "transaction temporary directory leaked after restoration",
            )

    def test_palette_contrast_and_no_pure_white(self) -> None:
        palettes = load_json(ART / "palette.json")
        required_roles = {
            "canvas", "surface", "card", "raised", "primary", "secondary",
            "luminous", "positive", "warning", "negative", "text", "muted",
            "outline", "shadow", "panel_top", "panel_mid", "panel_bottom",
        }
        self.assertEqual(set(palettes), {"dark", "light"})

        for variant, palette in palettes.items():
            with self.subTest(palette=variant):
                self.assertEqual(set(palette), required_roles)
                for role, literal in palette.items():
                    colour = hex_rgb(literal)
                    self.assertNotIn(colour, {(255, 255, 255), (0, 0, 0)},
                                     f"{variant}.{role} must not be pure white/black")
                for surface in ("canvas", "surface", "card", "raised"):
                    ratio = contrast_ratio(hex_rgb(palette["text"]),
                                           hex_rgb(palette[surface]))
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f"{variant} text/{surface} contrast is only {ratio:.2f}:1",
                    )
                for surface in ("canvas", "surface", "card"):
                    ratio = contrast_ratio(hex_rgb(palette["muted"]),
                                           hex_rgb(palette[surface]))
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f"{variant} muted/{surface} contrast is only {ratio:.2f}:1",
                    )

        for variant, names in VARIANTS.items():
            scheme_path = SHARE / "color-schemes" / f"{names['scheme']}.colors"
            scheme = load_kconfig(scheme_path)
            for section in scheme.sections():
                values = scheme[section]
                for key, value in values.items():
                    if re.fullmatch(r"\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*", value):
                        self.assertNotIn(
                            parse_rgb(value), {(255, 255, 255), (0, 0, 0)},
                            f"pure white/black in {scheme_path}:{section}/{key}",
                        )
                if (section.startswith("Colors:")
                        and "ForegroundNormal" in values
                        and "BackgroundNormal" in values):
                    ratio = contrast_ratio(parse_rgb(values["ForegroundNormal"]),
                                           parse_rgb(values["BackgroundNormal"]))
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f"{scheme_path}:{section} contrast is only {ratio:.2f}:1",
                    )

        # A named/hex pure-white literal can bypass palette.json. Scan every textual
        # UI2 runtime surface as a second line of defence.
        runtime_roots = (
            SHARE / "plasma/look-and-feel/org.moos.ui2",
            SHARE / "plasma/look-and-feel/org.moos.ui2.light",
            SHARE / "plasma/desktoptheme/MoOSUI2",
            SHARE / "plasma/desktoptheme/MoOSUI2Light",
            SHARE / "aurorae/themes/MoOSUI2",
            SHARE / "aurorae/themes/MoOSUI2Light",
            SHARE / "color-schemes/MoOSUI2Dark.colors",
            SHARE / "color-schemes/MoOSUI2Light.colors",
            SHARE / "konsole/MoOSUI2Dark.colorscheme",
            SHARE / "konsole/MoOSUI2Light.colorscheme",
            DASHBOARD,
        )
        pure_white = re.compile(
            r"(?i)(?<![0-9a-f])#(?:fff|ffffff)(?![0-9a-f])"
            r"|(?:fill|stroke|color)\s*[:=]\s*[\"']?white\b"
            r"|Qt\.rgba\(\s*1(?:\.0)?\s*,\s*1(?:\.0)?\s*,\s*1(?:\.0)?\s*,",
        )
        for root in runtime_roots:
            paths = [root] if root.is_file() else root.rglob("*")
            for path in paths:
                if not path.is_file() or path.suffix.lower() in {
                    ".png", ".jpg", ".jpeg", ".webp",
                }:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                self.assertIsNone(pure_white.search(text),
                                  f"pure-white runtime literal in {path}")

    def test_dark_and_light_own_complete_distinct_svg_suites(self) -> None:
        dark = SHARE / "plasma/desktoptheme/MoOSUI2"
        light = SHARE / "plasma/desktoptheme/MoOSUI2Light"
        dark_svgs = {str(path.relative_to(dark)) for path in dark.rglob("*.svg")}
        light_svgs = {str(path.relative_to(light)) for path in light.rglob("*.svg")}

        self.assertTrue(REQUIRED_DESKTOP_SVGS <= dark_svgs)
        self.assertEqual(dark_svgs, light_svgs,
                         "Light must ship every SVG Dark ships, and vice versa")

        for relative in sorted(dark_svgs):
            dark_svg = dark / relative
            light_svg = light / relative
            with self.subTest(svg=relative):
                self.assertFalse(dark_svg.is_symlink(), f"Dark SVG is a symlink: {dark_svg}")
                self.assertFalse(light_svg.is_symlink(), f"Light SVG is a symlink: {light_svg}")
                self.assertGreater(dark_svg.stat().st_size, 200)
                self.assertGreater(light_svg.stat().st_size, 200)
                ET.parse(dark_svg)
                ET.parse(light_svg)
                self.assertNotEqual(
                    sha256(dark_svg), sha256(light_svg),
                    f"Light SVG inherited Dark bytes instead of its own palette: {relative}",
                )

        for names in VARIANTS.values():
            aurorae = SHARE / "aurorae/themes" / names["aurorae"]
            actual = {path.name for path in aurorae.glob("*.svg")}
            self.assertTrue(REQUIRED_AURORAE_SVGS <= actual)
            for svg in aurorae.glob("*.svg"):
                self.assertFalse(svg.is_symlink(), f"Aurorae SVG is a symlink: {svg}")
                ET.parse(svg)

        for name in REQUIRED_AURORAE_SVGS:
            dark_svg = SHARE / "aurorae/themes/MoOSUI2" / name
            light_svg = SHARE / "aurorae/themes/MoOSUI2Light" / name
            self.assertNotEqual(sha256(dark_svg), sha256(light_svg),
                                f"Light Aurorae inherited Dark bytes: {name}")

    def test_wallpaper_exports_have_expected_dimensions_and_are_distinct(self) -> None:
        expected = {
            "3840x2160.jpg": (3840, 2160),
            "3440x1440.jpg": (3440, 1440),
            "2560x1600.jpg": (2560, 1600),
        }
        packages = {}
        for variant, names in VARIANTS.items():
            wallpaper = SHARE / "wallpapers" / names["wallpaper"]
            packages[variant] = wallpaper
            self.assertEqual(png_info(wallpaper / "contents/screenshot.png")[:2],
                             (1920, 1080))
            for folder in ("images", "images_dark"):
                for filename, dimensions in expected.items():
                    path = wallpaper / "contents" / folder / filename
                    with self.subTest(variant=variant, folder=folder, image=filename):
                        self.assertTrue(path.is_file(), f"missing wallpaper export: {path}")
                        self.assertEqual(jpeg_dimensions(path), dimensions)
                        self.assertGreater(path.stat().st_size, 100_000)
            for filename in expected:
                self.assertEqual(
                    sha256(wallpaper / "contents/images" / filename),
                    sha256(wallpaper / "contents/images_dark" / filename),
                    f"{names['wallpaper']} aliases must carry the same variant artwork",
                )

        for filename in expected:
            self.assertNotEqual(
                sha256(packages["dark"] / "contents/images" / filename),
                sha256(packages["light"] / "contents/images" / filename),
                f"Dark and Light wallpapers must be distinct: {filename}",
            )

        dark_master = ART / "wallpapers/moos-ui2-graphite-master.png"
        light_master = ART / "wallpapers/moos-ui2-tide-master.png"
        for variant, master in (("dark", dark_master), ("light", light_master)):
            with self.subTest(master=variant):
                self.assertTrue(master.is_file())
                width, height, bit_depth, colour_type = png_info(master)
                self.assertGreaterEqual(width, 1600,
                                        f"{variant} wallpaper master is too narrow")
                self.assertGreaterEqual(height, 900,
                                        f"{variant} wallpaper master is too short")
                self.assertAlmostEqual(width / height, 16 / 9, delta=0.01,
                                       msg=f"{variant} wallpaper master is not 16:9")
                self.assertEqual(bit_depth, 8)
                self.assertIn(colour_type, {2, 6},
                              f"{variant} wallpaper master must be lossless RGB/RGBA PNG")
        self.assertNotEqual(sha256(dark_master), sha256(light_master))

    def test_weather_art_is_complete_local_and_owned(self) -> None:
        source = ART / "weather"
        runtime = DASHBOARD / "contents/images/weather"
        source_names = {path.stem for path in source.glob("*.png")}
        runtime_names = {path.stem for path in runtime.glob("*.png")}

        self.assertTrue(WEATHER_KINDS <= source_names,
                        f"weather masters missing: {sorted(WEATHER_KINDS - source_names)}")
        self.assertEqual(runtime_names, WEATHER_KINDS,
                         "runtime weather set must exactly match the nine owned masters")
        self.assertTrue((source / "weather-atlas-alpha.png").is_file())
        self.assertTrue((source / "weather-atlas-chroma.png").is_file())
        self.assertTrue((ART / "previews/weather-icons-preview.png").is_file())

        hashes = set()
        for kind in sorted(WEATHER_KINDS):
            master = source / f"{kind}.png"
            shipped = runtime / f"{kind}.png"
            with self.subTest(weather=kind):
                self.assertEqual(png_info(master), (512, 512, 8, 6))
                self.assertEqual(png_info(shipped), (512, 512, 8, 6))
                self.assertGreater(shipped.stat().st_size, 50_000)
                self.assertEqual(sha256(master), sha256(shipped),
                                 f"shipped {kind} is not the owned MoOS master")
                hashes.add(sha256(shipped))
        self.assertEqual(len(hashes), len(WEATHER_KINDS),
                         "each weather condition must own distinct artwork")
        master_hashes = {
            kind: sha256(source / f"{kind}.png") for kind in WEATHER_KINDS
        }
        runtime_hashes = {
            kind: sha256(runtime / f"{kind}.png") for kind in WEATHER_KINDS
        }
        self.assertEqual(master_hashes, runtime_hashes,
                         "the generated runtime weather set must equal its masters")

    def test_dashboard_is_passive_palette_driven_and_motion_guarded(self) -> None:
        metadata = load_json(DASHBOARD / "metadata.json")
        self.assertEqual(metadata["KPlugin"]["Id"], "org.moos.ui2.wallpaper")
        self.assertEqual(metadata["KPackageStructure"], "Plasma/Wallpaper",
                         "the scene must be a WALLPAPER package — a Plasma/Applet here "
                         "puts the bento back on top of the desktop icons")
        self.assert_files(DASHBOARD / "contents/ui", {
            "main.qml",
            "DashboardBento.qml",
            "GlassCard.qml",
            "ClockCard.qml",
            "RollingDigit.qml",
            "WeatherCard.qml",
            "WeatherScene.qml",
            "SystemCard.qml",
            "MetricRing.qml",
        })

        qml_files = sorted((DASHBOARD / "contents/ui").glob("*.qml"))
        qml_by_path = {path: path.read_text(encoding="utf-8") for path in qml_files}
        combined = "\n".join(qml_by_path.values())
        for banned in BANNED_DASHBOARD_TYPES:
            self.assertNotIn(banned, combined,
                             f"UI2 dashboard must not use {banned}")

        self.assertNotRegex(combined, r"#[0-9A-Fa-f]{3,8}\b",
                            "dashboard colours must come from Kirigami.Theme")
        self.assertGreaterEqual(combined.count("Kirigami.Theme"), 20)
        self.assertIn("https://ipwho.is/", combined)
        self.assertIn("https://api.open-meteo.com/v1/forecast", combined)
        for sensor in (
            "cpu/all/usage",
            "memory/physical/usedPercent",
            "disk/all/usedPercent",
        ):
            self.assertIn(sensor, combined)
        for kind in WEATHER_KINDS:
            self.assertIn(f'"{kind}"', combined)

        main = qml_by_path[DASHBOARD / "contents/ui/DashboardBento.qml"]
        for numeric_weather_value in (
            "current.temperature_2m",
            "current.apparent_temperature",
            "current.weather_code",
            "daily.temperature_2m_max[0]",
            "daily.temperature_2m_min[0]",
        ):
            self.assertIn(
                f'typeof {numeric_weather_value} !== "number"', main,
                f"forecast validation must reject a non-numeric {numeric_weather_value}",
            )
            self.assertIn(
                f"!isFinite({numeric_weather_value})", main,
                f"forecast validation must reject a non-finite {numeric_weather_value}",
            )
        self.assertIn("daily.temperature_2m_max.length < 1", main)
        self.assertIn("daily.temperature_2m_min.length < 1", main)

        system_card = qml_by_path[DASHBOARD / "contents/ui/SystemCard.qml"]
        self.assertRegex(
            system_card,
            r"readonly\s+property\s+bool\s+coreSensorsReady\s*:\s*"
            r"cpuPresent\s*&&\s*memoryPresent",
            "CPU and RAM readiness must gate the dashboard's health verdict",
        )
        self.assertRegex(
            system_card,
            r"healthColor\s*:\s*!coreSensorsReady\s*\n\s*"
            r"\?\s*Kirigami\.Theme\.disabledTextColor",
            "missing core sensors must use a non-healthy neutral colour",
        )
        self.assertRegex(
            system_card,
            r"healthLabel\s*:\s*!coreSensorsReady\s*\n\s*\?\s*\"WAITING\"",
            "missing core sensors must never be labelled HEALTHY",
        )

        clock_card = qml_by_path[DASHBOARD / "contents/ui/ClockCard.qml"]
        # The identity badge names the ACTIVE theme (e.g. "MIDNIGHT GLASS"),
        # driven by themeLabel threaded from main.qml -> DashboardBento -> here,
        # and still falls back to the Light/Dark palette when no label is given.
        self.assertRegex(
            clock_card,
            r"property\s+string\s+themeLabel",
            "ClockCard must accept the active MoOS theme label",
        )
        self.assertIn('"TIDAL GLASS"', clock_card)
        self.assertIn('"GRAPHITE GLASS"', clock_card)
        self.assertRegex(
            clock_card,
            r"text:\s*clockCard\.themeLabel\s*!==\s*\"\"\s*"
            r"\?\s*clockCard\.themeLabel\s*"
            r":\s*\(\s*clockCard\.lightSurface\s*\?\s*\"TIDAL GLASS\"\s*"
            r":\s*\"GRAPHITE GLASS\"\s*\)",
            "the dashboard identity must name the active theme, "
            "falling back to the Light/Dark palette",
        )
        # main.qml must DERIVE that label from the active wallpaper package and
        # thread it down, or every theme would show the same fallback name.
        dashboard_main = qml_by_path[DASHBOARD / "contents/ui/main.qml"]
        self.assertRegex(
            dashboard_main,
            r"readonly\s+property\s+string\s+themeLabel\s*:",
            "main.qml must derive the active theme label",
        )
        self.assertRegex(
            dashboard_main,
            r"themeLabel:\s*root\.themeLabel",
            "the derived theme label must be threaded into the bento",
        )
        bento = qml_by_path[DASHBOARD / "contents/ui/DashboardBento.qml"]
        self.assertRegex(
            bento,
            r"themeLabel:\s*root\.themeLabel",
            "the bento must forward the theme label to the clock card",
        )

        self.assertRegex(main, r"readonly\s+property\s+bool\s+motionEnabled\s*:")
        self.assertIn("Kirigami.Units.longDuration > 0", main,
                      "motion guard must honour Plasma's disabled-animation duration")
        self.assertRegex(main, r"gridUnit\s*\*\s*31\b")
        self.assertRegex(main, r"gridUnit\s*\*\s*12\b")

        animation_type = re.compile(
            r"\b(?:Sequential|Parallel|Number|Pause|Property|Color|Rotation|"
            r"Smoothed|Spring)Animation\b|\bBehavior\s+on\b"
        )
        animated = {path: text for path, text in qml_by_path.items()
                    if animation_type.search(text)}
        self.assertTrue(animated, "dashboard must contain the designed motion system")
        for path, text in animated.items():
            with self.subTest(motion_file=path.name):
                self.assertIn("motionEnabled", text,
                              f"animated QML has no motion guard: {path}")
                if path.name not in ("main.qml", "DashboardBento.qml"):
                    self.assertRegex(
                        text, r"(?:required|readonly)\s+property\s+bool\s+motionEnabled",
                        f"animated component does not declare its motion seam: {path}",
                    )

                for loop in re.finditer(r"loops\s*:\s*Animation\.Infinite", text):
                    guard_window = text[max(0, loop.start() - 220):loop.end()]
                    self.assertRegex(
                        guard_window, r"running\s*:[^\n]*motionEnabled",
                        f"infinite animation is not motion-guarded in {path}",
                    )

                for behavior in re.finditer(r"\bBehavior\s+on\s+\w+\s*\{", text):
                    guard_window = text[behavior.start():behavior.start() + 260]
                    self.assertRegex(
                        guard_window, r"enabled\s*:[^\n]*motionEnabled",
                        f"Behavior is not motion-guarded in {path}",
                    )

                for restart in re.finditer(r"\b\w+\.restart\(\)", text):
                    guard_window = text[max(0, restart.start() - 220):restart.end()]
                    self.assertIn(
                        "motionEnabled", guard_window,
                        f"manual animation restart is not motion-guarded in {path}",
                    )

        # The wallpaper wrapper is the layer contract: WallpaperItem root, the
        # bento embedded, and the Image config key the theme scripts write.
        wrapper = qml_by_path[DASHBOARD / "contents/ui/main.qml"]
        self.assertIn("WallpaperItem", wrapper,
                      "the scene root must be a WallpaperItem — anything else does not "
                      "render below the icons")
        self.assertIn("DashboardBento", wrapper,
                      "the scene wallpaper no longer embeds the dashboard bento")
        self.assertIn("root.configuration.Image", wrapper,
                      "the scene must read the Image config key moos-theme writes per half")
        bento = qml_by_path[DASHBOARD / "contents/ui/DashboardBento.qml"]
        self.assertNotIn("import org.kde.plasma.plasmoid", bento,
                         "DashboardBento must stay plain QtQuick/Kirigami — the build's "
                         "smoke harness loads it directly")


if __name__ == "__main__":
    unittest.main(verbosity=2)
