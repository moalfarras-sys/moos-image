import QtQuick
import QtQuick.Controls.Basic

// One conversation entry: your words, Mira's words, or a verified action card.
Item {
    id: d
    required property string role
    required property string text
    required property string time
    required property string status
    required property string title
    required property int index
    property real maxBubble: width * 0.86
    width: ListView.view ? ListView.view.width : 300
    height: body.height + 14

    readonly property bool isUser: role === "user"
    readonly property bool isCard: role === "action" || role === "error"
    readonly property color cardColor: status === "ok" ? Theme.ok : status === "pending" || status === "partial" ? Theme.amber : Theme.danger

    Item {
        id: body
        width: d.isCard ? d.width : Math.min(d.maxBubble, Math.max(measure.implicitWidth, meta.implicitWidth) + 32)
        height: d.isCard ? card.height : bubble.height
        anchors.right: d.isUser ? parent.right : undefined
        anchors.left: d.isUser ? undefined : parent.left
        y: 7

        // chat bubble
        Rectangle {
            id: bubble
            visible: !d.isCard
            width: parent.width
            height: bubbleText.height + meta.height + 22
            radius: 18
            color: d.isUser ? Qt.rgba(0.21, 0.72, 0.95, 0.16) : Qt.rgba(0.62, 0.48, 1.0, 0.13)
            border.width: 1
            border.color: d.isUser ? Qt.rgba(0.3, 0.8, 1, 0.28) : Qt.rgba(0.72, 0.55, 1, 0.24)
            T { id: measure; visible: false; text: d.text; wrapMode: Text.NoWrap; font.pixelSize: Theme.body }
            TextEdit {
                id: bubbleText
                anchors.left: parent.left; anchors.leftMargin: 15
                y: 10
                width: Math.min(d.maxBubble - 30, measure.implicitWidth + 2)
                text: d.text
                readOnly: true
                selectByMouse: true
                wrapMode: TextEdit.Wrap
                color: Theme.ink
                selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
                font.family: Theme.font
                font.pixelSize: Theme.body
                textFormat: TextEdit.PlainText
            }
            T {
                id: meta
                anchors.top: bubbleText.bottom; anchors.topMargin: 4
                anchors.left: parent.left; anchors.leftMargin: 15
                text: (d.isUser ? mira.s.you : mira.s.mira) + " · " + d.time
                font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
            }
        }

        // verified action card
        Rectangle {
            id: card
            visible: d.isCard
            width: parent.width
            height: Math.max(46, cardText.height + 20)
            radius: 14
            color: Qt.rgba(d.cardColor.r, d.cardColor.g, d.cardColor.b, 0.08)
            border.width: 1
            border.color: Qt.rgba(d.cardColor.r, d.cardColor.g, d.cardColor.b, 0.30)
            Rectangle {
                id: badge
                anchors.left: parent.left; anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                width: 26; height: 26; radius: 13
                color: Qt.rgba(d.cardColor.r, d.cardColor.g, d.cardColor.b, 0.18)
                Icon {
                    anchors.centerIn: parent; size: 15; weight: 2.2
                    name: d.status === "ok" ? "check" : d.status === "pending" || d.status === "partial" ? "clock" : "alert"
                    color: d.cardColor
                }
            }
            T {
                id: cardText
                anchors.left: badge.right; anchors.leftMargin: 10
                anchors.right: stamp.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: d.text
                font.pixelSize: Theme.small + 1
                color: Theme.ink
                maximumLineCount: 4
                elide: Text.ElideRight
            }
            T {
                id: stamp
                anchors.right: parent.right; anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                text: d.time; font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
            }
        }
    }

    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: mira.copyText(d.text)
    }
}
