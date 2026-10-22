#!/usr/bin/env python3
"""Match the actual native Kicker IDs, recording activation instead of launching apps.

The old lookup passed string gates but the real Home button did nothing: Kicker
normalizes desktop IDs to applications: URLs. No owner bus, apps or data are used.
"""
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
SOURCE = ROOT / 'system_files/usr/share/plasma/plasmoids/org.moos.brand/contents/ui/main.qml'


def source_parts():
    text = SOURCE.read_text()
    start = text.index('function openDesktop(desktopId)')
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    model = text.split('id: launcherDestinations', 1)[1]
    configured = json.loads(re.search(r'favorites:\s*(\[[^\]]+\])', model).group(1))
    return text[start:end], configured


def native_driver():
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    from PySide6.QtTest import QTest

    app = QGuiApplication([])
    engine = QQmlEngine()
    function, configured = source_parts()
    fixed_lookup = 'destinations.indexOf("applications:" + desktopId)'
    assert fixed_lookup in function
    observations = []
    for broken in (False, True):
        body = function.replace(fixed_lookup, 'destinations.indexOf(desktopId)') if broken else function
        qml = '''import QtQuick
import org.kde.plasma.private.kicker as Kicker
QtObject {
    id: root
    property Kicker.SimpleFavoritesModel nativeModel: Kicker.SimpleFavoritesModel {
        favorites: ''' + json.dumps(configured) + '''
    }
    property var calls: []
    property int closed: 0
    property bool permit: true
    // Preserve the actual C++ model's identity data; intercept only the launch.
    readonly property var launcherDestinations: ({
        favorites: nativeModel.favorites,
        trigger: function(row, action, argument) {
            root.calls = root.calls.concat([row]);
            return root.permit;
        }
    })
    function closeLauncher() { root.closed += 1; }
    ''' + body + '''
    function probe() {
        const ids = ''' + json.dumps(configured) + ''';
        for (const id of ids) openDesktop(id);
        const accepted = closed;
        openDesktop("");
        openDesktop("not-installed.desktop");
        const afterUnknown = calls.length;
        permit = false;
        openDesktop(ids[0]);
        return JSON.stringify({nativeIds:nativeModel.favorites, accepted:accepted,
            afterUnknown:afterUnknown, finalClosed:closed, calls:calls});
    }
    property string result: ""
    function run() { result = probe(); }
}'''
        component = QQmlComponent(engine)
        component.setData(qml.encode(), QUrl())
        obj = component.create()
        assert obj is not None, [e.toString() for e in component.errors()]
        QTest.qWait(50)
        obj.run()
        result = json.loads(obj.property('result'))
        assert len(result['nativeIds']) == len(configured), result
        if broken:
            assert result['accepted'] == 0 and not result['calls'], result
        else:
            assert result['accepted'] == len(configured), result
            assert result['afterUnknown'] == len(configured), result
            assert result['finalClosed'] == len(configured), 'Failed activation must keep the launcher open'
            assert result['calls'] == list(range(len(configured))) + [0], result
        observations.append(dict(broken=broken, **result))
        obj.deleteLater()
        app.processEvents()
    print(json.dumps(observations))


class LauncherDestinations(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('PySide6'), 'native Qt/PySide6 unavailable')
    def test_native_normalization_failure_and_unknown_destination_refusals(self):
        with tempfile.TemporaryDirectory(prefix='moos-kicker-destinations-') as tmp:
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=tmp+'/config', XDG_DATA_HOME=tmp+'/data',
                       XDG_CACHE_HOME=tmp+'/cache', XDG_RUNTIME_DIR=tmp,
                       DBUS_SESSION_BUS_ADDRESS='unix:path='+tmp+'/absent',
                       QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software', QML_DISABLE_DISK_CACHE='1')
            result = subprocess.run([sys.executable, __file__, '--native-driver'], env=env,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(len(json.loads(result.stdout)), 2)


if __name__ == '__main__':
    if sys.argv[1:] == ['--native-driver']:
        native_driver()
    else:
        unittest.main()
