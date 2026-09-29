import QtQuick

// A glass workspace that slides in from the trailing edge over the stage. Esc closes it.
Item {
    id: sheet
    property string title: ""
    property string subtitle: ""
    property string icon: "sparkle"
    property bool open: false
    property real sheetWidth: 600
    default property alias content: holder.data
    signal closeRequested()
    visible: open || slide.running

    // scrim
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.01, 0.01, 0.04, sheet.open ? 0.45 : 0)
        Behavior on color { ColorAnimation { duration: Theme.normal } }
        TapHandler { onTapped: sheet.closeRequested() }
    }

    Glass {
        id: panel
        width: Math.min(sheet.width, sheet.sheetWidth)
        height: parent.height
        tint: Qt.rgba(0.045, 0.055, 0.13, 0.975)
        radius: Theme.rPanel
        property real offset: sheet.open ? 0 : width + 24
        x: (mira.lang === "ar" ? 0 : parent.width - width) + (mira.lang === "ar" ? -offset : offset)
        Behavior on offset { NumberAnimation { id: slide; duration: Theme.emphasized; easing.type: Easing.OutCubic } }
        opacity: sheet.open ? 1 : 0.6
        Behavior on opacity { NumberAnimation { duration: Theme.normal } }

        TapHandler {}  // keep clicks inside the panel from reaching the scrim

        Item {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 22 }
            height: 56
            Rectangle {
                id: iconBox
                width: 44; height: 44; radius: 15
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                color: Qt.rgba(0.21, 0.85, 0.96, 0.10)
                border.width: 1; border.color: Qt.rgba(0.21, 0.85, 0.96, 0.25)
                Icon { anchors.centerIn: parent; name: sheet.icon; size: 22; color: Theme.cyan }
            }
            Column {
                anchors.left: iconBox.right; anchors.leftMargin: 14
                anchors.right: closeBtn.left; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 2
                T { width: parent.width; text: sheet.title; font.pixelSize: Theme.heading; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                T { width: parent.width; text: sheet.subtitle; font.pixelSize: Theme.small; color: Theme.ink3; visible: text !== ""; maximumLineCount: 2; elide: Text.ElideRight }
            }
            IconButton { id: closeBtn; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; iconName: "x"; tip: mira.s.close; onClicked: sheet.closeRequested() }
        }
        Item {
            id: holder
            anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: parent.bottom; margins: 22; topMargin: 14 }
        }
    }
}
