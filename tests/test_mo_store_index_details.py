#!/usr/bin/env python3
"""details/<id>.json: everything an app's own page shows, one small document per app.

The index stays a light list (the window parses it synchronously); screenshots, release
notes, links, languages, requirements and verification live in per-app documents written
with the index generation. The whole set is published at once: `details` is a symlink to
one complete generation directory, swapped with a single rename, so a reader never sees a
half-written set; a cached run reuses it, and a damaged set is rebuilt.

Every run uses a private HOME and private XDG directories.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_details", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()
MEDIA = "https://dl.flathub.org/media/org/example/Rich"


def shot(number: int, *, default: bool = False, sizes=(224, 624, 752, 1248),
         caption: bool = False) -> str:
    images = [f'<image type="source" width="2560" height="1440">{MEDIA}/{number}_orig.png</image>']
    images += [f'<image type="thumbnail" width="{w}" height="{w * 9 // 16}">'
               f'{MEDIA}/{number}_{w}.png</image>' for w in sizes]
    captions = ('<caption>Main window</caption><caption xml:lang="ar">النافذة الرئيسية</caption>'
                if caption else "")
    kind = ' type="default"' if default else ""
    return f"<screenshot{kind}>{captions}{''.join(images)}</screenshot>"


RICH = f"""<components>
  <component type="desktop-application">
    <id>org.example.Rich</id>
    <name>Rich</name>
    <summary>An app with everything</summary>
    <developer><name>Example Studio</name><name xml:lang="ar">استوديو المثال</name></developer>
    <project_license>GPL-3.0-or-later</project_license>
    <url type="homepage">http://www.example.org/rich/</url>
    <url type="bugtracker">https://bugs.example.org/rich</url>
    <url type="vcs-browser">https://code.example.org/rich</url>
    <url type="help">javascript:alert(1)</url>
    <url type="donation">https://192.168.1.10/donate</url>
    <url type="faq">https://example.org/faq</url>
    <keywords><keyword>photo</keyword><keyword xml:lang="ar">صور</keyword>
      <keyword xml:lang="fr">photographie</keyword></keywords>
    <languages><lang percentage="91">de</lang><lang percentage="64">ar</lang></languages>
    <requires><memory>4096</memory><display_length>768</display_length>
      <internet>first-run</internet><control>keyboard</control></requires>
    <recommends><control>pointing</control><control>touch</control></recommends>
    <custom>
      <value key="flathub::verification::verified">true</value>
      <value key="flathub::verification::method">website</value>
      <value key="flathub::verification::website">example.org</value>
    </custom>
    <screenshots>
      {shot(1)}
      {shot(2, sizes=(224, 624))}
      {shot(3, default=True, caption=True)}
      <screenshot><video>{MEDIA}/clip.webm</video></screenshot>
      {shot(4)}{shot(5)}{shot(6)}{shot(7)}{shot(8)}{shot(9)}{shot(10)}
    </screenshots>
    <releases>
      <release version="3.0-beta1" timestamp="1790000000" type="development">
        <description><p>Not shown</p></description></release>
      <release version="2.2" timestamp="1789000000" type="stable">
        <description><p>Faster saving.</p><ul><li>Fix one</li><li>Fix two</li></ul>
          <p xml:lang="ar">حفظ أسرع.</p></description></release>
      <release version="2.1" date="2026-05-01"/>
      <release version="2.0" timestamp="1700000000"/>
      <release version="1.0" timestamp="1600000000"/>
    </releases>
    <bundle type="flatpak">app/org.example.Rich/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>org.example.Plain</id><name>Plain</name>
    <bundle type="flatpak">app/org.example.Plain/x86_64/stable</bundle>
  </component>
</components>"""


class Fixture:
    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        revision = base / "flatpak/appstream/flathub/x86_64" / ("9" * 64)
        revision.mkdir(parents=True)
        self.xml = revision / "appstream.xml"
        self.xml.write_text(RICH, encoding="utf-8")
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": [
            {"id": "page", "source": "moos", "cat": "util", "glyph": "spark", "en": "Page",
             "ar": "صفحة", "install": {"kind": "web", "url": "https://example.org/"}}]}),
            encoding="utf-8")
        self.cache = base / "cache"
        self.output = self.cache / "index.json"

    def run(self, locale: str = "ar") -> dict:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("XDG_")}
        environment.update({"HOME": str(self.home),
                            "XDG_DATA_HOME": str(self.home / ".local/share"),
                            "XDG_CACHE_HOME": str(self.home / ".cache"),
                            "XDG_STATE_HOME": str(self.home / ".local/state"),
                            "XDG_CONFIG_HOME": str(self.home / ".config"),
                            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"})
        result = subprocess.run(
            [sys.executable, str(INDEXER), "--output", str(self.output), "--catalog",
             str(self.catalog), "--appstream-root", str(self.base / "flatpak/appstream"),
             "--installation-root", str(self.base / "flatpak"), "--locale", locale,
             "--engines", "all"],
            text=True, capture_output=True, check=False, env=environment)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(self.output.read_text(encoding="utf-8"))

    def target(self) -> Path:
        return self.cache / os.readlink(self.cache / "details")

    def document(self, app_id: str) -> dict:
        return json.loads((self.cache / "details" / f"{app_id}.json").read_text(
            encoding="utf-8"))


class TheDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.fixture = Fixture(Path(cls.temporary.name))
        cls.index = cls.fixture.run()
        cls.apps = {app["id"]: app for app in cls.index["apps"]}
        cls.rich = cls.fixture.document("org.example.Rich")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_entries_name_their_document(self):
        self.assertEqual(self.apps["org.example.Rich"]["details"],
                         "details/org.example.Rich.json")
        self.assertIsNone(self.apps["page"]["details"])
        self.assertEqual(self.index["stats"]["details_documents"], 2)
        self.assertEqual(self.rich["schema"], 1)
        self.assertEqual(self.rich["id"], "org.example.Rich")

    def test_screenshots_default_first_bounded_and_sized_for_the_window(self):
        shots = self.rich["screenshots"]
        self.assertEqual(len(shots), 8)
        self.assertEqual(shots[0], {
            "thumb": f"{MEDIA}/3_752.png", "full": f"{MEDIA}/3_1248.png",
            "caption": "النافذة الرئيسية", "width": 1248, "height": 702})
        # No 752 or 1248 thumbnail: the nearest thumbnail, and the source as full.
        self.assertEqual((shots[2]["thumb"], shots[2]["full"]),
                         (f"{MEDIA}/2_624.png", f"{MEDIA}/2_orig.png"))
        self.assertEqual((shots[2]["width"], shots[2]["height"]), (2560, 1440))
        self.assertNotIn("caption", shots[1])
        self.assertTrue(all("clip.webm" not in json.dumps(item) for item in shots))
        # The card uses the same picture as the gallery's first.
        self.assertEqual(self.apps["org.example.Rich"]["screenshot"], f"{MEDIA}/3_752.png")

    def test_three_stable_releases_with_dates_and_plain_notes(self):
        self.assertEqual(self.rich["releases"], [
            {"version": "2.2", "date": "2026-09-10", "notes": "حفظ أسرع."},
            {"version": "2.1", "date": "2026-05-01", "notes": ""},
            {"version": "2.0", "date": "2023-11-14", "notes": ""},
        ])
        english = Fixture(Path(self.temporary.name) / "english")
        english.run(locale="en")
        self.assertEqual(english.document("org.example.Rich")["releases"][0]["notes"],
                         "Faster saving.\n\n• Fix one\n• Fix two")

    def test_links_languages_requirements_and_verification(self):
        self.assertEqual(self.rich["urls"], {
            "homepage": "http://www.example.org/rich/",
            "bugtracker": "https://bugs.example.org/rich",
            "source": "https://code.example.org/rich"})
        self.assertEqual(self.rich["keywords"], ["photo", "صور"])
        self.assertEqual(self.rich["languages"], {"ar": 64})
        self.assertEqual(self.rich["requires"], {
            "memory": 4096, "display_length": {"px": 768, "compare": "ge",
                                               "side": "shortest"},
            "internet": "first-run", "controls": ["keyboard"]})
        self.assertEqual(self.rich["recommends"], {"controls": ["pointing", "touch"]})
        self.assertEqual(self.rich["verification"], {"method": "website",
                                                     "website": "example.org"})
        self.assertEqual(self.rich["license"], "GPL-3.0-or-later")
        self.assertEqual(self.rich["developer"], "استوديو المثال")
        plain = self.fixture.document("org.example.Plain")
        self.assertEqual((plain["screenshots"], plain["releases"], plain["urls"],
                          plain["languages"]), ([], [], {}, {}))

    def test_the_set_is_private_to_the_person(self):
        target = self.fixture.target()
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
        for path in target.glob("*.json"):
            with self.subTest(file=path.name):
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


class OneGenerationAtATime(unittest.TestCase):
    def test_publish_reuse_rebuild_and_clean_up(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            fixture.run()
            first = fixture.target()
            self.assertRegex(first.name, r"^details-[0-9a-f]{16}-[0-9a-f]{8}$")
            self.assertTrue((fixture.cache / "details").is_symlink())
            document = first / "org.example.Rich.json"
            written = document.stat().st_mtime_ns

            # An unchanged run reuses the set; so does a run that only sees an
            # install (the refresh path).
            fixture.run()
            self.assertEqual(fixture.target(), first)
            active = fixture.base / "flatpak/app/org.example.Plain/x86_64/stable/active"
            active.mkdir(parents=True)
            (active / "deploy").write_bytes(b"flathub\0fixture")
            refreshed = {app["id"]: app for app in fixture.run()["apps"]}
            self.assertTrue(refreshed["org.example.Plain"]["installed"])
            self.assertEqual(fixture.target(), first)
            self.assertEqual(document.stat().st_mtime_ns, written)

            # New AppStream: a new generation replaces the old one, which is removed.
            fixture.xml.write_text(RICH.replace("Faster saving.", "Even faster."),
                                   encoding="utf-8")
            fixture.run(locale="en")
            second = fixture.target()
            self.assertNotEqual(second, first)
            self.assertFalse(first.exists())
            self.assertIn("Even faster.",
                          fixture.document("org.example.Rich")["releases"][0]["notes"])
            leftovers = [path.name for path in fixture.cache.iterdir()
                         if path.name.startswith(".details") or (
                             path.name.startswith("details-") and path != second)]
            self.assertEqual(leftovers, [])

    def test_a_damaged_or_missing_set_is_rebuilt_even_when_the_index_is_current(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            fixture.run()
            first = fixture.target()
            marker = json.loads((first / ".complete").read_text(encoding="utf-8"))
            (first / f"{marker['sample'][0]}.json").write_bytes(b"")
            fixture.run()
            second = fixture.target()
            self.assertNotEqual(second, first)
            self.assertGreater((second / f"{marker['sample'][0]}.json").stat().st_size, 16)
            (fixture.cache / "details").unlink()
            fixture.run()
            self.assertTrue((fixture.cache / "details").is_symlink())
            self.assertNotEqual(fixture.target(), second)

    def test_a_real_directory_in_the_way_is_moved_aside_and_removed(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            (fixture.cache / "details").mkdir(parents=True)
            (fixture.cache / "details/stale.json").write_text("{}", encoding="utf-8")
            fixture.run()
            self.assertTrue((fixture.cache / "details").is_symlink())
            names = sorted(path.name for path in fixture.cache.iterdir()
                           if path.name.startswith("details"))
            self.assertEqual(len(names), 2)       # the link and its one generation


class BuilderUnits(unittest.TestCase):
    def test_an_abandoned_build_leaves_nothing_and_old_temporaries_are_swept(self):
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw)
            builder = index.DetailsBuilder(cache, "a" * 64)
            builder.write("org.example.One", {"schema": 1})
            builder.discard()
            self.assertEqual(list(cache.iterdir()), [])
            fresh = index.DetailsBuilder(cache, "b" * 64)          # another indexer
            old = index.DetailsBuilder(cache, "c" * 64)
            hour_ago = time.time() - 2 * index.STALE_BUILD_SECONDS
            os.utime(old.directory, (hour_ago, hour_ago))
            index.clean_details(cache, keep=None)
            self.assertTrue(fresh.directory.is_dir())
            self.assertFalse(old.directory.exists())

    def test_a_sample_check_needs_a_marker_of_this_generation(self):
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw)
            builder = index.DetailsBuilder(cache, "d" * 64)
            for number in range(100):
                builder.write(f"org.example.App{number}", {"schema": 1, "id": number})
            generation = builder.finish()
            index.publish_details(cache, generation)
            self.assertTrue(index.details_ready(cache, "d" * 64))
            self.assertFalse(index.details_ready(cache, "e" * 64))
            marker = json.loads((generation / ".complete").read_text(encoding="utf-8"))
            self.assertEqual(marker["files"], 100)
            self.assertLessEqual(len(marker["sample"]), index.DETAILS_SAMPLE)
            self.assertGreater(len(marker["sample"]), 16)
            (generation / ".complete").unlink()
            self.assertFalse(index.details_ready(cache, "d" * 64))


if __name__ == "__main__":
    unittest.main()
