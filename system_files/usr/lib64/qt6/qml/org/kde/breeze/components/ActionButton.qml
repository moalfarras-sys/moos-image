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
//   3. The circle is MoOS glass — a tinted brand halo that answers the pointer —
//      instead of a flat 15%-opacity text-coloured blob.
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

    font.family: "IBM Plex Sans"
    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
    font.underline: root.activeFocus

    icon.width: Kirigami.Units.iconSizes.large
    icon.height: Kirigami.Units.iconSizes.large

    hoverEnabled: true

    // Expand clickable area, keep background centered
    leftInset: Math.max(Kirigami.Units.largeSpacing * 4, (implicitContentWidth - implicitBackgroundWidth) / 2)
    rightInset: leftInset

    padding: Kirigami.Units.smallSpacing
    // Labels wider than the background shouldn't be padded
    horizontalPadding: 0
    // No padding below label
    bottomPadding: 0

    // padding for circle and spacing between circle and label
    spacing: padding + Kirigami.Units.smallSpacing

    opacity: root.lit ? 1 : 0.85
    Behavior on opacity {
        PropertyAnimation { // OpacityAnimator makes it turn black at random intervals
            duration: Kirigami.Units.longDuration
            easing.type: Easing.InOutQuad
        }
    }

    // MoOS: the same answer-the-pointer lift the logout screen's buttons have.
    scale: root.down ? 0.98 : (root.hovered ? 1.03 : 1.0)
    Behavior on scale {
        NumberAnimation {
            duration: Kirigami.Units.shortDuration
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
        implicitWidth: root.icon.width + root.padding * 2
        implicitHeight: root.icon.height + root.padding * 2
        // explicitly set size to keep it from expanding or shrinking
        width: implicitWidth
        height: implicitHeight
        radius: width / 2
        // MoOS glass: the brand tint, warmed by the pointer. Software rendering
        // keeps upstream's opaque fallback — a tint over an unblurred surface
        // reads as dirt, and that path exists for machines with no GPU at all.
        color: root.softwareRendering
             ? Kirigami.Theme.backgroundColor
             : (root.destructive ? Kirigami.Theme.negativeTextColor
                                 : Kirigami.Theme.highlightColor)
        opacity: {
            if (root.softwareRendering) {
                return root.lit ? 0.8 : 0.6
            }
            return root.lit ? 0.26 : 0.14
        }
        Behavior on opacity {
            PropertyAnimation { // OpacityAnimator makes it turn black at random intervals
                duration: Kirigami.Units.longDuration
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
            border.color: Kirigami.Theme.textColor
            opacity: root.lit ? 0.22 : 0.10
        }
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Kirigami.Theme.textColor
            opacity: 0.15
            scale: root.down ? 1 : 0
            Behavior on scale {
                PropertyAnimation {
                    duration: Kirigami.Units.shortDuration
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
            color: root.destructive ? Kirigami.Theme.negativeTextColor
                                    : Kirigami.Theme.highlightColor
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
            font.family: "IBM Plex Sans"
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
