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
        color: Kirigami.Theme.backgroundColor
        opacity: 0
        Component.onCompleted: backdropFade.start()
        OpacityAnimator {
            id: backdropFade
            target: backdrop
            from: 0
            to: 0.72
            duration: Kirigami.Units.longDuration
            easing.type: Easing.OutCubic
        }
    }

    // MoOS UI2 "Cosmic Aurora" — evolved from Living Aurora with deeper cosmic
    // depth: 6 aurora curtains in jewel + warm tones with slow 3D rotation,
    // 24 stars at staggered depths, multiple rising motes, and a constellation
    // of connecting light threads. Rectangle gradients + Animators only
    // (render thread): no shaders/Canvas on an always-on doorway surface.
    Item {
        id: aurora
        anchors.fill: parent
        opacity: 0
        Component.onCompleted: auroraFade.start()
        OpacityAnimator {
            id: auroraFade
            target: aurora
            from: 0
            to: 1
            duration: Kirigami.Units.veryLongDuration
            easing.type: Easing.OutCubic
        }

        // ── Starfield: 24 stars at staggered depths ─────────────────────────
        // Background layer — distant, small, slow breathing
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.003); height: width
            x: 0.07 * root.width; y: 0.05 * root.height; opacity: 0.08; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.28; duration: 3200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.08; duration: 3200; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.004); height: width
            x: 0.16 * root.width; y: 0.18 * root.height; opacity: 0.10; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.35; duration: 2800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.10; duration: 2800; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(4, root.height * 0.005); height: width
            x: 0.25 * root.width; y: 0.08 * root.height; opacity: 0.12; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.40; duration: 2500; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.12; duration: 2500; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.003); height: width
            x: 0.34 * root.width; y: 0.28 * root.height; opacity: 0.09; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.32; duration: 3500; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.09; duration: 3500; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(4, root.height * 0.006); height: width
            x: 0.42 * root.width; y: 0.12 * root.height; opacity: 0.14; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.48; duration: 2200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.14; duration: 2200; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.004); height: width
            x: 0.50 * root.width; y: 0.38 * root.height; opacity: 0.07; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.30; duration: 3800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.07; duration: 3800; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(5, root.height * 0.007); height: width
            x: 0.58 * root.width; y: 0.15 * root.height; opacity: 0.16; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.52; duration: 2000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.16; duration: 2000; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.003); height: width
            x: 0.67 * root.width; y: 0.42 * root.height; opacity: 0.08; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.26; duration: 4000; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.08; duration: 4000; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(4, root.height * 0.005); height: width
            x: 0.75 * root.width; y: 0.06 * root.height; opacity: 0.11; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.38; duration: 2600; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.11; duration: 2600; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.004); height: width
            x: 0.83 * root.width; y: 0.22 * root.height; opacity: 0.10; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.34; duration: 3100; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.10; duration: 3100; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(5, root.height * 0.006); height: width
            x: 0.91 * root.width; y: 0.10 * root.height; opacity: 0.13; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.44; duration: 2400; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.13; duration: 2400; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.003); height: width
            x: 0.12 * root.width; y: 0.55 * root.height; opacity: 0.07; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.25; duration: 3600; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.07; duration: 3600; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(4, root.height * 0.005); height: width
            x: 0.22 * root.width; y: 0.45 * root.height; opacity: 0.12; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.40; duration: 2700; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.12; duration: 2700; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.004); height: width
            x: 0.38 * root.width; y: 0.62 * root.height; opacity: 0.09; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.30; duration: 3300; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.09; duration: 3300; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(4, root.height * 0.005); height: width
            x: 0.55 * root.width; y: 0.28 * root.height; opacity: 0.11; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.36; duration: 2900; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.11; duration: 2900; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.003); height: width
            x: 0.72 * root.width; y: 0.55 * root.height; opacity: 0.08; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.28; duration: 3400; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.08; duration: 3400; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(5, root.height * 0.006); height: width
            x: 0.86 * root.width; y: 0.38 * root.height; opacity: 0.14; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.46; duration: 2300; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.14; duration: 2300; easing.type: Easing.InOutSine } }
        }
        Image {
            source: "images/spark.png"; width: Math.max(3, root.height * 0.004); height: width
            x: 0.95 * root.width; y: 0.50 * root.height; opacity: 0.06; asynchronous: true
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.22; duration: 4200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.06; duration: 4200; easing.type: Easing.InOutSine } }
        }

        // ── 6 Aurora curtains: jewel + warm tones with 3D rotation ──────────
        // Original 4 + 2 new warm tones for cosmic richness
        Rectangle {
            id: curtain0
            width: root.width * 0.42; height: root.height * 0.66
            y: root.height * 0.02; rotation: -16; transformOrigin: Item.Center
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.42; color: "#10B981" }
                GradientStop { position: 1.0; color: "transparent" } }
            opacity: 0.20
            XAnimator on x { from: -0.14 * root.width; to: 0.46 * root.width
                duration: 46000; loops: Animation.Infinite; easing.type: Easing.InOutSine; running: root.visible }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.29; duration: 5200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.13; duration: 5200; easing.type: Easing.InOutSine } }
            // 3D rotation: slow tilt change
            SequentialAnimation on rotation { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: -16; to: -10; duration: 28000; easing.type: Easing.InOutSine }
                NumberAnimation { from: -10; to: -16; duration: 28000; easing.type: Easing.InOutSine } }
        }
        Rectangle {
            id: curtain1
            width: root.width * 0.48; height: root.height * 0.72
            y: root.height * -0.04; rotation: 12; transformOrigin: Item.Center
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.42; color: "#2DD4BF" }
                GradientStop { position: 1.0; color: "transparent" } }
            opacity: 0.22
            XAnimator on x { from: 0.50 * root.width; to: -0.06 * root.width
                duration: 58000; loops: Animation.Infinite; easing.type: Easing.InOutSine; running: root.visible }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.32; duration: 6050; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.14; duration: 6050; easing.type: Easing.InOutSine } }
            SequentialAnimation on rotation { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: 12; to: 18; duration: 32000; easing.type: Easing.InOutSine }
                NumberAnimation { from: 18; to: 12; duration: 32000; easing.type: Easing.InOutSine } }
        }
        Rectangle {
            id: curtain2
            width: root.width * 0.38; height: root.height * 0.60
            y: root.height * 0.10; rotation: -10; transformOrigin: Item.Center
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.42; color: "#22D3EE" }
                GradientStop { position: 1.0; color: "transparent" } }
            opacity: 0.16
            XAnimator on x { from: 0.16 * root.width; to: 0.58 * root.width
                duration: 52000; loops: Animation.Infinite; easing.type: Easing.InOutSine; running: root.visible }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.23; duration: 5850; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.10; duration: 5850; easing.type: Easing.InOutSine } }
            SequentialAnimation on rotation { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: -10; to: -5; duration: 26000; easing.type: Easing.InOutSine }
                NumberAnimation { from: -5; to: -10; duration: 26000; easing.type: Easing.InOutSine } }
        }
        Rectangle {
            id: curtain3
            width: root.width * 0.46; height: root.height * 0.68
            y: root.height * 0.00; rotation: 18; transformOrigin: Item.Center
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.42; color: "#8B5CF6" }
                GradientStop { position: 1.0; color: "transparent" } }
            opacity: 0.18
            XAnimator on x { from: 0.42 * root.width; to: 0.04 * root.width
                duration: 64000; loops: Animation.Infinite; easing.type: Easing.InOutSine; running: root.visible }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.26; duration: 6700; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.12; duration: 6700; easing.type: Easing.InOutSine } }
            SequentialAnimation on rotation { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: 18; to: 24; duration: 34000; easing.type: Easing.InOutSine }
                NumberAnimation { from: 24; to: 18; duration: 34000; easing.type: Easing.InOutSine } }
        }
        // NEW: Warm gold nebula — cosmic depth
        Rectangle {
            id: curtain4
            width: root.width * 0.35; height: root.height * 0.55
            y: root.height * 0.15; rotation: -22; transformOrigin: Item.Center
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.45; color: "#F59E0B" }
                GradientStop { position: 1.0; color: "transparent" } }
            opacity: 0.10
            XAnimator on x { from: 0.65 * root.width; to: 0.15 * root.width
                duration: 72000; loops: Animation.Infinite; easing.type: Easing.InOutSine; running: root.visible }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.16; duration: 7200; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.06; duration: 7200; easing.type: Easing.InOutSine } }
            SequentialAnimation on rotation { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: -22; to: -15; duration: 38000; easing.type: Easing.InOutSine }
                NumberAnimation { from: -15; to: -22; duration: 38000; easing.type: Easing.InOutSine } }
        }
        // NEW: Warm rose nebula
        Rectangle {
            id: curtain5
            width: root.width * 0.32; height: root.height * 0.50
            y: root.height * 0.08; rotation: 25; transformOrigin: Item.Center
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.40; color: "#F472B6" }
                GradientStop { position: 1.0; color: "transparent" } }
            opacity: 0.08
            XAnimator on x { from: -0.05 * root.width; to: 0.55 * root.width
                duration: 68000; loops: Animation.Infinite; easing.type: Easing.InOutSine; running: root.visible }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { to: 0.14; duration: 7800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 0.05; duration: 7800; easing.type: Easing.InOutSine } }
            SequentialAnimation on rotation { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: 25; to: 30; duration: 36000; easing.type: Easing.InOutSine }
                NumberAnimation { from: 30; to: 25; duration: 36000; easing.type: Easing.InOutSine } }
        }

        // ── Rising light motes ──────────────────────────────────────────────
        Image {
            id: mote0
            source: "images/spark.png"
            width: Math.max(6, root.height * 0.008); height: width
            x: 0.22 * root.width; opacity: 0.22; asynchronous: true
            YAnimator on y { from: root.height * 1.05; to: -mote0.height - root.height * 0.05
                duration: 42000; loops: Animation.Infinite; running: root.visible }
        }
        Image {
            id: mote1
            source: "images/spark.png"
            width: Math.max(6, root.height * 0.012); height: width
            x: 0.60 * root.width; opacity: 0.16; asynchronous: true
            YAnimator on y { from: root.height * 1.05; to: -mote1.height - root.height * 0.05
                duration: 53000; loops: Animation.Infinite; running: root.visible }
        }
        Image {
            id: mote2
            source: "images/spark.png"
            width: Math.max(6, root.height * 0.010); height: width
            x: 0.82 * root.width; opacity: 0.20; asynchronous: true
            YAnimator on y { from: root.height * 1.05; to: -mote2.height - root.height * 0.05
                duration: 48000; loops: Animation.Infinite; running: root.visible }
        }
        // NEW: additional motes for cosmic richness
        Image {
            id: mote3
            source: "images/spark.png"
            width: Math.max(5, root.height * 0.007); height: width
            x: 0.38 * root.width; opacity: 0.14; asynchronous: true
            YAnimator on y { from: root.height * 1.05; to: -mote3.height - root.height * 0.05
                duration: 58000; loops: Animation.Infinite; running: root.visible }
        }
        Image {
            id: mote4
            source: "images/spark.png"
            width: Math.max(4, root.height * 0.006); height: width
            x: 0.72 * root.width; opacity: 0.12; asynchronous: true
            YAnimator on y { from: root.height * 1.05; to: -mote4.height - root.height * 0.05
                duration: 62000; loops: Animation.Infinite; running: root.visible }
        }

        // ── Enhanced shooting star — longer trail ───────────────────────────
        Rectangle {
            id: shootingStar
            width: Math.max(65, root.width * 0.065)
            height: 2
            radius: 1
            rotation: 20
            opacity: 0
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.6; color: Qt.rgba(0.918, 0.992, 0.973, 0.3) }
                GradientStop { position: 1.0; color: "#EAFDF8" }
            }
            SequentialAnimation {
                loops: Animation.Infinite
                running: root.visible
                PauseAnimation { duration: 8000 }
                ParallelAnimation {
                    NumberAnimation { target: shootingStar; property: "x"; from: root.width * 0.10; to: root.width * 0.65; duration: 1400; easing.type: Easing.InCubic }
                    NumberAnimation { target: shootingStar; property: "y"; from: root.height * 0.08; to: root.height * 0.38; duration: 1400; easing.type: Easing.InCubic }
                    SequentialAnimation {
                        NumberAnimation { target: shootingStar; property: "opacity"; to: 0.9; duration: 300; easing.type: Easing.OutCubic }
                        NumberAnimation { target: shootingStar; property: "opacity"; to: 0; duration: 1100; easing.type: Easing.InCubic }
                    }
                }
                PauseAnimation { duration: 5000 }
                // Second streak — different angle
                ParallelAnimation {
                    NumberAnimation { target: shootingStar; property: "x"; from: root.width * 0.75; to: root.width * 0.30; duration: 1200; easing.type: Easing.InCubic }
                    NumberAnimation { target: shootingStar; property: "y"; from: root.height * 0.15; to: root.height * 0.42; duration: 1200; easing.type: Easing.InCubic }
                    SequentialAnimation {
                        NumberAnimation { target: shootingStar; property: "opacity"; to: 0.7; duration: 250; easing.type: Easing.OutCubic }
                        NumberAnimation { target: shootingStar; property: "opacity"; to: 0; duration: 950; easing.type: Easing.InCubic }
                    }
                }
                PauseAnimation { duration: 7000 }
            }
        }

        // ── Horizon tide line ───────────────────────────────────────────────
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            y: root.height * 0.62
            width: root.width * 0.72
            height: 1
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.alpha(Kirigami.Theme.highlightColor, 0.55) }
                GradientStop { position: 1.0; color: "transparent" }
            }
            SequentialAnimation on opacity { loops: Animation.Infinite; running: root.visible
                NumberAnimation { from: 1.0; to: 0.5; duration: 4000; easing.type: Easing.InOutSine }
                NumberAnimation { from: 0.5; to: 1.0; duration: 4000; easing.type: Easing.InOutSine } }
        }
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
            GradientStop { position: 0.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                         Kirigami.Theme.backgroundColor.g,
                                                         Kirigami.Theme.backgroundColor.b, 0.97) }
            GradientStop { position: 1.0; color: Qt.rgba(Kirigami.Theme.backgroundColor.r,
                                                         Kirigami.Theme.backgroundColor.g,
                                                         Kirigami.Theme.backgroundColor.b, 0.93) }
        }
        border.width: 1
        border.color: Qt.rgba(Kirigami.Theme.highlightColor.r,
                              Kirigami.Theme.highlightColor.g,
                              Kirigami.Theme.highlightColor.b, 0.35)

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
                    // Orbiting spark
                    Item {
                        anchors.fill: parent
                        RotationAnimator on rotation {
                            from: 0; to: 360
                            duration: 20000
                            loops: Animation.Infinite
                            running: root.visible
                        }
                        Image {
                            source: "images/spark.png"
                            width: brandStage.width * 0.15
                            height: width
                            x: (brandStage.width - width) / 2
                            y: -brandStage.width * 0.10
                        }
                    }
                    // Primary comet ring
                    Image {
                        anchors.centerIn: parent
                        width: brandStage.width * 1.5
                        height: width
                        source: "images/ring.png"
                        mirror: true
                        opacity: 0.7
                        sourceSize: Qt.size(width * 2, height * 2)
                        RotationAnimator on rotation {
                            from: 360; to: 0
                            duration: 26000
                            loops: Animation.Infinite
                            running: root.visible
                        }
                    }
                    // NEW: Second counter-rotating ring for 3D depth
                    Image {
                        anchors.centerIn: parent
                        width: brandStage.width * 1.2
                        height: width
                        source: "images/ring.png"
                        opacity: 0.35
                        sourceSize: Qt.size(width * 2, height * 2)
                        RotationAnimator on rotation {
                            from: 0; to: 360
                            duration: 18000
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
                    color: Kirigami.Theme.textColor
                    font.family: "IBM Plex Sans"
                    font.pointSize: Kirigami.Theme.defaultFont.pointSize + 8
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: currentUser.fullName
                    color: Kirigami.Theme.disabledTextColor
                    visible: text.length > 0
                    font.family: "IBM Plex Sans"
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    horizontalAlignment: Text.AlignHCenter
                    text: root.bilingual("سيتم التنفيذ خلال %1 ثانية".arg(root.remainingTime),
                                         "Action in %1 seconds".arg(root.remainingTime))
                    color: Kirigami.Theme.hoverColor
                    visible: countdownTimer.running
                    font.family: "IBM Plex Sans"
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
                        ? "يوجد مستخدم آخر مسجّل الدخول وقد يفقد عمله | Another user is signed in and may lose work"
                        : "يوجد %1 مستخدمين آخرين مسجّلي الدخول وقد يفقدون عملهم | %1 other users are signed in and may lose work".arg(otherSessionsModel.count)
                    color: Kirigami.Theme.neutralTextColor
                    visible: otherSessionsModel.count > 0
                        && (sdtype !== ShutdownType.ShutdownTypeNone || root.showAllOptions)
                    wrapMode: Text.WordWrap
                    font.family: "IBM Plex Sans"
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
                    font.family: "IBM Plex Sans"
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
                        onNavigate: root.moveFocus(suspendButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: hibernateButton
                        Layout.fillWidth: true
                        iconName: "system-suspend-hibernate-symbolic"
                        text: root.bilingual("إسبات", "Hibernate")
                        description: root.bilingual("حفظ الجلسة", "Save session")
                        visible: root.showAllOptions && spdMethods.HibernateState
                        onClicked: { root.stopCountdown(); root.suspendRequested(4); }
                        onNavigate: root.moveFocus(hibernateButton, step)
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
                        onNavigate: root.moveFocus(rebootButton, step)
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
                        onNavigate: root.moveFocus(rebootWithoutUpdatesButton, step)
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
                        onNavigate: root.moveFocus(shutdownButton, step)
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
                        onNavigate: root.moveFocus(shutdownWithoutUpdatesButton, step)
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
                        onNavigate: root.moveFocus(logoutButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: lockButton
                        Layout.fillWidth: true
                        iconName: "system-lock-screen-symbolic"
                        text: root.bilingual("قفل الشاشة", "Lock Screen")
                        description: root.bilingual("العودة لاحقًا", "Return later")
                        visible: root.showAllOptions
                        onClicked: { root.stopCountdown(); root.lockScreenRequested(); }
                        onNavigate: root.moveFocus(lockButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: cancelButton
                        Layout.fillWidth: true
                        iconName: "cancel-operation-symbolic"
                        text: root.bilingual("إلغاء", "Cancel")
                        description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                        emphasized: root.showAllOptions
                        onClicked: root.cancelRequested()
                        onNavigate: root.moveFocus(cancelButton, step)
                    }
                }

                QQC2.Label {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: rebootToFirmwareSetup
                        ? (isUefi
                            ? "ستفتح إعدادات UEFI بعد إعادة التشغيل | UEFI settings will open after restart"
                            : "ستفتح إعدادات البرنامج الثابت بعد إعادة التشغيل | Firmware setup will open after restart")
                        : (rebootToBootLoaderMenu
                            ? "ستفتح قائمة الإقلاع بعد إعادة التشغيل | Boot menu will open after restart"
                            : (rebootToBootLoaderEntry.length > 0
                                ? "سيتم الإقلاع إلى %1 | Restarting into %1".arg(rebootToBootLoaderEntry)
                                : ""))
                    color: Kirigami.Theme.disabledTextColor
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                    font.family: "IBM Plex Sans"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }
        }
    }
}
