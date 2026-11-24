import QtQuick
import QtQuick.Layouts

Item {
    id: bars
    required property string phase
    required property color ink
    required property int duration
    Accessible.ignored: true

    // These are phase silhouettes, not a microphone meter. They settle once
    // per transition and do not keep repainting while a phase is held.
    readonly property var silhouette: {
        switch (phase) {
        case "listening": return [0.28, 0.65, 1.0, 0.65, 0.28];
        case "speaking": return [0.45, 1.0, 0.56, 0.83, 0.36];
        case "activating": return [0.22, 0.34, 0.48, 0.64, 0.82];
        case "thinking": return [0.30, 0.72, 0.40, 0.72, 0.30];
        case "executing": return [0.55, 0.32, 0.88, 0.32, 0.55];
        case "stopping": return [0.78, 0.62, 0.48, 0.34, 0.22];
        default: return [0.22, 0.34, 0.46, 0.34, 0.22];
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: Math.max(1, bars.width * 0.07)

        Repeater {
            model: 5

            Rectangle {
                required property int index
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredHeight: bars.height * bars.silhouette[index]
                radius: width / 2
                color: bars.ink
                Behavior on Layout.preferredHeight {
                    enabled: bars.visible && bars.duration > 0
                    NumberAnimation { duration: bars.duration; easing.type: Easing.OutCubic }
                }
            }
        }
    }
}
