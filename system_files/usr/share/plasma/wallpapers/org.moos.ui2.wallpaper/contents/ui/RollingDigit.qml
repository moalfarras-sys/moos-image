// A single tabular digit. Only the column whose glyph changes performs the roll.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: digit

    required property string glyph
    required property bool motionEnabled
    property int pixelSize: Math.round(Kirigami.Units.gridUnit * 3)
    property string displayedGlyph: glyph

    implicitWidth: metrics.advanceWidth
    implicitHeight: metrics.height
    Layout.preferredWidth: implicitWidth
    Layout.preferredHeight: implicitHeight
    Layout.alignment: Qt.AlignVCenter
    clip: true

    TextMetrics {
        id: metrics
        font: incoming.font
        text: "0"
    }

    onGlyphChanged: {
        if (glyph === displayedGlyph) {
            return
        }
        outgoing.text = displayedGlyph
        displayedGlyph = glyph
        if (motionEnabled) {
            turn.restart()
        } else {
            turn.stop()
            incoming.y = 0
            incoming.opacity = 1
            outgoing.opacity = 0
        }
    }

    onMotionEnabledChanged: {
        if (!motionEnabled) {
            turn.stop()
            incoming.y = 0
            incoming.opacity = 1
            incoming.scale = 1
            outgoing.opacity = 0
        }
    }

    Text {
        id: outgoing
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        color: Kirigami.Theme.textColor
        font.family: "IBM Plex Sans"
        font.pixelSize: digit.pixelSize
        font.weight: Font.Light
        font.features: ({ "tnum": 1 })
        opacity: 0
    }

    Text {
        id: incoming
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        text: digit.displayedGlyph
        color: Kirigami.Theme.textColor
        font.family: "IBM Plex Sans"
        font.pixelSize: digit.pixelSize
        font.weight: Font.Light
        font.features: ({ "tnum": 1 })
    }

    SequentialAnimation {
        id: turn
        running: false

        PropertyAction { target: outgoing; property: "y"; value: 0 }
        PropertyAction { target: outgoing; property: "opacity"; value: 1 }
        PropertyAction { target: outgoing; property: "scale"; value: 1 }
        PropertyAction { target: incoming; property: "y"; value: digit.height * 0.7 }
        PropertyAction { target: incoming; property: "opacity"; value: 0 }
        PropertyAction { target: incoming; property: "scale"; value: 0.94 }

        ParallelAnimation {
            NumberAnimation {
                target: outgoing
                property: "y"
                to: -digit.height * 0.7
                duration: 420
                easing.type: Easing.InCubic
            }
            NumberAnimation {
                target: outgoing
                property: "opacity"
                to: 0
                duration: 150
                easing.type: Easing.InQuad
            }
            NumberAnimation {
                target: incoming
                property: "y"
                to: 0
                duration: 420
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: incoming
                property: "scale"
                to: 1
                duration: 420
                easing.type: Easing.OutCubic
            }
            SequentialAnimation {
                PauseAnimation { duration: 150 }
                NumberAnimation {
                    target: incoming
                    property: "opacity"
                    to: 1
                    duration: 270
                    easing.type: Easing.OutCubic
                }
            }
        }
    }
}
