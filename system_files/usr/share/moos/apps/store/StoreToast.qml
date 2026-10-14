pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// Mo Store — a short message near the foot of the window, read out to a screen reader. main.qml's
// flash() calls show(); the toast closes itself after a few seconds.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: toast
    required property var win
    readonly property var design: win.design

    function show(message) {
        toastLabel.text = message
        toast.open()
        toastTimer.restart()
    }

    x: (win.width - width) / 2
    y: win.height - height - win.fs(112)
    width: Math.min(toastLabel.implicitWidth + design.space5 * 2, win.width - win.fs(64))
    height: win.fs(46)
    padding: 0
    modal: false
    focus: false
    closePolicy: Popup.NoAutoClose
    background: Rectangle {
        radius: height / 2
        color: toast.win.txt
        SoftShadow { win: toast.win; radius: parent.radius; strength: 1.6 }
    }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: toast.win.motionEnabled ? toast.design.motionPress : 0 }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: toast.win.motionEnabled ? toast.design.motionPress : 0 }
    }
    Text {
        id: toastLabel
        anchors.centerIn: parent
        width: parent.width - toast.design.space5 * 2
        horizontalAlignment: Text.AlignHCenter
        text: "Mo Store"
        color: toast.win.canvas
        font.family: toast.win.uiFont
        font.pixelSize: toast.win.typePx(14)
        font.weight: Font.Medium
        elide: Text.ElideRight
        Accessible.role: Accessible.AlertMessage
        Accessible.name: toastLabel.text
    }
    Timer { id: toastTimer; interval: 3200; onTriggered: toast.close() }
}
