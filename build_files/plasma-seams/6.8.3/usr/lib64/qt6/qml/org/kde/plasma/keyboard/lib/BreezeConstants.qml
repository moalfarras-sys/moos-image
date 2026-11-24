// SPDX-FileCopyrightText: 2025 Devin Lin <devin@kde.org>
// SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity
// SPDX-License-Identifier: LGPL-2.1-only OR LGPL-3.0-only OR LicenseRef-KDE-Accepted-LGPL

// MoOS: plasma-keyboard's own style constants, wearing Meyar Glass.
//
// PLASMA 6.8.3 SEAM (plasma-keyboard). Every property name, type and the
// singleton contract are upstream's: style.qml and the key panels read them by
// name. What MoOS owns is the values — the keyboard follows the selected MoOS
// look (Kirigami's Window set, the same pair the session island wears), types
// in the interface family (Meyar), and its keys carry the MoOS corner: three
// round, the top-trailing one square.

import QtQuick
import org.moos.keyboard as MoOSKeyboard

import org.kde.kirigami as Kirigami

pragma Singleton

QtObject {
    // Filled in by the style
    property real scaleHint

    readonly property string fontFamily: Kirigami.Theme.defaultFont.family
    // A little more air between keys than Breeze: glass keys read as separate
    // pieces, not as one slab.
    readonly property real keyBackgroundMargin: Math.round(9 * scaleHint)
    readonly property real keyContentMargin: Math.round(40 * scaleHint)
    readonly property real keyIconScale: scaleHint * 0.8

    // ── Meyar Glass roles ───────────────────────────────────────────────────
    readonly property color glassGround: Kirigami.Theme.backgroundColor
    readonly property color glassInk: Kirigami.Theme.textColor
    readonly property bool darkGround: Kirigami.ColorUtils.brightnessForColor(glassGround)
                                       === Kirigami.ColorUtils.Dark
    // Keys stand forward of the panel: lighter than it on a dark look, nearly
    // white on a light one. Function keys (shift, delete, language, enter,
    // symbols, hide) are a step denser, so the letters read as the field.
    readonly property color letterKey: darkGround
        ? Kirigami.ColorUtils.tintWithAlpha(glassGround, glassInk, 0.16)
        : Kirigami.ColorUtils.tintWithAlpha(glassGround, "#ffffff", 0.72)
    readonly property color functionKey: Kirigami.ColorUtils.tintWithAlpha(
        glassGround, Kirigami.Theme.highlightColor, darkGround ? 0.14 : 0.13)

    property color primaryColor: Kirigami.Theme.backgroundColor
    property color primaryLightColor: Qt.lighter(primaryColor, 1.3)
    property color primaryDarkColor: Qt.darker(primaryColor, 1.3)
    property color textOnPrimaryColor: Kirigami.Theme.textColor
    property color secondaryColor: Kirigami.Theme.backgroundColor
    property color secondaryLightColor: Qt.lighter(secondaryColor, 1.3)
    property color secondaryDarkColor: Qt.darker(secondaryColor, 1.3)
    property color textOnSecondaryColor: Kirigami.Theme.textColor

    readonly property color panelGround: darkGround
        ? Kirigami.ColorUtils.tintWithAlpha(glassGround, "#000000", 0.18)
        : Kirigami.ColorUtils.tintWithAlpha(glassGround, glassInk, 0.04)
    property color keyboardBackgroundColor: Qt.alpha(panelGround, MoOSKeyboard.PanelState.surfaceOpacity / 100)
    property color normalKeyBackgroundColor: letterKey
    property color normalKeyPressedBackgroundColor: Kirigami.ColorUtils.tintWithAlpha(letterKey,
        Kirigami.Theme.highlightColor, 0.42)
    property color highlightedKeyBackgroundColor: functionKey
    property color capsLockKeyAccentColor: Kirigami.Theme.highlightColor
    property color modeKeyAccentColor: Kirigami.Theme.highlightColor
    property color keyTextColor: textOnPrimaryColor
    property color keySmallTextColor: Kirigami.ColorUtils.tintWithAlpha(letterKey, glassInk, 0.82)
    property color popupBackgroundColor: darkGround
        ? Kirigami.ColorUtils.tintWithAlpha(glassGround, glassInk, 0.09)
        : Kirigami.ColorUtils.tintWithAlpha(glassGround, "#ffffff", 0.82)
    property color popupBorderColor: Kirigami.ColorUtils.tintWithAlpha(popupBackgroundColor, glassInk, 0.16)
    property color popupTextColor: textOnPrimaryColor
    property color popupTextSelectedColor: Kirigami.Theme.highlightedTextColor
    property color popupHighlightBorderColor: Kirigami.Theme.highlightColor
    property color popupHighlightColor: Kirigami.Theme.highlightColor
    property color selectionListTextColor: textOnPrimaryColor
    property color selectionListSeparatorColor: Kirigami.ColorUtils.tintWithAlpha(keyboardBackgroundColor, glassInk, 0.14)
    property color selectionListBackgroundColor: keyboardBackgroundColor
    property color navigationHighlightColor: Qt.rgba(navigationHighlightBorderColor.r, navigationHighlightBorderColor.g, navigationHighlightBorderColor.b, 0.3)
    property color navigationHighlightBorderColor: Kirigami.Theme.highlightColor

    // The MoOS corner, in design units of the keyboard (scaleHint follows it).
    readonly property real buttonRadius: Math.round(22 * scaleHint)
    readonly property real squareRadius: Math.max(1, Math.round(4 * scaleHint))
    readonly property real popupRadius: Math.round(26 * scaleHint)
}
