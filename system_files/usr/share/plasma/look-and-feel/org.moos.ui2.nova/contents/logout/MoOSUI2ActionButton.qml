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
    scale: down ? 0.98 : (hovered ? 1.03 : 1.0)

    Keys.onLeftPressed: navigate(-1)
    Keys.onRightPressed: navigate(1)
    Keys.onUpPressed: navigate(-1)
    Keys.onDownPressed: navigate(1)

    Behavior on scale {
        NumberAnimation {
            duration: Kirigami.Units.shortDuration
            easing.type: Easing.OutCubic
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
    }

    contentItem: Column {
        spacing: Kirigami.Units.smallSpacing

        Item {
            width: parent.width
            height: Kirigami.Units.gridUnit * 3.4

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
                opacity: control.emphasized ? 0.14 : 0.18
            }

            Kirigami.Icon {
                id: actionIcon
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.large
                height: width
                selected: control.emphasized
                isMask: true
                color: control.destructive
                    ? (control.destructiveActive
                        ? Kirigami.Theme.highlightedTextColor
                        : Kirigami.Theme.negativeTextColor)
                    : Kirigami.Theme.highlightColor
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
                : ((control.emphasized || control.destructiveActive)
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
