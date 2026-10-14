pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

// Mo Store — the running or finished transaction, floating at the foot of the window: which app,
// the backend's words in the owner's language (win.jobText), the job's real percentage or an
// honest indeterminate bar that runs only while the job runs, Cancel while it works and Dismiss
// once it has ended — success, partly done, failed or cancelled, never claimed before job.json
// says so.
//
// Drawn from main.qml's state: `win` is the Store window, which owns the data, the actions
// and the palette. This file only presents them.
Item {
    id: jobShelf
    objectName: "jobShelf"
    required property var win
    readonly property var design: win.design
    readonly property bool shown: win.jobIsActive() || win.jobIsTerminal()
    readonly property var items: win.job.items || []
    readonly property var subject: {
        var id = jobShelf.win.job.current_id || (jobShelf.items.length === 1 ? jobShelf.items[0].id : "")
        return id ? jobShelf.win.appById(id) : null
    }
    readonly property color tone: jobShelf.win.job.state === "failed" ? jobShelf.win.dangerInk
                                : jobShelf.win.job.state === "partial" ? jobShelf.win.warningInk
                                : jobShelf.win.job.state === "success" ? jobShelf.win.positiveInk
                                : jobShelf.win.accent

    anchors.horizontalCenter: parent.horizontalCenter
    anchors.bottom: parent.bottom
    anchors.bottomMargin: jobShelf.shown ? win.fs(20) : -win.fs(120)
    width: Math.min(win.fs(720), win.width - win.fs(64))
    height: win.fs(80)
    visible: anchors.bottomMargin > -win.fs(120)
    z: 50
    Behavior on anchors.bottomMargin { NumberAnimation { duration: jobShelf.win.motionEnabled ? jobShelf.design.motionGeometry : 0; easing.type: Easing.OutCubic } }

    SoftShadow { win: jobShelf.win; radius: shelf.radius; strength: 2.2; lift: jobShelf.design.space3 }
    Rectangle {
        id: shelf
        anchors.fill: parent
        radius: jobShelf.design.radiusPanel
        color: jobShelf.win.cardColor
        border.width: 1
        border.color: jobShelf.win.job.state === "failed" ? jobShelf.win.tint(jobShelf.win.dangerInk, 0.6)
                    : jobShelf.win.tint(jobShelf.win.accent, 0.45)
        LayoutMirroring.enabled: jobShelf.win.rtl
        LayoutMirroring.childrenInherit: true
        Accessible.role: Accessible.StatusBar
        Accessible.name: jobLine.text

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: jobShelf.design.space4
            anchors.rightMargin: jobShelf.design.space3
            spacing: jobShelf.design.space3

            Item {
                Layout.preferredWidth: jobShelf.win.fs(48)
                Layout.preferredHeight: jobShelf.win.fs(48)
                AppIcon {
                    win: jobShelf.win
                    anchors.fill: parent
                    visible: jobShelf.subject !== null
                    app: jobShelf.subject
                    size: jobShelf.win.fs(48)
                }
                Rectangle {
                    anchors.fill: parent
                    visible: jobShelf.subject === null
                    radius: width / 2
                    color: jobShelf.win.tint(jobShelf.tone, 0.16)
                    Glyph {
                        win: jobShelf.win
                        anchors.centerIn: parent
                        width: jobShelf.win.fs(24)
                        height: width
                        name: jobShelf.win.jobIsTerminal()
                            ? (jobShelf.win.job.state === "success" ? "check"
                               : jobShelf.win.job.state === "failed" ? "danger" : "warning")
                            : "download"
                        tint: jobShelf.tone
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: jobShelf.design.space1 + 2
                RowLayout {
                    Layout.fillWidth: true
                    spacing: jobShelf.design.space2
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        id: jobLine
                        Layout.fillWidth: true
                        text: {
                            var words = jobShelf.win.waitingForJob
                                ? jobShelf.win.local("يبدأ العمل…", "Starting…")
                                : jobShelf.win.jobText(jobShelf.win.job, jobShelf.win.local("جارٍ تنفيذ العملية", "Working"))
                            if (jobShelf.subject && !jobShelf.win.waitingForJob)
                                return jobShelf.win.localName(jobShelf.subject) + "  ·  " + words
                            if (jobShelf.items.length > 1 && !jobShelf.win.waitingForJob)
                                return jobShelf.win.appsCountText(jobShelf.items.length) + "  ·  " + words
                            return words
                        }
                        color: jobShelf.win.txt
                        font.family: jobShelf.win.uiFont
                        font.pixelSize: jobShelf.win.typePx(14)
                        font.weight: Font.DemiBold
                        elide: Text.ElideRight
                    }
                    Text {
                        visible: jobShelf.win.job.progress !== null && jobShelf.win.job.progress !== undefined
                                 && jobShelf.win.jobIsActive()
                        text: jobShelf.win.ltr(Math.round(jobShelf.win.job.progress || 0) + "%")
                        color: jobShelf.win.accent
                        font.family: jobShelf.win.uiFont
                        font.pixelSize: jobShelf.win.typePx(13)
                        font.weight: Font.Bold
                    }
                }
                Rectangle {
                    id: jobProgressTrack
                    Layout.fillWidth: true
                    Layout.preferredHeight: jobShelf.win.fs(6)
                    visible: jobShelf.win.jobIsActive()
                    radius: height / 2
                    color: jobShelf.win.tint(jobShelf.win.txt, jobShelf.win.lightScheme ? 0.10 : 0.12)
                    clip: true
                    // Progress runs the way the window reads. Inside, the fill and the sweep are laid
                    // out left to right; in Arabic the whole track is drawn mirrored, so both run
                    // from the right.
                    LayoutMirroring.enabled: false
                    LayoutMirroring.childrenInherit: true
                    transform: Scale { origin.x: jobProgressTrack.width / 2; xScale: jobShelf.win.rtl ? -1 : 1 }
                    Rectangle {
                        visible: jobShelf.win.job.progress !== null && jobShelf.win.job.progress !== undefined
                        height: parent.height
                        radius: height / 2
                        width: parent.width * Math.max(0, Math.min(100, jobShelf.win.job.progress || 0)) / 100
                        anchors.left: parent.left
                        color: jobShelf.win.accent
                        Behavior on width { NumberAnimation { duration: jobShelf.win.motionEnabled ? jobShelf.design.motionGeometry : 0; easing.type: Easing.OutCubic } }
                    }
                    Rectangle {
                        id: jobProgressIndeterminate
                        visible: jobShelf.win.job.progress === null || jobShelf.win.job.progress === undefined
                        width: jobProgressTrack.width * 0.28
                        height: jobProgressTrack.height
                        radius: height / 2
                        color: jobShelf.win.accent
                        // The one endless motion of the window, and only while a job runs.
                        SequentialAnimation on x {
                            running: jobProgressIndeterminate.visible && jobShelf.win.jobIsActive() && jobShelf.win.motionEnabled
                            loops: Animation.Infinite
                            NumberAnimation {
                                from: -jobProgressIndeterminate.width
                                to: jobProgressTrack.width
                                duration: jobShelf.win.motionEnabled ? jobShelf.design.motionPortal * 3 : 0
                                easing.type: Easing.InOutQuad
                            }
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    visible: jobShelf.win.jobIsTerminal() && jobShelf.win.job.state !== "success"
                    text: jobShelf.win.job.state === "partial"
                        ? jobShelf.win.local("انتهى بعضها ولم ينتهِ بعضها.", "Some finished and some did not.")
                        : jobShelf.win.job.state === "cancelled" ? jobShelf.win.local("أُلغي قبل أن يكتمل.", "Cancelled before it finished.")
                        // The backend's own sentence, unless the line above already says it.
                        : (jobShelf.win.job.message || "") !== ""
                          && jobShelf.win.jobText(jobShelf.win.job, "") !== jobShelf.win.job.message
                            ? jobShelf.win.job.message
                        : jobShelf.win.local("يمكنك المحاولة مجددًا.", "You can try again.")
                    color: jobShelf.win.txt2
                    font.family: jobShelf.win.uiFont
                    font.pixelSize: jobShelf.win.typePx(12)
                    elide: Text.ElideRight
                }
            }
            ActionButton {
                win: jobShelf.win
                visible: win.jobIsActive()
                enabled: !win.waitingForJob
                label: win.rtl ? "إلغاء" : "Cancel"
                pill: true
                compact: true
                destructive: true
                triggered: function() { jobShelf.win.cancelJob() }
            }
            ActionButton {
                win: jobShelf.win
                visible: jobShelf.win.jobIsTerminal()
                label: jobShelf.win.local("إخفاء", "Dismiss")
                pill: true
                compact: true
                triggered: function() { jobShelf.win.job = ({}) }
            }
        }
    }
}
