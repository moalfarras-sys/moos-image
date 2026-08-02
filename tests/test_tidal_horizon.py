#!/usr/bin/env python3
"""Product-level gates for the MoOS Tidal Horizon wallpaper language."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import unittest

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
SHARE = ROOT / "system_files/usr/share"
MASTERS = {
    False: ART / "moos-ui2/wallpapers/moos-ui-graphite-horizon-master-v1.png",
    True: ART / "moos-ui2/wallpapers/moos-ui-tidal-horizon-master-v1.png",
}


def load_family_generator():
    path = ART / "generate_moos_themes.py"
    spec = importlib.util.spec_from_file_location("moos_theme_family", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TidalHorizonContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.family = load_family_generator()

    def test_owned_light_and_dark_masters_are_lossless_and_matched(self) -> None:
        sizes = set()
        digests = set()
        for path in MASTERS.values():
            self.assertTrue(path.is_file(), path)
            with Image.open(path) as image:
                self.assertEqual(image.format, "PNG")
                self.assertEqual(image.mode, "RGB")
                sizes.add(image.size)
                digests.add(hash(image.tobytes()))
        self.assertEqual(sizes, {(1672, 941)})
        self.assertEqual(len(digests), 2, "light/dark masters must be distinct")

    def test_base_generator_no_longer_selects_retired_flow_masters(self) -> None:
        text = (ART / "generate_moos_ui2.py").read_text(encoding="utf-8")
        self.assertIn("moos-ui-tidal-horizon-master-v1.png", text)
        self.assertIn("moos-ui-graphite-horizon-master-v1.png", text)
        self.assertNotIn("moos-ui-tidal-flow-master-v3.png", text)
        self.assertNotIn("moos-ui-graphite-flow-master-v4.png", text)

    def test_every_family_preview_is_generated_from_one_horizon_geometry(self) -> None:
        for key, metadata in self.family.THEMES.items():
            with self.subTest(theme=key):
                expected = self.family.crop_to_fill(
                    self.family.make_tidal_horizon(
                        key, metadata.get("light", False)
                    ),
                    (600, 337),
                ).convert("RGB")
                preview = (
                    SHARE
                    / "plasma/look-and-feel"
                    / metadata["lnf"]
                    / "contents/previews/preview.png"
                )
                self.assertTrue(preview.is_file(), preview)
                with Image.open(preview) as actual:
                    difference = ImageChops.difference(
                        expected, actual.convert("RGB")
                    )
                    self.assertIsNone(
                        difference.getbbox(),
                        f"{key} preview drifted from Tidal Horizon",
                    )

    def test_base_picker_names_expose_horizon_identity(self) -> None:
        for package in ("MoOSUI2Graphite", "MoOSUI2Tide"):
            metadata_path = SHARE / "wallpapers" / package / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertIn("Horizon", metadata["KPlugin"]["Name"])

    def test_first_party_apps_never_draw_the_retired_arc(self) -> None:
        """Owner verdict (2026-08-02): the curve is retired inside apps too."""
        ui_dir = SHARE / "moos/apps"
        for qml in sorted(ui_dir.rglob("*.qml")):
            text = re.sub(r"//[^\n]*", "", qml.read_text(encoding="utf-8"))
            self.assertNotIn("TidalHorizon", text,
                             f"{qml} still references the retired arc")


if __name__ == "__main__":
    unittest.main()
