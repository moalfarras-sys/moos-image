// SPDX-License-Identifier: GPL-2.0-or-later
// Present Plasma's existing notification model, replies, jobs and actions.
// This view does not adopt Globals or create a second notification server.
pragma ComponentBehavior: Bound
import QtQuick
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.notificationmanager as NotificationManager
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: pane
    required property var appletInterface
    signal historyRequested()
    property var modelOverride: null
    readonly property var owner: modelOverride || history
    readonly property bool serviceValid: modelOverride !== null || NotificationManager.Server.valid
    readonly property int presentedCount: list.count
    readonly property int unreadCount: owner.unreadNotificationsCount
    property var representedIds: []
    function updateRepresentedIds() {
        const ids = [];
        if (!modelOverride && appletInterface.expanded === true) {
            for (let i = 0; i < history.count; ++i) {
                const value = history.data(history.index(i, 0), NotificationManager.Notifications.IdRole);
                if (value !== null && value !== undefined) ids.push(String(value));
            }
        }
        if (JSON.stringify(ids) !== JSON.stringify(representedIds)) representedIds = ids;
    }
    function markVisibleRead() {
        if (modelOverride || !visible || appletInterface.expanded !== true) return;
        for (let i = 0; i < history.count; ++i) history.setData(history.index(i, 0), true, NotificationManager.Notifications.ReadRole);
    }
    Connections {
        target: pane.appletInterface
        function onExpandedChanged() { pane.updateRepresentedIds(); if (pane.appletInterface.expanded === true) Qt.callLater(pane.markVisibleRead); }
    }
    Component.onCompleted: Qt.callLater(markVisibleRead)
    onVisibleChanged: if (visible) Qt.callLater(markVisibleRead)
    NotificationManager.Settings { id: settings }
    NotificationManager.Notifications {
        id: history
        groupMode: NotificationManager.Notifications.GroupDisabled
        showExpired: true
        showDismissed: true
        showJobs: settings.jobsInNotifications
        onCountChanged: { pane.updateRepresentedIds(); if (pane.visible) Qt.callLater(pane.markVisibleRead); }
        sortMode: NotificationManager.Notifications.SortByDate
        ignoreBlacklistDuringInhibition: true
        blacklistedDesktopEntries: settings.historyBlacklistedApplications
        blacklistedNotifyRcNames: settings.historyBlacklistedServices
        urgencies: NotificationManager.Notifications.CriticalUrgency
            | NotificationManager.Notifications.NormalUrgency
            | (settings.lowPriorityHistory ? NotificationManager.Notifications.LowUrgency : 0)
    }
    Connections {
        target: history
        function onDataChanged(first, last, roles) {
            if (roles.length === 0 || roles.indexOf(NotificationManager.Notifications.IdRole) >= 0) pane.updateRepresentedIds();
        }
        function onModelReset() { pane.updateRepresentedIds(); }
    }
    PlasmaCore.Action {
        id: clearHistory
        text: MoUI.Locale.local("مسح الإشعارات المنتهية", "Clear expired notifications")
        visible: pane.owner.expiredNotificationsCount > 0
        onTriggered: pane.owner.clear(NotificationManager.Notifications.ClearExpired)
    }
    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        RowLayout {
            Layout.fillWidth: true
            PC3.Label { text: MoUI.Locale.local("الإشعارات", "Notifications"); font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true }
            PC3.ToolButton { icon.name: "go-next-symbolic"; implicitWidth: 44; implicitHeight: 44; Accessible.name: MoUI.Locale.local("كل الإشعارات", "All notifications"); onClicked: pane.historyRequested() }
            PC3.ToolButton { icon.name: "edit-clear-history"; implicitWidth: 44; implicitHeight: 44; enabled: clearHistory.visible; Accessible.name: MoUI.Locale.local("مسح الإشعارات المنتهية", "Clear expired notifications"); onClicked: clearHistory.trigger() }
        }
        ListView {
            id: list
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; spacing: 10
            model: pane.appletInterface.expanded === true ? pane.owner : null
            boundsBehavior: Flickable.StopAtBounds
            QQC2.ScrollBar.vertical: QQC2.ScrollBar {}
            delegate: Rectangle {
                id: notice
                required property int index
                objectName: "centerNotification_" + index
                required property var model
                width: ListView.view.width
                height: content.implicitHeight + 24
                radius: 16
                color: Qt.alpha(Kirigami.Theme.textColor, 0.045)
                border.color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
                function row() { return pane.owner.index(index, 0); }
                function behavior() { return model.resident ? NotificationManager.Notifications.None : NotificationManager.Notifications.Close; }
                ColumnLayout {
                    id: content
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        Kirigami.Icon { source: notice.model.applicationIconName || "notifications"; implicitWidth: 22; implicitHeight: 22 }
                        PC3.Label { Layout.fillWidth: true; text: notice.model.applicationName || ""; textFormat: Text.PlainText; elide: Text.ElideRight; opacity: 0.78; font.pixelSize: 12 }
                        PC3.ToolButton { icon.name: "moos-settings-symbolic"; implicitWidth: 44; implicitHeight: 44; visible: notice.model.configurable === true; Accessible.name: MoUI.Locale.local("إعدادات إشعارات التطبيق", "Application notification settings"); onClicked: pane.owner.configure(notice.row()) }
                        PC3.ToolButton { icon.name: "moos-close-symbolic"; implicitWidth: 44; implicitHeight: 44; visible: notice.model.closable === true; Accessible.name: MoUI.Locale.local("إغلاق الإشعار", "Dismiss notification"); onClicked: pane.owner.close(notice.row()) }
                    }
                    PC3.Label { Layout.fillWidth: true; text: notice.model.summary || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap; font.weight: Font.DemiBold }
                    PC3.Label { Layout.fillWidth: true; text: notice.model.body || ""; visible: text.length > 0; textFormat: Text.StyledText; wrapMode: Text.Wrap; onLinkActivated: link => Qt.openUrlExternally(link) }
                    PC3.ProgressBar { Layout.fillWidth: true; visible: notice.model.type === NotificationManager.Notifications.JobType; from: 0; to: 100; value: notice.model.percentage || 0 }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 4
                        PC3.Button { visible: notice.model.hasDefaultAction === true; text: notice.model.defaultActionLabel || MoUI.Locale.local("فتح", "Open"); implicitHeight: 56; width: Math.min(implicitWidth, parent.width); Accessible.name: text; PC3.ToolTip { text: parent.text } onClicked: pane.owner.invokeDefaultAction(notice.row(), notice.behavior()) }
                        Repeater {
                            model: notice.model.actionNames || []
                            PC3.Button { required property int index; required property string modelData; objectName: "centerNotificationAction_" + notice.index + "_" + index; text: (notice.model.actionLabels || [])[index] || modelData; implicitHeight: 56; width: Math.min(implicitWidth, parent.width); Accessible.name: text; PC3.ToolTip { text: parent.text } onClicked: pane.owner.invokeAction(notice.row(), modelData, notice.behavior()) }
                        }
                        PC3.Button { visible: notice.model.suspendable === true && notice.model.jobState === NotificationManager.Notifications.JobStateRunning; text: MoUI.Locale.local("إيقاف مؤقت", "Pause"); implicitHeight: 56; width: Math.min(implicitWidth, parent.width); Accessible.name: text; PC3.ToolTip { text: parent.text } onClicked: pane.owner.suspendJob(notice.row()) }
                        PC3.Button { visible: notice.model.jobState === NotificationManager.Notifications.JobStateSuspended; text: MoUI.Locale.local("متابعة", "Resume"); implicitHeight: 56; width: Math.min(implicitWidth, parent.width); Accessible.name: text; PC3.ToolTip { text: parent.text } onClicked: pane.owner.resumeJob(notice.row()) }
                        PC3.Button { visible: notice.model.killable === true; text: MoUI.Locale.local("إلغاء المهمة", "Cancel job"); implicitHeight: 56; width: Math.min(implicitWidth, parent.width); Accessible.name: text; PC3.ToolTip { text: parent.text } onClicked: pane.owner.killJob(notice.row()) }
                    }
                    Flow {
                        Layout.fillWidth: true; spacing: 4
                        Repeater {
                            model: notice.model.urls || []
                            PC3.Button {
                                required property url modelData
                                icon.name: "document-open"
                                text: MoUI.Locale.local("فتح المرفق", "Open attachment")
                                implicitHeight: 56
                                width: Math.min(implicitWidth, parent.width)
                                Accessible.name: text
                                onClicked: Qt.openUrlExternally(modelData)
                            }
                        }
                    }
                    RowLayout {
                        visible: notice.model.hasReplyAction === true
                        Layout.fillWidth: true
                        PC3.TextField { id: reply; Layout.fillWidth: true; implicitHeight: 56; placeholderText: MoUI.Locale.local("رد…", "Reply…"); Accessible.name: placeholderText }
                        PC3.ToolButton { icon.name: "document-send"; implicitWidth: 44; implicitHeight: 44; enabled: reply.text.trim().length > 0; Accessible.name: MoUI.Locale.local("إرسال الرد", "Send reply"); onClicked: { pane.owner.reply(notice.row(), reply.text, notice.behavior()); reply.clear(); } }
                    }
                }
                DragHandler {
                    target: null; yAxis.enabled: false
                    property real travel: 0
                    onActiveTranslationChanged: if (active && activeTranslation.x !== 0) travel = activeTranslation.x
                    onCanceled: travel = 0
                    onActiveChanged: {
                        if (active) travel = 0;
                        else if (Math.abs(travel) > 110 && notice.model.closable === true) pane.owner.close(notice.row());
                    }
                }
            }
            PC3.Label {
                anchors.centerIn: parent
                width: parent.width - 24
                visible: list.count === 0
                text: pane.serviceValid ? MoUI.Locale.local("كل شيء هادئ\nلا توجد إشعارات جديدة", "All caught up\nNo new notifications") : MoUI.Locale.local("خدمة الإشعارات غير متاحة", "Notification service unavailable")
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; opacity: 0.78
            }
        }
    }
}
