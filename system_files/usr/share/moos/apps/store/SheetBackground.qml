pragma ComponentBehavior: Bound

import QtQuick

// Mo Store — the material of a sheet: the furthest-forward surface, so the densest. A sheet floats
// inside the window, where no compositor blur reaches it, so its pane is opaque: the scheme's card
// material with the dialog rim, one bright edge on top and a deep, soft shadow.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: sheet
    required property var win
    readonly property var design: win.design

    radius: design.radiusDialog
    color: win.cardColor
    border.width: 1
    border.color: win.design.glassEdge(win.cardColor, win.design.glassLevelDialog)

    SoftShadow { win: sheet.win; radius: sheet.radius; strength: 2.6; lift: sheet.design.space4 }
    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 1
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - sheet.radius * 1.6
        height: 1
        color: sheet.win.design.glassSpecular(sheet.win.cardColor, sheet.win.design.glassLevelDialog)
    }
}
