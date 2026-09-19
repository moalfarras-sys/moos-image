#!/usr/bin/env python3
"""Load the actual Store in isolated Qt and exercise the file-review boundary."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = shutil.which("moos-qml-shell")


@unittest.skipUnless(RUNTIME, "requires native MoOS Qt runtime")
class StoreDrop(unittest.TestCase):
    def test_real_window_file_review_and_capture(self):
        spec = importlib.util.spec_from_file_location("studio", ROOT / "scripts/review/design-studio.py")
        studio = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(studio)
        for language, scheme in (("en", "MoOSUI2Dark"), ("ar", "MoOSUI2AuroraLight")):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as raw:
                work = Path(raw)
                config = work / "config"
                config.mkdir()
                studio.write_palette(config, scheme)
                runtime = work / "run"
                runtime.mkdir(mode=0o700)
                evidence = ROOT / "test-results/store-drop"
                evidence.mkdir(parents=True, exist_ok=True)
                frame = evidence / f"store-{language}.png"
                qml = work / "probe.qml"
                qml.write_text('''import QtQuick
Item {
    property var app
    property var frame
    Component.onCompleted: {
        let component = Qt.createComponent("%s")
        if (component.status !== Component.Ready) {
            console.error(component.errorString()); Qt.exit(1); return
        }
        app = component.createObject(null, {width: 1100, height: 760})
        if (!app) { Qt.exit(2); return }
        // A remote URL must be refused: installFile only accepts a local regular
        // file. reviewDroppedFile returns whether MoOS took it, so this asserts
        // the refusal instead of merely not crashing.
        if (app.reviewDroppedFile("https://example.invalid/app") !== false) {
            console.error("STORE DROP: a remote URL was accepted"); Qt.exit(5); return
        }
        if (typeof MoosStore === "undefined") {
            console.error("STORE DROP: the bridge was never registered"); Qt.exit(6); return
        }
        let children = Array.from(app.contentItem.children)
        frame = Qt.createQmlObject('import QtQuick; Rectangle { anchors.fill: parent }', app.contentItem)
        frame.color = app.color
        for (let child of children) child.parent = frame
        capture.start()
    }
    Timer { id: capture; interval: 1500
        onTriggered: frame.grabToImage(function(result) {
            Qt.exit(result.saveToFile("%s") ? 0 : 4)
        })
    }
}
''' % ((ROOT / "system_files/usr/share/moos/apps/store/main.qml").as_uri(), frame))
                env = dict(os.environ, HOME=str(work), XDG_CONFIG_HOME=str(config),
                           XDG_CONFIG_DIRS=str(config), XDG_DATA_HOME=str(work / "data"),
                           XDG_CACHE_HOME=str(work / "cache"), XDG_RUNTIME_DIR=str(runtime),
                           DBUS_SESSION_BUS_ADDRESS="unix:path=" + str(work / "no-bus"),
                           QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                           QML_IMPORT_PATH=str(ROOT / "system_files/usr/lib64/qt6/qml"),
                           QML_DISABLE_DISK_CACHE="1", QML_XHR_ALLOW_FILE_READ="1",
                           QT_FORCE_STDERR_LOGGING="1", QT_LOGGING_RULES="qml=true",
                           QT_QPA_PLATFORMTHEME="kde", LANG=language + "_" + ("EG" if language == "ar" else "US") + ".UTF-8")
                result = subprocess.run([RUNTIME, "--app-id", "org.moos.store", "--qml", str(qml)],
                                        env=env, capture_output=True, text=True, timeout=35)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotRegex(result.stderr, r"TypeError|ReferenceError|Cannot assign|Unable to assign")
                self.assertGreater(frame.stat().st_size, 10000)


if __name__ == "__main__":
    unittest.main()
