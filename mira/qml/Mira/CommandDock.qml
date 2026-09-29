import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs

// The one place to talk or type to Mira. The microphone is the hero; the field is always ready.
Item {
    id: dock
    property alias field: input
    property string attachmentName: ""
    property string attachmentText: ""
    property real level: 0
    implicitHeight: 76 + (attachmentName !== "" ? 34 : 0)

    function submit() {
        let text = input.text.trim()
        if (text === "" && attachmentText === "") return
        if (attachmentText !== "")
            text = (text !== "" ? text + "\n\n" : "") + "[" + attachmentName + "]\n" + attachmentText
        mira.send(text)
        input.clear()
        attachmentName = ""
        attachmentText = ""
    }

    // attachment chip
    Rectangle {
        visible: dock.attachmentName !== ""
        anchors.bottom: bar.top; anchors.bottomMargin: 8
        anchors.horizontalCenter: bar.horizontalCenter
        height: 28; radius: 14
        width: chipRow.implicitWidth + 20
        color: Theme.glassStrong
        border.width: 1; border.color: Theme.hairlineStrong
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 6
            Icon { name: "clip"; size: 14; color: Theme.cyan; anchors.verticalCenter: parent.verticalCenter }
            T { text: dock.attachmentName; font.pixelSize: Theme.small; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
            Icon { name: "x"; size: 13; color: Theme.ink2; anchors.verticalCenter: parent.verticalCenter
                   TapHandler { onTapped: { dock.attachmentName = ""; dock.attachmentText = "" } } }
        }
    }

    Glass {
        id: bar
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width, 980)
        height: 72
        radius: height / 2
        tint: Theme.glassStrong
        lit: input.activeFocus

        // microphone: the primary action
        Item {
            id: micBox
            width: 72; height: 72
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            readonly property bool active: ["listening", "thinking", "speaking", "executing"].indexOf(mira.phase) >= 0
            readonly property color c: Theme.phaseColor(mira.phase === "idle" ? "listening" : mira.phase, mira.faceStyle)

            Rectangle {  // live level ring
                anchors.centerIn: parent
                width: 58 + dock.level * 16; height: width; radius: width / 2
                color: "transparent"
                border.width: 2
                border.color: Qt.rgba(micBox.c.r, micBox.c.g, micBox.c.b, micBox.active ? 0.55 : 0)
                Behavior on width { SmoothedAnimation { velocity: 120 } }
            }
            AbstractButton {
                id: mic
                anchors.centerIn: parent
                width: 54; height: 54
                hoverEnabled: true
                focusPolicy: Qt.StrongFocus
                Accessible.name: micBox.active ? mira.s.stop : mira.s.talk
                ToolTip.visible: hovered
                ToolTip.text: (micBox.active ? mira.s.stop : mira.s.talk) + "  ·  Ctrl+Space"
                ToolTip.delay: 450
                onClicked: mira.talk()
                background: Rectangle {
                    radius: width / 2
                    gradient: Gradient {
                        orientation: Gradient.Vertical
                        GradientStop { position: 0; color: micBox.active ? Qt.lighter(micBox.c, 1.15) : "#7B63FF" }
                        GradientStop { position: 1; color: micBox.active ? Qt.darker(micBox.c, 1.25) : "#2BC4E6" }
                    }
                    border.width: mic.visualFocus ? 2 : 1
                    border.color: mic.visualFocus ? "white" : Qt.rgba(1, 1, 1, 0.3)
                }
                contentItem: Item {
                    Icon { anchors.centerIn: parent; name: micBox.active ? "stop" : "mic"; size: 24; weight: 2; color: "white"
                           filled: micBox.active }
                }
                scale: down ? 0.93 : hovered ? 1.04 : 1
                Behavior on scale { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutBack } }
            }
        }

        TextField {
            id: input
            anchors.left: micBox.right
            anchors.right: tools.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 6
            height: 48
            placeholderText: mira.s.ask_placeholder
            placeholderTextColor: Theme.ink3
            color: Theme.ink
            selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
            font.family: Theme.font
            font.pixelSize: 16
            background: Item {}
            Accessible.name: mira.s.ask_placeholder
            onAccepted: dock.submit()
            Keys.onEscapePressed: { if (text !== "") clear(); else focus = false }
        }

        Row {
            id: tools
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6
            IconButton { iconName: "clip"; tip: mira.s.attach; diameter: 40; onClicked: fileDialog.open() }
            IconButton {
                iconName: "send"; tip: mira.s.send; diameter: 44
                enabled: input.text.trim() !== "" || dock.attachmentText !== ""
                active: enabled
                accent: Theme.cyan
                onClicked: dock.submit()
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: mira.s.attach
        nameFilters: ["Text (*.txt *.md *.json *.csv *.log)"]
        onAccepted: {
            const content = mira.readTextFile(selectedFile.toString())
            if (content !== "") {
                dock.attachmentText = content
                const parts = selectedFile.toString().split("/")
                dock.attachmentName = decodeURIComponent(parts[parts.length - 1])
                input.forceActiveFocus()
            }
        }
    }
}
