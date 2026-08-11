/*
    SPDX-FileCopyrightText: 2016 Kai Uwe Broulik <kde@privat.broulik.de>
    SPDX-FileCopyrightText: 2026 Moalfarras

    SPDX-License-Identifier: GPL-2.0-or-later

    MoOS keeps Plasma's proven MPRIS controls and interaction path intact.  The
    visual delta is deliberately small: use the MoOS interface family, and let
    the translated fallback status use the secondary type size.  The upstream
    default-font-plus-one fallback visibly truncated German "No media playing"
    on the real 4K lock screen at 225%; real track titles keep the larger size.
*/

import QtQuick
import QtQuick.Layouts

import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris
import org.moos.ui as MoUI

Item {
    id: root

    readonly property var design: MoUI.Tokens

    visible: instantiator.count > 0
    implicitHeight: Kirigami.Units.gridUnit * 3
    implicitWidth: Kirigami.Units.gridUnit * 16

    Repeater {
        id: instantiator
        model: Mpris.MultiplexerModel { }

        RowLayout {
            id: controlsRow

            anchors.fill: parent
            spacing: 0
            enabled: model.canControl

            Image {
                id: albumArt
                Layout.preferredWidth: height
                Layout.fillHeight: true
                visible: status === Image.Loading || status === Image.Ready
                asynchronous: true
                fillMode: Image.PreserveAspectFit
                source: model.artUrl
                sourceSize.height: height * Screen.devicePixelRatio
            }

            Item {
                implicitWidth: Kirigami.Units.smallSpacing
                implicitHeight: 1
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0

                PlasmaComponents3.Label {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    font.family: root.design.interfaceFamily
                    // A real title is primary content.  The localized stopped
                    // status is secondary and needs the language-safe size.
                    font.pointSize: model.track.length > 0
                        ? Kirigami.Theme.defaultFont.pointSize + 1
                        : Kirigami.Theme.smallFont.pointSize + 1
                    maximumLineCount: 1
                    text: model.track.length > 0
                        ? model.track
                        : (model.playbackStatus > Mpris.PlaybackStatus.Stopped
                            ? i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "No title")
                            : i18ndc("plasma_shell_org.kde.plasma.desktop", "@info:status", "No media playing"))
                    textFormat: Text.PlainText
                    wrapMode: Text.NoWrap
                }

                PlasmaExtras.DescriptiveLabel {
                    Layout.fillWidth: true
                    wrapMode: Text.NoWrap
                    elide: Text.ElideRight
                    text: model.artist || model.identity
                    textFormat: Text.PlainText
                    font.family: root.design.interfaceFamily
                    font.pointSize: Kirigami.Theme.smallFont.pointSize + 1
                    maximumLineCount: 1
                }
            }

            PlasmaComponents3.ToolButton {
                Layout.preferredHeight: Kirigami.Units.gridUnit * 2
                Layout.preferredWidth: Layout.preferredHeight
                visible: model.canGoBack || model.canGoNext
                enabled: model.canGoPrevious
                focusPolicy: Qt.TabFocus
                icon.name: LayoutMirroring.enabled ? "media-skip-forward" : "media-skip-backward"
                onClicked: {
                    fadeoutTimer.running = false
                    model.container.Previous()
                }
                Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button Accessible only", "Previous track")
            }

            PlasmaComponents3.ToolButton {
                Layout.fillHeight: true
                Layout.preferredWidth: height
                focusPolicy: Qt.TabFocus
                icon.name: model.playbackStatus === Mpris.PlaybackStatus.Playing
                    ? "media-playback-pause"
                    : "media-playback-start"
                onClicked: {
                    fadeoutTimer.running = false
                    model.container.PlayPause()
                }
                Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button Accessible only", "Play or Pause media")
            }

            PlasmaComponents3.ToolButton {
                Layout.preferredHeight: Kirigami.Units.gridUnit * 2
                Layout.preferredWidth: Layout.preferredHeight
                visible: model.canGoBack || model.canGoNext
                enabled: model.canGoNext
                focusPolicy: Qt.TabFocus
                icon.name: LayoutMirroring.enabled ? "media-skip-backward" : "media-skip-forward"
                Accessible.name: i18ndc("plasma_shell_org.kde.plasma.desktop", "@action:button Accessible only", "Next track")
                onClicked: {
                    fadeoutTimer.running = false
                    model.container.Next()
                }
            }
        }
    }
}
