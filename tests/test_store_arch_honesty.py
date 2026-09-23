#!/usr/bin/env python3
"""The Store may not offer an app this machine cannot install.

THE DEFECT, measured on the Oracle A1 on 2026-09-21:

  `catalog.json` had no notion of architecture, and neither did the index
  builder. The browse index is otherwise built from the RUNNING architecture's
  AppStream data, so it is arch-correct — but when a curated entry found no
  AppStream match, `catalog_fallback_app()` MANUFACTURED an index entry for it.
  On aarch64 that happened for every app with no ARM build.

  Eleven of the catalogue's thirty-three Flathub apps have no aarch64 build:
  Thunderbird, OBS Studio, Steam, Bottles, Lutris, Heroic, Spotify, Discord,
  Zoom, Slack and Android Studio. All eleven appeared in the A1's Store index of
  2941 apps, and two of them — Steam and Spotify — carry "popular": true, so
  they were promoted on the front page. Every one was a dead button:

      $ flatpak --system remote-info flathub com.spotify.Client --arch=aarch64
      error: Error searching remote flathub: Can't find ref com.spotify.Client/aarch64

  MoOS already refuses PC gaming on ARM in Mo AI (`moai-do`'s
  `pc_games_supported`), so the Store offering a "Gaming Starter" bundle led by
  Steam was also two MoOS surfaces disagreeing with each other.

AGENTS.md: "No fake apps and no dead buttons."
"""
import importlib.machinery
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "system_files/usr/share/moos/store/catalog.json"
INDEX_TOOL = ROOT / "system_files/usr/bin/moos-store-index"
STORECTL = ROOT / "system_files/usr/bin/moos-storectl"


def load(name: str, path: Path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: moos-storectl defines dataclasses, and
    # @dataclass resolves annotations through sys.modules[cls.__module__].
    sys.modules[name] = module
    loader.exec_module(module)
    return module


index = load("moos_store_index", INDEX_TOOL)

# Measured against `flatpak --system remote-ls flathub --arch=aarch64` (2923 apps)
# on 2026-09-21. These are the catalogue entries with no ARM build at all.
# load_catalog is pure: it filters only what the caller describes. Tests that are
# about the ARCH filter pass every engine, so the two rules stay separable.
ALL_ENGINES = {"windows", "android", "linux"}

NO_ARM_BUILD = {
    "org.mozilla.thunderbird_esr", "com.obsproject.Studio", "com.valvesoftware.Steam",
    "com.usebottles.bottles", "net.lutris.Lutris", "com.heroicgameslauncher.hgl",
    "com.spotify.Client", "com.discordapp.Discord", "us.zoom.Zoom", "com.slack.Slack",
    "com.google.AndroidStudio",
}


class TheCatalogueSaysWhereItsAppsExist(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(CATALOG.read_text(encoding="utf-8"))

    def test_every_app_with_no_arm_build_is_marked_x86_only(self):
        """The data half. Without it the filter below has nothing to act on."""
        by_id = {app["id"]: app for app in self.raw["apps"]}
        for app_id in sorted(NO_ARM_BUILD):
            with self.subTest(app=app_id):
                self.assertIn(app_id, by_id, "measured x86-only app left the catalogue; "
                                             "drop it from NO_ARM_BUILD too")
                self.assertEqual(
                    by_id[app_id].get("arch"), ["x86_64"],
                    f"{app_id} has no aarch64 build on Flathub, so the ARM Store would "
                    f"offer an install that can only answer \"Can't find ref\"")

    def test_an_app_that_runs_everywhere_stays_unmarked(self):
        """`arch` is an exception, not boilerplate: absent must keep meaning 'all'."""
        by_id = {app["id"]: app for app in self.raw["apps"]}
        self.assertNotIn("arch", by_id["org.mozilla.firefox"])


class TheIndexOffersOnlyWhatRunsHere(unittest.TestCase):
    def test_the_x86_editions_are_unchanged(self):
        """A fix for ARM that quietly shrinks the x86 store would be a regression."""
        everywhere = index.load_catalog(CATALOG, "x86_64", ALL_ENGINES)
        self.assertEqual(len(everywhere["apps"]), len(json.loads(
            CATALOG.read_text(encoding="utf-8"))["apps"]))
        self.assertEqual(len(everywhere["bundles"]), 5)

    def test_arm_is_offered_the_catalogue_minus_what_cannot_install(self):
        # Every engine, so this measures the ARCH rule alone.
        here = index.load_catalog(CATALOG, "aarch64", ALL_ENGINES)
        offered = {app["id"] for app in here["apps"]}
        self.assertEqual(offered & NO_ARM_BUILD, set(),
                         "these cannot be installed on aarch64 and must not be offered")
        self.assertEqual(len(here["apps"]),
                         len(index.load_catalog(CATALOG, "x86_64", ALL_ENGINES)["apps"]) - len(NO_ARM_BUILD))

    def test_a_bundle_never_lists_an_app_the_machine_cannot_install(self):
        for arch in ("x86_64", "aarch64"):
            data = index.load_catalog(CATALOG, arch, ALL_ENGINES)
            offered = {app["id"] for app in data["apps"]}
            for bundle in data["bundles"]:
                with self.subTest(arch=arch, bundle=bundle["id"]):
                    self.assertTrue(set(bundle.get("apps", [])) <= offered,
                                    "a bundle may only name apps the store offers here")

    def test_a_bundle_gutted_by_the_filter_is_not_offered_at_all(self):
        """Gaming Starter lost 5 of 6 on ARM; one compatibility tool is not that bundle."""
        arm = {bundle["id"] for bundle in index.load_catalog(CATALOG, "aarch64", {"linux"})["bundles"]}
        x86 = {bundle["id"] for bundle in index.load_catalog(CATALOG, "x86_64", ALL_ENGINES)["bundles"]}
        self.assertIn("game-starter", x86)
        self.assertNotIn("game-starter", arm)

    def test_the_filter_is_a_whitelist_not_a_hint(self):
        self.assertTrue(index.catalog_app_runs_here({"id": "a"}, "aarch64"))
        self.assertTrue(index.catalog_app_runs_here({"id": "a", "arch": ["aarch64"]}, "aarch64"))
        self.assertFalse(index.catalog_app_runs_here({"id": "a", "arch": ["x86_64"]}, "aarch64"))
        self.assertTrue(
            index.catalog_app_runs_here({"id": "a", "arch": ["x86_64", "aarch64"]}, "aarch64"))

    def test_an_unknown_machine_is_offered_everything_rather_than_nothing(self):
        """An empty store is a worse failure than an install that reports honestly."""
        data = index.load_catalog(CATALOG, "riscv64", ALL_ENGINES)
        self.assertEqual(len(data["apps"]),
                         len(json.loads(CATALOG.read_text(encoding="utf-8"))["apps"])
                         - len(NO_ARM_BUILD))

    def test_a_malformed_arch_is_rejected_rather_than_ignored(self):
        for bad in ("x86_64", [], ["not a ref!"], [7]):
            with self.subTest(bad=bad):
                with self.assertRaises(index.CatalogError):
                    index.sanitize_catalog_app(
                        {"id": "org.x.Y", "source": "flathub", "arch": bad})

    def test_a_declared_arch_survives_sanitising(self):
        """The sanitiser whitelists keys, so an unlisted one is silently dropped."""
        clean = index.sanitize_catalog_app(
            {"id": "org.x.Y", "source": "flathub", "arch": ["x86_64"]})
        self.assertEqual(clean["arch"], ["x86_64"])


class TheBackendAgreesWithTheIndex(unittest.TestCase):
    """A hidden app must not be installable by id, from a stale index or by hand."""

    def test_storectl_filters_the_same_catalogue(self):
        source = STORECTL.read_text(encoding="utf-8")
        self.assertIn("running_arch()", source)
        self.assertIn('declared = app.get("arch")', source,
                      "moos-storectl._catalog must drop entries this arch cannot install")

    def test_both_tools_spell_the_architecture_the_same_way(self):
        storectl = load("moos_storectl_arch", STORECTL)
        self.assertEqual(storectl.running_arch(), index.running_arch())

    def test_a_catalogue_read_here_drops_the_x86_only_entries(self):
        with tempfile.TemporaryDirectory() as raw:
            catalog = Path(raw) / "catalog.json"
            catalog.write_text(json.dumps({"apps": [
                {"id": "org.a.Everywhere", "source": "flathub"},
                {"id": "org.b.X86Only", "source": "flathub", "arch": ["x86_64"]},
            ]}), encoding="utf-8")
            data = index.load_catalog(catalog, "aarch64")
            self.assertEqual([app["id"] for app in data["apps"]], ["org.a.Everywhere"])


class TheEngineAnAppNeedsMustBePresent(unittest.TestCase):
    """An app whose ENGINE is not in this image is as dead as one with no build.

    Measured on the A1 2026-09-21: neither wine nor waydroid is in the ARM image
    (`rpm -q` says not installed, neither is on PATH), so the windows and android
    engines have no runtime there -- while the Store offered 8 Windows programs
    and 7 Android apps. `moai-do setup-windows` refuses on ARM outright, and
    `setup-waydroid` dead-ends with "waydroid not found", so neither could ever
    have been installed. app-engines.json is MoOS's own source of truth for what
    it can run and already carries the `probe` that settles it.
    """

    ENGINES = ROOT / "system_files/usr/share/moos/app-engines.json"

    def test_the_catalogue_declares_the_engine_its_windows_and_android_apps_need(self):
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        for app in raw["apps"]:
            if app.get("cat") == "win":
                with self.subTest(app=app["id"]):
                    self.assertEqual(app.get("engine"), "windows")
            if (app.get("install") or {}).get("kind") == "android":
                with self.subTest(app=app["id"]):
                    self.assertEqual(app.get("engine"), "android")

    def test_an_engine_is_implied_when_the_install_kind_says_so(self):
        """An older catalogue with no `engine` key must still be filtered."""
        self.assertEqual(
            index.catalog_app_engine({"id": "a", "install": {"kind": "android"}}), "android")
        self.assertEqual(index.catalog_app_engine({"id": "a", "engine": "windows"}), "windows")
        self.assertEqual(index.catalog_app_engine({"id": "a"}), "")

    def test_a_probe_that_is_not_on_path_is_not_an_available_runtime(self):
        self.assertFalse(index.engine_runtime_available(
            {"id": "x", "probe": "moos-no-such-binary-ever"}))
        self.assertTrue(index.engine_runtime_available(
            {"id": "x", "probe": "sh"}))

    def test_a_runtime_with_neither_probe_nor_flatpak_carrier_is_not_assumed_present(self):
        self.assertFalse(index.engine_runtime_available({"id": "x"}))

    def test_an_unreadable_registry_filters_nothing_rather_than_everything(self):
        """None, never set(): an empty set would silently empty the whole Store."""
        self.assertIsNone(index.available_engines(Path("/nonexistent/app-engines.json")))
        before = len(json.loads(CATALOG.read_text(encoding="utf-8"))["apps"])
        self.assertEqual(len(index.load_catalog(CATALOG, "x86_64", None)["apps"]), before)

    def test_a_machine_with_every_engine_is_offered_every_curated_app(self):
        data = index.load_catalog(CATALOG, "x86_64", {"windows", "android", "linux"})
        self.assertEqual(len(data["apps"]),
                         len(json.loads(CATALOG.read_text(encoding="utf-8"))["apps"]))

    def test_a_machine_with_only_linux_loses_the_windows_and_android_apps(self):
        data = index.load_catalog(CATALOG, "x86_64", {"linux"})
        offered = {app["id"] for app in data["apps"]}
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))["apps"]
        for app in raw:
            if app.get("engine") in {"windows", "android"}:
                with self.subTest(app=app["id"]):
                    self.assertNotIn(app["id"], offered)

    def test_the_registrys_own_engines_are_the_only_ones_the_catalogue_names(self):
        """A typo'd engine would hide an app forever with no error anywhere."""
        known = {engine["id"] for engine
                 in json.loads(self.ENGINES.read_text(encoding="utf-8"))["engines"]}
        for app in json.loads(CATALOG.read_text(encoding="utf-8"))["apps"]:
            engine = app.get("engine")
            if engine:
                with self.subTest(app=app["id"]):
                    self.assertIn(engine, known)

    def test_the_machine_profile_is_shaped_for_the_surfaces_that_read_it(self):
        profile = index.machine_profile()
        self.assertEqual(sorted(profile), ["arch", "engines"])
        self.assertIsInstance(profile["arch"], str)
        self.assertTrue(profile["engines"] is None or isinstance(profile["engines"], list))


class TheFirstFrameIsFilteredToo(unittest.TestCase):
    """The Store paints the curated catalogue BEFORE the index exists.

    Component.onCompleted calls loadCurated() first and only swaps in the index
    when it is ready, so a filter that lives only in the index leaves the first
    frame -- and the whole of a first run -- showing apps that cannot install.
    """

    QML = ROOT / "system_files/usr/share/moos/apps/store/main.qml"
    LAUNCHER = ROOT / "system_files/usr/bin/moos-store"

    def test_the_launcher_writes_the_machine_profile_before_the_window(self):
        launcher = self.LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("--print-machine", launcher)
        self.assertIn("--machine=", launcher)
        index_at = launcher.index("--print-machine")
        exec_at = launcher.index("exec /usr/bin/moos-qml-shell")
        self.assertLess(index_at, exec_at,
                        "the profile must exist before the first frame is painted")

    def test_the_curated_path_filters_and_reads_the_profile_first(self):
        qml = self.QML.read_text(encoding="utf-8")
        self.assertIn("win.curatedRunsHere(apps[i])", qml)
        self.assertLess(qml.index("win.loadMachine()"), qml.index("win.loadCurated()"),
                        "the profile has to be read before the catalogue is painted")

    def test_the_capability_strip_lists_only_engines_with_a_runtime(self):
        """It advertised Windows programs and Android apps on a machine with neither."""
        qml = self.QML.read_text(encoding="utf-8")
        self.assertIn("ready.indexOf(\"\" + engine.id) < 0", qml)


if __name__ == "__main__":
    unittest.main()
