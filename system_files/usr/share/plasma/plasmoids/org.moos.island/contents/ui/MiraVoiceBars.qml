import QtQuick
import QtQuick.Layouts

Item {
    id: bars
    required property string phase
    required property color ink
    required property int duration

    // These are phase silhouettes, not a microphone meter. They settle once
    // per transition and do not keep repainting while a phase is held.
    readonly property var silhouette: {
        switch (phase) {
        case "listening": return [0.28, 0.65, 1.0, 0.65, 0.28];
        case "speaking": return [0.45, 1.0, 0.56, 0.83, 0.36];
        case "thinking":
        case "executing":
        case "activating": return [0.25, 0.48, 0.64, 0.48, 0.25];
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
