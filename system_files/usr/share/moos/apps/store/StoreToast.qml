pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

// Mo Store — a short message at the bottom of the window. main.qml's flash() calls
// show(); the toast closes itself after 2.5 s.
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
    y: win.height - 112
    width: Math.min(toastLabel.implicitWidth + 38, win.width - 60)
    height: 44
    padding: 0
    modal: false
    closePolicy: Popup.NoAutoClose
    background: Rectangle {
        radius: design.radiusCard
        color: win.raised
        border.width: 1
        border.color: win.accent
    }
    Text {
        id: toastLabel
        anchors.centerIn: parent
        width: parent.width - 22
        horizontalAlignment: Text.AlignHCenter
        text: "Mo Store"
        color: win.txt
        font.family: win.uiFont
        font.pixelSize: win.typePx(11)
        elide: Text.ElideRight
    }
    Timer { id: toastTimer; interval: 2500; onTriggered: toast.close() }
}
