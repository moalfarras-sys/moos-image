import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// The computer through Mo AI's fixed executor: live levels, read-only checks, and app launching.
Item {
    id: pcs
    property string filter: ""
    readonly property var checks: [
        { tool: "get_system_status", icon: "pulse", label: mira.s.pc_status },
        { tool: "memory_status", icon: "memory", label: mira.s.pc_memory },
        { tool: "disk_status", icon: "disk", label: mira.s.pc_disk },
        { tool: "network_status", icon: "wifi", label: mira.s.pc_network },
        { tool: "top_processes", icon: "chip", label: mira.s.pc_processes },
        { tool: "list_failed_units", icon: "alert", label: mira.s.pc_failed } ]

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

            // live levels
            Glass {
                Layout.fillWidth: true
                Layout.preferredHeight: levels.implicitHeight + 28
                radius: 18
                ColumnLayout {
                    id: levels
                    anchors.fill: parent; anchors.margins: 14
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Icon { name: "volume"; size: 18; color: Theme.cyan }
                        T { text: mira.s.pc_volume; font.pixelSize: Theme.small + 1; Layout.preferredWidth: 130; wrapMode: Text.NoWrap }
                        MiraSlider {
                            Layout.fillWidth: true
                            from: 0; to: 100; stepSize: 1
                            enabled: mira.pc.volume !== null && mira.pc.volume !== undefined && !mira.pc.busy
                            value: mira.pc.volume || 0
                            onPressedChanged: if (!pressed) mira.setPcVolume(value)
                        }
                        T { text: (mira.pc.volume !== null && mira.pc.volume !== undefined) ? mira.pc.volume + "%" : "—"; font.pixelSize: Theme.small; color: Theme.ink2; Layout.preferredWidth: 42; horizontalAlignment: Text.AlignRight; wrapMode: Text.NoWrap }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Icon { name: "sun"; size: 18; color: Theme.amber }
                        T { text: mira.s.pc_brightness; font.pixelSize: Theme.small + 1; Layout.preferredWidth: 130; wrapMode: Text.NoWrap }
                        MiraSlider {
                            Layout.fillWidth: true
                            accent: Theme.amber
                            from: 5; to: 100; stepSize: 1
                            enabled: mira.pc.brightness !== null && mira.pc.brightness !== undefined && !mira.pc.busy
                            value: mira.pc.brightness || 50
                            onPressedChanged: if (!pressed) mira.setPcBrightness(value)
                        }
                        T { text: (mira.pc.brightness !== null && mira.pc.brightness !== undefined) ? mira.pc.brightness + "%" : "—"; font.pixelSize: Theme.small; color: Theme.ink2; Layout.preferredWidth: 42; horizontalAlignment: Text.AlignRight; wrapMode: Text.NoWrap }
                    }
                }
            }

            // checks
            SectionTitle { icon: "pulse"; text: mira.s.pc_result; accent: Theme.violet }
            GridLayout {
                Layout.fillWidth: true
                columns: pcs.width > 480 ? 3 : 2
                columnSpacing: 8; rowSpacing: 8
                Repeater {
                    model: pcs.checks
                    delegate: PillButton {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.label; iconName: modelData.icon; size: Theme.small
                        enabled: !mira.pc.busy
                        primary: mira.pc.tool === modelData.tool && mira.pc.output !== ""
                        onClicked: mira.runPc(modelData.tool)
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(120, Math.min(360, out.implicitHeight + 28))
                radius: 16
                color: Qt.rgba(0, 0, 0, 0.28)
                border.width: 1; border.color: mira.pc.status === "error" ? Qt.rgba(1, 0.36, 0.48, 0.45) : Theme.hairline
                Flickable {
                    anchors.fill: parent; anchors.margins: 14
                    contentHeight: out.implicitHeight
                    clip: true
                    TextEdit {
                        id: out
                        width: parent.width
                        readOnly: true; selectByMouse: true
                        wrapMode: TextEdit.Wrap
                        color: mira.pc.output ? Theme.ink2 : Theme.ink3
                        readonly property bool reading: !mira.pc.busy && !!mira.pc.output
                        font.family: reading ? Theme.mono : Theme.font
                        font.pixelSize: reading ? 12 : Theme.body
                        text: mira.pc.busy ? mira.s.pc_working : (mira.pc.output || mira.s.pc_result_empty)
                        horizontalAlignment: reading ? Text.AlignLeft : Text.AlignHCenter
                        LayoutMirroring.enabled: false
                    }
                }
            }

            // applications
            SectionTitle { icon: "apps"; text: mira.s.pc_apps; accent: Theme.cyan }
            RowLayout {
                Layout.fillWidth: true
                MiraField { Layout.fillWidth: true; placeholderText: mira.s.pc_search_apps; onTextChanged: pcs.filter = text.toLowerCase() }
                IconButton { iconName: "refresh"; tip: mira.s.refresh; onClicked: mira.refreshApps() }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                    model: (mira.pc.apps || []).filter(function(a) { return pcs.filter === "" || a.name.toLowerCase().indexOf(pcs.filter) >= 0 || a.id.toLowerCase().indexOf(pcs.filter) >= 0 }).slice(0, 60)
                    delegate: PillButton {
                        required property var modelData
                        text: modelData.name
                        iconName: "external"
                        size: Theme.small
                        implicitHeight: 34
                        onClicked: mira.openApp(modelData.id)
                        ToolTip.visible: hovered; ToolTip.text: modelData.id; ToolTip.delay: 600
                    }
                }
            }
            Item { height: 8 }
        }
    }
}
