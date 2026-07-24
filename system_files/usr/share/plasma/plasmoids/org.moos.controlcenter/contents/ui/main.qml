/*
 * MoOS Control Center — the one glass status hub.
 *
 * Merges the everyday status into a single Apple-style panel: connectivity rows
 * that NAME what is connected (the Wi-Fi network, the Bluetooth device), quick
 * toggles, a live volume slider, whatever media is playing, and a shortcut into
 * the full notification history. Every control drives the real backend
 * (nmcli / bluetoothctl / KWin Night Light / wpctl / MPRIS) — not a mock-up.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support

PlasmoidItem {
    id: root
    preferredRepresentation: compactRepresentation

    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property color txt: Kirigami.Theme.textColor
    function soft(a) { return Qt.rgba(txt.r, txt.g, txt.b, a) }

    // live state
    property bool wifiOn: false
    property string wifiName: ""
    property bool btOn: false
    property string btName: ""
    property bool nightOn: false
    property bool dndOn: false
    property int volume: 50
    property string mediaTitle: ""
    property string mediaArtist: ""

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        property var cbs: ({})
        onNewData: (source, data) => {
            const cb = cbs[source]
            if (cb) { cb((data["stdout"] || "").trim()); delete cbs[source] }
            disconnectSource(source)
        }
        function run(cmd, cb) { if (cb) cbs[cmd] = cb; connectSource(cmd) }
    }

    function refresh() {
        exec.run("sh -c \"nmcli -t -f active,ssid dev wifi 2>/dev/null | grep '^yes' | cut -d: -f2 | head -1\"",
                 (o) => { root.wifiName = o; root.wifiOn = o.length > 0 || root.wifiOn })
        exec.run("sh -c \"nmcli -t radio wifi 2>/dev/null\"", (o) => { root.wifiOn = o.indexOf('enabled') !== -1 })
        exec.run("sh -c \"bluetoothctl devices Connected 2>/dev/null | sed 's/^Device [^ ]* //' | head -1\"",
                 (o) => { root.btName = o })
        exec.run("sh -c \"bluetoothctl show 2>/dev/null | grep -q 'Powered: yes' && echo on || echo off\"",
                 (o) => { root.btOn = o.indexOf('on') !== -1 })
        exec.run("sh -c \"wpctl get-volume @DEFAULT_AUDIO_SINK@ 2>/dev/null | awk '{print int($2*100)}'\"",
                 (o) => { const n = parseInt(o); if (!isNaN(n)) root.volume = n })
        exec.run("sh -c \"playerctl metadata --format '{{title}}\\n{{artist}}' 2>/dev/null\"",
                 (o) => { const p = o.split('\\n'); root.mediaTitle = p[0] || ''; root.mediaArtist = p[1] || '' })
    }
    Timer { interval: 5000; running: root.expanded; repeat: true; onTriggered: root.refresh() }
    onExpandedChanged: if (expanded) refresh()

    compactRepresentation: MouseArea {
        id: compact
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded
        Kirigami.Icon {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height); height: width
            source: "moos-logo"
            opacity: compact.containsMouse ? 1.0 : 0.88
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }
    }

    fullRepresentation: Item {
        Layout.preferredWidth: 22 * Kirigami.Units.gridUnit
        Layout.preferredHeight: 30 * Kirigami.Units.gridUnit

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing * 1.5

            // ── header ──
            RowLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: Kirigami.Units.smallSpacing
                Kirigami.Icon { source: "moos-logo"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: width }
                ColumnLayout {
                    spacing: 0; Layout.fillWidth: true
                    PlasmaComponents.Label {
                        text: i18nd("plasma_applet_org.moos.controlcenter", "مركز التحكّم")
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize + 3
                        font.weight: Font.DemiBold
                    }
                    PlasmaComponents.Label { text: Qt.formatDate(new Date(), "dddd d MMMM"); opacity: 0.55; font.pointSize: Kirigami.Theme.smallFont.pointSize }
                }
            }

            // ── connectivity: names WHAT is connected ──
            component ConnRow : Rectangle {
                id: cr
                property alias icon: ci.source
                property string title: ""
                property string status: ""
                property bool on: false
                signal toggled(bool v)
                Layout.fillWidth: true
                Layout.preferredHeight: 4 * Kirigami.Units.gridUnit
                radius: Kirigami.Units.gridUnit * 0.8
                color: root.soft(cm.containsMouse ? 0.12 : 0.07)
                border.width: 1; border.color: root.soft(0.09)
                Behavior on color { ColorAnimation { duration: 140 } }
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Kirigami.Units.largeSpacing; anchors.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing
                    Rectangle {
                        implicitWidth: 2.6 * Kirigami.Units.gridUnit; implicitHeight: width; radius: width/2
                        color: cr.on ? root.accent : root.soft(0.12)
                        Behavior on color { ColorAnimation { duration: 180 } }
                        Kirigami.Icon { id: ci; anchors.centerIn: parent; width: Kirigami.Units.iconSizes.smallMedium; height: width; isMask: true; color: cr.on ? Kirigami.Theme.highlightedTextColor : root.txt }
                    }
                    ColumnLayout {
                        spacing: 0; Layout.fillWidth: true
                        PlasmaComponents.Label { text: cr.title; font.weight: Font.DemiBold }
                        PlasmaComponents.Label { text: cr.status; opacity: 0.6; font.pointSize: Kirigami.Theme.smallFont.pointSize; elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                    QQC2.Switch { checked: cr.on; onToggled: cr.toggled(checked) }
                }
                MouseArea { id: cm; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
            }

            ConnRow {
                icon: "network-wireless-symbolic"; title: "واي‑فاي"
                on: root.wifiOn
                status: root.wifiOn ? (root.wifiName.length ? "متصل: " + root.wifiName : "مُفعّل") : "مُطفأ"
                onToggled: (v) => { exec.run(v ? "nmcli radio wifi on" : "nmcli radio wifi off"); root.wifiOn = v; refreshTimer.restart() }
            }
            ConnRow {
                icon: "network-bluetooth-symbolic"; title: "بلوتوث"
                on: root.btOn
                status: root.btOn ? (root.btName.length ? "متصل: " + root.btName : "مُفعّل — لا جهاز") : "مُطفأ"
                onToggled: (v) => { exec.run(v ? "bluetoothctl power on" : "bluetoothctl power off"); root.btOn = v; refreshTimer.restart() }
            }
            Timer { id: refreshTimer; interval: 900; onTriggered: root.refresh() }

            // ── quick toggles ──
            GridLayout {
                Layout.fillWidth: true; columns: 2
                rowSpacing: Kirigami.Units.smallSpacing * 1.5; columnSpacing: Kirigami.Units.smallSpacing * 1.5

                component Tile : Rectangle {
                    id: tl
                    property alias icon: ti.source
                    property string label: ""
                    property bool on: false
                    signal clicked()
                    Layout.fillWidth: true; Layout.preferredHeight: 4.2 * Kirigami.Units.gridUnit
                    radius: Kirigami.Units.gridUnit * 0.8
                    color: on ? root.accent : root.soft(tm.containsMouse ? 0.12 : 0.07)
                    border.width: 1; border.color: on ? Qt.lighter(root.accent, 1.15) : root.soft(0.09)
                    Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
                    scale: tm.pressed ? 0.96 : 1.0
                    Behavior on scale { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
                    ColumnLayout {
                        anchors.centerIn: parent; spacing: Kirigami.Units.smallSpacing
                        Kirigami.Icon { id: ti; Layout.alignment: Qt.AlignHCenter; width: Kirigami.Units.iconSizes.medium; height: width; isMask: true; color: tl.on ? Kirigami.Theme.highlightedTextColor : root.txt }
                        PlasmaComponents.Label { Layout.alignment: Qt.AlignHCenter; text: tl.label; color: tl.on ? Kirigami.Theme.highlightedTextColor : root.txt; font.pointSize: Kirigami.Theme.smallFont.pointSize }
                    }
                    MouseArea { id: tm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tl.clicked() }
                }
                Tile {
                    icon: "night-light-symbolic"; label: "الوضع الليلي"; on: root.nightOn
                    onClicked: { root.nightOn = !root.nightOn; exec.run("qdbus6 org.kde.KWin /org/kde/KWin/NightLight org.kde.KWin.NightLight.setEnabled " + root.nightOn + " 2>/dev/null || dbus-send --session --dest=org.kde.KWin /org/kde/KWin/NightLight org.kde.KWin.NightLight.setEnabled boolean:" + root.nightOn) }
                }
                Tile {
                    icon: "notifications-disabled-symbolic"; label: "عدم الإزعاج"; on: root.dndOn
                    onClicked: { root.dndOn = !root.dndOn; exec.run("kwriteconfig6 --file plasmanotifyrc --group DoNotDisturb --key Until " + (root.dndOn ? "9999-12-31T23:59:59" : "")) }
                }
            }

            // ── volume ──
            RowLayout {
                Layout.fillWidth: true; Layout.topMargin: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.largeSpacing
                Kirigami.Icon { source: root.volume === 0 ? "audio-volume-muted-symbolic" : "audio-volume-high-symbolic"; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: width; isMask: true; color: root.txt }
                QQC2.Slider {
                    Layout.fillWidth: true; from: 0; to: 100; stepSize: 1; value: root.volume
                    onMoved: { root.volume = Math.round(value); exec.run("wpctl set-volume @DEFAULT_AUDIO_SINK@ " + root.volume + "%") }
                }
            }

            // ── now playing (only when something is) ──
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 3.6 * Kirigami.Units.gridUnit
                visible: root.mediaTitle.length > 0
                radius: Kirigami.Units.gridUnit * 0.8; color: root.soft(0.07); border.width: 1; border.color: root.soft(0.09)
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Kirigami.Units.largeSpacing; anchors.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.smallSpacing
                    Kirigami.Icon { source: "media-playback-start-symbolic"; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: width; isMask: true; color: root.accent }
                    ColumnLayout {
                        spacing: 0; Layout.fillWidth: true
                        PlasmaComponents.Label { text: root.mediaTitle; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
                        PlasmaComponents.Label { text: root.mediaArtist; opacity: 0.6; font.pointSize: Kirigami.Theme.smallFont.pointSize; elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                    PlasmaComponents.ToolButton { icon.name: "media-skip-backward-symbolic"; onClicked: exec.run("playerctl previous") }
                    PlasmaComponents.ToolButton { icon.name: "media-playback-start-symbolic"; onClicked: exec.run("playerctl play-pause") }
                    PlasmaComponents.ToolButton { icon.name: "media-skip-forward-symbolic"; onClicked: exec.run("playerctl next") }
                }
            }

            Item { Layout.fillHeight: true }

            // ── footer: proper icons, notifications + settings + Mo AI ──
            RowLayout {
                Layout.fillWidth: true; spacing: Kirigami.Units.smallSpacing
                PlasmaComponents.Button {
                    Layout.fillWidth: true; icon.name: "notifications-symbolic"; text: "الإشعارات"
                    onClicked: { exec.run("plasma-open-settings kcm_notifications 2>/dev/null || systemsettings kcm_notifications"); root.expanded = false }
                }
                PlasmaComponents.Button {
                    Layout.fillWidth: true; icon.name: "settings-configure"; text: "الإعدادات"
                    onClicked: { exec.run("systemsettings"); root.expanded = false }
                }
                PlasmaComponents.Button {
                    Layout.fillWidth: true; icon.name: "org.moos.moai"; text: "Mo AI"
                    onClicked: { exec.run("moos-open ai/config"); root.expanded = false }
                }
            }
        }
    }
}
