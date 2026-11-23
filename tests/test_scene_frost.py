#!/usr/bin/env python3
"""Gate: the desktop Hub's glass cards sit on real frost, without a shader on any card.

The Hub is painted INSIDE the scene wallpaper, so no compositor can blur what lies behind
it. With KWin's blur on, every card still painted its thin "frosted" density straight over
the sharp artwork: at 1766x1104 @1.45 in Bloom a ribbon's black edge ran through the system
card's verdict and read as clipped text. Cards may not carry a shader (test_moos_ui2.py bans
ShaderEffect/MultiEffect there), so the Gaussian blur is baked by
artwork/generate_scene_frost.py and each card only crops it and paints it through Kirigami's
rounded-texture primitive.

This gate holds each half to what makes it true:
  * every scene master has its frost, the frost is that master's blur (pixels compared with
    a fresh in-memory bake, within a tolerance any JPEG encoder meets), and the provenance
    names the master and frost bytes actually shipped — a changed master without new frost
    fails here by name;
  * the card paints the frost only with GPU compositing and a known frost, through
    Kirigami.ShadowedTexture with the shell's own corners, crops it to its settled rectangle,
    and the wallpaper hands the frost of the painted master down to all three cards.
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "system_files/usr/share/plasma/wallpapers/org.moos.ui2.wallpaper/contents/ui"
spec = importlib.util.spec_from_file_location("scene_frost", ROOT / "artwork/generate_scene_frost.py")
frost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frost)


def code(path: Path) -> str:
    return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("//"))


class FrostAssets(unittest.TestCase):
    def test_every_master_has_its_own_frost(self) -> None:
        record = json.loads(frost.PROVENANCE.read_text(encoding="utf-8"))
        masters = frost.masters()
        self.assertGreaterEqual(len(masters), 40, "the scene packages were not found")
        self.assertEqual(sorted(record["files"]),
                         sorted(frost.frost_path(m).relative_to(ROOT).as_posix() for m in masters))
        for master in masters:
            target = frost.frost_path(master)
            rel = target.relative_to(ROOT).as_posix()
            with self.subTest(frost=rel):
                entry = record["files"][rel]
                self.assertEqual(entry["masterSHA256"], frost.sha256(master.read_bytes()),
                                 "the master changed; run artwork/generate_scene_frost.py")
                self.assertEqual(entry["sha256"], frost.sha256(target.read_bytes()))
                with Image.open(target) as shipped:
                    self.assertEqual(list(shipped.size), entry["size"])
                    self.assertEqual(shipped.width, frost.WIDTH)
                    self.assertLess(target.stat().st_size, 48 * 1024)

    def test_frost_is_the_blur_of_its_master(self) -> None:
        for master in frost.masters()[::7]:
            target = frost.frost_path(master)
            with self.subTest(frost=target.name, branch=master.parent.name):
                fresh, size = frost.frost_bytes(master)
                with Image.open(io.BytesIO(fresh)) as a, Image.open(target) as b:
                    self.assertEqual(list(b.size), size)
                    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
                    self.assertLess(max(ImageStat.Stat(diff).mean), 2.0,
                                    "the shipped frost is not this master's blur")

    def test_a_planted_wrong_frost_is_refused(self) -> None:
        masters = frost.masters()
        first, other = masters[0], masters[len(masters) // 2]
        fresh_first, _ = frost.frost_bytes(first)
        with Image.open(io.BytesIO(fresh_first)) as a, Image.open(frost.frost_path(other)) as b:
            b = b.convert("RGB").resize(a.size)
            self.assertGreater(max(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b)).mean), 2.0,
                               "the similarity check cannot tell two scenes apart")


class CardContract(unittest.TestCase):
    def test_card_crops_baked_frost_through_kirigami(self) -> None:
        card = code(HUB / "GlassCard.qml")
        for banned in ("ShaderEffect", "MultiEffect", "QtQuick.Effects"):
            self.assertNotIn(banned, card)
        self.assertIn("Kirigami.ShadowedTexture {", card)
        self.assertIn("source: frostSlice", card)
        self.assertIn("sourceClipRect: card.frostClip", card)
        self.assertIn("radius: shell.radius", card)
        self.assertIn("corners.topLeftRadius: shell.topLeftRadius", card)
        self.assertIn("corners.topRightRadius: shell.topRightRadius", card)
        frosted = re.search(r"readonly property bool frosted:([^\n]+\n[^\n]+)", card).group(1)
        for required in ("backdrop !== null", "backdropFrost", "!integrated", "design.blurActive"):
            self.assertIn(required, frosted)
        # The settled rectangle, never the entrance offset.
        self.assertIn("card.parent.mapToItem(card.backdrop, card.x + shell.x, card.y + shell.y", card)

    def test_wallpaper_hands_the_painted_masters_frost_to_every_card(self) -> None:
        main = code(HUB / "main.qml")
        self.assertIn("readonly property url sceneFrost:", main)
        self.assertIn('"/frost/"', main)
        self.assertIn("sceneBackdrop: art", main)
        self.assertIn("sceneFrost: root.sceneFrost", main)
        bento = code(HUB / "DashboardBento.qml")
        self.assertEqual(bento.count("backdropFrost: root.sceneFrost"), 3)
        self.assertEqual(bento.count("backdrop: root.sceneBackdrop"), 3)
        for name, rid in (("ClockCard", "clockCard"), ("WeatherCard", "weatherCard"),
                          ("SystemCard", "systemCard")):
            text = code(HUB / f"{name}.qml")
            self.assertIn(f"backdropFrost: {rid}.backdropFrost", text, name)
            self.assertIn(f"backdrop: {rid}.backdrop", text, name)


if __name__ == "__main__":
    unittest.main()
