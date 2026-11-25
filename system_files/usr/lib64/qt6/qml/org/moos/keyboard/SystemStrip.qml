// SPDX-FileCopyrightText: 2026 Moalfarras
// SPDX-License-Identifier: GPL-2.0-or-later
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami
import org.kde.plasma.workspace.dbus as DBus
import org.kde.plasma.private.mpris as Mpris

Item {
    id: strip
    property bool rtl: false
    property string language: "en"
    property bool compact: false
    property bool inInputPanel: false
    implicitHeight: 52
    implicitWidth: 312

    // Row and the scroll origin both use the requested reading direction.
    LayoutMirroring.enabled: false
    LayoutMirroring.childrenInherit: true
    Mpris.Mpris2Model { id: media }
    readonly property var player: media.currentPlayer
    readonly property bool playing: !!player && player.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property bool mediaAvailable: !!player && player.canControl && (playing ? player.canPause : player.canPlay)
    readonly property int toolCount: mediaAvailable ? tools.length : tools.length - 1

    function label(ar, en) { return language === "ar" ? ar : en }
    // System Settings owns both hardware pages. KRunner uses KWin’s windows provider, and
    // Mira.Show only raises her window. Voice capture stays a separate action.
    readonly property var tools: [
        { key: "windows", icon: "moos-grid-symbolic", ar: "النوافذ", en: "Windows" },
        { key: "audio", icon: "moos-volume-symbolic", ar: "الصوت", en: "Sound" },
        { key: "display", icon: "moos-system-symbolic", ar: "الشاشة", en: "Display" },
        { key: "mira", icon: "moos-ai-symbolic", ar: "ميرا", en: "Mira" },
        { key: "media" }
    ]

    Flickable {
        id: viewport
        anchors.fill: parent
        clip: true
        contentWidth: Math.max(width, strip.toolCount * 44 + (strip.toolCount - 1) * row.spacing)
        contentHeight: height
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.HorizontalFlick
        Component.onCompleted: if (strip.rtl) contentX = Math.max(0, contentWidth - width)
        Row {
            id: row
            width: viewport.contentWidth
            height: viewport.height
            spacing: 4
            layoutDirection: strip.rtl ? Qt.RightToLeft : Qt.LeftToRight
            Repeater {
                model: strip.tools
                Controls.ToolButton {
                    id: command
                    required property var modelData
                    property bool pending: false
                    property int requestId: 0
                    property bool refused: false
                    objectName: "moosStrip_" + modelData.key
                    visible: modelData.key !== "media" || strip.mediaAvailable
                    height: row.height
                    width: (row.width - (strip.toolCount - 1) * row.spacing) / strip.toolCount
                    Binding on font.pixelSize {
                        when: strip.inInputPanel
                        value: Math.max(Kirigami.Units.gridUnit * 0.82, Math.round(command.height * 0.35))
                    }
                    text: refused ? strip.label("تعذّر الفتح", "Unavailable") : actionLabel
                    readonly property string actionLabel: modelData.key === "media"
                        ? (strip.playing ? strip.label("إيقاف مؤقت", "Pause") : strip.label("تشغيل", "Play")) : strip.label(modelData.ar, modelData.en)
                    Accessible.name: text
                    Accessible.description: actionLabel
                    focusPolicy: strip.inInputPanel ? Qt.NoFocus : Qt.StrongFocus
                    enabled: !pending
                    hoverEnabled: true
                    icon.name: modelData.key === "media"
                        ? (strip.playing ? "moos-pause-symbolic" : "moos-play-symbolic") : modelData.icon
                    readonly property int iconExtent: Math.min(24, Math.round(height * 0.44))
                    icon.width: command.iconExtent
                    icon.height: command.iconExtent
                    display: width >= (strip.compact ? 106 : 88)
                             ? Controls.AbstractButton.TextBesideIcon : Controls.AbstractButton.IconOnly
                    // The Plasma shell can supply an empty desktop ToolButton content item.
                    // Use the same label and symbolic icon in the shell and input panel.
                    contentItem: Item {
                        RowLayout {
                            anchors.centerIn: parent
                            width: Math.min(implicitWidth, parent.width)
                            spacing: 4
                            layoutDirection: strip.rtl ? Qt.RightToLeft : Qt.LeftToRight
                            Kirigami.Icon {
                                source: command.icon.name
                                Layout.preferredWidth: command.iconExtent
                                Layout.preferredHeight: command.iconExtent
                                isMask: true
                                color: Kirigami.Theme.textColor
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: command.display !== Controls.AbstractButton.IconOnly
                                text: command.text
                                font: command.font
                                color: Kirigami.Theme.textColor
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }
                        }
                    }
                    Controls.ToolTip.visible: hovered && display === Controls.AbstractButton.IconOnly
                    Controls.ToolTip.text: text
                    Controls.ToolTip.delay: Kirigami.Units.toolTipDelay
                    background: Rectangle {
                        anchors.fill: parent
                        anchors.margins: 2
                        radius: Math.min(12, height / 3)
                        topLeftRadius: strip.rtl ? 3 : radius
                        topRightRadius: strip.rtl ? radius : 3
                        color: Qt.alpha(Kirigami.Theme.highlightColor,
                                        command.down ? 0.30 : command.hovered || command.visualFocus ? 0.20 : 0.09)
                        border.width: command.visualFocus ? 2 : 1
                        border.color: command.refused ? Kirigami.Theme.negativeTextColor
                            : Qt.alpha(Kirigami.Theme.highlightColor, command.visualFocus ? 1 : 0.32)
                        scale: command.down ? 0.95 : 1
                        Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
                        Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                    }
                    Timer { id: retryLabel; interval: 2200; onTriggered: command.refused = false }
                    // A disconnected session bus can leave the KDE async callback undelivered.
                    Timer { id: deadline; interval: 4000; onTriggered: command.finish(false) }
                    function finish(ok) {
                        deadline.stop()
                        pending = false
                        refused = !ok
                        if (refused) retryLabel.restart()
                    }
                    onClicked: {
                        if (!strip.enabled || !strip.visible || pending) return
                        const key = modelData.key
                        if (key === "media") {
                            if (!strip.mediaAvailable) return
                            if (strip.playing) strip.player.Pause()
                            else strip.player.Play()
                            return
                        }
                        if (key === "audio" || key === "display") {
                            finish(Qt.openUrlExternally(key === "audio" ? "systemsettings:kcm_pulseaudio" : "systemsettings:kcm_kscreen"))
                            return
                        }
                        const mira = key === "mira"
                        if (!mira && key !== "windows") return
                        pending = true
                        const request = ++requestId
                        deadline.restart()
                        const completed = ok => {
                            if (command && command.pending && command.requestId === request) command.finish(ok)
                        }
                        DBus.SessionBus.asyncCall({
                            service: mira ? "org.moos.Mira" : "org.kde.krunner",
                            path: mira ? "/Mira" : "/App",
                            iface: mira ? "org.moos.Mira" : "org.kde.krunner.App",
                            member: mira ? "Show" : "displaySingleRunner",
                            signature: "(s)", arguments: [mira ? "" : "windows"]
                        }, reply => {
                            const raw = reply.value
                            const result = raw && raw.value !== undefined ? raw.value : raw
                            completed(!reply.isError && (!mira || result === "ok"))
                        }, _error => completed(false))
                    }
                }
            }
        }
    }
}
