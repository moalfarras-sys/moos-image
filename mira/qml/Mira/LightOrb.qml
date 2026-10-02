import QtQuick
import QtQuick.Controls.Basic

// One light on Lumen's stage: a glowing orb in the light's own colour, as bright as the light is.
// Tap picks it (the controls act on what is picked); double-tap switches it on or off.
// A light that cannot be reached is a dim outline, never a colour it does not show.
AbstractButton {
    id: orb
    property string name: ""
    property color tone: "#FFC478"
    property bool lit: false
    property bool online: true
    property real level: 100            // 0–100
    property bool picked: false
    property bool pc: false
    property bool living: false
    property real clock: 0               // the window's shared clock (a living light breathes with it)
    property real size: 54
    signal powerRequested()
    implicitWidth: Math.max(size * 1.9, label.implicitWidth + 8)
    implicitHeight: size * 1.75 + label.implicitHeight + 4
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    Accessible.name: name + " · " + (online ? (lit ? mira.s.lu_on + " " + Math.round(level) + "%" : mira.s.lu_off) : mira.s.lu_offline)
    onDoubleClicked: orb.powerRequested()

    readonly property real glow: !online || !lit ? 0 : 0.35 + 0.65 * Math.min(1, level / 100)
    readonly property real breathe: living && lit && mira.motion ? 0.06 * Math.sin(clock * 1.6) : 0

    background: Item {}
    contentItem: Item {
        Item {
            id: body
            width: orb.size * 1.75; height: width
            anchors.horizontalCenter: parent.horizontalCenter
            // halo, two soft rings of the light's own colour
            Rectangle {
                anchors.centerIn: parent
                width: orb.size * (1.55 + orb.breathe); height: width; radius: width / 2
                color: Qt.rgba(orb.tone.r, orb.tone.g, orb.tone.b, 0.10 * orb.glow)
                Behavior on color { ColorAnimation { duration: Theme.emphasized } }
            }
            Rectangle {
                anchors.centerIn: parent
                width: orb.size * (1.22 + orb.breathe * 0.5); height: width; radius: width / 2
                color: Qt.rgba(orb.tone.r, orb.tone.g, orb.tone.b, 0.20 * orb.glow)
                Behavior on color { ColorAnimation { duration: Theme.emphasized } }
            }
            // the pick ring
            Rectangle {
                anchors.centerIn: parent
                width: orb.size + 12; height: width; radius: width / 2
                color: "transparent"
                border.width: orb.picked ? 2 : (orb.visualFocus ? 2 : (orb.hovered ? 1 : 0))
                border.color: orb.picked ? "white" : Theme.cyan
                opacity: orb.picked ? 0.95 : 0.6
                Behavior on border.width { NumberAnimation { duration: Theme.fast } }
            }
            // the light itself
            Rectangle {
                id: core
                anchors.centerIn: parent
                width: orb.size; height: width; radius: width / 2
                opacity: orb.online ? 1 : 0.35
                border.width: orb.online ? 1 : 1.5
                border.color: orb.lit ? Qt.rgba(1, 1, 1, 0.45) : Qt.rgba(0.7, 0.75, 1, 0.25)
                gradient: Gradient {
                    GradientStop { position: 0.0; color: orb.lit ? Qt.lighter(orb.tone, 1.35) : Qt.rgba(0.20, 0.22, 0.32, 1) }
                    GradientStop { position: 0.55; color: orb.lit ? orb.tone : Qt.rgba(0.12, 0.13, 0.22, 1) }
                    GradientStop { position: 1.0; color: orb.lit ? Qt.darker(orb.tone, 1.6) : Qt.rgba(0.07, 0.08, 0.15, 1) }
                }
                // glass highlight
                Rectangle {
                    width: parent.width * 0.42; height: parent.height * 0.24; radius: height / 2
                    x: parent.width * 0.2; y: parent.height * 0.14
                    rotation: -24
                    color: Qt.rgba(1, 1, 1, orb.lit ? 0.32 : 0.10)
                }
                Icon {
                    anchors.centerIn: parent
                    visible: !orb.lit || !orb.online
                    name: orb.pc ? "fan" : "bulb"
                    size: orb.size * 0.42
                    color: Theme.ink3
                    opacity: orb.online ? 1 : 0.6
                }
                Icon {
                    anchors.centerIn: parent
                    visible: orb.lit && orb.pc
                    name: "fan"
                    size: orb.size * 0.46
                    color: Qt.rgba(1, 1, 1, 0.75)
                    rotation: orb.living && mira.motion ? orb.clock * 90 : 0
                }
            }
            scale: orb.down ? 0.94 : (orb.hovered ? 1.04 : 1)
            Behavior on scale { NumberAnimation { duration: Theme.fast; easing.type: Easing.OutBack } }
        }
        T {
            id: label
            anchors { top: body.bottom; topMargin: -orb.size * 0.18; horizontalCenter: parent.horizontalCenter }
            width: Math.min(implicitWidth, orb.size * 2.4)
            text: orb.name
            horizontalAlignment: Text.AlignHCenter
            font.pixelSize: Theme.small
            font.weight: orb.picked ? Font.DemiBold : Font.Normal
            color: orb.picked ? Theme.ink : Theme.ink2
            wrapMode: Text.NoWrap
            elide: Text.ElideRight
        }
    }
}
