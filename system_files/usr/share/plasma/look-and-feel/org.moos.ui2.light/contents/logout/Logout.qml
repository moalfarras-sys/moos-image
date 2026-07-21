/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: GPL-2.0-or-later

    The host contract and capability rules are derived from KDE Plasma 6.7's
    org.kde.breeze Logout.qml. The visual implementation is original MoOS UI2.
*/

pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts

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

    function stopCountdown() {
        countdownTimer.stop();
    }

    function currentAction() {
        switch (sdtype) {
        case ShutdownType.ShutdownTypeReboot:
            if (softwareUpdatePending) {
                rebootUpdateRequested();
            } else {
                rebootRequested();
            }
            break;
        case ShutdownType.ShutdownTypeHalt:
            if (softwareUpdatePending) {
                haltUpdateRequested();
            } else {
                haltRequested();
            }
            break;
        default:
            logoutRequested();
        }
    }

    function visibleActions() {
        const candidates = [
            suspendButton,
            hibernateButton,
            rebootButton,
            rebootWithoutUpdatesButton,
            shutdownButton,
            shutdownWithoutUpdatesButton,
            logoutButton,
            lockButton,
            cancelButton
        ];
        const result = [];
        for (let index = 0; index < candidates.length; ++index) {
            if (candidates[index].visible && candidates[index].enabled) {
                result.push(candidates[index]);
            }
        }
        return result;
    }

    function moveFocus(button, step) {
        const actions = visibleActions();
        if (actions.length === 0) {
            return;
        }
        let logicalStep = step;
        if (Qt.application.layoutDirection === Qt.RightToLeft) {
            logicalStep *= -1;
        }
        const currentIndex = Math.max(0, actions.indexOf(button));
        const nextIndex = (currentIndex + logicalStep + actions.length) % actions.length;
        actions[nextIndex].forceActiveFocus(Qt.TabFocusReason);
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

    function headingText() {
        switch (sdtype) {
        case ShutdownType.ShutdownTypeReboot:
            return bilingual("إعادة تشغيل MoOS", "Restart MoOS");
        case ShutdownType.ShutdownTypeHalt:
            return bilingual("إيقاف MoOS", "Shut down MoOS");
        case ShutdownType.ShutdownTypeNone:
            return bilingual("تسجيل الخروج", "Log out");
        default:
            return bilingual("ماذا تريد أن تفعل؟", "What would you like to do?");
        }
    }

    function bilingual(arabic, english) {
        const ar = "\u2067" + arabic + "\u2069";
        const en = "\u2066" + english + "\u2069";
        return Qt.application.layoutDirection === Qt.RightToLeft
            ? ar + "  ·  " + en
            : en + "  ·  " + ar;
    }

    // The aurora curtains were authored with fixed cosmic jewel tones, so every
    // theme in the family (Midnight, Amethyst, Forge, …) showed the identical
    // cyan-violet-rose logout — the one doorway that never tracked its own accent.
    // auroraTint() keeps each designed hue but pulls it 40% toward the live
    // Kirigami highlightColor, so the aurora stays a rich multi-colour sweep while
    // taking on the current theme's identity. Qt.tint composites the accent (at
    // 0.4 alpha) over the base, i.e. a bounded lerp — it can never yield a broken
    // colour, and a palette change now reaches this surface for free.
    function auroraTint(base) {
        const a = Kirigami.Theme.highlightColor;
        return Qt.tint(base, Qt.rgba(a.r, a.g, a.b, 0.40));
    }

    KCoreAddons.KUser {
        id: currentUser
    }

    SessionsModel {
        id: otherSessionsModel
        includeUnusedSessions: false
        includeOwnSession: false
    }

    QQC2.Action {
        shortcut: "Escape"
        onTriggered: root.cancelRequested()
    }

    Timer {
        id: countdownTimer
        interval: 1000
        repeat: true
        running: !root.showAllOptions
        onTriggered: {
            root.remainingTime -= 1;
            if (root.remainingTime <= 0) {
                stop();
                root.currentAction();
            }
        }
    }

    Component.onCompleted: Qt.callLater(root.focusInitialAction)

    Rectangle {
        id: backdrop
        anchors.fill: parent
        color: "#070A0C"
        opacity: 0
        Component.onCompleted: backdropFade.start()
        OpacityAnimator {
            id: backdropFade
            target: backdrop
            from: 0
            to: 0.88
            duration: Kirigami.Units.longDuration
            easing.type: Easing.OutCubic
        }
    }

    // MoOS UI2 "Cosmic Aurora" — evolved from Living Aurora with deeper cosmic
    // depth: 6 aurora curtains in jewel + warm tones with slow 3D rotation,
    // 24 stars at staggered depths, multiple rising motes, and a constellation
    // of connecting light threads. Rectangle gradients + Animators only
    // (render thread): no shaders/Canvas on an always-on doorway surface.
    // ── MoOS UI2 · Liquid Glass — a calm, theme-lit scene ──────────────────
    // Content leads. A whisper of the Graphite wallpaper, six SOFT aurora veils
    // that each track the live accent through auroraTint(), and two glow pools.
    // The starfield, motes and shooting stars that made this screen noisy are gone.
    Image {
        anchors.fill: parent
        source: "file:///usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"
        fillMode: Image.PreserveAspectCrop
        opacity: 0.18
        asynchronous: true
        cache: true
        sourceSize: Qt.size(root.width, root.height)
    }
    Rectangle { anchors.fill: parent; color: "#070A0C"; opacity: 0.45 }

    // MoOS signature: ONE slow aurora ribbon that tracks the live theme accent,
    // plus a single companion veil for depth. Two animated surfaces replace the
    // former six — the scene still breathes, the GPU barely wakes.
    Item {
        anchors.fill: parent
        opacity: 0
        Component.onCompleted: auroraCalmFade.start()
        OpacityAnimator { id: auroraCalmFade; target: parent; from: 0; to: 1; duration: Kirigami.Units.veryLongDuration; easing.type: Easing.OutCubic }
        Rectangle {
            width: root.width * 1.5; height: root.height * 0.66
            x: -root.width * 0.25; y: root.height * 0.04
            rotation: -9; transformOrigin: Item.Center; opacity: 0.17
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.auroraTint("#2DD4BF") }
                GradientStop { position: 1.0; color: "transparent" } }
            SequentialAnimation on x {
                loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: -root.width * 0.08; duration: 40000; easing.type: Easing.InOutSine }
                NumberAnimation { to: -root.width * 0.25; duration: 40000; easing.type: Easing.InOutSine }
            }
        }
        Rectangle {
            width: root.width * 1.2; height: root.height * 0.5
            x: root.width * 0.1; y: root.height * 0.34
            rotation: 12; transformOrigin: Item.Center; opacity: 0.08
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.auroraTint("#8B5CF6") }
                GradientStop { position: 1.0; color: "transparent" } }
            SequentialAnimation on x {
                loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: root.width * 0.02; duration: 52000; easing.type: Easing.InOutSine }
                NumberAnimation { to: root.width * 0.1; duration: 52000; easing.type: Easing.InOutSine }
            }
        }
    }

    Image {
        source: "images/glow-cyan.png"
        width: Math.max(root.width, root.height) * 0.6
        height: width
        x: root.width * 0.5 - width / 2
        y: root.height * 0.34 - height / 2
        opacity: 0.4
        asynchronous: true
        sourceSize: Qt.size(width, width)
    }
    Image {
        source: "images/glow-violet.png"
        width: Math.max(root.width, root.height) * 0.5
        height: width
        x: root.width * 0.86 - width / 2
        y: root.height * 0.9 - height / 2
        opacity: 0.28
        asynchronous: true
        sourceSize: Qt.size(width, width)
    }

    Image {
        anchors {
            horizontalCenter: parent.horizontalCenter
            bottom: parent.bottom
            bottomMargin: -Kirigami.Units.gridUnit * 5
        }
        width: Math.min(root.width, root.height) * 0.68
        height: width
        source: "../splash/images/moos-logo.png"
        fillMode: Image.PreserveAspectFit
        opacity: 0.075
        asynchronous: true
        SequentialAnimation on scale {
            loops: Animation.Infinite
            running: root.visible
            NumberAnimation { to: 1.025; duration: 6000; easing.type: Easing.InOutSine }
            NumberAnimation { to: 1.0; duration: 6000; easing.type: Easing.InOutSine }
        }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: root.cancelRequested()
    }

    Rectangle {
        id: glassPanel

        anchors.centerIn: parent
        width: Math.min(root.width - Kirigami.Units.gridUnit * 4, Kirigami.Units.gridUnit * 62)
        height: Math.min(root.height - Kirigami.Units.gridUnit * 4, contentColumn.implicitHeight + Kirigami.Units.gridUnit * 4)
        radius: Kirigami.Units.gridUnit
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0.94, 0.97, 0.96, 0.085) }
            GradientStop { position: 1.0; color: Qt.rgba(0.94, 0.97, 0.96, 0.035) }
        }
        border.width: 1.5
        border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                              Kirigami.Theme.highlightColor.g,
                              Kirigami.Theme.highlightColor.b, 0.55)

        opacity: 0
        scale: 0.95
        transform: Translate { id: panelRise; y: Kirigami.Units.gridUnit * 1.5 }
        Component.onCompleted: panelEntrance.start()
        ParallelAnimation {
            id: panelEntrance
            NumberAnimation { target: glassPanel; property: "opacity"; from: 0; to: 0.92
                duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
            NumberAnimation { target: glassPanel; property: "scale"; from: 0.95; to: 1.0
                duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
            NumberAnimation { target: panelRise; property: "y"; from: Kirigami.Units.gridUnit * 1.5; to: 0
                duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.NoButton
        }

        // ── Glass refraction lines — 3 thin translucent diagonal streaks ────
        // that drift slowly across the panel, simulating light refracting
        // through glass. Rectangle + x animation only.
        Item {
            anchors.fill: parent
            clip: true

            Rectangle {
                id: refract1
                width: parent.width * 0.06
                height: parent.height * 2.0
                rotation: 22
                y: -parent.height * 0.5
                color: Kirigami.Theme.textColor
                opacity: 0.03
                NumberAnimation on x {
                    from: -100; to: glassPanel.width + 100
                    duration: 18000; loops: Animation.Infinite
                    easing.type: Easing.Linear; running: root.visible
                }
            }
            Rectangle {
                id: refract2
                width: parent.width * 0.04
                height: parent.height * 2.0
                rotation: 22
                y: -parent.height * 0.5
                color: Kirigami.Theme.textColor
                opacity: 0.02
                NumberAnimation on x {
                    from: -200; to: glassPanel.width + 200
                    duration: 26000; loops: Animation.Infinite
                    easing.type: Easing.Linear; running: root.visible
                }
            }
            Rectangle {
                id: refract3
                width: parent.width * 0.03
                height: parent.height * 2.0
                rotation: 22
                y: -parent.height * 0.5
                color: Kirigami.Theme.highlightColor
                opacity: 0.02
                NumberAnimation on x {
                    from: -150; to: glassPanel.width + 150
                    duration: 22000; loops: Animation.Infinite
                    easing.type: Easing.Linear; running: root.visible
                }
            }
        }

        Rectangle {
            anchors {
                top: parent.top
                horizontalCenter: parent.horizontalCenter
                topMargin: 1
            }
            width: parent.width - 2
            height: 1
            radius: glassPanel.radius
            color: Kirigami.Theme.textColor
            opacity: 0.10
        }

        QQC2.ScrollView {
            anchors {
                fill: parent
                margins: Kirigami.Units.gridUnit * 2
            }
            clip: true

            ColumnLayout {
                id: contentColumn
                width: glassPanel.width - Kirigami.Units.gridUnit * 4
                spacing: Kirigami.Units.largeSpacing

                // ── Animated brand stage ────────────────────────────────────
                Item {
                    id: brandStage
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 5.5
                    Layout.preferredHeight: Layout.preferredWidth

                    Image {
                        anchors.centerIn: parent
                        width: parent.width * 2.2
                        height: width
                        source: "images/glow-cyan.png"
                        opacity: 0.5
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.visible
                            NumberAnimation { to: 0.8; duration: 3400; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.5; duration: 3400; easing.type: Easing.InOutSine }
                        }
                    }
                    Image {
                        anchors.centerIn: parent
                        width: parent.width * 1.7
                        height: width
                        source: "images/glow-violet.png"
                        opacity: 0.55
                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: root.visible
                            NumberAnimation { to: 0.32; duration: 3400; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.55; duration: 3400; easing.type: Easing.InOutSine }
                        }
                    }
                    Image {
                        id: brandEmblem
                        anchors.centerIn: parent
                        width: parent.width
                        height: parent.height
                        source: "../splash/images/moos-logo.png"
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        smooth: true
                        SequentialAnimation on scale {
                            loops: Animation.Infinite
                            running: root.visible
                            NumberAnimation { to: 1.03; duration: 2900; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 1.0; duration: 2900; easing.type: Easing.InOutSine }
                        }
                    }
                    // A single slow halo ring — the one piece of orbital motion.
                    Image {
                        anchors.centerIn: parent
                        width: brandStage.width * 1.5
                        height: width
                        source: "images/ring.png"
                        mirror: true
                        opacity: 0.6
                        sourceSize: Qt.size(width * 2, height * 2)
                        RotationAnimator on rotation {
                            from: 360; to: 0
                            duration: 30000
                            loops: Animation.Infinite
                            running: root.visible
                        }
                    }
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: root.headingText()
                    color: "#F2F7F5"
                    font.family: "Inter"
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 12
                    font.weight: Font.Bold
                    font.letterSpacing: -0.5
                    wrapMode: Text.WordWrap
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: currentUser.fullName
                    color: "#AEBFBB"
                    visible: text.length > 0
                    font.family: "Inter"
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: root.bilingual("سيتم التنفيذ خلال %1 ثانية".arg(root.remainingTime),
                                         "Action in %1 seconds".arg(root.remainingTime))
                    color: Kirigami.Theme.hoverColor
                    visible: countdownTimer.running
                    font.family: "Inter"
                    font.weight: Font.DemiBold
                }

                // Countdown progress bar
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 14
                    Layout.preferredHeight: 3
                    radius: height / 2
                    visible: countdownTimer.running
                    color: Qt.alpha(Kirigami.Theme.highlightColor, 0.25)

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        radius: parent.radius
                        color: Kirigami.Theme.highlightColor
                        width: parent.width * Math.max(0, Math.min(1, root.remainingTime / 30))
                        Behavior on width {
                            NumberAnimation { duration: 950; easing.type: Easing.Linear }
                        }
                    }
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: otherSessionsModel.count === 1
                        ? root.bilingual("يوجد مستخدم آخر مسجّل الدخول وقد يفقد عمله",
                                         "Another user is signed in and may lose work")
                        : root.bilingual("يوجد %1 مستخدمين آخرين مسجّلي الدخول وقد يفقدون عملهم".arg(otherSessionsModel.count),
                                         "%1 other users are signed in and may lose work".arg(otherSessionsModel.count))
                    color: Kirigami.Theme.neutralTextColor
                    visible: otherSessionsModel.count > 0
                        && (sdtype !== ShutdownType.ShutdownTypeNone || root.showAllOptions)
                    wrapMode: Text.WordWrap
                    font.family: "Inter"
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: root.bilingual("تحديثات النظام جاهزة للتثبيت",
                                         "System updates are ready to install")
                    color: Kirigami.Theme.positiveTextColor
                    visible: softwareUpdatePending
                    wrapMode: Text.WordWrap
                    font.family: "Inter"
                    font.weight: Font.DemiBold
                }

                GridLayout {
                    id: actionGrid

                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    columns: root.width < Kirigami.Units.gridUnit * 55 ? 2 : 3
                    columnSpacing: Kirigami.Units.largeSpacing
                    rowSpacing: Kirigami.Units.largeSpacing

                    MoOSUI2ActionButton {
                        id: suspendButton
                        Layout.fillWidth: true
                        iconName: "system-suspend-symbolic"
                        text: root.bilingual("تعليق", "Sleep")
                        description: root.bilingual("إبقاء الجلسة", "Keep session")
                        visible: root.showAllOptions && spdMethods.SuspendState
                        onClicked: { root.stopCountdown(); root.suspendRequested(2); }
                        onNavigate: (step) => root.moveFocus(suspendButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: hibernateButton
                        Layout.fillWidth: true
                        iconName: "system-suspend-hibernate-symbolic"
                        text: root.bilingual("إسبات", "Hibernate")
                        description: root.bilingual("حفظ الجلسة", "Save session")
                        visible: root.showAllOptions && spdMethods.HibernateState
                        onClicked: { root.stopCountdown(); root.suspendRequested(4); }
                        onNavigate: (step) => root.moveFocus(hibernateButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: rebootButton
                        Layout.fillWidth: true
                        iconName: softwareUpdatePending ? "system-reboot-update-symbolic" : "system-reboot-symbolic"
                        text: softwareUpdatePending
                            ? root.bilingual("تحديث وإعادة تشغيل", "Update & Restart")
                            : root.bilingual("إعادة التشغيل", "Restart")
                        description: softwareUpdatePending
                            ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first")
                            : root.bilingual("بدء جلسة جديدة", "Start fresh")
                        emphasized: sdtype === ShutdownType.ShutdownTypeReboot
                        visible: maysd && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                        onClicked: {
                            root.stopCountdown();
                            if (softwareUpdatePending) { root.rebootUpdateRequested(); }
                            else { root.rebootRequested(); }
                        }
                        onNavigate: (step) => root.moveFocus(rebootButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: rebootWithoutUpdatesButton
                        Layout.fillWidth: true
                        iconName: "system-reboot-symbolic"
                        text: root.bilingual("إعادة التشغيل الآن", "Restart now")
                        description: root.bilingual("بدون تحديث", "Without updating")
                        visible: maysd && softwareUpdatePending
                            && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                        onClicked: { root.stopCountdown(); root.rebootRequested(); }
                        onNavigate: (step) => root.moveFocus(rebootWithoutUpdatesButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: shutdownButton
                        Layout.fillWidth: true
                        iconName: softwareUpdatePending ? "system-shutdown-update-symbolic" : "system-shutdown-symbolic"
                        text: softwareUpdatePending
                            ? root.bilingual("تحديث وإيقاف", "Update & Shut Down")
                            : root.bilingual("إيقاف التشغيل", "Shut Down")
                        description: softwareUpdatePending
                            ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first")
                            : root.bilingual("إيقاف الجهاز بأمان", "Power off safely")
                        emphasized: sdtype === ShutdownType.ShutdownTypeHalt
                        destructive: true
                        visible: maysd && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                        onClicked: {
                            root.stopCountdown();
                            if (softwareUpdatePending) { root.haltUpdateRequested(); }
                            else { root.haltRequested(); }
                        }
                        onNavigate: (step) => root.moveFocus(shutdownButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: shutdownWithoutUpdatesButton
                        Layout.fillWidth: true
                        iconName: "system-shutdown-symbolic"
                        text: root.bilingual("إيقاف الآن", "Shut down now")
                        description: root.bilingual("بدون تحديث", "Without updating")
                        destructive: true
                        visible: maysd && softwareUpdatePending
                            && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                        onClicked: { root.stopCountdown(); root.haltRequested(); }
                        onNavigate: (step) => root.moveFocus(shutdownWithoutUpdatesButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: logoutButton
                        Layout.fillWidth: true
                        iconName: "system-log-out-symbolic"
                        text: root.bilingual("تسجيل الخروج", "Log Out")
                        description: root.bilingual("إنهاء الجلسة", "End session")
                        visible: canLogout
                            && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                        onClicked: { root.stopCountdown(); root.logoutRequested(); }
                        onNavigate: (step) => root.moveFocus(logoutButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: lockButton
                        Layout.fillWidth: true
                        iconName: "system-lock-screen-symbolic"
                        text: root.bilingual("قفل الشاشة", "Lock Screen")
                        description: root.bilingual("العودة لاحقًا", "Return later")
                        visible: root.showAllOptions
                        onClicked: { root.stopCountdown(); root.lockScreenRequested(); }
                        onNavigate: (step) => root.moveFocus(lockButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: cancelButton
                        Layout.fillWidth: true
                        iconName: "cancel-operation-symbolic"
                        text: root.bilingual("إلغاء", "Cancel")
                        description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                        emphasized: root.showAllOptions
                        onClicked: root.cancelRequested()
                        onNavigate: (step) => root.moveFocus(cancelButton, step)
                    }
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: rebootToFirmwareSetup
                        ? (isUefi
                            ? root.bilingual("ستفتح إعدادات UEFI بعد إعادة التشغيل", "UEFI settings will open after restart")
                            : root.bilingual("ستفتح إعدادات البرنامج الثابت بعد إعادة التشغيل", "Firmware setup will open after restart"))
                        : (rebootToBootLoaderMenu
                            ? root.bilingual("ستفتح قائمة الإقلاع بعد إعادة التشغيل", "Boot menu will open after restart")
                            : (rebootToBootLoaderEntry.length > 0
                                ? root.bilingual("سيتم الإقلاع إلى %1".arg(rebootToBootLoaderEntry),
                                                 "Restarting into %1".arg(rebootToBootLoaderEntry))
                                : ""))
                    color: Kirigami.Theme.disabledTextColor
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                    font.family: "Inter"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }
        }
    }
}
