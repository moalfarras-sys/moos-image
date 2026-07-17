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
//   · the colon breathing in the brand colour — the one proof the clock is live
//     and not a picture;
//   · one turquoise tick that swells in period with the brand mark above it;
//   · the date bilingually, Arabic first, exactly as MoOS speaks everywhere else.
//
// Upstream's ENGINE is kept on purpose: PlasmaClock.Clock is the system clock
// source and handles timezone and resume correctly. Only the face changed, and
// the root stays a ColumnLayout so the compiled greeter's `y:` maths and its
// DropShadow keep working untouched.

import QtQuick
import QtQuick.Layouts

import org.kde.plasma.clock as PlasmaClock
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software

    // The breathing colon. Two seconds on, two off — slow enough to read as
    // alive rather than as a flashing error.
    property bool tick: true

    spacing: Kirigami.Units.largeSpacing

    RowLayout {
        Layout.alignment: Qt.AlignHCenter
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
            font.family: "IBM Plex Sans"
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 7.4)
            font.weight: Font.Light
            renderType: Text.NativeRendering // looks better than QtTextRendering at large size, while CurveRendering suffers from jagged diagonals with some fonts (QTBUG-146898)
        }
        PlasmaComponents3.Label {
            id: colon
            text: ":"
            textFormat: Text.PlainText
            style: root.softwareRendering ? Text.Outline : Text.Normal
            styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
            color: Kirigami.Theme.highlightColor
            font.family: "IBM Plex Sans"
            font.pointSize: hours.font.pointSize
            font.weight: Font.Light
            renderType: Text.NativeRendering
            opacity: root.tick ? 1.0 : 0.35
            Behavior on opacity {
                NumberAnimation {
                    duration: Kirigami.Units.longDuration
                    easing.type: Easing.InOutQuad
                }
            }
        }
        PlasmaComponents3.Label {
            id: minutes
            text: Qt.formatTime(timeSource.dateTime, "mm")
            textFormat: Text.PlainText
            style: root.softwareRendering ? Text.Outline : Text.Normal
            styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
            color: Kirigami.Theme.textColor
            font.family: "IBM Plex Sans"
            font.pointSize: hours.font.pointSize
            font.weight: Font.Light
            renderType: Text.NativeRendering
        }
    }

    // The one luminous accent, breathing in period with the brand above it.
    Rectangle {
        Layout.alignment: Qt.AlignHCenter
        Layout.preferredWidth: Math.round(hours.implicitWidth * 0.6)
        Layout.preferredHeight: Math.round(Kirigami.Units.smallSpacing * 0.6)
        radius: height
        color: Kirigami.Theme.highlightColor
        opacity: 0.9
        SequentialAnimation on scale {
            loops: Animation.Infinite
            running: root.visible
            NumberAnimation { to: 1.18; duration: 3000; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.0; duration: 3000; easing.type: Easing.InOutSine }
        }
    }

    PlasmaComponents3.Label {
        Layout.alignment: Qt.AlignHCenter
        text: Qt.formatDate(timeSource.dateTime, Qt.locale("ar"),
                            Qt.locale("ar").dateFormat(Locale.LongFormat))
        textFormat: Text.PlainText
        style: root.softwareRendering ? Text.Outline : Text.Normal
        styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
        color: Kirigami.Theme.textColor
        opacity: 0.92
        font.family: "IBM Plex Sans Arabic"
        font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.5)
        font.weight: Font.Normal
        horizontalAlignment: Text.AlignHCenter
        renderType: Text.NativeRendering
    }

    PlasmaComponents3.Label {
        Layout.alignment: Qt.AlignHCenter
        text: Qt.formatDate(timeSource.dateTime, Qt.locale("en"), "dddd, d MMMM yyyy")
        textFormat: Text.PlainText
        style: root.softwareRendering ? Text.Outline : Text.Normal
        styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
        color: Kirigami.Theme.textColor
        opacity: 0.62
        font.family: "IBM Plex Sans"
        font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.05)
        font.weight: Font.Normal
        horizontalAlignment: Text.AlignHCenter
        renderType: Text.NativeRendering
    }

    PlasmaClock.Clock {
        id: timeSource
        // The colon needs a second-resolution source to breathe; upstream only
        // tracked seconds when the locale's short format asked for them.
        trackSeconds: true
        onDateTimeChanged: {
            if (timeSource.dateTime.getSeconds() % 2 === 0) {
                root.tick = !root.tick;
            }
        }
    }
}
