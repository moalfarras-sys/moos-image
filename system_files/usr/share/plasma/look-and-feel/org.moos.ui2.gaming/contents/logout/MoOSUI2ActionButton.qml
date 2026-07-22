/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 — command row. A ground-up redesign of the power action: the tile
    grid is gone. Each action is a full-width glass ROW — a lit icon badge, a
    two-line bilingual label, and a trailing chevron — that fills with the theme
    accent when it leads or lights. The public API is unchanged (iconName, text,
    description, emphasized, destructive, clicked, navigate) so the logout logic
    drives it exactly as before.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

import org.kde.kirigami as Kirigami

QQC2.AbstractButton {
    id: control

    property alias iconName: actionIcon.source
    property string description: ""
    property bool emphasized: false
    property bool destructive: false

    readonly property bool lit: hovered || visualFocus || down
    readonly property color accent: destructive
        ? Kirigami.Theme.negativeTextColor
        : Kirigami.Theme.highlightColor
    readonly property color ink: "#EFF4F2"     // light label on the dark scene
    readonly property color frost: "#E9F1EF"   // near-white glass (MoOS bans pure white)

    signal navigate(int step)

    Accessible.name: text
    Accessible.description: description
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Layout.fillWidth: true
    implicitHeight: Kirigami.Units.gridUnit * 4.0
    padding: Kirigami.Units.largeSpacing
    scale: down ? 0.985 : 1.0
    Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }

    Keys.onUpPressed: navigate(-1)
    Keys.onDownPressed: navigate(1)
    Keys.onLeftPressed: navigate(-1)
    Keys.onRightPressed: navigate(1)

    background: Item {
        RectangularGlow {
            anchors.fill: card
            glowRadius: Kirigami.Units.gridUnit * 1.1
            spread: 0.03
            color: control.accent
            cornerRadius: card.radius + glowRadius
            opacity: control.lit ? 0.34 : (control.emphasized ? 0.18 : 0.0)
            Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        }
        Rectangle {
            id: card
            anchors.fill: parent
            radius: height * 0.30
            readonly property bool filled: control.emphasized || control.down
            color: filled
                ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, control.lit ? 0.96 : 0.88)
                : Qt.rgba(control.frost.r, control.frost.g, control.frost.b, control.lit ? 0.15 : 0.06)
            border.width: 1
            border.color: control.emphasized
                ? "transparent"
                : (control.lit ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.7)
                               : Qt.rgba(control.frost.r, control.frost.g, control.frost.b, 0.14))
            Rectangle {   // top crest
                anchors { top: parent.top; left: parent.left; right: parent.right; margins: 1 }
                height: 1; radius: 1
                visible: !card.filled
                color: Qt.rgba(control.frost.r, control.frost.g, control.frost.b, control.lit ? 0.30 : 0.16)
            }
        }
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing

        Rectangle {                       // icon badge
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.preferredWidth: Kirigami.Units.gridUnit * 2.5
            Layout.preferredHeight: Kirigami.Units.gridUnit * 2.5
            radius: width * 0.32
            color: (control.emphasized || control.down)
                ? Qt.rgba(control.frost.r, control.frost.g, control.frost.b, 0.20)
                : Qt.rgba(control.accent.r, control.accent.g, control.accent.b, control.lit ? 0.26 : 0.15)
            Kirigami.Icon {
                id: actionIcon
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.medium
                height: width
                isMask: true
                color: (control.emphasized || control.down) ? Kirigami.Theme.highlightedTextColor
                     : (control.destructive ? control.accent : control.ink)
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            QQC2.Label {
                Layout.fillWidth: true
                text: control.text
                elide: Text.ElideRight
                color: (control.emphasized || control.down) ? Kirigami.Theme.highlightedTextColor
                     : (control.destructive ? control.accent : control.ink)
                font.family: "Inter"
                font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
            }
            QQC2.Label {
                Layout.fillWidth: true
                text: control.description
                visible: text.length > 0
                elide: Text.ElideRight
                color: (control.emphasized || control.down) ? Kirigami.Theme.highlightedTextColor : control.ink
                opacity: 0.62
                font.family: "Inter"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
        }

        Kirigami.Icon {                   // trailing chevron
            Layout.rightMargin: Kirigami.Units.largeSpacing
            width: Kirigami.Units.iconSizes.small
            height: width
            isMask: true
            source: "go-next-symbolic"
            opacity: control.lit ? 0.9 : 0.35
            color: (control.emphasized || control.down) ? Kirigami.Theme.highlightedTextColor : control.ink
        }
    }
}
