import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window

// This PC: the computer Mira runs on, as one page. Every value here is the machine's own read-back
// (mira.pcPage polls it every 5 s while this page is on screen); a control says "done" only when the
// read-back shows it, and a change the owner must approve becomes a card, never a silent action.
PageFrame {
    id: pcp
    icon: "monitor"
    title: mira.s.pcp_title
    subtitle: mira.s.pcp_sub
    accent: Theme.cyan
    busy: st.statusState === "loading" || st.hardwareState === "loading" || st.windowsState === "loading"

    readonly property var st: mira.pcPage ? mira.pcPage.state : ({})
    readonly property var status: st.status || ({})
    readonly property var busyMap: st.busy || ({})
    readonly property var awaiting: st.awaiting || ({})
    readonly property var notes: st.notes || ({})
    readonly property var outputs: st.outputs || ({})
    readonly property var running: st.running || ({})
    readonly property var hw: st.hardware || ({})
    readonly property var media: st.media || ({})
    readonly property bool wide: contentWidth >= 760
    readonly property bool statusKnown: st.statusState === "ok"
    property string journalPriority: "warning"
    property string journalSince: "boot"

    function known(v) { return v !== undefined && v !== null }
    function toggleOn(key) {
        if (!statusKnown) return null
        if (key === "mic") return known(status.mic_muted) ? !status.mic_muted : null
        return known(status[key]) ? status[key] : null
    }
    function themeFamily(theme) {
        if (!theme) return ""
        if (theme === "auto") return "auto"
        if (theme === "light" || theme === "daylight" || theme.indexOf("-light") > 0) return "light"
        return "dark"
    }
    function stateWord(key, on) {
        if (!!busyMap[key]) return mira.s.pcp_working
        if (awaiting[key] === "approval") return mira.s.pcp_waiting
        if (awaiting[key] === "settle") return mira.s.pcp_applying
        if (!statusKnown) return st.statusState === "error" ? mira.s.pcp_no_reading : mira.s.pcp_reading
        if (on === null) return mira.s.pcp_unknown
        if (key === "mic") return on ? mira.s.pcp_mic_live : mira.s.pcp_mic_muted
        return on ? mira.s.pcp_on : mira.s.pcp_off
    }
    function gb(v) { return (Math.round(v * 10) / 10) + " " + mira.s.pcp_gb }
    // a file size in the owner's language ("" for a folder or an unknown size)
    function size(bytes) {
        if (bytes === undefined || bytes === null || bytes < 0) return ""
        const units = [mira.s.pcp_b, mira.s.pcp_kb, mira.s.pcp_mb, mira.s.pcp_gb]
        let v = bytes, u = 0
        while (v >= 1024 && u < 3) { v = v / 1024; u++ }
        return (u === 0 || v >= 10 ? Math.round(v) : Math.round(v * 10) / 10) + " " + units[u]
    }
    // one run of mixed text (a path, a date, "48 KB") keeps its own order inside the other language
    function isolate(text) { return "\u2068" + text + "\u2069" }
    readonly property string offlineTitle: st.statusCode === "timeout" ? mira.s.pcp_offline_slow
                                         : st.statusCode === "missing" ? mira.s.pcp_offline_old
                                         : st.statusCode === "unreachable" ? mira.s.pcp_offline : mira.s.pcp_offline_other
    // what a control that reads get_system_status says while there is no reading
    readonly property string noReading: statusKnown ? mira.s.pcp_unknown : st.statusState === "error" ? mira.s.pcp_no_reading : mira.s.pcp_reading

    // poll only while the page is really on screen: the window hidden to the tray stops it too
    readonly property bool onScreen: Window.visibility !== Window.Hidden && Window.visibility !== Window.Minimized
    property bool wasHidden: false
    onOnScreenChanged: {
        if (!onScreen) { wasHidden = true; mira.pcPage.hidden() }
        else if (wasHidden) { wasHidden = false; mira.pcPage.resume() }
    }
    Component.onDestruction: mira.pcPage.hidden()

    actions: [
        StatusPill {
            visible: !!pcp.st.sample
            anchors.verticalCenter: parent.verticalCenter
            text: mira.s.pcp_sample; tone: "warn"; icon: "alert"
        },
        StatusPill {
            visible: (pcp.st.readAt || "") !== ""
            anchors.verticalCenter: parent.verticalCenter
            text: mira.s.pcp_read_at + " " + (pcp.st.readAt || "")
            tone: pcp.st.statusState === "error" ? "error" : "ok"
            icon: pcp.st.statusState === "error" ? "alert" : "pulse"
        },
        IconButton {
            anchors.verticalCenter: parent.verticalCenter
            iconName: "refresh"; tip: mira.s.pcp_refresh
            onClicked: mira.pcPage.refresh()
        }
    ]

    // ── the executor is not answering ──
    Glass {
        Layout.fillWidth: true
        visible: pcp.st.statusState === "error"
        Layout.preferredHeight: offline.implicitHeight + 28
        radius: 18
        tint: Qt.rgba(0.30, 0.07, 0.14, 0.55)
        edge: Qt.rgba(1, 0.36, 0.48, 0.45)
        RowLayout {
            id: offline
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
            spacing: 12
            Icon { name: "alert"; size: 22; color: Theme.danger }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                T { text: pcp.offlineTitle; font.weight: Font.DemiBold; Layout.fillWidth: true }
                T { text: [pcp.st.statusError || "", mira.s.pcp_offline_hint].filter(function(p) { return p !== "" }).join(" · ")
                    font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true }
            }
            PillButton { text: mira.s.pcp_refresh; iconName: "refresh"; size: Theme.small; onClicked: mira.pcPage.refreshStatus() }
        }
    }

    // ── sound and screen · now playing ──
    GridLayout {
        Layout.fillWidth: true
        columns: pcp.wide ? 2 : 1
        columnSpacing: 16; rowSpacing: 16

        Card {
            id: levelsCard
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            icon: "volume"; title: mira.s.pcp_levels; accent: Theme.cyan
            trailing: IconButton { iconName: "refresh"; diameter: 30; tip: mira.s.pcp_refresh; onClicked: mira.pcPage.refreshStatus() }
            LevelRow {
                icon: pcp.status.muted ? "volume-off" : "volume"
                leadButton: true
                leadActive: !!pcp.status.muted
                leadTip: pcp.status.muted ? mira.s.pcp_unmute : mira.s.pcp_mute
                leadEnabled: pcp.statusKnown && pcp.known(pcp.status.muted) && !pcp.busyMap.mute
                label: pcp.status.muted ? mira.s.pcp_muted : mira.s.pcp_volume
                readback: pcp.statusKnown ? pcp.status.volume : null
                wanted: (pcp.st.wanted || {}).volume
                working: !!pcp.busyMap.volume
                dim: !!pcp.status.muted
                accent: Theme.cyan
                settingsTip: mira.s.pcp_sound_settings
                onSettings: mira.pcPage.openSettings("audio")
                onLeadClicked: mira.pcPage.toggleMute()
                onCommit: function(value) { mira.pcPage.setVolume(value) }
            }
            LevelRow {
                icon: "sun"
                label: mira.s.pcp_brightness
                readback: pcp.statusKnown ? pcp.status.brightness : null
                wanted: (pcp.st.wanted || {}).brightness
                working: !!pcp.busyMap.brightness
                minimum: 5
                accent: Theme.amber
                settingsTip: mira.s.pcp_display_settings
                onSettings: mira.pcPage.openSettings("display")
                onCommit: function(value) { mira.pcPage.setBrightness(value) }
            }
            T {
                visible: pcp.statusKnown && !pcp.known(pcp.status.brightness)
                text: mira.s.pcp_no_brightness
                font.pixelSize: Theme.tiny + 1; color: Theme.ink3
                Layout.fillWidth: true
            }
            // the night light's MODE is KWin's own config (read back from kwinrc); "warm now" is KWin running it
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 2
                spacing: 10
                SegRow {
                    icon: "bulb"; label: mira.s.pcp_night_light; accent: Theme.amber
                    options: [{ key: "off", label: mira.s.pcp_off }, { key: "on", label: mira.s.pcp_night_on }, { key: "auto", label: mira.s.pcp_auto }]
                    current: (pcp.st.look || {}).night || ""
                    working: !!pcp.busyMap.night
                    waiting: pcp.awaiting.night || ""
                    extra: pcp.statusKnown && pcp.status.night_light === true ? mira.s.pcp_night_warm : ""
                    onPicked: function(key) { mira.pcPage.setNightLight(key) }
                }
                IconButton {
                    Layout.alignment: Qt.AlignBottom
                    Layout.bottomMargin: 4
                    iconName: "settings"; diameter: 30; tip: mira.s.pcp_night_settings
                    onClicked: mira.pcPage.openSettings("night-light")
                }
            }
            NoteLine { note: pcp.notes.levels || null }
        }

        Card {
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            icon: "play"; title: mira.s.pcp_media; accent: Theme.rose
            trailing: IconButton { iconName: "refresh"; diameter: 30; tip: mira.s.pcp_refresh; onClicked: mira.pcPage.refreshMedia() }

            // centred beside the taller levels card: reads only that card's height, so no binding loop
            Item {
                Layout.fillWidth: true
                implicitHeight: pcp.wide ? Math.max(mediaCol.implicitHeight, levelsCard.implicitHeight - 74) : mediaCol.implicitHeight
                ColumnLayout {
                    id: mediaCol
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                    spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        visible: pcp.st.mediaState === "ok"
                        spacing: 14
                        Rectangle {
                            Layout.preferredWidth: 62; Layout.preferredHeight: 62
                            radius: 18
                            gradient: Gradient {
                                GradientStop { position: 0; color: Qt.rgba(1.0, 0.44, 0.71, 0.55) }
                                GradientStop { position: 1; color: Qt.rgba(0.61, 0.48, 1.0, 0.45) }
                            }
                            border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18)
                            Icon { anchors.centerIn: parent; name: pcp.media.state === "Playing" ? "wave" : "pause"; size: 26; color: "white" }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            T { text: pcp.media.title || mira.s.pcp_untitled; font.pixelSize: Theme.title; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                            T { visible: (pcp.media.artist || "") !== ""; text: pcp.media.artist || ""; font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                            StatusPill {
                                text: (pcp.media.player || "") + " · " + (pcp.media.state === "Playing" ? mira.s.pcp_playing
                                      : pcp.media.state === "Paused" ? mira.s.pcp_paused : mira.s.pcp_stopped)
                                tone: pcp.media.state === "Playing" ? "ok" : "off"
                                icon: pcp.media.state === "Playing" ? "play" : "pause"
                            }
                        }
                    }
                    // transport controls keep their left-to-right order in both languages
                    Row {
                        Layout.alignment: Qt.AlignHCenter
                        visible: pcp.st.mediaState === "ok"
                        spacing: 14
                        LayoutMirroring.enabled: false
                        LayoutMirroring.childrenInherit: true
                        IconButton { iconName: "chevron"; rotation: 180; diameter: 40; tip: mira.s.pcp_previous; enabled: !pcp.busyMap.media; anchors.verticalCenter: parent.verticalCenter; onClicked: mira.pcPage.media("previous") }
                        IconButton {
                            iconName: pcp.media.state === "Playing" ? "pause" : "play"
                            diameter: 50; active: true; accent: Theme.rose
                            tip: pcp.media.state === "Playing" ? mira.s.pcp_pause : mira.s.pcp_play
                            enabled: !pcp.busyMap.media
                            onClicked: mira.pcPage.media(pcp.media.state === "Playing" ? "pause" : "play")
                        }
                        IconButton { iconName: "chevron"; diameter: 40; tip: mira.s.pcp_next; enabled: !pcp.busyMap.media; anchors.verticalCenter: parent.verticalCenter; onClicked: mira.pcPage.media("next") }
                    }
                    EmptyState {
                        visible: pcp.st.mediaState !== "ok"
                        icon: "volume-off"
                        text: pcp.st.mediaState === "error" ? (pcp.media.error || mira.s.pcp_no_media)
                              : pcp.st.mediaState === "idle" ? mira.s.pcp_reading : mira.s.pcp_no_media
                    }
                    NoteLine { note: pcp.notes.media || null }
                }
            }
        }
    }

    // ── quick controls ──
    Card {
        icon: "bolt"; title: mira.s.pcp_controls; accent: Theme.violet
        GridLayout {
            Layout.fillWidth: true
            columns: pcp.contentWidth > 820 ? 4 : pcp.contentWidth > 560 ? 3 : 2
            columnSpacing: 8; rowSpacing: 8
            Repeater {
                model: [
                    { key: "wifi", icon: "wifi", label: mira.s.pcp_wifi, accent: Theme.cyan },
                    { key: "bluetooth", icon: "bluetooth", label: mira.s.pcp_bluetooth, accent: "#5B8CFF" },
                    { key: "dnd", icon: "moon", label: mira.s.pcp_dnd, accent: Theme.violet },
                    { key: "mic", icon: "mic", label: mira.s.pcp_mic, accent: Theme.mint } ]
                delegate: PcTile {
                    required property var modelData
                    readonly property var isOn: pcp.toggleOn(modelData.key)
                    Layout.preferredWidth: 1
                    glyph: modelData.key === "mic" && isOn === false ? "mic-off" : modelData.icon
                    title: modelData.label
                    subtitle: pcp.stateWord(modelData.key, isOn)
                    accent: modelData.accent
                    lit: isOn === true
                    busy: !!pcp.busyMap[modelData.key]
                    enabled: isOn !== null
                    onClicked: mira.pcPage.setToggle(modelData.key, !isOn)
                }
            }
            PcTile {
                Layout.preferredWidth: 1
                glyph: "keyboard"; title: mira.s.pcp_keyboard
                subtitle: pcp.busyMap.keyboard ? mira.s.pcp_working : (pcp.st.layout || mira.s.pcp_keyboard_next)
                accent: Theme.cyan
                busy: !!pcp.busyMap.keyboard
                onClicked: mira.pcPage.nextKeyboardLayout()
            }
            PcTile {
                Layout.preferredWidth: 1
                glyph: "monitor"; title: mira.s.pcp_screenshot
                subtitle: pcp.busyMap.screenshot ? mira.s.pcp_working : mira.s.pcp_screenshot_sub
                accent: Theme.rose
                busy: !!pcp.busyMap.screenshot
                onClicked: mira.pcPage.screenshot()
            }
            PcTile {
                Layout.preferredWidth: 1
                glyph: "globe"; title: mira.s.pcp_networks
                subtitle: pcp.busyMap["settings:network"] ? mira.s.pcp_working : mira.s.pcp_networks_sub
                accent: Theme.cyan
                busy: !!pcp.busyMap["settings:network"]
                onClicked: mira.pcPage.openSettings("network")
            }
            PcTile {
                Layout.preferredWidth: 1
                glyph: "settings"; title: mira.s.pcp_settings
                subtitle: pcp.busyMap["settings:overview"] ? mira.s.pcp_working : mira.s.pcp_settings_sub
                accent: Theme.ink2
                busy: !!pcp.busyMap["settings:overview"]
                onClicked: mira.pcPage.openSettings("overview")
            }
        }
        GridLayout {
            Layout.fillWidth: true
            Layout.topMargin: 4
            columns: pcp.wide ? 2 : 1
            columnSpacing: 18; rowSpacing: 12
            SegRow {
                Layout.preferredWidth: 1
                icon: "palette"; label: mira.s.pcp_theme; accent: Theme.violet
                options: [{ key: "dark", label: mira.s.pcp_dark }, { key: "light", label: mira.s.pcp_light }, { key: "auto", label: mira.s.pcp_auto }]
                current: pcp.statusKnown ? pcp.themeFamily(pcp.status.theme) : ""
                available: pcp.statusKnown
                offText: pcp.noReading
                working: !!pcp.busyMap.theme
                waiting: pcp.awaiting.theme || ""
                onPicked: function(key) { mira.pcPage.setTheme(key) }
            }
            SegRow {
                Layout.preferredWidth: 1
                icon: "bolt"; label: mira.s.pcp_power; accent: Theme.amber
                options: [{ key: "power-saver", label: mira.s.pcp_saver }, { key: "balanced", label: mira.s.pcp_balanced }, { key: "performance", label: mira.s.pcp_performance }]
                current: pcp.statusKnown ? (pcp.status.power_profile || "") : ""
                available: pcp.statusKnown && pcp.known(pcp.status.power_profile)
                offText: pcp.noReading
                working: !!pcp.busyMap.power
                waiting: pcp.awaiting.power || ""
                onPicked: function(key) { mira.pcPage.setPowerProfile(key) }
            }
            SegRow {
                Layout.preferredWidth: 1
                icon: "wave"; label: mira.s.pcp_motion; accent: Theme.cyan
                options: [{ key: "still", label: mira.s.pcp_still }, { key: "gentle", label: mira.s.pcp_gentle }, { key: "alive", label: mira.s.pcp_alive }]
                current: (pcp.st.look || {}).motion || ""
                working: !!pcp.busyMap.motion
                waiting: pcp.awaiting.motion || ""
                onPicked: function(key) { mira.pcPage.setMotion(key) }
            }
            SegRow {
                Layout.preferredWidth: 1
                icon: "sparkle"; label: mira.s.pcp_clarity; accent: Theme.mint
                options: [{ key: "clear", label: mira.s.pcp_clear }, { key: "balanced", label: mira.s.pcp_balanced }, { key: "solid", label: mira.s.pcp_solid }]
                current: (pcp.st.look || {}).clarity || ""
                working: !!pcp.busyMap.clarity
                waiting: pcp.awaiting.clarity || ""
                onPicked: function(key) { mira.pcPage.setClarity(key) }
            }
        }
        NoteLine { note: pcp.notes.controls || null }
    }

    // ── windows and desktops ──
    Card {
        icon: "grid"; title: mira.s.pcp_windows; accent: Theme.cyan
        trailing: IconButton { iconName: "settings"; diameter: 30; tip: mira.s.pcp_window_settings; onClicked: mira.pcPage.openSettings("window-behavior") }
        GridLayout {
            Layout.fillWidth: true
            columns: pcp.wide ? 3 : 1
            columnSpacing: 18; rowSpacing: 12
            ButtonGroupBox {
                Layout.preferredWidth: 3
                label: mira.s.pcp_view
                model: [{ key: "view:overview", arg: "overview", label: mira.s.pcp_overview, icon: "grid" },
                        { key: "view:grid", arg: "grid", label: mira.s.pcp_grid, icon: "apps" },
                        { key: "view:show-desktop", arg: "show-desktop", label: mira.s.pcp_show_desktop, icon: "monitor" }]
                busyKeys: pcp.busyMap
                onPicked: function(arg) { mira.pcPage.showWindows(arg) }
            }
            ButtonGroupBox {
                Layout.preferredWidth: 2
                label: mira.s.pcp_arrange
                model: [{ key: "arrange:halves", arg: "halves", label: mira.s.pcp_halves, icon: "" },
                        { key: "arrange:thirds", arg: "thirds", label: mira.s.pcp_thirds, icon: "" },
                        { key: "arrange:quarters", arg: "quarters", label: mira.s.pcp_quarters, icon: "" }]
                busyKeys: pcp.busyMap
                onPicked: function(arg) { mira.pcPage.arrange(arg) }
            }
            ButtonGroupBox {
                Layout.preferredWidth: 2
                label: mira.s.pcp_desktops
                model: [{ key: "desktop:previous", arg: "previous", label: mira.s.pcp_desktop_prev, icon: "" },
                        { key: "desktop:next", arg: "next", label: mira.s.pcp_desktop_next, icon: "" }]
                busyKeys: pcp.busyMap
                onPicked: function(arg) { mira.pcPage.switchDesktop(arg) }
            }
        }
        NoteLine { note: pcp.notes.windows || null }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.hairline }
        RowLayout {
            Layout.fillWidth: true
            SectionTitle {
                icon: "apps"; accent: Theme.cyan
                text: mira.s.pcp_open_windows + ((pcp.st.windows || []).length > 0 ? " · " + (pcp.st.windows || []).length : "")
            }
            Item { Layout.fillWidth: true }
            IconButton { iconName: "refresh"; diameter: 30; tip: mira.s.pcp_refresh; onClicked: mira.pcPage.refreshWindows() }
        }
        EmptyState {
            visible: (pcp.st.windows || []).length === 0
            icon: pcp.st.windowsState === "error" ? "alert" : "grid"
            tone: pcp.st.windowsState === "error" ? "error" : ""
            text: pcp.st.windowsState === "error" ? (pcp.st.windowsError || "")
                  : pcp.st.windowsState === "ok" ? mira.s.pcp_no_windows : mira.s.pcp_reading
        }
        Repeater {
            model: pcp.st.windows || []
            delegate: Rectangle {
                id: winRow
                required property var modelData
                readonly property string appName: (modelData.app || "").split(".").pop()
                // a title another row shares cannot be told apart until desktop_tools acts by window id
                readonly property bool limited: !modelData.canFocus || !modelData.canClose
                Layout.fillWidth: true
                implicitHeight: 58
                radius: 14
                color: winRow.modelData.active ? Qt.rgba(0.21, 0.85, 0.96, 0.08) : Qt.rgba(1, 1, 1, 0.035)
                border.width: 1
                border.color: winRow.modelData.active ? Qt.rgba(0.21, 0.85, 0.96, 0.35) : Theme.hairline
                RowLayout {
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                    spacing: 12
                    Rectangle {
                        Layout.preferredWidth: 36; Layout.preferredHeight: 36
                        radius: 11
                        gradient: Gradient {
                            GradientStop { position: 0; color: Qt.rgba(0.42, 0.33, 0.94, 0.50) }
                            GradientStop { position: 1; color: Qt.rgba(0.17, 0.78, 0.90, 0.40) }
                        }
                        T { anchors.centerIn: parent; text: (winRow.appName || winRow.modelData.title || "?").charAt(0).toUpperCase(); font.pixelSize: 16; font.weight: Font.Bold; color: "white" }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        T { text: winRow.modelData.title; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                        T {
                            text: pcp.isolate(winRow.appName) + (winRow.modelData.active ? " · " + mira.s.pcp_active : "")
                                  + (winRow.modelData.minimized ? " · " + mira.s.pcp_minimized : "")
                                  + (winRow.limited ? " · " + mira.s.pcp_same_title : "")
                            font.pixelSize: Theme.tiny + 1
                            color: winRow.limited ? Theme.amber : winRow.modelData.active ? Theme.cyan : Theme.ink3
                            Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight
                            horizontalAlignment: Text.AlignLeft
                        }
                    }
                    PillButton {
                        text: mira.s.pcp_focus; iconName: "external"; size: Theme.small; implicitHeight: 32
                        visible: !winRow.modelData.active || winRow.modelData.minimized
                        enabled: !!winRow.modelData.canFocus && !pcp.busyMap["focus:" + winRow.modelData.id]
                        onClicked: mira.pcPage.focusWindow(winRow.modelData.id, winRow.modelData.title)
                    }
                    PillButton {
                        text: mira.s.pcp_close; iconName: "x"; danger: true; size: Theme.small; implicitHeight: 32
                        enabled: !!winRow.modelData.canClose      // PillButton dims a disabled danger button itself
                        onClicked: mira.pcPage.closeWindow(winRow.modelData.id, winRow.modelData.title)
                    }
                }
            }
        }
    }

    // ── hardware ──
    Card {
        icon: "chip"; title: mira.s.pcp_hardware; accent: Theme.mint
        trailing: [
            StatusPill { visible: (pcp.hw.version || "") !== ""; text: "MoOS " + (pcp.hw.version || ""); tone: "info"; icon: "shield"; anchors.verticalCenter: parent.verticalCenter },
            IconButton { iconName: "external"; diameter: 30; tip: mira.s.pcp_about; onClicked: mira.pcPage.openSettings("about") }
        ]
        GridLayout {
            Layout.fillWidth: true
            visible: pcp.st.hardwareState === "ok"
            columns: pcp.wide ? 4 : 2
            columnSpacing: 10; rowSpacing: 10
            Spec {
                Layout.columnSpan: 2
                icon: "chip"; label: mira.s.pcp_cpu; accent: Theme.mint
                value: pcp.hw.cpu || "—"
                sub: pcp.hw.arch || ""
            }
            Spec {
                Layout.columnSpan: 2
                icon: "grid"; label: mira.s.pcp_gpu; accent: Theme.violet
                value: pcp.hw.gpu || "—"
                sub: (mira.lang === "en" ? pcp.hw.driver_en : pcp.hw.driver_ar) || ""
            }
            Spec {
                icon: "memory"; label: mira.s.pcp_memory; accent: Theme.cyan
                value: pcp.known(pcp.hw.memory_gb) ? pcp.gb(pcp.hw.memory_gb) : "—"
            }
            Spec {
                icon: "bolt"; label: mira.s.pcp_cores; accent: Theme.amber
                value: pcp.known(pcp.hw.cores) ? String(pcp.hw.cores) : "—"
            }
            Spec {
                icon: "disk"; label: mira.s.pcp_disk; accent: Theme.rose
                value: pcp.known(pcp.hw.disk_free_gb) && pcp.known(pcp.hw.disk_total_gb)
                       ? pcp.gb(pcp.hw.disk_free_gb) + " " + mira.s.pcp_free_of + " " + pcp.gb(pcp.hw.disk_total_gb) : "—"
                fraction: pcp.known(pcp.hw.disk_free_gb) && pcp.hw.disk_total_gb > 0 ? 1 - pcp.hw.disk_free_gb / pcp.hw.disk_total_gb : -1
            }
            Spec {
                icon: "settings"; label: mira.s.pcp_kernel; accent: Theme.ink2
                value: pcp.hw.kernel || "—"
            }
        }
        EmptyState {
            visible: pcp.st.hardwareState !== "ok"
            icon: pcp.st.hardwareState === "error" ? "alert" : "chip"
            tone: pcp.st.hardwareState === "error" ? "error" : ""
            text: pcp.st.hardwareState === "error" ? mira.s.pcp_no_hardware : mira.s.pcp_reading
        }
        NoteLine { note: pcp.notes.hardware || null }
    }

    // ── checks and logs (read only) ──
    Card {
        icon: "pulse"; title: mira.s.pcp_diag; subtitle: mira.s.pcp_diag_sub; accent: Theme.amber
        GridLayout {
            Layout.fillWidth: true
            columns: pcp.contentWidth > 560 ? 3 : 2
            columnSpacing: 8; rowSpacing: 8
            Repeater {
                model: [
                    { key: "top_processes:cpu", icon: "chip", label: mira.s.pcp_proc_cpu },
                    { key: "top_processes:memory", icon: "memory", label: mira.s.pcp_proc_mem },
                    { key: "memory_status", icon: "pulse", label: mira.s.pcp_mem },
                    { key: "disk_status", icon: "disk", label: mira.s.pcp_disks },
                    { key: "network_status", icon: "wifi", label: mira.s.pcp_net },
                    { key: "list_failed_units", icon: "alert", label: mira.s.pcp_failed } ]
                delegate: PcTile {
                    required property var modelData
                    Layout.preferredWidth: 1
                    implicitHeight: 60
                    glyph: modelData.icon; title: modelData.label
                    accent: Theme.amber
                    busy: pcp.running.checks === modelData.key
                    lit: !busy && (pcp.outputs.checks || {}).tool === modelData.key
                    enabled: !pcp.running.checks || busy
                    onClicked: mira.pcPage.runCheck(modelData.key)
                }
            }
        }
        Output { slot: "checks" }

        Rectangle { Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 1; color: Theme.hairline }
        SectionTitle { icon: "settings"; text: mira.s.pcp_unit; accent: Theme.amber }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            MiraField {
                id: unitField
                Layout.fillWidth: true
                placeholderText: mira.s.pcp_unit_hint
                onAccepted: if (text.trim() !== "") mira.pcPage.unitStatus(text, unitUser.checked)
            }
            MiraSwitch { id: unitUser; text: mira.s.pcp_unit_user; accent: Theme.amber }
            PillButton {
                text: mira.s.pcp_show; primary: true; size: Theme.small
                enabled: unitField.text.trim() !== "" && !pcp.running.unit
                onClicked: mira.pcPage.unitStatus(unitField.text, unitUser.checked)
            }
        }
        Output { slot: "unit" }

        Rectangle { Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 1; color: Theme.hairline }
        SectionTitle { icon: "clock"; text: mira.s.pcp_journal; accent: Theme.amber }
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            MiraField { id: journalUnit; Layout.fillWidth: true; placeholderText: mira.s.pcp_journal_unit }
            MiraSwitch { id: journalUser; text: mira.s.pcp_unit_user; accent: Theme.amber; enabled: journalUnit.text.trim() !== "" }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: pcp.wide ? 3 : 1
            columnSpacing: 14; rowSpacing: 10
            SegRow {
                Layout.preferredWidth: 3
                label: mira.s.pcp_severity; accent: Theme.amber
                options: [{ key: "err", label: mira.s.pcp_prio_err }, { key: "warning", label: mira.s.pcp_prio_warning }, { key: "info", label: mira.s.pcp_prio_info }]
                current: pcp.journalPriority
                onPicked: function(key) { pcp.journalPriority = key }
            }
            SegRow {
                Layout.preferredWidth: 4
                label: mira.s.pcp_since; accent: Theme.amber
                options: [{ key: "boot", label: mira.s.pcp_since_boot }, { key: "1h", label: mira.s.pcp_since_1h },
                          { key: "24h", label: mira.s.pcp_since_24h }, { key: "7d", label: mira.s.pcp_since_7d }]
                current: pcp.journalSince
                onPicked: function(key) { pcp.journalSince = key }
            }
            PillButton {
                Layout.alignment: Qt.AlignBottom
                text: mira.s.pcp_read; primary: true; size: Theme.small
                enabled: !pcp.running.journal
                onClicked: mira.pcPage.readJournal(journalUnit.text, pcp.journalPriority, pcp.journalSince, journalUser.checked)
            }
        }
        Output { slot: "journal" }

        Rectangle { Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 1; color: Theme.hairline }
        SectionTitle { icon: "package"; text: mira.s.pcp_logs; accent: Theme.amber }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: [{ key: "moai", label: mira.s.pcp_log_moai, icon: "sparkle" }, { key: "theme", label: mira.s.pcp_log_theme, icon: "palette" },
                        { key: "store", label: mira.s.pcp_log_store, icon: "package" }, { key: "remote", label: mira.s.pcp_log_remote, icon: "globe" }]
                delegate: PillButton {
                    required property var modelData
                    text: modelData.label; iconName: modelData.icon; size: Theme.small; implicitHeight: 34
                    primary: (pcp.outputs.logs || {}).tool === "log:" + modelData.key
                    enabled: !pcp.running.logs
                    onClicked: mira.pcPage.readLog(modelData.key)
                }
            }
        }
        Output { slot: "logs" }
    }

    // ── files ──
    Card {
        icon: "copy"; title: mira.s.pcp_files; accent: Theme.violet
        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            MiraField {
                id: fileQuery
                Layout.fillWidth: true
                placeholderText: mira.s.pcp_files_hint
                onAccepted: if (text.trim() !== "") mira.pcPage.findFiles(text)
            }
            // a newer search may start while one runs: the page keeps only the latest answer
            PillButton {
                text: mira.s.pcp_search; primary: true; size: Theme.small
                enabled: fileQuery.text.trim() !== ""
                onClicked: mira.pcPage.findFiles(fileQuery.text)
            }
        }
        EmptyState {
            visible: (pcp.st.files || []).length === 0
            icon: pcp.st.filesState === "error" ? "alert" : "copy"
            tone: pcp.st.filesState === "error" ? "error" : ""
            text: pcp.st.filesState === "loading" ? mira.s.pcp_working
                  : pcp.st.filesState === "error" ? (pcp.st.filesError || "")
                  : pcp.st.filesState === "ok" ? mira.s.pcp_no_files : mira.s.pcp_files_empty
        }
        Repeater {
            model: pcp.st.files || []
            delegate: Rectangle {
                id: fileRow
                required property var modelData
                readonly property string ext: modelData.dir ? "" : (modelData.name.indexOf(".") > 0 ? modelData.name.split(".").pop().split(" ")[0].slice(0, 4).toUpperCase() : "")
                Layout.fillWidth: true
                implicitHeight: 58
                radius: 14
                color: Qt.rgba(1, 1, 1, 0.035)
                border.width: 1; border.color: Theme.hairline
                RowLayout {
                    anchors { fill: parent; leftMargin: 10; rightMargin: 10 }
                    spacing: 12
                    Rectangle {
                        Layout.preferredWidth: 36; Layout.preferredHeight: 36
                        radius: 11
                        color: Qt.rgba(0.61, 0.48, 1.0, fileRow.modelData.dir ? 0.22 : 0.14)
                        border.width: 1; border.color: Qt.rgba(0.61, 0.48, 1.0, 0.35)
                        Icon { visible: fileRow.modelData.dir || fileRow.ext === ""; anchors.centerIn: parent; name: fileRow.modelData.dir ? "grid" : "copy"; size: 17; color: Theme.violet }
                        T { visible: !fileRow.modelData.dir && fileRow.ext !== ""; anchors.centerIn: parent; text: fileRow.ext; font.pixelSize: 10; font.weight: Font.Bold; color: Theme.violet; wrapMode: Text.NoWrap }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        T { text: fileRow.modelData.name; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
                        T {
                            text: [fileRow.modelData.folder, fileRow.modelData.dir ? mira.s.pcp_folder : pcp.size(fileRow.modelData.bytes), fileRow.modelData.modified]
                                  .filter(function(p) { return !!p }).map(pcp.isolate).join(" · ")
                            font.pixelSize: Theme.tiny + 1; color: Theme.ink3
                            Layout.fillWidth: true; wrapMode: Text.NoWrap; elide: Text.ElideMiddle
                            horizontalAlignment: Text.AlignLeft
                        }
                    }
                    PillButton {
                        text: mira.s.pcp_open; iconName: "external"; size: Theme.small; implicitHeight: 32
                        enabled: !pcp.busyMap["open:" + fileRow.modelData.path]
                        onClicked: mira.pcPage.openFile(fileRow.modelData.path, false)
                    }
                    PillButton {
                        text: mira.s.pcp_open_folder; iconName: "grid"; size: Theme.small; implicitHeight: 32
                        onClicked: mira.pcPage.openFile(fileRow.modelData.path, true)
                    }
                }
            }
        }
        NoteLine { note: pcp.notes.files || null }
    }

    // ═════ the page's own small parts ═════

    // A clickable tile: glyph, title, one line of state (the shared Tile's look). Tab/Enter/Space reach
    // it; `busy` turns the glyph, `lit` marks a control that is on.
    component PcTile: AbstractButton {
        id: tile
        property string glyph: "sparkle"
        property string title: ""
        property string subtitle: ""
        property color accent: Theme.cyan
        property bool busy: false
        property bool lit: false
        Layout.fillWidth: true
        implicitHeight: 74
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: title + (subtitle ? " · " + subtitle : "")
        background: Rectangle {
            radius: 16
            color: tile.lit ? Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, 0.16)
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
                color: Qt.rgba(tile.accent.r, tile.accent.g, tile.accent.b, tile.lit ? 0.30 : 0.14)
                Icon { anchors.centerIn: parent; name: tile.glyph; size: 19; color: tile.lit ? "white" : tile.accent }
                NumberAnimation on spin { running: tile.busy && mira.motion; from: 0; to: 360; duration: 1500; loops: Animation.Infinite }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.rightMargin: 10
                spacing: 2
                T { text: tile.title; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                T { visible: tile.subtitle !== ""; text: tile.subtitle; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 1; elide: Text.ElideRight }
            }
        }
        scale: down ? 0.98 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    // One live level: a glyph (or the mute button), its name, a slider that holds the owner's value
    // while he drags and until the executor has answered, and the read-back number.
    component LevelRow: RowLayout {
        id: lr
        property string icon: "volume"
        property string label: ""
        property var readback: null
        property bool working: false
        property bool dim: false
        property int minimum: 0
        property color accent: Theme.cyan
        property bool leadButton: false
        property bool leadActive: false
        property bool leadEnabled: true
        property string leadTip: ""
        property string settingsTip: ""
        property int dragged: -1
        // the value on its way to the executor (the page keeps the owner's latest until it is read back)
        property var wanted: null
        readonly property bool known: readback !== undefined && readback !== null
        readonly property bool holding: wanted !== undefined && wanted !== null
        signal commit(int value)
        signal leadClicked()
        signal settings()
        function send() { const v = lr.dragged; lr.commit(v); lr.dragged = -1 }
        Layout.fillWidth: true
        spacing: 10
        IconButton {
            visible: lr.leadButton
            iconName: lr.icon; diameter: 34; tip: lr.leadTip
            active: lr.leadActive; accent: Theme.danger
            enabled: lr.leadEnabled
            onClicked: lr.leadClicked()
        }
        Item {
            visible: !lr.leadButton
            implicitWidth: 34; implicitHeight: 34
            Icon { anchors.centerIn: parent; name: lr.icon; size: 18; color: lr.accent }
        }
        T { text: lr.label; font.pixelSize: Theme.small + 1; Layout.preferredWidth: 96; wrapMode: Text.NoWrap; elide: Text.ElideRight; color: lr.dim ? Theme.ink3 : Theme.ink }
        MiraSlider {
            id: slider
            Layout.fillWidth: true
            from: lr.minimum; to: 100; stepSize: 1
            accent: lr.accent
            enabled: lr.known
            opacity: lr.dim ? 0.55 : 1
            Accessible.name: lr.label
            onMoved: { lr.dragged = Math.round(value); if (!pressed) keyTimer.restart() }
            onPressedChanged: if (!pressed && lr.dragged >= 0) lr.send()
            Timer { id: keyTimer; interval: 350; onTriggered: if (!slider.pressed && lr.dragged >= 0) lr.send() }
        }
        Binding {
            target: slider; property: "value"
            when: !slider.pressed && lr.dragged < 0
            value: lr.holding ? lr.wanted : lr.known ? lr.readback : lr.minimum
            restoreMode: Binding.RestoreNone
        }
        T {
            text: lr.known ? ((slider.pressed || lr.dragged >= 0) ? Math.round(slider.value) : lr.holding ? lr.wanted : lr.readback) + "%" : "—"
            opacity: lr.holding || lr.working ? 0.7 : 1
            font.pixelSize: Theme.small; font.weight: Font.DemiBold; color: Theme.ink2
            Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight; wrapMode: Text.NoWrap
        }
        IconButton {
            visible: lr.settingsTip !== ""
            iconName: "settings"; diameter: 30; tip: lr.settingsTip
            onClicked: lr.settings()
        }
    }

    // A labelled segmented choice; the chosen segment is the read-back, never the click.
    component SegRow: ColumnLayout {
        id: sr
        property string icon: ""
        property string label: ""
        property var options: []
        property string current: ""
        property string waiting: ""
        property bool working: false
        property bool available: true
        property string offText: mira.s.pcp_unknown     // said while !available
        property string extra: ""                        // a quiet fact when nothing is happening
        property color accent: Theme.violet
        signal picked(string key)
        Layout.fillWidth: true
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Icon { visible: sr.icon !== ""; name: sr.icon || "sparkle"; size: 14; color: sr.accent }
            T { text: sr.label; font.pixelSize: Theme.small; font.weight: Font.Medium; color: Theme.ink2; wrapMode: Text.NoWrap }
            Item { Layout.fillWidth: true }
            T {
                readonly property bool quiet: sr.available && !sr.working && sr.waiting === ""
                visible: !quiet || sr.extra !== ""
                text: !sr.available ? sr.offText : sr.working ? mira.s.pcp_working
                      : sr.waiting === "approval" ? mira.s.pcp_waiting : sr.waiting !== "" ? mira.s.pcp_applying : sr.extra
                font.pixelSize: Theme.tiny; wrapMode: Text.NoWrap
                color: !sr.available ? Theme.ink3 : quiet ? sr.accent : Theme.amber
            }
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 38
            radius: 19
            color: Qt.rgba(1, 1, 1, 0.04)
            border.width: 1; border.color: Theme.hairline
            opacity: sr.available ? 1 : 0.45
            RowLayout {
                anchors.fill: parent
                anchors.margins: 3
                spacing: 3
                Repeater {
                    model: sr.options
                    delegate: AbstractButton {
                        id: seg
                        required property var modelData
                        readonly property bool chosen: sr.current === modelData.key
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        hoverEnabled: true
                        focusPolicy: Qt.StrongFocus
                        enabled: sr.available && !sr.working
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: sr.label + " · " + modelData.label
                        Accessible.checked: chosen
                        onClicked: if (!chosen) sr.picked(modelData.key)
                        background: Rectangle {
                            radius: height / 2
                            color: seg.chosen ? Qt.rgba(sr.accent.r, sr.accent.g, sr.accent.b, 0.26)
                                 : seg.hovered ? Qt.rgba(1, 1, 1, 0.07) : "transparent"
                            border.width: seg.visualFocus ? 2 : seg.chosen ? 1 : 0
                            border.color: seg.visualFocus ? Theme.cyan : Qt.rgba(sr.accent.r, sr.accent.g, sr.accent.b, 0.6)
                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                        }
                        contentItem: T {
                            text: seg.modelData.label
                            font.pixelSize: Theme.small
                            font.weight: seg.chosen ? Font.DemiBold : Font.Normal
                            color: seg.chosen ? Theme.ink : Theme.ink2
                            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.NoWrap; elide: Text.ElideRight
                        }
                    }
                }
            }
        }
    }

    // A small group of related one-shot actions under a label.
    component ButtonGroupBox: ColumnLayout {
        id: bg
        property string label: ""
        property var model: []
        property var busyKeys: ({})
        signal picked(string arg)
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: 6
        T { text: bg.label; font.pixelSize: Theme.small; font.weight: Font.Medium; color: Theme.ink2; wrapMode: Text.NoWrap }
        Flow {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: bg.model
                delegate: PillButton {
                    required property var modelData
                    text: modelData.label; iconName: modelData.icon; size: Theme.small; implicitHeight: 34
                    enabled: !bg.busyKeys[modelData.key]
                    onClicked: bg.picked(modelData.arg)
                }
            }
        }
    }

    // One fact about the hardware.
    component Spec: Rectangle {
        id: sp
        property string icon: "chip"
        property string label: ""
        property string value: ""
        property string sub: ""
        property real fraction: -1
        property color accent: Theme.mint
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        implicitHeight: specCol.implicitHeight + 24
        radius: 16
        color: Qt.rgba(1, 1, 1, 0.035)
        border.width: 1; border.color: Theme.hairline
        ColumnLayout {
            id: specCol
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
            spacing: 4
            RowLayout {
                spacing: 6
                Icon { name: sp.icon; size: 14; color: sp.accent }
                T { text: sp.label; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
            }
            T { text: sp.value; font.pixelSize: Theme.body; font.weight: Font.DemiBold; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
            T { visible: sp.sub !== ""; text: sp.sub; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight; horizontalAlignment: Text.AlignLeft }
            Item {
                visible: sp.fraction >= 0
                Layout.fillWidth: true
                Layout.topMargin: 2
                implicitHeight: 5
                Rectangle { anchors.fill: parent; radius: 3; color: Qt.rgba(1, 1, 1, 0.08) }
                Rectangle {
                    width: parent.width * Math.max(0, Math.min(1, sp.fraction)); height: parent.height; radius: 3
                    anchors.left: parent.left
                    color: sp.fraction > 0.9 ? Theme.danger : sp.fraction > 0.75 ? Theme.amber : sp.accent
                }
            }
        }
    }

    // What happened to the last action of a group, in the owner's words, with its tone.
    component NoteLine: RowLayout {
        id: nl
        property var note: null
        readonly property string tone: nl.note ? (nl.note.status || "") : ""
        readonly property color c: tone === "ok" ? Theme.ok : tone === "pending" ? Theme.amber : tone === "error" ? Theme.danger : Theme.cyan
        visible: !!nl.note && !!nl.note.text
        Layout.fillWidth: true
        spacing: 8
        Icon { name: nl.tone === "ok" ? "check" : nl.tone === "pending" ? "clock" : nl.tone === "error" ? "alert" : "sparkle"; size: 14; weight: 2; color: nl.c }
        T { text: nl.note ? (nl.note.text || "") : ""; font.pixelSize: Theme.small; color: Theme.ink2; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
    }

    // A quiet placeholder: nothing yet, nothing found, or why it could not be read.
    component EmptyState: RowLayout {
        id: es
        property string icon: "sparkle"
        property string text: ""
        property string tone: ""
        Layout.fillWidth: true
        Layout.topMargin: 4; Layout.bottomMargin: 4
        spacing: 10
        Rectangle {
            Layout.preferredWidth: 34; Layout.preferredHeight: 34
            radius: 11
            color: es.tone === "error" ? Qt.rgba(1, 0.36, 0.48, 0.12) : Qt.rgba(1, 1, 1, 0.05)
            Icon { anchors.centerIn: parent; name: es.icon; size: 17; color: es.tone === "error" ? Theme.danger : Theme.ink3 }
        }
        T { text: es.text; font.pixelSize: Theme.small; color: es.tone === "error" ? Theme.ink2 : Theme.ink3; Layout.fillWidth: true }
    }

    // The real output of one diagnostics control, right under it.
    component Output: OutputBox {
        property string slot: ""
        readonly property var entry: (mira.pcPage.state.outputs || {})[slot] || null
        readonly property bool working: !!(mira.pcPage.state.running || {})[slot]
        visible: working || entry !== null
        text: working ? "" : (entry ? entry.text : "")
        placeholder: working ? mira.s.pcp_working : ""
        error: !working && !!entry && entry.status === "error"
        maxHeight: 320
    }
}
