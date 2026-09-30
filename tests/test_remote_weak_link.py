#!/usr/bin/env python3
"""Mo PC Remote on a weak link: the helper must honour the controller's weak-link rung.

The controller's automatic ladder now goes below Data saver to 854 px at 15 fps (WEAK_LINK in
moremote/controller/src/lib/quality.ts), about 0.34 Mbit/s by the helper's own formula. A flat
800 kbit/s floor in the helper handed that struggling link more than twice what it asked for.
The floor is a per-frame budget now; these pin both halves of that promise.
"""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"
QUALITY = ROOT / "moremote/controller/src/lib/quality.ts"


def bitrate(width, height, fps, quality):
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "h264_bitrate_bps")
    scope = {"state": {"fps": fps, "quality": quality, "out": (width, height)}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(HELPER), "exec"), scope)
    return scope["h264_bitrate_bps"](width, height)


class WeakLinkBitrate(unittest.TestCase):
    def weak_rung(self):
        text = QUALITY.read_text(encoding="utf-8")
        found = re.search(r"WEAK_LINK = \{ quality: (\d+), fps: (\d+), width: (\d+) \}", text)
        self.assertIsNotNone(found, "the controller's WEAK_LINK rung was not found")
        quality, fps, width = (int(v) for v in found.groups())
        return quality, fps, width, round(width * 9 / 16)

    def test_the_weak_rung_really_is_lighter(self):
        quality, fps, width, height = self.weak_rung()
        weak = bitrate(width, height, fps, quality)
        data_saver = bitrate(1024, 576, 30, 52)
        self.assertLessEqual(weak, 450_000, f"the weak rung still asks for {weak} bit/s")
        self.assertLess(weak, data_saver * 0.45,
                        "the weak rung must cut the bitrate well below Data saver's")

    def test_thirty_fps_presets_are_unchanged(self):
        # The old flat floor, for every preset shape the controller can send at 30 fps and above.
        for width, height, fps, quality in ((720, 405, 30, 52), (1024, 576, 30, 52),
                                            (1366, 768, 30, 68), (1920, 1080, 30, 80),
                                            (2560, 1440, 60, 85)):
            with self.subTest(width=width, fps=fps):
                bpp = 0.03 + (quality - 10) / 85.0 * 0.07
                old = int(max(800_000, min(12_000_000, bpp * width * height * fps)))
                self.assertEqual(bitrate(width, height, fps, quality), old)


if __name__ == "__main__":
    unittest.main()
