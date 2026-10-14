pragma ComponentBehavior: Bound

import QtQuick
import org.moos.ui as MoUI

// Mo Store — a round glass button with one glyph: previous/next on a row or the hero, back, more.
// `onGlass` draws it for a coloured surface (the hero), where the scheme's own fill would vanish.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: circle
    required property var win
    readonly property var design: win.design
    property string glyph: "arrow"
    property string accessibleName: ""
    property bool onGlass: false
    property color glassInk: win.inkOnDark
    property real size: win.fs(36)
    signal activated()

    implicitWidth: circle.size
    implicitHeight: circle.size
    radius: width / 2
    opacity: enabled ? 1 : 0.38
    color: circle.onGlass ? win.tint(circle.glassInk, circleHover.hovered ? 0.30 : 0.18)
         : circleHover.hovered ? win.tint(win.txt, win.lightScheme ? 0.10 : 0.12)
         : win.cardColor
    border.width: 1
    border.color: circle.onGlass ? win.tint(circle.glassInk, 0.32) : win.cardBorder
    scale: feedback.value
    activeFocusOnTab: true
    Accessible.role: Accessible.Button
    Accessible.name: circle.accessibleName
    Accessible.onPressAction: if (circle.enabled) circle.activated()
    Keys.onReturnPressed: if (circle.enabled) circle.activated()
    Keys.onEnterPressed: if (circle.enabled) circle.activated()
    Keys.onSpacePressed: if (circle.enabled) circle.activated()
    Behavior on color { ColorAnimation { duration: circle.win.motionEnabled ? circle.design.motionFast : 0 } }

    MoUI.SpringFeedback {
        id: feedback
        active: circle.visible
        motionEnabled: circle.win.motionEnabled
        targetScale: circleTap.pressed ? circle.design.pressScale : 1
    }
    HoverHandler { id: circleHover; cursorShape: Qt.PointingHandCursor }
    TapHandler { id: circleTap; onTapped: if (circle.enabled) circle.activated() }
    FocusRing { win: circle.win }

    Glyph {
        win: circle.win
        anchors.centerIn: parent
        width: circle.size * 0.46
        height: width
        name: circle.glyph
        tint: circle.onGlass ? circle.glassInk : circle.win.txt
    }
}
