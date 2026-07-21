/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import QtQuick.Controls as QQC2

import org.kde.kirigami as Kirigami

QQC2.AbstractButton {
    id: control

    property alias iconName: actionIcon.source
    property string description: ""
    property bool emphasized: false
    property bool destructive: false
    readonly property bool destructiveActive: destructive && (hovered || down || emphasized)

    signal navigate(int step)

    Accessible.name: text
    Accessible.description: description
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    implicitWidth: Kirigami.Units.gridUnit * 10
    implicitHeight: Kirigami.Units.gridUnit * 8
    scale: down ? 0.96 : (hovered ? 1.04 : 1.0)

    Keys.onLeftPressed: navigate(-1)
    Keys.onRightPressed: navigate(1)
    Keys.onUpPressed: navigate(-1)
    Keys.onDownPressed: navigate(1)

    Behavior on scale {
        NumberAnimation {
            duration: Kirigami.Units.shortDuration
            easing.type: Easing.OutBack
            easing.overshoot: 1.5
        }
    }

    background: Rectangle {
        radius: Kirigami.Units.gridUnit * 0.65
        color: control.destructiveActive
            ? Kirigami.Theme.negativeBackgroundColor
            : (control.emphasized || control.down
                ? Kirigami.Theme.highlightColor
                : Kirigami.Theme.alternateBackgroundColor)
        opacity: control.enabled
            ? (control.hovered || control.visualFocus ? 0.96 : 0.82)
            : 0.42
        border.width: control.visualFocus ? 2 : 1
        border.color: control.destructive
            ? Kirigami.Theme.negativeTextColor
            : (control.visualFocus || control.hovered
                ? Kirigami.Theme.hoverColor
                : Kirigami.Theme.highlightColor)

        // Top highlight
        Rectangle {
            anchors {
                top: parent.top
                horizontalCenter: parent.horizontalCenter
                topMargin: 1
            }
            width: parent.width - 2
            height: 1
            radius: parent.radius
            color: Kirigami.Theme.textColor
            opacity: 0.10
        }

        // Bottom inner shadow
        Rectangle {
            anchors {
                bottom: parent.bottom
                horizontalCenter: parent.horizontalCenter
                bottomMargin: 1
            }
            width: parent.width - 2
            height: 1
            radius: parent.radius
            color: Kirigami.Theme.backgroundColor
            opacity: 0.30
        }

        // Animated light sweep across the card on hover — glass refraction effect
        Item {
            anchors.fill: parent
            clip: true
            visible: control.hovered

            Rectangle {
                id: cardSweep
                width: parent.width * 0.25
                height: parent.height * 2
                rotation: 20
                y: -parent.height * 0.5
                x: -width
                color: Kirigami.Theme.textColor
                opacity: 0.04
                NumberAnimation on x {
                    from: -cardSweep.width * 1.5
                    to: control.width + cardSweep.width * 0.5
                    duration: 2200
                    loops: Animation.Infinite
                    easing.type: Easing.InOutSine
                    running: control.hovered
                }
            }
        }

        // Active neon indicator rail
        Rectangle {
            anchors {
                bottom: parent.bottom
                horizontalCenter: parent.horizontalCenter
                bottomMargin: 2
            }
            width: control.hovered || control.visualFocus ? parent.width * 0.55 : (control.emphasized ? parent.width * 0.32 : 0)
            height: 2
            radius: 1
            color: control.destructive
                ? Kirigami.Theme.negativeTextColor
                : Kirigami.Theme.highlightColor
            opacity: control.hovered || control.visualFocus || control.emphasized ? 0.95 : 0
            Behavior on width { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: 150 } }
        }

        // Press pulse — ring that expands outward on click
        Rectangle {
            id: pressPulse
            anchors.centerIn: parent
            width: 0
            height: 0
            radius: width / 2
            color: control.destructive ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.highlightColor
            opacity: 0

            states: State {
                name: "pressed"
                when: control.down
                PropertyChanges { pressPulse.width: control.width * 1.2; pressPulse.height: control.width * 1.2; pressPulse.opacity: 0 }
            }
            transitions: Transition {
                from: ""; to: "pressed"
                ParallelAnimation {
                    NumberAnimation { target: pressPulse; properties: "width,height"; from: 0; to: control.width * 1.2; duration: 400; easing.type: Easing.OutCubic }
                    SequentialAnimation {
                        NumberAnimation { target: pressPulse; property: "opacity"; from: 0.3; to: 0; duration: 400; easing.type: Easing.OutCubic }
                    }
                }
            }
        }
    }

    contentItem: Column {
        spacing: Kirigami.Units.smallSpacing

        Item {
            width: parent.width
            height: Kirigami.Units.gridUnit * 3.4

            readonly property bool active: control.hovered || control.down

            // Glow disc behind icon
            Rectangle {
                anchors.centerIn: parent
                width: Kirigami.Units.gridUnit * 3
                height: width
                radius: width / 2
                color: control.destructive
                    ? (control.destructiveActive
                        ? Kirigami.Theme.highlightedTextColor
                        : Kirigami.Theme.negativeTextColor)
                    : (control.emphasized
                        ? Kirigami.Theme.textColor
                        : Kirigami.Theme.highlightColor)
                opacity: parent.active ? (control.emphasized ? 0.24 : 0.30)
                                       : (control.emphasized ? 0.14 : 0.18)
                scale: parent.active ? 1.18 : 1.0
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
                Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
            }

            Kirigami.Icon {
                id: actionIcon
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.large
                height: width
                selected: control.emphasized
                isMask: true
                // The background turns highlightColor on emphasized/down (see
                // background:, above), so a highlightColor glyph would vanish into
                // it — the primary logout Cancel button was exactly this. Use the
                // contrasting highlightedTextColor whenever the fill is the accent.
                color: control.destructive
                    ? (control.destructiveActive
                        ? Kirigami.Theme.highlightedTextColor
                        : Kirigami.Theme.negativeTextColor)
                    : (control.emphasized || control.down
                        ? Kirigami.Theme.highlightedTextColor
                        : Kirigami.Theme.highlightColor)
                scale: parent.active ? 1.10 : 1.0
                // Subtle rotation on hover — icon tilts 5° with bounce back
                rotation: parent.active ? 5 : 0
                Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutBack; easing.overshoot: 1.5 } }
                Behavior on rotation { NumberAnimation { duration: 300; easing.type: Easing.OutBack; easing.overshoot: 2.0 } }
            }
        }

        QQC2.Label {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap
            text: control.text
            color: control.destructive && !control.destructiveActive
                ? Kirigami.Theme.negativeTextColor
                : ((control.emphasized || control.down || control.destructiveActive)
                    ? Kirigami.Theme.highlightedTextColor
                    : Kirigami.Theme.textColor)
            font.family: "IBM Plex Sans"
            font.weight: Font.DemiBold
            font.pointSize: Kirigami.Theme.defaultFont.pointSize
        }

        QQC2.Label {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 1
            text: control.description
            visible: text.length > 0
            color: control.emphasized || control.destructiveActive
                ? Kirigami.Theme.highlightedTextColor
                : (control.destructive
                    ? Kirigami.Theme.negativeTextColor
                    : Kirigami.Theme.disabledTextColor)
            opacity: 0.82
            font.family: "IBM Plex Sans"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }
    }
}
