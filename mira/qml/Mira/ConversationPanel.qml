import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import "icons.js" as Icons

// The conversation: words and verified results, newest at the bottom, and every earlier chat one
// tap away. «محادثة جديدة» starts a fresh chat (the model stops receiving the earlier one); the
// history drawer lists, searches, opens, renames, pins and archives chats. All of it lives only
// in Mira's local files on this computer.
Glass {
    id: panel
    objectName: "conversationPanel"
    radius: Theme.rPanel
    property bool showHeader: true
    property bool drawerOpen: false
    signal suggestion(string text)

    // The chat's history object (the controller's chatHistory) is looked up by name: until the controller
    // exposes it the panel keeps its old «clear view» control and shows no history control.
    readonly property var history: mira["chatHistory"] || null
    readonly property var hs: history ? history.state : ({})
    readonly property string chatTitle: hs.currentTitle || ""
    // A short panel that is only part of its area (the narrow window puts it under Mira's face)
    // lends its drawer that whole area, so the chat list is never a sliver.
    readonly property bool drawerLifted: parent !== null && height < 440 && height < parent.height * 0.7

    function openDrawer() {
        if (!history) return
        drawerOpen = true
        history.refresh()
        search.forceActiveFocus()
    }
    function closeDrawer() {
        drawerOpen = false
        if (search.text !== "") search.text = ""
    }
    function newChat() {
        if (!history) return
        history.newChat()
        closeDrawer()
    }

    // Glyphs this panel needs beyond the shared set; the shared set wins once it carries them.
    // (an Icon: the same drawing on both scene graphs, clipped correctly on the software one)
    component Glyph: Icon {
        color: Theme.ink2
        size: 18
        readonly property var local: ({
            "plus": "M12 5v14 M5 12h14",
            "compose": "M11 4.5H6A1.5 1.5 0 0 0 4.5 6v12A1.5 1.5 0 0 0 6 19.5h12a1.5 1.5 0 0 0 1.5-1.5v-5 M17.5 3.5l3 3-7.5 7.5-3.5.5.5-3.5z",
            "search": "M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z M20 20l-4.4-4.4",
            "pin": "M9 3.5h6 M10 3.5v5.2L7 12.5V14h10v-1.5l-3-3.8V3.5 M12 14v6.5",
            "archive": "M3.5 4.5h17v4h-17z M5 8.5V19a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8.5 M10 12.5h4",
            "pencil": "M15.5 4.5l4 4L8.5 19.5 4 20l.5-4.5z M13.5 6.5l4 4",
            "history": "M4 12a8 8 0 1 0 2.4-5.7 M4 4.5v4h4 M12 8v4l3 2"
        })
        path: Icons.paths[name] ? "" : (local[name] || "")
    }

    // a round control with one glyph, a tooltip and an accessible name
    component GlyphButton: AbstractButton {
        id: gb
        property string glyph: "sparkle"
        property string tip: ""
        property bool lit: false
        property color accent: Theme.cyan
        property real diameter: 32
        implicitWidth: diameter
        implicitHeight: diameter
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: tip
        ToolTip.visible: hovered && tip.length > 0
        ToolTip.text: tip
        ToolTip.delay: 450
        background: Rectangle {
            radius: width / 2
            color: gb.lit ? Qt.rgba(gb.accent.r, gb.accent.g, gb.accent.b, 0.18)
                 : gb.down ? Theme.glassHover : gb.hovered ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.03)
            border.width: gb.visualFocus ? 2 : 1
            border.color: gb.visualFocus ? Theme.cyan : gb.lit ? Qt.rgba(gb.accent.r, gb.accent.g, gb.accent.b, 0.5)
                        : gb.hovered ? Theme.hairlineStrong : Theme.hairline
        }
        contentItem: Item {
            Glyph {
                anchors.centerIn: parent
                name: gb.glyph
                size: Math.round(gb.diameter * 0.5)
                color: gb.lit ? gb.accent : gb.hovered ? Theme.ink : Theme.ink2
            }
        }
        scale: down ? 0.93 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    // a pill with a glyph and a label (the new-chat action; the archive filter)
    component GlyphPill: AbstractButton {
        id: gp
        property string glyph: ""
        property bool primary: false
        property bool selected: false
        implicitHeight: 32
        implicitWidth: pillRow.implicitWidth + 24
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text
        background: Rectangle {
            radius: height / 2
            gradient: gp.primary ? pillGrad : null
            color: gp.primary ? "transparent" : gp.selected ? Qt.rgba(0.61, 0.48, 1, 0.20)
                 : gp.hovered ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.04)
            border.width: gp.visualFocus ? 2 : 1
            border.color: gp.visualFocus ? Theme.cyan : gp.primary ? Qt.rgba(1, 1, 1, 0.22)
                        : gp.selected ? Qt.rgba(0.72, 0.55, 1, 0.55) : Theme.hairline
            Gradient {
                id: pillGrad
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: gp.hovered ? "#7C68FF" : "#6A55F0" }
                GradientStop { position: 1; color: gp.hovered ? "#3FE0F8" : "#2CC6E6" }
            }
        }
        contentItem: Item {
            implicitWidth: pillRow.implicitWidth
            Row {
                id: pillRow
                anchors.centerIn: parent
                spacing: 6
                Glyph { visible: gp.glyph !== ""; name: gp.glyph || "sparkle"; size: 15; weight: 2
                        color: gp.primary ? "white" : gp.selected ? Theme.ink : Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
                T { text: gp.text; font.pixelSize: Theme.small; font.weight: gp.primary || gp.selected ? Font.DemiBold : Font.Medium
                    color: gp.primary ? "white" : gp.selected ? Theme.ink : Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
            }
        }
        scale: down ? 0.96 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    Shortcut { sequences: ["Ctrl+N"]; enabled: panel.visible && panel.history !== null; onActivated: panel.newChat() }
    Shortcut { sequences: ["Ctrl+H"]; enabled: panel.visible && panel.history !== null
               onActivated: panel.drawerOpen ? panel.closeDrawer() : panel.openDrawer() }

    // ── header: which chat is open, its history, a new chat ──
    Item {
        id: header
        enabled: !panel.drawerOpen            // behind the open drawer: no clicks, no Tab stops
        visible: panel.showHeader || panel.history !== null
        height: panel.showHeader ? 44 : panel.history ? 34 : 0
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14; bottomMargin: 0 }

        Row {
            id: titleRow
            visible: panel.showHeader
            anchors { left: parent.left; right: headerTools.left; rightMargin: 10; verticalCenter: parent.verticalCenter }
            spacing: 8
            Icon { name: "chat"; size: 16; color: Theme.violet; anchors.verticalCenter: parent.verticalCenter }
            Column {
                anchors.verticalCenter: parent.verticalCenter
                width: titleRow.width - 24
                // AlignLeft is the reading side: layout mirroring turns it right in Arabic
                T { width: parent.width; horizontalAlignment: Text.AlignLeft; text: mira.s.conversation; font.pixelSize: Theme.small
                    font.weight: Font.DemiBold; color: Theme.ink2; font.letterSpacing: 0.3; wrapMode: Text.NoWrap }
                T { visible: panel.chatTitle !== ""; width: parent.width; horizontalAlignment: Text.AlignLeft; text: panel.chatTitle
                    font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap; elide: Text.ElideRight }
            }
        }
        Row {
            id: headerTools
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 6
            GlyphButton {
                visible: panel.history !== null
                glyph: "history"; diameter: 32
                tip: mira.s.ch_history
                lit: panel.drawerOpen
                accent: Theme.violet
                onClicked: panel.drawerOpen ? panel.closeDrawer() : panel.openDrawer()
            }
            GlyphPill {
                visible: panel.history !== null
                glyph: "compose"
                text: mira.s.ch_new
                primary: list.count > 0
                ToolTip.visible: hovered
                ToolTip.text: mira.s.ch_new_tip
                ToolTip.delay: 450
                onClicked: panel.newChat()
            }
            IconButton {   // until the history object exists: the view can only be cleared
                visible: panel.history === null && panel.showHeader && list.count > 0
                diameter: 30; iconName: "x"; tip: mira.s.clear_view
                onClicked: mira.clearView()
            }
        }
    }

    ListView {
        id: list
        objectName: "chatList"
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: parent.bottom; margins: 14; topMargin: 4 }
        // Behind the open drawer the conversation takes no clicks, wheel or focus (its entries' copy
        // controls and right-click are disabled with it).
        enabled: !panel.drawerOpen
        clip: true
        model: mira.chatModel
        spacing: 2
        boundsBehavior: Flickable.StopAtBounds
        delegate: MessageDelegate {}
        // each entry learns where a new day begins (the `day` role of the chat model)
        section.property: "day"
        section.criteria: ViewSection.FullString
        // Follow the newest entry until the owner scrolls up to read; scrolling back down resumes it.
        property bool follow: true
        onMovementEnded: follow = atYEnd
        onContentHeightChanged: if (follow) Qt.callLater(positionViewAtEnd)
        onCountChanged: if (follow || count <= 1) { follow = true; Qt.callLater(positionViewAtEnd) }
        onHeightChanged: if (follow) Qt.callLater(positionViewAtEnd)
        Component.onCompleted: Qt.callLater(positionViewAtEnd)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }
        // No `add` transition: a view transition freezes where the entries after a new one land, and an
        // entry's height settles a frame after it is made (its reply pieces are laid out then), which
        // left gaps. A new entry animates itself instead (MessageDelegate's `appear`).
    }

    // back to the newest words after scrolling up
    IconButton {
        anchors { horizontalCenter: list.horizontalCenter; bottom: list.bottom; bottomMargin: 6 }
        enabled: !panel.drawerOpen
        visible: !list.follow && list.count > 0 && !list.atYEnd && !panel.drawerOpen
        diameter: 34; iconName: "chevron-down"; tip: mira.s.ch_latest
        onClicked: { list.follow = true; list.positionViewAtEnd() }
    }

    // empty state that teaches
    Column {
        anchors.centerIn: parent
        width: parent.width - 48
        spacing: 12
        visible: list.count === 0 && !panel.drawerOpen
        Icon { anchors.horizontalCenter: parent.horizontalCenter; name: "sparkle"; size: 30; color: Theme.violet }
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: mira.s.empty_chat_title; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: mira.s.empty_chat_body; color: Theme.ink2; font.pixelSize: Theme.small + 1 }
        Flow {
            width: parent.width
            spacing: 8
            layoutDirection: mira.lang === "ar" ? Qt.RightToLeft : Qt.LeftToRight
            Repeater {
                model: mira.home.linked ? [mira.s.sg_home_status, mira.s.sg_weather, mira.s.sg_pc_status, mira.s.sg_browser]
                                        : [mira.s.sg_update, mira.s.sg_pc_status, mira.s.sg_install, mira.s.sg_reminder]
                delegate: PillButton { required property string modelData; text: modelData; size: Theme.small; implicitHeight: 32; onClicked: panel.suggestion(modelData) }
            }
        }
    }

    // ── the history drawer: every chat, searchable, over the conversation ──
    FocusScope {
        id: drawer
        objectName: "chatDrawer"
        parent: panel.drawerLifted ? panel.parent : panel
        anchors.fill: parent
        z: 10
        visible: panel.drawerOpen || slide.running
        enabled: panel.drawerOpen
        Keys.onShortcutOverride: function(event) { event.accepted = event.key === Qt.Key_Escape }
        Keys.onEscapePressed: panel.closeDrawer()

        Glass {
            id: sheet
            width: parent.width
            height: parent.height
            radius: panel.radius
            tint: Qt.rgba(0.045, 0.055, 0.13, 1.0)   // opaque: the conversation must not show through
            edge: Theme.hairlineStrong
            property real offset: panel.drawerOpen ? 0 : 40
            x: (mira.lang === "ar" ? 1 : -1) * offset
            opacity: panel.drawerOpen ? 1 : 0
            Behavior on offset { NumberAnimation { id: slide; duration: Theme.normal; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: Theme.normal } }

            // Everything that lands on the drawer stays in it: every button, the wheel and hover
            // (the first child, so the drawer's own controls are above it and still work).
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.AllButtons
                hoverEnabled: true
                onWheel: function(wheel) { wheel.accepted = true }
            }

            Item {
                id: dhead
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                height: 40
                GlyphButton {
                    id: back
                    anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                    glyph: "x"; diameter: 32; tip: mira.s.ch_close
                    onClicked: panel.closeDrawer()
                }
                Row {
                    anchors { left: back.right; leftMargin: 10; verticalCenter: parent.verticalCenter }
                    spacing: 8
                    Glyph { name: "history"; size: 17; color: Theme.violet; anchors.verticalCenter: parent.verticalCenter }
                    T { text: mira.s.ch_title; font.pixelSize: Theme.title; font.weight: Font.DemiBold; wrapMode: Text.NoWrap
                        anchors.verticalCenter: parent.verticalCenter }
                }
                GlyphPill {
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    glyph: "compose"; text: mira.s.ch_new; primary: true
                    ToolTip.visible: hovered
                    ToolTip.text: mira.s.ch_new_tip
                    ToolTip.delay: 450
                    onClicked: panel.newChat()
                }
            }

            MiraField {
                id: search
                objectName: "chatSearch"
                anchors { left: parent.left; right: parent.right; top: dhead.bottom; margins: 14; topMargin: 10 }
                placeholderText: mira.s.ch_search
                horizontalAlignment: TextInput.AlignLeft       // mirrored: the reading side in Arabic too
                // text fields do not mirror their padding: the glyph sits on the reading side
                leftPadding: mira.lang === "ar" ? (text !== "" ? 38 : 14) : 38
                rightPadding: mira.lang === "ar" ? 38 : (text !== "" ? 38 : 14)
                Accessible.name: mira.s.ch_search
                onTextChanged: searchDelay.restart()
                Keys.onDownPressed: threads.enter()
                Glyph { name: "search"; size: 16; color: Theme.ink3; anchors { left: parent.left; leftMargin: 13; verticalCenter: parent.verticalCenter } }
                GlyphButton {
                    visible: search.text !== ""
                    anchors { right: parent.right; rightMargin: 5; verticalCenter: parent.verticalCenter }
                    glyph: "x"; diameter: 28; tip: mira.s.ch_search_clear
                    onClicked: { search.text = ""; search.forceActiveFocus() }
                }
                Timer { id: searchDelay; interval: 220; onTriggered: if (panel.history) panel.history.search(search.text) }
            }

            Row {
                id: filters
                anchors { left: parent.left; top: search.bottom; margins: 14; topMargin: 10 }
                spacing: 8
                visible: search.text === ""
                GlyphPill { text: mira.s.ch_all; selected: !panel.hs.archived; implicitHeight: 30
                            onClicked: if (panel.history) panel.history.showArchived(false) }
                GlyphPill { glyph: "archive"; text: mira.s.ch_archived; selected: panel.hs.archived === true; implicitHeight: 30
                            onClicked: if (panel.history) panel.history.showArchived(true) }
            }

            ListView {
                id: threads
                objectName: "chatThreads"
                anchors { left: parent.left; right: parent.right; top: filters.visible ? filters.bottom : search.bottom
                          bottom: parent.bottom; margins: 10; topMargin: 8 }
                clip: true
                spacing: 2
                model: panel.history ? panel.history.threadModel : null
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationEnabled: true
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 5 }
                // From the search field: the first chat's row takes the keys; Up/Down then walk the
                // rows (the current row keeps the focus), Return or Space opens one.
                function enter() {
                    if (count === 0) return
                    currentIndex = 0
                    positionViewAtBeginning()
                    if (currentItem) currentItem.forceActiveFocus()
                }
                onCurrentItemChanged: if (activeFocus && currentItem) currentItem.forceActiveFocus()

                delegate: FocusScope {
                    id: entry
                    required property string tid
                    required property string title
                    required property string when
                    required property string preview
                    required property string header
                    required property bool pinned
                    required property bool archived
                    required property bool current
                    required property int index
                    property bool renaming: false
                    readonly property bool tools: rowHover.hovered || row.activeFocus || renameBtn.activeFocus
                                                  || pinBtn.activeFocus || archiveBtn.activeFocus
                    width: ListView.view.width
                    height: rows.implicitHeight
                    Keys.onUpPressed: function(event) {
                        if (entry.index === 0) search.forceActiveFocus()
                        else event.accepted = false          // the view moves to the row above
                    }

                    Column {
                        id: rows
                        width: parent.width
                        spacing: 0

                        T {
                            visible: entry.header !== ""
                            width: parent.width
                            topPadding: entry.index === 0 ? 2 : 12
                            bottomPadding: 6
                            leftPadding: 10; rightPadding: 10
                            text: entry.header
                            font.pixelSize: Theme.tiny; font.weight: Font.DemiBold; font.letterSpacing: 0.4
                            color: Theme.ink3; wrapMode: Text.NoWrap
                        }

                        AbstractButton {
                            id: row
                            objectName: "chatThreadRow"
                            width: parent.width
                            height: 60
                            focus: true                          // the row is what a focused entry gives the keys to
                            hoverEnabled: true
                            focusPolicy: Qt.StrongFocus
                            enabled: !entry.renaming
                            // a keyboard ring for Tab and for the arrow keys alike (not after a click)
                            readonly property bool ring: activeFocus && focusReason !== Qt.MouseFocusReason
                            Accessible.name: entry.title + " · " + entry.when + (entry.current ? " · " + mira.s.ch_open_now : "")
                            onClicked: { panel.history.openThread(entry.tid); panel.closeDrawer() }
                            Keys.onReturnPressed: clicked()
                            Keys.onEnterPressed: clicked()
                            HoverHandler { id: rowHover }
                            background: Rectangle {
                                radius: 14
                                color: entry.current ? Qt.rgba(0.61, 0.48, 1, 0.16)
                                     : row.down ? Theme.glassHover : rowHover.hovered || row.ring ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                                border.width: row.ring ? 2 : entry.current ? 1 : 0
                                border.color: row.ring ? Theme.cyan : Qt.rgba(0.72, 0.55, 1, 0.40)
                                Rectangle {   // the open chat's accent on the leading edge
                                    visible: entry.current
                                    anchors { left: parent.left; verticalCenter: parent.verticalCenter; leftMargin: 3 }
                                    width: 3; height: parent.height - 22; radius: 2
                                    color: Theme.violet
                                }
                            }
                            contentItem: Item {
                                Row {
                                    id: titleLine
                                    anchors { left: parent.left; right: side.left; top: parent.top; leftMargin: 14; rightMargin: 8; topMargin: 10 }
                                    spacing: 6
                                    Glyph { visible: entry.pinned; name: "pin"; size: 13; weight: 2; color: Theme.amber; anchors.verticalCenter: parent.verticalCenter }
                                    T {
                                        width: titleLine.width - (entry.pinned ? 19 : 0)
                                        text: entry.title
                                        font.pixelSize: Theme.small + 1; font.weight: entry.current ? Font.DemiBold : Font.Medium
                                        wrapMode: Text.NoWrap; elide: Text.ElideRight
                                    }
                                }
                                T {
                                    anchors { left: parent.left; right: side.left; top: titleLine.bottom; leftMargin: 14; rightMargin: 8; topMargin: 3 }
                                    text: entry.preview
                                    font.pixelSize: Theme.tiny + 1; color: Theme.ink3
                                    wrapMode: Text.NoWrap; elide: Text.ElideRight
                                }
                                Item {
                                    id: side
                                    anchors { right: parent.right; top: parent.top; bottom: parent.bottom; rightMargin: 8 }
                                    width: entry.tools ? actions.implicitWidth : Math.max(whenText.implicitWidth, 1)
                                    T {
                                        id: whenText
                                        visible: !entry.tools
                                        anchors { right: parent.right; top: parent.top; topMargin: 11 }
                                        text: entry.when; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
                                    }
                                    Row {
                                        id: actions
                                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                                        spacing: 2
                                        opacity: entry.tools ? 1 : 0
                                        GlyphButton {
                                            id: renameBtn; glyph: "pencil"; diameter: 28; tip: mira.s.ch_rename
                                            onClicked: { entry.renaming = true; renameField.text = entry.title; renameField.forceActiveFocus(); renameField.selectAll() }
                                        }
                                        GlyphButton {
                                            id: pinBtn; glyph: "pin"; diameter: 28; lit: entry.pinned; accent: Theme.amber
                                            tip: entry.pinned ? mira.s.ch_unpin : mira.s.ch_pin
                                            onClicked: panel.history.pinThread(entry.tid, !entry.pinned)
                                        }
                                        GlyphButton {
                                            id: archiveBtn; glyph: "archive"; diameter: 28
                                            tip: entry.archived ? mira.s.ch_unarchive : mira.s.ch_archive
                                            onClicked: panel.history.archiveThread(entry.tid, !entry.archived)
                                        }
                                    }
                                }
                            }
                        }

                        MiraField {
                            id: renameField
                            visible: entry.renaming
                            width: parent.width
                            height: visible ? 40 : 0
                            placeholderText: mira.s.ch_rename_hint
                            horizontalAlignment: TextInput.AlignLeft
                            maximumLength: 80
                            Accessible.name: mira.s.ch_rename
                            onAccepted: { panel.history.renameThread(entry.tid, text); entry.renaming = false; row.forceActiveFocus() }
                            Keys.onEscapePressed: { entry.renaming = false; row.forceActiveFocus() }
                            onActiveFocusChanged: if (!activeFocus) entry.renaming = false
                        }
                    }
                }
            }

            // loading, empty, nothing found, or unreadable
            Column {
                anchors { horizontalCenter: threads.horizontalCenter; top: threads.top; topMargin: 48 }
                width: threads.width - 40
                spacing: 10
                visible: threads.count === 0
                Glyph { anchors.horizontalCenter: parent.horizontalCenter; size: 28; color: Theme.violet
                        name: panel.hs.error ? "alert" : search.text !== "" ? "search" : panel.hs.archived ? "archive" : "history" }
                T {
                    width: parent.width; horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.body; font.weight: Font.DemiBold
                    text: panel.hs.error ? panel.hs.error : panel.hs.loading ? mira.s.ch_loading
                        : search.text !== "" ? mira.s.ch_no_results : panel.hs.archived ? mira.s.ch_empty_archived : mira.s.ch_empty
                }
                T {
                    visible: !panel.hs.error && !panel.hs.loading && search.text === "" && !panel.hs.archived
                    width: parent.width; horizontalAlignment: Text.AlignHCenter
                    text: mira.s.ch_empty_body; font.pixelSize: Theme.small; color: Theme.ink3
                }
                PillButton {
                    visible: panel.hs.error !== undefined && panel.hs.error !== ""
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: mira.s.retry; iconName: "refresh"; size: Theme.small; implicitHeight: 32
                    onClicked: panel.history.refresh()
                }
            }
        }
    }

    // review renders only: `--chat-history` opens the drawer
    Component.onCompleted: if (Qt.application.arguments.indexOf("--chat-history") >= 0 && visible) Qt.callLater(openDrawer)
}
