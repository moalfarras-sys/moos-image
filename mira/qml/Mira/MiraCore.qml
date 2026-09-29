import QtQuick
import QtQuick.Shapes

// Mira's presence: the original face (rose or holographic) inside a portal of light.
// The ring's colour, energy and motion say what Mira is doing; the face says how she feels.
Item {
    id: core
    property string phase: "idle"          // idle listening thinking speaking executing error offline
    property string faceStyle: "rose"
    property string mood: "neutral"
    property real level: 0                  // live mic / voice energy 0..1
    property real clock: 0                  // shared animation clock (seconds)
    property bool motion: true
    property bool hovered: hover.hovered
    signal activated()
    signal faceToggleRequested()

    implicitWidth: 520
    implicitHeight: 520
    Accessible.role: Accessible.Button
    Accessible.name: qsTr("Mira")
    activeFocusOnTab: true
    Keys.onReturnPressed: core.activated()
    Keys.onSpacePressed: core.activated()

    readonly property real portalSize: Math.min(width, height) * 0.66
    // Qt Quick's software scene graph (every MoOS ARM session; /usr/bin/mira where no real GPU
    // exists) draws no ShaderEffect at all. There the portal is the still face, already cut to the
    // circle by the face provider, inside a static ring of her colour.
    readonly property bool softwareScene: GraphicsInfo.api === GraphicsInfo.Software
    readonly property real still: 1 - core.wOff * 0.6     // the ring's strength there (dim offline)
    property real lvl: level
    Behavior on lvl { SmoothedAnimation { velocity: 3.2; duration: -1 } }

    // animated state weights so every state change blends instead of snapping
    property real wThink: phase === "thinking" ? 1 : 0
    property real wExec: phase === "executing" ? 1 : 0
    property real wErr: phase === "error" ? 1 : 0
    property real wOff: phase === "offline" ? 1 : 0
    property real wHover: hovered ? 1 : 0
    Behavior on wThink { NumberAnimation { duration: Theme.emphasized; easing.type: Easing.OutCubic } }
    Behavior on wExec { NumberAnimation { duration: Theme.emphasized; easing.type: Easing.OutCubic } }
    Behavior on wErr { NumberAnimation { duration: Theme.emphasized } }
    Behavior on wOff { NumberAnimation { duration: Theme.emphasized } }
    Behavior on wHover { NumberAnimation { duration: Theme.normal } }
    property color cA: Theme.phaseColor(phase, faceStyle)
    property color cB: Theme.phaseColor2(phase, faceStyle)
    Behavior on cA { ColorAnimation { duration: Theme.emphasized } }
    Behavior on cB { ColorAnimation { duration: Theme.emphasized } }

    // breathing and pointer-follow (springs settle; nothing runs when motion is off)
    property real breathe: motion ? Math.sin(clock * 2 * Math.PI / 3.23) : 0
    property point look: Qt.point(0, 0)
    property real lookX: look.x
    property real lookY: look.y
    Behavior on lookX { SpringAnimation { spring: 2.2; damping: 0.32; epsilon: 0.002 } }
    Behavior on lookY { SpringAnimation { spring: 2.2; damping: 0.32; epsilon: 0.002 } }

    // ── aura ─────────────────────────────────────────────────────────
    ShaderEffect {
        id: aura
        anchors.centerIn: parent
        width: core.portalSize * 1.5
        height: width
        property real time: core.clock
        property real level: core.lvl
        property real radius: 0.5 / 1.5 * 0.94
        property real think: core.wThink
        property real exec: core.wExec
        property real err: core.wErr
        property real off: core.wOff
        property real hover: core.wHover
        property color colorA: core.cA
        property color colorB: core.cB
        fragmentShader: Qt.resolvedUrl("../../shaders/aura.frag.qsb")
        blending: true
        visible: !core.softwareScene
    }
    Shape {
        id: stillAura
        visible: core.softwareScene
        anchors.centerIn: parent
        width: core.portalSize * 1.5
        height: width
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: stillAura.width / 2; centerY: stillAura.height / 2
                focalX: centerX; focalY: centerY
                centerRadius: stillAura.width / 2
                // the portal's edge sits at 0.627 of this radius: a bright line there, light beyond
                GradientStop { position: 0.58; color: Qt.rgba(core.cA.r, core.cA.g, core.cA.b, 0.0) }
                GradientStop { position: 0.622; color: Qt.rgba(core.cA.r, core.cA.g, core.cA.b, 0.85 * core.still) }
                GradientStop { position: 0.640; color: Qt.rgba(core.cB.r, core.cB.g, core.cB.b, 0.70 * core.still) }
                GradientStop { position: 0.675; color: Qt.rgba(core.cB.r, core.cB.g, core.cB.b, 0.22 * core.still) }
                GradientStop { position: 0.80; color: Qt.rgba(core.cA.r, core.cA.g, core.cA.b, 0.07 * core.still) }
                GradientStop { position: 1.0; color: "transparent" }
            }
            PathAngleArc {
                centerX: stillAura.width / 2; centerY: stillAura.height / 2
                radiusX: stillAura.width / 2; radiusY: radiusX
                startAngle: 0; sweepAngle: 360
            }
        }
    }

    // ── face portal ──────────────────────────────────────────────────
    Item {
        id: portalBox
        width: core.portalSize
        height: width
        scale: 1.0 + 0.006 * core.breathe + 0.02 * core.lvl + (core.hovered ? 0.012 : 0)
        x: (parent.width - width) / 2 + (core.motion ? width * 0.006 * Math.sin(core.clock * 2 * Math.PI / 6.53) : 0)
        y: (parent.height - height) / 2 + (core.motion ? height * 0.005 * Math.sin(core.clock * 2 * Math.PI / 3.53 + 1.3) : 0)
        rotation: core.motion ? 0.8 * Math.sin(core.clock * 2 * Math.PI / 5.53 + 0.4) : 0
        transform: Rotation {
            origin.x: portalBox.width / 2; origin.y: portalBox.height / 2
            axis { x: -core.lookY; y: core.lookX; z: 0 }
            angle: core.motion ? 5 * Math.min(1, Math.sqrt(core.lookX * core.lookX + core.lookY * core.lookY)) : 0
        }

        FaceFrames {
            id: frames
            style: core.faceStyle
            expression: core.expression
            phase: core.phase
            speaking: core.phase === "speaking"
            level: core.level
            motion: core.motion
        }

        ShaderEffect {
            anchors.fill: parent
            property variant faceA: frames.a
            property variant faceB: frames.b
            property variant eyes: frames.eyes
            property variant mouthRound: frames.mouthRound
            property variant mouthOpen: frames.mouthOpen
            property real mixT: frames.mix
            property real blinkW: frames.blinkW
            property real roundW: frames.roundW
            property real openW: frames.openW
            property real time: core.clock
            property real level: core.lvl
            property real scan: core.wThink * 0.9 + core.wExec * 0.5
            property real feather: 0.05
            property real dim: core.wOff * 0.35
            property point parallax: Qt.point(core.lookX, core.lookY)
            property color tint: core.cA
            fragmentShader: Qt.resolvedUrl("../../shaders/portal.frag.qsb")
            visible: !core.softwareScene
        }

        Image {
            anchors.fill: parent
            visible: core.softwareScene
            source: core.softwareScene ? "image://mira/" + core.faceStyle + "/" + core.expression + "?round" : ""
            readonly property int edge: Math.max(128, Math.ceil(width / 32) * 32)
            sourceSize: Qt.size(edge, edge)
            smooth: true
            opacity: 1 - core.wOff * 0.35
        }
        Shape {
            id: stillRim
            visible: core.softwareScene
            anchors.fill: parent
            ShapePath {
                strokeColor: "transparent"
                fillGradient: RadialGradient {
                    centerX: stillRim.width / 2; centerY: stillRim.height / 2
                    focalX: centerX; focalY: centerY
                    centerRadius: stillRim.width / 2
                    GradientStop { position: 0.74; color: "transparent" }
                    GradientStop { position: 0.90; color: Qt.rgba(core.cA.r, core.cA.g, core.cA.b, 0.30) }
                    GradientStop { position: 0.95; color: "transparent" }
                }
                PathAngleArc {
                    centerX: stillRim.width / 2; centerY: stillRim.height / 2
                    radiusX: stillRim.width / 2; radiusY: radiusX
                    startAngle: 0; sweepAngle: 360
                }
            }
        }
    }

    // expression = phase first, then the mood Mira is in
    readonly property string expression: {
        switch (phase) {
        case "listening": return "attentive"
        case "thinking": return "thinking"
        case "executing": return "curious"
        case "error": return "sad"
        case "offline": return "sleepy"
        default: return mood || "neutral"
        }
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
        onPointChanged: {
            if (!core.motion) return
            const cx = core.width / 2, cy = core.height / 2
            const nx = (point.position.x - cx) / (core.width / 2)
            const ny = (point.position.y - cy) / (core.height / 2)
            core.look = Qt.point(Math.max(-1, Math.min(1, nx)), Math.max(-1, Math.min(1, ny)))
        }
        onHoveredChanged: if (!hovered) core.look = Qt.point(0, 0)
    }
    TapHandler {
        onTapped: core.activated()
        onDoubleTapped: core.faceToggleRequested()
    }

    // focus ring for keyboard users
    Rectangle {
        anchors.centerIn: parent
        width: core.portalSize + 18; height: width; radius: width / 2
        color: "transparent"
        border.width: 2
        border.color: Theme.cyan
        visible: core.activeFocus
        opacity: 0.8
    }
}
