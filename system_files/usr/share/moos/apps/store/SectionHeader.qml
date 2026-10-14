pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — a section's head: its glyph, its title and one line about it, and on the trailing
// side "See all" and, for a row that scrolls sideways, its previous/next buttons. The arrows point
// the way the row moves in the person's reading direction.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
RowLayout {
    id: header
    required property var win
    readonly property var design: win.design
    property string title: ""
    property string subtitle: ""
    property string glyph: ""
    property bool showAll: false
    property bool showArrows: false
    property bool canPrevious: true
    property bool canNext: true
    signal seeAll()
    signal previous()
    signal next()

    spacing: design.space3

    Rectangle {
        visible: header.glyph !== ""
        Layout.preferredWidth: header.win.fs(36)
        Layout.preferredHeight: header.win.fs(36)
        Layout.alignment: Qt.AlignVCenter
        radius: header.design.radiusControl
        color: header.win.tint(header.win.accent, header.win.lightScheme ? 0.14 : 0.18)
        Glyph {
            win: header.win
            anchors.centerIn: parent
            width: header.win.fs(20)
            height: width
            name: header.glyph === "" ? "spark" : header.glyph
            tint: header.win.accent
        }
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            text: header.title
            color: header.win.txt
            font.family: header.win.uiFont
            font.pixelSize: header.win.typePx(20)
            font.weight: Font.Bold
            elide: Text.ElideRight
            Accessible.role: Accessible.Heading
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            visible: header.subtitle !== ""
            text: header.subtitle
            color: header.win.txt2
            font.family: header.win.uiFont
            font.pixelSize: header.win.typePx(13)
            elide: Text.ElideRight
        }
    }

    ActionButton {
        win: header.win
        visible: header.showAll
        label: header.win.local("عرض الكل", "See all")
        compact: true
        pill: true
        Accessible.name: header.win.local("عرض الكل: ", "See all: ") + header.title
        triggered: function() { header.seeAll() }
    }

    RowLayout {
        visible: header.showArrows
        spacing: header.design.space2
        CircleButton {
            win: header.win
            glyph: header.win.rtl ? "arrow" : "arrow-back"
            enabled: header.canPrevious
            accessibleName: header.win.local("السابق", "Previous")
            onActivated: header.previous()
        }
        CircleButton {
            win: header.win
            glyph: header.win.rtl ? "arrow-back" : "arrow"
            enabled: header.canNext
            accessibleName: header.win.local("التالي", "Next")
            onActivated: header.next()
        }
    }
}
