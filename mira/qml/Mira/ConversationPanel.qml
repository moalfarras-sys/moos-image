import QtQuick
import QtQuick.Controls.Basic

// The conversation: words and verified results, newest at the bottom.
Glass {
    id: panel
    radius: Theme.rPanel
    property bool showHeader: true
    signal suggestion(string text)

    Item {
        id: header
        visible: panel.showHeader
        height: visible ? 44 : 0
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        SectionTitle { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; icon: "chat"; text: mira.s.conversation; accent: Theme.violet }
        IconButton {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            diameter: 30; iconName: "x"; tip: mira.s.clear_view
            visible: list.count > 0
            onClicked: mira.clearView()
        }
    }

    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: parent.bottom; margins: 14; topMargin: 4 }
        clip: true
        model: mira.chatModel
        spacing: 2
        boundsBehavior: Flickable.StopAtBounds
        delegate: MessageDelegate {}
        // Follow the newest entry until the owner scrolls up to read; scrolling back down resumes it.
        property bool follow: true
        onMovementEnded: follow = atYEnd
        onContentHeightChanged: if (follow) Qt.callLater(positionViewAtEnd)
        onCountChanged: if (follow) Qt.callLater(positionViewAtEnd)
        onHeightChanged: if (follow) Qt.callLater(positionViewAtEnd)
        Component.onCompleted: Qt.callLater(positionViewAtEnd)
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; width: 6 }
        add: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.normal }
            NumberAnimation { property: "y"; from: list.contentHeight; duration: Theme.normal; easing.type: Easing.OutCubic }
        }
    }

    // empty state that teaches
    Column {
        anchors.centerIn: parent
        width: parent.width - 48
        spacing: 12
        visible: list.count === 0
        Icon { anchors.horizontalCenter: parent.horizontalCenter; name: "sparkle"; size: 30; color: Theme.violet }
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: mira.s.empty_chat_title; font.pixelSize: Theme.title; font.weight: Font.DemiBold }
        T { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: mira.s.empty_chat_body; color: Theme.ink2; font.pixelSize: Theme.small + 1 }
        Flow {
            width: parent.width
            spacing: 8
            layoutDirection: mira.lang === "ar" ? Qt.RightToLeft : Qt.LeftToRight
            Repeater {
                model: [mira.s.sg_home_status, mira.s.sg_weather, mira.s.sg_pc_status, mira.s.sg_browser]
                delegate: PillButton { required property string modelData; text: modelData; size: Theme.small; implicitHeight: 32; onClicked: panel.suggestion(modelData) }
            }
        }
    }
}
