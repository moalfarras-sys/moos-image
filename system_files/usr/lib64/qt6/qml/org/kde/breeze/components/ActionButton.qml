/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2024 Noah Davis <noahadvs@gmail.com>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// Plasma's native login and lock controls supply the action, mnemonic and text.
// Keep them together as a single, touch-sized command on the session wallpaper.

import QtQuick
import QtQuick.Window
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

PlasmaComponents3.AbstractButton {
    id: root
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property var design: MoUI.Tokens
    // The session family is sized by one number, taken from the window
    // (Tokens.sessionScale): these keys shrink with everything else in a
    // 640x480 firmware mode, where software-rendered ARM guests commonly enter
    // the greeter, and grow with it on a large desktop.
    readonly property real sceneWidth: Window.width > 0 ? Window.width : Screen.width
    readonly property real sceneHeight: Window.height > 0 ? Window.height : Screen.height
    readonly property real compactScale: design.sessionScale(sceneWidth, sceneHeight)

    // The compiled greeter supplies these two legacy account icons.
    function symbolicName(name) {
        if (!name || name.endsWith("-symbolic")) {
            return name;
        }
        if (name === "system-user-prompt") {
            return "user-symbolic";
        }
        if (name === "system-user-list") {
            return "system-users-symbolic";
        }
        return name + "-symbolic";
    }

    readonly property bool destructive: root.icon.name === "system-shutdown"
                                        || root.icon.name === "system-shutdown-update"
    // The native dock paints the group's surface. A key paints over it only
    // for feedback; standalone callers retain their own command surface.
    readonly property bool docked: root.parent !== null && root.parent.moosDock === true
    readonly property bool lit: root.hovered || root.visualFocus
    readonly property color actionAccent: destructive ? Kirigami.Theme.negativeTextColor
                                                     : Kirigami.Theme.highlightColor
    readonly property color faceColor: down ? actionAccent
        : Qt.tint(Kirigami.Theme.backgroundColor, Qt.alpha(Kirigami.Theme.textColor, lit ? 0.07 : 0.025))
    readonly property color commandInk: down
        ? (destructive ? Kirigami.Theme.backgroundColor : Kirigami.Theme.highlightedTextColor)
        : Kirigami.Theme.textColor

    font.family: design.interfaceFamily
    font.pointSize: Math.max(8, Math.round((Kirigami.Theme.defaultFont.pointSize + 2)
                                           * Math.min(1.25, compactScale)))
    font.weight: Font.Medium
    hoverEnabled: true

    // The login manager loads this file from disk into an otherwise compiled
    // greeter. Keep the assistive contract local and explicit: a screen-reader
    // press must follow the exact same animated click path as the mnemonic.
    Accessible.role: Accessible.Button
    // Callers use KDE mnemonic markers ("Slee&p", "&Hibernate"). Exposing the
    // raw string makes assistive clients announce the implementation marker;
    // MnemonicData is already the source of the visible label and provides the
    // same label as plain text with markup and ampersands removed.
    // The caption and the spoken name are the same words: plasma_login's
    // text, in the session's own Arabic where MoUI.SessionText knows a
    // better one (presentation only; the action is upstream's).
    readonly property string presentedLabel: MoUI.SessionText.present(root.Kirigami.MnemonicData.plainTextLabel,
                                                                       MoUI.SessionText.isArabic(Qt.locale().name))
    Accessible.name: root.presentedLabel
    Accessible.pressed: root.down
    Accessible.onPressAction: root.animateClick()

    implicitWidth: Math.max(design.targetControl, contents.implicitWidth + horizontalPadding * 2)
    implicitHeight: Math.max(design.targetControl, contents.implicitHeight + verticalPadding * 2)
    horizontalPadding: Math.round(Kirigami.Units.gridUnit * Math.max(0.8, compactScale)
                                  * (docked ? 0.65 : 1))
    verticalPadding: Math.round(Kirigami.Units.smallSpacing * Math.max(1, compactScale))
    leftInset: 0
    rightInset: 0
    topInset: 0
    bottomInset: 0
    opacity: enabled ? 1 : design.disabledOpacity
    scale: down ? design.pressScale : 1
    Behavior on scale {
        NumberAnimation { duration: design.duration(root.motionEnabled, design.motionFast) }
    }

    Kirigami.MnemonicData.enabled: root.enabled && root.visible
    Kirigami.MnemonicData.controlType: Kirigami.MnemonicData.SecondaryControl
    Kirigami.MnemonicData.label: root.text

    Shortcut {
        //in case of explicit & the button manages it by itself
        enabled: !(RegExp(/\&[^\&]/).test(root.text))
        sequence: root.Kirigami.MnemonicData.sequence
        onActivated: root.animateClick()
    }

    background: MoUI.Surface {
        LayoutMirroring.enabled: root.mirrored
        objectName: "moosSessionActionSurface"
        radius: design.radiusControl
        visible: !root.docked || root.lit || root.down
        color: root.faceColor
        border.width: root.visualFocus ? design.focusWidth : design.borderHairline
        border.color: root.visualFocus ? root.actionAccent
            : Qt.alpha(Kirigami.Theme.textColor, root.hovered ? 0.28 : 0.16)
    }

    contentItem: Item {
        implicitWidth: contents.implicitWidth
        implicitHeight: contents.implicitHeight
        Row {
            id: contents
            anchors.centerIn: parent
            LayoutMirroring.enabled: false
            layoutDirection: root.mirrored ? Qt.RightToLeft : Qt.LeftToRight
            spacing: Math.round(Kirigami.Units.smallSpacing * 1.5 * root.compactScale)

            MoUI.SessionActionGlyph {
                anchors.verticalCenter: parent.verticalCenter
                source: root.symbolicName(root.icon.name)
                accentColor: root.faceColor
                inkColor: root.commandInk
                embeddedInAccent: true
                implicitWidth: Math.round(root.design.targetControl * Math.min(1.22, root.compactScale))
                implicitHeight: implicitWidth
                active: root.lit
            }
            PlasmaComponents3.Label {
                objectName: "moosSessionActionCaption"
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, root.sceneWidth * 0.42)
                text: root.presentedLabel !== root.Kirigami.MnemonicData.plainTextLabel
                    ? root.presentedLabel : root.Kirigami.MnemonicData.richTextLabel
                textFormat: Text.StyledText
                font: root.font
                color: root.commandInk
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }
    }

    Keys.onEnterPressed: clicked()
    Keys.onReturnPressed: clicked()
}
