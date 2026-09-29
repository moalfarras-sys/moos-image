import QtQuick
import QtQuick.Layouts

// Teach Mira the owner's voice: record through the Echo itself, train here, install with read-back.
Glass {
    id: coach
    radius: 18
    implicitHeight: col.implicitHeight + 32
    readonly property var e: mira.enrol
    readonly property bool recording: e.recording !== undefined && e.recording !== ""
    readonly property var report: e.report || ({})

    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16 }
        spacing: 10

        SectionTitle { icon: "mic"; text: mira.s.enrol_title; accent: Theme.rose }
        T { Layout.fillWidth: true; text: mira.s.enrol_body; font.pixelSize: Theme.small; color: Theme.ink2 }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            PillButton { text: mira.s.enrol_record_mira; iconName: "mic"; primary: true
                enabled: !coach.recording && mira.echo.online === true && !coach.e.training
                onClicked: mira.enrolRecord("mira") }
            PillButton { text: mira.s.enrol_record_other; iconName: "chat"
                enabled: !coach.recording && mira.echo.online === true && !coach.e.training
                onClicked: mira.enrolRecord("other") }
        }

        // live recording feedback: the real microphone level from the Echo
        Rectangle {
            Layout.fillWidth: true
            visible: coach.recording
            height: 8; radius: 4
            color: Qt.rgba(1, 1, 1, 0.08)
            Rectangle {
                width: parent.width * Math.min(1, mira.level * 1.4); height: parent.height; radius: 4
                color: Theme.mint
                Behavior on width { SmoothedAnimation { velocity: 900 } }
            }
        }

        T {
            Layout.fillWidth: true
            text: mira.s.enrol_counts.replace("{mira}", coach.e.mira || 0).replace("{other}", coach.e.other || 0)
                  + (coach.e.message ? "  ·  " + coach.e.message : "")
            font.pixelSize: Theme.small
            color: coach.recording ? Theme.mint : Theme.ink2
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.hairline }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            PillButton { text: mira.s.enrol_train; iconName: "sparkle"
                enabled: (coach.e.mira || 0) >= 3 && !coach.e.training && !coach.recording
                onClicked: mira.enrolTrain() }
            PillButton { text: mira.s.enrol_install; iconName: "echo"; primary: coach.report.status === "ok"
                enabled: coach.report.status === "ok" && coach.e.model !== "" && !coach.e.installing && mira.echo.online === true
                onClicked: mira.enrolInstall() }
            Item { Layout.fillWidth: true }
        }

        // training result, stated as measured on held-out recordings
        Column {
            Layout.fillWidth: true
            visible: coach.report.status === "ok"
            spacing: 4
            T { width: parent.width; font.pixelSize: Theme.small; color: Theme.ink
                text: mira.s.enrol_recall.replace("{hit}", coach.report.holdout_hits !== undefined ? coach.report.holdout_hits : "—")
                                        .replace("{total}", coach.report.holdout_total !== undefined ? coach.report.holdout_total : "—")
                      + (coach.report.cutoff !== undefined ? "  ·  cutoff " + coach.report.cutoff : "") }
            T { width: parent.width; font.pixelSize: Theme.small; color: Theme.ink2
                text: mira.s.enrol_false.replace("{rate}", coach.report.false_per_hour !== undefined ? coach.report.false_per_hour : "—") }
        }

        T {
            Layout.fillWidth: true
            visible: (coach.e.active || []).length > 0
            text: mira.s.enrol_active.replace("{words}", (coach.e.active || []).join(" · "))
            font.pixelSize: Theme.small; color: Theme.cyan
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            PillButton { text: mira.s.enrol_rollback; iconName: "refresh"; size: Theme.small; implicitHeight: 32
                enabled: (coach.e.active || []).indexOf("mira_ar_owner") >= 0 && !coach.e.installing
                onClicked: mira.enrolRollback() }
            PillButton { text: mira.s.enrol_delete; iconName: "x"; danger: true; size: Theme.small; implicitHeight: 32
                enabled: ((coach.e.mira || 0) + (coach.e.other || 0)) > 0 && !coach.recording && !coach.e.training
                onClicked: mira.enrolClear() }
            Item { Layout.fillWidth: true }
        }
        T { Layout.fillWidth: true; text: mira.s.enrol_privacy; font.pixelSize: Theme.tiny; color: Theme.ink3 }
    }
}
