import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

// The interactive target stays still; only its plate and glyph compress. A
// native button owns keyboard, pointer and accessibility activation together.
Controls.AbstractButton {
    id: control
    property string iconName: ""
    property bool revealed: true
    property bool controlEnabled: true
    property string label: ""
    property bool primary: false
    property bool motionEnabled: Kirigami.Units.longDuration > 1
    property real slotSize: control.primary ? 52 : 40
    property real revealProgress: control.revealed ? 1 : 0
    readonly property bool settling: feedback.settling
    signal activated

    implicitWidth: slotSize * revealProgress
    implicitHeight: slotSize
    Layout.preferredWidth: implicitWidth
    Layout.preferredHeight: implicitHeight
    Layout.alignment: Qt.AlignVCenter
    clip: true
    opacity: revealProgress * (controlEnabled ? 1 : 0.35)
    visible: revealProgress > 0.01
    // A closing control immediately leaves both the input and focus chains.
    enabled: controlEnabled && revealed
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    padding: 0
    Accessible.name: label
    Accessible.onPressAction: if (enabled && visible) { activated(); }
    onClicked: activated()

    Behavior on revealProgress {
        enabled: control.visible && control.motionEnabled
        NumberAnimation {
            duration: MoUI.Tokens.motionGeometry
            easing.type: MoUI.Tokens.easeEmphasis
        }
    }
    // Return is an activation key as well as Space on this icon-only surface.
    Keys.onReturnPressed: event => { if (!event.isAutoRepeat) { activated(); } }
    Keys.onEnterPressed: event => { if (!event.isAutoRepeat) { activated(); } }

    background: Item {
        Rectangle {
            width: control.slotSize
            height: control.slotSize
            anchors.centerIn: parent
            radius: width / 2
            scale: feedback.value
            color: control.primary
                ? Qt.alpha(Kirigami.Theme.highlightColor,
                           control.down ? 1 : (control.hovered ? 0.92 : 0.82))
                : Qt.alpha(Kirigami.Theme.textColor,
                           control.down ? 0.18 : (control.hovered ? 0.10 : 0))
            border.width: control.visualFocus ? 2 : 0
            border.color: Kirigami.Theme.highlightColor
            Behavior on color {
                ColorAnimation {
                    duration: MoUI.Tokens.duration(control.motionEnabled,
                                                   MoUI.Tokens.motionFast)
                }
            }
        }
    }
    contentItem: Item {
        Kirigami.Icon {
            anchors.centerIn: parent
            width: control.primary ? 26 : 18
            height: width
            source: control.iconName
            color: control.primary ? Kirigami.Theme.highlightedTextColor
                                   : Kirigami.Theme.textColor
            scale: feedback.value
        }
    }
    MoUI.SpringFeedback {
        id: feedback
        active: control.visible && control.enabled
        motionEnabled: control.motionEnabled
        targetScale: control.down ? MoUI.Tokens.pressScale : 1
    }
    Controls.ToolTip.text: label
    Controls.ToolTip.visible: hovered && label.length > 0
    Controls.ToolTip.delay: Kirigami.Units.toolTipDelay
}
