import QtQuick

// A destination that scrolls itself (Home, Settings): the same header as PageFrame over a filled area.
Item {
    id: frame
    property string icon: "sparkle"
    property string title: ""
    property string subtitle: ""
    property color accent: Theme.cyan
    default property alias content: holder.data
    Item {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 64
        Rectangle {
            id: glyph
            width: 46; height: 46; radius: 15
            anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
            color: Qt.rgba(frame.accent.r, frame.accent.g, frame.accent.b, 0.12)
            border.width: 1; border.color: Qt.rgba(frame.accent.r, frame.accent.g, frame.accent.b, 0.32)
            Icon { anchors.centerIn: parent; name: frame.icon; size: 22; color: frame.accent }
        }
        Column {
            anchors { left: glyph.right; leftMargin: 14; right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 2
            T { text: frame.title; font.pixelSize: Theme.heading; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight; width: parent.width }
            T { visible: text !== ""; text: frame.subtitle; font.pixelSize: Theme.small; color: Theme.ink3; width: parent.width; maximumLineCount: 2; elide: Text.ElideRight }
        }
    }
    Item {
        id: holder
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; topMargin: 14 }
    }
}
