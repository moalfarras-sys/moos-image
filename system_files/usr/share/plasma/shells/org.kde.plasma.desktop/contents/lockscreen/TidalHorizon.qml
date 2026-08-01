/*
    Tidal Horizon Portal — the shared MoOS doorway motif.

    This component is intentionally pure geometry. It contains no timer, loop,
    shader, hard-coded palette, logo, or input handler. Splash, login, lock and
    logout supply the same semantic colours and decide whether a single finite
    reveal is appropriate for their lifecycle.

    The signature is one rising horizon: a cubic arc whose crest is interrupted
    by a short "Tidal Cut". The aperture below it is a low-alpha depth field,
    not a glass card. At any scale the one-pixel horizon remains precise while
    the broad under-stroke provides optical depth without blur.

    SPDX-License-Identifier: GPL-2.0-or-later
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Shapes

Item {
    id: portal

    property color accentA: "#4ED7C8"
    property color accentB: "#78AFFF"
    property color ink: "#E8F1EF"
    property color surface: "#1D2529"
    property real reveal: 1
    property real intensity: 1
    property bool compact: false

    readonly property real leftX: width * (compact ? 0.04 : 0.11)
    readonly property real rightX: width - leftX
    readonly property real horizonY: height * (compact ? 0.78 : 0.82)
    readonly property real crestY: height * (compact ? 0.19 : 0.12)
    readonly property real cutHalf: Math.max(11, width * 0.013)
    readonly property real shoulder: width * (compact ? 0.18 : 0.22)

    opacity: Math.max(0, Math.min(1, reveal))
    transform: Scale {
        origin.x: portal.width / 2
        origin.y: portal.horizonY
        xScale: 0.97 + portal.reveal * 0.03
        yScale: 0.88 + portal.reveal * 0.12
    }

    // The aperture: a low-alpha depth field contained by the one horizon.
    Shape {
        anchors.fill: parent
        antialiasing: true

        ShapePath {
            strokeWidth: 0
            fillGradient: LinearGradient {
                x1: portal.width / 2
                y1: portal.crestY
                x2: portal.width / 2
                y2: portal.horizonY
                GradientStop {
                    position: 0
                    color: Qt.rgba(portal.accentB.r, portal.accentB.g,
                                   portal.accentB.b, 0.07 * portal.intensity)
                }
                GradientStop {
                    position: 0.58
                    color: Qt.rgba(portal.accentA.r, portal.accentA.g,
                                   portal.accentA.b, 0.035 * portal.intensity)
                }
                GradientStop {
                    position: 1
                    color: Qt.rgba(portal.surface.r, portal.surface.g,
                                   portal.surface.b, 0)
                }
            }
            startX: portal.leftX
            startY: portal.horizonY
            PathCubic {
                control1X: portal.leftX + portal.shoulder
                control1Y: portal.horizonY
                control2X: portal.width * 0.31
                control2Y: portal.crestY
                x: portal.width / 2
                y: portal.crestY
            }
            PathCubic {
                control1X: portal.width * 0.69
                control1Y: portal.crestY
                control2X: portal.rightX - portal.shoulder
                control2Y: portal.horizonY
                x: portal.rightX
                y: portal.horizonY
            }
            PathLine { x: portal.leftX; y: portal.horizonY }
        }
    }

    // Optical depth under the rim. It follows the exact same horizon and never
    // becomes a second decorative orbit.
    Shape {
        anchors.fill: parent
        antialiasing: true
        opacity: 0.48 * portal.intensity

        ShapePath {
            fillColor: "transparent"
            strokeColor: Qt.rgba(portal.accentA.r, portal.accentA.g,
                                 portal.accentA.b, 0.11)
            strokeWidth: Math.max(8, Math.round(portal.height * 0.018))
            capStyle: ShapePath.RoundCap
            startX: portal.leftX
            startY: portal.horizonY
            PathCubic {
                control1X: portal.leftX + portal.shoulder
                control1Y: portal.horizonY
                control2X: portal.width * 0.31
                control2Y: portal.crestY
                x: portal.width / 2 - portal.cutHalf
                y: portal.crestY
            }
            PathMove {
                x: portal.width / 2 + portal.cutHalf
                y: portal.crestY
            }
            PathCubic {
                control1X: portal.width * 0.69
                control1Y: portal.crestY
                control2X: portal.rightX - portal.shoulder
                control2Y: portal.horizonY
                x: portal.rightX
                y: portal.horizonY
            }
        }
    }

    // The precision rim. The deliberate break at the crest is the Tidal Cut.
    Shape {
        anchors.fill: parent
        antialiasing: true
        opacity: 0.92 * portal.intensity

        ShapePath {
            fillColor: "transparent"
            strokeColor: portal.accentA
            strokeWidth: Math.max(1.25, portal.height * 0.0024)
            capStyle: ShapePath.RoundCap
            startX: portal.leftX
            startY: portal.horizonY
            PathCubic {
                control1X: portal.leftX + portal.shoulder
                control1Y: portal.horizonY
                control2X: portal.width * 0.31
                control2Y: portal.crestY
                x: portal.width / 2 - portal.cutHalf
                y: portal.crestY
            }
            PathMove {
                x: portal.width / 2 + portal.cutHalf
                y: portal.crestY
            }
            PathCubic {
                control1X: portal.width * 0.69
                control1Y: portal.crestY
                control2X: portal.rightX - portal.shoulder
                control2Y: portal.horizonY
                x: portal.rightX
                y: portal.horizonY
            }
        }
    }

    // The cut is sealed by a short secondary-colour threshold: one unmistakable
    // accent, not another ring.
    Rectangle {
        x: portal.width / 2 - portal.cutHalf * 0.58
        y: portal.crestY - height / 2
        width: portal.cutHalf * 1.16
        height: Math.max(2, portal.height * 0.004)
        radius: height / 2
        color: portal.accentB
        opacity: 0.96 * portal.intensity
    }

    // A quiet ground line makes the portal read as a threshold rather than a
    // floating badge. It fades before reaching either arc end.
    Rectangle {
        x: portal.leftX
        y: portal.horizonY - height / 2
        width: portal.rightX - portal.leftX
        height: Math.max(1, portal.height * 0.0018)
        opacity: 0.7 * portal.intensity
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "transparent" }
            GradientStop {
                position: 0.24
                color: Qt.rgba(portal.accentA.r, portal.accentA.g,
                               portal.accentA.b, 0.55)
            }
            GradientStop {
                position: 0.5
                color: Qt.rgba(portal.ink.r, portal.ink.g, portal.ink.b, 0.34)
            }
            GradientStop {
                position: 0.76
                color: Qt.rgba(portal.accentB.r, portal.accentB.g,
                               portal.accentB.b, 0.55)
            }
            GradientStop { position: 1; color: "transparent" }
        }
    }
}
