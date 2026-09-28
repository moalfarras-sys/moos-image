import QtQuick
import QtQuick.Window
import QtQuick.Controls.Basic
import Mira

// Mira Neural OS · the whole window. Face in the middle, context on one side, the conversation on
// the other, one command dock at the bottom; Home, Computer and Settings slide in as workspaces.
ApplicationWindow {
    id: win
    width: 1480
    height: 920
    minimumWidth: 420
    minimumHeight: 640
    visible: true
    title: mira.lang === "ar" ? "ميرا · Mira" : "Mira · ميرا"
    color: Theme.bg0
    font.family: Theme.font
    LayoutMirroring.enabled: mira.lang === "ar"
    LayoutMirroring.childrenInherit: true

    readonly property bool wide: width >= 1180
    readonly property bool narrow: width < 760
    readonly property bool shown: visibility !== Window.Minimized && visibility !== Window.Hidden
    readonly property bool lively: ["listening", "thinking", "speaking", "executing"].indexOf(mira.phase) >= 0 || core.hovered
    property string sheet: ""
    onClosing: function(close) { if (mira.hideToTray()) { close.accepted = false; win.hide() } }

    Component.onCompleted: Theme.motionScale = Qt.binding(function() { return mira.motion ? 1.0 : 0.0 })

    // ── one shared clock for every living surface, spent only where it carries meaning ──
    // speaking/listening/thinking/acting or pointer on the face: smooth (display rate);
    // recently used: 30 Hz breathing; left alone: 12 Hz, then still after two minutes
    // (blinks remain, they are brief). Hidden or Reduced Motion: nothing runs.
    property real clock: 0
    property real lastActivity: Date.now()
    property bool resting: false
    function touch() { lastActivity = Date.now(); resting = false }
    onLivelyChanged: touch()
    onActiveChanged: touch()
    Connections { target: mira; function onPhaseChanged() { win.touch() } function onCaptionChanged() { win.touch() } }
    NumberAnimation on clock {
        id: smoothClock
        running: mira.motion && win.shown && win.lively
        from: win.clock; to: win.clock + 3600; duration: 3600 * 1000; loops: Animation.Infinite
    }
    Timer {
        running: mira.motion && win.shown && !win.lively && !win.resting
        interval: win.active && Date.now() - win.lastActivity < 45000 ? 33 : 83
        repeat: true
        onTriggered: {
            win.clock += interval / 1000
            if (Date.now() - win.lastActivity > 120000) win.resting = true
        }
    }
    HoverHandler { onPointChanged: if (win.resting || Date.now() - win.lastActivity > 5000) win.touch() }

    Nebula {
        anchors.fill: parent
        clock: win.clock
        energy: win.lively ? 1 : 0.25
        focusPoint: Qt.point((stageArea.x + stageArea.width / 2 + content.x) / Math.max(1, win.width), (content.y + stageArea.y + core.y + core.height / 2) / Math.max(1, win.height))
        accent: Theme.phaseColor(mira.phase, mira.faceStyle)
        accent2: Theme.phaseColor2(mira.phase, mira.faceStyle)
    }

    Item {
        id: frame
        anchors.fill: parent
        anchors.margins: win.narrow ? 10 : 18

        TopBar {
            id: top
            anchors { left: parent.left; right: parent.right; top: parent.top }
            compact: win.narrow
            onOpenSheet: function(name) { win.sheet = name === "chat" ? "" : name }
        }

        Item {
            id: content
            anchors { left: parent.left; right: parent.right; top: top.bottom; bottom: dock.top; topMargin: 12; bottomMargin: 14 }

            ContextRail {
                id: rail
                visible: win.wide
                width: 300
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                onSuggestion: function(text) { mira.send(text) }
                onOpenSheet: function(name) { win.sheet = name }
            }

            ConversationPanel {
                id: convo
                visible: !win.narrow
                width: win.width >= 1500 ? 420 : 370
                anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                onSuggestion: function(text) { mira.send(text) }
            }

            Item {
                id: stageArea
                anchors {
                    left: win.wide ? rail.right : parent.left
                    right: win.narrow ? parent.right : convo.left
                    top: parent.top
                    leftMargin: win.wide ? 16 : 0; rightMargin: win.narrow ? 0 : 16
                }
                height: win.narrow ? Math.min(parent.height * 0.56, width + 90) : parent.height

                MiraCore {
                    id: core
                    width: Math.min(parent.width, parent.height - caption.height - 18)
                    height: width
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Math.max(0, (parent.height - height - caption.height - 18) / 2)
                    phase: mira.phase
                    faceStyle: mira.faceStyle
                    mood: mira.mood
                    level: mira.level
                    clock: win.clock
                    motion: mira.motion
                    onActivated: mira.talk()
                    onFaceToggleRequested: mira.toggleFace()
                }
                StageCaption {
                    id: caption
                    width: Math.min(parent.width - 20, 620)
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: core.bottom
                    anchors.topMargin: -Math.round(core.height * 0.12)
                }
            }

            ConversationPanel {
                id: narrowConvo
                visible: win.narrow
                showHeader: false
                anchors { left: parent.left; right: parent.right; top: stageArea.bottom; bottom: parent.bottom; topMargin: 8 }
                onSuggestion: function(text) { mira.send(text) }
            }
        }

        CommandDock {
            id: dock
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            level: mira.level
        }

        SideSheet {
            id: sheetView
            anchors { left: parent.left; right: parent.right; top: top.bottom; bottom: parent.bottom; topMargin: 12 }
            open: win.sheet !== ""
            sheetWidth: win.narrow ? win.width : Math.max(560, Math.min(720, win.width * 0.52))
            icon: win.sheet === "home" ? "home" : win.sheet === "computer" ? "monitor" : "settings"
            title: win.sheet === "home" ? mira.s.home_title : win.sheet === "computer" ? mira.s.pc_title : mira.s.st_title
            subtitle: win.sheet === "home" ? mira.s.home_sub : win.sheet === "computer" ? mira.s.pc_sub : ""
            onCloseRequested: win.sheet = ""
            Loader {
                anchors.fill: parent
                active: win.sheet !== ""
                sourceComponent: win.sheet === "home" ? homeC : win.sheet === "computer" ? pcC : setC
            }
        }
    }

    Component { id: homeC; HomeSheet {} }
    Component { id: pcC; ComputerSheet {} }
    Component { id: setC; SettingsSheet {} }

    Toasts {
        id: toasts
        anchors.horizontalCenter: parent.horizontalCenter
        y: 74
        width: Math.min(460, win.width - 40)
    }

    Connections {
        target: mira
        function onToast(kind, text) { toasts.show(kind, text) }
        function onFocusComposer() { dock.field.forceActiveFocus() }
    }

    Shortcut { sequences: ["Ctrl+Space"]; onActivated: mira.talk() }
    Shortcut { sequences: ["Escape"]; onActivated: { if (win.sheet !== "") win.sheet = ""; else if (mira.busy) mira.stop() } }
    Shortcut { sequences: ["Ctrl+K", "Ctrl+L"]; onActivated: dock.field.forceActiveFocus() }
    Shortcut { sequences: ["Ctrl+1"]; onActivated: win.sheet = win.sheet === "home" ? "" : "home" }
    Shortcut { sequences: ["Ctrl+2"]; onActivated: win.sheet = win.sheet === "computer" ? "" : "computer" }
    Shortcut { sequences: ["Ctrl+,", "Ctrl+3"]; onActivated: win.sheet = win.sheet === "settings" ? "" : "settings" }
    Shortcut { sequences: ["Ctrl+Shift+F"]; onActivated: mira.toggleFace() }
}
