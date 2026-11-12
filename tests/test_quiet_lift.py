#!/usr/bin/env python3
"""Execute KWin effect callbacks and verify bounded ownership and interruption."""
import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "system_files/usr/share/kwin/effects/moos-quiet-lift"


class QuietLiftTest(unittest.TestCase):
    def test_inside_refuses_inherited_state_before_starting_compositor(self):
        path = ROOT / "scripts/review/quiet-lift-native.py"
        spec = importlib.util.spec_from_file_location("quiet_lift_review", path)
        review = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(review)
        with tempfile.TemporaryDirectory() as directory, patch.object(
                review.subprocess, "Popen", side_effect=AssertionError("compositor started")), \
                patch.object(review.resource, "setrlimit"):
            with self.assertRaisesRegex(RuntimeError, "private session environment unavailable"):
                review.inside(Path(directory), "fixed")

    @unittest.skipUnless(shutil.which("dbus-run-session") and shutil.which("dbus-send")
                         and Path("/proc/self/environ").exists(),
                         "native D-Bus and procfs are needed for activation isolation")
    def test_private_bus_itself_inherits_only_review_state(self):
        # Intercept only the display child, keeping the script's actual outer
        # dbus-run-session command and environment. No compositor or owner
        # service is launched. Checking the bus daemon catches an environment
        # applied too late, even if the later KWin child would look isolated.
        probe = r'''
import json, os, pathlib, re, subprocess
reply = subprocess.run(['dbus-send', '--session', '--print-reply',
    '--dest=org.freedesktop.DBus', '/org/freedesktop/DBus',
    'org.freedesktop.DBus.GetConnectionUnixProcessID', 'string:org.freedesktop.DBus'],
    check=True, capture_output=True, text=True, timeout=5)
pid = int(re.search(r'uint32\s+(\d+)', reply.stdout).group(1))
daemon = dict(item.split(b'=', 1) for item in pathlib.Path(f'/proc/{pid}/environ')
              .read_bytes().split(b'\0') if b'=' in item)
keys = ('HOME', 'XDG_CONFIG_HOME', 'XDG_CONFIG_DIRS', 'XDG_DATA_HOME',
        'XDG_CACHE_HOME', 'XDG_RUNTIME_DIR', 'DISPLAY', 'WAYLAND_DISPLAY')
print(json.dumps({'child': {key: os.environ.get(key) for key in keys},
    'daemon': {key: daemon.get(key.encode(), b'').decode() or None for key in keys}}))
'''
        wrapper = r'''
import runpy, subprocess, sys
actual_run = subprocess.run
probe = sys.argv.pop(1)
script = sys.argv.pop(1)
def substitute_client(command, *args, **kwargs):
    if command[0] != 'dbus-run-session':
        raise AssertionError('Unexpected command before private bus')
    return actual_run([command[0], '--', sys.executable, '-c', probe], *args, **kwargs)
subprocess.run = substitute_client
sys.argv[0] = script
runpy.run_path(script, run_name='__main__')
'''
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            result = subprocess.run([sys.executable, "-c", wrapper, probe,
                str(ROOT / "scripts/review/quiet-lift-native.py"),
                "--mode", "fixed", "--output", str(output)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout)
            expected = {"HOME": str(output / "home"),
                "XDG_CONFIG_HOME": str(output / "config"),
                "XDG_CONFIG_DIRS": str(output / "config"),
                "XDG_DATA_HOME": str(output / "data"),
                "XDG_CACHE_HOME": str(output / "cache"),
                "XDG_RUNTIME_DIR": str(output / "runtime"),
                "DISPLAY": None, "WAYLAND_DISPLAY": None}
            self.assertEqual(observed["daemon"], expected)
            self.assertEqual(observed["child"], expected)

    def test_exclusive_native_package_is_selectable_without_forcing_preferences(self):
        data = json.loads((PACKAGE / "metadata.json").read_text())
        self.assertEqual(data["X-KWin-Exclusive-Category"], "toplevel-open-close-animation")
        self.assertEqual(data["X-Plasma-API"], "javascript")
        self.assertFalse(data["KPlugin"]["EnabledByDefault"])

    @unittest.skipUnless(shutil.which("node"), "Node is needed for portable effect callbacks")
    def test_real_callbacks_preserve_guards_reversal_roles_and_reduced_motion(self):
        source = (PACKAGE / "contents/code/main.js").read_text()
        tokens = json.loads((ROOT / "artwork/moos-design/tokens.json").read_text())["motion"]
        harness = r'''
const assert = require('node:assert/strict');
const signal = () => ({callbacks: [], connect(f) {this.callbacks.push(f)},
                      emit(...a) {this.callbacks.forEach(f => f(...a))}});
const effects = {windowAdded: signal(), windowClosed: signal(), windowDeleted: signal(),
                 windowDataChanged: signal(), hasActiveFullScreenEffect: false};
const effect = {animationEnded: signal(), configChanged: signal(),
                isGrabbed: (w, r) => w.grabbed === r};
const Effect = {Scale: 1, Translation: 2, Opacity: 3, Backward: 4,
                WindowAddedGrabRole: 5, WindowClosedGrabRole: 6,
                WindowForceBackgroundContrastRole: 7, WindowForceBlurRole: 8};
const QEasingCurve = {OutCubic: 1, InCubic: 2};
let factor = 1, calls = [], cancelled = [], reversed = [], serial = 0;
const animationTime = n => Math.max(1, Math.floor(n * factor));
const animate = args => {calls.push(args); return args.animations.map(() => ++serial)};
const cancel = ids => cancelled.push(ids);
const redirect = (ids, direction) => {reversed.push({ids, direction}); return true};
const window = changes => Object.assign({managed: true, visible: true, normalWindow: true,
    hasDecoration: true, windowClass: 'blender org.blender.Blender', geometry: {height: 900},
    data: {}, setData(role, value) {this.data[role] = value}}, changes);
'''
        assertions = r'''
assert.equal(motionGeometry, TOKENS.motionGeometry);
assert.equal(motionPress, TOKENS.motionPress);
const w = window(); effects.windowAdded.emit(w);
assert.equal(calls.length, 1); assert.equal(calls[0].duration, 220);
assert.equal(calls[0].animations[1].from.value2, 18);
const ids = w.moosQuietLift.ids;
effects.windowClosed.emit(w);
assert.equal(calls.length, 1); assert.equal(cancelled.length, 0);
assert.deepEqual(reversed, [{ids, direction: Effect.Backward}]);
effect.animationEnded.emit(w, 0); effect.animationEnded.emit(w, 0);
assert.equal(w.data[Effect.WindowForceBlurRole], true);
effect.animationEnded.emit(w, 0);
assert.equal(w.data[Effect.WindowForceBlurRole], null);
assert.equal(w.moosQuietLift, undefined);
for (const change of [{managed:false}, {visible:false}, {popupWindow:true},
        {lockScreen:true}, {outline:true}, {fullScreen:true},
        {windowClass:'ksmserver-logout-greeter ksmserver-logout-greeter'},
        {windowClass:'plasmashell org.kde.plasmashell',hasDecoration:false},
        {windowClass:'spectacle org.kde.spectacle',tag:'region-editor'},
        {grabbed:Effect.WindowAddedGrabRole}]) {
    effects.windowAdded.emit(window(change));
}
assert.equal(calls.length, 1);
effects.hasActiveFullScreenEffect = true; effects.windowAdded.emit(window());
assert.equal(calls.length, 1); effects.hasActiveFullScreenEffect = false;
factor = 0; effects.windowAdded.emit(window()); assert.equal(calls.length, 1);
factor = 0.85; const normal = window(); effects.windowAdded.emit(normal);
assert.equal(calls.at(-1).duration, 187);
normal.grabbed = Effect.WindowAddedGrabRole;
effects.windowDataChanged.emit(normal, Effect.WindowAddedGrabRole);
assert.equal(cancelled.length, 1); assert.equal(normal.moosQuietLift, undefined);
assert.equal(normal.data[Effect.WindowForceBlurRole], null);
const during = window(); effects.windowAdded.emit(during);
factor = 0; effect.configChanged.emit();
assert.equal(during.moosQuietLift, undefined);
assert.equal(during.data[Effect.WindowForceBlurRole], null);
factor = 1; const skip = window(); effects.windowAdded.emit(skip);
skip.skipsCloseAnimation = true; effects.windowClosed.emit(skip);
assert.equal(skip.moosQuietLift, undefined);
assert.equal(skip.data[Effect.WindowForceBlurRole], null);
const closed = window(); effects.windowClosed.emit(closed);
assert.equal(calls.at(-1).duration, 160);
assert.equal(calls.at(-1).animations[2].to, 0);
console.log('MOOS_QUIET_LIFT_CALLBACKS_PASSED');
'''.replace("TOKENS", json.dumps(tokens))
        result = subprocess.run(["node", "-e", harness + source + assertions],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MOOS_QUIET_LIFT_CALLBACKS_PASSED", result.stdout)


if __name__ == "__main__":
    unittest.main()
