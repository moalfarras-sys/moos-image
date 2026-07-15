// Adaptive Tidal Glass card. The layered rectangles keep the effect inexpensive
// inside plasmashell while preserving the palette of the active colour scheme.
pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: card

    required property bool motionEnabled
    property int entranceDelay: 0
    default property alias contentData: contentLayer.data

    readonly property bool lightSurface:
        Kirigami.Theme.backgroundColor.hslLightness > 0.55
    readonly property color upperSurface: Qt.rgba(
        Kirigami.Theme.alternateBackgroundColor.r,
        Kirigami.Theme.alternateBackgroundColor.g,
        Kirigami.Theme.alternateBackgroundColor.b,
        lightSurface ? 0.91 : 0.84)
    readonly property color lowerSurface: Qt.rgba(
        Kirigami.Theme.backgroundColor.r,
        Kirigami.Theme.backgroundColor.g,
        Kirigami.Theme.backgroundColor.b,
        lightSurface ? 0.83 : 0.76)
    readonly property color edgeColor: Qt.rgba(
        Kirigami.Theme.highlightColor.r,
        Kirigami.Theme.highlightColor.g,
        Kirigami.Theme.highlightColor.b,
        lightSurface ? 0.31 : 0.36)

    opacity: motionEnabled ? 0 : 1
    transform: Translate {
        id: entranceShift
        y: card.motionEnabled ? Kirigami.Units.largeSpacing : 0
    }

    Component.onCompleted: Qt.callLater(function() {
        if (card.motionEnabled) {
            entrance.restart()
        } else {
            card.opacity = 1
            entranceShift.y = 0
        }
    })

    onMotionEnabledChanged: {
        if (!motionEnabled) {
            entrance.stop()
            card.opacity = 1
            entranceShift.y = 0
        }
    }

    SequentialAnimation {
        id: entrance
        running: false

        PauseAnimation { duration: card.entranceDelay }
        ParallelAnimation {
            NumberAnimation {
                target: card
                property: "opacity"
                from: 0
                to: 1
                duration: 420
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: entranceShift
                property: "y"
                from: Kirigami.Units.largeSpacing
                to: 0
                duration: 420
                easing.type: Easing.OutCubic
            }
        }
    }

    Rectangle {
        x: Kirigami.Units.smallSpacing
        y: Kirigami.Units.largeSpacing
        width: parent.width - Kirigami.Units.smallSpacing * 2
        height: parent.height - Kirigami.Units.largeSpacing
        radius: Math.round(Kirigami.Units.gridUnit * 1.35)
        color: {
            const shade = Qt.darker(Kirigami.Theme.backgroundColor, 1.45)
            return Qt.rgba(shade.r, shade.g, shade.b,
                           card.lightSurface ? 0.16 : 0.26)
        }
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        anchors.leftMargin: 1
        anchors.rightMargin: 1
        anchors.topMargin: 1
        anchors.bottomMargin: Math.max(2, Kirigami.Units.smallSpacing / 2)
        radius: Math.round(Kirigami.Units.gridUnit * 1.35)
        border.width: 1
        border.color: card.edgeColor
        clip: true

        gradient: Gradient {
            GradientStop { position: 0.0; color: card.upperSurface }
            GradientStop { position: 1.0; color: card.lowerSurface }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: Math.round(Kirigami.Units.gridUnit * 1.25)
            anchors.rightMargin: Math.round(Kirigami.Units.gridUnit * 1.25)
            height: 1
            color: Qt.rgba(Kirigami.Theme.highlightedTextColor.r,
                           Kirigami.Theme.highlightedTextColor.g,
                           Kirigami.Theme.highlightedTextColor.b,
                           card.lightSurface ? 0.52 : 0.28)
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 1.2)
            anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 1.2)
            width: 1
            color: card.edgeColor
        }

        Rectangle {
            id: sheen
            width: Math.max(Kirigami.Units.gridUnit * 3, shell.width * 0.2)
            height: shell.height * 1.7
            y: -shell.height * 0.35
            rotation: 12
            opacity: card.lightSurface ? 0.16 : 0.11
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop {
                    position: 0.5
                    color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                   Kirigami.Theme.highlightColor.g,
                                   Kirigami.Theme.highlightColor.b, 0.45)
                }
                GradientStop { position: 1.0; color: "transparent" }
            }

            SequentialAnimation on x {
                running: card.motionEnabled && card.visible
                loops: Animation.Infinite
                PropertyAction { value: -sheen.width * 1.5 }
                PauseAnimation { duration: 2200 }
                NumberAnimation {
                    to: shell.width + sheen.width
                    duration: 14000
                    easing.type: Easing.InOutSine
                }
                PauseAnimation { duration: 5200 }
            }
        }

        Item {
            id: contentLayer
            anchors.fill: parent
            anchors.margins: Math.round(Kirigami.Units.gridUnit * 1.05)
        }
    }
}
