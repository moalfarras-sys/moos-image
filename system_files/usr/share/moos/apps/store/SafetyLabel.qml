pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — how far an app reaches, in one word and one plain sentence: Sandboxed, Asks for more,
// or Full access. App Drop apps, Windows programs and developer tools run as the person; they are
// labelled Full access, never dressed up.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
RowLayout {
    id: safety
    required property var win
    readonly property var design: win.design
    property var app: null
    readonly property string level: win.safetyLevel(safety.app)
    readonly property color tone: safety.level === "sandboxed" ? win.positiveInk
                                : safety.level === "page" ? win.accent : win.warningInk

    spacing: design.space3
    Accessible.role: Accessible.StaticText
    Accessible.name: win.safetyTitle(safety.app) + ". " + win.safetyLine(safety.app)

    Rectangle {
        Layout.preferredWidth: safety.win.fs(44)
        Layout.preferredHeight: safety.win.fs(44)
        Layout.alignment: Qt.AlignTop
        radius: width / 2
        color: safety.win.tint(safety.tone, safety.win.lightScheme ? 0.14 : 0.18)
        Glyph {
            win: safety.win
            anchors.centerIn: parent
            width: safety.win.fs(22)
            height: width
            name: safety.level === "sandboxed" ? "shield"
                : safety.level === "more" ? "lock"
                : safety.level === "page" ? "globe" : "warning"
            tint: safety.tone
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: safety.design.space1
        Text {
            Layout.fillWidth: true
            text: safety.win.safetyTitle(safety.app)
            color: safety.win.txt
            font.family: safety.win.uiFont
            font.pixelSize: safety.win.typePx(15)
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
        }
        Text {
            Layout.fillWidth: true
            text: safety.win.safetyLine(safety.app)
            color: safety.win.txt2
            font.family: safety.win.uiFont
            font.pixelSize: safety.win.typePx(13)
            wrapMode: Text.WordWrap
        }
    }
}
