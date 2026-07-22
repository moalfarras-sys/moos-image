/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    The MoOS UI2 lock-screen clock. A drop-in replacement for org.kde.breeze
    components' Clock: same minimal contract (an Item with `visible`, a `shadow`
    alias, horizontalCenter/y set by LockScreenUi) so the WallpaperFader keeps
    driving it. The look is original MoOS — a large light-weight time, a bilingual
    Arabic/English date, and one restrained turquoise tick, drawn from the active
    colour scheme so it themes correctly on both Graphite and Tidal.
*/
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: clock

    // LockScreenUi points a DropShadow at this via `property Item shadow`.
    property Item shadow

    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight

    // A quiet minute pulse on the colon — motion that reads even in a still frame.
    property bool tick: true

    // Floating iOS 27 Glass Capsule Backdrop
    Rectangle {
        id: glassContainer
        anchors.fill: column
        anchors.margins: -Kirigami.Units.gridUnit * 1.6
        radius: Kirigami.Units.gridUnit * 2.1
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.36) }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.22) }
        }
        border.width: 1
        border.color: Qt.rgba(Kirigami.Theme.highlightColor.r, Kirigami.Theme.highlightColor.g, Kirigami.Theme.highlightColor.b, 0.28)

        // Top specular crest light
        Rectangle {
            anchors { top: parent.top; left: parent.left; right: parent.right; margins: 1.5 }
            height: 1.5
            radius: glassContainer.radius
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.30)
        }
    }

    ColumnLayout {
        id: column
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            // Time is always LTR (HH:mm), never mm:HH. LayoutMirroring (inherited
            // from the RTL lock screen) overrides layoutDirection, so it must be
            // switched off here or the hour and minute groups swap sides.
            LayoutMirroring.enabled: false
            layoutDirection: Qt.LeftToRight
            spacing: 0

            Text {
                id: hours
                text: Qt.formatTime(timeSource.now, "HH")
                color: Kirigami.Theme.textColor
                font.family: "Inter"
                font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 7.4)
                font.weight: Font.Light
                renderType: Text.NativeRendering
            }
            Text {
                id: colon
                text: ":"
                color: Kirigami.Theme.highlightColor
                font.family: "Inter"
                font.pointSize: hours.font.pointSize
                font.weight: Font.Light
                renderType: Text.NativeRendering
                opacity: clock.tick ? 1.0 : 0.35
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutQuad } }
            }
            Text {
                id: minutes
                text: Qt.formatTime(timeSource.now, "mm")
                color: Kirigami.Theme.textColor
                font.family: "Inter"
                font.pointSize: hours.font.pointSize
                font.weight: Font.Light
                renderType: Text.NativeRendering
            }
        }

        // A short turquoise tick under the time — the one luminous accent.
        Rectangle {
            id: accentTick
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Math.round(hours.implicitWidth * 0.6)
            Layout.preferredHeight: Math.round(Kirigami.Units.smallSpacing * 0.6)
            radius: height
            color: Kirigami.Theme.highlightColor
            opacity: 0.9
            SequentialAnimation on scale {
                loops: Animation.Infinite
                running: clock.visible
                NumberAnimation { to: 1.18; duration: 3000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 3000; easing.type: Easing.InOutSine }
            }
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: Kirigami.Units.gridUnit * 30
            elide: Text.ElideRight
            text: Qt.locale("ar").toString(timeSource.now, Qt.locale("ar").dateFormat(Locale.LongFormat))
            color: Kirigami.Theme.textColor
            opacity: 0.92
            font.family: "IBM Plex Sans Arabic"
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.5)
            font.weight: Font.Normal
            horizontalAlignment: Text.AlignHCenter
            renderType: Text.NativeRendering
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: Kirigami.Units.gridUnit * 30
            elide: Text.ElideRight
            text: Qt.locale("en").toString(timeSource.now, "dddd, d MMMM yyyy")
            color: Kirigami.Theme.textColor
            opacity: 0.62
            font.family: "Inter"
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.05)
            font.weight: Font.Normal
            horizontalAlignment: Text.AlignHCenter
            renderType: Text.NativeRendering
        }
    }

    QtObject {
        id: timeSource
        property date now: new Date()
    }

    Timer {
        interval: 1000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: {
            const d = new Date();
            if (d.getSeconds() % 2 === 0) {
                clock.tick = !clock.tick;
            }
            timeSource.now = d;
        }
    }
}
