pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: weatherCard

    required property bool weatherReady
    required property string city
    required property int temperature
    required property int feelsLike
    required property int high
    required property int low
    required property string kind
    required property string condition
    required property bool motionEnabled
    // 0 now, 1 the next hours. The wallpaper owns the value (HubWeatherPage) and the
    // desktop's own menu writes it, because a wallpaper receives no pointer events.
    property int page: 0
    property var hours: []
    // weatherKind(code, daylight) from the bento, so one code cannot mean two
    // pictures on the two faces of one card.
    property var kindForCode: (function (code) { return "cloudy" })
    // MotionMode 2 ("alive"). Gentle keeps one infrequent artwork drift; the
    // condition-specific rain/snow/fog/storm bursts belong to alive so the
    // calm default never turns the 4K wallpaper into a permanent repaint loop.
    required property bool accentMotion
    property int entranceDelay: 0
    property bool integrated: false

    // One locale authority for every label on the hub. The cards used to hard-code a mix of
    // English eyebrows ("SYSTEM", "HIGH", "FEELS") and Arabic words ("الآن") whatever the session
    // language was, so an Arabic desktop read as two languages and an English one showed Arabic
    // weather. Brand names and the bilingual date pair shared with the login/lock clocks are the
    // only deliberate exceptions. Arabic is never letter-spaced.
    readonly property bool rtl: MoUI.Locale.rtl
    readonly property string labelFamily: rtl ? "IBM Plex Sans Arabic" : "IBM Plex Sans"
    function local(arabic, english) { return MoUI.Locale.local(arabic, english) }
    // A temperature is an LTR island. Inside an Arabic label the bidi algorithm otherwise
    // moves the degree sign in front of the number ("°18"), as the 4K capture showed.
    function degrees(value) { return "\u2066" + value + "°\u2069" }

    GlassCard {
        anchors.fill: parent
        motionEnabled: weatherCard.motionEnabled
        accentMotion: weatherCard.accentMotion
        entranceDelay: weatherCard.entranceDelay
        integrated: weatherCard.integrated

        CardStack {
            anchors.fill: parent
            motionEnabled: weatherCard.motionEnabled
            page: weatherCard.page

            Item {
        RowLayout {
            anchors.fill: parent
            spacing: Math.round(Kirigami.Units.gridUnit * 0.75)

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
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
                        text: weatherCard.city.length > 0
                              ? weatherCard.city
                              : weatherCard.local("الطقس المحلي", "LOCAL FORECAST")
                        color: Kirigami.Theme.disabledTextColor
                        font.family: weatherCard.city.length > 0 ? "IBM Plex Sans" : weatherCard.labelFamily
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.54)
                        font.weight: Font.DemiBold
                        font.letterSpacing: weatherCard.city.length > 0 ? 0.8 : (weatherCard.rtl ? 0 : 1.5)
                        elide: Text.ElideRight
                        Layout.maximumWidth: Kirigami.Units.gridUnit * 7
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: weatherCard.weatherReady
                              ? weatherCard.local("الآن", "NOW")
                              : weatherCard.local("تلقائي", "AUTO")
                        color: Kirigami.Theme.highlightColor
                        font.family: weatherCard.labelFamily
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.56)
                        font.weight: Font.DemiBold
                    }
                }

                Item { Layout.preferredHeight: Kirigami.Units.gridUnit * 0.45 }

                RowLayout {
                    visible: weatherCard.weatherReady
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Text {
                        text: weatherCard.temperature + "°"
                        color: Kirigami.Theme.textColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 2.15)
                        font.weight: Font.Light
                        font.features: ({ "tnum": 1 })
                    }
                    ColumnLayout {
                        Layout.alignment: Qt.AlignVCenter
                        Layout.fillWidth: true
                        spacing: 0

                        Text {
                            // A long Arabic condition ("عاصفة رعدية") or a large
                            // font must elide, not push the row wider than the card.
                            Layout.fillWidth: true
                            text: weatherCard.condition
                            color: Kirigami.Theme.textColor
                            font.family: weatherCard.labelFamily
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.72)
                            font.weight: Font.Medium
                            elide: Text.ElideRight
                        }
                        Text {
                            text: weatherCard.local("المحسوسة ", "FEELS ") + weatherCard.degrees(weatherCard.feelsLike)
                            color: Kirigami.Theme.disabledTextColor
                            font.family: weatherCard.labelFamily
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.48)
                            font.weight: Font.Medium
                            font.letterSpacing: weatherCard.rtl ? 0 : 0.8
                        }
                    }
                }

                Text {
                    visible: !weatherCard.weatherReady
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.largeSpacing
                    text: weatherCard.local("سيظهر الطقس المحلي تلقائياً",
                                            "Local weather appears automatically")
                    color: Kirigami.Theme.disabledTextColor
                    font.family: weatherCard.labelFamily
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.75)
                    font.weight: Font.Medium
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    visible: weatherCard.weatherReady
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 4.25
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 1.25
                        radius: height / 2
                        color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                                       Kirigami.Theme.alternateBackgroundColor.g,
                                       Kirigami.Theme.alternateBackgroundColor.b, 0.64)
                        border.width: 1
                        border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                              Kirigami.Theme.highlightColor.g,
                                              Kirigami.Theme.highlightColor.b, 0.2)
                        Text {
                            anchors.centerIn: parent
                            text: weatherCard.local("العظمى  ", "HIGH  ") + weatherCard.degrees(weatherCard.high)
                            color: Kirigami.Theme.textColor
                            font.family: weatherCard.labelFamily
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.52)
                            font.weight: Font.DemiBold
                            font.features: ({ "tnum": 1 })
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 4.25
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 1.25
                        radius: height / 2
                        color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                                       Kirigami.Theme.alternateBackgroundColor.g,
                                       Kirigami.Theme.alternateBackgroundColor.b, 0.48)
                        border.width: 1
                        border.color: Qt.rgba(Kirigami.Theme.disabledTextColor.r,
                                              Kirigami.Theme.disabledTextColor.g,
                                              Kirigami.Theme.disabledTextColor.b, 0.18)
                        Text {
                            anchors.centerIn: parent
                            text: weatherCard.local("الصغرى  ", "LOW  ") + weatherCard.degrees(weatherCard.low)
                            color: Kirigami.Theme.disabledTextColor
                            font.family: weatherCard.labelFamily
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.52)
                            font.weight: Font.DemiBold
                            font.features: ({ "tnum": 1 })
                        }
                    }
                }
            }

            WeatherScene {
                Layout.preferredWidth: Math.round(Kirigami.Units.gridUnit * 6.2)
                Layout.fillHeight: true
                visible: weatherCard.weatherReady
                opacity: weatherCard.weatherReady ? 1 : 0
                kind: weatherCard.kind
                motionEnabled: weatherCard.motionEnabled
                accentMotion: weatherCard.accentMotion

                // A one-shot value transition — the kind Plasma's animation-speed
                // slider is meant to own. It could not, because 420 was a literal
                // and only Kirigami.Units.* tracks that slider.
                Behavior on opacity {
                    enabled: weatherCard.motionEnabled
                    NumberAnimation {
                        duration: Kirigami.Units.veryLongDuration
                        easing.type: Easing.OutCubic
                    }
                }
            }
        }
            }

            HourlyStrip {
                hours: weatherCard.hours
                city: weatherCard.city
                weatherReady: weatherCard.weatherReady
                kindForCode: weatherCard.kindForCode
            }
        }
    }
}
