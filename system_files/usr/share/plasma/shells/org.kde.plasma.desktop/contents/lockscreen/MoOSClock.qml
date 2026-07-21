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

    ColumnLayout {
        id: column
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 0

            Text {
                id: hours
                // Qt.formatTime has NO (date, locale, string) overload: the extra
                // locale made it IGNORE "HH" and render the full long time —
                // "20:03:56 UTC+00:00" — at 7.4x, twice, across the lock screen.
                text: Qt.formatTime(timeSource.now, "HH")
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans"
                font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 7.4)
                font.weight: Font.Light
                renderType: Text.NativeRendering
            }
            Text {
                id: colon
                text: ":"
                color: Kirigami.Theme.highlightColor
                font.family: "IBM Plex Sans"
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
                font.family: "IBM Plex Sans"
                font.pointSize: hours.font.pointSize
                font.weight: Font.Light
                renderType: Text.NativeRendering
            }
        }

        // A short turquoise tick under the time — the one luminous accent.
        // It breathes: a slow width swell, in period with the brand above it,
        // so the lock screen's two living elements share one pulse.
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
            font.family: "IBM Plex Sans"
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
