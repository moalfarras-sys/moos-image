import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// MoOS itself, inside Mira (mira.systemPage, pages/system.py): the version this computer runs and its
// updates, the daily check with its findings and security, the self-check, the device plan, every
// repair and the troubleshooting playbooks. A read shows its real output under the tile that asked;
// a change becomes a card the owner approves, and the tile follows that card to its real end.
// Every word is a key of the interface table: the page stores keys, never rendered text, so a
// language switch re-renders all of it; the backends' raw codes are put into words here (why(),
// nightlyResult()).
PageFrame {
    id: root
    readonly property var st: mira.systemPage ? mira.systemPage.state : ({})
    readonly property var upd: st.update || ({})
    readonly property var chk: upd.check || ({})
    readonly property var health: st.health || ({})
    readonly property var sec: st.security || ({})
    readonly property var diag: st.diag || ({})
    readonly property var dev: st.device || ({})
    readonly property var scan: st.scan || ({})
    readonly property var skill: st.skill || ({})
    readonly property var booted: st.booted || ({})
    readonly property var kept: st.kept || ({})
    readonly property bool en: mira.lang === "en"
    readonly property bool staged: !!upd.staged
    readonly property int cols: contentWidth > 1180 ? 3 : contentWidth > 600 ? 2 : 1
    // The update resolver accepted this origin as a signed official MoOS one (any answer but "unsigned").
    readonly property bool official: ["current", "available", "replace-staged", "staged", "blocked-downgrade", "busy"].indexOf(chk.state || "") >= 0

    icon: "shield"
    accent: Theme.violet
    title: mira.s.sy_title
    subtitle: mira.s.sy_sub
    busy: !!st.loading
    actions: [
        Chip { visible: !!root.st.sample; icon: "alert"; text: mira.s.sy_sample; c: Theme.amber; anchors.verticalCenter: parent.verticalCenter },
        IconButton { iconName: "refresh"; tip: mira.s.sy_reread; diameter: 38; onClicked: mira.systemPage.refresh() }
    ]

    function when(c) {
        if (!c || !c.time) return ""
        return (c.day === "today" ? mira.s.sy_today : c.day === "yesterday" ? mira.s.sy_yesterday : c.date) + " · " + c.time
    }
    function tone(t) {
        return t === "ok" ? Theme.ok : t === "warn" ? Theme.amber : t === "error" ? Theme.danger : t === "off" ? Theme.ink3 : Theme.cyan
    }
    // A backend's code in the owner's words (the code itself when there are none).
    function why(code) {
        code = String(code || "")
        if (code === "") return ""
        if (mira.s["sy_err_" + code]) return mira.s["sy_err_" + code]
        if (code.indexOf("http_") === 0) return mira.s.sy_err_http + " · " + code.slice(5)
        if (code.indexOf("exit ") === 0) return mira.s.sy_err_exit + " " + code.slice(5)
        return code
    }
    function nightlyResult(token) { return mira.s["sy_res_" + token] || token }
    function editionName(e) { return mira.s["sy_ed_" + e] || e }
    function phaseOf(name) { return ((root.st.outputs || {})[name] || {}).state || "" }
    // A playbook's "use when" line (written in English in the playbook itself).
    function useWhen(id) {
        const list = root.st.skills || []
        for (let i = 0; i < list.length; ++i)
            if (list[i].id === id) return list[i].use_when || ""
        return ""
    }

    readonly property string checkState: {
        switch (chk.state) {
        case "available": case "replace-staged":
            return mira.s["sy_upd_" + chk.state].replace("{v}", "⁦" + (chk.latest || "?") + "⁩")
        case "current": case "blocked-downgrade": case "busy": case "unsigned": case "unknown":
            return mira.s["sy_upd_" + chk.state]
        default: return ""
        }
    }
    readonly property string updateState: checkState !== "" && chk.state !== "unknown" ? checkState
        : staged ? mira.s.sy_state_staged
        : !upd.known ? (chk.state === "unknown" ? checkState : mira.s.sy_state_unknown)
        // "Up to date" only from a nightly run whose time is known: systemd says "success" for a unit that never ran.
        : (upd.nightly === true && upd.last_result === "success" && upd.last_run && upd.last_run.time) ? mira.s.sy_state_current
        : mira.s.sy_state_none
    readonly property color updateColor: chk.state === "available" || chk.state === "replace-staged" || chk.state === "busy" ? Theme.amber
        : chk.state === "unsigned" ? Theme.danger
        : chk.state === "current" || chk.state === "blocked-downgrade" ? Theme.ok
        : staged ? Theme.amber
        : updateState === mira.s.sy_state_current ? Theme.ok
        : upd.known ? Theme.cyan : Theme.ink3
    readonly property bool offerUpdate: chk.state === "available" || chk.state === "replace-staged"
        || (!staged && ["current", "blocked-downgrade", "busy", "unsigned"].indexOf(chk.state || "") < 0)
    readonly property bool nightlyRan: upd.last_result === "success" && !!(upd.last_run && upd.last_run.time)
    readonly property string nightlyText: upd.nightly === true
        ? mira.s.sy_nightly_on + (upd.last_result === "success"
                                  ? " · " + (nightlyRan ? mira.s.sy_last_ok + " · " + root.when(upd.last_run) : mira.s.sy_no_failure)
                                  : upd.last_result ? " · " + mira.s.sy_last_failed + " (" + root.nightlyResult(upd.last_result) + ")" : "")
        : upd.nightly === false ? mira.s.sy_nightly_off : mira.s.sy_unknown
    readonly property color nightlyColor: upd.nightly === false || (upd.last_result && upd.last_result !== "success") ? Theme.amber
        : upd.nightly === true && nightlyRan ? Theme.ok
        : upd.nightly === true ? Theme.cyan : Theme.ink3
    readonly property string healthHead: {
        switch (health.state) {
        case "ok": return mira.s.sy_all_fine
        case "attention": case "action-needed": return mira.s.sy_attention
        case "incomplete": return mira.s.sy_incomplete
        case "none": return mira.s.sy_no_report
        case "error": return mira.s.sy_health_error + (health.error ? " (" + root.why(health.error) + ")" : "")
        default: return mira.s.page_loading
        }
    }
    readonly property color healthColor: health.state === "ok" ? Theme.ok
        : health.state === "action-needed" || health.state === "error" ? Theme.danger
        : health.state === "attention" || health.state === "incomplete" ? Theme.amber : Theme.ink3
    readonly property string diagHead: diag.state === "running" ? mira.s.sy_diag_running
        : diag.state === "error" ? mira.s.sy_diag_error + (diag.error ? " (" + root.why(diag.error) + ")" : "")
        : diag.state === "done" ? (diag.healthy ? mira.s.sy_diag_ok + " (" + diag.ok + ")"
                                  : mira.s.sy_diag_broken + ": " + diag.fail + " · " + mira.s.sy_diag_passed + ": " + diag.ok)
        : mira.s.sy_diag_idle

    // ── small parts of this page ─────────────────────────────────────
    // A state chip with an optional glyph and any colour (and an optional tooltip).
    component Chip: Rectangle {
        id: chip
        property string icon: ""
        property string text: ""
        property string tip: ""
        property color c: Theme.ink2
        implicitHeight: 26
        implicitWidth: chipRow.implicitWidth + 20
        radius: 13
        color: Qt.rgba(c.r, c.g, c.b, 0.12)
        border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.34)
        Accessible.role: Accessible.StaticText
        Accessible.name: text + (tip ? " · " + tip : "")
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 5
            Icon { visible: chip.icon !== ""; name: chip.icon || "check"; size: 13; weight: 2; color: chip.c; anchors.verticalCenter: parent.verticalCenter }
            T { text: chip.text; font.pixelSize: Theme.small; color: chip.c; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
        }
        HoverHandler { id: chipHover; enabled: chip.tip !== "" }
        ToolTip.visible: chipHover.hovered && chip.tip !== ""
        ToolTip.text: chip.tip
        ToolTip.delay: 450
    }

    // A button that says why it is unavailable. A disabled control receives no pointer events, so
    // the hover that shows the reason is watched by this (enabled) wrapper around it.
    component ReasonButton: Item {
        id: rb
        property alias text: rbButton.text
        property alias iconName: rbButton.iconName
        property bool available: true
        property string reason: ""
        signal clicked()
        implicitWidth: rbButton.implicitWidth
        implicitHeight: rbButton.implicitHeight
        Accessible.description: available ? "" : reason
        PillButton {
            id: rbButton
            anchors.fill: parent
            size: Theme.small; implicitHeight: 34
            enabled: rb.available
            onClicked: rb.clicked()
        }
        HoverHandler { id: rbHover }
        ToolTip.visible: rbHover.hovered && !rb.available && rb.reason !== ""
        ToolTip.text: rb.reason
        ToolTip.delay: 300
    }

    // One fact: glyph, small label, value.
    component Fact: Rectangle {
        id: fact
        property string icon: "check"
        property string label: ""
        property string value: ""
        property color c: Theme.cyan
        Layout.fillWidth: true
        Layout.preferredWidth: 10
        implicitHeight: Math.max(62, factCol.implicitHeight + 22)
        radius: 16
        color: Qt.rgba(0, 0, 0, 0.16)
        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.08)
        Accessible.role: Accessible.StaticText
        Accessible.name: label + ": " + value
        RowLayout {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 12; rightMargin: 12 }
            spacing: 11
            Rectangle {
                Layout.preferredWidth: 34; Layout.preferredHeight: 34
                radius: 11
                color: Qt.rgba(fact.c.r, fact.c.g, fact.c.b, 0.14)
                Icon { anchors.centerIn: parent; name: fact.icon; size: 17; color: fact.c }
            }
            ColumnLayout {
                id: factCol
                Layout.fillWidth: true
                spacing: 2
                T { text: fact.label; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                T { text: fact.value; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
            }
        }
    }

    // What one tool is doing, or did: a state line and its real output (hidden until there is one).
    component OpStatus: ColumnLayout {
        id: op
        property string name: ""
        property string origin: ""          // shown only where the owner asked (hero, tools, diag, finding:<id>…)
        property bool showTitle: false
        readonly property var raw: (mira.systemPage && name !== "" ? (mira.systemPage.state.outputs || {})[name] : null) || ({})
        readonly property var o: origin === "" || raw.origin === origin ? raw : ({})
        readonly property string phase: o.state || ""
        readonly property string word: o.key ? (mira.s[o.key] || "") : ""
        readonly property color c: phase === "ok" ? Theme.ok : phase === "error" ? Theme.danger : phase === "waiting" ? Theme.violet
                                 : phase === "running" || phase === "detached" ? Theme.amber : Theme.ink3
        readonly property string said: phase === "running" ? mira.s.sy_running
            : phase === "waiting" ? mira.s.sy_waiting
            : phase === "ok" ? (word || mira.s.sy_done)
            : phase === "error" ? mira.s.sy_failed + (word ? " · " + word : o.summary ? " · " + root.why(o.summary) : "")
            : phase === "cancelled" ? (word || mira.s.sy_cancelled)
            : phase === "lost" ? mira.s.sy_card_gone
            : phase === "detached" ? (word || mira.s.sy_still_running)
            : ""
        // The owner's half of a bilingual output when the page split it; otherwise the raw output.
        readonly property string prose: (root.en ? o.text_en : o.text_ar) || ""
        visible: phase !== ""
        Layout.fillWidth: true
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Rectangle {
                id: dot
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: 5
                width: 8; height: 8; radius: 4
                color: op.c
                readonly property bool pulsing: (op.phase === "running" || op.phase === "waiting") && mira.motion
                opacity: pulsing ? pulse.value : 1
                QtObject { id: pulse; property real value: 1 }
                SequentialAnimation {
                    running: dot.pulsing
                    loops: Animation.Infinite
                    NumberAnimation { target: pulse; property: "value"; to: 0.25; duration: 650 }
                    NumberAnimation { target: pulse; property: "value"; to: 1; duration: 650 }
                }
            }
            T {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: (op.showTitle ? (mira.s["sy_t_" + op.name] || op.name) + " · " : "") + op.said
                font.pixelSize: Theme.small; color: op.c
                maximumLineCount: 3; elide: Text.ElideRight
            }
            T { Layout.alignment: Qt.AlignTop; text: op.o.at || ""; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap }
            IconButton {
                Layout.alignment: Qt.AlignTop
                visible: op.phase !== "running" && op.phase !== "waiting"
                iconName: "x"; tip: mira.s.sy_hide; diameter: 26
                onClicked: mira.systemPage.closeOutput(op.name)
            }
        }
        T {
            visible: op.prose !== ""
            Layout.fillWidth: true
            text: op.prose
            font.pixelSize: Theme.small
            color: op.phase === "error" ? Theme.danger : Theme.ink2
            horizontalAlignment: Text.AlignLeft
        }
        OutputBox {
            visible: op.prose === "" && (op.o.text || "") !== ""
            text: op.o.text || ""
            error: op.phase === "error"
            maxHeight: 260
        }
    }

    // A clickable tile (Tab/Enter/Space reach it). The shared Tile's `icon` collides with
    // AbstractButton's FINAL `icon` on Qt 6.11, so this page draws its own with `glyph`.
    component ToolTile: AbstractButton {
        id: tile
        property string glyph: "sparkle"
        property string title: ""
        property string subtitle: ""
        property string badge: ""
        property color accent: Theme.cyan
        property bool busy: false
        property bool lit: false
        implicitHeight: 74
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.role: Accessible.Button
        Accessible.name: title + (subtitle ? " · " + subtitle : "") + (badge ? " · " + badge : "")
        background: Rectangle {
            radius: 16
            color: tile.lit ? Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.14)
                 : tile.down ? Theme.glassHover : tile.hovered ? Qt.rgba(1, 1, 1, 0.075) : Qt.rgba(1, 1, 1, 0.04)
            border.width: tile.visualFocus ? 2 : 1
            border.color: tile.visualFocus ? Theme.cyan : tile.lit || tile.busy ? Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.55)
                        : tile.hovered ? Theme.hairlineStrong : Theme.hairline
            opacity: tile.enabled ? 1 : 0.45
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: RowLayout {
            spacing: 10
            Rectangle {
                id: glyphBox
                property real spin: 0
                Layout.preferredWidth: 38; Layout.preferredHeight: 38
                Layout.leftMargin: 10
                radius: 12
                rotation: tile.busy ? spin : 0
                color: Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, tile.lit ? 0.28 : 0.14)
                Icon { anchors.centerIn: parent; name: tile.glyph; size: 19; color: tile.lit ? "white" : tile.accent }
                NumberAnimation on spin { running: tile.busy && mira.motion; from: 0; to: 360; duration: 1500; loops: Animation.Infinite }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                T { text: tile.title; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                T { visible: tile.subtitle !== ""; text: tile.subtitle; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
            }
            Rectangle {
                visible: tile.badge !== ""
                Layout.rightMargin: 10
                implicitHeight: 22; implicitWidth: badgeText.implicitWidth + 14; radius: 11
                color: Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.18)
                T { id: badgeText; anchors.centerIn: parent; text: tile.badge; font.pixelSize: Theme.tiny; color: tile.accent; wrapMode: Text.NoWrap }
            }
            Item { visible: tile.badge === ""; Layout.preferredWidth: 2 }
        }
        scale: down ? 0.98 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    // A tool as a tile; its own result right under it.
    component ToolCell: ColumnLayout {
        id: cell
        required property var modelData
        property string origin: "tools"
        readonly property string name: modelData.name || ""
        readonly property string category: modelData.category || ""
        readonly property var o: (mira.systemPage ? (mira.systemPage.state.outputs || {})[name] : null) || ({})
        Layout.fillWidth: true
        Layout.preferredWidth: 10
        Layout.alignment: Qt.AlignTop
        spacing: 8
        ToolTile {
            Layout.fillWidth: true
            glyph: cell.modelData.icon || "wrench"
            title: mira.s["sy_t_" + cell.name] || cell.name
            subtitle: mira.s["sy_d_" + cell.name] || ""
            accent: cell.modelData.password ? Theme.violet : cell.category === "user_confirm" ? Theme.amber : Theme.cyan
            badge: cell.modelData.password ? mira.s.sy_badge_password : cell.category === "user_confirm" ? mira.s.sy_badge_asks : ""
            busy: cell.o.state === "running"
            lit: cell.o.state === "waiting"
            onClicked: mira.systemPage.runTool(cell.name, cell.origin)
        }
        OpStatus { name: cell.name; origin: cell.origin }
    }

    // A finding, a device-plan problem or a self-check issue: what it is, and what can be done.
    component ItemRow: Rectangle {
        id: row
        required property var modelData
        readonly property bool en: mira.lang === "en"
        readonly property string heading: (en ? modelData.title_en : modelData.title_ar) || modelData.title_en || ""
        readonly property string detail: (en ? modelData.detail_en : modelData.detail_ar) || ""
        readonly property color c: modelData.severity === "important" ? Theme.danger : modelData.severity === "warning" ? Theme.amber : Theme.cyan
        readonly property string sev: modelData.severity === "important" ? mira.s.sy_sev_important
                                    : modelData.severity === "warning" ? mira.s.sy_sev_warning : mira.s.sy_sev_info
        readonly property string fixPhase: modelData.fix_tool ? root.phaseOf(modelData.fix_tool) : ""
        Layout.fillWidth: true
        Layout.preferredHeight: rowCol.implicitHeight + 26
        implicitHeight: rowCol.implicitHeight + 26
        radius: 16
        color: Qt.rgba(c.r, c.g, c.b, 0.055)
        border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.22)
        Accessible.role: Accessible.StaticText
        Accessible.name: sev + ": " + heading + (detail ? " · " + detail : "")
        Rectangle {
            id: bar
            width: 3; radius: 1.5
            color: row.c
            opacity: row.modelData.incomplete ? 0.4 : 1
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; leftMargin: 12; topMargin: 14; bottomMargin: 14 }
        }
        ColumnLayout {
            id: rowCol
            anchors { left: bar.right; right: parent.right; top: parent.top; leftMargin: 12; rightMargin: 12; topMargin: 13 }
            spacing: 8
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    T { text: row.sev; font.pixelSize: Theme.tiny; font.weight: Font.DemiBold; color: row.c; wrapMode: Text.NoWrap }
                    T { text: row.heading; font.pixelSize: Theme.body; font.weight: Font.Medium; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft }
                    T { visible: row.detail !== ""; text: row.detail; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 3; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                }
                // A tool fix runs through a card; a route fix only opens the MoOS page (or action) that handles it.
                PillButton {
                    visible: row.modelData.fix !== ""
                    text: row.modelData.fix === "route" ? mira.s.sy_open : mira.s.sy_fix
                    iconName: row.modelData.fix === "route" ? "external" : "wrench"
                    // Pressed again while its card waits or its job runs, the page says why nothing starts.
                    primary: row.modelData.fix === "tool" && row.fixPhase !== "running" && row.fixPhase !== "waiting"
                    size: Theme.small; implicitHeight: 34
                    Layout.alignment: Qt.AlignVCenter
                    ToolTip.visible: hovered
                    ToolTip.delay: 450
                    ToolTip.text: row.modelData.fix === "route" ? (row.modelData.fix_page ? mira.s.sy_opens_page : mira.s.sy_route_asks)
                                : row.fixPhase === "waiting" ? mira.s.sy_waiting : row.fixPhase === "running" ? mira.s.sy_running
                                : (mira.s["sy_t_" + row.modelData.fix_tool] || "")
                    onClicked: mira.systemPage.fixItem(row.modelData.kind, row.modelData.id)
                }
                PillButton {
                    text: mira.s.sy_ask; iconName: "chat"
                    size: Theme.small; implicitHeight: 34
                    Layout.alignment: Qt.AlignVCenter
                    onClicked: mira.systemPage.askItem(row.modelData.kind, row.modelData.id)
                }
            }
            OpStatus { name: row.modelData.fix_tool || ""; origin: row.modelData.kind + ":" + row.modelData.id; showTitle: true }
        }
    }

    // ── 1. this MoOS and its updates ─────────────────────────────────
    Glass {
        id: hero
        Layout.fillWidth: true
        Layout.preferredHeight: heroCol.implicitHeight + 40
        radius: 24
        edge: Qt.rgba(0.61, 0.48, 1.0, 0.40)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0.36, 0.26, 0.85, 0.30) }
            GradientStop { position: 1; color: Qt.rgba(0.10, 0.55, 0.75, 0.16) }
        }
        ColumnLayout {
            id: heroCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 20 }
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                Rectangle {
                    Layout.preferredWidth: 68; Layout.preferredHeight: 68
                    Layout.alignment: Qt.AlignTop
                    radius: 22
                    color: Qt.rgba(1, 1, 1, 0.08)
                    border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18)
                    Image { anchors.centerIn: parent; width: 44; height: 44; source: "image://icon/moos-updater"; sourceSize: Qt.size(88, 88); smooth: true }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5
                    T { text: mira.s.sy_runs; font.pixelSize: Theme.small; color: Theme.ink3; wrapMode: Text.NoWrap }
                    T {
                        Layout.fillWidth: true
                        text: root.booted.version ? "MoOS " + root.booted.version
                            : root.st.os_state === "error" ? mira.s.sy_unknown_version : mira.s.sy_reading
                        font.pixelSize: root.booted.version ? 28 : Theme.title
                        font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight
                        horizontalAlignment: Text.AlignLeft
                        color: root.booted.version ? Theme.ink : Theme.ink2
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                        spacing: 6
                        // "Official" only when the update resolver accepted the origin; a signed
                        // transport alone says "signed origin".
                        Chip {
                            visible: (root.booted.version || "") !== ""
                            icon: root.chk.state === "unsigned" || !root.booted.signed ? "alert" : "shield"
                            text: root.chk.state === "unsigned" ? mira.s.sy_not_official
                                : !root.booted.signed ? mira.s.sy_unsigned
                                : root.official ? mira.s.sy_signed_official : mira.s.sy_signed_origin
                            c: root.chk.state === "unsigned" || !root.booted.signed ? Theme.danger : Theme.ok
                            tip: mira.s.sy_origin_tip
                        }
                        Chip { visible: (root.booted.edition || "") !== ""; icon: "package"; text: root.editionName(root.booted.edition || ""); c: Theme.ink2 }
                        Chip { visible: (root.st.kernel || "") !== ""; icon: "chip"; text: mira.s.sy_kernel + " ⁦" + (root.st.kernel || "") + "⁩"; c: Theme.ink2 }
                        Chip {
                            visible: root.st.os_state === "ok"
                            icon: "clock"
                            text: root.kept.version ? mira.s.sy_kept + " · " + root.kept.version : mira.s.sy_no_kept
                            c: root.kept.version ? Theme.cyan : Theme.ink3
                        }
                    }
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: root.cols >= 2 ? 3 : 1
                columnSpacing: 8; rowSpacing: 8
                Fact {
                    icon: root.chk.state === "available" || root.chk.state === "replace-staged" ? "download"
                        : root.chk.state === "unsigned" ? "alert" : root.staged ? "refresh" : "download"
                    label: mira.s.sy_updates_label
                    value: root.updateState + (root.staged && root.upd.staged_version && root.checkState === "" ? " · " + root.upd.staged_version : "")
                    c: root.updateColor
                }
                Fact {
                    icon: "moon"
                    label: mira.s.sy_nightly
                    value: root.nightlyText
                    c: root.nightlyColor
                }
                Fact {
                    icon: "apps"
                    label: mira.s.sy_app_updates
                    value: !root.upd.known ? mira.s.sy_unknown : root.upd.app_updates > 0 ? String(root.upd.app_updates) : mira.s.sy_app_updates_none
                    c: !root.upd.known ? Theme.ink3 : root.upd.app_updates > 0 ? Theme.cyan : Theme.ok
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: 8
                PillButton {
                    visible: root.staged
                    text: mira.s.sy_restart; iconName: "power"; primary: root.chk.state !== "replace-staged"; size: Theme.small
                    onClicked: mira.systemPage.restartNow()
                }
                PillButton {
                    readonly property string phase: root.phaseOf("system_update")
                    text: mira.s.sy_update; iconName: "download"; primary: root.offerUpdate; size: Theme.small
                    ToolTip.visible: hovered && phase === "waiting"
                    ToolTip.text: mira.s.sy_waiting
                    onClicked: mira.systemPage.updateSystem()
                }
                PillButton {
                    text: mira.s.sy_check_updates; iconName: "refresh"; size: Theme.small
                    enabled: !root.st.checking && root.phaseOf("check_system_update") !== "running"
                    onClicked: mira.systemPage.checkUpdates()
                }
                PillButton {
                    text: mira.s.sy_rollback; iconName: "clock"; size: Theme.small
                    enabled: (root.kept.version || "") !== ""
                    onClicked: mira.systemPage.rollBack()
                }
                PillButton { text: mira.s.sy_recovery; iconName: "shield"; size: Theme.small; onClicked: mira.systemPage.openPage("recovery") }
                PillButton { text: mira.s.sy_whats_new; iconName: "sparkle"; size: Theme.small; onClicked: mira.systemPage.openPage("whats_new") }
            }

            RowLayout {
                Layout.fillWidth: true
                visible: (root.st.note_key || "") !== ""
                spacing: 10
                Icon { name: root.st.note_tone === "warn" ? "alert" : root.st.note_tone === "ok" ? "check" : "clock"; size: 16; color: root.tone(root.st.note_tone) }
                T { Layout.fillWidth: true; text: mira.s[root.st.note_key || ""] || ""; font.pixelSize: Theme.small; color: Theme.ink2 }
                PillButton {
                    visible: !root.staged
                    text: mira.s.sy_open_updater; iconName: "external"; size: Theme.small; implicitHeight: 32
                    onClicked: mira.systemPage.openPage("updater")
                }
            }
            OpStatus { name: "system_update"; origin: "hero"; showTitle: true }
            OpStatus { name: "system_rollback"; origin: "hero"; showTitle: true }
            OpStatus { name: "check_system_update"; origin: "hero"; showTitle: true }
            OpStatus { name: "restart_computer"; origin: "hero"; showTitle: true }
        }
    }

    // ── 2. the daily check ───────────────────────────────────────────
    Card {
        icon: "pulse"
        accent: root.healthColor
        title: mira.s.sy_health
        subtitle: root.health.checked && root.health.checked.time ? mira.s.sy_last_check + ": " + root.when(root.health.checked)
                : root.health.state === "none" ? mira.s.sy_never_checked : ""
        trailing: [
            PillButton {
                text: root.scan.running ? mira.s.sy_scanning + (root.scan.elapsed > 0 ? " " + root.scan.elapsed + " " + mira.s.sy_seconds : "") : mira.s.sy_check_now
                iconName: "pulse"; size: Theme.small; implicitHeight: 34
                enabled: !root.scan.running
                onClicked: mira.systemPage.scanHealth()
            }
        ]

        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Rectangle {
                Layout.preferredWidth: 46; Layout.preferredHeight: 46
                radius: 23
                color: Qt.rgba(root.healthColor.r, root.healthColor.g, root.healthColor.b, 0.14)
                border.width: 1; border.color: Qt.rgba(root.healthColor.r, root.healthColor.g, root.healthColor.b, 0.4)
                Icon {
                    anchors.centerIn: parent
                    name: root.health.state === "ok" ? "check" : root.health.state === "unknown" || !root.health.state ? "clock" : "alert"
                    size: 22; weight: 2; color: root.healthColor
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                T { text: root.healthHead; font.pixelSize: Theme.title; font.weight: Font.DemiBold; Layout.fillWidth: true }
                T {
                    visible: root.health.state === "attention" || root.health.state === "action-needed" || root.health.state === "incomplete"
                    text: mira.s.sy_important + ": " + (root.health.important || 0) + " · " + mira.s.sy_warnings + ": " + (root.health.warning || 0)
                          + " · " + mira.s.sy_notes + ": " + (root.health.info || 0)
                    font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true
                }
            }
        }

        T {
            Layout.fillWidth: true
            visible: (root.scan.key || "") !== ""
            text: (mira.s[root.scan.key || ""] || "") + (root.scan.error ? " (" + root.why(root.scan.error) + ")" : "")
            font.pixelSize: Theme.small
            color: root.tone(root.scan.tone)
        }

        // security at a glance
        SectionTitle { visible: !!root.sec.known; icon: "lock"; text: mira.s.sy_security; accent: Theme.mint; Layout.topMargin: 4 }
        GridLayout {
            Layout.fillWidth: true
            visible: !!root.sec.known
            columns: root.cols >= 2 ? 3 : 1
            columnSpacing: 8; rowSpacing: 8
            Fact {
                icon: "shield"
                label: mira.s.sy_selinux
                value: root.sec.selinux === "Enforcing" ? mira.s.sy_enforcing : root.sec.selinux === "Permissive" ? mira.s.sy_permissive
                     : root.sec.selinux === "Disabled" ? mira.s.sy_se_disabled : mira.s.sy_unknown
                c: root.tone(root.sec.selinux_tone)
            }
            Fact {
                icon: "lock"
                label: mira.s.sy_firewall
                value: root.sec.firewall === "running" ? mira.s.sy_fw_running : root.sec.firewall === "off" ? mira.s.sy_fw_off : mira.s.sy_unknown
                c: root.tone(root.sec.firewall_tone)
            }
            Fact {
                icon: "globe"
                label: mira.s.sy_ports
                value: !root.sec.ports_known ? mira.s.sy_unknown
                     : (root.sec.ports || 0) + (root.sec.unknown_ports > 0 ? " · " + mira.s.sy_unrecognised + ": " + root.sec.unknown_ports : "")
                c: !root.sec.ports_known ? Theme.ink3 : root.sec.unknown_ports > 0 ? Theme.amber : Theme.ok
            }
        }

        // what the check found
        Repeater {
            model: root.st.findings || []
            delegate: ItemRow {}
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.health.state === "ok" && (root.st.findings || []).length === 0
            spacing: 8
            Icon { name: "check"; size: 16; weight: 2; color: Theme.ok }
            T { text: mira.s.sy_nothing; font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true }
        }
    }

    // ── 3. the self-check ────────────────────────────────────────────
    Card {
        icon: "check"
        accent: Theme.mint
        title: mira.s.sy_diag
        subtitle: mira.s.sy_diag_sub
        trailing: [
            PillButton {
                text: mira.s.sy_diag_run; iconName: "refresh"; size: Theme.small; implicitHeight: 34
                enabled: root.diag.state !== "running"
                onClicked: mira.systemPage.runDiagnosis()
            }
        ]
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Icon {
                name: root.diag.state === "done" && root.diag.healthy ? "check" : root.diag.state === "done" || root.diag.state === "error" ? "alert" : "clock"
                size: 18; weight: 2
                color: root.diag.state === "done" ? (root.diag.healthy ? Theme.ok : Theme.amber) : root.diag.state === "error" ? Theme.danger : Theme.ink3
            }
            T { text: root.diagHead; font.pixelSize: Theme.body; font.weight: Font.Medium; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft }
        }
        Repeater {
            model: root.diag.issues || []
            delegate: ItemRow {}
        }
        SectionTitle { visible: (root.diag.fixes || []).length > 0; icon: "wrench"; text: mira.s.sy_diag_tools; accent: Theme.mint; Layout.topMargin: 4 }
        Flow {
            Layout.fillWidth: true
            visible: (root.diag.fixes || []).length > 0
            spacing: 8
            Repeater {
                model: root.diag.fixes || []
                delegate: ReasonButton {
                    id: chipButton
                    required property var modelData
                    readonly property string phase: root.phaseOf(modelData.name)
                    // Rolling back needs a kept version, here as on the hero.
                    readonly property bool noKept: modelData.name === "system_rollback" && root.st.os_state === "ok" && !root.kept.version
                    text: (mira.s["sy_t_" + modelData.name] || modelData.name)
                          + (modelData.category === "privileged_confirm" || modelData.category === "user_confirm" ? " …" : "")
                    iconName: modelData.icon || "wrench"
                    available: phase !== "running" && phase !== "waiting" && !noKept
                    reason: noKept ? mira.s.sy_no_kept : phase === "waiting" ? mira.s.sy_waiting : mira.s.sy_running
                    onClicked: mira.systemPage.runTool(modelData.name, "diag")
                }
            }
        }
        Repeater {
            model: root.diag.fixes || []
            delegate: OpStatus {
                required property var modelData
                name: modelData.name
                origin: "diag"
                showTitle: true
            }
        }
    }

    // ── 4. devices and drivers ───────────────────────────────────────
    Card {
        icon: "chip"
        accent: Theme.cyan
        title: mira.s.sy_device
        trailing: [
            StatusPill {
                visible: (root.dev.verdict || "") !== ""
                text: root.dev.verdict === "ready" ? mira.s.sy_device_ready : root.dev.verdict === "attention" ? mira.s.sy_device_attention : mira.s.sy_device_action
                tone: root.dev.verdict === "ready" ? "ok" : root.dev.verdict === "attention" ? "warn" : "error"
                icon: root.dev.verdict === "ready" ? "check" : "alert"
            }
        ]
        T {
            Layout.fillWidth: true
            visible: root.dev.state === "pending" || root.dev.state === "error" || root.dev.state === "idle"
            text: root.dev.state === "pending" ? mira.s.sy_device_pending
                : root.dev.state === "error" ? mira.s.sy_device_error + (root.dev.error ? " (" + root.why(root.dev.error) + ")" : "") : mira.s.page_loading
            font.pixelSize: Theme.small; color: root.dev.state === "error" ? Theme.danger : Theme.ink3
        }
        RowLayout {
            Layout.fillWidth: true
            visible: root.dev.state === "done"
            spacing: 12
            Rectangle {
                Layout.preferredWidth: 42; Layout.preferredHeight: 42
                radius: 14
                color: Qt.rgba(0.21, 0.85, 0.96, 0.12)
                Icon { anchors.centerIn: parent; name: "monitor"; size: 20; color: Theme.cyan }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3
                T { text: mira.s.sy_graphics; font.pixelSize: Theme.tiny + 1; color: Theme.ink3 }
                T { text: root.dev.gpu || mira.s.sy_unknown; font.pixelSize: Theme.body; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight; maximumLineCount: 2; horizontalAlignment: Text.AlignLeft }
                RowLayout {
                    spacing: 6
                    Layout.fillWidth: true
                    Icon { name: root.dev.driver_ok ? "check" : "alert"; size: 14; weight: 2; color: root.dev.driver_ok ? Theme.ok : Theme.amber }
                    T { text: (root.en ? root.dev.driver_en : root.dev.driver_ar) || ""; font.pixelSize: Theme.small; color: root.dev.driver_ok ? Theme.ok : Theme.amber; Layout.fillWidth: true; horizontalAlignment: Text.AlignLeft }
                }
            }
        }
        SectionTitle { visible: (root.dev.problems || []).length > 0; icon: "alert"; text: mira.s.sy_advice; accent: Theme.amber; Layout.topMargin: 4 }
        Repeater {
            model: root.dev.problems || []
            delegate: ItemRow {}
        }
        SectionTitle { visible: root.dev.state === "done"; icon: "memory"; text: mira.s.sy_firmware; accent: Theme.violet; Layout.topMargin: 4 }
        Repeater {
            model: root.dev.state === "done" ? (root.dev.firmware || []) : []
            delegate: Rectangle {
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: 46
                radius: 14
                color: Qt.rgba(1, 1, 1, 0.035); border.width: 1; border.color: Theme.hairline
                RowLayout {
                    anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
                    spacing: 10
                    Icon { name: "memory"; size: 16; color: Theme.violet }
                    T { text: modelData; font.pixelSize: Theme.small + 1; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                    Chip { text: mira.s.sy_firmware_found; icon: "alert"; c: Theme.amber }
                }
            }
        }
        T {
            visible: root.dev.state === "done" && (root.dev.firmware || []).length === 0
            text: mira.s.sy_firmware_none; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true
            horizontalAlignment: Text.AlignLeft
        }
        Flow {
            Layout.fillWidth: true
            visible: root.dev.state === "done" && (root.dev.firmware || []).length > 0
            ReasonButton {
                readonly property string phase: root.phaseOf("update_firmware")
                text: mira.s.sy_firmware_install; iconName: "memory"
                available: phase !== "running" && phase !== "waiting"
                reason: phase === "waiting" ? mira.s.sy_waiting : mira.s.sy_running
                onClicked: mira.systemPage.runTool("update_firmware", "device")
            }
        }
        OpStatus { name: "update_firmware"; origin: "device"; showTitle: true }
    }

    // ── 5. repairs and tools ─────────────────────────────────────────
    Card {
        icon: "wrench"
        accent: Theme.amber
        title: mira.s.sy_tools
        subtitle: mira.s.sy_tools_sub
        GridLayout {
            Layout.fillWidth: true
            columns: root.cols
            columnSpacing: 8; rowSpacing: 8
            Repeater {
                model: root.st.tiles || []
                delegate: ToolCell {}
            }
        }
    }

    // ── 6. troubleshooting playbooks ─────────────────────────────────
    Card {
        id: playbooks
        property bool stepsOpen: false        // the raw steps Mira follows, shown only on request
        icon: "book"
        accent: Theme.violet
        title: mira.s.sy_skills
        subtitle: mira.s.sy_skills_sub
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: root.st.skills || []
                delegate: PillButton {
                    required property var modelData
                    readonly property bool open: root.skill.id === modelData.id
                    text: mira.s["sy_sk_" + modelData.id] || modelData.id
                    iconName: open ? "chevron-down" : "book"
                    primary: open
                    size: Theme.small; implicitHeight: 34
                    onClicked: {
                        playbooks.stepsOpen = false
                        if (open) mira.systemPage.closeSkill()
                        else mira.systemPage.readSkill(modelData.id)
                    }
                }
            }
        }
        T {
            visible: root.st.skills_state !== "done" || (root.st.skills || []).length === 0
            text: root.st.skills_state === "done" || root.st.skills_state === "error" ? mira.s.sy_skills_none : mira.s.page_loading
            font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true
            horizontalAlignment: Text.AlignLeft
        }
        Rectangle {
            Layout.fillWidth: true
            visible: (root.skill.id || "") !== ""
            implicitHeight: skillCol.implicitHeight + 28
            radius: 18
            color: Qt.rgba(0.61, 0.48, 1.0, 0.07)
            border.width: 1; border.color: Qt.rgba(0.61, 0.48, 1.0, 0.28)
            ColumnLayout {
                id: skillCol
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Rectangle {
                        Layout.preferredWidth: 36; Layout.preferredHeight: 36
                        Layout.alignment: Qt.AlignTop
                        radius: 12
                        color: Qt.rgba(0.61, 0.48, 1.0, 0.18)
                        Icon { anchors.centerIn: parent; name: "book"; size: 18; color: Theme.violet }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        T {
                            Layout.fillWidth: true
                            text: mira.s["sy_sk_" + (root.skill.id || "")] || root.skill.id || ""
                            font.pixelSize: Theme.body; font.weight: Font.DemiBold; horizontalAlignment: Text.AlignLeft
                        }
                        T {
                            Layout.fillWidth: true
                            text: root.skill.state === "running" ? mira.s.sy_skill_reading
                                : root.skill.state === "error" ? mira.s.sy_failed + (root.skill.error ? " · " + root.why(root.skill.error) : "")
                                : mira.s.sy_skill_lead
                            font.pixelSize: Theme.small
                            color: root.skill.state === "error" ? Theme.danger : Theme.ink2
                            horizontalAlignment: Text.AlignLeft
                        }
                        T {
                            Layout.fillWidth: true
                            visible: root.en && text !== ""
                            readonly property string when: root.skill.state === "ok" ? root.useWhen(root.skill.id || "") : ""
                            text: when !== "" ? mira.s.sy_use_when + ": " + when : ""
                            font.pixelSize: Theme.small; font.italic: true
                            color: Theme.ink3
                            horizontalAlignment: Text.AlignLeft
                        }
                    }
                    IconButton { Layout.alignment: Qt.AlignTop; iconName: "x"; tip: mira.s.sy_close; diameter: 30; onClicked: { playbooks.stepsOpen = false; mira.systemPage.closeSkill() } }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: root.skill.state === "ok"
                    PillButton {
                        text: mira.s.sy_skill_walk; iconName: "chat"; primary: true; size: Theme.small; implicitHeight: 34
                        onClicked: mira.systemPage.askSkill(root.skill.id)
                    }
                    PillButton {
                        text: playbooks.stepsOpen ? mira.s.sy_skill_hide : mira.s.sy_skill_steps
                        iconName: playbooks.stepsOpen ? "chevron-down" : "chevron"
                        size: Theme.small; implicitHeight: 34
                        onClicked: playbooks.stepsOpen = !playbooks.stepsOpen
                    }
                }
                OutputBox {
                    visible: playbooks.stepsOpen && root.skill.state === "ok"
                    text: root.skill.text || ""
                    maxHeight: 420
                }
            }
        }
    }
    Item { Layout.preferredHeight: 6 }
}
