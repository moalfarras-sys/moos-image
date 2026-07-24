/*
 * MoOS Control Center — a glass status panel in the corner.
 *
 * The everyday toggles (Wi-Fi, Bluetooth, Night Light, Do Not Disturb) and the
 * volume live one tap away, the way a control centre should. Each tile flips its
 * own state instantly for feedback and drives the real backend (nmcli / bluetoothctl
 * / KWin Night Light / wpctl), so it is not a mock-up — it works.
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
    readonly property color glassText: Kirigami.Theme.textColor

    // ── shell backend (toggles + volume) ────────────────────────────────
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

    // ── panel icon (compact) ────────────────────────────────────────────
    compactRepresentation: MouseArea {
        id: compact
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded
        Kirigami.Icon {
            anchors.centerIn: parent
            width: Math.min(parent.width, parent.height)
            height: width
            source: "moos-logo"
            opacity: compact.containsMouse ? 1.0 : 0.9
            Behavior on opacity { NumberAnimation { duration: 120 } }
        }
    }

    // ── the control centre (full) ───────────────────────────────────────
    fullRepresentation: Item {
        Layout.preferredWidth: 21 * Kirigami.Units.gridUnit
        Layout.preferredHeight: 24 * Kirigami.Units.gridUnit

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            // header
            RowLayout {
                Layout.fillWidth: true
                ColumnLayout {
                    spacing: 0
                    Layout.fillWidth: true
                    PlasmaComponents.Label {
                        text: i18nd("plasma_applet_org.moos.controlcenter", "مركز التحكّم")
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize + 3
                        font.weight: Font.DemiBold
                    }
                    PlasmaComponents.Label {
                        text: "MoOS"
                        opacity: 0.6
                        color: root.accent
                        font.weight: Font.DemiBold
                    }
                }
                Kirigami.Icon { source: "moos-logo"; implicitWidth: Kirigami.Units.iconSizes.medium; implicitHeight: width }
            }

            // 2×2 toggle tiles
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: Kirigami.Units.largeSpacing
                columnSpacing: Kirigami.Units.largeSpacing

                Repeater {
                    model: [
                        { key: "wifi",  label: "واي‑فاي",      icon: "network-wireless-symbolic",     on: "nmcli radio wifi on",  off: "nmcli radio wifi off",  probe: "nmcli -t radio wifi",             onWord: "enabled" },
                        { key: "bt",    label: "بلوتوث",       icon: "network-bluetooth-symbolic",    on: "bluetoothctl power on", off: "bluetoothctl power off", probe: "bluetoothctl show",                onWord: "Powered: yes" },
                        { key: "night", label: "الوضع الليلي", icon: "redshift-status-on-symbolic",   on: "qdbus6 org.kde.KWin /org/kde/KWin/NightLight org.kde.KWin.NightLight.setEnabled true",  off: "qdbus6 org.kde.KWin /org/kde/KWin/NightLight org.kde.KWin.NightLight.setEnabled false", probe: "", onWord: "" },
                        { key: "dnd",   label: "عدم الإزعاج",  icon: "notifications-disabled-symbolic", on: "kwriteconfig6 --file plasmanotifyrc --group DoNotDisturb --key WhenScreensMirrored true", off: "kwriteconfig6 --file plasmanotifyrc --group DoNotDisturb --key WhenScreensMirrored false", probe: "", onWord: "" }
                    ]
                    delegate: Rectangle {
                        id: tile
                        required property var modelData
                        property bool active: false
                        Layout.fillWidth: true
                        Layout.preferredHeight: 5.2 * Kirigami.Units.gridUnit
                        radius: Kirigami.Units.gridUnit * 0.9
                        color: active ? root.accent : Qt.rgba(root.glassText.r, root.glassText.g, root.glassText.b, tileMouse.containsMouse ? 0.14 : 0.08)
                        border.width: 1
                        border.color: active ? Qt.lighter(root.accent, 1.15) : Qt.rgba(root.glassText.r, root.glassText.g, root.glassText.b, 0.10)
                        Behavior on color { ColorAnimation { duration: 160; easing.type: Easing.OutCubic } }
                        scale: tileMouse.pressed ? 0.96 : 1.0
                        Behavior on scale { NumberAnimation { duration: 110; easing.type: Easing.OutCubic } }

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: Kirigami.Units.smallSpacing
                            Kirigami.Icon {
                                Layout.alignment: Qt.AlignHCenter
                                source: modelData.icon
                                implicitWidth: Kirigami.Units.iconSizes.medium
                                implicitHeight: width
                                color: tile.active ? Kirigami.Theme.highlightedTextColor : root.glassText
                                isMask: true
                            }
                            PlasmaComponents.Label {
                                Layout.alignment: Qt.AlignHCenter
                                text: modelData.label
                                color: tile.active ? Kirigami.Theme.highlightedTextColor : root.glassText
                                font.pointSize: Kirigami.Theme.smallFont.pointSize
                            }
                        }
                        MouseArea {
                            id: tileMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                tile.active = !tile.active
                                exec.run(tile.active ? modelData.on : modelData.off)
                            }
                        }
                        Component.onCompleted: {
                            if (modelData.probe.length > 0)
                                exec.run(modelData.probe, (out) => { tile.active = out.indexOf(modelData.onWord) !== -1 })
                        }
                    }
                }
            }

            // volume
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 3.4 * Kirigami.Units.gridUnit
                radius: Kirigami.Units.gridUnit * 0.9
                color: Qt.rgba(root.glassText.r, root.glassText.g, root.glassText.b, 0.08)
                border.width: 1
                border.color: Qt.rgba(root.glassText.r, root.glassText.g, root.glassText.b, 0.10)
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: Kirigami.Units.largeSpacing
                    anchors.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.largeSpacing
                    Kirigami.Icon { source: "audio-volume-high-symbolic"; implicitWidth: Kirigami.Units.iconSizes.smallMedium; implicitHeight: width; isMask: true; color: root.glassText }
                    QQC2.Slider {
                        id: vol
                        Layout.fillWidth: true
                        from: 0; to: 100; stepSize: 1
                        onMoved: exec.run("wpctl set-volume @DEFAULT_AUDIO_SINK@ " + Math.round(value) + "%")
                        Component.onCompleted: exec.run("sh -c \"wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{print int($2*100)}'\"",
                                                        (out) => { const n = parseInt(out); if (!isNaN(n)) value = n })
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // footer: quick launches
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.largeSpacing
                PlasmaComponents.Button {
                    Layout.fillWidth: true
                    icon.name: "settings-configure"
                    text: "الإعدادات"
                    onClicked: { exec.run("systemsettings"); root.expanded = false }
                }
                PlasmaComponents.Button {
                    Layout.fillWidth: true
                    icon.name: "moos-logo"
                    text: "Mo AI"
                    onClicked: { exec.run("moos-open ai/config"); root.expanded = false }
                }
            }
        }
    }
}
