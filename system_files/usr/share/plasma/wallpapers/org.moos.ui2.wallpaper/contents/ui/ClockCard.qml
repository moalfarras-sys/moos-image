pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: clockCard

    required property date now
    required property bool motionEnabled
    // MotionMode 2 ("alive"). Passed straight through to the card shell, which
    // owns the only accent this card has: the sheen sweep.
    required property bool accentMotion
    property int entranceDelay: 0
    // Active MoOS look, e.g. "MIDNIGHT GLASS"; empty falls back to the half.
    property string themeLabel: ""

    // The once-a-minute colon pulse is a one-shot transition, which is exactly
    // what Plasma's animation-speed slider is meant to own — and it could not,
    // because both halves were hardcoded milliseconds. Only Kirigami.Units.*
    // tracks that slider, so derive them from it.
    readonly property int pulseOutDuration:
        Math.round(Kirigami.Units.veryLongDuration * 0.42)
    readonly property int pulseInDuration:
        Math.round(Kirigami.Units.veryLongDuration * 0.62)

    readonly property string timeText: Qt.formatTime(now, "HH:mm")
    readonly property var arabicLocale: Qt.locale("ar")
    readonly property bool lightSurface:
        Kirigami.Theme.backgroundColor.hslLightness > 0.55

    onNowChanged: {
        if (motionEnabled) {
            minutePulse.restart()
        }
    }

    GlassCard {
        anchors.fill: parent
        motionEnabled: clockCard.motionEnabled
        accentMotion: clockCard.accentMotion
        entranceDelay: clockCard.entranceDelay

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    Layout.preferredWidth: Math.max(5, Kirigami.Units.gridUnit * 0.34)
                    Layout.preferredHeight: Layout.preferredWidth
                    radius: width / 2
                    color: Kirigami.Theme.highlightColor
                }

                Text {
                    text: "LOCAL TIME"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.55)
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.8
                }

                // No AM/PM badge: the digits below are 24-hour (HH:mm), so a
                // meridiem marker contradicts them. Every other MoOS clock (login,
                // lock, Hero) shows 24-hour with no meridiem — this card matches.
                Item { Layout.fillWidth: true }
            }

            Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.75 }

            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignLeft
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
                    glyph: clockCard.timeText.charAt(0)
                    motionEnabled: clockCard.motionEnabled
                    pixelSize: Math.round(Kirigami.Units.gridUnit * 3.15)
                }
                RollingDigit {
                    glyph: clockCard.timeText.charAt(1)
                    motionEnabled: clockCard.motionEnabled
                    pixelSize: Math.round(Kirigami.Units.gridUnit * 3.15)
                }

                Text {
                    id: colon
                    Layout.alignment: Qt.AlignVCenter
                    text: ":"
                    color: Kirigami.Theme.highlightColor
                    opacity: 0.74
                    font.family: "IBM Plex Sans"
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 3.15)
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
                    glyph: clockCard.timeText.charAt(3)
                    motionEnabled: clockCard.motionEnabled
                    pixelSize: Math.round(Kirigami.Units.gridUnit * 3.15)
                }
                RollingDigit {
                    glyph: clockCard.timeText.charAt(4)
                    motionEnabled: clockCard.motionEnabled
                    pixelSize: Math.round(Kirigami.Units.gridUnit * 3.15)
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
                    duration: clockCard.pulseOutDuration
                    easing.type: Easing.InQuad
                }
                NumberAnimation {
                    target: colon
                    property: "opacity"
                    to: 0.74
                    duration: clockCard.pulseInDuration
                    easing.type: Easing.OutCubic
                }
            }

            Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.55 }

            Text {
                Layout.fillWidth: true
                text: clockCard.arabicLocale.standaloneDayName(
                          clockCard.now.getDay(), Locale.LongFormat)
                      + "، " + Qt.formatDate(clockCard.now, "d ")
                      + clockCard.arabicLocale.standaloneMonthName(
                          clockCard.now.getMonth(), Locale.LongFormat)
                color: Kirigami.Theme.textColor
                font.family: "IBM Plex Sans Arabic"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.88)
                font.weight: Font.Medium
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing / 2
                // Pinned to English (not the ambient session locale) so the two
                // date lines are always the same ar+en bilingual pair the login,
                // lock and Hero clocks use — never two Arabic lines on an Arabic
                // session.
                text: Qt.formatDate(clockCard.now, Qt.locale("en"), "dddd, d MMMM yyyy")
                color: Kirigami.Theme.disabledTextColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.68)
                font.weight: Font.Normal
                elide: Text.ElideRight
            }

            Item { Layout.fillHeight: true }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.round(Kirigami.Units.gridUnit * 1.45)
                radius: height / 2
                color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                               Kirigami.Theme.alternateBackgroundColor.g,
                               Kirigami.Theme.alternateBackgroundColor.b, 0.62)
                border.width: 1
                border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                      Kirigami.Theme.highlightColor.g,
                                      Kirigami.Theme.highlightColor.b, 0.22)

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Kirigami.Units.largeSpacing
                    anchors.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 1.1
                        Layout.preferredHeight: 2
                        radius: 1
                        color: Kirigami.Theme.highlightColor
                    }
                    Text {
                        text: "MoOS"
                        color: Kirigami.Theme.textColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.53)
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.4
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: clockCard.themeLabel !== ""
                            ? clockCard.themeLabel
                            : (clockCard.lightSurface ? "TIDAL GLASS" : "GRAPHITE GLASS")
                        color: Kirigami.Theme.disabledTextColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.49)
                        font.weight: Font.Medium
                        font.letterSpacing: 1.1
                    }
                }
            }
        }
    }
}
