pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — one filter chip (a category, a kind of app, an order, a page of My apps): a pill with
// an optional glyph, its words and an optional count. The chosen one is filled with the accent and
// says so to a screen reader; the others are quiet glass.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: chip
    required property var win
    readonly property var design: win.design
    property string label: ""
    property string glyph: ""
    property int count: -1
    property bool checked: false
    signal activated()

    implicitHeight: win.fs(36)
    implicitWidth: chipRow.implicitWidth + design.space4 * 2
    radius: height / 2
    color: chip.checked ? win.accent
         : chipHover.hovered ? win.tint(win.txt, win.lightScheme ? 0.08 : 0.10)
         : win.tint(win.cardColor, win.lightScheme ? 0.82 : 0.70)
    border.width: chip.checked ? 0 : 1
    border.color: chipHover.hovered ? win.tint(win.accent, 0.5) : win.cardBorder
    activeFocusOnTab: true
    Accessible.role: Accessible.RadioButton
    Accessible.name: chip.count >= 0 ? chip.label + ", " + chip.count : chip.label
    Accessible.checkable: true
    Accessible.checked: chip.checked
    Accessible.onPressAction: chip.activated()
    Keys.onReturnPressed: chip.activated()
    Keys.onEnterPressed: chip.activated()
    Keys.onSpacePressed: chip.activated()
    FocusRing { win: chip.win }
    HoverHandler { id: chipHover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: chip.activated() }
    Behavior on color { ColorAnimation { duration: chip.win.motionEnabled ? chip.design.motionFast : 0 } }

    RowLayout {
        id: chipRow
        anchors.centerIn: parent
        spacing: chip.design.space2
        Glyph {
            win: chip.win
            visible: chip.glyph !== ""
            name: chip.glyph === "" ? "spark" : chip.glyph
            tint: chip.checked ? chip.win.accentText : chip.win.txt2
            Layout.preferredWidth: chip.win.fs(16)
            Layout.preferredHeight: chip.win.fs(16)
        }
        Text {
            text: chip.label
            color: chip.checked ? chip.win.accentText : chip.win.txt
            font.family: chip.win.uiFont
            font.pixelSize: chip.win.typePx(13)
            font.weight: chip.checked ? Font.DemiBold : Font.Medium
        }
        Text {
            visible: chip.count >= 0
            text: chip.win.countText(chip.count)
            color: chip.checked ? chip.win.accentText : chip.win.txt2
            opacity: chip.checked ? 0.8 : 1
            font.family: chip.win.uiFont
            font.pixelSize: chip.win.typePx(11)
        }
    }
}
