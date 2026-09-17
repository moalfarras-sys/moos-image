// Measures the REAL Mo AI window's navigation rail and prints the geometry as JSON.
// tests/test_moai_rail_layout.py decides what is right; this file only looks.
//
//   qml-qt6 moai-rail-review.qml -- --w=940 --h=700 [--arabic]
import QtQuick

Item {
    id: harness
    property var app

    function arg(name, fallback) {
        var hit = Qt.application.arguments.filter(a => a.indexOf("--" + name + "=") === 0)
        return hit.length ? hit[hit.length - 1].substring(name.length + 3) : fallback
    }
    function flag(name) { return Qt.application.arguments.indexOf("--" + name) >= 0 }
    function collect(item, prefix, into) {
        if (String(item.objectName || "").indexOf(prefix) === 0) into.push(item)
        for (var child of item.children || []) collect(child, prefix, into)
        return into
    }
    function box(item) {
        var origin = item.mapToItem(harness.app.contentItem, 0, 0)
        return { x: origin.x, y: origin.y, w: item.width, h: item.height }
    }

    Component.onCompleted: {
        var component = Qt.createComponent(Qt.resolvedUrl("../../system_files/usr/share/moos/apps/moai/main.qml"))
        if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.exit(2); return }
        app = component.createObject(null, { width: parseInt(arg("w", "940")), height: parseInt(arg("h", "700")) })
        settle.start()
    }

    Timer {
        id: settle; interval: 1800
        onTriggered: {
            harness.app.langOverride = harness.flag("arabic") ? "ar" : "en"
            measure.start()
        }
    }
    Timer {
        id: measure; interval: 900
        onTriggered: {
            var entries = []
            for (var pill of harness.collect(harness.app.contentItem, "railPill-", [])) {
                var id = String(pill.objectName).substring(9)
                var icon = harness.collect(pill, "railIcon-" + id, [])[0]
                var label = harness.collect(pill, "railLabel-" + id, [])[0]
                entries.push({ id: id, pill: harness.box(pill), icon: harness.box(icon),
                               label: harness.box(label), text: label.text, truncated: label.truncated,
                               inked: label.contentWidth })
            }
            console.error("RAIL-GEOMETRY " + JSON.stringify({
                width: harness.app.width, expanded: harness.app.workspaceSidebarExpanded,
                rtl: harness.app.moaiRtl, entries: entries }))
            Qt.exit(0)
        }
    }
}
