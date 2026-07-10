/*
    SPDX-FileCopyrightText: 2014 Aleix Pol Gonzalez <aleixpol@blue-systems.com>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: GPL-2.0-or-later

    The host contract and capability rules are derived from KDE Plasma 6.7's
    org.kde.breeze Logout.qml. The visual implementation is original MoOS Nova.
*/

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
            return "إعادة تشغيل MoOS | Restart MoOS";
        case ShutdownType.ShutdownTypeHalt:
            return "إيقاف MoOS | Shut down MoOS";
        case ShutdownType.ShutdownTypeNone:
            return "تسجيل الخروج | Log out";
        default:
            return "ماذا تريد أن تفعل؟ | What would you like to do?";
        }
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
        anchors.fill: parent
        color: Kirigami.Theme.backgroundColor
        opacity: 0.62
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
        color: Kirigami.Theme.backgroundColor
        opacity: 0.92
        border.width: 1
        border.color: Kirigami.Theme.highlightColor

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

                Image {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Kirigami.Units.gridUnit * 5
                    Layout.preferredHeight: Layout.preferredWidth
                    source: "../splash/images/moos-logo.png"
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
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
                    text: "سيتم التنفيذ خلال %1 ثانية | Action in %1 seconds".arg(root.remainingTime)
                    color: Kirigami.Theme.hoverColor
                    visible: countdownTimer.running
                    font.family: "IBM Plex Sans"
                    font.weight: Font.DemiBold
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
                    text: "تحديثات النظام جاهزة للتثبيت | System updates are ready to install"
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

                    NovaActionButton {
                        id: suspendButton
                        Layout.fillWidth: true
                        iconName: "system-suspend"
                        text: "تعليق | Sleep"
                        description: "إبقاء الجلسة | Keep session"
                        visible: root.showAllOptions && spdMethods.SuspendState
                        onClicked: {
                            root.stopCountdown();
                            root.suspendRequested(2);
                        }
                        onNavigate: root.moveFocus(suspendButton, step)
                    }

                    NovaActionButton {
                        id: hibernateButton
                        Layout.fillWidth: true
                        iconName: "system-suspend-hibernate"
                        text: "إسبات | Hibernate"
                        description: "حفظ الجلسة | Save session"
                        visible: root.showAllOptions && spdMethods.HibernateState
                        onClicked: {
                            root.stopCountdown();
                            root.suspendRequested(4);
                        }
                        onNavigate: root.moveFocus(hibernateButton, step)
                    }

                    NovaActionButton {
                        id: rebootButton
                        Layout.fillWidth: true
                        iconName: softwareUpdatePending ? "system-reboot-update" : "system-reboot"
                        text: softwareUpdatePending
                            ? "تحديث وإعادة تشغيل | Update & Restart"
                            : "إعادة التشغيل | Restart"
                        description: softwareUpdatePending
                            ? "تثبيت التحديثات أولًا | Install updates first"
                            : "بدء جلسة جديدة | Start fresh"
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

                    NovaActionButton {
                        id: rebootWithoutUpdatesButton
                        Layout.fillWidth: true
                        iconName: "system-reboot"
                        text: "إعادة التشغيل الآن | Restart now"
                        description: "بدون تحديث | Without updating"
                        visible: maysd && softwareUpdatePending
                            && (sdtype === ShutdownType.ShutdownTypeReboot || root.showAllOptions)
                        onClicked: {
                            root.stopCountdown();
                            root.rebootRequested();
                        }
                        onNavigate: root.moveFocus(rebootWithoutUpdatesButton, step)
                    }

                    NovaActionButton {
                        id: shutdownButton
                        Layout.fillWidth: true
                        iconName: softwareUpdatePending ? "system-shutdown-update" : "system-shutdown"
                        text: softwareUpdatePending
                            ? "تحديث وإيقاف | Update & Shut Down"
                            : "إيقاف التشغيل | Shut Down"
                        description: softwareUpdatePending
                            ? "تثبيت التحديثات أولًا | Install updates first"
                            : "إيقاف الجهاز بأمان | Power off safely"
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

                    NovaActionButton {
                        id: shutdownWithoutUpdatesButton
                        Layout.fillWidth: true
                        iconName: "system-shutdown"
                        text: "إيقاف الآن | Shut down now"
                        description: "بدون تحديث | Without updating"
                        destructive: true
                        visible: maysd && softwareUpdatePending
                            && (sdtype === ShutdownType.ShutdownTypeHalt || root.showAllOptions)
                        onClicked: {
                            root.stopCountdown();
                            root.haltRequested();
                        }
                        onNavigate: root.moveFocus(shutdownWithoutUpdatesButton, step)
                    }

                    NovaActionButton {
                        id: logoutButton
                        Layout.fillWidth: true
                        iconName: "system-log-out"
                        text: "تسجيل الخروج | Log Out"
                        description: "إنهاء الجلسة | End session"
                        visible: canLogout
                            && (sdtype === ShutdownType.ShutdownTypeNone || root.showAllOptions)
                        onClicked: {
                            root.stopCountdown();
                            root.logoutRequested();
                        }
                        onNavigate: root.moveFocus(logoutButton, step)
                    }

                    NovaActionButton {
                        id: lockButton
                        Layout.fillWidth: true
                        iconName: "system-lock-screen"
                        text: "قفل الشاشة | Lock Screen"
                        description: "العودة لاحقًا | Return later"
                        visible: root.showAllOptions
                        onClicked: {
                            root.stopCountdown();
                            root.lockScreenRequested();
                        }
                        onNavigate: root.moveFocus(lockButton, step)
                    }

                    NovaActionButton {
                        id: cancelButton
                        Layout.fillWidth: true
                        iconName: "dialog-cancel"
                        text: "إلغاء | Cancel"
                        description: "العودة إلى سطح المكتب | Back to desktop"
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
