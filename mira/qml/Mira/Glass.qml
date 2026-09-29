import QtQuick

// Liquid-glass surface: tinted fallback fill, one hairline, one inner highlight.
// Works without blur; `lit` adds the focus/active edge.
Rectangle {
    id: root
    property bool lit: false
    property color tint: Theme.glass
    property color edge: lit ? Qt.rgba(0.40, 0.85, 1.0, 0.45) : Theme.hairline
    radius: Theme.rPanel
    color: tint
    border.width: 1
    border.color: edge
    Behavior on border.color { ColorAnimation { duration: Theme.normal } }
    Behavior on color { ColorAnimation { duration: Theme.normal } }
    // inner top highlight (glass thickness)
    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: parent.radius - 1
        color: "transparent"
        border.width: 1
        border.color: Theme.innerLight
        opacity: 0.9
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.045) }
            GradientStop { position: 0.35; color: Qt.rgba(1, 1, 1, 0.0) }
        }
    }
}
