// Adaptive Tidal Glass card. The layered rectangles keep the effect inexpensive
// inside plasmashell while preserving the palette of the active colour scheme.
pragma ComponentBehavior: Bound

import QtQuick
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: card

    required property bool motionEnabled
    // MotionMode 2 ("alive"). Read together with motionEnabled, never alone.
    required property bool accentMotion
    property int entranceDelay: 0
    // A dashboard section can borrow one shared outer glass shell. In that
    // mode this component contributes only spacing/content; it must not paint a
    // second card or run a second entrance over the shared Horizon Hub.
    property bool integrated: false
    default property alias contentData: contentLayer.data
    readonly property var design: MoUI.Tokens

    // Plasma's animation-speed slider (System Settings → General Behaviour)
    // scales Kirigami.Units.*Duration and NOTHING else. Every millisecond in this
    // package was a literal, so the slider moved nothing in either direction: a
    // user who asked for snappier feedback still waited the same 420 ms for a
    // card to arrive, and one who asked for slower got no slower. One-shot
    // transitions are exactly what that slider is for, so they follow it. The
    // looping ambient cadences below stay literal on purpose — those are a
    // duty-cycle budget for a 4K surface, not a response time, and letting the
    // slider stretch them would stretch the CPU cost with them.
    readonly property int entranceDuration: Kirigami.Units.veryLongDuration

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
    // The shade under the top edge. Derived from the active background, not from
    // pure black: no MoOS runtime surface uses pure black or pure white, and a
    // palette-derived shade also keeps the card looking like the same object in
    // all sixteen themes instead of gaining a neutral grey seam in the warm ones.
    readonly property color shadeColor: {
        const shade = Qt.darker(Kirigami.Theme.backgroundColor, 2.2)
        return Qt.rgba(shade.r, shade.g, shade.b, lightSurface ? 0.05 : 0.09)
    }

    opacity: integrated ? 1 : (motionEnabled ? 0 : 1)
    transform: Translate {
        id: entranceShift
        y: card.motionEnabled && !card.integrated
            ? Kirigami.Units.largeSpacing : 0
    }

    Component.onCompleted: Qt.callLater(function() {
        if (card.motionEnabled && !card.integrated) {
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
                duration: card.entranceDuration
                easing.type: Easing.OutCubic
            }
            NumberAnimation {
                target: entranceShift
                property: "y"
                from: Kirigami.Units.largeSpacing
                to: 0
                duration: card.entranceDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    Rectangle {
        visible: !card.integrated
        x: Kirigami.Units.smallSpacing
        y: Kirigami.Units.largeSpacing
        width: parent.width - Kirigami.Units.smallSpacing * 2
        height: parent.height - Kirigami.Units.largeSpacing
        radius: card.design.radiusPanel
        color: {
            const shade = Qt.darker(Kirigami.Theme.backgroundColor, 1.45)
            return Qt.rgba(shade.r, shade.g, shade.b,
                           card.lightSurface ? 0.16 : 0.26)
        }
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        anchors.leftMargin: card.integrated ? 0 : card.design.borderHairline
        anchors.rightMargin: card.integrated ? 0 : card.design.borderHairline
        anchors.topMargin: card.integrated ? 0 : card.design.borderHairline
        anchors.bottomMargin: card.integrated ? 0
            : Math.max(2, Kirigami.Units.smallSpacing / 2)
        radius: card.integrated ? 0 : card.design.radiusPanel
        border.width: card.integrated ? 0 : card.design.borderHairline
        border.color: card.edgeColor
        clip: true

        gradient: Gradient {
            GradientStop {
                position: 0.0
                color: card.integrated ? "transparent" : card.upperSurface
            }
            GradientStop {
                position: 1.0
                color: card.integrated ? "transparent" : card.lowerSurface
            }
        }

        // Micro-shadow: a soft inset shade under the top edge, for depth.
        //
        // The first version of this was a 3 px-tall strip carrying
        // `radius: parent.radius` and trusting the shell's `clip: true` to cut
        // its corners. Neither half of that works. A Rectangle clamps its radius
        // to half its SHORTEST side, so a 3 px strip can only ever be 1.5 px
        // round no matter what you ask for; and QQuickItem clipping is a
        // RECTANGULAR scissor, which cannot cut a rounded corner. The strip's
        // square corners therefore drew straight across the card's rounded ones —
        // two hard little notches at the top of every card, exactly where the eye
        // goes first.
        //
        // Give the shade the card's OWN geometry and radius instead, and let the
        // rounded rectangle clip its own gradient: the dark band lives in the
        // first few pixels of the height and everything below it is transparent.
        Rectangle {
            id: topShade
            visible: !card.integrated
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            // Three pixels expressed as a fraction of the card's height, clamped
            // at both ends: during the first layout pass the height is 0, and an
            // unclamped 3/0 would hand Gradient an out-of-order stop.
            readonly property real shadeStop:
                Math.max(0.01, Math.min(0.5, 3 / Math.max(1, shell.height)))
            gradient: Gradient {
                GradientStop { position: 0.0; color: card.shadeColor }
                GradientStop { position: topShade.shadeStop; color: "transparent" }
            }
        }

        // Inner glow: faint highlight-coloured rim inside the card
        Rectangle {
            visible: !card.integrated
            anchors.fill: parent
            anchors.margins: 1
            radius: parent.radius - 1
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                   Kirigami.Theme.highlightColor.g,
                                   Kirigami.Theme.highlightColor.b,
                                   card.lightSurface ? 0.05 : 0.08)
        }

        Rectangle {
            visible: !card.integrated
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: Math.round(Kirigami.Units.gridUnit * 1.25)
            anchors.rightMargin: Math.round(Kirigami.Units.gridUnit * 1.25)
            height: card.design.borderHairline
            color: Qt.rgba(Kirigami.Theme.highlightedTextColor.r,
                           Kirigami.Theme.highlightedTextColor.g,
                           Kirigami.Theme.highlightedTextColor.b,
                           card.lightSurface ? 0.52 : 0.28)
        }

        Rectangle {
            visible: !card.integrated
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 1.2)
            anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 1.2)
            width: card.design.borderHairline
            color: card.edgeColor
        }

        // The travelling glass highlight. This is `alive` only (MotionMode 2) —
        // it is the thing that makes the level worth having, and it is also the
        // single most expensive decoration in the package, because a moving item
        // repaints the whole card every frame it moves.
        //
        // `visible` is gated as well as `running`, and that is not belt and
        // braces. `SequentialAnimation on x` is a property VALUE SOURCE: it owns
        // x and, when `running` goes false, simply stops writing it. It does not
        // rewind. Dropping from alive to gentle mid-sweep therefore used to be
        // able to leave a bright diagonal bar frozen across the middle of every
        // card, with nothing left running to move it off again. An invisible item
        // cannot leave a mark — and it costs nothing to paint.
        Rectangle {
            id: sheen
            visible: !card.integrated && card.motionEnabled && card.accentMotion
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

            Timer {
                id: sheenCadence
                interval: 30000 + card.entranceDelay * 3
                repeat: true
                triggeredOnStart: false
                running: card.motionEnabled && card.accentMotion && sheen.visible
                onTriggered: sheenSweep.restart()
                onRunningChanged: {
                    if (!running) {
                        sheenSweep.stop()
                        sheen.x = -sheen.width * 1.5
                    }
                }
            }

            SequentialAnimation {
                id: sheenSweep
                PropertyAction {
                    target: sheen
                    property: "x"
                    value: -sheen.width * 1.5
                }
                NumberAnimation {
                    target: sheen
                    property: "x"
                    to: shell.width + sheen.width
                    duration: 5200
                    easing.type: Easing.InOutSine
                }
            }
        }

        Item {
            id: contentLayer
            anchors.fill: parent
            anchors.margins: card.integrated
                ? Math.round(Kirigami.Units.gridUnit * 0.55)
                : Math.round(Kirigami.Units.gridUnit * 1.05)
        }
    }
}
