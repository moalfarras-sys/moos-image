import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// The Brain page: who answers Mira's typed chat (Gemini with the owner's key, then Mo AI's free
// cloud brain, then local commands, then the Mo AI agent), with which model, what answered last,
// Mo AI's permission tier and where the words go. Every value is the page object's read-back
// (mira.brainPage.state); every button reaches a slot of that page or the controller.
PageFrame {
    id: page
    icon: "sparkle"
    accent: Theme.violet
    title: mira.s.nav_brain || ""
    subtitle: mira.s.br_sub
    busy: st.loading === true || st.models_state === "loading"

    readonly property var st: mira.brainPage ? mira.brainPage.state : ({})
    readonly property bool ar: mira.lang === "ar"
    readonly property bool wide: page.contentWidth >= 760
    readonly property var cloud: st.cloud || ({})
    readonly property var measure: st.measure || ({})
    readonly property var gtest: st.gemini_test || ({})
    readonly property var ctest: st.cloud_test || ({})
    readonly property var last: st.last || ({})
    readonly property var perms: st.permissions || ({})
    readonly property var health: st.gemini_health || ({})
    // One truth, derived by the page from brain.TextBrain's rule (pages/brain.py `_derived`): Gemini
    // answers first whenever a key is saved, unless the latest proof says it is rejected or missing.
    readonly property string keyStatus: st.key_status || "unknown"
    readonly property bool keyPresent: ["set", "ok", "testing", "failed"].indexOf(page.keyStatus) >= 0
    readonly property string routeNow: st.route_now || ""
    readonly property bool geminiUsable: page.routeNow === "gemini"
    readonly property bool keyRejected: page.keyStatus === "failed" && ["auth", "config"].indexOf(page.health.reason) >= 0
    // A pick that left the catalogue is refused by the gateway, so Mo AI's setting answers instead.
    readonly property bool ownPick: !!st.cloud_model && st.pick_missing !== true
    readonly property string cloudUses: page.ownPick ? st.cloud_model : (st.moai_default || cloud.model || "")
    property bool showAll: false

    // The controller's Save-and-test result reaches the page, so the key and the route never disagree.
    readonly property string brainKeyNow: mira.brainKey || ""
    onBrainKeyNowChanged: if (mira.brainPage) mira.brainPage.keyChecked(page.brainKeyNow, "")
    Component.onCompleted: if (mira.brainPage) mira.brainPage.keyChecked(page.brainKeyNow, "")
    Component.onDestruction: if (mira && mira.brainPage) mira.brainPage.pageHidden()

    function pick(a, e) { return page.bidi(page.ar ? (a || e || "") : (e || a || "")) }
    function cap(text) { return text ? text.charAt(0).toUpperCase() + text.slice(1) : "" }
    // «today», «yesterday», «2 days ago», then the plural Arabic needs (3–10 أيام, 11+ يوماً).
    function ageText(days) {
        var d = Math.max(0, Math.floor(days || 0))
        if (d === 0) return mira.s.br_age_today
        if (d === 1) return mira.s.br_age_yesterday
        if (d === 2) return mira.s.br_age_two
        return page.fill(d <= 10 ? mira.s.br_age_few : mira.s.br_age_many, { days: d })
    }
    function warningText(reason) {
        if (!reason) return ""
        return reason === "save" ? mira.s.br_key_failed_last : page.fill(mira.s.br_gemini_reason, { reason: page.reasonText(reason) })
    }
    // An Arabic line that starts with a Latin name (a model, a provider) must still read right to
    // left: a leading RLM makes the whole line an RTL paragraph.
    function bidi(text) { return page.ar && text ? "\u200f" + text : (text || "") }
    function word(key) { return (key && mira.s[key]) ? mira.s[key] : "" }
    function fill(text, map) {
        var out = text || ""
        for (var k in map) out = out.split("{" + k + "}").join(String(map[k]))
        return out
    }
    function seconds(ms) { return ((ms || 0) / 1000).toFixed(1) + " " + mira.s.br_seconds }
    function routeName(route) {
        switch (route) {
        case "gemini": return mira.s.br_route_gemini
        case "moai-cloud": return mira.s.br_route_cloud
        case "router": return mira.s.br_route_router
        case "moai": return mira.s.br_route_moai
        default: return mira.s.br_route_none
        }
    }
    function reasonText(reason) { return word("br_reason_" + (reason || "unknown")) || word("br_reason_unknown") }
    function textModelName(id) {
        var list = st.text_models || []
        for (var i = 0; i < list.length; ++i) if (list[i].id === id) return word(list[i].name_key) || id
        return id || ""
    }
    function rowLabel(id) {
        var groups = st.groups || []
        for (var g = 0; g < groups.length; ++g)
            for (var r = 0; r < groups[g].rows.length; ++r)
                if (groups[g].rows[r].id === id) return pick(groups[g].rows[r].label_ar, groups[g].rows[r].label_en)
        return (id || "").split("/").pop().replace(/:free$/, "")
    }
    function modelLabel(route, model) {
        if (!model) return mira.s.br_no_model
        return route === "gemini" ? textModelName(model) + " · " + model : rowLabel(model) + " · " + model
    }
    function tierTone(tier) { return tier === "read" || tier === "project" ? "ok" : tier === "system" ? "info" : tier === "full" ? "error" : "warn" }

    actions: [
        PillButton {
            text: mira.s.br_refresh; iconName: "refresh"; size: Theme.small
            enabled: mira.brainPage !== null && st.models_state !== "loading"
            onClicked: mira.brainPage.refresh()
        }
    ]

    // ── small parts, used only here ─────────────────────────────────
    component Chip: Rectangle {
        id: chip
        property string text: ""
        property color tone: Theme.ink2
        property string icon: ""
        implicitHeight: 22; implicitWidth: chipRow.implicitWidth + 16; radius: 11
        color: Qt.rgba(tone.r, tone.g, tone.b, 0.13)
        border.width: 1; border.color: Qt.rgba(tone.r, tone.g, tone.b, 0.35)
        Accessible.role: Accessible.StaticText
        Accessible.name: text
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 4
            Icon { visible: chip.icon !== ""; name: chip.icon || "check"; size: 12; weight: 2; color: chip.tone; anchors.verticalCenter: parent.verticalCenter }
            T { text: chip.text; font.pixelSize: Theme.tiny; color: chip.tone; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
        }
    }

    // A selectable line: a radio mark, a name with short tags, one line of why, the exact id.
    component Option: AbstractButton {
        id: opt
        property string name: ""
        property string note: ""
        property string mono: ""
        property bool chosen: false
        property color accent: Theme.cyan
        property var tags: []            // [{ text, tone }]
        Layout.fillWidth: true
        implicitHeight: Math.max(50, optCol.implicitHeight + 18)
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.role: Accessible.RadioButton
        Accessible.name: name + (note ? " · " + note : "")
        Accessible.checked: chosen
        background: Rectangle {
            radius: 14
            color: opt.chosen ? Qt.rgba(opt.accent.r, opt.accent.g, opt.accent.b, 0.13)
                 : opt.down ? Theme.glassHover : opt.hovered ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.025)
            border.width: opt.visualFocus ? 2 : 1
            border.color: opt.visualFocus ? Theme.cyan : opt.chosen ? Qt.rgba(opt.accent.r, opt.accent.g, opt.accent.b, 0.55)
                        : opt.hovered ? Theme.hairlineStrong : Theme.hairline
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: RowLayout {
            spacing: 12
            Rectangle {
                Layout.leftMargin: 12
                Layout.preferredWidth: 18; Layout.preferredHeight: 18; radius: 9
                color: "transparent"
                border.width: 2; border.color: opt.chosen ? opt.accent : Theme.hairlineStrong
                Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; color: opt.accent; visible: opt.chosen }
            }
            ColumnLayout {
                id: optCol
                Layout.fillWidth: true
                Layout.rightMargin: 12
                spacing: 2
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    T { text: opt.name; font.pixelSize: Theme.small + 1; font.weight: opt.chosen ? Font.DemiBold : Font.Medium
                        wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.maximumWidth: Math.max(80, opt.width * 0.55) }
                    Repeater {
                        model: opt.tags
                        delegate: Chip { required property var modelData; text: modelData.text; tone: modelData.tone }
                    }
                    Item { Layout.fillWidth: true }
                }
                T { horizontalAlignment: Text.AlignLeft; visible: opt.note !== ""; text: opt.note; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                T { horizontalAlignment: Text.AlignLeft; visible: opt.mono !== ""; text: opt.mono; font.family: Theme.mono; font.pixelSize: 10; color: Theme.ink3
                    Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideMiddle }
            }
        }
    }

    // One brain in the chain: lit when it answers first now, ticked when it answered last.
    component Step: Rectangle {
        id: step
        property string label: ""
        property string icon: "sparkle"
        property color accent: Theme.cyan
        property bool first: false
        property bool answered: false
        property bool unavailable: false
        property bool warned: false       // still asked first, but its latest proof failed
        implicitHeight: 34; implicitWidth: stepRow.implicitWidth + 24; radius: 17
        color: first ? Qt.rgba(accent.r, accent.g, accent.b, 0.20) : Qt.rgba(1, 1, 1, 0.045)
        border.width: 1; border.color: first ? Qt.rgba(accent.r, accent.g, accent.b, 0.6) : Theme.hairline
        opacity: unavailable ? 0.5 : 1
        Accessible.role: Accessible.StaticText
        Accessible.name: label
        Row {
            id: stepRow
            anchors.centerIn: parent
            spacing: 6
            Icon { name: step.icon; size: 15; color: step.first ? step.accent : Theme.ink2; anchors.verticalCenter: parent.verticalCenter }
            T { text: step.label; font.pixelSize: Theme.small; font.weight: step.first ? Font.DemiBold : Font.Normal
                color: step.first ? Theme.ink : Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
            Rectangle {
                visible: step.answered
                width: 16; height: 16; radius: 8; color: Theme.ok
                anchors.verticalCenter: parent.verticalCenter
                Icon { anchors.centerIn: parent; name: "check"; size: 11; weight: 2.4; color: Theme.bg0 }
            }
            Icon { visible: step.warned; name: "alert"; size: 14; color: Theme.amber; anchors.verticalCenter: parent.verticalCenter }
        }
    }

    component Arrow: Item {
        implicitWidth: 14; implicitHeight: 34
        Icon { anchors.centerIn: parent; name: "chevron"; size: 14; color: Theme.ink3; rotation: page.ar ? 180 : 0 }
    }

    // A test's outcome in one line.
    component Outcome: RowLayout {
        id: outcome
        property string result: "idle"
        property string okText: ""
        property string failText: ""
        visible: result !== "idle"
        Layout.fillWidth: true
        spacing: 8
        StatusPill {
            tone: outcome.result === "ok" ? "ok" : outcome.result === "testing" ? "info" : "error"
            icon: outcome.result === "ok" ? "check" : outcome.result === "testing" ? "clock" : "alert"
            text: outcome.result === "ok" ? mira.s.br_works : outcome.result === "testing" ? mira.s.br_testing : mira.s.br_failed
        }
        T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; visible: outcome.result !== "testing"; font.pixelSize: Theme.small
            color: outcome.result === "ok" ? Theme.ink2 : Theme.danger
            text: outcome.result === "ok" ? outcome.okText : outcome.failText; maximumLineCount: 3; elide: Text.ElideRight }
    }

    // ═══ the route: who answers now, the chain, and what answered last ═══
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: heroCol.implicitHeight + 36
        radius: 22
        edge: Qt.rgba(0.61, 0.48, 1.0, 0.38)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0.36, 0.26, 0.85, 0.28) }
            GradientStop { position: 1; color: Qt.rgba(0.10, 0.55, 0.75, 0.16) }
        }
        ColumnLayout {
            id: heroCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 14
            GridLayout {
                Layout.fillWidth: true
                columns: page.wide ? 2 : 1
                columnSpacing: 18; rowSpacing: 14
                // who answers now
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 14
                    Rectangle {
                        Layout.preferredWidth: 54; Layout.preferredHeight: 54; radius: 18
                        gradient: Gradient {
                            GradientStop { position: 0; color: Qt.rgba(0.49, 0.41, 1.0, 0.75) }
                            GradientStop { position: 1; color: Qt.rgba(0.21, 0.85, 0.96, 0.55) }
                        }
                        Icon { anchors.centerIn: parent; name: page.routeNow === "gemini" ? "sparkle" : "cloud"; size: 26; color: "white" }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        T { text: mira.s.br_route_now; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                        T { horizontalAlignment: Text.AlignLeft; font.pixelSize: Theme.title + 2; font.weight: Font.DemiBold
                            text: page.routeNow ? page.routeName(page.routeNow) : mira.s.page_loading
                            color: page.routeNow ? Theme.ink : Theme.ink3
                            Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                        T { horizontalAlignment: Text.AlignLeft;
                            visible: page.routeNow !== ""
                            Layout.fillWidth: true; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap; elide: Text.ElideRight
                            text: page.routeNow === "gemini" ? page.textModelName(st.text_model)
                                  : page.ownPick ? page.rowLabel(st.cloud_model)
                                  : page.bidi(mira.s.br_moai_setting + (page.cloudUses ? " · " + page.rowLabel(page.cloudUses) : ""))
                        }
                        // Gemini is still asked first, but its latest proof failed: say why (never hide it).
                        RowLayout {
                            visible: page.routeNow === "gemini" && !!st.gemini_warning
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            spacing: 6
                            Icon { name: "alert"; size: 13; color: Theme.amber }
                            T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; font.pixelSize: Theme.tiny + 1; color: Theme.amber
                                text: page.bidi(page.warningText(st.gemini_warning)); maximumLineCount: 2; elide: Text.ElideRight }
                        }
                        RowLayout {
                            visible: page.keyRejected
                            Layout.fillWidth: true
                            Layout.topMargin: 2
                            spacing: 6
                            Icon { name: "alert"; size: 13; color: Theme.danger }
                            T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; font.pixelSize: Theme.tiny + 1; color: Theme.danger
                                text: page.bidi(page.fill(mira.s.br_gemini_reason, { reason: page.reasonText(page.health.reason) }))
                                maximumLineCount: 2; elide: Text.ElideRight }
                        }
                    }
                }
                // what answered last
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: lastCol.implicitHeight + 22
                    radius: 16
                    color: Qt.rgba(0, 0, 0, 0.18); border.width: 1; border.color: Theme.hairline
                    ColumnLayout {
                        id: lastCol
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 4
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Icon { name: "clock"; size: 14; color: Theme.ink3 }
                            T { horizontalAlignment: Text.AlignLeft; text: mira.s.br_last; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap; Layout.fillWidth: true }
                            T { visible: !!page.last.time; text: page.last.time || ""; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                        }
                        T { horizontalAlignment: Text.AlignLeft; visible: !page.last.route; text: mira.s.br_last_none; font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true }
                        RowLayout {
                            visible: !!page.last.route
                            Layout.fillWidth: true
                            spacing: 8
                            T { text: page.routeName(page.last.route); font.pixelSize: Theme.body; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                            StatusPill {
                                visible: !!page.last.status && page.last.status !== "ok"
                                tone: page.last.status === "cancelled" ? "off" : page.last.status === "error" ? "error" : "warn"
                                text: page.last.status === "cancelled" ? mira.s.br_last_stopped : mira.s.br_last_failed
                            }
                            Item { Layout.fillWidth: true }
                            T { text: page.seconds(page.last.ms); font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap }
                        }
                        T { horizontalAlignment: Text.AlignLeft;
                            visible: !!page.last.route && !!page.last.model
                            text: page.modelLabel(page.last.route, page.last.model)
                            font.pixelSize: Theme.tiny + 1; color: Theme.ink3
                            Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideMiddle
                        }
                        T { horizontalAlignment: Text.AlignLeft;
                            visible: !!page.last.reason && page.last.reason !== "config"
                            text: page.bidi(page.fill(mira.s.br_gemini_reason, { reason: page.reasonText(page.last.reason) }))
                            font.pixelSize: Theme.tiny + 1; color: Theme.amber; Layout.fillWidth: true
                        }
                        T { horizontalAlignment: Text.AlignLeft; visible: !!page.last.refused; text: mira.s.br_last_refused; font.pixelSize: Theme.tiny + 1; color: Theme.amber; Layout.fillWidth: true }
                    }
                }
            }
            // the chain
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Step { label: "Gemini"; icon: "sparkle"; accent: Theme.violet; first: page.routeNow === "gemini"; unavailable: !page.geminiUsable
                       warned: page.geminiUsable && !!st.gemini_warning
                       answered: page.last.route === "gemini" && page.last.status === "ok" }
                Arrow {}
                Step { label: mira.s.br_route_cloud; icon: "cloud"; accent: Theme.cyan; first: page.routeNow === "moai-cloud"
                       answered: page.last.route === "moai-cloud" && page.last.status === "ok" }
                Arrow {}
                Step { label: mira.s.br_route_router; icon: "bolt"; accent: Theme.mint; answered: page.last.route === "router" && page.last.status === "ok" }
                Arrow {}
                Step { label: mira.s.br_route_moai; icon: "chip"; accent: Theme.amber; answered: page.last.route === "moai" && page.last.status === "ok" }
            }
            // the chain's rule, and the voice beside it (stacked when the page is narrow)
            GridLayout {
                Layout.fillWidth: true
                columns: page.wide ? 2 : 1
                columnSpacing: 12; rowSpacing: 6
                T { horizontalAlignment: Text.AlignLeft; text: mira.s.br_chain; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true }
                RowLayout {
                    spacing: 8
                    Layout.fillWidth: false        // packed together, never spread across the cell
                    Icon { name: "wave"; size: 14; color: page.geminiUsable ? Theme.rose : Theme.ink3 }
                    T { text: mira.s.br_voice; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                    T {
                        text: page.keyPresent ? (st.voice_model || "Gemini Live") : mira.s.br_voice_needs_key
                        font.pixelSize: Theme.tiny + 1; font.weight: Font.Medium; color: page.geminiUsable ? Theme.ink2 : Theme.ink3
                        wrapMode: Text.NoWrap; elide: Text.ElideRight
                        Layout.maximumWidth: heroCol.width * (page.wide ? 0.3 : 0.6)
                    }
                }
            }
        }
    }

    // ═══ Gemini: the key, and the typed-chat model ═══
    GridLayout {
        Layout.fillWidth: true
        columns: page.wide ? 2 : 1
        columnSpacing: 16; rowSpacing: 16

        Card {
            icon: "lock"; accent: Theme.violet
            title: mira.s.br_key_title
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            trailing: [
                // The latest proof of the key: the page's test, the Save-and-test, or a real answer.
                StatusPill {
                    readonly property string k: page.keyStatus
                    readonly property bool soft: k === "failed" && !page.keyRejected
                    tone: k === "ok" || k === "set" ? "ok" : k === "testing" ? "info" : soft ? "warn" : k === "failed" ? "error" : "off"
                    icon: k === "ok" || k === "set" ? "check" : k === "testing" ? "clock" : k === "failed" ? "alert" : ""
                    text: k === "ok" ? mira.s.br_key_works
                        : k === "set" ? mira.s.brain_key_set
                        : k === "testing" ? mira.s.brain_key_testing
                        : page.keyRejected ? mira.s.br_key_rejected
                        : soft ? (page.health.reason === "unknown" ? mira.s.brain_key_failed : page.cap(page.reasonText(page.health.reason)))
                        : k === "missing" ? mira.s.brain_key_missing : mira.s.page_loading
                }
            ]
            T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; text: mira.s.br_key_sub; font.pixelSize: Theme.small; color: Theme.ink2 }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                MiraField {
                    id: keyField
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    placeholderText: mira.s.brain_key_placeholder
                    Accessible.name: mira.s.br_key_title
                    onAccepted: if (text.trim().length >= 20) { mira.saveGeminiKey(text); text = "" }
                }
                PillButton {
                    text: mira.s.brain_key_save; iconName: "check"; primary: true; size: Theme.small
                    enabled: keyField.text.trim().length >= 20 && mira.brainKey !== "testing"
                    onClicked: { mira.saveGeminiKey(keyField.text); keyField.text = "" }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Icon { name: "shield"; size: 13; color: Theme.ink3 }
                T { horizontalAlignment: Text.AlignLeft; text: mira.s.br_key_stored; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                PillButton {
                    text: mira.s.br_key_test; iconName: "pulse"; size: Theme.small
                    enabled: page.keyPresent && page.keyStatus !== "testing"
                    onClicked: mira.brainPage.testGemini()
                }
                PillButton { text: mira.s.br_key_get; iconName: "external"; size: Theme.small; onClicked: mira.brainPage.openKeyHelp() }
            }
            Outcome {
                result: page.gtest.state || "idle"
                okText: page.fill(mira.s.br_test_ok, { model: page.textModelName(page.gtest.model), ms: page.seconds(page.gtest.ms) })
                failText: page.cap(page.reasonText(page.gtest.reason))
            }
        }

        Card {
            icon: "chat"; accent: Theme.cyan
            title: mira.s.br_model_title
            subtitle: mira.s.br_model_sub
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            Repeater {
                model: st.text_models || []
                delegate: Option {
                    required property var modelData
                    name: page.word(modelData.name_key) || modelData.id
                    note: page.word(modelData.note_key)
                    mono: modelData.id
                    chosen: st.text_model === modelData.id
                    accent: Theme.cyan
                    tags: chosen && st.text_model_source === "mira" ? [{ text: mira.s.br_chosen, tone: Theme.cyan }]
                          : modelData["default"] ? [{ text: mira.s.br_default, tone: Theme.ink2 }] : []
                    onClicked: if (!chosen || st.text_model_source !== "mira") mira.brainPage.setTextModel(modelData.id)
                }
            }
            T { horizontalAlignment: Text.AlignLeft; visible: st.text_model_source === "config"; text: mira.s.br_model_from_config; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true }
            RowLayout {
                visible: !page.keyPresent
                Layout.fillWidth: true
                spacing: 6
                Icon { name: "alert"; size: 13; color: Theme.amber }
                T { horizontalAlignment: Text.AlignLeft; text: mira.s.br_model_needs_key; font.pixelSize: Theme.tiny + 1; color: Theme.amber; Layout.fillWidth: true }
            }
        }
    }

    // ═══ Mo AI's free cloud brain ═══
    Card {
        icon: "cloud"; accent: Theme.mint
        title: mira.s.br_cloud_title
        subtitle: mira.s.br_cloud_sub
        trailing: [
            PillButton { text: mira.s.br_provider_settings; iconName: "settings"; size: Theme.small; implicitHeight: 34
                         onClicked: mira.brainPage.openProviderSettings() }
        ]

        // provider, key, test
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: provCol.implicitHeight + 24
            radius: 16
            color: Qt.rgba(1, 1, 1, 0.035); border.width: 1; border.color: Theme.hairline
            ColumnLayout {
                id: provCol
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Rectangle {
                        Layout.preferredWidth: 36; Layout.preferredHeight: 36; radius: 12
                        color: Qt.rgba(0.24, 0.95, 0.77, 0.14)
                        Icon { anchors.centerIn: parent; name: "globe"; size: 18; color: Theme.mint }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        T { text: mira.s.br_provider + (page.cloud.host ? " · " + page.cloud.host : ""); font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                        T { horizontalAlignment: Text.AlignLeft;
                            Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight
                            font.pixelSize: Theme.body; font.weight: Font.DemiBold
                            text: page.cloud.state === "ok" ? page.pick(page.cloud.name_ar, page.cloud.name_en)
                                  : page.cloud.state === "error" ? mira.s.br_unreachable : mira.s.page_loading
                            color: page.cloud.state === "error" ? Theme.danger : Theme.ink
                        }
                    }
                    StatusPill {
                        visible: page.cloud.state === "ok"
                        tone: page.cloud.has_key ? "ok" : "error"; icon: page.cloud.has_key ? "check" : "alert"
                        text: page.cloud.has_key ? mira.s.br_key_saved : mira.s.br_key_missing
                    }
                    StatusPill { visible: page.cloud.state === "ok" && page.cloud.free === false; tone: "warn"; text: mira.s.br_group_paid }
                    PillButton {
                        text: mira.s.br_test_connection; iconName: "pulse"; size: Theme.small; implicitHeight: 34
                        enabled: page.cloud.state === "ok" && page.ctest.state !== "testing"
                        onClicked: mira.brainPage.testCloud()
                    }
                }
                Outcome {
                    result: page.ctest.state || "idle"
                    okText: page.fill(mira.s.br_test_ok, { model: page.rowLabel(page.ctest.model), ms: page.seconds(page.ctest.ms) })
                            + (page.ctest.reply ? " · «" + page.ctest.reply + "»" : "")
                    failText: page.pick(page.ctest.error_ar, page.ctest.error_en)
                }
            }
        }

        // measured best
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Rectangle {
                Layout.preferredWidth: 36; Layout.preferredHeight: 36; radius: 12
                color: Qt.rgba(1, 0.77, 0.42, 0.14)
                Icon { anchors.centerIn: parent; name: "bolt"; size: 18; color: Theme.amber }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                T { horizontalAlignment: Text.AlignLeft; text: mira.s.br_best; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                // The best measured so far stays in ink even when a later run failed (its reason is below).
                T { horizontalAlignment: Text.AlignLeft;
                    Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight; font.pixelSize: Theme.small + 1; font.weight: Font.Medium
                    text: page.measure.measuring ? page.fill(mira.s.br_measuring, { done: page.measure.done || 0, total: page.measure.total || "…" })
                          : page.measure.best ? page.bidi(page.measure.best_label + " · " + page.ageText(page.measure.age_days)
                            + (page.measure.best_available ? "" : " · " + mira.s.br_best_gone))
                          : mira.s.br_best_none
                    color: page.measure.best || page.measure.measuring ? Theme.ink : Theme.ink2
                }
                RowLayout {
                    visible: page.measure.state === "error" && !page.measure.measuring && !!(page.measure.error_ar || page.measure.error_en)
                    Layout.fillWidth: true
                    Layout.topMargin: 3
                    spacing: 6
                    Icon { name: "alert"; size: 13; color: Theme.danger; Layout.alignment: Qt.AlignTop; Layout.topMargin: 2 }
                    T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; font.pixelSize: Theme.tiny + 1; color: Theme.danger
                        text: page.pick(page.measure.error_ar, page.measure.error_en); maximumLineCount: 3; elide: Text.ElideRight }
                }
            }
            PillButton {
                visible: !!page.measure.best && page.measure.best_available === true && st.cloud_model !== page.measure.best && !page.measure.measuring
                text: mira.s.br_use_it; iconName: "check"; size: Theme.small; implicitHeight: 34
                onClicked: mira.brainPage.setCloudModel(page.measure.best)
            }
            PillButton {
                text: mira.s.br_measure; iconName: "refresh"; size: Theme.small; implicitHeight: 34
                enabled: !page.measure.measuring && page.cloud.state === "ok" && page.cloud.has_key === true
                onClicked: mira.brainPage.measureNow()
            }
        }

        // the paid confirmation
        Rectangle {
            visible: !!st.paid_pending
            Layout.fillWidth: true
            Layout.preferredHeight: paidRow.implicitHeight + 20
            radius: 14
            color: Qt.rgba(1, 0.77, 0.42, 0.12); border.width: 1; border.color: Qt.rgba(1, 0.77, 0.42, 0.45)
            RowLayout {
                id: paidRow
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                spacing: 10
                Icon { name: "alert"; size: 18; color: Theme.amber }
                T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; font.pixelSize: Theme.small; color: Theme.ink
                    text: page.bidi(page.fill(mira.s.br_paid_confirm, { model: st.paid_pending_label || "", provider: page.pick(page.cloud.name_ar, page.cloud.name_en) })) }
                PillButton { text: mira.s.br_paid_yes; size: Theme.small; implicitHeight: 34; danger: true; onClicked: mira.brainPage.confirmPaidModel() }
                PillButton { text: mira.s.br_cancel; size: Theme.small; implicitHeight: 34; onClicked: mira.brainPage.cancelPaidModel() }
            }
        }

        RowLayout {
            visible: st.pick_missing === true
            Layout.fillWidth: true
            spacing: 6
            Icon { name: "alert"; size: 14; color: Theme.amber }
            T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; font.pixelSize: Theme.small; color: Theme.amber
                text: page.fill(mira.s.br_pick_gone, { model: page.rowLabel(st.cloud_model) }) }
        }

        // the list
        SectionTitle { icon: "grid"; text: mira.s.br_uses; accent: Theme.mint; Layout.topMargin: 4 }
        T { horizontalAlignment: Text.AlignLeft;
            visible: st.models_state === "loading" && (st.groups || []).length === 0
            text: mira.s.br_models_loading; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true
        }
        RowLayout {
            visible: st.models_state === "error"
            Layout.fillWidth: true
            spacing: 8
            Icon { name: "alert"; size: 16; color: Theme.danger }
            T { horizontalAlignment: Text.AlignLeft; Layout.fillWidth: true; font.pixelSize: Theme.small; color: Theme.danger; text: page.pick(st.models_error_ar, st.models_error_en) || mira.s.br_models_failed }
            PillButton { text: mira.s.retry; iconName: "refresh"; size: Theme.small; implicitHeight: 32; onClicked: mira.brainPage.refresh() }
        }
        Option {
            visible: (st.groups || []).length > 0
            name: mira.s.br_follow
            note: page.fill(mira.s.br_follow_note, { model: page.rowLabel(st.moai_default || page.cloud.model) })
            // Also what answers while a saved pick is no longer listed (the banner above says so).
            chosen: !page.ownPick
            accent: Theme.mint
            onClicked: if (st.cloud_model) mira.brainPage.setCloudModel("")
        }
        Repeater {
            model: st.groups || []
            delegate: ColumnLayout {
                id: group
                required property var modelData
                readonly property bool folded: modelData.key === "all" && !page.showAll
                Layout.fillWidth: true
                spacing: 6
                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 6
                    spacing: 8
                    T { text: page.word("br_group_" + group.modelData.key); font.pixelSize: Theme.tiny + 1; font.weight: Font.DemiBold
                        color: group.modelData.key === "paid" ? Theme.amber : Theme.ink3; wrapMode: Text.NoWrap }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.hairline }
                    PillButton {
                        visible: group.modelData.key === "all"
                        text: page.showAll ? mira.s.br_hide_all : page.fill(mira.s.br_show_all, { count: st.all_count || 0 })
                        iconName: page.showAll ? "" : "chevron-down"
                        size: Theme.tiny + 1; implicitHeight: 28
                        onClicked: page.showAll = !page.showAll
                    }
                }
                Repeater {
                    model: group.folded ? [] : group.modelData.rows
                    delegate: Option {
                        required property var modelData
                        name: page.pick(modelData.label_ar, modelData.label_en)
                        note: page.pick(modelData.note_ar, modelData.note_en)
                        mono: modelData.id
                        chosen: st.cloud_model === modelData.id
                        accent: modelData.paid ? Theme.amber : Theme.mint
                        tags: {
                            var out = []
                            if (modelData.serving) out.push({ text: mira.s.br_moai_setting, tone: Theme.violet })
                            if (modelData.id === page.measure.best) out.push({ text: mira.s.br_best_short, tone: Theme.amber })
                            if (modelData.paid) out.push({ text: mira.s.br_paid, tone: Theme.amber })
                            if (modelData.vision) out.push({ text: mira.s.br_vision, tone: Theme.cyan })
                            return out
                        }
                        onClicked: if (!chosen) mira.brainPage.setCloudModel(modelData.id)
                    }
                }
            }
        }
    }

    // ═══ permissions and privacy ═══
    GridLayout {
        Layout.fillWidth: true
        columns: page.wide ? 2 : 1
        columnSpacing: 16; rowSpacing: 16

        Card {
            icon: "shield"; accent: Theme.amber
            title: mira.s.br_perm_title
            subtitle: mira.s.br_perm_sub
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            T { visible: page.perms.state === "loading"; text: mira.s.page_loading; font.pixelSize: Theme.small; color: Theme.ink3 }
            T { horizontalAlignment: Text.AlignLeft; visible: page.perms.state === "error"; text: mira.s.br_unreachable; font.pixelSize: Theme.small; color: Theme.danger; Layout.fillWidth: true }
            ColumnLayout {
                visible: page.perms.state === "ok"
                Layout.fillWidth: true
                spacing: 8
                StatusPill {
                    tone: page.tierTone(page.perms.tier)
                    icon: page.perms.tier === "full" ? "alert" : "shield"
                    text: page.word("br_tier_" + (page.perms.tier || "custom")) || mira.s.br_tier_custom
                }
                T { horizontalAlignment: Text.AlignLeft; text: page.word("br_tier_" + (page.perms.tier || "custom") + "_note"); font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true }
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    Chip { icon: "globe"; tone: page.perms.web ? Theme.amber : Theme.ink3; text: page.perms.web ? mira.s.br_web_on : mira.s.br_web_off }
                    Chip { icon: "keyboard"; tone: page.perms.exec ? Theme.amber : Theme.ink3; text: page.perms.exec ? mira.s.br_exec_on : mira.s.br_exec_off }
                    Chip { icon: "monitor"; tone: page.perms.host_control ? Theme.amber : Theme.ok; text: page.perms.host_control ? mira.s.br_host_on : mira.s.br_host_off }
                    Chip { icon: "check"; tone: page.perms.approvals ? Theme.ok : Theme.amber; text: page.perms.approvals ? mira.s.br_approvals_on : mira.s.br_approvals_off }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: ruleText.implicitHeight + 20
                radius: 12
                color: Qt.rgba(0.61, 0.48, 1.0, 0.10); border.width: 1; border.color: Qt.rgba(0.61, 0.48, 1.0, 0.28)
                RowLayout {
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
                    spacing: 8
                    Icon { name: "sparkle"; size: 15; color: Theme.violet; Layout.alignment: Qt.AlignTop }
                    T { horizontalAlignment: Text.AlignLeft; id: ruleText; text: mira.s.br_mira_rule; font.pixelSize: Theme.tiny + 1; color: Theme.ink2; Layout.fillWidth: true }
                }
            }
            PillButton { text: mira.s.br_perm_open; iconName: "settings"; size: Theme.small; onClicked: mira.brainPage.openPermissionSettings() }
        }

        Card {
            icon: "lock"; accent: Theme.rose
            title: mira.s.br_privacy_title
            subtitle: mira.s.br_privacy_sub
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            Repeater {
                model: [
                    { icon: "sparkle", tone: Theme.violet, text: mira.s.br_priv_gemini, dim: !page.keyPresent },
                    { icon: "cloud", tone: Theme.mint, dim: false,
                      text: page.fill(mira.s.br_priv_cloud, { provider: page.pick(page.cloud.name_ar, page.cloud.name_en) || "Mo AI",
                                                              host: page.cloud.host || "—" }) },
                    { icon: "user", tone: Theme.cyan, text: mira.s.br_priv_local, dim: false },
                    { icon: "lock", tone: Theme.rose, text: mira.s.br_priv_keys, dim: false }
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 10
                    opacity: modelData.dim ? 0.6 : 1
                    Rectangle {
                        Layout.preferredWidth: 28; Layout.preferredHeight: 28; radius: 9
                        Layout.alignment: Qt.AlignTop
                        color: Qt.rgba(modelData.tone.r, modelData.tone.g, modelData.tone.b, 0.14)
                        Icon { anchors.centerIn: parent; name: modelData.icon; size: 15; color: modelData.tone }
                    }
                    T { horizontalAlignment: Text.AlignLeft; text: modelData.text; font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true }
                }
            }
        }
    }
}
