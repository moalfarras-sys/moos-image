// Drives the REAL Mo AI window through its native tool loop against a scripted provider and the
// real moai-control. No fixtures inside the app, no automatic approvals in the app: this harness
// presses the card's own button, the way a person would, and records what happened.
//
//   qml-qt6 moai-tools-review.qml -- --gateway-port G --control-port C --agent-port A
//                                    --out=/dir [--arabic] [--decline]
import QtQuick
import QtTest as Test

Item {
    id: harness
    property var app
    property var frame
    property int ticks: 0
    property bool decided: false
    property var seenRoles: []
    readonly property string out: arg("out", "/tmp")
    Test.TestCase { id: driver; name: "MoAIToolsReview"; when: false }

    function arg(name, fallback) {
        var hit = Qt.application.arguments.filter(a => a.indexOf("--" + name + "=") === 0)
        return hit.length ? hit[hit.length - 1].substring(name.length + 3) : fallback
    }
    function flag(name) { return Qt.application.arguments.indexOf("--" + name) >= 0 }
    function find(item, name) {
        if (item.objectName === name) return item
        for (var child of item.children || []) {
            var match = find(child, name)
            if (match) return match
        }
        return null
    }
    function shoot(name, then) {
        frame.grabToImage(function (result) {
            result.saveToFile(harness.out + "/" + name + ".png")
            if (then) then()
        })
    }
    function finish(verdict) {
        var rows = []
        for (var i = 0; i < app.chatRows.count; ++i) {
            var row = app.chatRows.get(i)
            rows.push({ role: row.role, text: String(row.text).substring(0, 400) })
        }
        var report = {
            verdict: verdict, rows: rows, history: app.history, stepsLeft: app.toolStepsLeft,
            toolsOffered: app.availableTools.length, agentMode: app.agentMode,
            hermesReady: app.hermesReady, busy: app.busy
        }
        console.error("REVIEW-RESULT " + JSON.stringify(report))
        shoot("final", function () { Qt.exit(verdict === "ok" ? 0 : 1) })
    }

    Component.onCompleted: {
        var component = Qt.createComponent(Qt.resolvedUrl("../../system_files/usr/share/moos/apps/moai/main.qml"))
        if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.exit(2); return }
        // 1400x900 unless told otherwise; the window's real default is 940x700, and a layout that is
        // only ever looked at wide is how the compact rail shipped broken.
        app = component.createObject(null, { width: parseInt(arg("w", "1400")), height: parseInt(arg("h", "900")) })
        var children = Array.from(app.contentItem.children)
        frame = Qt.createQmlObject('import QtQuick; Rectangle { anchors.fill: parent; color: "' + app.color + '" }', app.contentItem)
        for (var child of children) child.parent = frame
        begin.start()
    }

    Timer {
        id: begin; interval: 2500
        onTriggered: {
            harness.app.langOverride = harness.flag("arabic") ? "ar" : "en"
            if (harness.app.availableTools.length === 0) { harness.finish("no tools were loaded from moai-control"); return }
            harness.app.sendPrompt(harness.flag("arabic") ? "الصوت لا يعمل، افحص وأصلح" : "My sound is broken. Check and fix it.")
            watch.start()
        }
    }

    Timer {
        id: watch; interval: 400; repeat: true
        onTriggered: {
            harness.ticks += 1
            var pending = harness.app.pendingToolConfirmation
            if (pending !== null && !harness.decided) {
                harness.decided = true
                watch.stop()
                harness.shoot("card", function () {
                    if (harness.flag("decline")) harness.app.cancelToolExecution()
                    else harness.app.confirmToolExecution()
                    watch.start()
                })
                return
            }
            var last = harness.app.chatRows.count > 0
                ? harness.app.chatRows.get(harness.app.chatRows.count - 1) : null
            if (harness.decided && !harness.app.busy && harness.app.toolBatch === null
                    && last && last.role === "assistant") {
                watch.stop()
                harness.finish("ok")
            } else if (harness.ticks > 110) {
                watch.stop()
                harness.finish("timed out waiting for the loop to finish")
            }
        }
    }
}
