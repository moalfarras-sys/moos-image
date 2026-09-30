import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes

// System changes waiting for the owner, and the jobs he approved, as live glass cards.
// «موافقة» and «إلغاء» are the OWNER's buttons: nothing here runs on Mira's own say-so,
// and a card that times out runs nothing. Newest card sits nearest the dock.
// An agent card (kind "agent", inbox.py) shows the exact command or file content the Mo AI
// agent asks to run or write, as plain text, before the owner allows it once or denies it.
// Only one agent request is open for review at a time; the others wait folded, with no Allow
// button, so an Allow is never on screen while its request is not.
Item {
    id: stack
    property real now: Date.now()
    property int maxCards: 3
    // the room above the dock (Main.qml sets it to the space below the top bar; this is a fallback)
    property real maxHeight: parent ? Math.max(240, parent.height - 170) : 3 * 176
    // the agent request open for review ("" = none); the one that expires first is chosen
    property string reviewAid: ""
    // the cards stand over words (the conversation beside a page, or the page itself): every card
    // is then solid, so no line of the chat reads through it (Main.qml sets it)
    property bool overText: false
    property var offers: []
    // the tallest an exact-request box may be, so an open agent card fits in the stack
    readonly property real boxMax: Math.max(96, Math.min(240, maxHeight - 290))
    readonly property int shown: Math.min(list.count, maxCards)
    implicitHeight: list.contentHeight
    height: Math.min(list.contentHeight, maxHeight)
    visible: list.count > 0

    Timer { interval: 1000; repeat: true; running: stack.visible; onTriggered: stack.now = Date.now() }

    function clock(ms) {
        var s = Math.max(0, Math.round(ms / 1000)), m = Math.floor(s / 60)
        s = s % 60
        return m + ":" + (s < 10 ? "0" : "") + s
    }
    function tone(state) {
        return state === "ask" ? Theme.amber : state === "running" ? Theme.violet : state === "ok" ? Theme.ok
             : state === "error" ? Theme.danger : Theme.off
    }
    function glyph(state, category) {
        return state === "ask" ? (category === "privileged_confirm" ? "lock" : "shield") : state === "running" ? "bolt"
             : state === "ok" ? "check" : state === "error" ? "alert" : "clock"
    }
    // a waiting agent card asks to be the open one; the one that expires first wins
    function offer(aid, expires) {
        offers = offers.concat([{ aid: aid, expires: expires }])
        election.restart()
    }
    // cards beyond the visible part of the list are created a moment later: let them all offer
    Timer { id: election; interval: 250; onTriggered: stack.elect() }
    function elect() {
        if (reviewAid === "" && offers.length > 0) {
            var best = offers[0]
            for (var i = 1; i < offers.length; ++i)
                if (offers[i].expires > 0 && (best.expires <= 0 || offers[i].expires < best.expires))
                    best = offers[i]
            reviewAid = best.aid
        }
        offers = []
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: parent.height
        model: mira.actionModel
        spacing: 10
        clip: true
        interactive: contentHeight > height
        verticalLayoutDirection: ListView.BottomToTop
        boundsBehavior: Flickable.StopAtBounds
        cacheBuffer: 100000          // a handful of cards: keep every delegate (and which one is open)
        add: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.emphasized }
                NumberAnimation { property: "scale"; from: 0.94; to: 1; duration: Theme.emphasized; easing.type: Easing.OutBack }
            }
        }
        displaced: Transition { NumberAnimation { properties: "y"; duration: Theme.normal; easing.type: Easing.OutCubic } }
        remove: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.normal } }
        // more cards than room: a visible rail says the stack scrolls
        ScrollBar.vertical: ScrollBar {
            policy: list.interactive ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
            width: 6
            contentItem: Rectangle { implicitWidth: 5; radius: 2.5; color: Qt.rgba(1, 1, 1, 0.55) }
            background: Rectangle { implicitWidth: 5; radius: 2.5; color: Qt.rgba(1, 1, 1, 0.08) }
        }

        delegate: Glass {
            id: card
            required property int index
            required property string aid
            required property string kind
            required property string title
            required property string detail
            required property string reason
            required property string stage
            required property string category
            required property string summary
            required property string output
            required property real started
            required property real expires
            property bool open: false
            // too narrow for the text and both answers on one line (the conversation column): the
            // answers get their own line, so the request is never cut to fit them
            readonly property bool narrow: width < 460
            readonly property color c: stack.tone(stage)
            readonly property bool asking: stage === "ask"
            readonly property bool running: stage === "running"
            readonly property bool agent: kind === "agent"
            readonly property bool agentAsk: agent && asking
            // an agent request waiting behind the open one: title and place only, no Allow
            readonly property bool folded: agentAsk && stack.reviewAid !== aid
            readonly property bool reviewing: agentAsk && !folded
            // Allow comes alive a moment after the request opens: a double click never allows
            property bool armed: false
            // ... and only while the card's title and place are on screen (unless it cannot fit at all)
            readonly property bool headerInView: y >= list.contentY - 1 || height > list.height
            property real openedAt: 0
            // the agent waits 120 s for an answer (moai_runtime); Mo AI's own changes 180 s
            readonly property real lifetime: agent ? 120000 : 180000
            readonly property real remaining: asking && expires > 0 ? Math.max(0, expires - stack.now) : 0

            function claim() {
                if (agentAsk && stack.reviewAid === "")
                    stack.offer(aid, expires)
            }
            onAgentAskChanged: {
                if (!agentAsk && stack.reviewAid === aid)
                    stack.reviewAid = ""
                else
                    claim()
            }
            onReviewingChanged: {
                armed = false
                if (reviewing) {
                    openedAt = Date.now()
                    arming.restart()
                    placing.restart()
                }
            }
            // bring the opened card fully into view once its layout has grown
            onHeightChanged: if (reviewing && Date.now() - openedAt < 1500) placing.restart()
            Component.onCompleted: {
                claim()
                if (reviewing)
                    arming.restart()
            }
            Component.onDestruction: {
                if (stack && stack.reviewAid === aid)
                    stack.reviewAid = ""
            }
            Connections {
                target: stack
                function onReviewAidChanged() { card.claim() }
            }
            Timer { id: arming; interval: 700; onTriggered: card.armed = true }
            Timer { id: placing; interval: 80; onTriggered: list.positionViewAtIndex(card.index, ListView.Contain) }

            width: ListView.view.width
            height: body.implicitHeight + 28
            radius: 20
            // an agent's request is read word for word: nothing from the stage may show through it
            tint: agentAsk || stack.overText ? Qt.rgba(0.055, 0.066, 0.145, 0.985) : Theme.glassStrong
            edge: Qt.rgba(c.r, c.g, c.b, asking ? (folded ? 0.38 : 0.55) : 0.38)
            Accessible.role: Accessible.AlertMessage
            Accessible.name: title + " · " + (summary || detail)
            Accessible.description: agent ? reason + "\n" + output : ""

            // a slow breath around a card that waits for the owner
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: parent.radius + 4
                color: "transparent"
                border.width: 2
                border.color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.35)
                visible: card.asking && !card.folded
                opacity: 0.3
                SequentialAnimation on opacity {
                    running: card.asking && !card.folded && mira.motion
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.9; duration: 1100; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.2; duration: 1100; easing.type: Easing.InOutSine }
                }
            }

            ColumnLayout {
                id: body
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    // status orb; a turning arc while the job runs
                    Item {
                        Layout.preferredWidth: 42; Layout.preferredHeight: 42
                        Layout.alignment: card.agentAsk ? Qt.AlignTop : Qt.AlignVCenter
                        Rectangle {
                            anchors.fill: parent
                            radius: width / 2
                            color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.16)
                            border.width: 1; border.color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.45)
                        }
                        Icon { anchors.centerIn: parent; name: stack.glyph(card.stage, card.category); size: 20; weight: 2; color: card.c }
                        // the turning arc, drawn as an Icon (Mira's 24×24 grid scaled to the 42 px orb) so the
                        // software scene graph clips it with the list like everything else
                        Icon {
                            anchors.fill: parent
                            visible: card.running
                            size: 42
                            weight: 1.37                                  // 2.4 px at 42 px
                            color: card.c
                            path: "M12 0.86A11.14 11.14 0 0 1 22.47 15.81"
                            RotationAnimation on rotation { running: card.running && mira.motion; from: 0; to: 360; duration: 1300; loops: Animation.Infinite }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            T { text: card.title; font.pixelSize: Theme.title; font.weight: Font.DemiBold; Layout.fillWidth: true
                                wrapMode: card.agentAsk ? Text.Wrap : Text.NoWrap; maximumLineCount: card.agentAsk ? 2 : 1; elide: Text.ElideRight }
                            Rectangle {
                                Layout.alignment: Qt.AlignTop
                                Layout.topMargin: 1
                                visible: card.asking || card.running
                                radius: 9; height: 20
                                width: badge.implicitWidth + 16
                                color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.14)
                                border.width: 1; border.color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.35)
                                Row {
                                    id: badge
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Icon { name: card.agent ? "wrench" : card.category === "privileged_confirm" ? "lock" : "shield"; size: 12; weight: 2; color: card.c; anchors.verticalCenter: parent.verticalCenter }
                                    T { text: card.agent ? mira.s.agent_approval_badge : card.category === "privileged_confirm" ? mira.s.act_needs_password : mira.s.act_change; font.pixelSize: Theme.tiny; color: card.c; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
                                }
                            }
                        }
                        // where it happens: an agent request's file and folder are always whole
                        T {
                            Layout.fillWidth: true
                            text: card.summary !== "" && !card.asking ? card.summary : card.detail
                            visible: text !== ""
                            font.pixelSize: Theme.small + 1
                            color: Theme.ink2
                            maximumLineCount: card.agentAsk ? 40 : 2; elide: Text.ElideRight
                        }
                        T {
                            Layout.fillWidth: true
                            visible: (card.asking || card.running) && !card.folded
                            text: card.asking ? (card.agent ? card.reason
                                                            : (card.category === "privileged_confirm" ? mira.s.act_password + " · " : "") + mira.s.act_voice_hint)
                                              : mira.s.act_elapsed.replace("{t}", stack.clock(stack.now - card.started))
                            font.pixelSize: Theme.tiny + 1
                            color: card.agentAsk ? Theme.ink2 : Theme.ink3
                            wrapMode: card.agentAsk || card.narrow ? Text.Wrap : Text.NoWrap
                            maximumLineCount: card.agentAsk ? 40 : card.narrow ? 2 : 1
                            elide: Text.ElideRight
                        }
                    }

                    // the owner's answer (an agent card answers in its footer, after the request);
                    // on a narrow card it moves to its own line below (answerLine)
                    Loader {
                        active: card.asking && !card.agent && !card.narrow
                        visible: active
                        Layout.alignment: Qt.AlignVCenter
                        sourceComponent: answers
                    }
                    Row {
                        visible: !card.asking && !card.running
                        spacing: 6
                        Layout.alignment: Qt.AlignVCenter
                        IconButton {
                            visible: card.output !== ""
                            iconName: "book"; tip: card.open ? mira.s.act_hide : mira.s.act_details
                            onClicked: card.open = !card.open
                        }
                        IconButton { iconName: "x"; tip: mira.s.act_dismiss; onClicked: mira.dismissAction(card.aid) }
                    }
                }

                Loader {
                    objectName: "answerLine"
                    active: card.asking && !card.agent && card.narrow
                    visible: active
                    Layout.alignment: Qt.AlignRight      // the line's end (mirrored in Arabic)
                    sourceComponent: answers
                }
                Component {
                    id: answers
                    Row {
                        spacing: 8
                        PillButton {
                            text: mira.s.act_reject; iconName: "x"; size: Theme.small
                            implicitHeight: 36
                            onClicked: mira.rejectAction(card.aid)
                        }
                        PillButton {
                            text: mira.s.act_approve; iconName: "check"; primary: true; size: Theme.small
                            implicitHeight: 36
                            onClicked: mira.approveAction(card.aid)
                        }
                    }
                }

                // what really came back (the executor's own output); on the agent card under review,
                // the exact command or file content being asked for, always open, as plain text
                Rectangle {
                    id: outBox
                    objectName: "requestBox"
                    Layout.fillWidth: true
                    visible: (card.open || card.reviewing) && card.output !== ""
                    Layout.preferredHeight: Math.min(card.reviewing ? stack.boxMax : 200, outText.implicitHeight + 20)
                    radius: 12
                    color: Qt.rgba(0, 0, 0, card.reviewing ? 0.42 : 0.32)
                    border.width: 1
                    border.color: outText.activeFocus ? Theme.cyan
                                : card.reviewing ? Qt.rgba(card.c.r, card.c.g, card.c.b, 0.32) : Theme.hairline
                    Flickable {
                        id: flick
                        anchors.fill: parent; anchors.margins: 10
                        contentHeight: outText.implicitHeight
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        function scrollBy(dy) {
                            contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height), contentY + dy))
                        }
                        ScrollBar.vertical: ScrollBar {
                            policy: flick.contentHeight > flick.height + 1 ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                            width: 6
                            contentItem: Rectangle { implicitWidth: 4; radius: 2; color: Qt.rgba(1, 1, 1, 0.4) }
                        }
                        TextEdit {
                            id: outText
                            objectName: "requestText"
                            width: flick.width - 10
                            readOnly: true; selectByMouse: true
                            // never markup: an agent writing HTML shows its source, not a rendering of it
                            textFormat: TextEdit.PlainText
                            wrapMode: TextEdit.Wrap
                            text: card.output
                            color: card.reviewing ? Theme.ink : Theme.ink2
                            font.family: Theme.mono; font.pixelSize: 11
                            LayoutMirroring.enabled: false
                            horizontalAlignment: Text.AlignLeft
                            // the keyboard reaches the exact request too, and scrolls it
                            activeFocusOnTab: card.reviewing
                            Accessible.role: Accessible.StaticText
                            Accessible.name: card.output
                            Keys.onPressed: function(event) {
                                var page = Math.max(40, flick.height - 24)
                                if (event.key === Qt.Key_Down) { flick.scrollBy(32); event.accepted = true }
                                else if (event.key === Qt.Key_Up) { flick.scrollBy(-32); event.accepted = true }
                                else if (event.key === Qt.Key_PageDown || event.key === Qt.Key_Space) { flick.scrollBy(page); event.accepted = true }
                                else if (event.key === Qt.Key_PageUp) { flick.scrollBy(-page); event.accepted = true }
                                else if (event.key === Qt.Key_Home) { flick.contentY = 0; event.accepted = true }
                                else if (event.key === Qt.Key_End) { flick.scrollBy(flick.contentHeight); event.accepted = true }
                            }
                        }
                    }
                }

                // an agent request is answered after it is read: the decision sits below the request.
                // A folded request offers "Show request", never Allow.
                GridLayout {
                    visible: card.agentAsk
                    Layout.fillWidth: true
                    // a narrow card puts the note on its own line, above the buttons
                    columns: card.width < 540 ? 1 : 2
                    columnSpacing: 10; rowSpacing: 8
                    T {
                        Layout.fillWidth: true
                        text: card.folded ? mira.s.agent_approval_collapsed
                                          : mira.s.agent_approval_left.replace("{t}", stack.clock(card.remaining))
                        font.pixelSize: Theme.tiny + 1
                        color: Theme.ink3
                    }
                    Row {
                        Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                        spacing: 8
                        PillButton {
                            text: mira.s.agent_approval_deny; iconName: "x"; size: Theme.small
                            implicitHeight: 36
                            onClicked: mira.rejectAction(card.aid)
                        }
                        PillButton {
                            objectName: "showRequest"
                            visible: card.folded
                            text: mira.s.agent_approval_review; iconName: "book"; size: Theme.small
                            implicitHeight: 36
                            onClicked: stack.reviewAid = card.aid
                        }
                        PillButton {
                            objectName: "allowOnce"
                            visible: !card.folded
                            enabled: card.armed && card.headerInView
                            text: mira.s.agent_approval_allow; iconName: "check"; primary: true; size: Theme.small
                            implicitHeight: 36
                            onClicked: mira.approveAction(card.aid)
                        }
                    }
                }
            }

            // time left to answer, or an indeterminate shimmer while the job runs
            Item {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 18; rightMargin: 18; bottomMargin: 6 }
                height: 3
                visible: card.asking || card.running
                clip: true
                Rectangle { anchors.fill: parent; radius: 2; color: Qt.rgba(1, 1, 1, 0.06) }
                Rectangle {
                    visible: card.asking
                    height: parent.height; radius: 2
                    width: parent.width * Math.min(1, card.remaining / card.lifetime)
                    color: card.c
                    opacity: 0.8
                    Behavior on width { NumberAnimation { duration: 950 } }
                }
                Rectangle {
                    id: shimmer
                    visible: card.running
                    height: parent.height; radius: 2
                    width: parent.width * 0.3
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: "transparent" }
                        GradientStop { position: 0.5; color: card.c }
                        GradientStop { position: 1; color: "transparent" }
                    }
                    NumberAnimation on x {
                        running: card.running && mira.motion
                        from: -shimmer.width; to: shimmer.parent.width
                        duration: 1400; loops: Animation.Infinite
                    }
                }
            }
        }
    }
}
