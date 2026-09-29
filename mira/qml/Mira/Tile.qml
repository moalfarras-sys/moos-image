import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// A clickable tile: glyph, title, one line of state. Tab/Enter/Space reach it; `busy` spins the glyph,
// `on` marks a toggle that is on, `badge` shows a short count or word.
AbstractButton {
    id: tile
    property string icon: "sparkle"
    property string title: ""
    property string subtitle: ""
    property string badge: ""
    property color accent: Theme.cyan
    property bool busy: false
    property bool lit: false
    Layout.fillWidth: true
    implicitHeight: 74
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: title + (subtitle ? " · " + subtitle : "")
    background: Rectangle {
        radius: 16
        color: tile.lit ? Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.16)
             : tile.down ? Theme.glassHover : tile.hovered ? Qt.rgba(1, 1, 1, 0.075) : Qt.rgba(1, 1, 1, 0.04)
        border.width: tile.visualFocus ? 2 : 1
        border.color: tile.visualFocus ? Theme.cyan : tile.lit || tile.busy ? Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.55)
                    : tile.hovered ? Theme.hairlineStrong : Theme.hairline
        opacity: tile.enabled ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    contentItem: RowLayout {
        spacing: 10
        Rectangle {
            property real spin: 0
            Layout.preferredWidth: 38; Layout.preferredHeight: 38
            Layout.leftMargin: 10
            radius: 12
            rotation: tile.busy ? spin : 0
            color: Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, tile.lit ? 0.30 : 0.14)
            Icon { anchors.centerIn: parent; name: tile.icon; size: 19; color: tile.lit ? "white" : tile.accent }
            NumberAnimation on spin { running: tile.busy && mira.motion; from: 0; to: 360; duration: 1500; loops: Animation.Infinite }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.rightMargin: 10
            spacing: 2
            T { text: tile.title; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
            T { visible: tile.subtitle !== ""; text: tile.subtitle; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
        }
        Rectangle {
            visible: tile.badge !== ""
            Layout.rightMargin: 10
            implicitHeight: 22; implicitWidth: badgeText.implicitWidth + 14; radius: 11
            color: Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.2)
            T { id: badgeText; anchors.centerIn: parent; text: tile.badge; font.pixelSize: Theme.tiny; color: tile.accent; wrapMode: Text.NoWrap }
        }
    }
    scale: down ? 0.98 : 1
    Behavior on scale { NumberAnimation { duration: Theme.fast } }
}
