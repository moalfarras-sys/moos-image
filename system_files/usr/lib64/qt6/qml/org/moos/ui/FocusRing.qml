import QtQuick
import org.kde.kirigami as Kirigami

// One keyboard-focus treatment for all hand-drawn MoOS controls.
Rectangle {
    id: ring

    property color accentColor: Kirigami.Theme.highlightColor
    property real controlRadius: parent && parent["radius"] !== undefined
                                 ? parent["radius"] : 0

    anchors.fill: parent
    anchors.margins: -Tokens.focusGap
    radius: controlRadius + Tokens.focusGap
    color: "transparent"
    border.width: Tokens.focusWidth
    border.color: Qt.alpha(accentColor, Tokens.focusOpacity)
    visible: parent ? parent.activeFocus : false
    z: 99
    Accessible.ignored: true
}
