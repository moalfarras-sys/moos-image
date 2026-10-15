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

import contextlib
import errno
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

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


class AFailedBuild(unittest.TestCase):
    """A build that fails on a full disk fails as a whole: it publishes nothing, leaves no
    private .details-…tmp directory, and the last good index and set stay.

    Until 2026-10-15 a FIRST build that failed before its set was complete kept the directory:
    with no `details` link yet, "the published set" and "this build's set" were both None, so
    the clean-up decided the failed set was the published one. Up to 3,321 files (~14 MB)
    stayed for an hour, one more set per failed launch. And a document that could not be
    written was taken for an unreadable AppStream file: the parse stopped there and the apps
    read so far were published as the whole catalogue, kept by every later launch until
    Flathub's metadata changed.

    The set is published before the index that names it is written. Until 2026-10-15 a build
    whose index then failed (the details fit, the index did not: 6.8 MB and 6.0 MB on live
    Flathub data) kept its set published: a first build left one more details-* set per failed
    launch, each holding the space the next launch needed, and a rebuild moved `details` off
    the last good set onto one whose index was never written, while index.json stayed the old
    generation.
    """

    def run_failing(self, fixture: Fixture, where: str) -> int:
        calls = []
        full = OSError(errno.ENOSPC, "No space left on device")
        owner = index.DetailsBuilder
        if where == "document":
            original = index.DetailsBuilder.write

            def failing(builder, app_id, document):
                calls.append(app_id)
                if len(calls) > 1:
                    raise full
                original(builder, app_id, document)
            method = "write"
        elif where == "finish":
            def failing(builder):
                calls.append("finish")
                raise full
            method = "finish"
        elif where == "index":
            # The set is complete and published; the index that names it does not fit.
            original_write = index.atomic_write_json

            def failing(path, payload):
                if path == fixture.output:
                    calls.append("index")
                    raise full
                original_write(path, payload)
            owner, method = index, "atomic_write_json"
        else:
            # The link is swapped, and the disk fails to commit it.
            def failing(directory):
                if not calls:
                    calls.append("link")
                    raise OSError(errno.EIO, "Input/output error")
            owner, method = index, "fsync_directory"

        environment = {"HOME": str(fixture.home),
                       "XDG_DATA_HOME": str(fixture.home / ".local/share"),
                       "XDG_CACHE_HOME": str(fixture.home / ".cache"),
                       "XDG_STATE_HOME": str(fixture.home / ".local/state"),
                       "XDG_CONFIG_HOME": str(fixture.home / ".config"),
                       "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"}
        machine = fixture.base / "machine.json"
        machine.write_text(json.dumps({"arch": "x86_64", "free_bytes": {"apps": 10 ** 12}}),
                           encoding="utf-8")
        with mock.patch.dict(os.environ, environment), \
                mock.patch.object(owner, method, failing), \
                contextlib.redirect_stderr(io.StringIO()):
            code = index.main([
                "--output", str(fixture.output), "--catalog", str(fixture.catalog),
                "--appstream-root", str(fixture.base / "flatpak/appstream"),
                "--installation-root", str(fixture.base / "flatpak"), "--locale", "en",
                "--engines", "all", "--machine", str(machine)])
        self.assertGreater(len(calls), 1 if where == "document" else 0,
                           "the injected failure never happened")
        return code

    @staticmethod
    def leftovers(fixture: Fixture) -> list[str]:
        if not fixture.cache.is_dir():
            return []
        return sorted(path.name for path in fixture.cache.iterdir()
                      if path.name.startswith(".details-"))

    @staticmethod
    def sets(fixture: Fixture) -> list[str]:
        if not fixture.cache.is_dir():
            return []
        return sorted(path.name for path in fixture.cache.iterdir()
                      if path.name.startswith("details-"))

    def test_a_failed_first_build_leaves_nothing_behind(self):
        for where in ("finish", "document", "index", "link"):
            with self.subTest(failure=where), tempfile.TemporaryDirectory() as raw:
                fixture = Fixture(Path(raw))
                for _attempt in range(2):       # each failed launch used to add one more
                    self.assertEqual(self.run_failing(fixture, where), 2)
                    self.assertEqual(self.leftovers(fixture), [])
                    self.assertEqual(self.sets(fixture), [])
                self.assertFalse(os.path.lexists(fixture.cache / "details"),
                                 "a failed build left `details` naming its set")
                self.assertFalse(fixture.output.exists(), "a failed build published an index")

    def test_a_failed_rebuild_keeps_the_last_good_index_and_set(self):
        for where in ("finish", "document", "index", "link"):
            with self.subTest(failure=where), tempfile.TemporaryDirectory() as raw:
                fixture = Fixture(Path(raw))
                good = fixture.run()
                published = fixture.target()
                fixture.xml.write_text(RICH.replace("Faster saving.", "Even faster."),
                                       encoding="utf-8")
                self.assertEqual(self.run_failing(fixture, where), 2)
                self.assertEqual(fixture.target(), published,
                                 "`details` left the set the published index names")
                self.assertTrue((published / ".complete").is_file())
                self.assertEqual(self.leftovers(fixture), [])
                self.assertEqual(self.sets(fixture), [published.name])
                kept = json.loads(fixture.output.read_text(encoding="utf-8"))
                self.assertEqual(kept["generation"], good["generation"])
                self.assertEqual(len(kept["apps"]), len(good["apps"]))
                # The next launch that can write builds this generation as usual.
                rebuilt = fixture.run()
                self.assertNotEqual(rebuilt["generation"]["metadata_token"],
                                    good["generation"]["metadata_token"])
                self.assertEqual(self.sets(fixture), [fixture.target().name])

    def test_an_index_the_disk_refuses_publishes_nothing(self):
        """No mocks: the kernel refuses the index's bytes (EFBIG under RLIMIT_FSIZE) after
        every details document and the set's marker were written."""

        limit = 4096
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))

            def components(note: str) -> str:
                return "<components>\n" + "".join(
                    listed(f"org.example.Small{number}", f"Small {number}{note}")
                    for number in range(8)) + "</components>\n"

            def run(bounded: bool) -> subprocess.CompletedProcess:
                def apply() -> None:
                    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                    if bounded:
                        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
                environment = {key: value for key, value in os.environ.items()
                               if not key.startswith(("XDG_", "FLATPAK_"))}
                environment.update({"HOME": str(fixture.home),
                                    "XDG_DATA_HOME": str(fixture.home / ".local/share"),
                                    "XDG_CACHE_HOME": str(fixture.home / ".cache"),
                                    "XDG_STATE_HOME": str(fixture.home / ".local/state"),
                                    "XDG_CONFIG_HOME": str(fixture.home / ".config"),
                                    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"})
                machine = fixture.base / "machine.json"
                machine.write_text(json.dumps({"arch": "x86_64",
                                               "free_bytes": {"apps": 10 ** 12}}),
                                   encoding="utf-8")
                return subprocess.run(
                    [sys.executable, str(INDEXER), "--output", str(fixture.output),
                     "--catalog", str(fixture.catalog), "--appstream-root",
                     str(fixture.base / "flatpak/appstream"), "--installation-root",
                     str(fixture.base / "flatpak"), "--locale", "en", "--engines", "all",
                     "--machine", str(machine)],
                    env=environment, capture_output=True, text=True, check=False,
                    preexec_fn=apply)

            fixture.xml.write_text(components(""), encoding="utf-8")
            for _attempt in range(2):
                refused = run(bounded=True)
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertIn("File too large", refused.stderr)
                self.assertEqual((self.sets(fixture), self.leftovers(fixture)), ([], []))
                self.assertFalse(os.path.lexists(fixture.cache / "details"))
                self.assertFalse(fixture.output.exists())
            good = run(bounded=False)
            self.assertEqual(good.returncode, 0, good.stderr)
            published = fixture.target()
            self.assertTrue(all(path.stat().st_size < limit for path in published.iterdir()),
                            "a details document is too big for this check")
            self.assertGreater(fixture.output.stat().st_size, limit)
            generation = json.loads(fixture.output.read_text(encoding="utf-8"))["generation"]
            fixture.xml.write_text(components(" again"), encoding="utf-8")
            refused = run(bounded=True)
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertEqual(fixture.target(), published)
            self.assertEqual(self.sets(fixture), [published.name])
            self.assertEqual(self.leftovers(fixture), [])
            self.assertEqual(json.loads(fixture.output.read_text(encoding="utf-8"))["generation"],
                             generation)


# A valid Flatpak id may have 255 characters; `<id>.json` must fit in a 255-byte file name.
LONG_ID = "org.example." + "a" * 240


def listed(app_id: str, name: str) -> str:
    return (f'  <component type="desktop-application"><id>{app_id}</id><name>{name}</name>'
            f"<summary>An app</summary><bundle type=\"flatpak\">app/{app_id}/x86_64/stable"
            "</bundle></component>\n")


class ADocumentThatCannotBeAFile(unittest.TestCase):
    """One app whose details cannot be a file loses its own details, not the catalogue.

    A full disk fails the build as a whole (AFailedBuild), but a name too long for a file fails
    for that one app on every build. Until 2026-10-15 it failed them all the same way: exit 2
    and no index at all, on every launch; before that, the parse stopped at the app and the
    apps read so far were published as the whole catalogue (2 of 7).
    """

    def test_the_app_is_listed_without_details_and_every_other_one_is_whole(self):
        self.assertEqual(len(LONG_ID), 252)
        self.assertTrue(index.valid_flatpak_id(LONG_ID))
        after = [f"org.example.After{number}" for number in range(5)]
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            fixture.xml.write_text(
                "<components>\n" + listed("org.example.First", "First")
                + listed(LONG_ID, "Long") + "".join(listed(app_id, app_id) for app_id in after)
                + "</components>\n", encoding="utf-8")
            built = fixture.run()
            apps = {app["id"]: app for app in built["apps"]}
            self.assertIsNone(apps[LONG_ID]["details"])
            for app_id in ["org.example.First", *after]:
                with self.subTest(app=app_id):
                    self.assertEqual(apps[app_id]["details"], f"details/{app_id}.json")
                    self.assertEqual(fixture.document(app_id)["id"], app_id)
            self.assertEqual({source["error"] for source in built["sources"]}, {None})
            self.assertEqual(built["stats"]["details_documents"], 6)
            self.assertTrue(index.details_ready(fixture.cache,
                                                built["generation"]["metadata_token"]))
            # The next launch reuses it as it is.
            self.assertEqual(fixture.run()["generation"], built["generation"])

    def test_the_writer_skips_only_that_name(self):
        with tempfile.TemporaryDirectory() as raw:
            builder = index.DetailsBuilder(Path(raw), "f" * 64)
            self.assertFalse(builder.write(LONG_ID, {"schema": 1}))
            self.assertTrue(builder.write("org.example.Short", {"schema": 1}))
            self.assertEqual(builder.written, {"org.example.Short"})
            self.assertEqual(sorted(path.name for path in builder.directory.iterdir()),
                             ["org.example.Short.json"])
            # Anything else is the disk's or the directory's: it still fails the build.
            builder.discard()
            with self.assertRaises(OSError):
                builder.write("org.example.Gone", {"schema": 1})


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

    def test_the_link_goes_back_or_stays_on_a_set_that_exists(self):
        with tempfile.TemporaryDirectory() as raw:
            cache = Path(raw)
            sets = []
            for token in ("a" * 64, "b" * 64):
                builder = index.DetailsBuilder(cache, token)
                builder.write("org.example.One", {"schema": 1})
                sets.append(builder.finish())
            older, newer = sets
            index.publish_details(cache, newer)
            index.unpublish_details(cache, older, None)     # names another set: left alone
            self.assertEqual(index.details_target(cache), newer)
            with mock.patch.object(index, "publish_details",
                                   side_effect=OSError(errno.ENOSPC, "No space left")):
                index.unpublish_details(cache, newer, older)
            self.assertEqual(index.details_target(cache), newer,
                             "a link that could not go back must keep naming a set")
            index.unpublish_details(cache, newer, older)
            self.assertEqual(index.details_target(cache), older)
            index.publish_details(cache, newer)
            index.unpublish_details(cache, newer, None)     # a first build: no link at all
            self.assertFalse(os.path.lexists(cache / index.DETAILS_LINK))

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
