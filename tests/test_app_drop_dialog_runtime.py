#!/usr/bin/env python3
"""Exercise App Drop's real kdialog consent on a private X server, never the desktop.

Requires kdialog, Xvfb and xdotool (a disposable SDK container is sufficient).
Missing runtime dependencies skip explicitly; source checks are not consent proof.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(all(shutil.which(x) for x in ("kdialog", "Xvfb", "xdotool")),
                     "real consent requires kdialog, Xvfb and xdotool")
class ConsentRuntime(unittest.TestCase):
    def test_real_default_escape_and_explicit_continue(self):
        with tempfile.TemporaryDirectory(prefix="moos-consent-") as directory:
            env = dict(os.environ)
            for key in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
                        "SESSION_MANAGER", "QT_STYLE_OVERRIDE", "QT_QPA_PLATFORMTHEME"):
                env.pop(key, None)
            env.update(HOME=directory, XDG_CONFIG_HOME=directory,
                       XDG_DATA_HOME=directory, XDG_CACHE_HOME=directory,
                       XDG_RUNTIME_DIR=directory, XDG_CONFIG_DIRS=directory,
                       DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent-moos-consent-bus",
                       QT_QPA_PLATFORM="xcb", LANG="C.UTF-8", LC_ALL="C.UTF-8")
            read_fd, write_fd = os.pipe()
            server = subprocess.Popen(["Xvfb", "-displayfd", str(write_fd),
                                       "-screen", "0", "800x600x24", "-nolisten", "tcp"],
                                      env=env, pass_fds=(write_fd,),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            os.close(write_fd)
            try:
                import select
                self.assertTrue(select.select([read_fd], [], [], 10)[0], "Xvfb startup timed out")
                display = os.read(read_fd, 64).decode().strip()
                self.assertTrue(display.isdigit(), "Xvfb did not allocate a private display")
                env["DISPLAY"] = ":" + display
                for keys, accepted in ((["Return"], False), (["Escape"], False),
                                       (["Tab", "Return"], True)):
                    with self.subTest(keys=keys):
                        code = ("import runpy,sys; ns=runpy.run_path(sys.argv[1]); "
                                "sys.exit(0 if ns['ask']('MoOS Consent Runtime', "
                                "'Install the test application?', 'Install') else 1)")
                        dialog = subprocess.Popen([sys.executable, "-c", code,
                                                   str(ROOT / "system_files/usr/bin/moos-app-drop")],
                                                  env=env, stdout=subprocess.PIPE,
                                                  stderr=subprocess.PIPE)
                        try:
                            window = ""
                            deadline = time.monotonic() + 10
                            while time.monotonic() < deadline and dialog.poll() is None:
                                result = subprocess.run(["xdotool", "search", "--onlyvisible",
                                                         "--name", "MoOS Consent Runtime"],
                                                        env=env, capture_output=True, text=True)
                                if result.returncode == 0 and result.stdout.strip():
                                    window = result.stdout.splitlines()[-1]
                                    break
                                time.sleep(0.05)
                            self.assertTrue(window, "real dialog did not appear")
                            subprocess.run(["xdotool", "windowfocus", "--sync", window],
                                           env=env, check=True, timeout=5)
                            subprocess.run(["xdotool", "key", "--clearmodifiers", *keys],
                                           env=env, check=True, timeout=5)
                            _, errors = dialog.communicate(timeout=5)
                            self.assertEqual(dialog.returncode, 0 if accepted else 1,
                                             errors.decode(errors="replace"))
                        finally:
                            if dialog.poll() is None:
                                dialog.kill()
                                dialog.communicate()
            finally:
                os.close(read_fd)
                server.terminate()
                server.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
