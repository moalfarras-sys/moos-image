/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    The host contract (signals, ShutdownType, spdMethods, maysd, canLogout,
    softwareUpdatePending, remainingTime) is KDE Plasma 6.7's org.kde.breeze
    Logout.qml — untouched, so every action stays wired to the system. The
    visual design is an original MoOS UI2 ground-up rework: an immersive
    theme-driven scene, a centred live-clock + emblem header, and a DOCK of
    circular action ORBS with labels beneath — no tile grid, no bento, no bars.
    Shut Down / Restart are gated behind a confirm tap (armOrFire); the signal
    each orb emits stays byte-identical to the stock contract.
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import Qt5Compat.GraphicalEffects

import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.sessions

Item {
    id: root

    width: screenGeometry.width
    height: screenGeometry.height
    focus: true

    Kirigami.Theme.inherit: false
    Kirigami.Theme.colorSet: Kirigami.Theme.Complementary

    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    signal logoutRequested()
    signal haltRequested()
    signal haltUpdateRequested()
    signal suspendRequested(int spdMethod)
    signal rebootRequested()
    signal rebootRequested2(int opt)
    signal rebootUpdateRequested()
    signal cancelRequested()
    signal lockScreenRequested()
    signal cancelSoftwareUpdateRequested()

    readonly property bool showAllOptions: sdtype === ShutdownType.ShutdownTypeDefault
    property int remainingTime: 30

    // ═══════════════════ MoOS Session Design Tokens ═══════════════════════
    // ONE canonical set for every session surface (lock, power, login scene).
    // Mirrored exactly on the lock (LockScreenUi/MainBlock/MoOSClock) and the
    // breeze ActionButton; documented here as the single source of truth so no
    // surface drifts. Change a token here → change it on the lock to match.
    //   accentA = Kirigami.Theme.highlightColor       · live theme accent
    //   accentB = accentA HSL hue +0.09               · two-tone signature
    //   ink     = Kirigami.Theme.textColor            · neutral glyph / text
    //   orb     = gridUnit*4.6 disc · iconSizes.medium glyph · radius w/2
    //             idle fill ink 0.08 · lit fill ink 0.16 · border accent 0.8 lit / ink 0.16 idle
    //   pill    = radius height/2 (password field)
    //   scrim   = backgroundColor  0.52 / 0.30 / 0.60  (top / mid / foot)
    //   blur    = 54 wallpaper (lock's breeze WallpaperFader = 50)
    //   fonts   = Inter (Latin/digits) · IBM Plex Sans Arabic (Arabic)
    //   clock   = Font.Thin · letterSpacing -2 · accent colon · hairline accent
    //   motion  = Units.shortDuration (hover/press) · longDuration (fades) · OutCubic
    // ══════════════════════════════════════════════════════════════════════
    readonly property color accent: Kirigami.Theme.highlightColor
    // accentB — the two-tone partner (accentA hue-rotated +0.09 in HSL), same
    // derivation as the orb. The aurora ribbons ride accentA/accentB so their
    // hue is 100% theme-derived — no hardcoded base colour anywhere.
    readonly property color accentB: {
        const c = Kirigami.Theme.highlightColor;
        if (c.hslSaturation < 0.08 || c.hslHue < 0) { return Qt.lighter(c, 1.28); }
        let nh = c.hslHue + 0.09; if (nh > 1) { nh -= 1; }
        return Qt.hsla(nh, Math.min(1, c.hslSaturation), Math.min(0.72, c.hslLightness * 1.08), 1);
    }

    property string nowTime: Qt.formatTime(new Date(), "HH:mm")
    Timer {
        interval: 15000; repeat: true; running: root.visible
        onTriggered: root.nowTime = Qt.formatTime(new Date(), "HH:mm")
    }

    // The aurora keeps its designed hue but pulls 40% toward the live accent, so
    // every one of the 16 themes lights this doorway with its own colour.
    function auroraTint(base) {
        const a = Kirigami.Theme.highlightColor;
        return Qt.tint(base, Qt.rgba(a.r, a.g, a.b, 0.40));
    }

    function stopCountdown() { countdownTimer.stop(); }

    function currentAction() {
        switch (sdtype) {
        case ShutdownType.ShutdownTypeReboot:
            if (softwareUpdatePending) { rebootUpdateRequested(); } else { rebootRequested(); }
            break;
        case ShutdownType.ShutdownTypeHalt:
            if (softwareUpdatePending) { haltUpdateRequested(); } else { haltRequested(); }
            break;
        default:
            logoutRequested();
        }
    }

    function visibleActions() {
        const candidates = [suspendButton, hibernateButton, rebootButton,
            rebootWithoutUpdatesButton, shutdownButton, shutdownWithoutUpdatesButton,
            logoutButton, lockButton, cancelButton];
        const result = [];
        for (let i = 0; i < candidates.length; ++i) {
            if (candidates[i].visible && candidates[i].enabled) { result.push(candidates[i]); }
        }
        return result;
    }

    function moveFocus(button, step) {
        const actions = visibleActions();
        if (actions.length === 0) { return; }
        let logicalStep = step;
        if (Qt.application.layoutDirection === Qt.RightToLeft) { logicalStep *= -1; }
        const idx = Math.max(0, actions.indexOf(button));
        const next = (idx + logicalStep + actions.length) % actions.length;
        actions[next].forceActiveFocus(Qt.TabFocusReason);
    }

    function focusInitialAction() {
        if (sdtype === ShutdownType.ShutdownTypeReboot && rebootButton.visible) {
            rebootButton.forceActiveFocus(Qt.OtherFocusReason);
        } else if (sdtype === ShutdownType.ShutdownTypeHalt && shutdownButton.visible) {
            shutdownButton.forceActiveFocus(Qt.OtherFocusReason);
        } else if (sdtype === ShutdownType.ShutdownTypeNone && logoutButton.visible) {
            logoutButton.forceActiveFocus(Qt.OtherFocusReason);
        } else {
            cancelButton.forceActiveFocus(Qt.OtherFocusReason);
        }
    }

    // ── Confirm-on-sensitive ────────────────────────────────────────────────
    // Shut Down / Restart are gated behind a second tap: the first tap ARMS the
    // orb (it pulses + shows a "press again" hint), the second FIRES the real
    // system signal. Everything else (Sleep, Log Out, Lock) fires immediately.
    // This only gates the click — the signal each orb emits is byte-identical to
    // the stock contract, so the system path is untouched.
    property var armedButton: null
    Timer { id: armTimer; interval: 4000; onTriggered: root.disarm() }
    function disarm() {
        if (root.armedButton) { root.armedButton.armed = false; root.armedButton = null; }
        armTimer.stop();
    }
    function armOrFire(btn, fire) {
        root.stopCountdown();
        if (root.armedButton === btn) { root.disarm(); fire(); return; }
        root.disarm();
        btn.armed = true;
        root.armedButton = btn;
        armTimer.restart();
    }
    // Any immediate action or a cancel clears a pending arm first.
    function fireNow(fire) { root.disarm(); root.stopCountdown(); fire(); }

    function headingText() {
        switch (sdtype) {
        case ShutdownType.ShutdownTypeReboot: return bilingual("إعادة تشغيل MoOS", "Restart MoOS");
        case ShutdownType.ShutdownTypeHalt: return bilingual("إيقاف MoOS", "Shut down MoOS");
        case ShutdownType.ShutdownTypeNone: return bilingual("تسجيل الخروج", "Log out");
        default: return bilingual("ماذا تريد أن تفعل؟", "What would you like to do?");
        }
    }

    function bilingual(arabic, english) {
        const ar = "\u2067" + arabic + "\u2069";
        const en = "\u2066" + english + "\u2069";
        return Qt.application.layoutDirection === Qt.RightToLeft ? ar + "  ·  " + en : en + "  ·  " + ar;
    }

    // A single-language SHORT label for the orb captions — the full bilingual
    // string is too wide to sit under a round orb without colliding with its
    // neighbours, so the caption shows the session's own language and the
    // bilingual detail lives in the hover description + Accessible name.
    function shortLabel(arabic, english) {
        return Qt.application.layoutDirection === Qt.RightToLeft ? arabic : english;
    }

    KCoreAddons.KUser { id: currentUser }
    SessionsModel { id: otherSessionsModel; includeUnusedSessions: false; includeOwnSession: false }
    QQC2.Action { shortcut: "Escape"; onTriggered: root.cancelRequested() }

    Timer {
        id: countdownTimer
        interval: 1000; repeat: true; running: !root.showAllOptions
        onTriggered: {
            root.remainingTime -= 1;
            if (root.remainingTime <= 0) { stop(); root.currentAction(); }
        }
    }

    Component.onCompleted: Qt.callLater(root.focusInitialAction)

    // ── Scene: the active theme's OWN wallpaper, blurred ─────────────────────
    // Every look-and-feel package ships its theme's wallpaper as
    // previews/fullscreenpreview.jpg; a package-relative path resolves to the
    // right one for each of the 16 themes, so the doorway is NEVER a flat colour
    // — it is the same background the desktop wears, softened by a real blur.
    // The QML stays byte-identical across packages; only the image differs.
    Image {
        id: wallpaper
        anchors.fill: parent
        source: Qt.resolvedUrl("../previews/fullscreenpreview.jpg")
        fillMode: Image.PreserveAspectCrop
        cache: true
        asynchronous: true
        opacity: 0
        layer.enabled: true
        // MoOS token: the same wallpaper blur the lock uses (breeze WallpaperFader
        // is 50) — so the frosted background reads identically on both screens.
        layer.effect: FastBlur { radius: 54 }
        Component.onCompleted: backdropFade.start()
        OpacityAnimator { id: backdropFade; target: wallpaper; from: 0; to: 1.0
            duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
    }
    // Legibility scrim — the theme's own canvas, heavier at the top and foot so
    // the clock and the dock stay readable over any wallpaper. Calculated
    // transparency, never an opaque wash.
    Rectangle {
        anchors.fill: parent
        opacity: wallpaper.opacity
        // MoOS token — the ONE session scrim (0.52 / 0.30 / 0.60), shared by the
        // lock and the login scene so every surface veils the wallpaper equally.
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.52) }
            GradientStop { position: 0.45; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.30) }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.60) }
        }
    }

    Item {
        anchors.fill: parent
        opacity: 0
        Component.onCompleted: auroraFade.start()
        OpacityAnimator { id: auroraFade; target: parent; from: 0; to: 1
            duration: Kirigami.Units.veryLongDuration; easing.type: Easing.OutCubic }
        Rectangle {
            width: root.width * 1.5; height: root.height * 0.62
            x: -root.width * 0.25; y: root.height * 0.04
            rotation: -9; transformOrigin: Item.Center; opacity: 0.10
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.auroraTint(root.accent) }
                GradientStop { position: 1.0; color: "transparent" } }
            SequentialAnimation on x {
                loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: -root.width * 0.08; duration: 42000; easing.type: Easing.InOutSine }
                NumberAnimation { to: -root.width * 0.25; duration: 42000; easing.type: Easing.InOutSine }
            }
        }
        Rectangle {
            width: root.width * 1.2; height: root.height * 0.5
            x: root.width * 0.12; y: root.height * 0.36
            rotation: 12; transformOrigin: Item.Center; opacity: 0.05
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.auroraTint(root.accentB) }
                GradientStop { position: 1.0; color: "transparent" } }
            SequentialAnimation on x {
                loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: root.width * 0.04; duration: 54000; easing.type: Easing.InOutSine }
                NumberAnimation { to: root.width * 0.12; duration: 54000; easing.type: Easing.InOutSine }
            }
        }
    }

    MouseArea { anchors.fill: parent; onClicked: root.cancelRequested() }

    // ── The command sheet: a live-clock header over a column of action rows ──
    Item {
        id: sheet
        anchors.centerIn: parent
        width: Math.min(root.width - Kirigami.Units.gridUnit * 3, Kirigami.Units.gridUnit * 64)
        height: Math.min(root.height - Kirigami.Units.gridUnit * 3, column.implicitHeight)

        opacity: 0
        transform: Translate { id: sheetRise; y: Kirigami.Units.gridUnit * 2 }
        Component.onCompleted: sheetEnter.start()
        ParallelAnimation {
            id: sheetEnter
            NumberAnimation { target: sheet; property: "opacity"; from: 0; to: 1
                duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
            NumberAnimation { target: sheetRise; property: "y"; from: Kirigami.Units.gridUnit * 2; to: 0
                duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
        }

        MouseArea { anchors.fill: parent; acceptedButtons: Qt.NoButton }

        ColumnLayout {
            id: column
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            // ── Header: emblem, live clock, context — centred over the dock ──
            Item {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.gridUnit * 4.4
                Layout.preferredHeight: Kirigami.Units.gridUnit * 4.4
                Image {
                    anchors.centerIn: parent
                    width: parent.width * 1.9; height: width
                    source: "images/glow-cyan.png"; opacity: 0.5
                    asynchronous: true
                }
                Image {
                    anchors.fill: parent
                    source: "../splash/images/moos-logo.png"
                    fillMode: Image.PreserveAspectFit; smooth: true; asynchronous: true
                    SequentialAnimation on scale {
                        loops: Animation.Infinite; running: root.visible
                        NumberAnimation { to: 1.03; duration: 3200; easing.type: Easing.InOutSine }
                        NumberAnimation { to: 1.0; duration: 3200; easing.type: Easing.InOutSine }
                    }
                }
            }
            // ── Editorial clock — the ONE MoOS clock face, unified with the lock's
            //    MoOSClock: oversized, ultra-thin, an accent colon, a hairline.
            //    Forced LTR so HH:mm never mirrors under RTL.
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                LayoutMirroring.enabled: false
                layoutDirection: Qt.LeftToRight
                spacing: 0
                QQC2.Label {
                    text: root.nowTime.split(":")[0]
                    color: Kirigami.Theme.textColor
                    font.family: "Inter"; font.weight: Font.Thin
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 34
                    font.letterSpacing: -2
                }
                QQC2.Label {
                    text: ":"
                    color: root.accent
                    font.family: "Inter"; font.weight: Font.Thin
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 34
                }
                QQC2.Label {
                    text: root.nowTime.split(":")[1]
                    color: Kirigami.Theme.textColor
                    font.family: "Inter"; font.weight: Font.Thin
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 34
                    font.letterSpacing: -2
                }
            }
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.preferredWidth: Kirigami.Units.gridUnit * 4
                Layout.preferredHeight: 2; radius: 1
                color: root.accent
                opacity: 0.9
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.maximumWidth: Kirigami.Units.gridUnit * 36
                horizontalAlignment: Text.AlignHCenter
                text: root.headingText()
                color: Kirigami.Theme.disabledTextColor
                elide: Text.ElideRight
                font.family: "Inter"
                font.pointSize: Kirigami.Theme.defaultFont.pointSize + 1
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                text: currentUser.fullName
                visible: text.length > 0
                color: root.accent
                font.family: "Inter"; font.weight: Font.DemiBold
                font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            // ── Countdown (only when an action is pending) ──
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: Kirigami.Units.gridUnit * 22
                visible: countdownTimer.running
                spacing: Kirigami.Units.smallSpacing
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 3; radius: 2
                    color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.22)
                    Rectangle {
                        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                        radius: parent.radius; color: root.accent
                        width: parent.width * Math.max(0, Math.min(1, root.remainingTime / 30))
                        Behavior on width { NumberAnimation { duration: 950; easing.type: Easing.Linear } }
                    }
                }
                QQC2.Label {
                    text: root.remainingTime
                    color: root.accent; font.family: "Inter"; font.weight: Font.Bold
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: Kirigami.Units.gridUnit * 34
                horizontalAlignment: Text.AlignHCenter
                visible: otherSessionsModel.count > 0 && (sdtype !== ShutdownType.ShutdownTypeNone || root.showAllOptions)
                text: otherSessionsModel.count === 1
                    ? root.bilingual("يوجد مستخدم آخر مسجّل الدخول وقد يفقد عمله", "Another user is signed in and may lose work")
                    : root.bilingual("يوجد %1 مستخدمين آخرين مسجّلي الدخول".arg(otherSessionsModel.count), "%1 other users are signed in".arg(otherSessionsModel.count))
                color: Kirigami.Theme.neutralTextColor
                wrapMode: Text.WordWrap; font.family: "Inter"; font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignHCenter
                Layout.maximumWidth: Kirigami.Units.gridUnit * 34
                horizontalAlignment: Text.AlignHCenter
                visible: softwareUpdatePending
                text: root.bilingual("تحديثات النظام جاهزة للتثبيت", "System updates are ready to install")
                color: Kirigami.Theme.positiveTextColor
                wrapMode: Text.WordWrap; font.family: "Inter"; font.weight: Font.DemiBold; font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            // ── The power dock: a centred row of action ORBS ──
            RowLayout {
                id: dock
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.largeSpacing

                MoOSUI2ActionButton {
                    id: suspendButton
                    iconName: "system-suspend-symbolic"
                    text: root.shortLabel("تعليق", "Sleep")
                    description: root.bilingual("إبقاء الجلسة", "Keep session")
                    visible: root.showAllOptions && spdMethods.SuspendState
                    onClicked: root.fireNow(() => root.suspendRequested(2))
                    onNavigate: (step) => root.moveFocus(suspendButton, step)
                }
                MoOSUI2ActionButton {
                    id: hibernateButton
                    iconName: "system-suspend-hibernate-symbolic"
                    text: root.shortLabel("إسبات", "Hibernate")
                    description: root.bilingual("حفظ الجلسة", "Save session")
                    visible: root.showAllOptions && spdMethods.HibernateState
                    onClicked: root.fireNow(() => root.suspendRequested(4))
                    onNavigate: (step) => root.moveFocus(hibernateButton, step)
                }
                MoOSUI2ActionButton {
                    id: rebootButton
                    iconName: softwareUpdatePending ? "system-reboot-update-symbolic" : "system-reboot-symbolic"
                    text: softwareUpdatePending ? root.shortLabel("تحديث وإعادة", "Update & Restart") : root.shortLabel("إعادة التشغيل", "Restart")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart")
                        : (softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("بدء جلسة جديدة", "Start fresh"))
                    emphasized: sdtype === ShutdownType.ShutdownTypeReboot
                    visible: maysd && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootButton, () => { if (softwareUpdatePending) { root.rebootUpdateRequested(); } else { root.rebootRequested(); } })
                    onNavigate: (step) => root.moveFocus(rebootButton, step)
                }
                MoOSUI2ActionButton {
                    id: rebootWithoutUpdatesButton
                    iconName: "system-reboot-symbolic"
                    text: root.shortLabel("إعادة الآن", "Restart now")
                    description: armed ? root.bilingual("اضغط مجددًا لإعادة التشغيل", "Tap again to restart") : root.bilingual("بدون تحديث", "Without updating")
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                    onClicked: root.armOrFire(rebootWithoutUpdatesButton, () => root.rebootRequested())
                    onNavigate: (step) => root.moveFocus(rebootWithoutUpdatesButton, step)
                }
                MoOSUI2ActionButton {
                    id: shutdownButton
                    iconName: softwareUpdatePending ? "system-shutdown-update-symbolic" : "system-shutdown-symbolic"
                    text: softwareUpdatePending ? root.shortLabel("تحديث وإيقاف", "Update & Shut Down") : root.shortLabel("إيقاف التشغيل", "Shut Down")
                    description: armed ? root.bilingual("اضغط مجددًا للإيقاف", "Tap again to power off")
                        : (softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("إيقاف الجهاز بأمان", "Power off safely"))
                    emphasized: sdtype === ShutdownType.ShutdownTypeHalt
                    destructive: true
                    visible: maysd && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                    onClicked: root.armOrFire(shutdownButton, () => { if (softwareUpdatePending) { root.haltUpdateRequested(); } else { root.haltRequested(); } })
                    onNavigate: (step) => root.moveFocus(shutdownButton, step)
                }
                MoOSUI2ActionButton {
                    id: shutdownWithoutUpdatesButton
                    iconName: "system-shutdown-symbolic"
                    text: root.shortLabel("إيقاف الآن", "Shut down now")
                    description: armed ? root.bilingual("اضغط مجددًا للإيقاف", "Tap again to power off") : root.bilingual("بدون تحديث", "Without updating")
                    destructive: true
                    visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                    onClicked: root.armOrFire(shutdownWithoutUpdatesButton, () => root.haltRequested())
                    onNavigate: (step) => root.moveFocus(shutdownWithoutUpdatesButton, step)
                }
                MoOSUI2ActionButton {
                    id: logoutButton
                    iconName: "system-log-out-symbolic"
                    text: root.shortLabel("تسجيل الخروج", "Log Out")
                    description: root.bilingual("إنهاء الجلسة", "End session")
                    visible: canLogout && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                    onClicked: root.fireNow(() => root.logoutRequested())
                    onNavigate: (step) => root.moveFocus(logoutButton, step)
                }
                MoOSUI2ActionButton {
                    id: lockButton
                    iconName: "system-lock-screen-symbolic"
                    text: root.shortLabel("قفل الشاشة", "Lock Screen")
                    description: root.bilingual("العودة لاحقًا", "Return later")
                    visible: root.showAllOptions
                    onClicked: root.fireNow(() => root.lockScreenRequested())
                    onNavigate: (step) => root.moveFocus(lockButton, step)
                }
            }

            // ── Cancel — subtle, centred below the dock ──
            MoOSUI2ActionButton {
                id: cancelButton
                iconName: "cancel-operation-symbolic"
                text: root.shortLabel("إلغاء", "Cancel")
                description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: Kirigami.Units.smallSpacing
                onClicked: { root.disarm(); root.cancelRequested(); }
                onNavigate: (step) => root.moveFocus(cancelButton, step)
            }
        }
    }
}
