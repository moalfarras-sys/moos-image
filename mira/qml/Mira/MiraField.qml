import QtQuick
import QtQuick.Controls.Basic

TextField {
    id: f
    color: Theme.ink
    placeholderTextColor: Theme.ink3
    selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
    font.family: Theme.font
    font.pixelSize: Theme.body
    leftPadding: 14; rightPadding: 14
    implicitHeight: 40
    background: Rectangle {
        radius: Theme.rControl
        color: Qt.rgba(1, 1, 1, f.activeFocus ? 0.07 : 0.045)
        border.width: 1
        border.color: f.activeFocus ? Qt.rgba(0.35, 0.85, 1, 0.55) : Theme.hairline
    }
}
