pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the badge that says where an app comes from (win.sourceLabel):
// "Verified" for the default channel, the origin itself for anything else.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: badge
    required property var win
    readonly property var design: win.design
    property var app: null
    implicitHeight: win.fs(22)
    implicitWidth: badgeRow.implicitWidth + 15
    radius: height / 2
    color: Qt.rgba(win.txt2.r, win.txt2.g, win.txt2.b, 0.12)
    RowLayout {
        id: badgeRow
        anchors.centerIn: parent
        spacing: design.space1
        Glyph {
            win: badge.win
            name: badge.app && badge.app.verified === true ? "check"
                                                          : badge.app && badge.app.flatpak_ref ? "shield" : "external"
            tint: badge.app && badge.app.verified === true ? win.accent : win.txt2
            Layout.preferredWidth: win.fs(11)
            Layout.preferredHeight: win.fs(11)
        }
        Text {
            text: win.sourceLabel(badge.app)
            color: badge.app && badge.app.verified === true ? win.accent : win.txt2
            font.family: win.uiFont
            font.pixelSize: win.typePx(10)
            font.bold: true
        }
    }
}
