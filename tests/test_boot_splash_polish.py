#!/usr/bin/env python3
"""4K fidelity and bounded-render-work gates for the MoOS Plymouth scene."""

from __future__ import annotations

from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "system_files/usr/share/plymouth/themes/moos"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise AssertionError(f"not a PNG with an IHDR header: {path}")
    return struct.unpack(">II", data[16:24])


class BootSplashPolishTests(unittest.TestCase):
    def test_hero_assets_downsample_instead_of_upscaling_at_4k(self) -> None:
        minimums = {
            "logo.png": 1024,
            "ring.png": 1440,
            "ring2.png": 1440,
            "glow.png": 1024,
            "pulse.png": 1024,
        }
        for name, minimum in minimums.items():
            with self.subTest(asset=name):
                width, height = png_size(THEME / name)
                self.assertEqual(width, height)
                self.assertGreaterEqual(width, minimum)

    def test_logo_and_field_stop_resampling_after_the_finite_entrance(self) -> None:
        script = (THEME / "moos.script").read_text(encoding="utf-8")
        self.assertIn("logo_settled = 1", script)
        self.assertIn("field_settled = 1", script)
        self.assertIn("pulse_done = 1", script)
        self.assertNotIn("BREATH_SEC", script)
        self.assertNotIn("PULSE_SEC", script)
        self.assertNotIn("Math.Int(t /", script)
        # One cached full-size image plus the finite entrance scale. A third
        # call would mean the settled logo is being resampled again.
        self.assertEqual(script.count("logo_image.Scale"), 2)
        self.assertIn("logo_sprite.SetImage(logo_full)", script)


if __name__ == "__main__":
    unittest.main(verbosity=2)
