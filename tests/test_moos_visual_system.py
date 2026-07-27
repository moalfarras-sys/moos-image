#!/usr/bin/env python3
"""Structural gates for the unified MoOS Plasma visual system."""

from __future__ import annotations

import pathlib
import re
import unittest
import xml.etree.ElementTree as ET

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
SHARE = ROOT / "system_files/usr/share"

STYLE_NAMES = (
    "MoOSUI2",
    "MoOSUI2Light",
    "MoOSUI2Amethyst",
    "MoOSUI2AmethystLight",
    "MoOSUI2Aurora",
    "MoOSUI2AuroraLight",
    "MoOSUI2Forge",
    "MoOSUI2ForgeLight",
    "MoOSUI2Arena",
    "MoOSUI2ArenaLight",
    "MoOSUI2Midnight",
    "MoOSUI2Daylight",
    "MoOSUI2Nova",
    "MoOSUI2NovaLight",
    "MoOSUI2Scholar",
    "MoOSUI2ScholarLight",
)

SURFACE_SVGS = {
    "actionbutton.svg",
    "arrows.svg",
    "background.svg",
    "busywidget.svg",
    "checkmarks.svg",
    "frame.svg",
    "menubaritem.svg",
    "pager.svg",
    "radiobutton.svg",
    "scrollbar.svg",
    "slider.svg",
    "switch.svg",
    "tabbar.svg",
    "toolbar.svg",
    "tooltip.svg",
    "translucentbackground.svg",
}

AURORAE_BUTTONS = {
    "close.svg",
    "minimize.svg",
    "maximize.svg",
    "restore.svg",
    "help.svg",
    "alldesktops.svg",
    "keepabove.svg",
    "keepbelow.svg",
    "shade.svg",
    "appmenu.svg",
}

ICON_SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 192, 256, 512)

BUTTON_STATES = {
    "active-center",
    "inactive-center",
    "hover-center",
    "hover-inactive-center",
    "pressed-center",
    "pressed-inactive-center",
    "deactivated-center",
    "deactivated-inactive-center",
}

FRAME_POSITIONS = {
    "topleft", "top", "topright",
    "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
}


def svg_ids(path: pathlib.Path) -> set[str]:
    tree = ET.parse(path)
    return {
        element_id
        for element in tree.iter()
        if (element_id := element.attrib.get("id"))
    }


class MoOSVisualSystemTests(unittest.TestCase):
    def test_every_palette_owns_high_visibility_plasma_surfaces(self) -> None:
        for style in STYLE_NAMES:
            with self.subTest(style=style):
                widgets = SHARE / "plasma/desktoptheme" / style / "widgets"
                actual = {path.name for path in widgets.glob("*.svg")}
                self.assertTrue(
                    SURFACE_SVGS <= actual,
                    f"{style} still falls back for {sorted(SURFACE_SVGS - actual)}",
                )
                for name in SURFACE_SVGS:
                    ET.parse(widgets / name)

    def test_plasma_surface_contracts_cover_interaction_and_blur(self) -> None:
        for style in STYLE_NAMES:
            widgets = SHARE / "plasma/desktoptheme" / style / "widgets"
            with self.subTest(style=style):
                for name in (
                    "background.svg",
                    "tooltip.svg",
                    "translucentbackground.svg",
                ):
                    ids = svg_ids(widgets / name)
                    self.assertTrue(FRAME_POSITIONS <= ids, f"{style}/{name}")
                    self.assertTrue(
                        {f"mask-{position}" for position in FRAME_POSITIONS}
                        <= ids,
                        f"{style}/{name} has no complete rounded blur mask",
                    )

                menu_ids = svg_ids(widgets / "menubaritem.svg")
                for state in ("normal", "hover", "pressed"):
                    self.assertTrue(
                        {
                            f"{state}-{position}"
                            for position in FRAME_POSITIONS
                        } <= menu_ids,
                        f"{style}/menubaritem.svg lacks {state}",
                    )

                tab_ids = svg_ids(widgets / "tabbar.svg")
                for direction in ("north", "east", "south", "west"):
                    self.assertTrue(
                        {
                            f"{direction}-active-tab-{position}"
                            for position in FRAME_POSITIONS
                        } <= tab_ids,
                        f"{style}/tabbar.svg lacks {direction}",
                    )

                switch_ids = svg_ids(widgets / "switch.svg")
                self.assertTrue({
                    "active-left", "active-center", "active-right",
                    "inactive-left", "inactive-center", "inactive-right",
                    "handle", "handle-hover", "handle-focus", "handle-pressed",
                } <= switch_ids, f"{style}/switch.svg")

    def test_aurorae_has_real_blur_fallbacks_and_full_button_states(self) -> None:
        for style in STYLE_NAMES:
            package = SHARE / "aurorae/themes" / style
            with self.subTest(style=style):
                actual = {path.name for path in package.glob("*.svg")}
                self.assertTrue(
                    AURORAE_BUTTONS <= actual,
                    f"{style} omits functional buttons: "
                    f"{sorted(AURORAE_BUTTONS - actual)}",
                )
                decoration_ids = svg_ids(package / "decoration.svg")
                for prefix in (
                    "mask",
                    "innerborder",
                    "innerborder-inactive",
                    "decoration-opaque",
                    "decoration-opaque-inactive",
                ):
                    self.assertTrue(
                        {f"{prefix}-{position}" for position in FRAME_POSITIONS}
                        <= decoration_ids,
                        f"{style} lacks the {prefix} frame",
                    )
                self.assertTrue({
                    "decoration-maximized-center",
                    "decoration-maximized-inactive-center",
                    "decoration-maximized-opaque-center",
                    "decoration-maximized-opaque-inactive-center",
                } <= decoration_ids)

                for button in AURORAE_BUTTONS:
                    ids = svg_ids(package / button)
                    self.assertTrue(BUTTON_STATES <= ids, f"{style}/{button}")

                rc_files = list(package.glob("*rc"))
                self.assertEqual(len(rc_files), 1, style)
                rc = rc_files[0].read_text(encoding="utf-8")
                self.assertIn("Animation=140", rc)
                self.assertIn("TitleHeight=32", rc)
                self.assertIn("ButtonWidth=20", rc)
                self.assertIn("RightButtons=HIAX", rc)
                self.assertNotIn("macOS", rc)

    def test_window_buttons_are_not_passive_traffic_lights(self) -> None:
        for style in STYLE_NAMES:
            package = SHARE / "aurorae/themes" / style
            for button in ("close.svg", "minimize.svg", "maximize.svg"):
                with self.subTest(style=style, button=button):
                    text = (package / button).read_text(encoding="utf-8")
                    active = re.search(
                        r'<g id="active-center".*?</g>',
                        text,
                        flags=re.DOTALL,
                    )
                    self.assertIsNotNone(active)
                    self.assertNotIn("<circle", active.group(0))
                    self.assertRegex(active.group(0), r"<(?:path|rect)\b")
                    self.assertIn('id="hover-center"', text)
                    self.assertIn('id="pressed-center"', text)

    def test_every_global_theme_uses_live_aurorae_v2_and_widget_style(self) -> None:
        packages = sorted((SHARE / "plasma/look-and-feel").glob("org.moos.ui2*"))
        self.assertEqual(len(packages), 16)
        for package in packages:
            defaults = (package / "contents/defaults").read_text(encoding="utf-8")
            with self.subTest(package=package.name):
                self.assertIn("library=org.kde.kwin.aurorae.v2", defaults)
                self.assertIn("[kdeglobals][KDE]\nwidgetStyle=Breeze", defaults)

        kwinrc = (ROOT / "system_files/etc/xdg/kwinrc").read_text(encoding="utf-8")
        self.assertIn("library=org.kde.kwin.aurorae.v2", kwinrc)
        for script_name in ("moos-theme", "moos-apply-theme"):
            script = (ROOT / "system_files/usr/bin" / script_name).read_text(
                encoding="utf-8"
            )
            self.assertIn("org.kde.kwin.aurorae.v2", script)

    def test_generated_wallpaper_pair_is_project_bound(self) -> None:
        masters = ROOT / "artwork/moos-ui2/wallpapers"
        expected = {
            "moos-ui-graphite-flow-master-v4.png",
            "moos-ui-tidal-flow-master-v3.png",
        }
        self.assertTrue(expected <= {path.name for path in masters.glob("*.png")})
        generator = (ROOT / "artwork/generate_moos_ui2.py").read_text(
            encoding="utf-8"
        )
        for name in expected:
            self.assertIn(name, generator)

    def test_dynamic_wallpaper_is_4k_safe_and_low_duty_cycle(self) -> None:
        package = SHARE / "plasma/wallpapers/org.moos.ui2.wallpaper"
        qml = (package / "contents/ui/main.qml").read_text(encoding="utf-8")
        config = (package / "contents/config/main.xml").read_text(encoding="utf-8")
        self.assertIn('<entry name="AmbientMotion" type="Bool">', config)
        # MotionMode is the key `moos-theme motion` actually writes. It was
        # written for months while no such entry existed and no QML line read it,
        # so 'gentle' and 'alive' were the same desktop. Its default must stay the
        # -1 SENTINEL: KConfigXT cannot tell an absent key from one holding the
        # default, so a default of 1 would silently promote every installed
        # desktop that has AmbientMotion=false and no MotionMode from 'still' back
        # to 'gentle' on upgrade.
        self.assertIn('<entry name="MotionMode" type="Int">', config)
        self.assertRegex(config,
                         r'<entry name="MotionMode" type="Int">\s*<default>-1</default>')
        self.assertIn("configuration.MotionMode", qml,
                      "the scene must READ MotionMode, not merely declare it")
        self.assertIn("configuration.AmbientMotion", qml,
                      "MotionMode's -1 sentinel must fall back to the legacy Boolean, "
                      "or an upgraded desktop loses the motion setting it already had")
        self.assertIn("interval: 90000", qml)
        self.assertIn("duration: 1800", qml)
        self.assertNotRegex(qml, r"interval:\s*(?:[1-9]\d{0,3}|[1-5]\d{4})\b")
        self.assertIn("sourceSize: Qt.size(root.width * Screen.devicePixelRatio", qml)
        # Every stock Plasma wallpaper plugin ships a config page; this one did
        # not, so 'Configure Desktop and Wallpaper' offered the owner of the MoOS
        # scene no way to change the image, the motion or the dashboard, and the
        # settings dialog read as broken rather than as configured elsewhere.
        self.assertTrue((package / "contents/ui/config.qml").is_file(),
                        "the MoOS scene must ship contents/ui/config.qml — that path "
                        "is the KPackage Plasma/Wallpaper config contract")
        # Every infinite animation in the package must REST. An unguarded infinite
        # QML animation pins the render loop at the full frame rate and repaints
        # the whole window for as long as it runs — about 11% of a CPU core
        # regardless of the item's size — so a loop with no PauseAnimation is a
        # permanent tax even at the calm default level.
        # Read the loop's ACTUAL block by matching its braces, not a fixed number of
        # characters. A 1400-character window silently passed for as long as every
        # loop happened to be short, then failed on a correct animation whose rest
        # simply sat further down than the window reached — a magic number gating a
        # relationship. The block is what the rule is about, so measure the block.
        for _qml in sorted((package / "contents/ui").glob("*.qml")):
            _t = _qml.read_text(encoding="utf-8")
            for _loop in re.finditer(r"loops:\s*Animation\.Infinite", _t):
                _open = _t.rfind("{", 0, _loop.start())
                _depth, _i = 1, _open + 1
                while _i < len(_t) and _depth:
                    _depth += (_t[_i] == "{") - (_t[_i] == "}")
                    _i += 1
                _body = _t[_open:_i]
                self.assertIn("PauseAnimation", _body,
                              f"{_qml.name} has an infinite animation with no rest — "
                              "every loop in this package must have a duty cycle")

    def test_panel_clock_localizes_compact_date_in_rtl(self) -> None:
        qml = (
            SHARE
            / "plasma/plasmoids/org.moos.nova.clock/contents/ui/main.qml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'displayLocale: rtl ? Qt.locale("ar") : Qt.locale()', qml
        )
        # The pattern must go through Locale.toString. This test used to assert
        # `Qt.formatDate(now, locale, "ddd d MMM")`, which LOOKS like it applies
        # the pattern and does not: the three-argument overload takes a
        # Locale.FormatType, so the string was discarded and the dock rendered
        # the full long date instead of the compact one this test is named for.
        # A green assertion sat on top of the broken call for a whole revision.
        self.assertIn(
            'root.displayLocale.toString(root.now, "ddd d MMM")', qml
        )
        self.assertNotIn(
            'Qt.formatDate(root.now, root.displayLocale, "ddd d MMM")', qml,
            "Qt.formatDate ignores a format string in its locale overload",
        )

    def test_first_party_icons_are_owned_and_take_theme_precedence(self) -> None:
        expected = {
            "moos-moai.svg",
            "moos-moplayer.svg",
            "moos-pc-remote.svg",
            "moos-installer.svg",
            "moos-recovery.svg",
            "moos-store.svg",
            "moos-themes.svg",
            "moos-updater.svg",
            "moos-welcome.svg",
        }
        scalable = SHARE / "icons/hicolor/scalable/apps"
        self.assertTrue(expected <= {path.name for path in scalable.glob("moos-*.svg")})
        for icon in expected:
            ET.parse(scalable / icon)
            stem = pathlib.Path(icon).stem
            for size in ICON_SIZES:
                raster = (
                    SHARE
                    / "icons/hicolor"
                    / f"{size}x{size}"
                    / "apps"
                    / f"{stem}.png"
                )
                with self.subTest(icon=stem, size=size):
                    self.assertTrue(raster.is_file(), raster)
                    with Image.open(raster) as image:
                        self.assertEqual(image.size, (size, size))
                        self.assertEqual(image.mode, "RGBA")

        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
        self.assertEqual(
            build.count("Directories=moos/apps/scalable,"),
            3,
            "both theme builders plus the fail-loud gate must name the overlay",
        )
        self.assertIn("Name=MoOS UI|", build)
        self.assertIn("Name=MoOS UI Light|", build)
        self.assertIn("test ! -L", build)

        desktop = (
            SHARE / "applications/org.moos.themepicker.desktop"
        ).read_text(encoding="utf-8")
        self.assertIn("\nIcon=moos-themes\n", desktop)
        launcher = (
            ROOT / "system_files/usr/bin/moos-theme-picker"
        ).read_text(encoding="utf-8")
        self.assertIn("--app-id org.moos.themepicker --icon moos-themes", launcher)

    def test_default_cursor_never_falls_back_to_a_foreign_identity(self) -> None:
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
        self.assertIn("Name=MoOS Pointer|", build)
        self.assertIn("Name=MoOS Pointer Dark|", build)
        self.assertIn(
            "cat > /usr/share/icons/default/index.theme <<'EOF'", build
        )
        self.assertIn("Inherits=MoOS", build)

    def test_every_font_family_named_in_qml_is_one_the_image_ships(self) -> None:
        """A `font.family:` naming a family the image does not install does not
        fail, warn, or log — Qt silently substitutes, and the surface just quietly
        stops looking like MoOS.

        Found live: the MoOS launcher asked for "IBM Plex Mono" in three places on
        an image that installs `ibm-plex-sans-fonts` and `ibm-plex-sans-arabic-fonts`
        but never a Plex mono. `fc-match "IBM Plex Mono"` on the running machine
        answered **Noto Sans Arabic** — an Arabic PROPORTIONAL face standing in for
        a monospace one, inside the launcher's result counters. MoOS's own design
        contract names JetBrains Mono as the code face, and that one is installed.

        So the rule is a relationship, not a list of blessed strings: every family
        a shipped QML asks for by name must be traceable to something this build
        actually puts on disk — a dnf package in build.sh, or a font file carried in
        system_files/."""
        # family -> the evidence that the image provides it
        PROVIDERS = {
            "IBM Plex Sans": ("dnf", "ibm-plex-sans-fonts"),
            "IBM Plex Sans Arabic": ("dnf", "ibm-plex-sans-arabic-fonts"),
            "JetBrains Mono": ("dnf", "jetbrains-mono-fonts"),
            "Inter": ("file", "system_files/usr/share/fonts/inter/Inter.ttf"),
        }
        build = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")

        used: dict[str, list[str]] = {}
        for qml in sorted((ROOT / "system_files").rglob("*.qml")):
            for family in re.findall(r'font\.family:\s*"([^"]+)"',
                                     qml.read_text(encoding="utf-8", errors="replace")):
                used.setdefault(family, []).append(
                    qml.relative_to(ROOT).as_posix())

        self.assertTrue(used, "no font.family literals found — did the tree move?")
        for family, files in sorted(used.items()):
            with self.subTest(family=family):
                self.assertIn(
                    family, PROVIDERS,
                    f"{family!r} is requested by {files[0]} (and {len(files) - 1} "
                    "other places) but nothing in this test can prove the image "
                    "ships it. Install it in build.sh or carry it in system_files/, "
                    "then name the evidence here — otherwise Qt substitutes another "
                    "face and the surface silently stops looking like MoOS.")
                kind, evidence = PROVIDERS[family]
                if kind == "dnf":
                    self.assertIn(
                        evidence, build,
                        f"{family!r} is used in QML but build.sh no longer installs "
                        f"{evidence}")
                else:
                    self.assertTrue(
                        (ROOT / evidence).is_file(),
                        f"{family!r} is used in QML but {evidence} is not in the tree")


if __name__ == "__main__":
    unittest.main()
