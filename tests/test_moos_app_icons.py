#!/usr/bin/env python3
"""Release gates for MoOS-owned application artwork.

The application icons are now static PNGs. We only test for the presence
of the raster ladder and the protected identity of Mo AI.
"""

from __future__ import annotations

import collections
import importlib.util
import pathlib
import unittest

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "artwork/generate_moos_app_icons.py"
SHARE = ROOT / "system_files/usr/share"
ICONS = SHARE / "icons/hicolor"
SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)

def load_generator():
    spec = importlib.util.spec_from_file_location("moos_app_icons", GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {GENERATOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

MODULE = load_generator()

class ProtectedIdentities(unittest.TestCase):
    def test_moai_is_not_authored_by_the_family_glyph_catalog(self) -> None:
        self.assertNotIn("moos-moai", MODULE.MARKS)
        self.assertEqual(
            MODULE.MOAI_GENERATOR.name,
            "generate_moai_icon.py",
            "the family generator must delegate the protected identity",
        )

    def test_moai_master_is_a_seated_orb_not_an_edge_to_edge_raster(self) -> None:
        with Image.open(ICONS / "512x512/apps/moos-moai.png") as source:
            raster = source.convert("RGBA")
        for corner in ((2, 2), (509, 2), (2, 509), (509, 509)):
            self.assertEqual(
                raster.getpixel(corner)[3], 0, f"Mo AI corner {corner} is not clear"
            )

class RasterLadder(unittest.TestCase):
    def test_every_mark_exports_the_full_ladder(self) -> None:
        for name in ("moos-moai", *MODULE.MARKS):
            for size in SIZES:
                with self.subTest(mark=name, size=size):
                    raster = ICONS / f"{size}x{size}/apps/{name}.png"
                    self.assertTrue(raster.is_file(), f"missing {raster}")
                    with Image.open(raster) as image:
                        self.assertEqual(max(image.size), size)

    def test_compatibility_copies_track_their_source(self) -> None:
        for size in SIZES:
            with self.subTest(size=size):
                self.assertEqual(
                    (ICONS / f"{size}x{size}/apps/mo-store.png").read_bytes(),
                    (ICONS / f"{size}x{size}/apps/moos-store.png").read_bytes(),
                )
        self.assertEqual(
            (ROOT / "moremote/Logo.png").read_bytes(),
            (ICONS / "512x512/apps/moos-pc-remote.png").read_bytes(),
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)
