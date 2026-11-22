// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity
// SPDX-License-Identifier: LGPL-2.1-only OR LGPL-3.0-only OR LicenseRef-KDE-Accepted-LGPL

// MoOS: plasma-keyboard's key panel, wearing Meyar Glass.
//
// PLASMA 6.8.3 SEAM (plasma-keyboard). Upstream's contract is kept name for
// name — the default contentItem slot, `background`, `padding`, `radius`,
// `color` (which style.qml's states override, e.g. Caps Lock) and the sound and
// vibration feedback. What MoOS paints: a glass key with the MoOS corner (three
// round, the top-trailing one square), a light line along its top edge, a short
// press, and the Enter key in the selected accent; style.qml draws its icon and
// label in highlightedTextColor, the ink paired with that fill.

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.VirtualKeyboard
import QtQuick.VirtualKeyboard.Styles

import org.kde.plasma.keyboard
import org.kde.kirigami as Kirigami

KeyPanel {
    id: root

    default property alias contentItem: visualContainer.contentItem

    property alias background: visualContainer.background

    property real padding: BreezeConstants.keyBackgroundMargin

    property real radius: BreezeConstants.buttonRadius

    readonly property bool enterKey: control !== null && control.keyType === QtVirtualKeyboard.KeyType.EnterKey
    readonly property bool functionKey: control !== null && control.functionKey === true

    property color color: {
        if (control && control.pressed) {
            return BreezeConstants.normalKeyPressedBackgroundColor;
        } else if (enterKey) {
            return Kirigami.Theme.highlightColor;
        } else if (control && control.highlighted) {
            return BreezeConstants.highlightedKeyBackgroundColor;
        } else if (functionKey) {
            return BreezeConstants.highlightedKeyBackgroundColor;
        }
        return BreezeConstants.normalKeyBackgroundColor;
    }
    // A key filled with the accent (Enter, an engaged Caps Lock). The style
    // draws its glyph in highlightedTextColor, the ink KDE pairs with that fill.
    readonly property bool accented: Qt.colorEqual(root.color, Kirigami.Theme.highlightColor)
    // The keyboard panel is not mirrored; the MoOS corner follows the language
    // being TYPED instead, so an Arabic layout's square corner is top-left.
    readonly property bool typingRightToLeft: Qt.locale(InputContext.locale).textDirection === Qt.RightToLeft

    soundEffect: PlasmaKeyboardSettings.soundEnabled ? Qt.resolvedUrl('qrc:///sounds/keyboard_tick2_quiet.wav') : ''

    QQC2.Control {
        id: visualContainer
        anchors.fill: parent
        anchors.margins: root.padding

        background: Rectangle {
            id: keyFace
            color: root.color
            radius: root.radius
            // The MoOS corner.
            topLeftRadius: root.typingRightToLeft ? BreezeConstants.squareRadius : root.radius
            topRightRadius: root.typingRightToLeft ? root.radius : BreezeConstants.squareRadius
            border.width: 1
            border.color: Qt.rgba(BreezeConstants.glassInk.r, BreezeConstants.glassInk.g,
                                  BreezeConstants.glassInk.b, BreezeConstants.darkGround ? 0.10 : 0.12)
            scale: control && control.pressed ? 0.97 : 1
            Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
            Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }

            // The light along the top edge: glass, lit from above.
            Rectangle {
                anchors.top: parent.top
                anchors.topMargin: 1
                x: root.typingRightToLeft ? BreezeConstants.squareRadius + 1 : root.radius * 0.7
                width: Math.max(0, parent.width - root.radius * 0.7 - BreezeConstants.squareRadius - 1)
                height: 1
                color: Qt.rgba(1, 1, 1, root.accented ? 0.32 : (BreezeConstants.darkGround ? 0.10 : 0.85))
            }
        }
    }

    // Implement key vibration
    Connections {
        target: root.control
        function onPressedChanged() {
            if (root.control.pressed && PlasmaKeyboardSettings.vibrationEnabled) {
                Vibration.vibrate(PlasmaKeyboardSettings.vibrationMs);
            }
        }
    }
}
