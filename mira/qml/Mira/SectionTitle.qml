import QtQuick

Row {
    property string icon: ""
    property string text: ""
    property color accent: Theme.cyan
    spacing: 8
    Icon { visible: parent.icon !== ""; name: parent.icon || "sparkle"; size: 16; color: parent.accent; anchors.verticalCenter: parent.verticalCenter }
    T { text: parent.text; font.pixelSize: Theme.small; font.weight: Font.DemiBold; color: Theme.ink2; font.letterSpacing: 0.3; anchors.verticalCenter: parent.verticalCenter }
}
