#!/usr/bin/env python3
"""Will this app work well on THIS machine? Mo Store's compatibility verdicts.

compat_verdict(app, machine.json, facts.json) is pure, so every rule is proven here on
fixture machines: `blocked` for no build for this architecture, a missing engine, a pinned
download that does not fit, or an end-of-life app not yet installed; `warn` for Android
setup or software graphics, too little memory, a screen smaller than the app needs, an app
that needs the internet, an X11-only app on a fractionally scaled screen, broad permissions,
a download from the vendor at install time, and an unverified Flatpak. An installed app is
never blocked.

low_disk, what an install really needs, and never a stale answer:

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
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_compat", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()
GIB = 1024 ** 3

DESKTOP = {
    "arch": "x86_64", "engines": ["android", "linux", "windows"],
    "memory_bytes": 16 * GIB, "swap_bytes": 8 * GIB, "cpu_cores": 16,
    "gpu": {"vendor": "nvidia", "name": "RTX", "discrete": True}, "session": "wayland",
    "free_bytes": {"apps": 140 * GIB},
    "android": {"ready": True, "initialized": True, "graphics": "hardware"},
    "windows": {"ready": True, "x86_32": False},
    "screen": {"width": 3840, "height": 2160, "scale": 2.5},
}


def machine(**changes) -> dict:
    document = json.loads(json.dumps(DESKTOP))
    for key, value in changes.items():
        document[key] = value
    return document


def flatpak(app_id: str = "org.example.App", **extra) -> dict:
    app = {"id": app_id, "kind": "flatpak", "source": "flatpak", "arch": "x86_64",
           "verified": True, "installed": False, "eol": False}
    app.update(extra)
    return app


def verdict(app: dict, on: dict | None = None, facts: dict | None = None) -> tuple:
    result = index.compat_verdict(app, DESKTOP if on is None else on, facts)
    return result["verdict"], result["reasons"]


class Blocked(unittest.TestCase):
    def test_no_build_for_this_architecture(self):
        app = {"id": "tool", "kind": "appdrop", "arch": ["aarch64"], "installed": False}
        self.assertEqual(verdict(app), ("blocked", ["arch"]))
        self.assertEqual(verdict(dict(app, installed=True)), ("warn", ["arch"]))
        self.assertEqual(verdict(flatpak(arch="aarch64")), ("blocked", ["arch"]))

    def test_the_engine_is_missing(self):
        app = {"id": "org.example.droid", "kind": "android", "engine": "android",
               "installed": False}
        self.assertEqual(verdict(app, machine(engines=["linux"])),
                         ("blocked", ["engine_missing"]))
        windows = {"id": "notepad", "kind": "windows", "installed": False}
        self.assertEqual(verdict(windows, machine(engines=["linux", "android"])),
                         ("blocked", ["engine_missing"]))

    def test_a_pinned_download_that_does_not_fit(self):
        app = {"id": "tool", "kind": "appdrop", "installed": False,
               "needs": {"size": 3 * GIB}}
        self.assertEqual(verdict(app, machine(free_bytes={"apps": 2 * GIB})),
                         ("blocked", ["low_disk"]))
        self.assertEqual(verdict(app, machine(free_bytes={"apps": 4 * GIB})), ("ok", []))
        self.assertEqual(verdict(dict(app, installed=True),
                                 machine(free_bytes={"apps": 2 * GIB})), ("ok", []))

    def test_end_of_life_blocks_a_new_install_and_warns_an_installed_one(self):
        self.assertEqual(verdict(flatpak(eol=True)), ("blocked", ["eol"]))
        self.assertEqual(verdict(flatpak(eol=True, installed=True)), ("warn", ["eol"]))


class Warnings(unittest.TestCase):
    def test_android_needs_its_one_time_setup_and_draws_in_software_on_nvidia(self):
        app = {"id": "org.example.droid", "kind": "android", "installed": False}
        self.assertEqual(
            verdict(app, machine(android={"ready": True, "initialized": False,
                                          "graphics": "software"})),
            ("warn", ["android_setup", "android_software_graphics"]))
        self.assertEqual(verdict(app), ("ok", []))

    def test_too_little_memory(self):
        self.assertEqual(verdict(flatpak(needs={"memory": 32768})), ("warn", ["low_memory"]))
        self.assertEqual(verdict(flatpak(needs={"memory": 8192})), ("ok", []))

    def test_a_screen_smaller_than_the_app_needs(self):
        needs = {"display": {"px": 768, "compare": "ge", "side": "shortest"}}
        laptop = machine(screen={"width": 1280, "height": 720, "scale": 1.0})
        exact = machine(screen={"width": 1366, "height": 768, "scale": 1.0})
        self.assertEqual(verdict(flatpak(needs=needs), laptop), ("warn", ["small_screen"]))
        self.assertEqual(verdict(flatpak(needs=needs), exact), ("ok", []))
        # 3840x2160 at 2.5 is 1536x864 logical: enough.
        self.assertEqual(verdict(flatpak(needs=needs)), ("ok", []))
        longest = {"display": {"px": 1600, "compare": "ge", "side": "longest"}}
        self.assertEqual(verdict(flatpak(needs=longest)), ("warn", ["small_screen"]))
        strictly = {"display": {"px": 864, "compare": "gt", "side": "shortest"}}
        self.assertEqual(verdict(flatpak(needs=strictly)), ("warn", ["small_screen"]))
        upper_bound = {"display": {"px": 600, "compare": "le", "side": "shortest"}}
        self.assertEqual(verdict(flatpak(needs=upper_bound)), ("ok", []))
        self.assertEqual(verdict(flatpak(needs=needs), machine(screen=None)), ("ok", []))

    def test_the_internet(self):
        self.assertEqual(verdict(flatpak(needs={"internet": "always"})),
                         ("warn", ["needs_internet"]))
        self.assertEqual(verdict({"id": "chat", "kind": "webapp", "installed": False}),
                         ("warn", ["needs_internet"]))

    def test_facts_from_the_flathub_summary(self):
        facts = {"org.example.App": {"eol": False, "x11_only": True, "extra_data": True,
                                     "broad": True}}
        self.assertEqual(verdict(flatpak(), facts=facts),
                         ("warn", ["x11_only_scaled", "broad_permissions", "vendor_download"]))
        # Whole-number scale and X11 sessions are not the fractional-scaling case.
        for screen, session in (({"width": 3840, "height": 2160, "scale": 2.0}, "wayland"),
                                ({"width": 3840, "height": 2160, "scale": 2.5}, "x11")):
            with self.subTest(screen=screen, session=session):
                self.assertEqual(
                    verdict(flatpak(), machine(screen=screen, session=session), facts),
                    ("warn", ["broad_permissions", "vendor_download"]))
        # Facts describe Flathub apps only.
        self.assertEqual(verdict({"id": "org.example.App", "kind": "android",
                                  "installed": False}, facts=facts), ("ok", []))

    def test_an_unverified_flatpak(self):
        self.assertEqual(verdict(flatpak(verified=False)), ("warn", ["not_verified"]))
        self.assertEqual(verdict({"id": "tool", "kind": "appdrop", "verified": False,
                                  "installed": False}), ("ok", []))


class Shape(unittest.TestCase):
    def test_reasons_follow_the_contracts_order_and_blocked_wins(self):
        app = flatpak(verified=False, eol=True, needs={"memory": 99999, "internet": "always"},
                      arch="aarch64")
        result = index.compat_verdict(app, DESKTOP, {"org.example.App": {
            "eol": True, "x11_only": True, "extra_data": True, "broad": True}})
        self.assertEqual(result["verdict"], "blocked")
        self.assertEqual(result["reasons"],
                         [reason for reason in index.COMPAT_ORDER
                          if reason in set(result["reasons"])])
        self.assertEqual(set(result["reasons"]), {
            "arch", "low_memory", "needs_internet", "x11_only_scaled", "eol",
            "broad_permissions", "vendor_download", "not_verified"})

    def test_an_unknown_machine_only_reports_what_the_app_itself_says(self):
        self.assertEqual(index.compat_verdict(flatpak(verified=False, needs={
            "memory": 99999, "size": 10 ** 15}), None, None),
            {"verdict": "warn", "reasons": ["not_verified"]})
        self.assertEqual(index.compat_verdict(flatpak(), {}, None),
                         {"verdict": "ok", "reasons": []})


class Relations(unittest.TestCase):
    def test_requires_and_recommends_are_read(self):
        component = ET.fromstring("""<component>
          <requires><display_length>small</display_length><internet>always</internet>
            <memory>4096</memory><control>keyboard</control><control>pointing</control>
            <control>telepathy</control></requires>
          <recommends><display_length compare="gt" side="longest">1200</display_length>
            <control>touch</control></recommends>
          <size type="download">1000</size><size type="installed">3000</size>
        </component>""")
        self.assertEqual(index.component_relations(component, "requires"), {
            "display_length": {"px": 420, "compare": "ge", "side": "shortest"},
            "internet": "always", "memory": 4096, "controls": ["keyboard", "pointing"]})
        self.assertEqual(index.component_relations(component, "recommends"), {
            "display_length": {"px": 1200, "compare": "gt", "side": "longest"},
            "controls": ["touch"]})
        self.assertEqual(index.component_needs(component), {
            "memory": 4096, "display": {"px": 420, "compare": "ge", "side": "shortest"},
            "internet": "always", "size": 4000})


class Facts(unittest.TestCase):
    def test_facts_are_reduced_to_what_a_verdict_reads(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "facts.json"
            path.write_text(json.dumps({"schema": 1, "generated_at": "now", "apps": {
                "org.example.Big": {"download": 1, "installed": 2, "eol": "Retired",
                                    "permissions": ["network", "files-all"],
                                    "x11_only": True, "extra_data": False},
                "org.example.Small": {"permissions": ["devices"], "extra_data": True},
                "not a flatpak id": {"eol": True},
                "org.example.Odd": "not an object",
            }}), encoding="utf-8")
            facts = index.read_facts(path)
            self.assertEqual(facts, {
                "org.example.Big": {"eol": True, "x11_only": True, "extra_data": False,
                                    "broad": True},
                "org.example.Small": {"eol": False, "x11_only": False, "extra_data": True,
                                      "broad": True}})
            path.write_text("{broken", encoding="utf-8")
            self.assertIsNone(index.read_facts(path))
            self.assertIsNone(index.read_facts(Path(raw) / "missing.json"))


APPSTREAM = """<components>
  <component type="desktop-application"><id>org.example.Verified</id><name>Verified</name>
    <custom><value key="flathub::verification::verified">true</value></custom>
    <bundle type="flatpak">app/org.example.Verified/x86_64/stable</bundle></component>
  <component type="desktop-application"><id>org.example.Wide</id><name>Wide</name>
    <requires><display_length>1200</display_length></requires>
    <custom><value key="flathub::verification::verified">true</value></custom>
    <bundle type="flatpak">app/org.example.Wide/x86_64/stable</bundle></component>
  <component type="desktop-application"><id>org.example.Old</id><name>Old</name>
    <custom><value key="flathub::verification::verified">true</value></custom>
    <bundle type="flatpak">app/org.example.Old/x86_64/stable</bundle></component>
</components>"""


class IndexCarriesVerdicts(unittest.TestCase):
    def run_index(self, base: Path, facts: dict, machine_document: dict) -> dict:
        revision = base / "flatpak/appstream/flathub/x86_64" / ("f" * 64)
        revision.mkdir(parents=True, exist_ok=True)
        xml = revision / "appstream.xml"
        if not xml.exists():
            xml.write_text(APPSTREAM, encoding="utf-8")
        catalog = base / "catalog.json"
        catalog.write_text(json.dumps({"apps": [
            {"id": "org.example.droid", "source": "moos", "cat": "droid", "glyph": "grid",
             "en": "Droid", "ar": "درويد", "engine": "android",
             "install": {"kind": "android", "url": "https://example.org/d.apk",
                         "sha256": "a" * 64, "package": "org.example.droid", "size": 5000}}]}),
            encoding="utf-8")
        output = base / "cache/index.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        (output.parent / "facts.json").write_text(json.dumps({"schema": 1, "apps": facts}),
                                                  encoding="utf-8")
        machine_file = base / "machine.json"
        machine_file.write_text(json.dumps(machine_document), encoding="utf-8")
        home = base / "home"
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("XDG_")}
        environment.update({"HOME": str(home), "XDG_DATA_HOME": str(home / ".local/share"),
                            "XDG_CACHE_HOME": str(home / ".cache"),
                            "XDG_STATE_HOME": str(home / ".local/state"),
                            "XDG_CONFIG_HOME": str(home / ".config"),
                            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/nonexistent"})
        result = subprocess.run(
            [sys.executable, str(INDEXER), "--output", str(output), "--catalog", str(catalog),
             "--appstream-root", str(base / "flatpak/appstream"),
             "--installation-root", str(base / "flatpak"), "--locale", "en",
             "--engines", "all", "--machine", str(machine_file)],
            text=True, capture_output=True, check=False, env=environment)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(output.read_text(encoding="utf-8"))

    def test_every_entry_carries_a_verdict_and_new_facts_refresh_it(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            first = self.run_index(base, {"org.example.Old": {"eol": True}},
                                   machine(screen={"width": 1920, "height": 1080,
                                                   "scale": 1.25}))
            apps = {app["id"]: app for app in first["apps"]}
            for app_id, app in apps.items():
                with self.subTest(app=app_id):
                    self.assertIn(app["compat"]["verdict"], {"ok", "warn", "blocked"})
            self.assertEqual(apps["org.example.Verified"]["compat"],
                             {"verdict": "ok", "reasons": []})
            self.assertEqual(apps["org.example.Wide"]["compat"],
                             {"verdict": "warn", "reasons": ["small_screen"]})
            self.assertEqual(apps["org.example.Wide"]["needs"],
                             {"display": {"px": 1200, "compare": "ge", "side": "shortest"}})
            self.assertTrue(apps["org.example.Old"]["eol"])
            self.assertEqual(apps["org.example.Old"]["compat"]["verdict"], "blocked")
            # The 5,000-byte package's peak on disk, not its download: the package and what
            # the container unpacks from it (4x), plus the container's own copy of it.
            self.assertEqual(apps["org.example.droid"]["needs"], {"size": 25000, "copy": 5000})
            self.assertEqual(first["stats"]["compat_blocked"], 1)
            self.assertEqual(first["stats"]["eol_apps"], 1)

            # New facts and a new machine: the verdicts follow, AppStream unread.
            xml = next((base / "flatpak/appstream").rglob("appstream.xml"))
            xml.chmod(0)
            try:
                second = self.run_index(
                    base, {"org.example.Verified": {"x11_only": True,
                                                    "permissions": ["files-all"]}},
                    machine(android={"ready": True, "initialized": False,
                                     "graphics": "software"},
                            screen={"width": 1920, "height": 1080, "scale": 1.25}))
            finally:
                xml.chmod(0o644)
            self.assertEqual(second["generation"]["metadata_token"],
                             first["generation"]["metadata_token"])
            self.assertNotEqual(second["generation"]["context_token"],
                                first["generation"]["context_token"])
            apps = {app["id"]: app for app in second["apps"]}
            self.assertTrue(apps["org.example.Wide"]["listed"])
            self.assertEqual(apps["org.example.Verified"]["compat"]["reasons"],
                             ["x11_only_scaled", "broad_permissions"])
            self.assertFalse(apps["org.example.Old"]["eol"])
            self.assertEqual(apps["org.example.Old"]["compat"], {"verdict": "ok",
                                                                 "reasons": []})
            self.assertEqual(apps["org.example.droid"]["compat"]["reasons"],
                             ["android_setup", "android_software_graphics"])


# ── low_disk: the footprint of a pinned install, and a cached index that is never stale ──
MIB = 1024 ** 2
ARCH = index.running_arch()
REVIEW = {"external": True, "risk": "downloaded-executable", "requires_review": True}


def pinned_entry(app_id: str, kind: str, size: int, **install) -> dict:
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


def with_free(free: int | None, *, reflink=True, template=True) -> dict:
    return {"arch": ARCH, "engines": ["android", "linux", "windows"],
            "free_bytes": {"apps": free}, "memory_bytes": 16 * 1024 ** 3,
            "android": {"ready": True, "initialized": True, "graphics": "hardware"},
            "windows": {"ready": True, "x86_32": False, "reflink": reflink, "template": template}}


def disk_verdict(app: dict, free: int, **facts) -> str:
    return index.compat_verdict(app, with_free(free, **facts), None)["verdict"]


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
        return indexed(pinned_entry(app_id, kind, download, **install))

    def test_every_measured_pin_fits_its_estimate(self):
        for app_id, (_kind, artifact, download, tree) in MEASURED.items():
            app = self.app(app_id)
            for shared in (True, False):
                # The download stays until the job ends; an AppImage is copied into App Drop's
                # staging folder first, which costs nothing only where extents are shared.
                peak = download + tree + (download if artifact == "appimage" and not shared else 0)
                extra = index.windows_settings_bytes(with_free(0, reflink=shared))
                need = index.install_need(app, with_free(0, reflink=shared))
                if app["kind"] == "windows":
                    need -= extra
                with self.subTest(app=app_id, shared=shared):
                    self.assertGreaterEqual(need, peak)
                    self.assertLessEqual(need, 2 * peak,
                                         "an estimate this loose blocks for nothing")

    def test_the_needs_of_each_kind(self):
        size = 10 * MIB

        def needs(app_id: str, kind: str, **install) -> dict:
            return indexed(pinned_entry(app_id, kind, size, **install))["needs"]

        self.assertEqual(needs("tool", "appdrop", artifact="archive"), {"size": 5 * size})
        self.assertEqual(needs("tool", "appdrop", artifact="appimage"),
                         {"size": 5 * size, "copy": size})
        self.assertEqual(needs("org.example.droid", "android"), {"size": 5 * size, "copy": size})
        self.assertEqual(needs("tool", "windows-portable", exe="app/app.exe"), {"size": 5 * size})
        page = indexed({"id": "page", "source": "moos", "cat": "util", "glyph": "spark",
                        "en": "Page", "ar": "صفحة",
                        "install": {"kind": "web", "url": "https://example.org/"}})
        self.assertNotIn("needs", page)

    def test_the_reported_installs_no_longer_start_on_a_disk_too_small(self):
        antigravity, lmstudio, heidisql = (self.app(name) for name in
                                           ("antigravity", "lmstudio", "heidisql"))
        # Antigravity: 181 MB to download, 700 MB at its peak.
        self.assertEqual(disk_verdict(antigravity, 400 * 1000 ** 2), "blocked")
        self.assertEqual(disk_verdict(antigravity, 1000 ** 3), "ok")
        # LM Studio: 1.02 GB AppImage, 3.4 GB at its peak on btrfs, 4.4 GB elsewhere.
        self.assertEqual(disk_verdict(lmstudio, 1100 * 1000 ** 2), "blocked")
        self.assertEqual(disk_verdict(lmstudio, 5500 * 1000 ** 2, reflink=True), "ok")
        self.assertEqual(disk_verdict(lmstudio, 5500 * 1000 ** 2, reflink=False), "blocked")
        # HeidiSQL's 30 MB zip unpacks to 83 MB: 100 MB is not enough even with the template.
        self.assertEqual(disk_verdict(heidisql, 100 * 1000 ** 2), "blocked")
        self.assertEqual(disk_verdict(heidisql, 200 * 1000 ** 2), "ok")
        # An installed app is never judged on its install size.
        self.assertEqual(disk_verdict(dict(antigravity, installed=True), 1), "ok")


SIZED_APPSTREAM = """<components>
  <component type="desktop-application"><id>org.example.Sized</id><name>Sized</name>
    <size type="download">314572800</size><size type="installed">734003200</size>
    <custom><value key="flathub::verification::verified">true</value></custom>
    <bundle type="flatpak">app/org.example.Sized/x86_64/stable</bundle></component>
</components>"""
PINNED_CATALOG = [
    pinned_entry("tool", "appdrop", 500 * MIB, artifact="archive", version="1.0"),
    pinned_entry("image", "appdrop", 300 * MIB, artifact="appimage", version="1.0"),
    pinned_entry("org.example.droid", "android", 100 * MIB, version="1.0"),
    pinned_entry("notepad", "windows-portable", 10 * MIB, exe="app/app.exe", version="1.0"),
]


class DiskFixture:
    def __init__(self, base: Path):
        self.base = base
        self.home = base / "home"
        revision = base / "flatpak/appstream/flathub/x86_64" / ("f" * 64)
        revision.mkdir(parents=True)
        (revision / "appstream.xml").write_text(SIZED_APPSTREAM, encoding="utf-8")
        self.catalog = base / "catalog.json"
        self.catalog.write_text(json.dumps({"apps": PINNED_CATALOG}), encoding="utf-8")
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
        self.machine_file.write_text(json.dumps(with_free(free)), encoding="utf-8")
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
            fixture = DiskFixture(Path(raw))
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
        apps = [indexed(raw) for raw in PINNED_CATALOG]
        for free_mib in (0, 50, 51, 52, 499, 500, 1499, 1500, 2499, 2500, 10 ** 6):
            free = free_mib * MIB
            low, high = index.free_space_range(apps, with_free(free))
            here = [index.compat_verdict(app, with_free(free), None) for app in apps]
            with self.subTest(free_mib=free_mib):
                self.assertLessEqual(low, free)
                self.assertTrue(high is None or free < high)
                for probe in (low, free, (high - 1) if high is not None else free * 2):
                    self.assertEqual([index.compat_verdict(app, with_free(probe), None)
                                      for app in apps], here)
                if high is not None:
                    self.assertNotEqual([index.compat_verdict(app, with_free(high), None)
                                         for app in apps], here)
        self.assertIsNone(index.free_space_range(apps, with_free(None)))


class TheEarlyReturnStaysEarly(unittest.TestCase):
    def test_moving_inside_the_range_reads_only_the_header(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = DiskFixture(Path(raw))
            output = fixture.base / "cache/index.json"
            calls = []
            original = index.load_refreshable_output

            def counting(*args):
                calls.append(args)
                return original(*args)

            def run(free_mib: int) -> int:
                fixture.machine_file.write_text(json.dumps(with_free(free_mib * MIB)),
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
