pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the small badge that says where an app comes from (win.sourceLabel): "Verified" for
// a verified Linux app and only then, otherwise its kind in a person's words — Web app, Windows
// program, Android app, From the publisher's website, Developer tool.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: badge
    required property var win
    readonly property var design: win.design
    property var app: null
    // A badge never pushes a card's button out: past this width its words are elided.
    property real maxWidth: win.fs(240)
    readonly property bool verified: badge.app !== null && badge.app.verified === true
    readonly property color ink: badge.verified ? win.accent : win.txt2

    implicitHeight: win.fs(22)
    implicitWidth: Math.min(badge.maxWidth, badgeRow.implicitWidth + design.space2 * 2)
    Layout.maximumWidth: badge.maxWidth
    clip: true
    radius: height / 2
    color: badge.verified ? win.tint(win.accent, win.lightScheme ? 0.12 : 0.16)
                          : win.tint(win.txt, win.lightScheme ? 0.06 : 0.08)
    Accessible.ignored: true

    RowLayout {
        id: badgeRow
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: badge.design.space2
        width: Math.min(implicitWidth, badge.width - badge.design.space2 * 2)
        spacing: badge.design.space1
        Glyph {
            win: badge.win
            name: badge.verified ? "check" : badge.win.kindGlyph(badge.win.appKind(badge.app))
            tint: badge.ink
            Layout.preferredWidth: badge.win.fs(12)
            Layout.preferredHeight: badge.win.fs(12)
        }
        Text {
            Layout.fillWidth: true
            text: badge.win.sourceLabel(badge.app)
            horizontalAlignment: Text.AlignLeft
            elide: Text.ElideRight
            color: badge.ink
            font.family: badge.win.uiFont
            font.pixelSize: badge.win.typePx(11)
            font.weight: Font.DemiBold
        }
    }
}
