pragma ComponentBehavior: Bound

import QtQuick

// Mo Store — one soft depth shadow under a raised surface, drawn as four widening rounded layers
// so it costs no shader and looks the same with software rendering. Place it inside the surface
// with `z: -1`: an item with a negative z is painted below its parent. `strength` 0..1 lets a
// hovered card lift (its shadow grows) without moving its hit area.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: shadow
    required property var win
    property real radius: win.design.radiusCard
    property real strength: 1
    property real lift: win.design.space2

    anchors.fill: parent
    z: -1

    Repeater {
        model: 4
        delegate: Rectangle {
            required property int index
            readonly property real spread: (index + 1) * shadow.lift * 0.5
            x: -spread
            y: -spread + shadow.lift * (0.35 + index * 0.25)
            width: shadow.width + spread * 2
            height: shadow.height + spread * 2
            radius: shadow.radius + spread
            color: Qt.rgba(0, 0, 0, (shadow.win.lightScheme ? 0.035 : 0.09) * shadow.strength / (index + 1))
        }
    }
}
