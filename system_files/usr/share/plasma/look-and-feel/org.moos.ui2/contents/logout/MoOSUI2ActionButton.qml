/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 action tile — Liquid Glass.

    A translucent frosted tile that floats above the scene on a soft shadow and
    lifts toward the pointer: content leads, the control recedes until touched.
    The API is unchanged (iconName, text, description, emphasized, destructive,
    clicked, navigate) so the logout screen keeps driving it exactly as before.
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
    readonly property bool destructiveActive: destructive && (hovered || down || emphasized)
    readonly property bool lit: hovered || visualFocus
    readonly property color accent: destructive
        ? Kirigami.Theme.negativeTextColor
        : Kirigami.Theme.highlightColor
    // The logout is a dark, dramatic power moment on every theme, so the tile
    // frost is a fixed near-white (MoOS bans pure white) that reads as bright
    // glass over the dark scrim — the theme supplies only the accent, not the
    // scene. glassInk is the light label colour that rides on that frost.
    readonly property color glass: "#EFF4F2"
    readonly property color glassInk: "#EFF4F2"

    signal navigate(int step)

    Accessible.name: text
    Accessible.description: description
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    implicitWidth: Kirigami.Units.gridUnit * 10
    implicitHeight: Kirigami.Units.gridUnit * 8.5
    padding: Kirigami.Units.largeSpacing
    scale: down ? 0.97 : (lit ? 1.03 : 1.0)

    // Bento: the contextual primary (emphasized) tile is the hero and stands
    // taller; the grid instance sets its columnSpan to the live column count so
    // it fills the whole row. The composition is asymmetric and the likely
    // action leads.
    Layout.preferredHeight: emphasized ? Kirigami.Units.gridUnit * 10
                                       : Kirigami.Units.gridUnit * 8.5

    Keys.onLeftPressed: navigate(-1)
    Keys.onRightPressed: navigate(1)
    Keys.onUpPressed: navigate(-1)
    Keys.onDownPressed: navigate(1)

    Behavior on scale {
        NumberAnimation {
            duration: Kirigami.Units.shortDuration
            easing.type: Easing.OutBack
            easing.overshoot: 1.4
        }
    }

    background: Item {
        // Accent bloom — the tile responds by lighting from within.
        RectangularGlow {
            anchors.fill: card
            glowRadius: Kirigami.Units.gridUnit * 1.4
            spread: 0.04
            color: control.accent
            cornerRadius: card.radius + glowRadius
            opacity: control.lit ? 0.42 : (control.emphasized ? 0.20 : 0.0)
            Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        }
        // Soft depth shadow so the tile floats off the scene.
        RectangularGlow {
            anchors.fill: card
            glowRadius: Kirigami.Units.gridUnit
            spread: 0.02
            color: Qt.rgba(0, 0, 0, 0.5)
            cornerRadius: card.radius + glowRadius
        }

        Rectangle {
            id: card
            anchors.fill: parent
            radius: Kirigami.Units.gridUnit * 1.15

            // Frosted glass: a milky vertical fall of light. Emphasized (the
            // primary action) is tinted with the accent; everything else is
            // neutral glass so the scene, not the button, sets the colour.
            // Emphasized (the primary action) and any pressed tile fill with the
            // accent so the contrasting highlightedTextColor glyph reads on it;
            // every other tile is neutral frosted glass and lets the scene lead.
            readonly property bool filled: control.emphasized || control.down
            gradient: Gradient {
                GradientStop { position: 0.0; color: card.filled
                    ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.96)
                    : Qt.rgba(control.glass.r, control.glass.g, control.glass.b, control.lit ? 0.26 : 0.17) }
                GradientStop { position: 0.5; color: card.filled
                    ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.84)
                    : Qt.rgba(control.glass.r, control.glass.g, control.glass.b, control.lit ? 0.16 : 0.10) }
                GradientStop { position: 1.0; color: card.filled
                    ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.70)
                    : Qt.rgba(control.glass.r, control.glass.g, control.glass.b, control.lit ? 0.12 : 0.07) }
            }
            border.width: 1.5
            border.color: (control.lit || control.emphasized)
                ? Qt.rgba(control.accent.r, control.accent.g, control.accent.b, 0.85)
                : Qt.rgba(control.glass.r, control.glass.g, control.glass.b, 0.26)

            // Crest highlight — the light along the top rim.
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right; margins: 2 }
                height: 1.5
                radius: 1
                color: Qt.rgba(control.glass.r, control.glass.g, control.glass.b, control.lit ? 0.46 : 0.30)
            }
            // A faint diagonal specular.
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: Qt.rgba(control.glass.r, control.glass.g, control.glass.b, 0.06) }
                    GradientStop { position: 0.4; color: "transparent" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
            // Press ripple.
            Rectangle {
                anchors.centerIn: parent
                width: control.down ? parent.width * 1.15 : 0
                height: width
                radius: width / 2
                color: Qt.rgba(control.accent.r, control.accent.g, control.accent.b, control.down ? 0.0 : 0.22)
                Behavior on width { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
            }
        }
    }

    contentItem: Column {
        spacing: Kirigami.Units.smallSpacing

        Item {
            width: parent.width
            height: Kirigami.Units.gridUnit * 3.2

            // Glow pool behind the glyph, swelling when lit.
            Rectangle {
                anchors.centerIn: parent
                width: Kirigami.Units.gridUnit * 2.8
                height: width
                radius: width / 2
                color: control.destructiveActive ? Kirigami.Theme.negativeTextColor
                     : (control.emphasized ? Kirigami.Theme.highlightColor : control.accent)
                opacity: control.lit ? 0.28 : (control.emphasized ? 0.16 : 0.10)
                scale: control.lit ? 1.12 : 1.0
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }
            }
            Kirigami.Icon {
                id: actionIcon
                anchors.centerIn: parent
                width: Kirigami.Units.iconSizes.large
                height: width
                isMask: true
                // On the accent fill (emphasized or down) the glyph switches to
                // the contrasting highlightedTextColor so it never vanishes.
                color: control.destructive
                    ? (control.destructiveActive ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.negativeTextColor)
                    : ((control.emphasized || control.down) ? Kirigami.Theme.highlightedTextColor : control.glassInk)
                scale: control.lit ? 1.08 : 1.0
                Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
            }
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap
            text: control.text
            color: control.destructive && !control.destructiveActive
                ? Kirigami.Theme.negativeTextColor
                : ((control.emphasized || control.down || control.destructiveActive)
                    ? Kirigami.Theme.highlightedTextColor : control.glassInk)
            font.family: "Inter"
            font.weight: Font.DemiBold
            font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
            renderType: Text.NativeRendering
        }

        Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            maximumLineCount: 1
            text: control.description
            visible: text.length > 0
            color: (control.emphasized || control.down)
                ? Kirigami.Theme.highlightedTextColor
                : (control.destructive ? Kirigami.Theme.negativeTextColor : control.glassInk)
            opacity: 0.62
            font.family: "Inter"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            renderType: Text.NativeRendering
        }
    }
}
