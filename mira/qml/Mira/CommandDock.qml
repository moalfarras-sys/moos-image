import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs

// The one place to talk or type to Mira. The microphone is the hero; the composer is always ready.
// Enter sends, Shift+Enter starts a new line, and the composer grows to five lines before it
// scrolls. While an input method is still composing a word, Enter belongs to the input method.
// The bar grows UPWARD over the content: the dock's own height stays that of one line (plus an
// attached file's chip), so Mira's stage above never shrinks or jumps while the owner types.
Item {
    id: dock
    objectName: "commandDock"
    property alias field: input
    property string attachmentName: ""
    property string attachmentText: ""
    property real level: 0
    readonly property int maxLength: 6000             // what the controller accepts in one message
    readonly property int maxLines: 5
    readonly property real barBase: 72                // the one-line bar
    readonly property real lineHeight: Math.ceil(metrics.lineSpacing)
    readonly property real editorHeight: Math.min(input.implicitHeight, lineHeight * maxLines + input.topPadding + input.bottomPadding)
    readonly property bool multiline: input.lineCount > 1
    // What one Enter would send: the typed words and the attached file, exactly as submit() joins them.
    readonly property int typedLength: input.text.trim().length
    readonly property int composedLength: attachmentText === "" ? typedLength
                                          : typedLength + (typedLength > 0 ? 2 : 0) + attachmentName.length + 3 + attachmentText.length
    readonly property bool tooLong: composedLength > maxLength
    readonly property bool fileTooLong: tooLong && attachmentText !== "" && typedLength <= maxLength
    readonly property bool counting: composedLength > maxLength - 1000
    // how far the bar reaches above the dock (the window may keep the conversation's end above it)
    readonly property real growth: Math.max(0, bar.height - barBase)
    property bool refused: false                      // the last Enter was over the limit
    // how far ANY of the composer's own surfaces (the grown bar, the file chip, the count pill) reach
    // above the dock's top: an overlay placed above the dock keeps clear of all of them
    readonly property real reach: Math.max(0, -Math.min(bar.y, chip.visible ? chip.y : bar.y,
                                                        counter.visible ? counter.y : bar.y))
    // a narrow bar has no room for the file chip and the count side by side: the count sits above it
    readonly property bool stacked: attachmentName !== "" && counter.visible && bar.width / 2 - 70 < counter.width + 30
    implicitHeight: barBase + (attachmentName !== "" ? 34 : 0)

    function submit() {
        let text = input.text.trim()
        if (text === "" && attachmentText === "") return
        if (attachmentText !== "")
            text = (text !== "" ? text + "\n\n" : "") + "[" + attachmentName + "]\n" + attachmentText
        if (text.length > maxLength) {        // kept, not sent: the owner shortens it first
            refused = true
            return
        }
        mira.send(text)
        input.clear()
        attachmentName = ""
        attachmentText = ""
    }
    function cursorToEnd() { input.cursorPosition = input.length }

    FontMetrics { id: metrics; font: input.font }

    // A page's words put in the composer (host.prefill): the owner continues after them, not before.
    Connections {
        target: mira
        function onPrefill(text) { Qt.callLater(dock.cursorToEnd) }
    }

    // attachment chip (rides on the bar's top edge as the bar grows)
    Rectangle {
        id: chip
        objectName: "attachmentChip"
        visible: dock.attachmentName !== ""
        anchors.bottom: bar.top; anchors.bottomMargin: 8
        anchors.horizontalCenter: bar.horizontalCenter
        height: 28; radius: 14
        // centred on the bar, clear of the counter pill at the send side (or under it when narrow)
        readonly property real room: counter.visible && !dock.stacked ? Math.max(140, bar.width - 2 * (counter.width + 30))
                                                                      : bar.width - 36
        width: chipRow.implicitWidth + 20
        color: Theme.glassStrong
        border.width: 1; border.color: dock.fileTooLong ? Qt.rgba(1, 0.36, 0.48, 0.6) : Theme.hairlineStrong
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 6
            Icon { name: "clip"; size: 14; color: dock.fileTooLong ? Theme.danger : Theme.cyan; anchors.verticalCenter: parent.verticalCenter }
            T { text: dock.attachmentName; font.pixelSize: Theme.small; wrapMode: Text.NoWrap; elide: Text.ElideMiddle
                width: Math.min(implicitWidth, chip.room - 20 - 45); anchors.verticalCenter: parent.verticalCenter }
            Icon { name: "x"; size: 13; color: Theme.ink2; anchors.verticalCenter: parent.verticalCenter
                   TapHandler { onTapped: { dock.attachmentName = ""; dock.attachmentText = ""; dock.refused = false } } }
        }
    }

    // A count when a message nears the limit, and why it cannot be sent: a small pill on the bar's
    // top edge at the send side, where it cannot collide with the buttons inside the bar.
    Rectangle {
        id: counter
        objectName: "composerCounter"
        visible: dock.counting || dock.refused
        anchors.bottom: dock.stacked ? chip.top : bar.top; anchors.bottomMargin: dock.stacked ? 6 : 8
        anchors.right: bar.right; anchors.rightMargin: 18
        height: 24; radius: 12
        width: counterText.implicitWidth + 20
        color: Theme.glassStrong
        border.width: 1
        border.color: dock.tooLong || dock.refused ? Qt.rgba(1, 0.36, 0.48, 0.55) : Theme.hairline
        scale: dock.refused ? 1.04 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutBack } }
        T {
            id: counterText
            objectName: "composerCounterText"
            anchors.centerIn: parent
            text: (dock.tooLong ? (dock.fileTooLong ? mira.s.ch_too_long_file : mira.s.ch_too_long) + " · " : "")
                  + dock.composedLength + " / " + dock.maxLength
            font.pixelSize: Theme.tiny; wrapMode: Text.NoWrap
            color: dock.tooLong || dock.refused ? Theme.danger : Theme.ink2
        }
    }

    Glass {
        id: bar
        objectName: "composerBar"
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width, 980)
        // one line is always the base bar, whatever the font's line height, so the stage never moves;
        // only a second line grows it
        height: dock.multiline ? Math.max(dock.barBase, dock.editorHeight + 24) : dock.barBase
        radius: dock.multiline ? Theme.rDock : height / 2
        tint: Theme.glassStrong
        lit: input.activeFocus
        Behavior on height { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutCubic } }

        // microphone: the primary action (stays beside the last line as the composer grows)
        Item {
            id: micBox
            width: 72; height: 72
            anchors.left: parent.left
            anchors.bottom: parent.bottom
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

        // the composer: grows with its lines, then scrolls (the view follows the cursor)
        Flickable {
            id: editor
            objectName: "composerView"
            anchors.left: micBox.right
            anchors.right: tools.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            height: dock.editorHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: dock.multiline && input.implicitHeight > editor.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff; width: 5 }

            TextArea.flickable: TextArea {
                id: input
                objectName: "composer"
                placeholderText: mira.s.ask_placeholder
                placeholderTextColor: Theme.ink3
                color: Theme.ink
                selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
                font.family: Theme.font
                font.pixelSize: 16
                wrapMode: TextArea.Wrap
                textFormat: TextArea.PlainText
                topPadding: 8; bottomPadding: 8
                leftPadding: 4; rightPadding: 4
                background: Item {}
                Accessible.name: mira.s.ask_placeholder
                Accessible.description: dock.tooLong ? counterText.text : mira.s.ch_send_tip
                onTextChanged: dock.refused = false
                Keys.onPressed: function(event) {
                    if (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter)
                        return
                    if (event.modifiers & Qt.ShiftModifier)
                        return                       // a new line
                    if (input.inputMethodComposing)
                        return                       // the input method commits its word first
                    event.accepted = true
                    dock.submit()
                }
                Keys.onEscapePressed: { if (text !== "") clear(); else focus = false }
            }
        }

        Row {
            id: tools
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 14
            spacing: 6
            IconButton { iconName: "clip"; tip: mira.s.attach; diameter: 40; anchors.verticalCenter: parent.verticalCenter; onClicked: fileDialog.open() }
            IconButton {
                objectName: "sendButton"
                iconName: "send"; tip: dock.tooLong ? counterText.text : mira.s.ch_send_tip; diameter: 44
                enabled: (input.text.trim() !== "" || dock.attachmentText !== "") && !dock.tooLong
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
                dock.refused = false
                dock.attachmentText = content
                const parts = selectedFile.toString().split("/")
                dock.attachmentName = decodeURIComponent(parts[parts.length - 1])
                input.forceActiveFocus()
            }
        }
    }
}
