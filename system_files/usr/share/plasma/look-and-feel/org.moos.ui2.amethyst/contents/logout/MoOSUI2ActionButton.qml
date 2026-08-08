/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 — Tidal Portal key, second generation. Each action is now a real
    TILE: one glass chip that carries its own glyph AND its caption inside the
    same rounded surface, so the dock reads as a bank of substantial controls
    instead of small discs with floating text. The public API is unchanged
    (iconName, text, description, emphasized, destructive, armed, subtle,
    clicked, navigate) so the logout logic drives it exactly as before.

    Colour contract (measured across all 16 schemes in tests/test_moos_ui2.py):
    the filled surface is accentA (highlight, or the negative role when
    destructive) under its PAIRED foreground — highlightedTextColor, or the
    Complementary background for destructive fills. accentB exists for the rim
    only; it has no paired foreground role and never sits under the glyph.
    Armed is a still, high-contrast fill — confirmation never pulses.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

QQC2.AbstractButton {
    id: control

    property alias iconName: actionIcon.source
    property string description: ""
    property bool emphasized: false
    property bool destructive: false
    property bool armed: false   // a sensitive action awaiting its confirm tap
    // The way OUT is not an action. `subtle` renders the same tile one step
    // down the hierarchy — a quieter fill and a lighter caption — so the dock
    // reads first and Cancel second. Only Cancel sets it.
    property bool subtle: false

    readonly property bool lit: hovered || visualFocus || down
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    // accentA is the live theme highlight (or the negative colour for destructive
    // actions); accentB is a second hue derived from it for the decorative rim.
    // It must never sit underneath the glyph: unlike accentA, it has no paired
    // foreground role in the KDE colour scheme.
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
    // The tile fills with one contrast-gated role when emphasized, pressed, or
    // armed. Selection ink is paired with highlight; destructive ink is the
    // Complementary background paired with ForegroundNegative.
    readonly property bool filled: control.emphasized || control.down || control.armed
    readonly property color filledInk: control.destructive
        ? Kirigami.Theme.backgroundColor
        : Kirigami.Theme.highlightedTextColor

    signal navigate(int horizontalStep, int verticalStep)

    // Do not rely on AbstractButton's platform-specific implicit accessibility
    // mapping on the logout greeter.  This component is also loaded by
    // ksmserver outside a normal application window, where assistive clients
    // need the role and transient pressed state to be explicit.
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.description: description
    Accessible.pressed: down
    // Assistive activation must emit the same clicked signal as touch/mouse.
    // Sensitive actions then still pass through Logout.qml's armOrFire gate;
    // accessibility is never a side door around confirmation.
    Accessible.onPressAction: control.animateClick()
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true

    // The tile IS the control: glyph and caption share one surface, so the
    // whole footprint is interactive and the dock has real visual mass.
    readonly property real keyHeight: Kirigami.Units.gridUnit * (control.subtle ? 3.1 : 6.2)
    readonly property real keyWidth: Kirigami.Units.gridUnit * (control.subtle ? 10.4 : 8.6)
    implicitWidth: keyWidth
    implicitHeight: keyHeight
    padding: 0
    scale: down ? design.pressScale : (lit ? design.hoverScale : 1.0)
    Behavior on scale {
        NumberAnimation {
            duration: design.duration(control.motionEnabled, design.motionFast)
            easing.type: design.easeStandard
        }
    }

    Keys.onUpPressed: navigate(0, -1)
    Keys.onDownPressed: navigate(0, 1)
    Keys.onLeftPressed: navigate(-1, 0)
    Keys.onRightPressed: navigate(1, 0)

    background: null

    contentItem: Item {
        implicitWidth: control.keyWidth
        implicitHeight: control.keyHeight

        // Accent bloom behind a lit or armed tile — still, never looping.
        Rectangle {
            anchors.centerIn: parent
            width: parent.width * 1.10
            height: parent.height * 1.16
            radius: Math.min(width, height) * 0.30
            visible: control.lit || control.armed
            color: control.accentA
            opacity: control.armed ? 0.14 : 0.06
        }

        // One contrast-paired tile surface.
        Rectangle {
            id: disc
            anchors.fill: parent
            radius: control.subtle ? design.radiusControl : design.radiusPanel
            color: control.filled
                ? control.accentA
                : Qt.rgba(control.ink.r, control.ink.g, control.ink.b,
                          control.subtle
                          ? (control.lit ? design.surfaceRestingOpacity
                                         : design.surfaceRestingOpacity / 2)
                          : (control.lit ? design.surfaceHoverOpacity
                                         : design.surfaceRestingOpacity))
            border.width: control.visualFocus
                          ? design.focusWidth : design.borderHairline
            border.color: control.filled
                ? control.accentB
                : (control.lit ? Qt.rgba(control.accentA.r, control.accentA.g, control.accentA.b, 0.8)
                               : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.15))

            // Inner sheen: the glass catch-light along the tile's upper third.
            // Painted from the scheme's own foreground at whisper opacity so it
            // survives every palette without a literal colour.
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right }
                anchors.margins: 1
                height: parent.height * 0.46
                radius: parent.radius - 1
                visible: !control.filled
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.05) }
                    GradientStop { position: 1.0; color: Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.0) }
                }
            }

            // The same crest cut that seals the full-screen horizon.
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: -height / 2
                width: parent.width * 0.30
                height: control.visualFocus ? 3 : 2
                radius: height / 2
                visible: !control.subtle
                color: control.filled ? control.filledInk : control.accentB
                opacity: control.filled ? 0.55 : (control.lit ? 0.95 : 0.62)
            }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Math.max(5, parent.height * 0.07)
                width: parent.width * 0.42
                height: 1
                radius: height / 2
                visible: !control.subtle
                color: control.filled ? control.filledInk : control.accentA
                opacity: control.filled ? 0.35 : (control.lit ? 0.55 : 0.22)
            }

            // Glyph above caption, both inside the tile.
            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.largeSpacing * 2
                spacing: control.subtle ? 0 : Kirigami.Units.smallSpacing

                Kirigami.Icon {
                    id: actionIcon
                    Layout.alignment: Qt.AlignHCenter
                    // Size the glyph FROM the tile it sits in — the -symbolic
                    // sources render crisp at any size, so no step snapping.
                    // The subtle (Cancel) pill is text-only: the caption alone
                    // reads faster than glyph+word at its quiet weight.
                    visible: !control.subtle
                    Layout.preferredWidth: Math.round(control.keyHeight * 0.30)
                    Layout.preferredHeight: Layout.preferredWidth
                    isMask: true
                    color: control.filled
                        ? control.filledInk
                        : (control.destructive && control.lit ? control.accentA : control.ink)
                }
                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: control.text
                    elide: Text.ElideRight
                    maximumLineCount: 1
                    color: control.filled ? control.filledInk
                        : (control.subtle ? Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.85)
                                          : control.ink)
                    // Plex carries both scripts so focus never swaps typefaces.
                    font.family: design.interfaceFamily
                    font.weight: control.subtle ? Font.Normal : Font.DemiBold
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                }
            }
        }
    }
}
