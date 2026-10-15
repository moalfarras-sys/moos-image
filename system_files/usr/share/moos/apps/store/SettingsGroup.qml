pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — one group on the Settings page: its name above, and its rows on one card.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
ColumnLayout {
    id: group
    required property var win
    readonly property var design: win.design
    property string title: ""
    default property alias content: rows.data

    spacing: design.space2

    Text {
        Layout.fillWidth: true
        Layout.leftMargin: group.design.space2
        text: group.title
        color: group.win.txt2
        font.family: group.win.uiFont
        font.pixelSize: group.win.typePx(13)
        font.weight: Font.DemiBold
        Accessible.role: Accessible.Heading
    }
    Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: rows.implicitHeight + group.design.space5 * 2
        radius: group.design.radiusCard + 2
        color: group.win.cardColor
        border.width: 1
        border.color: group.win.cardBorder
        SoftShadow { win: group.win; radius: parent.radius; strength: 0.7 }
        ColumnLayout {
            id: rows
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: group.design.space5
            spacing: group.design.space4
        }
    }
}
