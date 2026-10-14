#!/usr/bin/env python3
"""Mo Store's low_disk verdict: what an install really needs, and never a stale answer.

  Footprint   a pinned install keeps its download while it unpacks beside it, and an AppImage or
              an Android package is copied once more first. The verdict counted the download
              alone: Antigravity's 181 MB archive unpacks to 518 MB, so with 400 MB free it said
              "ok" and the install filled the disk partway through. needs.size is now the
              download and its unpacked tree, needs.copy the extra copy (free where the home's
              filesystem shares extents), checked here against every pin measured on the
              station (2026-10-15).
  NeverStale  a cached index is reused only while free space stays inside the range its
              verdicts hold for. The context token carried free space as a power-of-two bucket
              of GiB, so freeing 200 MB inside one bucket left an app blocked (and filling the
              disk left an "ok") until something else changed. Every cached run here must equal
              a fresh build for the same machine, and a change that flips no verdict must still
              be a header read that rewrites nothing.

Index runs use a private HOME, private XDG directories and --machine fixtures.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_disk", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()
MIB = 1024 ** 2
ARCH = index.running_arch()
REVIEW = {"external": True, "risk": "downloaded-executable", "requires_review": True}


def entry(app_id: str, kind: str, size: int, **install) -> dict:
    """A catalogue entry pinning `size` bytes for every architecture it may run on."""
    recipe = {"kind": kind, **REVIEW, **install}
    if kind == "android":
        recipe.update(url=f"https://example.org/{app_id}.apk", sha256="a" * 64, package=app_id,
                      size=size)
    else:
        arches = ("x86_64",) if kind == "windows-portable" else ("x86_64", "aarch64")
        recipe["downloads"] = {arch: {"url": f"https://example.org/{app_id}-{arch}",
                                      "sha256": "a" * 64, "size": size} for arch in arches}
    extra = {"engine": "windows"} if kind == "windows-portable" else {}
    return {"id": app_id, "source": "moos", "cat": "util", "glyph": "spark",
            "en": app_id.title(), "ar": "تطبيق", **extra, "install": recipe}


def indexed(raw: dict) -> dict:
    """The index entry of one catalogue entry, as a build without AppStream data writes it."""
    clean = index.sanitize_catalog_app(raw)
    return index.finish_app(index.catalog_fallback_app(clean, ["en"], "x86_64"))


def machine(free: int | None, *, reflink=True, template=True) -> dict:
    return {"arch": ARCH, "engines": ["android", "linux", "windows"],
            "free_bytes": {"apps": free}, "memory_bytes": 16 * 1024 ** 3,
            "android": {"ready": True, "initialized": True, "graphics": "hardware"},
            "windows": {"ready": True, "x86_32": False, "reflink": reflink, "template": template}}


def verdict(app: dict, free: int, **facts) -> str:
    return index.compat_verdict(app, machine(free, **facts), None)["verdict"]


# Measured on the station, 2026-10-15: each pinned x86_64 file (SHA-256 verified against the
# catalogue), unpacked with App Drop's own extractors or unsquashfs onto btrfs; allocated bytes.
MEASURED = {
    # id: (kind, artifact, download, unpacked tree)
    "photocraft": ("appdrop", "appimage", 77_478_392, 162_701_312),
    "cursor": ("appdrop", "appimage", 306_850_296, 1_061_199_872),
    "lmstudio": ("appdrop", "appimage", 1_021_758_187, 2_378_805_248),
    "antigravity": ("appdrop", "archive", 181_083_164, 519_606_272),
    "antigravity-ide": ("appdrop", "archive", 240_837_095, 800_714_752),
    "heidisql": ("windows-portable", None, 29_789_003, 82_673_664),
    "notepad-plus-plus": ("windows-portable", None, 8_250_001, 27_615_232),
    "notepad3": ("windows-portable", None, 6_868_273, 22_257_664),
    "sumatrapdf": ("windows-portable", None, 10_031_830, 20_295_680),
    "winmerge": ("windows-portable", None, 24_493_933, 82_726_912),
}


class Footprint(unittest.TestCase):
    def app(self, app_id: str) -> dict:
        kind, artifact, download, _tree = MEASURED[app_id]
        install = {"artifact": artifact} if artifact else {"exe": "app/app.exe"}
        return indexed(entry(app_id, kind, download, **install))

    def test_every_measured_pin_fits_its_estimate(self):
        for app_id, (_kind, artifact, download, tree) in MEASURED.items():
            app = self.app(app_id)
            for shared in (True, False):
                # The download stays until the job ends; an AppImage is copied into App Drop's
                # staging folder first, which costs nothing only where extents are shared.
                peak = download + tree + (download if artifact == "appimage" and not shared else 0)
                extra = index.windows_settings_bytes(machine(0, reflink=shared))
                need = index.install_need(app, machine(0, reflink=shared))
                if app["kind"] == "windows":
                    need -= extra
                with self.subTest(app=app_id, shared=shared):
                    self.assertGreaterEqual(need, peak)
                    self.assertLessEqual(need, 2 * peak, "an estimate this loose blocks for nothing")

    def test_the_needs_of_each_kind(self):
        size = 10 * MIB
        self.assertEqual(indexed(entry("tool", "appdrop", size, artifact="archive"))["needs"],
                         {"size": 5 * size})
        self.assertEqual(indexed(entry("tool", "appdrop", size, artifact="appimage"))["needs"],
                         {"size": 5 * size, "copy": size})
        self.assertEqual(indexed(entry("org.example.droid", "android", size))["needs"],
                         {"size": 5 * size, "copy": size})
        self.assertEqual(indexed(entry("tool", "windows-portable", size,
                                       exe="app/app.exe"))["needs"], {"size": 5 * size})
        page = indexed({"id": "page", "source": "moos", "cat": "util", "glyph": "spark",
                        "en": "Page", "ar": "صفحة",
                        "install": {"kind": "web", "url": "https://example.org/"}})
        self.assertNotIn("needs", page)

    def test_the_reported_installs_no_longer_start_on_a_disk_too_small(self):
        antigravity, lmstudio, heidisql = (self.app(name) for name in
                                           ("antigravity", "lmstudio", "heidisql"))
        # Antigravity: 181 MB to download, 700 MB at its peak.
        self.assertEqual(verdict(antigravity, 400 * 1000 ** 2), "blocked")
        self.assertEqual(verdict(antigravity, 1000 ** 3), "ok")
        # LM Studio: 1.02 GB AppImage, 3.4 GB at its peak on btrfs, 4.4 GB elsewhere.
        self.assertEqual(verdict(lmstudio, 1100 * 1000 ** 2), "blocked")
        self.assertEqual(verdict(lmstudio, 5500 * 1000 ** 2, reflink=True), "ok")
        self.assertEqual(verdict(lmstudio, 5500 * 1000 ** 2, reflink=False), "blocked")
        # HeidiSQL's 30 MB zip unpacks to 83 MB: 100 MB is not enough even with the template.
        self.assertEqual(verdict(heidisql, 100 * 1000 ** 2), "blocked")
        self.assertEqual(verdict(heidisql, 200 * 1000 ** 2), "ok")
        # An installed app is never judged on its install size.
        self.assertEqual(verdict(dict(antigravity, installed=True), 1), "ok")


APPSTREAM = """<components>
  <component type="desktop-application"><id>org.example.Sized</id><name>Sized</name>
    <size type="download">314572800</size><size type="installed">734003200</size>
    <custom><value key="flathub::verification::verified">true</value></custom>
    <bundle type="flatpak">app/org.example.Sized/x86_64/stable</bundle></component>
</components>"""
CATALOG = [entry("tool", "appdrop", 500 * MIB, artifact="archive", version="1.0"),
           entry("image", "appdrop", 300 * MIB, artifact="appimage", version="1.0"),
           entry("org.example.droid", "android", 100 * MIB, version="1.0"),
           entry("notepad", "windows-portable", 10 * MIB, exe="app/app.exe", version="1.0")]


class Fixture:
    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        revision = base / "flatpak/appstream/flathub/x86_64" / ("f" * 64)
        revision.mkdir(parents=True)
        (revision / "appstream.xml").write_text(APPSTREAM, encoding="utf-8")
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": CATALOG}), encoding="utf-8")
        self.machine_file = base / "machine.json"
        self.environment = {
            "HOME": str(self.home), "XDG_DATA_HOME": str(self.home / ".local/share"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_STATE_HOME": str(self.home / ".local/state"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"}

    def argv(self, output: Path) -> list[str]:
        return ["--output", str(output), "--catalog", str(self.catalog),
                "--appstream-root", str(self.base / "flatpak/appstream"),
                "--installation-root", str(self.base / "flatpak"), "--locale", "en",
                "--engines", "all", "--machine", str(self.machine_file)]

    def run(self, output: Path, free: int) -> dict:
        self.machine_file.write_text(json.dumps(machine(free)), encoding="utf-8")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("XDG_", "FLATPAK_"))}
        environment.update(self.environment)
        result = subprocess.run([sys.executable, str(INDEXER), *self.argv(output)],
                                text=True, capture_output=True, check=False, env=environment)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(output.read_text(encoding="utf-8"))


def verdicts(data: dict) -> dict:
    return {app["id"]: app["compat"] for app in data["apps"]}


class NeverStale(unittest.TestCase):
    # Free space, MiB, as a person frees and fills the disk: crossings of the needs below and
    # moves that cross none, several inside one power-of-two GiB bucket.
    STEPS = (400, 600, 900, 1100, 1450, 1550, 2400, 2600, 5000, 5100, 2450, 450)

    def test_a_cached_index_always_says_what_a_fresh_build_says(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            cached = fixture.base / "cache/index.json"
            for number, free_mib in enumerate(self.STEPS):
                free = free_mib * MIB
                before = cached.stat().st_mtime_ns if cached.exists() else None
                reused = fixture.run(cached, free)
                fresh = fixture.run(fixture.base / f"fresh-{number}/index.json", free)
                with self.subTest(free_mib=free_mib):
                    self.assertEqual(verdicts(reused), verdicts(fresh),
                                     "a cached index served verdicts a fresh build does not give")
                    self.assertEqual(reused["stats"]["compat_blocked"],
                                     fresh["stats"]["compat_blocked"])
                    self.assertEqual(reused["generation"]["metadata_token"],
                                     fresh["generation"]["metadata_token"])
                    if before is not None and verdicts(reused) == previous:
                        self.assertEqual(cached.stat().st_mtime_ns, before,
                                         "free space that flips no verdict rewrote the index")
                previous = verdicts(reused)

    def test_the_range_holds_exactly_the_free_space_the_verdicts_hold_for(self):
        apps = [indexed(raw) for raw in CATALOG]
        for free_mib in (0, 50, 51, 52, 499, 500, 1499, 1500, 2499, 2500, 10 ** 6):
            free = free_mib * MIB
            low, high = index.free_space_range(apps, machine(free))
            here = [index.compat_verdict(app, machine(free), None) for app in apps]
            with self.subTest(free_mib=free_mib):
                self.assertLessEqual(low, free)
                self.assertTrue(high is None or free < high)
                for probe in (low, free, (high - 1) if high is not None else free * 2):
                    self.assertEqual([index.compat_verdict(app, machine(probe), None)
                                      for app in apps], here)
                if high is not None:
                    self.assertNotEqual([index.compat_verdict(app, machine(high), None)
                                         for app in apps], here)
        self.assertIsNone(index.free_space_range(apps, machine(None)))


class TheEarlyReturnStaysEarly(unittest.TestCase):
    def test_moving_inside_the_range_reads_only_the_header(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            output = fixture.base / "cache/index.json"
            calls = []
            original = index.load_refreshable_output

            def counting(*args):
                calls.append(args)
                return original(*args)

            def run(free_mib: int) -> int:
                fixture.machine_file.write_text(json.dumps(machine(free_mib * MIB)),
                                                encoding="utf-8")
                with mock.patch.dict(os.environ, fixture.environment), \
                        mock.patch.object(index, "load_refreshable_output", counting), \
                        contextlib.redirect_stderr(io.StringIO()):
                    return index.main(fixture.argv(output))

            self.assertEqual(run(600), 0)                 # a full build
            self.assertEqual((run(700), run(990), len(calls)), (0, 0, 0))
            self.assertEqual((run(1100), len(calls)), (0, 1))   # Sized now fits: refreshed
            self.assertEqual((run(1200), len(calls)), (0, 1))


if __name__ == "__main__":
    unittest.main()
