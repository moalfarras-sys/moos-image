// Render a first-party MoOS QML app FROM SOURCE into a PNG, with no backend services.
// A review aid (see render-app.sh), not a gate: what a person sees when the window opens.
//
//   --src=/abs/main.qml --out=/abs/frame.png [--w=1400 --h=900] [--lang=ar|en]
//   [--set=property=value …] [--call=function …] [--wait=2500]
import QtQuick

Item {
    id: harness
    property var app
    property var frame
    function arg(name, fallback) {
        var hit = Qt.application.arguments.filter(a => a.indexOf("--" + name + "=") === 0)
        return hit.length ? hit[hit.length - 1].substring(name.length + 3) : fallback
    }
    function args(name) {
        return Qt.application.arguments.filter(a => a.indexOf("--" + name + "=") === 0)
                 .map(a => a.substring(name.length + 3))
    }
    Component.onCompleted: {
        var component = Qt.createComponent("file://" + arg("src", ""))
        if (component.status !== Component.Ready) {
            console.error("RENDER FAIL: " + component.errorString()); Qt.exit(1); return
        }
        app = component.createObject(null, { width: parseInt(arg("w", "1400")), height: parseInt(arg("h", "900")) })
        if (!app) { console.error("RENDER FAIL: createObject returned null"); Qt.exit(1); return }
        // grabToImage needs an Item: move the window's content under one we own.
        var children = Array.from(app.contentItem.children)
        frame = Qt.createQmlObject('import QtQuick; Rectangle { anchors.fill: parent; color: "' + app.color + '" }', app.contentItem)
        for (var child of children) child.parent = frame
        apply.start()
    }
    Timer {
        id: apply; interval: 600
        onTriggered: {
            var lang = harness.arg("lang", "")
            if (lang !== "" && harness.app.hasOwnProperty("langOverride")) harness.app.langOverride = lang
            for (var pair of harness.args("set")) {
                var eq = pair.indexOf("=")
                var key = pair.substring(0, eq), raw = pair.substring(eq + 1)
                var value = raw === "true" ? true : raw === "false" ? false
                          : (isNaN(Number(raw)) || raw === "" ? raw : Number(raw))
                try { harness.app[key] = value } catch (e) { console.error("set " + key + " failed: " + e) }
            }
            for (var fn of harness.args("call")) {
                try { harness.app[fn]() } catch (e) { console.error("call " + fn + " failed: " + e) }
            }
            shoot.interval = parseInt(harness.arg("wait", "2500"))
            shoot.start()
        }
    }
    Timer {
        id: shoot
        onTriggered: harness.frame.grabToImage(function (result) {
            var ok = result.saveToFile(harness.arg("out", "/tmp/render.png"))
            if (!ok) console.error("RENDER FAIL: could not save the frame")
            Qt.exit(ok ? 0 : 1)
        })
    }
}
