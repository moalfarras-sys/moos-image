#!/usr/bin/env python3
"""Transactional Fast Remote regression tests.

The real helper spans KConfig, the theme owner, KWin layouts and the selected
local model service. These tests exercise that relationship with real KConfig
tools and deterministic D-Bus/systemd/theme stubs. Most importantly, a partial
OFF failure must retain every snapshot for a successful retry.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAST_REMOTE = ROOT / "system_files/usr/bin/moos-fast-remote"


class FastRemoteTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.config = self.root / "config"
        self.runtime = self.root / "runtime"
        self.state = self.root / "state"
        for directory in (self.bin, self.config, self.runtime, self.state):
            directory.mkdir()

        self.motion = self.state / "motion"
        self.motion.write_text("alive\n", encoding="utf-8")
        self.layout = self.state / "layout"
        self.layout.write_text("0\n", encoding="utf-8")
        self.brain = self.state / "brain"
        self.brain.write_text("active\n", encoding="utf-8")
        self.layout_fail = self.state / "layout-fail"

        self.theme = self._stub(
            "theme",
            """#!/usr/bin/env bash
set -eu
[ "${1:-}" = motion ] || exit 2
if [ "$#" -eq 1 ]; then
    cat "$TEST_MOTION"
else
    [ "${MOOS_THEME_LOCK_HELD:-0}" = 1 ] || exit 3
    case "$2" in still|gentle|alive) ;; *) exit 2 ;; esac
    printf '%s\n' "$2" >"$TEST_MOTION"
    printf '%s\n' "$2"
fi
""",
        )
        self.engine = self._stub(
            "engine",
            """#!/usr/bin/env bash
[ "${1:-}" = unit ] || exit 2
printf '%s\n' ollama.service
""",
        )
        self._stub(
            "systemctl",
            """#!/usr/bin/env bash
set -eu
action=
for arg in "$@"; do
    case "$arg" in is-active|start|stop) action="$arg" ;; esac
done
case "$action" in
  is-active) [ "$(cat "$TEST_BRAIN")" = active ] ;;
  start) printf '%s\n' active >"$TEST_BRAIN" ;;
  stop) printf '%s\n' inactive >"$TEST_BRAIN" ;;
  *) exit 2 ;;
esac
""",
        )
        self._stub(
            "gdbus",
            """#!/usr/bin/env bash
set -eu
case "$*" in
  *org.kde.KeyboardLayouts.getLayoutsList*)
    printf "%s\n" "([('de', 'DE', 'German'), ('us', '', 'English')],)"
    ;;
  *org.kde.KeyboardLayouts.getLayout*)
    printf '(uint32 %s,)\n' "$(cat "$TEST_LAYOUT")"
    ;;
  *org.kde.KeyboardLayouts.setLayout*)
    value="${!#}"
    if [ -f "$TEST_LAYOUT_FAIL" ] && [ "$value" = 0 ]; then
        printf '%s\n' '(false,)'
    else
        printf '%s\n' "$value" >"$TEST_LAYOUT"
        printf '%s\n' '(true,)'
    fi
    ;;
  *org.kde.KWin.reconfigure*) printf '%s\n' '()' ;;
  *) exit 2 ;;
esac
""",
        )

        # XDG_CONFIG_DIRS, and without it this test's answer depended on the
        # machine it ran on.
        #
        # KConfig CASCADES: kreadconfig6 resolves a key through XDG_CONFIG_HOME
        # and then through every directory in XDG_CONFIG_DIRS, which defaults to
        # /etc/xdg. Setting XDG_CONFIG_HOME alone therefore isolates only half of
        # the lookup, and the host's own /etc/xdg/kwinrc still answered.
        #
        # That is not hypothetical. The MoOS image installed on the cloud server
        # ships `contrastEnabled=false` in /etc/xdg/kwinrc, so the key this test
        # calls "deliberately absent" resolved to `false` through the cascade.
        # snapshot_config then correctly recorded a PRESENT key, no `.missing`
        # marker was written, and the assertion below failed — on a machine where
        # nothing was broken. `just build` and `just build-cloud` run this in
        # their `check` step, so the whole image build stopped, while CI stayed
        # green because CI's gate list does not include this file.
        #
        # An empty directory pins the cascade to exactly what this test writes.
        self.xdg_dirs = self.root / "xdg"
        self.xdg_dirs.mkdir()

        self.env = {
            **os.environ,
            "HOME": str(self.root / "home"),
            "XDG_CONFIG_HOME": str(self.config),
            "XDG_CONFIG_DIRS": str(self.xdg_dirs),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "XDG_STATE_HOME": str(self.state),
            "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "MOOS_THEME_HELPER": str(self.theme),
            "MOOS_ENGINE_HELPER": str(self.engine),
            "TEST_MOTION": str(self.motion),
            "TEST_LAYOUT": str(self.layout),
            "TEST_LAYOUT_FAIL": str(self.layout_fail),
            "TEST_BRAIN": str(self.brain),
        }
        (self.root / "home").mkdir()

        self._write_config("kwinrc", "Plugins", "blurEnabled", "true")
        self._write_config("kwinrc", "Plugins", "slideEnabled", "true")
        # contrastEnabled deliberately does not exist; exact restoration must
        # delete the temporary key rather than persist a guessed default.
        self._write_config(
            "kdeglobals", "KDE", "AnimationDurationFactor", "0.73"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _stub(self, name: str, content: str) -> Path:
        target = self.bin / name
        target.write_text(content, encoding="utf-8")
        target.chmod(0o755)
        return target

    def _write_config(self, file: str, group: str, key: str, value: str) -> None:
        subprocess.run(
            [
                "kwriteconfig6", "--file", file, "--group", group,
                "--key", key, value,
            ],
            env=self.env,
            check=True,
        )

    def _read_config(self, file: str, group: str, key: str) -> str:
        return subprocess.run(
            [
                "kreadconfig6", "--file", file, "--group", group,
                "--key", key, "--default", "__MISSING__",
            ],
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def _run(self, action: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(FAST_REMOTE), action],
            env=self.env,
            check=check,
            capture_output=True,
            text=True,
        )

    def test_exact_round_trip_and_failed_restore_retry(self) -> None:
        self._run("on")
        # Repeated ON is a no-op and must not replace the original snapshot.
        self.assertIn("already ON", self._run("on").stdout)
        self.assertEqual(self._read_config("kwinrc", "Plugins", "blurEnabled"), "false")
        self.assertEqual(self._read_config("kwinrc", "Plugins", "slideEnabled"), "false")
        self.assertEqual(self._read_config("kwinrc", "Plugins", "contrastEnabled"), "false")
        self.assertEqual(
            self._read_config("kdeglobals", "KDE", "AnimationDurationFactor"),
            "0.05",
        )
        self.assertEqual(self.motion.read_text(encoding="utf-8").strip(), "still")
        self.assertEqual(self.layout.read_text(encoding="utf-8").strip(), "1")
        self.assertEqual(self.brain.read_text(encoding="utf-8").strip(), "inactive")

        # Simulate KWin rejecting the final layout restoration. OFF must fail
        # and keep the recovery marker and every exact snapshot for a retry.
        self.layout_fail.touch()
        failed = self._run("off", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("state retained", failed.stderr)
        marker = self.state / "moos" / "fast-remote.on"
        self.assertTrue(marker.exists())
        self.assertTrue((self.state / "moos" / "fast-remote.on.motion").exists())
        self.assertTrue((self.state / "moos" / "fast-remote.on.contrast.missing").exists())

        self.layout_fail.unlink()
        # A crash/reboot clears XDG_RUNTIME_DIR.  The phase-2 autostart recovery
        # must still have the exact persistent transaction journal it needs.
        shutil.rmtree(self.runtime)
        self.runtime.mkdir()
        self._run("recover")
        self.assertEqual(self._run("status").stdout.strip(), "off")
        self.assertEqual(self._read_config("kwinrc", "Plugins", "blurEnabled"), "true")
        self.assertEqual(self._read_config("kwinrc", "Plugins", "slideEnabled"), "true")
        self.assertEqual(
            self._read_config("kwinrc", "Plugins", "contrastEnabled"), "__MISSING__"
        )
        self.assertEqual(
            self._read_config("kdeglobals", "KDE", "AnimationDurationFactor"),
            "0.73",
        )
        self.assertEqual(self.motion.read_text(encoding="utf-8").strip(), "alive")
        self.assertEqual(self.layout.read_text(encoding="utf-8").strip(), "0")
        self.assertEqual(self.brain.read_text(encoding="utf-8").strip(), "active")
        self.assertEqual(list((self.state / "moos").glob("fast-remote.on*")), [])


if __name__ == "__main__":
    # THIS TEST DRIVES THE REAL KConfig BINARIES, AND CI DOES NOT HAVE THEM.
    #
    # Everything else the script talks to is stubbed above — moos-theme, the engine helper, gdbus,
    # systemctl — but kreadconfig6/kwriteconfig6 are deliberately NOT, because the behaviour under
    # test is KConfig's own: the cascade through XDG_CONFIG_DIRS, `--default` on an absent key, and
    # `--delete`. A stub would be a second implementation of the thing being verified, and would
    # pass while the real one broke.
    #
    # The cost is that the test cannot run where KDE Frameworks is absent. That is `ubuntu-latest`:
    # the runner has no kwriteconfig6 at all, and adding this file to the CI gate list turned every
    # image build red with `FileNotFoundError: 'kwriteconfig6'` — three failed builds before the
    # cause was clear. KF6 is not in noble's archive either, so installing it is not a one-line fix.
    #
    # So it skips where it cannot run, and it says so LOUDLY rather than printing a reassuring OK.
    # It is still a real gate everywhere it matters: `just check` runs on MoOS machines, where the
    # binaries exist and the assertions all execute. Green here without the notice below means it
    # ran for real.
    if shutil.which("kwriteconfig6") is None or shutil.which("kreadconfig6") is None:
        print("SKIPPED: moos-fast-remote's transaction test needs the real kreadconfig6/"
              "kwriteconfig6 (KDE Frameworks), which this machine does not have. NOTHING WAS "
              "VERIFIED HERE — run `just check` on a MoOS machine to actually exercise it.")
        raise SystemExit(0)
    unittest.main(verbosity=2)
