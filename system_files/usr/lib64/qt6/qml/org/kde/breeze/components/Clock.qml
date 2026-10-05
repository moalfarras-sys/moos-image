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
// borrows it too.
//
// It has two poses, and it MOVES between them.
//   · Nobody at the keyboard: the screen is a cover, and the clock is its
//     headline — up to half as large again, standing low in its band.
//   · Someone arrives (a key, the pointer): the clock draws back to its working
//     size and rises, and the session island comes up underneath it.
// Both greeters keep a `uiVisible` on the item they parent the clock to, which is
// how it knows; anywhere else (the power screen) it simply keeps the working pose.
// The move is one GPU transform on type drawn as curves, so it stays sharp at
// every step and costs no re-layout. When the minute changes, the digits that
// changed roll over. Nothing here loops, and with animations off it does not
// move at all.
//
// The face is the family's: ExtraLight HH:mm, one brand-colour colon and one
// horizon cut; one date in the session's locale and in the clock's own numerals.
//
// Upstream's ENGINE is kept on purpose: PlasmaClock.Clock is the system clock
// source and handles timezone and resume correctly. Both greeters place this
// item by its height (`y: band / 2 - height / 2`) and hide it when it does not
// fit, so its height is the band it is given, less a margin, in both poses.

import QtQuick
import QtQuick.Layouts
import QtQuick.Window

import org.kde.plasma.clock as PlasmaClock
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: root

    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var sessionLocale: Qt.locale()
    readonly property var design: MoUI.Tokens

    // The WINDOW's size, not the screen's. They are the same on a real lock or
    // login screen, but kscreenlocker's testing window and the power screen's
    // windowed mode are smaller than the screen they open on.
    readonly property real sceneWidth: Window.width > 0 ? Window.width : Screen.width
    readonly property real sceneHeight: Window.height > 0 ? Window.height : Screen.height
    // One number sizes the whole session family (see Tokens.sessionScale).
    readonly property real responsiveScale: design.sessionScale(sceneWidth, sceneHeight)
    readonly property real unit: Kirigami.Units.gridUnit * responsiveScale

    // Somebody is at the keyboard. Both greeters parent the clock to the item
    // that owns `uiVisible`; a caller that has no such thing gets the working pose.
    readonly property bool sessionActive: (parent && parent.uiVisible !== undefined)
        ? parent.uiVisible : true
    // The power screen places the clock itself and wants no cover pose.
    property bool heroWhenIdle: true

    // The band both greeters centre the clock in: from the top of the screen to
    // the top of the user list, which stands nine (scaled) grid units above the
    // centre line of a stack one and a half grid units lower than the screen's.
    readonly property real band: sceneHeight / 2 + Kirigami.Units.gridUnit * 1.5 - unit * 9
    readonly property real coverScale: !heroWhenIdle ? 1.0
        : Math.max(1.0, Math.min(1.5, (band - unit * 3.5) / Math.max(1, face.implicitHeight)))
    // 0 = cover pose, 1 = working pose.
    property real presence: sessionActive ? 1 : 0
    Behavior on presence {
        enabled: root.motionEnabled
        NumberAnimation {
            duration: root.design.duration(root.motionEnabled, root.design.motionPortal)
            easing.type: root.design.easeEmphasis
        }
    }

    function latinNumerals(s) {
        return String(s)
            .replace(/[٠۰]/g, "0").replace(/[١۱]/g, "1")
            .replace(/[٢۲]/g, "2").replace(/[٣۳]/g, "3")
            .replace(/[٤۴]/g, "4").replace(/[٥۵]/g, "5")
            .replace(/[٦۶]/g, "6").replace(/[٧۷]/g, "7")
            .replace(/[٨۸]/g, "8").replace(/[٩۹]/g, "9");
    }

    implicitWidth: Math.ceil(face.implicitWidth * coverScale)
    // The whole band, less a grid unit: both poses happen inside it, so the
    // caller's `visible: y > 0` holds and its drop shadow covers either one.
    implicitHeight: heroWhenIdle ? Math.max(face.implicitHeight, Math.floor(band - Kirigami.Units.gridUnit))
                                 : face.implicitHeight

    ColumnLayout {
        id: face

        // Cover: large, standing on the band's floor. Working: its own size,
        // a little above the band's middle, clear of the island below.
        readonly property real coverY: root.height - (implicitHeight * root.coverScale) / 2 - root.unit * 0.5
        readonly property real workingY: root.height / 2 - root.unit * 0.6
        x: Math.round((root.width - width) / 2)
        y: root.heroWhenIdle
            ? Math.round(coverY + (workingY - coverY) * root.presence - height / 2)
            : 0
        scale: root.coverScale + (1.0 - root.coverScale) * root.presence
        transformOrigin: Item.Center

        spacing: Math.max(Kirigami.Units.smallSpacing,
                          Math.round(Kirigami.Units.largeSpacing * 1.5 * root.responsiveScale))

        // Plex Arabic reserves room above and below every line for Arabic marks —
        // about as much again as the digits are tall. Left in, that leading made
        // the clock half as tall again as what it shows and hung the horizon cut
        // a finger's width under the time. The time row gives back the leading
        // its digits never use.
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
                // time — "20:03:56 UTC+00:00" — across the screen. That shipped
                // once on the lock screen; do not reintroduce the locale argument.
                text: Qt.formatTime(timeSource.dateTime, "HH")
                textFormat: Text.PlainText
                style: root.softwareRendering ? Text.Outline : Text.Normal
                styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
                color: Kirigami.Theme.textColor
                font.family: root.design.interfaceFamily
                font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize
                                           * 7.8 * root.responsiveScale)
                font.weight: Font.ExtraLight
                renderType: Text.CurveRendering
                transform: Translate { id: hoursLift }
                // The digits that changed roll over: the old value lifts out and
                // the new one rises in. A Behavior on `text` is the one place QML
                // lets an animation hold the old value while the binding already
                // has the new one.
                Behavior on text {
                    enabled: root.motionEnabled && timeSource.settled
                    SequentialAnimation {
                        ParallelAnimation {
                            NumberAnimation {
                                target: hours; property: "opacity"; to: 0
                                duration: root.design.duration(root.motionEnabled, root.design.motionPress)
                                easing.type: Easing.InQuad
                            }
                            NumberAnimation {
                                target: hoursLift; property: "y"; to: -root.unit * 0.9
                                duration: root.design.duration(root.motionEnabled, root.design.motionPress)
                                easing.type: Easing.InQuad
                            }
                        }
                        PropertyAction {}
                        PropertyAction { target: hoursLift; property: "y"; value: root.unit * 0.9 }
                        ParallelAnimation {
                            NumberAnimation {
                                target: hours; property: "opacity"; to: 1
                                duration: root.design.duration(root.motionEnabled, root.design.motionPage)
                                easing.type: root.design.easeStandard
                            }
                            NumberAnimation {
                                target: hoursLift; property: "y"; to: 0
                                duration: root.design.duration(root.motionEnabled, root.design.motionPage)
                                easing.type: root.design.easeEmphasis
                            }
                        }
                    }
                }
            }
            PlasmaComponents3.Label {
                id: colon
                text: ":"
                textFormat: Text.PlainText
                style: root.softwareRendering ? Text.Outline : Text.Normal
                styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
                color: Kirigami.Theme.highlightColor
                font.family: root.design.interfaceFamily
                font.pointSize: hours.font.pointSize
                font.weight: Font.ExtraLight
                renderType: Text.CurveRendering
                opacity: 1 - root.design.surfaceRestingOpacity
            }
            PlasmaComponents3.Label {
                id: minutes
                text: Qt.formatTime(timeSource.dateTime, "mm")
                textFormat: Text.PlainText
                style: root.softwareRendering ? Text.Outline : Text.Normal
                styleColor: root.softwareRendering ? Kirigami.Theme.backgroundColor : "transparent"
                color: Kirigami.Theme.textColor
                font.family: root.design.interfaceFamily
                font.pointSize: hours.font.pointSize
                font.weight: Font.ExtraLight
                renderType: Text.CurveRendering
                transform: Translate { id: minutesLift }
                Behavior on text {
                    enabled: root.motionEnabled && timeSource.settled
                    SequentialAnimation {
                        ParallelAnimation {
                            NumberAnimation {
                                target: minutes; property: "opacity"; to: 0
                                duration: root.design.duration(root.motionEnabled, root.design.motionPress)
                                easing.type: Easing.InQuad
                            }
                            NumberAnimation {
                                target: minutesLift; property: "y"; to: -root.unit * 0.9
                                duration: root.design.duration(root.motionEnabled, root.design.motionPress)
                                easing.type: Easing.InQuad
                            }
                        }
                        PropertyAction {}
                        PropertyAction { target: minutesLift; property: "y"; value: root.unit * 0.9 }
                        ParallelAnimation {
                            NumberAnimation {
                                target: minutes; property: "opacity"; to: 1
                                duration: root.design.duration(root.motionEnabled, root.design.motionPage)
                                easing.type: root.design.easeStandard
                            }
                            NumberAnimation {
                                target: minutesLift; property: "y"; to: 0
                                duration: root.design.duration(root.motionEnabled, root.design.motionPage)
                                easing.type: root.design.easeEmphasis
                            }
                        }
                    }
                }
            }
        }

        // The one luminous horizon cut, lit from its middle.
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Math.round(hours.implicitWidth * 0.7)
            Layout.preferredHeight: Math.max(2, Math.round(Kirigami.Units.smallSpacing * 0.6
                                                           * root.responsiveScale))
            radius: height
            opacity: 1 - root.design.surfaceRestingOpacity
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: Qt.alpha(Kirigami.Theme.highlightColor, 0.0) }
                GradientStop { position: 0.5; color: Kirigami.Theme.highlightColor }
                GradientStop { position: 1.0; color: Qt.alpha(Kirigami.Theme.highlightColor, 0.0) }
            }
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
            opacity: 1 - root.design.surfaceRestingOpacity
            font.family: root.design.interfaceFamily
            font.pointSize: Math.max(8, Math.round(Kirigami.Theme.defaultFont.pointSize * 1.5
                                                   * root.responsiveScale))
            font.weight: Font.Normal
            horizontalAlignment: Text.AlignHCenter
            // Not NativeRendering: it snaps glyphs to whole device pixels, which
            // fringes on a fractional scale and smears under the cover transform.
            renderType: Text.QtRendering
        }
    }

    PlasmaClock.Clock {
        id: timeSource
        trackSeconds: false
        // The first value is not a change of minute; nothing rolls until it is in.
        property bool settled: false
        Component.onCompleted: Qt.callLater(() => { timeSource.settled = true; })
    }
}
