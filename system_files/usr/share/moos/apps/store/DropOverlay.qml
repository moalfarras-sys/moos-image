pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.moos.ui as MoUI

// Mo Store — what the window shows while a file is dragged over it: one invitation to let go, and
// the promise that nothing installs before MoOS has looked at the file and asked. main.qml owns the
// drop target (appDropTarget) and binds this overlay's `visible` to it.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: dropOverlay
    objectName: "dropOverlay"
    required property var win
    anchors.fill: parent
    z: 100
    color: win.tint(win.canvas, 0.97)

    Rectangle {
        anchors.fill: parent
        anchors.margins: MoUI.Tokens.space5
        radius: MoUI.Tokens.radiusDialog
        color: dropOverlay.win.tint(dropOverlay.win.accent, 0.08)
        border.color: dropOverlay.win.accent
        border.width: 2

        ColumnLayout {
            anchors.centerIn: parent
            width: Math.min(parent.width - dropOverlay.win.fs(48), dropOverlay.win.fs(560))
            spacing: MoUI.Tokens.space4
            LayoutMirroring.enabled: dropOverlay.win.rtl
            LayoutMirroring.childrenInherit: true
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: dropOverlay.win.fs(88)
                Layout.preferredHeight: dropOverlay.win.fs(88)
                radius: width / 2
                color: dropOverlay.win.tint(dropOverlay.win.accent, 0.16)
                Glyph {
                    win: dropOverlay.win
                    anchors.centerIn: parent
                    width: dropOverlay.win.fs(44)
                    height: width
                    name: "upload"
                    tint: dropOverlay.win.accent
                }
            }
            Text {
                Layout.fillWidth: true
                text: dropOverlay.win.local("أضف تطبيقك إلى MoOS", "Bring your app to MoOS")
                font.family: dropOverlay.win.uiFont
                font.pixelSize: dropOverlay.win.typePx(32)
                font.weight: Font.Bold
                color: dropOverlay.win.txt
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
            Text {
                Layout.fillWidth: true
                text: dropOverlay.win.local("أفلت ملفًا واحدًا. يفحص MoOS نوعه ويسألك قبل التثبيت.",
                                            "Drop one file. MoOS inspects what it is and asks before installing.")
                font.family: dropOverlay.win.uiFont
                font.pixelSize: dropOverlay.win.typePx(15)
                color: dropOverlay.win.txt2
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
}
