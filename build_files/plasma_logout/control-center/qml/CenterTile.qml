// SPDX-License-Identifier: GPL-2.0-or-later
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.components as PC3
import org.kde.kirigami as Kirigami
import org.moos.ui as MoUI

Item {
    id: tile
    property string label: ""
    property string symbol: ""
    property string detailText: ""
    property var measured: null
    property bool pending: false
    property bool compact: false
    property bool invertIndicator: false
    property bool detailsAvailable: false
    property bool toggleEnabled: true
    property bool detailsEnabled: true
    readonly property bool known: typeof measured === "boolean"
    readonly property bool highlighted: known && (invertIndicator ? !measured : measured)
    readonly property string statusText: pending ? MoUI.Locale.local("جارٍ التحقق", "Checking") : !known ? MoUI.Locale.local("غير متاح", "Unavailable") : detailText.length ? detailText : invertIndicator ? (measured ? MoUI.Locale.local("مكتوم", "Muted") : MoUI.Locale.local("غير مكتوم", "Unmuted")) : measured ? MoUI.Locale.local("مفعّل", "On") : MoUI.Locale.local("متوقف", "Off")
    signal clicked()
    signal detailsRequested()
    implicitHeight: compact ? Math.max(104, compactContent.implicitHeight + 4) : 84
    implicitWidth: 188
    Rectangle {
        anchors.fill: parent; radius: MoUI.Tokens.radiusCard
        visible: !tile.compact
        color: tile.highlighted ? Qt.alpha(Kirigami.Theme.highlightColor, .17) : Qt.alpha(Kirigami.Theme.textColor, mainButton.hovered ? .08 : .045)
        border.width: mainButton.activeFocus || detailButton.activeFocus ? 2 : 1
        border.color: mainButton.activeFocus || detailButton.activeFocus ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, .10)
        Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionFast } }
    }
    RowLayout {
        anchors.fill: parent; spacing: 0
        PC3.AbstractButton {
            id: mainButton
            objectName: "centerTileToggle_" + tile.label
            Layout.fillWidth: true; Layout.fillHeight: true
            enabled: tile.known && tile.toggleEnabled
            leftPadding: tile.compact ? 0 : 12; rightPadding: tile.compact ? 0 : 8
            Accessible.name: tile.label
            Accessible.description: tile.statusText
            activeFocusOnTab: true
            background: null
            contentItem: Item {
                scale: mainButton.down && Kirigami.Units.longDuration > 1 ? .98 : 1
                Behavior on scale { NumberAnimation { duration: MoUI.Tokens.motionFast; easing.type: Easing.OutCubic } }
                RowLayout {
                    anchors.fill: parent; spacing: 8; visible: !tile.compact
                    Kirigami.Icon { source: tile.symbol; Layout.preferredWidth: 24; Layout.preferredHeight: 24; color: Kirigami.Theme.textColor }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 2
                        PC3.Label { text: tile.label; Layout.fillWidth: true; font.weight: Font.DemiBold; textFormat: Text.PlainText; elide: Text.ElideRight }
                        PC3.Label { text: tile.statusText; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; opacity: .78; textFormat: Text.PlainText; elide: Text.ElideRight }
                    }
                }
                ColumnLayout {
                    id: compactContent
                    anchors.fill: parent; spacing: 4; visible: tile.compact
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 40; Layout.preferredHeight: 40; radius: 20
                        color: tile.highlighted ? Qt.alpha(Kirigami.Theme.highlightColor, .20) : Qt.alpha(Kirigami.Theme.textColor, mainButton.hovered ? .10 : .055)
                        border.width: mainButton.activeFocus ? 2 : 1
                        border.color: mainButton.activeFocus ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, .10)
                        Kirigami.Icon { anchors.centerIn: parent; width: 22; height: 22; source: tile.symbol; color: Kirigami.Theme.textColor }
                        Behavior on color { ColorAnimation { duration: MoUI.Tokens.motionFast } }
                    }
                    PC3.Label { text: tile.label; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeSecondary; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                    PC3.Label { text: tile.statusText; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; opacity: .78 }
                }
            }
            onClicked: tile.clicked()
            PC3.ToolTip { text: tile.compact ? tile.label + " · " + tile.statusText : "" }
        }
        PC3.ToolButton {
            id: detailButton
            objectName: "centerTileDetails_" + tile.label
            visible: tile.detailsAvailable
            enabled: tile.detailsEnabled
            Layout.preferredWidth: 44; Layout.fillHeight: true
            icon.name: MoUI.Locale.rtl ? "go-previous-symbolic" : "go-next-symbolic"
            text: tile.label + " · " + MoUI.Locale.local("التفاصيل", "Details")
            display: PC3.AbstractButton.IconOnly
            onClicked: tile.detailsRequested()
            PC3.ToolTip { text: parent.text }
            background: null
        }
    }
}
