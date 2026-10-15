pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — whether this computer is ready for one kind of app (Windows programs, Android apps):
// Ready, Needs a one-time setup, or Not available here, in words, with the existing setup at hand.
// The setup itself belongs to MoOS (moai-do, with its own confirmation); this row only opens it.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
RowLayout {
    id: readiness
    required property var win
    readonly property var design: win.design
    property string glyph: "system"
    property string title: ""
    property string line: ""
    property bool available: true
    property bool ready: false
    property bool known: true
    property string action: ""
    readonly property color tone: !readiness.available ? readiness.win.txt2
                                : readiness.ready ? readiness.win.positiveInk : readiness.win.warningInk

    spacing: readiness.design.space4

    Rectangle {
        Layout.preferredWidth: readiness.win.fs(40)
        Layout.preferredHeight: readiness.win.fs(40)
        Layout.alignment: Qt.AlignTop
        radius: readiness.design.radiusControl
        color: readiness.win.tint(readiness.win.txt, readiness.win.lightScheme ? 0.06 : 0.08)
        Glyph {
            win: readiness.win
            anchors.centerIn: parent
            width: readiness.win.fs(20)
            height: width
            name: readiness.glyph
            tint: readiness.win.txt
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        RowLayout {
            Layout.fillWidth: true
            spacing: readiness.design.space2
            Text {
                text: readiness.title
                color: readiness.win.txt
                font.family: readiness.win.uiFont
                font.pixelSize: readiness.win.typePx(15)
                font.weight: Font.DemiBold
            }
            Rectangle {
                visible: readiness.known
                Layout.preferredHeight: readiness.win.fs(22)
                Layout.preferredWidth: stateLabel.implicitWidth + readiness.design.space3 * 2
                radius: height / 2
                color: readiness.win.tint(readiness.tone, readiness.win.lightScheme ? 0.12 : 0.16)
                Text {
                    id: stateLabel
                    anchors.centerIn: parent
                    text: !readiness.available ? readiness.win.local("غير متاح هنا", "Not available here")
                        : readiness.ready ? readiness.win.local("جاهز", "Ready")
                        : readiness.win.local("يحتاج إعدادًا", "Needs setup")
                    color: readiness.tone
                    font.family: readiness.win.uiFont
                    font.pixelSize: readiness.win.typePx(11)
                    font.weight: Font.DemiBold
                }
            }
            Item { Layout.fillWidth: true }
        }
        Text {
            Layout.fillWidth: true
            text: readiness.line
            color: readiness.win.txt2
            font.family: readiness.win.uiFont
            font.pixelSize: readiness.win.typePx(13)
            wrapMode: Text.WordWrap
        }
    }
    ActionButton {
        win: readiness.win
        visible: readiness.action !== ""
        pill: true
        label: readiness.win.local("إعداد…", "Set up…")
        glyphName: "settings"
        Accessible.name: readiness.win.local("إعداد ", "Set up ") + readiness.title
        triggered: function() { readiness.win.openSystemRoute(readiness.action) }
    }
}
