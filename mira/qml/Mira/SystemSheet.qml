import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Mo AI's centre, inside Mira: the MoOS deployment, the store, and every fixed check, repair,
// update and set-up the executor offers. Checks run at once and show their real output; every
// change becomes a card the owner approves (and a password prompt when it needs one).
Item {
    id: sys
    readonly property var groups: mira.systemGroups
    readonly property var sections: [
        { key: "check", icon: "pulse", label: mira.s.sys_check, accent: Theme.cyan },
        { key: "repair", icon: "wrench", label: mira.s.sys_repair, accent: Theme.amber },
        { key: "update", icon: "download", label: mira.s.sys_update, accent: Theme.violet },
        { key: "setup", icon: "rocket", label: mira.s.sys_setup, accent: Theme.rose } ]
    readonly property var glyphs: ({
        device_report: "monitor", check_drivers: "chip", gpu_report: "grid", net_doctor: "wifi", inspect_boot: "power",
        os_state: "shield", support_bundle: "package", fix_audio: "volume", optimize_system: "bolt",
        system_update: "download", update_apps: "apps", update_firmware: "chip", system_rollback: "refresh",
        setup_gaming: "play", setup_windows: "grid", setup_waydroid: "apps", install_nvidia: "chip", remote_anywhere: "globe" })

    // "booted: version 44.2026… · signed origin · moos-nvidia@sha256:…" → its parts
    function deployment(prefix) {
        var lines = (mira.system.os || "").split("\n")
        for (var i = 0; i < lines.length; ++i) {
            if (lines[i].indexOf(prefix) !== 0) continue
            var parts = lines[i].slice(prefix.length).split("·")
            var version = (parts[0] || "").replace("version", "").trim()
            var signed = (parts[1] || "").indexOf("signed") >= 0
            var edition = ((parts[2] || "").split("@")[0] || "").trim()
            return { version: version, signed: signed, edition: edition }
        }
        return null
    }
    readonly property var booted: deployment("booted:")
    readonly property var kept: deployment("kept for rollback:")

    readonly property var health: mira.system.health || ({})
    readonly property bool staged: !!(health.moos && health.moos.update_staged_for_restart)
    readonly property int findings: (health.findings || []).length
    Component.onCompleted: { if (!mira.system.os) mira.systemAction("os_state"); mira.refreshHealth() }

    Flickable {
        anchors.fill: parent
        contentHeight: col.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { width: 6 }

        ColumnLayout {
            id: col
            width: parent.width
            spacing: 16

            // ── this MoOS ──
            Glass {
                Layout.fillWidth: true
                Layout.preferredHeight: hero.implicitHeight + 32
                radius: 22
                edge: Qt.rgba(0.61, 0.48, 1.0, 0.38)
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.rgba(0.36, 0.26, 0.85, 0.30) }
                    GradientStop { position: 1; color: Qt.rgba(0.10, 0.55, 0.75, 0.18) }
                }
                RowLayout {
                    id: hero
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
                    spacing: 14
                    Rectangle {
                        Layout.preferredWidth: 56; Layout.preferredHeight: 56
                        radius: 18
                        color: Qt.rgba(1, 1, 1, 0.08)
                        border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18)
                        Image { anchors.centerIn: parent; width: 38; height: 38; source: "image://icon/moos-moai"; sourceSize: Qt.size(76, 76); smooth: true }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3
                        T { text: mira.s.sys_version; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap }
                        T {
                            text: sys.booted ? "MoOS " + sys.booted.version : (mira.system.busy === "os_state" ? mira.s.sys_working : "MoOS")
                            font.pixelSize: Theme.heading; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Row {
                            spacing: 6
                            visible: !!sys.booted
                            Rectangle {
                                visible: sys.booted && sys.booted.signed
                                height: 22; radius: 11; width: sigRow.implicitWidth + 16
                                color: Qt.rgba(0.28, 0.88, 0.63, 0.14); border.width: 1; border.color: Qt.rgba(0.28, 0.88, 0.63, 0.4)
                                Row { id: sigRow; anchors.centerIn: parent; spacing: 4
                                    Icon { name: "shield"; size: 13; color: Theme.ok; anchors.verticalCenter: parent.verticalCenter }
                                    T { text: mira.lang === "ar" ? "موقّع ومتحقَّق" : "Signed"; font.pixelSize: Theme.tiny; color: Theme.ok; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter } }
                            }
                            Rectangle {
                                visible: sys.booted && sys.booted.edition !== ""
                                height: 22; radius: 11; width: edText.implicitWidth + 16
                                color: Qt.rgba(1, 1, 1, 0.06); border.width: 1; border.color: Theme.hairline
                                T { id: edText; anchors.centerIn: parent; text: sys.booted ? sys.booted.edition : ""; font.pixelSize: Theme.tiny; color: Theme.ink2; wrapMode: Text.NoWrap }
                            }
                            Rectangle {
                                visible: !!sys.health.moos
                                height: 22; radius: 11; width: updRow.implicitWidth + 16
                                readonly property color c: sys.staged ? Theme.amber : Theme.cyan
                                color: Qt.rgba(c.r, c.g, c.b, 0.14); border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.4)
                                Row { id: updRow; anchors.centerIn: parent; spacing: 4
                                    Icon { name: sys.staged ? "refresh" : "check"; size: 13; color: parent.parent.c; anchors.verticalCenter: parent.verticalCenter }
                                    T { text: sys.staged ? mira.s.sys_staged : mira.s.sys_current; font.pixelSize: Theme.tiny; color: parent.parent.c; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter } }
                            }
                            T {
                                visible: !!sys.kept
                                text: (mira.lang === "ar" ? "الاحتياطي: " : "Rollback: ") + (sys.kept ? sys.kept.version : "")
                                font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                    ColumnLayout {
                        spacing: 8
                        PillButton { text: mira.s.sys_update; iconName: "download"; primary: true; size: Theme.small; onClicked: mira.systemAction("system_update") }
                        PillButton { text: mira.s.sys_settings; iconName: "settings"; size: Theme.small; onClicked: mira.openSettingsPage("update") }
                    }
                }
            }

            // ── the store ──
            SectionTitle { icon: "package"; text: mira.s.sys_store; accent: Theme.mint }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                MiraField {
                    id: query
                    Layout.fillWidth: true
                    placeholderText: mira.s.sys_search
                    onAccepted: mira.searchStore(text)
                }
                IconButton { iconName: "send"; tip: mira.s.send; enabled: query.text.trim() !== "" && !mira.system.searching; onClicked: mira.searchStore(query.text) }
            }
            T {
                visible: mira.system.searching
                text: mira.lang === "ar" ? "أبحث في المتجر…" : "Searching the store…"
                color: Theme.ink3; font.pixelSize: Theme.small
            }
            T {
                visible: !mira.system.searching && mira.system.query !== "" && (mira.system.apps || []).length === 0
                text: mira.s.sys_no_results
                color: Theme.ink3; font.pixelSize: Theme.small
            }
            Repeater {
                model: mira.system.apps || []
                delegate: Glass {
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 64
                    radius: 16
                    RowLayout {
                        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                        spacing: 12
                        Rectangle {
                            Layout.preferredWidth: 40; Layout.preferredHeight: 40
                            radius: 12
                            gradient: Gradient {
                                GradientStop { position: 0; color: Qt.rgba(0.42, 0.33, 0.94, 0.55) }
                                GradientStop { position: 1; color: Qt.rgba(0.17, 0.78, 0.9, 0.45) }
                            }
                            T { anchors.centerIn: parent; text: (modelData.name || "?").charAt(0).toUpperCase(); font.pixelSize: 18; font.weight: Font.Bold; color: "white" }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            RowLayout {
                                spacing: 6
                                T { text: modelData.name || modelData.id; font.pixelSize: Theme.body; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                                Icon { visible: !!modelData.verified; name: "check"; size: 13; weight: 2.2; color: Theme.cyan }
                                T { visible: !!modelData.installed; text: "· " + mira.s.sys_installed; font.pixelSize: Theme.tiny; color: Theme.ok; wrapMode: Text.NoWrap }
                            }
                            T { text: modelData.summary || modelData.id; font.pixelSize: Theme.tiny + 1; color: Theme.ink3; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true }
                        }
                        PillButton {
                            visible: !!modelData.installed
                            text: mira.lang === "ar" ? "فتح" : "Open"; iconName: "external"; size: Theme.small; implicitHeight: 34
                            onClicked: mira.openApp(modelData.id)
                        }
                        PillButton {
                            text: modelData.installed ? mira.s.sys_remove : mira.s.sys_install
                            iconName: modelData.installed ? "trash" : "download"
                            primary: !modelData.installed; danger: !!modelData.installed
                            size: Theme.small; implicitHeight: 34
                            onClicked: mira.storeAction(modelData.installed ? "uninstall_app" : "install_app", modelData.id)
                        }
                    }
                }
            }

            // ── checks, repairs, updates, set-ups ──
            Repeater {
                model: sys.sections
                delegate: ColumnLayout {
                    required property var modelData
                    readonly property var section: modelData
                    Layout.fillWidth: true
                    spacing: 10
                    visible: (sys.groups[section.key] || []).length > 0
                    SectionTitle { icon: section.icon; text: section.label; accent: section.accent }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: sys.width > 560 ? 3 : 2
                        columnSpacing: 8; rowSpacing: 8
                        Repeater {
                            model: sys.groups[section.key] || []
                            delegate: AbstractButton {
                                id: tile
                                required property var modelData
                                readonly property bool changes: modelData.category === "user_confirm" || modelData.category === "privileged_confirm"
                                readonly property bool busyNow: mira.system.busy === modelData.name
                                Layout.fillWidth: true
                                implicitHeight: 76
                                hoverEnabled: true
                                enabled: mira.system.busy === "" || busyNow
                                Accessible.name: modelData.title
                                onClicked: if (!busyNow) mira.systemAction(modelData.name)
                                background: Rectangle {
                                    radius: 16
                                    color: tile.down ? Theme.glassHover : tile.hovered ? Qt.rgba(1, 1, 1, 0.075) : Qt.rgba(1, 1, 1, 0.04)
                                    border.width: 1
                                    border.color: tile.busyNow || (mira.system.tool === tile.modelData.name && mira.system.output !== "")
                                                  ? Qt.rgba(section.accent.r, section.accent.g, section.accent.b, 0.55)
                                                  : tile.hovered ? Theme.hairlineStrong : Theme.hairline
                                    opacity: tile.enabled ? 1 : 0.5
                                    Behavior on color { ColorAnimation { duration: Theme.fast } }
                                }
                                contentItem: RowLayout {
                                    spacing: 10
                                    Rectangle {
                                        property real spin: 0
                                        Layout.preferredWidth: 38; Layout.preferredHeight: 38
                                        Layout.leftMargin: 10
                                        radius: 12
                                        rotation: tile.busyNow ? spin : 0
                                        color: Qt.rgba(section.accent.r, section.accent.g, section.accent.b, 0.14)
                                        Icon { anchors.centerIn: parent; name: sys.glyphs[tile.modelData.name] || section.icon; size: 19; color: section.accent }
                                        NumberAnimation on spin { running: tile.busyNow && mira.motion; from: 0; to: 360; duration: 1600; loops: Animation.Infinite }
                                    }
                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.rightMargin: 10
                                        spacing: 2
                                        T { text: tile.modelData.title; font.pixelSize: Theme.small + 1; font.weight: Font.Medium; Layout.fillWidth: true; maximumLineCount: 2; elide: Text.ElideRight }
                                        Row {
                                            visible: tile.changes
                                            spacing: 4
                                            Icon { name: tile.modelData.category === "privileged_confirm" ? "lock" : "shield"; size: 11; weight: 2; color: Theme.ink3; anchors.verticalCenter: parent.verticalCenter }
                                            T { text: tile.modelData.category === "privileged_confirm" ? mira.s.sys_privileged : mira.s.sys_confirm; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── what the last check really returned ──
            SectionTitle { icon: "book"; text: mira.s.sys_result; accent: Theme.violet }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(110, Math.min(380, out.implicitHeight + 28))
                radius: 16
                color: Qt.rgba(0, 0, 0, 0.28)
                border.width: 1; border.color: mira.system.status === "error" ? Qt.rgba(1, 0.36, 0.48, 0.45) : Theme.hairline
                Flickable {
                    anchors.fill: parent; anchors.margins: 14
                    contentHeight: out.implicitHeight
                    clip: true
                    TextEdit {
                        id: out
                        width: parent.width
                        readOnly: true; selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        readonly property bool reading: mira.system.busy === "" && mira.system.output !== ""
                        color: reading ? Theme.ink2 : Theme.ink3
                        font.family: reading ? Theme.mono : Theme.font
                        font.pixelSize: reading ? 12 : Theme.body
                        text: mira.system.busy !== "" && mira.system.busy !== "os_state" ? mira.s.sys_working : (reading ? mira.system.output : mira.s.sys_result_empty)
                        horizontalAlignment: reading ? Text.AlignLeft : Text.AlignHCenter
                        LayoutMirroring.enabled: false
                    }
                }
            }
            Item { height: 8 }
        }
    }
}
