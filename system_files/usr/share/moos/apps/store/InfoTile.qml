pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — one fact on an app's page (size, version, age rating, licence, language, source):
// a small caption, the fact in large type, and a line under it. Values that are numbers or
// versions stay a left-to-right island inside Arabic.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: tile
    required property var win
    readonly property var design: win.design
    property string caption: ""
    property string value: ""
    property string detail: ""
    property string glyph: "spark"
    property color tone: win.accent

    implicitHeight: column.implicitHeight + design.space3 * 2
    implicitWidth: win.fs(150)
    Accessible.role: Accessible.StaticText
    Accessible.name: tile.caption + ": " + tile.value + (tile.detail !== "" ? ", " + tile.detail : "")

    ColumnLayout {
        id: column
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: tile.design.space3
        anchors.rightMargin: tile.design.space3
        spacing: tile.design.space1
        Text {
            Layout.fillWidth: true
            text: tile.caption
            color: tile.win.txt2
            font.family: tile.win.uiFont
            font.pixelSize: tile.win.typePx(11)
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: tile.design.space1 + 2
            Glyph {
                win: tile.win
                name: tile.glyph
                tint: tile.tone
                Layout.preferredWidth: tile.win.fs(16)
                Layout.preferredHeight: tile.win.fs(16)
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.maximumWidth: tile.width - tile.design.space6 - tile.design.space3
                text: tile.value
                color: tile.win.txt
                font.family: tile.win.uiFont
                font.pixelSize: tile.win.typePx(15)
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }
        Text {
            Layout.fillWidth: true
            visible: tile.detail !== ""
            text: tile.detail
            color: tile.win.txt2
            font.family: tile.win.uiFont
            font.pixelSize: tile.win.typePx(11)
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }
    }
}
