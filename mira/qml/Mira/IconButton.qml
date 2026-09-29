import QtQuick
import QtQuick.Controls.Basic

// Round glass icon button with an accessible name and a tooltip.
AbstractButton {
    id: b
    property string iconName: "sparkle"
    property string tip: ""
    property color tint: Theme.ink2
    property color accent: Theme.cyan
    property bool active: false
    property real diameter: 38
    implicitWidth: diameter
    implicitHeight: diameter
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: tip
    ToolTip.visible: hovered && tip.length > 0
    ToolTip.text: tip
    ToolTip.delay: 450

    background: Rectangle {
        radius: width / 2
        color: b.active ? Qt.rgba(b.accent.r, b.accent.g, b.accent.b, 0.18)
             : b.down ? Theme.glassHover : b.hovered ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.03)
        border.width: 1
        border.color: b.active ? Qt.rgba(b.accent.r, b.accent.g, b.accent.b, 0.55)
                    : b.visualFocus ? Theme.cyan : b.hovered ? Theme.hairlineStrong : Theme.hairline
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: b.iconName
            size: Math.round(b.diameter * 0.47)
            color: b.active ? b.accent : b.enabled ? (b.hovered ? Theme.ink : b.tint) : Theme.ink3
        }
    }
    scale: down ? 0.94 : 1
    Behavior on scale { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutBack } }
}
