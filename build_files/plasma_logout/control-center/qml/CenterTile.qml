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
    property var measured: null
    property bool pending: false
    property bool detailsAvailable: false
    property bool toggleEnabled: true
    property bool detailsEnabled: true
    readonly property bool known: typeof measured === "boolean"
    readonly property string statusText: pending ? MoUI.Locale.local("جارٍ التحقق", "Checking") : !known ? MoUI.Locale.local("غير متاح", "Unavailable") : measured ? MoUI.Locale.local("مفعّل", "On") : MoUI.Locale.local("متوقف", "Off")
    signal clicked()
    signal detailsRequested()
    implicitHeight: 80
    implicitWidth: 188
    Rectangle {
        anchors.fill: parent; radius: 20
        color: tile.known && tile.measured ? Qt.alpha(Kirigami.Theme.highlightColor, .17) : Qt.alpha(Kirigami.Theme.textColor, mainButton.hovered ? .08 : .045)
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
            leftPadding: 12; rightPadding: 8
            Accessible.name: tile.label
            Accessible.description: tile.statusText
            activeFocusOnTab: true
            background: null
            contentItem: RowLayout {
                spacing: 8
                Kirigami.Icon { source: tile.symbol; Layout.preferredWidth: 22; Layout.preferredHeight: 22; color: Kirigami.Theme.textColor }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 2
                    PC3.Label { text: tile.label; Layout.fillWidth: true; font.weight: Font.DemiBold; elide: Text.ElideRight }
                    PC3.Label { text: tile.statusText; Layout.fillWidth: true; font.pixelSize: MoUI.Tokens.typeCaption; opacity: .78; elide: Text.ElideRight }
                }
            }
            onClicked: tile.clicked()
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
