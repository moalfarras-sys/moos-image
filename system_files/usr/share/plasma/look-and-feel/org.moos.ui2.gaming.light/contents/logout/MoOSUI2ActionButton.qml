/*
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    The account's Window and Selection colour sets supply both parts of each
    native command. Only an emphasized, pressed or armed command fills with
    the semantic accent. The ordinary glyph and caption share a single face.
*/
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window

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
    readonly property color accentB: control.destructive ? control.accentA : design.sessionRim(control.accentA, Kirigami.Theme.linkColor)
    readonly property color ink: Kirigami.Theme.textColor
    // The tile fills with one contrast-gated role when emphasized, pressed, or
    // armed. Selection ink is paired with highlight; destructive ink is the
    // Complementary background paired with ForegroundNegative.
    readonly property bool filled: control.emphasized || control.down || control.armed
    readonly property color filledInk: control.destructive
        ? Kirigami.Theme.backgroundColor
        : Kirigami.Theme.highlightedTextColor

    // Keep the destructive role on its measured Window background until the
    // entire tile fills. The normal mark takes a quieter shade of the link ink.
    readonly property color restingGlyphInk: destructive ? accentA
        : Qt.tint(ink, Qt.alpha(Kirigami.Theme.linkColor, 0.65))

    signal navigate(int horizontalStep, int verticalStep)
    signal interacted()
    onPressed: interacted()

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
    // The session family's one size, from the window this tile is in.
    readonly property real sessionScale: design.sessionScale(Window.width, Window.height)
    readonly property real keyHeight: Math.max(design.targetControl,
        Kirigami.Units.gridUnit * (control.subtle ? 3.1 : 5.3) * sessionScale)
    readonly property real keyWidth: Kirigami.Units.gridUnit * (control.subtle ? 10.4 : 8.6) * sessionScale
    // The way out is one line of words, and it must never be cut short: on a
    // small screen the pill takes the width its caption needs.
    readonly property real fittedWidth: control.subtle
        ? Math.max(keyWidth, caption.implicitWidth + Kirigami.Units.gridUnit * 2)
        : keyWidth
    implicitWidth: fittedWidth
    implicitHeight: keyHeight
    padding: 0
    scale: down ? design.pressScale : 1.0
    Behavior on scale {
        NumberAnimation {
            duration: design.duration(control.motionEnabled, design.motionFast)
            easing.type: design.easeStandard
        }
    }

    Keys.onPressed: event => { interacted(); event.accepted = false; }
    Keys.onUpPressed: { interacted(); navigate(0, -1); }
    Keys.onDownPressed: { interacted(); navigate(0, 1); }
    Keys.onLeftPressed: { interacted(); navigate(-1, 0); }
    Keys.onRightPressed: { interacted(); navigate(1, 0); }
    Keys.onReturnPressed: event => {
        if (!event.isAutoRepeat) { interacted(); control.animateClick(); }
    }
    Keys.onEnterPressed: event => {
        if (!event.isAutoRepeat) { interacted(); control.animateClick(); }
    }

    background: null

    contentItem: Item {
        implicitWidth: control.fittedWidth
        implicitHeight: control.keyHeight

        // One contrast-paired tile surface.
        MoUI.Surface {
            id: disc
            LayoutMirroring.enabled: control.mirrored
            objectName: "moosPowerActionSurface"
            anchors.fill: parent
            radius: design.radiusControl
            color: control.filled
                ? control.accentA
                : (control.destructive ? Kirigami.Theme.backgroundColor
                    : Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(control.ink, control.lit ? 0.07 : 0.025)))
            border.width: control.visualFocus ? design.focusWidth : design.borderHairline
            border.color: control.filled
                ? control.accentB
                : (control.visualFocus ? control.accentA
                    : Qt.alpha(control.ink, control.hovered ? 0.28 : 0.16))

            // Glyph above caption, both inside the tile.
            ColumnLayout {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.largeSpacing * 2
                spacing: control.subtle ? 0 : Kirigami.Units.smallSpacing

                MoUI.SessionActionGlyph {
                    id: actionIcon
                    Layout.alignment: Qt.AlignHCenter
                    // Size the glyph FROM the tile it sits in — the -symbolic
                    // sources render crisp at any size, so no step snapping.
                    // The subtle (Cancel) pill is text-only: the caption alone
                    // reads faster than glyph+word at its quiet weight.
                    visible: !control.subtle
                    Layout.preferredWidth: Math.round(design.targetControl * control.sessionScale)
                    Layout.preferredHeight: Layout.preferredWidth
                    accentColor: disc.color
                    inkColor: control.filled ? control.filledInk : control.restingGlyphInk
                    embeddedInAccent: true
                }
                QQC2.Label {
                    id: caption
                    objectName: "moosPowerActionCaption"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: control.text
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    wrapMode: Text.WordWrap
                    maximumLineCount: control.subtle ? 1 : 2
                    color: control.filled ? control.filledInk
                        : (control.subtle ? Qt.rgba(control.ink.r, control.ink.g, control.ink.b, 0.85)
                                          : control.ink)
                    // Meyar carries both scripts across every button state.
                    font.family: design.interfaceFamily
                    font.weight: control.subtle ? Font.Normal : Font.DemiBold
                    font.pointSize: Math.max(8, Math.round((Kirigami.Theme.defaultFont.pointSize + 1)
                                                           * Math.min(1.3, control.sessionScale)))
                }
            }
        }
    }
}
