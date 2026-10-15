pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — whether an app works on this computer, in one pill: "Works on this PC", "Works with
// limits" or "Not available here", in the scheme's positive, neutral or negative ink. The verdict
// comes from the index (compat), judged against this machine; an index that does not say shows
// nothing rather than a guess.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: badge
    required property var win
    readonly property var design: win.design
    property var app: null
    property bool compact: false
    readonly property var compat: win.compatOf(badge.app)
    readonly property color ink: badge.compat.verdict === "blocked" ? win.dangerInk
                               : badge.compat.verdict === "warn" ? win.warningInk : win.positiveInk

    visible: badge.app !== null && badge.compat.known
    implicitHeight: badge.compact ? win.fs(24) : win.fs(30)
    implicitWidth: badgeRow.implicitWidth + (badge.compact ? design.space2 * 2 : design.space3 * 2)
    radius: height / 2
    color: win.tint(badge.ink, win.lightScheme ? 0.12 : 0.14)
    border.width: 1
    border.color: win.tint(badge.ink, 0.28)
    Accessible.role: Accessible.StaticText
    Accessible.name: win.compatTitle(badge.compat.verdict)

    RowLayout {
        id: badgeRow
        anchors.centerIn: parent
        spacing: badge.compact ? badge.design.space1 : badge.design.space2
        Glyph {
            win: badge.win
            name: badge.compat.verdict === "blocked" ? "danger"
                : badge.compat.verdict === "warn" ? "warning" : "check"
            tint: badge.ink
            Layout.preferredWidth: badge.compact ? badge.win.fs(13) : badge.win.fs(16)
            Layout.preferredHeight: badge.compact ? badge.win.fs(13) : badge.win.fs(16)
        }
        Text {
            text: badge.win.compatTitle(badge.compat.verdict)
            color: badge.ink
            font.family: badge.win.uiFont
            font.pixelSize: badge.compact ? badge.win.typePx(11) : badge.win.typePx(13)
            font.weight: Font.DemiBold
        }
    }
}
