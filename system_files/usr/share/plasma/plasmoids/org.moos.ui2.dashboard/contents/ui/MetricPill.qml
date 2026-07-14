pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: pill

    required property string label
    required property real value
    required property bool present
    required property bool motionEnabled
    property color accentColor: Kirigami.Theme.highlightColor

    readonly property real clampedValue: Math.max(0, Math.min(100, value))
    property real displayedValue: present ? clampedValue : 0

    radius: Math.round(Kirigami.Units.gridUnit * 0.78)
    color: Qt.rgba(Kirigami.Theme.alternateBackgroundColor.r,
                   Kirigami.Theme.alternateBackgroundColor.g,
                   Kirigami.Theme.alternateBackgroundColor.b, 0.58)
    border.width: 1
    border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.21)

    Behavior on displayedValue {
        enabled: pill.motionEnabled
        NumberAnimation { duration: 700; easing.type: Easing.OutCubic }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: Kirigami.Units.largeSpacing
        anchors.rightMargin: Kirigami.Units.largeSpacing
        anchors.topMargin: Kirigami.Units.smallSpacing
        anchors.bottomMargin: Kirigami.Units.smallSpacing
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Text {
                text: pill.label
                color: Kirigami.Theme.disabledTextColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.47)
                font.weight: Font.DemiBold
                font.letterSpacing: 1.1
            }
            Item { Layout.fillWidth: true }
            Text {
                text: pill.present ? Math.round(pill.displayedValue) + "%" : "—"
                color: pill.present ? Kirigami.Theme.textColor
                                    : Kirigami.Theme.disabledTextColor
                font.family: "IBM Plex Sans"
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 0.72)
                font.weight: Font.DemiBold
                font.features: ({ "tnum": 1 })
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            id: track
            Layout.fillWidth: true
            Layout.preferredHeight: Math.max(3, Kirigami.Units.gridUnit * 0.18)
            radius: height / 2
            color: Qt.rgba(Kirigami.Theme.textColor.r,
                           Kirigami.Theme.textColor.g,
                           Kirigami.Theme.textColor.b, 0.11)
            clip: true

            Rectangle {
                height: parent.height
                width: parent.width * pill.displayedValue / 100
                radius: height / 2
                color: pill.accentColor

                Behavior on width {
                    enabled: pill.motionEnabled
                    NumberAnimation { duration: 700; easing.type: Easing.OutCubic }
                }
            }
        }
    }
}
