import QtQuick
import QtQuick.Shapes

// The dark space behind everything. Rendered at half resolution (it is all low frequency),
// and brightened a little around Mira's core by her current state.
Item {
    id: root
    property real clock: 0
    property real energy: 0
    property point focusPoint: Qt.point(0.5, 0.45)
    property color accent: Theme.violet
    property color accent2: Theme.cyan
    // Qt Quick's software scene graph draws no ShaderEffect: there the space is one still glow in
    // the design's own colours, so a phase change never repaints the whole window.
    readonly property bool softwareScene: GraphicsInfo.api === GraphicsInfo.Software
    Behavior on energy { NumberAnimation { duration: Theme.emphasized } }
    Behavior on accent { ColorAnimation { duration: 900 } }
    Behavior on accent2 { ColorAnimation { duration: 900 } }

    Rectangle { anchors.fill: parent; color: Theme.bg0 }

    Shape {
        id: still
        anchors.fill: parent
        visible: root.softwareScene
        ShapePath {
            strokeColor: "transparent"
            fillGradient: RadialGradient {
                centerX: root.focusPoint.x * still.width; centerY: root.focusPoint.y * still.height
                focalX: centerX; focalY: centerY
                centerRadius: Math.max(still.width, still.height) * 0.6
                GradientStop { position: 0.0; color: Qt.rgba(Theme.violet.r, Theme.violet.g, Theme.violet.b, 0.16) }
                GradientStop { position: 0.45; color: Qt.rgba(Theme.cyan.r, Theme.cyan.g, Theme.cyan.b, 0.05) }
                GradientStop { position: 1.0; color: "transparent" }
            }
            startX: 0; startY: 0
            PathLine { x: still.width; y: 0 }
            PathLine { x: still.width; y: still.height }
            PathLine { x: 0; y: still.height }
            PathLine { x: 0; y: 0 }
        }
    }

    ShaderEffect {
        id: fx
        anchors.fill: parent
        visible: !root.softwareScene
        property real time: root.clock
        property real aspect: width / Math.max(1, height)
        property real energy: root.energy
        property point focusPt: root.focusPoint
        property color accent: root.accent
        property color accent2: root.accent2
        fragmentShader: Qt.resolvedUrl("../../shaders/nebula.frag.qsb")
        layer.enabled: !root.softwareScene
        layer.textureSize: Qt.size(Math.max(1, Math.round(width / 2)), Math.max(1, Math.round(height / 2)))
        layer.smooth: true
    }
}
