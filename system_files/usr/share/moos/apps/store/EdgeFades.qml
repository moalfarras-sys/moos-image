pragma ComponentBehavior: Bound

import QtQuick

// Mo Store — a sideways strip fades at an edge it continues past, so a cut chip reads as "more this
// way" rather than as a mistake. Placed over the strip (not inside its scrolling content), on the
// strip's absolute left and right: the visibility of each side follows contentX, which is never
// mirrored, so neither are the fades.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: fades
    required property var win
    property Flickable flick: null
    property color base: win.canvas
    LayoutMirroring.enabled: false
    LayoutMirroring.childrenInherit: true

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: fades.win.fs(48)
        visible: fades.flick !== null && fades.flick.contentX > 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: fades.base }
            GradientStop { position: 1; color: fades.win.tint(fades.base, 0) }
        }
    }
    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: fades.win.fs(48)
        visible: fades.flick !== null && fades.flick.contentX < fades.flick.contentWidth - fades.flick.width - 1
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: fades.win.tint(fades.base, 0) }
            GradientStop { position: 1; color: fades.base }
        }
    }
}
