#!/usr/bin/env python3
"""Regression gate for MoOS UI's palette-aware symbolic action icons."""

from __future__ import annotations

import configparser
import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "artwork/generate_moos_symbolic_icons.py"
FAMILY_GENERATOR_PATH = ROOT / "artwork/generate_moos_themes.py"
ACTION_DIR = ROOT / "system_files/usr/share/icons/hicolor/scalable/actions"
APP_DIR = ROOT / "system_files/usr/share/icons/hicolor/scalable/apps"
ICON_ROOT = ROOT / "system_files/usr/share/icons"
QML_ROOTS = (
    ROOT / "system_files/usr/share/moos",
    ROOT / "system_files/usr/share/plasma",
)

# Family members generated from the Graphite/Tidal engine own only the 69
# palette-sensitive action symbols. Their broad file/application vocabulary is
# inherited from the corresponding base icon theme.
FAMILY_ICON_THEMES = {
    "MoOSUI2Amethyst": ("org.moos.ui2.amethyst", "MoOSUI2"),
    "MoOSUI2AmethystLight": ("org.moos.ui2.amethyst.light", "MoOSUI2Light"),
    "MoOSUI2Arena": ("org.moos.ui2.gaming", "MoOSUI2"),
    "MoOSUI2ArenaLight": ("org.moos.ui2.gaming.light", "MoOSUI2Light"),
    "MoOSUI2Aurora": ("org.moos.ui2.aurora", "MoOSUI2"),
    "MoOSUI2AuroraLight": ("org.moos.ui2.aurora.light", "MoOSUI2Light"),
    "MoOSUI2Daylight": ("org.moos.ui2.midnight.light", "MoOSUI2Light"),
    "MoOSUI2Forge": ("org.moos.ui2.dev", "MoOSUI2"),
    "MoOSUI2ForgeLight": ("org.moos.ui2.dev.light", "MoOSUI2Light"),
    "MoOSUI2Midnight": ("org.moos.ui2.midnight", "MoOSUI2"),
    "MoOSUI2Nova": ("org.moos.ui2.nova", "MoOSUI2"),
    "MoOSUI2NovaLight": ("org.moos.ui2.nova.light", "MoOSUI2Light"),
    "MoOSUI2Scholar": ("org.moos.ui2.study", "MoOSUI2"),
    "MoOSUI2ScholarLight": ("org.moos.ui2.study.light", "MoOSUI2Light"),
}

spec = importlib.util.spec_from_file_location("moos_symbolic_generator", GENERATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {GENERATOR_PATH}")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)

family_spec = importlib.util.spec_from_file_location(
    "moos_symbolic_family_generator", FAMILY_GENERATOR_PATH
)
if family_spec is None or family_spec.loader is None:
    raise RuntimeError(f"cannot load {FAMILY_GENERATOR_PATH}")
family_generator = importlib.util.module_from_spec(family_spec)
family_spec.loader.exec_module(family_generator)


class MoOSSymbolicIconTests(unittest.TestCase):
    maxDiff = None

    @staticmethod
    def _kconfig(path: Path) -> configparser.ConfigParser:
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        if not parser.read(path, encoding="utf-8"):
            raise AssertionError(f"could not parse {path.relative_to(ROOT)}")
        return parser

    @staticmethod
    def _hex(rgb: str) -> str:
        channels = tuple(int(channel.strip()) for channel in rgb.split(",")[:3])
        if len(channels) != 3 or any(channel < 0 or channel > 255 for channel in channels):
            raise AssertionError(f"invalid KDE RGB colour: {rgb}")
        return "#" + "".join(f"{channel:02X}" for channel in channels)

    @staticmethod
    def _contrast(first: str, second: str) -> float:
        def luminance(literal: str) -> float:
            channels = []
            for offset in (1, 3, 5):
                value = int(literal[offset:offset + 2], 16) / 255
                channels.append(
                    value / 12.92
                    if value <= 0.04045
                    else ((value + 0.055) / 1.055) ** 2.4
                )
            return (
                0.2126 * channels[0]
                + 0.7152 * channels[1]
                + 0.0722 * channels[2]
            )

        lighter, darker = sorted(
            (luminance(first), luminance(second)), reverse=True
        )
        return (lighter + 0.05) / (darker + 0.05)

    @staticmethod
    def _mix(first: str, second: str, amount: float) -> str:
        left = tuple(int(first[offset:offset + 2], 16) for offset in (1, 3, 5))
        right = tuple(int(second[offset:offset + 2], 16) for offset in (1, 3, 5))
        return "#" + "".join(
            f"{round(left[index] + (right[index] - left[index]) * amount):02X}"
            for index in range(3)
        )

    @staticmethod
    def _css_palette(source: str) -> dict[str, str]:
        return {
            role: colour.upper()
            for role, colour in re.findall(
                r"\.(ColorScheme-(?:Text|Highlight|NeutralText|NegativeText))"
                r"\s*\{\s*color:\s*(#[0-9A-Fa-f]{6})\s*;",
                source,
            )
        }

    def test_generated_sources_are_current_and_only_canonical_symbolics_ship(self) -> None:
        expected = generator.expected_outputs()
        self.assertEqual(
            set(ACTION_DIR.glob("moos-*.svg")),
            set(expected),
            "action directory contains a missing or unmanaged legacy MoOS symbol",
        )
        for path, content in expected.items():
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                content,
                f"{path.relative_to(ROOT)} is stale; run the symbolic generator",
            )
            self.assertTrue(
                path.stem.endswith("-symbolic"),
                f"{path.name} is an action icon without the symbolic suffix",
            )

    def test_every_symbol_uses_the_dynamic_colour_roles_and_safe_geometry(self) -> None:
        forbidden = ("linearGradient", "radialGradient", "<filter", "<image", "fill-opacity")
        role_fallbacks = {
            "ColorScheme-Text": "#2e3436",
            "ColorScheme-Highlight": "#2e3436",
            "ColorScheme-NeutralText": "#ff7800",
            "ColorScheme-NegativeText": "#e01b24",
        }
        for path in sorted(ACTION_DIR.glob("moos-*.svg")):
            text = path.read_text(encoding="utf-8")
            root = ET.fromstring(text)
            self.assertEqual(root.attrib.get("viewBox"), "0 0 24 24", path.name)
            self.assertEqual(root.attrib.get("width"), "24", path.name)
            self.assertEqual(root.attrib.get("height"), "24", path.name)
            self.assertIn('id="current-color-scheme"', text, path.name)
            self.assertIn("ColorScheme-Text", text, path.name)
            self.assertIn("ColorScheme-Highlight", text, path.name)
            self.assertIn("currentColor", text, path.name)
            self.assertRegex(text, r"<title\b[^>]*>[^<]+</title>", path.name)
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.name} contains non-symbolic {token}")

            # Each filled path carries a deterministic GTK/librsvg fallback,
            # but its class is the live KDE palette role. No shape may choose an
            # arbitrary paint or depend on a fixed paint server.
            shapes = root.findall("{http://www.w3.org/2000/svg}path")
            self.assertTrue(shapes, f"{path.name} contains no painted geometry")
            for shape in shapes:
                role = shape.attrib.get("class", "").split()[0]
                self.assertIn(role, role_fallbacks, f"{path.name} has no semantic colour role")
                self.assertEqual(
                    shape.attrib.get("fill"),
                    role_fallbacks[role],
                    f"{path.name} has a non-canonical renderer fallback",
                )
                self.assertNotIn("stroke", shape.attrib, f"{path.name} must remain path-only")
                self.assertNotIn("url(#", shape.attrib.get("fill", ""), path.name)

    def test_warning_uses_the_theme_warning_role(self) -> None:
        warning = (ACTION_DIR / "moos-warning-symbolic.svg").read_text(encoding="utf-8")
        self.assertIn('class="ColorScheme-NeutralText warning"', warning)
        danger = (ACTION_DIR / "moos-danger-symbolic.svg").read_text(encoding="utf-8")
        self.assertIn('class="ColorScheme-NegativeText error"', danger)

    def test_family_overlays_are_complete_palette_matched_and_geometry_identical(self) -> None:
        actual_themes = {
            path.name
            for path in ICON_ROOT.iterdir()
            if path.is_dir() and path.name != "hicolor"
        }
        self.assertEqual(
            actual_themes,
            set(FAMILY_ICON_THEMES),
            "the source tree must carry exactly one symbolic overlay for each "
            "non-base MoOS palette",
        )
        keys_by_style = {
            metadata["style"]: key
            for key, metadata in family_generator.THEMES.items()
        }
        self.assertEqual(
            set(keys_by_style),
            set(FAMILY_ICON_THEMES),
            "the icon-overlay contract drifted from the generated theme family",
        )

        canonical_names = {
            f"moos-{name}-symbolic.svg" for name in generator.SYMBOLS
        }
        palette_fingerprints: set[tuple[tuple[str, str], ...]] = set()
        derived_highlights: set[str] = set()
        for style, (lnf, inherited) in FAMILY_ICON_THEMES.items():
            with self.subTest(icon_theme=style):
                family_key = keys_by_style[style]
                roles = family_generator._roles(family_key)
                semantic_surfaces = tuple(
                    roles[name] for name in ("canvas", "surface", "card", "raised")
                )
                raw_primary = roles["primary"].upper()
                if min(
                    self._contrast(raw_primary, surface)
                    for surface in semantic_surfaces
                ) >= 3.0:
                    nearest_safe_accent = raw_primary
                else:
                    derived_highlights.add(style)
                    nearest_safe_accent = next(
                        candidate
                        for step in range(1, 101)
                        for candidate in (
                            self._mix(raw_primary, roles["text"], step / 100),
                        )
                        if min(
                            self._contrast(candidate, surface)
                            for surface in semantic_surfaces
                        ) >= 3.0
                    )
                self.assertEqual(
                    family_generator._symbol_accent_ink(roles).upper(),
                    nearest_safe_accent,
                    f"{style}: symbolic accent must be the nearest 1% step from "
                    "primary toward text that clears 3:1 on every surface",
                )
                expected_palette = {
                    generator.TEXT: roles["text"],
                    generator.HIGHLIGHT: nearest_safe_accent,
                    generator.WARNING: roles["warning"],
                    generator.ERROR: roles["negative"],
                }
                root = ICON_ROOT / style
                index = self._kconfig(root / "index.theme")
                self.assertEqual(index["Icon Theme"]["Inherits"], inherited)
                self.assertEqual(
                    index["Icon Theme"]["FollowsColorScheme"],
                    "false",
                    f"{style}: QIcon recolouring reads the application QPalette, "
                    "not the Plasma surface colour set, which painted dark "
                    "symbols on the dark Launcher — each overlay bakes its "
                    "WCAG-checked palette inks instead",
                )
                self.assertEqual(
                    index["Icon Theme"]["Directories"],
                    "moos/actions/scalable",
                )
                self.assertEqual(
                    dict(index["moos/actions/scalable"]),
                    {
                        "Size": "24",
                        "Context": "Actions",
                        "Type": "Scalable",
                        "MinSize": "16",
                        "MaxSize": "512",
                    },
                )

                defaults = self._kconfig(
                    ROOT
                    / "system_files/usr/share/plasma/look-and-feel"
                    / lnf
                    / "contents/defaults"
                )
                self.assertEqual(
                    defaults["kdeglobals][Icons"]["Theme"],
                    style,
                    f"{lnf} does not select its palette-matched icon overlay",
                )
                self.assertEqual(defaults["plasmarc][Theme"]["name"], style)
                self.assertEqual(
                    defaults["kdeglobals][General"]["ColorScheme"],
                    style,
                )

                scheme = self._kconfig(
                    ROOT / f"system_files/usr/share/color-schemes/{style}.colors"
                )
                expected_literal_roles = {
                    "ColorScheme-Text": self._hex(
                        scheme["Colors:Window"]["ForegroundNormal"]
                    ),
                    "ColorScheme-NeutralText": self._hex(
                        scheme["Colors:Window"]["ForegroundNeutral"]
                    ),
                    "ColorScheme-NegativeText": self._hex(
                        scheme["Colors:Window"]["ForegroundNegative"]
                    ),
                }
                primary = self._hex(
                    scheme["Colors:Selection"]["BackgroundNormal"]
                )
                surfaces = {
                    "window": self._hex(
                        scheme["Colors:Window"]["BackgroundNormal"]
                    ),
                    "view": self._hex(
                        scheme["Colors:View"]["BackgroundNormal"]
                    ),
                    "raised": self._hex(
                        scheme["Colors:Button"]["BackgroundNormal"]
                    ),
                }

                actions = root / "moos/actions/scalable"
                actual_names = {path.name for path in actions.glob("*.svg")}
                self.assertEqual(
                    actual_names,
                    canonical_names,
                    f"{style} must carry all {len(canonical_names)} owned symbols "
                    "and no private geometry",
                )

                theme_palette: dict[str, str] | None = None
                for name in sorted(canonical_names):
                    overlay_path = actions / name
                    overlay_source = overlay_path.read_text(encoding="utf-8")
                    symbol_name = name.removeprefix("moos-").removesuffix(
                        "-symbolic.svg"
                    )
                    self.assertEqual(
                        overlay_source,
                        generator.render(
                            symbol_name,
                            generator.SYMBOLS[symbol_name],
                            expected_palette,
                        ),
                        f"{style}/{name} is stale; regenerate the theme family",
                    )
                    palette = self._css_palette(overlay_source)
                    self.assertEqual(
                        set(palette),
                        {
                            "ColorScheme-Text",
                            "ColorScheme-Highlight",
                            "ColorScheme-NeutralText",
                            "ColorScheme-NegativeText",
                        },
                        f"{style}/{name} has an incomplete semantic palette",
                    )
                    for role, expected in expected_literal_roles.items():
                        self.assertEqual(
                            palette[role],
                            expected,
                            f"{style}/{name}: {role} drifted from {style}.colors",
                        )

                    # Highlight is the one derived role: a light scheme's raw
                    # Selection colour can miss WCAG's 3:1 non-text threshold
                    # on a raised control. It may move only to regain that
                    # threshold; the generator test below holds the exact
                    # derivation. It must still be a distinct accent channel.
                    highlight = palette["ColorScheme-Highlight"]
                    self.assertEqual(
                        highlight,
                        expected_palette[generator.HIGHLIGHT].upper(),
                        f"{style}/{name}: highlight does not match the generator's "
                        "nearest WCAG-safe accent",
                    )
                    self.assertNotEqual(
                        highlight,
                        palette["ColorScheme-Text"],
                        f"{style}/{name}: highlight collapsed into ordinary ink",
                    )
                    for surface_name, surface in surfaces.items():
                        ratio = self._contrast(highlight, surface)
                        self.assertGreaterEqual(
                            ratio,
                            3.0,
                            f"{style}/{name}: derived highlight has only "
                            f"{ratio:.2f}:1 on {surface_name}",
                        )
                    for role_name in ("canvas", "surface", "card", "raised"):
                        ratio = self._contrast(highlight, roles[role_name])
                        self.assertGreaterEqual(
                            ratio,
                            3.0,
                            f"{style}/{name}: highlight has only {ratio:.2f}:1 "
                            f"against semantic {role_name}",
                        )
                    if highlight != primary:
                        self.assertGreater(
                            self._contrast(highlight, primary),
                            1.0,
                            f"{style}/{name}: derived highlight did not change",
                        )

                    if theme_palette is None:
                        theme_palette = palette
                    self.assertEqual(
                        palette,
                        theme_palette,
                        f"{style}: {name} carries a different fallback palette",
                    )

                    canonical_root = ET.parse(ACTION_DIR / name).getroot()
                    overlay_root = ET.fromstring(overlay_source)
                    for actual_root in (canonical_root, overlay_root):
                        self.assertEqual(
                            actual_root.attrib.get("viewBox"),
                            "0 0 24 24",
                            f"{style}/{name}",
                        )
                    canonical_paths = [
                        (
                            path.attrib.get("class"),
                            path.attrib.get("fill"),
                            path.attrib.get("fill-rule"),
                            path.attrib.get("d"),
                        )
                        for path in canonical_root.findall(
                            "{http://www.w3.org/2000/svg}path"
                        )
                    ]
                    overlay_paths = [
                        (
                            path.attrib.get("class"),
                            path.attrib.get("fill"),
                            path.attrib.get("fill-rule"),
                            path.attrib.get("d"),
                        )
                        for path in overlay_root.findall(
                            "{http://www.w3.org/2000/svg}path"
                        )
                    ]
                    self.assertEqual(
                        overlay_paths,
                        canonical_paths,
                        f"{style}/{name}: palette overlay forked the Tidal Cut geometry",
                    )

                assert theme_palette is not None
                palette_fingerprints.add(tuple(sorted(theme_palette.items())))

        self.assertEqual(
            len(palette_fingerprints),
            len(FAMILY_ICON_THEMES),
            "two family members share one copied fallback palette instead of "
            "following their own semantic colours",
        )
        self.assertEqual(
            derived_highlights,
            {"MoOSUI2Daylight"},
            "the regression fixture must keep exercising the unsafe-raw-accent "
            "path; currently Daylight is the one palette that needs correction",
        )

    def test_image_build_places_symbols_ahead_of_the_fallback_theme(self) -> None:
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
        self.assertIn("recolor_moos_symbolic_dir()", build)
        self.assertEqual(
            build.count(
                "Directories=moos/actions/scalable,moos/apps/scalable,"
            ),
            3,
            "both themes and the image gate must agree on overlay precedence",
        )
        self.assertEqual(
            build.count(
                "hicolor/scalable/actions/moos-*-symbolic.svg"
            ),
            2,
            "both dark and light themes must copy the owned symbolic layer",
        )
        self.assertIn(
            'moos/actions/scalable/moos-warning-symbolic.svg',
            build,
            "the in-image gate must prove an owned semantic symbol landed",
        )

        # The base Graphite/Tidal packages are assembled inside build.sh rather
        # than committed under system_files. They need the same palette bridge:
        # copying hicolor's light fallback into both is the original live bug.
        collapsed = re.sub(r"\\\s*\n\s*", " ", build)
        calls = {
            theme: tuple(colour.upper() for colour in colours)
            for theme, *colours in re.findall(
                r"recolor_moos_symbolic_dir\s+"
                r"/usr/share/icons/(MoOSUI2(?:Light)?)/moos/actions/scalable\s+"
                r"'(#[0-9A-Fa-f]{6})'\s+'(#[0-9A-Fa-f]{6})'\s+"
                r"'(#[0-9A-Fa-f]{6})'\s+'(#[0-9A-Fa-f]{6})'",
                collapsed,
            )
        }
        expected_calls: dict[str, tuple[str, ...]] = {}
        for theme, scheme_name in (
            ("MoOSUI2", "MoOSUI2Dark"),
            ("MoOSUI2Light", "MoOSUI2Light"),
        ):
            scheme = self._kconfig(
                ROOT
                / f"system_files/usr/share/color-schemes/{scheme_name}.colors"
            )
            expected_calls[theme] = (
                self._hex(scheme["Colors:Window"]["ForegroundNormal"]),
                self._hex(scheme["Colors:Selection"]["BackgroundNormal"]),
                self._hex(scheme["Colors:Window"]["ForegroundNeutral"]),
                self._hex(scheme["Colors:Window"]["ForegroundNegative"]),
            )
        self.assertEqual(
            calls,
            expected_calls,
            "build.sh must recolour both base symbolic layers to their exact "
            "Graphite/Tidal semantic roles",
        )

    def test_every_first_party_qml_icon_reference_resolves(self) -> None:
        unresolved: list[str] = []
        legacy_actions: list[str] = []
        action_stems = {path.stem for path in ACTION_DIR.glob("moos-*.svg")}
        app_stems = {path.stem for path in APP_DIR.glob("moos-*.svg")}
        app_stems.update(
            path.stem
            for path in (ROOT / "system_files/usr/share/icons/hicolor").glob(
                "*x*/apps/moos-*.png"
            )
        )
        legacy_stems = {name.removesuffix("-symbolic") for name in action_stems}
        quoted_name = re.compile(r"""["'](moos-[a-z0-9-]+)["']""")

        for qml_root in QML_ROOTS:
            for path in qml_root.rglob("*.qml"):
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if "source" not in line and not re.search(r"\bicon(?:\.name)?\s*:", line):
                        continue
                    for name in quoted_name.findall(line):
                        where = f"{path.relative_to(ROOT)}:{lineno}: {name}"
                        if name in legacy_stems:
                            legacy_actions.append(where)
                        if name not in action_stems and name not in app_stems:
                            unresolved.append(where)

        self.assertFalse(
            legacy_actions,
            "first-party QML references legacy non-symbolic action names:\n"
            + "\n".join(legacy_actions),
        )
        self.assertFalse(
            unresolved,
            "first-party QML references icons with no owned scalable asset:\n"
            + "\n".join(unresolved),
        )

    def test_apps_use_one_symbolic_glyph_vocabulary_not_private_data_svgs(self) -> None:
        action_stems = {path.stem for path in ACTION_DIR.glob("moos-*.svg")}
        aliases = {
            "android": "android-apps",
            "brain": "ai",
            "doc": "document",
            "gamepad": "gaming",
            "gear": "settings",
            "mic": "microphone",
            "monitor": "system",
            "note": "music",
            "warn": "warning",
            "download": "install",
            "disk": "storage",
        }
        unresolved: list[str] = []

        for app in ("welcome", "installer", "store"):
            path = ROOT / f"system_files/usr/share/moos/apps/{app}/main.qml"
            source = path.read_text(encoding="utf-8")
            with self.subTest(app=app):
                self.assertNotIn("glyphURL", source)
                self.assertNotIn("data:image/svg+xml", source)
                self.assertNotIn("readonly property var glyphs:", source)
                self.assertEqual(
                    source.count("component Glyph: MoOSUi.SymbolIcon"),
                    1,
                    f"{app} must consume the shared icon-theme layer",
                )
                self.assertIn("symbol: win.glyphIcon(name)", source)
                self.assertIn('import "../ui" as MoOSUi', source)
                self.assertIn(
                    'import "../ui/SymbolCatalog.js" as MoOSSymbols',
                    source,
                )
                self.assertIn("MoOSSymbols.resolve(", source)
                for old, canonical in aliases.items():
                    self.assertIn(f'"{old}": "{canonical}"', source)

            names = set(re.findall(
                r"\b(?:glyphName|glyph|g)\s*:\s*"
                r'"([a-z][a-z0-9-]*)"',
                source,
            ))
            names.update(re.findall(
                r"\bGlyph\s*\{[^{}]{0,500}?\bname\s*:\s*"
                r'"([a-z][a-z0-9-]*)"',
                source,
                re.DOTALL,
            ))
            for name in names:
                stem = f"moos-{aliases.get(name, name)}-symbolic"
                if stem not in action_stems:
                    unresolved.append(f"{app}: {name} -> {stem}")

        self.assertFalse(
            unresolved,
            "a first-party glyph name has no generated symbolic asset:\n"
            + "\n".join(unresolved),
        )

        moai = (
            ROOT / "system_files/usr/share/moos/apps/moai/main.qml"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"configure"', moai)
        self.assertNotIn('"utilities-terminal"', moai)

        shared_symbol = (
            ROOT / "system_files/usr/share/moos/apps/ui/SymbolIcon.qml"
        ).read_text(encoding="utf-8")
        self.assertIn("Accessible.ignored: true", shared_symbol)
        self.assertIn("Kirigami.Icon", shared_symbol)


if __name__ == "__main__":
    unittest.main(verbosity=2)
