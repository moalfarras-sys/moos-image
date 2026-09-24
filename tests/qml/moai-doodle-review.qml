import QtQuick

// Loads the real Mo AI window and reports how its chat texture is drawn on THIS scene graph.
// tests/test_moai_doodle_software.py runs it offscreen under QT_QUICK_BACKEND=software.
Item {
    id: harness
    property var app

    function collect(item, name, into) {
        if (String(item.objectName || "") === name) into.push(item)
        for (var child of item.children || []) collect(child, name, into)
        return into
    }

    Component.onCompleted: {
        var component = Qt.createComponent(Qt.resolvedUrl("../../system_files/usr/share/moos/apps/moai/main.qml"))
        if (component.status !== Component.Ready) { console.error(component.errorString()); Qt.exit(2); return }
        app = component.createObject(null, { width: 940, height: 700 })
        settle.start()
    }
    Timer {
        id: settle; interval: 2500
        onTriggered: {
            var doodles = []
            for (var doodle of harness.collect(harness.app.contentItem, "chatDoodle", [])) {
                var tile = harness.collect(doodle, "chatDoodleTile", [])[0]
                doodles.push({ recolourable: doodle.recolourable, drawsTexture: doodle.drawsTexture,
                               layer: tile ? tile.layer.enabled : null,
                               api: doodle.GraphicsInfo.api })
            }
            console.error("DOODLE-STATE " + JSON.stringify({
                software: GraphicsInfo.Software, isDark: harness.app.isDark, doodles: doodles }))
            Qt.exit(0)
        }
    }
}
