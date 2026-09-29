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
            anchors { left: rail.right; right: parent.right; top: parent.top; leftMargin: 14 }
            compact: win.narrow
            onOpenSheet: function(name) { win.go(name === "chat" ? "" : name) }
        }

        // the destinations, labelled; Mira's own face leads back to the conversation
        NavRail {
            id: rail
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            compact: win.height < 760 || win.narrow
            current: win.sheet
            badges: ({ inbox: mira.inboxCount > 0 ? String(mira.inboxCount) : "",
                       system: mira.systemBadge || "" })
            onNavigate: function(name) { win.go(name) }
        }

        Item {
            id: content
            anchors { left: rail.right; right: parent.right; top: top.bottom; bottom: dock.top; leftMargin: 14; topMargin: 12; bottomMargin: 14 }

            ConversationPanel {
                id: convo
                visible: !win.narrow
                width: win.width >= 1500 ? 420 : 370
                anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
                onSuggestion: function(text) { mira.send(text) }
            }

            // ── the Mira stage (her face, the context) ──
            Item {
                id: stageHost
                visible: win.sheet === ""
                anchors { left: parent.left; right: win.narrow ? parent.right : convo.left; top: parent.top; bottom: parent.bottom; rightMargin: win.narrow ? 0 : 16 }

                ContextRail {
                    id: ctxRail
                    visible: win.width >= 1320
                    width: 300
                    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                    onSuggestion: function(text) { mira.send(text) }
                    onOpenSheet: function(name) { win.go(name) }
                }

                Item {
                    id: stageArea
                    anchors {
                        left: ctxRail.visible ? ctxRail.right : parent.left
                        right: parent.right
                        top: parent.top
                        leftMargin: ctxRail.visible ? 16 : 0
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

            // ── one destination at a time ──
            Glass {
                id: pageHost
                visible: win.sheet !== ""
                anchors { left: parent.left; right: win.narrow ? parent.right : convo.left; top: parent.top; bottom: parent.bottom; rightMargin: win.narrow ? 0 : 16 }
                radius: Theme.rPanel
                tint: Qt.rgba(0.045, 0.055, 0.13, 0.9)
                opacity: visible ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.normal } }
                Loader {
                    id: pageLoader
                    anchors.fill: parent
                    anchors.margins: win.narrow ? 14 : 22
                    active: win.sheet !== ""
                    sourceComponent: win.pageComponent(win.sheet)
                }
            }
        }

        CommandDock {
            id: dock
            anchors { left: rail.right; right: parent.right; bottom: parent.bottom; leftMargin: 14 }
            level: mira.level
        }

        // system changes waiting for the owner, and the jobs he approved — above everything
        // (beside an open page when there is room, so they never hide the page being used)
        ActionCards {
            id: cards
            readonly property bool beside: win.sheet !== "" && !win.narrow && convo.visible
            width: Math.min(640, (beside ? convo.width : content.width) - (win.narrow ? 0 : 24))
            x: beside ? content.x + convo.x + (convo.width - width) / 2 : content.x + (content.width - width) / 2
            anchors { bottom: dock.top; bottomMargin: 12 }
        }
    }

    // destination → page. A page not built yet shows the conversation's old sheet in its frame.
    function pageComponent(name) {
        switch (name) {
        case "home": return homeC
        case "pc": return mira.pcPage ? pcPageC : pcC
        case "system": return mira.systemPage ? sysPageC : sysC
        case "apps": return mira.appsPage ? appsPageC : sysC
        case "workbench": return mira.workbenchPage ? workbenchPageC : soonC
        case "connect": return mira.connectPage ? connectPageC : soonC
        case "brain": return mira.brainPage ? brainPageC : soonC
        default: return setC
        }
    }
    function go(name) {
        win.sheet = name
        if (name !== "")
            mira.pageShown(name)
    }

    Component { id: homeC; SheetFrame { icon: "home"; title: mira.s.home_title; subtitle: mira.s.home_sub; HomeSheet { anchors.fill: parent } } }
    Component { id: pcC; SheetFrame { icon: "monitor"; title: mira.s.pc_title; subtitle: mira.s.pc_sub; ComputerSheet { anchors.fill: parent } } }
    Component { id: sysC; SheetFrame { icon: "shield"; title: mira.s.sys_title; subtitle: mira.s.sys_sub; SystemSheet { anchors.fill: parent } } }
    Component { id: setC; SheetFrame { icon: "settings"; title: mira.s.st_title; SettingsSheet { anchors.fill: parent } } }
    Component { id: soonC; PageFrame { icon: "sparkle"; title: mira.s.page_loading } }
    // the new pages (pages/*.py + qml/Mira/*Page.qml); each is used once its file exists
    Component { id: pcPageC; PcPage {} }
    Component { id: sysPageC; SystemPage {} }
    Component { id: appsPageC; AppsPage {} }
    Component { id: workbenchPageC; WorkbenchPage {} }
    Component { id: connectPageC; ConnectPage {} }
    Component { id: brainPageC; BrainPage {} }

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
        function onShowSheet(name) { win.go(name) }
        function onPrefill(text) { dock.field.text = text; dock.field.forceActiveFocus() }
    }

    Shortcut { sequences: ["Ctrl+Space"]; onActivated: mira.talk() }
    Shortcut { sequences: ["Escape"]; onActivated: { if (win.sheet !== "") win.go(""); else if (mira.busy) mira.stop() } }
    Shortcut { sequences: ["Ctrl+K", "Ctrl+L"]; onActivated: dock.field.forceActiveFocus() }
    Shortcut { sequences: ["Ctrl+0"]; onActivated: win.go("") }
    Shortcut { sequences: ["Ctrl+1"]; onActivated: win.go(win.sheet === "home" ? "" : "home") }
    Shortcut { sequences: ["Ctrl+2"]; onActivated: win.go(win.sheet === "pc" ? "" : "pc") }
    Shortcut { sequences: ["Ctrl+3"]; onActivated: win.go(win.sheet === "apps" ? "" : "apps") }
    Shortcut { sequences: ["Ctrl+4"]; onActivated: win.go(win.sheet === "system" ? "" : "system") }
    Shortcut { sequences: ["Ctrl+5"]; onActivated: win.go(win.sheet === "workbench" ? "" : "workbench") }
    Shortcut { sequences: ["Ctrl+6"]; onActivated: win.go(win.sheet === "connect" ? "" : "connect") }
    Shortcut { sequences: ["Ctrl+7"]; onActivated: win.go(win.sheet === "brain" ? "" : "brain") }
    Shortcut { sequences: ["Ctrl+,"]; onActivated: win.go(win.sheet === "settings" ? "" : "settings") }
    Shortcut { sequences: ["Ctrl+Shift+F"]; onActivated: mira.toggleFace() }
}
