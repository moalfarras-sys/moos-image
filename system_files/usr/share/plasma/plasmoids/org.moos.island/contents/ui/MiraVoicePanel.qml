pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3
import org.moos.ui as MoUI

Item {
    id: panel
    required property MiraVoiceConnection connection
    required property bool rtl
    required property int motionDuration
    required property string phaseLabel
    signal back()
    signal openMira()
    signal openSettings()
    // This panel sets its own logical direction for every row. Stop the
    // inherited shell mirror from swapping the same edge a second time.
    LayoutMirroring.enabled: false
    LayoutMirroring.childrenInherit: true

    readonly property var design: MoUI.Tokens
    readonly property bool live: connection.active
    readonly property bool busy: connection.pending.length > 0 || connection.stopping
    readonly property bool needsSettings: connection.result === "setup"
        || connection.result === "off" || connection.phase === "off"
    readonly property bool failed: connection.phase === "error"
        || ["unavailable", "failed", "refused", "stopUnconfirmed"].includes(connection.result)
    readonly property color accent: failed ? Kirigami.Theme.negativeTextColor
        : connection.phase === "listening" ? Kirigami.Theme.positiveTextColor
        : Kirigami.Theme.highlightColor

    function local(arabic, english) { return rtl ? arabic : english; }
    function focusAction() { action.forceActiveFocus(Qt.TabFocusReason); }

    readonly property string currentLabel: {
        if (connection.stopping || connection.pending === "stop")
            return local("جارٍ الإيقاف", "Stopping");
        if (connection.pending === "start") return local("جارٍ فتح الاتصال", "Connecting");
        switch (connection.result) {
        case "setup": return local("الصوت بحاجة إلى إعداد", "Voice setup required");
        case "off": return local("الصوت متوقف في ميرا", "Voice is turned off");
        case "busy": return local("الصوت مشغول", "Voice is busy");
        case "stopUnconfirmed": return local("لم تؤكّد ميرا الإيقاف", "Mira hasn’t confirmed the stop");
        case "unavailable": return local("ميرا غير متاحة", "Mira is unavailable");
        case "failed":
        case "refused": return local("تعذّر تشغيل الصوت", "Voice could not be started");
        default: return phaseLabel;
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: panel.design.space3
        layoutDirection: panel.rtl ? Qt.RightToLeft : Qt.LeftToRight

        RowLayout {
            Layout.fillWidth: true
            layoutDirection: panel.rtl ? Qt.RightToLeft : Qt.LeftToRight

            PC3.ToolButton {
                Layout.minimumWidth: panel.design.targetComfortable
                Layout.minimumHeight: panel.design.targetComfortable
                icon.name: panel.rtl ? "go-next-symbolic" : "go-previous-symbolic"
                text: panel.local("رجوع", "Back")
                display: PC3.AbstractButton.IconOnly
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: panel.back()
                Keys.onReturnPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
                Keys.onEnterPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
            }
            PC3.Label {
                Layout.fillWidth: true
                text: panel.local("ميرا", "Mira")
                font.pixelSize: panel.design.typeTitle
                font.weight: Font.DemiBold
                horizontalAlignment: panel.rtl ? Text.AlignRight : Text.AlignLeft
            }
            PC3.ToolButton {
                Layout.minimumWidth: panel.design.targetComfortable
                Layout.minimumHeight: panel.design.targetComfortable
                icon.name: "moos-ai-symbolic"
                text: panel.local("فتح ميرا", "Open Mira")
                display: PC3.AbstractButton.IconOnly
                PC3.ToolTip.text: text
                PC3.ToolTip.visible: hovered
                PC3.ToolTip.delay: Kirigami.Units.toolTipDelay
                onClicked: panel.openMira()
                Keys.onReturnPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
                Keys.onEnterPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 78
            radius: panel.design.radiusCard
            topLeftRadius: panel.rtl ? panel.design.radiusSquare : radius
            topRightRadius: panel.rtl ? radius : panel.design.radiusSquare
            color: Qt.alpha(panel.accent, 0.09)
            border.width: 1
            border.color: Qt.alpha(panel.accent, 0.36)
            Behavior on color { ColorAnimation { duration: panel.motionDuration } }
            Behavior on border.color { ColorAnimation { duration: panel.motionDuration } }

            RowLayout {
                anchors.fill: parent
                anchors.margins: panel.design.space4
                spacing: panel.design.space4
                layoutDirection: panel.rtl ? Qt.RightToLeft : Qt.LeftToRight

                MiraVoiceBars {
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 32
                    phase: panel.connection.stopping || panel.connection.pending === "stop" ? "stopping"
                        : panel.connection.pending === "start" ? "activating" : panel.connection.phase
                    ink: panel.accent
                    duration: panel.motionDuration
                }

                PC3.Label {
                    Layout.fillWidth: true
                    objectName: "miraIslandVoiceStatus"
                    text: panel.currentLabel
                    wrapMode: Text.Wrap
                    font.pixelSize: panel.design.typeTitle
                    font.weight: Font.Medium
                    horizontalAlignment: panel.rtl ? Text.AlignRight : Text.AlignLeft
                    Accessible.ignored: false
                    Accessible.name: text
                    onTextChanged: if (visible && panel.Window.window?.visible) Accessible.announce(text)
                }
            }
        }

        PC3.Button {
            id: action
            objectName: "miraIslandTalk"
            LayoutMirroring.enabled: panel.rtl
            LayoutMirroring.childrenInherit: true
            Layout.fillWidth: true
            Layout.minimumHeight: panel.design.targetComfortable
            text: panel.live && panel.connection.result === "stopUnconfirmed"
                ? panel.local("أعِد طلب الإيقاف", "Retry stop")
                : panel.live ? panel.local("إيقاف المحادثة", "Stop talking")
                : panel.needsSettings ? panel.local("إعداد الصوت في ميرا", "Set up voice in Mira")
                : panel.local("تحدّث مع ميرا", "Talk to Mira")
            icon.name: panel.live ? "media-playback-stop-symbolic"
                : panel.needsSettings ? "moos-settings-symbolic" : "moos-microphone-symbolic"
            icon.width: panel.design.iconControl
            icon.height: panel.design.iconControl
            font.pixelSize: panel.design.typeLabel
            font.weight: Font.DemiBold
            enabled: !panel.busy
            Accessible.description: panel.currentLabel
            onClicked: {
                if (panel.needsSettings && !panel.live) panel.openSettings();
                else panel.connection.request();
            }
            Keys.onReturnPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
            Keys.onEnterPressed: event => { if (!event.isAutoRepeat) clicked(); event.accepted = true; }
        }
    }
}
