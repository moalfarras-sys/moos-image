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

    // Mixed Arabic/English strings need explicit directional isolation. Without
    // it the inherited RTL layout moved punctuation across the sentence and
    // rendered the English half before the Arabic half on the live logout
    // screen. Keep the primary session language first while each phrase retains
    // its own natural direction.
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

    // MoOS UI2 "Living Aurora" — flowing curtains of emerald, teal and violet
    // light drifting across the night behind the dialog, over a quiet scatter of
    // stars, with a mote or two rising through the whole scene. Rectangle
    // gradients + Animators only (render thread): no shaders/Canvas on an
    // always-on doorway surface. Vivid at the edges, but the near-opaque glass
    // panel above always keeps the focus.
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

        // A quiet scatter of stars, each breathing at its own rate.
        Repeater {
            model: 18
            delegate: Image {
                id: star
                required property int index
                readonly property var xs: [0.05, 0.14, 0.23, 0.31, 0.40, 0.48, 0.57, 0.66, 0.74, 0.83, 0.91, 0.09, 0.19, 0.37, 0.53, 0.71, 0.88, 0.62]
                readonly property var ys: [0.08, 0.22, 0.05, 0.34, 0.13, 0.44, 0.19, 0.52, 0.10, 0.38, 0.24, 0.60, 0.48, 0.66, 0.30, 0.58, 0.15, 0.70]
                source: "images/spark.png"
                width: Math.max(4, root.height * (0.004 + 0.003 * (star.index % 3)))
                height: width
                x: star.xs[star.index] * root.width
                y: star.ys[star.index] * root.height
                opacity: 0.10
                asynchronous: true
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: root.visible
                    NumberAnimation { to: 0.42; duration: 2200 + star.index * 140; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 0.10; duration: 2200 + star.index * 140; easing.type: Easing.InOutSine }
                }
            }
        }

        // Four aurora curtains: tall vertical light-sheets, each a different jewel
        // tone, drifting horizontally and breathing at its own pace. The gradient
        // fades top and bottom so each reads as a hanging curtain, not a slab.
        Repeater {
            model: 4
            delegate: Rectangle {
                id: curtain
                required property int index
                readonly property color tone: ["#10B981", "#2DD4BF", "#22D3EE", "#8B5CF6"][curtain.index]
                readonly property real baseOp: [0.20, 0.22, 0.16, 0.18][curtain.index]
                width: root.width * [0.42, 0.48, 0.38, 0.46][curtain.index]
                height: root.height * [0.66, 0.72, 0.60, 0.68][curtain.index]
                y: root.height * [0.02, -0.04, 0.10, 0.00][curtain.index]
                rotation: [-16, 12, -10, 18][curtain.index]
                transformOrigin: Item.Center
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.42; color: curtain.tone }
                    GradientStop { position: 1.0; color: "transparent" }
                }
                opacity: baseOp
                XAnimator on x {
                    from: [-0.14, 0.50, 0.16, 0.42][curtain.index] * root.width
                    to: [0.46, -0.06, 0.58, 0.04][curtain.index] * root.width
                    duration: [46000, 58000, 52000, 64000][curtain.index]
                    loops: Animation.Infinite
                    easing.type: Easing.InOutSine
                    running: root.visible
                }
                SequentialAnimation on opacity {
                    loops: Animation.Infinite
                    running: root.visible
                    NumberAnimation { to: curtain.baseOp * 1.45; duration: 5200 + curtain.index * 850; easing.type: Easing.InOutSine }
                    NumberAnimation { to: curtain.baseOp * 0.65; duration: 5200 + curtain.index * 850; easing.type: Easing.InOutSine }
                }
            }
        }

        // Two or three light motes rising slowly through the whole scene.
        Repeater {
            model: 3
            delegate: Image {
                id: mote
                required property int index
                source: "images/spark.png"
                width: Math.max(6, root.height * (0.008 + 0.004 * (mote.index % 2)))
                height: width
                x: [0.22, 0.60, 0.82][mote.index] * root.width
                opacity: [0.22, 0.16, 0.20][mote.index]
                asynchronous: true
                YAnimator on y {
                    from: root.height * 1.05
                    to: -mote.height - root.height * 0.05
                    duration: 42000 + mote.index * 11000
                    loops: Animation.Infinite
                    running: root.visible
                }
            }
        }

        // An occasional shooting star streaks across the upper sky — the one
        // deliberate glint over the calm drift of the curtains.
        Rectangle {
            id: shootingStar
            width: Math.max(40, root.width * 0.045)
            height: 2
            radius: 1
            rotation: 20
            opacity: 0
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 1.0; color: "#EAFDF8" }
            }
            SequentialAnimation {
                loops: Animation.Infinite
                running: root.visible
                PauseAnimation { duration: 8000 }
                ParallelAnimation {
                    NumberAnimation { target: shootingStar; property: "x"; from: root.width * 0.14; to: root.width * 0.60; duration: 1200; easing.type: Easing.InCubic }
                    NumberAnimation { target: shootingStar; property: "y"; from: root.height * 0.12; to: root.height * 0.40; duration: 1200; easing.type: Easing.InCubic }
                    SequentialAnimation {
                        NumberAnimation { target: shootingStar; property: "opacity"; to: 0.9; duration: 260; easing.type: Easing.OutCubic }
                        NumberAnimation { target: shootingStar; property: "opacity"; to: 0; duration: 900; easing.type: Easing.InCubic }
                    }
                }
                PauseAnimation { duration: 6000 }
            }
        }

        // the tide line — a fine luminous horizon in the theme accent, the thread
        // of continuity from the earlier scene, now drawn under the aurora
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
        // The watermark breathes too — twelve seconds a cycle, felt more
        // than seen, so the backdrop is alive without competing with the
        // dialog above it.
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
        // UI2 glass: a near-opaque vertical depth gradient rather than one flat
        // fill, and a TRANSLUCENT inner border — the old full-strength highlight
        // read as a hard teal outline, not a premium edge.
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

        // Premium entrance: the panel fades and rises into place, scaling up a
        // touch — the calm, confident motion of a finished OS, not a jump-cut.
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

                // The animated brand: breathing halo, the emblem, one slow spark —
                // the same living mark the login scene and lock screen carry.
                // Sprites are pre-baked alpha PNGs (artwork/generate_login_scene.py);
                // the motion is Animators-only, no shaders on a shutdown prompt.
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
                    // The comet ring: the same orbit the login scene carries,
                    // counter-rotating against the spark so the mark reads as
                    // one living system on every doorway surface.
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

                // The countdown made visible: a hairline that drains with the
                // seconds, so the remaining time reads at a glance from across
                // the room — not only as a number.
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 14
                    Layout.preferredHeight: 3
                    radius: height / 2
                    visible: countdownTimer.running
                    // Translucent track colour, NOT `opacity` — item opacity
                    // multiplies into children, and would dim the filler too.
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
                    columns: root.width < Kirigami.Units.gridUnit * 50 ? 2 : 4
                    columnSpacing: Kirigami.Units.largeSpacing
                    rowSpacing: Kirigami.Units.largeSpacing

                    MoOSUI2ActionButton {
                        id: suspendButton
                        Layout.fillWidth: true
                        iconName: "system-suspend-symbolic"
                        text: root.bilingual("تعليق", "Sleep")
                        description: root.bilingual("إبقاء الجلسة", "Keep session")
                        visible: root.showAllOptions && spdMethods.SuspendState
                        onClicked: {
                            root.stopCountdown();
                            root.suspendRequested(2);
                        }
                        onNavigate: root.moveFocus(suspendButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: hibernateButton
                        Layout.fillWidth: true
                        iconName: "system-suspend-hibernate-symbolic"
                        text: root.bilingual("إسبات", "Hibernate")
                        description: root.bilingual("حفظ الجلسة", "Save session")
                        visible: root.showAllOptions && spdMethods.HibernateState
                        onClicked: {
                            root.stopCountdown();
                            root.suspendRequested(4);
                        }
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
                            if (softwareUpdatePending) {
                                root.rebootUpdateRequested();
                            } else {
                                root.rebootRequested();
                            }
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
                        onClicked: {
                            root.stopCountdown();
                            root.rebootRequested();
                        }
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
                            if (softwareUpdatePending) {
                                root.haltUpdateRequested();
                            } else {
                                root.haltRequested();
                            }
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
                        onClicked: {
                            root.stopCountdown();
                            root.haltRequested();
                        }
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
                        onClicked: {
                            root.stopCountdown();
                            root.logoutRequested();
                        }
                        onNavigate: root.moveFocus(logoutButton, step)
                    }

                    MoOSUI2ActionButton {
                        id: lockButton
                        Layout.fillWidth: true
                        iconName: "system-lock-screen-symbolic"
                        text: root.bilingual("قفل الشاشة", "Lock Screen")
                        description: root.bilingual("العودة لاحقًا", "Return later")
                        visible: root.showAllOptions
                        onClicked: {
                            root.stopCountdown();
                            root.lockScreenRequested();
                        }
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
