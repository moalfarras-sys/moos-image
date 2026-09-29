import QtQuick
import QtQuick.Controls.Basic

Switch {
    id: sw
    property color accent: Theme.cyan
    hoverEnabled: true
    padding: 0
    indicator: Rectangle {
        implicitWidth: 46; implicitHeight: 26
        x: sw.mirrored ? 0 : sw.width - width
        y: (sw.height - height) / 2
        radius: 13
        color: sw.checked ? Qt.rgba(sw.accent.r, sw.accent.g, sw.accent.b, 0.78) : Qt.rgba(1, 1, 1, 0.07)
        border.width: 1
        border.color: sw.visualFocus ? "white" : sw.checked ? Qt.rgba(sw.accent.r, sw.accent.g, sw.accent.b, 0.95) : Theme.hairlineStrong
        opacity: sw.enabled ? 1 : 0.4
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle {
            width: 20; height: 20; radius: 10
            y: 3
            x: (sw.checked !== sw.mirrored) ? parent.width - width - 3 : 3
            color: sw.checked ? "white" : Qt.rgba(0.8, 0.82, 0.92, 0.75)
            Behavior on x { SpringAnimation { spring: 4; damping: 0.4; epsilon: 0.3 } }
        }
    }
    contentItem: T {
        text: sw.text
        leftPadding: sw.mirrored ? sw.indicator.width + 12 : 0
        rightPadding: sw.mirrored ? 0 : sw.indicator.width + 12
        verticalAlignment: Text.AlignVCenter
        color: sw.enabled ? Theme.ink : Theme.ink3
    }
}
