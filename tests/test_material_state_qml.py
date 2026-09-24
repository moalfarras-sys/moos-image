#!/usr/bin/env python3
"""The QML half of the clarity bridge: does a real engine FOLLOW the live state?

`tests/test_material_state.py` proves the publisher writes the right marker.
This proves the other end — that `Tokens.blurActive` actually changes when the
marker changes, in a running Qt engine, with no restart and no polling.

That is the whole reason the bridge exists. `moos-fast-remote` turns blur off
mid-session (`set_config kwinrc Plugins blurEnabled false`, then
`kwin_reconfigure`), and until this bridge existed `Tokens.blurActive` was a
one-shot read at load, so every MoOS surface already on screen kept painting
0.22-alpha glass over a background that no longer had a blur pass behind it —
the P2.5 "Liquid Glass is see-through" defect, live, on a shipped path.

A string-matching test cannot check any of this. Only a real engine can say what
a FolderListModel does when a file appears under it, so this runs one.

The contract being checked, in the order it matters:

  * no publisher at all  -> the startup kwinrc policy still decides. A greeter or
    a source-tree review tool has no session service, and must not be forced
    opaque by its absence.
  * `blur-on` alone      -> blur is on, EVEN IF kwinrc says otherwise. The
    publisher asks the compositor; the config file is a guess about it.
  * `blur-off` alone     -> off.
  * both markers at once -> off. The publisher writes the new marker before
    removing the old one precisely so an observer can catch both; ambiguity
    must read as opaque, never as false clarity.
  * marker changes while running -> the value follows, with no restart.
"""
from pathlib import Path
import shutil
import select
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "system_files/usr/lib64/qt6/qml"
RUNTIME = next((name for name in ("moos-qml-shell", "qml-qt6", "qml6", "qml")
                if shutil.which(name)), None)

# Appends one line per change so the test can watch the value MOVE, not just
# sample it once. Qt.exit is never called: Python decides when it has seen
# enough, which is what makes the live-change case observable at all.
PROBE = """
import QtQuick
import org.moos.ui as MoUI

QtObject {
    id: probe
    property string last: "unset"
    function record() {
        const now = String(MoUI.Tokens.blurActive)
                  + " observed=" + String(MoUI.Tokens.materialObserved)
                  + " clarity=" + String(MoUI.Tokens.clarityPreference)
                  + " value=" + Number(MoUI.Tokens.glassClarity).toFixed(1)
        if (now === probe.last) return
        probe.last = now
        console.log("MATERIAL " + now)
    }
    property var watcher: Connections {
        target: MoUI.Tokens
        function onBlurActiveChanged() { probe.record() }
        function onMaterialObservedChanged() { probe.record() }
        function onClarityPreferenceChanged() { probe.record() }
        function onGlassClarityChanged() { probe.record() }
    }
    Component.onCompleted: record()
}
"""


class Probe:
    """A live QML engine whose reported blurActive this test can watch change."""

    def __init__(self, work: Path, blur_in_config: bool):
        self.work = work
        self.runtime_dir = work / "run"
        self.runtime_dir.mkdir(mode=0o700, exist_ok=True)
        self.material = self.runtime_dir / "moos-material"
        config = work / "config"
        config.mkdir(exist_ok=True)
        (config / "kwinrc").write_text(
            f"[Plugins]\nblurEnabled={'true' if blur_in_config else 'false'}\n",
            encoding="utf-8")
        probe = work / "probe.qml"
        probe.write_text(PROBE, encoding="utf-8")
        self.seen: list[str] = []
        command = ([RUNTIME, "--app-id", "org.moos.material.gate", "--qml", str(probe)]
                   if RUNTIME == "moos-qml-shell" else [RUNTIME, str(probe)])
        self.process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
            env={
                "HOME": str(work), "XDG_CONFIG_HOME": str(config),
                "XDG_CONFIG_DIRS": str(work / "empty-system"),
                "XDG_RUNTIME_DIR": str(self.runtime_dir),
                "QT_QUICK_BACKEND": "software", "QT_QPA_PLATFORM": "offscreen",
                # Without these the engine buffers qml: output and the test
                # watches a pipe that never moves.
                "QT_FORCE_STDERR_LOGGING": "1", "QT_LOGGING_RULES": "qml=true",
                "QT_ASSUME_STDERR_HAS_CONSOLE": "1",
                "QML_IMPORT_PATH": str(UI), "QML2_IMPORT_PATH": str(UI),
                "PATH": "/usr/bin:/bin",
            })
        self.reader = self.process.stdout

    def mark(self, *names: str) -> None:
        """Make the marker directory hold exactly these files."""
        self.material.mkdir(mode=0o700, exist_ok=True)
        for name in ("blur-on", "blur-off", "clarity-clear",
                     "clarity-balanced", "clarity-solid"):
            path = self.material / name
            if name in names:
                path.touch()
            else:
                path.unlink(missing_ok=True)

    def expect(self, value: str, timeout: float = 20.0) -> str:
        """Wait for the engine to REPORT this value, and say so if it never does.

        Waiting for the expected line rather than for the stream to go quiet is
        what keeps the live-change cases honest: a bridge that never fires looks
        exactly like a stable value if you only sample.
        """
        if self.seen and self.seen[-1] == value:
            return value
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # A blocking readline() never looks at the deadline: when the engine stays silent,
            # the gate hung for good (seen on the A1, 2026-09-24) instead of failing with what
            # it saw. Wait for output only as long as the deadline allows.
            ready, _, _ = select.select([self.reader], [], [], max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            line = self.reader.readline()
            if not line:
                if self.process.poll() is not None:
                    break
                continue
            text = line.decode(errors="replace").strip()
            if "MATERIAL " in text:
                reported = text.split("MATERIAL ", 1)[1].strip()
                self.seen.append(reported)
                if reported == value:
                    return reported
        raise AssertionError(
            f"the engine never reported {value!r}; it reported {self.seen}")

    def close(self) -> None:
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()


@unittest.skipIf(RUNTIME is None, "no QML runtime on this machine (CI)")
class MaterialStateInARealEngine(unittest.TestCase):
    def run_case(self, blur_in_config: bool, steps):
        """Drive one engine through a sequence of (markers, expected) steps."""
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            (work / "empty-system").mkdir()
            probe = Probe(work, blur_in_config)
            try:
                for markers, expected in steps:
                    if markers is not None:
                        probe.mark(*markers)
                    probe.expect(expected)
            finally:
                probe.close()

    def test_without_a_publisher_the_startup_policy_still_decides(self):
        """A greeter has no session service. Its absence must not force opaque."""
        self.run_case(True, [(None, "true observed=false clarity=clear value=0.0")])
        self.run_case(False, [(None, "false observed=false clarity=clear value=1.0")])

    def test_the_live_marker_outranks_what_the_config_file_guessed(self):
        """kwinrc is a guess about the compositor; the publisher asked it."""
        self.run_case(False, [(("blur-on", "clarity-clear"),
                               "true observed=true clarity=clear value=0.0")])
        self.run_case(True, [(("blur-off", "clarity-clear"),
                              "false observed=true clarity=clear value=1.0")])

    def test_ambiguity_reads_as_opaque_never_as_clarity(self):
        """The publisher adds before it removes, so both markers is a real state."""
        self.run_case(True, [(("blur-on", "blur-off", "clarity-clear"),
                              "false observed=true clarity=clear value=1.0")])

    def test_the_value_follows_the_marker_with_no_restart(self):
        """The defect this whole bridge exists to close.

        One engine, three states, no relaunch: this is what `moos-fast-remote`
        flipping blur mid-session has to look like from inside a MoOS surface.
        """
        self.run_case(True, [
            (("blur-on", "clarity-clear"),
             "true observed=true clarity=clear value=0.0"),
            (("blur-off", "clarity-clear"),
             "false observed=true clarity=clear value=1.0"),
            (("blur-on", "clarity-clear"),
             "true observed=true clarity=clear value=0.0"),
        ])

    def test_a_publisher_that_goes_away_does_not_leave_clarity_behind(self):
        """If the service dies it removes both markers. Opaque is the safe read."""
        self.run_case(True, [
            (("blur-on", "clarity-clear"),
             "true observed=true clarity=clear value=0.0"),
            ((), "false observed=true clarity=clear value=1.0"),
        ])

    def test_clarity_follows_live_and_blur_off_pins_solid(self):
        self.run_case(True, [
            (("blur-on", "clarity-clear"),
             "true observed=true clarity=clear value=0.0"),
            (("blur-on", "clarity-balanced"),
             "true observed=true clarity=balanced value=0.5"),
            (("blur-on", "clarity-solid"),
             "true observed=true clarity=solid value=1.0"),
            (("blur-off", "clarity-clear"),
             "false observed=true clarity=clear value=1.0"),
        ])

    def test_ambiguous_clarity_is_solid_not_translucent(self):
        self.run_case(True, [
            (("blur-on", "clarity-clear", "clarity-solid"),
             "true observed=true clarity=solid value=1.0"),
        ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
