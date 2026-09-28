import QtQuick
import QtQuick.Controls.Basic

Slider {
    id: sl
    property color accent: Theme.cyan
    hoverEnabled: true
    implicitHeight: 28
    background: Rectangle {
        x: sl.leftPadding; y: sl.topPadding + sl.availableHeight / 2 - height / 2
        width: sl.availableWidth; height: 6; radius: 3
        color: Qt.rgba(1, 1, 1, 0.09)
        opacity: sl.enabled ? 1 : 0.4
        Rectangle {
            width: sl.visualPosition * parent.width; height: parent.height; radius: 3
            x: sl.mirrored ? parent.width - width : 0
            gradient: Gradient { orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.rgba(sl.accent.r, sl.accent.g, sl.accent.b, 0.55) }
                GradientStop { position: 1; color: sl.accent } }
        }
    }
    handle: Rectangle {
        x: sl.leftPadding + sl.visualPosition * (sl.availableWidth - width)
        y: sl.topPadding + sl.availableHeight / 2 - height / 2
        width: 18; height: 18; radius: 9
        color: "white"
        border.width: sl.visualFocus ? 2 : 0
        border.color: Theme.cyan
        visible: sl.enabled
        scale: sl.pressed ? 1.15 : sl.hovered ? 1.07 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }
}
