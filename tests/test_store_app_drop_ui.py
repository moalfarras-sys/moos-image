#!/usr/bin/env python3
"""Load the actual Store in isolated Qt and exercise the file-review boundary, every page, both
sheets and an app's page opened from a link: any binding error in the window or its view files
fails the run."""
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
        // Every page and both sheets, one event-loop turn apart, so a binding error anywhere in
        // the window (its views are separate files) reaches the log this test reads. Updates is
        // marked known first: with the real bridge, an unknown answer would start a real check.
        // The app page opens on a reviewed recipe and then on an app with no recipe at all, the
        // order in which its advanced-source warning once kept the previous app's answer.
        plain = app.allApps.find(a => !a.install)
        reviewed = app.allApps.find(a => a.install && a.install.requires_review === true)
        if (!plain || !reviewed) {
            console.error("STORE DROP: the catalogue offered no app to open"); Qt.exit(7); return
        }
        app.updatesState = "known"
        steps.start()
    }
    property var plain
    property var reviewed
    property int step: 0
    readonly property var pages: ["apps", "games", "library", "updates", "settings", "search", "discover"]
    Timer { id: steps; interval: 120; repeat: true
        onTriggered: {
            if (step < pages.length) app.page = pages[step]
            else if (step === pages.length) app.openDetails(reviewed)
            else if (step === pages.length + 1) app.openDetails(plain)
            else if (step === pages.length + 2) app.installOne(plain)
            else if (step === pages.length + 3) {
                if (!app.selectedApp || app.selectedApp.id !== plain.id || app.pickCount !== 1) {
                    console.error("STORE DROP: the app page and the review never opened"); Qt.exit(8); return
                }
                // A link reaches a window that is already open as activateRequested(argv), the
                // way moos-qml-shell forwards a second launch. An id that breaks the launcher's
                // own rule (a leading dot, a "..") opens nothing.
                if (typeof app.activateRequested !== "function") {
                    console.error("STORE DROP: the open window cannot take a link"); Qt.exit(11); return
                }
                if (app.requestedAppId(["moos-qml-shell", "--open-app=../" + reviewed.id]) !== ""
                        || app.requestedAppId(["moos-qml-shell", "--open-app=" + reviewed.id + ".."]) !== ""
                        || app.requestedAppId(["moos-qml-shell", "--open-app=" + reviewed.id]) !== reviewed.id) {
                    console.error("STORE DROP: a malformed --open-app id was accepted"); Qt.exit(9); return
                }
                app.activateRequested(["moos-qml-shell", "--", "--open-app=../" + reviewed.id,
                                       "--open-app=" + reviewed.id + ".."])
                if (app.pendingOpenApp !== "" || app.selectedApp.id !== plain.id) {
                    console.error("STORE DROP: a malformed --open-app id was accepted"); Qt.exit(9); return
                }
                app.activateRequested(["moos-qml-shell", "--", "--open-app=" + reviewed.id])
            } else if (app.pendingOpenApp !== "") {
                return          // the request waits for the launch-time index poll to finish
            } else {
                stop()
                if (!app.selectedApp || app.selectedApp.id !== reviewed.id) {
                    console.error("STORE DROP: --open-app did not open the app's page"); Qt.exit(10); return
                }
                console.warn("STORE DROP: pages and sheets exercised")
                capture.start()
            }
            step++
        }
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
                self.assertIn("STORE DROP: pages and sheets exercised", result.stderr)
                self.assertNotRegex(result.stderr, r"TypeError|ReferenceError|Cannot assign|Unable to assign")
                self.assertGreater(frame.stat().st_size, 10000)


if __name__ == "__main__":
    unittest.main()
