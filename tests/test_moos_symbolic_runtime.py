#!/usr/bin/env python3
"""Runtime rendering gate for the MoOS Tidal Cut symbolic icon family.

The static companion test proves source ownership and palette-role markup.
This gate asks the installed GTK and KDE icon resolvers for the committed
assets, then lets librsvg rasterise the exact SVGs at every supported review
size.  It catches valid XML that is blank, clipped, loses its counters under a
symbolic renderer, or stops adapting when the palette changes.
"""

from __future__ import annotations

import importlib.util
import io
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "artwork/generate_moos_symbolic_icons.py"
ACTION_DIR = ROOT / "system_files/usr/share/icons/hicolor/scalable/actions"
ICON_ROOT = ROOT / "system_files/usr/share/icons"
SIZES = (16, 20, 24, 64, 128)

spec = importlib.util.spec_from_file_location("moos_symbolic_generator_runtime", GENERATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {GENERATOR_PATH}")
generator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generator
spec.loader.exec_module(generator)

try:
    import cairo
    import gi
    from PIL import Image

    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg

    HAVE_RASTER_RUNTIME = True
except (ImportError, ValueError):
    HAVE_RASTER_RUNTIME = False

try:
    import gi as gtk_gi

    gtk_gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    HAVE_GTK_RUNTIME = True
except (ImportError, ValueError):
    HAVE_GTK_RUNTIME = False


def _palette_source(source: str, *, dark: bool) -> str:
    colours = {
        "#243238": "#e1f0ec" if dark else "#203034",
        "#147d72": "#43e0c1" if dark else "#006d67",
        "#8a5a00": "#ffd166" if dark else "#8a5a00",
        "#a9364b": "#ff8296" if dark else "#a9364b",
    }
    for current, replacement in colours.items():
        source = source.replace(f"color: {current}", f"color: {replacement}")
    return source


@unittest.skipUnless(HAVE_RASTER_RUNTIME, "librsvg + cairo + Pillow are required")
class MoOSSymbolicRasterTests(unittest.TestCase):
    def _render(self, name: str, size: int, *, dark: bool = False):
        source = (ACTION_DIR / f"moos-{name}-symbolic.svg").read_text(encoding="utf-8")
        handle = Rsvg.Handle.new_from_data(_palette_source(source, dark=dark).encode())
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        context = cairo.Context(surface)
        viewport = Rsvg.Rectangle()
        viewport.x = viewport.y = 0
        viewport.width = viewport.height = size
        self.assertTrue(handle.render_document(context, viewport), name)
        output = io.BytesIO()
        surface.write_to_png(output)
        output.seek(0)
        return Image.open(output).convert("RGBA")

    @staticmethod
    def _holes(alpha, threshold: int = 24) -> int:
        width, height = alpha.size
        pixels = alpha.load()
        outside: set[tuple[int, int]] = set()
        queue: deque[tuple[int, int]] = deque()

        def enqueue(x: int, y: int) -> None:
            point = (x, y)
            if point not in outside and pixels[x, y] <= threshold:
                outside.add(point)
                queue.append(point)

        for x in range(width):
            enqueue(x, 0)
            enqueue(x, height - 1)
        for y in range(height):
            enqueue(0, y)
            enqueue(width - 1, y)

        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < width and 0 <= ny < height:
                    enqueue(nx, ny)

        visited = set(outside)
        holes = 0
        for y in range(height):
            for x in range(width):
                if pixels[x, y] > threshold or (x, y) in visited:
                    continue
                visited.add((x, y))
                component = [(x, y)]
                area = 0
                while component:
                    px, py = component.pop()
                    area += 1
                    for nx, ny in (
                        (px + 1, py),
                        (px - 1, py),
                        (px, py + 1),
                        (px, py - 1),
                    ):
                        point = (nx, ny)
                        if (
                            0 <= nx < width
                            and 0 <= ny < height
                            and point not in visited
                            and pixels[nx, ny] <= threshold
                        ):
                            visited.add(point)
                            component.append(point)
                if area >= 4:
                    holes += 1
        return holes

    @staticmethod
    def _similarity(first, second) -> float:
        left = first.getchannel("A").tobytes()
        right = second.getchannel("A").tobytes()
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = sum(a * a for a in left)
        right_norm = sum(b * b for b in right)
        return dot / math.sqrt(left_norm * right_norm)

    def test_all_sizes_have_ink_optical_air_and_preserved_counters(self) -> None:
        fingerprints: dict[bytes, str] = {}
        for name, symbol in generator.SYMBOLS.items():
            for size in SIZES:
                with self.subTest(icon=name, size=size):
                    image = self._render(name, size)
                    alpha = image.getchannel("A")
                    bounds = alpha.getbbox()
                    self.assertIsNotNone(bounds, f"{name} is blank at {size}px")
                    assert bounds is not None
                    self.assertGreater(bounds[0], 0, f"{name} touches the left edge at {size}px")
                    self.assertGreater(bounds[1], 0, f"{name} touches the top edge at {size}px")
                    self.assertLess(bounds[2], size, f"{name} touches the right edge at {size}px")
                    self.assertLess(bounds[3], size, f"{name} touches the bottom edge at {size}px")
                    coverage = sum(value >= 16 for value in alpha.tobytes()) / (size * size)
                    self.assertGreaterEqual(coverage, 0.07, f"{name} is too faint at {size}px")
                    self.assertLessEqual(coverage, 0.72, f"{name} becomes a block at {size}px")

            large = self._render(name, 128)
            self.assertGreaterEqual(
                self._holes(large.getchannel("A")),
                symbol.min_holes,
                f"{name} lost a designed internal cut under librsvg",
            )
            fingerprint = self._render(name, 24).getchannel("A").tobytes()
            self.assertNotIn(
                fingerprint,
                fingerprints,
                f"{name} duplicates the silhouette of {fingerprints.get(fingerprint)}",
            )
            fingerprints[fingerprint] = name

    def test_light_and_dark_palettes_recolour_without_changing_geometry(self) -> None:
        for name in generator.SYMBOLS:
            with self.subTest(icon=name):
                light = self._render(name, 24, dark=False)
                dark = self._render(name, 24, dark=True)
                self.assertEqual(
                    light.getchannel("A").tobytes(),
                    dark.getchannel("A").tobytes(),
                    f"{name} changes geometry between light and dark palettes",
                )
                self.assertNotEqual(
                    light.convert("RGB").tobytes(),
                    dark.convert("RGB").tobytes(),
                    f"{name} ignores dynamic palette colours",
                )

        warning = self._render("warning", 128, dark=False)
        danger = self._render("danger", 128, dark=False)
        warning_opaque = {
            pixel[:3]
            for pixel in warning.get_flattened_data()
            if pixel[3] == 255
        }
        danger_opaque = {
            pixel[:3]
            for pixel in danger.get_flattened_data()
            if pixel[3] == 255
        }
        self.assertIn((138, 90, 0), warning_opaque)
        self.assertIn((169, 54, 75), danger_opaque)

    def test_visually_confusable_system_states_remain_distinct(self) -> None:
        pairs = {
            ("settings", "sun"): 0.75,
            ("warning", "danger"): 0.85,
            ("power", "bolt"): 0.75,
            ("search", "target"): 0.80,
        }
        for (first, second), maximum in pairs.items():
            with self.subTest(first=first, second=second):
                self.assertLess(
                    self._similarity(self._render(first, 24), self._render(second, 24)),
                    maximum,
                    f"{first} and {second} are too similar at control size",
                )


@unittest.skipUnless(HAVE_GTK_RUNTIME, "GTK 4 introspection is required")
class MoOSSymbolicGtkResolverTests(unittest.TestCase):
    def test_gtk_resolves_every_symbol_as_the_owned_hicolor_asset(self) -> None:
        theme = Gtk.IconTheme.new()
        # add_search_path() appends after the live session's user/system paths.
        # On an installed MoOS machine that lets GTK satisfy every lookup from
        # /usr/share/icons before it ever reaches this checkout, producing a
        # green test for stale installed bytes. Replace the resolver path
        # completely: this gate is about the repository, not the running image.
        theme.set_search_path([str(ICON_ROOT)])
        theme.set_theme_name("hicolor")
        self.assertEqual(theme.get_search_path(), [str(ICON_ROOT)])
        for name in generator.SYMBOLS:
            icon_name = f"moos-{name}-symbolic"
            for size in SIZES:
                with self.subTest(icon=icon_name, size=size):
                    paintable = theme.lookup_icon(
                        icon_name,
                        None,
                        size,
                        1,
                        Gtk.TextDirection.LTR,
                        Gtk.IconLookupFlags.FORCE_SYMBOLIC,
                    )
                    self.assertIsNotNone(paintable, icon_name)
                    resolved = Path(paintable.get_file().get_path()).resolve()
                    self.assertEqual(
                        resolved,
                        (ACTION_DIR / f"{icon_name}.svg").resolve(),
                    )


def _isolated_kde_environment(runtime: Path) -> dict[str, str]:
    """An XDG profile with the repository as its only icon data root.

    KIconLoader reads both the active icon theme from kdeglobals and the system
    data roots.  Merely prepending the checkout is insufficient: under a booted
    MoOSUI2Light session it searches that installed theme first and returns
    /usr/share/icons/MoOSUI2Light, so a stale installed byte would pass a gate
    about the repository.  offscreen keeps this runnable with no display.
    """
    environment = os.environ.copy()
    environment.update({
        "HOME": str(runtime / "home"),
        "XDG_CACHE_HOME": str(runtime / "cache"),
        "XDG_CONFIG_HOME": str(runtime / "config"),
        "XDG_CONFIG_DIRS": str(runtime / "config-dirs"),
        "XDG_DATA_HOME": str(runtime / "data"),
        "XDG_DATA_DIRS": str(ROOT / "system_files/usr/share"),
        "QT_QPA_PLATFORM": "offscreen",
    })
    for key in (
        "HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_HOME",
    ):
        Path(environment[key]).mkdir(parents=True, exist_ok=True)
    return environment


@unittest.skipUnless(shutil.which("kiconfinder6"), "kiconfinder6 is required")
class MoOSAppMarkThemeResolverTests(unittest.TestCase):
    """Ask KDE which file it would paint, once per palette.

    This is the empirical half of "the app icons follow the theme".  MoOS pins
    FollowsColorScheme=false and bakes one copy of every mark per palette icon
    theme, so the claim is only true if KDE resolves moos-store to the ACTIVE
    theme's copy — not to hicolor's default-teal master, and not to Colloid's.
    Nothing about the markup can prove that; only the resolver can.
    """

    MARKS = ("moos-store", "moos-control-center", "moos-moplayer", "moos-welcome")
    THEMES = ("MoOSUI2Forge", "MoOSUI2NovaLight", "MoOSUI2Amethyst", "MoOSUI2Daylight")

    @staticmethod
    def _scheme_accent(theme: str) -> str:
        scheme = (
            ROOT / f"system_files/usr/share/color-schemes/{theme}.colors"
        ).read_text(encoding="utf-8")
        selection = scheme.split("[Colors:Selection]", 1)[1]
        red, green, blue = (
            int(part) for part in
            re.search(r"BackgroundNormal=([\d,]+)", selection)[1].split(",")[:3]
        )
        return f"#{red:02x}{green:02x}{blue:02x}"

    def test_each_palette_theme_resolves_to_its_own_baked_marks(self) -> None:
        accents: dict[str, str] = {}
        for theme in self.THEMES:
            expected_accent = self._scheme_accent(theme)
            with tempfile.TemporaryDirectory(prefix="moos-app-mark-kde-") as runtime:
                environment = _isolated_kde_environment(Path(runtime))
                (Path(environment["XDG_CONFIG_HOME"]) / "kdeglobals").write_text(
                    f"[Icons]\nTheme={theme}\n", encoding="utf-8"
                )
                for mark in self.MARKS:
                    result = subprocess.run(
                        ["kiconfinder6", mark],
                        check=False, text=True, capture_output=True, env=environment,
                    )
                    with self.subTest(theme=theme, mark=mark):
                        self.assertEqual(result.returncode, 0, result.stderr)
                        resolved = Path(result.stdout.strip()).resolve()
                        self.assertEqual(
                            resolved,
                            (ICON_ROOT / theme / "moos/apps/scalable" / f"{mark}.svg")
                            .resolve(),
                            f"{theme} does not win the lookup for {mark}; the user "
                            "would see another theme's colours",
                        )
                        accent = re.search(
                            r"\.ColorScheme-Highlight\s*\{\s*color:\s*(#[0-9a-fA-F]{6})",
                            resolved.read_text(encoding="utf-8"),
                        )
                        self.assertIsNotNone(accent, f"{theme}/{mark} has no accent ink")
                        self.assertEqual(
                            accent[1].lower(),
                            expected_accent,
                            f"KDE paints {mark} with {accent[1]} under {theme}, whose "
                            f"colour scheme selects {expected_accent}",
                        )
                accents[theme] = expected_accent

        self.assertEqual(
            len(set(accents.values())),
            len(self.THEMES),
            f"these palettes are indistinguishable on the dock: {accents}",
        )


@unittest.skipUnless(shutil.which("kiconfinder6"), "kiconfinder6 is required")
class MoOSSymbolicKdeResolverTests(unittest.TestCase):
    def test_kde_resolves_every_symbol_from_the_owned_overlay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="moos-symbolic-kde-") as runtime:
            environment = _isolated_kde_environment(Path(runtime))
            for name in generator.SYMBOLS:
                icon_name = f"moos-{name}-symbolic"
                result = subprocess.run(
                    ["kiconfinder6", icon_name],
                    check=False,
                    text=True,
                    capture_output=True,
                    env=environment,
                )
                with self.subTest(icon=icon_name):
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        Path(result.stdout.strip()).resolve(),
                        (ACTION_DIR / f"{icon_name}.svg").resolve(),
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
