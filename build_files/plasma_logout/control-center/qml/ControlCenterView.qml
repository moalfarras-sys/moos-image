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
    property string expandedGroup: "levels"
    readonly property bool foldingAvailable: !backend.busy && typeof backend.activeInteractions === "number" && backend.activeInteractions === 0
    function toggleGroup(group) {
        if (!foldingAvailable || ["levels", "focus"].indexOf(group) < 0) return false;
        expandedGroup = expandedGroup === group ? "" : group;
        return true;
    }
    function percent(field) {
        const value = backend.state[field];
        return typeof value === "number" && Number.isFinite(value) ? "\u2066" + Math.round(value) + "%\u2069" : "—";
    }
    function levelsSummary() {
        const sound = backend.state.muted === true ? t("الصوت مكتوم", "Sound muted") : t("الصوت ", "Sound ") + percent("volume");
        return sound + " · " + t("السطوع ", "Brightness ") + percent("brightness");
    }
    function focusSummary() {
        const muted = backend.state.mic_muted;
        const parts = [t("الميكروفون: ", "Mic: ") + (typeof muted !== "boolean" ? t("غير متاح", "Unavailable") : muted ? t("مكتوم", "Muted") : t("غير مكتوم", "Unmuted"))];
        if (backend.state.dnd === true) parts.push(t("عدم الإزعاج", "Do not disturb"));
        if (backend.state.night_light === true) parts.push(t("إضاءة ليلية", "Night Light"));
        return parts.join(" · ");
    }
    component FoldHeader: PC3.AbstractButton {
        id: fold
        required property string heading
        required property string summary
        required property string symbol
        property bool expanded: false
        readonly property bool stacked: width < 360
        signal disclosureRequested()
        implicitHeight: Math.max(56, foldContent.implicitHeight + topPadding + bottomPadding)
        leftPadding: 12; rightPadding: 12; topPadding: 4; bottomPadding: 4
        enabled: center.foldingAvailable
        activeFocusOnTab: true
        checkable: true; checked: expanded
        Accessible.name: heading
        Accessible.description: summary + " · " + (expanded ? center.t("طي المجموعة", "Collapse group") : center.t("توسيع المجموعة", "Expand group"))
        onClicked: disclosureRequested()
        background: Rectangle {
            radius: MoUI.Tokens.radiusCard
            color: Qt.alpha(Kirigami.Theme.textColor, fold.down ? .07 : fold.hovered ? .045 : 0)
            border.width: fold.activeFocus ? 2 : 0
            border.color: Kirigami.Theme.highlightColor
            Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionFast } }
        }
        contentItem: ColumnLayout {
            id: foldContent
            spacing: fold.stacked ? 2 : 0
            scale: fold.down && Kirigami.Units.longDuration > 1 ? .98 : 1
            Behavior on scale { NumberAnimation { duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic } }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Kirigami.Icon { source: fold.symbol; Layout.preferredWidth: 20; Layout.preferredHeight: 20; color: Kirigami.Theme.textColor }
                PC3.Label { text: fold.heading; Layout.fillWidth: fold.stacked; font.pixelSize: MoUI.Tokens.typeSecondary; font.weight: Font.DemiBold; textFormat: Text.PlainText; elide: Text.ElideRight }
                PC3.Label { visible: !fold.stacked; text: fold.summary; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; opacity: .86; textFormat: Text.PlainText; elide: Text.ElideRight }
                Kirigami.Icon {
                    source: "go-down-symbolic"; Layout.preferredWidth: 20; Layout.preferredHeight: 20
                    color: Kirigami.Theme.textColor; rotation: fold.expanded ? 180 : 0
                    Behavior on rotation { NumberAnimation { duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic } }
                }
            }
            PC3.Label { visible: fold.stacked; text: fold.summary; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; opacity: .86; textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
        }
    }
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
                PC3.Label { text: center.t("مركز التحكم", "Control Center"); font.pixelSize: MoUI.Tokens.typeTitle; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
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
                        implicitHeight: levelsHeader.height + levelsBody.height
                        radius: MoUI.Tokens.radiusCard; color: Qt.alpha(Kirigami.Theme.textColor, .035)
                        border.color: Qt.alpha(Kirigami.Theme.textColor, .08)
                        FoldHeader {
                            id: levelsHeader; objectName: "centerLevelsDisclosure"
                            anchors { left: parent.left; right: parent.right; top: parent.top }
                            height: implicitHeight
                            heading: center.t("الصوت والشاشة", "Sound & display"); symbol: "moos-sun-symbolic"
                            summary: center.levelsSummary()
                            expanded: center.expandedGroup === "levels"
                            onDisclosureRequested: center.toggleGroup("levels")
                        }
                        FocusScope {
                            id: levelsBody; objectName: "centerLevelsBody"
                            anchors { left: parent.left; right: parent.right; top: levelsHeader.bottom }
                            height: center.expandedGroup === "levels" ? sliders.implicitHeight + 20 : 0
                            enabled: center.expandedGroup === "levels"; visible: height > 0; clip: true
                            opacity: enabled ? 1 : 0
                            Behavior on height { NumberAnimation { duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic } }
                            Behavior on opacity { NumberAnimation { duration: MoUI.Tokens.motionFast } }
                            ColumnLayout {
                                id: sliders
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                                spacing: 0
                                CenterSlider { Layout.fillWidth: true; backend: center.backend; field: "brightness"; minimum: 5; label: center.t("سطوع الشاشة", "Screen brightness"); symbol: "moos-sun-symbolic"; showDetails: true; onDetailsRequested: center.nativeAppletRequested("org.kde.plasma.brightness") }
                                CenterSlider { Layout.fillWidth: true; backend: center.backend; field: "volume"; label: center.t("مستوى الصوت", "Sound level"); symbol: "moos-volume-symbolic"; showDetails: true; onDetailsRequested: center.nativeAppletRequested("org.kde.plasma.volume") }
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: focusHeader.height + focusBody.height
                        radius: MoUI.Tokens.radiusCard; color: Qt.alpha(Kirigami.Theme.textColor, .035)
                        border.color: Qt.alpha(Kirigami.Theme.textColor, .08)
                        FoldHeader {
                            id: focusHeader; objectName: "centerFocusDisclosure"
                            anchors { left: parent.left; right: parent.right; top: parent.top }
                            height: implicitHeight
                            heading: center.t("التركيز والخصوصية", "Focus & privacy"); summary: center.focusSummary(); symbol: "moos-microphone-symbolic"
                            expanded: center.expandedGroup === "focus"
                            onDisclosureRequested: center.toggleGroup("focus")
                        }
                        FocusScope {
                            id: focusBody; objectName: "centerFocusBody"
                            anchors { left: parent.left; right: parent.right; top: focusHeader.bottom }
                            height: center.expandedGroup === "focus" ? focusGrid.implicitHeight + 20 : 0
                            enabled: center.expandedGroup === "focus"; visible: height > 0; clip: true
                            opacity: enabled ? 1 : 0
                            Behavior on height { NumberAnimation { duration: MoUI.Tokens.motionGeometry; easing.type: Easing.OutCubic } }
                            Behavior on opacity { NumberAnimation { duration: MoUI.Tokens.motionFast } }
                            GridLayout {
                                id: focusGrid
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                                columns: center.width < 360 ? 2 : 3; columnSpacing: 8; rowSpacing: 6
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
