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

    // The motion gate. This is the ONE surface in MoOS that a machine can sit on
    // for hours with nobody in front of it, so everything that loops forever is
    // gated on this — see the brand stage below.
    //
    // It is `> 1`, not `> 0`. Kirigami FLOORS longDuration at 1 when animations
    // are switched off (by the user, or by the cloud edition's
    // AnimationDurationFactor=0); it is never 0, so `> 0` is always true and
    // gates precisely nothing. KDE's own three BusyIndicator.qml files and
    // RejectPasswordPathAnimation.qml all test against 1 for this reason. The
    // failure mode is silent: with `> 0` the animation simply keeps running and
    // nothing is reported, because a busy rasteriser is not an error.
    readonly property bool motionEnabled: Kirigami.Units.longDuration > 1
    readonly property bool rtl: Qt.locale().textDirection === Qt.RightToLeft

    // ── Two-tone MoOS accent ──────────────────────────────────────────────
    // accentA is the live theme highlight; accentB is a second hue derived
    // from it (a small rotation in HSL), so every palette gets its own
    // coherent TWO-colour signature — never one flat tint. Achromatic
    // highlights fall back to a brighter shade of themselves. Used by the
    // avatar ring, the unlock button and the ambient light shaft.
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

        // ── Where the user's face actually is ────────────────────────────────
        // The avatar bloom used to be pinned to the auth card's centre minus a
        // hand-tuned 4.6 grid units. That was about a grid unit low, and it
        // would have drifted further the moment a second account made the user
        // list reserve room for a wrapped name.
        //
        // The real geometry is not guesswork, it is three facts from the base
        // components: SessionManagementScreen anchors the UserList's BOTTOM to
        // its own vertical centre (with three extra grid units of margin when it
        // has to constrain a multi-line name), UserList's height is one delegate
        // — Kirigami.Units.gridUnit * 9 — and UserDelegate anchors the face to
        // the delegate's TOP at gridUnit * 7 across. So the face centre is the
        // list's own y plus 3.5 grid units, and binding to `userList.y` makes
        // the bloom follow every one of those cases by itself.
        readonly property Item lockUserList: mainBlock ? mainBlock.userList : null
        readonly property real avatarCenterY: lockUserList
            ? mainStack.y + lockUserList.y + Kirigami.Units.gridUnit * 3.5
            : mainStack.y + mainStack.height / 2 - Kirigami.Units.gridUnit * 5.5

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
            duration: lockScreenUi.motionEnabled ? Kirigami.Units.veryLongDuration * 2 : 0
        }
        NumberAnimation {
            id: riseAnimation
            target: brandShift
            property: "y"
            from: -Kirigami.Units.gridUnit * 1.2
            to: 0
            duration: lockScreenUi.motionEnabled ? Kirigami.Units.veryLongDuration * 2 : 0
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

        // The idle background is simply the wallpaper (blurred on focus by the
        // WallpaperFader above) — no drifting curtains, no shooting stars, no
        // busy motion. Calm and clean, and it takes each theme’s own wallpaper.
        // The only accent light is the soft theme bloom behind the auth cluster.

        // ── MoOS visual layer — ON TOP of the wallpaper ──────────────────────
        // MoOS token — the ONE session scrim (0.52 / 0.30 / 0.60), identical to the
        // power screen and the login scene so every surface veils the wallpaper the
        // same way. A gentle darkening top & foot keeps the brand, clock and
        // password legible over any wallpaper. Full-bleed, purely cosmetic.
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.52) }
                GradientStop { position: 0.45; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.30) }
                GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                             Kirigami.Theme.backgroundColor.g,
                                                             Kirigami.Theme.backgroundColor.b, 0.60) }
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

            // The protected emblem sits at the Tidal Cut. It is intentionally
            // still: the portal's finite reveal is the doorway motion.
            Item {
                id: brandStage
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.gridUnit * 4.2
                Layout.preferredHeight: Layout.preferredWidth

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 1.42
                    height: width
                    radius: width / 2
                    color: lockScreenUi.accentA
                    opacity: 0.075
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 1.14
                    height: width
                    radius: width / 2
                    color: lockScreenUi.accentB
                    opacity: 0.05
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
                }
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "MoOS"
                color: Kirigami.Theme.textColor
                opacity: 0.85
                font.family: "IBM Plex Sans Arabic"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 2
                font.weight: Font.DemiBold
                font.letterSpacing: 2
                // Not NativeRendering. Same trap as the hero clock (see the long
                // note in MoOSClock.qml): native rasterisation snaps glyphs to
                // the integer DEVICE pixel grid with subpixel antialiasing, and
                // on this machine's 2.25 fractional scale the wordmark landed
                // off-grid — captured at 8x, every stem of "MoOS" carried a cyan
                // edge on the left and an orange one on the right. On the brand
                // mark. Distance-field text has no grid to miss and is the right
                // renderer at this size; the clock needs CurveRendering only
                // because it is ~110pt and a distance field has to be magnified
                // that far.
                renderType: Text.QtRendering
            }
        }

        // ── Authentication island ────────────────────────────────────────────
        // A still mineral-glass plate gives the security boundary an authored
        // home inside the large portal. It remains purely visual; MainBlock and
        // every authentication wire stay outside and untouched.
        Rectangle {
            id: authCard
            anchors.horizontalCenter: parent.horizontalCenter
            y: mainStack.y + mainStack.height * 0.5 - height * 0.5
            width: Math.min(parent.width - Kirigami.Units.gridUnit * 4,
                            Kirigami.Units.gridUnit * 25)
            height: Math.min(parent.height - Kirigami.Units.gridUnit * 6,
                             Kirigami.Units.gridUnit * 35)
            radius: Kirigami.Units.gridUnit * 2
            // The lock island wears the SAME material as the power doorway's
            // Glass Island: the Complementary surface set, so the card is a
            // deliberate dark glass slab on light palettes too — one session
            // language across lock and power.
            Kirigami.Theme.inherit: false
            Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
            color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                           Kirigami.Theme.backgroundColor.g,
                           Kirigami.Theme.backgroundColor.b, 0.58)
            border.width: 1
            border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                  Kirigami.Theme.textColor.g,
                                  Kirigami.Theme.textColor.b, 0.16)
            visible: opacity > 0
            opacity: lockScreenRoot.uiVisible ? 1 : 0
            scale: lockScreenRoot.uiVisible ? 1 : 0.96
            Behavior on opacity {
                NumberAnimation {
                    duration: lockScreenUi.motionEnabled ? Kirigami.Units.longDuration : 0
                    easing.type: Easing.OutCubic
                }
            }
            Behavior on scale {
                NumberAnimation {
                    duration: lockScreenUi.motionEnabled ? Kirigami.Units.longDuration : 0
                    easing.type: Easing.OutCubic
                }
            }

            // Sheen — the glass catch-light across the island's upper field,
            // painted from the (Complementary) foreground at whisper opacity.
            Rectangle {
                anchors { top: parent.top; left: parent.left; right: parent.right }
                anchors.margins: 1
                height: parent.height * 0.38
                radius: parent.radius - 1
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.textColor.r,
                        Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.05) }
                    GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.textColor.r,
                        Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.0) }
                }
            }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: -height / 2
                width: Kirigami.Units.gridUnit * 4
                height: 3
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: lockScreenUi.accentA }
                    GradientStop { position: 1; color: lockScreenUi.accentB }
                }
            }
        }

        // Depth halo — the same still three-step falloff as the power island,
        // drawn as siblings BEHIND the card (z below), no offscreen effects.
        Rectangle {
            z: -1
            anchors.fill: authCard
            anchors.margins: -Kirigami.Units.gridUnit * 1.1
            radius: authCard.radius + Kirigami.Units.gridUnit * 1.1
            color: Qt.rgba(0, 0, 0, 0.04)
            visible: authCard.visible
            opacity: authCard.opacity
            scale: authCard.scale
        }
        Rectangle {
            z: -1
            anchors.fill: authCard
            anchors.margins: -Kirigami.Units.gridUnit * 0.7
            radius: authCard.radius + Kirigami.Units.gridUnit * 0.7
            color: Qt.rgba(0, 0, 0, 0.06)
            visible: authCard.visible
            opacity: authCard.opacity
            scale: authCard.scale
        }
        Rectangle {
            z: -1
            anchors.fill: authCard
            anchors.margins: -Kirigami.Units.gridUnit * 0.35
            radius: authCard.radius + Kirigami.Units.gridUnit * 0.35
            color: Qt.rgba(0, 0, 0, 0.08)
            visible: authCard.visible
            opacity: authCard.opacity
            scale: authCard.scale
        }

        // Jewel bloom behind the user avatar — a soft two-tone circle so the
        // photo reads as set into the theme's light. RadialGradient keeps it a
        // clean circular glow (never a square). Centred on the avatar's REAL
        // position now (see lockScreenRoot.avatarCenterY): the old hand-tuned
        // offset put the glow about a grid unit low, so the light pooled under
        // the face and left its crown flat — visible the moment the two were
        // captured and compared. Decorative only — never touches the auth path.
        //
        // This bloom, and nothing else, is the avatar's MoOS treatment. A
        // hairline glass bezel a grid unit outside the face was tried here and
        // removed after looking at it: UserDelegate already draws the avatar's
        // one luminous edge in the brand colour, and a second hoop beside it
        // read as an accident. So did a broad ink contact-shadow — the face is
        // opaque, so only the shadow's rim showed, and all it did there was
        // mute the brand light. One edge, one bloom.
        RadialGradient {
            id: avatarHalo
            anchors.horizontalCenter: authCard.horizontalCenter
            y: lockScreenRoot.avatarCenterY - height / 2
            width: Kirigami.Units.gridUnit * 13
            height: width
            visible: authCard.opacity > 0 && !lockScreenUi.softwareRendering
            opacity: authCard.opacity
            scale: authCard.scale
            // Explicit radii so the bloom fades to nothing WELL inside the item
            // box — otherwise the default radius fills the corners and it reads as
            // a square. Transparent by 0.72 of the radius → a clean soft circle.
            horizontalRadius: width * 0.5
            verticalRadius: height * 0.5
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(lockScreenUi.accentB.r, lockScreenUi.accentB.g, lockScreenUi.accentB.b, 0.50) }
                GradientStop { position: 0.34; color: Qt.rgba(lockScreenUi.accentA.r, lockScreenUi.accentA.g, lockScreenUi.accentA.b, 0.30) }
                GradientStop { position: 0.72; color: "transparent" }
                GradientStop { position: 1.0; color: "transparent" }
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
                    duration: lockScreenUi.motionEnabled ? Kirigami.Units.veryLongDuration * 2 : 0
                    easing.type: Easing.InOutQuad
                }
            }
        }

        // New arrangement: the clock is a hero anchored to the LEADING top corner
        // (top-right under RTL, top-left otherwise), free of the centred auth
        // cluster — a modern lock composition instead of one stacked column.
        MoOSClock {
            id: clock
            shadow: clockShadow
            visible: y > 0 && config.alwaysShowClock
            anchors.left: lockScreenUi.rtl ? undefined : parent.left
            anchors.right: lockScreenUi.rtl ? parent.right : undefined
            anchors.leftMargin: lockScreenUi.rtl ? 0 : Kirigami.Units.gridUnit * 5
            anchors.rightMargin: lockScreenUi.rtl ? Kirigami.Units.gridUnit * 5 : 0
            y: Kirigami.Units.gridUnit * 4.5
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


                // Same text, same assembly, same Caps-Lock hint as always — only
                // the surface that shows it changed. MoOS draws it as a glass
                // notice pill inside MainBlock instead of the base
                // SessionManagementScreen's plain italic label; see the note
                // beside `notice` there for why the base label cannot simply be
                // restyled in place.
                notice: {
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
