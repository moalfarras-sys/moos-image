// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity
// SPDX-License-Identifier: LGPL-2.1-only OR LGPL-3.0-only OR LicenseRef-KDE-Accepted-LGPL

// MoOS: plasma-keyboard's popup (alternate characters, previews), wearing
// Meyar Glass. PLASMA 6.8.3 SEAM (plasma-keyboard): upstream's `theme` slot and
// its ShadowedRectangle shadow are kept; MoOS adds the MoOS corner (three round,
// the top-trailing one square) and a light line along the top edge.

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import QtQuick.VirtualKeyboard

import org.kde.kirigami as Kirigami

Kirigami.ShadowedRectangle {
    id: popup
    property BreezeConstants theme

    // Use stronger shadow for dark theme for contrast
    shadow.size: Kirigami.ColorUtils.brightnessForColor(Kirigami.Theme.backgroundColor) === Kirigami.ColorUtils.Dark ? 20 : 5
    shadow.color: Qt.rgba(0, 0, 0, 0.2)

    // The style assigns `theme` after this popup's own children exist; until
    // then nothing below may read through it.
    readonly property real roundRadius: theme ? theme.popupRadius : 0
    readonly property real squareRadius: theme ? theme.squareRadius : 0
    readonly property bool darkGround: theme ? theme.darkGround : true
    // The keyboard panel is not mirrored; the MoOS corner follows the language
    // being TYPED, so an Arabic layout's square corner is top-left.
    readonly property bool typingRightToLeft: Qt.locale(InputContext.locale).textDirection === Qt.RightToLeft

    color: theme.popupBackgroundColor
    radius: theme.popupRadius
    // The MoOS corner.
    corners.topLeftRadius: typingRightToLeft ? squareRadius : roundRadius
    corners.topRightRadius: typingRightToLeft ? roundRadius : squareRadius
    corners.bottomLeftRadius: roundRadius
    corners.bottomRightRadius: roundRadius
    border {
        width: 1
        color: theme.popupBorderColor
    }

    Rectangle {
        anchors.top: parent.top
        anchors.topMargin: 1
        x: popup.typingRightToLeft ? popup.squareRadius + 1 : popup.roundRadius * 0.7
        width: Math.max(0, parent.width - popup.roundRadius * 0.7 - popup.squareRadius - 1)
        height: 1
        color: Qt.rgba(1, 1, 1, popup.darkGround ? 0.10 : 0.85)
    }
}
