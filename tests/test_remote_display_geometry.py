#!/usr/bin/env python3
"""Exercise the real monitor watcher without inheriting the workstation bus."""
import ast
import tempfile
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
            self.display, self.pending.append, self.renewals.append)

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

    def test_hotplug_invalidates(self):
        monitor = Monitor()
        self.display.monitors.append(monitor)
        self.display.emit("monitor-added", monitor)
        self.assertIn("notify::geometry", monitor.signals)
        self.drain()
        self.assertEqual(len(self.renewals), 1)

    def test_empty_monitor_list_waits_for_a_real_output(self):
        old = self.display.monitors.pop()
        self.display.emit("monitor-removed", old)
        self.drain()
        self.assertFalse(self.renewals)
        self.assertFalse(self.watch.invalid)

        replacement = Monitor()
        self.display.monitors.append(replacement)
        self.display.emit("monitor-added", replacement)
        self.drain()
        self.assertEqual(self.renewals, ["output replaced, same geometry 1280x720+0+0@2"])

    def test_replaced_monitor_with_identical_geometry_invalidates(self):
        self.display.monitors[0] = Monitor()
        self.display.emit("monitor-added", self.display.monitors[0])
        self.drain()
        self.assertEqual(len(self.renewals), 1)
        # The log line must tell a returning output from a real change.
        self.assertEqual(self.renewals[0], "output replaced, same geometry 1280x720+0+0@2")

    def test_zero_size_placeholder_does_not_renew_mid_handshake(self):
        # On the station HDMI loss leaves one 0x0 GDK monitor, rather than an
        # empty list. It must not invalidate the grant before Start saves its
        # replacement token. Returning to the real extent is compared normally.
        old = self.display.monitors[0]
        self.display.monitors[0] = Monitor(width=0, height=0)
        self.display.emit("monitor-added", self.display.monitors[0])
        self.drain()
        self.assertFalse(self.watch.invalid)
        self.assertEqual(self.renewals, [])
        self.display.monitors[0] = old
        self.display.emit("monitor-added", old)
        self.drain()
        self.assertEqual(self.renewals, [])
        old.rect.width = 1536
        old.emit("notify::geometry", None)
        self.drain()
        self.assertEqual(len(self.renewals), 1)

    def test_renewal_names_the_old_and_new_geometry(self):
        monitor = self.display.monitors[0]
        monitor.rect.width, monitor.rect.height = 1536, 864
        monitor.emit("notify::geometry", None)
        self.drain()
        self.assertEqual(self.renewals, ["1280x720+0+0@2 -> 1536x864+0+0@2"])
        self.setUp()
        self.display.monitors.pop()
        self.display.emit("monitor-removed", None)
        self.drain()
        self.assertFalse(self.renewals)

    def test_compositor_closed_is_not_healthy(self):
        self.display.emit("closed", False)
        self.assertEqual(self.renewals, ["compositor connection closed"])

    def test_watch_is_wired_before_portal_grant_without_polling(self):
        source = SOURCE.read_text()
        self.assertLess(source.index("display_watch = watch_display_geometry()"),
                        source.index('created = request("CreateSession"'))
        self.assertIn('os.environ["GDK_BACKEND"] = "wayland"', source)
        self.assertIn("DisplayGeometryWatch(display, GLib.idle_add", source)
        self.assertIn('die(EXIT_LOST, "display geometry changed;', source)
        self.assertIn('f" ({detail})"', source)


def extract(*names):
    """Load the named top-level classes/functions of the helper without running it."""
    tree = ast.parse(SOURCE.read_text())
    nodes = [n for n in tree.body
             if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    scope = {"os": __import__("os")}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), scope)
    return scope


class GrantKeptTests(unittest.TestCase):
    """The owner's one-time approval must survive a renewal seen mid-handshake."""

    def test_a_change_during_the_handshake_waits_for_the_saved_token(self):
        guard = extract("GrantGuard")["GrantGuard"]()
        order = []
        guard.renew(lambda: order.append("renew"))
        guard.renew(lambda: order.append("second renew"))
        self.assertEqual(order, [], "renewed before the replacement token was stored")
        order.append("token saved")
        guard.stored()
        self.assertEqual(order, ["token saved", "renew"])
        guard.renew(lambda: order.append("later change"))
        self.assertEqual(order[-1], "later change")

    def test_the_token_is_stored_before_the_guard_releases(self):
        source = SOURCE.read_text()
        saved = source.index('save_token(started.get("restore_token"))')
        released = source.index("grant_guard.stored()")
        self.assertLess(saved, released)
        self.assertEqual(source[saved:released].count("\n"), 1,
                         "nothing may run between storing the token and releasing the guard")
        watch = source[source.index("def watch_display_geometry"):saved]
        self.assertIn("grant_guard.renew(", watch)

    def test_token_file_is_replaced_whole_and_private(self):
        scope = extract("save_token")
        with tempfile.TemporaryDirectory() as home:
            target = Path(home, "MoRemote", "portal-restore-token")
            scope.update(TOKEN_FILE=str(target), emit=lambda **_m: None)
            target.parent.mkdir()
            target.write_text("old-token")
            scope["save_token"]("new-token")
            self.assertEqual(target.read_text(), "new-token")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertFalse(Path(str(target) + ".new").exists())
            scope["save_token"]("")
            self.assertEqual(target.read_text(), "new-token", "an empty answer erased the grant")


if __name__ == "__main__":
    unittest.main()
