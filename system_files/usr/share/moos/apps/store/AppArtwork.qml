pragma ComponentBehavior: Bound

import QtQuick

// Mo Store — an app's artwork: its AppStream icon when one loads, otherwise its
// category glyph.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: artwork
    required property var win
    property var app: null
    property int size: 52
    implicitWidth: size
    implicitHeight: size
    radius: Math.round(size * 0.28)
    color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.12)
    border.width: 1
    border.color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.22)
    Image {
        id: realIcon
        anchors.centerIn: parent
        width: artwork.size * 0.72
        height: width
        source: artwork.app && artwork.app.icon ? artwork.app.icon : ""
        sourceSize.width: Math.max(64, width)
        sourceSize.height: Math.max(64, height)
        fillMode: Image.PreserveAspectFit
        smooth: true
        asynchronous: true
        visible: status === Image.Ready
    }
    Glyph {
        win: artwork.win
        anchors.centerIn: parent
        width: artwork.size * 0.52
        height: width
        name: artwork.app && artwork.app.glyph
              ? artwork.app.glyph : win.categoryGlyph(win.normalizedCategory(artwork.app || ({})))
        tint: win.accent
        visible: !realIcon.visible
    }
}
