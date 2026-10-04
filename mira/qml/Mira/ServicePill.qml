import QtQuick
import QtQuick.Controls.Basic

// A tiny live status: coloured dot + label. Tooltip explains the state.
Rectangle {
    id: pill
    property string label: ""
    property string state_: "connecting"   // online offline connecting off (not set up here)
    property string icon: "sparkle"
    property string detail: ""
    readonly property color dot: state_ === "online" ? Theme.ok : state_ === "offline" ? Theme.danger : state_ === "off" ? Theme.off : Theme.amber
    height: 30
    width: row.implicitWidth + 20
    radius: 15
    color: Qt.rgba(1, 1, 1, hh.hovered ? 0.07 : 0.035)
    border.width: 1
    border.color: Theme.hairline
    Accessible.role: Accessible.StaticText
    Accessible.name: label + " " + detail
    HoverHandler { id: hh }
    ToolTip.visible: hh.hovered && detail !== ""
    ToolTip.text: detail
    ToolTip.delay: 350
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 7
        Rectangle {
            width: 7; height: 7; radius: 3.5
            color: pill.dot
            anchors.verticalCenter: parent.verticalCenter
            SequentialAnimation on opacity {
                // A cloud desktop can remain disconnected from an optional home/Echo service.
                // Do not animate that permanent state on a software renderer, or when the owner
                // disables motion; the controller's motion policy already covers both cases.
                running: pill.state_ === "connecting" && pill.visible && mira.motion
                loops: Animation.Infinite
                NumberAnimation { to: 0.3; duration: 700 }
                NumberAnimation { to: 1; duration: 700 }
            }
        }
        T { text: pill.label; font.pixelSize: Theme.small; color: Theme.ink2; wrapMode: Text.NoWrap; anchors.verticalCenter: parent.verticalCenter }
    }
}
