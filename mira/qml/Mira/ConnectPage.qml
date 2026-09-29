import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes

// Connect: every way to reach this computer, and Mira, away from the desk — Mo PC Remote, Mira on
// the phone, the phone link, the message channels and the Echo in the room. Every state here is read
// back (mira.connectPage.state, mira.companion, mira.echo); a click never flips a state by itself:
// a system change is an owner card, and the page says "waiting" until the executor or a read-back
// answers, or says it did not happen. Notes age away; a note never contradicts the pill beside it.
PageFrame {
    id: page
    icon: "globe"
    accent: Theme.cyan
    title: mira.s.nav_connect
    subtitle: mira.s.cn_sub
    busy: !!page.st.loading

    readonly property var st: mira.connectPage ? mira.connectPage.state : ({})
    readonly property var remote: page.st.remote || ({})
    readonly property var channels: page.st.channels || ({})
    readonly property var telegram: page.channels.telegram || ({})
    readonly property var phone: page.st.phone || ({})
    readonly property var echo: mira.echo || ({})
    readonly property bool wide: page.contentWidth > 820
    readonly property bool rtl: mira.lang === "ar"
    readonly property string busyVerb: page.st.remote_busy || ""
    readonly property bool remoteLive: !!page.remote.known && !!page.remote.active
    readonly property bool phoneInstalled: !!(page.phone.system || page.phone.local)
    readonly property bool chReading: !page.channels.known && !page.channels.error

    // A stored note is a word key (re-worded on a language switch).
    function w(key) { return key ? (mira.s[key] || "") : "" }
    function toneColor(tone) {
        return tone === "ok" ? Theme.ok : tone === "error" ? Theme.danger
             : tone === "pending" || tone === "warn" ? Theme.amber : Theme.ink2
    }
    function toneIcon(tone) { return tone === "ok" ? "check" : tone === "error" ? "alert" : tone === "pending" ? "clock" : "sparkle" }

    readonly property string phonePath: "M8.5 2.5h7a2 2 0 0 1 2 2v15a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-15a2 2 0 0 1 2-2z M10.5 18.5h3"
    readonly property string planePath: "M20.5 3.8L3.2 10.6c-.9.4-.9 1.3.1 1.6l4.4 1.4 1.7 5.3c.2.7.8.8 1.3.4l2.5-2.1 4.6 3.4c.8.6 1.6.3 1.8-.7l2.9-14.2c.3-1.1-.4-1.6-1.9-1.9z M8 13.4l9.6-6.1-7.4 7.2"
    readonly property string bubblePath: "M12 3.5a8.5 8.5 0 0 0-7.3 12.9L3.5 20.5l4.2-1.1A8.5 8.5 0 1 0 12 3.5z M9.3 8.2c-.4 0-.9.4-.9 1.2 0 2.3 2.9 5.4 5.5 5.9.9.2 1.5-.4 1.6-.9l.1-.5-1.9-.9-.8.8c-.9-.4-2-1.4-2.4-2.4l.7-.8-.8-1.9z"

    // ── small parts of this page ─────────────────────────────────────
    // a drawing of this page's own on Mira's 24×24 grid (an Icon: clipped correctly on both scene graphs)
    component Glyph: Icon {
        size: 20
    }

    // A live service behind Mo PC Remote: a dot, its plain name, and its state in words for a
    // screen reader and on hover (the colour alone is not the state).
    component ServiceChip: Rectangle {
        id: chip
        property string label: ""
        property bool lit: false
        property bool known: true
        readonly property string stateWord: !chip.known ? mira.s.cn_unknown : chip.lit ? mira.s.cn_on : mira.s.cn_off
        implicitHeight: 26
        implicitWidth: chipRow.implicitWidth + 20
        radius: 13
        color: Qt.rgba(1, 1, 1, 0.05)
        border.width: 1; border.color: Theme.hairline
        Accessible.role: Accessible.StaticText
        Accessible.name: chip.label + " · " + chip.stateWord
        HoverHandler { id: chipHover }
        ToolTip.visible: chipHover.hovered
        ToolTip.delay: 350
        ToolTip.text: chip.label + " · " + chip.stateWord
        Row {
            id: chipRow
            anchors.centerIn: parent
            spacing: 6
            Rectangle {
                width: 7; height: 7; radius: 3.5
                anchors.verticalCenter: parent.verticalCenter
                color: !chip.known ? Theme.off : chip.lit ? Theme.ok : Theme.danger
            }
            T { text: chip.label; font.pixelSize: Theme.tiny + 1; color: Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
        }
    }

    // A percentage the Echo reports ("—" until it has reported). A level fills its bar; a threshold
    // (`marker`) is a point on the track, with a caption saying which way is easier.
    component Meter: ColumnLayout {
        id: meter
        property string label: ""
        property string caption: ""
        property var value: null
        property bool marker: false
        property color accent: Theme.rose
        readonly property bool has: value !== null && value !== undefined
        readonly property real frac: has ? Math.max(0, Math.min(100, value)) / 100 : 0
        spacing: 7
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            T { text: meter.label; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true }
            T { text: meter.has ? meter.value + "%" : "—"; font.pixelSize: Theme.small; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
        }
        Item {
            Layout.fillWidth: true
            implicitHeight: 10
            Rectangle {
                id: track
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                height: 6; radius: 3
                color: meter.marker ? "transparent" : Qt.rgba(1, 1, 1, 0.08)
                gradient: meter.marker ? thresholdTrack : null
                Gradient {   // a threshold: faint where it wakes easily, fainter where it is strict
                    id: thresholdTrack
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(meter.accent.r, meter.accent.g, meter.accent.b, page.rtl ? 0.08 : 0.30) }
                    GradientStop { position: 1; color: Qt.rgba(meter.accent.r, meter.accent.g, meter.accent.b, page.rtl ? 0.30 : 0.08) }
                }
                Rectangle {   // a level: the filled part
                    visible: !meter.marker
                    height: parent.height; radius: 3
                    width: parent.width * meter.frac
                    x: page.rtl ? parent.width - width : 0
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: Qt.rgba(meter.accent.r, meter.accent.g, meter.accent.b, page.rtl ? 1 : 0.5) }
                        GradientStop { position: 1; color: Qt.rgba(meter.accent.r, meter.accent.g, meter.accent.b, page.rtl ? 0.5 : 1) }
                    }
                    Behavior on width { NumberAnimation { duration: Theme.normal } }
                }
            }
            Rectangle {   // a threshold: where the line sits
                visible: meter.marker && meter.has
                width: 12; height: 12; radius: 6
                anchors.verticalCenter: parent.verticalCenter
                x: (page.rtl ? (1 - meter.frac) : meter.frac) * (parent.width - width)
                color: meter.accent
                border.width: 2; border.color: Theme.bg2
                Behavior on x { NumberAnimation { duration: Theme.normal } }
            }
        }
        T { visible: meter.caption !== ""; text: meter.caption; font.pixelSize: Theme.tiny; color: Theme.ink3; Layout.fillWidth: true }
    }

    // One message channel: its glyph, its read-back state, what it means, and the one thing to do next.
    component ChannelRow: RowLayout {
        id: channel
        property string glyph: ""
        property color tint: Theme.cyan
        property string name: ""
        property string stateText: ""
        property string tone: "off"
        property string detail: ""
        property string action: ""
        property string actionIcon: "settings"
        property bool primaryAction: false
        property bool actionEnabled: true
        signal act()
        spacing: 12
        Rectangle {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 40; Layout.preferredHeight: 40
            radius: 12
            color: Qt.rgba(channel.tint.r, channel.tint.g, channel.tint.b, 0.15)
            Glyph { anchors.centerIn: parent; path: channel.glyph; size: 20; color: channel.tint }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Flow {
                Layout.fillWidth: true
                spacing: 8
                T { id: channelName; text: channel.name; font.pixelSize: Theme.body; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                Item {
                    width: channelPill.implicitWidth; height: Math.max(channelName.height, channelPill.implicitHeight)
                    StatusPill { id: channelPill; anchors.verticalCenter: parent.verticalCenter; text: channel.stateText; tone: channel.tone }
                }
            }
            T { Layout.fillWidth: true; visible: text !== ""; text: channel.detail; font.pixelSize: Theme.small; color: Theme.ink3 }
            PillButton {
                visible: channel.action !== ""
                Layout.topMargin: 2
                text: channel.action; iconName: channel.actionIcon; primary: channel.primaryAction
                enabled: channel.actionEnabled
                size: Theme.small; implicitHeight: 32
                onClicked: channel.act()
            }
        }
    }

    // A card whose glyph is drawn from a path (for the things Mira's icon set does not have yet).
    component PathCard: Glass {
        id: pcard
        property string glyph: ""
        property string title: ""
        property string subtitle: ""
        property color accent: Theme.cyan
        default property alias content: pbody.data
        property alias trailing: ptrail.data
        Layout.fillWidth: true
        Layout.preferredHeight: pcol.implicitHeight + 32
        implicitHeight: pcol.implicitHeight + 32
        radius: 20
        ColumnLayout {
            id: pcol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Glyph { path: pcard.glyph; size: 18; color: pcard.accent }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    T { text: pcard.title; font.pixelSize: Theme.body; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight }
                    T { visible: pcard.subtitle !== ""; text: pcard.subtitle; font.pixelSize: Theme.small; color: Theme.ink3; Layout.fillWidth: true }
                }
                Row { id: ptrail; spacing: 8 }
            }
            ColumnLayout { id: pbody; Layout.fillWidth: true; spacing: 10 }
        }
    }

    // Start, or Stop (an owner card; on an image without that card, a second click within 5 s).
    component RemotePrimary: PillButton {
        readonly property bool stopping: !!page.remote.active
        text: stopping ? (page.st.stop_armed ? mira.s.cn_stop_confirm : mira.s.cn_stop) : mira.s.cn_start
        iconName: stopping ? "stop" : "play"
        primary: !stopping
        danger: stopping
        enabled: page.busyVerb === ""
        onClicked: stopping ? mira.connectPage.stopRemote() : mira.connectPage.startRemote()
    }

    // A one-line result: tone glyph + words (+ a word saying why), and an optional small action.
    component Note: RowLayout {
        id: note
        property string text: ""
        property string tone: ""
        property string icon: ""
        property string action: ""
        signal act()
        visible: text !== ""
        spacing: 8
        Icon { Layout.alignment: Qt.AlignTop; Layout.topMargin: 1; name: note.icon || page.toneIcon(note.tone); size: 15; weight: 2; color: page.toneColor(note.tone) }
        T { Layout.fillWidth: true; text: note.text; font.pixelSize: Theme.small; color: note.tone === "" ? Theme.ink2 : page.toneColor(note.tone) }
        PillButton {
            visible: note.action !== ""
            Layout.alignment: Qt.AlignVCenter
            text: note.action; iconName: "x"; size: Theme.tiny + 1; implicitHeight: 28
            onClicked: note.act()
        }
    }

    actions: IconButton {
        iconName: "refresh"; tip: mira.s.refresh; diameter: 36
        enabled: !page.busy
        onClicked: mira.connectPage.refresh()
    }

    // while the page is on screen: notes age, the remote's live state, and an install being followed
    Timer { interval: 6000; running: true; repeat: true; onTriggered: mira.connectPage.poll() }

    // ── Mo PC Remote ─────────────────────────────────────────────────
    Glass {
        id: hero
        Layout.fillWidth: true
        Layout.preferredHeight: heroCol.implicitHeight + 36
        radius: 22
        readonly property bool compact: hero.width < 600
        edge: page.remoteLive ? Qt.rgba(0.21, 0.85, 0.96, 0.42) : Theme.hairlineStrong
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.rgba(0.08, 0.42, 0.62, page.remoteLive ? 0.32 : 0.16) }
            GradientStop { position: 1; color: Qt.rgba(0.36, 0.26, 0.85, page.remoteLive ? 0.26 : 0.16) }
        }
        ColumnLayout {
            id: heroCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 18 }
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                spacing: 16
                Rectangle {
                    visible: !hero.compact
                    Layout.alignment: Qt.AlignTop
                    Layout.preferredWidth: 62; Layout.preferredHeight: 62
                    radius: 20
                    color: Qt.rgba(1, 1, 1, 0.08)
                    border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.16)
                    Icon { anchors.centerIn: parent; anchors.verticalCenterOffset: -2; name: "monitor"; size: 32; color: page.remoteLive ? Theme.cyan : Theme.ink2 }
                    Rectangle {   // the phone that drives it
                        width: 22; height: 26; radius: 7
                        anchors { right: parent.right; bottom: parent.bottom; rightMargin: -4; bottomMargin: -4 }
                        color: Theme.bg2
                        border.width: 1; border.color: page.remoteLive ? Qt.rgba(0.21, 0.85, 0.96, 0.6) : Theme.hairlineStrong
                        Glyph { anchors.centerIn: parent; path: page.phonePath; size: 16; color: page.remoteLive ? Theme.cyan : Theme.ink3 }
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5
                    Flow {
                        Layout.fillWidth: true
                        spacing: 10
                        T { id: heroTitle; text: "Mo PC Remote"; font.pixelSize: hero.compact ? Theme.title + 1 : Theme.heading; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                        Item {   // the pill centred on the title's line
                            width: statePill.implicitWidth; height: heroTitle.height
                            StatusPill {
                                id: statePill
                                anchors.verticalCenter: parent.verticalCenter
                                text: !page.remote.known ? (page.st.remote_error ? mira.s.cn_unknown : mira.s.cn_reading)
                                      : page.remote.active ? mira.s.cn_running : mira.s.cn_stopped
                                tone: !page.remote.known ? (page.st.remote_error ? "warn" : "info") : page.remote.active ? "ok" : "off"
                                icon: page.remoteLive ? "check" : ""
                            }
                        }
                    }
                    T { Layout.fillWidth: true; text: mira.s.cn_remote_sub; font.pixelSize: Theme.small; color: Theme.ink2 }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 3
                        spacing: 6
                        ServiceChip { label: mira.s.cn_screen; lit: !!page.remote.pipewire; known: !!page.remote.known }
                        ServiceChip { label: mira.s.cn_permission; lit: !!page.remote.portal; known: !!page.remote.known }
                        StatusPill { visible: !!page.remote.fast; text: mira.s.cn_fast_state; tone: "warn"; icon: "bolt"; height: 26 }
                    }
                }
                RemotePrimary {
                    objectName: "cnPrimary"
                    Layout.alignment: Qt.AlignTop
                    visible: !!page.remote.known && !hero.compact
                }
            }

            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }

            Flow {
                Layout.fillWidth: true
                spacing: 8
                RemotePrimary { objectName: "cnPrimaryCompact"; visible: !!page.remote.known && hero.compact; size: Theme.small; implicitHeight: 34 }
                PillButton {
                    objectName: "cnRestart"
                    visible: page.remoteLive
                    text: mira.s.cn_restart; iconName: "refresh"; size: Theme.small; implicitHeight: 34
                    enabled: page.busyVerb === ""
                    onClicked: mira.connectPage.restartRemote()
                }
                PillButton {   // "off" whenever it is on (a local file says so); "on" only for a running remote
                    objectName: "cnFast"
                    visible: !!page.remote.fast || page.remoteLive
                    text: page.remote.fast ? mira.s.cn_fast_off : mira.s.cn_fast_on
                    iconName: "bolt"; size: Theme.small; implicitHeight: 34
                    enabled: page.busyVerb === ""
                    onClicked: mira.connectPage.setFastRemote(!page.remote.fast)
                    ToolTip.visible: hovered && !page.remote.fast; ToolTip.delay: 450; ToolTip.text: mira.s.cn_fast_hint
                }
                PillButton {
                    text: mira.s.cn_open_remote; iconName: "external"; size: Theme.small; implicitHeight: 34
                    onClicked: mira.connectPage.openRemoteApp()
                }
                PillButton {
                    text: mira.s.cn_remote_settings; iconName: "settings"; size: Theme.small; implicitHeight: 34
                    onClicked: mira.connectPage.openRemoteSettings()
                }
                PillButton {
                    objectName: "cnAnywhere"
                    text: mira.s.cn_anywhere; iconName: "globe"; size: Theme.small; implicitHeight: 34
                    enabled: page.st.anywhere_tone !== "pending"
                    onClicked: mira.connectPage.remoteAnywhere()
                    ToolTip.visible: hovered; ToolTip.delay: 450; ToolTip.text: mira.s.cn_anywhere_detail
                }
            }

            Note { Layout.fillWidth: true; visible: !!page.st.stop_armed; text: mira.s.cn_stop_warning; tone: "pending"; icon: "alert" }
            Note {
                objectName: "cnRemoteNote"
                Layout.fillWidth: true
                visible: !page.st.stop_armed && text !== ""
                text: page.w(page.st.remote_note) + (page.st.remote_note && page.st.remote_reason ? " · " + page.w(page.st.remote_reason) : "")
                tone: page.st.remote_tone || ""
                action: page.st.remote_phase === "card" || page.st.remote_phase === "dialog" ? mira.s.cn_stop_waiting : ""
                onAct: mira.connectPage.stopWaiting()
            }
            Note { Layout.fillWidth: true; text: page.w(page.st.remote_error); tone: "error" }
            Note { Layout.fillWidth: true; text: page.remote.fast ? mira.s.cn_fast_now : ""; tone: "warn"; icon: "bolt" }
            Note {   // named, so it never reads like a second copy of the remote's own note
                objectName: "cnAnywhereNote"
                Layout.fillWidth: true
                text: page.st.anywhere_note ? mira.s.cn_anywhere + " · " + page.w(page.st.anywhere_note) : ""
                tone: page.st.anywhere_tone || ""
                icon: page.st.anywhere_tone === "ok" ? "globe" : ""
            }
        }
    }

    // ── the phone, Mira's companion and the room ─────────────────────
    // Two columns side by side when there is room (the first on the reading side), one below the
    // other when narrow. Placed by hand: each column's width is fixed, its height is its own.
    Item {
        id: grid
        Layout.fillWidth: true
        readonly property int gap: 16
        readonly property real colWidth: page.wide ? Math.floor((width - gap) / 2) : width
        Layout.preferredHeight: page.wide ? Math.max(colA.implicitHeight, colB.implicitHeight)
                                          : colA.implicitHeight + gap + colB.implicitHeight
        implicitHeight: Layout.preferredHeight

        ColumnLayout {
            id: colA
            width: grid.colWidth
            x: page.wide && page.rtl ? grid.width - width : 0
            y: 0
            spacing: 16

            // Mira on the phone: the companion's own panels (read from mira.companion), unframed
            CompanionPanel { Layout.fillWidth: true }

            // the Echo in the room
            Card {
                icon: "echo"
                title: mira.s.cn_echo
                subtitle: mira.s.cn_echo_sub
                accent: Theme.rose
                trailing: StatusPill {
                    text: page.echo.online ? mira.s.cn_online : page.echo.paired === false ? mira.s.cn_unpaired : mira.s.cn_offline
                    tone: page.echo.online ? "ok" : "off"
                    icon: page.echo.online ? "check" : ""
                }
                GridLayout {
                    Layout.fillWidth: true
                    visible: page.echo.paired !== false
                    columns: 2
                    columnSpacing: 18
                    rowSpacing: 12
                    Meter { Layout.fillWidth: true; Layout.alignment: Qt.AlignTop; label: mira.s.cn_volume; value: page.echo.speaker_volume }
                    Meter {
                        Layout.fillWidth: true; Layout.alignment: Qt.AlignTop
                        label: mira.s.cn_wake_threshold; caption: mira.s.cn_wake_threshold_sub
                        value: page.echo.wake_threshold; marker: true; accent: Theme.violet
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: !!page.echo.online && !!page.echo.mute_available
                    spacing: 8
                    Icon { name: page.echo.muted ? "mic-off" : "mic"; size: 16; color: page.echo.muted ? Theme.amber : Theme.ok }
                    T { Layout.fillWidth: true; text: mira.s.cn_mics + " · " + (page.echo.muted ? mira.s.cn_muted : mira.s.cn_listening)
                        font.pixelSize: Theme.small; color: Theme.ink2 }
                }
                Rectangle {   // what to say, as the Echo reported it
                    Layout.fillWidth: true
                    visible: !!page.echo.wake_hint
                    implicitHeight: hint.implicitHeight + 18
                    radius: 12
                    color: Qt.rgba(Theme.rose.r, Theme.rose.g, Theme.rose.b, 0.08)
                    border.width: 1; border.color: Qt.rgba(Theme.rose.r, Theme.rose.g, Theme.rose.b, 0.25)
                    RowLayout {
                        id: hint
                        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                        spacing: 8
                        Icon { name: "wave"; size: 16; color: Theme.rose }
                        T { Layout.fillWidth: true; text: page.echo.wake_hint || ""; font.pixelSize: Theme.small; color: Theme.ink }
                    }
                }
                Note { Layout.fillWidth: true; text: page.echo.standalone === "synced" ? mira.s.cn_echo_alone : ""; tone: "ok" }
                T {
                    Layout.fillWidth: true
                    visible: !page.echo.online && text !== ""
                    text: page.echo.state || ""
                    font.pixelSize: Theme.small; color: Theme.ink3
                }
                PillButton {
                    text: mira.s.cn_echo_settings; iconName: "settings"; size: Theme.small; implicitHeight: 34
                    onClicked: mira.connectPage.openSettings()
                }
            }
        }

        ColumnLayout {
            id: colB
            width: grid.colWidth
            x: page.wide && !page.rtl ? grid.width - width : 0
            y: page.wide ? 0 : colA.implicitHeight + grid.gap
            spacing: 16

            // the phone link: the image's own app, the phones it knows and a ring for a lost one
            PathCard {
                glyph: page.phonePath
                title: mira.s.cn_phone
                subtitle: mira.s.cn_phone_sub
                accent: Theme.cyan
                trailing: StatusPill {
                    objectName: "cnPhonePill"
                    text: !page.phone.known ? (page.phone.error ? mira.s.cn_unknown : mira.s.cn_reading)
                          : page.phone.system ? mira.s.cn_phone_builtin : page.phone.local ? mira.s.cn_phone_local : mira.s.cn_phone_missing
                    tone: !page.phone.known ? (page.phone.error ? "warn" : "info") : page.phoneInstalled ? "ok" : "off"
                }
                Repeater {
                    model: page.phoneInstalled ? (page.phone.devices || []) : []
                    delegate: Rectangle {
                        id: device
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: 54
                        radius: 14
                        color: Qt.rgba(1, 1, 1, device.modelData.reachable ? 0.06 : 0.03)
                        border.width: 1
                        border.color: device.modelData.reachable ? Qt.rgba(0.21, 0.85, 0.96, 0.35) : Theme.hairline
                        RowLayout {
                            anchors { fill: parent; leftMargin: 12; rightMargin: 10 }
                            spacing: 10
                            Glyph { path: page.phonePath; size: 20; color: device.modelData.reachable ? Theme.cyan : Theme.ink3 }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1
                                T { Layout.fillWidth: true; text: device.modelData.name; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; wrapMode: Text.NoWrap; elide: Text.ElideRight
                                    horizontalAlignment: Text.AlignLeft }
                                T {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignLeft
                                    text: !device.modelData.paired ? mira.s.cn_phone_unpaired
                                          : device.modelData.reachable ? mira.s.cn_phone_paired + " · " + mira.s.cn_phone_reachable
                                          : mira.s.cn_phone_paired + " · " + mira.s.cn_phone_away
                                    font.pixelSize: Theme.tiny + 1
                                    color: device.modelData.reachable ? Theme.ok : Theme.ink3
                                    wrapMode: Text.NoWrap
                                }
                            }
                            PillButton {
                                visible: !!device.modelData.paired && !!device.modelData.reachable
                                text: mira.s.cn_ring; iconName: "volume"; size: Theme.small; implicitHeight: 32
                                enabled: !page.st.ringing
                                onClicked: mira.connectPage.ringPhone(device.modelData.id)
                            }
                        }
                    }
                }
                T {
                    Layout.fillWidth: true
                    visible: page.phoneInstalled && !!page.phone.listed && (page.phone.devices || []).length === 0
                    text: mira.s.cn_phone_none
                    font.pixelSize: Theme.small; color: Theme.ink3
                }
                T {
                    Layout.fillWidth: true
                    visible: !!page.phone.system && !!page.phone.known && !page.phone.running
                    text: mira.s.cn_phone_daemon_off
                    font.pixelSize: Theme.small; color: Theme.amber
                }
                T {
                    Layout.fillWidth: true
                    visible: page.phoneInstalled && !!page.phone.known && !page.phone.listed && (!page.phone.system || !!page.phone.running)
                    text: mira.s.cn_phone_devices_unknown
                    font.pixelSize: Theme.small; color: Theme.ink3
                }
                T {
                    Layout.fillWidth: true
                    visible: !page.phoneInstalled && !!page.phone.known
                    text: mira.s.cn_phone_missing_note
                    font.pixelSize: Theme.small; color: Theme.ink2
                }
                Note { Layout.fillWidth: true; text: page.w(page.phone.error); tone: "error" }
                Note {
                    Layout.fillWidth: true
                    text: page.st.phone_note ? page.w(page.st.phone_note) + (page.st.phone_about ? " " + page.st.phone_about : "") : ""
                    tone: page.st.phone_tone || ""
                }
                PillButton {
                    visible: page.phoneInstalled
                    text: mira.s.cn_open_phone; iconName: "external"; primary: true; size: Theme.small; implicitHeight: 34
                    onClicked: mira.connectPage.openPhoneApp()
                }
            }

            // message channels: Telegram from the agent's configuration, WhatsApp through the messaging agent
            Card {
                icon: "chat"
                title: mira.s.cn_channels
                subtitle: mira.s.cn_channels_sub
                accent: Theme.violet
                ChannelRow {
                    Layout.fillWidth: true
                    glyph: page.planePath
                    tint: "#4FB3F6"
                    name: mira.s.cn_telegram
                    stateText: !page.channels.known ? (page.channels.error ? mira.s.cn_unknown : mira.s.cn_reading)
                               : page.telegram.enabled && page.telegram.has_token ? mira.s.cn_on
                               : page.telegram.has_token ? mira.s.cn_off : mira.s.cn_not_set
                    tone: !page.channels.known ? (page.channels.error ? "warn" : "info")
                          : page.telegram.enabled && page.telegram.has_token ? "ok" : "off"
                    detail: !page.channels.known ? page.w(page.channels.error)
                            : !page.telegram.has_token ? mira.s.cn_tg_none
                            : (page.telegram.enabled ? "" : mira.s.cn_tg_token_saved + " · ")
                              + (page.telegram.policy === "allowlist" ? mira.s.cn_policy_allow.arg(page.telegram.allowed || 0) : mira.s.cn_policy_pairing)
                    action: mira.s.cn_setup
                    actionIcon: "settings"
                    primaryAction: !!page.channels.known && !page.telegram.has_token
                    onAct: mira.connectPage.setupChannels()
                }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }
                ChannelRow {   // nothing is claimed about the agent until the first read answers
                    objectName: "cnWhatsappRow"
                    Layout.fillWidth: true
                    glyph: page.bubblePath
                    tint: "#3DDC84"
                    name: mira.s.cn_whatsapp
                    stateText: page.chReading ? mira.s.cn_reading : page.channels.engine ? mira.s.cn_wa_link : mira.s.cn_agent_missing
                    tone: page.chReading || page.channels.engine ? "info" : "warn"
                    detail: page.chReading ? "" : page.channels.engine ? mira.s.cn_wa_hint : mira.s.cn_agent_missing_note
                    action: page.chReading ? "" : page.channels.engine ? mira.s.cn_wa_login : mira.s.cn_agent_setup
                    actionIcon: page.channels.engine ? "grid" : "download"
                    primaryAction: !page.chReading
                    actionEnabled: page.channels.engine || !page.st.agent_install
                    onAct: page.channels.engine ? mira.connectPage.whatsappLogin() : mira.connectPage.setupAgent()
                }
                Note { Layout.fillWidth: true; text: page.w(page.st.channel_note); tone: page.st.channel_tone || "" }
            }
        }
    }
}
