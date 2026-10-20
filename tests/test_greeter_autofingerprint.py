#!/usr/bin/env python3
"""Native automatic-start control and bounded, read-only enrollment discovery."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'build_files/plasma_login'
spec = importlib.util.spec_from_file_location('fingerprint_availability', PACKAGE / 'capabilities.py')
capabilities = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capabilities)


def added_source(path):
    patch = (PACKAGE / 'automatic-fingerprint.patch').read_text()
    target = '+++ b/' + path + '\n'
    section = patch.split(target, 1)[1].split('--- ', 1)[0]
    return '\n'.join(line[1:] for line in section.splitlines()
                     if line.startswith('+') and not line.startswith('+++')) + '\n'


class EnrollmentAvailability(unittest.TestCase):
    def responder(self, arguments, **kwargs):
        self.assertLessEqual(kwargs['timeout'], 2)
        method = arguments[7]
        if method == 'GetDevices':
            value = {'type': 'ao', 'data': [['/net/reactivated/Fprint/Device/0']]}
        elif arguments[-1] == 'without-enrollment':
            raise subprocess.CalledProcessError(1, arguments)
        else:
            value = {'type': 'as', 'data': [['right-index-finger']]}
        return subprocess.CompletedProcess(arguments, 0, json.dumps(value), '')

    def test_account_without_enrollment_does_not_hide_confirmed_account(self):
        self.assertEqual(capabilities.enrolled_users(['without-enrollment', 'owner'],
                         run=self.responder, clock=lambda: 0), ['owner'])

    def test_expired_budget_refuses_to_start_a_query(self):
        with self.assertRaises(TimeoutError):
            capabilities.query([], 0, run=lambda *a, **k: self.fail('late bus query'), clock=lambda: 1)

    def test_invalid_response_types_and_excess_entries_are_rejected(self):
        for data in ({'type': 'as', 'data': [[]]}, {'type': 'ao', 'data': ['bad']},
                     {'type': 'ao', 'data': [[1]]}, {'type': 'ao', 'data': [['x'] * 33]}):
            def respond(*args, **kwargs):
                return subprocess.CompletedProcess(args, 0, json.dumps(data), '')
            with self.subTest(data=data), self.assertRaises(ValueError):
                capabilities.query(['/manager', 'manager', 'GetDevices'], 4, respond, lambda: 0)

    def test_device_path_must_belong_to_fprint(self):
        def respond(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, '{"type":"ao","data":[["/other/service"]]}', '')
        with self.assertRaises(ValueError):
            capabilities.enrolled_users(['owner'], run=respond, clock=lambda: 0)

    def test_collection_never_claims_device_or_starts_verification(self):
        calls = []
        def respond(arguments, **kwargs):
            calls.append(arguments)
            return self.responder(arguments, **kwargs)
        capabilities.enrolled_users(['owner'], run=respond, clock=lambda: 0)
        self.assertEqual([call[7] for call in calls], ['GetDevices', 'ListEnrolledFingers'])


class NativeAutomaticStart(unittest.TestCase):
    def reveal_probe(self, broken=False):
        if importlib.util.find_spec('PySide6') is None:
            if os.environ.get('MOOS_REQUIRE_AUTO_FINGERPRINT_QT') == '1':
                self.fail('the native image proof requires PySide6')
            self.skipTest('native Qt is unavailable')
        source = added_source('src/frontend/greeter/qml/Login.qml')
        reveal = re.search(r'    Component.onCompleted: Qt.callLater\(\(\) => \{.*?\n    \}\)', source, re.S)
        self.assertIsNotNone(reveal)
        body = reveal[0]
        if broken:
            self.assertIn('root.Screen.name', body)
            body = body.replace('root.Screen.name', 'root.Window.window.screen.name')
        with tempfile.TemporaryDirectory(prefix='moos-greeter-screen-') as directory:
            root = Path(directory)
            (root / 'qmldir').write_text('singleton UserModel 1.0 UserModel.qml\nsingleton GreeterState 1.0 GreeterState.qml\n')
            (root / 'UserModel.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject { function hasFingerprint(user) { return user === "owner"; } }\n')
            (root / 'GreeterState.qml').write_text('pragma Singleton\nimport QtQuick\nQtObject { property var activeWindow: null; function activateWindow(window) { activeWindow = window; } }\n')
            (root / 'probe.qml').write_text('''import QtQuick
import "." as PlasmaLogin
Item {
    id: root
    width: 100; height: 100
    property bool showUsernamePrompt: false
    property var userList: ({selectedUser: "owner"})
    property bool completed: false
''' + body + '''
    Timer {
        interval: 500; running: true
        onTriggered: {
            root.completed = PlasmaLogin.GreeterState.activeWindow === root.Window.window
                && root.Window.window !== null;
            Qt.quit();
        }
    }
}
''')
            for name in ('home', 'config', 'data', 'cache', 'runtime'):
                (root / name).mkdir(mode=0o700)
            env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_FORCE_STDERR_LOGGING': '1',
                   'HOME': str(root / 'home'), 'XDG_RUNTIME_DIR': str(root / 'runtime'),
                   'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_CONFIG_DIRS': str(root / 'config'),
                   'XDG_DATA_HOME': str(root / 'data'), 'XDG_CACHE_HOME': str(root / 'cache'),
                   'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(root / 'no-bus')}
            for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
                env.pop(name, None)
            return subprocess.run([sys.executable, '-c', '''
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
app=QGuiApplication([]);view=QQuickView();view.setScreen(app.screens()[0])
view.setSource(QUrl.fromLocalFile(sys.argv[1]))
if not view.rootObject():sys.exit(2)
view.engine().quit.connect(app.quit);view.show();app.exec()
if not view.rootObject().property('completed'):sys.exit(1)
print('MOOS_AUTO_FINGERPRINT_SCREEN_OK',flush=True)
''', str(root / 'probe.qml')], env=env, capture_output=True, text=True, timeout=10)

    def test_actual_qquickview_reveals_selected_enrolled_account(self):
        result = self.reveal_probe()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('MOOS_AUTO_FINGERPRINT_SCREEN_OK', result.stdout)
        self.assertNotIn('TypeError', result.stderr)

    def test_original_qquickwindow_screen_lookup_fails_the_same_probe(self):
        result = self.reveal_probe(broken=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('TypeError', result.stderr)
        self.assertNotIn('MOOS_AUTO_FINGERPRINT_SCREEN_OK', result.stdout)

    def probe(self, broken=False):
        if importlib.util.find_spec('PySide6') is None:
            if os.environ.get('MOOS_REQUIRE_AUTO_FINGERPRINT_QT') == '1':
                self.fail('the native image proof requires PySide6')
            self.skipTest('native Qt is unavailable')
        controller = added_source('src/frontend/greeter/qml/AutomaticFingerprint.qml')
        state = added_source('src/frontend/greeter/qml/GreeterState.qml')
        claim = re.search(r'    function claimAutomaticFingerprint\(user\): bool \{.*?\n    \}', state, re.S)
        self.assertIsNotNone(claim)
        if broken:
            self.assertIn('root.requested()', controller)
            controller = controller.replace('root.requested()', 'void 0')
        with tempfile.TemporaryDirectory(prefix='moos-auto-fingerprint-') as directory:
            root = Path(directory)
            (root / 'AutomaticFingerprint.qml').write_text(controller)
            (root / 'probe.qml').write_text('''import QtQuick
Item {
    id: root
    property bool authenticationInProgress: false
    property var automaticFingerprintAttempts: []
    property int requests: 0
    property int stage: 0
    property bool completed: false
    property string failureMessage
''' + claim[0] + '''
    function require(condition, message) {
        if (!condition) { root.failureMessage = message; Qt.exit(1); return false; }
        return true;
    }
    AutomaticFingerprint {
        id: first
        username: "owner"
        available: false
        uiVisible: true
        busy: root.authenticationInProgress
        claim: function(user) { return root.claimAutomaticFingerprint(user); }
        onRequested: root.requests++
    }
    AutomaticFingerprint {
        username: first.username
        available: first.available
        uiVisible: first.uiVisible
        passwordEmpty: first.passwordEmpty
        busy: first.busy
        claim: function(user) { return root.claimAutomaticFingerprint(user); }
        onRequested: root.requests++
    }
    Timer {
        interval: 250; running: true; repeat: true
        onTriggered: {
            switch (root.stage++) {
            case 0:
                if (!root.require(root.requests === 0, "unavailable account")) return;
                root.authenticationInProgress = true; first.available = true; break;
            case 1:
                if (!root.require(root.requests === 0, "busy authentication")) return;
                first.passwordEmpty = false; root.authenticationInProgress = false; break;
            case 2:
                if (!root.require(root.requests === 0, "typed password")) return;
                first.uiVisible = false; first.passwordEmpty = true; break;
            case 3:
                if (!root.require(root.requests === 0, "hidden screen")) return;
                first.username = ""; first.uiVisible = true; break;
            case 4:
                if (!root.require(root.requests === 0, "missing account")) return;
                first.username = "owner"; break;
            case 5:
                if (!root.require(root.requests === 1, "expected request after eligibility")) return;
                root.authenticationInProgress = true; break;
            case 6:
                root.authenticationInProgress = false; break;
            case 7:
                if (!root.require(root.requests === 1, "retry or second-screen loop")) return;
                first.username = "other-owner"; break;
            case 8:
                if (!root.require(root.requests === 2, "new enrolled account")) return;
                first.username = "third-owner"; first.passwordEmpty = false; break;
            case 9:
                if (!root.require(root.requests === 2, "password entry race")) return;
                root.completed = true; Qt.quit(); break;
            }
        }
    }
}
''')
            for name in ('home', 'config', 'data', 'cache', 'runtime'):
                (root / name).mkdir(mode=0o700)
            env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'QT_FORCE_STDERR_LOGGING': '1', 'HOME': str(root / 'home'),
                   'XDG_CONFIG_HOME': str(root / 'config'), 'XDG_CONFIG_DIRS': str(root / 'config'),
                   'XDG_DATA_HOME': str(root / 'data'), 'XDG_CACHE_HOME': str(root / 'cache'),
                   'XDG_RUNTIME_DIR': str(root / 'runtime'),
                   'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + str(root / 'no-bus')}
            for name in ('DISPLAY', 'WAYLAND_DISPLAY', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH'):
                env.pop(name, None)
            return subprocess.run([sys.executable, '-c', '''
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtCore import QUrl
app=QGuiApplication([]);engine=QQmlApplicationEngine()
engine.load(QUrl.fromLocalFile(sys.argv[1]))
if not engine.rootObjects():sys.exit(2)
result=app.exec();root=engine.rootObjects()[0]
if root.property('completed'):
 print('MOOS_AUTO_FINGERPRINT_QT_OK',flush=True)
else:
 print('AUTO_FINGERPRINT_FAILURE: '+root.property('failureMessage'),flush=True)
sys.exit(result)
''', str(root / 'probe.qml')], env=env, capture_output=True, text=True, timeout=15)

    def test_actual_controller_automatically_requests_once_without_input(self):
        result = self.probe()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('MOOS_AUTO_FINGERPRINT_QT_OK', result.stdout + result.stderr)
        self.assertNotIn('AUTO_FINGERPRINT_FAILURE', result.stdout + result.stderr)

    def test_disconnected_request_path_fails_the_same_native_probe(self):
        result = self.probe(broken=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AUTO_FINGERPRINT_FAILURE: expected request after eligibility', result.stdout + result.stderr)
        self.assertNotIn('MOOS_AUTO_FINGERPRINT_QT_OK', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
