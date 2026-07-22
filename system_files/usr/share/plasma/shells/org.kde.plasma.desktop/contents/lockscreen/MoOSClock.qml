/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 lock clock — editorial. A drop-in for org.kde.breeze components'
    Clock (same Item + `shadow` alias contract). Deliberately NOT a widget: a
    single oversized, ultra-thin Inter time set in generous space, a hairline
    accent, and a quiet bilingual date. No capsule, no chrome. Premium by
    restraint, and fully theme-driven so it reads on any palette or wallpaper.
*/
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: clock

    property Item shadow
    implicitWidth: column.implicitWidth
    implicitHeight: column.implicitHeight

    property bool tick: true

    ColumnLayout {
        id: column
        spacing: 0

        // ── The oversized, ultra-thin time. Always LTR (HH:mm) ──
        RowLayout {
            LayoutMirroring.enabled: false
            layoutDirection: Qt.LeftToRight
            spacing: 0

            Text {
                id: hours
                text: Qt.formatTime(timeSource.now, "HH")
                color: Kirigami.Theme.textColor
                font.family: "Inter"
                font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 11)
                font.weight: Font.Thin
                font.letterSpacing: -2
                renderType: Text.NativeRendering
            }
            Text {
                id: colon
                text: ":"
                color: Kirigami.Theme.highlightColor
                font.family: "Inter"
                font.pointSize: hours.font.pointSize
                font.weight: Font.Thin
                renderType: Text.NativeRendering
                opacity: clock.tick ? 1.0 : 0.3
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.InOutQuad } }
            }
            Text {
                id: minutes
                text: Qt.formatTime(timeSource.now, "mm")
                color: Kirigami.Theme.textColor
                font.family: "Inter"
                font.pointSize: hours.font.pointSize
                font.weight: Font.Thin
                font.letterSpacing: -2
                renderType: Text.NativeRendering
            }
        }

        // ── A single hairline accent, breathing slowly ──
        Rectangle {
            id: accentTick
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.preferredWidth: Kirigami.Units.gridUnit * 4
            Layout.preferredHeight: 2
            radius: 1
            color: Kirigami.Theme.highlightColor
            opacity: 0.9
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: clock.visible
                NumberAnimation { to: 0.45; duration: 3200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.9; duration: 3200; easing.type: Easing.InOutSine }
            }
        }

        // ── Quiet bilingual date ──
        Text {
            Layout.topMargin: Kirigami.Units.largeSpacing
            text: Qt.locale("ar").toString(timeSource.now, Qt.locale("ar").dateFormat(Locale.LongFormat))
            color: Kirigami.Theme.textColor
            opacity: 0.85
            font.family: "IBM Plex Sans Arabic"
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.4)
            font.weight: Font.Light
            renderType: Text.NativeRendering
        }
        Text {
            text: Qt.locale("en").toString(timeSource.now, "dddd, d MMMM")
            color: Kirigami.Theme.textColor
            opacity: 0.55
            font.family: "Inter"
            font.pointSize: Math.round(Kirigami.Theme.defaultFont.pointSize * 1.05)
            font.weight: Font.Normal
            font.letterSpacing: 1
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
