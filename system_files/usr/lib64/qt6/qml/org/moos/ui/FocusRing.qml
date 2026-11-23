import QtQuick
import org.kde.kirigami as Kirigami

// One keyboard-focus treatment for all hand-drawn MoOS controls.
Rectangle {
    id: ring

    property color accentColor: Kirigami.Theme.focusColor
    property real controlRadius: parent && parent["radius"] !== undefined
                                 ? parent["radius"] : 0

    anchors.fill: parent
    anchors.margins: -Tokens.focusGap
    radius: controlRadius + Tokens.focusGap
    // A control that carries the MoOS corner (a square top-trailing corner)
    // gets a ring with the same corner; anything else keeps one radius.
    readonly property bool followsCorners: parent !== null
        && parent["topLeftRadius"] !== undefined && parent["topRightRadius"] !== undefined
    topLeftRadius: followsCorners ? parent["topLeftRadius"] + Tokens.focusGap : radius
    topRightRadius: followsCorners ? parent["topRightRadius"] + Tokens.focusGap : radius
    color: "transparent"
    border.width: Tokens.focusWidth
    // DecorationFocus is paired with the surrounding KDE surface. Fading it
    // a second time erased the outline on light glass.
    border.color: accentColor
    visible: parent ? parent.activeFocus : false
    z: 99
    Accessible.ignored: true
}
