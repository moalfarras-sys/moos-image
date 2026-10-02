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

    // Transitions follow Plasma's own speed (mira.motionScale: 0 only when animations are off),
    // whatever her ambient loop does. A controller without the visual policy keeps the old rule.
    Component.onCompleted: Theme.motionScale = Qt.binding(function() {
        return typeof mira.motionScale === "number" ? mira.motionScale : (mira.motion ? 1.0 : 0.0) })

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
                // the composer grows upward over the content: the conversation's end stays above it
                anchors { right: parent.right; top: parent.top; bottom: parent.bottom; bottomMargin: dock.growth }
                onSuggestion: function(text) { mira.send(text) }
            }

            // ── the Mira stage (her face, the context) ──
            Item {
                id: stageHost
                visible: win.sheet === ""
                anchors { left: parent.left; right: win.narrow ? parent.right : convo.left; top: parent.top; bottom: parent.bottom; rightMargin: win.narrow ? 0 : 16 }

                ContextRail {
                    id: ctxRail
                    objectName: "contextRail"
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
                        mouthLevel: mira.mouthLevel
                        mouthPacket: mira.mouthPacket
                        clock: win.clock
                        motion: mira.motion
                        onActivated: mira.talk()
                        onFaceToggleRequested: mira.toggleFace()
                    }
                    StageCaption {
                        id: caption
                        objectName: "stageCaption"
                        width: Math.min(parent.width - 20, 620)
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: core.bottom
                        anchors.topMargin: -Math.round(core.height * 0.12)
                        // the cards stand over the stage: her caption would show through their gaps,
                        // and while a card waits the card itself says what she is waiting for
                        opacity: cards.onStage ? 0 : 1
                        visible: opacity > 0
                        Behavior on opacity { enabled: mira.motion; NumberAnimation { duration: Theme.normal } }
                    }
                }

                ConversationPanel {
                    id: narrowConvo
                    visible: win.narrow
                    showHeader: false
                    anchors { left: parent.left; right: parent.right; top: stageArea.bottom; bottom: parent.bottom; topMargin: 8; bottomMargin: dock.growth }
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

        // system changes waiting for the owner, and the jobs he approved — above everything.
        // Beside an open page they stand over the conversation, so they never hide the page being
        // used; on the stage they stand in the free space between the context rail and the
        // conversation, so they cover neither panel. They always stay clear of the composer (its
        // grown lines, file chip and count) and of the top bar, and scroll when there are more.
        ActionCards {
            id: cards
            objectName: "actionCards"
            readonly property bool beside: win.sheet !== "" && !win.narrow && convo.visible
            readonly property bool onStage: visible && win.sheet === ""
            overText: win.sheet !== ""
            readonly property real areaX: beside ? content.x + convo.x
                                        : win.sheet === "" ? content.x + stageHost.x + stageArea.x : content.x
            readonly property real areaWidth: beside ? convo.width : win.sheet === "" ? stageArea.width : content.width
            width: Math.min(640, areaWidth - (win.narrow ? 0 : 24))
            x: areaX + (areaWidth - width) / 2
            maxHeight: Math.max(120, dock.y - dock.reach - 12 - (top.y + top.height) - 12)
            anchors { bottom: dock.top; bottomMargin: 12 + dock.reach }
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
    // Dolphin's «Ask Mira about this» on a small text file: the composer's own attachment chip.
    // mira.kde is null (or absent) when kde_integration could not load; a null target listens to nothing.
    Connections {
        target: mira.kde || null
        function onAttach(name, text) { dock.attachmentName = name; dock.attachmentText = text; dock.refused = false }
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
