import QtQuick
import QtQuick.Controls.Basic

// One conversation entry: your words, Mira's formatted words, or a verified action card.
// Every entry can be copied (its button shows on hover or keyboard focus; right-click copies too);
// Mira's last plain reply offers a fresh answer, and a question that ended only in an error offers
// «Try again»; an entry that opens an earlier day carries that day's separator (the view's `day`
// section, once the chat model has that role). A link shows where it really goes before it opens.
Item {
    id: d
    required property string role
    required property string text
    required property string time
    required property string status
    required property string title
    required property int index

    // The chat's history object (the controller's chatHistory) is looked up by name: until the controller
    // exposes it, an entry shows plain text and offers no control that could not work.
    readonly property var history: mira["chatHistory"] || null
    readonly property bool isUser: role === "user"
    readonly property bool isMira: role === "mira"
    readonly property bool isCard: role === "action" || role === "error"
    readonly property bool isLast: ListView.view ? index === ListView.view.count - 1 : false
    readonly property bool askAgain: isLast && history !== null && history.state.canRegenerate === true && !mira.busy
    readonly property bool canRegenerate: askAgain && isMira && history.state.retry !== true
    readonly property bool canRetry: askAgain && role === "error" && history.state.retry === true
    readonly property bool showTools: hover.hovered || copyBtn.activeFocus || regenBtn.activeFocus
                                      || cardCopy.activeFocus || retryBtn.activeFocus
    readonly property bool rich: isMira && history !== null
    // Mira's reply in pieces: formatted words, and each fenced code block as its own card
    readonly property var pieces: rich ? history.pieces(text) : [{ kind: "plain", html: text, code: "", lang: "" }]
    readonly property bool hasCode: rich && pieces.some(function(piece) { return piece.kind === "code" })
    // a verified result, a job still running, a failure, or something this computer cannot do (neutral)
    readonly property color cardColor: status === "ok" ? Theme.ok : status === "pending" || status === "partial" ? Theme.amber
                                     : status === "unsupported" ? Theme.ink2 : Theme.danger
    readonly property string cardIcon: status === "ok" ? "check" : status === "pending" || status === "partial" ? "clock"
                                     : status === "unsupported" ? "x" : "alert"

    // day separator: where an earlier day begins, and where today begins after one
    readonly property string day: ListView.section
    readonly property string previousDay: ListView.previousSection
    readonly property string today: Qt.formatDate(new Date(), "yyyy-MM-dd")
    readonly property bool newDay: day !== "" && day !== previousDay && (day !== today || previousDay !== "")

    property real maxBubble: width * 0.86
    property real rise: 0
    width: ListView.view ? ListView.view.width : 300
    height: sep.height + body.height + 14
    transform: Translate { y: d.rise }

    // The newest entry fades in and rises into place; entries made while scrolling back do not.
    ParallelAnimation {
        id: appear
        NumberAnimation { target: d; property: "opacity"; from: 0; to: 1; duration: Theme.normal }
        NumberAnimation { target: d; property: "rise"; from: 22; to: 0; duration: Theme.normal; easing.type: Easing.OutCubic }
    }
    Component.onCompleted: if (isLast) appear.start()

    // a small control of one entry (copy, a fresh answer)
    component MiniButton: AbstractButton {
        id: mb
        property string iconName: "copy"
        property string tip: ""
        property string label: ""
        property color accent: Theme.ink2
        implicitWidth: label.length > 0 ? row.implicitWidth + 18 : 26
        implicitHeight: 26
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: tip
        ToolTip.visible: hovered && tip.length > 0
        ToolTip.text: tip
        ToolTip.delay: 450
        background: Rectangle {
            radius: height / 2
            color: mb.down ? Theme.glassHover : mb.hovered ? Qt.rgba(1, 1, 1, 0.10)
                 : mb.label.length > 0 ? Qt.rgba(0.61, 0.48, 1, 0.12) : "transparent"
            border.width: mb.visualFocus ? 2 : mb.label.length > 0 ? 1 : 0
            border.color: mb.visualFocus ? Theme.cyan : Qt.rgba(0.72, 0.55, 1, 0.30)
        }
        contentItem: Item {
            Row {
                id: row
                anchors.centerIn: parent
                spacing: 5
                Icon { name: mb.iconName; size: 14; weight: 2; color: mb.hovered ? Theme.ink : mb.accent; anchors.verticalCenter: parent.verticalCenter }
                T { visible: mb.label.length > 0; text: mb.label; font.pixelSize: Theme.tiny + 1; font.weight: Font.Medium
                    color: mb.hovered ? Theme.ink : Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
            }
        }
        scale: down ? 0.92 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
    }

    HoverHandler { id: hover }

    Item {
        id: sep
        visible: d.newDay
        width: parent.width
        height: visible ? 40 : 0
        Rectangle {
            anchors { left: parent.left; right: dayChip.left; rightMargin: 10; verticalCenter: dayChip.verticalCenter }
            height: 1; color: Theme.hairline
        }
        Rectangle {
            id: dayChip
            anchors.horizontalCenter: parent.horizontalCenter
            y: 10
            height: 24; radius: 12
            width: dayText.implicitWidth + 22
            color: Qt.rgba(1, 1, 1, 0.05)
            border.width: 1; border.color: Theme.hairline
            T {
                id: dayText
                objectName: "dayChipText"
                anchors.centerIn: parent
                text: d.newDay ? (d.history ? d.history.dayLabel(d.day, mira.lang) : d.day) : ""
                font.pixelSize: Theme.tiny + 1; font.weight: Font.Medium; color: Theme.ink2; wrapMode: Text.NoWrap
            }
        }
        Rectangle {
            anchors { left: dayChip.right; right: parent.right; leftMargin: 10; verticalCenter: dayChip.verticalCenter }
            height: 1; color: Theme.hairline
        }
    }

    Item {
        id: body
        // a reply with code takes the full bubble width (a code card reads best wide)
        width: d.isCard ? d.width
                        : d.hasCode ? d.maxBubble
                        : Math.min(d.maxBubble, Math.max(measure.implicitWidth + 32, metaRow.implicitWidth + 24))
        height: d.isCard ? card.height : bubble.height
        anchors.right: d.isUser ? parent.right : undefined
        anchors.left: d.isUser ? undefined : parent.left
        y: sep.height + 7

        // chat bubble
        Rectangle {
            id: bubble
            visible: !d.isCard
            width: parent.width
            height: words.height + metaRow.height + 16
            radius: 18
            color: d.isUser ? Qt.rgba(0.21, 0.72, 0.95, 0.16) : Qt.rgba(0.62, 0.48, 1.0, 0.13)
            border.width: 1
            border.color: d.isUser ? Qt.rgba(0.3, 0.8, 1, 0.28) : Qt.rgba(0.72, 0.55, 1, 0.24)
            Accessible.role: Accessible.StaticText
            Accessible.name: (d.isUser ? mira.s.you : mira.s.mira) + ": " + d.text

            // the words' natural width, before wrapping (a reply without code is one piece)
            Text {
                id: measure
                visible: false
                text: d.hasCode ? "" : d.pieces[0].html
                textFormat: d.rich ? Text.RichText : Text.PlainText
                wrapMode: Text.NoWrap
                font.family: Theme.font
                font.pixelSize: Theme.body
            }
            Column {
                id: words
                objectName: "bubblePieces"
                anchors.left: parent.left; anchors.leftMargin: 15
                y: 11
                width: Math.max(10, parent.width - 30)
                spacing: 8
                Repeater {
                    model: d.pieces
                    delegate: Item {
                        id: piece
                        required property var modelData
                        readonly property bool code: modelData.kind === "code"
                        width: words.width
                        height: code ? codeCard.height : pieceText.height

                        TextEdit {
                            id: pieceText
                            visible: !piece.code
                            width: parent.width
                            text: piece.code ? "" : piece.modelData.html
                            textFormat: piece.modelData.kind === "plain" ? TextEdit.PlainText : TextEdit.RichText
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                            color: Theme.ink
                            selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
                            font.family: Theme.font
                            font.pixelSize: Theme.body
                            // only an address the window may open is a link at all (chat_ui.openable); asked again here
                            onLinkActivated: function(link) { if (d.history && d.history.openable(link)) mira.openUrl(link) }
                            HoverHandler { cursorShape: pieceText.hoveredLink !== "" ? Qt.PointingHandCursor : Qt.IBeamCursor }
                            // where the link really goes, whatever its words say
                            ToolTip.visible: hoveredLink !== "" && d.history !== null
                            ToolTip.text: hoveredLink !== "" && d.history ? mira.s.ch_opens + "  " + d.history.linkLabel(hoveredLink) : ""
                            ToolTip.delay: 250
                        }

                        // a code block: a rounded card that reads left to right in both languages
                        Rectangle {
                            id: codeCard
                            objectName: "codeCard"
                            visible: piece.code
                            width: parent.width
                            height: visible ? codeHead.height + codeText.height + 14 : 0
                            radius: 12
                            color: "#0B0F26"
                            border.width: 1
                            border.color: Qt.rgba(0.47, 0.55, 1, 0.18)
                            LayoutMirroring.enabled: false
                            LayoutMirroring.childrenInherit: true
                            Item {
                                id: codeHead
                                width: parent.width
                                height: 32
                                T {
                                    anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                                    text: piece.modelData.lang || mira.s.ch_code
                                    font.family: piece.modelData.lang ? Theme.mono : Theme.font
                                    font.pixelSize: Theme.tiny; font.letterSpacing: 0.3
                                    color: Theme.ink3; wrapMode: Text.NoWrap
                                }
                                MiniButton {
                                    objectName: "copyCode"
                                    anchors { right: parent.right; rightMargin: 5; verticalCenter: parent.verticalCenter }
                                    iconName: "copy"
                                    label: mira.s.ch_copy_code
                                    tip: mira.s.ch_copy_code_tip
                                    onClicked: mira.copyText(piece.modelData.code)
                                }
                                Rectangle {
                                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                                    height: 1; color: Qt.rgba(0.47, 0.55, 1, 0.12)
                                }
                            }
                            TextEdit {
                                id: codeText
                                anchors { left: parent.left; right: parent.right; top: codeHead.bottom; leftMargin: 12; rightMargin: 12; topMargin: 7 }
                                text: piece.code ? piece.modelData.html : ""
                                textFormat: TextEdit.RichText
                                readOnly: true
                                selectByMouse: true
                                wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                                selectionColor: Qt.rgba(0.35, 0.8, 1, 0.35)
                                font.family: Theme.mono
                                font.pixelSize: 13
                            }
                        }
                    }
                }
            }
            Item {
                id: metaRow
                anchors { left: parent.left; right: parent.right; top: words.bottom; leftMargin: 15; rightMargin: 8; topMargin: 3 }
                height: 26
                implicitWidth: meta.implicitWidth + tools.implicitWidth + 16
                T {
                    id: meta
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: (d.isUser ? mira.s.you : mira.s.mira) + " · " + d.time
                    font.pixelSize: Theme.tiny; color: Theme.ink3; wrapMode: Text.NoWrap
                }
                Row {
                    id: tools
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    MiniButton {
                        id: regenBtn
                        visible: d.canRegenerate
                        iconName: "refresh"
                        label: mira.s.ch_regenerate
                        tip: mira.s.ch_regenerate_tip
                        accent: Theme.violet
                        onClicked: d.history.regenerate()
                    }
                    MiniButton {
                        id: copyBtn
                        iconName: "copy"
                        tip: mira.s.ch_copy
                        opacity: d.showTools ? 1 : 0
                        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                        onClicked: mira.copyText(d.text)
                    }
                }
            }
        }

        // verified action card
        Rectangle {
            id: card
            visible: d.isCard
            width: parent.width
            height: Math.max(46, cardBody.height + 20)
            radius: 14
            color: Qt.rgba(d.cardColor.r, d.cardColor.g, d.cardColor.b, d.status === "unsupported" ? 0.05 : 0.08)
            border.width: 1
            border.color: Qt.rgba(d.cardColor.r, d.cardColor.g, d.cardColor.b, d.status === "unsupported" ? 0.22 : 0.30)
            Accessible.role: Accessible.StaticText
            Accessible.name: d.text
            Rectangle {
                id: badge
                anchors.left: parent.left; anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                width: 26; height: 26; radius: 13
                color: Qt.rgba(d.cardColor.r, d.cardColor.g, d.cardColor.b, 0.18)
                Icon {
                    anchors.centerIn: parent; size: 15; weight: 2.2
                    name: d.cardIcon
                    color: d.cardColor
                }
            }
            // the result's words; «Try again» sits under them when the question got only this error
            Column {
                id: cardBody
                anchors.left: badge.right; anchors.leftMargin: 10
                anchors.right: cardCopy.left; anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8
                T {
                    id: cardText
                    width: parent.width
                    text: d.text
                    font.pixelSize: Theme.small + 1
                    color: Theme.ink
                    maximumLineCount: 4
                    elide: Text.ElideRight
                }
                MiniButton {
                    id: retryBtn
                    visible: d.canRetry
                    anchors.left: parent.left
                    iconName: "refresh"
                    label: mira.s.ch_retry
                    tip: mira.s.ch_retry_tip
                    accent: Theme.violet
                    onClicked: d.history.regenerate()
                }
            }
            MiniButton {
                id: cardCopy
                anchors.right: stamp.left; anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                iconName: "copy"
                tip: mira.s.ch_copy
                opacity: d.showTools ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                onClicked: mira.copyText(d.text)
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
