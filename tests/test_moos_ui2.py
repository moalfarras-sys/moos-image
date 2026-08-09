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
import pathlib
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
        "fallback": "breeze-light",
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


def qml_code(text: str) -> str:
    """Strip QML comments so prose cannot satisfy a relationship gate."""
    without_blocks = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(
        line
        for line in without_blocks.splitlines()
        if not line.lstrip().startswith("//")
    )


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
                # Every Global Theme must name its OWN wallpaper. libkworkspace's
                # DefaultWallpaper::defaultWallpaperPackage() reads kdeglobals [KDE]
                # LookAndFeelPackage, opens that package's contents/defaults and takes
                # [Wallpaper] Image; org.kde.image and the Wallpaper KCM both call it,
                # and packageContents() reads the same key to decide whether System
                # Settings lists a wallpaper among this theme's contents. Without it,
                # picking a MoOS theme gave MoOS colours on the previous wallpaper.
                #
                # This gate USED to assert the opposite, on the belief that a
                # [Wallpaper] here makes LookAndFeelManager force org.kde.image onto
                # every containment. It does not: KLookAndFeelManager::save() never
                # reads this group at all (checked in plasma-workspace 6.7.3 and in
                # the shipped libklookandfeel.so.6.7.3, where the literal is referenced
                # only from packageContents() and remove()), and it rebuilds the desktop
                # layout only for packages that ship contents/layouts/, which no MoOS
                # look does. The scene plugin is safe.
                self.assertIn(f"[Wallpaper]\nImage={names['wallpaper']}", defaults,
                              f"{look_and_feel} does not name its own wallpaper package — "
                              "picking it in System Settings leaves the old wallpaper")
                self.assertTrue((SHARE / "wallpapers" / names["wallpaper"]).is_dir(),
                                f"{look_and_feel} names a wallpaper package that does not exist")

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
                art / "wallpapers/moos-ui-graphite-horizon-master-v2.png",
                art / "wallpapers/moos-ui-tidal-horizon-master-v2.png",
            ):
                master.parent.mkdir(parents=True, exist_ok=True)
                master.write_bytes(b"fixture-png")
            for visual in (
                "plasma/dialog-background.svg.in",
                "plasma/panel-background.svg.in",
            ):
                target = art / visual
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(
                    (DEFAULT_ROOT / "artwork/moos-ui2" / visual).read_bytes()
                )
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
            # shutil.which() honours PATHEXT on Windows, so an extensionless
            # Unix-style fixture is invisible there even though the generator
            # is never supposed to execute it in this test.
            fake_ffmpeg = fake_bin / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
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
                for surface in ("canvas", "surface", "card", "raised"):
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
            SHARE / (
                "plasma/shells/org.kde.plasma.desktop/contents/"
                "lockscreen/MainBlock.qml"
            ),
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

    def test_family_palette_contrast_and_no_pure_white(self) -> None:
        # The 7 accent families (nova, amethyst, midnight, aurora, gaming, dev,
        # study) carry their OWN palettes in artwork/moos-themes/palettes.json.
        # test_palette_contrast_and_no_pure_white only covers the Graphite/Tidal
        # base, so a hand-edit to a family palette that wrecked contrast or slipped
        # in pure white used to pass every gate. This closes that gap. Pure BLACK
        # is allowed (Midnight is a deliberate true-black OLED canvas); pure white
        # never is; and text must stay legible on every surface it lands on.
        family = load_json(ROOT / "artwork/moos-themes/palettes.json")
        required_roles = {
            "canvas", "surface", "card", "raised", "primary", "secondary",
            "luminous", "positive", "warning", "negative", "text", "muted",
            "outline", "shadow", "panel_top", "panel_mid", "panel_bottom",
        }
        themes = [k for k in family if not k.startswith("_")]
        self.assertGreaterEqual(len(themes), 7,
                                "expected at least the 7 accent-family palettes")
        for theme in themes:
            with self.subTest(theme=theme):
                roles = {k: v for k, v in family[theme].items()
                         if not k.startswith("_")}
                self.assertEqual(set(roles), required_roles,
                                 f"{theme} palette is missing/extra colour roles")
                for role, literal in roles.items():
                    self.assertNotEqual(
                        hex_rgb(literal), (255, 255, 255),
                        f"{theme}.{role} must not be pure white")
                for surface in ("canvas", "surface", "card", "raised"):
                    ratio = contrast_ratio(hex_rgb(roles["text"]),
                                           hex_rgb(roles[surface]))
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f"{theme} text/{surface} contrast is only {ratio:.2f}:1")
                for surface in ("canvas", "surface", "card", "raised"):
                    ratio = contrast_ratio(hex_rgb(roles["muted"]),
                                           hex_rgb(roles[surface]))
                    self.assertGreaterEqual(
                        ratio, 4.5,
                        f"{theme} muted/{surface} contrast is only {ratio:.2f}:1")

        # The family generator also derives seven LIGHT siblings which do not
        # live literally in palettes.json.  Gate the generated schemes too:
        # selected ink must read on the accent, and the small secondary text
        # Plasma draws on raised buttons must not disappear into that surface.
        family_schemes = sorted((SHARE / "color-schemes").glob("MoOSUI2*.colors"))
        self.assertGreaterEqual(len(family_schemes), 16,
                                "the complete 8-pair UI2 family is not generated")
        for scheme_path in family_schemes:
            scheme = load_kconfig(scheme_path)
            with self.subTest(generated_scheme=scheme_path.name):
                selection = scheme["Colors:Selection"]
                selected_ink = parse_rgb(selection["ForegroundNormal"])
                selected_fill = parse_rgb(selection["BackgroundNormal"])
                ratio = contrast_ratio(selected_ink, selected_fill)
                self.assertGreaterEqual(
                    ratio, 4.5,
                    f"{scheme_path}: selected ink/accent contrast is only {ratio:.2f}:1",
                )
                self.assertNotEqual(
                    selected_ink, (255, 255, 255),
                    f"{scheme_path}: selected text must be soft ink, not pure white",
                )

                button = scheme["Colors:Button"]
                muted = parse_rgb(button["ForegroundInactive"])
                raised = parse_rgb(button["BackgroundNormal"])
                ratio = contrast_ratio(muted, raised)
                self.assertGreaterEqual(
                    ratio, 4.5,
                    f"{scheme_path}: muted/raised contrast is only {ratio:.2f}:1",
                )

        # A partially generated Look-and-Feel family can leave a working colour
        # scheme behind while the picker shows a blank/broken card.  Keep the
        # exact dark/light package matrix and all four Plasma preview surfaces
        # in lockstep with the palettes that produced them.
        expected_package_ids = {"org.moos.ui2", "org.moos.ui2.light"}
        for theme in themes:
            expected_package_ids.update({
                f"org.moos.ui2.{theme}",
                f"org.moos.ui2.{theme}.light",
            })
        look_and_feel_root = SHARE / "plasma/look-and-feel"
        generated_packages = {
            path.name: path
            for path in look_and_feel_root.glob("org.moos.ui2*")
            if path.is_dir()
        }
        self.assertEqual(
            set(generated_packages), expected_package_ids,
            "the generated UI2 Look-and-Feel matrix is incomplete or stale",
        )
        preview_names = {
            "preview.png", "lockscreen.png", "splash.png",
            "fullscreenpreview.jpg",
        }
        for package_id, package in generated_packages.items():
            with self.subTest(generated_package=package_id):
                previews = package / "contents/previews"
                self.assert_files(previews, preview_names)
                self.assertEqual(
                    {path.name for path in previews.iterdir() if path.is_file()},
                    preview_names,
                    f"{package_id}: generated preview set is incomplete or stale",
                )
                metadata = load_json(package / "metadata.json")
                self.assertEqual(metadata["KPlugin"]["Id"], package_id)

    def test_greeter_palette_follows_every_light_wallpaper_variant(self) -> None:
        source = qml_code(
            (SHARE / "plasma/wallpapers/org.moos.ui2.greeter/contents/ui/main.qml")
            .read_text(encoding="utf-8")
        )
        self.assertIn("/\\/MoOSUI2[^/]*Light\\//", source)
        self.assertIn('root.sceneImage.indexOf("/MoOSUI2Tide/")', source)
        self.assertIn('root.sceneImage.indexOf("/MoOSUI2Daylight/")', source)
        self.assertNotIn('root.sceneImage.indexOf("MoOSUI2Tide") >= 0', source)

    def test_logout_actions_expose_complete_accessibility_state(self) -> None:
        """The out-of-process session greeter must not depend on implicit roles."""
        button_path = (
            SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/"
            "MoOSUI2ActionButton.qml"
        )
        button = qml_code(button_path.read_text(encoding="utf-8"))
        for contract in (
            "Accessible.role: Accessible.Button",
            "Accessible.name: text",
            "Accessible.description: description",
            "Accessible.pressed: down",
            "Accessible.onPressAction: control.animateClick()",
            "focusPolicy: Qt.StrongFocus",
        ):
            self.assertIn(contract, button)
        for direction in ("Up", "Down", "Left", "Right"):
            self.assertIn(f"Keys.on{direction}Pressed: navigate(", button)

    def test_lock_authentication_exposes_explicit_accessibility_state(self) -> None:
        lock_path = (
            SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/"
            "MainBlock.qml"
        )
        lock = qml_code(lock_path.read_text(encoding="utf-8"))
        password_start = lock.index("id: passwordBox")
        password = lock[password_start:lock.index("Binding {", password_start)]
        self.assertIn("Accessible.name:", password)

        unlock_start = lock.index("id: loginButton")
        unlock = lock[unlock_start:lock.index("component FailableLabel", unlock_start)]
        for contract in (
            "Accessible.role: Accessible.Button",
            "Accessible.name:",
            "Accessible.pressed: down",
            "Accessible.onPressAction: loginButton.clicked()",
            "Keys.onEnterPressed: clicked()",
            "Keys.onReturnPressed: clicked()",
        ):
            self.assertIn(contract, unlock)

    def test_login_greeter_actions_are_operable_by_assistive_clients(self) -> None:
        components = ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components"
        action = qml_code((components / "ActionButton.qml").read_text(encoding="utf-8"))
        for contract in (
            "Accessible.role: Accessible.Button",
            "Accessible.name: root.Kirigami.MnemonicData.plainTextLabel",
            "Accessible.pressed: root.down",
            "Accessible.onPressAction: root.animateClick()",
            "Keys.onEnterPressed: clicked()",
            "Keys.onReturnPressed: clicked()",
        ):
            self.assertIn(contract, action)
        self.assertNotIn("Accessible.name: root.text", action)

        user = qml_code((components / "UserDelegate.qml").read_text(encoding="utf-8"))
        for contract in (
            "Accessible.role: Accessible.Button",
            "Accessible.name: name",
            "Accessible.focusable: true",
            "Accessible.focused: activeFocus",
            "Accessible.onPressAction: wrapper.clicked()",
            "Keys.onSpacePressed: wrapper.clicked()",
            "Keys.onEnterPressed: wrapper.clicked()",
            "Keys.onReturnPressed: wrapper.clicked()",
        ):
            self.assertIn(contract, user)
        self.assertNotIn("function accessiblePressAction", user)

    def test_login_greeter_reduced_motion_is_a_true_static_state(self) -> None:
        components = ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components"
        for filename, owner, expected_durations in (
            ("ActionButton.qml", "root", 4),
            ("UserDelegate.qml", "wrapper", 3),
        ):
            with self.subTest(filename=filename):
                source = qml_code((components / filename).read_text(encoding="utf-8"))
                self.assertIn(
                    "readonly property bool motionEnabled: Kirigami.Units.longDuration > 1",
                    source,
                )
                self.assertEqual(source.count("duration:"), expected_durations)
                guarded = re.findall(
                    rf"duration:\s*design\.duration\(\s*"
                    rf"{re.escape(owner)}\.motionEnabled\s*,\s*"
                    r"design\.motion(?:Press|Fast|Geometry|Emphasis|Portal)\s*\)",
                    source,
                )
                self.assertEqual(len(guarded), expected_durations)

    def test_lock_authentication_reduced_motion_is_a_true_static_state(self) -> None:
        lock_root = (
            SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen"
        )
        for filename, owner, expected_durations in (
            ("MainBlock.qml", "sessionManager", 8),
            ("LockScreenUi.qml", "lockScreenUi", 5),
        ):
            with self.subTest(filename=filename):
                source = qml_code((lock_root / filename).read_text(encoding="utf-8"))
                self.assertIn(
                    "readonly property bool motionEnabled: Kirigami.Units.longDuration > 1",
                    source,
                )
                self.assertEqual(source.count("duration:"), expected_durations)
                guarded = re.findall(
                    rf"duration:\s*{re.escape(owner)}\.design\.duration\(\s*"
                    rf"{re.escape(owner)}\.motionEnabled\s*,\s*"
                    rf"{re.escape(owner)}\.design\.motion"
                    r"(?:Press|Fast|Geometry|Emphasis|Portal)\s*\)",
                    source,
                )
                self.assertEqual(len(guarded), expected_durations)
        main_block = qml_code((lock_root / "MainBlock.qml").read_text(encoding="utf-8"))
        repeated = main_block[main_block.index("function onNotificationRepeated"):
                              main_block.index("}", main_block.index("function onNotificationRepeated")) + 1]
        self.assertIn("if (sessionManager.motionEnabled)", repeated)

    def test_lock_wallpaper_migrates_existing_users_and_matches_exactly(self) -> None:
        apply = (ROOT / "system_files/usr/bin/moos-apply-theme").read_text(encoding="utf-8")
        switch = (ROOT / "system_files/usr/bin/moos-theme").read_text(encoding="utf-8")
        self.assertIn(
            "THEME_REV=48", apply,
            "existing pre-v48 users would exit before post-marker shadow quarantine, "
            "the Horizon Bar/theme migration, and the SVG cache purge that is the "
            "only way new Plasma Style art reaches a frozen /usr",
        )
        self.assertIn('[ "$lock_image" = "$wallpaper_package" ] || return 1', switch)
        self.assertIn('moos-theme apply-lnf "$want_lnf"', apply)
        self.assertIn('moos-theme verify-lnf "$lnf_after"', apply)
        self.assertNotIn('case "$lockscreen" in *"$wallpaper_package"*', switch)
        self.assertIn("--file kscreenlockerrc --group Greeter", switch)
        self.assertIn("--key WallpaperPlugin org.kde.image", switch)
        self.assertIn('--key Image "$wallpaper_package"', switch)

    def test_session_controls_use_only_wcag_paired_foregrounds(self) -> None:
        """Security/session glyphs must sit on a scheme-paired flat colour.

        accentB is a generated hue used for decorative depth; KDE has no
        foreground role paired with it.  The old gradients put the Unlock and
        power glyphs over that unpaired endpoint (1.77:1 on Graphite).  Destructive
        actions also used Selection foreground on ForegroundNegative (2.78:1 in
        Daylight).  Hold both the QML relationship and all 16 numeric schemes.
        """
        lock_path = (
            SHARE / "plasma/shells/org.kde.plasma.desktop/contents/"
            "lockscreen/MainBlock.qml"
        )
        lock = qml_code(lock_path.read_text(encoding="utf-8"))
        unlock_start = lock.index("id: loginButton")
        unlock = lock[unlock_start:lock.index("component FailableLabel", unlock_start)]
        self.assertIn("color: sessionManager.accentA", unlock)
        self.assertIn("color: Kirigami.Theme.highlightedTextColor", unlock)
        self.assertIn(
            "scale: loginButton.down ? sessionManager.design.pressScale : 1.0",
            unlock,
            "contrast-safe flat fill must still acknowledge a press",
        )
        self.assertNotIn(
            "gradient: Gradient",
            unlock,
            "Unlock glyph must not cross an unpaired accentB gradient",
        )
        self.assertNotRegex(
            unlock,
            r'color\s*:\s*["\']white["\']|Qt\.rgba\(\s*1\s*,\s*1\s*,\s*1\s*,',
            "Unlock must use the active scheme's selected ink, never literal white",
        )

        logout_root = SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout"
        logout_screen = qml_code(
            (logout_root / "Logout.qml").read_text(encoding="utf-8")
        )
        button = qml_code(
            (logout_root / "MoOSUI2ActionButton.qml").read_text(encoding="utf-8")
        )
        self.assertIn(
            "Kirigami.Theme.colorSet: Kirigami.Theme.Complementary",
            logout_screen,
            "destructive foreground/fill pairing below assumes Complementary",
        )
        self.assertRegex(
            button,
            r"readonly property color filledInk:\s*control\.destructive\s*"
            r"\?\s*Kirigami\.Theme\.backgroundColor\s*"
            r":\s*Kirigami\.Theme\.highlightedTextColor",
        )
        disc_start = button.index("id: disc")
        disc = button[disc_start:button.index("QQC2.Label {", disc_start)]
        self.assertIn("? control.accentA", disc)
        self.assertIn("? control.accentB", disc)
        self.assertIn("? control.filledInk", disc)
        self.assertNotIn(
            "filledGrad",
            disc,
            "the power glyph must sit on flat accentA; accentB is rim-only",
        )

        scheme_paths = sorted(
            (SHARE / "color-schemes").glob("MoOSUI2*.colors")
        )
        self.assertEqual(
            len(scheme_paths),
            16,
            "session contrast must be measured across the complete theme family",
        )
        for scheme_path in scheme_paths:
            scheme = load_kconfig(scheme_path)
            selection = scheme["Colors:Selection"]
            selected_ink = parse_rgb(selection["ForegroundNormal"])
            selected_fill = parse_rgb(selection["BackgroundNormal"])
            selected_ratio = contrast_ratio(selected_ink, selected_fill)

            complementary = scheme["Colors:Complementary"]
            destructive_ink = parse_rgb(complementary["BackgroundNormal"])
            destructive_fill = parse_rgb(complementary["ForegroundNegative"])
            destructive_ratio = contrast_ratio(destructive_ink, destructive_fill)
            with self.subTest(session_scheme=scheme_path.name):
                self.assertGreaterEqual(
                    selected_ratio,
                    4.5,
                    f"{scheme_path}: unlock/on-accent contrast is only "
                    f"{selected_ratio:.2f}:1",
                )
                self.assertGreaterEqual(
                    destructive_ratio,
                    4.5,
                    f"{scheme_path}: destructive power glyph contrast is only "
                    f"{destructive_ratio:.2f}:1",
                )

    def test_power_dock_wraps_and_keyboard_navigation_tracks_the_grid(self) -> None:
        logout_root = SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout"
        logout = qml_code((logout_root / "Logout.qml").read_text(encoding="utf-8"))
        button = qml_code((logout_root / "MoOSUI2ActionButton.qml").read_text(encoding="utf-8"))
        dock = logout[logout.index("id: dock"):logout.index("id: cancelButton")]

        self.assertIn("GridLayout {", logout[:logout.index("id: dock")])
        self.assertIn("actionCount: root.visibleDockActions().length", dock)
        self.assertIn("Math.min(4, widthLimit", dock)
        self.assertIn("Math.ceil(actionCount / 2)", dock)
        self.assertIn("verticalStep * dock.columns", logout)
        self.assertIn("if (button === cancelButton)", logout)
        self.assertIn("cancelButton.forceActiveFocus(Qt.TabFocusReason)", logout)
        self.assertIn("if (Qt.application.layoutDirection === Qt.RightToLeft) { logicalStep *= -1; }", logout)
        self.assertIn("signal navigate(int horizontalStep, int verticalStep)", button)
        for key, vector in (("Up", "0, -1"), ("Down", "0, 1"),
                            ("Left", "-1, 0"), ("Right", "1, 0")):
            self.assertIn(f"Keys.on{key}Pressed: navigate({vector})", button)

        # With room for four tile columns, every possible capability/update
        # shape is either one row or two rows differing by at most one item.
        # The second-generation tiles are wider (8.6 grid units), so the cap
        # dropped from five to four; 6→3+3, 7→4+3, 8→4+4 stay balanced.
        for count in range(1, 9):
            columns = min(4, count if count <= 4 else (count + 1) // 2)
            rows = (count + columns - 1) // columns
            self.assertLessEqual(columns, 4)
            self.assertLessEqual(rows, 2)
            if rows == 2:
                self.assertLessEqual(columns - (count - columns), 1)

    def test_session_splash_reduced_motion_reaches_static_resting_frame(self) -> None:
        """The splash owns one finite reveal and a truly static off state."""
        splash = qml_code((
            SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/Splash.qml"
        ).read_text(encoding="utf-8"))
        static_frame = splash.split("function showStaticFrame()", 1)[1].split(
            "onMotionEnabledChanged:", 1
        )[0]
        for resting_value in (
            "revealAnimation.stop()",
            "content.opacity = 1",
            "contentShift.y = 0",
        ):
            self.assertIn(
                resting_value,
                static_frame,
                f"reduced-motion frame is missing {resting_value}",
            )

        stage_handler = splash.split("onStageChanged:", 1)[1].split("Rectangle {", 1)[0]
        self.assertRegex(
            stage_handler,
            re.compile(
                r"if\s*\(stage\s*===\s*2\)\s*\{.*?"
                r"if\s*\(root\.motionEnabled\)\s*\{\s*"
                r"revealAnimation\.restart\(\);\s*\}\s*else\s*\{\s*"
                r"root\.showStaticFrame\(\);",
                re.DOTALL,
            ),
            "stage 2 must start the sole reveal only behind motionEnabled",
        )
        self.assertRegex(
            stage_handler,
            re.compile(
                r"stage\s*>=\s*5\)\s*\{\s*"
                r"revealAnimation\.stop\(\);",
                re.DOTALL,
            ),
            "stage 5 must stop the reveal and hand off without another animation",
        )
        self.assertEqual(
            splash.count("loops: Animation.Infinite"),
            0,
            "a boot doorway must settle completely; progress is finite stage interpolation",
        )
        self.assertEqual(splash.count("id: revealAnimation"), 1)
        self.assertNotIn("progressMotion", splash)
        self.assertRegex(
            splash,
            r"Behavior on width\s*\{\s*NumberAnimation\s*\{\s*"
            r"duration:\s*root\.design\.duration\(\s*root\.motionEnabled\s*,\s*"
            r"root\.design\.motionEmphasis\s*\)",
            "stage progress must use one short reduced-motion-aware interpolation",
        )
        self.assertIn("opacity: root.stage >= 5 ? 0 : 1", splash)
        for retired_motion in (
            "ringReveal", "shineSweep", "bloomFlash", "particleBurst",
            "typewriterTimer", "logoBreathe", "outroAnimation",
        ):
            self.assertNotIn(
                retired_motion,
                splash,
                f"the over-animated splash primitive {retired_motion} returned",
            )
        self.assertNotIn("TidalHorizon", splash)

        family = sorted(
            path for path in
            (SHARE / "plasma/look-and-feel").glob("org.moos.ui2*")
            if path.is_dir()
        )
        splash_bytes = {
            (path / "contents/splash/Splash.qml").read_bytes()
            for path in family
        }
        logout_bytes = {
            (path / "contents/logout/Logout.qml").read_bytes()
            for path in family
        }
        logout_button_bytes = {
            (path / "contents/logout/MoOSUI2ActionButton.qml").read_bytes()
            for path in family
        }
        self.assertEqual(len(family), 16)
        self.assertEqual(
            len(splash_bytes), 1,
            "all 16 palettes must use the same reviewed splash composition",
        )
        self.assertEqual(
            len(logout_bytes), 1,
            "all 16 palettes must use the same reviewed session-language policy",
        )
        self.assertEqual(
            len(logout_button_bytes), 1,
            "all 16 palettes must use one reviewed session-action geometry",
        )

    def test_shell_rtl_uses_inherited_logical_edges_once(self) -> None:
        """Plasma mirrors applet trees; manual RTL mirroring reverses them twice."""
        launcher = qml_code((
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
        ).read_text(encoding="utf-8"))
        self.assertNotRegex(
            launcher,
            r"anchors\.(?:left|right)\s*:\s*view\.rtl\s*\?",
            "launcher edges must be logical anchors; plasmashell mirrors them",
        )
        nav = launcher.split("component NavButton:", 1)[1].split(
            "component AppTile:", 1
        )[0]
        self.assertIn(
            "anchors.left: parent.left",
            nav,
            "the active rail belongs on logical start",
        )
        app_tile = launcher.split("component AppTile:", 1)[1].split(
            "component RecentTile:", 1
        )[0]
        self.assertIn(
            "anchors.right: parent.right",
            app_tile,
            "the pin affordance belongs on logical trailing",
        )

        clock = qml_code((
            SHARE / "plasma/plasmoids/org.moos.nova.clock/contents/ui/main.qml"
        ).read_text(encoding="utf-8"))
        self.assertNotRegex(
            clock,
            r"layoutDirection\s*:\s*root\.rtl\s*\?",
            "clock rows inherit plasmashell RTL; setting RTL again double-mirrors",
        )

    def test_launcher_uses_one_readable_low_density_shell_language(self) -> None:
        """The launcher must not regress to a dense, microtyped KDE grid."""
        launcher = qml_code((
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
        ).read_text(encoding="utf-8"))
        dock = qml_code((
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/main.qml"
        ).read_text(encoding="utf-8"))

        design = load_json(ROOT / "artwork/moos-design/tokens.json")
        self.assertEqual(
            [design["spacing"][name] for name in
             ("space1", "space2", "space3", "space4", "space5")],
            [4, 8, 12, 16, 24],
        )
        self.assertEqual(
            [design["radius"][name] for name in
             ("radiusSmall", "radiusControl", "radiusCard", "radiusPanel")],
            [8, 12, 16, 24],
        )
        for token, source in (
            ("space1", "design.space1"), ("space2", "design.space2"),
            ("space3", "design.space3"), ("space4", "design.space4"),
            ("space5", "design.space5"), ("space6", "design.space5"),
            ("radiusS", "design.radiusSmall"),
            ("radiusM", "design.radiusControl"),
            ("radiusL", "design.radiusCard"),
            ("radiusXL", "design.radiusPanel"),
            ("targetSize", "design.targetCompact"),
            ("typeCaption", "design.typeCaption"),
            ("typeSecondary", "design.typeSecondary"),
            ("typeBody", "design.typeBody"),
            ("typeEmphasis", "design.typeLabel"),
            ("typeSubheading", "design.typeTitle"),
            ("typeTitle", "design.typeTitle"),
        ):
            self.assertIn(
                f"readonly property int {token}: {source}",
                launcher,
                f"launcher bypasses the global MoOS {token} token",
            )
        self.assertIn(
            "readonly property string uiFontFamily: Qt.application.font.family",
            launcher,
        )
        self.assertNotRegex(
            launcher,
            r'font\.family\s*:\s*"',
            "the launcher must follow the session font instead of pinning a family",
        )
        self.assertNotIn("Press Meta to open", launcher)
        self.assertNotIn("يفتح بزر Meta", launcher)
        self.assertIn("anchors.margins: view.space5", launcher)
        self.assertEqual(
            launcher.count("cellWidth: Math.max(1, Math.floor(width / 4))"),
            2,
            "Pinned and All Apps must share the calm four-column rhythm",
        )
        self.assertNotRegex(
            launcher,
            r"cellWidth:.*width\s*/\s*(?:[5-9]|\d{2,})",
            "the app grid must never densify past four columns",
        )
        self.assertGreaterEqual(
            launcher.count("view.targetSize"),
            24,
            "custom launcher affordances must retain 40px pointer targets",
        )
        pixel_sizes = re.findall(r"font\.pixelSize\s*:\s*([^\n]+)", launcher)
        self.assertTrue(pixel_sizes)
        self.assertTrue(
            all("type" in expression for expression in pixel_sizes),
            f"launcher bypasses its type scale: {pixel_sizes}",
        )

        self.assertIn(
            "readonly property string uiFontFamily: Qt.application.font.family",
            dock,
        )
        self.assertNotRegex(dock, r'font\.family\s*:\s*"')
        self.assertIn(
            "font.pixelSize: Math.max(11, Math.round(compact.height * 0.20))",
            dock,
            "the dock launcher caption must never shrink below 11px",
        )

    def test_tidal_command_canvas_is_a_product_surface_not_a_menu(self) -> None:
        """Hold the premium shell composition and its zero-idle contract."""
        launcher_raw = (
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml"
        ).read_text(encoding="utf-8")
        launcher = qml_code(launcher_raw)
        dock = qml_code((
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/main.qml"
        ).read_text(encoding="utf-8"))
        hero = qml_code((
            SHARE / "plasma/plasmoids/org.moos.heroclock/contents/ui/main.qml"
        ).read_text(encoding="utf-8"))

        self.assertIn("implicitWidth: design.dialogWidth", launcher)
        self.assertIn("implicitHeight: design.dialogHeight", launcher)
        self.assertIn("LOCAL · PRIVATE", launcher)
        self.assertNotIn("import QtQuick.Shapes", launcher)
        for unfinished_wireframe in ("ShapePath {", "PathQuad {", "PathLine {"):
            self.assertNotIn(
                unfinished_wireframe,
                launcher,
                "the launcher must not restore clipped wireframe corners",
            )
        self.assertRegex(
            launcher,
            r"Rectangle\s*\{\s*anchors\.fill:\s*parent\s*"
            r"radius:\s*view\.radiusXL",
            "the launcher must own one continuous rounded material silhouette",
        )
        self.assertIn("border.width: design.borderHairline", launcher)
        command_field = launcher_raw.split(
            "// ── The command field", 1
        )[1].split("RowLayout {", 1)[0]
        self.assertNotIn(
            "Kirigami.Theme.highlightColor",
            command_field,
            "the search field must not restore a full neon focus outline",
        )
        self.assertNotIn(
            "Row {",
            command_field,
            "the search field must not restore detached underline segments",
        )
        self.assertIn("component CommandCard:", launcher)
        self.assertEqual(
            launcher.count("CommandCard {"), 3,
            "the Command Canvas must keep exactly three hero destinations",
        )
        # THEME_REV 43: hero cards must carry at REST (docs/MOOS_DESIGN_PLAN.md §0).
        # Resting textColour 0.11 is the measured AppTile contract; 0.025/0.105
        # was the invisible band that made these cards look flat.
        command_card = launcher.split("component CommandCard:", 1)[1].split(
            "component SettingCard:", 1
        )[0]
        self.assertIn("Qt.alpha(Kirigami.Theme.textColor, 0.11)", command_card)
        self.assertNotIn("0.025", command_card)
        self.assertNotIn("0.105", command_card)
        self.assertIn("Qt.alpha(Kirigami.Theme.highlightColor, 0.24)", command_card)
        setting_card = launcher.split("component SettingCard:", 1)[1]
        self.assertIn("Qt.alpha(Kirigami.Theme.textColor, 0.11)", setting_card)
        self.assertNotIn("0.045", setting_card)
        for destination in (
            "org.moos.moai.desktop",
            "org.moos.store.desktop",
            "org.moos.themepicker.desktop",
            "systemsettings.desktop",
        ):
            self.assertIn(destination, launcher + dock)
        self.assertIn('text: root.rtl ? "مساحة الأوامر" : "COMMAND"', dock)
        self.assertIn("readonly property int motionMedium: design.duration(", launcher)
        self.assertIn("design.motionGeometry", launcher)
        self.assertIn(
            "Math.max(0, Math.min(tile.index, 11)) * 24",
            launcher,
            "DelegateModel index=-1 teardown must never create a negative "
            "PauseAnimation duration",
        )
        self.assertNotIn("Math.min(tile.index, 11) * 24 : 0", launcher)
        self.assertIn("duration: root.motionPortal", dock)
        self.assertIn("duration: root.motionEmphasis", dock)
        self.assertNotIn("root.rtl ? 720 : -720", dock)
        self.assertNotIn("duration: 1000", dock)
        quiet_edge = launcher_raw.split(
            "// ── Quiet session edge:", 1
        )[1].split("// ── Reusable pieces", 1)[0]
        self.assertNotIn("org.moos.moai.desktop", quiet_edge)
        self.assertNotIn("org.moos.store.desktop", quiet_edge)
        self.assertNotIn("systemsettings.desktop", quiet_edge)
        self.assertIn("org.moos.themepicker.desktop", quiet_edge)

        # The always-visible hero clock used to wake at 1 Hz while five ambient
        # loops repainted plasmashell forever. Tidal Horizon wakes on the minute
        # and moves only when the displayed value changes.
        self.assertIn("interval: 60000 -", hero)
        self.assertNotIn("Animation.Infinite", hero)
        self.assertNotIn('Qt.formatTime(root.now, "ss")', hero)
        self.assertIn("onTextChanged: minutePulse.restart()", hero)
        self.assertIn("root.latinNumerals(root.displayLocale.toString", hero)
        self.assertIn("YOUR DAILY HORIZON", hero)

    def test_logout_draws_only_the_active_session_language(self) -> None:
        logout = qml_code((
            SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml"
        ).read_text(encoding="utf-8"))
        formatter = logout.split(
            "function bilingual(arabic, english)", 1
        )[1].split("function shortLabel", 1)[0]
        self.assertIn('return "\\u2067" + arabic + "\\u2069"', formatter)
        self.assertIn('return "\\u2066" + english + "\\u2069"', formatter)
        self.assertNotIn(' + "  ·  " + ', formatter)
        self.assertNotRegex(
            formatter,
            r"\bar\s*\+.*\ben\b|\ben\s*\+.*\bar\b",
            "Logout must not concatenate two visible languages",
        )

    def test_glass_surfaces_keep_rounded_blur_masks_and_translucency(self) -> None:
        dialog_master = ART / "plasma/dialog-background.svg.in"
        panel_master = ART / "plasma/panel-background.svg.in"
        self.assertTrue(dialog_master.is_file(),
                        "the popup glass must be generated from a reviewed SVG master")

        dialog_template = dialog_master.read_text(encoding="utf-8")
        panel_template = panel_master.read_text(encoding="utf-8")
        required_masks = {
            "mask-topleft", "mask-top", "mask-topright", "mask-left",
            "mask-center", "mask-right", "mask-bottomleft", "mask-bottom",
            "mask-bottomright",
        }
        self.assertTrue(required_masks <= set(re.findall(
            r'\bid="([^"]+)"', dialog_template
        )), "the popup master must ship a complete rounded blur mask")
        painted_frame = dialog_template.split("</defs>", 1)[1].split(
            "<!-- Rounded KWin blur mask", 1
        )[0]
        self.assertNotIn(
            "@PRIMARY@", painted_frame,
            "popup rims must not restore the split accent band",
        )
        self.assertNotIn(
            "@LUMINOUS@", painted_frame,
            "popup rims must remain one neutral continuous edge",
        )

        # Panel glass opacity is now tokenised in the master (@GLASS_P*@) so Dark
        # and Light are ONE source with two per-half profiles. Assert the master
        # drives it through tokens, then read the numeric opacities from the
        # GENERATED panels and hold the 0.93 blur ceiling for EVERY variant.
        self.assertIn("@GLASS_P0@", panel_template,
                      "the panel master must drive glass opacity through tokens")
        for names in VARIANTS.values():
            panel_path = (SHARE / "plasma/desktoptheme"
                          / names["desktop_theme"] / "widgets/panel-background.svg")
            panel_opacities = [
                float(value) for value in re.findall(
                    r'stop-opacity="([0-9.]+)"',
                    panel_path.read_text(encoding="utf-8"))
            ]
            with self.subTest(panel=panel_path):
                self.assertTrue(panel_opacities)
                self.assertLessEqual(
                    max(panel_opacities), 0.93,
                    "the dock glass becomes effectively opaque and hides KWin blur",
                )

        for names in VARIANTS.values():
            dialog_path = (SHARE / "plasma/desktoptheme"
                           / names["desktop_theme"] / "dialogs/background.svg")
            dialog = dialog_path.read_text(encoding="utf-8")
            ids = set(re.findall(r'\bid="([^"]+)"', dialog))
            with self.subTest(dialog=dialog_path):
                self.assertTrue(required_masks <= ids,
                                "the generated popup lost its rounded blur mask")
                body_opacities = [
                    float(value) for value in re.findall(
                        r'(?:fill|stop)-opacity="([0-9.]+)"', dialog
                    )
                ]
                self.assertTrue(body_opacities)
                self.assertLessEqual(
                    max(body_opacities), 0.93,
                    "popup glass is too opaque for the light KWin frost to show",
                )

        migration = (ROOT / "system_files/usr/bin/moos-ui-migrate").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "MOOS_THEME_REV=11", migration,
            "changed FrameSvgs need a new migration revision for existing users",
        )
        for stale_cache in (
            "ksvg-elements", "plasma_theme_", "plasma-svgelements",
        ):
            self.assertIn(
                stale_cache, migration,
                f"UI migration does not clear the {stale_cache} SVG cache",
            )

    def test_dock_corner_bands_are_annuli_with_no_stray_run(self) -> None:
        """A rounded corner band is an annulus — outer arc, radial step, inner arc.

        The shipped dock grew a stray turquoise line falling out of its top-left
        corner, on every one of the sixteen themes at once. The cause was a
        corner accent written `M0 18A18 18 0 0 1 18 0V18H17V2A16 16 0 0 0 1 18Z`:
        `V18` ran the pen the full height of the corner tile before doubling
        back, enclosing a 1x16 rectangle of accent that is not part of any
        radius, and its inner arc could not solve about the corner's own centre.

        Two things are asserted, because either alone would have passed while the
        dock was visibly wrong:
          * no corner path takes more than ONE straight step between its arcs;
          * every inner arc is exactly `radius - band` from the corner centre, so
            the band cannot silently drift off-centre the way that one did.
        """
        corner_centre = {"topleft": (18, 18), "topright": (42, 18),
                         "bottomleft": (18, 42), "bottomright": (42, 42)}
        # Every SHIPPED theme, not just the base pair: the family members are
        # recoloured copies of this geometry, so the stray line reached all
        # sixteen at once and a two-theme check would have missed fourteen.
        panels = sorted((SHARE / "plasma/desktoptheme")
                        .glob("*/widgets/panel-background.svg"))
        self.assertGreaterEqual(len(panels), 16, "the theme family shrank")
        checked = 0
        for panel in panels:
            svg = ET.fromstring(panel.read_text(encoding="utf-8"))
            for group in svg.iter():
                name = group.attrib.get("id", "")
                if name not in corner_centre:
                    continue
                cx, cy = corner_centre[name]
                for path in group.iter("{http://www.w3.org/2000/svg}path"):
                    d = path.attrib["d"]
                    with self.subTest(theme=panel.parents[1].name, corner=name, d=d):
                        steps = re.findall(r"[VH]\s*(-?[\d.]+)", d)
                        self.assertLessEqual(
                            len(steps), 1,
                            "a corner band stepped more than once between its "
                            "arcs — that encloses a straight sliver, which is "
                            "exactly the stray line users saw in the dock",
                        )
                        for rx, _ry, ex, ey in re.findall(
                            r"A\s*([\d.]+)\s+([\d.]+)\s+\d+\s+\d+\s+\d+\s+"
                            r"(-?[\d.]+)\s+(-?[\d.]+)", d
                        ):
                            radius = math.hypot(float(ex) - cx, float(ey) - cy)
                            self.assertAlmostEqual(
                                radius, float(rx), places=6,
                                msg="an arc endpoint is not its own radius from "
                                    "the corner centre, so SVG re-solves the arc "
                                    "about some other point and the band skews",
                            )
                        checked += 1
        self.assertGreaterEqual(checked, 4 * len(panels),
                                "every corner of every theme must be inspected")

    def test_dock_tiles_say_which_apps_are_open(self) -> None:
        """`normal` and `minimized` must carry a visible running indicator.

        Probed on the running session: Plasma hides the task frame entirely for a
        pinned app that is not running, draws `normal` for one that is running
        and on screen, `minimized` for one that is running but put away, and
        `focus` for the active window. `normal` shipped as fill="none", so an
        open, visible, unfocused app was indistinguishable from a closed one —
        the dock could not answer "what is running?" at all.

        `hover` must NOT carry the indicator: Plasma draws that prefix on pinned
        launchers too, so an accent bar there would claim a closed app is open
        for as long as the pointer rests on it.
        """
        tasks_files = sorted((SHARE / "plasma/desktoptheme")
                             .glob("*/widgets/tasks.svg"))
        self.assertGreaterEqual(len(tasks_files), 16, "the theme family shrank")
        for tasks in tasks_files:
            theme = tasks.parents[1].name
            text = tasks.read_text(encoding="utf-8")
            svg = ET.fromstring(text)
            # Each theme recolours the accent, so read this file's own highlight
            # rather than hunting for the base turquoise in fifteen other hues.
            accent = re.search(
                r'\.ColorScheme-Highlight\s*\{\s*color:\s*(#[0-9A-Fa-f]{6})', text
            ).group(1)
            bottoms = {
                element.attrib["id"]: element
                for element in svg.iter()
                if element.attrib.get("id", "").endswith("-bottom")
            }
            for state, wants_bar in (("normal", True), ("minimized", True),
                                     ("focus", True), ("hover", False)):
                with self.subTest(theme=theme, state=state):
                    group = bottoms.get(f"{state}-bottom")
                    self.assertIsNotNone(group, f"{state}-bottom is missing")
                    accented = [
                        child for child in group
                        if child.attrib.get("fill", "").startswith("url(")
                        or child.attrib.get("fill") == accent
                    ]
                    if wants_bar:
                        self.assertTrue(
                            accented,
                            f"{state} has no accent indicator: the dock cannot "
                            f"say that this app is open",
                        )
                    else:
                        self.assertFalse(
                            accented,
                            "hover must not claim an app is running — Plasma "
                            "draws it on pinned launchers as well",
                        )

    def test_every_moos_widget_can_be_found_and_added(self) -> None:
        """A widget nobody can find is a widget that does not exist.

        The owner's report was "I don't know where to manage the widgets,
        change them, or add others". The first cause was a locked desktop (rev
        40). The second is here: org.moos.nova.clock shipped with NO Category
        at all — the only applet on the whole system without one — so it fell
        outside every filter in Plasma's widget browser, and with no
        Description[ar] it also described itself in English to an Arabic
        session.

        Every field below is one the widget EXPLORER renders. Missing any of
        them does not fail a build or log a warning; it just makes a MoOS
        widget harder to find than a stock KDE one, in MoOS's own browser.
        """
        import json

        plasmoids = sorted((SHARE / "plasma/plasmoids").glob("org.moos.*"))
        self.assertGreaterEqual(len(plasmoids), 4, "the MoOS widget set shrank")

        for package in plasmoids:
            meta = json.loads((package / "metadata.json").read_text(encoding="utf-8"))
            plugin = meta["KPlugin"]
            with self.subTest(widget=plugin.get("Id", package.name)):
                for field in ("Id", "Name", "Name[ar]", "Description",
                              "Description[ar]", "Icon", "Category"):
                    self.assertTrue(
                        plugin.get(field),
                        f"{field} is what the widget browser shows; without it "
                        f"this widget is harder to find than a stock KDE one")

                # Only a MoOS-OWNED icon can be checked here. The icon is a
                # theme NAME, and a stock freedesktop/Breeze name like
                # "preferences-system-time" resolves from the icon themes
                # Plasma installs — which a CI runner does not have. The first
                # version of this check globbed /usr/share/icons unconditionally
                # and so passed on a desktop and failed the build on the runner:
                # a gate that depends on its environment tests the environment,
                # not the repository.
                #
                # It may also legitimately be a png in hicolor rather than a
                # scalable svg, so every extension is checked or the gate
                # reports defects that are not there.
                icon = plugin["Icon"]
                if icon.startswith("moos"):
                    found = any(
                        any((SHARE / "icons").glob(f"**/{icon}.{ext}"))
                        for ext in ("svg", "png", "svgz"))
                    self.assertTrue(
                        found,
                        f"Icon '{icon}' is MoOS-owned but this repository ships "
                        f"nothing by that name, so the widget browser draws a "
                        f"blank tile for it")

    def test_open_applet_slot_is_never_a_bordered_box(self) -> None:
        """`widgets/tabbar.svg` must not draw a framed rectangle on the dock.

        Plasma's shell (`CompactApplet.qml`) paints `<edge>-active-tab` behind a
        PANEL APPLET for as long as its popup is open, choosing the prefix from
        the panel edge — a bottom dock asks for `south-active-tab`. The same
        four prefixes are the active tab of a PlasmaComponents TabBar, so there
        is exactly one piece of art for both roles.

        It shipped as a near-opaque slab (0.84) ringed by a 0.88 accent rim, so
        opening the MoOS launcher wrapped the button in a hard bordered
        rectangle standing on the dock glass. Hold the replacement: a rim that
        cannot be seen, a tint that stays glass, and a corner radius large
        enough that the frame reads as a capsule at dock height.
        """
        # UI1's metadata-less `desktoptheme/Nova` is deliberately absent. Git
        # history and OSTree provide rollback; dead runtime art must not become
        # a second visual source beside the generated MoOSUI2 family.
        self.assertFalse((SHARE / "plasma/desktoptheme/Nova").exists())
        tabbars = sorted((SHARE / "plasma/desktoptheme").glob("MoOSUI2*/widgets/tabbar.svg"))
        self.assertGreaterEqual(len(tabbars), 16, "the theme family shrank")
        for tabbar in tabbars:
            theme = tabbar.parents[1].name
            svg = ET.fromstring(tabbar.read_text(encoding="utf-8"))
            painted = 0
            positions = re.compile(
                r"^(north|east|south|west)-active-tab-(topleft|top|topright|"
                r"left|center|right|bottomleft|bottom|bottomright)$")
            for element in svg.iter():
                identifier = element.attrib.get("id", "")
                if not positions.match(identifier):
                    continue  # margin hints carry no paint
                # _frame() lays the tile down first and the border strip — the
                # 1 px sliver, or the inset arc in a corner — second.
                cells = list(element) if len(element) else [element]
                for index, cell in enumerate(cells):
                    opacity = float(cell.attrib.get("fill-opacity", "1"))
                    with self.subTest(theme=theme, id=identifier, cell=index):
                        if index:
                            self.assertLessEqual(
                                opacity, 0.02,
                                "the open-applet slot has grown a border again",
                            )
                        else:
                            self.assertLessEqual(
                                opacity, 0.22,
                                "the open-applet slot is a slab, not glass",
                            )
                    painted += index == 0 and opacity > 0
            self.assertTrue(painted, f"{theme}/tabbar.svg paints nothing at all")

            radii = {
                float(match)
                for match in re.findall(r"A(\d+(?:\.\d+)?) ", tabbar.read_text(
                    encoding="utf-8"))
            }
            self.assertTrue(
                radii and min(radii) >= 18,
                f"{theme}/tabbar.svg corners are too square for a dock slot",
            )

    def test_native_controls_hint_an_edge_instead_of_drawing_a_box(self) -> None:
        """Hold the MoOS rim scale across every generated interaction surface.

        An interaction state is told by its fill; the rim is a hint of an edge.
        The family shipped accent rims up to 0.94 (the pager's active desktop)
        and 0.88 (the open-applet slot), which stop reading as glass and start
        reading as a rectangle drawn on top of the surface. Keyboard focus is
        the one exception and keeps its own, higher ceiling — it has to be
        unmistakable, and it is the only rim a keyboard user can navigate by.

        Floating glass (tooltip, popup background, dock) is NOT covered here:
        its rim is the only thing separating the surface from live wallpaper.
        """
        interaction = ("button.svg", "lineedit.svg", "listitem.svg",
                       "menubaritem.svg", "pager.svg", "tabbar.svg",
                       "viewitem.svg")
        themes = sorted((SHARE / "plasma/desktoptheme").glob("MoOSUI2*"))
        self.assertGreaterEqual(len(themes), 16, "the theme family shrank")
        for theme in themes:
            for filename in interaction:
                svg = ET.fromstring(
                    (theme / "widgets" / filename).read_text(encoding="utf-8"))
                cell = re.compile(
                    r"^(.+)-(topleft|top|topright|left|center|"
                    r"right|bottomleft|bottom|bottomright)$")
                for element in svg.iter():
                    identifier = element.attrib.get("id", "")
                    # Only a frame cell carries a rim: a <g> whose second child
                    # is the edge _frame() lays over the tile. Margin hints, the
                    # button's soft drop shadow and the gradients that build it
                    # paint no edge at all.
                    if not element.tag.endswith("g") or len(element) < 2:
                        continue
                    if not cell.match(identifier):
                        continue
                    ceiling = 0.60 if "focus" in identifier else 0.42
                    for rim in list(element)[1:]:
                        with self.subTest(theme=theme.name, id=identifier):
                            self.assertLessEqual(
                                float(rim.attrib.get("fill-opacity", "1")),
                                ceiling,
                                f"{filename} draws a box instead of hinting "
                                f"an edge",
                            )

    def test_dock_task_states_never_paint_a_tile_box(self) -> None:
        """No task state may fill a flat slab behind the icon.

        Every state used to paint the TEXT colour at ~0.10 across all nine
        cells plus a 1 px accent hairline along its top edge. On a light family
        member the text colour is near-black, so the active app sat inside a
        grey rectangle with a lit edge. Running state is carried by the bottom
        indicator (and, for focus/attention, by light rising from it), which
        fades out before it reaches an edge and so has no outline to read as a
        border. `hover` is the one state that may still fill, because it is the
        only feedback a pointer gets — and it must tint, never darken.
        """
        tasks_files = sorted((SHARE / "plasma/desktoptheme")
                             .glob("MoOSUI2*/widgets/tasks.svg"))
        self.assertGreaterEqual(len(tasks_files), 16, "the theme family shrank")
        for tasks in tasks_files:
            theme = tasks.parents[1].name
            text = tasks.read_text(encoding="utf-8")
            ink = re.search(
                r'\.ColorScheme-Text\s*\{\s*color:\s*(#[0-9A-Fa-f]{6})', text
            ).group(1)
            svg = ET.fromstring(text)
            cell = re.compile(
                r"^(normal|hover|focus|minimized|attention)-(topleft|top|"
                r"topright|left|center|right|bottomleft|bottom|bottomright)$")
            for element in svg.iter():
                match = cell.match(element.attrib.get("id", ""))
                if match is None:
                    continue
                identifier, state = match.group(0), match.group(1)
                # The indicator bar (rounded, `rx`) and the light it throws
                # (a gradient `url(...)` fill) are the running state itself.
                # Everything else in the nine cells is tile surface, and tile
                # surface is what drew the box.
                for child in (list(element) or [element]):
                    if (child.attrib.get("fill", "").startswith("url(")
                            or "rx" in child.attrib):
                        continue
                    opacity = float(child.attrib.get("fill-opacity", "1"))
                    with self.subTest(theme=theme, id=identifier):
                        if state == "hover":
                            self.assertLessEqual(
                                opacity, 0.12,
                                "the hover tile is a slab again",
                            )
                            self.assertNotEqual(
                                child.attrib.get("fill", "").upper(), ink.upper(),
                                "hover must tint with the accent, not darken "
                                "with the text colour — that is the grey box",
                            )
                        else:
                            self.assertEqual(
                                opacity, 0.0,
                                f"{state} paints a tile box behind the icon",
                            )

    def test_every_theme_keeps_one_safe_kwin_frost_profile(self) -> None:
        """Applying a family member must not silently weaken or overdrive blur."""
        shipped_kwin = load_kconfig(ROOT / "system_files/etc/xdg/kwinrc")
        expected_strength = shipped_kwin["Effect-blur"]["BlurStrength"]
        expected_noise = shipped_kwin["Effect-blur"]["NoiseStrength"]
        self.assertEqual(
            expected_strength, "15",
            "KWin's supported blur range tops out at 15; the shipped profile drifted",
        )
        self.assertEqual(expected_noise, "3")

        defaults_files = sorted(
            (SHARE / "plasma/look-and-feel").glob("org.moos.ui2*/contents/defaults")
        )
        self.assertEqual(
            len(defaults_files), 16,
            "the complete eight-pair MoOS UI family must share one frost profile",
        )
        for defaults_path in defaults_files:
            defaults = load_kconfig(defaults_path)
            with self.subTest(look_and_feel=defaults_path.parent.parent.name):
                self.assertEqual(
                    defaults["kwinrc][Effect-blur"]["BlurStrength"],
                    expected_strength,
                    "applying this theme weakens or overdrives the shared KWin frost",
                )
                self.assertEqual(
                    defaults["kwinrc][Effect-blur"]["NoiseStrength"],
                    expected_noise,
                    "applying this theme changes the shared frost grain",
                )

    def test_family_wallpaper_exports_crop_without_distortion(self) -> None:
        """Ultrawide and 16:10 exports must crop the master, never stretch it."""
        source_path = ROOT / "artwork/generate_moos_themes.py"
        source = source_path.read_text(encoding="utf-8")
        wallpaper_builder = source.split("def build_wallpaper(", 1)[1].split(
            "# ---------------------------------------------------------------- driver", 1
        )[0]
        self.assertIn("ImageOps.fit(", source)
        self.assertIn("Image.Resampling.LANCZOS", source)
        self.assertNotIn(
            ".resize(",
            wallpaper_builder,
            "wallpaper packages/previews must all use crop-to-fill",
        )

        # A square painted into a 4:3 synthetic master must still be square
        # after a 16:9 export. A direct resize would turn it into a 4:3 box.
        from PIL import Image, ImageDraw

        module_spec = __import__("importlib.util").util.spec_from_file_location(
            "moos_family_wallpaper_test", source_path
        )
        self.assertIsNotNone(module_spec)
        self.assertIsNotNone(module_spec.loader)
        family_generator = __import__("importlib.util").util.module_from_spec(module_spec)
        module_spec.loader.exec_module(family_generator)

        master = Image.new("RGB", (400, 300), "black")
        ImageDraw.Draw(master).rectangle((150, 100, 249, 199), fill="red")
        fitted = family_generator.crop_to_fill(master, (160, 90))
        self.assertEqual(fitted.size, (160, 90))
        red_pixels = [
            (x, y)
            for y in range(fitted.height)
            for x in range(fitted.width)
            if fitted.getpixel((x, y))[0] > 200
            and fitted.getpixel((x, y))[1] < 50
            and fitted.getpixel((x, y))[2] < 50
        ]
        self.assertTrue(red_pixels)
        xs, ys = zip(*red_pixels)
        mark_width = max(xs) - min(xs) + 1
        mark_height = max(ys) - min(ys) + 1
        self.assertAlmostEqual(
            mark_width / mark_height,
            1.0,
            delta=0.08,
            msg="crop-to-fill changed a square artwork element's proportions",
        )

    def test_theme_picker_is_glass_polished_and_hidpi_bounded(self) -> None:
        picker = (SHARE / "moos/theme-picker/main.qml").read_text(encoding="utf-8")
        self.assertIn("Screen.desktopAvailableWidth", picker)
        self.assertIn("Screen.desktopAvailableHeight", picker)
        self.assertRegex(
            picker,
            r"sourceSize:\s*Qt\.size\([^)]*Screen\.devicePixelRatio",
            "theme previews must decode at their rendered HiDPI size",
        )
        self.assertIn("Kirigami.Theme.highlightedTextColor", picker,
                      "selected theme badges must use the scheme's contrasting ink")
        self.assertNotRegex(
            picker,
            r'color\s*:\s*["\']white["\']',
            "the picker must not force white ink onto every family's accent",
        )
        self.assertGreaterEqual(
            picker.count("GradientStop"), 4,
            "the picker lost its layered, palette-driven glass finish",
        )

    def test_theme_picker_and_welcome_are_rtl_complete_and_route_safe(self) -> None:
        picker = (SHARE / "moos/theme-picker/main.qml").read_text(encoding="utf-8")
        self.assertIsNotNone(
            re.search(
            r"Kirigami\.ApplicationWindow\s*\{.*?"
            r"LayoutMirroring\.enabled:\s*"
            r"Qt\.application\.layoutDirection\s*===\s*Qt\.RightToLeft.*?"
            r"LayoutMirroring\.childrenInherit:\s*true",
                picker,
                re.DOTALL,
            ),
            "the whole picker hierarchy must mirror in Arabic",
        )

        welcome = (SHARE / "moos/apps/welcome/main.qml").read_text(encoding="utf-8")
        quick_model = welcome.split("WELCOME_QUICK_THEME_IDS_BEGIN", 1)[1].split(
            "WELCOME_QUICK_THEME_IDS_END", 1
        )[0]
        quick_ids = set(re.findall(r'\{\s*id:\s*"([a-z-]+)"', quick_model))
        expected_quick_ids = {
            "dark",
            "light",
            "nova",
            "amethyst",
            "midnight",
            "aurora",
        }
        self.assertEqual(quick_ids, expected_quick_ids)
        self.assertIn("6 quick looks from a 16-theme family", welcome)
        self.assertIn("6 إطلالات سريعة من عائلة تضم 16 ثيمًا", welcome)

        # Each preview swatch's accent must be the theme's REAL primary, or the first-run
        # picker shows the wrong colour: Nova was previewed sky-blue (#38BDF8) though it is
        # royal indigo #6366F1, and Aurora teal though it is azure #3B82F6. Tie the hand-set
        # literals to the palette files so they cannot silently drift again.
        family = load_json(ROOT / "artwork/moos-themes/palettes.json")
        base = load_json(ROOT / "artwork/moos-ui2/palette.json")
        expected_accent = {
            "dark": base["dark"]["primary"],       # base MoOS UI (Graphite)
            "light": base["light"]["primary"],     # base MoOS UI (Tidal Light)
            "nova": family["nova"]["primary"],
            "amethyst": family["amethyst"]["primary"],
            "midnight": family["midnight"]["primary"],
            "aurora": family["aurora"]["primary"],
        }
        swatch_accent = dict(re.findall(
            r'id:\s*"([a-z-]+)"[^}]*?accentC:\s*"(#[0-9A-Fa-f]{6})"', quick_model, re.S))
        for theme_id, want in expected_accent.items():
            with self.subTest(swatch_accent=theme_id):
                self.assertEqual(
                    swatch_accent.get(theme_id, "").upper(), want.upper(),
                    f"Welcome '{theme_id}' swatch accent must equal its palette primary {want}")

        # The mini preview must not elevate its glass surfaces with Qt.lighter(canvasC):
        # Qt.lighter multiplies HSV Value, so on Midnight's #000000 canvas it is a no-op and
        # the bento/dock render black-on-black (invisible). Elevation must be additive.
        self.assertNotIn(
            "Qt.lighter(lookCard.modelData.canvasC", welcome,
            "the Welcome mini-preview elevates with Qt.lighter(canvasC), which vanishes on the "
            "Midnight #000000 canvas — use additive Qt.tint so black lifts too")

        router = (ROOT / "system_files/usr/bin/moos-open").read_text(encoding="utf-8")
        direct_routes = dict(
            re.findall(
                r"theme/([a-z-]+)\)\s+setsid\s+moos-theme\s+([a-z-]+)",
                router,
            )
        )
        theme_command = (ROOT / "system_files/usr/bin/moos-theme").read_text(
            encoding="utf-8"
        )
        for theme_id in sorted(quick_ids):
            with self.subTest(welcome_theme=theme_id):
                self.assertEqual(
                    direct_routes.get(theme_id),
                    theme_id,
                    "a Welcome theme card has no matching fixed moos-open route",
                )
                self.assertRegex(
                    theme_command,
                    rf"(?m)^\s*{re.escape(theme_id)}\)",
                    "moos-open points at a moos-theme command with no handler",
                )

        # The standalone picker discovers all installed members and uses the
        # validated apply-lnf seam, so it needs no public moos:// route per ID.
        installed_ids = {
            path.name
            for path in (SHARE / "plasma/look-and-feel").glob("org.moos.ui2*")
            if path.is_dir()
        }
        self.assertEqual(len(installed_ids), 16)
        self.assertTrue(
            all(re.fullmatch(r"org\.moos\.ui2(?:\.[a-z0-9]+)*", item)
                for item in installed_ids)
        )
        self.assertIn("moos-theme apply-lnf", picker)
        self.assertIn("org.moos.ui2|org.moos.ui2.*)", theme_command)
        self.assertIn(
            '[ -d "/usr/share/plasma/look-and-feel/$target" ]',
            theme_command,
        )

    def test_theme_picker_waits_for_the_real_switch_result(self) -> None:
        picker = (SHARE / "moos/theme-picker/main.qml").read_text(encoding="utf-8")
        self.assertNotIn(
            "interval: 1400", picker,
            "a cosmetic delay must never stand in for moos-theme process completion",
        )
        self.assertIn('Number(data["exit code"]) === 0', picker)
        self.assertIn('Number(data["exit status"]) === 0', picker)
        self.assertIn(
            "interval: 30000", picker,
            "the picker needs a bounded watchdog for a lost completion/readback",
        )
        self.assertIn(
            "Kirigami.MessageType.Error", picker,
            "theme failures must be visible instead of silently clearing the spinner",
        )

        completion_match = re.search(
            r"function handleThemeResult\(.*?\n    }\n\n    function refreshThemes",
            picker,
            re.DOTALL,
        )
        self.assertIsNotNone(completion_match)
        completion = completion_match.group(0)
        exit_check = completion.find("normalExit(data)")
        readback_state = completion.find("awaitingReadback = true")
        readback_call = completion.find("refreshCurrent()")
        self.assertTrue(
            0 <= exit_check < readback_state < readback_call,
            "live theme readback must start only after a successful process exit",
        )

        watchdog_start = picker.find("id: operationTimeout")
        watchdog_end = picker.find("ListModel { id: themesModel }", watchdog_start)
        watchdog = picker[watchdog_start:watchdog_end]
        self.assertIn("root.busy = false", watchdog)
        self.assertNotIn(
            "themeExec.disconnectSource", watchdog,
            "the watchdog must not kill moos-theme halfway through an atomic apply",
        )
        # A hung read-only verification query must be released. Assert the
        # RELATIONSHIP, not one literal argument: the picker now waits on more than
        # one query source (the theme readback and the wallpaper-motion readback),
        # so it selects the source it is actually waiting on. Pinning the old
        # single-argument literal here is what turned this gate red the moment a
        # second readback was added — a constant assertion outliving its constant.
        self.assertRegex(
            watchdog, r"queryExec\.disconnectSource\(",
            "a hung read-only verification query should be safely released",
        )
        for _source in ("root.currentQuery", "root.currentMotionQuery",
                        "root.supplementQuery"):
            self.assertIn(
                _source, watchdog,
                f"the watchdog must be able to release {_source}; every query source "
                "the picker can be waiting on has to be reachable from the timeout",
            )
        # "Verified" has to mean a SUPPLEMENT was verified. Reading back only
        # LookAndFeelPackage checks the one value plasma-apply-lookandfeel never
        # gets wrong, and none of the four things moos-theme exists to carry —
        # so a switch that left Firefox dark on a light desktop still reported
        # success. GTK's light/dark bit is the one the picker can predict alone
        # (every MoOS light sibling is its dark id + ".light").
        self.assertIn(
            '"gsettings get org.gnome.desktop.interface color-scheme"', picker,
            "the picker must read back a supplement moos-theme itself owns",
        )
        supplement_readback = picker[
            picker.index("} else if (cmd === supplementQuery)"):
            picker.index("function handleThemeResult")
        ]
        self.assertIn(
            "activeScheme !== pendingExpectedColorScheme", supplement_readback
        )
        self.assertIn(
            "Theme applied and verified", supplement_readback,
            "the success message must be reachable only through the supplement "
            "readback, never straight from the LookAndFeelPackage readback",
        )

    def test_dark_and_light_own_complete_distinct_svg_suites(self) -> None:
        dark = SHARE / "plasma/desktoptheme/MoOSUI2"
        light = SHARE / "plasma/desktoptheme/MoOSUI2Light"
        dark_svgs = {path.relative_to(dark).as_posix() for path in dark.rglob("*.svg")}
        light_svgs = {path.relative_to(light).as_posix() for path in light.rglob("*.svg")}

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
        self.assertRegex(
            system_card,
            r"Layout\.preferredWidth:\s*Math\.round\("
            r"Kirigami\.Units\.gridUnit\s*\*\s*(?:4\.[2-9]|[5-9])",
            "the verdict column must fit HEALTHY at the supported 4K/200% scale",
        )

        clock_card = qml_by_path[DASHBOARD / "contents/ui/ClockCard.qml"]
        self.assertRegex(
            clock_card,
            r"RowLayout\s*\{[^}]*LayoutMirroring\.enabled:\s*false"
            r"[^}]*LayoutMirroring\.childrenInherit:\s*true"
            r"[^}]*layoutDirection:\s*Qt\.LeftToRight",
            "the HH:mm glyph row must opt out of Plasma's inherited RTL mirroring",
        )
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
        # `> 1`, not `> 0`. Kirigami FLOORS longDuration at 1 when the animation
        # factor is 0 — measured 200 / 100 / 1 at factors 1 / 0.5 / 0 — so `> 0`
        # is true even with animations fully disabled and this guard never fired.
        # This assertion USED to require the broken form, which is how the bug
        # survived every gate. tests/test_moos_motion_gate.py proves it in a real
        # QML engine rather than by string.
        self.assertIn("Kirigami.Units.longDuration > 1", main,
                      "motion guard must honour Plasma's disabled-animation duration")
        self.assertNotIn("Kirigami.Units.longDuration > 0", main,
                         "`> 0` never fires: Kirigami floors longDuration at 1")
        self.assertIn("import org.moos.ui as MoUI", main)
        self.assertIn("design.desktopHubColumns", main)
        self.assertIn("design.desktopHubRows", main)
        self.assertIn("Horizon Hub", main)
        self.assertEqual(
            len(re.findall(r"integrated:\s*true", main)),
            3,
            "time, weather and system health must suppress their individual cards",
        )
        self.assertNotIn(
            "GlassCard {",
            main,
            "Horizon Hub content must float directly over the wallpaper, with no "
            "outer card, border, shadow or glass rectangle",
        )
        glass_card = qml_by_path[DASHBOARD / "contents/ui/GlassCard.qml"]
        self.assertIn("property bool integrated: false", glass_card)
        self.assertIn("!card.integrated", glass_card)

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
        self.assertIn(
            "anchors.horizontalCenter: parent.horizontalCenter",
            wrapper,
            "the complete Horizon Hub must be centred horizontally",
        )
        bento_frame = wrapper.split("id: bentoFrame", 1)[1].split(
            "Loader {", 1
        )[0]
        self.assertNotIn(
            "anchors.left:",
            bento_frame,
            "the Horizon Hub must not regress to a top-left anchored frame",
        )
        self.assertIn("parent.height * 0.16", bento_frame)
        self.assertRegex(
            wrapper,
            r"(?s)Loader\s*\{\s*id:\s*bentoLoader.*?active:\s*bentoFrame\.dashboardRequested",
            "ShowDashboard=false must unload the bento, not leave its timers and weather "
            "requests alive behind visible=false",
        )
        self.assertNotRegex(
            wrapper,
            r"(?s)Item\s*\{\s*id:\s*bentoFrame.*?DashboardBento\s*\{\s*id:",
            "the dashboard is still instantiated unconditionally inside its hidden frame",
        )
        self.assertIn("root.configuration.Image", wrapper,
                      "the scene must read the Image config key moos-theme writes per half")
        # The scene layer owns motion too (the ambient wash), and it must obey the
        # SAME setting the bento obeys. Plasma expresses "animations off" by
        # collapsing durations to their floor of 1 (NOT 0 — that is the whole
        # trap); a wallpaper that only consults its own
        # AmbientMotion key keeps breathing on a desktop whose owner asked every
        # animation to stop — an accessibility promise broken by the largest
        # surface on screen.
        self.assertIn("Kirigami.Units.longDuration > 1", wrapper,
                      "the wallpaper scene's motion guard must honour Plasma's "
                      "disabled-animation duration, not only its own AmbientMotion key")
        self.assertNotIn("Kirigami.Units.longDuration > 0", wrapper,
                         "`> 0` never fires: Kirigami floors longDuration at 1, so the "
                         "scene kept breathing on a desktop whose owner asked every "
                         "animation to stop")
        bento = qml_by_path[DASHBOARD / "contents/ui/DashboardBento.qml"]
        self.assertNotIn("import org.kde.plasma.plasmoid", bento,
                         "DashboardBento must stay plain QtQuick/Kirigami — the build's "
                         "smoke harness loads it directly")


if __name__ == "__main__":
    unittest.main(verbosity=2)
