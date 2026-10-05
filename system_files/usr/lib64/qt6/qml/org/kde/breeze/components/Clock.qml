/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2025 Thomas Duckworth <tduck@filotimoproject.org>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: Plasma's own session clock, wearing the MoOS face.
//
// This is the clock of BOTH doors. plasma-login-manager's greeter instantiates
// BreezeComponents.Clock from QML compiled into its binary, and the lock screen's
// own LockScreenUi.qml instantiates the same type — so this file on disk is the
// one clock the login screen and the lock screen share, and the power screen
// borrows it too. (The lock screen used to carry a second, different clock in a
// forked LockScreenUi.qml: larger, pinned to a corner, and able to slide under
// the password card on a small screen. One clock now, in one place.)
//
// The face is the family's: large ExtraLight HH:mm, because light at scale is
// what modern reads like; one static brand-colour colon and one horizon cut; one
// date in the session's locale and in the clock's own numerals. Session surfaces
// never print two languages or two numeral systems at once.
//
// Upstream's ENGINE is kept on purpose: PlasmaClock.Clock is the system clock
// source and handles timezone and resume correctly. Only the face changed, and
// the root stays a ColumnLayout so both greeters' `y:` maths and their
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
    // Both greeters centre this clock in the band above the user's face and
    // HIDE it when it does not fit (`visible: y > 0`). The face sits nine grid
    // units above the centre line, so that band is about half the scene less
    // 135 px; the session island starts a little above the face, which takes
    // another 32 px off what the clock may fill. The full clock is about
    // 160 px tall, so it fits whole from 685 logical pixels of height upwards
    // and scales below that. Under 560 the band holds the time and nothing
    // else: the date steps aside and the digits take the room — two-thirds
    // size in a 640x480 firmware mode, which is where AArch64 guests and
    // first-boot VMs commonly start. Scaling it is what keeps the idle greeter
    // from being bare wallpaper there. (The old divisor was 760, which shrank
    // the clock to 0.72 on the station's own 864-pixel-high desktop.)
    //
    // The height is the WINDOW's, not the screen's. They are the same on a
    // real lock or login screen, but kscreenlocker's testing window and the
    // power screen's windowed mode are smaller than the screen they open on,
    // and a clock sized for the screen slid its date under the island there.
    readonly property real sceneHeight: Window.height > 0 ? Window.height : Screen.height
    readonly property bool roomForDate: sceneHeight >= 560
    readonly property real responsiveScale: Math.min(
        1.0, Math.max(0.4, roomForDate ? (sceneHeight - 385) / 300
                                       : (sceneHeight - 346) / 200))

    function latinNumerals(s) {
        return String(s)
            .replace(/[٠۰]/g, "0").replace(/[١۱]/g, "1")
            .replace(/[٢۲]/g, "2").replace(/[٣۳]/g, "3")
            .replace(/[٤۴]/g, "4").replace(/[٥۵]/g, "5")
            .replace(/[٦۶]/g, "6").replace(/[٧۷]/g, "7")
            .replace(/[٨۸]/g, "8").replace(/[٩۹]/g, "9");
    }

    spacing: Math.max(Kirigami.Units.smallSpacing,
                      Math.round(Kirigami.Units.largeSpacing * 1.5 * responsiveScale))

    // Plex Arabic reserves room above and below every line for Arabic marks —
    // about as much again as the digits are tall. Left in, that leading made
    // the clock half as tall again as what it shows: the horizon cut hung a
    // finger's width under the time, and both greeters, which hide a clock
    // that does not fit, hid this one on small screens for the sake of blank
    // space. The time row gives back the leading its digits never use.
    FontMetrics {
        id: timeMetrics
        font: hours.font
    }
    TextMetrics {
        id: digitMetrics
        font: hours.font
        text: "0"
    }

    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: -Math.round(Math.max(
            0, timeMetrics.ascent - digitMetrics.tightBoundingRect.height) * 0.7)
        Layout.bottomMargin: -Math.round(timeMetrics.descent * 0.7)
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
                                       * 7.8 * root.responsiveScale)
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
        visible: root.roomForDate
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: Math.round(hours.implicitWidth * 0.6)
        Layout.preferredHeight: Math.round(Kirigami.Units.smallSpacing * 0.6)
        radius: height
        color: Kirigami.Theme.highlightColor
        opacity: 1 - design.surfaceRestingOpacity
    }

    PlasmaComponents3.Label {
        visible: root.roomForDate
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
        // Not NativeRendering: on a fractional scale it snaps glyphs to whole
        // device pixels and the date picks up a colour fringe under the clock.
        renderType: Text.QtRendering
    }

    PlasmaClock.Clock {
        id: timeSource
        trackSeconds: false
    }
}
