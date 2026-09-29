import QtQuick
import QtQuick.Controls.Basic

// Mira's destinations, labelled. The top is Mira herself (her live face = the conversation);
// the rest are the pages of the system she runs. `compact` drops the labels for short windows.
Item {
    id: rail
    property string current: ""
    property bool compact: false
    property var badges: ({})
    signal navigate(string name)
    implicitWidth: compact ? 64 : 88

    readonly property var items: [
        { id: "home", icon: "home", label: mira.s.nav_home },
        { id: "pc", icon: "monitor", label: mira.s.nav_pc },
        { id: "apps", icon: "apps", label: mira.s.nav_apps },
        { id: "system", icon: "shield", label: mira.s.nav_system },
        { id: "workbench", icon: "chip", label: mira.s.nav_workbench },
        { id: "connect", icon: "globe", label: mira.s.nav_connect },
        { id: "brain", icon: "sparkle", label: mira.s.nav_brain }
    ]

    component NavButton: AbstractButton {
        id: nb
        property string key: ""
        property string glyph: "sparkle"
        property string label: ""
        property string badge: ""
        readonly property bool active: rail.current === key
        width: rail.width
        height: rail.compact ? 52 : 64
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: label + (badge ? " · " + badge : "")
        onClicked: rail.navigate(key)
        ToolTip.visible: rail.compact && hovered
        ToolTip.text: label
        ToolTip.delay: 300
        background: Rectangle {
            anchors.fill: parent; anchors.margins: 4
            radius: 16
            color: nb.active ? Qt.rgba(0.61, 0.48, 1, 0.20) : nb.hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
            border.width: nb.visualFocus ? 2 : nb.active ? 1 : 0
            border.color: nb.visualFocus ? Theme.cyan : Qt.rgba(0.7, 0.6, 1, 0.45)
            Behavior on color { ColorAnimation { duration: Theme.fast } }
            // the active marker on the leading edge
            Rectangle {
                visible: nb.active
                width: 3; height: parent.height * 0.5; radius: 2
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left; anchors.leftMargin: -4
                gradient: Gradient {
                    GradientStop { position: 0; color: Theme.violet }
                    GradientStop { position: 1; color: Theme.cyan }
                }
            }
        }
        contentItem: Item {
            Column {
                anchors.centerIn: parent
                spacing: 3
                Item {
                    width: 24; height: 24
                    anchors.horizontalCenter: parent.horizontalCenter
                    Icon { anchors.centerIn: parent; name: nb.glyph; size: 21; color: nb.active ? Theme.ink : nb.hovered ? Theme.ink : Theme.ink2 }
                    Rectangle {
                        visible: nb.badge !== ""
                        anchors { right: parent.right; top: parent.top; rightMargin: -8; topMargin: -5 }
                        height: 16; width: Math.max(16, bt.implicitWidth + 8); radius: 8
                        color: Theme.rose
                        T { id: bt; anchors.centerIn: parent; text: nb.badge; font.pixelSize: 10; font.weight: Font.Bold; color: "white"; wrapMode: Text.NoWrap }
                    }
                }
                T {
                    visible: !rail.compact
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: nb.label
                    font.pixelSize: Theme.tiny
                    font.weight: nb.active ? Font.DemiBold : Font.Normal
                    color: nb.active ? Theme.ink : Theme.ink3
                    wrapMode: Text.NoWrap
                }
            }
        }
    }

    Glass {
        anchors.fill: parent
        radius: 24
        tint: Qt.rgba(0.06, 0.07, 0.16, 0.72)
    }

    Column {
        anchors { top: parent.top; left: parent.left; right: parent.right; topMargin: 8 }
        spacing: 2
        // Mira herself: her face is the way back to the conversation.
        AbstractButton {
            id: me
            width: rail.width; height: rail.compact ? 60 : 78
            hoverEnabled: true
            focusPolicy: Qt.StrongFocus
            Accessible.name: mira.s.nav_mira
            onClicked: rail.navigate("")
            background: Rectangle {
                anchors.fill: parent; anchors.margins: 4; radius: 18
                color: rail.current === "" ? Qt.rgba(1, 0.44, 0.71, 0.14) : me.hovered ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                border.width: me.visualFocus ? 2 : 0; border.color: Theme.cyan
            }
            contentItem: Item {
                Column {
                    anchors.centerIn: parent
                    spacing: 3
                    Item {
                        width: rail.compact ? 36 : 42; height: width
                        anchors.horizontalCenter: parent.horizontalCenter
                        Avatar { anchors.fill: parent; tint: Theme.phaseColor(mira.phase, mira.faceStyle) }
                        // her live state on the ring
                        Rectangle {
                            anchors.fill: parent; anchors.margins: -3; radius: width / 2
                            color: "transparent"; border.width: 2
                            border.color: Theme.phaseColor(mira.phase, mira.faceStyle)
                            opacity: ["listening", "thinking", "speaking", "executing"].indexOf(mira.phase) >= 0 ? 0.9 : 0.25
                            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
                        }
                        Rectangle {
                            visible: (rail.badges.inbox || "") !== ""
                            anchors { right: parent.right; top: parent.top; rightMargin: -6; topMargin: -4 }
                            height: 16; width: Math.max(16, ib.implicitWidth + 8); radius: 8
                            color: Theme.amber
                            T { id: ib; anchors.centerIn: parent; text: rail.badges.inbox || ""; font.pixelSize: 10; font.weight: Font.Bold; color: "#1a1204"; wrapMode: Text.NoWrap }
                        }
                    }
                    T { visible: !rail.compact; anchors.horizontalCenter: parent.horizontalCenter; text: mira.s.nav_mira; font.pixelSize: Theme.tiny; font.weight: Font.DemiBold; color: rail.current === "" ? Theme.ink : Theme.ink2; wrapMode: Text.NoWrap }
                }
            }
        }
        Rectangle { width: rail.width * 0.5; height: 1; color: Theme.hairline; anchors.horizontalCenter: parent.horizontalCenter }
        Repeater {
            model: rail.items
            delegate: NavButton {
                required property var modelData
                key: modelData.id; glyph: modelData.icon; label: modelData.label
                badge: rail.badges[modelData.id] || ""
            }
        }
    }
    NavButton {
        anchors { bottom: parent.bottom; bottomMargin: 8 }
        key: "settings"; glyph: "settings"; label: mira.s.nav_settings
    }
}
