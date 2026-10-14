#!/usr/bin/env python3
"""An app's age label (`content_rating`) is the age its OARS rating means.

OARS intensity is graded per attribute: `social-chat: intense` (unmoderated chat) is age 13,
`violence-cartoon: intense` 6, `violence-bloodshed: intense` 18. The index used to read only
the word, so any `intense` was "mature" and any `moderate` "teen": 323 of Flathub's 362
"Adults only" apps had an OARS age under 16 (SuperTuxKart, tagged for children in the
catalogue, and Signal, Telegram and Discord among them), while `sex-themes: mild` (13) read
"Suitable for everyone".

The age is libappstream's, the reference KDE Discover and GNOME Software show: the highest of
the attributes' minimum ages from its OARS-to-CSM table. The index copies that table
(OARS_CSM_AGES) so it needs no library; where the host has libappstream through GObject
introspection, the copy is checked against it. The bands: under 13 "all", 13-17 "teen",
18 "mature"; no OARS rating is null ("unrated" is not "all ages").

Pure functions only; nothing is read from or written to the home.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_rating", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()


def appstream():
    """libappstream through GObject introspection, or None where it is not installed."""
    try:
        import gi
        gi.require_version("AppStream", "1.0")
        from gi.repository import AppStream
    except (ImportError, AttributeError, ValueError):
        return None
    return AppStream


def component(rating: str) -> ET.Element:
    return ET.fromstring(f"<component><id>org.example.App</id>{rating}</component>")


def oars(*attributes: tuple[str, str], kind: str = "oars-1.1") -> str:
    inner = "".join(f'<content_attribute id="{key}">{value}</content_attribute>'
                    for key, value in attributes)
    return f'<content_rating type="{kind}">{inner}</content_rating>'


# Real Flathub ratings (live AppStream, 2026-10-14) and the age libappstream 1.1.3 gives each.
REAL = {
    "SuperTuxKart": ([("violence-cartoon", "mild"), ("social-chat", "intense")], 13, "teen"),
    "Signal": ([("social-chat", "intense"), ("social-audio", "intense"),
                ("social-contacts", "intense")], 15, "teen"),
    "a cartoon brawler": ([("violence-cartoon", "moderate")], 4, "all"),
    "a donation button": ([("money-purchasing", "mild")], 12, "all"),
    "a romance": ([("sex-themes", "mild")], 13, "teen"),
    "a dungeon crawl": ([("violence-fantasy", "intense"), ("language-humor", "moderate")],
                        8, "all"),
    "a shooter": ([("violence-realistic", "intense"), ("language-profanity", "moderate")],
                  14, "teen"),
    "a narcotics drama": ([("drugs-narcotics", "intense")], 17, "teen"),
    "a gore fest": ([("violence-bloodshed", "intense"), ("social-chat", "mild")], 18, "mature"),
    "a casino": ([("money-gambling", "intense")], 18, "mature"),
}


class TheBands(unittest.TestCase):
    def test_real_ratings_get_their_age_band(self):
        for label, (attributes, _age, band) in REAL.items():
            with self.subTest(app=label):
                self.assertEqual(index.content_rating(component(oars(*attributes))), band)

    def test_the_band_edges(self):
        for age, band in ((0, "all"), (12, "all"), (13, "teen"), (17, "teen"), (18, "mature")):
            with self.subTest(age=age):
                self.assertEqual(index.content_age_band(age), band)

    def test_unrated_and_unknown(self):
        self.assertIsNone(index.content_rating(component("")))
        self.assertEqual(index.content_rating(component(oars())), "all")
        self.assertEqual(index.content_rating(component(oars(kind="oars-1.0"))), "all")
        self.assertEqual(index.content_rating(component(oars(("violence-bloodshed", "none")))),
                         "all")
        # An attribute or a word OARS does not define says nothing.
        self.assertEqual(index.content_rating(component(oars(("no-such-thing", "intense")))),
                         "all")
        self.assertEqual(index.content_rating(component(oars(("violence-bloodshed", "extreme")))),
                         "all")
        # A rating system that is not OARS has no age here, as in libappstream.
        self.assertIsNone(index.content_rating(component(
            oars(("violence-bloodshed", "intense"), kind="esrb"))))
        self.assertIsNone(index.content_rating(component(
            '<content_rating><content_attribute id="violence-bloodshed">intense'
            "</content_attribute></content_rating>")))

    def test_every_attribute_and_intensity_is_known(self):
        self.assertEqual(len(index.OARS_CSM_AGES), 28)
        for attribute, ages in index.OARS_CSM_AGES.items():
            with self.subTest(attribute=attribute):
                self.assertEqual(len(ages), 4)
                self.assertEqual(ages[0], 0, "none is never an age")
                self.assertEqual(list(ages), sorted(ages), "intensity never lowers the age")


@unittest.skipIf(appstream() is None, "libappstream (GObject introspection) is not installed here")
class TheCopyIsLibappstreams(unittest.TestCase):
    def test_the_table_matches_the_library(self):
        library = appstream()
        values = library.ContentRatingValue
        self.assertEqual(set(index.OARS_CSM_AGES),
                         set(library.ContentRating.get_all_rating_ids()))
        for attribute, ages in index.OARS_CSM_AGES.items():
            for intensity, value in zip(("none", "mild", "moderate", "intense"),
                                        (values.NONE, values.MILD, values.MODERATE,
                                         values.INTENSE)):
                with self.subTest(attribute=attribute, intensity=intensity):
                    self.assertEqual(
                        ages[("none", "mild", "moderate", "intense").index(intensity)],
                        library.ContentRating.attribute_to_csm_age(attribute, value))

    def test_the_real_ratings_have_the_librarys_age(self):
        library = appstream()
        for label, (attributes, age, _band) in REAL.items():
            with self.subTest(app=label):
                rating = library.ContentRating.new()
                rating.set_kind("oars-1.1")
                for attribute, intensity in attributes:
                    rating.add_attribute(attribute,
                                         getattr(library.ContentRatingValue, intensity.upper()))
                self.assertEqual(rating.get_minimum_age(), age)


if __name__ == "__main__":
    unittest.main()
