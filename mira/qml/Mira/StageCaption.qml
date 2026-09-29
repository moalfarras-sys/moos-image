import QtQuick

// Under the face: what Mira is doing, and the live words (yours while listening, hers while speaking).
Column {
    id: cap
    property string phase: mira.phase
    spacing: 10

    Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 8
        Rectangle {
            width: 8; height: 8; radius: 4
            anchors.verticalCenter: parent.verticalCenter
            color: Theme.phaseColor(cap.phase, mira.faceStyle)
            Behavior on color { ColorAnimation { duration: Theme.normal } }
        }
        T {
            text: mira.phase === "idle" ? mira.s.phase_idle : (mira.s["phase_" + mira.phase] || "")
            font.pixelSize: Theme.small; font.weight: Font.DemiBold; font.letterSpacing: 1.2
            color: Theme.ink2; wrapMode: Text.NoWrap
        }
    }

    Item {
        width: cap.width
        height: Math.max(captionText.implicitHeight, hint.implicitHeight)
        T {
            id: captionText
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: mira.caption
            visible: opacity > 0
            opacity: mira.caption !== "" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
            maximumLineCount: 3
            elide: Text.ElideLeft
            font.pixelSize: mira.captionRole === "mira" ? 21 : 19
            font.weight: mira.captionRole === "mira" ? Font.Medium : Font.Normal
            color: mira.captionRole === "mira" ? Theme.ink : mira.captionRole === "error" ? Qt.lighter(Theme.danger, 1.25) : Theme.ink2
            lineHeight: 1.15
        }
        T {
            id: hint
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: mira.status
            opacity: mira.caption === "" ? 1 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
            font.pixelSize: Theme.body
            color: Theme.ink3
        }
    }
}
