/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: LGPL-2.0-or-later

    This IS the plasma-desktop shell's lockscreen MainBlock.qml, overridden by
    MoOS. It is the auth cluster that lives INSIDE the frosted glass card drawn
    by LockScreenUi.qml: the user avatar + name (from SessionManagementScreen),
    the password field, the unlock button, and the fingerprint/smartcard hints.

    It was the last stock-Breeze surface on an otherwise fully-MoOS lock screen —
    the deferred "auth card" item. This fork dresses the password field, the
    unlock button and the notice line in MoOS UI2 (glass field with a
    brand-accent focus ring; a Tidal Portal unlock key; a glass notice pill in
    place of the base's plain italic label) and NOTHING else.

    AUTH SAFETY CONTRACT — read before editing:
      Every line that touches authentication is kept BYTE-IDENTICAL to the base
      file shipped by plasma-workspace: the SessionManagementScreen root and its
      `userList`/avatar, the `mainPasswordBox`/`showPassword` aliases, the
      `passwordResult` signal, `startLogin()`, `onUserSelected`, the passwordBox
      id/text/PasswordSync binding/onAccepted/Keys/Connections, the loginButton
      id/onClicked/Keys, and both FailableLabels' kind/visible/text/Connections.
      The ONLY additions are visual: a `background:` on the field,
      `topPadding`/`bottomPadding`, the button's `background:`/`contentItem:`,
      typography on the two hint labels, and the notice pill — which only ever
      DISPLAYS a string LockScreenUi hands it. This file must never be the reason
      someone cannot unlock their own machine — restyle, never rewire.
*/

import QtQuick

import QtQuick.Layouts

import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.kscreenlocker as ScreenLocker

import org.kde.breeze.components

SessionManagementScreen {
    id: sessionManager

    readonly property alias mainPasswordBox: passwordBox
    property bool lockScreenUiVisible: false
    property alias showPassword: passwordBox.showPassword

    // ── Two-tone MoOS accent (visual only) ──────────────────────────────────
    // A second hue derived from the live theme highlight, so the unlock button
    // spans TWO of the palette's colours instead of one flat tint. Mirrors the
    // accentB used across the lock scene. Never touches the auth path.
    readonly property color accentA: Kirigami.Theme.highlightColor
    readonly property color accentB: {
        const c = Kirigami.Theme.highlightColor;
        if (c.hslSaturation < 0.08 || c.hslHue < 0) {
            return Qt.lighter(c, 1.28);
        }
        let nh = c.hslHue + 0.09;
        if (nh > 1) { nh -= 1; }
        return Qt.hsla(nh, Math.min(1, c.hslSaturation), Math.min(0.72, c.hslLightness * 1.08), 1);
    }

    // ── The notice line (visual only — see AUTH SAFETY CONTRACT) ────────────
    // "Unlocking failed" and "Caps Lock is on" are the most important things
    // this screen ever says, and they were the last stock-Breeze voice on it: a
    // plain italic Label in the ordinary text colour, wedged above the prompts.
    //
    // The base SessionManagementScreen hands a derived component exactly ONE
    // handle on that label — `notificationMessage`, an alias to its `text`.
    // There is no `visible` alias and no way to reach the item itself. So the
    // base label is held EMPTY (it still reserves its blank line, which is what
    // keeps the cluster from jumping when a message arrives) and LockScreenUi
    // feeds the text to `notice` here instead, where it can be drawn as MoOS
    // glass. Nothing on this path touches the authenticator: the pill only ever
    // displays a string that has already been assembled elsewhere.
    property string notice: ""
    notificationMessage: ""

    // A refusal wears the negative role; a hint (Caps Lock, a PAM prompt) must
    // not — a red pill for "Caps Lock is on" would cry wolf at the one place
    // where red has to mean something. `root.notification` is set only by
    // LockScreenUi's authenticator handlers, so it is the honest test for "this
    // was a refusal"; MainBlock already talks to `root` for clearPassword.
    readonly property bool noticeIsAlert: root.notification !== ""

    //the y position that should be ensured visible when the on screen keyboard is visible
    property int visibleBoundary: mapFromItem(loginButton, 0, 0).y
    onHeightChanged: visibleBoundary = mapFromItem(loginButton, 0, 0).y + loginButton.height + Kirigami.Units.smallSpacing
    /*
     * Login has been requested with the following username and password
     * If username field is visible, it will be taken from that, otherwise from the "name" property of the currentIndex
     */
    signal passwordResult(string password)

    onUserSelected: {
        const nextControl = (passwordBox.visible ? passwordBox : loginButton);
        // Don't startLogin() here, because the signal is connected to the
        // Escape key as well, for which it wouldn't make sense to trigger
        // login. Using TabFocusReason, so that the loginButton gets the
        // visual highlight.
        nextControl.forceActiveFocus(Qt.TabFocusReason);
    }

    function startLogin() {
        const password = passwordBox.text

        // This is partly because it looks nicer, but more importantly it
        // works round a Qt bug that can trigger if the app is closed with a
        // TextField focused.
        //
        // See https://bugreports.qt.io/browse/QTBUG-55460
        loginButton.forceActiveFocus();
        passwordResult(password);
    }

    // The glass notice pill. It sits directly above the field the message is
    // about, rises the last half grid unit as it fades in (the Translate below
    // is driven by the pill's own opacity, so the entrance needs no animation of
    // its own — nothing here loops), and carries the message on a translucent
    // surface with one luminous edge, like every other MoOS control.
    Rectangle {
        id: noticePill

        Layout.alignment: Qt.AlignHCenter
        Layout.bottomMargin: Kirigami.Units.smallSpacing

        // The pill takes its size from the label and the label caps its OWN
        // width, rather than the label filling the pill: a wrapping Text whose
        // width comes from its parent, while the parent's implicit width comes
        // from the Text, is the classic QML binding loop. Here the label's width
        // depends only on its content and a constant, so nothing is circular.
        implicitWidth: noticeLabel.width + Kirigami.Units.gridUnit * 2
        implicitHeight: noticeLabel.implicitHeight + Kirigami.Units.largeSpacing

        // A pill for the one-line case, a rounded card when PAM says something
        // long enough to wrap. The message is never elided: on this screen the
        // text IS the reason the machine refused, and half of it is worse than
        // an extra line.
        radius: Math.min(height / 2, Kirigami.Units.gridUnit * 1.2)
        visible: opacity > 0
        opacity: sessionManager.notice !== "" ? 1 : 0
        transform: Translate { y: (1 - noticePill.opacity) * Kirigami.Units.gridUnit * 0.5 }

        color: sessionManager.noticeIsAlert
            ? Qt.rgba(Kirigami.Theme.negativeTextColor.r,
                      Kirigami.Theme.negativeTextColor.g,
                      Kirigami.Theme.negativeTextColor.b, 0.16)
            : Qt.rgba(Kirigami.Theme.backgroundColor.r,
                      Kirigami.Theme.backgroundColor.g,
                      Kirigami.Theme.backgroundColor.b, 0.55)
        border.width: 1
        border.color: sessionManager.noticeIsAlert
            ? Qt.rgba(Kirigami.Theme.negativeTextColor.r,
                      Kirigami.Theme.negativeTextColor.g,
                      Kirigami.Theme.negativeTextColor.b, 0.65)
            : Qt.rgba(Kirigami.Theme.textColor.r,
                      Kirigami.Theme.textColor.g,
                      Kirigami.Theme.textColor.b, 0.20)

        Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
        Behavior on color { ColorAnimation { duration: Kirigami.Units.longDuration } }

        PlasmaComponents3.Label {
            id: noticeLabel
            anchors.centerIn: parent
            width: Math.min(implicitWidth, Kirigami.Units.gridUnit * 16)
            text: sessionManager.notice
            textFormat: Text.PlainText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            // Plex Arabic, never Inter: Inter has no Arabic coverage, so its Arabic
            // text silently falls back to Noto — a second Arabic face on the same
            // screen as the Plex date. Plex Arabic carries a full Latin set. And
            // font.families does not exist on Qt 6.11.1 here — see Logout.qml.
            font.family: "IBM Plex Sans Arabic"
            font.pointSize: Kirigami.Theme.defaultFont.pointSize
            font.weight: Font.Medium
            color: sessionManager.noticeIsAlert ? Kirigami.Theme.negativeTextColor
                                                : Kirigami.Theme.textColor
        }

        // The base's playHighlightAnimation() bounces the label MoOS holds
        // empty. When the authenticator repeats a message it has already shown,
        // bounce the pill that is actually carrying it — otherwise a repeated
        // "Unlocking failed" would look like nothing happened at all. Durations
        // come from Kirigami, so this collapses to an instant with animations
        // off; it is one-shot either way and never loops.
        SequentialAnimation {
            id: noticeBounce
            running: false
            NumberAnimation {
                target: noticePill; property: "scale"
                from: 1.0; to: 1.06
                duration: Kirigami.Units.longDuration
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: noticePill; property: "scale"
                from: 1.06; to: 1.0
                duration: Kirigami.Units.longDuration
                easing.type: Easing.InQuad
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        PlasmaExtras.PasswordField {
            id: passwordBox
            Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:accessible", "Password")
            font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
            Layout.fillWidth: true
            text: PasswordSync.password

            placeholderText: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:placeholder in text field", "Password")
            focus: true
            enabled: !authenticator.graceLocked

            // ── MoOS UI2 visual only (see AUTH SAFETY CONTRACT) ──────────────
            // A little more air than Breeze's default so the field reads as a
            // premium glass control on the card.
            topPadding: Kirigami.Units.largeSpacing * 1.1
            bottomPadding: Kirigami.Units.largeSpacing * 1.1
            leftPadding: Kirigami.Units.gridUnit * 1.4
            rightPadding: Kirigami.Units.gridUnit * 1.4
            // The MoOS glass field: a full-height translucent pill with a hairline
            // border that swells into the active accent (plus a soft accent glow)
            // when the field has focus — a premium control, not a boxy input.
            background: Rectangle {
                radius: height / 2
                color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                               Kirigami.Theme.backgroundColor.g,
                               Kirigami.Theme.backgroundColor.b, passwordBox.activeFocus ? 0.62 : 0.48)
                border.width: passwordBox.activeFocus ? 1.5 : 1
                border.color: passwordBox.activeFocus
                    ? Qt.rgba(Kirigami.Theme.highlightColor.r,
                              Kirigami.Theme.highlightColor.g,
                              Kirigami.Theme.highlightColor.b, 0.95)
                    : Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.18)
                Behavior on border.color { ColorAnimation { duration: Kirigami.Units.longDuration } }
                // soft accent glow when focused
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width + Kirigami.Units.gridUnit
                    height: parent.height + Kirigami.Units.gridUnit
                    radius: height / 2
                    z: -1
                    color: "transparent"
                    border.width: Kirigami.Units.smallSpacing
                    border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                                          Kirigami.Theme.highlightColor.g,
                                          Kirigami.Theme.highlightColor.b, passwordBox.activeFocus ? 0.14 : 0.0)
                    Behavior on border.color { ColorAnimation { duration: Kirigami.Units.longDuration } }
                }
            }

            // In Qt this is implicitly active based on focus rather than visibility
            // in any other application having a focussed invisible object would be weird
            // but here we are using to wake out of screensaver mode
            // We need to explicitly disable cursor flashing to avoid unnecessary renders
            cursorVisible: visible

            onAccepted: {
                if (sessionManager.lockScreenUiVisible) {
                    sessionManager.startLogin();
                }
            }

            //if empty and left or right is pressed change selection in user switch
            //this cannot be in keys.onLeftPressed as then it doesn't reach the password box
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Left && !text) {
                    sessionManager.userList.decrementCurrentIndex();
                    event.accepted = true
                }
                if (event.key === Qt.Key_Right && !text) {
                    sessionManager.userList.incrementCurrentIndex();
                    event.accepted = true
                }
            }

            Connections {
                target: root
                function onClearPassword() {
                    passwordBox.forceActiveFocus()
                    passwordBox.text = "";
                    passwordBox.text = Qt.binding(() => PasswordSync.password);
                }
                function onNotificationRepeated() {
                    noticeBounce.restart();
                }
            }
        }
        Binding {
            target: PasswordSync
            property: "password"
            value: passwordBox.text
        }

        PlasmaComponents3.Button {
            id: loginButton
            Accessible.role: Accessible.Button
            Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button accessible only", "Unlock")
            Accessible.pressed: down
            Layout.preferredHeight: passwordBox.implicitHeight
            Layout.preferredWidth: loginButton.Layout.preferredHeight * 1.28

            icon.name: LayoutMirroring.enabled ? "go-previous" : "go-next"

            onClicked: sessionManager.startLogin()
            Keys.onEnterPressed: clicked()
            Keys.onReturnPressed: clicked()
            scale: loginButton.down ? 0.94 : 1.0
            Behavior on scale {
                NumberAnimation {
                    duration: Kirigami.Units.shortDuration
                    easing.type: Easing.OutCubic
                }
            }

            // ── MoOS UI2 visual only (see AUTH SAFETY CONTRACT) ──────────────
            // A compact Tidal Portal key. Its fill stays on accentA — the colour
            // scheme's Selection background — because highlightedTextColor is
            // WCAG-gated against that exact role in every MoOS palette.  The old
            // accentA→accentB gradient crossed through colours the scheme does
            // not pair with highlighted ink (Graphite's white glyph reached only
            // 1.77:1), making the security-critical Unlock action disappear.
            // accentB remains in the decorative focus rim, where it cannot
            // compromise glyph contrast.
            background: Rectangle {
                radius: height * 0.30
                color: sessionManager.accentA
                border.width: loginButton.activeFocus ? 2 : 1
                border.color: Qt.rgba(sessionManager.accentB.r,
                                      sessionManager.accentB.g,
                                      sessionManager.accentB.b,
                                      loginButton.activeFocus ? 0.90 : 0.48)
                Behavior on border.color { ColorAnimation { duration: Kirigami.Units.shortDuration } }

                // Crest cut + quiet lower horizon: the same two marks used by
                // Login, Logout and every session action key.
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: parent.top
                    anchors.topMargin: -height / 2
                    width: parent.width * 0.30
                    height: loginButton.activeFocus ? 3 : 2
                    radius: height / 2
                    color: Kirigami.Theme.highlightedTextColor
                    opacity: loginButton.activeFocus ? 0.96 : 0.72
                }
                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: Math.max(4, parent.height * 0.10)
                    width: parent.width * 0.42
                    height: 1
                    radius: height / 2
                    color: Kirigami.Theme.highlightedTextColor
                    opacity: loginButton.activeFocus ? 0.52 : 0.28
                }
            }
            contentItem: Kirigami.Icon {
                source: loginButton.icon.name
                isMask: true
                color: Kirigami.Theme.highlightedTextColor
                implicitWidth: Kirigami.Units.iconSizes.smallMedium
                implicitHeight: Kirigami.Units.iconSizes.smallMedium
            }
        }
    }

    component FailableLabel : PlasmaComponents3.Label {
        id: _failableLabel
        required property int kind
        required property string label

        visible: authenticator.authenticatorTypes & kind
        text: label
        textFormat: Text.PlainText
        horizontalAlignment: Text.AlignHCenter
        Layout.fillWidth: true

        // ── MoOS UI2 visual only (see AUTH SAFETY CONTRACT) ──────────────
        // "(or scan your fingerprint on the reader)" is a hint, not a
        // statement: it belongs in the muted voice the rest of MoOS uses for
        // secondary text, and in the same family as everything else on this
        // cluster. `kind`, `visible`, `text` and the Connections below are
        // untouched — this is typography, nothing more.
        font.family: "IBM Plex Sans Arabic"
        font.pointSize: Kirigami.Theme.defaultFont.pointSize - 1
        color: Kirigami.Theme.disabledTextColor

        RejectPasswordAnimation {
            id: _rejectAnimation
            target: _failableLabel
            onFinished: _timer.restart()
        }

        Connections {
            target: authenticator
            function onNoninteractiveError(kind, authenticator) {
                if (kind & _failableLabel.kind) {
                    _failableLabel.text = Qt.binding(() => authenticator.errorMessage)
                    _rejectAnimation.start()
                }
            }
        }
        Timer {
            id: _timer
            interval: Kirigami.Units.humanMoment
            onTriggered: {
                _failableLabel.text = Qt.binding(() => _failableLabel.label)
            }
        }
    }

    FailableLabel {
        kind: ScreenLocker.Authenticator.Fingerprint
        label: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:usagetip", "(or scan your fingerprint on the reader)")
    }
    FailableLabel {
        kind: ScreenLocker.Authenticator.Smartcard
        label: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:usagetip", "(or scan your smartcard)")
    }
}
