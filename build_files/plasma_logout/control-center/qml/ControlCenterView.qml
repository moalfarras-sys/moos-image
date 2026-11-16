// SPDX-License-Identifier: GPL-2.0-or-later
// One native Plasma popup: frequent actions first, history one gesture away.
pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

FocusScope {
    id: center
    property bool opened: false
    property bool reviewMode: false
    property var backendOverride: null
    property int page: 0
    readonly property var backend: backendOverride || liveBackend
    readonly property bool rtl: MoUI.Locale.rtl
    property QtObject notificationHost: QtObject { property bool expanded: center.opened && center.page === 1 }
    signal closeRequested()
    signal toolsRequested()
    signal nativeAppletRequested(string id)
    signal routeRequested(string route)
    function t(ar, en) { return MoUI.Locale.local(ar, en); }
    function openSettings() {
        routeRequested("moos://settings/full");
        if (reviewMode || Qt.openUrlExternally("moos://settings/full")) closeRequested();
        else backend.errorText = t("تعذّر فتح الإعدادات.", "Settings could not be opened.");
    }
    LayoutMirroring.enabled: rtl
    LayoutMirroring.childrenInherit: true
    implicitWidth: 440
    implicitHeight: 700
    Keys.onEscapePressed: closeRequested()
    CenterBackend { id: liveBackend; testing: center.reviewMode; opened: center.opened && !center.reviewMode }
    onOpenedChanged: {
        if (opened) { page = 0; Qt.callLater(() => { if (center.opened && tabs.currentItem) tabs.currentItem.forceActiveFocus(Qt.PopupFocusReason); }); if (Kirigami.Units.longDuration > 1) arrival.restart(); }
        else { arrival.stop(); opacity = 1; }
    }
    NumberAnimation { id: arrival; target: center; property: "opacity"; from: 0; to: 1; duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic }
    Connections { target: Kirigami.Units; function onLongDurationChanged() { if (Kirigami.Units.longDuration <= 1) { arrival.stop(); center.opacity = 1; } } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12
        spacing: 12
        Item {
            objectName: "centerHandle"
            Layout.fillWidth: true; Layout.preferredHeight: 10
            Rectangle { anchors.centerIn: parent; width: 36; height: 4; radius: 2; color: Qt.alpha(Kirigami.Theme.textColor, .22) }
            DragHandler {
                target: null; xAxis.enabled: false; margin: 12
                property real travel: 0
                onActiveTranslationChanged: if (active && activeTranslation.y !== 0) travel = activeTranslation.y
                onCanceled: travel = 0
                onActiveChanged: { if (active) travel = 0; else if (travel > 48) center.closeRequested(); }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            ColumnLayout {
                Layout.fillWidth: true; spacing: 2
                PC3.Label { text: center.t("مركز التحكم", "Control Center"); font.pixelSize: 21; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                PC3.Label {
                    Layout.fillWidth: true; elide: Text.ElideRight
                    text: center.backend.busy ? center.t("جارٍ تحديث الحالات…", "Updating status…") : typeof center.backend.batteryPercent === "number" ? center.t("البطارية ", "Battery ") + center.backend.batteryPercent + "%" + (center.backend.pluggedIn === true ? center.t(" · تشحن", " · Charging") : "") : "MoOS"
                    opacity: .72; font.pixelSize: 12
                }
            }
            PC3.ToolButton { objectName: "centerSettings"; icon.name: "settings-configure"; implicitWidth: 44; implicitHeight: 44; text: center.t("الإعدادات", "Settings"); display: PC3.AbstractButton.IconOnly; onClicked: center.openSettings(); PC3.ToolTip { text: parent.text } }
            PC3.ToolButton { icon.name: "window-close"; implicitWidth: 44; implicitHeight: 44; text: center.t("إغلاق", "Close"); display: PC3.AbstractButton.IconOnly; onClicked: center.closeRequested(); PC3.ToolTip { text: parent.text } }
        }
        PC3.TabBar {
            id: tabs
            objectName: "centerTabs"
            Layout.fillWidth: true
            currentIndex: center.page
            onCurrentIndexChanged: if (currentIndex >= 0 && currentIndex <= 1) center.page = currentIndex
            PC3.TabButton { text: center.t("التحكم", "Controls"); implicitHeight: 44 }
            PC3.TabButton { text: center.t("الإشعارات", "Notifications") + (inbox.unreadCount > 0 ? " · " + inbox.unreadCount : ""); implicitHeight: 44 }
            DragHandler {
                target: null; yAxis.enabled: false
                property real travel: 0
                onActiveTranslationChanged: if (active && activeTranslation.x !== 0) travel = activeTranslation.x
                onCanceled: travel = 0
                onActiveChanged: {
                    if (active) travel = 0;
                    else if (Math.abs(travel) > 48) center.page = Math.max(0, Math.min(1, center.page + (travel * (center.rtl ? -1 : 1) < 0 ? 1 : -1)));
                }
            }
        }
        StackLayout {
            id: pages
            Layout.fillWidth: true; Layout.fillHeight: true
            currentIndex: center.page
            clip: true
            Connections { target: center; function onPageChanged() { if (Kirigami.Units.longDuration > 1) { pages.opacity = 0; pageArrival.restart(); } else { pageArrival.stop(); pages.opacity = 1; } } }
            NumberAnimation { id: pageArrival; target: pages; property: "opacity"; to: 1; duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic }
            QQC2.ScrollView {
                objectName: "centerControls"
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: parent.width; spacing: 14
                    GridLayout {
                        Layout.fillWidth: true; columns: center.width < 360 ? 1 : 2; columnSpacing: 8
                        Repeater {
                            model: [
                                {field:"wifi",label:center.t("واي فاي", "Wi-Fi"),icon:"network-wireless-symbolic",app:"org.kde.plasma.networkmanagement"},
                                {field:"bluetooth",label:center.t("بلوتوث", "Bluetooth"),icon:"network-bluetooth-symbolic",app:"org.kde.plasma.bluetooth"}
                            ]
                            CenterTile {
                                required property var modelData
                                Layout.fillWidth: true
                                label: modelData.label; symbol: modelData.icon
                                measured: center.backend.state[modelData.field] === undefined ? null : center.backend.state[modelData.field]
                                pending: center.backend.busy && center.backend.pendingField === modelData.field
                                toggleEnabled: center.backend.ready && !center.backend.busy
                                detailsAvailable: true; detailsEnabled: !center.backend.busy
                                onClicked: center.backend.request(modelData.field, !measured)
                                onDetailsRequested: center.nativeAppletRequested(modelData.app)
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: sliderGroup.implicitHeight + 24
                        radius: 20; color: Qt.alpha(Kirigami.Theme.textColor, .04)
                        ColumnLayout {
                            id: sliderGroup
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                            spacing: 4
                            CenterSlider { Layout.fillWidth: true; backend: center.backend; field: "brightness"; minimum: 5; label: center.t("الإضاءة", "Brightness"); symbol: "brightness-high" }
                            CenterSlider { Layout.fillWidth: true; backend: center.backend; field: "volume"; label: center.t("الصوت", "Sound"); symbol: "audio-volume-high" }
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true; columns: center.width < 360 ? 1 : 2; rowSpacing: 8; columnSpacing: 8
                        Repeater {
                            model: [{field:"dnd",label:center.t("عدم الإزعاج", "Do not disturb"),icon:"notifications-disabled-symbolic"},{field:"night_light",label:center.t("إضاءة ليلية", "Night Light"),icon:"redshift-status-on"},{field:"muted",label:center.t("كتم الصوت", "Mute sound"),icon:"audio-volume-muted"},{field:"mic_muted",label:center.t("كتم الميكروفون", "Mute microphone"),icon:"microphone-sensitivity-muted"}]
                            CenterTile {
                                required property var modelData
                                Layout.fillWidth: true; implicitHeight: 64
                                label: modelData.label; symbol: modelData.icon
                                measured: center.backend.state[modelData.field] === undefined ? null : center.backend.state[modelData.field]
                                pending: center.backend.busy && center.backend.pendingField === modelData.field
                                toggleEnabled: center.backend.ready && !center.backend.busy
                                onClicked: center.backend.request(modelData.field, !measured)
                            }
                        }
                    }
                    PC3.Label { visible: !!center.backend.errorText; text: center.backend.errorText; color: Kirigami.Theme.negativeTextColor; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    PC3.Button { visible: !!center.backend.errorText; text: center.t("إعادة قراءة الحالة", "Retry device status"); implicitHeight: 44; enabled: !center.backend.busy; onClicked: center.backend.refresh() }
                }
            }
            CenterNotifications {
                id: inbox
                appletInterface: center.notificationHost
                onHistoryRequested: center.nativeAppletRequested("org.kde.plasma.notifications")
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 4
            PC3.Label { text: "MoOS"; font.weight: Font.DemiBold; opacity: .72; Layout.fillWidth: true }
            PC3.ToolButton { objectName: "centerPower"; icon.name: "battery"; text: center.t("الطاقة", "Power"); implicitHeight: 44; onClicked: center.nativeAppletRequested("org.kde.plasma.battery") }
            PC3.ToolButton { objectName: "centerTools"; icon.name: "view-grid-symbolic"; text: center.t("كل الأدوات", "All tools"); implicitHeight: 44; onClicked: center.toolsRequested() }
        }
    }
}
