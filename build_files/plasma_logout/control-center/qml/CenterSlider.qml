// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI
ColumnLayout {
    id: card
    required property var backend
    property string field: "volume"
    property string label: ""
    property string symbol: ""
    property real minimum: 0
    property bool showDetails: false
    signal detailsRequested()
    readonly property var measured: backend.state[field]
    readonly property bool known: typeof measured === "number" && Number.isFinite(measured)
    spacing: 0
    RowLayout {
        Layout.fillWidth: true
        PC3.Label { text: card.label; font.pixelSize: MoUI.Tokens.typeSecondary; Layout.fillWidth: true }
        PC3.Label { text: card.known ? Math.round(card.measured) + "%" : "—"; font.pixelSize: MoUI.Tokens.typeSecondary; font.features: ({tnum:1}) }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 6
        PC3.ToolButton {
            objectName: "centerSoundMute"
            visible: card.field === "volume"
            Layout.preferredWidth: 44; Layout.preferredHeight: 44
            icon.name: card.backend.state.muted === true ? "moos-volume-off-symbolic" : "moos-volume-symbolic"
            text: card.backend.state.muted === true ? MoUI.Locale.local("إلغاء كتم الصوت", "Unmute sound") : MoUI.Locale.local("كتم الصوت", "Mute sound")
            display: PC3.AbstractButton.IconOnly
            enabled: typeof card.backend.state.muted === "boolean" && card.backend.ready && !card.backend.busy
            onClicked: card.backend.request("muted", !card.backend.state.muted)
            PC3.ToolTip { text: parent.text }
        }
        Kirigami.Icon { visible: card.field !== "volume"; source: card.symbol; Layout.preferredWidth: 44; Layout.preferredHeight: 22; color: Kirigami.Theme.textColor }
        PC3.Slider {
            id: slider
            objectName: "centerSlider_" + card.field
            Layout.fillWidth: true; Layout.minimumWidth: 100; Layout.minimumHeight: 44
            from: card.minimum; to: 100; stepSize: 1
            value: card.known ? card.measured : card.minimum
            enabled: card.known && card.backend.ready && !card.backend.busy
            Accessible.name: card.label
            background: Item {
                x: slider.leftPadding; y: slider.topPadding
                width: slider.availableWidth; height: slider.availableHeight
                // Liquid track: a glass channel, a native-accent fill and a
                // specular upper sheen. Paint only; the 44px hit area is unchanged.
                Rectangle {
                    objectName: "centerSliderTrack"
                    anchors.verticalCenter: parent.verticalCenter; width: parent.width
                    height: slider.pressed && Kirigami.Units.longDuration > 1 ? 16 : 12; radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, .10)
                    border.width: 1; border.color: Qt.alpha(Kirigami.Theme.textColor, .06)
                    Behavior on height { NumberAnimation { duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic } }
                    Rectangle {
                        x: slider.mirrored ? parent.width - width : 0
                        width: Math.max(parent.height, slider.position * parent.width); height: parent.height; radius: parent.radius
                        color: Kirigami.Theme.highlightColor
                        opacity: card.known ? 1 : .35
                        Rectangle {
                            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 1; leftMargin: parent.radius * .6; rightMargin: parent.radius * .6 }
                            height: parent.height / 2; radius: height / 2
                            visible: width > 0
                            gradient: Gradient {
                                GradientStop { position: 0; color: Qt.alpha("white", .28) }
                                GradientStop { position: 1; color: "transparent" }
                            }
                        }
                    }
                }
            }
            handle: Item {
                x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
                y: slider.topPadding + (slider.availableHeight - height) / 2
                implicitWidth: 26; implicitHeight: 26
                scale: slider.pressed && Kirigami.Units.longDuration > 1 ? 1.12 : 1
                Behavior on scale { NumberAnimation { duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic } }
                // Soft accent halo while held or focused.
                Rectangle {
                    anchors.centerIn: parent; width: parent.width + 10; height: width; radius: width / 2
                    color: Qt.alpha(Kirigami.Theme.highlightColor, slider.pressed || slider.activeFocus ? .22 : 0)
                    Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionFast } }
                }
                Rectangle {
                    anchors.fill: parent; radius: width / 2
                    color: Kirigami.Theme.backgroundColor
                    border.width: slider.activeFocus ? 3 : 2
                    border.color: Kirigami.Theme.highlightColor
                    Rectangle {
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 3 }
                        height: parent.height * .45; radius: height / 2
                        gradient: Gradient {
                            GradientStop { position: 0; color: Qt.alpha("white", .35) }
                            GradientStop { position: 1; color: "transparent" }
                        }
                    }
                }
            }
            property bool interactionChanged: false
            property bool interactionLease: false
            function commitValue() {
                if (enabled && visible && card.backend.opened)
                    card.backend.request(card.field, Math.round(value));
                else value = Qt.binding(() => card.known ? card.measured : card.minimum);
                interactionChanged = false;
            }
            onMoved: {
                interactionChanged = true;
                if (!pressed) commitValue();
            }
            onPressedChanged: {
                if (pressed && !interactionLease) {
                    interactionLease = true;
                    card.backend.beginInteraction();
                } else if (!pressed) {
                    if (interactionChanged) commitValue();
                    if (interactionLease) { interactionLease = false; card.backend.endInteraction(); }
                }
            }
            Component.onDestruction: if (interactionLease) card.backend.endInteraction()
        }
        PC3.ToolButton {
            visible: card.showDetails
            Layout.preferredWidth: 44; Layout.preferredHeight: 44
            icon.name: MoUI.Locale.rtl ? "go-previous-symbolic" : "go-next-symbolic"
            text: MoUI.Locale.local("تفاصيل ", "Details: ") + card.label
            display: PC3.AbstractButton.IconOnly
            onClicked: card.detailsRequested()
            PC3.ToolTip { text: parent.text }
        }
    }
}
