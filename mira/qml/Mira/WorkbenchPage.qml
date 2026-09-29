import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Dialogs
import QtQuick.Window
import QtCore
import "icons.js" as Icons

// The Workbench: give Mira projects. Mo AI's agent workspace behind it — projects, their files and
// Git state, tracked tasks, the owner's own terminal, the coding agents and the agent's sessions.
// A file or a diff is read only on the owner's click; only the owner types in his terminal; every
// state shown is the backend's own answer (pages/workbench.py). Lists come from their own
// properties (mira.workbenchPage.tasks …) so a poll never resets a list the owner is scrolling.
PageFrame {
    id: page
    readonly property var st: mira.workbenchPage ? mira.workbenchPage.state : ({})
    readonly property bool ar: mira.lang === "ar"
    readonly property bool wide: page.contentWidth >= 720
    readonly property bool roomy: page.contentWidth >= 860
    readonly property bool hasProject: (st.project || "") !== ""
    readonly property int projectCount: mira.workbenchPage ? mira.workbenchPage.projects.length : 0
    readonly property color readyColor: st.ready === "ready" ? Theme.ok : st.ready === "setup" ? Theme.amber
                                       : st.ready === "offline" ? Theme.danger : Theme.cyan
    readonly property string readyText: st.ready === "ready" ? mira.s.wb_ready : st.ready === "setup" ? mira.s.wb_setup
                                       : st.ready === "offline" ? mira.s.wb_offline : mira.s.wb_checking
    readonly property string tierText: st.tier === "read" ? mira.s.wb_tier_read : st.tier === "project" ? mira.s.wb_tier_project
                                      : st.tier === "system" ? mira.s.wb_tier_system : st.tier === "full" ? mira.s.wb_tier_full
                                      : st.tier === "custom" ? mira.s.wb_tier_custom : ""
    readonly property string tierTone: st.tier === "read" ? "info" : st.tier === "project" ? "ok" : "warn"

    icon: "chip"
    accent: Theme.violet
    title: mira.s.nav_workbench
    subtitle: mira.s.wb_sub
    busy: !!st.loading
    actions: [
        StatusPill {
            anchors.verticalCenter: parent.verticalCenter
            text: page.readyText
            tone: st.ready === "ready" ? "ok" : st.ready === "setup" ? "warn" : st.ready === "offline" ? "error" : "info"
            icon: st.ready === "ready" ? "check" : st.ready === "unknown" ? "clock" : "alert"
        },
        IconButton {
            iconName: "refresh"; tip: mira.s.wb_refresh
            onClicked: mira.workbenchPage.refresh()
        }
    ]

    // Polling runs only while the page is really on screen: its view exists AND Mira's window is
    // shown (closing Mira hides it to the tray with this page still loaded; minimising keeps it too).
    readonly property bool onScreen: Window.window !== null && Window.window.visible
                                     && Window.window.visibility !== Window.Minimized
                                     && Window.window.visibility !== Window.Hidden
    onOnScreenChanged: if (mira.workbenchPage) mira.workbenchPage.setShown(onScreen)

    // The page's scrolling view (PageFrame's). The destinations bar stays pinned to its top once the
    // owner scrolls past it; choosing a destination brings its content right under the bar.
    property Item scroller: null
    property bool settled: false
    readonly property string tab: st.tab || "files"
    readonly property bool pinnedTabs: scroller !== null && scroller.contentY > tabBar.y + 1
    onTabChanged: if (settled) Qt.callLater(page.revealTabs)
    Component.onCompleted: {
        var f = tabBar.parent
        while (f && f.contentY === undefined) f = f.parent
        if (f) { stickyTabs.parent = f; scroller = f }
        mira.workbenchPage.setShown(onScreen)
        settled = true
    }
    Component.onDestruction: if (mira && mira.workbenchPage) mira.workbenchPage.setShown(false)
    NumberAnimation { id: reveal; property: "contentY"; duration: Theme.normal; easing.type: Easing.OutCubic }
    function revealTabs() {
        var f = page.scroller
        if (!f) return
        var target = Math.max(0, Math.min(tabBar.y, f.contentHeight - f.height))
        // under the pinned bar the new content starts right below it (this may scroll up);
        // otherwise the page only ever scrolls down to it, never away from what the owner reads
        if (f.contentY > tabBar.y + 1 ? Math.abs(target - f.contentY) <= 1 : target <= f.contentY + 1) return
        reveal.stop(); reveal.target = f; reveal.from = f.contentY; reveal.to = target; reveal.start()
    }

    function sizeText(b) {
        if (b < 1024) return b + " B"
        if (b < 1048576) return (b / 1024).toFixed(b < 10240 ? 1 : 0) + " KB"
        return (b / 1048576).toFixed(1) + " MB"
    }
    function ago(ts) {
        if (!ts) return ""
        var s = Math.max(0, Date.now() / 1000 - ts)
        if (s < 60) return page.ar ? "الآن" : "just now"
        if (s < 3600) { var m = Math.round(s / 60); return page.ar ? "منذ " + m + " د" : m + " min ago" }
        if (s < 86400) { var h = Math.round(s / 3600); return page.ar ? "منذ " + h + " س" : h + " h ago" }
        var d = Math.round(s / 86400); return page.ar ? "منذ " + d + " يوم" : d + " d ago"
    }
    function statusText(s) {
        return s === "running" ? mira.s.wb_st_running : s === "paused" ? mira.s.wb_st_paused : s === "failed" ? mira.s.wb_st_failed
             : s === "completed" ? mira.s.wb_st_completed : s === "cancelled" ? mira.s.wb_st_cancelled : mira.s.wb_st_pending
    }
    function kindColor(k) {
        return k === "new" ? Theme.mint : k === "modified" ? Theme.amber : k === "added" ? Theme.ok
             : k === "deleted" ? Theme.danger : k === "renamed" || k === "copied" ? Theme.violet
             : k === "conflict" ? Theme.rose : Theme.ink3
    }
    function toneColor(t) {
        return t === "ok" ? Theme.ok : t === "warn" ? Theme.amber : t === "error" ? Theme.danger : t === "off" ? Theme.off : Theme.cyan
    }

    // ── small pieces of this page ───────────────────────────────────
    // A line glyph from Mira's set, or one of the few this page draws itself (folder, file, branch…).
    // (an Icon: the same drawing on both scene graphs, clipped correctly on the software one)
    component Glyph: Icon {
        size: 18
        readonly property var own: ({
            folder: "M3.5 7a1.5 1.5 0 0 1 1.5-1.5h4.3l2 2.2H19a1.5 1.5 0 0 1 1.5 1.5v8.3A1.5 1.5 0 0 1 19 19H5a1.5 1.5 0 0 1-1.5-1.5z",
            file: "M6.5 3.5h7l4 4v13h-11z M13.5 3.5v4h4 M9 12.5h6 M9 16h6",
            branch: "M7 4.5v10 M7 14.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z M17 4.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z M17 9.5c0 4-4 4.5-10 5",
            terminal: "M3.5 5.5h17v13h-17z M7 10l3 2.5L7 15 M12.5 15.5h4.5",
            plus: "M12 5v14 M5 12h14",
            pin: "M9 3.5h6 M10 3.5v6L7 13h10l-3-3.5v-6 M12 13v7.5",
            archive: "M3.5 5h17v4h-17z M5 9v10h14V9 M10 13h4",
            back: "M14.5 6l-6 6 6 6",
            "chevron-up": "M6 14.5l6-6 6 6"
        })
        path: Icons.paths[name] ? "" : (own[name] || "")
    }

    // A quiet pill button that can carry any Glyph (PillButton takes only the shared set). `compact`
    // shows the glyph alone; its words stay its accessible name and its tooltip.
    component GlyphButton: AbstractButton {
        id: gb
        property string glyph: ""
        property bool mirrorGlyph: false
        property bool primary: false
        property bool danger: false
        property bool compact: false
        implicitHeight: 34
        implicitWidth: compact ? 34 : gbRow.implicitWidth + 24
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text
        ToolTip.visible: compact && hovered && text !== ""
        ToolTip.text: text
        ToolTip.delay: 450
        Keys.onReturnPressed: clicked()
        background: Rectangle {
            radius: height / 2
            color: gb.primary ? Qt.rgba(0.42, 0.33, 0.94, gb.hovered ? 0.55 : 0.42)
                 : gb.danger ? Qt.rgba(1, 0.36, 0.48, gb.hovered ? 0.22 : 0.12)
                 : gb.down ? Theme.glassHover : gb.hovered ? Qt.rgba(1, 1, 1, 0.09) : Qt.rgba(1, 1, 1, 0.045)
            border.width: gb.visualFocus ? 2 : 1
            border.color: gb.visualFocus ? Theme.cyan : gb.primary ? Qt.rgba(0.7, 0.62, 1, 0.55)
                        : gb.danger ? Qt.rgba(1, 0.36, 0.48, 0.45) : gb.hovered ? Theme.hairlineStrong : Theme.hairline
            opacity: gb.enabled ? 1 : 0.45
        }
        contentItem: Item {
            implicitWidth: gbRow.implicitWidth; implicitHeight: gbRow.implicitHeight
            Row {
                id: gbRow
                anchors.centerIn: parent
                spacing: 6
                Glyph {
                    visible: gb.glyph !== ""; name: gb.glyph; size: 16
                    color: gb.danger ? Theme.danger : gb.primary ? "white" : Theme.ink2
                    anchors.verticalCenter: parent.verticalCenter
                    transform: Scale { xScale: gb.mirrorGlyph ? -1 : 1; origin.x: 8 }
                }
                T { visible: gb.text !== "" && !gb.compact; text: gb.text; font.pixelSize: Theme.small; font.weight: Font.Medium; wrapMode: Text.NoWrap
                    color: gb.danger ? Theme.danger : gb.primary ? "white" : gb.enabled ? Theme.ink : Theme.ink3
                    anchors.verticalCenter: parent.verticalCenter }
            }
        }
        scale: down ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    // One destination of the workbench.
    component WbTab: AbstractButton {
        id: tb
        property string key: ""
        property string glyph: "sparkle"
        property int count: 0
        readonly property bool selected: mira.workbenchPage && mira.workbenchPage.state.tab === key
        Layout.fillWidth: true
        implicitHeight: 44
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text + (count > 0 ? " · " + count : "")
        Accessible.role: Accessible.PageTab
        Keys.onReturnPressed: clicked()
        onClicked: mira.workbenchPage.setTab(key)
        background: Rectangle {
            radius: 13
            color: tb.selected ? Qt.rgba(0.61, 0.48, 1, 0.22) : tb.hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
            border.width: tb.visualFocus ? 2 : tb.selected ? 1 : 0
            border.color: tb.visualFocus ? Theme.cyan : Qt.rgba(0.72, 0.6, 1, 0.5)
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: Item {
            implicitWidth: tabRow.implicitWidth + 16
            Row {
                id: tabRow
                anchors.centerIn: parent
                spacing: 7
                Glyph { name: tb.glyph; size: 17; color: tb.selected ? Theme.ink : Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
                T { text: tb.text; font.pixelSize: Theme.small + 1; font.weight: tb.selected ? Font.DemiBold : Font.Medium
                    color: tb.selected ? Theme.ink : Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
                Rectangle {
                    visible: tb.count > 0
                    anchors.verticalCenter: parent.verticalCenter
                    height: 18; width: Math.max(18, cnt.implicitWidth + 10); radius: 9
                    color: tb.selected ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(0.21, 0.85, 0.96, 0.18)
                    T { id: cnt; anchors.centerIn: parent; text: String(tb.count); font.pixelSize: Theme.tiny; color: tb.selected ? Theme.ink : Theme.cyan; wrapMode: Text.NoWrap }
                }
            }
        }
    }

    // The destinations of the workbench, as one bar. It is drawn twice: in the page's flow, and pinned
    // to the top of the view once the owner scrolls past it (the two never show at once).
    component TabStrip: Glass {
        id: ts
        property real avail: 0
        implicitHeight: tabGrid.implicitHeight + 12
        radius: 17
        tint: Qt.rgba(0.06, 0.07, 0.16, 0.7)
        GridLayout {
            id: tabGrid
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 6 }
            columns: ts.avail >= 760 ? 6 : 3
            columnSpacing: 4; rowSpacing: 4
            WbTab { key: "files"; glyph: "folder"; text: mira.s.wb_tab_files }
            WbTab { key: "git"; glyph: "branch"; text: mira.s.wb_tab_git
                    count: mira.workbenchPage ? mira.workbenchPage.gitRows.length : 0 }
            WbTab { key: "tasks"; glyph: "rocket"; text: mira.s.wb_tab_tasks
                    count: mira.workbenchPage ? mira.workbenchPage.state.running || 0 : 0 }
            WbTab { key: "terminal"; glyph: "terminal"; text: mira.s.wb_tab_terminal
                    count: mira.workbenchPage ? mira.workbenchPage.terminals.filter(function(t) { return t.running && !t.agent }).length : 0 }
            WbTab { key: "agents"; glyph: "bolt"; text: mira.s.wb_tab_agents }
            WbTab { key: "sessions"; glyph: "chat"; text: mira.s.wb_tab_sessions
                    count: mira.workbenchPage ? mira.workbenchPage.sessions.length : 0 }
        }
    }

    // A row of a list (a file, a change, a session): glyph or code badge, text, a trailing note.
    component RowButton: AbstractButton {
        id: rb
        property string glyph: "file"
        property color glyphColor: Theme.ink2
        property string note: ""
        property string badge: ""
        property color badgeColor: Theme.cyan
        property bool mono: false
        property bool selected: false
        implicitHeight: 40
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text + (note ? " · " + note : "")
        Keys.onReturnPressed: clicked()
        background: Rectangle {
            radius: 11
            color: rb.selected ? Qt.rgba(0.21, 0.85, 0.96, 0.12) : rb.down ? Theme.glassHover : rb.hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
            border.width: rb.visualFocus ? 2 : rb.selected ? 1 : 0
            border.color: rb.visualFocus ? Theme.cyan : Qt.rgba(0.21, 0.85, 0.96, 0.35)
        }
        contentItem: RowLayout {
            spacing: 10
            Rectangle {
                visible: rb.badge !== ""
                Layout.leftMargin: 8
                Layout.preferredWidth: 28; Layout.preferredHeight: 20; radius: 6
                color: Qt.rgba(rb.badgeColor.r, rb.badgeColor.g, rb.badgeColor.b, 0.16)
                T { anchors.centerIn: parent; text: rb.badge; font.family: Theme.mono; font.pixelSize: Theme.tiny; font.weight: Font.Bold; color: rb.badgeColor; wrapMode: Text.NoWrap }
            }
            Glyph { visible: rb.badge === ""; Layout.leftMargin: 10; name: rb.glyph; size: 17; color: rb.glyphColor }
            T {
                Layout.fillWidth: true
                text: rb.text
                font.family: rb.mono ? Theme.mono : Theme.font
                font.pixelSize: rb.mono ? Theme.small : Theme.small + 1
                wrapMode: Text.NoWrap; elide: rb.mono ? Text.ElideMiddle : Text.ElideRight
                horizontalAlignment: Text.AlignLeft
                color: rb.selected ? Theme.ink : Theme.ink2
            }
            T { visible: rb.note !== ""; Layout.rightMargin: 10; text: rb.note; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
        }
    }

    // An empty or waiting state: a quiet glyph and one honest sentence.
    component Empty: ColumnLayout {
        id: em
        property string glyph: "sparkle"
        property string text: ""
        property color tint: Theme.ink3
        Layout.fillWidth: true
        Layout.topMargin: 4; Layout.bottomMargin: 4
        spacing: 8
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 44; Layout.preferredHeight: 44; radius: 14
            color: Qt.rgba(1, 1, 1, 0.045); border.width: 1; border.color: Theme.hairline
            Glyph { anchors.centerIn: parent; name: em.glyph; size: 20; color: em.tint }
        }
        T { Layout.fillWidth: true; text: em.text; color: em.tint; font.pixelSize: Theme.small + 1; horizontalAlignment: Text.AlignHCenter }
    }

    // A multi-line field in Mira's glass. Escape while it holds words only leaves the field (every
    // word stays); Mira's window-wide Escape closes the page only from an empty field.
    component Area: TextArea {
        id: ta
        Keys.onShortcutOverride: function(event) { if (event.key === Qt.Key_Escape && ta.text !== "") event.accepted = true }
        Keys.onEscapePressed: function(event) { if (ta.text !== "") { ta.focus = false; event.accepted = true } }
        color: Theme.ink
        placeholderTextColor: Theme.ink3
        selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
        font.family: Theme.font
        font.pixelSize: Theme.body
        wrapMode: TextArea.Wrap
        leftPadding: 14; rightPadding: 14; topPadding: 10; bottomPadding: 10
        background: Rectangle {
            radius: Theme.rControl
            color: Qt.rgba(1, 1, 1, ta.activeFocus ? 0.07 : 0.045)
            border.width: 1
            border.color: ta.activeFocus ? Qt.rgba(0.35, 0.85, 1, 0.55) : Theme.hairline
        }
    }

    FolderDialog {
        id: folderDialog
        title: mira.s.wb_pick_folder
        currentFolder: StandardPaths.standardLocations(StandardPaths.HomeLocation)[0]
        onAccepted: mira.workbenchPage.addProject(selectedFolder.toString())
    }

    // ── the agent: ready, and with which permissions ────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: readyRow.implicitHeight + 24
        radius: 20
        edge: Qt.rgba(page.readyColor.r, page.readyColor.g, page.readyColor.b, 0.38)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0.36, 0.26, 0.85, 0.24) }
            GradientStop { position: 1; color: Qt.rgba(0.10, 0.55, 0.75, 0.14) }
        }
        GridLayout {
            id: readyRow
            readonly property bool narrow: page.contentWidth < 560
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
            columns: narrow ? 2 : 3
            columnSpacing: 12; rowSpacing: 10
            Rectangle {
                Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 13
                Layout.alignment: Qt.AlignVCenter
                color: Qt.rgba(page.readyColor.r, page.readyColor.g, page.readyColor.b, 0.14)
                border.width: 1; border.color: Qt.rgba(page.readyColor.r, page.readyColor.g, page.readyColor.b, 0.42)
                Icon { anchors.centerIn: parent; name: "chip"; size: 20; color: page.readyColor }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                // the name, the state and, when all is well, the chips that say how — on one line when it fits
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    Row {
                        height: 24
                        spacing: 7
                        T { text: mira.s.wb_agent; height: 24; verticalAlignment: Text.AlignVCenter; font.pixelSize: Theme.title - 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                        T { text: "·"; height: 24; verticalAlignment: Text.AlignVCenter; color: Theme.ink3; wrapMode: Text.NoWrap }
                        T { text: page.readyText; height: 24; verticalAlignment: Text.AlignVCenter; color: page.readyColor; font.pixelSize: Theme.title - 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                    }
                    Item { width: 4; height: 24; visible: st.ready === "ready" || st.ready === "setup" }
                    StatusPill { visible: page.tierText !== "" && (st.ready === "ready" || st.ready === "setup"); icon: "shield"; text: page.tierText; tone: page.tierTone }
                    StatusPill { visible: st.ready === "ready" || st.ready === "setup"; icon: "globe"; text: st.web ? mira.s.wb_web_on : mira.s.wb_web_off; tone: st.web ? "info" : "off" }
                    StatusPill { visible: st.ready === "ready" || st.ready === "setup"; icon: "cloud"; tone: st.brain ? "ok" : "error"
                                 text: st.brain ? mira.s.wb_brain_on + ((st.provider || "") !== "" ? " · " + st.provider : "") : mira.s.wb_brain_off }
                    StatusPill { visible: (st.approvals || 0) > 0; icon: "alert"; tone: "warn"; text: st.approvals + " " + mira.s.wb_approvals }
                }
                // otherwise one sentence says what is missing
                T {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                    visible: text !== "" && st.ready !== "ready"
                    text: st.readyReason ? (mira.s[st.readyReason] || "") : ""
                    font.pixelSize: Theme.small; color: Theme.ink2; maximumLineCount: 2; elide: Text.ElideRight
                }
            }
            PillButton {
                Layout.alignment: Qt.AlignVCenter
                Layout.columnSpan: readyRow.narrow ? 2 : 1
                text: mira.s.wb_permissions; iconName: "settings"
                primary: st.ready === "setup"; size: Theme.small; implicitHeight: 34
                onClicked: mira.workbenchPage.changePermissions()
            }
        }
    }

    // ── projects: the chosen one and what to do with it; the whole list on demand ──
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: projCol.implicitHeight + 24
        radius: 20
        ColumnLayout {
            id: projCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
            spacing: 12
            GridLayout {
                visible: page.hasProject
                Layout.fillWidth: true
                columns: page.contentWidth >= 640 ? 2 : 1
                columnSpacing: 12; rowSpacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 200      // the buttons wrap before the project's name gives way
                    spacing: 10
                    Rectangle {
                        Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 13
                        gradient: Gradient {
                            GradientStop { position: 0; color: Qt.rgba(0.61, 0.48, 1, 0.42) }
                            GradientStop { position: 1; color: Qt.rgba(0.21, 0.72, 0.95, 0.30) }
                        }
                        border.width: 1; border.color: Qt.rgba(0.72, 0.6, 1, 0.45)
                        Glyph { anchors.centerIn: parent; name: "folder"; size: 20; color: "white" }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            T { text: st.projectName || ""; font.pixelSize: Theme.body + 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap
                                elide: Text.ElideRight; Layout.maximumWidth: Math.max(60, parent.width - 44); horizontalAlignment: Text.AlignLeft }
                            Glyph { visible: !!st.projectPinned; name: "pin"; size: 14; color: Theme.violet }
                            Glyph { visible: !!st.projectArchived; name: "archive"; size: 14; color: Theme.ink3 }
                            Item { Layout.fillWidth: true }
                        }
                        T { Layout.fillWidth: true; text: st.projectPath || ""; font.family: Theme.mono; font.pixelSize: Theme.tiny; color: Theme.ink3
                            wrapMode: Text.NoWrap; elide: Text.ElideLeft; horizontalAlignment: Text.AlignLeft }
                    }
                }
                Flow {
                    id: projectActions
                    // as wide as its buttons need; narrower only when the page is, and then it wraps
                    readonly property real need: {
                        var w = 0, n = 0
                        for (var i = 0; i < children.length; ++i)
                            if (children[i].visible) { w += Math.max(children[i].implicitWidth, children[i].width); n++ }
                        // whole pixels and one spare: at a fractional scale the layout's rounding must not wrap it
                        return Math.ceil(w + spacing * Math.max(0, n - 1)) + 1
                    }
                    Layout.fillWidth: true
                    Layout.preferredWidth: need
                    Layout.maximumWidth: need
                    spacing: 8
                    GlyphButton {
                        compact: true
                        glyph: "pin"; text: st.projectPinned ? mira.s.wb_unpin : mira.s.wb_pin
                        onClicked: mira.workbenchPage.pinProject(st.project, !st.projectPinned)
                    }
                    GlyphButton {
                        compact: true
                        glyph: "archive"; text: st.projectArchived ? mira.s.wb_unarchive : mira.s.wb_archive
                        onClicked: mira.workbenchPage.archiveProject(st.project, !st.projectArchived)
                    }
                    GlyphButton {
                        compact: !page.roomy
                        glyph: "terminal"; text: mira.s.wb_term_new
                        enabled: st.ready !== "offline" && !st.termStarting
                        onClicked: { mira.workbenchPage.setTab("terminal"); mira.workbenchPage.newTerminal() }
                    }
                    GlyphButton {
                        glyph: "chat"; text: mira.s.wb_ask; primary: true
                        onClicked: mira.workbenchPage.askAboutProject()
                    }
                    Rectangle { width: 1; height: 34; color: "transparent"
                                Rectangle { anchors.centerIn: parent; width: 1; height: 24; color: Theme.hairlineStrong
                                            visible: projectActions.width >= projectActions.need - 1 } }  // no divider once the row wraps
                    GlyphButton {
                        glyph: st.projectsOpen ? "chevron-up" : "chevron-down"
                        text: st.projectsOpen ? mira.s.wb_hide_projects : mira.s.wb_all_projects + " · " + page.projectCount
                        onClicked: mira.workbenchPage.setProjectsOpen(!st.projectsOpen)
                    }
                }
            }
            // the whole list: on demand once a project is chosen, always while none is
            ColumnLayout {
                visible: !!st.projectsOpen || !page.hasProject
                Layout.fillWidth: true
                spacing: 10
                Rectangle { visible: page.hasProject; Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.hairline }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    SectionTitle { text: mira.s.wb_projects; icon: "package"; accent: Theme.violet }
                    Item { Layout.fillWidth: true }
                    GlyphButton {
                        compact: !page.wide
                        glyph: "archive"; text: mira.s.wb_show_archived
                        primary: !!st.showArchived
                        onClicked: mira.workbenchPage.setShowArchived(!st.showArchived)
                    }
                    GlyphButton {
                        glyph: "plus"; text: mira.s.wb_add_project; primary: true
                        enabled: st.ready !== "offline"
                        onClicked: folderDialog.open()
                    }
                }
                T { visible: (st.projectsError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.projectsError || ""; color: Theme.danger; font.pixelSize: Theme.small }
                Empty {
                    visible: projectRepeater.count === 0 && (st.projectsError || "") === ""
                    glyph: "folder"; text: mira.s.wb_no_projects
                }
                Flow {
                    id: projectFlow
                    // as many chips as fit at 220 px or more, stretched so every full row is filled
                    readonly property int perRow: Math.max(1, Math.floor((width + spacing) / (220 + spacing)))
                    Layout.fillWidth: true
                    spacing: 8
                    visible: projectRepeater.count > 0
                    Repeater {
                        id: projectRepeater
                        model: mira.workbenchPage ? mira.workbenchPage.projects : []
                        delegate: AbstractButton {
                            id: chip
                            required property var modelData
                            readonly property bool selected: modelData.id === st.project
                            width: Math.floor((projectFlow.width - projectFlow.spacing * (projectFlow.perRow - 1)) / projectFlow.perRow)
                            height: 58
                            hoverEnabled: true
                            focusPolicy: Qt.StrongFocus
                            Accessible.name: modelData.name + (modelData.archived ? " · " + mira.s.wb_archived : "")
                            Keys.onReturnPressed: clicked()
                            onClicked: mira.workbenchPage.selectProject(modelData.id)
                            background: Rectangle {
                                radius: 15
                                color: chip.selected ? Qt.rgba(0.61, 0.48, 1, 0.20) : chip.hovered ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.035)
                                border.width: chip.visualFocus ? 2 : 1
                                border.color: chip.visualFocus ? Theme.cyan : chip.selected ? Qt.rgba(0.72, 0.6, 1, 0.6) : Theme.hairline
                                opacity: chip.modelData.archived ? 0.6 : 1
                                Behavior on color { ColorAnimation { duration: Theme.fast } }
                            }
                            contentItem: RowLayout {
                                spacing: 10
                                Rectangle {
                                    Layout.leftMargin: 10
                                    Layout.preferredWidth: 36; Layout.preferredHeight: 36; radius: 11
                                    color: chip.selected ? Qt.rgba(0.61, 0.48, 1, 0.35) : Qt.rgba(0.61, 0.48, 1, 0.13)
                                    Glyph { anchors.centerIn: parent; name: "folder"; size: 19; color: chip.selected ? "white" : Theme.violet }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.rightMargin: 10
                                    spacing: 1
                                    RowLayout {
                                        spacing: 5
                                        Layout.fillWidth: true
                                        T { text: chip.modelData.name; font.pixelSize: Theme.small + 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight
                                            Layout.maximumWidth: chip.width - 116; horizontalAlignment: Text.AlignLeft }
                                        Glyph { visible: chip.modelData.pinned; name: "pin"; size: 14; color: Theme.violet }
                                        Glyph { visible: chip.modelData.archived; name: "archive"; size: 14; color: Theme.ink3 }
                                        Item { Layout.fillWidth: true }
                                    }
                                    T { text: chip.modelData.path; font.family: Theme.mono; font.pixelSize: Theme.tiny; color: Theme.ink3
                                        wrapMode: Text.NoWrap; elide: Text.ElideLeft; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── the destinations of the workbench ───────────────────────────
    TabStrip {
        id: tabBar
        avail: page.contentWidth
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
    }
    // the same bar, pinned to the top of the view (reparented there when the page is complete)
    TabStrip {
        id: stickyTabs
        avail: page.contentWidth
        visible: page.pinnedTabs
        x: 0; y: 0; z: 20
        width: page.contentWidth
        height: implicitHeight
        tint: "#0B0E22"            // opaque: the content scrolling beneath must not read through it
        edge: Theme.hairlineStrong
        Rectangle {        // a soft shade under it, so the content reads as passing beneath
            anchors { left: parent.left; right: parent.right; top: parent.bottom; leftMargin: 14; rightMargin: 14 }
            height: 10
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.rgba(0, 0, 0, 0.32) }
                GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0) }
            }
        }
    }

    // ── files ───────────────────────────────────────────────────────
    Card {
        visible: st.tab === "files"
        Empty { visible: !page.hasProject; glyph: "folder"; text: mira.s.wb_pick_project }
        GridLayout {
            visible: page.hasProject
            Layout.fillWidth: true
            columns: page.wide ? 2 : 1
            columnSpacing: 14; rowSpacing: 14
            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: page.wide ? 2 : 1
                Layout.alignment: Qt.AlignTop
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    IconButton {
                        iconName: "send"; tip: mira.s.wb_up; diameter: 32
                        enabled: (st.dirPath || "") !== ""
                        onClicked: mira.workbenchPage.goUp()
                    }
                    T {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignLeft
                        text: (st.projectName || "") + ((st.dirPath || "") !== "" ? "  ›  " + st.dirPath : "")
                        font.pixelSize: Theme.small + 1; font.weight: Font.Medium; color: Theme.ink2
                        wrapMode: Text.NoWrap; elide: Text.ElideMiddle
                    }
                    T { visible: !!st.filesLoading; text: mira.s.page_loading; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                    IconButton {
                        iconName: "refresh"; tip: mira.s.wb_refresh_files; diameter: 32
                        enabled: !st.filesLoading
                        onClicked: mira.workbenchPage.openDir(st.dirPath || "")
                    }
                }
                T { visible: (st.filesError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.filesError || ""; color: Theme.danger; font.pixelSize: Theme.small }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(440, Math.max(1, fileList.count) * 40 + 12)
                    visible: fileList.count > 0
                    radius: 14
                    color: Qt.rgba(0, 0, 0, 0.18); border.width: 1; border.color: Theme.hairline
                    ListView {
                        id: fileList
                        anchors.fill: parent; anchors.margins: 6
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        model: mira.workbenchPage ? mira.workbenchPage.entries : []
                        ScrollBar.vertical: ScrollBar { width: 5 }
                        delegate: RowButton {
                            required property var modelData
                            width: ListView.view.width
                            text: modelData.name
                            glyph: modelData.dir ? "folder" : "file"
                            glyphColor: modelData.dir ? Theme.violet : Theme.ink3
                            note: modelData.dir ? "" : page.sizeText(modelData.size)
                            selected: !modelData.dir && modelData.path === st.previewPath
                            onClicked: modelData.dir ? mira.workbenchPage.openDir(modelData.path) : mira.workbenchPage.previewFile(modelData.path)
                        }
                    }
                }
                T { visible: fileList.count === 0 && !st.filesLoading && (st.filesError || "") === ""; text: mira.s.wb_empty_dir; color: Theme.ink3; font.pixelSize: Theme.small }
                T { visible: !!st.truncated; text: mira.s.wb_truncated; color: Theme.amber; font.pixelSize: Theme.tiny + 1 }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.preferredWidth: page.wide ? 3 : 1
                Layout.alignment: Qt.AlignTop
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    spacing: 8
                    Glyph { name: "file"; size: 17; color: Theme.cyan }
                    T {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignLeft
                        text: (st.previewPath || "") !== "" ? st.previewPath : mira.s.wb_preview_hint
                        font.family: (st.previewPath || "") !== "" ? Theme.mono : Theme.font
                        font.pixelSize: Theme.small; color: (st.previewPath || "") !== "" ? Theme.ink : Theme.ink3
                        wrapMode: Text.NoWrap; elide: Text.ElideMiddle
                    }
                    T { visible: (st.previewSize || 0) > 0; text: page.sizeText(st.previewSize || 0); font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                    IconButton {
                        visible: (st.previewPath || "") !== ""
                        iconName: "x"; tip: mira.s.wb_close; diameter: 30
                        onClicked: mira.workbenchPage.closePreview()
                    }
                }
                OutputBox {
                    text: st.previewText || ""
                    error: (st.previewError || "") !== ""
                    placeholder: st.previewLoading ? mira.s.page_loading : (st.previewError || "") !== "" ? st.previewError : mira.s.wb_preview_hint
                    maxHeight: 440
                    Layout.preferredHeight: page.wide ? Math.max(160, Math.min(440, fileList.count * 40 + 12))
                                                      : Math.max(64, Math.min(320, implicitHeight))
                }
                T { visible: !!st.previewCut; text: mira.s.wb_preview_cut; color: Theme.amber; font.pixelSize: Theme.tiny + 1 }
            }
        }
    }

    // ── changes (Git) ───────────────────────────────────────────────
    Card {
        visible: st.tab === "git"
        Empty { visible: !page.hasProject; glyph: "branch"; text: mira.s.wb_pick_project }
        RowLayout {
            visible: page.hasProject
            Layout.fillWidth: true
            spacing: 8
            Glyph { name: "branch"; size: 18; color: Theme.violet }
            T {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: st.gitNotRepo ? mira.s.wb_git_not_repo
                    : !st.gitLoaded ? mira.s.page_loading
                    : gitList.count === 0 ? mira.s.wb_git_clean
                    : (st.gitCountText || "") + "  ·  " + (st.projectName || "")
                font.pixelSize: Theme.small + 1; font.weight: Font.Medium; color: Theme.ink2; wrapMode: Text.NoWrap; elide: Text.ElideRight
            }
            GlyphButton {
                visible: gitList.count > 0
                glyph: "grid"; text: mira.s.wb_show_diff
                onClicked: mira.workbenchPage.showDiff("")
            }
            GlyphButton {
                visible: gitList.count > 0
                glyph: "chat"; text: mira.s.wb_ask_review; primary: true
                onClicked: mira.workbenchPage.askReview()
            }
            T { visible: !!st.gitLoading && !!st.gitLoaded; text: mira.s.page_loading; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
            IconButton { iconName: "refresh"; tip: mira.s.wb_refresh; diameter: 32; enabled: !st.gitLoading; onClicked: mira.workbenchPage.refreshGit() }
        }
        T { visible: (st.gitError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.gitError || ""; color: Theme.danger; font.pixelSize: Theme.small }
        Rectangle {
            visible: page.hasProject && gitList.count > 0
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(236, Math.max(1, gitList.count) * 38 + 12)
            radius: 14
            color: Qt.rgba(0, 0, 0, 0.18); border.width: 1; border.color: Theme.hairline
            ListView {
                id: gitList
                anchors.fill: parent; anchors.margins: 6
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                model: mira.workbenchPage ? mira.workbenchPage.gitRows : []
                ScrollBar.vertical: ScrollBar { width: 5 }
                delegate: RowButton {
                    required property var modelData
                    width: ListView.view.width
                    implicitHeight: 38
                    text: modelData.label
                    mono: true
                    badge: modelData.code
                    badgeColor: page.kindColor(modelData.kind)
                    note: modelData.staged ? mira.s.wb_staged : ""
                    selected: !!st.diffShown && st.diffPath === modelData.path
                    onClicked: mira.workbenchPage.openChange(modelData.path)
                }
            }
        }
        // the diff the owner asked for
        T {
            visible: page.hasProject && !st.diffShown && gitList.count > 0
            Layout.fillWidth: true
            text: mira.s.wb_diff_hint; color: Theme.ink3; font.pixelSize: Theme.small
        }
        ColumnLayout {
            visible: page.hasProject && !!st.diffShown
            Layout.fillWidth: true
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Glyph { name: "file"; size: 16; color: Theme.cyan }
                T {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                    text: (st.diffPath || "") !== "" ? (st.diffLabel || st.diffPath) : mira.s.wb_diff_all
                    font.family: (st.diffPath || "") !== "" ? Theme.mono : Theme.font
                    font.pixelSize: Theme.small; wrapMode: Text.NoWrap; elide: Text.ElideMiddle
                }
                T { visible: !!st.diffLoading; text: mira.s.page_loading; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                IconButton { iconName: "x"; tip: mira.s.wb_close; diameter: 30; onClicked: mira.workbenchPage.closeDiff() }
            }
            T { visible: (st.diffError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.diffError || ""; color: Theme.danger; font.pixelSize: Theme.small }
            T { visible: !st.diffLoading && (st.diffError || "") === "" && (st.diffNote || "") === "" && diffList.count === 0
                text: mira.s.wb_no_diff; color: Theme.ink3; font.pixelSize: Theme.small }
            // a file with no diff of its own: a new file is read whole, a deleted one lives in the whole diff
            Rectangle {
                visible: (st.diffNote || "") !== ""
                readonly property color c: st.diffNote === "new" ? Theme.mint : Theme.amber
                Layout.fillWidth: true
                Layout.preferredHeight: noteRow.implicitHeight + 20
                radius: 14
                color: Qt.rgba(c.r, c.g, c.b, 0.08); border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.32)
                RowLayout {
                    id: noteRow
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
                    spacing: 10
                    Glyph { name: st.diffNote === "new" ? "file" : "archive"; size: 18; color: parent.parent.c }
                    T { Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; font.pixelSize: Theme.small; color: Theme.ink2
                        text: st.diffNote === "new" ? mira.s.wb_new_file_note : mira.s.wb_gone_note }
                    GlyphButton {
                        visible: st.diffNote === "new"
                        glyph: "file"; text: mira.s.wb_read_file; primary: true
                        onClicked: mira.workbenchPage.previewChange(st.diffPath)
                    }
                    GlyphButton {
                        visible: st.diffNote === "gone"
                        glyph: "grid"; text: mira.s.wb_show_diff; primary: true
                        onClicked: mira.workbenchPage.showDiff("")
                    }
                }
            }
            Rectangle {
                visible: diffList.count > 0
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(460, diffList.contentHeight + 16)
                radius: 14
                color: Qt.rgba(0, 0, 0, 0.32); border.width: 1; border.color: Theme.hairline
                LayoutMirroring.enabled: false
                LayoutMirroring.childrenInherit: true
                ListView {
                    id: diffList
                    anchors.fill: parent; anchors.margins: 8
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    model: mira.workbenchPage ? mira.workbenchPage.diff : []
                    ScrollBar.vertical: ScrollBar { width: 5 }
                    delegate: Rectangle {
                        required property var modelData
                        width: ListView.view.width
                        height: line.implicitHeight + (modelData.k === "head" ? 12 : 2)
                        color: modelData.k === "add" ? Qt.rgba(0.28, 0.88, 0.63, 0.10) : modelData.k === "del" ? Qt.rgba(1, 0.36, 0.48, 0.11)
                             : modelData.k === "hunk" ? Qt.rgba(0.21, 0.85, 0.96, 0.07) : "transparent"
                        Text {
                            id: line
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 8; rightMargin: 8; bottomMargin: 1 }
                            text: modelData.t
                            textFormat: Text.PlainText
                            wrapMode: Text.WrapAnywhere
                            horizontalAlignment: Text.AlignLeft
                            font.family: modelData.k === "head" ? Theme.font : Theme.mono
                            font.pixelSize: modelData.k === "head" ? Theme.small : 12
                            font.weight: modelData.k === "head" ? Font.DemiBold : Font.Normal
                            color: modelData.k === "add" ? "#8FF0C4" : modelData.k === "del" ? "#FF9DB2" : modelData.k === "hunk" ? Theme.cyan
                                 : modelData.k === "head" ? Theme.violet : modelData.k === "meta" ? Theme.ink3 : Theme.ink2
                        }
                    }
                }
            }
            T { visible: !!st.diffCut; text: mira.s.wb_diff_cut; color: Theme.amber; font.pixelSize: Theme.tiny + 1 }
        }
    }

    // ── tasks ───────────────────────────────────────────────────────
    Card {
        visible: st.tab === "tasks"
        icon: "rocket"
        accent: Theme.rose
        title: mira.s.wb_new_task
        subtitle: mira.s.wb_task_where + " " + (page.hasProject ? st.projectName : mira.s.wb_no_project_scope)
        MiraField {
            id: taskTitle
            objectName: "taskTitle"
            Layout.fillWidth: true
            placeholderText: mira.s.wb_task_title
            maximumLength: 160
            onAccepted: createBtn.clicked()
            // as in the task's other fields: Escape while typing leaves the field, never the page
            Keys.onShortcutOverride: function(event) { if (event.key === Qt.Key_Escape && text !== "") event.accepted = true }
            Keys.onEscapePressed: function(event) { if (text !== "") { focus = false; event.accepted = true } }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: page.wide ? 2 : 1
            columnSpacing: 10; rowSpacing: 10
            Area {
                id: taskDesc
                objectName: "taskDetails"
                Layout.fillWidth: true
                Layout.preferredHeight: 76
                placeholderText: mira.s.wb_task_desc
            }
            Area {
                id: taskSteps
                Layout.fillWidth: true
                Layout.preferredHeight: 76
                placeholderText: mira.s.wb_task_steps
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            StatusPill { visible: page.tierText !== ""; icon: "shield"; text: page.tierText; tone: page.tierTone }
            Item { Layout.fillWidth: true }
            PillButton {
                id: createBtn
                text: mira.s.wb_create; iconName: "rocket"; primary: true; size: Theme.small; implicitHeight: 36
                enabled: taskTitle.text.trim() !== "" && !st.creating && st.ready !== "offline"
                onClicked: {
                    if (!enabled) return
                    mira.workbenchPage.createTask(taskTitle.text, taskDesc.text, taskSteps.text)
                }
            }
        }
    }
    // the form empties only when the service accepted the task: a refusal keeps every word he typed
    Connections {
        target: mira.workbenchPage
        function onTaskCreated() { taskTitle.text = ""; taskDesc.text = ""; taskSteps.text = "" }
    }
    RowLayout {
        visible: st.tab === "tasks"
        Layout.fillWidth: true
        spacing: 6
        GlyphButton { text: mira.s.wb_scope_project; primary: st.tasksScope === "project"; enabled: page.hasProject; onClicked: mira.workbenchPage.setTasksScope("project") }
        GlyphButton { text: mira.s.wb_scope_all; primary: st.tasksScope === "all"; onClicked: mira.workbenchPage.setTasksScope("all") }
        Item { Layout.fillWidth: true }
        T { visible: !!st.tasksLoading; text: mira.s.page_loading; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
        IconButton { iconName: "refresh"; tip: mira.s.wb_refresh; diameter: 32; onClicked: mira.workbenchPage.loadTasks() }
    }
    T { visible: st.tab === "tasks" && (st.tasksError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.tasksError || ""; color: Theme.danger; font.pixelSize: Theme.small }
    Empty {
        visible: st.tab === "tasks" && taskRepeater.count === 0 && !st.tasksLoading && (st.tasksError || "") === ""
        glyph: "rocket"; text: mira.s.wb_no_tasks
    }
    Repeater {
        id: taskRepeater
        model: mira.workbenchPage ? mira.workbenchPage.tasks : []
        delegate: Glass {
            id: task
            required property var modelData
            readonly property color tone: page.toneColor(modelData.tone)
            readonly property bool busyNow: st.taskBusy === modelData.id
            visible: st.tab === "tasks"
            Layout.fillWidth: true
            Layout.preferredHeight: taskCol.implicitHeight + 28
            radius: 18
            edge: modelData.status === "running" ? Qt.rgba(0.21, 0.85, 0.96, 0.45) : Theme.hairline
            ColumnLayout {
                id: taskCol
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                spacing: 9
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 9
                    Rectangle {
                        Layout.preferredWidth: 10; Layout.preferredHeight: 10; radius: 5
                        color: task.tone
                        opacity: pulse.running ? value : 1
                        property real value: 1
                        SequentialAnimation on value {
                            id: pulse
                            running: task.modelData.status === "running" && mira.motion && task.visible
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.3; duration: 650 } NumberAnimation { to: 1; duration: 650 }
                        }
                    }
                    T { Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: task.modelData.title; font.pixelSize: Theme.body; font.weight: Font.DemiBold; maximumLineCount: 2; elide: Text.ElideRight }
                    StatusPill { text: page.statusText(task.modelData.status)
                                 tone: task.modelData.tone
                                 icon: task.modelData.status === "completed" ? "check" : task.modelData.status === "failed" ? "alert"
                                     : task.modelData.status === "running" ? "pulse" : task.modelData.status === "paused" ? "pause" : "clock" }
                }
                T {
                    Layout.fillWidth: true
                    visible: text !== ""
                    text: [task.modelData.projectName, page.ago(task.modelData.updated)].filter(function(x) { return !!x }).join("  ·  ")
                    font.pixelSize: Theme.tiny + 1; color: Theme.ink3
                }
                T { visible: task.modelData.description !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: task.modelData.description; font.pixelSize: Theme.small; color: Theme.ink2; maximumLineCount: 4; elide: Text.ElideRight }
                // steps
                ColumnLayout {
                    visible: task.modelData.steps.length > 0
                    Layout.fillWidth: true
                    spacing: 5
                    SectionTitle { text: mira.s.wb_steps; icon: "check"; accent: Theme.cyan }
                    Repeater {
                        model: task.modelData.steps
                        delegate: RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 8
                            Rectangle {
                                readonly property color c: modelData.status === "completed" ? Theme.ok : modelData.status === "failed" ? Theme.danger
                                                         : modelData.status === "running" ? Theme.cyan : Theme.off
                                Layout.preferredWidth: 20; Layout.preferredHeight: 20; radius: 10
                                color: Qt.rgba(c.r, c.g, c.b, 0.16); border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.5)
                                Icon { anchors.centerIn: parent; size: 12; weight: 2.2; color: parent.c
                                       name: modelData.status === "completed" ? "check" : modelData.status === "failed" ? "x"
                                           : modelData.status === "running" ? "pulse" : modelData.status === "skipped" ? "chevron" : "clock" }
                            }
                            T { Layout.fillWidth: true; text: modelData.title + (modelData.error ? " — " + modelData.error : "")
                                font.pixelSize: Theme.small; color: modelData.error ? Theme.danger : modelData.status === "completed" ? Theme.ink2 : Theme.ink
                                maximumLineCount: 2; elide: Text.ElideRight }
                        }
                    }
                }
                // the tools it used
                Flow {
                    visible: task.modelData.tools.length > 0
                    Layout.fillWidth: true
                    spacing: 5
                    T { text: mira.s.wb_tools; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; height: 22; verticalAlignment: Text.AlignVCenter; wrapMode: Text.NoWrap }
                    Repeater {
                        model: task.modelData.tools
                        delegate: Rectangle {
                            required property var modelData
                            height: 22; radius: 7; width: toolName.implicitWidth + 14
                            color: Qt.rgba(0.61, 0.48, 1, 0.12); border.width: 1; border.color: Qt.rgba(0.61, 0.48, 1, 0.3)
                            T { id: toolName; anchors.centerIn: parent; text: modelData; font.family: Theme.mono; font.pixelSize: Theme.tiny; color: Theme.violet; wrapMode: Text.NoWrap }
                        }
                    }
                }
                Rectangle {
                    visible: task.modelData.error !== ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: errText.implicitHeight + 16
                    radius: 12
                    color: Qt.rgba(1, 0.36, 0.48, 0.10); border.width: 1; border.color: Qt.rgba(1, 0.36, 0.48, 0.35)
                    RowLayout {
                        anchors { fill: parent; margins: 8 }
                        spacing: 8
                        Icon { name: "alert"; size: 15; color: Theme.danger; Layout.alignment: Qt.AlignTop }
                        T { id: errText; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: task.modelData.error; font.pixelSize: Theme.small; color: "#FFB3C1"; maximumLineCount: 5; elide: Text.ElideRight }
                    }
                }
                OutputBox {
                    visible: task.modelData.result !== ""
                    text: task.modelData.result
                    maxHeight: 160
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 7
                    Repeater {
                        model: task.modelData.actions
                        delegate: PillButton {
                            required property var modelData
                            size: Theme.small; implicitHeight: 34
                            text: modelData === "start" ? (task.modelData.status === "pending" ? mira.s.wb_start : mira.s.wb_retry)
                                : modelData === "pause" ? mira.s.wb_pause : modelData === "resume" ? mira.s.wb_resume : mira.s.wb_cancel
                            iconName: modelData === "pause" ? "pause" : modelData === "cancel" ? "stop"
                                    : modelData === "start" && task.modelData.status !== "pending" ? "refresh" : "play"
                            primary: modelData === "start" || modelData === "resume"
                            danger: modelData === "cancel"
                            enabled: !task.busyNow && st.ready !== "offline"
                            onClicked: mira.workbenchPage.taskAction(task.modelData.id, modelData)
                        }
                    }
                    PillButton {
                        visible: task.modelData.status !== "pending"
                        text: mira.s.wb_show_work; iconName: "book"; size: Theme.small; implicitHeight: 34
                        onClicked: mira.workbenchPage.showTaskWork(task.modelData.id)
                    }
                    PillButton {
                        text: mira.s.wb_ask; iconName: "chat"; size: Theme.small; implicitHeight: 34
                        onClicked: mira.workbenchPage.askAboutTask(task.modelData.id)
                    }
                }
            }
        }
    }

    // ── the owner's terminal ────────────────────────────────────────
    Card {
        visible: st.tab === "terminal"
        icon: "lock"
        accent: Theme.mint
        title: mira.s.wb_term_title
        subtitle: mira.s.wb_term_note
        Flow {
            Layout.fillWidth: true
            spacing: 7
            Repeater {
                model: mira.workbenchPage ? mira.workbenchPage.terminals : []
                delegate: AbstractButton {
                    id: termChip
                    required property var modelData
                    readonly property bool selected: modelData.id === st.terminal
                    height: 34; width: termRow.implicitWidth + 24
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    Accessible.name: modelData.title + (modelData.agent ? " · " + mira.s.wb_term_read_only
                                                        : !modelData.running ? " · " + mira.s.wb_term_ended : "")
                    Keys.onReturnPressed: clicked()
                    onClicked: {
                        mira.workbenchPage.selectTerminal(modelData.id)
                        if (!modelData.agent && modelData.running) Qt.callLater(function() { termInput.forceActiveFocus() })
                    }
                    background: Rectangle {
                        radius: 12
                        color: termChip.selected ? Qt.rgba(0.24, 0.95, 0.77, 0.16) : termChip.hovered ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.035)
                        border.width: termChip.visualFocus ? 2 : 1
                        border.color: termChip.visualFocus ? Theme.cyan : termChip.selected ? Qt.rgba(0.24, 0.95, 0.77, 0.5) : Theme.hairline
                    }
                    contentItem: Item {
                        opacity: termChip.modelData.running || termChip.selected ? 1 : 0.7
                        Row {
                            id: termRow
                            anchors.centerIn: parent
                            spacing: 7
                            Rectangle { width: 8; height: 8; radius: 4; anchors.verticalCenter: parent.verticalCenter
                                        color: termChip.modelData.running ? Theme.mint : Theme.off }
                            Glyph { name: termChip.modelData.agent ? "chip" : "terminal"; size: 15; color: termChip.modelData.agent ? Theme.violet : Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
                            T { text: termChip.modelData.title; font.pixelSize: Theme.small; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(implicitWidth, 200); elide: Text.ElideRight }
                        }
                    }
                }
            }
            GlyphButton {
                visible: (st.termsHidden || 0) > 0 || !!st.showAllTerms
                glyph: st.showAllTerms ? "chevron-up" : "chevron-down"
                text: st.showAllTerms ? mira.s.wb_term_show_fewer : mira.s.wb_term_show_all + " (" + (st.termsHidden || 0) + ")"
                onClicked: mira.workbenchPage.setShowAllTerms(!st.showAllTerms)
            }
            GlyphButton {
                glyph: "plus"; text: mira.s.wb_term_new; primary: true
                enabled: !st.termStarting && st.ready !== "offline"
                onClicked: mira.workbenchPage.newTerminal()
            }
        }
        Empty { visible: (st.terminal || "") === ""; glyph: "terminal"; text: mira.s.wb_term_none }
        Rectangle {
            visible: (st.terminal || "") !== ""
            Layout.fillWidth: true
            Layout.preferredHeight: 360
            radius: 14
            color: Qt.rgba(0.012, 0.016, 0.045, 0.92)
            border.width: 1; border.color: termInput.activeFocus ? Qt.rgba(0.24, 0.95, 0.77, 0.45) : Theme.hairline
            LayoutMirroring.enabled: false
            LayoutMirroring.childrenInherit: true
            RowLayout {
                id: consoleHead
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                spacing: 8
                Rectangle { Layout.preferredWidth: 9; Layout.preferredHeight: 9; radius: 5; color: st.termRunning ? Theme.mint : Theme.off }
                T { Layout.fillWidth: true; text: (st.termTitle || "") + ((st.termCwd || "") !== "" ? "  —  " + st.termCwd : "")
                    font.family: Theme.mono; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap; elide: Text.ElideMiddle }
            }
            Flickable {
                id: termFlick
                property bool follow: true
                anchors { left: parent.left; right: parent.right; top: consoleHead.bottom; bottom: parent.bottom; margins: 10; topMargin: 6 }
                contentHeight: termText.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { width: 5 }
                onMovementEnded: follow = contentY >= contentHeight - height - 8
                onContentHeightChanged: if (follow) contentY = Math.max(0, contentHeight - height)
                TextEdit {
                    id: termText
                    width: termFlick.width - 8
                    readOnly: true; selectByMouse: true
                    wrapMode: TextEdit.WrapAnywhere
                    textFormat: TextEdit.PlainText
                    text: st.termOutput || ""
                    color: "#D6E2FF"
                    selectionColor: Qt.rgba(0.24, 0.95, 0.77, 0.3)
                    font.family: Theme.mono; font.pixelSize: 13
                    horizontalAlignment: TextEdit.AlignLeft
                }
            }
            T { anchors.centerIn: parent; visible: (st.termOutput || "") === ""; color: Theme.ink3; font.pixelSize: Theme.small
                text: st.termRunning ? mira.s.wb_term_waiting : mira.s.wb_term_exited }
        }
        RowLayout {
            visible: (st.terminal || "") !== "" && !st.termAgent && !!st.termRunning
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                radius: Theme.rControl
                color: Qt.rgba(1, 1, 1, termInput.activeFocus ? 0.07 : 0.045)
                border.width: 1; border.color: termInput.activeFocus ? Qt.rgba(0.24, 0.95, 0.77, 0.55) : Theme.hairline
                LayoutMirroring.enabled: false
                LayoutMirroring.childrenInherit: true
                Icon { id: prompt; anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                       name: "chevron"; size: 15; weight: 2.2; color: Theme.mint }
                TextField {
                    id: termInput
                    property var history: []
                    property int back: -1
                    anchors { left: prompt.right; right: parent.right; top: parent.top; bottom: parent.bottom; leftMargin: 6; rightMargin: 8 }
                    background: null
                    color: Theme.ink
                    placeholderText: mira.s.wb_term_input
                    placeholderTextColor: Theme.ink3
                    selectionColor: Qt.rgba(0.24, 0.95, 0.77, 0.3)
                    // the command is monospace; the (Arabic or English) hint keeps Mira's own face
                    font.family: text === "" ? Theme.font : Theme.mono
                    font.pixelSize: 13
                    horizontalAlignment: text === "" && page.ar ? TextInput.AlignRight : TextInput.AlignLeft
                    inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                    Accessible.name: mira.s.wb_term_input
                    onAccepted: {
                        mira.workbenchPage.sendTerminal(text)
                        if (text.trim() !== "") { history.push(text); if (history.length > 50) history.shift() }
                        back = -1; text = ""; termFlick.follow = true
                    }
                    Keys.onUpPressed: { if (history.length === 0) return; back = back < 0 ? history.length - 1 : Math.max(0, back - 1); text = history[back] }
                    Keys.onDownPressed: { if (back < 0) return; back = back + 1; if (back >= history.length) { back = -1; text = "" } else text = history[back] }
                    // Mira's window shortcuts must not take a terminal's keys: Escape clears the line he is
                    // typing (it closes the page only from an empty line), Ctrl+L clears the view, Ctrl+K
                    // deletes to the end of the line — none of them jumps to the composer.
                    Keys.onShortcutOverride: function(event) {
                        var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
                        if ((event.key === Qt.Key_Escape && text !== "") || (ctrl && (event.key === Qt.Key_L || event.key === Qt.Key_K)))
                            event.accepted = true
                    }
                    Keys.onPressed: function(event) {
                        var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
                        if (ctrl && event.key === Qt.Key_C && selectedText === "") {
                            mira.workbenchPage.interruptTerminal(); event.accepted = true
                        } else if (ctrl && event.key === Qt.Key_L) {
                            mira.workbenchPage.clearTerminalView(); termFlick.follow = true; event.accepted = true
                        } else if (event.key === Qt.Key_Escape && text !== "") {
                            text = ""; back = -1; event.accepted = true
                        }
                    }
                }
            }
            IconButton { iconName: "send"; tip: mira.s.send; accent: Theme.mint; active: termInput.text !== ""; onClicked: termInput.accepted() }
            GlyphButton { glyph: "stop"; compact: !page.roomy; text: mira.s.wb_term_interrupt; onClicked: mira.workbenchPage.interruptTerminal() }
            GlyphButton { glyph: "x"; compact: !page.roomy; text: mira.s.wb_term_stop; danger: true; onClicked: mira.workbenchPage.stopTerminal() }
        }
        RowLayout {
            visible: (st.terminal || "") !== "" && (!!st.termAgent || !st.termRunning)
            Layout.fillWidth: true
            spacing: 8
            Icon { name: st.termAgent ? "lock" : "stop"; size: 15; color: Theme.ink3 }
            T { Layout.fillWidth: true; font.pixelSize: Theme.small; color: Theme.ink3
                text: st.termAgent ? mira.s.wb_term_agent
                    : mira.s.wb_term_exited + ((st.termExit !== undefined && st.termExit >= 0) ? " (" + st.termExit + ")" : "") }
        }
        T { visible: (st.termError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.termError || ""; color: Theme.danger; font.pixelSize: Theme.small }
    }

    // ── coding agents ───────────────────────────────────────────────
    // how they run, and where they open — said plainly, so "Run" never implies a folder it does not use
    RowLayout {
        visible: st.tab === "agents"
        Layout.fillWidth: true
        spacing: 8
        Glyph { name: "folder"; size: 16; color: st.agentsInProject && page.hasProject ? Theme.violet : Theme.ink3; Layout.alignment: Qt.AlignTop }
        T {
            Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; font.pixelSize: Theme.small; color: Theme.ink3
            text: mira.s.wb_agents_note + ". " + (st.agentsInProject && page.hasProject
                                                   ? mira.s.wb_agents_where_project + (page.ar ? " «" + (st.projectName || "") + "»" : " \"" + (st.projectName || "") + "\"")
                                                   : mira.s.wb_agents_where_home)
        }
    }
    GridLayout {
        visible: st.tab === "agents"
        Layout.fillWidth: true
        columns: page.wide ? 2 : 1
        columnSpacing: 12; rowSpacing: 12
        Repeater {
            model: mira.workbenchPage ? mira.workbenchPage.agents : []
            delegate: Glass {
                id: agent
                required property var modelData
                readonly property string blurb: modelData.key === "opencode" ? mira.s.wb_agent_opencode : modelData.key === "claude" ? mira.s.wb_agent_claude
                                              : modelData.key === "codex" ? mira.s.wb_agent_codex : mira.s.wb_agent_hermes
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: agentCol.implicitHeight + 28
                radius: 18
                edge: modelData.key === "opencode" ? Qt.rgba(0.21, 0.85, 0.96, 0.4) : Theme.hairline
                ColumnLayout {
                    id: agentCol
                    anchors { fill: parent; margins: 14 }
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 44; Layout.preferredHeight: 44; radius: 14
                            gradient: Gradient {
                                GradientStop { position: 0; color: agent.modelData.engine ? Qt.rgba(1, 0.44, 0.71, 0.5) : Qt.rgba(0.42, 0.33, 0.94, 0.6) }
                                GradientStop { position: 1; color: agent.modelData.engine ? Qt.rgba(0.61, 0.48, 1, 0.45) : Qt.rgba(0.17, 0.78, 0.9, 0.5) }
                            }
                            T { anchors.centerIn: parent; text: agent.modelData.name.charAt(0); font.pixelSize: 20; font.weight: Font.Bold; color: "white" }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            RowLayout {
                                spacing: 8
                                T { text: agent.modelData.name; font.pixelSize: Theme.body; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                                StatusPill {
                                    text: agent.modelData.engine && agent.modelData.installed ? mira.s.wb_engine
                                        : !agent.modelData.known ? mira.s.wb_unknown : agent.modelData.installed ? mira.s.wb_installed : mira.s.wb_not_installed
                                    tone: !agent.modelData.known ? "off" : agent.modelData.installed ? "ok" : "off"
                                    icon: agent.modelData.installed ? "check" : ""
                                }
                            }
                            T { Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: agent.blurb; font.pixelSize: Theme.small; color: Theme.ink3; maximumLineCount: 2; elide: Text.ElideRight }
                        }
                    }
                    Item { Layout.fillHeight: true }    // a card stretched to its row keeps its actions at the bottom
                    RowLayout {
                        Layout.fillWidth: true
                        visible: (agent.modelData.canRun && agent.modelData.installed) || (agent.modelData.known && !agent.modelData.installed)
                        spacing: 8
                        Item { Layout.fillWidth: true }
                        PillButton {
                            visible: agent.modelData.known && !agent.modelData.installed
                            text: mira.s.wb_install; iconName: "download"; size: Theme.small; implicitHeight: 34
                            onClicked: mira.workbenchPage.installAgent(agent.modelData.key)
                        }
                        PillButton {
                            visible: agent.modelData.canRun && agent.modelData.installed
                            text: mira.s.wb_run; iconName: "play"; size: Theme.small; implicitHeight: 34
                            primary: true
                            onClicked: mira.workbenchPage.openAgent(agent.modelData.key)
                        }
                    }
                    Rectangle {
                        visible: st.agentNoteKey === agent.modelData.key && (st.agentNote || "") !== ""
                        Layout.fillWidth: true
                        Layout.preferredHeight: noteText.implicitHeight + 16
                        radius: 12
                        color: Qt.rgba(1, 0.77, 0.42, 0.10); border.width: 1; border.color: Qt.rgba(1, 0.77, 0.42, 0.35)
                        TextEdit {
                            id: noteText
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
                            text: st.agentNote || ""
                            readOnly: true; selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            color: Theme.amber
                            font.family: Theme.font; font.pixelSize: Theme.small
                            selectionColor: Qt.rgba(1, 0.77, 0.42, 0.3)
                        }
                    }
                }
            }
        }
    }
    AbstractButton {
        id: codeSpace
        visible: st.tab === "agents"
        Layout.fillWidth: true
        implicitHeight: 70
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: mira.s.wb_open_code + " · " + mira.s.wb_open_code_sub
        Keys.onReturnPressed: clicked()
        onClicked: mira.workbenchPage.openAgent("code")
        background: Rectangle {
            radius: 18
            color: codeSpace.down ? Theme.glassHover : codeSpace.hovered ? Qt.rgba(1, 1, 1, 0.075) : Qt.rgba(1, 1, 1, 0.04)
            border.width: codeSpace.visualFocus ? 2 : 1
            border.color: codeSpace.visualFocus ? Theme.cyan : codeSpace.hovered ? Theme.hairlineStrong : Theme.hairline
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: RowLayout {
            spacing: 12
            Rectangle {
                Layout.leftMargin: 14
                Layout.preferredWidth: 42; Layout.preferredHeight: 42; radius: 13
                color: Qt.rgba(0.21, 0.85, 0.96, 0.14)
                Glyph { anchors.centerIn: parent; name: "terminal"; size: 20; color: Theme.cyan }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                T { text: mira.s.wb_open_code; font.pixelSize: Theme.body; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                T { text: mira.s.wb_open_code_sub; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; elide: Text.ElideRight; wrapMode: Text.NoWrap }
            }
            Icon { Layout.rightMargin: 16; name: "external"; size: 17; color: Theme.ink3 }
        }
        scale: down ? 0.99 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    // ── agent sessions (read only) ──────────────────────────────────
    Card {
        visible: st.tab === "sessions"
        icon: (st.session || "") !== "" ? "" : "chat"
        accent: Theme.violet
        title: (st.session || "") !== "" ? "" : mira.s.wb_tab_sessions
        subtitle: (st.session || "") !== "" ? "" : mira.s.wb_sessions_note

        // the list
        T { visible: (st.session || "") === "" && (st.sessionsError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.sessionsError || ""; color: Theme.danger; font.pixelSize: Theme.small }
        Empty {
            visible: (st.session || "") === "" && sessionRepeater.count === 0 && (st.sessionsError || "") === ""
            glyph: "chat"; text: st.sessionsLoading ? mira.s.page_loading : mira.s.wb_no_sessions
        }
        Repeater {
            id: sessionRepeater
            model: mira.workbenchPage ? mira.workbenchPage.sessions : []
            delegate: RowButton {
                required property var modelData
                visible: (st.session || "") === ""
                Layout.fillWidth: true
                implicitHeight: 44
                glyph: modelData.task ? "rocket" : "chat"
                glyphColor: modelData.task ? Theme.rose : Theme.violet
                text: modelData.label || modelData.key
                note: modelData.when
                onClicked: mira.workbenchPage.openSession(modelData.id)
            }
        }

        // one transcript
        RowLayout {
            visible: (st.session || "") !== ""
            Layout.fillWidth: true
            spacing: 10
            GlyphButton { glyph: "back"; mirrorGlyph: page.ar; text: mira.s.wb_back; onClicked: mira.workbenchPage.closeSession() }
            T { Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.sessionLabel || ""; font.pixelSize: Theme.body; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight }
            T { visible: !!st.transcriptLoading; text: mira.s.page_loading; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
        }
        T { visible: (st.session || "") !== "" && (st.transcriptError || "") !== ""; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft; text: st.transcriptError || ""; color: Theme.danger; font.pixelSize: Theme.small }
        T { visible: (st.session || "") !== "" && !st.transcriptLoading && (st.transcriptError || "") === "" && transcriptList.count === 0
            text: mira.s.wb_no_messages; color: Theme.ink3; font.pixelSize: Theme.small }
        ListView {
            id: transcriptList
            visible: (st.session || "") !== "" && count > 0
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(520, contentHeight + 4)
            clip: true
            spacing: 8
            boundsBehavior: Flickable.StopAtBounds
            model: mira.workbenchPage ? mira.workbenchPage.transcript : []
            ScrollBar.vertical: ScrollBar { width: 5 }
            onCountChanged: Qt.callLater(positionViewAtEnd)
            delegate: Item {
                id: msg
                required property var modelData
                readonly property bool tool: modelData.role === "tool"
                readonly property bool mine: modelData.role === "user"
                readonly property color sc: modelData.status === "success" ? Theme.ok : modelData.status === "error" ? Theme.danger
                                          : modelData.status === "pending" ? Theme.amber : Theme.cyan
                property bool open: false
                width: ListView.view.width
                height: tool ? toolBox.height : bubble.height
                // a tool the agent used (its output opens on a click)
                Rectangle {
                    id: toolBox
                    visible: msg.tool
                    width: parent.width
                    height: 36 + (msg.open && msg.modelData.body ? toolBody.implicitHeight + 12 : 0)
                    radius: 12
                    color: Qt.rgba(msg.sc.r, msg.sc.g, msg.sc.b, 0.06)
                    border.width: 1; border.color: Qt.rgba(msg.sc.r, msg.sc.g, msg.sc.b, 0.28)
                    AbstractButton {
                        id: toolHead
                        width: parent.width; height: 36
                        enabled: !!msg.modelData.body
                        hoverEnabled: true
                        focusPolicy: Qt.StrongFocus
                        Accessible.name: (msg.modelData.tool || "") + " · " + msg.modelData.status
                        Keys.onReturnPressed: clicked()
                        onClicked: msg.open = !msg.open
                        background: Rectangle { radius: 12; color: toolHead.hovered ? Qt.rgba(1, 1, 1, 0.04) : "transparent"
                                                border.width: toolHead.visualFocus ? 2 : 0; border.color: Theme.cyan }
                        contentItem: RowLayout {
                            spacing: 8
                            Icon { Layout.leftMargin: 10; name: "wrench"; size: 15; color: msg.sc }
                            T { text: msg.modelData.tool || ""; font.family: Theme.mono; font.pixelSize: Theme.small; color: Theme.ink; wrapMode: Text.NoWrap }
                            T { text: msg.modelData.status === "success" ? mira.s.wb_tool_success : msg.modelData.status === "error" ? mira.s.wb_tool_error
                                    : msg.modelData.status === "pending" ? mira.s.wb_tool_pending : mira.s.wb_tool_running
                                font.pixelSize: Theme.tiny + 1; color: msg.sc; wrapMode: Text.NoWrap }
                            Item { Layout.fillWidth: true }
                            T { text: msg.modelData.when || ""; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
                                Layout.rightMargin: msg.modelData.body ? 0 : 12 }
                            Icon { visible: !!msg.modelData.body; Layout.rightMargin: 10; name: msg.open ? "chevron-down" : "chevron"; size: 14; color: Theme.ink3
                                   transform: Scale { xScale: page.ar && !msg.open ? -1 : 1; origin.x: 7 } }
                        }
                    }
                    TextEdit {
                        id: toolBody
                        visible: msg.open
                        anchors { left: parent.left; right: parent.right; top: toolHead.bottom; leftMargin: 12; rightMargin: 12 }
                        text: msg.modelData.body || ""
                        readOnly: true; selectByMouse: true
                        wrapMode: TextEdit.WrapAnywhere
                        textFormat: TextEdit.PlainText
                        color: Theme.ink2
                        font.family: Theme.mono; font.pixelSize: 12
                        LayoutMirroring.enabled: false
                        horizontalAlignment: TextEdit.AlignLeft
                    }
                }
                // what the owner or the agent said
                Rectangle {
                    id: bubble
                    visible: !msg.tool
                    width: Math.min(parent.width * 0.86, Math.max(measure.implicitWidth, who.implicitWidth) + 30)
                    height: bubbleText.implicitHeight + who.implicitHeight + 24
                    anchors.right: msg.mine ? parent.right : undefined
                    anchors.left: msg.mine ? undefined : parent.left
                    radius: 16
                    color: msg.mine ? Qt.rgba(0.21, 0.72, 0.95, 0.15) : Qt.rgba(0.62, 0.48, 1.0, 0.12)
                    border.width: 1
                    border.color: msg.mine ? Qt.rgba(0.3, 0.8, 1, 0.26) : Qt.rgba(0.72, 0.55, 1, 0.22)
                    T { id: measure; visible: false; text: msg.tool ? "" : msg.modelData.text; wrapMode: Text.NoWrap; font.pixelSize: Theme.small + 1 }
                    T {
                        id: bubbleText
                        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 15; rightMargin: 15; topMargin: 10 }
                        text: msg.tool ? "" : msg.modelData.text
                        font.pixelSize: Theme.small + 1
                    }
                    T {
                        id: who
                        anchors { left: parent.left; top: bubbleText.bottom; leftMargin: 15; topMargin: 4 }
                        text: (msg.mine ? mira.s.wb_you : mira.s.wb_agent_role) + (msg.modelData.when ? " · " + msg.modelData.when : "")
                        font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
                    }
                }
            }
        }
    }
}
