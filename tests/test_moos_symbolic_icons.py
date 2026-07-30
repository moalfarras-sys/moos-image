#!/usr/bin/env python3
"""Regression gate for MoOS UI's palette-aware symbolic action icons."""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "artwork/generate_moos_symbolic_icons.py"
ACTION_DIR = ROOT / "system_files/usr/share/icons/hicolor/scalable/actions"
APP_DIR = ROOT / "system_files/usr/share/icons/hicolor/scalable/apps"
QML_ROOTS = (
    ROOT / "system_files/usr/share/moos",
    ROOT / "system_files/usr/share/plasma",
)

spec = importlib.util.spec_from_file_location("moos_symbolic_generator", GENERATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {GENERATOR_PATH}")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)


class MoOSSymbolicIconTests(unittest.TestCase):
    maxDiff = None

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

    def test_image_build_places_symbols_ahead_of_the_fallback_theme(self) -> None:
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
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
