pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: clockCard

    required property date now
    required property bool motionEnabled
    property int entranceDelay: 0
    // Active MoOS look, e.g. "MIDNIGHT GLASS"; empty falls back to the half.
    property string themeLabel: ""

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
                    duration: 170
                    easing.type: Easing.InQuad
                }
                NumberAnimation {
                    target: colon
                    property: "opacity"
                    to: 0.74
                    duration: 250
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
