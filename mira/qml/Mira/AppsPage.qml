import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts

// Apps: Mo Store inside Mira. Search the store, your apps, updates, what this device should have,
// the compatibility hub (Windows games and programs, Android, the phone, virtual machines) and an
// app that arrived as a file. Every change is a card the owner approves; an app is "installed"
// only when the machine's own installed list says so (mira.appsPage re-reads it).
PageFrame {
    id: page
    readonly property var st: mira.appsPage ? mira.appsPage.state : ({})
    readonly property bool ar: mira.lang === "ar"
    readonly property bool wide: page.contentWidth >= 700
    readonly property bool compact: page.width < 520      // beside the conversation on a small window
    readonly property var pending: st.pending || ({})
    property bool showAll: false
    property string filter: ""

    icon: "apps"
    accent: Theme.mint
    title: mira.s.nav_apps || ""
    subtitle: mira.s.apps_sub
    busy: !!(st.installed_loading || st.scan_loading || st.searching || st.updates_scanning)

    actions: [
        PillButton {
            text: mira.s.apps_from_file; iconName: "download"; size: Theme.small; implicitHeight: 36
            visible: page.width > 640
            onClicked: fileDialog.open()
        },
        PillButton {
            text: mira.s.apps_open_store; iconName: "external"; size: Theme.small; implicitHeight: 36
            visible: !page.compact
            Accessible.description: mira.s.apps_open_store_tip
            onClicked: mira.appsPage.openStore()
        },
        IconButton { visible: page.compact; iconName: "external"; tip: mira.s.apps_open_store_tip; diameter: 36; onClicked: mira.appsPage.openStore() },
        IconButton { iconName: "refresh"; tip: mira.s.apps_reload; diameter: 36; onClicked: mira.appsPage.refresh() }
    ]

    // ── helpers ─────────────────────────────────────────────────────
    function installs(n) {
        if (!n) return ""
        var v = n >= 1000000 ? (n / 1000000).toFixed(1) + "M" : n >= 1000 ? Math.round(n / 1000) + "k" : "" + n
        return v + " " + mira.s.apps_installs
    }
    // "قبل ساعتين" / "2 hours ago" from an ISO time
    function ago(iso) {
        var t = Date.parse(iso || "")
        if (isNaN(t)) return ""
        var m = Math.max(0, Math.round((Date.now() - t) / 60000))
        if (m < 2) return mira.s.apps_ago_now
        var n = m, forms = mira.s.apps_ago_min
        if (m >= 1440) { n = Math.round(m / 1440); forms = mira.s.apps_ago_day }
        else if (m >= 60) { n = Math.round(m / 60); forms = mira.s.apps_ago_hour }
        var f = (forms || "").split("|"), word
        if (page.ar) word = n === 1 ? f[0] : n === 2 ? f[1] : (n <= 10 ? f[2] : f[3])
        else word = n === 1 ? f[0] : f[1]
        var phrase = page.ar && n <= 2 ? word : n + " " + word
        return (mira.s.apps_ago || "%1").replace("%1", phrase)
    }
    // "تحديث واحد بانتظارك" / "3 updates waiting": Arabic one|two|few|many, English one|many
    function plural(forms, n) {
        var f = (forms || "").split("|"), w
        if (page.ar) w = n === 1 ? f[0] : n === 2 ? f[1] : (n <= 10 ? f[2] : f[3])
        else w = n === 1 ? f[0] : f[1]
        return (w || "").replace("%1", n)
    }
    // what a pending mark says: a card waiting for him, or an approved job being followed
    function waitWord(w) { return w === "running" ? mira.s.apps_following : mira.s.apps_waiting }
    function hue(name) {
        var h = 0
        for (var i = 0; i < (name || "").length; ++i) h = (h * 31 + name.charCodeAt(i)) % 360
        return h / 360
    }
    readonly property var installedShown: {
        var all = st.installed || []
        var f = page.filter.trim().toLowerCase()
        var list = f === "" ? all : all.filter(function(a) {
            return a.name.toLowerCase().indexOf(f) >= 0 || a.id.toLowerCase().indexOf(f) >= 0 })
        return f === "" && !page.showAll ? list.slice(0, 10) : list
    }
    readonly property var suggestions: [mira.s.apps_q_video, mira.s.apps_q_music, mira.s.apps_q_browser,
                                        mira.s.apps_q_office, mira.s.apps_q_chat, mira.s.apps_q_draw]

    // the field says what the results below are for, also when the page is opened again
    Component.onCompleted: { query.text = page.st.query || ""; query.forceActiveFocus() }

    // ── inline components ───────────────────────────────────────────
    // An app's face: its theme icon or store icon when there is one, else a coloured monogram.
    component AppGlyph: Item {
        id: g
        property string name: ""
        property string source: ""
        property int size: 44
        implicitWidth: size; implicitHeight: size
        Layout.preferredWidth: size; Layout.preferredHeight: size
        Rectangle {
            anchors.fill: parent
            radius: Math.round(g.size * 0.3)
            visible: img.status !== Image.Ready
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.hsla(page.hue(g.name), 0.62, 0.58, 0.62) }
                GradientStop { position: 1; color: Qt.hsla((page.hue(g.name) + 0.12) % 1, 0.70, 0.45, 0.50) }
            }
            border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.14)
            T { anchors.centerIn: parent; text: (g.name || "?").charAt(0).toUpperCase(); font.pixelSize: Math.round(g.size * 0.42); font.weight: Font.Bold; color: "white" }
        }
        // Never `asynchronous`: image://icon is a Python provider, and Qt's reader thread waiting for
        // the GIL while the main thread holds it (a state update building these rows) froze the
        // window. A theme icon is cheap; a store icon (https) loads off the thread by itself.
        Image {
            id: img
            anchors.fill: parent
            source: g.source
            sourceSize: Qt.size(g.size * 2, g.size * 2)
            fillMode: Image.PreserveAspectFit
            smooth: true
            visible: status === Image.Ready
        }
    }

    // A small rounded word you can press (suggestions).
    component Chip: AbstractButton {
        id: chip
        property color accent: Theme.cyan
        implicitHeight: 30
        implicitWidth: chipText.implicitWidth + 26
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text
        background: Rectangle {
            radius: 15
            color: chip.down ? Qt.rgba(chip.accent.r, chip.accent.g, chip.accent.b, 0.26)
                 : chip.hovered ? Qt.rgba(chip.accent.r, chip.accent.g, chip.accent.b, 0.17) : Qt.rgba(1, 1, 1, 0.05)
            border.width: chip.visualFocus ? 2 : 1
            border.color: chip.visualFocus ? Theme.cyan : Qt.rgba(chip.accent.r, chip.accent.g, chip.accent.b, chip.hovered ? 0.55 : 0.28)
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }
        contentItem: T { id: chipText; text: chip.text; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap
                         horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
    }

    // A placeholder row that breathes while the store answers.
    component Skeleton: Rectangle {
        id: sk
        Layout.fillWidth: true
        Layout.preferredHeight: 72
        radius: 16
        color: Qt.rgba(1, 1, 1, 0.04)
        border.width: 1; border.color: Theme.hairline
        SequentialAnimation on opacity {
            running: sk.visible && mira.motion; loops: Animation.Infinite
            NumberAnimation { to: 0.45; duration: 650 } NumberAnimation { to: 1; duration: 650 }
        }
        Rectangle { anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter } width: 44; height: 44; radius: 13; color: Qt.rgba(1, 1, 1, 0.07) }
        Rectangle { anchors { left: parent.left; leftMargin: 72 } y: 20; width: parent.width * 0.32; height: 11; radius: 5; color: Qt.rgba(1, 1, 1, 0.08) }
        Rectangle { anchors { left: parent.left; leftMargin: 72 } y: 40; width: parent.width * 0.5; height: 9; radius: 4; color: Qt.rgba(1, 1, 1, 0.05) }
    }

    // One line saying why a list is empty or failed, with an optional action.
    component Notice: RowLayout {
        id: notice
        property string icon: "alert"
        property string text: ""
        property color tone: Theme.ink3
        property string action: ""
        signal triggered()
        Layout.fillWidth: true
        spacing: 10
        Icon { name: notice.icon; size: 16; color: notice.tone }
        T { text: notice.text; color: notice.tone === Theme.ink3 ? Theme.ink2 : notice.tone; font.pixelSize: Theme.small; Layout.fillWidth: true }
        PillButton { visible: notice.action !== ""; text: notice.action; size: Theme.small; implicitHeight: 32; onClicked: notice.triggered() }
    }

    // ── 1. the store ────────────────────────────────────────────────
    Glass {
        id: hero
        Layout.fillWidth: true
        Layout.preferredHeight: heroCol.implicitHeight + 36
        radius: 22
        edge: Qt.rgba(0.24, 0.95, 0.77, 0.30)
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0.10, 0.55, 0.50, 0.22) }
            GradientStop { position: 1; color: Qt.rgba(0.36, 0.26, 0.85, 0.22) }
        }
        ColumnLayout {
            id: heroCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Icon { name: "package"; size: 20; color: Theme.mint }
                T { text: mira.s.apps_search_title; font.pixelSize: Theme.title; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                StatusPill { visible: page.st.source === "local"; text: mira.s.apps_local_source; tone: "warn"; icon: "wifi" }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                MiraField {
                    id: query
                    Layout.fillWidth: true
                    implicitHeight: 46
                    font.pixelSize: Theme.body + 1
                    placeholderText: mira.s.apps_search_hint
                    horizontalAlignment: TextInput.AlignLeft      // mirrored to the right in Arabic
                    leftPadding: page.ar ? 14 : 42
                    rightPadding: page.ar ? 42 : 14
                    Accessible.name: mira.s.apps_search_title
                    onAccepted: mira.appsPage.search(text)
                    // Main.qml's Escape shortcut closes the page; a search to clear wins it first
                    Keys.onShortcutOverride: function(event) {
                        if (event.key === Qt.Key_Escape && (text !== "" || page.st.searched)) event.accepted = true
                    }
                    Keys.onEscapePressed: function(event) {
                        if (text !== "" || page.st.searched) { text = ""; mira.appsPage.clearSearch(); event.accepted = true }
                        else event.accepted = false
                    }
                    Icon {
                        anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
                        name: "sparkle"; size: 18; color: query.activeFocus ? Theme.mint : Theme.ink3
                    }
                }
                PillButton {
                    text: page.compact ? "" : mira.s.apps_search_go; iconName: "send"; primary: true
                    Accessible.name: mira.s.apps_search_go
                    implicitHeight: 46
                    enabled: query.text.trim() !== "" && !page.st.searching
                    onClicked: mira.appsPage.search(query.text)
                }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                T { text: mira.s.apps_try; font.pixelSize: Theme.small; color: Theme.ink3; height: 30; verticalAlignment: Text.AlignVCenter; wrapMode: Text.NoWrap }
                Repeater {
                    model: page.suggestions
                    delegate: Chip {
                        required property var modelData
                        text: modelData
                        accent: Theme.mint
                        onClicked: { query.text = modelData; mira.appsPage.search(modelData) }
                    }
                }
            }
        }
    }

    // results
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 8
        visible: !!(page.st.searching || page.st.searched)
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            SectionTitle { icon: "grid"; text: mira.s.apps_results + (page.st.searching ? "" : " · " + (page.st.results || []).length); accent: Theme.mint }
            Item { Layout.fillWidth: true }
            PillButton { text: mira.s.apps_clear; iconName: "x"; size: Theme.small; implicitHeight: 30
                         onClicked: { query.text = ""; mira.appsPage.clearSearch() } }
        }
        Repeater { model: page.st.searching ? 3 : 0; delegate: Skeleton {} }
        Notice {
            visible: !page.st.searching && !!page.st.search_failed
            icon: "alert"; tone: Theme.danger
            text: mira.s.apps_search_failed + (page.st.search_error ? " — " + page.st.search_error : "")
            action: mira.s.retry
            onTriggered: mira.appsPage.search(page.st.query)
        }
        Glass {
            visible: !page.st.searching && !page.st.search_failed && !!page.st.searched && (page.st.results || []).length === 0
            Layout.fillWidth: true
            Layout.preferredHeight: emptyRow.implicitHeight + 28
            radius: 16
            RowLayout {
                id: emptyRow
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                spacing: 12
                Icon { name: "package"; size: 22; color: Theme.ink3 }
                T { text: mira.s.apps_no_results; color: Theme.ink2; Layout.fillWidth: true }
                PillButton { text: mira.s.apps_ask_mira; iconName: "sparkle"; size: Theme.small; implicitHeight: 34
                             onClicked: mira.appsPage.askMira(query.text !== "" ? query.text : page.st.query) }
            }
        }
        Repeater {
            model: page.st.searching ? [] : (page.st.results || [])
            delegate: Glass {
                id: result
                required property var modelData
                readonly property string waiting: page.pending[modelData.id] || ""
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(78, resultRow.implicitHeight + 24)
                radius: 18
                lit: !!modelData.recommended
                RowLayout {
                    id: resultRow
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 14; rightMargin: 14 }
                    spacing: 14
                    AppGlyph { name: result.modelData.name; source: result.modelData.icon || ""; size: page.compact ? 40 : 48 }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            T { text: result.modelData.name; font.pixelSize: Theme.body + 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight
                                Layout.fillWidth: true; Layout.maximumWidth: Math.ceil(implicitWidth) + 2; horizontalAlignment: Text.AlignLeft }
                            Icon {
                                visible: !!result.modelData.verified; name: "shield"; size: 14; weight: 2; color: Theme.cyan
                                ToolTip.visible: vHover.hovered; ToolTip.text: mira.s.apps_verified
                                HoverHandler { id: vHover }
                            }
                            StatusPill { visible: !!result.modelData.recommended && !page.compact; text: mira.s.apps_pick; tone: "ok"; icon: "sparkle" }
                            StatusPill { visible: !!result.modelData.installed && !page.compact; text: mira.s.apps_installed; tone: "info"; icon: "check" }
                            Item { Layout.fillWidth: true }
                        }
                        T { visible: text !== ""; text: result.modelData.summary || ""; font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideRight; wrapMode: Text.NoWrap
                            horizontalAlignment: Text.AlignLeft }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            T { visible: text !== "" && !page.compact; text: page.installs(result.modelData.installs); font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap }
                            T { visible: text !== ""; text: result.modelData.note || ""; font.pixelSize: Theme.tiny; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true
                                horizontalAlignment: Text.AlignLeft; color: result.modelData.recommended ? Theme.mint : Theme.amber }
                        }
                    }
                    StatusPill {
                        visible: result.waiting !== "" && result.waiting !== "open"
                        text: page.compact ? "" : page.waitWord(result.waiting)
                        tone: result.waiting === "running" ? "info" : "warn"; icon: result.waiting === "running" ? "pulse" : "clock"
                        Accessible.name: page.waitWord(result.waiting)
                    }
                    StatusPill {
                        visible: result.waiting === "" && !!result.modelData.installed && result.modelData.scope === "system" && !page.compact
                        text: mira.s.apps_system_scope; tone: "off"; icon: "lock"
                        ToolTip.visible: sysHover.hovered; ToolTip.text: mira.s.apps_system_tip
                        HoverHandler { id: sysHover }
                    }
                    PillButton {
                        visible: (!!result.modelData.installed && result.waiting === "") || result.waiting === "open"
                        readonly property string label: result.waiting === "open" ? mira.s.apps_opening : mira.s.apps_open
                        text: page.compact ? "" : label
                        Accessible.name: label + " " + result.modelData.name
                        enabled: result.waiting !== "open"
                        iconName: "external"; size: Theme.small; implicitHeight: 34
                        onClicked: mira.appsPage.openApp(result.modelData.id)
                    }
                    PillButton {
                        // one action per row when compact: Remove stays in "Your apps"; Mo Store removes
                        // only the owner's own apps, so a system-wide one offers Open alone
                        visible: result.waiting === "" && !(result.modelData.installed && (page.compact || result.modelData.scope === "system"))
                        readonly property string label: result.modelData.installed ? mira.s.apps_remove : mira.s.apps_install
                        text: page.compact ? "" : label
                        Accessible.name: label + " " + result.modelData.name
                        iconName: result.modelData.installed ? "trash" : "download"
                        primary: !result.modelData.installed; danger: !!result.modelData.installed
                        size: Theme.small; implicitHeight: 34
                        onClicked: result.modelData.installed ? mira.appsPage.remove(result.modelData.id) : mira.appsPage.install(result.modelData.id)
                    }
                }
            }
        }
    }

    // ── 2. updates · recommended for this device ────────────────────
    GridLayout {
        Layout.fillWidth: true
        columns: page.wide ? 2 : 1
        columnSpacing: 16; rowSpacing: 16

        Card {
            id: updatesCard
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            icon: "download"; accent: Theme.violet
            title: mira.s.apps_updates_title
            subtitle: page.st.updates_at ? mira.s.apps_checked + " · " + page.ago(page.st.updates_at) : ""
            readonly property bool settled: !page.st.updates_scanning && !page.st.updates_loading && !page.st.updates_failed
            trailing: [ StatusPill { visible: (page.st.updates || []).length > 0; text: page.plural(mira.s.apps_updates_n, (page.st.updates || []).length); tone: "warn" } ]

            Notice { visible: !!page.st.updates_scanning; icon: "pulse"; tone: Theme.violet; text: mira.s.apps_checking_updates }
            Notice { visible: !page.st.updates_scanning && !!page.st.updates_loading && !page.st.updates_at; icon: "clock"; text: mira.s.page_loading }
            Notice { visible: !page.st.updates_scanning && !page.st.updates_loading && !!page.st.updates_failed; icon: "alert"; tone: Theme.danger
                     text: mira.s.apps_updates_failed + (page.st.updates_error ? " — " + page.st.updates_error : "")
                     action: mira.s.retry; onTriggered: mira.appsPage.refresh() }
            Notice { visible: updatesCard.settled && !page.st.updates_report
                     icon: "clock"; text: mira.s.apps_updates_unknown }
            Notice { visible: updatesCard.settled && !!page.st.updates_report && !page.st.updates_checked
                     icon: "alert"; tone: Theme.amber; text: mira.s.apps_updates_check_failed }
            Notice { visible: updatesCard.settled && !!page.st.updates_checked && (page.st.updates || []).length === 0
                     icon: "check"; tone: Theme.ok; text: mira.s.apps_updates_none }
            Notice { visible: !page.st.updates_scanning && (page.st.updates_note || "") !== ""
                     icon: "clock"; text: mira.s[page.st.updates_note] || "" }
            Flow {
                Layout.fillWidth: true
                visible: !page.st.updates_scanning && (page.st.updates || []).length > 0
                spacing: 6
                Repeater {
                    model: (page.st.updates || []).slice(0, 9)
                    delegate: Rectangle {
                        required property var modelData
                        height: 28; radius: 14; width: upText.implicitWidth + 22
                        color: Qt.rgba(0.61, 0.48, 1.0, 0.12); border.width: 1; border.color: Qt.rgba(0.61, 0.48, 1.0, 0.30)
                        T { id: upText; anchors.centerIn: parent; text: modelData; font.pixelSize: Theme.small; color: Theme.ink; wrapMode: Text.NoWrap }
                    }
                }
                T { visible: (page.st.updates || []).length > 9; text: "+" + ((page.st.updates || []).length - 9); color: Theme.ink3; font.pixelSize: Theme.small; height: 28; verticalAlignment: Text.AlignVCenter }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                StatusPill { visible: !!page.pending.__updates__; text: page.waitWord(page.pending.__updates__ || "")
                             tone: page.pending.__updates__ === "running" ? "info" : "warn"; icon: page.pending.__updates__ === "running" ? "pulse" : "clock"; height: 34 }
                PillButton {
                    visible: !page.pending.__updates__
                    text: mira.s.apps_update_all; iconName: "download"
                    primary: (page.st.updates || []).length > 0
                    size: Theme.small; implicitHeight: 34
                    onClicked: mira.appsPage.updateAll()
                }
                PillButton {
                    text: mira.s.apps_check_now; iconName: "refresh"; size: Theme.small; implicitHeight: 34
                    enabled: !page.st.updates_scanning
                    onClicked: mira.appsPage.checkUpdates()
                }
            }
        }

        Card {
            id: recCard
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            icon: "sparkle"; accent: Theme.rose
            title: mira.s.apps_rec_title
            subtitle: mira.s.apps_rec_sub
            readonly property var missing: page.st.recommended || []
            readonly property int free: missing.filter(function(r) { return !page.pending[r.id] }).length
            trailing: [ PillButton {
                visible: recCard.free > 1 && recCard.width > 460
                text: mira.s.apps_rec_all + " · " + recCard.free; iconName: "download"; primary: true
                size: Theme.small; implicitHeight: 32
                onClicked: mira.appsPage.installAllRecommended()
            } ]

            Notice { visible: !page.st.scanned || !!page.st.plan_pending; icon: "clock"; text: mira.s.apps_rec_reading }
            Notice { visible: !!page.st.scanned && !!page.st.scan_failed; icon: "alert"; tone: Theme.danger
                     text: mira.s.apps_rec_failed + (page.st.scan_error ? " — " + page.st.scan_error : "")
                     action: mira.s.retry; onTriggered: mira.appsPage.refresh() }
            Notice { visible: !!page.st.scanned && !page.st.plan_pending && !page.st.scan_failed && recCard.missing.length === 0
                     icon: "check"; tone: Theme.ok; text: mira.s.apps_rec_done }
            Repeater {
                model: recCard.missing
                delegate: RowLayout {
                    id: rec
                    required property var modelData
                    readonly property string waiting: page.pending[modelData.id] || ""
                    Layout.fillWidth: true
                    spacing: 12
                    Rectangle {
                        Layout.preferredWidth: 38; Layout.preferredHeight: 38; radius: 12
                        color: Qt.rgba(1, 0.44, 0.71, 0.13); border.width: 1; border.color: Qt.rgba(1, 0.44, 0.71, 0.28)
                        Icon { anchors.centerIn: parent; name: rec.modelData.glyph || "package"; size: 18; color: Theme.rose }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        T { text: rec.modelData.name; font.pixelSize: Theme.small + 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true
                            horizontalAlignment: Text.AlignLeft }
                        T { visible: text !== ""; text: (page.ar ? rec.modelData.why_ar : rec.modelData.why_en) || ""; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap
                            horizontalAlignment: Text.AlignLeft }
                    }
                    StatusPill { visible: rec.waiting !== ""; text: page.compact ? "" : page.waitWord(rec.waiting)
                                 tone: rec.waiting === "running" ? "info" : "warn"; icon: rec.waiting === "running" ? "pulse" : "clock"
                                 Accessible.name: page.waitWord(rec.waiting) }
                    PillButton { visible: rec.waiting === ""; text: page.compact ? "" : mira.s.apps_install; iconName: "download"; size: Theme.small; implicitHeight: 32
                                 Accessible.name: mira.s.apps_install + " " + rec.modelData.name
                                 onClicked: mira.appsPage.installRecommended(rec.modelData.id) }
                }
            }
            PillButton {
                visible: recCard.free > 1 && recCard.width <= 460
                Layout.alignment: Qt.AlignHCenter
                text: mira.s.apps_rec_all + " · " + recCard.free; iconName: "download"; primary: true
                size: Theme.small; implicitHeight: 34
                onClicked: mira.appsPage.installAllRecommended()
            }
        }
    }

    // ── 3. your apps ────────────────────────────────────────────────
    Card {
        icon: "grid"; accent: Theme.cyan
        title: mira.s.apps_installed_title
        trailing: [ StatusPill { visible: !!page.st.installed_read; text: "" + (page.st.installed || []).length; tone: "info" } ]

        MiraField {
            id: filterField
            Layout.fillWidth: true
            visible: (page.st.installed || []).length > 6
            placeholderText: mira.s.apps_filter
            Accessible.name: mira.s.apps_filter
            onTextChanged: page.filter = text
        }
        Notice { visible: !!page.st.installed_loading && !page.st.installed_read; icon: "clock"; text: mira.s.page_loading }
        Notice { visible: !page.st.installed_loading && !!page.st.installed_failed; icon: "alert"; tone: Theme.danger
                 text: mira.s.apps_installed_failed + (page.st.installed_error ? " — " + page.st.installed_error : "")
                 action: mira.s.retry; onTriggered: mira.appsPage.refresh() }
        Notice { visible: !!page.st.installed_partial; icon: "alert"; tone: Theme.amber; text: mira.s.apps_installed_partial }
        Notice { visible: !!page.st.installed_read && (page.st.installed || []).length === 0; icon: "package"; text: mira.s.apps_installed_empty }
        Notice { visible: page.filter.trim() !== "" && page.installedShown.length === 0 && (page.st.installed || []).length > 0; icon: "x"; text: mira.s.apps_no_match }

        GridLayout {
            Layout.fillWidth: true
            columns: page.wide ? 2 : 1
            columnSpacing: 8; rowSpacing: 8
            Repeater {
                model: page.installedShown
                delegate: Rectangle {
                    id: app
                    required property var modelData
                    readonly property string waiting: page.pending[modelData.id] || ""
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    implicitHeight: 60
                    radius: 16
                    color: appHover.hovered ? Qt.rgba(1, 1, 1, 0.065) : Qt.rgba(1, 1, 1, 0.035)
                    border.width: 1; border.color: appHover.hovered ? Theme.hairlineStrong : Theme.hairline
                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                    HoverHandler { id: appHover }
                    RowLayout {
                        anchors { fill: parent; leftMargin: 10; rightMargin: 8 }
                        spacing: 10
                        AppGlyph { name: app.modelData.name; source: app.modelData.icon || ""; size: 38 }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            T { text: app.modelData.name; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true
                                horizontalAlignment: Text.AlignLeft }
                            T {
                                horizontalAlignment: Text.AlignLeft
                                text: app.modelData.id + (app.modelData.version ? "  ·  " + app.modelData.version : "")
                                font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true
                            }
                        }
                        StatusPill { visible: app.waiting !== "" && app.waiting !== "open"; text: page.waitWord(app.waiting)
                                     tone: app.waiting === "running" ? "info" : "warn"; icon: app.waiting === "running" ? "pulse" : "clock" }
                        IconButton { visible: app.waiting === "" || app.waiting === "open"; iconName: "external"; tip: mira.s.apps_open + " " + app.modelData.name; diameter: 34
                                     enabled: app.waiting !== "open"; onClicked: mira.appsPage.openApp(app.modelData.id) }
                        // Mo Store removes only the owner's own apps: a system-wide one says so instead
                        IconButton { visible: app.waiting === "" && app.modelData.scope !== "system"; iconName: "trash"; tip: mira.s.apps_remove + " " + app.modelData.name; diameter: 34
                                     tint: Qt.rgba(1, 0.36, 0.48, 0.8); accent: Theme.danger
                                     onClicked: mira.appsPage.remove(app.modelData.id) }
                        Item {
                            visible: app.waiting === "" && app.modelData.scope === "system"
                            implicitWidth: 34; implicitHeight: 34
                            Accessible.role: Accessible.StaticText
                            Accessible.name: mira.s.apps_system_scope + ": " + mira.s.apps_system_tip
                            Icon { anchors.centerIn: parent; name: "lock"; size: 15; color: Theme.ink3 }
                            HoverHandler { id: lockHover }
                            ToolTip.visible: lockHover.hovered; ToolTip.text: mira.s.apps_system_tip; ToolTip.delay: 300
                        }
                    }
                }
            }
        }
        PillButton {
            visible: page.filter.trim() === "" && (page.st.installed || []).length > 10
            text: page.showAll ? mira.s.apps_show_less : mira.s.apps_show_all + " · " + (page.st.installed || []).length
            iconName: "chevron-down"
            size: Theme.small; implicitHeight: 32
            Layout.alignment: Qt.AlignHCenter
            onClicked: page.showAll = !page.showAll
        }
    }

    // ── 4. run everything: the compatibility hub ────────────────────
    Card {
        icon: "rocket"; accent: Theme.amber
        title: mira.s.apps_compat_title
        subtitle: mira.s.apps_compat_sub

        Notice { visible: !page.st.scanned && (page.st.compat || []).length === 0; icon: "clock"; text: mira.s.page_loading }
        Notice { visible: !!page.st.scanned && (page.st.compat || []).length === 0; icon: "alert"; tone: Theme.danger
                 text: mira.s.page_unreachable; action: mira.s.retry; onTriggered: mira.appsPage.refresh() }
        GridLayout {
            id: hubGrid
            Layout.fillWidth: true
            columns: page.contentWidth > 980 ? 3 : page.wide ? 2 : 1
            columnSpacing: 8; rowSpacing: 8
            Repeater {
                id: hubRepeater
                model: page.st.compat || []
                delegate: Rectangle {
                    id: hub
                    required property var modelData
                    required property int index
                    readonly property color c: modelData.state === "ready" ? Theme.ok : modelData.state === "setup" ? Theme.amber : Theme.off
                    readonly property string name: mira.s[modelData.title] || ""
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.preferredWidth: 1
                    // a last tile alone on its row takes the whole row
                    Layout.columnSpan: hubGrid.columns > 1 && index === hubRepeater.count - 1 && hubRepeater.count % hubGrid.columns === 1 ? hubGrid.columns : 1
                    implicitHeight: hubCol.implicitHeight + 26
                    radius: 18
                    color: Qt.rgba(1, 1, 1, 0.035)
                    border.width: 1; border.color: modelData.waiting ? Qt.rgba(1, 0.77, 0.42, 0.55) : Theme.hairline
                    ColumnLayout {
                        id: hubCol
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 13 }
                        spacing: 10
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Rectangle {
                                Layout.preferredWidth: 38; Layout.preferredHeight: 38; radius: 12
                                color: Qt.rgba(hub.c.r, hub.c.g, hub.c.b, 0.14)
                                Icon { anchors.centerIn: parent; name: hub.modelData.glyph; size: 19; color: hub.c }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                T { text: mira.s[hub.modelData.title] || ""; font.pixelSize: Theme.small + 1; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignLeft }
                                T { text: mira.s[hub.modelData.detail] || ""; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight
                                    horizontalAlignment: Text.AlignLeft }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            StatusPill {
                                readonly property string w: hub.modelData.waiting || ""
                                text: w !== "" ? page.waitWord(w)
                                      : hub.modelData.state === "ready" ? mira.s.apps_ready
                                      : hub.modelData.state === "setup" ? mira.s.apps_needs_setup
                                      : hub.modelData.state === "checking" ? mira.s.apps_checking
                                      : hub.modelData.state === "unknown" ? mira.s.apps_unknown : mira.s.apps_unavailable
                                tone: w === "running" ? "info" : w !== "" ? "warn" : hub.modelData.state === "ready" ? "ok" : hub.modelData.state === "setup" ? "warn" : "off"
                                icon: w === "running" ? "pulse" : w !== "" ? "clock" : hub.modelData.state === "ready" ? "check" : ""
                            }
                            Item { Layout.fillWidth: true }
                            PillButton {
                                visible: hub.modelData.state === "setup" && !hub.modelData.waiting
                                text: mira.s.apps_set_up; iconName: hub.modelData.privileged ? "lock" : "rocket"
                                primary: true; size: Theme.small; implicitHeight: 32
                                Accessible.name: mira.s.apps_set_up + " " + hub.name
                                Accessible.description: hub.modelData.privileged ? mira.s.apps_admin : ""
                                onClicked: mira.appsPage.setup(hub.modelData.key)
                            }
                            PillButton {
                                visible: hub.modelData.state === "ready" && (hub.modelData.opens || "") !== ""
                                text: mira.s.apps_open; iconName: "external"; size: Theme.small; implicitHeight: 32
                                Accessible.name: mira.s.apps_open + " " + hub.name
                                onClicked: mira.appsPage.openApp(hub.modelData.opens)
                            }
                            IconButton {
                                visible: (hub.modelData.sheet || "") !== ""
                                iconName: "chevron"; diameter: 32
                                rotation: page.ar ? 180 : 0          // "onward" points left in Arabic
                                tip: mira.s.apps_phone_devices
                                onClicked: mira.appsPage.showPage(hub.modelData.sheet)
                            }
                        }
                    }
                }
            }
        }
    }

    // ── 5. an app that arrived as a file ────────────────────────────
    Card {
        icon: "package"; accent: Theme.cyan
        title: mira.s.apps_file_title
        subtitle: mira.s.apps_file_sub

        Rectangle {
            id: dropZone
            Layout.fillWidth: true
            Layout.preferredHeight: dropCol.implicitHeight + 36
            radius: 18
            color: drop.containsDrag ? Qt.rgba(0.21, 0.85, 0.96, 0.12) : Qt.rgba(0, 0, 0, 0.18)
            border.width: drop.containsDrag ? 2 : 1
            border.color: drop.containsDrag ? Theme.cyan : Theme.hairlineStrong
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            ColumnLayout {
                id: dropCol
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 18 }
                spacing: 10
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 48; Layout.preferredHeight: 48; radius: 24
                    color: Qt.rgba(0.21, 0.85, 0.96, drop.containsDrag ? 0.25 : 0.12)
                    Icon { anchors.centerIn: parent; name: "download"; size: 22; color: Theme.cyan }
                }
                T { Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
                    text: drop.containsDrag ? mira.s.apps_file_drop : mira.s.apps_kinds
                    font.pixelSize: drop.containsDrag ? Theme.body : Theme.small; color: drop.containsDrag ? Theme.ink : Theme.ink2 }
                PillButton { Layout.alignment: Qt.AlignHCenter; text: mira.s.apps_file_choose; iconName: "clip"; size: Theme.small; implicitHeight: 34
                             onClicked: fileDialog.open() }
            }
            DropArea {
                id: drop
                anchors.fill: parent
                onDropped: function(event) {
                    if (event.hasUrls && event.urls.length > 0) {
                        var files = []
                        for (var i = 0; i < event.urls.length; ++i) files.push(event.urls[i].toString())
                        mira.appsPage.installDropped(files)
                        event.acceptProposedAction()
                    }
                }
            }
        }
        Notice {
            visible: (page.st.file_status || "") !== ""
            icon: page.st.file_tone === "error" ? "alert" : "clock"
            tone: page.st.file_tone === "error" ? Theme.danger : Theme.amber
            text: page.st.file_status || ""
        }
    }

    Item { Layout.preferredHeight: 4 }

    FileDialog {
        id: fileDialog
        title: mira.s.apps_file_title
        currentFolder: page.st.file_folder || ""
        nameFilters: [mira.s.apps_file_title + " (*.AppImage *.appimage *.flatpakref *.tar.gz *.tgz *.tar.xz *.txz *.tar.bz2 *.tbz2 *.tar.zst *.tar *.zip *.rpm *.exe *.msi *.apk)", "* (*)"]
        onAccepted: mira.appsPage.installFile(selectedFile.toString())
    }
}
