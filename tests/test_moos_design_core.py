#!/usr/bin/env python3
"""Architecture gate for the global MoOS Design Core and MoUI module."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artwork/moos-design/tokens.json"
GENERATOR = ROOT / "artwork/generate_moos_design_core.py"
PROFILE_SOURCE = ROOT / "artwork/moos-design/theme-profiles.json"
PROFILE_GENERATOR = ROOT / "artwork/generate_moos_theme_profiles.py"
MODULE = ROOT / "system_files/usr/lib64/qt6/qml/org/moos/ui"
APPS = ROOT / "system_files/usr/share/moos/apps"
SHARE = ROOT / "system_files/usr/share"
PROFILE_RUNTIME = SHARE / "moos"
BUILD_SCRIPT = ROOT / "build_files/build.sh"


class DesignCoreTests(unittest.TestCase):
    def test_json_is_the_complete_bounded_identity_contract(self) -> None:
        document = json.loads(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], 1)
        self.assertEqual(
            set(document) - {"schema"},
            {
                "spacing", "radius", "target", "type", "font", "weight", "motion",
                "opacity", "border", "icon", "layout", "material", "easing",
            },
        )
        self.assertEqual(document["material"]["blurCeiling"], 15)
        self.assertEqual(document["font"]["interfaceFamily"],
                         "IBM Plex Sans Arabic")
        self.assertLessEqual(document["material"]["shadowBlur"], 15)
        for name, value in document["opacity"].items():
            with self.subTest(opacity=name):
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 1)

    def test_generated_singleton_and_module_are_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary)
            target = isolated / "artwork/moos-design"
            target.mkdir(parents=True)
            shutil.copy2(SOURCE, target / "tokens.json")
            env = os.environ.copy()
            env["MOOS_DESIGN_TEST_ROOT"] = str(isolated)
            subprocess.run(
                ["python3", str(GENERATOR)],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            generated = isolated / "system_files/usr/lib64/qt6/qml/org/moos/ui"
            for name in ("Tokens.qml", "qmldir"):
                with self.subTest(output=name):
                    self.assertEqual(
                        (generated / name).read_bytes(),
                        (MODULE / name).read_bytes(),
                    )

        tokens = (MODULE / "Tokens.qml").read_text(encoding="utf-8")
        qmldir = (MODULE / "qmldir").read_text(encoding="utf-8")
        self.assertIn("pragma Singleton", tokens)
        self.assertIn("function stateOpacity(", tokens)
        self.assertNotRegex(tokens, r"#[0-9A-Fa-f]{6,8}")
        self.assertIn("KeyboardViewport 1.0 KeyboardViewport.js", qmldir)
        self.assertIn("SymbolCatalog 1.0 SymbolCatalog.js", qmldir)
        self.assertNotIn("singleton KeyboardViewport", qmldir)
        self.assertNotIn("singleton SymbolCatalog", qmldir)

    def test_one_global_module_owns_the_shared_components(self) -> None:
        expected = {
            "Tokens.qml", "Surface.qml", "GlassSurface.qml", "Card.qml",
            "Button.qml", "IconButton.qml", "Separator.qml", "FocusRing.qml",
            "SymbolIcon.qml", "KeyboardViewport.js", "SymbolCatalog.js", "qmldir",
        }
        self.assertTrue(expected.issubset({path.name for path in MODULE.iterdir()}))

        retired = APPS / "ui"
        self.assertFalse(
            retired.exists() and any(retired.iterdir()),
            "the application-local design-system copy returned",
        )

        for app in ("welcome", "installer", "store", "moai", "settings"):
            source = (APPS / app / "main.qml").read_text(encoding="utf-8")
            with self.subTest(app=app):
                self.assertIn("import org.moos.ui as MoUI", source)
                self.assertIn("readonly property var design: MoUI.Tokens", source)
                self.assertNotIn('import "../ui', source)
                self.assertNotIn("MoOSUi.", source)

    def test_components_consume_tokens_not_private_identity_literals(self) -> None:
        for name in (
            "Surface.qml", "GlassSurface.qml", "Card.qml", "Button.qml",
            "IconButton.qml", "Separator.qml", "FocusRing.qml", "SymbolIcon.qml",
        ):
            source = (MODULE / name).read_text(encoding="utf-8")
            with self.subTest(component=name):
                self.assertIn("Tokens.", source)
                self.assertNotRegex(source, r"#[0-9A-Fa-f]{6,8}")

    def test_shell_surfaces_share_the_global_module(self) -> None:
        surfaces = (
            SHARE / "moos/theme-picker/main.qml",
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/main.qml",
            SHARE / "plasma/plasmoids/org.moos.brand/contents/ui/LauncherView.qml",
            SHARE / "plasma/plasmoids/org.moos.nova.clock/contents/ui/main.qml",
            SHARE / "plasma/plasmoids/org.moos.heroclock/contents/ui/main.qml",
            SHARE / "plasma/plasmoids/org.moos.island/contents/ui/main.qml",
        )
        for path in surfaces:
            source = path.read_text(encoding="utf-8")
            with self.subTest(surface=path.relative_to(ROOT)):
                self.assertIn("import org.moos.ui as MoUI", source)
                self.assertRegex(
                    source,
                    r"readonly property var design:\s*MoUI\.Tokens",
                )

        launcher = surfaces[2].read_text(encoding="utf-8")
        self.assertIn("readonly property int radiusM: design.radiusControl", launcher)
        self.assertNotIn("readonly property int radiusM: 12", launcher)

        command_center = (APPS / "settings/main.qml").read_text(encoding="utf-8")
        self.assertGreaterEqual(command_center.count("MoUI.GlassSurface {"), 3)
        self.assertIn("component StatusCapsule: MoUI.Surface", command_center)
        self.assertIn("component MetricTile: MoUI.Surface", command_center)
        self.assertIn("design.commandCenterWidth", command_center)
        self.assertNotIn("width: Math.min(1360,", command_center)

        session_surfaces = (
            ROOT / "artwork/tidal-portal/Splash.qml",
            SHARE / "plasma/look-and-feel/org.moos.ui2/contents/splash/Splash.qml",
            SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/Logout.qml",
            SHARE / "plasma/look-and-feel/org.moos.ui2/contents/logout/MoOSUI2ActionButton.qml",
            SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/LockScreenUi.qml",
            SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/MainBlock.qml",
            SHARE / "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/MoOSClock.qml",
            ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components/ActionButton.qml",
            ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components/UserDelegate.qml",
            ROOT / "system_files/usr/lib64/qt6/qml/org/kde/breeze/components/Clock.qml",
        )
        for path in session_surfaces:
            source = path.read_text(encoding="utf-8")
            with self.subTest(session_surface=path.relative_to(ROOT)):
                self.assertIn("import org.moos.ui as MoUI", source)
                self.assertRegex(
                    source,
                    r"readonly property var design:\s*MoUI\.Tokens",
                )
                self.assertNotIn('font.family: "IBM Plex Sans Arabic"', source)

    def test_theme_profiles_are_generated_complete_pairs(self) -> None:
        document = json.loads(PROFILE_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(document["schema"], 1)
        self.assertEqual(
            document["engines"],
            {"qtWidgetStyle": "Breeze", "gtkTheme": "Breeze"},
            "Qt and GTK must share one declared technical engine; adding "
            "Kvantum or another style requires a profile-schema migration",
        )
        profiles = document["profiles"]
        self.assertEqual(len(profiles), 16)
        self.assertEqual(len({profile["id"] for profile in profiles}), 16)
        families: dict[str, set[str]] = {}
        for profile in profiles:
            families.setdefault(profile["family"], set()).add(profile["mode"])
            with self.subTest(profile=profile["id"]):
                self.assertRegex(profile["accent"], r"^#[0-9A-F]{6}$")
                self.assertTrue(
                    (SHARE / "plasma/look-and-feel" / profile["id"] / "metadata.json").is_file()
                )
                self.assertTrue(
                    (SHARE / "color-schemes" / f"{profile['scheme']}.colors").is_file()
                )
                self.assertTrue((SHARE / "plasma/desktoptheme" / profile["style"]).is_dir())
                self.assertTrue((SHARE / "aurorae/themes" / profile["decoration"]).is_dir())
                self.assertTrue((SHARE / "konsole" / profile["konsole"]).is_file())
                self.assertTrue((SHARE / "moos/gtk" / profile["gtkCss"]).is_file())
                icon_theme = SHARE / "icons" / profile["icons"]
                if profile["icons"] in {"MoOSUI2", "MoOSUI2Light"}:
                    # The broad base vocabularies are derived from packaged
                    # Colloid during image construction; Git carries only the
                    # palette overlays.  Gate the actual compose path for those
                    # two targets rather than requiring a source-only copy.
                    build = BUILD_SCRIPT.read_text(encoding="utf-8")
                    self.assertIn(
                        f'mkdir -p /usr/share/icons/{profile["icons"]}',
                        build,
                    )
                    self.assertIn(
                        f'gtk-update-icon-cache -f /usr/share/icons/{profile["icons"]}',
                        build,
                    )
                else:
                    self.assertTrue(icon_theme.is_dir())
                self.assertTrue((SHARE / "wallpapers" / profile["wallpaper"]).is_dir())
        self.assertTrue(all(modes == {"light", "dark"} for modes in families.values()))

    def test_theme_profile_runtime_database_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            isolated = Path(temporary)
            target = isolated / "artwork/moos-design"
            target.mkdir(parents=True)
            shutil.copy2(PROFILE_SOURCE, target / "theme-profiles.json")
            env = os.environ.copy()
            env["MOOS_THEME_PROFILE_TEST_ROOT"] = str(isolated)
            subprocess.run(
                ["python3", str(PROFILE_GENERATOR)],
                check=True,
                env=env,
                capture_output=True,
                text=True,
            )
            generated = isolated / "system_files/usr/share/moos"
            for name in ("theme-profiles.json", "theme-profiles.tsv"):
                with self.subTest(output=name):
                    self.assertEqual(
                        (generated / name).read_bytes(),
                        (PROFILE_RUNTIME / name).read_bytes(),
                    )

        switch = (SHARE.parent / "bin/moos-theme").read_text(encoding="utf-8")
        migrator = (SHARE.parent / "bin/moos-apply-theme").read_text(encoding="utf-8")
        self.assertIn("MOOS_THEME_PROFILE_DB", switch)
        self.assertIn('moos-theme apply-lnf "$want_lnf"', migrator)
        self.assertIn('moos-theme verify-lnf "$lnf_after"', migrator)
        self.assertIn('moos-theme guard', migrator)
        self.assertNotIn("pin_gtk()", migrator)
        for duplicate in (
            "want_scheme=", "want_style=", "want_deco=", "want_icons=",
            "want_konsole=", "want_wallpaper_package=",
        ):
            with self.subTest(retired_owner=duplicate):
                self.assertNotIn(duplicate, migrator)
        for function in (
            "theme_intact", "apply_desktop_scene", "reconcile_wallpaper_drift",
        ):
            with self.subTest(retired_owner=function):
                self.assertNotRegex(
                    migrator,
                    rf"(?m)^{function}\(\)\s*\{{",
                    "historical migration notes may name a retired function, "
                    "but the migrator must not define it",
                )

        self.assertIn('"schema": 2', switch)
        self.assertIn('"wallpaperMode": "%s"', switch)
        self.assertIn('"wallpaperEncoded": "%s"', switch)
        self.assertIn('[ "$status" = committed ] && [ -z "$identity" ]', switch)
        self.assertIn("verified=0", switch)
        self.assertNotIn(r"/[!\x27()*]/g", switch)
        self.assertGreaterEqual(
            switch.count('.split(String.fromCharCode(39)).join("%27")'),
            2,
            "scene and wallpaper identity encoding must avoid QJSEngine's "
            "broken \\x27 character-class interpretation",
        )
        self.assertIn("apply_wallpaper_transaction", switch)
        self.assertIn("custom_wallpapers_complete", switch)


if __name__ == "__main__":
    unittest.main(verbosity=2)
