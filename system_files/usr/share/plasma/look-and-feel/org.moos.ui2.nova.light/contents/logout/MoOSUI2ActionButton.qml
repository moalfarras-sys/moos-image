/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS UI2 — Tidal Portal key. Each action is a compact rounded threshold with
    a horizon cut and a label beneath. The public API
    is unchanged (iconName, text, description, emphasized, destructive, armed,
    clicked, navigate) so the logout logic drives it exactly as before; only the
    shape is new. Two-tone accent (accentA fill + accentB rim, both derived from
    the live theme) so every palette lights the key in its own two colours while
    the glyph remains on one contrast-gated fill. Hover blooms and grows, focus
    rings and press acknowledgement. Armed state is a still high-contrast fill
    for the confirm tap on sensitive actions. `subtle` is the one later addition:
    a second, quieter weight for Cancel, which is not a peer of Shut Down.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

import org.kde.kirigami as Kirigami

QQC2.AbstractButton {
    id: control

    property alias iconName: actionIcon.source
    property string description: ""
    property bool emphasized: false
    property bool destructive: false
    property bool armed: false   // a sensitive action awaiting its confirm tap
    // The way OUT is not an action. `subtle` renders the same key one step down
    // the hierarchy — a smaller disc, a lighter caption — so the dock reads
    // first and Cancel second. Only Cancel sets it.
    property bool subtle: false

    readonly property bool lit: hovered || visualFocus || down
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
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
    // The disc fills with one contrast-gated role when emphasized, pressed, or
    // armed. Selection ink is paired with highlight; destructive ink is the
    // Complementary background paired with ForegroundNegative. Both relationships
    // are measured across all 16 schemes in tests/test_moos_ui2.py.
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

    readonly property real keyHeight: Kirigami.Units.gridUnit * (control.subtle ? 3.6 : 4.8)
    readonly property real keyWidth: Kirigami.Units.gridUnit * (control.subtle ? 4.8 : 5.8)
    implicitWidth: Kirigami.Units.gridUnit * 7
    implicitHeight: keyHeight + Kirigami.Units.gridUnit * 2.7
    padding: 0
    scale: down ? 0.97 : (lit ? 1.025 : 1.0)
    Behavior on scale {
        NumberAnimation {
            duration: control.motionEnabled ? Kirigami.Units.shortDuration : 0
            easing.type: Easing.OutCubic
        }
    }

    Keys.onUpPressed: navigate(0, -1)
    Keys.onDownPressed: navigate(0, 1)
    Keys.onLeftPressed: navigate(-1, 0)
    Keys.onRightPressed: navigate(1, 0)

    background: null

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.smallSpacing

        // ── The portal key ───────────────────────────────────────────────────
        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: control.keyWidth
            implicitHeight: control.keyHeight

            // A still depth plate replaces the old pulsing orb. Armed state is
            // unmistakable through fill, text and border; it never needs a loop.
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 1.12
                height: parent.height * 1.24
                radius: Math.min(width, height) * 0.28
                visible: control.lit || control.armed
                color: control.accentA
                opacity: control.armed ? 0.12 : 0.055
            }

            // One contrast-paired key surface.
            Rectangle {
                id: disc
                anchors.fill: parent
                radius: Math.min(width, height) * 0.28
                color: control.filled
                    ? control.accentA
                    : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, control.lit ? 0.16 : 0.08)
                border.width: control.visualFocus ? 2 : 1
                border.color: control.filled
                    ? control.accentB
                    : (control.lit ? Qt.rgba(control.accentA.r, control.accentA.g, control.accentA.b, 0.8)
                                   : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.16))

                // The same crest cut that seals the full-screen horizon.
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: -height / 2
                    width: parent.width * 0.30
                    height: control.visualFocus ? 3 : 2
                    radius: height / 2
                    color: control.filled ? control.filledInk : control.accentB
                    opacity: control.lit || control.filled ? 0.95 : 0.62
                }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: Math.max(5, parent.height * 0.10)
                    width: parent.width * 0.42
                    height: 1
                    radius: height / 2
                    color: control.filled ? control.filledInk : control.accentA
                    opacity: control.lit || control.filled ? 0.55 : 0.22
                }

                Kirigami.Icon {
                    id: actionIcon
                    anchors.centerIn: parent
                    // Size the glyph FROM the disc it sits in. This was
                    // iconSizes.medium — one fixed step that does not know the
                    // key exists, so the mark cannot rattle around inside the
                    // surface. Not snapped to a standard
                    // icon step on purpose: the sources are -symbolic SVGs, so
                    // Kirigami renders them crisp at any size, and snapping down
                    // (roundedIconSize(38) is 32) would just restore the bug.
                    width: Math.round(control.keyHeight * 0.42)
                    height: width
                    isMask: true
                    color: control.filled
                        ? control.filledInk
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
            // NOT dimmed for `subtle`: a lighter alpha here measured 4.12:1 on
            // the Tidal Light render, under WCAG AA. The smaller disc and the
            // lighter weight carry the hierarchy; the caption stays legible.
            color: (control.lit || control.emphasized || control.armed)
                ? Kirigami.Theme.textColor
                : Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.85)
            // Plex carries both scripts so focus never swaps typefaces.
            font.family: "IBM Plex Sans Arabic"
            font.weight: control.subtle ? Font.Normal : Font.DemiBold
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
            // The description is always a bilingual() string, so it takes the
            // one face that carries both scripts — Inter has no Arabic and would
            // hand this line to Noto. See the note on bilingual() in Logout.qml.
            font.family: "IBM Plex Sans Arabic"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
        }
    }
}
