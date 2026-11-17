// SPDX-License-Identifier: GPL-2.0-or-later
// Native MoOS system center: controls and notifications share one surface.
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
    property bool controlsCollapsed: false
    readonly property alias representedNotificationIds: inbox.representedIds
    readonly property var backend: backendOverride || liveBackend
    readonly property bool rtl: MoUI.Locale.rtl
    property QtObject notificationHost: QtObject { property bool expanded: center.opened }
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
    implicitWidth: 460
    implicitHeight: 800
    Keys.onEscapePressed: closeRequested()
    CenterBackend { id: liveBackend; testing: center.reviewMode; opened: center.opened && !center.reviewMode }
    onOpenedChanged: {
        if (opened) {
            // Native popup geometry starts at zero before its first layout.
            // Track it until the owner explicitly expands/collapses controls.
            controlsCollapsed = Qt.binding(() => center.height > 0 && center.height < 560);
            Qt.callLater(() => { if (center.opened) settingsButton.forceActiveFocus(Qt.PopupFocusReason); });
            if (Kirigami.Units.longDuration > 1) arrival.restart();
        } else { arrival.stop(); opacity = 1; }
    }
    NumberAnimation { id: arrival; target: center; property: "opacity"; from: 0; to: 1; duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic }
    Connections { target: Kirigami.Units; function onLongDurationChanged() { if (Kirigami.Units.longDuration <= 1) { arrival.stop(); center.opacity = 1; } } }
    Rectangle {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Math.min(130, parent.height)
        radius: MoUI.Tokens.radiusPanel
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(Kirigami.Theme.highlightColor, .09) }
            GradientStop { position: 1; color: "transparent" }
        }
    }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12
        spacing: 10
        Item {
            objectName: "centerHandle"
            Layout.fillWidth: true; Layout.preferredHeight: 10
            Rectangle { anchors.centerIn: parent; width: 36; height: 4; radius: 2; color: Qt.alpha(Kirigami.Theme.textColor, .22) }
            DragHandler {
                target: null; xAxis.enabled: false; margin: 12
                property real travel: 0
                onActiveTranslationChanged: if (active && activeTranslation.y !== 0) travel = activeTranslation.y
                onCanceled: travel = 0
                onActiveChanged: {
                    if (active) travel = 0;
                    else if (travel > 48) center.closeRequested();
                    else if (travel < -48) center.controlsCollapsed = true;
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            ColumnLayout {
                Layout.fillWidth: true; spacing: 2
                PC3.Label { text: center.t("مركز النظام", "System Center"); font.pixelSize: MoUI.Tokens.typeTitle; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                PC3.Label {
                    Layout.fillWidth: true; elide: Text.ElideRight
                    text: "MoOS" + (typeof center.backend.batteryPercent === "number" ? "  ·  " + center.backend.batteryPercent + "%" + (center.backend.pluggedIn === true ? center.t(" · تشحن", " · Charging") : "") : "")
                    opacity: .78; font.pixelSize: MoUI.Tokens.typeSecondary
                }
            }
            PC3.ToolButton {
                objectName: "centerExpandNotifications"
                icon.name: "moos-notification-symbolic"
                implicitWidth: 44; implicitHeight: 44
                checkable: true; checked: center.controlsCollapsed
                text: center.controlsCollapsed ? center.t("إظهار التحكمات", "Show controls") : center.t("توسيع الإشعارات", "Expand notifications")
                display: PC3.AbstractButton.IconOnly
                onClicked: center.controlsCollapsed = !center.controlsCollapsed
                PC3.ToolTip { text: parent.text }
            }
            PC3.ToolButton { id: settingsButton; objectName: "centerSettings"; icon.name: "moos-settings-symbolic"; implicitWidth: 44; implicitHeight: 44; text: center.t("الإعدادات", "Settings"); display: PC3.AbstractButton.IconOnly; onClicked: center.openSettings(); PC3.ToolTip { text: parent.text } }
            PC3.ToolButton { icon.name: "moos-close-symbolic"; implicitWidth: 44; implicitHeight: 44; text: center.t("إغلاق", "Close"); display: PC3.AbstractButton.IconOnly; onClicked: center.closeRequested(); PC3.ToolTip { text: parent.text } }
        }
        Item {
            id: controlsRegion
            objectName: "centerControlsRegion"
            Layout.fillWidth: true
            Layout.preferredHeight: center.controlsCollapsed ? 0 : Math.min(controlsContent.implicitHeight, Math.max(160, center.height * .60))
            enabled: !center.controlsCollapsed
            clip: true
            opacity: center.controlsCollapsed ? 0 : 1
            Behavior on Layout.preferredHeight { NumberAnimation { duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic } }
            Behavior on opacity { NumberAnimation { duration: MoUI.Tokens.motionFast } }
            QQC2.ScrollView {
                objectName: "centerControls"
                anchors.fill: parent
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    id: controlsContent
                    width: parent.width; spacing: 10
                    GridLayout {
                        Layout.fillWidth: true; columns: center.width < 360 ? 1 : 2; columnSpacing: 8; rowSpacing: 8
                        Repeater {
                            model: [
                                {field:"wifi",label:center.t("واي فاي", "Wi-Fi"),icon:"moos-wifi-symbolic",app:"org.kde.plasma.networkmanagement"},
                                {field:"bluetooth",label:center.t("بلوتوث", "Bluetooth"),icon:"moos-bluetooth-symbolic",app:"org.kde.plasma.bluetooth"}
                            ]
                            CenterTile {
                                required property var modelData
                                Layout.fillWidth: true
                                label: modelData.label; symbol: modelData.icon
                                measured: center.backend.state[modelData.field] === undefined ? null : center.backend.state[modelData.field]
                                detailText: measured === true ? (modelData.field === "wifi" && typeof center.backend.wifiConnectionName === "string" ? center.backend.wifiConnectionName : modelData.field === "bluetooth" && typeof center.backend.bluetoothConnectionName === "string" ? center.backend.bluetoothConnectionName : "") : ""
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
                        implicitHeight: sliders.implicitHeight + 20
                        radius: MoUI.Tokens.radiusCard; color: Qt.alpha(Kirigami.Theme.textColor, .04)
                        ColumnLayout {
                            id: sliders
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                            spacing: 0
                            CenterSlider { Layout.fillWidth: true; backend: center.backend; field: "brightness"; minimum: 5; label: center.t("الإضاءة", "Brightness"); symbol: "moos-sun-symbolic"; showDetails: true; onDetailsRequested: center.nativeAppletRequested("org.kde.plasma.brightness") }
                            CenterSlider { Layout.fillWidth: true; backend: center.backend; field: "volume"; label: center.t("الصوت", "Sound"); symbol: "moos-volume-symbolic"; showDetails: true; onDetailsRequested: center.nativeAppletRequested("org.kde.plasma.volume") }
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true; columns: center.width < 360 ? 2 : 3; columnSpacing: 8; rowSpacing: 6
                        Repeater {
                            model: [{field:"dnd",label:center.t("عدم الإزعاج", "Do not disturb"),icon:"moos-notification-symbolic"},{field:"night_light",label:center.t("إضاءة ليلية", "Night Light"),icon:"moos-moon-symbolic"},{field:"mic_muted",label:center.t("الميكروفون", "Microphone"),icon:"moos-microphone-symbolic"}]
                            CenterTile {
                                required property var modelData
                                Layout.fillWidth: true
                                compact: true; invertIndicator: modelData.field === "mic_muted"
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
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Qt.alpha(Kirigami.Theme.textColor, .08) }
        CenterNotifications {
            id: inbox
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 80
            appletInterface: center.notificationHost
            onHistoryRequested: { center.controlsCollapsed = true; center.nativeAppletRequested("org.kde.plasma.notifications"); }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 4
            PC3.ToolButton { objectName: "centerPower"; icon.name: "moos-battery-symbolic"; text: center.t("الطاقة", "Power"); implicitHeight: 48; onClicked: center.nativeAppletRequested("org.kde.plasma.battery") }
            Item { Layout.fillWidth: true }
            PC3.ToolButton { objectName: "centerTools"; icon.name: "view-grid-symbolic"; text: center.t("كل الأدوات", "All tools"); implicitHeight: 48; onClicked: center.toolsRequested() }
        }
    }
}
