/*
    SPDX-FileCopyrightText: 2016 David Edmundson <davidedmundson@kde.org>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: LGPL-2.0-or-later

    This IS the plasma-desktop shell's lockscreen MainBlock.qml, overridden by
    MoOS. It is the auth cluster that lives INSIDE the frosted glass card drawn
    by LockScreenUi.qml: the user avatar + name (from SessionManagementScreen),
    the password field, the unlock button, and the fingerprint/smartcard hints.

    It was the last stock-Breeze surface on an otherwise fully-MoOS lock screen —
    the deferred "auth card" item. This fork dresses the password field and the
    unlock button in MoOS UI2 (glass field with a brand-accent focus ring; a
    round accent unlock button) and NOTHING else.

    AUTH SAFETY CONTRACT — read before editing:
      Every line that touches authentication is kept BYTE-IDENTICAL to the base
      file shipped by plasma-workspace: the SessionManagementScreen root and its
      `userList`/avatar, the `mainPasswordBox`/`showPassword` aliases, the
      `passwordResult` signal, `startLogin()`, `onUserSelected`, the passwordBox
      id/text/PasswordSync binding/onAccepted/Keys/Connections, the loginButton
      id/onClicked/Keys, and both FailableLabels. The ONLY additions are visual:
      a `background:` on the field, `topPadding`/`bottomPadding`, and the button's
      `background:`/`contentItem:`. This file must never be the reason someone
      cannot unlock their own machine — restyle, never rewire.
*/

import QtQuick

import QtQuick.Layouts
import QtQuick.Controls as QQC2

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

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        PlasmaExtras.PasswordField {
            id: passwordBox
            font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
            Layout.fillWidth: true
            text: PasswordSync.password

            placeholderText: i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:placeholder in text field", "Password")
            focus: true
            enabled: !authenticator.graceLocked

            // ── MoOS UI2 visual only (see AUTH SAFETY CONTRACT) ──────────────
            // A little more air than Breeze's default so the field reads as a
            // premium glass control on the card.
            topPadding: Kirigami.Units.smallSpacing * 1.5
            bottomPadding: Kirigami.Units.smallSpacing * 1.5
            leftPadding: Kirigami.Units.largeSpacing
            // The MoOS glass field: translucent fill, a hairline border that
            // lights up in the active theme's accent when the field has focus.
            background: Rectangle {
                radius: Kirigami.Units.gridUnit * 0.55
                color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                               Kirigami.Theme.backgroundColor.g,
                               Kirigami.Theme.backgroundColor.b, 0.55)
                border.width: 1
                border.color: passwordBox.activeFocus
                    ? Qt.rgba(Kirigami.Theme.highlightColor.r,
                              Kirigami.Theme.highlightColor.g,
                              Kirigami.Theme.highlightColor.b, 0.9)
                    : Qt.rgba(Kirigami.Theme.textColor.r,
                              Kirigami.Theme.textColor.g,
                              Kirigami.Theme.textColor.b, 0.18)
                Behavior on border.color { ColorAnimation { duration: Kirigami.Units.longDuration } }
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
                    sessionManager.playHighlightAnimation();
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
            Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button accessible only", "Unlock")
            Layout.preferredHeight: passwordBox.implicitHeight
            Layout.preferredWidth: loginButton.Layout.preferredHeight

            icon.name: LayoutMirroring.enabled ? "go-previous" : "go-next"

            onClicked: sessionManager.startLogin()
            Keys.onEnterPressed: clicked()
            Keys.onReturnPressed: clicked()

            // ── MoOS UI2 visual only (see AUTH SAFETY CONTRACT) ──────────────
            // A round accent button: the active theme's highlight, a touch
            // brighter at the crest, dimming on press. The go-next glyph is the
            // base control's icon, re-rendered white so it reads on the accent.
            background: Rectangle {
                radius: height / 2
                gradient: Gradient {
                    GradientStop {
                        position: 0.0
                        color: Qt.lighter(Kirigami.Theme.highlightColor, loginButton.down ? 1.0 : 1.18)
                    }
                    GradientStop {
                        position: 1.0
                        color: loginButton.down
                            ? Qt.darker(Kirigami.Theme.highlightColor, 1.12)
                            : Kirigami.Theme.highlightColor
                    }
                }
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, loginButton.activeFocus ? 0.55 : 0.22)
                Behavior on border.color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
            }
            contentItem: Kirigami.Icon {
                source: loginButton.icon.name
                isMask: true
                color: "white"
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
