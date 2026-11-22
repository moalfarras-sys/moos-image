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
    // The MoOS corner: the top-trailing corner is square. A Popup's background
    // sits outside its content's LayoutMirroring scope, so read the window's
    // direction itself.
    readonly property real squareRadius: Math.min(radius, design.radiusSquare)
    topLeftRadius: win.rtl ? squareRadius : radius
    topRightRadius: win.rtl ? radius : squareRadius
    color: win.cardColor
    border.width: 1
    border.color: win.design.glassEdge(win.cardColor, win.design.glassLevelDialog)

    SoftShadow { win: sheet.win; radius: sheet.radius; strength: 2.6; lift: sheet.design.space4 }
    Rectangle {
        // The catch-light stops short of each corner by that corner's own
        // curve: a round corner's 0.8 of the radius, the square one's softening.
        readonly property real roundInset: sheet.radius * 0.8
        readonly property real squareInset: sheet.squareRadius + 2
        anchors.top: parent.top
        anchors.topMargin: 1
        x: sheet.win.rtl ? squareInset : roundInset
        width: Math.max(0, parent.width - roundInset - squareInset)
        height: 1
        color: sheet.win.design.glassSpecular(sheet.win.cardColor, sheet.win.design.glassLevelDialog)
    }
}
