import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes

// Mira on the owner's phone: turn it on, pair with the code, see who is connected.
// Everything here is read back from the companion service (`mira.companion`): the switch and the
// state follow what the server reports, never what was just clicked. The pairing code stays
// hidden until asked for and hides itself again after two minutes.
ColumnLayout {
    id: panel
    spacing: 14

    readonly property var c: mira.companion || ({})
    readonly property var tx: c.text || ({})
    readonly property var qr: c.qr || ({ size: 0, runs: [] })
    readonly property bool running: c.state === "running"
    readonly property color stateColor: c.state === "running" ? Theme.ok
                                      : c.state === "waiting" || c.state === "starting" ? Theme.amber
                                      : c.state === "error" ? Theme.danger : Theme.off
    property bool revealed: false
    property bool armed: false

    onRunningChanged: if (!running) { revealed = false; armed = false }
    onRevealedChanged: revealed ? hideTimer.restart() : hideTimer.stop()
    Timer { id: hideTimer; interval: 120000; onTriggered: panel.revealed = false }
    Timer { id: disarmTimer; interval: 5000; onTriggered: panel.armed = false }

    // ── the switch and the live state ─────────────────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: head.implicitHeight + 32
        radius: 18
        lit: panel.running
        ColumnLayout {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Rectangle {
                    Layout.preferredWidth: 40
                    Layout.preferredHeight: 40
                    radius: 12
                    color: Qt.rgba(Theme.cyan.r, Theme.cyan.g, Theme.cyan.b, panel.running ? 0.18 : 0.07)
                    Icon {   // a phone, drawn like Mira's own line icons
                        anchors.centerIn: parent
                        size: 24
                        color: panel.running ? Theme.cyan : Theme.ink3
                        path: "M8.5 2.5h7a2 2 0 0 1 2 2v15a2 2 0 0 1-2 2h-7a2 2 0 0 1-2-2v-15a2 2 0 0 1 2-2z M10.5 18.5h3"
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    T { Layout.fillWidth: true; text: panel.tx.title || ""; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
                    T { Layout.fillWidth: true; text: panel.tx.subtitle || ""; font.pixelSize: Theme.small; color: Theme.ink3 }
                }
                MiraSwitch {
                    Accessible.name: panel.tx.enable || ""
                    checked: panel.c.enabled === true
                    onToggled: {
                        const want = checked
                        checked = Qt.binding(function() { return panel.c.enabled === true })
                        mira.setCompanionEnabled(want)
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Rectangle {
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: 5
                    width: 8; height: 8; radius: 4
                    color: panel.stateColor
                    Behavior on color { ColorAnimation { duration: Theme.normal } }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 3
                    T {
                        Layout.fillWidth: true
                        text: (panel.c.label || "") + (panel.running ? " · " + (panel.c.phones || "") : "")
                        font.pixelSize: Theme.small; font.weight: Font.DemiBold; color: Theme.ink2
                    }
                    T {
                        Layout.fillWidth: true
                        visible: text !== ""
                        text: panel.c.reason || ""
                        font.pixelSize: Theme.small
                        color: panel.c.state === "error" ? Theme.danger : Theme.amber
                    }
                    T {
                        Layout.fillWidth: true
                        visible: panel.running
                        text: (panel.tx.address || "") + " · " + (panel.c.address || "")
                        font.pixelSize: Theme.small; color: Theme.ink3
                    }
                    T {
                        Layout.fillWidth: true
                        visible: panel.running && text !== ""
                        text: panel.c.lastPaired || ""
                        font.pixelSize: Theme.small; color: Theme.ink3
                    }
                }
            }
        }
    }

    // ── pairing ───────────────────────────────────────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: pair.implicitHeight + 32
        radius: 18
        visible: panel.running
        ColumnLayout {
            id: pair
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
            spacing: 12
            SectionTitle { icon: "shield"; text: panel.tx.pair_title || ""; accent: Theme.cyan }
            T { Layout.fillWidth: true; text: panel.tx.pair_steps || ""; font.pixelSize: Theme.small; color: Theme.ink2 }

            Rectangle {
                id: qrBox
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 232
                Layout.preferredHeight: 232
                visible: panel.revealed && (panel.qr.size || 0) > 0
                radius: 16
                color: "white"
                readonly property int n: panel.qr.size || 0
                readonly property int cell: n > 0 ? Math.floor((width - 28) / n) : 0
                readonly property int offset: Math.floor((width - cell * n) / 2)
                Accessible.role: Accessible.Graphic
                Accessible.name: panel.tx.link || ""
                Repeater {
                    model: qrBox.visible ? panel.qr.runs : []
                    delegate: Rectangle {
                        required property var modelData
                        x: qrBox.offset + modelData[0] * qrBox.cell
                        y: qrBox.offset + modelData[1] * qrBox.cell
                        width: modelData[2] * qrBox.cell
                        height: qrBox.cell
                        color: Theme.bg0
                        antialiasing: false
                    }
                }
            }
            T {
                Layout.fillWidth: true
                visible: panel.revealed && (panel.qr.size || 0) === 0
                text: panel.tx.qr_missing || ""
                font.pixelSize: Theme.small; color: Theme.amber
            }
            TextEdit {
                Layout.fillWidth: true
                visible: panel.revealed
                readOnly: true
                selectByMouse: true
                text: panel.c.url || ""
                wrapMode: TextEdit.WrapAnywhere
                horizontalAlignment: TextEdit.AlignHCenter
                color: Theme.ink2
                selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
                font.family: Theme.mono
                font.pixelSize: Theme.small
                Accessible.name: panel.tx.link || ""
            }
            T {
                Layout.fillWidth: true
                visible: !panel.revealed
                text: panel.tx.code_hidden || ""
                font.pixelSize: Theme.small; color: Theme.ink3
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                PillButton {
                    text: panel.revealed ? (panel.tx.hide_code || "") : (panel.tx.show_code || "")
                    iconName: panel.revealed ? "x" : "grid"
                    primary: !panel.revealed
                    onClicked: panel.revealed = !panel.revealed
                }
                PillButton {
                    text: panel.armed ? (panel.tx.rotate_confirm || "") : (panel.tx.rotate || "")
                    iconName: "refresh"
                    danger: true
                    onClicked: {
                        if (!panel.armed) {
                            panel.armed = true
                            disarmTimer.restart()
                            return
                        }
                        panel.armed = false
                        disarmTimer.stop()
                        mira.rotateCompanionCode()
                    }
                }
            }
            T { Layout.fillWidth: true; text: panel.tx.rotate_note || ""; font.pixelSize: Theme.small; color: Theme.ink3 }
        }
    }

    // ── what the phone can and cannot do ──────────────────────────────
    Glass {
        Layout.fillWidth: true
        Layout.preferredHeight: note.implicitHeight + 32
        radius: 18
        Column {
            id: note
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
            spacing: 8
            SectionTitle { icon: "shield"; text: panel.tx.note_title || ""; accent: Theme.ok }
            T { width: parent.width; text: panel.tx.note || ""; font.pixelSize: Theme.small; color: Theme.ink2 }
            T { width: parent.width; text: panel.tx.note_brain || ""; font.pixelSize: Theme.small; color: Theme.ink3 }
        }
    }
}
