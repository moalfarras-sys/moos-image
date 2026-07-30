#!/usr/bin/env python3
"""Runtime gates for first-party GTK theming and Mo PC Remote refreshes."""

from __future__ import annotations

import ast
import configparser
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import time
import types
import unittest

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk  # noqa: E402
    HAS_GI = True
except (ImportError, ValueError):
    # ubuntu-latest may have no PyGObject at all, or PyGObject without the GTK4
    # typelib (``require_version`` raises ValueError in that second case).
    # Keep the pure palette and concurrency contracts active there; only the
    # real Gio/CSS parser test skips. The shipped image and local MoOS host
    # exercise the real types.
    HAS_GI = False
    gi = types.ModuleType("gi")
    gi.require_version = lambda *_args: None

    class _Application:
        pass

    class _Settings:
        @staticmethod
        def get_default():
            return None

    class _GLib:
        Error = Exception
        idle_add = staticmethod(lambda *_args: 1)
        timeout_add = staticmethod(lambda *_args: 1)
        source_remove = staticmethod(lambda *_args: None)
        markup_escape_text = staticmethod(lambda value: value)

    Gtk = types.SimpleNamespace(Application=_Application, Settings=_Settings)
    GLib = _GLib()
    repository = types.ModuleType("gi.repository")
    repository.Gtk = Gtk
    repository.Gdk = types.SimpleNamespace()
    repository.Gio = types.SimpleNamespace()
    repository.GLib = GLib
    gi.repository = repository
    # ``import gi`` may already have succeeded before GTK4 resolution failed.
    # Replace that partial real module rather than leaving moos_ui2 to hit the
    # same unavailable namespace again during its own import.
    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = repository


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("MOOS_GTK_TEST_ROOT", DEFAULT_ROOT)).resolve()
SHARE = ROOT / "system_files/usr/share"
UI2_PATH = ROOT / "system_files/usr/lib/moos/moos_ui2.py"
REMOTE_PATH = ROOT / "system_files/usr/bin/mo-pc-remote"
UPDATER_PATH = ROOT / "system_files/usr/bin/moos-update"
RECOVERY_PATH = ROOT / "system_files/usr/bin/moos-rollback"


def load_modules():
    ui2_spec = importlib.util.spec_from_file_location("moos_ui2", UI2_PATH)
    if ui2_spec is None or ui2_spec.loader is None:
        raise RuntimeError(f"cannot load {UI2_PATH}")
    ui2 = importlib.util.module_from_spec(ui2_spec)
    sys.modules["moos_ui2"] = ui2
    ui2_spec.loader.exec_module(ui2)

    loader = importlib.machinery.SourceFileLoader(
        "mo_pc_remote_runtime_test", str(REMOTE_PATH)
    )
    remote_spec = importlib.util.spec_from_loader(loader.name, loader)
    if remote_spec is None:
        raise RuntimeError(f"cannot load {REMOTE_PATH}")
    remote = importlib.util.module_from_spec(remote_spec)
    loader.exec_module(remote)
    return ui2, remote


UI2, REMOTE = load_modules()


def parse_hex(value):
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise AssertionError(f"not a CSS hex colour: {value!r}")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def luminance(colour):
    channels = []
    for channel in colour:
        value = channel / 255
        channels.append(
            value / 12.92
            if value <= 0.04045
            else ((value + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first, second):
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def load_scheme(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(path, encoding="utf-8")
    return parser


def rgb_hex(value):
    return "#{:02X}{:02X}{:02X}".format(
        *(int(part.strip()) for part in value.split(","))
    )


def wait_until(predicate, timeout=2.0):
    context = GLib.MainContext.default()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class FakeProvider:
    def __init__(self):
        self.loads = []

    def load_from_data(self, css):
        self.loads.append(css)

    def load_from_string(self, css):
        self.loads.append(css)


class TestMoOSGtkRuntime(unittest.TestCase):
    maxDiff = None

    def test_session_locale_is_single_language_and_logical_start(self):
        cases = (
            ({"LANG": "ar_SA.UTF-8"}, "ar", True, "عربي", 1.0),
            ({"LC_MESSAGES": "fa_IR", "LANG": "en_US"}, "fa", True, "عربي", 1.0),
            ({"LC_ALL": "en_GB.UTF-8", "LANG": "ar_SA"}, "en", False, "English", 0.0),
            ({"LANG": "de_DE.UTF-8"}, "de", False, "English", 0.0),
        )
        for environment, language, rtl, visible, alignment in cases:
            with self.subTest(environment=environment):
                self.assertEqual(UI2.session_language(environment), language)
                self.assertEqual(UI2.ui_is_rtl(environment), rtl)
                self.assertEqual(
                    UI2.local_text("عربي", "English", environment),
                    visible,
                )
                self.assertEqual(UI2.logical_start(environment), alignment)

    def test_first_party_gtk_chrome_never_concatenates_two_locales(self):
        allowed_products = re.compile(
            r"\b(?:MoOS|MoPC|Mo AI|Tailscale|PipeWire|QR|PIN)\b"
        )
        for path in (UPDATER_PATH, RECOVERY_PATH, REMOTE_PATH):
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            with self.subTest(path=path.name):
                self.assertIn("local_text", source)
                self.assertNotRegex(source, r"xalign\s*=\s*0(?:[.,)])")
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Constant) or not isinstance(
                        node.value, str
                    ):
                        continue
                    value = node.value
                    if not re.search(r"[\u0600-\u06ff]", value):
                        continue
                    stripped = allowed_products.sub("", value)
                    self.assertNotRegex(
                        stripped,
                        r"[A-Za-z]{3,}",
                        f"{path.name}:{node.lineno} concatenates two visible locales",
                    )

    def test_updater_never_waits_for_bootc_on_gtk_callback(self):
        source = UPDATER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        updater = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "Updater"
        )
        run_async = next(
            node
            for node in updater.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_async"
        )
        calls = {
            (
                node.func.attr
                if isinstance(node.func, ast.Attribute)
                else node.func.id
                if isinstance(node.func, ast.Name)
                else ""
            )
            for node in ast.walk(run_async)
            if isinstance(node, ast.Call)
        }
        self.assertNotIn(
            "wait",
            calls,
            "bootc can close stdout before exit; proc.wait() would freeze GTK",
        )
        self.assertIn("poll", calls)
        self.assertIn("io_add_watch", calls)
        self.assertIn("timeout_add", calls)

    def test_all_16_kde_schemes_map_to_accessible_gtk_roles(self):
        schemes = sorted((SHARE / "color-schemes").glob("MoOSUI2*.colors"))
        self.assertEqual(len(schemes), 16)

        for path in schemes:
            with self.subTest(scheme=path.name):
                source = load_scheme(path)
                palette = UI2.palette_from_color_scheme(path)
                self.assertEqual(set(palette), set(UI2.PALETTE_ROLES))
                self.assertEqual(
                    palette["on_accent"],
                    rgb_hex(source["Colors:Selection"]["ForegroundNormal"]),
                    "GTK on_accent must be KDE Selection.ForegroundNormal exactly",
                )
                pairs = (
                    ("text", "canvas", 4.5),
                    ("text", "card", 4.5),
                    ("text", "raised", 4.5),
                    ("text", "surface", 4.5),
                    ("muted", "canvas", 4.5),
                    ("muted", "card", 4.5),
                    ("muted", "surface", 4.5),
                    ("positive", "canvas", 4.5),
                    ("positive", "card", 4.5),
                    ("warning", "canvas", 4.5),
                    ("warning", "card", 4.5),
                    ("negative", "canvas", 4.5),
                    ("negative", "card", 4.5),
                    ("on_accent", "primary", 4.5),
                    ("on_negative", "negative", 4.5),
                    ("outline", "canvas", 3.0),
                    ("outline", "surface", 3.0),
                    ("outline", "card", 3.0),
                    ("outline", "raised", 3.0),
                )
                for foreground, background, minimum in pairs:
                    ratio = contrast(
                        parse_hex(palette[foreground]),
                        parse_hex(palette[background]),
                    )
                    self.assertGreaterEqual(
                        ratio,
                        minimum,
                        f"{path.name}: {foreground}/{background} is "
                        f"{ratio:.2f}:1",
                    )

                css = UI2.ui2_css(palette)
                suggested = css.split(
                    "window.moos-ui2 button.suggested-action", 1
                )[1].split("}", 1)[0]
                destructive = css.split(
                    "window.moos-ui2 button.destructive-action", 1
                )[1].split("}", 1)[0]
                self.assertIn("background-color: @ui2_primary", suggested)
                self.assertNotIn(
                    "linear-gradient",
                    suggested,
                    "Selection ink is paired with primary, not secondary",
                )
                self.assertIn("border-color: @ui2_outline", suggested)
                self.assertIn("color: @ui2_on_negative", destructive)
                # GTK's own parser is the final word on whether generated CSS
                # reaches an application.
                if HAS_GI:
                    Gtk.CssProvider().load_from_string(css)

    def test_active_scheme_resolution_covers_every_palette_and_falls_back(self):
        with tempfile.TemporaryDirectory(prefix="moos-gtk-scheme-") as temp:
            config = Path(temp) / "kdeglobals"
            schemes = sorted((SHARE / "color-schemes").glob("MoOSUI2*.colors"))
            for path in schemes:
                config.write_text(
                    f"[General]\nColorScheme={path.stem}\n", encoding="utf-8"
                )
                expected = UI2.palette_from_color_scheme(path)
                actual = UI2.active_ui2_palette(
                    config_path=config,
                    data_dirs=(SHARE,),
                    prefers_dark=path.stem != "MoOSUI2Light",
                )
                self.assertEqual(actual, expected, path.stem)

            config.write_text(
                "[General]\nColorScheme=../../not-a-scheme\n", encoding="utf-8"
            )
            self.assertEqual(
                UI2.active_ui2_palette(
                    config_path=config,
                    data_dirs=(SHARE,),
                    prefers_dark=False,
                ),
                UI2.UI2_LIGHT,
            )

            bad_data = Path(temp) / "data"
            bad_scheme = bad_data / "color-schemes/Broken.colors"
            bad_scheme.parent.mkdir(parents=True)
            bad_scheme.write_text(
                "[Colors:Window]\nBackgroundNormal=nope\n", encoding="utf-8"
            )
            config.write_text(
                "[General]\nColorScheme=Broken\n", encoding="utf-8"
            )
            self.assertEqual(
                UI2.active_ui2_palette(
                    config_path=config,
                    data_dirs=(bad_data,),
                    prefers_dark=True,
                ),
                UI2.UI2_DARK,
            )

            unsafe_scheme = bad_data / "color-schemes/Unsafe.colors"
            unsafe = load_scheme(
                SHARE / "color-schemes/MoOSUI2Dark.colors"
            )
            unsafe["Colors:Selection"]["ForegroundNormal"] = (
                unsafe["Colors:Selection"]["BackgroundNormal"]
            )
            with unsafe_scheme.open("w", encoding="utf-8") as destination:
                unsafe.write(destination)
            config.write_text(
                "[General]\nColorScheme=Unsafe\n", encoding="utf-8"
            )
            self.assertEqual(
                UI2.active_ui2_palette(
                    config_path=config,
                    data_dirs=(bad_data,),
                    prefers_dark=True,
                ),
                UI2.UI2_DARK,
                "an installed scheme with unreadable selected text must fail safe",
            )

    @unittest.skipUnless(HAS_GI, "PyGObject/Gio is unavailable on this runner")
    def test_kdeglobals_change_restyles_live_and_burst_is_coalesced(self):
        with tempfile.TemporaryDirectory(prefix="moos-gtk-watch-") as temp:
            config = Path(temp) / "kdeglobals"
            config.write_text(
                "[General]\nColorScheme=MoOSUI2Dark\n", encoding="utf-8"
            )
            provider = FakeProvider()
            controller = UI2.UI2StyleController(
                provider,
                config_path=config,
                data_dirs=(SHARE,),
                settings=False,
                prefers_dark=True,
            )
            self.addCleanup(controller.close)
            self.assertEqual(len(provider.loads), 1)
            self.assertIn(
                "@define-color ui2_primary #4ED7C8;", provider.loads[-1]
            )

            for _ in range(20):
                controller.schedule_restyle()
            self.assertTrue(wait_until(lambda: len(provider.loads) >= 2))
            self.assertEqual(
                len(provider.loads),
                2,
                "twenty notifications must collapse into one CSS reload",
            )

            replacement = Path(temp) / "kdeglobals.new"
            replacement.write_text(
                "[General]\nColorScheme=MoOSUI2Daylight\n", encoding="utf-8"
            )
            os.replace(replacement, config)
            self.assertTrue(
                wait_until(
                    lambda: any(
                        "@define-color ui2_primary #0284C7;" in css
                        for css in provider.loads[2:]
                    )
                ),
                "atomic kdeglobals rewrite did not restyle the live provider",
            )
            self.assertIn(
                "@define-color ui2_on_accent #07111E;", provider.loads[-1]
            )

    def test_live_restyle_source_contract_is_wired_into_first_party_apps(self):
        ui2_source = UI2_PATH.read_text(encoding="utf-8")
        remote_source = REMOTE_PATH.read_text(encoding="utf-8")
        self.assertIn("def watch_kdeglobals(", ui2_source)
        self.assertIn("monitor_directory(", ui2_source)
        self.assertIn(
            "self._monitor = watch_kdeglobals(self.schedule_restyle",
            ui2_source,
        )
        self.assertIn(
            "self._style_controller = UI2StyleController(self._css)",
            ui2_source,
        )
        self.assertIn(
            "self.style_controller=UI2StyleController(self.style_provider)",
            remote_source,
        )

    def test_remote_refresh_returns_immediately_and_coalesces_bursts(self):
        idle_queue = queue.Queue()
        first_started = threading.Event()
        release_first = threading.Event()
        collect_calls = []
        collect_threads = []
        deliveries = []
        delivery_threads = []
        main_thread = threading.get_ident()

        def collect():
            collect_calls.append(len(collect_calls) + 1)
            collect_threads.append(threading.get_ident())
            if len(collect_calls) == 1:
                first_started.set()
                release_first.wait(2)
            return collect_calls[-1]

        def deliver(payload, error):
            deliveries.append((payload, error))
            delivery_threads.append(threading.get_ident())

        def idle_add(callback, *args):
            idle_queue.put((callback, args))
            return idle_queue.qsize()

        worker = REMOTE.CoalescingWorker(collect, deliver, idle_add=idle_add)
        started = time.monotonic()
        self.assertTrue(worker.request())
        request_elapsed = time.monotonic() - started
        self.assertLess(
            request_elapsed,
            0.05,
            "refresh request waited for the collector instead of returning to GTK",
        )
        self.assertTrue(first_started.wait(1))
        for _ in range(25):
            worker.request()
        release_first.set()

        callback, args = idle_queue.get(timeout=2)
        callback(*args)  # emulate GLib.idle_add dispatch on the main thread
        callback, args = idle_queue.get(timeout=2)
        callback(*args)
        if worker._thread:
            worker._thread.join(timeout=1)

        self.assertEqual(
            collect_calls,
            [1, 2],
            "twenty-five overlapping requests must become one trailing refresh",
        )
        self.assertEqual(deliveries, [(1, None), (2, None)])
        self.assertTrue(all(thread != main_thread for thread in collect_threads))
        self.assertEqual(delivery_threads, [main_thread, main_thread])

    def test_remote_ui_apply_path_contains_no_blocking_io(self):
        source = REMOTE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        app = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "App"
        )
        apply_refresh = next(
            node
            for node in app.body
            if isinstance(node, ast.FunctionDef) and node.name == "_apply_refresh"
        )
        refresh = next(
            node
            for node in app.body
            if isinstance(node, ast.FunctionDef) and node.name == "refresh"
        )
        banned = {
            "run", "active", "tailscale_url", "qr_png",
            "collect_remote_snapshot", "open",
        }
        calls = {
            node.func.id
            for node in ast.walk(apply_refresh)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(
            calls & banned,
            f"GTK apply path still performs blocking I/O: {sorted(calls & banned)}",
        )
        refresh_source = ast.get_source_segment(source, refresh) or ""
        self.assertIn("self._refresh_worker.request()", refresh_source)
        self.assertNotIn("collect_remote_snapshot()", refresh_source)
        self.assertIn("GLib.idle_add", source)
        self.assertIn(
            'active("firewalld.service", user=False)',
            source,
            "firewalld is a system service, not a --user unit",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
