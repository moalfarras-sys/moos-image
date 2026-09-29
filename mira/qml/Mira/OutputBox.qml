import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// The real output of a check or command, selectable, monospace, left-to-right, bounded in height.
Rectangle {
    id: box
    property string text: ""
    property string placeholder: ""
    property bool error: false
    property int maxHeight: 360
    Layout.fillWidth: true
    Layout.preferredHeight: Math.max(64, Math.min(maxHeight, out.implicitHeight + 24))
    radius: 14
    color: Qt.rgba(0, 0, 0, 0.30)
    border.width: 1; border.color: box.error ? Qt.rgba(1, 0.36, 0.48, 0.45) : Theme.hairline
    Flickable {
        anchors.fill: parent; anchors.margins: 12
        contentHeight: out.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { width: 5 }
        TextEdit {
            id: out
            width: parent.width
            readOnly: true; selectByMouse: true
            wrapMode: TextEdit.Wrap
            text: box.text || box.placeholder
            color: box.text ? Theme.ink2 : Theme.ink3
            font.family: box.text ? Theme.mono : Theme.font
            font.pixelSize: box.text ? 12 : Theme.small
            LayoutMirroring.enabled: false
            horizontalAlignment: box.text ? Text.AlignLeft : Text.AlignHCenter
        }
    }
}
