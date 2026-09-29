import QtQuick

// The dark space behind everything. Rendered at half resolution (it is all low frequency),
// and brightened a little around Mira's core by her current state.
Item {
    id: root
    property real clock: 0
    property real energy: 0
    property point focusPoint: Qt.point(0.5, 0.45)
    property color accent: Theme.violet
    property color accent2: Theme.cyan
    Behavior on energy { NumberAnimation { duration: Theme.emphasized } }
    Behavior on accent { ColorAnimation { duration: 900 } }
    Behavior on accent2 { ColorAnimation { duration: 900 } }

    Rectangle { anchors.fill: parent; color: Theme.bg0 }

    ShaderEffect {
        id: fx
        anchors.fill: parent
        property real time: root.clock
        property real aspect: width / Math.max(1, height)
        property real energy: root.energy
        property point focusPt: root.focusPoint
        property color accent: root.accent
        property color accent2: root.accent2
        fragmentShader: Qt.resolvedUrl("../../shaders/nebula.frag.qsb")
        layer.enabled: true
        layer.textureSize: Qt.size(Math.max(1, Math.round(width / 2)), Math.max(1, Math.round(height / 2)))
        layer.smooth: true
    }
}
