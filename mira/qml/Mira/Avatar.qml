import QtQuick

// Mira's face as a small round avatar (same portal shader as the core, no animation).
Item {
    id: av
    property string style: mira.faceStyle
    property string expression: "neutral"
    property color tint: Theme.rose
    implicitWidth: 34; implicitHeight: 34
    // Qt Quick's software scene graph draws no ShaderEffect: there the face comes pre-cut.
    readonly property bool softwareScene: GraphicsInfo.api === GraphicsInfo.Software
    Image {
        id: src
        visible: false
        source: av.softwareScene ? "" : "image://mira/" + av.style + "/" + av.expression
        sourceSize: Qt.size(192, 192)
        smooth: true; mipmap: true
    }
    ShaderEffect {
        anchors.fill: parent
        visible: !av.softwareScene
        property variant faceA: src
        property variant faceB: src
        property variant eyes: src
        property variant eyesHalf: src
        property real speechW: 0
        property real mouthY: 0.665
        property variant mouthOpen: src
        property real mixT: 0
        property real blinkW: 0
        property real mouthActive: 0
        property real time: 0
        property real level: 0
        property real scan: 0
        property real feather: 0.03
        property real dim: 0
        property point parallax: Qt.point(0, 0)
        property color tint: av.tint
        fragmentShader: Qt.resolvedUrl("../../shaders/portal.frag.qsb")
    }
    Image {
        anchors.fill: parent
        visible: av.softwareScene
        source: av.softwareScene ? "image://mira/" + av.style + "/" + av.expression + "?round" : ""
        readonly property int edge: Math.max(128, Math.ceil(width / 32) * 32)
        sourceSize: Qt.size(edge, edge)
        smooth: true
    }
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.96; height: width; radius: width / 2
        color: "transparent"; border.width: 1; border.color: Qt.rgba(av.tint.r, av.tint.g, av.tint.b, 0.45)
    }
}
