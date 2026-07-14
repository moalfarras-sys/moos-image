pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

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
    property int entranceDelay: 0

    GlassCard {
        anchors.fill: parent
        motionEnabled: weatherCard.motionEnabled
        entranceDelay: weatherCard.entranceDelay

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
                              ? weatherCard.city : "LOCAL FORECAST"
                        color: Kirigami.Theme.disabledTextColor
                        font.family: "IBM Plex Sans"
                        font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.54)
                        font.weight: Font.DemiBold
                        font.letterSpacing: weatherCard.city.length > 0 ? 0.8 : 1.5
                        elide: Text.ElideRight
                        Layout.maximumWidth: Kirigami.Units.gridUnit * 7
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: weatherCard.weatherReady ? "الآن" : "تلقائي"
                        color: Kirigami.Theme.highlightColor
                        font.family: "IBM Plex Sans Arabic"
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
                        spacing: 0

                        Text {
                            text: weatherCard.condition
                            color: Kirigami.Theme.textColor
                            font.family: "IBM Plex Sans Arabic"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.72)
                            font.weight: Font.Medium
                        }
                        Text {
                            text: "FEELS " + weatherCard.feelsLike + "°"
                            color: Kirigami.Theme.disabledTextColor
                            font.family: "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.48)
                            font.weight: Font.Medium
                            font.letterSpacing: 0.8
                        }
                    }
                }

                Text {
                    visible: !weatherCard.weatherReady
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.largeSpacing
                    text: "سيظهر الطقس المحلي تلقائياً"
                    color: Kirigami.Theme.disabledTextColor
                    font.family: "IBM Plex Sans Arabic"
                    font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.75)
                    font.weight: Font.Medium
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    visible: weatherCard.weatherReady
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 3.55
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
                            text: "HIGH  " + weatherCard.high + "°"
                            color: Kirigami.Theme.textColor
                            font.family: "IBM Plex Sans"
                            font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.52)
                            font.weight: Font.DemiBold
                            font.features: ({ "tnum": 1 })
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 3.55
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
                            text: "LOW  " + weatherCard.low + "°"
                            color: Kirigami.Theme.disabledTextColor
                            font.family: "IBM Plex Sans"
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

                Behavior on opacity {
                    enabled: weatherCard.motionEnabled
                    NumberAnimation { duration: 420; easing.type: Easing.OutCubic }
                }
            }
        }
    }
}
