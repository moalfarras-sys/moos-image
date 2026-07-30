import QtQuick
import org.kde.kirigami as Kirigami

// The single keyboard-focus treatment for hand-drawn MoOS controls.
Rectangle {
    id: ring

    property color accentColor: Kirigami.Theme.highlightColor
    property real controlRadius: parent && parent["radius"] !== undefined
                                 ? parent["radius"] : 0

    anchors.fill: parent
    anchors.margins: -3
    radius: controlRadius + 3
    color: "transparent"
    border.width: 2
    border.color: accentColor
    visible: parent ? parent.activeFocus : false
    z: 99
    Accessible.ignored: true
}
