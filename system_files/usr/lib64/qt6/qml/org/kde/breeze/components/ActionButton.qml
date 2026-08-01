/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2024 Noah Davis <noahadvs@gmail.com>
    SPDX-FileCopyrightText: 2026 Moalfarras — MoOS identity

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

// MoOS: this IS Plasma's own ActionButton, wearing the MoOS identity.
//
// Why it is edited in place rather than wrapped, hidden, or duplicated: this one
// file is where the login screen, the lock screen AND the logout screen all get
// their action buttons. plasma-login-manager's greeter QML is compiled into the
// binary (qrc:/qt/qml/org/kde/plasma/login/Main.qml), so the greeter itself can
// never be replaced from the filesystem — but every button it draws comes from
// HERE, on disk, and Plasma looks this module up by import path. Change this and
// Plasma's own login screen becomes MoOS, with nothing layered over it and
// nothing hidden. That is the whole point: MoOS is not a skin on top of Plasma,
// it is Plasma.
//
// What changed from upstream, and why each one:
//   1. FULL-COLOUR DISCS → the MoOS symbolic mark. The greeter asks for
//      "system-shutdown"; Colloid answers with a red disc, and the login screen
//      ended up wearing three primary-coloured buttons two seconds before the
//      MoOS logout screen showed the same six actions as monochrome teal glyphs.
//      Session F fixed exactly this class of bug on the logout screen ("isMask
//      over full-colour disc icons"); the login screen was simply out of reach
//      then. symbolicName() maps each name the greeter can ask for onto its
//      -symbolic variant, and isMask paints it in the brand colour.
//   2. Destructive intent is SAID, not decorated: Shut Down and Restart carry
//      the negative colour, exactly as they do on MoOS's logout screen.
//   3. The control is a MoOS portal key — rounded threshold, crest cut and
//      horizon line — instead of Plasma's generic circle.
//   4. IBM Plex Sans, the family every other MoOS surface uses.
//
// The upstream contract is untouched: same id, same API (text, icon.name,
// enabled, visible, clicked, animateClick), same mnemonic and key handling, same
// softwareRendering fallback. A caller cannot tell the difference — which is why
// the compiled greeter, the lock screen and the logout screen all keep working.

import QtQuick
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami

PlasmaComponents3.AbstractButton {
    id: root
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1

    // MoOS: the greeter hands us a full-colour icon name. Map it to the symbolic
    // glyph so isMask can paint it in the brand colour. Names already ending in
    // -symbolic pass through, and anything unmapped keeps its own name rather
    // than vanishing — an unknown action must still draw SOMETHING.
    //
    // system-user-prompt and system-user-list have no -symbolic variant in the
    // icon theme (checked, 2026-07-17), so they borrow the closest ones that do:
    // one person for "type a username", several for "show the user list".
    //
    // The substitutes were chosen by RENDERING every candidate under isMask and
    // looking, not by the name reading well: user-identity-symbolic — the obvious
    // pick — is a FILLED disc, so masking it produced a solid teal blob with no
    // glyph at all. That is the same failure session F hit on the logout screen's
    // nine icons. A name is not evidence; the picture is.
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

    // Shutting the machine down is the one action here you cannot take back, and
    // MoOS's logout screen already says exactly that: Shut Down wears the negative
    // colour and every other action — Restart included — stays brand teal. The
    // login screen follows the screen the user already knows. (Restart WAS red
    // here for one build; two red buttons side by side read as an alarm, and it
    // disagreed with the logout screen. One system, one language.)
    readonly property bool destructive: root.icon.name === "system-shutdown"
    readonly property bool lit: root.activeFocus || root.hovered

    // Plex Arabic, never Inter: Inter has no Arabic coverage, so its Arabic
    // text silently falls back to Noto — a second Arabic face on the same
    // screen as the Plex date. Plex Arabic carries a full Latin set. And
    // font.families does not exist on Qt 6.11.1 here — see Logout.qml.
    font.family: "IBM Plex Sans Arabic"
    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
    font.underline: root.activeFocus

    // MoOS token: medium glyph inside the same portal key used by Logout, so
    // the lock's session buttons and the power dock are
    // the same control at the same size.
    icon.width: Kirigami.Units.iconSizes.medium
    icon.height: Kirigami.Units.iconSizes.medium

    hoverEnabled: true

    // The login manager loads this file from disk into an otherwise compiled
    // greeter. Keep the assistive contract local and explicit: a screen-reader
    // press must follow the exact same animated click path as the mnemonic.
    Accessible.role: Accessible.Button
    Accessible.name: root.text
    Accessible.pressed: root.down
    Accessible.onPressAction: root.animateClick()

    // Expand clickable area, keep background centered
    leftInset: Math.max(Kirigami.Units.largeSpacing * 4, (implicitContentWidth - implicitBackgroundWidth) / 2)
    rightInset: leftInset

    padding: Kirigami.Units.smallSpacing
    // Labels wider than the background shouldn't be padded
    horizontalPadding: 0
    // No padding below label
    bottomPadding: 0

    // MoOS token: the same disc-to-label gap as the logout orb.
    spacing: Kirigami.Units.smallSpacing

    opacity: root.lit ? 1 : 0.85
    Behavior on opacity {
        PropertyAnimation { // OpacityAnimator makes it turn black at random intervals
            duration: root.motionEnabled ? Kirigami.Units.longDuration : 0
            easing.type: Easing.InOutQuad
        }
    }

    // MoOS: the same answer-the-pointer lift the logout screen's buttons have.
    scale: root.down ? 0.98 : (root.hovered ? 1.03 : 1.0)
    Behavior on scale {
        NumberAnimation {
            duration: root.motionEnabled ? Kirigami.Units.shortDuration : 0
            easing.type: Easing.OutCubic
        }
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

    background: Rectangle {
        // The Tidal Portal key: a wide, calm threshold instead of a generic
        // circular icon button.
        implicitWidth: Kirigami.Units.gridUnit * 5.4
        implicitHeight: Kirigami.Units.gridUnit * 3.9
        // explicitly set size to keep it from expanding or shrinking
        width: implicitWidth
        height: implicitHeight
        radius: height * 0.30
        // MoOS glass: the brand tint, warmed by the pointer. Software rendering
        // keeps upstream's opaque fallback — a tint over an unblurred surface
        // reads as dirt, and that path exists for machines with no GPU at all.
        // MoOS UI2 — the SAME frosted disc as the logout dock's orbs: a neutral
        // ink fill (not an accent-tinted blob), so the lock's session buttons and
        // the power dock read as one control family. The accent lives on the
        // border when lit, exactly like the orb.
        color: root.softwareRendering
             ? Kirigami.Theme.backgroundColor
             : (root.destructive ? Kirigami.Theme.negativeTextColor
                                 : Kirigami.Theme.textColor)
        opacity: {
            if (root.softwareRendering) {
                return root.lit ? 0.8 : 0.6
            }
            return root.lit ? 0.16 : 0.08
        }
        Behavior on opacity {
            PropertyAnimation { // OpacityAnimator makes it turn black at random intervals
                duration: root.motionEnabled ? Kirigami.Units.longDuration : 0
                easing.type: Easing.InOutQuad
            }
        }
        // MoOS: a hairline that catches the light, the same one the dock, the
        // lock card and the Hero Clock carry.
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            visible: !root.softwareRendering
            border.width: 1
            // Accent border when lit (hover/focus), hairline ink when idle —
            // matching the logout orb's border exactly.
            border.color: root.lit
                ? (root.destructive ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.highlightColor)
                : Kirigami.Theme.textColor
            opacity: root.lit ? 0.8 : 0.16
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: -height / 2
            width: parent.width * 0.28
            height: root.activeFocus ? 3 : 2
            radius: height / 2
            color: root.destructive
                ? Kirigami.Theme.negativeTextColor
                : Kirigami.Theme.highlightColor
            opacity: root.lit ? 0.96 : 0.62
        }
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: Math.max(4, parent.height * 0.10)
            width: parent.width * 0.42
            height: 1
            radius: height / 2
            color: root.destructive
                ? Kirigami.Theme.negativeTextColor
                : Kirigami.Theme.highlightColor
            opacity: root.lit ? 0.55 : 0.22
        }
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Kirigami.Theme.textColor
            opacity: 0.15
            scale: root.down ? 1 : 0
            Behavior on scale {
                PropertyAnimation {
                    duration: root.motionEnabled ? Kirigami.Units.shortDuration : 0
                    easing.type: Easing.InOutQuart
                }
            }
        }
    }

    contentItem: Column {
        spacing: root.spacing
        Kirigami.Icon {
            anchors.horizontalCenter: parent.horizontalCenter
            // MoOS: the symbolic glyph, painted in the brand colour.
            source: root.symbolicName(root.icon.name)
            isMask: !root.softwareRendering
            // Ink glyph (not accent) — the logout orbs paint their glyph in ink
            // too; the accent shows on the border/hover, keeping one language.
            color: root.destructive ? Kirigami.Theme.negativeTextColor
                                    : Kirigami.Theme.textColor
            implicitWidth: root.icon.width
            implicitHeight: root.icon.height
            active: root.lit
        }
        PlasmaComponents3.Label {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(implicitWidth, parent.width)
            text: root.Kirigami.MnemonicData.richTextLabel
            style: root.softwareRendering ? Text.Outline : Text.Normal
            styleColor: Kirigami.Theme.backgroundColor // Unused without outline
            font.family: "IBM Plex Sans Arabic"
            font.weight: Font.DemiBold
            color: root.destructive ? Kirigami.Theme.negativeTextColor
                                    : Kirigami.Theme.textColor
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignTop
            textFormat: Text.StyledText
            wrapMode: Text.WordWrap
        }
    }

    Keys.onEnterPressed: clicked()
    Keys.onReturnPressed: clicked()
}
