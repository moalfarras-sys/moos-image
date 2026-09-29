import QtQuick
import QtQuick.Controls.Basic

// Text button. `primary` = Mira gradient; default = quiet glass.
AbstractButton {
    id: b
    property string iconName: ""
    property bool primary: false
    property bool danger: false
    property color accent: Theme.cyan
    property int size: Theme.body
    implicitHeight: 38
    implicitWidth: row.implicitWidth + 28
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: text

    background: Rectangle {
        radius: height / 2
        gradient: b.primary ? grad : null
        color: b.primary ? "transparent"
             : b.danger ? Qt.rgba(1, 0.36, 0.48, b.hovered ? 0.22 : 0.12)
             : b.down ? Theme.glassHover : b.hovered ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(1, 1, 1, 0.045)
        border.width: 1
        border.color: b.visualFocus ? Theme.cyan : b.primary ? Qt.rgba(1, 1, 1, 0.22)
                    : b.danger ? Qt.rgba(1, 0.36, 0.48, 0.45) : b.hovered ? Theme.hairlineStrong : Theme.hairline
        opacity: b.enabled ? 1 : 0.45
        Gradient {
            id: grad
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: b.hovered ? "#7C68FF" : "#6A55F0" }
            GradientStop { position: 1; color: b.hovered ? "#3FE0F8" : "#2CC6E6" }
        }
    }
    contentItem: Item {
        implicitWidth: row.implicitWidth
        implicitHeight: row.implicitHeight
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 7
            Icon { visible: b.iconName !== ""; name: b.iconName || "sparkle"; size: b.size + 3; anchors.verticalCenter: parent.verticalCenter
                   color: b.primary ? "white" : b.danger ? Theme.danger : b.enabled ? Theme.ink : Theme.ink3 }
            T { text: b.text; font.pixelSize: b.size; font.weight: b.primary ? Font.DemiBold : Font.Medium; wrapMode: Text.NoWrap
                color: b.primary ? "white" : b.danger ? Theme.danger : b.enabled ? Theme.ink : Theme.ink3; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    scale: down ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: Theme.fast } }
}
