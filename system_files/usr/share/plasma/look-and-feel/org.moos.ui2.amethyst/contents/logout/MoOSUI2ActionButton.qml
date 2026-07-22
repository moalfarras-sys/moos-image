/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 — power ORB. A ground-up redesign of the power action: the full-width
    command rows are gone. Each action is a circular glyph ORB with a label
    beneath — a compact dock of round buttons, not a stack of bars. The public API
    is unchanged (iconName, text, description, emphasized, destructive, armed,
    clicked, navigate) so the logout logic drives it exactly as before; only the
    shape is new. Two-tone accent (accentA→accentB, both derived from the live
    theme) so every palette lights the orb in its own two colours, never one flat
    tint. Hover blooms and grows, focus rings, press dims, an armed state pulses
    for the confirm tap on sensitive actions.
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
    property bool armed: false   // a sensitive action awaiting its confirm tap

    readonly property bool lit: hovered || visualFocus || down
    // accentA is the live theme highlight (or the negative colour for destructive
    // actions); accentB is a second hue derived from it, so the filled orb spans
    // TWO of the palette's colours. Achromatic accents fall back to a brighter shade.
    readonly property color accentA: destructive ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.highlightColor
    readonly property color accentB: {
        const c = control.accentA;
        if (c.hslSaturation < 0.08 || c.hslHue < 0) {
            return Qt.lighter(c, 1.28);
        }
        let nh = c.hslHue + 0.09;
        if (nh > 1) { nh -= 1; }
        return Qt.hsla(nh, Math.min(1, c.hslSaturation), Math.min(0.72, c.hslLightness * 1.08), 1);
    }
    readonly property color ink: Kirigami.Theme.textColor
    // The disc fills with the accent when emphasized, pressed, or armed for a
    // confirm — so the glyph must switch to highlightedTextColor there, or an
    // accent glyph on an accent fill (the old Cancel bug) goes invisible.
    readonly property bool filled: control.emphasized || control.down || control.armed

    signal navigate(int step)

    Accessible.name: text
    Accessible.description: description
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true

    readonly property real orb: Kirigami.Units.gridUnit * 4.6
    implicitWidth: Kirigami.Units.gridUnit * 7
    implicitHeight: orb + Kirigami.Units.gridUnit * 2.7
    padding: 0
    scale: down ? 0.96 : (lit ? 1.03 : 1.0)
    Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }

    Keys.onUpPressed: navigate(-1)
    Keys.onDownPressed: navigate(1)
    Keys.onLeftPressed: navigate(-1)
    Keys.onRightPressed: navigate(1)

    background: null

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        // ── The orb ──────────────────────────────────────────────────────────
        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: control.orb
            implicitHeight: control.orb

            // Ambient bloom on hover / focus / armed — a soft accent pool behind
            // the disc (RadialGradient with explicit radii → a clean circle).
            RadialGradient {
                anchors.centerIn: parent
                width: parent.width * 1.75
                height: width
                visible: control.lit || control.armed
                horizontalRadius: width * 0.5
                verticalRadius: height * 0.5
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(control.accentA.r, control.accentA.g, control.accentA.b, control.armed ? 0.5 : 0.32) }
                    GradientStop { position: 0.55; color: "transparent" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                SequentialAnimation on opacity {
                    running: control.armed
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.55; duration: 700; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.0; duration: 700; easing.type: Easing.InOutSine }
                }
            }

            // The disc.
            Rectangle {
                id: disc
                anchors.fill: parent
                radius: width / 2
                gradient: control.filled ? filledGrad : null
                color: control.filled
                    ? "transparent"
                    : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, control.lit ? 0.16 : 0.08)
                border.width: control.visualFocus ? 2 : 1
                border.color: control.filled
                    ? "transparent"
                    : (control.lit ? Qt.rgba(control.accentA.r, control.accentA.g, control.accentA.b, 0.8)
                                   : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.16))

                Gradient {
                    id: filledGrad
                    GradientStop { position: 0.0; color: control.accentB }
                    GradientStop { position: 1.0; color: control.accentA }
                }

                Kirigami.Icon {
                    id: actionIcon
                    anchors.centerIn: parent
                    width: Kirigami.Units.iconSizes.medium
                    height: width
                    isMask: true
                    color: control.filled
                        ? Kirigami.Theme.highlightedTextColor
                        : (control.destructive && control.lit ? control.accentA : control.ink)
                }
            }
        }

        // ── Label + (on hover / armed) description ────────────────────────────
        QQC2.Label {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: control.text
            color: (control.lit || control.emphasized || control.armed)
                ? Kirigami.Theme.textColor
                : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.85)
            // Arabic captions use IBM Plex Sans Arabic (as on the lock screen),
            // Latin uses Inter — one bilingual type system across every surface.
            font.family: Qt.application.layoutDirection === Qt.RightToLeft ? "IBM Plex Sans Arabic" : "Inter"
            font.weight: Font.DemiBold
            font.pointSize: Kirigami.Theme.defaultFont.pointSize
        }
        QQC2.Label {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 8
            horizontalAlignment: Text.AlignHCenter
            text: control.description
            visible: text.length > 0 && (control.lit || control.armed)
            wrapMode: Text.WordWrap
            color: control.armed ? control.accentA : control.ink
            opacity: control.armed ? 1.0 : 0.6
            font.family: "Inter"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }
    }
}
