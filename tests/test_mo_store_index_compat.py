#!/usr/bin/env python3
"""Will this app work well on THIS machine? Mo Store's compatibility verdicts.

compat_verdict(app, machine.json, facts.json) is pure, so every rule is proven here on
fixture machines: `blocked` for no build for this architecture, a missing engine, a pinned
download that does not fit, or an end-of-life app not yet installed; `warn` for Android
setup or software graphics, too little memory, a screen smaller than the app needs, an app
that needs the internet, an X11-only app on a fractionally scaled screen, broad permissions,
a download from the vendor at install time, and an unverified Flatpak. An installed app is
never blocked.

Index runs use a private HOME, private XDG directories and --machine fixtures.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
