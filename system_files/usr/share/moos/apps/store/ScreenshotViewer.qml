pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Mo Store — one screenshot over the whole window, whole and as large as it fits, with its caption,
// which one of how many, ←/→ (and the arrows) between them, and Escape or the close button to
// return. The picture is decoded at the size it is shown times the screen's scale.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Popup {
    id: viewer
    required property var win
    readonly property var design: win.design
    property var shots: []
    property int index: 0
    readonly property var shot: viewer.shots.length > viewer.index ? viewer.shots[viewer.index] : null
    readonly property color ink: win.inkOnDark
    x: 0
    y: 0
    width: win.width
    height: win.height
    modal: true
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape
    background: Rectangle { color: Qt.rgba(0, 0, 0, 0.88) }
    Overlay.modal: Item {}
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: viewer.win.motionEnabled ? viewer.design.motionEmphasis : 0; easing.type: Easing.OutCubic }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: viewer.win.motionEnabled ? viewer.design.motionFast : 0 }
    }

    function step(delta) {
        if (viewer.shots.length < 2) return
        viewer.index = (viewer.index + delta + viewer.shots.length) % viewer.shots.length
    }

    Item {
        id: stage
        anchors.fill: parent
        focus: true
        LayoutMirroring.enabled: viewer.win.rtl
        LayoutMirroring.childrenInherit: true
        Accessible.role: Accessible.Dialog
        Accessible.name: viewer.win.local("لقطة شاشة ", "Screenshot ") + (viewer.index + 1) + " / " + viewer.shots.length
        Keys.onLeftPressed: viewer.win.rtl ? viewer.step(1) : viewer.step(-1)
        Keys.onRightPressed: viewer.win.rtl ? viewer.step(-1) : viewer.step(1)
        Keys.onEscapePressed: viewer.close()

        Image {
            id: picture
            anchors.fill: parent
            anchors.leftMargin: viewer.win.fs(88)
            anchors.rightMargin: viewer.win.fs(88)
            anchors.topMargin: viewer.win.fs(72)
            anchors.bottomMargin: viewer.win.fs(96)
            source: viewer.shot ? viewer.win.pictureSource(viewer.shot.full || viewer.shot.thumb) : ""
            sourceSize.width: Math.ceil(width * Math.max(1, Screen.devicePixelRatio))
            sourceSize.height: Math.ceil(height * Math.max(1, Screen.devicePixelRatio))
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            smooth: true
            mipmap: true
        }
        Glyph {
            win: viewer.win
            anchors.centerIn: parent
            width: viewer.win.fs(40)
            height: width
            name: "image"
            tint: viewer.ink
            opacity: 0.5
            visible: picture.status !== Image.Ready
        }

        RowLayout {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: viewer.design.space5
            spacing: viewer.design.space3
            Text {
                Layout.fillWidth: true
                text: viewer.win.ltr((viewer.index + 1) + " / " + viewer.shots.length)
                color: viewer.ink
                font.family: viewer.win.uiFont
                font.pixelSize: viewer.win.typePx(14)
                font.weight: Font.DemiBold
            }
            CircleButton {
                win: viewer.win
                onGlass: true
                glassInk: viewer.ink
                glyph: "close"
                accessibleName: viewer.win.local("إغلاق", "Close")
                onActivated: viewer.close()
            }
        }

        CircleButton {
            win: viewer.win
            visible: viewer.shots.length > 1
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: viewer.design.space5
            size: viewer.win.fs(48)
            onGlass: true
            glassInk: viewer.ink
            glyph: viewer.win.rtl ? "arrow" : "arrow-back"
            accessibleName: viewer.win.local("السابقة", "Previous")
            onActivated: viewer.step(-1)
        }
        CircleButton {
            win: viewer.win
            visible: viewer.shots.length > 1
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: viewer.design.space5
            size: viewer.win.fs(48)
            onGlass: true
            glassInk: viewer.ink
            glyph: viewer.win.rtl ? "arrow-back" : "arrow"
            accessibleName: viewer.win.local("التالية", "Next")
            onActivated: viewer.step(1)
        }

        Text {
            anchors.bottom: parent.bottom
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottomMargin: viewer.design.space6
            width: Math.min(parent.width - viewer.win.fs(176), viewer.win.fs(900))
            visible: text !== ""
            text: viewer.shot && viewer.shot.caption ? viewer.shot.caption : ""
            color: viewer.win.tint(viewer.ink, 0.9)
            font.family: viewer.win.uiFont
            font.pixelSize: viewer.win.typePx(15)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
    }
}
