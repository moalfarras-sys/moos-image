import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes

// System changes waiting for the owner, and the jobs he approved, as live glass cards.
// «موافقة» and «إلغاء» are the OWNER's buttons: nothing here runs on Mira's own say-so,
// and a card that times out runs nothing. Newest card sits nearest the dock.
Item {
    id: stack
    property real now: Date.now()
    property int maxCards: 3
    readonly property int shown: Math.min(list.count, maxCards)
    implicitHeight: list.contentHeight
    height: Math.min(list.contentHeight, 3 * 176)
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
        add: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.emphasized }
                NumberAnimation { property: "scale"; from: 0.94; to: 1; duration: Theme.emphasized; easing.type: Easing.OutBack }
            }
        }
        displaced: Transition { NumberAnimation { properties: "y"; duration: Theme.normal; easing.type: Easing.OutCubic } }
        remove: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Theme.normal } }

        delegate: Glass {
            id: card
            required property string aid
            required property string title
            required property string detail
            required property string stage
            required property string category
            required property string summary
            required property string output
            required property real started
            required property real expires
            property bool open: false
            readonly property color c: stack.tone(stage)
            readonly property bool asking: stage === "ask"
            readonly property bool running: stage === "running"
            readonly property real remaining: asking && expires > 0 ? Math.max(0, expires - stack.now) : 0

            width: ListView.view.width
            height: body.implicitHeight + 28
            radius: 20
            tint: Theme.glassStrong
            edge: Qt.rgba(c.r, c.g, c.b, asking ? 0.55 : 0.38)
            Accessible.role: Accessible.AlertMessage
            Accessible.name: title + " · " + (summary || detail)

            // a slow breath around a card that waits for the owner
            Rectangle {
                anchors.fill: parent
                anchors.margins: -4
                radius: parent.radius + 4
                color: "transparent"
                border.width: 2
                border.color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.35)
                visible: card.asking
                opacity: 0.3
                SequentialAnimation on opacity {
                    running: card.asking && mira.motion
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
                        Rectangle {
                            anchors.fill: parent
                            radius: width / 2
                            color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.16)
                            border.width: 1; border.color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.45)
                        }
                        Icon { anchors.centerIn: parent; name: stack.glyph(card.stage, card.category); size: 20; weight: 2; color: card.c }
                        Shape {
                            anchors.fill: parent
                            visible: card.running
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                strokeColor: card.c; strokeWidth: 2.4; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                                PathAngleArc { centerX: 21; centerY: 21; radiusX: 19.5; radiusY: 19.5; startAngle: -90; sweepAngle: 110 }
                            }
                            RotationAnimation on rotation { running: card.running && mira.motion; from: 0; to: 360; duration: 1300; loops: Animation.Infinite }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            T { text: card.title; font.pixelSize: Theme.title; font.weight: Font.DemiBold; wrapMode: Text.NoWrap; elide: Text.ElideRight; Layout.fillWidth: true }
                            Rectangle {
                                visible: card.asking || card.running
                                radius: 9; height: 20
                                width: badge.implicitWidth + 16
                                color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.14)
                                border.width: 1; border.color: Qt.rgba(card.c.r, card.c.g, card.c.b, 0.35)
                                Row {
                                    id: badge
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Icon { name: card.category === "privileged_confirm" ? "lock" : "shield"; size: 12; weight: 2; color: card.c; anchors.verticalCenter: parent.verticalCenter }
                                    T { text: card.category === "privileged_confirm" ? mira.s.act_needs_password : mira.s.act_change; font.pixelSize: Theme.tiny; color: card.c; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
                                }
                            }
                        }
                        T {
                            Layout.fillWidth: true
                            text: card.summary !== "" && !card.asking ? card.summary : card.detail
                            visible: text !== ""
                            font.pixelSize: Theme.small + 1
                            color: Theme.ink2
                            maximumLineCount: 2; elide: Text.ElideRight
                        }
                        T {
                            Layout.fillWidth: true
                            visible: card.asking || card.running
                            text: card.asking ? (card.category === "privileged_confirm" ? mira.s.act_password + " · " : "") + mira.s.act_voice_hint
                                              : mira.s.act_elapsed.replace("{t}", stack.clock(stack.now - card.started))
                            font.pixelSize: Theme.tiny + 1
                            color: Theme.ink3
                            wrapMode: Text.NoWrap; elide: Text.ElideRight
                        }
                    }

                    // the owner's answer
                    Row {
                        visible: card.asking
                        spacing: 8
                        Layout.alignment: Qt.AlignVCenter
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

                // what really came back (the executor's own output)
                Rectangle {
                    Layout.fillWidth: true
                    visible: card.open && card.output !== ""
                    Layout.preferredHeight: Math.min(200, outText.implicitHeight + 20)
                    radius: 12
                    color: Qt.rgba(0, 0, 0, 0.32)
                    border.width: 1; border.color: Theme.hairline
                    Flickable {
                        anchors.fill: parent; anchors.margins: 10
                        contentHeight: outText.implicitHeight
                        clip: true
                        TextEdit {
                            id: outText
                            width: parent.width
                            readOnly: true; selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            text: card.output
                            color: Theme.ink2
                            font.family: Theme.mono; font.pixelSize: 11
                            LayoutMirroring.enabled: false
                            horizontalAlignment: Text.AlignLeft
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
                    width: parent.width * Math.min(1, card.remaining / 180000)
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
