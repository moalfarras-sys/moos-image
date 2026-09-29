import QtQuick

// Mira's face as a small round avatar (same portal shader as the core, no animation).
Item {
    id: av
    property string style: mira.faceStyle
    property string expression: "neutral"
    property color tint: Theme.rose
    implicitWidth: 34; implicitHeight: 34
    Image {
        id: src
        visible: false
        source: "image://mira/" + av.style + "/" + av.expression
        sourceSize: Qt.size(192, 192)
        smooth: true; mipmap: true
    }
    ShaderEffect {
        anchors.fill: parent
        property variant faceA: src
        property variant faceB: src
        property variant eyes: src
        property variant mouthRound: src
        property variant mouthOpen: src
        property real mixT: 0
        property real blinkW: 0
        property real roundW: 0
        property real openW: 0
        property real time: 0
        property real level: 0
        property real scan: 0
        property real feather: 0.03
        property real dim: 0
        property point parallax: Qt.point(0, 0)
        property color tint: av.tint
        fragmentShader: Qt.resolvedUrl("../../shaders/portal.frag.qsb")
    }
    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.96; height: width; radius: width / 2
        color: "transparent"; border.width: 1; border.color: Qt.rgba(av.tint.r, av.tint.g, av.tint.b, 0.45)
    }
}
