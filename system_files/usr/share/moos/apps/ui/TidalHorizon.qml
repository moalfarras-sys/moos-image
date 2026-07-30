import QtQuick
import QtQuick.Shapes
import org.kde.kirigami as Kirigami

// Application expression of the shared MoOS Tidal Horizon geometry.
//
// Splash, login, lock, logout, Launcher and first-party apps all use the same
// rising cubic rim and interrupted crest. Geometry is physical, so it is not
// mirrored in RTL; colour is semantic and always supplied by the active theme.
// This component has no loop, timer, shader or input handler.
// SPDX-License-Identifier: GPL-2.0-or-later
Item {
    id: root

    property color surfaceColor: "#14191c"
    property color primaryColor: "#4ed7c8"
    property color secondaryColor: "#78afff"
    property color luminousColor: "#a8f1e8"
    property real strength: 1.0
    property bool compact: false
    property bool motionEnabled: Kirigami.Units.longDuration > 1
    property bool animateIn: false

    implicitWidth: 720
    implicitHeight: 240
    clip: false

    property real reveal: animateIn && motionEnabled ? 0.0 : 1.0
    readonly property real leftX: width * (compact ? 0.04 : 0.11)
    readonly property real rightX: width - leftX
    readonly property real horizonY: height * (compact ? 0.78 : 0.82)
    readonly property real crestY: height * (compact ? 0.19 : 0.12)
    readonly property real cutHalf: Math.max(11, width * 0.013)
    readonly property real shoulder: width * (compact ? 0.18 : 0.22)

    Component.onCompleted: {
        if (root.animateIn && root.motionEnabled)
            entrance.start()
    }

    NumberAnimation {
        id: entrance
        target: root
        property: "reveal"
        from: 0.0
        to: 1.0
        duration: 320
        easing.type: Easing.OutCubic
    }

    opacity: Math.max(0, Math.min(1, reveal))
    transform: Scale {
        origin.x: root.width / 2
        origin.y: root.horizonY
        xScale: 0.97 + root.reveal * 0.03
        yScale: 0.88 + root.reveal * 0.12
    }

    // Low-alpha aperture: depth without another glass card.
    Shape {
        anchors.fill: parent
        antialiasing: true
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeWidth: 0
            fillGradient: LinearGradient {
                x1: root.width / 2
                y1: root.crestY
                x2: root.width / 2
                y2: root.horizonY
                GradientStop {
                    position: 0
                    color: Qt.rgba(root.secondaryColor.r, root.secondaryColor.g,
                                   root.secondaryColor.b, 0.07 * root.strength)
                }
                GradientStop {
                    position: 0.58
                    color: Qt.rgba(root.primaryColor.r, root.primaryColor.g,
                                   root.primaryColor.b, 0.035 * root.strength)
                }
                GradientStop {
                    position: 1
                    color: Qt.rgba(root.surfaceColor.r, root.surfaceColor.g,
                                   root.surfaceColor.b, 0)
                }
            }
            startX: root.leftX
            startY: root.horizonY
            PathCubic {
                control1X: root.leftX + root.shoulder
                control1Y: root.horizonY
                control2X: root.width * 0.31
                control2Y: root.crestY
                x: root.width / 2
                y: root.crestY
            }
            PathCubic {
                control1X: root.width * 0.69
                control1Y: root.crestY
                control2X: root.rightX - root.shoulder
                control2Y: root.horizonY
                x: root.rightX
                y: root.horizonY
            }
            PathLine { x: root.leftX; y: root.horizonY }
        }
    }

    // Broad optical under-stroke follows the exact rim without blur.
    Shape {
        anchors.fill: parent
        antialiasing: true
        opacity: 0.48 * root.strength
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: "transparent"
            strokeColor: Qt.rgba(root.primaryColor.r, root.primaryColor.g,
                                 root.primaryColor.b, 0.11)
            strokeWidth: Math.max(8, Math.round(root.height * 0.018))
            capStyle: ShapePath.RoundCap
            startX: root.leftX
            startY: root.horizonY
            PathCubic {
                control1X: root.leftX + root.shoulder
                control1Y: root.horizonY
                control2X: root.width * 0.31
                control2Y: root.crestY
                x: root.width / 2 - root.cutHalf
                y: root.crestY
            }
            PathMove {
                x: root.width / 2 + root.cutHalf
                y: root.crestY
            }
            PathCubic {
                control1X: root.width * 0.69
                control1Y: root.crestY
                control2X: root.rightX - root.shoulder
                control2Y: root.horizonY
                x: root.rightX
                y: root.horizonY
            }
        }
    }

    // Precision rim with the deliberate Tidal Cut at its crest.
    Shape {
        anchors.fill: parent
        antialiasing: true
        opacity: 0.92 * root.strength
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            fillColor: "transparent"
            strokeColor: root.primaryColor
            strokeWidth: Math.max(1.25, root.height * 0.0024)
            capStyle: ShapePath.RoundCap
            startX: root.leftX
            startY: root.horizonY
            PathCubic {
                control1X: root.leftX + root.shoulder
                control1Y: root.horizonY
                control2X: root.width * 0.31
                control2Y: root.crestY
                x: root.width / 2 - root.cutHalf
                y: root.crestY
            }
            PathMove {
                x: root.width / 2 + root.cutHalf
                y: root.crestY
            }
            PathCubic {
                control1X: root.width * 0.69
                control1Y: root.crestY
                control2X: root.rightX - root.shoulder
                control2Y: root.horizonY
                x: root.rightX
                y: root.horizonY
            }
        }
    }

    Rectangle {
        x: root.width / 2 - root.cutHalf * 0.58
        y: root.crestY - height / 2
        width: root.cutHalf * 1.16
        height: Math.max(2, root.height * 0.004)
        radius: height / 2
        color: root.secondaryColor
        opacity: 0.96 * root.strength
    }

    // Quiet threshold line fades before either arc end.
    Rectangle {
        x: root.leftX
        y: root.horizonY - height / 2
        width: root.rightX - root.leftX
        height: Math.max(1, root.height * 0.0018)
        opacity: 0.7 * root.strength
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "transparent" }
            GradientStop {
                position: 0.24
                color: Qt.rgba(root.primaryColor.r, root.primaryColor.g,
                               root.primaryColor.b, 0.55)
            }
            GradientStop {
                position: 0.5
                color: Qt.rgba(root.luminousColor.r, root.luminousColor.g,
                               root.luminousColor.b, 0.34)
            }
            GradientStop {
                position: 0.76
                color: Qt.rgba(root.secondaryColor.r, root.secondaryColor.g,
                               root.secondaryColor.b, 0.55)
            }
            GradientStop { position: 1; color: "transparent" }
        }
    }
}
