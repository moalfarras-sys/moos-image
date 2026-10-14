pragma ComponentBehavior: Bound

import QtQuick
import org.moos.ui as MoUI

// Mo Store — an action: MoOS's shared Button in the window's palette, with a Store glyph and a
// `triggered` function the caller supplies. `pill` rounds it fully, for the actions that sit on
// a hero or a card's foot.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
MoUI.Button {
    id: action
    required property var win
    readonly property var design: win.design
    property string glyphName: ""
    property var triggered
    property bool pill: false
    implicitHeight: win.fs(40)
    cornerRadius: action.pill ? height / 2 : design.radiusControl
    iconName: action.glyphName === "" ? "" : win.glyphIcon(action.glyphName)
    iconPixelSize: win.typePx(15)
    fontPixelSize: win.typePx(13)
    motionEnabled: win.motionEnabled
    surfaceColor: win.cardColor
    accentColor: win.accent
    dangerColor: win.dangerInk
    textColor: win.txt
    mutedTextColor: win.txt2
    accentForegroundColor: win.accentText
    outlineColor: win.cardBorder
    leftPadding: design.space4
    rightPadding: design.space4
    // The shared button sizes itself for its own, narrower padding; a Store action measures its
    // label with the padding it actually has, so a label is never cut to "Det…".
    implicitWidth: Math.max(implicitHeight, contentItem.implicitWidth + leftPadding + rightPadding)
    onClicked: if (action.triggered) action.triggered()
}
