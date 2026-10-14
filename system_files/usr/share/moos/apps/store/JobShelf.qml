pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the running or finished transaction: its words in the owner's language
// (win.jobText), real progress or an honest indeterminate bar, Cancel and Dismiss.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Rectangle {
    id: jobShelf
    required property var win
    readonly property var design: win.design
    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: win.jobIsActive() || win.jobIsTerminal() ? 20 : -100
    width: Math.min(690, win.width - 56)
    height: 76
    radius: win.fs(22)
    visible: anchors.bottomMargin > -100
    color: Qt.rgba(win.raised.r, win.raised.g, win.raised.b, 0.98)
    border.width: 1
    border.color: win.job.state === "failed" ? win.violet
                  : Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.48)
    Behavior on anchors.bottomMargin { NumberAnimation { duration: win.motionEnabled ? design.motionGeometry : 0; easing.type: Easing.OutBack } }
    RowLayout {
        anchors.fill: parent
        anchors.margins: 13
        spacing: design.space3
        Rectangle {
            Layout.preferredWidth: win.fs(44)
            Layout.preferredHeight: win.fs(44)
            radius: design.radiusCard
            color: Qt.rgba(win.accent.r, win.accent.g, win.accent.b, 0.14)
            Glyph {
                win: jobShelf.win
                anchors.centerIn: parent
                width: 23
                height: 23
                name: win.jobIsTerminal() ? (win.job.state === "success" ? "check" : "shield") : "download"
                tint: win.job.state === "failed" ? win.violet : win.accent
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: win.waitingForJob
                        ? (win.rtl ? "يبدأ العمل…" : "Starting…")
                        : win.jobText(win.job, win.rtl ? "جارٍ تنفيذ العملية" : "Working")
                    color: win.txt
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(12)
                    font.bold: true
                    elide: Text.ElideRight
                }
                Text {
                    visible: win.job.progress !== null && win.job.progress !== undefined
                    text: Math.round(win.job.progress || 0) + "%"
                    color: win.accent
                    font.family: win.uiFont
                    font.pixelSize: win.typePx(11)
                    font.bold: true
                }
            }
            Rectangle {
                id: jobProgressTrack
                Layout.fillWidth: true
                Layout.preferredHeight: win.fs(6)
                radius: height / 2
                color: Qt.rgba(win.outline.r, win.outline.g, win.outline.b, 0.5)
                clip: true
                Rectangle {
                    visible: win.job.progress !== null && win.job.progress !== undefined
                    height: parent.height
                    radius: height / 2
                    width: parent.width * Math.max(0, Math.min(100, win.job.progress || 0)) / 100
                    color: win.accent
                    Behavior on width { NumberAnimation { duration: win.motionEnabled ? design.motionGeometry : 0; easing.type: Easing.OutCubic } }
                }
                Rectangle {
                    id: jobProgressIndeterminate
                    visible: win.job.progress === null || win.job.progress === undefined
                    width: jobProgressTrack.width * 0.28
                    height: jobProgressTrack.height
                    radius: win.fs(3)
                    color: win.accent
                    SequentialAnimation on x {
                        running: jobProgressIndeterminate.visible && win.motionEnabled
                        loops: Animation.Infinite
                        NumberAnimation {
                            from: -jobProgressIndeterminate.width
                            to: jobProgressTrack.width
                            duration: win.motionEnabled ? 1200 : 0
                            easing.type: Easing.InOutQuad
                        }
                    }
                }
            }
        }
        ActionButton {
            win: jobShelf.win
            visible: win.jobIsActive()
            enabled: !win.waitingForJob
            label: win.rtl ? "إلغاء" : "Cancel"
            glyphName: "trash"
            destructive: true
            triggered: function() { win.cancelJob() }
        }
        ActionButton {
            win: jobShelf.win
            visible: win.jobIsTerminal()
            label: win.rtl ? "إخفاء" : "Dismiss"
            glyphName: "check"
            triggered: function() { win.job = ({}) }
        }
    }
}
