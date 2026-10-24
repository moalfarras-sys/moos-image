// SPDX-License-Identifier: GPL-2.0-or-later
// One fixed native action per release/key step. Only a measured reread changes
// the displayed device state; refusal is visible and never becomes success.
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

MoUI.Surface {
    id: card
    required property var backend
    readonly property var audio: backend.status.audio || ({})
    readonly property bool available: backend.statusValid && audio.available === true
    property bool busy: false
    property string errorText: ""
    implicitHeight: body.implicitHeight + MoUI.Tokens.space4 * 2
    fillOpacity: 0.035
    function t(ar, en) { return MoUI.Locale.local(ar, en) }
    function sync() {
        if (!level.pressed && !busy)
            level.value = available ? Math.min(100, Math.max(0, audio.volume)) : 0
    }
    function perform(action, argument) {
        if (!available || busy) return
        busy = true
        errorText = ""
        if (!backend.runFixed(action, argument)) {
            busy = false
            errorText = t("تعذّر تغيير الصوت. حاول مرة أخرى.", "Could not change the sound. Try again.")
            sync()
        }
    }
    Component.onCompleted: sync()
    Connections {
        target: card.backend
        function onStatusChanged() { card.sync() }
        function onJobFinished(id, exitCode, output) {
            if (["audio-volume", "audio-mute", "audio-unmute"].indexOf(id) < 0) return
            card.busy = false
            card.errorText = exitCode === 0 ? "" : card.t(
                "تعذّر تغيير الصوت. راجع جهاز الإخراج ثم حاول مجددًا.",
                "Could not change the sound. Check your output device and try again.")
            card.backend.refresh()
            card.sync()
        }
    }
    ColumnLayout {
        id: body
        anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: MoUI.Tokens.space4 }
        spacing: MoUI.Tokens.space4
        RowLayout {
            Layout.fillWidth: true
            Controls.Label {
                Layout.fillWidth: true
                text: card.t("الصوت", "Sound")
                font.pixelSize: MoUI.Tokens.typeBody
                font.weight: Font.DemiBold
            }
            Controls.Label {
                objectName: "moosAudioMeasuredState"
                text: !card.available ? card.t("غير متاح", "Unavailable")
                    : card.audio.muted ? card.t("مكتوم", "Muted")
                    : Number(card.audio.volume).toLocaleString(Qt.locale(), "f", 0) + "%"
                color: Kirigami.Theme.textColor
                font.pixelSize: MoUI.Tokens.typeTitle
                font.weight: Font.DemiBold
            }
            Controls.ToolButton {
                objectName: "moosAudioSettings"
                Layout.minimumWidth: MoUI.Tokens.targetControl
                Layout.minimumHeight: MoUI.Tokens.targetControl
                text: card.t("أجهزة الصوت", "Sound devices")
                icon.name: MoUI.SymbolCatalog.resolve("settings")
                display: Controls.AbstractButton.IconOnly
                Accessible.name: text
                enabled: card.backend.statusValid && (card.backend.status.destinations || {}).audio === true
                onClicked: {
                    if (!card.backend.openRoute("moos://settings/audio"))
                        card.errorText = card.t("تعذّر فتح إعدادات الصوت.", "Could not open sound settings.")
                }
                Controls.ToolTip.visible: hovered
                Controls.ToolTip.text: text
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: MoUI.Tokens.space3
            Controls.ToolButton {
                objectName: "moosAudioMute"
                Layout.minimumWidth: MoUI.Tokens.targetControl
                Layout.minimumHeight: MoUI.Tokens.targetControl
                text: card.audio.muted ? card.t("إلغاء الكتم", "Unmute") : card.t("كتم الصوت", "Mute")
                icon.name: MoUI.SymbolCatalog.resolve(card.audio.muted ? "volume-off" : "volume")
                display: Controls.AbstractButton.IconOnly
                enabled: card.available && !card.busy
                Accessible.name: text
                onClicked: card.perform(card.audio.muted ? "audio-unmute" : "audio-mute", "")
                Controls.ToolTip.visible: hovered
                Controls.ToolTip.text: text
            }
            Controls.Slider {
                id: level
                objectName: "moosAudioVolume"
                Layout.fillWidth: true
                Layout.minimumHeight: MoUI.Tokens.targetControl
                from: 0
                to: 100
                stepSize: 1
                enabled: card.available && !card.busy
                Accessible.name: card.t("مستوى الصوت", "Volume")
                background: Rectangle {
                    x: level.leftPadding
                    y: level.topPadding + (level.availableHeight - height) / 2
                    width: level.availableWidth
                    height: 6
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.16)
                    Rectangle {
                        width: level.position * parent.width
                        x: level.mirrored ? parent.width - width : 0
                        height: parent.height
                        radius: parent.radius
                        color: level.enabled ? Kirigami.Theme.highlightColor
                            : Qt.alpha(Kirigami.Theme.textColor, 0.35)
                    }
                }
                handle: Rectangle {
                    x: level.leftPadding + level.visualPosition * (level.availableWidth - width)
                    y: level.topPadding + (level.availableHeight - height) / 2
                    implicitWidth: 20
                    implicitHeight: 20
                    radius: width / 2
                    color: level.pressed ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
                    border.width: level.visualFocus ? 3 : 0
                    border.color: Kirigami.Theme.highlightColor
                }
                onMoved: if (!pressed) card.perform("audio-volume", String(Math.round(value)))
                onPressedChanged: if (!pressed && card.available && !card.busy)
                    card.perform("audio-volume", String(Math.round(value)))
            }
        }
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: card.errorText.length > 0
            text: card.errorText
            type: Kirigami.MessageType.Error
        }
    }
}
