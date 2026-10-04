#!/usr/bin/env python3
"""Gate: the compositor rig can be run on an owner's machine without touching the owner's screen.

`scripts/station/compositor-rig/rig.sh` starts a second, invisible `kwin_wayland --virtual` so a
question about the cloud desktop (what does a smaller desktop cost, does a frame-rate cap help)
can be measured without restarting the compositor the owner is looking through. Its whole value
is that isolation. One careless edit — the default socket name, the real config home, the session
bus — and the next agent to run it takes a D-Bus name from the live compositor or rewrites the
owner's output configuration, on the one machine where the screen cannot be walked up to.

So the contract is checked here, on the script as it is written (comments removed), and its
argument checks are run for real with `systemd-run` replaced by a trap.
"""

from __future__ import annotations

import ast
import os
import py_compile
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RIG = ROOT / "scripts/station/compositor-rig"
SCRIPT = RIG / "rig.sh"
HELPER = ROOT / "moremote/agent-linux/mo-remote-portal.py"
BASH = shutil.which("bash") or "/bin/bash"
LIVE_UNITS = ("plasma-kwin_wayland", "plasma-plasmashell", "mo-remote-personal", "pipewire",
              "wireplumber", "xdg-desktop-portal", "plasma-workspace", "graphical-session")


def code() -> str:
    lines = []
    for line in SCRIPT.read_text(encoding="utf-8").splitlines():
        lines.append(re.sub(r"(^|\s)#.*$", "", line))
    return "\n".join(lines)


class Isolation(unittest.TestCase):
    def setUp(self):
        self.code = code()

    def test_it_is_valid_shell(self):
        done = subprocess.run([BASH, "-n", str(SCRIPT)], capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_its_socket_is_its_own(self):
        self.assertIn("SOCKET=wayland-rig", self.code)
        self.assertIn('--socket "$SOCKET"', self.code)
        self.assertNotIn("wayland-0", self.code, "the owner's socket must not be named at all")
        self.assertIn("--virtual", self.code, "without --virtual KWin would open a window on the "
                                              "owner's desktop instead of an invisible output")

    def test_its_home_and_config_are_its_own_and_the_originals_are_only_copied(self):
        isolated = re.search(r'ISOLATED="([^"]+)"', self.code)
        self.assertIsNotNone(isolated)
        env = isolated.group(1)
        for name in ("HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME"):
            self.assertRegex(env, rf"-E {name}=\$R/", f"{name} is not inside the rig's directory")
        # every write to the real config home would be the rig changing the owner's desktop
        for line in self.code.splitlines():
            if "$HOME/.config" in line:
                self.assertRegex(line.strip(), r'^cp "\$HOME/\.config/[^"]+" "\$R/',
                                 f"only a copy may read the owner's configuration: {line.strip()}")
        for line in self.code.splitlines():
            if re.search(r"\brm\b", line):
                self.assertTrue('"$R"' in line or '"$RT/$SOCKET"' in line,
                                f"the rig removes only its own directory and socket: {line.strip()}")

    def test_it_has_no_session_bus(self):
        isolated = re.search(r'ISOLATED="([^"]+)"', self.code).group(1)
        self.assertRegex(isolated, r"-E DBUS_SESSION_BUS_ADDRESS=unix:path=\$R/",
                         "with the real bus a second KWin competes for the first one's D-Bus names")
        launches = [l for l in self.code.splitlines() if "systemd-run" in l]
        self.assertEqual(len(launches), 3)
        for launch in launches[:2]:                    # the compositor and the workload
            self.assertIn("$ISOLATED", launch)

    def test_the_permission_bypass_is_given_to_the_rig_compositor_only(self):
        hits = [l for l in self.code.splitlines() if "KWIN_WAYLAND_NO_PERMISSION_CHECKS" in l]
        self.assertEqual(len(hits), 1)
        self.assertIn('--unit="$U"', hits[0])

    def test_it_never_names_or_drives_the_owners_units(self):
        for unit in LIVE_UNITS:
            self.assertNotIn(unit, self.code, f"the rig refers to the live session's {unit}")
        for call in re.findall(r"systemctl --user (\S+)([^\n|;)]*)", self.code):
            verb, rest = call
            self.assertIn(verb, ("stop", "reset-failed", "show", "is-active"),
                          f"systemctl --user {verb}: the rig only reads and stops its own units")
            if verb in ("stop", "reset-failed"):
                self.assertIn("$U", rest, "a stop that is not scoped to the rig's own unit names")
        self.assertRegex(self.code, r'U="moos-kwin-rig-\$\$"')

    def test_everything_it_started_is_stopped_however_it_ends(self):
        self.assertRegex(self.code, r"trap stop_all EXIT")
        body = re.search(r"stop_all\(\) \{([\s\S]*?)\n\}", self.code).group(1)
        for unit in ('"$U-consumer.service"', '"$U-client.service"', '"$U.service"'):
            self.assertIn(unit, body)
        self.assertIn('rm -f "$RT/$SOCKET"', body)


class Arguments(unittest.TestCase):
    def run_rig(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            trap = Path(tmp) / "bin"
            trap.mkdir()
            for name in ("systemd-run", "systemctl", "kwin_wayland"):
                (trap / name).write_text(f'#!/bin/sh\necho "{name} $*" >> "{tmp}/called"\n', encoding="utf-8")
                (trap / name).chmod(0o755)
            env = {"HOME": tmp, "PATH": f"{trap}{os.pathsep}/usr/bin{os.pathsep}/bin",
                   "XDG_CACHE_HOME": f"{tmp}/cache"}
            done = subprocess.run([BASH, str(SCRIPT), *args], env=env, capture_output=True,
                                  text=True, timeout=30)
            called = Path(tmp, "called")
            started = [l for l in (called.read_text().splitlines() if called.exists() else [])
                       if l.startswith(("systemd-run", "kwin_wayland"))]
            return done, started

    def test_without_arguments_it_explains_itself_and_starts_nothing(self):
        done, started = self.run_rig()
        self.assertEqual(done.returncode, 2)
        self.assertIn("ISOLATED second compositor", done.stdout)
        self.assertEqual(started, [])

    def test_what_is_not_a_backend_a_rate_or_a_size_starts_nothing(self):
        for args in (("X", "off"), ("O2", "45"), ("O2", "off", "1920"), ("O2", "off", "1920x1080; id"),
                     ("O2", "60", "1920x1080", "2"), ("O2", "60", "1920x1080", "15", "big"),
                     ("O2", "60", "1920x1080", "15", "1280x720", "$(id)")):
            done, started = self.run_rig(*args)
            self.assertEqual(done.returncode, 2, args)
            self.assertEqual(started, [], f"{args} reached systemd-run")


class WhatItMeasures(unittest.TestCase):
    def test_the_python_halves_compile(self):
        for name in ("workload.py", "consumer.py"):
            with tempfile.TemporaryDirectory() as tmp:
                py_compile.compile(str(RIG / name), cfile=str(Path(tmp) / "out.pyc"), doraise=True)

    def test_the_consumer_installs_the_helpers_own_pacer_not_a_copy(self):
        consumer = (RIG / "consumer.py").read_text(encoding="utf-8")
        self.assertIn('parents[3] / "moremote/agent-linux/mo-remote-portal.py"', consumer)
        self.assertNotIn("class FramePacer", consumer, "a copy would measure the copy")
        tree = ast.parse(HELPER.read_text(encoding="utf-8"))
        names = {getattr(n, "name", None) for n in tree.body}
        for wanted in ("FramePacer", "pace_frame"):
            self.assertIn(wanted, names, f"the helper no longer has {wanted}; the rig would crash")
            self.assertIn(f'"{wanted}"', consumer)

    def test_the_consumer_reads_through_the_same_queue_as_the_helper(self):
        consumer = (RIG / "consumer.py").read_text(encoding="utf-8")
        helper = HELPER.read_text(encoding="utf-8")
        queue = "queue name=capq leaky=downstream max-size-buffers=2 max-size-bytes=0 max-size-time=0"
        self.assertIn(queue, consumer)
        self.assertIn(queue, helper, "the helper's capture queue changed; the rig measures another pipeline")


if __name__ == "__main__":
    unittest.main(verbosity=1)
