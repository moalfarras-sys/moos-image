// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS
// SPDX-License-Identifier: GPL-2.0-or-later

// One emoji the person can touch: in the Touch Bar's scrubber and in the emoji sheet's
// grid, where hundreds exist at once, so it is a glyph and a glass disc while pressed —
// nothing more. A tap picks it; holding it asks for its skin tones.
import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: cell

    property string emoji: ""
    property string accessibleName: emoji
    property string family: "Noto Color Emoji"
    property QtObject theme: null
    property bool hasTones: false

    signal picked(string emoji)
    signal held(Item cell, string emoji)

    Rectangle {
        anchors.centerIn: parent
        width: Math.min(cell.width, cell.height) * 0.92
        height: width
        radius: width / 2
        color: cell.theme ? cell.theme.normalKeyPressedBackgroundColor : Kirigami.Theme.highlightColor
        opacity: tap.pressed ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
    }

    Text {
        anchors.centerIn: parent
        text: cell.emoji
        font.family: cell.family
        font.pixelSize: Math.max(1, Math.round(Math.min(cell.width, cell.height) * 0.6))
        scale: tap.pressed ? 1.18 : 1
        Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutBack } }
    }

    // A dot under an emoji that comes in skin tones, the way the keys mark alternates.
    Rectangle {
        visible: cell.hasTones
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Math.round(cell.height * 0.06)
        width: Math.max(3, Math.round(cell.height * 0.06))
        height: width
        radius: width / 2
        color: cell.theme ? cell.theme.keySmallTextColor : Kirigami.Theme.disabledTextColor
        opacity: 0.6
    }

    TapHandler {
        id: tap
        gesturePolicy: TapHandler.ReleaseWithinBounds
        longPressThreshold: 0.45
        onTapped: cell.picked(cell.emoji)
        onLongPressed: cell.held(cell, cell.emoji)
    }

    Accessible.role: Accessible.Button
    Accessible.name: cell.accessibleName
    Accessible.onPressAction: cell.picked(cell.emoji)
}
