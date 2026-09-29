import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// One destination of Mira's window: a header (glyph, title, one line of purpose, optional actions)
// over a scrolling column. Pages put their cards in it; spacing and width come from here so every
// page reads the same.
Item {
    id: frame
    property string icon: "sparkle"
    property string title: ""
    property string subtitle: ""
    property color accent: Theme.cyan
    property bool busy: false
    default property alias content: column.data
    property alias actions: actionRow.data
    readonly property real contentWidth: column.width

    Item {
        id: head
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 64
        Rectangle {
            id: glyph
            width: 46; height: 46; radius: 15
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            color: Qt.rgba(frame.accent.r, frame.accent.g, frame.accent.b, 0.12)
            border.width: 1; border.color: Qt.rgba(frame.accent.r, frame.accent.g, frame.accent.b, 0.32)
            Icon { anchors.centerIn: parent; name: frame.icon; size: 22; color: frame.accent }
            // a slow turn while the page reads
            Rectangle {
                anchors.fill: parent; anchors.margins: -3; radius: 18
                color: "transparent"; border.width: 2
                border.color: Qt.rgba(frame.accent.r, frame.accent.g, frame.accent.b, 0.55)
                visible: frame.busy
                opacity: 0.6
                SequentialAnimation on opacity {
                    running: frame.busy && mira.motion; loops: Animation.Infinite
                    NumberAnimation { to: 0.15; duration: 700 } NumberAnimation { to: 0.7; duration: 700 }
                }
            }
        }
        Column {
            anchors { left: glyph.right; leftMargin: 14; right: actionRow.left; rightMargin: 12; verticalCenter: parent.verticalCenter }
            spacing: 2
            T { text: frame.title; font.pixelSize: Theme.heading; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight; width: parent.width }
            T { visible: text !== ""; text: frame.subtitle; font.pixelSize: Theme.small; color: Theme.ink3; width: parent.width; maximumLineCount: 2; elide: Text.ElideRight }
        }
        Row {
            id: actionRow
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 8
        }
    }

    Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; topMargin: 14 }
        contentHeight: column.implicitHeight + 24
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { width: 6 }
        ColumnLayout {
            id: column
            width: flick.width - 10
            spacing: 16
        }
    }
}
