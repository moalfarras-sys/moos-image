// The clock card's first page: the hour and localized date/week.
// Split out of ClockCard.qml when the card gained a second page, so each
// page is one readable file and the card itself is the composition of the two.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: face

    required property date now
    required property bool motionEnabled
    property string themeLabel: ""

    readonly property bool rtl: MoUI.Locale.rtl
    readonly property string labelFamily: rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
    function local(arabic, english) { return MoUI.Locale.local(arabic, english) }

    // The once-a-minute colon pulse is a one-shot transition, which is exactly
    // what Plasma's animation-speed slider is meant to own — and it could not,
    // because both halves were hardcoded milliseconds. Only Kirigami.Units.*
    // tracks that slider, so derive them from it.
    readonly property int pulseOutDuration:
        Math.round(Kirigami.Units.veryLongDuration * 0.42)
    readonly property int pulseInDuration:
        Math.round(Kirigami.Units.veryLongDuration * 0.62)

    readonly property int clockSize: Math.round(Math.max(Kirigami.Units.gridUnit * 3.15,
        Math.min(Kirigami.Units.gridUnit * 4.8, width * 0.22)))
    readonly property string timeText: Qt.formatTime(now, "HH:mm")

    onNowChanged: {
        if (motionEnabled) {
            minutePulse.restart()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Text {
            Layout.fillWidth: true
            objectName: "hubLocalDate"
            text: Qt.formatDate(face.now, Qt.locale(face.rtl ? "ar" : "en"), Locale.LongFormat)
            color: Kirigami.Theme.textColor
            font.family: face.labelFamily
            font.pixelSize: face.width > Kirigami.Units.gridUnit * 16
                ? MoUI.Tokens.typeTitle : MoUI.Tokens.typeBody
            font.weight: Font.Medium
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }

        Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.75 }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            // Time is a left-to-right technical token even when the shell
            // language is Arabic. Plasma enables LayoutMirroring on the
            // wallpaper tree, which overrides layoutDirection alone; stop
            // that inheritance here and keep the rolling digits in HH:mm
            // order.
            LayoutMirroring.enabled: false
            LayoutMirroring.childrenInherit: true
            layoutDirection: Qt.LeftToRight
            spacing: 0

            RollingDigit {
                glyph: face.timeText.charAt(0)
                motionEnabled: face.motionEnabled
                pixelSize: face.clockSize
            }
            RollingDigit {
                glyph: face.timeText.charAt(1)
                motionEnabled: face.motionEnabled
                pixelSize: face.clockSize
            }

            Text {
                id: colon
                Layout.alignment: Qt.AlignVCenter
                text: ":"
                color: Kirigami.Theme.highlightColor
                opacity: 0.74
                font.family: "IBM Plex Sans"
                font.pixelSize: face.clockSize
                font.weight: Font.Light

                // NOTHING may take ownership of this opacity. A
                // `SequentialAnimation on opacity` was added here as a
                // "breathing pulse" and was wrong three ways at once:
                //
                //   * `... on opacity` is a property VALUE SOURCE, so it OWNS
                //     the property. The minutePulse below writes the same
                //     property by target — the value source simply overwrote
                //     it every frame, so the designed once-a-minute pulse
                //     stopped being visible at all.
                //   * a value source does not rewind when it stops. Turning
                //     motion off left the colon frozen at whatever the fade
                //     had reached, i.e. permanently dimmer than the 0.74 it
                //     is designed to sit at, with nothing left to restore it.
                //   * it turned a 420 ms event that happens once a minute
                //     into a permanent 1.8 s loop, and a looping animation
                //     repaints the WHOLE window — on a 4K desktop, forever,
                //     for a two-pixel colon.
                //
                // The minute pulse below is the designed motion. Leave the
                // resting opacity a plain value.
            }

            RollingDigit {
                glyph: face.timeText.charAt(3)
                motionEnabled: face.motionEnabled
                pixelSize: face.clockSize
            }
            RollingDigit {
                glyph: face.timeText.charAt(4)
                motionEnabled: face.motionEnabled
                pixelSize: face.clockSize
            }
        }

        SequentialAnimation {
            id: minutePulse
            running: false

            NumberAnimation {
                target: colon
                property: "opacity"
                from: 0.74
                to: 0.28
                duration: face.pulseOutDuration
                easing.type: Easing.InQuad
            }
            NumberAnimation {
                target: colon
                property: "opacity"
                to: 0.74
                duration: face.pulseInDuration
                easing.type: Easing.OutCubic
            }
        }

        Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.55 }

        WeekStrip {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
            Layout.topMargin: Kirigami.Units.smallSpacing
            now: face.now
            compact: true
        }

        Item { Layout.fillHeight: true }
    }
}
