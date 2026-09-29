import QtQuick

// Short, honest outcome notices (verified / unverified / failed), stacked at the top.
Column {
    id: toasts
    spacing: 8
    width: 460
    function show(kind, text) {
        if (!text) return
        model.append({ kind: kind, text: text })
        if (model.count > 3) model.remove(0)
    }
    ListModel { id: model }
    Repeater {
        model: model
        delegate: Rectangle {
            id: t
            required property int index
            required property string kind
            required property string text
            readonly property color c: kind === "ok" ? Theme.ok : kind === "pending" ? Theme.amber : kind === "error" ? Theme.danger : Theme.cyan
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(toasts.width, row.implicitWidth + 32)
            height: Math.max(42, label.implicitHeight + 20)
            radius: height / 2
            color: Qt.rgba(0.05, 0.06, 0.14, 0.95)
            border.width: 1; border.color: Qt.rgba(c.r, c.g, c.b, 0.45)
            opacity: 0
            Component.onCompleted: { opacity = 1; life.start() }
            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
            Row {
                id: row
                anchors.centerIn: parent
                spacing: 9
                Icon { name: t.kind === "ok" ? "check" : t.kind === "info" ? "sparkle" : t.kind === "pending" ? "clock" : "alert"; size: 17; weight: 2.1; color: t.c; anchors.verticalCenter: parent.verticalCenter }
                T { id: label; text: t.text; font.pixelSize: Theme.small + 1; width: Math.min(implicitWidth, toasts.width - 70); anchors.verticalCenter: parent.verticalCenter; maximumLineCount: 3; elide: Text.ElideRight }
            }
            Timer { id: life; interval: 3600; onTriggered: t.opacity = 0 }
            Timer { interval: 4000; running: true; onTriggered: { for (let i = 0; i < model.count; ++i) if (model.get(i).text === t.text) { model.remove(i); break } } }
        }
    }
}
