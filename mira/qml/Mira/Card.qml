import QtQuick
import QtQuick.Layouts

// A titled glass card inside a page: glyph + title (+ trailing status or actions) over its content.
Glass {
    id: card
    property string icon: ""
    property string title: ""
    property string subtitle: ""
    property color accent: Theme.cyan
    default property alias content: body.data
    property alias trailing: trail.data
    Layout.fillWidth: true
    Layout.preferredHeight: col.implicitHeight + 32
    implicitHeight: col.implicitHeight + 32
    radius: 20

    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            visible: card.title !== "" || card.icon !== ""
            spacing: 10
            Icon { visible: card.icon !== ""; name: card.icon || "sparkle"; size: 18; color: card.accent }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                T { text: card.title; font.pixelSize: Theme.body; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                T { visible: card.subtitle !== ""; text: card.subtitle; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true }
            }
            Row { id: trail; spacing: 8 }
        }
        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 10
        }
    }
}
