/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: GPL-2.0-or-later

    This IS the plasma-desktop shell's LockScreenUi.qml, overridden by MoOS —
    kscreenlocker draws the lock screen from the SHELL package, not the
    look-and-feel (verified live 2026-07-14: a [Greeter] Theme pointing at a
    look-and-feel silently fell back to this shell default). The base shell's
    LockScreen.qml loads this file and provides MainBlock/PasswordSync/qmldir/
    MediaControls/NoPasswordUnlock/LockOsd beside it; only this file and
    MoOSClock.qml are MoOS overrides.

    Forked from Plasma 6.7's original. EVERY authenticator connection, the
    MainBlock auth path, the StackView, the grace timers and the footer are kept
    exactly as shipped — this file must never be the reason someone cannot unlock
    their own machine. The additions are purely visual and purely MoOS UI2: a
    bottom graphite scrim, a frosted glass card that fades in with the UI, the
    MoOS emblem + wordmark, the MoOSClock, and a softer entrance. All colours come
    from the active scheme so it themes on both Graphite and Tidal.
*/
import QtQml
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.workspace.components as PW
import org.kde.plasma.private.keyboardindicator as KeyboardIndicator
import org.kde.kirigami as Kirigami
import org.kde.kscreenlocker as ScreenLocker

import org.kde.plasma.private.sessions
import org.kde.breeze.components

Item {
    id: lockScreenUi

    // If we're using software rendering, draw outlines instead of shadows
    readonly property bool softwareRendering: GraphicsInfo.api === GraphicsInfo.Software

    function handleMessage(msg) {
        if (!root.notification) {
            root.notification += msg;
        } else if (root.notification.includes(msg)) {
            root.notificationRepeated();
        } else {
            root.notification += "\n" + msg
        }
    }

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    Connections {
        target: authenticator
        function onFailed(kind) {
            if (kind != 0) { // if this is coming from the noninteractive authenticators
                return;
            }
            const msg = i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "Unlocking failed");
            lockScreenUi.handleMessage(msg);
            graceLockTimer.restart();
            notificationRemoveTimer.restart();
            rejectPasswordAnimation.start();
        }

        function onSucceeded() {
            if (authenticator.hadPrompt) {
                Qt.quit();
            } else {
                mainStack.replace(null, Qt.resolvedUrl("NoPasswordUnlock.qml"),
                    {
                        userListModel: users
                    },
                    StackView.Immediate,
                );
                mainStack.forceActiveFocus();
            }
        }

        function onInfoMessageChanged() {
            lockScreenUi.handleMessage(authenticator.infoMessage);
        }

        function onErrorMessageChanged() {
            lockScreenUi.handleMessage(authenticator.errorMessage);
        }

        function onPromptChanged(msg) {
            lockScreenUi.handleMessage(authenticator.prompt);
        }
        function onPromptForSecretChanged(msg) {
            mainBlock.showPassword = false;
            mainBlock.mainPasswordBox.forceActiveFocus();
        }
    }

    SessionManagement {
        id: sessionManagement
    }

    KeyboardIndicator.KeyState {
        id: capsLockState
        key: Qt.Key_CapsLock
    }

    Connections {
        target: sessionManagement
        function onAboutToSuspend() {
            root.clearPassword();
        }
    }

    RejectPasswordAnimation {
        id: rejectPasswordAnimation
        target: mainBlock
    }

    MouseArea {
        id: lockScreenRoot

        property bool uiVisible: false
        property bool seenPositionChange: false
        property bool blockUI: containsMouse && (mainStack.depth > 1 || mainBlock.mainPasswordBox.text.length > 0 || inputPanel.keyboardActive)

        x: parent.x
        y: parent.y
        width: parent.width
        height: parent.height
        hoverEnabled: true
        cursorShape: uiVisible ? Qt.ArrowCursor : Qt.BlankCursor
        drag.filterChildren: true
        onPressed: uiVisible = true;
        onPositionChanged: {
            uiVisible = seenPositionChange;
            seenPositionChange = true;
        }
        onUiVisibleChanged: {
            if (uiVisible) {
                Window.window.requestActivate();
            }

            if (blockUI) {
                fadeoutTimer.running = false;
            } else if (uiVisible) {
                fadeoutTimer.restart();
            }
            authenticator.startAuthenticating();
        }
        onBlockUIChanged: {
            if (blockUI) {
                fadeoutTimer.running = false;
                uiVisible = true;
            } else {
                fadeoutTimer.restart();
            }
        }
        onExited: {
            uiVisible = false;
        }
        Keys.onEscapePressed: {
            if (uiVisible) {
                uiVisible = false;
                if (inputPanel.keyboardActive) {
                    inputPanel.showHide();
                }
                root.clearPassword();
            }
        }
        Keys.onPressed: event => {
            uiVisible = true;
            event.accepted = false;
        }
        Timer {
            id: fadeoutTimer
            interval: 10000
            onTriggered: {
                if (!lockScreenRoot.blockUI) {
                    mainBlock.mainPasswordBox.showPassword = false;
                    lockScreenRoot.uiVisible = false;
                }
            }
        }
        Timer {
            id: notificationRemoveTimer
            interval: 3000
            onTriggered: root.notification = ""
        }
        Timer {
            id: graceLockTimer
            interval: 3000
            onTriggered: {
                root.clearPassword();
                authenticator.startAuthenticating();
            }
        }

        // NOTE: the MoOS visual layer (scrim, brand) is declared AFTER the
        // WallpaperFader below — z-order is declaration order, and anything before
        // the fader is painted over by the wallpaper. An earlier revision put the
        // scrim and brand here and the wallpaper hid them both.

        // The whole scene fades up on appear (original Breeze behaviour), and the
        // brand mark settles down a touch — a calm, premium entrance. A shared
        // Transform cannot drive several items at once in QML, so the only moving
        // transform here belongs to `brand` alone; the auth card has its own
        // opacity+scale, and the clock/stack keep the geometry the WallpaperFader
        // expects untouched.
        PropertyAnimation {
            id: launchAnimation
            target: lockScreenRoot
            property: "opacity"
            from: 0
            to: 1
            duration: Kirigami.Units.veryLongDuration * 2
        }
        NumberAnimation {
            id: riseAnimation
            target: brandShift
            property: "y"
            from: -Kirigami.Units.gridUnit * 1.2
            to: 0
            duration: Kirigami.Units.veryLongDuration * 2
            easing.type: Easing.OutCubic
        }

        Component.onCompleted: {
            launchAnimation.start();
            riseAnimation.start();
        }

        WallpaperFader {
            anchors.fill: parent
            state: lockScreenRoot.uiVisible ? "on" : "off"
            source: wallpaper
            mainStack: mainStack
            footer: footer
            clock: clock
            alwaysShowClock: config.alwaysShowClock && !config.hideClockWhenIdle
        }

        // ── MoOS "Living Aurora" — four drifting curtains of emerald, teal, cyan
        //    and violet light over the wallpaper, the same living sky the login
        //    and logout scenes carry, so lock, login and logout read as one brand.
        //    Explicit Rectangles (no Repeater → no ComponentBehavior pragma in the
        //    unlock file); Animators only, no shaders. Kept quiet so the clock and
        //    password never lose legibility, and drawn UNDER the scrim + brand.
        Item {
            id: lockAurora
            anchors.fill: parent

            Rectangle {
                width: lockAurora.width * 0.42
                height: lockAurora.height * 0.66
                y: 0
                rotation: -16
                transformOrigin: Item.Center
                opacity: 0.13
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.42; color: "#10B981" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                XAnimator on x {
                    from: -lockAurora.width * 0.14; to: lockAurora.width * 0.46
                    duration: 64000; loops: Animation.Infinite
                    easing.type: Easing.InOutSine; running: lockAurora.visible
                }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite; running: lockAurora.visible
                    NumberAnimation { to: 0.20; duration: 6000; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.08; duration: 6000; easing.type: Easing.InOutSine }
                }
            }
            Rectangle {
                width: lockAurora.width * 0.48
                height: lockAurora.height * 0.72
                y: -lockAurora.height * 0.05
                rotation: 12
                transformOrigin: Item.Center
                opacity: 0.16
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.42; color: "#2DD4BF" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                XAnimator on x {
                    from: lockAurora.width * 0.50; to: -lockAurora.width * 0.06
                    duration: 82000; loops: Animation.Infinite
                    easing.type: Easing.InOutSine; running: lockAurora.visible
                }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite; running: lockAurora.visible
                    NumberAnimation { to: 0.24; duration: 6900; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.10; duration: 6900; easing.type: Easing.InOutSine }
                }
            }
            Rectangle {
                width: lockAurora.width * 0.38
                height: lockAurora.height * 0.60
                y: lockAurora.height * 0.08
                rotation: -10
                transformOrigin: Item.Center
                opacity: 0.11
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.42; color: "#22D3EE" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                XAnimator on x {
                    from: lockAurora.width * 0.16; to: lockAurora.width * 0.58
                    duration: 72000; loops: Animation.Infinite
                    easing.type: Easing.InOutSine; running: lockAurora.visible
                }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite; running: lockAurora.visible
                    NumberAnimation { to: 0.17; duration: 7600; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.07; duration: 7600; easing.type: Easing.InOutSine }
                }
            }
            Rectangle {
                width: lockAurora.width * 0.46
                height: lockAurora.height * 0.68
                y: -lockAurora.height * 0.02
                rotation: 18
                transformOrigin: Item.Center
                opacity: 0.13
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.42; color: "#8B5CF6" }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                XAnimator on x {
                    from: lockAurora.width * 0.42; to: lockAurora.width * 0.04
                    duration: 92000; loops: Animation.Infinite
                    easing.type: Easing.InOutSine; running: lockAurora.visible
                }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite; running: lockAurora.visible
                    NumberAnimation { to: 0.20; duration: 8200; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.08; duration: 8200; easing.type: Easing.InOutSine }
                }
            }
        }

        // ── MoOS visual layer — ON TOP of the wallpaper ──────────────────────
        // A soft graphite scrim: a gentle darkening at the top and bottom edges so
        // the brand, clock and password stay legible over any wallpaper. Full-bleed,
        // low opacity, purely cosmetic.
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.45) }
                GradientStop { position: 0.4; color: "transparent" }
                GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.5) }
            }
        }

        // The MoOS mark, quiet, upper-centre — brand identity without shouting.
        ColumnLayout {
            id: brand
            anchors {
                top: parent.top
                horizontalCenter: parent.horizontalCenter
                topMargin: Kirigami.Units.gridUnit * 2.5
            }
            spacing: Kirigami.Units.smallSpacing
            opacity: 0.92
            transform: Translate { id: brandShift }

            // The animated brand: breathing halo, the emblem, one slow spark —
            // the same living mark the login scene and logout greeter carry.
            // Sprites are pre-baked alpha PNGs (artwork/generate_login_scene.py,
            // copied into this shell dir); motion is Animators-only, no shaders
            // on a screen that can stay up for hours.
            Item {
                id: brandStage
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.gridUnit * 3.6
                Layout.preferredHeight: Layout.preferredWidth

                Image {
                    anchors.centerIn: brandEmblem
                    width: brandStage.width * 2.3
                    height: width
                    source: "images/glow-cyan.png"
                    opacity: 0.45
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: brandStage.visible
                        NumberAnimation { to: 0.75; duration: 3600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.45; duration: 3600; easing.type: Easing.InOutSine }
                    }
                }
                Image {
                    anchors.centerIn: brandEmblem
                    width: brandStage.width * 1.75
                    height: width
                    source: "images/glow-violet.png"
                    opacity: 0.5
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: brandStage.visible
                        NumberAnimation { to: 0.3; duration: 3600; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 0.5; duration: 3600; easing.type: Easing.InOutSine }
                    }
                }
                Image {
                    id: brandEmblem
                    anchors.centerIn: parent
                    width: brandStage.width
                    height: brandStage.height
                    // Absolute path: this file lives in the shell package now, which
                    // has no MoOS art of its own. /usr/share/pixmaps/moos-logo.png is
                    // the canonical mark the identity firewall pins.
                    source: "file:///usr/share/pixmaps/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    smooth: true
                    SequentialAnimation on scale {
                        loops: Animation.Infinite
                        running: brandStage.visible
                        NumberAnimation { to: 1.03; duration: 3000; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1.0; duration: 3000; easing.type: Easing.InOutSine }
                    }
                }
                Item {
                    anchors.fill: parent
                    RotationAnimator on rotation {
                        from: 0; to: 360
                        duration: 24000
                        loops: Animation.Infinite
                        running: brandStage.visible
                    }
                    Image {
                        source: "images/spark.png"
                        width: brandStage.width * 0.15
                        height: width
                        x: (brandStage.width - width) / 2
                        y: -brandStage.width * 0.10
                    }
                }
                // The comet ring, counter-rotating against the spark — the
                // same orbit the login and logout scenes carry, so lock,
                // login and logout read as one brand.
                Image {
                    anchors.centerIn: brandEmblem
                    width: brandStage.width * 1.5
                    height: width
                    source: "images/ring.png"
                    mirror: true
                    opacity: 0.65
                    sourceSize: Qt.size(width * 2, height * 2)
                    RotationAnimator on rotation {
                        from: 360; to: 0
                        duration: 28000
                        loops: Animation.Infinite
                        running: brandStage.visible
                    }
                }
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "MoOS"
                color: Kirigami.Theme.textColor
                opacity: 0.85
                font.family: "IBM Plex Sans"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 2
                font.weight: Font.DemiBold
                font.letterSpacing: 2
                renderType: Text.NativeRendering
            }
        }

        // A soft shadow beneath the auth card — the UI2 glass sits ON the
        // wallpaper, not painted into it. Behind the card, tied to its state.
        // Purely decorative; never touches the auth path.
        RectangularGlow {
            anchors.fill: authCard
            visible: !lockScreenUi.softwareRendering && authCard.opacity > 0
            glowRadius: Kirigami.Units.gridUnit * 1.1
            spread: 0.06
            color: Qt.rgba(0, 0, 0, 0.34)
            cornerRadius: authCard.radius + glowRadius
            opacity: authCard.opacity
            scale: authCard.scale
        }

        // The frosted card behind the auth cluster. Fades and lifts in only when
        // the UI is summoned, so the idle screen stays clean wallpaper + clock.
        // Real UI2 glass: a vertical depth gradient (lighter crest, deeper foot),
        // a 1px translucent inner border, a top highlight, and the shadow above.
        Rectangle {
            id: authCard
            anchors.horizontalCenter: parent.horizontalCenter
            y: mainStack.y + mainStack.height * 0.5 - height * 0.5
            width: Math.min(parent.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 30)
            height: Kirigami.Units.gridUnit * 21
            radius: Kirigami.Units.gridUnit * 1.2
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.64) }
                GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.50) }
            }
            border.width: 1
            border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                  Kirigami.Theme.textColor.g,
                                  Kirigami.Theme.textColor.b, 0.14)
            visible: opacity > 0
            opacity: lockScreenRoot.uiVisible ? 1 : 0
            scale: lockScreenRoot.uiVisible ? 1 : 0.96
            Behavior on opacity { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }
            Behavior on scale { NumberAnimation { duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic } }

            // One soft inner highlight along the top edge — the UI2 glass tell:
            // silk catching the light where the card meets the sky.
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right; margins: 1 }
                height: 1
                radius: 1
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.16)
            }
        }

        DropShadow {
            id: clockShadow
            anchors.fill: clock
            source: clock
            visible: !lockScreenUi.softwareRendering && config.alwaysShowClock
            radius: 12
            verticalOffset: 1.0
            samples: 25
            spread: 0.15
            color: Qt.rgba(0, 0, 0, 0.55)
            opacity: lockScreenRoot.uiVisible ? 0 : 1
            Behavior on opacity {
                OpacityAnimator {
                    duration: Kirigami.Units.veryLongDuration * 2
                    easing.type: Easing.InOutQuad
                }
            }
        }

        MoOSClock {
            id: clock
            property Item shadow: clockShadow
            visible: y > 0 && config.alwaysShowClock
            anchors.horizontalCenter: parent.horizontalCenter
            // Never above the brand: the halfway formula alone parked the clock
            // inside the emblem+wordmark on a 4K panel (the two were designed on
            // different rulers — the brand in gridUnits, the clock from the
            // userlist geometry). The floor keeps a clear breath below the brand.
            y: Math.max(brand.y + brand.height + Kirigami.Units.gridUnit * 1.5,
                        (mainBlock.userList.y + mainStack.y) / 2 - height / 2)
            Layout.alignment: Qt.AlignBaseline
        }

        ListModel {
            id: users

            Component.onCompleted: {
                users.append({
                    name: kscreenlocker_userName,
                    realName: kscreenlocker_userName,
                    icon: kscreenlocker_userImage !== ""
                          ? "file://" + kscreenlocker_userImage.split("/").map(encodeURIComponent).join("/")
                          : "",
                })
            }
        }

        StackView {
            id: mainStack
            anchors {
                left: parent.left
                right: parent.right
            }
            height: lockScreenRoot.height + Kirigami.Units.gridUnit * 3
            focus: true

            visible: opacity > 0

            initialItem: MainBlock {
                id: mainBlock
                lockScreenUiVisible: lockScreenRoot.uiVisible

                showUserList: userList.y + mainStack.y > 0

                enabled: !graceLockTimer.running

                StackView.onStatusChanged: {
                    if (StackView.status === StackView.Activating) {
                        mainPasswordBox.clear();
                        mainPasswordBox.focus = true;
                        root.notification = "";
                    }
                }
                userListModel: users


                notificationMessage: {
                    const parts = [];
                    if (capsLockState.locked) {
                        parts.push(i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "Caps Lock is on"));
                    }
                    if (root.notification) {
                        parts.push(root.notification);
                    }
                    return parts.join(" • ");
                }

                onPasswordResult: password => {
                    authenticator.respond(password)
                }

                actionItems: [
                    ActionButton {
                        text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "Slee&p")
                        icon.name: "system-suspend"
                        onClicked: sessionManagement.suspend()
                        visible: sessionManagement.canSuspend
                    },
                    ActionButton {
                        text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "&Hibernate")
                        icon.name: "system-suspend-hibernate"
                        onClicked: sessionManagement.hibernate()
                        visible: sessionManagement.canHibernate
                    },
                    ActionButton {
                        text: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button", "Switch &User")
                        icon.name: "system-switch-user"
                        onClicked: {
                            sessionManagement.switchUser();
                        }
                        visible: sessionManagement.canSwitchUser
                    }
                ]

                Loader {
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    Layout.fillWidth: true
                    Layout.preferredHeight: item ? item.implicitHeight : 0
                    active: config.showMediaControls
                    source: "MediaControls.qml"
                }
            }
        }

        VirtualKeyboardLoader {
            id: inputPanel

            z: 1

            screenRoot: lockScreenRoot
            mainStack: mainStack
            mainBlock: mainBlock
            passwordField: mainBlock.mainPasswordBox
        }

        Loader {
            z: 2
            active: root.viewVisible
            source: "LockOsd.qml"
            anchors {
                horizontalCenter: parent.horizontalCenter
                bottom: parent.bottom
                bottomMargin: Kirigami.Units.gridUnit
            }
        }

        RowLayout {
            id: footer
            anchors {
                bottom: parent.bottom
                left: parent.left
                right: parent.right
                margins: Kirigami.Units.smallSpacing
            }
            spacing: Kirigami.Units.smallSpacing

            PlasmaComponents3.ToolButton {
                id: virtualKeyboardButton

                focusPolicy: Qt.TabFocus
                text: i18ndc("plasma_shell_org.kde.plasma.desktop", "Button to show/hide virtual keyboard", "Virtual Keyboard")
                icon.name: inputPanel.keyboardActive ? "input-keyboard-virtual-on" : "input-keyboard-virtual-off"
                onClicked: {
                    mainBlock.mainPasswordBox.forceActiveFocus();
                    inputPanel.showHide()
                }

                visible: inputPanel.status === Loader.Ready

                Layout.fillHeight: true
                containmentMask: Item {
                    parent: virtualKeyboardButton
                    anchors.fill: parent
                    anchors.leftMargin: -footer.anchors.margins
                    anchors.bottomMargin: -footer.anchors.margins
                }
            }

            PlasmaComponents3.ToolButton {
                id: keyboardButton

                focusPolicy: Qt.TabFocus
                Accessible.description: i18ndc("plasma_shell_org.kde.plasma.desktop", "Button to change keyboard layout", "Switch layout")
                icon.name: "input-keyboard"

                PW.KeyboardLayoutSwitcher {
                    id: keyboardLayoutSwitcher

                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton
                }

                text: keyboardLayoutSwitcher.layoutNames.longName
                onClicked: keyboardLayoutSwitcher.keyboardLayout.switchToNextLayout()

                visible: keyboardLayoutSwitcher.hasMultipleKeyboardLayouts

                Layout.fillHeight: true
                containmentMask: Item {
                    parent: keyboardButton
                    anchors.fill: parent
                    anchors.leftMargin: virtualKeyboardButton.visible ? 0 : -footer.anchors.margins
                    anchors.bottomMargin: -footer.anchors.margins
                }
            }

            Item {
                Layout.fillWidth: true
            }

            Battery {}
        }
    }
}
