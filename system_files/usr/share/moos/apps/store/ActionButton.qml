pragma ComponentBehavior: Bound

import QtQuick
import org.moos.ui as MoUI

// Mo Store — an action: MoOS's shared Button in the window's palette, with a Store
// glyph and a `triggered` function the caller supplies.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
MoUI.Button {
    id: action
    required property var win
    readonly property var design: win.design
    property string glyphName: ""
    property var triggered
    implicitHeight: win.fs(40)
    cornerRadius: design.radiusControl
    iconName: action.glyphName === "" ? "" : win.glyphIcon(action.glyphName)
    iconPixelSize: win.typePx(14)
    fontPixelSize: win.typePx(13)
    motionEnabled: win.motionEnabled
    surfaceColor: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.74)
    accentColor: win.accent
    dangerColor: win.dangerInk
    textColor: win.txt
    mutedTextColor: win.txt2
    accentForegroundColor: win.accentText
    outlineColor: win.outline
    onClicked: if (action.triggered) action.triggered()
}
