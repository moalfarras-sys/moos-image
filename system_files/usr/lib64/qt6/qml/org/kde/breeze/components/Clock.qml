/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2025 Thomas Duckworth <tduck@filotimoproject.org>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own greeter clock, wearing the MoOS face.
//
// This clock is what the LOGIN screen draws — plasma-login-manager's greeter
// instantiates BreezeComponents.Clock, and its own QML is compiled into the
// binary, so this file on disk is the only way to reach it.
//
// It used to be HIDDEN. MoOS shipped `ShowClock=false` in
// plasmalogin.conf.d/10-moos-ui2.conf because the stock Breeze face — DemiBold,
// -3 letter spacing, one long English date — could not be re-skinned and read as
// foreign one second before MoOS's own lock clock appeared. Hiding it was a
// workaround, and it cost the login screen its clock. Now the face IS MoOS, so
// the clock is switched back ON: nothing is hidden, nothing is covered, the
// surface simply belongs to MoOS.
//
// The face is the one MoOS already uses on the lock screen (MoOSClock.qml) and
// on the desktop Hero Clock — the same family, the same weights, so the login
// screen, the lock screen and the desktop read as one system:
//   · large Light-weight HH:mm, because Light at scale is what modern reads like;
//   · one static brand-colour colon and one horizon cut;
//   · one date in the active locale. Session surfaces never print two languages
//     at once.
//
// Upstream's ENGINE is kept on purpose: PlasmaClock.Clock is the system clock
// source and handles timezone and resume correctly. Only the face changed, and
// the root stays a ColumnLayout so the compiled greeter's `y:` maths and its
// DropShadow keep working untouched.

import QtQuick
import QtQuick.Layouts
import QtQuick.Window

import org.kde.plasma.clock as PlasmaClock
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

ColumnLayout {
    id: root

    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property var sessionLocale: Qt.locale()
    readonly property var design: MoUI.Tokens
    // AArch64 firmware and first-boot VMs commonly start at 640x480 before the
    // desktop applies its preferred mode. Plasma places this clock only when its
    // implicit height fits above the user card; a fixed desktop-sized face is
    // therefore hidden at boot and turns the idle greeter into bare wallpaper.
    // Scale the same face down in logical pixels, then grow smoothly to its full
    // editorial size. This also keeps large host scale factors honest.
    readonly property real responsiveScale: Math.min(
        1.0, Math.max(0.28, (Screen.height - 320) / 760))

    function latinNumerals(s) {
        return String(s)
            .replace(/[٠۰]/g, "0").replace(/[١۱]/g, "1")
            .replace(/[٢۲]/g, "2").replace(/[٣۳]/g, "3")
            .replace(/[٤۴]/g, "4").replace(/[٥۵]/g, "5")
            .replace(/[٦۶]/g, "6").replace(/[٧۷]/g, "7")
            .replace(/[٨۸]/g, "8").replace(/[٩۹]/g, "9");
    }

    spacing: Math.max(Kirigami.Units.smallSpacing,
                      Math.round(Kirigami.Units.largeSpacing * responsiveScale))

    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        // Time is semantic LTR even in an Arabic session. Without this explicit
        // island, LayoutMirroring reverses the three children and 11:26 is drawn
        // as 26:11 on the real plasma-login greeter.
        LayoutMirroring.enabled: false
        layoutDirection: Qt.LeftToRight
        spacing: 0

        PlasmaComponents3.Label {
            id: hours
            // Qt.formatTime takes (date, format). Handing it a locale AND a
            // format string makes it ignore the format and print the full long
            // time — "20:03:56 UTC+00:00" — at 7.4x across the screen. That
            // shipped once on the lock screen (fixed in 55fef8b); do not
            // reintroduce the locale argument here.
            text: Qt.formatTime(timeSource.dateTime, "HH")
            textFormat: Text.PlainText
            style: root.softwareRendering ? Text.Outline : Text.Normal
            styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
            color: Kirigami.Theme.textColor
            font.family: design.interfaceFamily
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize
                                       * 7.4 * root.responsiveScale)
            font.weight: Font.ExtraLight
            renderType: Text.CurveRendering
        }
        PlasmaComponents3.Label {
            id: colon
            text: ":"
            textFormat: Text.PlainText
            style: root.softwareRendering ? Text.Outline : Text.Normal
            styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
            color: Kirigami.Theme.highlightColor
            font.family: design.interfaceFamily
            font.pointSize: hours.font.pointSize
            font.weight: Font.ExtraLight
            renderType: Text.CurveRendering
            opacity: 1 - design.surfaceRestingOpacity
        }
        PlasmaComponents3.Label {
            id: minutes
            text: Qt.formatTime(timeSource.dateTime, "mm")
            textFormat: Text.PlainText
            style: root.softwareRendering ? Text.Outline : Text.Normal
            styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
            color: Kirigami.Theme.textColor
            font.family: design.interfaceFamily
            font.pointSize: hours.font.pointSize
            font.weight: Font.ExtraLight
            renderType: Text.CurveRendering
        }
    }

    // The one luminous horizon cut. It is static by design.
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: Math.round(hours.implicitWidth * 0.6)
        Layout.preferredHeight: Math.round(Kirigami.Units.smallSpacing * 0.6)
        radius: height
        color: Kirigami.Theme.highlightColor
        opacity: 1 - design.surfaceRestingOpacity
    }

    PlasmaComponents3.Label {
        Layout.alignment: Qt.AlignHCenter
        text: root.latinNumerals(
            root.sessionLocale.toString(
                timeSource.dateTime,
                root.sessionLocale.dateFormat(Locale.LongFormat)))
        textFormat: Text.PlainText
        style: root.softwareRendering ? Text.Outline : Text.Normal
        styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
        color: Kirigami.Theme.textColor
        opacity: 1 - design.surfaceRestingOpacity
        font.family: design.interfaceFamily
        font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.5
                                   * Math.max(0.75, root.responsiveScale))
        font.weight: Font.Normal
        horizontalAlignment: Text.AlignHCenter
        renderType: Text.NativeRendering
    }

    PlasmaClock.Clock {
        id: timeSource
        trackSeconds: false
    }
}
