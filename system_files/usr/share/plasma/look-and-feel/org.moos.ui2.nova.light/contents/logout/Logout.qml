/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras
    SPDX-License-Identifier: GPL-2.0-or-later

    The host contract (signals, ShutdownType, spdMethods, maysd, canLogout,
    softwareUpdatePending, remainingTime) is KDE Plasma 6.7's org.kde.breeze
    Logout.qml — untouched, so every action stays wired to the system. The
    visual design is an original MoOS UI2 ground-up rework: an immersive dark
    scene, a live-clock header, and a single vertical column of full-width
    command ROWS. No tile grid, no bento — a new shape and a new arrangement.
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
    readonly property color accent: Kirigami.Theme.highlightColor

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

    // ── Immersive dark scene ────────────────────────────────────────────────
    Rectangle {
        id: backdrop
        anchors.fill: parent
        color: "#070A0C"
        opacity: 0
        Component.onCompleted: backdropFade.start()
        OpacityAnimator { id: backdropFade; target: backdrop; from: 0; to: 0.90
            duration: Kirigami.Units.longDuration; easing.type: Easing.OutCubic }
    }
    Image {
        anchors.fill: parent
        source: "file:///usr/share/wallpapers/MoOSUI2Graphite/contents/images_dark/3840x2160.jpg"
        fillMode: Image.PreserveAspectCrop
        opacity: 0.15
        asynchronous: true; cache: true
        sourceSize: Qt.size(root.width, root.height)
    }
    Rectangle { anchors.fill: parent; color: "#070A0C"; opacity: 0.5 }

    Item {
        anchors.fill: parent
        opacity: 0
        Component.onCompleted: auroraFade.start()
        OpacityAnimator { id: auroraFade; target: parent; from: 0; to: 1
            duration: Kirigami.Units.veryLongDuration; easing.type: Easing.OutCubic }
        Rectangle {
            width: root.width * 1.5; height: root.height * 0.62
            x: -root.width * 0.25; y: root.height * 0.04
            rotation: -9; transformOrigin: Item.Center; opacity: 0.17
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.auroraTint("#2DD4BF") }
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
            rotation: 12; transformOrigin: Item.Center; opacity: 0.08
            gradient: Gradient { orientation: Gradient.Vertical
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: root.auroraTint("#8B5CF6") }
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
        width: Math.min(root.width - Kirigami.Units.gridUnit * 6, Kirigami.Units.gridUnit * 33)
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
            spacing: Kirigami.Units.smallSpacing

            // ── Header: emblem + live clock + context line ──
            RowLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: Kirigami.Units.gridUnit
                spacing: Kirigami.Units.largeSpacing

                Item {
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 3.4
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 3.4
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
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    QQC2.Label {
                        text: root.nowTime
                        color: "#F2F7F5"
                        font.family: "Inter"; font.weight: Font.Bold
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize + 17
                        font.letterSpacing: -1
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: root.headingText()
                        color: "#AEBFBB"
                        elide: Text.ElideRight
                        font.family: "Inter"
                    }
                    QQC2.Label {
                        text: currentUser.fullName
                        visible: text.length > 0
                        color: root.accent
                        font.family: "Inter"; font.weight: Font.DemiBold
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                    }
                }
            }

            // ── Countdown (only when an action is pending) ──
            RowLayout {
                Layout.fillWidth: true
                Layout.bottomMargin: Kirigami.Units.smallSpacing
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
                Layout.fillWidth: true
                visible: otherSessionsModel.count > 0 && (sdtype !== ShutdownType.ShutdownTypeNone || root.showAllOptions)
                text: otherSessionsModel.count === 1
                    ? root.bilingual("يوجد مستخدم آخر مسجّل الدخول وقد يفقد عمله", "Another user is signed in and may lose work")
                    : root.bilingual("يوجد %1 مستخدمين آخرين مسجّلي الدخول".arg(otherSessionsModel.count), "%1 other users are signed in".arg(otherSessionsModel.count))
                color: Kirigami.Theme.neutralTextColor
                wrapMode: Text.WordWrap; font.family: "Inter"; font.pointSize: Kirigami.Theme.smallFont.pointSize
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: softwareUpdatePending
                text: root.bilingual("تحديثات النظام جاهزة للتثبيت", "System updates are ready to install")
                color: Kirigami.Theme.positiveTextColor
                wrapMode: Text.WordWrap; font.family: "Inter"; font.weight: Font.DemiBold; font.pointSize: Kirigami.Theme.smallFont.pointSize
            }

            // ── The action rows ──
            MoOSUI2ActionButton {
                id: suspendButton
                iconName: "system-suspend-symbolic"
                text: root.bilingual("تعليق", "Sleep")
                description: root.bilingual("إبقاء الجلسة", "Keep session")
                visible: root.showAllOptions && spdMethods.SuspendState
                onClicked: { root.stopCountdown(); root.suspendRequested(2); }
                onNavigate: (step) => root.moveFocus(suspendButton, step)
            }
            MoOSUI2ActionButton {
                id: hibernateButton
                iconName: "system-suspend-hibernate-symbolic"
                text: root.bilingual("إسبات", "Hibernate")
                description: root.bilingual("حفظ الجلسة", "Save session")
                visible: root.showAllOptions && spdMethods.HibernateState
                onClicked: { root.stopCountdown(); root.suspendRequested(4); }
                onNavigate: (step) => root.moveFocus(hibernateButton, step)
            }
            MoOSUI2ActionButton {
                id: rebootButton
                iconName: softwareUpdatePending ? "system-reboot-update-symbolic" : "system-reboot-symbolic"
                text: softwareUpdatePending ? root.bilingual("تحديث وإعادة تشغيل", "Update & Restart") : root.bilingual("إعادة التشغيل", "Restart")
                description: softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("بدء جلسة جديدة", "Start fresh")
                emphasized: sdtype === ShutdownType.ShutdownTypeReboot
                visible: maysd && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                onClicked: { root.stopCountdown(); if (softwareUpdatePending) { root.rebootUpdateRequested(); } else { root.rebootRequested(); } }
                onNavigate: (step) => root.moveFocus(rebootButton, step)
            }
            MoOSUI2ActionButton {
                id: rebootWithoutUpdatesButton
                iconName: "system-reboot-symbolic"
                text: root.bilingual("إعادة التشغيل الآن", "Restart now")
                description: root.bilingual("بدون تحديث", "Without updating")
                visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                onClicked: { root.stopCountdown(); root.rebootRequested(); }
                onNavigate: (step) => root.moveFocus(rebootWithoutUpdatesButton, step)
            }
            MoOSUI2ActionButton {
                id: shutdownButton
                iconName: softwareUpdatePending ? "system-shutdown-update-symbolic" : "system-shutdown-symbolic"
                text: softwareUpdatePending ? root.bilingual("تحديث وإيقاف", "Update & Shut Down") : root.bilingual("إيقاف التشغيل", "Shut Down")
                description: softwareUpdatePending ? root.bilingual("تثبيت التحديثات أولًا", "Install updates first") : root.bilingual("إيقاف الجهاز بأمان", "Power off safely")
                emphasized: sdtype === ShutdownType.ShutdownTypeHalt
                destructive: true
                visible: maysd && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                onClicked: { root.stopCountdown(); if (softwareUpdatePending) { root.haltUpdateRequested(); } else { root.haltRequested(); } }
                onNavigate: (step) => root.moveFocus(shutdownButton, step)
            }
            MoOSUI2ActionButton {
                id: shutdownWithoutUpdatesButton
                iconName: "system-shutdown-symbolic"
                text: root.bilingual("إيقاف الآن", "Shut down now")
                description: root.bilingual("بدون تحديث", "Without updating")
                destructive: true
                visible: maysd && softwareUpdatePending && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                onClicked: { root.stopCountdown(); root.haltRequested(); }
                onNavigate: (step) => root.moveFocus(shutdownWithoutUpdatesButton, step)
            }
            MoOSUI2ActionButton {
                id: logoutButton
                iconName: "system-log-out-symbolic"
                text: root.bilingual("تسجيل الخروج", "Log Out")
                description: root.bilingual("إنهاء الجلسة", "End session")
                visible: canLogout && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                onClicked: { root.stopCountdown(); root.logoutRequested(); }
                onNavigate: (step) => root.moveFocus(logoutButton, step)
            }
            MoOSUI2ActionButton {
                id: lockButton
                iconName: "system-lock-screen-symbolic"
                text: root.bilingual("قفل الشاشة", "Lock Screen")
                description: root.bilingual("العودة لاحقًا", "Return later")
                visible: root.showAllOptions
                onClicked: { root.stopCountdown(); root.lockScreenRequested(); }
                onNavigate: (step) => root.moveFocus(lockButton, step)
            }
            MoOSUI2ActionButton {
                id: cancelButton
                iconName: "cancel-operation-symbolic"
                text: root.bilingual("إلغاء", "Cancel")
                description: root.bilingual("العودة إلى سطح المكتب", "Back to desktop")
                emphasized: root.showAllOptions
                Layout.topMargin: Kirigami.Units.smallSpacing
                onClicked: root.cancelRequested()
                onNavigate: (step) => root.moveFocus(cancelButton, step)
            }
        }
    }
}
