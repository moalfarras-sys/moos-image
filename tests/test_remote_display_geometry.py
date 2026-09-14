#!/usr/bin/env python3
"""Exercise the real monitor watcher without inheriting the workstation bus."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "moremote/agent-linux/mo-remote-portal.py"


class Signals:
    def __init__(self):
        self.signals = {}

    def connect(self, name, callback):
        self.signals.setdefault(name, []).append(callback)

    def emit(self, name, *args):
        for callback in self.signals.get(name, []):
            callback(self, *args)


class Monitor(Signals):
    def __init__(self, width=1280, height=720):
        super().__init__()
        self.rect = SimpleNamespace(x=0, y=0, width=width, height=height)
        self.scale = 2

    def get_geometry(self):
        return self.rect

    def get_scale_factor(self):
        return self.scale


class Display(Signals):
    def __init__(self):
        super().__init__()
        self.monitors = [Monitor()]

    def get_n_monitors(self):
        return len(self.monitors)

    def get_monitor(self, index):
        return self.monitors[index]


class GeometryTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                    and n.name == "DisplayGeometryWatch")
        scope = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), scope)
        self.display = Display()
        self.pending = []
        self.renewals = []
        self.watch = scope["DisplayGeometryWatch"](
            self.display, self.pending.append, lambda: self.renewals.append(True))

    def drain(self):
        while self.pending:
            self.assertFalse(self.pending.pop(0)())

    def test_real_1280_to_1536_regression_renews_once(self):
        monitor = self.display.monitors[0]
        monitor.rect.width, monitor.rect.height = 1536, 864
        for _ in range(5):
            monitor.emit("notify::geometry", None)
        self.assertEqual(len(self.pending), 1)
        self.drain()
        monitor.emit("notify::geometry", None)
        self.drain()
        self.assertEqual(len(self.renewals), 1)

    def test_unchanged_notifications_do_not_restart_or_poll(self):
        self.assertFalse(self.pending)
        self.display.monitors[0].emit("notify::geometry", None)
        self.drain()
        self.assertFalse(self.renewals)
        self.assertFalse(self.pending)

    def test_move_rotation_and_scale_invalidate(self):
        for field, value in (("x", 100), ("y", -720), ("width", 720)):
            with self.subTest(field=field):
                self.setUp()
                setattr(self.display.monitors[0].rect, field, value)
                self.display.monitors[0].emit("notify::geometry", None)
                self.drain()
                self.assertEqual(len(self.renewals), 1)
        self.setUp()
        self.display.monitors[0].scale = 3
        self.display.monitors[0].emit("notify::scale-factor", None)
        self.drain()
        self.assertEqual(len(self.renewals), 1)

    def test_hotplug_and_unplug(self):
        for add in (True, False):
            with self.subTest(add=add):
                self.setUp()
                monitor = Monitor()
                if add:
                    self.display.monitors.append(monitor)
                    self.display.emit("monitor-added", monitor)
                    self.assertIn("notify::geometry", monitor.signals)
                else:
                    monitor = self.display.monitors.pop()
                    self.display.emit("monitor-removed", monitor)
                self.drain()
                self.assertEqual(len(self.renewals), 1)

    def test_replaced_monitor_with_identical_geometry_invalidates(self):
        self.display.monitors[0] = Monitor()
        self.display.emit("monitor-added", self.display.monitors[0])
        self.drain()
        self.assertEqual(len(self.renewals), 1)

    def test_compositor_closed_is_not_healthy(self):
        self.display.emit("closed", False)
        self.assertEqual(len(self.renewals), 1)

    def test_watch_is_wired_before_portal_grant_without_polling(self):
        source = SOURCE.read_text()
        self.assertLess(source.index("display_watch = watch_display_geometry()"),
                        source.index('created = request("CreateSession"'))
        self.assertIn('os.environ["GDK_BACKEND"] = "wayland"', source)
        self.assertIn("DisplayGeometryWatch(display, GLib.idle_add", source)
        self.assertIn('die(EXIT_LOST, "display geometry changed;', source)


if __name__ == "__main__":
    unittest.main()
