pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — what the window shows while a file is dragged over it. main.qml owns the
// drop target (appDropTarget) and binds this overlay's `visible` to it.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: dropOverlay
    required property var win
    anchors.fill: parent
    anchors.margins: MoUI.Tokens.space4
    z: 100
    radius: MoUI.Tokens.radiusDialog
    color: win.canvas
    border.color: win.accent
    border.width: 2
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 560)
        spacing: MoUI.Tokens.space4
        Text {
            Layout.fillWidth: true
            text: win.local("أضف تطبيقك إلى MoOS", "Bring your app to MoOS")
            font.pixelSize: win.typePx(32)
            font.bold: true
            color: win.txt
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
        Text {
            Layout.fillWidth: true
            text: win.local("أفلت ملفًا واحدًا. نفحص نوعه ونطلب موافقتك قبل التثبيت.",
                            "Drop one file. We inspect its format and ask before installing.")
            font.pixelSize: win.typePx(15)
            color: win.txt2
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
        }
    }
}
