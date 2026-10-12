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

The logical names below are shorthand for the single state-generation filename.
The production event policy keeps its existing 100/750 ms finite readback; there
is no recurring poll. Every acknowledgement must carry this request's generation
or a newer one, never a matching value left in the pipe from an earlier cycle.
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
import importlib.machinery
import importlib.util
import re
import shutil
import select
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "system_files/usr/lib64/qt6/qml"
LOADER = importlib.machinery.SourceFileLoader("material_publisher_for_qml", str(ROOT / "system_files/usr/libexec/moos-material-state"))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
PUBLISHER = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(PUBLISHER)
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
        let files = []
        for (let i = 0; i < MoUI.Tokens.materialFiles.count; ++i)
            files.push(String(MoUI.Tokens.materialFiles.get(i, 'fileName')))
        const snapshot = now + " files=" + files.sort().join(",")
        if (snapshot === probe.last) return
        probe.last = snapshot
        console.log("MATERIAL " + snapshot)
    }
    property var watcher: Connections {
        target: MoUI.Tokens
        function onBlurActiveChanged() { Qt.callLater(probe.record) }
        function onMaterialObservedChanged() { Qt.callLater(probe.record) }
        function onClarityPreferenceChanged() { Qt.callLater(probe.record) }
        function onGlassClarityChanged() { Qt.callLater(probe.record) }
    }
    property var stateWatcher: Connections {
        target: MoUI.Tokens.materialFiles
        function onDataChanged() { Qt.callLater(probe.record) }
        function onCountChanged() { Qt.callLater(probe.record) }
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
        self.expected_files = ""
        self.minimum_generation = 0
        self.state = None
        self.pending = {}
        self.serial = 0
        self.requested = (False, "clear")
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
        """Publish normal states through the real producer; plant ambiguous controls."""
        producer = PUBLISHER.Publisher(self.runtime_dir)
        blurs = [name[5:] for name in names if name.startswith("blur-")]
        clarities = [name[8:] for name in names if name.startswith("clarity-")]
        if len(blurs) == 1 and len(clarities) == 1:
            self.requested = (blurs[0] == "on", clarities[0])
            self.minimum_generation = time.monotonic_ns()
            self.expected_files = None
            if self.state is None:
                self.state = PUBLISHER.State(
                    producer, lambda: self.requested[0], self.schedule,
                    lambda key: self.pending.pop(key, None),
                    lambda: self.requested[1])
            self.state.changed()
        elif not names:
            if self.state is not None:
                self.state.close()
                self.state = None
            else:
                producer.close()
            self.expected_files = ""
            self.minimum_generation = 0
        else:
            desired = {f"state-1-{blur}-{clarity}" for blur in blurs for clarity in clarities}
            for name in desired:
                (self.material / name).touch()
            for path in self.material.glob("state-*"):
                if path.name not in desired:
                    path.unlink()
            self.expected_files = ",".join(sorted(desired))
            self.minimum_generation = 0

    def schedule(self, delay, callback):
        self.serial += 1
        self.pending[self.serial] = (time.monotonic() + delay / 1000, callback)
        return self.serial

    def run_due(self):
        for key, (due, callback) in list(self.pending.items()):
            if key in self.pending and due <= time.monotonic():
                self.pending.pop(key)
                callback()

    def expect(self, value: str, timeout: float = 20.0) -> str:
        """Wait for the engine to REPORT this value, and say so if it never does.

        Waiting for the expected line rather than for the stream to go quiet is
        what keeps the live-change cases honest: a bridge that never fires looks
        exactly like a stable value if you only sample.
        """
        def matches(reported):
            prefix, _, files = reported.partition(" files=")
            if prefix != value:
                return False
            if self.expected_files is not None:
                return files == self.expected_files
            generation = re.fullmatch(r"state-([0-9]+)-(on|off)-(clear|balanced|solid)", files)
            return bool(generation and int(generation[1]) >= self.minimum_generation)
        if self.seen and matches(self.seen[-1]):
            return value
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.run_due()
            # A blocking readline() never looks at the deadline: when the engine stays silent,
            # the gate hung for good (seen on the A1, 2026-09-24) instead of failing with what
            # it saw. Wait for output only as long as the deadline allows.
            next_due = min((item[0] for item in self.pending.values()), default=deadline)
            ready, _, _ = select.select([self.reader], [], [], max(0.0, min(deadline, next_due) - time.monotonic()))
            if not ready:
                continue
            line = self.reader.readline()
            if not line:
                if self.process.poll() is not None:
                    break
                continue
            text = line.decode(errors="replace").strip()
            if "MATERIAL " in text:
                reported = text.split("MATERIAL ", 1)[1].strip()
                self.seen.append(reported)
                if matches(reported):
                    return reported
        raise AssertionError(
            f"the engine never reported {value!r} for generation >= {self.minimum_generation}; last snapshots: {self.seen[-20:]}")

    def close(self) -> None:
        if self.state is not None:
            self.state.close()
            self.state = None
        if self.reader is not None:
            self.reader.close()
            self.reader = None
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


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

    def test_real_publisher_rapid_transitions_do_not_leave_a_stale_snapshot(self):
        # Old multi-file publication lost the last remove while Qt's directory
        # worker was scanning: the real producer reproduced it on native ARM.
        # One live consumer, all four required states, every cycle acknowledged.
        cycle = [
            (("blur-on", "clarity-clear"), "true observed=true clarity=clear value=0.0"),
            (("blur-on", "clarity-balanced"), "true observed=true clarity=balanced value=0.5"),
            (("blur-on", "clarity-solid"), "true observed=true clarity=solid value=1.0"),
            (("blur-off", "clarity-clear"), "false observed=true clarity=clear value=1.0"),
        ]
        self.run_case(True, cycle * 40)

    def test_unknown_state_is_opaque(self):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            (work / "empty-system").mkdir()
            probe = Probe(work, True)
            try:
                probe.material.mkdir()
                (probe.material / "state-invalid").touch()
                probe.expected_files = "state-invalid"
                probe.expect("false observed=true clarity=solid value=1.0")
            finally:
                probe.close()

    def test_a_broken_consumer_cannot_pass_the_live_transition_gate(self):
        global UI
        original = UI
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            staged = work / "qml"
            shutil.copytree(UI, staged)
            tokens = staged / "org/moos/ui/Tokens.qml"
            text = tokens.read_text()
            tokens.write_text(text.replace(
                "if (clarityMarkers.indexOf(fields[2]) < 0) clarityMarkers.push(fields[2])",
                "if (clarityMarkers.indexOf('clear') < 0) clarityMarkers.push('clear')"))
            UI = staged
            (work / "empty-system").mkdir()
            probe = Probe(work, True)
            try:
                probe.mark("blur-on", "clarity-clear")
                probe.expect("true observed=true clarity=clear value=0.0")
                probe.mark("blur-on", "clarity-balanced")
                with self.assertRaisesRegex(AssertionError, "never reported"):
                    probe.expect("true observed=true clarity=balanced value=0.5", timeout=2)
            finally:
                probe.close()
                UI = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
