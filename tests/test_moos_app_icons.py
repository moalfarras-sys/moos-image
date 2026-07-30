#!/usr/bin/env python3
"""Release gates for MoOS-owned application artwork.

The interface symbols have a monochrome runtime contract; application marks
have a different job: remain individually recognisable in the launcher while
sharing one optical plate.  These checks guard the two protected boundaries
that previously regressed silently:

* the family generator must delegate Mo AI to its byte-exact commissioned
  artwork generator instead of overwriting it;
* MoPlayer must carry its ember cinema identity, not the generic teal
  play-button glyph it used before the app itself was redesigned.
"""

from __future__ import annotations

import importlib.util
import pathlib
import unittest

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "artwork/generate_moos_app_icons.py"
ICONS = ROOT / "system_files/usr/share/icons/hicolor"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)


def load_generator():
    spec = importlib.util.spec_from_file_location("moos_app_icons", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AppIconContract(unittest.TestCase):
    def test_protected_moai_is_not_authored_by_the_family_glyph_catalog(self) -> None:
        module = load_generator()
        self.assertNotIn("moos-moai", module.GLYPHS)
        self.assertEqual(
            module.MOAI_GENERATOR.name,
            "generate_moai_icon.py",
            "the family generator must delegate the protected identity",
        )

    def test_moplayer_uses_the_owned_mark(self) -> None:
        svg_path = ICONS / "scalable/apps/moos-moplayer.svg"
        svg = svg_path.read_text(encoding="utf-8")
        self.assertIn("M286 694V374", svg)
        self.assertNotIn("<image", svg)
        self.assertNotIn("<text", svg)
        self.assertNotIn("m462 392 170 112-170 112", svg)

    def test_moplayer_ladder_is_rgba_nonempty_and_led(self) -> None:
        for size in SIZES:
            path = ICONS / f"{size}x{size}/apps/moos-moplayer.png"
            with self.subTest(size=size), Image.open(path) as image:
                rgba = image.convert("RGBA")
                self.assertEqual(rgba.size, (size, size))
                alpha = rgba.getchannel("A")
                self.assertIsNotNone(alpha.getbbox(), f"{path} is empty")

                # The mark must remain visible at the 16 px dock size.
                pixels = rgba.tobytes()
                visible = sum(
                    1
                    for offset in range(0, len(pixels), 4)
                    if pixels[offset + 3] >= 96
                )
                self.assertGreaterEqual(
                    visible,
                    max(2, size * size // 80),
                    f"{path} lost the MoPlayer identity",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
